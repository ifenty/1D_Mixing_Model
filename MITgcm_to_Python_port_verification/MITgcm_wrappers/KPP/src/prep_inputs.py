#!/usr/bin/env python3
"""
prep_inputs.py - Convert YAML configs to binary input for KPP Fortran wrapper

Reads initial_conditions.yaml and atmospheric_forcing.yaml, computes derived
grid quantities (rF, rC), and writes a binary file that the Fortran wrapper
can read.

Binary format (big-endian, float64):
  - Nr (int)
  - coriol (float)
  - drF(Nr) - cell thicknesses
  - rF(Nr+1) - interface depths (0 at surface, negative downward)
  - rC(Nr) - cell center depths (negative downward)
  - theta(Nr) - potential temperature [degC]
  - salt(Nr) - salinity [psu]
  - uVel(Nr) - zonal velocity [m/s]
  - vVel(Nr) - meridional velocity [m/s]
  - surfaceForcingU - surface u-momentum forcing [m^2/s^2]
  - surfaceForcingV - surface v-momentum forcing [m^2/s^2]
  - surfaceForcingT - surface heat forcing [degC m/s] (Q_net converted)
  - Qsw - shortwave radiation [W/m^2]
  - EmPmR - freshwater flux [m/s]

Usage:
    python prep_inputs.py --ic <initial_conditions.yaml> \\
                          --forcing <atmospheric_forcing.yaml> \\
                          --physical <physical_parameters.yaml> \\
                          --output <output.bin>
"""

import argparse
import numpy as np
import yaml
from pathlib import Path


