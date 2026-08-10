"""
Unit tests for physics_basis.py shared functions.

Tests:
1. Edge cases (surface, uniform profiles, zero values)
2. Reference profiles (stable, unstable, shear layers)
3. Analytical validation where possible
4. Cross-scheme consistency
"""

import pytest
import numpy as np
from physics_basis import (
    compute_buoyancy_frequency_squared,
    compute_vertical_shear_squared,
    compute_density_gradient,
    compute_richardson_number,
)


class TestBuoyancyFrequencySquared:
    """Test compute_buoyancy_frequency_squared."""

    def test_surface_is_zero(self):
        """N² at surface (k=0) should always be zero."""
        rho = np.array([1025.0, 1026.0, 1027.0])
        z = np.array([0.0, -10.0, -20.0])
        n2 = compute_buoyancy_frequency_squared(rho, z)
        assert n2[0] == 0.0, "N² at surface must be zero"

    def test_stable_stratification_positive_n2(self):
        """Stable stratification (density increasing downward) → N² > 0."""
        # Density increases downward (stable)
        rho = np.array([1025.0, 1026.0, 1027.0])
        z = np.array([0.0, -10.0, -20.0])
        n2 = compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
        
        # At k=1: drho/dz = (1025-1026)/(0-(-10)) = -0.1
        # N² = -(9.81/1025)*(-0.1) ≈ 0.000957 > 0 ✓
        assert n2[1] > 0, "Stable stratification should give N² > 0"
        assert n2[2] > 0, "Stable stratification should give N² > 0"

    def test_unstable_stratification_negative_n2(self):
        """Unstable stratification (density increasing upward) → N² < 0."""
        # Density decreases downward (unstable)
        rho = np.array([1027.0, 1026.0, 1025.0])
        z = np.array([0.0, -10.0, -20.0])
        n2 = compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
        
        # At k=1: drho/dz = (1027-1026)/(0-(-10)) = 0.1
        # N² = -(9.81/1025)*(0.1) ≈ -0.000957 < 0 ✓
        assert n2[1] < 0, "Unstable stratification should give N² < 0"

    def test_uniform_profile_zero_n2(self):
        """Uniform density profile → N² = 0 everywhere."""
        rho = np.ones(5) * 1026.0
        z = np.linspace(0, -40, 5)
        n2 = compute_buoyancy_frequency_squared(rho, z)
        
        np.testing.assert_array_almost_equal(n2, np.zeros(5), decimal=10)

    def test_linear_gradient(self):
        """Linear density gradient should give constant N²."""
        # Linear gradient: rho = 1025 - 0.1*depth
        z = np.array([0.0, -10.0, -20.0, -30.0])
        rho = 1025.0 - 0.1 * (-z)  # -z to convert to positive depth
        
        n2 = compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
        
        # Should be constant except at surface
        assert np.allclose(n2[1], n2[2]) and np.allclose(n2[2], n2[3])

    def test_input_validation_shape_mismatch(self):
        """Should raise error if rho and z have different shapes."""
        rho = np.array([1025.0, 1026.0])
        z = np.array([0.0, -10.0, -20.0])
        
        with pytest.raises(ValueError, match="shape"):
            compute_buoyancy_frequency_squared(rho, z)

    def test_custom_gravity(self):
        """Test with different gravity value."""
        rho = np.array([1025.0, 1026.0])
        z = np.array([0.0, -10.0])
        
        n2_earth = compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
        n2_moon = compute_buoyancy_frequency_squared(rho, z, gravity=1.62)
        
        # Moon gravity should scale the result
        assert abs(n2_moon / n2_earth - (1.62 / 9.81)) < 0.01

    def test_custom_rho_0(self):
        """Test with custom reference density."""
        rho = np.array([1025.0, 1026.0, 1027.0])
        z = np.array([0.0, -10.0, -20.0])
        
        n2_mean = compute_buoyancy_frequency_squared(rho, z)
        n2_const = compute_buoyancy_frequency_squared(rho, z, rho_0=1025.0)
        
        # Using explicit rho_0=1025 should differ slightly from mean
        assert not np.allclose(n2_mean, n2_const)


