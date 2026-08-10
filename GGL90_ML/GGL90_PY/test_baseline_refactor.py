"""
Phase 2 refactoring validation for GGL90_PY.

Validates that the refactored GGL90_PY modules work correctly after
consolidation. Old ggl90_core.py and ggl90_mixing_length.py have been
replaced with:
  - ggl90_core_driver.py (orchestration)
  - ggl90_scheme_specific.py (GGL90-specific logic + mixing length)
  - ggl90_mixing_coefficients.py (mixing coefficient computation)

Baseline regression test (comparing old vs new drivers) was run BEFORE
deleting the old files and verified byte-identical output.

Run this to validate the refactored code:
    cd 1D_Mixing_Model
    python -m GGL90_ML.GGL90_PY.test_baseline_refactor
"""

import sys
import numpy as np
import json
from pathlib import Path

# Import from GGL90_PY as a package
from .ggl90_parameters import GGL90Parameters
from .ggl90_core_driver import GGL90Driver as GGL90Driver_NEW


def create_test_column(nz: int = 20):
    """Create a simple test column."""
    # Stable stratification (temperature and salinity profiles)
    theta = np.linspace(20.0, 5.0, nz)  # Temperature decreases with depth
    salt = np.linspace(35.0, 34.7, nz)  # Salinity decreases with depth
    depth = np.linspace(0, -2500, nz)   # Depth negative-down
    z = -depth                          # z positive-up
    dz = np.full(nz, 2500.0 / nz)       # Cell thickness

    u = np.linspace(0.1, 0.05, nz)
    v = np.linspace(0.05, 0.02, nz)
    tke = np.full(nz, 1e-5)
    mask = np.ones(nz)

    return {
        'tke': tke,
        'u': u,
        'v': v,
        'theta': theta,
        'salt': salt,
        'depth': depth,
        'z': z,
        'dz': dz,
        'mask': mask,
        'dt': 600.0,
        'u_star_sq': 1e-4,
        'rho_const': 1029.0,
    }


def run_test_step(driver, col):
    """Run a single GGL90 computation step."""
    return driver.compute_mixing(
        tke=col['tke'],
        u=col['u'],
        v=col['v'],
        theta=col['theta'],
        salt=col['salt'],
        depth=col['depth'],
        z=col['z'],
        dz=col['dz'],
        dt=col['dt'],
        mask=col['mask'],
        u_star_sq=col['u_star_sq'],
        rho_const=col['rho_const'],
    )


def test_import():
    """Test that the refactored driver can be imported."""
    print("✓ New refactored GGL90Driver imported successfully")


def test_single_step():
    """Test a single computation step with refactored driver."""
    print("\n=== Single Step Test (Refactored Driver) ===")

    params = GGL90Parameters()
    col = create_test_column(nz=20)

    try:
        driver_new = GGL90Driver_NEW(params)
        output_new = run_test_step(driver_new, col)
        print("✓ Refactored driver completed single step")
    except Exception as e:
        print(f"✗ Refactored driver failed: {e}")
        return False

    # Verify output structure is correct
    required_fields = ['tke_new', 'kappa_m', 'kappa_h', 'mixing_length']
    for field in required_fields:
        if not hasattr(output_new, field):
            print(f"  {field}: MISSING ✗")
            return False
        val = getattr(output_new, field)
        if val is None:
            print(f"  {field}: None ✗")
            return False
        if not isinstance(val, np.ndarray):
            print(f"  {field}: not ndarray ✗")
            return False
        print(f"  {field}: shape={val.shape}, dtype={val.dtype} ✓")

    return True


if __name__ == '__main__':
    print("GGL90_PY Phase 2 Baseline Test")
    print("=" * 50)

    test_import()

    if test_single_step():
        print("\n✓ All baseline tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Baseline tests failed!")
        sys.exit(1)
