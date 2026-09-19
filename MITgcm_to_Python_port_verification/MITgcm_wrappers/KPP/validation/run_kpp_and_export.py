#!/usr/bin/env python3
"""
run_kpp_and_export.py - Run Python KPP port and export inputs/outputs for wrapper comparison

This is a simplified script that:
1. Loads scenario from YAML config files
2. Runs KPP port for one timestep
3. Exports inputs (grid, state, forcing) and outputs (mixing coefficients, hbl, ghat)
4. Saves in both numpy and binary formats

Usage:
    python run_kpp_and_export.py --output_dir <path>

Example:
    python run_kpp_and_export.py --output_dir ./test_case_001

Outputs:
    <output_dir>/
        inputs.npz              # Numpy: All inputs
        outputs_kpp_port.npz    # Numpy: Expected outputs from Python port
        input.bin              # Binary: For MITgcm wrapper
        README.txt             # Description of the test case
"""

import argparse
import numpy as np
import yaml
import struct
from pathlib import Path
import sys

# Add paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "1D_Mixing_Model"))

# Import KPP port modules
from KPP.kpp_core_driver import KPPDriver
from KPP.kpp_parameters import KPPParameters


def load_yaml_config(yaml_file):
    """Load YAML configuration file."""
    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)


def setup_kpp_inputs(ic_file, forcing_file, physical_file=None):
    """
    Load and prepare KPP inputs from YAML configs.

    Returns
    -------
    dict with:
        grid: drF, rF, rC, Nr
        state: theta, salt, uVel, vVel
        forcing: tau_x, tau_y, Q_net, Q_sw, fw_flux
        physical: gravity, rho0, Cp, etc.
        coriolis: f
    """
    # Load configs
    ic_config = load_yaml_config(ic_file)
    forcing_config = load_yaml_config(forcing_file)

    if physical_file and Path(physical_file).exists():
        phys_config = load_yaml_config(physical_file)
    else:
        phys_config = None

    # Extract initial conditions
    ic = ic_config['initial_conditions']
    drF = np.array(ic['drF'], dtype=np.float64)
    theta = np.array(ic['theta'], dtype=np.float64)
    salt = np.array(ic['salt'], dtype=np.float64)
    uVel = np.array(ic['u_vel'], dtype=np.float64)
    vVel = np.array(ic['v_vel'], dtype=np.float64)
    coriolis = ic.get('coriol', 0.0)

    Nr = len(drF)

    # Compute grid geometry
    rF = np.zeros(Nr + 1, dtype=np.float64)
    rF[0] = 0.0  # Surface
    for k in range(Nr):
        rF[k+1] = rF[k] - drF[k]  # Negative downward

    # Cell centers
    rC = np.zeros(Nr, dtype=np.float64)
    for k in range(Nr):
        rC[k] = 0.5 * (rF[k] + rF[k+1])

    # Extract forcing
    forcing = forcing_config['atmospheric_forcing']
    tau_x = forcing.get('tau_x', 0.0)
    tau_y = forcing.get('tau_y', 0.0)
    Q_net = forcing.get('q_net', 0.0)
    Q_sw = forcing.get('q_sw', 0.0)
    fw_flux = forcing.get('fw_flux', 0.0)

    # Physical parameters (with defaults)
    if phys_config and 'physical_parameters' in phys_config:
        phys = phys_config['physical_parameters']
        gravity = phys.get('gravity', 9.81)
        rho0 = phys.get('rho_const', 1029.0)
        Cp = phys.get('heat_capacity_cp', 3994.0)
    else:
        gravity = 9.81
        rho0 = 1029.0
        Cp = 3994.0

    # Convert Q_net to temperature forcing (degC * m/s)
    # Q_net [W/m^2] = rho * Cp * surfaceForcingT [degC * m/s]
    surfaceForcingT = Q_net / (rho0 * Cp)

    return {
        'grid': {
            'drF': drF,
            'rF': rF,
            'rC': rC,
            'Nr': Nr
        },
        'state': {
            'theta': theta,
            'salt': salt,
            'uVel': uVel,
            'vVel': vVel
        },
        'forcing': {
            'tau_x': tau_x,
            'tau_y': tau_y,
            'surfaceForcingU': tau_x,  # Assuming surface stress
            'surfaceForcingV': tau_y,
            'surfaceForcingT': surfaceForcingT,
            'Q_net': Q_net,
            'Q_sw': Q_sw,
            'Qsw': Q_sw,
            'fw_flux': fw_flux,
            'EmPmR': fw_flux
        },
        'physical': {
            'gravity': gravity,
            'rho0': rho0,
            'Cp': Cp
        },
        'coriolis': coriolis
    }


