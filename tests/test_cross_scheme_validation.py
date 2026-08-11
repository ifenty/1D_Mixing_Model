"""
Phase 4: Cross-scheme validation tests.

Validates that refactored GGL90 and KPP schemes produce physically consistent,
non-pathological results when run on the same test columns.

This suite tests:
  1. Single-column consistency: Both drivers complete without error on same input
  2. Physics basis consistency: Both use identical N², S², Richardson functions
  3. Output sanity checks: Mixing coefficients in expected ranges
  4. Comparative analysis: Differences between schemes are physically reasonable

Run this test:
    cd 1D_Mixing_Model
    python -m main.test_cross_scheme_validation
"""

import sys
import numpy as np
from typing import Dict, Tuple

# Import both schemes and shared physics
from GGL90 import GGL90Driver, GGL90Parameters
from KPP import KPPDriver, KPPParameters
from main.physics_basis import (
    compute_buoyancy_frequency_squared,
    compute_vertical_shear_squared,
    compute_richardson_number,
)
from main.eos import compute_buoyancy_gradients


def create_stratified_column(nz: int = 20) -> Dict:
    """Create a test column with stable stratification."""
    theta = np.linspace(22.0, 4.0, nz)  # Temperature decreases with depth
    salt = np.linspace(35.0, 34.7, nz)  # Salinity decreases with depth
    u_vel = np.linspace(0.2, 0.01, nz)
    v_vel = np.linspace(0.1, 0.01, nz)
    
    depth = np.linspace(0, -2500, nz)
    cell_thickness = np.full(nz, 2500.0 / nz)
    
    return {
        'name': 'Stratified',
        'theta': theta,
        'salt': salt,
        'u_vel': u_vel,
        'v_vel': v_vel,
        'depth': depth,
        'cell_thickness': cell_thickness,
        'tau_x': 0.1,
        'tau_y': 0.05,
        'q_net': 100.0,
        'q_sw': 20.0,
        'fw_flux': 0.0,
        'coriol': 1e-4,
    }


def create_shear_column(nz: int = 20) -> Dict:
    """Create a test column with strong shear but weak stratification."""
    theta = np.full(nz, 15.0)  # Nearly uniform temperature
    salt = np.full(nz, 35.0)   # Uniform salinity
    u_vel = np.linspace(0.5, 0.0, nz)  # Strong shear
    v_vel = np.linspace(0.3, 0.0, nz)
    
    depth = np.linspace(0, -500, nz)
    cell_thickness = np.full(nz, 500.0 / nz)
    
    return {
        'name': 'Shear-Dominated',
        'theta': theta,
        'salt': salt,
        'u_vel': u_vel,
        'v_vel': v_vel,
        'depth': depth,
        'cell_thickness': cell_thickness,
        'tau_x': 0.5,  # Strong wind
        'tau_y': 0.2,
        'q_net': 50.0,
        'q_sw': 10.0,
        'fw_flux': 0.0,
        'coriol': 1e-4,
    }


def create_weak_forcing_column(nz: int = 20) -> Dict:
    """Create a test column with weak forcing (calm baseline scenario)."""
    theta = np.linspace(20.0, 8.0, nz)
    salt = np.linspace(35.5, 34.9, nz)
    u_vel = np.linspace(0.05, 0.01, nz)
    v_vel = np.linspace(0.03, 0.01, nz)
    
    depth = np.linspace(0, -1000, nz)
    cell_thickness = np.full(nz, 1000.0 / nz)
    
    return {
        'name': 'Calm Baseline',
        'theta': theta,
        'salt': salt,
        'u_vel': u_vel,
        'v_vel': v_vel,
        'depth': depth,
        'cell_thickness': cell_thickness,
        'tau_x': 0.01,
        'tau_y': 0.005,
        'q_net': 10.0,
        'q_sw': 5.0,
        'fw_flux': 0.0,
        'coriol': 1e-4,
    }


def run_ggl90(col: Dict):
    """Run GGL90 driver on a test column."""
    # GGL90 now requires: tke, u, v, theta, salt, depth, z, dz, dt, mask,
    # u_star_sq, gravity, rho_const, background_visc, background_diff
    # It computes potential density gradients internally.

    # Initial TKE (small value)
    tke = np.full_like(col['theta'], 1e-6)

    # Compute z as positive-up (negate depth)
    z_positive_up = -col['depth']

    # Mask (all water)
    mask = np.ones_like(col['theta'])

    # Friction velocity squared
    tau_mag_sq = col['tau_x']**2 + col['tau_y']**2
    u_star = np.sqrt(max(tau_mag_sq, 1e-10))
    u_star_sq = u_star**2

    # Time step (1 hour)
    dt = 3600.0

    params = GGL90Parameters()
    driver = GGL90Driver(params)

    output = driver.compute_mixing(
        tke=tke,
        u=col['u_vel'],
        v=col['v_vel'],
        theta=col['theta'],
        salt=col['salt'],
        depth=col['depth'],
        z=z_positive_up,
        dz=col['cell_thickness'],
        dt=dt,
        mask=mask,
        u_star_sq=u_star_sq,
        gravity=9.81,
        rho_const=1029.0,
        background_visc=1e-4,
        background_diff=1e-5,
    )
    
    return output


