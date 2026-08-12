"""
Unit test to verify potential density gradient implementation.

This test demonstrates the difference between in-situ and potential density
gradients and verifies that the GGL90 port now uses the correct (potential)
formulation matching MITgcm.

Run:
    cd 1D_Mixing_Model
    python -m main.test_potential_density_gradient
"""

import sys
from pathlib import Path

import numpy as np

# Make the repo root importable so `python tests/<file>.py` works standalone
# (pytest resolves this via the root conftest.py instead).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main.eos import compute_ggl90_buoyancy_frequency_squared, jmd95_eos
from main.physics_basis import compute_buoyancy_frequency_squared


def test_deep_water_potential_vs_insitu():
    """
    Test that demonstrates the difference between potential and in-situ
    density gradients in deep water where compressibility matters.
    """
    print("\n=== Test: Potential vs In-Situ Density Gradients ===\n")

    # Create a deep, uniformly stratified column (constant dT/dz, dS/dz)
    # where compressibility effects are significant
    nz = 10
    depth = np.linspace(0, -5000, nz)  # Deep ocean column
    # Stable stratification: warm/light at top, cold/dense at bottom
    theta = np.linspace(10.0, 2.0, nz)  # Temperature decreases with depth
    salt = np.linspace(34.6, 34.9, nz)  # Salinity increases with depth (more dense)

    # Method 1: In-situ density gradient (OLD, INCORRECT method)
    # Compute density at each level's own pressure
    pressure_insitu = -depth  # pressure in dbar (positive, increasing with depth)
    rho_insitu_anom, _, _ = jmd95_eos(theta, salt, pressure_insitu, rho_const=1029.0)
    rho_insitu = rho_insitu_anom + 1029.0

    # Use the old physics_basis function (which just takes pre-computed rho)
    # z "positive up" means z increases upward. Since depth is negative-down,
    # z = depth (both are negative-down, but moving upward increases z toward 0)
    z_positive_up = depth
    n2_insitu = compute_buoyancy_frequency_squared(
        rho_insitu, z_positive_up, gravity=9.81, rho_0=1029.0
    )

    # Method 2: Potential density gradient (NEW, CORRECT method)
    # Uses compute_ggl90_buoyancy_frequency_squared which evaluates
    # water from adjacent levels at a common reference pressure
    n2_potential = compute_ggl90_buoyancy_frequency_squared(
        theta, salt, depth, rho_const=1029.0, gravity=9.81, use_jmd95=True
    )

    # Compare the two methods
    print("Depth (m) | N² (in-situ) | N² (potential) | Difference | % Difference")
    print("-" * 75)

    for k in range(1, nz):
        diff = n2_potential[k] - n2_insitu[k]
        if abs(n2_insitu[k]) > 1e-10:
            pct_diff = 100.0 * diff / n2_insitu[k]
        else:
            pct_diff = 0.0

        print(f"{depth[k]:8.1f}  | {n2_insitu[k]:12.6e} | {n2_potential[k]:12.6e} | "
              f"{diff:10.3e} | {pct_diff:6.2f}%")

    # Verify that:
    # 1. Both methods give positive N² (stable stratification)
    assert np.all(n2_insitu[1:] > 0), "In-situ N² should be positive"
    assert np.all(n2_potential[1:] > 0), "Potential N² should be positive"

    # 2. In-situ N² is larger than potential N² in deep water
    #    (compressibility makes water appear more stable)
    deep_indices = np.where(depth < -1000)[0]
    if len(deep_indices) > 0:
        mean_diff_deep = np.mean(n2_insitu[deep_indices] - n2_potential[deep_indices])
        print(f"\nMean difference in deep water (< -1000m): {mean_diff_deep:.6e} s⁻²")
        assert mean_diff_deep > 0, \
            "In-situ N² should be larger than potential N² in deep water"

    # 3. The difference is significant (> 1% in deep water)
    if len(deep_indices) > 0:
        mean_pct_diff = 100.0 * mean_diff_deep / np.mean(n2_insitu[deep_indices])
        print(f"Mean percentage difference in deep water: {mean_pct_diff:.2f}%")
        assert mean_pct_diff > 1.0, \
            "Difference should be > 1% in deep water"

    print("\n✓ Potential density gradient implementation verified")
    print("  - In-situ gradients overestimate stratification in deep water")
    print("  - Potential gradients correctly remove compressibility effects")


