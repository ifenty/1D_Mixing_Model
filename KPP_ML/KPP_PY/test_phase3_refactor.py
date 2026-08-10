"""
Phase 3 KPP_PY refactoring validation.

Validates that the refactored KPP_PY modules work correctly after
reorganization. Old kpp_core.py and kpp_boundary_layer.py have been
replaced with:
  - kpp_core_driver.py (orchestration)
  - kpp_scheme_specific.py (KPP-specific logic: boundary layer depth, mixing)
  - kpp_routines.py (unchanged: utility functions for Richardson mixing, velocity scales)

Run this to validate the refactored code:
    cd 1D_Mixing_Model
    python -m KPP_ML.KPP_PY.test_phase3_refactor
"""

import sys
import numpy as np
from pathlib import Path

# Import from KPP_PY as a package
from .kpp_parameters import KPPParameters
from .kpp_core_driver import KPPDriver as KPPDriver_NEW


def create_test_column(nz: int = 20):
    """Create a simple test column."""
    # Stratified profile
    theta = np.linspace(22.0, 4.0, nz)  # Temperature decreases with depth
    salt = np.linspace(35.0, 34.7, nz)  # Salinity decreases with depth
    
    # Weak velocity shear
    u_vel = np.linspace(0.2, 0.01, nz)
    v_vel = np.linspace(0.1, 0.01, nz)
    
    # Depth grid (negative, increasing downward)
    depth = np.linspace(0, -2500, nz)
    cell_thickness = np.full(nz, 2500.0 / nz)
    
    return {
        'theta': theta,
        'salt': salt,
        'u_vel': u_vel,
        'v_vel': v_vel,
        'depth': depth,
        'cell_thickness': cell_thickness,
        'tau_x': 0.1,  # Wind stress
        'tau_y': 0.05,
        'q_net': 100.0,  # Heat flux [W/m²]
        'q_sw': 20.0,   # Shortwave component
        'fw_flux': 0.0,  # No freshwater flux
        'coriol': 1e-4,
    }


def run_test_step(driver, col):
    """Run a single KPP computation step."""
    return driver.compute_mixing(
        theta=col['theta'],
        salt=col['salt'],
        u_vel=col['u_vel'],
        v_vel=col['v_vel'],
        depth=col['depth'],
        cell_thickness=col['cell_thickness'],
        tau_x=col['tau_x'],
        tau_y=col['tau_y'],
        q_net=col['q_net'],
        q_sw=col['q_sw'],
        fw_flux=col['fw_flux'],
        coriol=col['coriol'],
    )


def test_import():
    """Test that the refactored driver can be imported."""
    print("✓ Refactored KPPDriver imported successfully")


def test_single_step():
    """Test a single computation step with refactored driver."""
    print("\n=== Single Step Test (Refactored Driver) ===")

    params = KPPParameters()
    col = create_test_column(nz=20)

    try:
        driver_new = KPPDriver_NEW(params)
        output_new = run_test_step(driver_new, col)
        print("✓ Refactored driver completed single step")
    except Exception as e:
        print(f"✗ Refactored driver failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify output structure is correct
    required_fields = ['visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat', 'hbl']
    for field in required_fields:
        if not hasattr(output_new, field):
            print(f"  {field}: MISSING ✗")
            return False
        val = getattr(output_new, field)
        if isinstance(val, np.ndarray):
            print(f"  {field}: shape={val.shape}, dtype={val.dtype} ✓")
        elif isinstance(val, (int, float)):
            print(f"  {field}: scalar={val:.4f} ✓")
        else:
            print(f"  {field}: type={type(val)} ✓")

    return True


if __name__ == '__main__':
    print("KPP_PY Phase 3 Refactoring Validation")
    print("=" * 50)

    test_import()

    if test_single_step():
        print("\n✓ All refactoring validation tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Refactoring validation tests failed!")
        sys.exit(1)
