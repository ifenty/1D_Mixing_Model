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
    # 1DMIX-028: the Python port marks below-real-seafloor padding (in a
    # partially-wet multi-column capture, e.g. global_oce_latlon) as NaN
    # rather than guessing MITgcm's own non-trivial below-seafloor fill
    # (see run_ggl90_from_netcdf_input.py's truncation note) -- exclude
    # those genuinely-not-compared cells here instead of letting NaN
    # silently propagate into every statistic below. Single-column captures
    # (vermix, 1D_ocean_ice_column) never produce any NaN, so this is a
    # no-op for every capture this comparison was previously run against.
    wet = ~np.isnan(b)
    n_excluded = b.size - wet.sum()
    a, b = a[wet], b[wet]
    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)
    excluded_note = f" (excluded {n_excluded} below-seafloor NaN cells)" if n_excluded else ""
    print(
        f"  {name:15s} max_abs={diff.max():.3e} "
        f"median_abs={np.median(diff):.3e} "
        f"max_rel={rel.max():.3e} n_gt_1pct={(rel > 0.01).sum()}/{diff.size}{excluded_note}"
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
