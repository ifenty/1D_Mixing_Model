#!/usr/bin/env python3
"""
Compare a scenario's standalone-Fortran-GGL90_CALC output (parsed via
scripts/parse_mitgcm_ggl90_split.py) against the Python port's own dense
(output_frequency_steps=1) trajectory
(output/<scenario>/ggl90_experiment_dense.npz, produced by
export_scenario_to_ggl90_driver.py) -- 1DMIX-024's scenario-extension
scope, mirroring compare_scenario_standalone.py's role for KPP/1DMIX-023.

Row i (0-indexed, i=0..n_out-1) of the parsed Fortran output's
`mixing`/`tke_after` dict corresponds EXACTLY to the Python dense npz's:
  visc_az[i], diff_kz_s[i] (== diff_kz_t[i]), mixing_length[i], tke[i+1]
(see export_scenario_to_ggl90_driver.py's module docstring for the full
index-alignment derivation/verification).
"""

import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_mitgcm_ggl90_split import parse_mitgcm_ggl90_split  # noqa: E402


FIELD_MAP = [
    ('visc_az', 'visc_az'),
    ('diff_kz', 'diff_kz_s'),
    ('mixing_length', 'mixing_length'),
]


def summarize(name: str, a: np.ndarray, b: np.ndarray) -> dict:
    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)
    stats = {
        'max_abs': float(diff.max()),
        'median_abs': float(np.median(diff)),
        'p95_abs': float(np.percentile(diff, 95)),
        'max_rel': float(rel.max()),
        'n_gt_1pct': int((rel > 0.01).sum()),
        'n_total': int(diff.size),
    }
    print(
        f"  {name:15s} max_abs={stats['max_abs']:.3e} "
        f"median_abs={stats['median_abs']:.3e} p95_abs={stats['p95_abs']:.3e} "
        f"max_rel={stats['max_rel']:.3e} "
        f"n_gt_1pct={stats['n_gt_1pct']}/{stats['n_total']}"
    )
    return stats


def compare(scenario_name: str, output_dir: Path) -> dict:
    dense_npz = output_dir / "ggl90_experiment_dense.npz"
    driver_out = output_dir / "ggl90_standalone_output.txt"

    py = np.load(dense_npz)
    n_out = py['visc_az'].shape[0]
    nz = py['depth'].shape[0]

    inputs_ds, outputs_ds = parse_mitgcm_ggl90_split(driver_out, scenario_name)
    fort_n_out = outputs_ds.sizes['time']
    if fort_n_out != n_out:
        raise ValueError(
            f"{scenario_name}: Fortran driver produced {fort_n_out} timesteps, "
            f"expected {n_out} (from {dense_npz})"
        )

    print(f"\n{'=' * 70}\n{scenario_name} (n_out={n_out}, nz={nz})\n{'=' * 70}")

    results = {}
    for fort_name, py_name in FIELD_MAP:
        fort_arr = outputs_ds[fort_name].isel(x=0, y=0).values  # (time, z)
        py_arr = py[py_name]
        results[py_name] = summarize(py_name, fort_arr, py_arr)

    # TKE: Fortran's tke_after[i] vs Python's tke[i+1] (shifted by one --
    # see module docstring).
    fort_tke_after = outputs_ds['tke_after'].isel(x=0, y=0).values
    py_tke_after = py['tke'][1:n_out + 1]
    results['tke_after'] = summarize('tke_after', fort_tke_after, py_tke_after)

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_scenario_ggl90_standalone.py <scenario_name> [...]")
        sys.exit(1)

    pkg_dir = Path(__file__).resolve().parent.parent.parent / "Vertical_Mixing_Models"
    output_dir_root = pkg_dir / "output"

    all_results = {}
    for scenario_name in sys.argv[1:]:
        output_dir = output_dir_root / scenario_name
        all_results[scenario_name] = compare(scenario_name, output_dir)

    print(f"\n{'=' * 70}\nSUMMARY (max_rel across all fields, all >1% mismatch counts)\n{'=' * 70}")
    any_mismatch = False
    for scenario_name, results in all_results.items():
        worst_max_rel = max(r['max_rel'] for r in results.values())
        total_mismatch = sum(r['n_gt_1pct'] for r in results.values())
        if total_mismatch > 0:
            any_mismatch = True
        print(f"  {scenario_name:28s} worst_max_rel={worst_max_rel:.3e} "
              f"total_n_gt_1pct={total_mismatch}")
    sys.exit(1 if any_mismatch else 0)


if __name__ == '__main__':
    main()