def test_shallow_water_equivalence():
    """
    Test that potential and in-situ gradients nearly agree in a thin surface
    layer, where the pressure (hence compressibility) correction is small.

    The in-situ vs potential N^2 difference is a compressibility effect that
    grows monotonically with depth (empirically ~1.7% over a 5 m column, ~6%
    over 20 m, ~25% over 100 m, ~60% over 500 m for this T/S profile). So the
    two methods are only "equivalent" very near the surface; this test uses a
    5 m column and a correspondingly realistic tolerance. The complementary
    test_deep_water_potential_vs_insitu asserts the large divergence at depth.
    """
    print("\n=== Test: Shallow Surface Layer (Small Compressibility) ===\n")

    # Thin surface layer where the pressure correction is small.
    nz = 10
    depth = np.linspace(0, -5, nz)
    theta = np.linspace(20.0, 15.0, nz)
    salt = np.linspace(35.0, 35.2, nz)

    # In-situ method
    pressure_insitu = -depth
    rho_insitu_anom, _, _ = jmd95_eos(theta, salt, pressure_insitu, rho_const=1029.0)
    rho_insitu = rho_insitu_anom + 1029.0
    z_positive_up = depth  # z = depth for "positive up" convention
    n2_insitu = compute_buoyancy_frequency_squared(
        rho_insitu, z_positive_up, gravity=9.81, rho_0=1029.0
    )

    # Potential method
    n2_potential = compute_ggl90_buoyancy_frequency_squared(
        theta, salt, depth, rho_const=1029.0, gravity=9.81, use_jmd95=True
    )

    # In a thin surface layer the two methods agree to within a few percent.
    tol_pct = 3.0
    for k in range(1, nz):
        if abs(n2_insitu[k]) > 1e-10:
            pct_diff = 100.0 * abs(n2_potential[k] - n2_insitu[k]) / n2_insitu[k]
            print(f"Level {k}: N²(insitu)={n2_insitu[k]:.6e}, "
                  f"N²(pot)={n2_potential[k]:.6e}, diff={pct_diff:.4f}%")
            assert pct_diff < tol_pct, \
                f"Shallow surface-layer difference should be < {tol_pct}%, got {pct_diff:.4f}%"

    print(f"\n✓ Shallow surface-layer near-equivalence verified (< {tol_pct}%)")


def test_unstable_stratification():
    """
    Test that both methods correctly identify unstable stratification (N² < 0).
    """
    print("\n=== Test: Unstable Stratification (N² < 0) ===\n")

    # Create an unstable profile: warm water below cold water
    nz = 5
    depth = np.linspace(0, -100, nz)
    theta = np.linspace(5.0, 20.0, nz)  # Temperature INCREASES with depth (unstable)
    salt = np.linspace(35.0, 35.0, nz)   # Uniform salinity

    # In-situ method
    pressure_insitu = -depth
    rho_insitu_anom, _, _ = jmd95_eos(theta, salt, pressure_insitu, rho_const=1029.0)
    rho_insitu = rho_insitu_anom + 1029.0
    z_positive_up = depth  # z = depth for "positive up" convention
    n2_insitu = compute_buoyancy_frequency_squared(
        rho_insitu, z_positive_up, gravity=9.81, rho_0=1029.0
    )

    # Potential method
    n2_potential = compute_ggl90_buoyancy_frequency_squared(
        theta, salt, depth, rho_const=1029.0, gravity=9.81, use_jmd95=True
    )

    # Both methods should give negative N²
    print("Unstable stratification (denser water above lighter):")
    for k in range(1, nz):
        print(f"Level {k}: N²(insitu)={n2_insitu[k]:.6e}, N²(pot)={n2_potential[k]:.6e}")
        assert n2_insitu[k] < 0, "In-situ N² should be negative"
        assert n2_potential[k] < 0, "Potential N² should be negative"

    print("\n✓ Unstable stratification correctly identified by both methods")


if __name__ == '__main__':
    print("=" * 75)
    print("Testing Potential vs In-Situ Density Gradient Implementation")
    print("=" * 75)

    try:
        test_deep_water_potential_vs_insitu()
        test_shallow_water_equivalence()
        test_unstable_stratification()

        print("\n" + "=" * 75)
        print("All tests PASSED ✓")
        print("=" * 75)
        print("\nSummary:")
        print("  - GGL90 now uses POTENTIAL density gradients (matching MITgcm)")
        print("  - Removes compressibility artifacts in deep water")
        print("  - Correctly identifies stable and unstable stratification")

    except AssertionError as e:
        print(f"\n✗ Test FAILED: {e}")
        raise