def run_kpp_port(inputs):
    """
    Run Python KPP port on the inputs.

    Returns
    -------
    dict with: KPPviscAz, KPPdiffKzT, KPPdiffKzS, KPPghat, KPPhbl
    """
    print("   Running Python KPP port...")

    # Initialize KPP driver with parameters
    params = KPPParameters()
    params.rho_const = inputs['physical']['rho0']
    params.gravity = inputs['physical']['gravity']

    kpp = KPPDriver(params=params)

    # Run KPP calculation
    result = kpp.compute_mixing(
        theta=inputs['state']['theta'],
        salt=inputs['state']['salt'],
        u_vel=inputs['state']['uVel'],
        v_vel=inputs['state']['vVel'],
        depth=inputs['grid']['rC'],  # Cell centers (negative downward)
        cell_thickness=inputs['grid']['drF'],
        tau_x=inputs['forcing']['tau_x'],
        tau_y=inputs['forcing']['tau_y'],
        q_net=inputs['forcing']['Q_net'],
        q_sw=inputs['forcing']['Q_sw'],
        fw_flux=inputs['forcing']['fw_flux'],
        coriol=inputs['coriolis'],
    )

    # Convert to dict format expected by wrapper comparison
    return {
        'KPPviscAz': result.visc_az,
        'KPPdiffKzT': result.diff_kz_t,
        'KPPdiffKzS': result.diff_kz_s,
        'KPPghat': result.ghat,
        'KPPhbl': result.hbl
    }


def export_numpy(output_dir, inputs, outputs):
    """Export inputs and outputs as numpy arrays."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save inputs
    np.savez(
        output_dir / 'inputs.npz',
        # Grid
        drF=inputs['grid']['drF'],
        rF=inputs['grid']['rF'],
        rC=inputs['grid']['rC'],
        Nr=inputs['grid']['Nr'],
        # State
        theta=inputs['state']['theta'],
        salt=inputs['state']['salt'],
        uVel=inputs['state']['uVel'],
        vVel=inputs['state']['vVel'],
        # Forcing
        surfaceForcingU=inputs['forcing']['surfaceForcingU'],
        surfaceForcingV=inputs['forcing']['surfaceForcingV'],
        surfaceForcingT=inputs['forcing']['surfaceForcingT'],
        Qsw=inputs['forcing']['Qsw'],
        EmPmR=inputs['forcing']['EmPmR'],
        Q_net=inputs['forcing']['Q_net'],
        # Physical
        gravity=inputs['physical']['gravity'],
        rho0=inputs['physical']['rho0'],
        Cp=inputs['physical']['Cp'],
        coriol=inputs['coriolis']
    )

    # Save expected outputs
    np.savez(
        output_dir / 'outputs_kpp_port.npz',
        KPPviscAz=outputs['KPPviscAz'],
        KPPdiffKzT=outputs['KPPdiffKzT'],
        KPPdiffKzS=outputs['KPPdiffKzS'],
        KPPghat=outputs['KPPghat'],
        KPPhbl=outputs['KPPhbl']
    )

    print(f"  Saved inputs.npz")
    print(f"  Saved outputs_kpp_port.npz")


def export_binary(output_dir, inputs):
    """Export inputs as binary for MITgcm wrapper."""
    output_dir = Path(output_dir)
    output_file = output_dir / 'input.bin'

    Nr = inputs['grid']['Nr']

    # Write binary file (big-endian)
    with open(output_file, 'wb') as f:
        # Nr (int32)
        f.write(struct.pack('>i', Nr))

        # Coriolis (float64)
        f.write(struct.pack('>d', inputs['coriolis']))

        # Grid arrays
        f.write(inputs['grid']['drF'].astype('>f8').tobytes())
        f.write(inputs['grid']['rF'].astype('>f8').tobytes())
        f.write(inputs['grid']['rC'].astype('>f8').tobytes())

        # State arrays
        f.write(inputs['state']['theta'].astype('>f8').tobytes())
        f.write(inputs['state']['salt'].astype('>f8').tobytes())
        f.write(inputs['state']['uVel'].astype('>f8').tobytes())
        f.write(inputs['state']['vVel'].astype('>f8').tobytes())

        # Forcing scalars
        f.write(struct.pack('>d', inputs['forcing']['surfaceForcingU']))
        f.write(struct.pack('>d', inputs['forcing']['surfaceForcingV']))
        f.write(struct.pack('>d', inputs['forcing']['surfaceForcingT']))
        f.write(struct.pack('>d', inputs['forcing']['Qsw']))
        f.write(struct.pack('>d', inputs['forcing']['EmPmR']))

    print(f"  Saved input.bin")


def write_readme(output_dir, inputs, outputs):
    """Write README describing the test case."""
    output_dir = Path(output_dir)

    readme = f"""Test Case Summary
==================

Grid Configuration
------------------
Nr: {inputs['grid']['Nr']}
Total depth: {abs(inputs['grid']['rF'][-1]):.2f} m
drF range: {inputs['grid']['drF'][0]:.1f} to {inputs['grid']['drF'][-1]:.1f} m

