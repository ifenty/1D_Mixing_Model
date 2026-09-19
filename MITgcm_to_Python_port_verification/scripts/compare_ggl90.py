#!/usr/bin/env python3
"""
Compare MITgcm GGL90 outputs vs. Python GGL90 port outputs (single-step
replay), mirroring scripts/compare_three_way_kpp.py's summary format.

Usage:
  python compare_ggl90.py <mitgcm_outputs.nc> <python_outputs.nc>
"""

import sys
import numpy as np
import xarray as xr


FIELD_MAP = [
    ('visc_az', 'visc_az'),
    ('diff_kz', 'diff_kz'),
    ('mixing_length', 'mixing_length'),
    ('tke_after', 'tke_after'),
]


def summarize(name: str, a: np.ndarray, b: np.ndarray) -> None:
    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)
    print(
        f"  {name:15s} max_abs={diff.max():.3e} "
        f"median_abs={np.median(diff):.3e} "
        f"max_rel={rel.max():.3e} n_gt_1pct={(rel > 0.01).sum()}/{diff.size}"
    )


def main():
    if len(sys.argv) != 3:
        print("Usage: compare_ggl90.py <mitgcm_outputs.nc> <python_outputs.nc>")
        sys.exit(1)

    mit = xr.open_dataset(sys.argv[1])
    py = xr.open_dataset(sys.argv[2])

    print("=" * 70)
    print("GGL90 comparison: MITgcm vs. Python port (single-step replay)")
    print("=" * 70)
    for mit_name, py_name in FIELD_MAP:
        summarize(mit_name, mit[mit_name].values, py[py_name].values)


if __name__ == '__main__':
    main()
