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
    ) -> np.ndarray:
        """
        Step TKE forward in time using implicit scheme.

        ∂TKE/∂t = P + B - ε + ∂/∂z(KappaE * ∂TKE/∂z)

        where:
        - P = shear production
        - B = buoyancy term
        - ε = dissipation (treated implicitly)
        - Last term is vertical diffusion (treated implicitly)

        **Corresponds to**: GGL90_CALC.F TKE stepping logic

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
                diss_rate = self.params.ceps * sqrt_tke_k / mixing_length[k]

                # GGL90_CALC uses KappaE(k) at the surface-adjacent
                # interface and averages adjacent KappaE values below it.
                kappa_up = kappa_e[k] if k == 1 else 0.5 * (
                    kappa_e[k] + kappa_e[k - 1]
                )
                a[k] = -impl_fac * dt * kappa_up / (dz[k - 1] * dr_c[k - 1])

                if k == nz - 1:
                    # MITgcm forms a virtual bottom-neighbor coefficient, then
                    # moves its Dirichlet contribution to the right-hand side.
                    kappa_dn = kappa_e[k]
                    c[k] = -impl_fac * dt * kappa_dn / (dz[k] * dr_c[k - 1])
                else:
                    kappa_dn = 0.5 * (kappa_e[k] + kappa_e[k + 1])
                    c[k] = -impl_fac * dt * kappa_dn / (dz[k] * dr_c[k])

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
    ) -> GGL90Output:
        """
        Compute GGL90 mixing coefficients for a single column.

        Roadmap of this routine (calculations in order):
            Step 1: Compute stratification and shear (N², S²) — shared physics_basis
            Step 2: Compute mixing length (from TKE and N², with limits) — scheme_specific
            Step 3: Compute viscosity and diffusivity (κ_m, κ_h) — mixing_coefficients
            Step 4: Compute TKE budget terms (production, buoyancy, dissipation) — scheme_specific
            Step 5: Step TKE forward in time (implicit tridiagonal solve) — local
            Step 6: Assemble output

        Unlike KPP, GGL90 is prognostic: TKE is a state variable. The updated
        TKE (tke_new) is returned and must be fed back on the next call.

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
        # depth-to-surface / depth-to-bottom drive the mixing-length limiters.
        # z is positive-up (z[0] shallowest/least negative, z[-1] deepest/most
        # negative), so both distances must be built as (shallow - deep) to
        # come out positive.
        depth_to_surface = z[0] - z
        depth_to_bottom = z - z[-1]
        mixing_length, r_mixing_length = self.mixing_length_calc.compute(
            tke, n_square, dz, depth_to_surface, depth_to_bottom, mask
        )

        # ===== Step 3: Compute viscosity and diffusivity =====
        kappa_m, kappa_h = compute_viscosity_diffusivity(
            tke, mixing_length, mask, self.params, n_square, shear_square,
            background_visc=background_visc, background_diff=background_diff,
        )

        # ===== Step 4: Compute TKE budget terms =====
        production = compute_tke_production(kappa_m, shear_square, mask)
        buoyancy = compute_tke_buoyancy(kappa_h, n_square, mask)
        dissipation = compute_tke_dissipation(tke, mixing_length, self.params.ceps, mask)

        # ===== Step 5: Step TKE forward in time =====
        tke_new = self.step_tke_forward(
            tke, production, buoyancy, mixing_length, dz, dt, mask, u_star_sq,
            kappa_m=kappa_m,
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