class TestVerticalShearSquared:
    """Test compute_vertical_shear_squared."""

    def test_surface_is_zero(self):
        """S² at surface (k=0) should always be zero."""
        u = np.array([0.5, 0.3, 0.1])
        v = np.array([0.1, 0.05, 0.0])
        z = np.array([0.0, -10.0, -20.0])
        
        s2 = compute_vertical_shear_squared(u, v, z)
        assert s2[0] == 0.0, "S² at surface must be zero"

    def test_zero_velocity_zero_shear(self):
        """Zero velocity everywhere → S² = 0."""
        u = np.zeros(5)
        v = np.zeros(5)
        z = np.linspace(0, -40, 5)
        
        s2 = compute_vertical_shear_squared(u, v, z)
        np.testing.assert_array_almost_equal(s2, np.zeros(5), decimal=10)

    def test_uniform_velocity_zero_shear(self):
        """Uniform velocity profile → S² = 0."""
        u = np.ones(5) * 0.5
        v = np.ones(5) * 0.2
        z = np.linspace(0, -40, 5)
        
        s2 = compute_vertical_shear_squared(u, v, z)
        np.testing.assert_array_almost_equal(s2, np.zeros(5), decimal=10)

    def test_linear_shear(self):
        """Linear velocity profile should give constant S²."""
        # Linear shear: u = 0.5 - 0.01*depth (decreasing downward)
        z = np.array([0.0, -10.0, -20.0])
        u = 0.5 - 0.01 * (-z)
        v = np.zeros(3)
        
        s2 = compute_vertical_shear_squared(u, v, z)
        
        # du/dz = 0.01 everywhere, so S² should be constant
        assert np.allclose(s2[1], s2[2]), "Linear shear should give constant S²"

    def test_analytical_example(self):
        """Test against known analytical values."""
        z = np.array([0.0, -10.0])
        u = np.array([1.0, 0.5])
        v = np.array([0.0, 0.0])
        
        s2 = compute_vertical_shear_squared(u, v, z)
        
        # du/dz = (1.0 - 0.5) / (0 - (-10)) = 0.05
        # S² = 0.05^2 = 0.0025
        assert np.isclose(s2[1], 0.0025)

    def test_both_u_and_v_contribute(self):
        """Both u and v components should contribute to S²."""
        z = np.array([0.0, -10.0])
        u = np.array([1.0, 0.5])
        v = np.array([0.5, 0.0])
        
        s2 = compute_vertical_shear_squared(u, v, z)
        
        # du/dz = 0.05, dv/dz = 0.05
        # S² = 0.05² + 0.05² = 0.005
        assert np.isclose(s2[1], 0.005)

    def test_input_validation_shape_mismatch(self):
        """Should raise error if shapes don't match."""
        u = np.array([1.0, 0.5])
        v = np.array([0.1, 0.05, 0.0])
        z = np.array([0.0, -10.0])
        
        with pytest.raises(ValueError, match="shape"):
            compute_vertical_shear_squared(u, v, z)


class TestDensityGradient:
    """Test compute_density_gradient."""

    def test_surface_is_zero(self):
        """drho/dz at surface (k=0) should be zero."""
        rho = np.array([1025.0, 1026.0])
        z = np.array([0.0, -10.0])
        drho_dz = compute_density_gradient(rho, z)
        
        assert drho_dz[0] == 0.0

    def test_uniform_profile(self):
        """Uniform density → drho/dz = 0."""
        rho = np.ones(5) * 1026.0
        z = np.linspace(0, -40, 5)
        drho_dz = compute_density_gradient(rho, z)
        
        np.testing.assert_array_almost_equal(drho_dz, np.zeros(5), decimal=10)

    def test_linear_gradient(self):
        """Linear density gradient should give constant drho/dz."""
        z = np.array([0.0, -10.0, -20.0])
        rho = 1025.0 - 0.1 * (-z)
        
        drho_dz = compute_density_gradient(rho, z)
        
        # Should all be 0.1 (except surface)
        assert np.allclose(drho_dz[1], 0.1)
        assert np.allclose(drho_dz[2], 0.1)


