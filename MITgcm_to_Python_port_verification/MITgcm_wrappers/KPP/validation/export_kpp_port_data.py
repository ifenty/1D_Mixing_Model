#!/usr/bin/env python3
"""
export_kpp_port_data.py - Run Python KPP port and export inputs/outputs for validation

This script:
1. Runs the Python KPP port on a specified scenario
2. Exports inputs (state, forcing, grid) and outputs (mixing coefficients, hbl, ghat)
   at each timestep to a directory
3. Creates a manifest of all timesteps for processing by the wrapper

Usage:
    python export_kpp_port_data.py --scenario <scenario_name> --output_dir <path> --num_steps <N>

Output structure:
    output_dir/
        manifest.yaml              # List of all timesteps and metadata
        timestep_0000/
            inputs.npz             # Numpy arrays: theta, salt, uVel, vVel, forcing, grid
            outputs_expected.npz   # Numpy arrays: KPPviscAz, KPPdiffKzT, KPPdiffKzS, KPPghat, KPPhbl
        timestep_0001/
            ...
"""

import argparse
import numpy as np
import yaml
from pathlib import Path
import sys

# Add the KPP port directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "1D_Mixing_Model"))

from KPP.kpp_core_driver import run_kpp_timestep
from main.grid import create_grid
from main.initial_conditions import load_initial_conditions
from main.atmospheric_forcing import load_atmospheric_forcing
from KPP.kpp_parameters import KPPParameters


def export_timestep_data(timestep_dir, timestep_num, grid, state, forcing, kpp_outputs):
    """
    Export inputs and expected outputs for a single timestep.

    Parameters
    ----------
    timestep_dir : Path
        Directory to save this timestep's data
    timestep_num : int
        Timestep number
    grid : dict
        Grid geometry (drF, rF, rC, Nr)
    state : dict
        Ocean state (theta, salt, uVel, vVel)
    forcing : dict
        Surface forcing (tau_x, tau_y, Q_net, Q_sw, fw_flux)
    kpp_outputs : dict
        KPP outputs (KPPviscAz, KPPdiffKzT, KPPdiffKzS, KPPghat, KPPhbl)
    """
    timestep_dir.mkdir(parents=True, exist_ok=True)

    # Save inputs
    np.savez(
        timestep_dir / 'inputs.npz',
        # Grid
        drF=grid['drF'],
        rF=grid['rF'],
        rC=grid['rC'],
        Nr=grid['Nr'],
        # State
        theta=state['theta'],
        salt=state['salt'],
        uVel=state['uVel'],
        vVel=state['vVel'],
        # Forcing
        surfaceForcingU=forcing.get('tau_x', 0.0),
        surfaceForcingV=forcing.get('tau_y', 0.0),
        surfaceForcingT=forcing.get('Q_net_degC_m_s', 0.0),  # Convert Q_net to degC*m/s
        Qsw=forcing.get('Q_sw', 0.0),
        EmPmR=forcing.get('fw_flux', 0.0),
        # Physical parameters
        coriol=forcing.get('coriolis', 0.0),
        timestep=timestep_num
    )

    # Save expected outputs
    np.savez(
        timestep_dir / 'outputs_expected.npz',
        KPPviscAz=kpp_outputs['KPPviscAz'],
        KPPdiffKzT=kpp_outputs['KPPdiffKzT'],
        KPPdiffKzS=kpp_outputs['KPPdiffKzS'],
        KPPghat=kpp_outputs['KPPghat'],
        KPPhbl=kpp_outputs['KPPhbl'],
        timestep=timestep_num
    )

    print(f"  Exported timestep {timestep_num}: KPPhbl={kpp_outputs['KPPhbl']:.2f}m")


def run_and_export(scenario_config, output_dir, num_steps, export_interval=1):
    """
    Run KPP port and export validation data.

    Parameters
    ----------
    scenario_config : dict
        Configuration for the scenario (ICs, forcing, parameters)
    output_dir : Path
        Output directory for validation data
    num_steps : int
        Number of timesteps to run
    export_interval : int
        Export every N timesteps (default 1 = export all)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running KPP port for {num_steps} timesteps...")
    print(f"Output directory: {output_dir}")

    # Initialize
    grid = create_grid(scenario_config['grid'])
    state = load_initial_conditions(scenario_config['initial_conditions'], grid['Nr'])
    forcing = load_atmospheric_forcing(scenario_config['atmospheric_forcing'])
    kpp_params = KPPParameters(scenario_config.get('kpp_parameters', {}))

    # Track exported timesteps
    manifest = {
        'scenario': scenario_config.get('name', 'unknown'),
        'num_steps': num_steps,
        'export_interval': export_interval,
        'grid': {
            'Nr': int(grid['Nr']),
            'drF': grid['drF'].tolist(),
            'total_depth': float(abs(grid['rF'][-1]))
        },
        'timesteps': []
    }

    # Run and export
    for step in range(num_steps):
        # Run KPP for this timestep
        kpp_outputs = run_kpp_timestep(
            state=state,
            forcing=forcing,
            grid=grid,
            kpp_params=kpp_params,
            dt=scenario_config.get('dt', 3600.0)
        )

        # Export if at export interval
        if step % export_interval == 0:
            timestep_dir = output_dir / f"timestep_{step:04d}"
            export_timestep_data(timestep_dir, step, grid, state, forcing, kpp_outputs)

            manifest['timesteps'].append({
                'step': step,
                'dir': f"timestep_{step:04d}",
                'KPPhbl': float(kpp_outputs['KPPhbl']),
                'max_viscAz': float(np.max(kpp_outputs['KPPviscAz'])),
                'max_diffKzT': float(np.max(kpp_outputs['KPPdiffKzT']))
            })

        # Update state for next timestep (integrate forward)
        # For validation, we might just use the same state each time
        # OR actually integrate the tendencies
        # For now, keep state fixed for each timestep test
        # state = integrate_forward(state, kpp_outputs, dt)

    # Save manifest
    with open(output_dir / 'manifest.yaml', 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False)

    print(f"\nExported {len(manifest['timesteps'])} timesteps")
    print(f"Manifest: {output_dir / 'manifest.yaml'}")


def main():
    parser = argparse.ArgumentParser(
        description='Export Python KPP port data for wrapper validation'
    )
    parser.add_argument('--scenario', required=True,
                        help='Scenario YAML file')
    parser.add_argument('--output_dir', required=True,
                        help='Output directory for validation data')
    parser.add_argument('--num_steps', type=int, default=10,
                        help='Number of timesteps to run')
    parser.add_argument('--export_interval', type=int, default=1,
                        help='Export every N timesteps (default: 1)')

    args = parser.parse_args()

    # Load scenario configuration
    with open(args.scenario, 'r') as f:
        scenario_config = yaml.safe_load(f)

    # Run and export
    run_and_export(
        scenario_config=scenario_config,
        output_dir=args.output_dir,
        num_steps=args.num_steps,
        export_interval=args.export_interval
    )

    print("\n✓ Export complete!")


if __name__ == '__main__':
    main()
