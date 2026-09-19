"""
Main KPP driver class for column-wise mixing computations.

This is the Python equivalent of KPP_CALC and KPPMIX in MITgcm.

Orchestrates:
  1. Surface forcing diagnosis (ustar, buoyancy fluxes)
  2. Velocity shear computation
  3. Interior mixing from Richardson number — from kpp_routines
  4. Boundary layer depth diagnosis — from kpp_scheme_specific
  5. Boundary layer mixing coefficient computation — from kpp_scheme_specific
  6. Enhancement at mixed-layer base — from kpp_scheme_specific
  7. Coefficient combination and output formatting

Reference:
    Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing:
    A review and a model with a nonlocal boundary layer parameterization.
    Reviews of Geophysics, 32(4), 363-403.
"""

import numpy as np
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

from .kpp_parameters import KPPParameters
from main.eos import compute_buoyancy_gradients
from .kpp_routines import build_wscale_lookup_tables, ri_iwmix
from .kpp_scheme_specific import (
    diagnose_bl_depth,
    compute_bl_mixing,
    enhance_at_interface,
)


@dataclass
class KPPOutput:
    """Container for KPP output fields.

    Vertical staggering matches MITgcm's output arrays index-for-index (so no
    remapping is needed to compare against F77 MITgcm):
      * visc_az[k], diff_kz_s[k], diff_kz_t[k] are at the TOP face of cell k
        (interface between cells k-1 and k); index 0 is the surface face and is
        0 (no surface diffusive flux). This is MITgcm KPPviscAz/KPPdiffKzS/
        KPPdiffKzT (kpp_calc.F:574-588; kpp_transport_t.F:21-25).
      * ghat[k] is at the BOTTOM face of cell k (MITgcm keeps this half-level
        offset from diffKz; the diffusion flux at top face k pairs diffKz[k]
        with ghat[k-1]).
    """

    # Primary mixing coefficients [m^2/s], at TOP face of cell k (surface = 0)
    visc_az: np.ndarray  # Vertical viscosity
    diff_kz_s: np.ndarray  # Vertical diffusivity for salt
    diff_kz_t: np.ndarray  # Vertical diffusivity for temperature

    # Nonlocal transport [s/m^2], at BOTTOM face of cell k
    ghat: np.ndarray

    # Boundary layer depth [m]
    hbl: float

    # Diagnostics
    bulk_ri: Optional[np.ndarray] = None
    bfsfc: Optional[float] = None
    ustar: Optional[float] = None
    shear_sq: Optional[np.ndarray] = None

    # Forcing validation (Python-computed values when validate_forcing=True)
    ustar_computed: Optional[float] = None
    bo_computed: Optional[float] = None
    bosol_computed: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'KPPviscAz': self.visc_az,
            'KPPdiffKzS': self.diff_kz_s,
            'KPPdiffKzT': self.diff_kz_t,
            'KPPghat': self.ghat,
            'KPPhbl': self.hbl,
            'KPPbfsfc': self.bfsfc,
            'KPPustar': self.ustar,
        }


