"""
Main KPP driver class for column-wise mixing computations.

This is the Python equivalent of KPP_CALC and KPPMIX in MITgcm.

Orchestrates:
  0. Input geometry guard (z-coordinate columns only, ``ValueError`` otherwise,
     1DMIX-072/073) — from main.column_grid
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

import warnings
import numpy as np
from typing import Tuple, Optional, Dict
from dataclasses import dataclass

from .kpp_parameters import KPPParameters
from main.eos import compute_buoyancy_gradients
# Shared z-coordinate input guard (moved to main.column_grid under 1DMIX-073 so GGL90 uses
# the same check); re-exported here so `from KPP.kpp_core_driver import
# validate_zcoordinate_geometry, MAX_ZCOORD_EXTENT_M` keeps working.
from main.column_grid import MAX_ZCOORD_EXTENT_M, validate_zcoordinate_geometry  # noqa: F401
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
    bo: Optional[float] = None
    bosol: Optional[float] = None
    shear_sq: Optional[np.ndarray] = None

    # KPPMIX's other direct "I"-only arguments (unmodified by KPPMIX; exposed
    # so callers -- e.g. exporting a Python-driven column to the standalone
    # Fortran KPPMIX driver -- can replay the identical inputs without
    # duplicating this method's derivation of them).
    buoy_freq_sq: Optional[np.ndarray] = None  # dbloc
    dVsq: Optional[np.ndarray] = None
    Ritop: Optional[np.ndarray] = None

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


def _validate_column_input(name: str, arr, nz: int, nonnegative: bool):
    """Validate an optional per-column input of ``compute_mixing`` (1DMIX-071).

    Returns ``None`` for ``None`` (the exact no-op), otherwise a float64 copy of shape
    ``(nz,)``. Raises ``ValueError`` for a wrong shape, any non-finite value, or (when
    ``nonnegative``) any negative value.
    """
    if arr is None:
        return None
    a = np.array(arr, dtype=np.float64)
    if a.shape != (nz,):
        raise ValueError(f"{name} must have shape ({nz},) (one value per level), got {a.shape}")
    if not np.all(np.isfinite(a)):
        raise ValueError(f"{name} must be finite (found {int(np.sum(~np.isfinite(a)))} non-finite value(s))")
    if nonnegative and np.any(a < 0.0):
        raise ValueError(f"{name} is a squared quantity and must be >= 0 (min={a.min():.6g})")
    return a


def _validate_levels_below(depth, cell_thickness, depth_below, cell_thickness_below):
    """Validate the optional model levels below the supplied column (1DMIX-075).

    Returns ``(depth_below, cell_thickness_below)`` as float64 arrays; both are empty when
    neither input is given or both are empty (the column is then the full model depth).
    Raises ``ValueError`` if only one of the two is given, if they are not 1-D arrays of the
    same length, if any value is non-finite, if a thickness is not > 0, if a depth is > 0,
    if the levels are not strictly deeper than the column and strictly deepening, or if the
    combined column fails ``validate_zcoordinate_geometry``.
    """
    if depth_below is None and cell_thickness_below is None:
        return np.zeros(0), np.zeros(0)
    if depth_below is None or cell_thickness_below is None:
        raise ValueError("depth_below and cell_thickness_below must be given together "
                         "(got only one of them)")
    zb = np.array(depth_below, dtype=np.float64)
    hb = np.array(cell_thickness_below, dtype=np.float64)
    if zb.ndim != 1 or hb.ndim != 1 or zb.shape != hb.shape:
        raise ValueError("depth_below and cell_thickness_below must be 1-D arrays of the same "
                         f"length, got shapes {zb.shape} and {hb.shape}")
    if zb.size == 0:
        return zb, hb
    if not (np.all(np.isfinite(zb)) and np.all(np.isfinite(hb))):
        raise ValueError("depth_below and cell_thickness_below must be finite")
    if np.any(hb <= 0.0):
        raise ValueError(f"cell_thickness_below must be > 0 (min={hb.min():.6g})")
    if np.any(zb > 0.0):
        raise ValueError(f"depth_below must be <= 0 (negative downward; max={zb.max():.6g})")
    deeper = np.concatenate([[np.asarray(depth, dtype=np.float64)[-1]], zb])
    if np.any(np.diff(deeper) >= 0.0):
        raise ValueError("depth_below must be strictly deeper than the last supplied level and "
                         "strictly deepening (negative-down centres)")
    validate_zcoordinate_geometry(
        np.concatenate([np.asarray(depth, dtype=np.float64), zb]),
        np.concatenate([np.asarray(cell_thickness, dtype=np.float64), hb]), scheme="KPP")
    return zb, hb


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
        # Optional: salt-plume haline buoyancy forcing (1DMIX-034 part 2).
        # Independent of the ustar/bo/bosol forcing-mode switch above --
        # always additive, default 0.0 is a true no-op regardless of mode
        # (matches MITgcm's own boplume=0 initialization) and only takes
        # effect when self.params.use_salt_plume is True.
        boplume_forcing: float = 0.0,
        sp_depth_forcing: float = 0.0,
        # Investigation-only override (1DMIX-056), passed straight through to
        # kpp_scheme_specific.diagnose_bl_depth. Default None is an exact
        # behavioral no-op -- see that function's own docstring for the exact
        # substitution semantics.
        hbl_override: float = None,
        # Optional tracer-point inputs (1DMIX-071), keyword-only. MITgcm forms shsq,
        # dVsq and the horizontally smoothed dbloc from NEIGHBOURING columns, which a
        # single-column driver cannot see; a caller that has the neighbours (the
        # MITgcm-capture replays) supplies the finished values here. Default None for
        # each is an exact behavioral no-op (the column-local computation below).
        *,
        shsq_forcing: Optional[np.ndarray] = None,
        dvsq_forcing: Optional[np.ndarray] = None,
        dbloc_smooth_forcing: Optional[np.ndarray] = None,
        depth_below: Optional[np.ndarray] = None,
        cell_thickness_below: Optional[np.ndarray] = None,
    ) -> KPPOutput:
        """
        Compute KPP mixing coefficients for a single column.

        Roadmap of this routine (calculations in order):
            Step 1: Compute density and buoyancy gradients (dbloc, dbsfc)
            Step 2: Compute surface forcing (ustar, buoyancy forcing bo/bosol)
            Step 3: Compute velocity shear (shsq, dvsq)
            Step 4: Interior mixing from Richardson number (Ri-based) — kpp_routines.ri_iwmix
                    (then the bottom interior entry is zeroed as in KPPMIX, kpp_routines.F:208; 1DMIX-075)
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
        boplume_forcing : float, optional
            Surface haline buoyancy forcing from salt plumes, boplume(1)
            [m^2/s^3] (1DMIX-034). Default 0.0 (no salt plume). Only
            takes effect when self.params.use_salt_plume is True.
        sp_depth_forcing : float, optional
            Salt plume penetration (e-folding) depth, SPDepth [m]
            (1DMIX-034). Default 0.0.
        hbl_override : float, optional
            Investigation-only (1DMIX-056): substitute this value for the
            diagnosed boundary-layer depth before the boundary-layer shape
            function (`kpp_scheme_specific.compute_bl_mixing`) and downstream
            steps consume it -- see `diagnose_bl_depth`'s own docstring for
            exact semantics. Default `None` is an exact behavioral no-op;
            every existing caller/scenario is unaffected.
        shsq_forcing : np.ndarray, shape (nz,), optional
            (1DMIX-071, keyword-only) MITgcm's ``shsq(k)`` for this column
            (kpp_calc.F:459-495) [m^2/s^2], index k = interface below cell k, in place
            of the column-local ``du**2 + dv**2`` of ``_compute_shear``. Must be finite
            and >= 0. Default None = column-local computation (exact no-op). The last
            element (the bottom of the supplied column) is passed through unchanged.
        dvsq_forcing : np.ndarray, shape (nz,), optional
            (1DMIX-071, keyword-only) MITgcm's ``dVsq(k)`` (kpp_forcing_surf.F:463-504)
            [m^2/s^2], in place of the column-local surface-relative value. Finite and
            >= 0. Supplying it bypasses ``_estimate_reference_velocity`` (MITgcm's dVsq
            already contains its own uRef). Default None = no-op.
        dbloc_smooth_forcing : np.ndarray, shape (nz,), optional
            (1DMIX-071, keyword-only) horizontally smoothed ``dbloc`` (the ``ghat``
            input of KPPMIX, kpp_calc.F:276-289 via ``smooth_horiz``,
            kpp_routines.F:1311-1391) [m/s^2], used ONLY by the gradient-Richardson
            term of ``ri_iwmix`` (kpp_routines.F:1133-1137). Finite; may be negative.
            Default None = ``dbloc.copy()`` (no horizontal smoothing in a single column,
            exact no-op).
        depth_below, cell_thickness_below : np.ndarray, shape (m,), optional
            (1DMIX-075, keyword-only, given together) cell-centre depths (<= 0, negative
            down) and thicknesses (> 0) of the ``m`` MODEL levels that lie below the supplied
            column and are dry there (MITgcm's ``kmtj < Nr``). The supplied column is the
            wet part of the model column (``nz = kmtj``); the model has ``Nr = nz + m``
            levels. MITgcm's ``bldepth`` scans ``kl = 2..Nr`` for the new ``kbl`` with the
            condition ``kbl.EQ.kmtj`` (kpp_routines.F:818-824), so when the first level below
            ``hbl`` is the bottom wet level (or ``hbl`` is deeper than it) the scan continues
            below the bottom and ends with ``kbl = kmtj+1``, the first dry level; ``casea``,
            ``blmix`` and ``enhance`` then use that level's grid. The port reproduces this, and
            this needs the dry levels' grid. Default None (or empty) = the column IS the full
            model depth (``kmtj = Nr``): the scan then ends with ``kbl = Nr`` when no level
            is found, exactly as in MITgcm. The MITgcm-capture replays pass the dry levels of
            each truncated column. ``ValueError`` if only one is given, for a shape/finite/sign
            violation, or if the combined column fails ``validate_zcoordinate_geometry``.

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

        Raises
        ------
        ValueError
            For a partial/absent forcing set (above), and (1DMIX-072) for
            ``depth``/``cell_thickness`` that cannot be a metres-scale
            z-coordinate column -- non-finite, non-positive thickness, positive
            depth, or any extent above ``MAX_ZCOORD_EXTENT_M`` (11,000 m) -- which
            is how pressure-coordinate (Pa) geometry presents; see
            ``validate_zcoordinate_geometry``.

        Returns
        -------
        KPPOutput
            Mixing coefficients and diagnostics
        """
        nz = len(theta)

        # ===== Step 0: Reject non-z-coordinate geometry (1DMIX-072) =====
        # Pure pre-check; raises ValueError, changes no computed value.
        validate_zcoordinate_geometry(depth, cell_thickness, scheme="KPP")
        # Model levels below the supplied (wet) column, if any (1DMIX-075); validated like the
        # 1DMIX-071 inputs, plus the combined-column z-coordinate guard.
        depth_below_v, thk_below_v = _validate_levels_below(
            depth, cell_thickness, depth_below, cell_thickness_below)
        below_kw = {}
        if depth_below_v.size:
            below_kw = {'zgrid_below': depth_below_v, 'hwide_below': thk_below_v}

        # ===== Step 1: Compute density and buoyancy =====
        rho_surf, dbloc, dbsfc, ttalpha, ssbeta = compute_buoyancy_gradients(
            theta, salt, depth, self.params.rho_const, self.params.gravity, use_jmd95=True
        )

        # Smooth dbloc if requested
        dbloc_smooth = dbloc.copy()
        # Note: horizontal smoothing requires 2D/3D data, skipped for 1D columns --
        # unless the caller (the MITgcm-capture replay, 1DMIX-071) supplies the
        # already smoothed profile through `dbloc_smooth_forcing`.
        shsq_in = _validate_column_input("shsq_forcing", shsq_forcing, nz, nonnegative=True)
        dvsq_in = _validate_column_input("dvsq_forcing", dvsq_forcing, nz, nonnegative=True)
        dbloc_smooth_in = _validate_column_input(
            "dbloc_smooth_forcing", dbloc_smooth_forcing, nz, nonnegative=False)
        if dbloc_smooth_in is not None:
            dbloc_smooth = dbloc_smooth_in

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
        shsq, dvsq = self._compute_shear(
            u_vel, v_vel, depth, cell_thickness,
            dbloc=dbloc, tau_x=tau_x, tau_y=tau_y, ustar=ustar,
            shsq_override=shsq_in, dvsq_override=dvsq_in,
        )

        # ===== Step 4: Interior mixing (Ri-based) =====
        # Background diffusivities
        bg_visc = np.full(nz, background_visc)
        bg_diff_s = np.full(nz, background_diff_s)
        bg_diff_t = np.full(nz, background_diff_t)

        diffus_visc_int, diffus_s_int, diffus_t_int = ri_iwmix(
            shsq, dbloc, dbloc_smooth, bg_diff_s, bg_diff_t, self.params,
            zgrid=depth, visc_nr_bg=bg_visc
        )
        # MITgcm KPPMIX sets the interior coefficients at and below the bottom wet interface to
        # zero before bldepth/blmix read them: `IF (k.GE.kmtj(i)) diffus(i,k,md) = 0.0`
        # (kpp_routines.F:208). 0-based k >= nz-1 is the single bottom entry of this column.
        # Copies: ri_iwmix's own return value is left untouched.
        diffus_visc_int = diffus_visc_int.copy(); diffus_visc_int[nz - 1:] = 0.0
        diffus_s_int = diffus_s_int.copy(); diffus_s_int[nz - 1:] = 0.0
        diffus_t_int = diffus_t_int.copy(); diffus_t_int[nz - 1:] = 0.0

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
            depth, cell_thickness, self.wmt, self.wst, self.params,
            boplume=boplume_forcing, sp_depth=sp_depth_forcing,
            hbl_override=hbl_override, **below_kw,
        )

        # ===== Step 6: Boundary layer mixing =====
        blmc_visc, blmc_s, blmc_t, ghat, dkm1 = compute_bl_mixing(
            ustar, bfsfc, hbl, stable, casea,
            (diffus_visc_int, diffus_s_int, diffus_t_int),
            kbl, depth, cell_thickness, self.wmt, self.wst, self.params, **below_kw
        )

        # ===== Step 7: Enhance at interface =====
        blmc_visc, blmc_s, blmc_t, ghat = enhance_at_interface(
            dkm1, hbl, kbl,
            (diffus_visc_int, diffus_s_int, diffus_t_int),
            casea, depth, cell_thickness,
            (blmc_visc, blmc_s, blmc_t), ghat, **below_kw
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
            bo=bo,
            bosol=bosol,
            shear_sq=shsq,
            buoy_freq_sq=dbloc,
            dVsq=dvsq,
            Ritop=Ritop,
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
            # 1DMIX-022: warn rather than raise. This check is a diagnostic
            # comparison only -- the caller always uses ustar_forcing/
            # bo_forcing/bosol_forcing (MITgcm's own captured ground truth,
            # not this method's Python recomputation) for the actual mixing
            # computation regardless of outcome (see compute_mixing's Mode 3
            # branch). Raising here previously aborted the whole column via
            # the caller's broad exception handling, discarding hbl/visc_az/
            # etc. that have nothing to do with this specific check -- fatal
            # for realistic multi-column configurations (spherical grid +
            # climatological surface restoring) this check wasn't written
            # against, where it fails for the large majority of columns
            # (see open_issues.md 1DMIX-022 for the root causes found so far).
            warnings.warn(
                "Forcing computation validation FAILED (tolerance: 1%):\n" +
                "\n".join(errors) +
                "\n\nThe Python _compute_surface_forcing does not match MITgcm's "
                "kpp_forcing_surf.F within 1% relative error tolerance. "
                "Continuing with MITgcm's captured ustar/bo/bosol for the "
                "mixing computation (see 1DMIX-022)."
            )

    def _compute_shear(
        self,
        u_vel: np.ndarray,
        v_vel: np.ndarray,
        depth: np.ndarray,
        cell_thickness: np.ndarray,
        dbloc: Optional[np.ndarray] = None,
        tau_x: Optional[float] = None,
        tau_y: Optional[float] = None,
        ustar: Optional[float] = None,
        shsq_override: Optional[np.ndarray] = None,
        dvsq_override: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute velocity shear terms.

        ``shsq_override`` / ``dvsq_override`` (1DMIX-071; already validated by
        ``compute_mixing``) replace the respective column-local result; ``None`` is the
        unchanged computation. An overridden ``dvsq`` skips the reference-velocity
        estimate entirely.

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
        if shsq_override is not None:
            shsq = shsq_override.copy()
        if dvsq_override is not None:
            return shsq, dvsq_override.copy()

        if self.params.estimate_uref:
            u_ref, v_ref = self._estimate_reference_velocity(
                u_vel, v_vel, depth, cell_thickness, dbloc, tau_x, tau_y, ustar
            )
        else:
            u_ref, v_ref = u_vel[0], v_vel[0]

        # Shear relative to reference (surface, or resolution-independent
        # reference level when estimate_uref is enabled)
        dvsq = np.zeros(nz)
        for k in range(nz):
            du = u_ref - u_vel[k]
            dv = v_ref - v_vel[k]
            dvsq[k] = du**2 + dv**2

        return shsq, dvsq

    def _estimate_reference_velocity(
        self,
        u_vel: np.ndarray,
        v_vel: np.ndarray,
        depth: np.ndarray,
        cell_thickness: np.ndarray,
        dbloc: np.ndarray,
        tau_x: Optional[float],
        tau_y: Optional[float],
        ustar: Optional[float],
    ) -> Tuple[float, float]:
        """
        Resolution-independent reference velocity for dVsq (KPP_ESTIMATE_UREF).

        Corresponds to KPP_FORCING_SURF's KPP_ESTIMATE_UREF branch
        (kpp_forcing_surf.F:309-419). Gets rid of the vertical-resolution
        dependence of the surface shear term by estimating uRef/vRef at a
        mixed-layer-depth-dependent reference level zRef, rather than simply
        using the top-cell velocity. tau_x/tau_y here are already tau/rho
        (this driver's convention), matching surfaceForcingU/V exactly.
        """
        if tau_x is None or tau_y is None or ustar is None:
            raise ValueError(
                "estimate_uref=True requires tau_x, tau_y, and ustar "
                "(KPP_ESTIMATE_UREF needs the surface momentum forcing, "
                "not just a pre-computed scalar ustar magnitude)."
            )

        params = self.params
        nz = len(u_vel)

        interfaces = np.zeros(nz + 1)
        interfaces[1:] = -np.cumsum(cell_thickness)

        # Shallowest level where the local buoyancy gradient exceeds dB_dz
        # (kpp_forcing_surf.F:326-334); defaults to the deepest level if none.
        k_tmp = nz - 1
        for k in range(nz - 1):
            grad = dbloc[k] / (depth[k] - depth[k+1])
            if grad > params.dB_dz:
                k_tmp = k
                break

        if k_tmp == nz - 1:
            z_ref = abs(interfaces[nz])
        elif k_tmp == 0:
            dbdz2 = dbloc[0] / (depth[0] - depth[1])
            z_ref = cell_thickness[0] * params.dB_dz / dbdz2
        else:
            dbdz1 = dbloc[k_tmp-1] / (depth[k_tmp-1] - depth[k_tmp])
            dbdz2 = dbloc[k_tmp] / (depth[k_tmp] - depth[k_tmp+1])
            z_ref = abs(interfaces[k_tmp]) + cell_thickness[k_tmp] * (
                params.dB_dz - dbdz1
            ) / max(params.phepsi, dbdz2 - dbdz1)

        # Roughness length scale z0 (kpp_forcing_surf.F:320-372)
        drf1 = cell_thickness[0]
        z_fac = abs(interfaces[2]) * np.log(interfaces[2] / interfaces[1]) / cell_thickness[1]
        du01 = u_vel[0] - u_vel[1]
        dv01 = v_vel[0] - v_vel[1]
        temp1 = du01**2 + dv01**2
        temp2 = np.sqrt(temp1) if temp1 >= params.epsln**2 else params.epsln
        z0 = drf1 * (z_fac - temp2 * params.vonk / ustar)
        z0 = max(z0, params.phepsi)

        z_ref = max(params.epsilon * z_ref, z0)

        # Estimate uRef/vRef (kpp_forcing_surf.F:380-419)
        u_ref = u_vel[0]
        v_ref = v_vel[0]
        if z_ref < drf1:
            ustar_x = tau_x / drf1
            ustar_y = tau_y / drf1
            temp1 = ustar_x**2 + ustar_y**2
            temp2 = np.sqrt(temp1) if temp1 >= params.epsln**2 else params.epsln
            temp2 = ustar * (
                np.log(z_ref / drf1) + z0 / z_ref - z0 / drf1
            ) / params.vonk / temp2
            u_ref = u_ref + ustar_x * temp2
            v_ref = v_ref + ustar_y * temp2
        else:
            u_ref = u_ref * drf1
            v_ref = v_ref * drf1
            k = 1
            while k < nz - 1 and abs(interfaces[k+1]) <= z_ref:
                u_ref += cell_thickness[k] * u_vel[k]
                v_ref += cell_thickness[k] * v_vel[k]
                k += 1
            u_ref += max(0.0, z_ref - abs(interfaces[k])) * u_vel[k]
            v_ref += max(0.0, z_ref - abs(interfaces[k])) * v_vel[k]
            u_ref = u_ref / z_ref
            v_ref = v_ref / z_ref

        return u_ref, v_ref
