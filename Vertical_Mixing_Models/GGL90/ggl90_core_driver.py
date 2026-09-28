"""
Main GGL90 driver class for column-wise mixing computations.

This is the Python equivalent of GGL90_CALC in MITgcm.

Orchestrates:
  1. Stratification and shear diagnosis (N², S²) — from main.physics_basis
  2. Mixing length computation — from ggl90_scheme_specific
  3. Mixing coefficient assembly — from ggl90_mixing_coefficients
  4. TKE prognostic stepping — local to this module

Reference:
    Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990), JGR, 95(C9), pp. 16,179
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import sys
from pathlib import Path

from .ggl90_parameters import GGL90Parameters
from .ggl90_scheme_specific import (
    GGL90MixingLength,
    compute_tke_production,
    compute_tke_buoyancy,
    compute_tke_dissipation,
)
from .ggl90_mixing_coefficients import compute_viscosity_diffusivity

# Handle imports from main module (support both package and direct script execution)
try:
    from main.physics_basis import (
        compute_buoyancy_frequency_squared,
        compute_vertical_shear_squared,
    )
    from main.shared_column_solver import solve_tridiagonal
except ImportError:
    # Fallback: add parent directories to path
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    from main.physics_basis import (
        compute_buoyancy_frequency_squared,
        compute_vertical_shear_squared,
    )
    from main.shared_column_solver import solve_tridiagonal


@dataclass
class GGL90Output:
    """Container for GGL90 output fields."""

    # Prognostic variable [m^2/s^2]
    tke_new: np.ndarray  # Updated turbulent kinetic energy

    # Primary mixing coefficients [m^2/s]
    kappa_m: np.ndarray  # Eddy viscosity
    kappa_h: np.ndarray  # Eddy diffusivity

    # Mixing length [m]
    mixing_length: np.ndarray

    # Diagnostics
    n_square: Optional[np.ndarray] = None  # Buoyancy frequency squared [s^-2]
    shear_square: Optional[np.ndarray] = None  # Vertical shear squared [s^-2]
    production: Optional[np.ndarray] = None  # TKE shear production [m^2/s^3]
    buoyancy: Optional[np.ndarray] = None  # TKE buoyancy term [m^2/s^3]
    dissipation: Optional[np.ndarray] = None  # TKE dissipation [m^2/s^3]

    def to_dict(self) -> Dict:
        """Convert to dictionary (MITgcm-style diagnostic names)."""
        return {
            'GGL90TKE': self.tke_new,
            'GGL90viscAz': self.kappa_m,
            'GGL90diffKz': self.kappa_h,
            'GGL90mixingLength': self.mixing_length,
        }


class GGL90Driver:
    """
    Main driver for GGL90 mixing scheme.

    Computes vertical mixing coefficients for a single ocean column.
    Unlike KPP (diagnostic), GGL90 is prognostic: it evolves turbulent
    kinetic energy (TKE) as a state variable stepped forward each call.

    **Corresponds to**: GGL90_CALC.F in MITgcm (orchestrator)
    """

    def __init__(self, params: Optional[GGL90Parameters] = None):
        """
        Initialize GGL90 driver.

        Parameters
        ----------
        params : GGL90Parameters, optional
            Configuration object. If None, uses defaults.
        """
        self.params = params if params is not None else GGL90Parameters()
        self.mixing_length_calc = GGL90MixingLength(self.params)

    def step_tke_forward(
        self,
        tke: np.ndarray,
        production: np.ndarray,
        buoyancy: np.ndarray,
        mixing_length: np.ndarray,
        dz: np.ndarray,
        dt: float,
        mask: np.ndarray,
        u_star_sq: float = 0.0,
        kappa_m: Optional[np.ndarray] = None,
        r_mixing_length: Optional[np.ndarray] = None,
        is_true_surface: bool = True,
    ) -> np.ndarray:
        """
        Step TKE forward in time using implicit scheme.

        ∂TKE/∂t = P + B - ε + ∂/∂z(KappaE * ∂TKE/∂z)

        where:
        - P = shear production
        - B = buoyancy term
        - ε = dissipation (treated implicitly)
        - Last term is vertical diffusion (treated implicitly)

        **Corresponds to**: GGL90_CALC.F TKE stepping logic (dissipation rate:
        ggl90_calc.F:600-602, 747-748, `GGL90ceps*SQRTTKE(k)*rMixingLength(k)`)

        **1DMIX-038 fix**: for an `ALLOW_SHELFICE` column
        (`is_true_surface=False`), local index 0 is a real, interior
        `kSrf>1`, not the model's true k=1 array boundary. Derived directly
        from `ggl90_calc.F` (isomip `code_validation/ggl90_calc.F`) and
        confirmed exactly against all 28812 real ice-shelf column-timesteps
        in the `isomip` capture (zero exceptions): MITgcm's Dirichlet
        assignment at `kSrf` (ggl90_calc.F:944-946,
        `GGL90TKE(kSrf)=maskC(kSrf)*MAX(GGL90TKEsurfMin,GGL90m2*
        uStarSquare)`) is itself correct and nonzero, but the SAME
        "impose minimum TKE" loop that runs immediately after the
        tridiagonal solve, over the fixed Fortran range `k=2,Nr` (i.e.
        every array index except the true k=1 surface, which this loop
        never visits -- ggl90_calc.F:1003-1011), unconditionally
        re-applies `GGL90TKE(k)=maskC(k)*maskC(k-1)*MAX(GGL90TKE(k),
        GGL90TKEmin)`. At `k=kSrf`, `maskC(kSrf-1)=0` (the
        ice-shelf-masked cell immediately above the slice), so this
        multiplies the just-solved Dirichlet value by 0, discarding it
        entirely -- confirmed point check (`isomip` x=1,y=1, kSrf=22):
        `mit_tke_after[22]=0.0` exactly, not `MAX(GGL90TKEsurfMin,...)`.
        For the true k=1 surface (`is_true_surface=True`, default, every
        pre-existing call site), k=1 is outside this loop's `k=2,Nr`
        range and its Dirichlet-assigned value is never touched
        afterward -- unchanged, exact behavioral no-op.

        Args:
            tke: Current TKE (nz,) [m²/s²]
            production: Shear production (nz,) [m²/s³]
            buoyancy: Buoyancy term (nz,) [m²/s³]
            mixing_length: Mixing length (nz,) [m]
            dz: Vertical grid spacing (nz,) [m]
            dt: Time step [s]
            mask: Vertical mask (nz,) [0 or 1]
            u_star_sq: Surface friction velocity squared [m²/s²]
            kappa_m: Eddy viscosity (nz,) [m²/s], as returned by
                compute_viscosity_diffusivity (already floored by the
                background viscosity, matching MITgcm's KappaM(i,j)). Used to
                form KappaE = alpha * KappaM. If None (e.g. a standalone unit
                test), KappaM is recomputed here with no background floor.
            r_mixing_length: Reciprocal mixing length (nz,) [1/m], as returned
                by GGL90MixingLength.compute(). Used for the dissipation rate
                (rMixingLength(k) in ggl90_calc.F, which for mxl_max_flag==3
                is NOT simply 1/mixing_length[k] -- see
                GGL90MixingLength.compute(), 1DMIX-014). If None (e.g. a
                standalone unit test), falls back to 1/mixing_length[k],
                which is exact for mxl_max_flag in {0,1,2}.
            is_true_surface: True (default) when index 0 is the model's
                true k=1 array boundary (every non-ShelfIce experiment):
                tke_new[0] keeps its Dirichlet-assigned value. Set False
                when the caller has sliced a column starting at a real,
                shifted `kSrf>1` (an `ALLOW_SHELFICE` column): tke_new[0]
                is forced to exactly 0.0 instead, matching MITgcm's real
                behavior there (see 1DMIX-038 note above).

        Returns:
            tke_new: Updated TKE (nz,) [m²/s²]
        """
        nz = len(tke)

        # Compute KappaE (diffusivity for TKE)
        if kappa_m is not None:
            kappa_e = self.params.alpha * kappa_m
        else:
            kappa_e = np.zeros(nz)
            for k in range(nz):
                if mask[k] > 0:
                    sqrt_tke = np.sqrt(max(tke[k], self.params.tke_min))
                    kappa_e[k] = (
                        self.params.alpha
                        * self.params.ck
                        * mixing_length[k]
                        * sqrt_tke
                    )

        # Build the MITgcm W-point TKE system. Index 0 is the prescribed
        # surface TKE boundary; indices 1..nz-1 are prognostic interfaces.
        a = np.zeros(nz)
        b = np.zeros(nz)
        c = np.zeros(nz)
        rhs = np.zeros(nz)

        impl_fac = self.params.impl_diss_fac
        expl_fac = self.params.expl_diss_fac

        dr_c = 0.5 * (dz[:-1] + dz[1:])

        for k in range(1, nz):
            if mask[k] > 0:
                # Dissipation rate (implicit)
                sqrt_tke_k = np.sqrt(max(tke[k], self.params.tke_min))
                if r_mixing_length is not None:
                    diss_rate = self.params.ceps * sqrt_tke_k * r_mixing_length[k]
                else:
                    diss_rate = self.params.ceps * sqrt_tke_k / mixing_length[k]

                # GGL90_CALC uses KappaE(k) at the surface-adjacent
                # interface and averages adjacent KappaE values below it.
                kappa_up = kappa_e[k] if k == 1 else 0.5 * (
                    kappa_e[k] + kappa_e[k - 1]
                )
                a[k] = -impl_fac * dt * kappa_up / (dz[k - 1] * dr_c[k - 1])

                # **MITgcm correspondence** (fix, found while verifying
                # 1DMIX-014): ggl90_calc.F:691-694 (a3d(k)) and :713-716
                # (c3d(k)) both multiply by the SAME recip_drC(k) -- drC(k) is
                # the W-cell's own thickness, shared by both its up- and
                # down-coupling coefficients; only the recip_drF face term
                # (dz[k-1] for a, dz[k] for c) differs between them. c[k] here
                # previously used dr_c[k] instead of dr_c[k-1], disagreeing
                # with a[k]'s index. This has no effect on a uniform grid
                # (dr_c[k-1]==dr_c[k] there) but is wrong wherever cell
                # thickness varies with depth (e.g. the vermix grid's
                # transition layers).
                if k == nz - 1:
                    # MITgcm forms a virtual bottom-neighbor coefficient, then
                    # moves its Dirichlet contribution to the right-hand side.
                    kappa_dn = kappa_e[k]
                    c[k] = -impl_fac * dt * kappa_dn / (dz[k] * dr_c[k - 1])
                else:
                    kappa_dn = 0.5 * (kappa_e[k] + kappa_e[k + 1])
                    c[k] = -impl_fac * dt * kappa_dn / (dz[k] * dr_c[k - 1])

                b[k] = 1.0 + impl_fac * dt * diss_rate - a[k] - c[k]
                rhs[k] = tke[k] + dt * (production[k] + buoyancy[k])
                rhs[k] -= expl_fac * dt * diss_rate * tke[k]

        # Surface Dirichlet condition at the actual surface face. Retaining the
        # original a[1] contribution in b[1] is the standard elimination of
        # the prescribed surface value used by MITgcm's GGL90_CALC.
        surf_tke = max(self.params.m2 * u_star_sq, self.params.tke_surf_min)
        b[0] = 1.0
        rhs[0] = surf_tke
        if nz > 1:
            rhs[1] -= a[1] * surf_tke
            a[1] = 0.0

        # Bottom Dirichlet or Neumann condition. The surface condition is
        # always Dirichlet; use_dirichlet controls only the bottom condition.
        if self.params.use_dirichlet:
            rhs[nz - 1] -= self.params.tke_bottom * c[nz - 1]
            c[nz-1] = 0.0
        else:
            c[nz-1] = 0.0

        # Solve tridiagonal system (shared single-source-of-truth Thomas solver)
        tke_new = solve_tridiagonal(a, b, c, rhs)

        # Apply minimum TKE
        for k in range(nz):
            if mask[k] > 0:
                tke_new[k] = max(tke_new[k], self.params.tke_min)

        # 1DMIX-038: for an ALLOW_SHELFICE column (is_true_surface=False),
        # local index 0 is MITgcm's real, interior kSrf>1 -- its own
        # "impose minimum TKE" loop (fixed Fortran range k=2,Nr) masks
        # exactly this index to 0 via maskC(k-1)=0, discarding the
        # Dirichlet value set above (see docstring).
        if not is_true_surface and nz > 0:
            tke_new[0] = 0.0

        return tke_new

    def compute_mixing(
        self,
        tke: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        theta: np.ndarray,
        salt: np.ndarray,
        depth: np.ndarray,
        z: np.ndarray,
        dz: np.ndarray,
        dt: float,
        mask: np.ndarray,
        u_star_sq: float = 0.0,
        gravity: float = 9.81,
        rho_const: float = 1029.0,
        background_visc: float = 0.0,
        background_diff: float = 0.0,
        is_true_surface: bool = True,
    ) -> GGL90Output:
        """
        Compute GGL90 mixing coefficients for a single column.

        Roadmap of this routine (calculations in order):
            Step 1: Compute stratification and shear (N², S²) — shared physics_basis
            Step 2: Compute mixing length (from TKE and N², with limits) — scheme_specific
            Step 3: Compute viscosity and diffusivity (κ_m, κ_h, κ_h_tendency) — mixing_coefficients
            Step 4: Compute TKE budget terms (production, buoyancy, dissipation) — scheme_specific
            Step 5: Step TKE forward in time (implicit tridiagonal solve) — local
            Step 6: Assemble output

        Unlike KPP, GGL90 is prognostic: TKE is a state variable. The updated
        TKE (tke_new) is returned and must be fed back on the next call.

        **1DMIX-048**: Step 4's buoyancy term uses an internal-only
        `kappa_h_tendency` (MITgcm's real `KappaH`,
        `kappa_m/tke_prandtl_number`, unfloored/uncapped by the
        diffusivity background/`diff_max`) returned alongside `kappa_h`
        by `compute_viscosity_diffusivity` -- NOT the `kappa_h` field
        that appears in `GGL90Output`/`GGL90diffKr` (that quantity is
        additionally floored/capped for its role as a diagnostic output,
        which the real TKE buoyancy term does not use). `kappa_m`,
        `kappa_h` and every other output field are byte-for-byte
        unaffected by this fix; only `tke_new` (via the buoyancy term)
        can change, and only when `background_visc != background_diff`.
        See `compute_viscosity_diffusivity`'s own docstring for the full
        MITgcm derivation (`ggl90_calc.F:507-515,661,673,1086-1088`).

        **1DMIX-038**: `is_true_surface` (default True, an exact
        behavioral no-op for every pre-existing caller) is passed straight
        through to `compute_viscosity_diffusivity` (κ_h[0]) and
        `step_tke_forward` (tke_new[0]); see their own docstrings for the
        real MITgcm mechanism. `mixing_length` itself at local index 0
        needs no equivalent flag: MITgcm's own mixing-length computation
        and this port's (`GGL90MixingLength.compute()`) both independently
        leave index 0 at `mixing_length_min` whether index 0 is the true
        k=1 surface or a real, shifted `kSrf` -- confirmed exactly (0
        mismatch) against all 28812 real `isomip` ice-shelf
        column-timesteps. The flag IS also passed through to
        `GGL90MixingLength.compute()` itself (round 2): its internal
        `mxl_down` two-way-sweep companion array needs it, even though the
        visible `mixing_length[0]` does not -- a real, small, independently
        -derived fix, but NOT the explanation for the dominant reported
        `kSrf+1` mismatch (see `GGL90MixingLength.compute()`'s own
        docstring and open_issues.md's 1DMIX-038/1DMIX-039: that mismatch
        is a numerical-conditioning effect of `mixing_length`'s
        `1/sqrt(N²)` formula near N²≈0, unrelated to kSrf/is_true_surface,
        confirmed to occur equally in ordinary fully-wet columns).

        **Corresponds to**: GGL90_CALC.F (orchestration)

        Parameters
        ----------
        tke : np.ndarray, shape (nz,)
            Current turbulent kinetic energy [m²/s²]
        u : np.ndarray, shape (nz,)
            Zonal velocity [m/s]
        v : np.ndarray, shape (nz,)
            Meridional velocity [m/s]
        theta : np.ndarray, shape (nz,)
            Potential temperature [°C]
        salt : np.ndarray, shape (nz,)
            Salinity [psu]
        depth : np.ndarray, shape (nz,)
            Depth of cell centers (negative, increasing downward) [m]
        z : np.ndarray, shape (nz,)
            Vertical coordinate [m], positive upward
        dz : np.ndarray, shape (nz,)
            Vertical grid spacing [m]
        dt : float
            Time step [s]
        mask : np.ndarray, shape (nz,)
            Vertical mask [0 or 1]
        u_star_sq : float, optional
            Surface friction velocity squared [m²/s²]
        gravity : float, optional
            Gravitational acceleration [m/s²]
        rho_const : float, optional
            Reference density [kg/m³]
        background_visc : float, optional
            Background (floor) vertical viscosity [m²/s], MITgcm's
            viscArNr(k). Default 0.0 (no floor).
        background_diff : float, optional
            Background (floor) vertical diffusivity [m²/s], MITgcm's
            diffKrNrS(k). Default 0.0 (no floor).
        is_true_surface : bool, optional
            True (default) when index 0 is the model's true k=1 array
            boundary (every non-ShelfIce experiment). Set False when the
            caller has sliced a column starting at a real, shifted
            `kSrf>1` (an `ALLOW_SHELFICE` column) -- see 1DMIX-038 note
            above. Passed through unchanged to
            `compute_viscosity_diffusivity` and `step_tke_forward`.

        Returns
        -------
        GGL90Output
            Updated TKE, mixing coefficients, and diagnostics
        """
        nz = len(tke)

        # ===== Step 1: Compute stratification and shear =====
        # Compute N² using POTENTIAL density gradients (MITgcm's sigmaR).
        # This is the key fix: the old code used in-situ density gradients,
        # which incorrectly included compressibility effects.
        from main.eos import compute_ggl90_buoyancy_frequency_squared
        n_square = compute_ggl90_buoyancy_frequency_squared(
            theta, salt, depth, rho_const, gravity, use_jmd95=True
        )
        shear_square = compute_vertical_shear_squared(u, v, z)

        # ===== Step 2: Compute mixing length =====
        # depth-to-surface / depth-to-bottom drive the mixing-length limiters
        # (mxl_max_flag 0/1). **Fix for 1DMIX-030**: MITgcm's own bounds
        # (ggl90_mixinglength.F:163-193) are INTERFACE-referenced --
        # Ro_surf=rF(1), R_low=rF(Nr+1) (model/src/ini_depths.F:91-102,
        # 155-166), rF(k) = top face of level k (model/src/ini_vertical_
        # grid.F:162, rF(k)=rF(k+1)-rkSign*drF(k)) -- NOT cell-center-
        # referenced. Using cell-center `z` here (as a previous version of
        # this code did: depth_to_surface=z[0]-z, depth_to_bottom=z-z[-1])
        # is short of the true Ro_surf-R_low span by half the top cell's
        # thickness plus half the bottom cell's -- confirmed exactly via the
        # standalone-GGL90_CALC-driver scenario check (1DMIX-030 evidence).
        # Build interface depths from `dz` (cell thickness) exactly as
        # ColumnGrid.interfaces does (interfaces[0]=0=Ro_surf,
        # interfaces[j]=-cumsum(dz)[:j], interfaces[nz]=-total_depth=R_low);
        # this reproduces grid.interfaces index-for-index without requiring
        # this function to take the grid object itself (dz already IS
        # grid.cell_thickness at every call site).
        #
        # Fortran-index mapping (confirmed by direct derivation, not
        # assumed): mixing_length's Python index k corresponds to Fortran
        # level k+1 (0- vs 1-indexed offset, matching every other index in
        # this module). rF(k+1) [Fortran] = interfaces[k] [Python, 0-
        # indexed] -- i.e. the SAME array index k in `interfaces` gives the
        # top-face depth for mixing_length's own index k. So:
        #   depth_to_surface[k] = Ro_surf - rF(k+1) = -interfaces[k]
        #   depth_to_bottom[k]  = rF(k+1) - R_low   = interfaces[k] - interfaces[nz]
        # For mxl_max_flag=0, depth_to_surface[k]+depth_to_bottom[k] reduces
        # to the constant -interfaces[nz] = total_depth = Ro_surf-R_low at
        # every k, exactly matching ggl90_mixinglength.F:168-179's single
        # scalar MaxLength. For mxl_max_flag=1, this gives exactly
        # min(Ro_surf-rF(k+1), rF(k+1)-R_low) via
        # _limit_method_1's existing min(depth_to_surface[k],
        # depth_to_bottom[k]) -- ggl90_mixinglength.F:183-193 -- with no
        # further change needed to that method's own formula.
        interfaces = np.zeros(nz + 1)
        interfaces[1:] = -np.cumsum(dz)
        depth_to_surface = -interfaces[:nz]
        depth_to_bottom = interfaces[:nz] - interfaces[nz]
        mixing_length, r_mixing_length = self.mixing_length_calc.compute(
            tke, n_square, dz, depth_to_surface, depth_to_bottom, mask,
            is_true_surface=is_true_surface,
        )

        # ===== Step 3: Compute viscosity and diffusivity =====
        # 1DMIX-048: kappa_h_tendency is a THIRD quantity, distinct from
        # both kappa_m and kappa_h -- see compute_viscosity_diffusivity's
        # own docstring for the full MITgcm derivation. It is the
        # internal, tendency-only KappaH the real TKE buoyancy term uses
        # (kappa_m/tke_prandtl_number, unfloored by background_diff,
        # uncapped by diff_max); kappa_h (floored/capped for the
        # diagnostic GGL90diffKr output) is NOT the right quantity for
        # that term and must stay out of Step 4 below.
        kappa_m, kappa_h, kappa_h_tendency = compute_viscosity_diffusivity(
            tke, mixing_length, mask, self.params, n_square, shear_square,
            background_visc=background_visc, background_diff=background_diff,
            is_true_surface=is_true_surface,
        )

        # ===== Step 4: Compute TKE budget terms =====
        # 1DMIX-048: the buoyancy term uses kappa_h_tendency (MITgcm's
        # real KappaH), not the diagnostic kappa_h -- see Step 3's note
        # and compute_viscosity_diffusivity's docstring.
        production = compute_tke_production(kappa_m, shear_square, mask)
        buoyancy = compute_tke_buoyancy(kappa_h_tendency, n_square, mask)
        dissipation = compute_tke_dissipation(tke, r_mixing_length, self.params.ceps, mask)

        # ===== Step 5: Step TKE forward in time =====
        tke_new = self.step_tke_forward(
            tke, production, buoyancy, mixing_length, dz, dt, mask, u_star_sq,
            kappa_m=kappa_m, r_mixing_length=r_mixing_length,
            is_true_surface=is_true_surface,
        )

        # ===== Step 6: Assemble output =====
        return GGL90Output(
            tke_new=tke_new,
            kappa_m=kappa_m,
            kappa_h=kappa_h,
            mixing_length=mixing_length,
            n_square=n_square,
            shear_square=shear_square,
            production=production,
            buoyancy=buoyancy,
            dissipation=dissipation,
        )