def load_yaml(filepath):
    """Load YAML file and return parsed content."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def compute_grid(drF):
    """
    Compute MITgcm vertical grid: rF (interfaces) and rC (cell centers).

    Convention: z positive up, depth negative down
    - rF[0] = 0.0 (surface)
    - rF[k+1] = rF[k] - drF[k] (negative downward)
    - rC[k] = (rF[k] + rF[k+1]) / 2 (cell center)

    Args:
        drF: Cell thicknesses [m], length Nr

    Returns:
        rF: Interface depths [m], length Nr+1 (surface to bottom)
        rC: Cell center depths [m], length Nr
    """
    Nr = len(drF)
    drF_arr = np.array(drF, dtype=np.float64)

    # Interface depths: rF[0]=0 (surface), rF[k+1] = rF[k] - drF[k]
    rF = np.zeros(Nr + 1, dtype=np.float64)
    for k in range(Nr):
        rF[k + 1] = rF[k] - drF_arr[k]

    # Cell center depths: midpoint of interfaces
    rC = (rF[:-1] + rF[1:]) / 2.0

    return rF, rC


def convert_heat_flux_to_temp_flux(q_net, rho_const, heat_capacity_cp):
    """
    Convert net heat flux [W/m^2] to temperature flux [degC m/s].

    MITgcm convention:
        surfaceForcingT = Q_net / (rho_const * Cp)

    where:
        Q_net: positive into ocean [W/m^2]
        rho_const: reference density [kg/m^3]
        Cp: heat capacity [J/kg/K]

    Args:
        q_net: Net heat flux [W/m^2], positive into ocean
        rho_const: Reference density [kg/m^3]
        heat_capacity_cp: Heat capacity [J/kg/K]

    Returns:
        surfaceForcingT: Temperature flux [K m/s] = [degC m/s]
    """
    return q_net / (rho_const * heat_capacity_cp)


def write_binary(output_path, data_dict):
    """
    Write data to binary file in big-endian format.

    Binary layout (all float64 except Nr which is int32):
        Nr (int32)
        coriol (float64)
        drF(Nr)
        rF(Nr+1)
        rC(Nr)
        theta(Nr)
        salt(Nr)
        uVel(Nr)
        vVel(Nr)
        surfaceForcingU (float64)
        surfaceForcingV (float64)
        surfaceForcingT (float64)
        Qsw (float64)
        EmPmR (float64)
    """
    with open(output_path, 'wb') as f:
        # Write Nr as int32
        Nr = np.array([data_dict['Nr']], dtype='>i4')  # big-endian int32
        Nr.tofile(f)

        # Write all float64 arrays in big-endian
        for key in ['coriol', 'drF', 'rF', 'rC', 'theta', 'salt',
                    'uVel', 'vVel', 'surfaceForcingU', 'surfaceForcingV',
                    'surfaceForcingT', 'Qsw', 'EmPmR']:
            arr = np.array(data_dict[key], dtype='>f8')  # big-endian float64
            arr.tofile(f)


def main():
    parser = argparse.ArgumentParser(
        description='Convert YAML configs to binary input for KPP wrapper')
    parser.add_argument('--ic', required=True,
                        help='Path to initial_conditions.yaml')
    parser.add_argument('--forcing', required=True,
                        help='Path to atmospheric_forcing.yaml')
    parser.add_argument('--physical', required=True,
                        help='Path to physical_parameters.yaml')
    parser.add_argument('--output', required=True,
                        help='Output binary file path')

    args = parser.parse_args()

    # Load YAML files
    ic_data = load_yaml(args.ic)
    forcing_data = load_yaml(args.forcing)
    phys_data = load_yaml(args.physical)

    # Extract initial conditions
    ic = ic_data['initial_conditions']
    drF = ic['drF']
    theta = ic['theta']
    salt = ic['salt']
    uVel = ic['u_vel']
    vVel = ic['v_vel']
    coriol = ic['coriol']

    Nr = len(drF)

    # Validate array lengths
    assert len(theta) == Nr, f"theta length {len(theta)} != Nr {Nr}"
    assert len(salt) == Nr, f"salt length {len(salt)} != Nr {Nr}"
    assert len(uVel) == Nr, f"uVel length {len(uVel)} != Nr {Nr}"
    assert len(vVel) == Nr, f"vVel length {len(vVel)} != Nr {Nr}"

    # Compute grid
    rF, rC = compute_grid(drF)

    # Extract forcing
    forcing = forcing_data['atmospheric_forcing']
    tau_x = forcing['tau_x']  # [m^2/s^2]
    tau_y = forcing['tau_y']  # [m^2/s^2]
    q_net = forcing['q_net']  # [W/m^2]
    q_sw = forcing['q_sw']    # [W/m^2]
    fw_flux = forcing['fw_flux']  # [m/s]

    # Extract physical parameters
    phys = phys_data['physical_parameters']
    rho_const = phys['rho_const']
    heat_capacity_cp = phys['heat_capacity_cp']

    # Convert heat flux to temperature flux
    surfaceForcingT = convert_heat_flux_to_temp_flux(
        q_net, rho_const, heat_capacity_cp)

    # Prepare data dictionary
    data = {
        'Nr': Nr,
        'coriol': coriol,
        'drF': drF,
        'rF': rF,
        'rC': rC,
        'theta': theta,
        'salt': salt,
        'uVel': uVel,
        'vVel': vVel,
        'surfaceForcingU': tau_x,
        'surfaceForcingV': tau_y,
        'surfaceForcingT': surfaceForcingT,
        'Qsw': q_sw,
        'EmPmR': fw_flux
    }

    # Write binary file
    write_binary(args.output, data)

    print(f"Successfully wrote binary input to: {args.output}")
    print(f"  Nr = {Nr}")
    print(f"  coriol = {coriol}")
    print(f"  drF: {drF[0]:.2f} to {drF[-1]:.2f} m")
    print(f"  rF: {rF[0]:.2f} to {rF[-1]:.2f} m")
    print(f"  theta: {theta[0]:.2f} to {theta[-1]:.2f} degC")
    print(f"  surfaceForcingT: {surfaceForcingT:.6e} degC*m/s")


if __name__ == '__main__':
    main()
