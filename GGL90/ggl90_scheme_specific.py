"""
GGL90-specific physics and mixing length computation.

This module contains scheme-specific logic for GGL90:
  - Mixing length calculation with various limiting methods
  - TKE prognostic evolution and boundary conditions
  - TKE source/sink terms (production, buoyancy, dissipation)

Imports common physics from main.physics_basis (N², S², etc.).
Uses GGL90Parameters for configuration.

Reference:
    Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990), JGR, 95(C9), pp. 16,179
    Blanke, B., and P. Delecluse (1993), JPO, 23, pp. 1363-1388
"""

import numpy as np
from typing import Tuple, Optional


class GGL90MixingLength:
    """
    Compute GGL90 mixing length with various limiting methods.

    Corresponds to ggl90_mixinglength.F in MITgcm.
    """

    def __init__(self, params):
        """
        Initialize mixing length calculator.

        Args:
            params: GGL90Parameters object
        """
        self.params = params

    def compute(
        self,
        tke: np.ndarray,
        n_square: np.ndarray,
        dz: np.ndarray,
        depth_to_surface: np.ndarray,
        depth_to_bottom: np.ndarray,
        mask: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute mixing length.

        Corresponds to ggl90_mixinglength.F computation.

        Args:
            tke: Turbulent kinetic energy (nz,) [m²/s²]
            n_square: Squared buoyancy frequency (nz,) [s⁻²]
            dz: Vertical grid spacing (nz,) [m]
            depth_to_surface: Distance to surface (nz,) [m]
            depth_to_bottom: Distance to bottom (nz,) [m]
            mask: Vertical mask (nz,) [0 or 1]

        Returns:
            mixing_length: Mixing length (nz,) [m]
            r_mixing_length: Reciprocal of mixing length (nz,) [1/m]
        """
        nz = len(tke)

        # Initial estimate from TKE and buoyancy frequency (eq. 2.35)
        mixing_length = np.zeros(nz)
        for k in range(1, nz):  # Skip surface level (k=0)
            if mask[k] > 0:
                sqrt_tke = np.sqrt(max(tke[k], self.params.tke_min))
                sqrt_n2 = np.sqrt(max(n_square[k], self.params.ggl90_eps))
                mixing_length[k] = self.params.sqrt_two * sqrt_tke / sqrt_n2

        # Apply limiting method
        if self.params.mxl_max_flag == 0:
            mixing_length = self._limit_method_0(
                mixing_length, depth_to_surface, depth_to_bottom, mask
            )
        elif self.params.mxl_max_flag == 1:
            mixing_length = self._limit_method_1(
                mixing_length, depth_to_surface, depth_to_bottom, mask
            )
        elif self.params.mxl_max_flag in [2, 3]:
            mixing_length = self._limit_method_2(
                mixing_length, dz, mask
            )
        else:
            raise ValueError(f"mxl_max_flag={self.params.mxl_max_flag} not supported")

        # Force surface mixing if requested
        if self.params.mxl_surf_flag and nz > 1:
            mixing_length[1] = dz[0]

        # Impose minimum and compute reciprocal
        r_mixing_length = np.zeros(nz)
        for k in range(nz):
            if mask[k] > 0:
                ml = max(mixing_length[k], self.params.mixing_length_min)
                mixing_length[k] = ml
                r_mixing_length[k] = 1.0 / ml

        return mixing_length, r_mixing_length

    def _limit_method_0(
        self,
        mixing_length: np.ndarray,
        depth_to_surface: np.ndarray,
        depth_to_bottom: np.ndarray,
        mask: np.ndarray
    ) -> np.ndarray:
        """
        Method 0: Simple water column depth limit.

        L = min(L, total_depth)
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        for k in range(nz):
            if mask[k] > 0:
                max_length = depth_to_surface[k] + depth_to_bottom[k]
                result[k] = min(result[k], max_length)

        return result

    def _limit_method_1(
        self,
        mixing_length: np.ndarray,
        depth_to_surface: np.ndarray,
        depth_to_bottom: np.ndarray,
        mask: np.ndarray
    ) -> np.ndarray:
        """
        Method 1: Distance to surface or bottom.

        L = min(L, min(depth_to_surface, depth_to_bottom))
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        for k in range(nz):
            if mask[k] > 0:
                max_length = min(depth_to_surface[k], depth_to_bottom[k])
                result[k] = min(result[k], max_length)

        return result

    def _limit_method_2(
        self,
        mixing_length: np.ndarray,
        dz: np.ndarray,
        mask: np.ndarray
    ) -> np.ndarray:
        """
        Method 2: Two-way sweep (Blanke & Delecluse 1993).

        This is the most physically realistic method, ensuring smooth
        vertical variation of mixing length.

        Algorithm:
        1. Downward sweep: L(k) = min(L(k), L(k-1) + dz(k-1))
        2. Upward sweep: L(k) = min(L(k), L(k+1) + dz(k))
        3. Final limit: L(k) = min(L(k), L_downward(k))
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        # Initialize downward sweep array
        mxl_down = np.zeros(nz)
        mxl_down[0] = self.params.mixing_length_min

        # Downward sweep (from surface to bottom)
        for k in range(1, nz):
            if mask[k] > 0:
                if mask[k-1] > 0:
                    mxl_down[k] = min(
                        result[k],
                        mxl_down[k-1] + dz[k-1]
                    )
                else:
                    mxl_down[k] = result[k]
            else:
                mxl_down[k] = self.params.mixing_length_min

        # Upward sweep (from bottom to surface)
        for k in range(nz-2, 0, -1):
            if mask[k] > 0 and mask[k+1] > 0:
                result[k] = min(result[k], result[k+1] + dz[k])

        # Apply downward limit
        for k in range(1, nz):
            if mask[k] > 0:
                result[k] = min(result[k], mxl_down[k])

        return result

    def compute_langmuir_length(
        self,
        mixing_length: np.ndarray,
        mxl_down: np.ndarray,
        gamma: float = 10.0
    ) -> np.ndarray:
        """
        Compute Langmuir-enhanced mixing length.

        When the mixing length reaches the bottom of the mixed layer
        (i.e., L = L_downward), amplify it by factor gamma.

        Args:
            mixing_length: Base mixing length (nz,) [m]
            mxl_down: Downward sweep result (nz,) [m]
            gamma: Amplification factor (default: 10.0)

        Returns:
            lc_mixing_length: Langmuir-enhanced mixing length (nz,) [m]
        """
        lc_mixing_length = mixing_length.copy()

        # Check where mixing length hits the downward limit
        # (indicates bottom of mixed layer)
        at_ml_base = np.abs(mixing_length - mxl_down) < 1e-10

        # Amplify at mixed layer base
        lc_mixing_length[at_ml_base] *= gamma

        # Ensure minimum
        lc_mixing_length = np.maximum(
            lc_mixing_length,
            self.params.mixing_length_min
        )

        return lc_mixing_length


def compute_tke_production(
    kappa_m: np.ndarray,
    shear_square: np.ndarray,
    mask: np.ndarray
) -> np.ndarray:
    """
    Compute TKE production by shear.

    P = KappaM * S²

    Corresponds to GGL90_CALC.F TKE production term.

    Args:
        kappa_m: Eddy viscosity (nz,) [m²/s]
        shear_square: Vertical shear squared (nz,) [s⁻²]
        mask: Vertical mask (nz,) [0 or 1]

    Returns:
        production: TKE production (nz,) [m²/s³]
    """
    production = np.zeros(len(kappa_m))
    for k in range(len(kappa_m)):
        if mask[k] > 0:
            production[k] = kappa_m[k] * shear_square[k]
    return production


def compute_tke_buoyancy(
    kappa_h: np.ndarray,
    n_square: np.ndarray,
    mask: np.ndarray
) -> np.ndarray:
    """
    Compute TKE destruction by buoyancy.

    B = -KappaH * N²

    Corresponds to GGL90_CALC.F buoyancy term.

    Args:
        kappa_h: Eddy diffusivity (nz,) [m²/s]
        n_square: Buoyancy frequency squared (nz,) [s⁻²]
        mask: Vertical mask (nz,) [0 or 1]

    Returns:
        buoyancy: TKE buoyancy term (nz,) [m²/s³]
    """
    buoyancy = np.zeros(len(kappa_h))
    for k in range(len(kappa_h)):
        if mask[k] > 0:
            buoyancy[k] = -kappa_h[k] * n_square[k]
    return buoyancy


def compute_tke_dissipation(
    tke: np.ndarray,
    mixing_length: np.ndarray,
    ceps: float,
    mask: np.ndarray,
    tke_min: float = 1e-11
) -> np.ndarray:
    """
    Compute TKE dissipation.

    ε = c_eps * TKE^(3/2) / L

    Corresponds to GGL90_CALC.F dissipation term.

    Args:
        tke: Turbulent kinetic energy (nz,) [m²/s²]
        mixing_length: Mixing length (nz,) [m]
        ceps: Dissipation coefficient (Kolmogorov constant)
        mask: Vertical mask (nz,) [0 or 1]
        tke_min: Minimum TKE for regularization

    Returns:
        dissipation: TKE dissipation (nz,) [m²/s³]
    """
    dissipation = np.zeros(len(tke))
    for k in range(len(tke)):
        if mask[k] > 0:
            sqrt_tke = np.sqrt(max(tke[k], tke_min))
            dissipation[k] = ceps * tke[k] * sqrt_tke / mixing_length[k]
    return dissipation
