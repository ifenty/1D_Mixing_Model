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

        **MITgcm correspondence** (1DMIX-014): ggl90_calc.F:268-286 initializes
        GGL90mixingLength to GGL90mixingLengthMin at *every* level before the
        Gaspar-formula loop (ggl90_calc.F:331-357, Fortran k=2..Nr, i.e. this
        function's k=1..nz-1) overwrites all but the surface level. The surface
        level (Fortran k=1, here k=0) is therefore always exactly
        mixing_length_min and is never touched by GGL90_MIXINGLENGTH itself
        (ggl90_mixinglength.F's loops all run k=2,Nr). Correspondingly, the
        final floor-and-reciprocal step below (ggl90_mixinglength.F:381-416)
        only runs over k=2..Nr and is NOT a uniform MAX(L,min) for every
        mxl_max_flag: mxl_max_flag==3 takes a different IF branch
        (ggl90_mixinglength.F:383-400) that leaves GGL90mixingLength itself
        unfloored and instead floors only the reciprocal via
        sqrt(L(k)*mxLength_Dn(k)); mxl_max_flag in {0,1,2} takes the ELSE
        branch (ggl90_mixinglength.F:401-416), which *is* the blanket
        MAX(L,min) this function previously applied to every flag and every
        level (including the surface) -- that blanket application was the bug.
        """
        nz = len(tke)

        # Initial estimate from TKE and buoyancy frequency (eq. 2.35).
        # Surface level (k=0) seeded to mixing_length_min to match
        # ggl90_calc.F:276's blanket init, since nothing below ever assigns it.
        mixing_length = np.full(nz, self.params.mixing_length_min)
        for k in range(1, nz):  # Skip surface level (k=0)
            if mask[k] > 0:
                sqrt_tke = np.sqrt(max(tke[k], self.params.tke_min))
                sqrt_n2 = np.sqrt(max(n_square[k], self.params.ggl90_eps))
                mixing_length[k] = self.params.sqrt_two * sqrt_tke / sqrt_n2

        # Apply limiting method. Only method 2 (mxl_max_flag in {2,3})
        # produces mxl_down (ggl90_mixinglength.F's mxLength_Dn), needed below
        # for the mxl_max_flag==3 reciprocal formula.
        mxl_down = None
        if self.params.mxl_max_flag == 0:
            mixing_length = self._limit_method_0(
                mixing_length, depth_to_surface, depth_to_bottom, mask
            )
        elif self.params.mxl_max_flag == 1:
            mixing_length = self._limit_method_1(
                mixing_length, depth_to_surface, depth_to_bottom, mask
            )
        elif self.params.mxl_max_flag in [2, 3]:
            mixing_length, mxl_down = self._limit_method_2(
                mixing_length, dz, mask
            )
        else:
            raise ValueError(f"mxl_max_flag={self.params.mxl_max_flag} not supported")

        # Force surface mixing if requested
        if self.params.mxl_surf_flag and nz > 1:
            mixing_length[1] = dz[0]

        # Impose minimum and compute reciprocal (ggl90_mixinglength.F:381-416).
        # k=0 (surface) is intentionally excluded from both branches below --
        # it keeps the mixing_length_min seed from above and rMixingLength(1)
        # is never assigned in the Fortran (stays at its zero init).
        r_mixing_length = np.zeros(nz)
        if self.params.mxl_max_flag == 3:
            # ggl90_mixinglength.F:387-400 (GGL90_REGULARIZE_MIXINGLENGTH is
            # #undef by default, GGL90_OPTIONS.h:36): GGL90mixingLength(k) is
            # NOT reassigned here -- it keeps its raw (possibly sub-minimum)
            # two-way-sweep value. Only the reciprocal is floored, using the
            # geometric mean of L(k) and the downward-sweep companion mxl_down(k).
            for k in range(1, nz):
                if mask[k] > 0:
                    ml_recip_basis = np.sqrt(mixing_length[k] * mxl_down[k])
                    ml_recip_basis = max(ml_recip_basis, self.params.mixing_length_min)
                    r_mixing_length[k] = 1.0 / ml_recip_basis
        else:
            # ggl90_mixinglength.F:401-416 (mxl_max_flag in {0,1,2}): blanket
            # MAX(L,min) floor, applied to both L itself and its reciprocal.
            for k in range(1, nz):
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

        **MITgcm correspondence**: ggl90_mixinglength.F:168-179 (`DO k=2,Nr`).
        The loop starts at Fortran k=2 (here k=1): the surface level (k=0)
        is never touched by this limiter and keeps the mixing_length_min
        seed from compute().
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        for k in range(1, nz):
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

        **MITgcm correspondence**: ggl90_mixinglength.F:183-193 (`DO k=2,Nr`).
        The loop starts at Fortran k=2 (here k=1): the surface level (k=0)
        is never touched by this limiter and keeps the mixing_length_min
        seed from compute().
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        for k in range(1, nz):
            if mask[k] > 0:
                max_length = min(depth_to_surface[k], depth_to_bottom[k])
                result[k] = min(result[k], max_length)

        return result

    def _limit_method_2(
        self,
        mixing_length: np.ndarray,
        dz: np.ndarray,
        mask: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Method 2: Two-way sweep (Blanke & Delecluse 1993).

        This is the most physically realistic method, ensuring smooth
        vertical variation of mixing length.

        Algorithm (ggl90_mixinglength.F:240-299, z-coordinate branch --
        this project has no p-coordinate/atmosphere path):
        1. Downward sweep: mxl_down(k) = min(L_raw(k), mxl_down(k-1) + dz(k-1))
        2. Bottom special treatment (Fortran "extra treatment of k=Nr because
           level Nr+1 is not available", ggl90_mixinglength.F:260-267):
           L(nz-1) = min(L(nz-1), mixing_length_min + dz(nz-1))
        3. Upward sweep: L(k) = min(L(k), L(k+1) + dz(k)) for k = nz-2..1
        4. Final limit: L(k) = min(L(k), mxl_down(k))

        Step 2 was previously missing here (1DMIX-014 follow-up finding):
        without it the upward sweep at the level adjacent to the bottom used
        an unclamped bottom value, diverging from MITgcm at depth.

        Returns
        -------
        result : np.ndarray
            Two-way-sweep-limited mixing length (nz,) [m].
        mxl_down : np.ndarray
            The downward-sweep-only array (Fortran mxLength_Dn), needed by
            compute() to reproduce the mxl_max_flag==3 reciprocal formula.
        """
        nz = len(mixing_length)
        result = mixing_length.copy()

        # Initialize downward sweep array
        mxl_down = np.zeros(nz)
        mxl_down[0] = self.params.mixing_length_min

        # Downward sweep (from surface to bottom), using the raw (pre-sweep)
        # mixing_length values -- ggl90_mixinglength.F:246-258.
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

        # Bottom-boundary special treatment before the upward sweep
        # (ggl90_mixinglength.F:264-267).
        if mask[nz - 1] > 0:
            result[nz - 1] = min(
                result[nz - 1], self.params.mixing_length_min + dz[nz - 1]
            )

        # Upward sweep (from bottom to surface), ggl90_mixinglength.F:268-283.
        for k in range(nz-2, 0, -1):
            if mask[k] > 0 and mask[k+1] > 0:
                result[k] = min(result[k], result[k+1] + dz[k])

        # Apply downward limit (ggl90_mixinglength.F:291-299)
        for k in range(1, nz):
            if mask[k] > 0:
                result[k] = min(result[k], mxl_down[k])

        return result, mxl_down

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
    r_mixing_length: np.ndarray,
    ceps: float,
    mask: np.ndarray,
    tke_min: float = 1e-11
) -> np.ndarray:
    """
    Compute TKE dissipation.

    ε = c_eps * TKE^(3/2) * rMixingLength

    **MITgcm correspondence**: ggl90_calc.F:601-603 --
    `TKEdissipation = explDissFac*GGL90ceps*SQRTTKE(k)*rMixingLength(k)*TKE(k)`.
    Takes the reciprocal mixing length directly (matching Fortran's
    rMixingLength) rather than dividing by the mixing length itself: for
    mxl_max_flag==3, rMixingLength is NOT 1/mixing_length (see
    GGL90MixingLength.compute(), 1DMIX-014) -- passing the wrong one of the
    two silently reintroduces that bug at this call site.

    Args:
        tke: Turbulent kinetic energy (nz,) [m²/s²]
        r_mixing_length: Reciprocal mixing length (nz,) [1/m], as returned by
            GGL90MixingLength.compute() (NOT simply 1/mixing_length for
            mxl_max_flag==3)
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
            dissipation[k] = ceps * tke[k] * sqrt_tke * r_mixing_length[k]
    return dissipation
