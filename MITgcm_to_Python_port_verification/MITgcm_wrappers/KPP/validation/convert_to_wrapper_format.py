#!/usr/bin/env python3
"""
convert_to_wrapper_format.py - Convert exported KPP port data to wrapper binary format

Reads the numpy .npz files from export_kpp_port_data.py and converts them to
the binary format expected by the MITgcm KPP wrapper.

Usage:
    python convert_to_wrapper_format.py --input_dir <exported_data_dir>

Creates:
    input_dir/timestep_XXXX/input.bin    # Binary input for wrapper
"""

import argparse
import struct
import numpy as np
from pathlib import Path
import yaml


def convert_timestep_to_binary(timestep_dir):
    """
    Convert a single timestep's numpy data to binary format.

    Parameters
    ----------
    timestep_dir : Path
        Directory containing inputs.npz

    Creates
    -------
    input.bin : binary file in the same directory
    """
    # Load numpy inputs
    inputs = np.load(timestep_dir / 'inputs.npz')

    # Extract arrays
    Nr = int(inputs['Nr'])
    drF = inputs['drF'].astype(np.float64)
    rF = inputs['rF'].astype(np.float64)
    rC = inputs['rC'].astype(np.float64)
    theta = inputs['theta'].astype(np.float64)
    salt = inputs['salt'].astype(np.float64)
    uVel = inputs['uVel'].astype(np.float64)
    vVel = inputs['vVel'].astype(np.float64)

    # Extract scalars
    coriol = float(inputs['coriol'])
    surfForcU = float(inputs['surfaceForcingU'])
    surfForcV = float(inputs['surfaceForcingV'])
    surfForcT = float(inputs['surfaceForcingT'])
    Qsw = float(inputs['Qsw'])
    EmPmR = float(inputs['EmPmR'])

    # Validate dimensions
    assert len(drF) == Nr, f"drF length {len(drF)} != Nr {Nr}"
    assert len(rF) == Nr + 1, f"rF length {len(rF)} != Nr+1 {Nr+1}"
    assert len(rC) == Nr, f"rC length {len(rC)} != Nr {Nr}"
    assert len(theta) == Nr, f"theta length {len(theta)} != Nr {Nr}"
    assert len(salt) == Nr, f"salt length {len(salt)} != Nr {Nr}"
    assert len(uVel) == Nr, f"uVel length {len(uVel)} != Nr {Nr}"
    assert len(vVel) == Nr, f"vVel length {len(vVel)} != Nr {Nr}"

    # Write binary file (big-endian, matching wrapper expectations)
    output_file = timestep_dir / 'input.bin'
    with open(output_file, 'wb') as f:
        # Nr (int32)
        f.write(struct.pack('>i', Nr))

        # coriol (float64)
        f.write(struct.pack('>d', coriol))

        # Grid arrays (float64)
        f.write(drF.astype('>f8').tobytes())
        f.write(rF.astype('>f8').tobytes())
        f.write(rC.astype('>f8').tobytes())

        # State arrays (float64)
        f.write(theta.astype('>f8').tobytes())
        f.write(salt.astype('>f8').tobytes())
        f.write(uVel.astype('>f8').tobytes())
        f.write(vVel.astype('>f8').tobytes())

        # Forcing scalars (float64)
        f.write(struct.pack('>d', surfForcU))
        f.write(struct.pack('>d', surfForcV))
        f.write(struct.pack('>d', surfForcT))
        f.write(struct.pack('>d', Qsw))
        f.write(struct.pack('>d', EmPmR))

    return output_file


def main():
    parser = argparse.ArgumentParser(
        description='Convert exported KPP port data to wrapper binary format'
    )
    parser.add_argument('--input_dir', required=True,
                        help='Directory containing exported timesteps')

    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    # Read manifest
    manifest_file = input_dir / 'manifest.yaml'
    if not manifest_file.exists():
        print(f"Error: {manifest_file} not found!")
        print("Run export_kpp_port_data.py first.")
        return 1

    with open(manifest_file, 'r') as f:
        manifest = yaml.safe_load(f)

    print(f"Converting {len(manifest['timesteps'])} timesteps...")
    print(f"Scenario: {manifest['scenario']}")

    # Convert each timestep
    for ts_info in manifest['timesteps']:
        timestep_dir = input_dir / ts_info['dir']
        try:
            output_file = convert_timestep_to_binary(timestep_dir)
            print(f"  ✓ {ts_info['dir']}: {output_file.name}")
        except Exception as e:
            print(f"  ✗ {ts_info['dir']}: {e}")

    print("\n✓ Conversion complete!")
    print(f"\nTo run wrapper on all timesteps:")
    print(f"  cd {input_dir}")
    print(f"  for dir in timestep_*/; do")
    print(f"    echo \"Processing $dir\"")
    print(f"    cp $dir/input.bin ../../input.bin")
    print(f"    ../../kpp_wrapper > $dir/wrapper_output.csv")
    print(f"  done")


if __name__ == '__main__':
    main()
