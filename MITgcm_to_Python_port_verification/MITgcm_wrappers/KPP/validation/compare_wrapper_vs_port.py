#!/usr/bin/env python3
"""
compare_wrapper_vs_port.py - Compare MITgcm wrapper outputs vs Python port outputs

Reads:
- timestep_XXXX/outputs_expected.npz (from Python port)
- timestep_XXXX/wrapper_output.csv (from MITgcm wrapper)

Compares:
- KPPviscAz, KPPdiffKzT, KPPdiffKzS, KPPghat (vertical profiles)
- KPPhbl (scalar)

Reports:
- Max absolute difference
- RMS difference
- Correlation coefficient
- Pass/fail status (with tolerance thresholds)

Usage:
    python compare_wrapper_vs_port.py --validation_dir <path> [--rtol <value>] [--plot]
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
import yaml


def parse_wrapper_csv(csv_file):
    """
    Parse wrapper CSV output.

    Returns
    -------
    dict with keys: KPPviscAz, KPPdiffKzT, KPPdiffKzS, KPPghat (arrays), KPPhbl (scalar)
    """
    with open(csv_file, 'r') as f:
        lines = f.readlines()

    # Find OUTPUT_MIXING lines
    mixing_lines = [l for l in lines if l.startswith('OUTPUT_MIXING')]

    if not mixing_lines:
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


def compare_outputs(expected, wrapper, field_name, rtol=1e-12):
    """
    Compare expected vs wrapper output for a single field.

    Returns
    -------
    dict with: max_abs_diff, rms_diff, correlation, pass_fail
    """
    if expected is None or wrapper is None:
        return {
            'max_abs_diff': np.nan,
            'rms_diff': np.nan,
            'correlation': np.nan,
            'pass': False,
            'reason': 'Missing data'
        }

    # Convert scalars to arrays
    if np.isscalar(expected):
        expected = np.array([expected])
        wrapper = np.array([wrapper])

    # Compute metrics
    diff = wrapper - expected
    max_abs_diff = np.max(np.abs(diff))
    rms_diff = np.sqrt(np.mean(diff**2))

    # Correlation (only for arrays)
    if len(expected) > 1:
        corr = np.corrcoef(expected, wrapper)[0, 1]
    else:
        corr = 1.0 if diff[0] == 0 else np.nan

    # Pass/fail criteria
    max_expected = np.max(np.abs(expected))
    if max_expected > 0:
        rel_diff = max_abs_diff / max_expected
        passed = rel_diff < rtol
        reason = f"rel_diff={rel_diff:.2e}" if not passed else "OK"
    else:
        # Both zero
        passed = max_abs_diff < 1e-15
        reason = f"abs_diff={max_abs_diff:.2e}" if not passed else "OK (both zero)"

    return {
        'max_abs_diff': max_abs_diff,
        'rms_diff': rms_diff,
        'correlation': corr,
        'pass': passed,
        'reason': reason,
        'max_expected': max_expected,
        'max_wrapper': np.max(np.abs(wrapper))
    }


def compare_timestep(timestep_dir, rtol=1e-12):
    """
    Compare wrapper vs port for a single timestep.

    Returns
    -------
    dict with comparison results for each field
    """
    # Load expected outputs (from Python port)
    expected_file = timestep_dir / 'outputs_expected.npz'
    if not expected_file.exists():
        return None

    expected = np.load(expected_file)

    # Load wrapper outputs
    wrapper_file = timestep_dir / 'wrapper_output.csv'
    if not wrapper_file.exists():
        return None

    wrapper = parse_wrapper_csv(wrapper_file)
    if wrapper is None:
        return None

    # Compare each field
    results = {}
    for field in ['KPPviscAz', 'KPPdiffKzT', 'KPPdiffKzS', 'KPPghat', 'KPPhbl']:
        results[field] = compare_outputs(
            expected[field],
            wrapper[field],
            field,
            rtol=rtol
        )

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Compare MITgcm wrapper vs Python KPP port outputs'
    )
    parser.add_argument('--validation_dir', required=True,
                        help='Directory containing timestep subdirectories')
    parser.add_argument('--rtol', type=float, default=1e-12,
                        help='Relative tolerance for pass/fail (default: 1e-12)')
    parser.add_argument('--plot', action='store_true',
                        help='Generate comparison plots')
    parser.add_argument('--verbose', action='store_true',
                        help='Print detailed per-timestep results')

    args = parser.parse_args()

    validation_dir = Path(args.validation_dir)

    # Read manifest
    with open(validation_dir / 'manifest.yaml', 'r') as f:
        manifest = yaml.safe_load(f)

    print(f"Comparing wrapper vs port outputs")
    print(f"Scenario: {manifest['scenario']}")
    print(f"Timesteps: {len(manifest['timesteps'])}")
    print(f"Relative tolerance: {args.rtol:.2e}")
    print("")

    # Compare each timestep
    all_results = {}
    for ts_info in manifest['timesteps']:
        timestep_dir = validation_dir / ts_info['dir']
        results = compare_timestep(timestep_dir, rtol=args.rtol)

        if results is None:
            print(f"  {ts_info['dir']}: ✗ Missing data")
            continue

        all_results[ts_info['step']] = results

        # Print summary
        all_pass = all(r['pass'] for r in results.values())
        status = "✓" if all_pass else "✗"

        if args.verbose or not all_pass:
            print(f"  {ts_info['dir']}: {status}")
            for field, res in results.items():
                print(f"    {field:15s}: max_diff={res['max_abs_diff']:.2e}, "
                      f"rms={res['rms_diff']:.2e}, corr={res['correlation']:.4f}, "
                      f"{res['reason']}")
        else:
            print(f"  {ts_info['dir']}: {status}")

    # Overall summary
    print("")
    print("=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)

    if not all_results:
        print("No results to compare!")
        return 1

    # Aggregate statistics per field
    for field in ['KPPviscAz', 'KPPdiffKzT', 'KPPdiffKzS', 'KPPghat', 'KPPhbl']:
        max_diffs = [r[field]['max_abs_diff'] for r in all_results.values() if not np.isnan(r[field]['max_abs_diff'])]
        rms_diffs = [r[field]['rms_diff'] for r in all_results.values() if not np.isnan(r[field]['rms_diff'])]
        passes = [r[field]['pass'] for r in all_results.values()]

        if max_diffs:
            print(f"\n{field}:")
            print(f"  Max absolute diff: {np.max(max_diffs):.2e} (worst)")
            print(f"  Avg RMS diff:      {np.mean(rms_diffs):.2e}")
            print(f"  Pass rate:         {sum(passes)}/{len(passes)} timesteps")

    # Overall pass/fail
    all_pass = all(
        all(r[field]['pass'] for field in r.keys())
        for r in all_results.values()
    )

    print("")
    if all_pass:
        print("✓ ALL TESTS PASSED!")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    exit(main())
