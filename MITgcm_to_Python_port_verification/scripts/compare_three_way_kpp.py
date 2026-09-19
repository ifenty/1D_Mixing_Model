#!/usr/bin/env python3
"""
Three-way KPP comparison: full-model MITgcm vs. standalone-subroutine
MITgcm (KPPMIX compiled/run in isolation) vs. Python port -- all driven
by the same captured input, per mitgcm_verification_mods/kpp_standalone_driver.

Usage:
  python compare_three_way_kpp.py <full_model_outputs.nc> \
      <standalone_outputs.nc> <python_outputs.nc>
"""

import sys
import numpy as np
import xarray as xr
from pathlib import Path


FIELDS = ['visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat', 'hbl']


def summarize(name: str, a: np.ndarray, b: np.ndarray) -> None:
    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)
    print(
        f"  {name:12s} max_abs={diff.max():.3e} "
        f"median_abs={np.median(diff):.3e} "
        f"max_rel={rel.max():.3e} n_gt_1pct={(rel > 0.01).sum()}/{diff.size}"
    )


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: compare_three_way_kpp.py <full_model_outputs.nc> "
            "<standalone_outputs.nc> <python_outputs.nc>"
        )
        sys.exit(1)

    full = xr.open_dataset(sys.argv[1])
    standalone = xr.open_dataset(sys.argv[2])
    python = xr.open_dataset(sys.argv[3])

    print("=" * 70)
    print("Three-way KPP comparison (same captured input for all three)")
    print("=" * 70)

    print("\n[1] Standalone-subroutine MITgcm vs. full-model MITgcm")
    print("    (same subroutine, same compiler/parameters -- expect")
    print("     floating-point-roundoff agreement, ~1e-14, except where noted)")
    for field in FIELDS:
        summarize(field, full[field].values, standalone[field].values)

    print("\n[2] Standalone-subroutine MITgcm vs. Python port")
    print("    (expect the same tolerance already established for")
    print("     full-model vs. Python, since standalone replays KPPMIX exactly)")
    for field in FIELDS:
        summarize(field, standalone[field].values, python[field].values)

    print("\n[3] Full-model MITgcm vs. Python port (reference comparison)")
    for field in FIELDS:
        summarize(field, full[field].values, python[field].values)


if __name__ == '__main__':
    main()