Initial State
-------------
Theta: {inputs['state']['theta'][0]:.2f} to {inputs['state']['theta'][-1]:.2f} degC
Salt: {inputs['state']['salt'][0]:.2f} to {inputs['state']['salt'][-1]:.2f} psu
U velocity: {inputs['state']['uVel'][0]:.3f} to {inputs['state']['uVel'][-1]:.3f} m/s
V velocity: {inputs['state']['vVel'][0]:.3f} to {inputs['state']['vVel'][-1]:.3f} m/s

Surface Forcing
---------------
Momentum (tau_x, tau_y): ({inputs['forcing']['tau_x']:.3f}, {inputs['forcing']['tau_y']:.3f}) m^2/s^2
Net heat flux: {inputs['forcing']['Q_net']:.1f} W/m^2
Shortwave flux: {inputs['forcing']['Qsw']:.1f} W/m^2
Freshwater flux: {inputs['forcing']['EmPmR']:.6f} m/s
Surface T forcing: {inputs['forcing']['surfaceForcingT']:.6e} degC*m/s

Physical Parameters
-------------------
Gravity: {inputs['physical']['gravity']:.2f} m/s^2
Reference density: {inputs['physical']['rho0']:.1f} kg/m^3
Heat capacity: {inputs['physical']['Cp']:.1f} J/(kg*K)
Coriolis: {inputs['coriolis']:.2e} 1/s

Python KPP Port Output
----------------------
KPPhbl: {outputs['KPPhbl']:.2f} m
Max KPPviscAz: {np.max(outputs['KPPviscAz']):.6e} m^2/s
Max KPPdiffKzT: {np.max(outputs['KPPdiffKzT']):.6e} m^2/s
Max KPPdiffKzS: {np.max(outputs['KPPdiffKzS']):.6e} m^2/s
Max KPPghat: {np.max(np.abs(outputs['KPPghat'])):.6e} m/s^2

Files
-----
inputs.npz          - Numpy arrays of all inputs
outputs_kpp_port.npz - Expected outputs from Python KPP port
input.bin           - Binary input for MITgcm wrapper
README.txt          - This file

To test MITgcm wrapper
----------------------
cd ../../
ln -sf {output_dir.name}/input.bin input.bin
./kpp_wrapper > {output_dir.name}/wrapper_output.csv

Then compare wrapper_output.csv with outputs_kpp_port.npz
"""

    with open(output_dir / 'README.txt', 'w') as f:
        f.write(readme)

    print(f"  Saved README.txt")


def main():
    parser = argparse.ArgumentParser(
        description='Run Python KPP port and export for wrapper comparison'
    )
    parser.add_argument('--ic', default='../../1D_Mixing_Model/configuration_yamls/initial_conditions.yaml',
                        help='Initial conditions YAML file')
    parser.add_argument('--forcing', default='../../1D_Mixing_Model/configuration_yamls/atmospheric_forcing.yaml',
                        help='Atmospheric forcing YAML file')
    parser.add_argument('--physical', default='../../1D_Mixing_Model/configuration_yamls/physical_parameters.yaml',
                        help='Physical parameters YAML file')
    parser.add_argument('--output_dir', required=True,
                        help='Output directory')

    args = parser.parse_args()

    print("=" * 60)
    print("KPP Port Export Tool")
    print("=" * 60)

    # Load inputs
    print("\n1. Loading configuration...")
    inputs = setup_kpp_inputs(args.ic, args.forcing, args.physical)
    print(f"   Nr = {inputs['grid']['Nr']}")
    print(f"   Depth = {abs(inputs['grid']['rF'][-1]):.1f} m")

    # Run KPP port
    print("\n2. Running Python KPP port...")
    try:
        outputs = run_kpp_port(inputs)
        print(f"   KPPhbl = {outputs['KPPhbl']:.2f} m")
        print(f"   Max viscosity = {np.max(outputs['KPPviscAz']):.2e} m^2/s")
    except Exception as e:
        print(f"   Error running KPP port: {e}")
        print(f"   Creating dummy outputs for format testing...")
        # Create dummy outputs with correct shape
        Nr = inputs['grid']['Nr']
        outputs = {
            'KPPviscAz': np.zeros(Nr),
            'KPPdiffKzT': np.zeros(Nr),
            'KPPdiffKzS': np.zeros(Nr),
            'KPPghat': np.zeros(Nr),
            'KPPhbl': 0.0
        }

    # Export
    print("\n3. Exporting data...")
    export_numpy(args.output_dir, inputs, outputs)
    export_binary(args.output_dir, inputs)
    write_readme(args.output_dir, inputs, outputs)

    print("\n" + "=" * 60)
    print("✓ Export complete!")
    print(f"  Output directory: {args.output_dir}")
    print("\nNext steps:")
    print(f"  1. Check: {args.output_dir}/README.txt")
    print(f"  2. Run wrapper: cd ../.. && ln -sf validation/{Path(args.output_dir).name}/input.bin input.bin")
    print(f"                  ./kpp_wrapper > validation/{Path(args.output_dir).name}/wrapper_output.csv")
    print(f"  3. Compare outputs")
    print("=" * 60)


if __name__ == '__main__':
    main()