class TestRichardsonNumber:
    """Test compute_richardson_number."""

    def test_neutral_case(self):
        """Ri = 1 when N² = S²."""
        n_square = np.ones(3) * 1e-4
        shear_square = np.ones(3) * 1e-4
        
        ri = compute_richardson_number(n_square, shear_square)
        np.testing.assert_array_almost_equal(ri, np.ones(3), decimal=5)

    def test_stable_case(self):
        """Ri > 1 when N² > S² (buoyancy dominates)."""
        n_square = np.array([0.0, 2e-4, 1e-4])
        shear_square = np.array([0.0, 1e-4, 1e-4])
        
        ri = compute_richardson_number(n_square, shear_square)
        
        assert ri[1] > 1.0
        assert np.isclose(ri[1], 2.0)

    def test_unstable_case(self):
        """Ri < 1 when N² < S² (shear dominates)."""
        n_square = np.array([0.0, 1e-4, 1e-4])
        shear_square = np.array([0.0, 2e-4, 1e-3])
        
        ri = compute_richardson_number(n_square, shear_square)
        
        assert ri[1] < 1.0
        assert np.isclose(ri[1], 0.5)

    def test_zero_shear_safe_division(self):
        """Should handle zero shear gracefully (return large Ri)."""
        n_square = np.array([1e-4])
        shear_square = np.array([0.0])
        
        ri = compute_richardson_number(n_square, shear_square, epsilon=1e-14)
        
        # Should not be inf, but very large
        assert ri[0] > 1e10


class TestCrossSchemeConsistency:
    """Test that functions work consistently for both GGL90 and KPP."""

    def test_arctic_convection_profile(self):
        """Test with realistic arctic convection scenario."""
        # Typical arctic_convection aftermath:
        # - surface cooling → inversion (N² < 0)
        # - strong shear in BL from wind stress
        z = np.linspace(0, -100, 11)
        
        # Create a weakly stratified profile with surface inversion
        rho = 1027.0 + 0.1 * (-z) - 2.0 * np.exp(-(-z) / 10.0)
        
        u = 0.5 * np.exp(-(-z) / 50.0)  # Wind shear decays with depth
        v = 0.2 * np.exp(-(-z) / 50.0)
        
        n2 = compute_buoyancy_frequency_squared(rho, z)
        s2 = compute_vertical_shear_squared(u, v, z)
        ri = compute_richardson_number(n2, s2)
        
        # Sanity checks
        assert len(n2) == len(z)
        assert len(s2) == len(z)
        assert len(ri) == len(z)
        assert n2[0] == 0 and s2[0] == 0
        assert ri[0] == 0 or np.isnan(ri[0])  # Undefined at surface

    def test_calm_baseline_profile(self):
        """Test with realistic calm baseline scenario."""
        z = np.linspace(0, -50, 6)
        
        # Stably stratified, weak shear
        rho = 1025.0 + 0.05 * (-z)
        u = 0.1 * np.exp(-(-z) / 20.0)
        v = 0.05 * np.exp(-(-z) / 20.0)
        
        n2 = compute_buoyancy_frequency_squared(rho, z)
        s2 = compute_vertical_shear_squared(u, v, z)
        
        # All N² > 0 (stable)
        assert np.all(n2[1:] > 0)
        
        # All S² >= 0
        assert np.all(s2 >= 0)

    def test_hurricane_wind_profile(self):
        """Test with realistic hurricane wind scenario."""
        z = np.linspace(0, -200, 21)
        
        # Moderately stratified
        rho = 1024.0 + 0.03 * (-z) + 0.5 * np.sin(np.pi * (-z) / 200.0)
        
        # Strong wind shear
        u = 2.0 * np.exp(-(-z) / 30.0)
        v = 1.0 * np.exp(-(-z) / 30.0)
        
        n2 = compute_buoyancy_frequency_squared(rho, z)
        s2 = compute_vertical_shear_squared(u, v, z)
        ri = compute_richardson_number(n2, s2)
        
        # Surface shear should be strong (small Ri initially)
        assert ri[1] < 1.0  # Shear dominates at surface


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
