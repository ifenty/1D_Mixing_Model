#!/usr/bin/env python3
"""
Simple comparison script for wrapper vs port outputs
"""

import numpy as np
import sys
from pathlib import Path

def parse_wrapper_csv(csv_file):
    """Parse wrapper CSV output."""
    with open(csv_file, 'r') as f:
        lines = f.readlines()

    # Find OUTPUT_MIXING lines
    mixing_lines = [l for l in lines if l.startswith('OUTPUT_MIXING')]

    if not mixing_lines:
        print("ERROR: No OUTPUT_MIXING lines found")
        return None

    # Parse mixing data
    # Format: OUTPUT_MIXING,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat
    data = []
    for line in mixing_lines:
        parts = line.strip().split(',')
        k = int(parts[3])
        visc_az = float(parts[4])
        diff_kz_s = float(parts[5])
        diff_kz_t = float(parts[6])
        ghat = float(parts[7])
        data.append([k, visc_az, diff_kz_s, diff_kz_t, ghat])

    data = np.array(data)

    # Parse HBL
    hbl_line = [l for l in lines if l.startswith('OUTPUT_HBL')]
    if hbl_line:
        hbl = float(hbl_line[0].strip().split(',')[3])
    else:
        hbl = np.nan

    return {
        'KPPviscAz': data[:, 1],
        'KPPdiffKzS': data[:, 2],
        'KPPdiffKzT': data[:, 3],
        'KPPghat': data[:, 4],
        'KPPhbl': hbl
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_simple.py <test_case_dir>")
        sys.exit(1)

    test_dir = Path(sys.argv[1])

    # Load expected outputs (from Python port)
    expected_file = test_dir / 'outputs_kpp_port.npz'
    expected = np.load(expected_file)

    # Load wrapper outputs
    wrapper_file = test_dir / 'wrapper_output.csv'
    wrapper = parse_wrapper_csv(wrapper_file)

    if wrapper is None:
        print("ERROR: Failed to parse wrapper output")
        sys.exit(1)

    print("=" * 70)
    print("KPP Wrapper vs Port Comparison")
    print("=" * 70)
    print()

    # Compare each field
    fields = ['KPPviscAz', 'KPPdiffKzT', 'KPPdiffKzS', 'KPPghat', 'KPPhbl']

    all_pass = True

    for field in fields:
        exp = expected[field]
        wrp = wrapper[field]

        # Handle scalar vs array
        if np.isscalar(exp):
            exp = np.array([exp])
            wrp = np.array([wrp])

        # Compute differences
        diff = wrp - exp
        max_abs_diff = np.max(np.abs(diff))
        max_expected = np.max(np.abs(exp))

        if max_expected > 0:
            rel_diff = max_abs_diff / max_expected
        else:
            rel_diff = max_abs_diff

        # Pass/fail
        passed = rel_diff < 1e-12
        all_pass = all_pass and passed

        status = "✓ PASS" if passed else "✗ FAIL"

        print(f"{field:15s}: {status}")
        print(f"  Max expected:  {max_expected:.6e}")
        print(f"  Max wrapper:   {np.max(np.abs(wrp)):.6e}")
        print(f"  Max abs diff:  {max_abs_diff:.6e}")
        print(f"  Rel diff:      {rel_diff:.6e}")

        if not passed and len(exp) > 1:
            # Show profile for debugging
            print(f"  Profile comparison (first 5 levels):")
            for i in range(min(5, len(exp))):
                print(f"    k={i}: expected={exp[i]:.6e}, wrapper={wrp[i]:.6e}, diff={diff[i]:.6e}")
        print()

    print("=" * 70)
    if all_pass:
        print("✓ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