class KPPDriver:
    """
    Main driver for KPP mixing scheme.

    Computes vertical mixing coefficients for a single ocean column.
    Unlike GGL90 (prognostic), KPP is diagnostic: it computes mixing coefficients
    directly from the current column state with no prognostic variable.

    **Corresponds to**: KPP_CALC.F and KPPMIX in MITgcm (orchestrator)
    """

    def __init__(self, params: Optional[KPPParameters] = None):
        """
        Initialize KPP driver.

        Parameters
        ----------
        params : KPPParameters, optional
            Configuration object. If None, uses defaults.
        """
        self.params = params if params is not None else KPPParameters()

        # Build lookup tables
        self.wmt, self.wst = build_wscale_lookup_tables(self.params)

    def compute_mixing(
        self,
        theta: np.ndarray,
        salt: np.ndarray,
        u_vel: np.ndarray,
        v_vel: np.ndarray,
        depth: np.ndarray,
        cell_thickness: np.ndarray,
        tau_x: float = None,
        tau_y: float = None,
        q_net: float = None,
        q_sw: float = None,
        fw_flux: float = None,
        coriol: float = 1.0e-4,
        background_visc: float = 1.0e-4,
        background_diff_s: float = 1.0e-5,
        background_diff_t: float = 1.0e-5,
        # Optional: pre-computed forcing values (for validation against MITgcm)
        ustar_forcing: float = None,
        bo_forcing: float = None,
        bosol_forcing: float = None,
    ) -> KPPOutput:
        """
        Compute KPP mixing coefficients for a single column.

        Roadmap of this routine (calculations in order):
            Step 1: Compute density and buoyancy gradients (dbloc, dbsfc)
            Step 2: Compute surface forcing (ustar, buoyancy forcing bo/bosol)
            Step 3: Compute velocity shear (shsq, dvsq)
            Step 4: Interior mixing from Richardson number (Ri-based) — kpp_routines.ri_iwmix
            Step 5: Diagnose boundary-layer depth (hbl) — kpp_scheme_specific.diagnose_bl_depth
            Step 6: Compute boundary-layer mixing profiles + nonlocal transport — kpp_scheme_specific.compute_bl_mixing
            Step 7: Enhance mixing at the boundary-layer base interface — kpp_scheme_specific.enhance_at_interface
            Step 8: Combine interior and boundary-layer mixing (bottom-of-cell)
            Step 9: Re-index to MITgcm top-of-cell output convention
            Step 10: Assemble output

        Unlike GGL90, KPP is diagnostic: it computes mixing coefficients
        directly from the current column state with no prognostic variable.

        **Corresponds to**: KPP_CALC.F (orchestration)

        Parameters
        ----------
        theta : np.ndarray, shape (nz,)
            Potential temperature [°C]
        salt : np.ndarray, shape (nz,)
            Salinity [psu]
        u_vel : np.ndarray, shape (nz,)
            Zonal velocity [m/s]
        v_vel : np.ndarray, shape (nz,)
            Meridional velocity [m/s]
        depth : np.ndarray, shape (nz,)
            Depth of cell centers (negative, increasing downward) [m]
        cell_thickness : np.ndarray, shape (nz,)
            Thickness of each cell [m]
        tau_x : float, optional
            Zonal wind stress / rho [m^2/s^2]. Default: None (0.0)
            Required if computing forcing from fluxes or validating forcing
        tau_y : float, optional
            Meridional wind stress / rho [m^2/s^2]. Default: None (0.0)
            Required if computing forcing from fluxes or validating forcing
        q_net : float, optional
            Net surface heat flux (>0 = into ocean) [W/m^2]. Default: None (0.0)
        q_sw : float, optional
            Shortwave radiation component [W/m^2]. Default: None (0.0)
        fw_flux : float, optional
            Freshwater flux (E-P-R, >0 = into ocean) [m/s]. Default: None (0.0)
        coriol : float, optional
            Coriolis parameter [1/s]
        background_visc : float, optional
            Background viscosity [m^2/s]
        background_diff_s : float, optional
            Background diffusivity for salt [m^2/s]
        background_diff_t : float, optional
            Background diffusivity for temperature [m^2/s]
        ustar_forcing : float, optional
            Pre-computed friction velocity [m/s] (for MITgcm validation)
        bo_forcing : float, optional
            Pre-computed turbulent buoyancy forcing [m^2/s^3] (for MITgcm validation)
        bosol_forcing : float, optional
            Pre-computed radiative buoyancy forcing [m^2/s^3] (for MITgcm validation)

        Notes
        -----
        Three usage modes, determined automatically based on input:

        **Mode 1: Pre-computed forcing** (standard validation)
            Provide: ustar_forcing, bo_forcing, bosol_forcing (all 3)
            Omit: tau_x, tau_y, q_net, q_sw, fw_flux
            → Uses pre-computed forcing for mixing calculation

        **Mode 2: Compute forcing** (standalone)
            Provide: tau_x, tau_y, q_net, q_sw, fw_flux (all 5)
            Omit: ustar_forcing, bo_forcing, bosol_forcing
            → Computes forcing from raw fluxes

        **Mode 3: Forcing validation**
            Provide: ALL 8 parameters (both sets above)
            → Computes forcing from raw fluxes, validates against pre-computed
               (1% tolerance), then uses pre-computed for mixing

        Partial sets raise ValueError with clear guidance.

        Returns
        -------
        KPPOutput
            Mixing coefficients and diagnostics
        """
        nz = len(theta)

        # ===== Step 1: Compute density and buoyancy =====
        rho_surf, dbloc, dbsfc, ttalpha, ssbeta = compute_buoyancy_gradients(
            theta, salt, depth, self.params.rho_const, self.params.gravity, use_jmd95=True
        )

        # Smooth dbloc if requested
        dbloc_smooth = dbloc.copy()
        # Note: horizontal smoothing requires 2D/3D data, skipped for 1D columns

        # ===== Step 2: Compute surface forcing =====
        # Determine mode based on what parameters are provided:
        # Mode 1: Pre-computed forcing only (validation, MITgcm comparison)
        # Mode 2: Raw surface fluxes only (standalone, compute forcing)
        # Mode 3: Both provided (forcing validation mode)
        # Error: Neither complete, or partial sets

        # Check what's provided
        precomputed_complete = (
            ustar_forcing is not None and
            bo_forcing is not None and
            bosol_forcing is not None
        )
        precomputed_partial = (
            not precomputed_complete and
            (ustar_forcing is not None or bo_forcing is not None or bosol_forcing is not None)
        )

        raw_fluxes_complete = (
            tau_x is not None and
            tau_y is not None and
            q_net is not None and
            q_sw is not None and
            fw_flux is not None
        )
        raw_fluxes_partial = (
            not raw_fluxes_complete and
            (tau_x is not None or tau_y is not None or
             q_net is not None or q_sw is not None or fw_flux is not None)
        )

        # Validate input combinations
        if precomputed_partial:
            raise ValueError(
                "Incomplete pre-computed forcing provided.\n"
                "Must provide ALL THREE of: ustar_forcing, bo_forcing, bosol_forcing\n"
                f"Got: ustar_forcing={ustar_forcing is not None}, "
                f"bo_forcing={bo_forcing is not None}, "
                f"bosol_forcing={bosol_forcing is not None}"
            )

        if raw_fluxes_partial and not precomputed_complete:
            # Incomplete raw fluxes and no pre-computed forcing to fall back on
            raise ValueError(
                "Incomplete surface forcing provided.\n"
                "Must provide one of:\n"
                "  1. ALL FIVE raw fluxes: tau_x, tau_y, q_net, q_sw, fw_flux\n"
                "  2. ALL THREE pre-computed: ustar_forcing, bo_forcing, bosol_forcing\n"
                "  3. ALL EIGHT (both sets above for forcing validation)\n"
                f"\nGot raw fluxes: tau_x={tau_x is not None}, tau_y={tau_y is not None}, "
                f"q_net={q_net is not None}, q_sw={q_sw is not None}, fw_flux={fw_flux is not None}\n"
                f"Got pre-computed: ustar_forcing={ustar_forcing is not None}, "
                f"bo_forcing={bo_forcing is not None}, bosol_forcing={bosol_forcing is not None}"
            )

        if not precomputed_complete and not raw_fluxes_complete:
            raise ValueError(
                "No forcing provided.\n"
                "Must provide one of:\n"
                "  1. ALL FIVE raw fluxes: tau_x, tau_y, q_net, q_sw, fw_flux\n"
                "  2. ALL THREE pre-computed: ustar_forcing, bo_forcing, bosol_forcing\n"
                "  3. ALL EIGHT (both sets above for forcing validation)"
            )

        # Track computed forcing for output (used in validation mode)
        ustar_computed_out = None
        bo_computed_out = None
        bosol_computed_out = None

        # Execute appropriate mode
        if precomputed_complete and raw_fluxes_complete:
            # MODE 3: Forcing validation - compute and validate
            ustar_computed, bo_computed, bosol_computed = self._compute_surface_forcing(
                tau_x, tau_y, q_net, q_sw, fw_flux,
                rho_surf, ttalpha[0], ssbeta[0], salt[0]
            )
            # Store for output
            ustar_computed_out = ustar_computed
            bo_computed_out = bo_computed
            bosol_computed_out = bosol_computed

            self._validate_forcing_computation(
                ustar_forcing, bo_forcing, bosol_forcing,
                ustar_computed, bo_computed, bosol_computed
            )
            # Use pre-computed forcing for mixing calculation (validation passed)
            ustar, bo, bosol = ustar_forcing, bo_forcing, bosol_forcing

        elif precomputed_complete:
            # MODE 1: Use pre-computed forcing (standard validation)
            ustar, bo, bosol = ustar_forcing, bo_forcing, bosol_forcing

        else:  # raw_fluxes_complete must be True
            # MODE 2: Compute forcing from raw fluxes (standalone)
            ustar, bo, bosol = self._compute_surface_forcing(
                tau_x, tau_y, q_net, q_sw, fw_flux,
                rho_surf, ttalpha[0], ssbeta[0], salt[0]
            )
            # Store for output
            ustar_computed_out = ustar
            bo_computed_out = bo
            bosol_computed_out = bosol

        # ===== Step 3: Compute velocity shear =====
        shsq, dvsq = self._compute_shear(u_vel, v_vel, depth, cell_thickness)

        # ===== Step 4: Interior mixing (Ri-based) =====
        # Background diffusivities
        bg_visc = np.full(nz, background_visc)
        bg_diff_s = np.full(nz, background_diff_s)
        bg_diff_t = np.full(nz, background_diff_t)

        diffus_visc_int, diffus_s_int, diffus_t_int = ri_iwmix(
            shsq, dbloc, dbloc_smooth, bg_diff_s, bg_diff_t, self.params,
            zgrid=depth, visc_nr_bg=bg_visc
        )

        # ===== Step 5: Diagnose boundary layer depth =====
        # Compute Ritop (numerator of bulk Richardson number).
        # depth is negative-down (depth[0] ~ 0 at surface, more negative with depth),
        # so (depth[0]-depth[k]) is the positive distance from the surface to level k,
        # matching Fortran's (zgrid(1)-zgrid(kl)). Getting this sign wrong makes Rib
        # negative under stable stratification and the Ricr criterion never trips.
        Ritop = np.zeros(nz)
        for k in range(nz):
            Ritop[k] = (depth[0] - depth[k]) * dbsfc[k]

        hbl, bfsfc, stable, casea, kbl, bulk_ri = diagnose_bl_depth(
            dvsq, dbloc, Ritop, ustar, bo, bosol, coriol,
            depth, cell_thickness, self.wmt, self.wst, self.params
        )

        # ===== Step 6: Boundary layer mixing =====
        blmc_visc, blmc_s, blmc_t, ghat, dkm1 = compute_bl_mixing(
            ustar, bfsfc, hbl, stable, casea,
            (diffus_visc_int, diffus_s_int, diffus_t_int),
            kbl, depth, cell_thickness, self.wmt, self.wst, self.params
        )

        # ===== Step 7: Enhance at interface =====
        blmc_visc, blmc_s, blmc_t, ghat = enhance_at_interface(
            dkm1, hbl, kbl,
            (diffus_visc_int, diffus_s_int, diffus_t_int),
            casea, depth, cell_thickness,
            (blmc_visc, blmc_s, blmc_t), ghat
        )

        # ===== Step 8: Combine interior and BL mixing =====
        # These internal profiles are on the BOTTOM-of-cell convention: index k
        # is the interface below cell k (between cells k and k+1), matching the
        # internal layout of MITgcm's kpp_routines.F diffus(i,k,mr).
        visc_bot = np.zeros(nz)
        diff_s_bot = np.zeros(nz)
        diff_t_bot = np.zeros(nz)

        for k in range(nz):
            if k < kbl:
                # Within boundary layer: use BL profile
                visc_bot[k] = max(blmc_visc[k], background_visc)
                diff_s_bot[k] = max(blmc_s[k], background_diff_s)
                diff_t_bot[k] = max(blmc_t[k], background_diff_t)
            else:
                # Below boundary layer: use interior mixing
                visc_bot[k] = diffus_visc_int[k]
                diff_s_bot[k] = diffus_s_int[k]
                diff_t_bot[k] = diffus_t_int[k]
                ghat[k] = 0.0  # No nonlocal transport below BL

        # ===== Step 9: Re-index to MITgcm TOP-of-cell output convention =====
        # MITgcm reports KPPdiffKzT/S/viscAz at the TOP face of cell k, with the
        # surface entry = 0. It builds these by shifting its internal bottom-of-
        # cell array by one on output (kpp_calc.F:574-588, vddiff(k-1)->KPP*(k)).
        # We reproduce that exactly so our arrays overlay MITgcm's index-for-index:
        #   visc_az[k]  = visc_bot[k-1]   (top face of cell k), visc_az[0] = 0
        # ghat is NOT shifted: MITgcm keeps it at the BOTTOM of cell k
        # (kpp_transport_t.F:21-25); the solver pairs diffKz[k] with ghat[k-1].
        visc_az = np.zeros(nz)
        diff_kz_s = np.zeros(nz)
        diff_kz_t = np.zeros(nz)
        visc_az[1:] = visc_bot[: nz - 1]
        diff_kz_s[1:] = diff_s_bot[: nz - 1]
        diff_kz_t[1:] = diff_t_bot[: nz - 1]

        # ===== Step 10: Create output =====
        return KPPOutput(
            visc_az=visc_az,
            diff_kz_s=diff_kz_s,
            diff_kz_t=diff_kz_t,
            ghat=ghat,
            hbl=hbl,
            bfsfc=bfsfc,
            ustar=ustar,
            shear_sq=shsq,
            bulk_ri=bulk_ri,
            ustar_computed=ustar_computed_out,
            bo_computed=bo_computed_out,
            bosol_computed=bosol_computed_out,
        )

    def _compute_surface_forcing(
        self,
        tau_x: float,
        tau_y: float,
        q_net: float,
        q_sw: float,
        fw_flux: float,
        rho_surf: float,
        ttalpha: float,
        ssbeta: float,
        salt_surf: float,
    ) -> Tuple[float, float, float]:
        """
        Compute surface forcing terms.

        Returns
        -------
        ustar : float
            Friction velocity [m/s]
        bo : float
            Turbulent (non-penetrating) buoyancy forcing [m^2/s^3]
        bosol : float
            Radiative (penetrating) buoyancy forcing [m^2/s^3]; 0 unless
            config.shortwave_heating is enabled, in which case q_sw is withheld
            from `bo` and instead applied with depth via shortwave.swfrac().
        """
        # Friction velocity
        tau_mag_sq = tau_x**2 + tau_y**2
        if tau_mag_sq < self.params.phepsi**2:
            ustar = np.sqrt(self.params.phepsi)
        else:
            ustar = (tau_mag_sq**0.5)**0.5

        use_penetrating_sw = (
            self.params.shortwave_heating and self.params.select_penetrating_sw >= 1
        )

        # Non-penetrating heat flux driving bo. If shortwave penetration is enabled,
        # Qsw is withheld here and applied separately (with depth) as bosol below.
        q_non_sw = (q_net - q_sw) if use_penetrating_sw else q_net
        temp_flux = q_non_sw / (self.params.rho_const * self.params.heat_capacity_cp)

        # Virtual salt flux from freshwater flux: freshening (fw_flux > 0, into
        # ocean) dilutes salinity, so the induced salt flux is negative.
        salt_flux = -fw_flux * salt_surf

        # Turbulent (non-penetrating) buoyancy forcing.
        #
        # BUG FIX (Python porting error): the divisor is the surface in-situ
        # density rhoSurf alone (~1024 kg/m^3), NOT (rhoSurf + rho_const).
        # rho_surf as returned here is already the FULL in-situ surface density
        # (rho_anom + rho_const in compute_buoyancy_gradients), so adding
        # rho_const again nearly doubled the denominator (~2059) and halved bo.
        # MITgcm kpp_forcing_surf.F:225-229 divides by rhoSurf(i,j) directly.
        # The Fortran is correct, so this is fixed unconditionally.
        bo = -self.params.gravity * (ttalpha * temp_flux + ssbeta * salt_flux) / rho_surf

        # Radiative (penetrating) buoyancy forcing. Same denominator fix; cf.
        # kpp_forcing_surf.F:236-238 (bosol = g*alpha*Qsw*recip_Cp*recip_rhoConst/rhoSurf).
        if use_penetrating_sw:
            sw_flux = q_sw / (self.params.rho_const * self.params.heat_capacity_cp)
            bosol = self.params.gravity * ttalpha * sw_flux / rho_surf
        else:
            bosol = 0.0

        return ustar, bo, bosol

    def _validate_forcing_computation(
        self,
        ustar_mitgcm: float,
        bo_mitgcm: float,
        bosol_mitgcm: float,
        ustar_python: float,
        bo_python: float,
        bosol_python: float,
    ) -> None:
        """
        Validate that Python forcing computation matches MITgcm.

        Raises ValueError if differences exceed tolerance.

        Parameters
        ----------
        ustar_mitgcm, bo_mitgcm, bosol_mitgcm : float
            Pre-computed forcing values from MITgcm
        ustar_python, bo_python, bosol_python : float
            Python-computed forcing values from _compute_surface_forcing

        Raises
        ------
        ValueError
            If any forcing term differs by more than 1% (rtol=0.01)
        """
        import numpy as np

        # Tolerance for forcing validation: 1% relative error
        # This accounts for potential differences in flux computation between
        # MITgcm's complex surface forcing calculation and the simplified
        # KPP forcing interface
        rtol = 0.01  # 1%
        atol = 1e-16  # Absolute tolerance for near-zero values

        errors = []

        # Validate ustar
        if not np.isclose(ustar_python, ustar_mitgcm, rtol=rtol, atol=atol):
            rel_err = abs(ustar_python - ustar_mitgcm) / (abs(ustar_mitgcm) + atol)
            errors.append(
                f"ustar: Python={ustar_python:.15e}, MITgcm={ustar_mitgcm:.15e}, "
                f"rel_err={rel_err:.3e}"
            )

        # Validate bo
        if not np.isclose(bo_python, bo_mitgcm, rtol=rtol, atol=atol):
            rel_err = abs(bo_python - bo_mitgcm) / (abs(bo_mitgcm) + atol)
            errors.append(
                f"bo: Python={bo_python:.15e}, MITgcm={bo_mitgcm:.15e}, "
                f"rel_err={rel_err:.3e}"
            )

        # Validate bosol
        if not np.isclose(bosol_python, bosol_mitgcm, rtol=rtol, atol=atol):
            rel_err = abs(bosol_python - bosol_mitgcm) / (abs(bosol_mitgcm) + atol)
            errors.append(
                f"bosol: Python={bosol_python:.15e}, MITgcm={bosol_mitgcm:.15e}, "
                f"rel_err={rel_err:.3e}"
            )

        if errors:
            raise ValueError(
                "Forcing computation validation FAILED (tolerance: 1%):\n" +
                "\n".join(errors) +
                "\n\nThe Python _compute_surface_forcing does not match MITgcm's "
                "kpp_forcing_surf.F within 1% relative error tolerance. "
                "This indicates a potential issue in the forcing computation port."
            )

    def _compute_shear(
        self,
        u_vel: np.ndarray,
        v_vel: np.ndarray,
        depth: np.ndarray,
        cell_thickness: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute velocity shear terms.

        Returns
        -------
        shsq : np.ndarray, shape (nz,)
            Local velocity shear squared at interfaces [m^2/s^2]
        dvsq : np.ndarray, shape (nz,)
            Velocity shear squared relative to surface [m^2/s^2]
        """
        nz = len(u_vel)

        # Local shear at interfaces
        shsq = np.zeros(nz)
        for k in range(nz - 1):
            du = u_vel[k] - u_vel[k+1]
            dv = v_vel[k] - v_vel[k+1]
            shsq[k] = du**2 + dv**2

        # Shear relative to surface
        dvsq = np.zeros(nz)
        for k in range(nz):
            du = u_vel[0] - u_vel[k]
            dv = v_vel[0] - v_vel[k]
            dvsq[k] = du**2 + dv**2

        return shsq, dvsq