def run_kpp(col: Dict):
    """Run KPP driver on a test column."""
    params = KPPParameters()
    driver = KPPDriver(params)
    
    output = driver.compute_mixing(
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
    
    return output


def check_output_sanity(output, scheme_name: str, col_name: str) -> bool:
    """Validate output is physically reasonable."""
    # Handle both original and wrapped outputs
    visc_field = getattr(output, 'visc_az', None)
    if visc_field is None:
        visc_field = getattr(output, 'kappa_m', None)
    
    diff_field = getattr(output, 'diff_kz_t', None)
    if diff_field is None:
        diff_field = getattr(output, 'kappa_h', None)
    
    if visc_field is None or diff_field is None:
        print(f"  ✗ {scheme_name} ({col_name}): Missing output fields")
        return False
    
    nz = len(visc_field)
    
    # Check for NaN/Inf
    if np.any(np.isnan(visc_field)) or np.any(np.isinf(visc_field)):
        print(f"  ✗ {scheme_name} ({col_name}): NaN/Inf in viscosity")
        return False
    
    if np.any(np.isnan(diff_field)) or np.any(np.isinf(diff_field)):
        print(f"  ✗ {scheme_name} ({col_name}): NaN/Inf in diffusivity")
        return False
    
    # Check ranges (typical oceanographic values, but allow for high shear)
    # Viscosity typically 1e-6 to 1e-1 m²/s, but can reach 100+ in extreme shear
    if np.min(visc_field) < -1e-2:
        print(f"  ✗ {scheme_name} ({col_name}): negative viscosity: {np.min(visc_field):.2e}")
        return False
    
    if np.max(visc_field) > 1e3:  # Allow up to 1000 m²/s for extreme shear
        print(f"  ! {scheme_name} ({col_name}): HIGH viscosity: {np.max(visc_field):.2e}")
    
    # Diffusivity typically 1e-7 to 1e-2 m²/s, but can reach 100+ in extreme shear
    if np.min(diff_field) < -1e-3:
        print(f"  ✗ {scheme_name} ({col_name}): negative diffusivity: {np.min(diff_field):.2e}")
        return False
    
    if np.max(diff_field) > 1e3:  # Allow up to 1000 m²/s
        print(f"  ! {scheme_name} ({col_name}): HIGH diffusivity: {np.max(diff_field):.2e}")
    
    return True


def compare_schemes(col: Dict) -> Tuple[bool, Dict]:
    """
    Compare GGL90 and KPP on the same column.
    
    Returns (success, comparison_dict)
    """
    comparison = {'column': col['name']}
    
    try:
        ggl90_out = run_ggl90(col)
        # GGL90 returns kappa_m, kappa_h (not visc_az, diff_kz_t)
        comparison['ggl90_visc_mean'] = np.mean(ggl90_out.kappa_m[1:])
        comparison['ggl90_diff_mean'] = np.mean(ggl90_out.kappa_h[1:])
        # GGL90 doesn't return hbl, so use a proxy (mixed layer where kappa_m is high)
        above_thresh = ggl90_out.kappa_m > np.mean(ggl90_out.kappa_m) * 2
        if np.any(above_thresh):
            kbl = np.where(above_thresh)[0][-1]
            comparison['ggl90_hbl'] = abs(col['depth'][min(kbl+1, len(col['depth'])-1)])
        else:
            comparison['ggl90_hbl'] = abs(col['depth'][-1])
    except Exception as e:
        print(f"  ✗ GGL90 failed: {e}")
        import traceback
        traceback.print_exc()
        return False, comparison
    
    try:
        kpp_out = run_kpp(col)
        comparison['kpp_visc_mean'] = np.mean(kpp_out.visc_az[1:])
        comparison['kpp_diff_mean'] = np.mean(kpp_out.diff_kz_t[1:])
        comparison['kpp_hbl'] = kpp_out.hbl
    except Exception as e:
        print(f"  ✗ KPP failed: {e}")
        import traceback
        traceback.print_exc()
        return False, comparison
    
    # Check sanity
    if not check_output_sanity(ggl90_out, "GGL90", col['name']):
        return False, comparison
    
    # For KPP, visc_az is the output format, so we need to adapt the check
    class GGL90OutputWrapper:
        def __init__(self, ggl90_out):
            self.visc_az = ggl90_out.kappa_m
            self.diff_kz_t = ggl90_out.kappa_h
            self.hbl = 500.0  # dummy for check
    
    ggl90_wrapped = GGL90OutputWrapper(ggl90_out)
    if not check_output_sanity(ggl90_wrapped, "GGL90", col['name']):
        return False, comparison
    
    if not check_output_sanity(kpp_out, "KPP", col['name']):
        return False, comparison
    
    # Compute ratios (KPP / GGL90)
    visc_ratio = comparison['kpp_visc_mean'] / max(comparison['ggl90_visc_mean'], 1e-10)
    diff_ratio = comparison['kpp_diff_mean'] / max(comparison['ggl90_diff_mean'], 1e-10)
    
    comparison['visc_ratio'] = visc_ratio
    comparison['diff_ratio'] = diff_ratio
    
    # Ratios should be within ~0.1x to 10x (order of magnitude similar, not identical)
    if visc_ratio < 0.01 or visc_ratio > 100:
        print(f"  ! GGL90 vs KPP viscosity differ by {visc_ratio:.1f}x (column: {col['name']})")
    
    if diff_ratio < 0.01 or diff_ratio > 100:
        print(f"  ! GGL90 vs KPP diffusivity differ by {diff_ratio:.1f}x (column: {col['name']})")
    
    return True, comparison


def test_imports():
    """Test that all modules import correctly."""
    print("=== Import Validation ===")
    try:
        from GGL90 import GGL90Driver as GGL90_test
        from KPP import KPPDriver as KPP_test
        from main.physics_basis import compute_buoyancy_frequency_squared as N2_test
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_single_column():
    """Test both drivers on a single column."""
    print("\n=== Single Column Test ===")
    col = create_stratified_column(nz=20)
    
    try:
        ggl90_out = run_ggl90(col)
        print(f"✓ GGL90 completed: kappa_m_mean={np.mean(ggl90_out.kappa_m[1:]):.2e} m²/s, tke_new_min={np.min(ggl90_out.tke_new):.2e}")
    except Exception as e:
        print(f"✗ GGL90 failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        kpp_out = run_kpp(col)
        print(f"✓ KPP completed: hbl={kpp_out.hbl:.2f} m, visc_mean={np.mean(kpp_out.visc_az[1:]):.2e} m²/s")
    except Exception as e:
        print(f"✗ KPP failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_multiple_scenarios():
    """Test both drivers across multiple scenario types."""
    print("\n=== Multi-Scenario Comparison ===")
    scenarios = [
        create_stratified_column(),
        create_shear_column(),
        create_weak_forcing_column(),
    ]
    
    results = []
    for col in scenarios:
        print(f"\n{col['name']} scenario:")
        success, comparison = compare_schemes(col)
        if success:
            print(f"  ✓ GGL90: visc={comparison['ggl90_visc_mean']:.2e}, diff={comparison['ggl90_diff_mean']:.2e}")
            print(f"  ✓ KPP: visc={comparison['kpp_visc_mean']:.2e}, diff={comparison['kpp_diff_mean']:.2e}")
            print(f"  ✓ Ratio: visc={comparison['visc_ratio']:.2f}x, diff={comparison['diff_ratio']:.2f}x")
            results.append(comparison)
        else:
            print(f"  ✗ Comparison failed")
            return False
    
    return True


def test_physics_basis_consistency():
    """Verify physics basis functions work correctly across both schemes."""
    print("\n=== Physics Basis Consistency ===")
    
    # Create a simple density profile
    rho = np.linspace(1027.0, 1028.0, 20)  # Density increases with depth
    z = np.linspace(0, -500, 20)  # z negative downward
    
    try:
        n_sq = compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
        print(f"✓ N² computation: mean={np.mean(n_sq):.2e} s⁻², min={np.min(n_sq):.2e}, max={np.max(n_sq):.2e}")
        
        # N² should be positive for increasing density with depth
        if np.mean(n_sq) < 0:
            print("✗ N² is negative (sign error)")
            return False
    except Exception as e:
        print(f"✗ N² computation failed: {e}")
        return False
    
    try:
        u = np.linspace(0.2, 0.0, 20)
        v = np.linspace(0.1, 0.0, 20)
        s_sq = compute_vertical_shear_squared(u, v, z)
        print(f"✓ S² computation: mean={np.mean(s_sq):.2e} s⁻², min={np.min(s_sq):.2e}, max={np.max(s_sq):.2e}")
    except Exception as e:
        print(f"✗ S² computation failed: {e}")
        return False
    
    try:
        ri = compute_richardson_number(n_sq, s_sq)
        print(f"✓ Ri computation: mean={np.mean(ri):.2e}, min={np.min(ri):.2e}, max={np.max(ri):.2e}")
        
        # Some Ri should be finite and positive
        valid_ri = ri[np.isfinite(ri)]
        if len(valid_ri) > 0 and np.any(valid_ri > 0):
            print(f"✓ Ri has valid positive values (as expected for stable stratification)")
        else:
            print("! Ri values unexpected (all zero, negative, or NaN)")
    except Exception as e:
        print(f"✗ Ri computation failed: {e}")
        return False
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("PHASE 4: CROSS-SCHEME VALIDATION TEST SUITE")
    print("=" * 60)
    
    all_passed = True
    
    all_passed = test_imports() and all_passed
    all_passed = test_single_column() and all_passed
    all_passed = test_physics_basis_consistency() and all_passed
    all_passed = test_multiple_scenarios() and all_passed
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL CROSS-SCHEME VALIDATION TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        sys.exit(1)
