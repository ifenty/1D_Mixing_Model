"""
KPP-specific physics and boundary layer computation.

This module contains scheme-specific logic for KPP:
  - Boundary layer depth diagnosis using bulk Richardson criterion
  - Boundary layer mixing coefficient computation
  - Enhancement at the mixed-layer base interface
  - Richardson number-based interior mixing
  - Velocity scale lookup tables and computation

Imports common physics helpers from main and shared utilities from kpp_routines.

References:
    Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing,
    Reviews of Geophysics, 32(4), 363-403.
    Translated from MITgcm pkg/kpp/kpp_routines.F and kpp_boundary_layer.py
"""

import numpy as np
from typing import Tuple
from .kpp_parameters import KPPParameters
from .kpp_routines import wscale, ri_iwmix, build_wscale_lookup_tables
from .kpp_shortwave import swfrac
from .kpp_salt_plume import plume_frac


def diagnose_bl_depth(
    dvsq: np.ndarray,
    dbloc: np.ndarray,
    Ritop: np.ndarray,
    ustar: float,
    bo: float,
    bosol: float,
    coriol: float,
    zgrid: np.ndarray,
    hwide: np.ndarray,
    wmt: np.ndarray,
    wst: np.ndarray,
    config: KPPParameters,
    boplume: float = 0.0,
    sp_depth: float = 0.0,
    hbl_override: float = None,
    zgrid_below: np.ndarray = None,
    hwide_below: np.ndarray = None,
) -> Tuple[float, float, float, float, int, np.ndarray]:
    """
    Diagnose boundary layer depth using bulk Richardson criterion.

    Corresponds to bldepth routine in MITgcm kpp_routines.F.

    Parameters
    ----------
    dvsq : np.ndarray, shape (nz,)
        Velocity shear squared relative to surface [m^2/s^2]
    dbloc : np.ndarray, shape (nz,)
        Local buoyancy gradient [m/s^2]
    Ritop : np.ndarray, shape (nz,)
        Numerator of bulk Richardson number [(m/s)^2]
    ustar : float
        Friction velocity [m/s]
    bo : float
        Surface turbulent buoyancy forcing [m^2/s^3]
    bosol : float
        Radiative buoyancy forcing [m^2/s^3]
    coriol : float
        Coriolis parameter [1/s]
    zgrid : np.ndarray, shape (nz,)
        Vertical grid (negative, depth of cell centers) [m]
    hwide : np.ndarray, shape (nz,)
        Cell thicknesses [m]
    wmt, wst : np.ndarray
        Velocity scale lookup tables
    config : KPPParameters
        KPP configuration
    boplume : float, optional
        Surface haline buoyancy forcing from salt plumes, boplume(1)
        [m^2/s^3] (kpp_forcing_surf.F's SALT_PLUME_VOLUME-undef branch).
        Only used when config.use_salt_plume is True; default 0.0 is a
        true no-op (matches MITgcm's own boplume=0 initialization,
        kpp_forcing_surf.F:181-184).
    sp_depth : float, optional
        Salt plume penetration (e-folding) depth, SPDepth [m]
        (pkg/salt_plume/salt_plume_calc_depth.F). Only used when
        config.use_salt_plume is True.
    hbl_override : float, optional
        Investigation-only override (1DMIX-056): when not None, skip this
        routine's own Rib-crossing search, Ekman/Monin-Obukhov stability
        limit and minimum-hbl floor entirely, and use this value as the
        FINAL hbl directly (e.g. a reference implementation's own hbl at the
        same timestep, substituted to isolate whether hbl alone explains a
        downstream mixing-coefficient disagreement). `kbl`/`casea`/the final
        `bfsfc`/`stable` are still recomputed AT this hbl exactly as they
        would be for a diagnosed value, so the shape-function inputs stay
        internally consistent. Default `None` is an exact behavioral no-op
        -- every existing caller is unaffected and the default code path
        remains bit-identical (see `KPPDriver.compute_mixing`'s own
        `hbl_override` passthrough and `tests/test_kpp_hbl_override.py`).
    zgrid_below, hwide_below : np.ndarray, shape (m,), optional
        (1DMIX-075) centre depths and thicknesses of the m model levels below the
        supplied wet column (MITgcm kmtj < Nr). The final `kbl` scan runs over the whole
        model axis (wet levels then these), which reproduces MITgcm's sentinel aliasing
        (kpp_routines.F:818-824, see below). Default None = the column is the full model
        depth (kmtj = Nr).

    Returns
    -------
    hbl : float
        Boundary layer depth [m]
    bfsfc : float
        Surface buoyancy forcing (Bo + absorbed radiation) [m^2/s^3]
    stable : float
        Stability flag (1 = stable, 0 = unstable)
    casea : float
        Case flag (1 = case A, 0 = case B)
    kbl : int
        0-based index, on the model axis (supplied wet column followed by
        `zgrid_below`), of MITgcm's `kbl` (= Fortran kbl - 1): the first level
        below hbl, or the bottom wet level (nz-1) when none is found with no
        dry level below; may be >= nz (a dry level, MITgcm's kbl = kmtj+1).
    Rib : np.ndarray, shape (nz,)
        Bulk Richardson number profile
    """
    nz = len(zgrid)
    # Model axis (1DMIX-075): the supplied wet column, then the dry levels below it.
    if zgrid_below is not None and len(zgrid_below):
        zg_ext = np.concatenate([zgrid, np.asarray(zgrid_below, dtype=np.float64)])
        hw_ext = np.concatenate([hwide, np.asarray(hwide_below, dtype=np.float64)])
    else:
        zg_ext, hw_ext = zgrid, hwide
    n_model = len(zg_ext)          # MITgcm Nr

    # Initialize
    Rib = np.zeros(nz)
    Rib[0] = 0.0
    kbl = nz
    hbl = -zgrid[-1]  # Bottom as default

    # Compute bulk Richardson number at each level
    if config.debug:
        print(f"\nDEBUG: Computing Rib for {nz} levels")
        print(f"  ustar={ustar:.6e}, bo={bo:.6e}, bosol={bosol:.6e}")
        print(f"  Ricr={config.Ricr}")
        print(f"\nDEBUG: Input arrays (first 5 levels):")
        for k in range(min(5, nz)):
            print(f"  k={k}: dvsq={dvsq[k]:.6e}, dbloc={dbloc[k]:.6e}, Ritop={Ritop[k]:.6e}")

    for kl in range(1, nz):
        # Buoyancy forcing felt at this depth: bo is the non-penetrating (turbulent)
        # part, bosol*(1-swfrac(z)) is the fraction of shortwave already absorbed
        # above this depth (and thus already contributing to local buoyancy forcing).
        # MITgcm (kpp_routines.F:505-511) evaluates SWFRAC here with fact=hbf at zgrid(kl),
        # i.e. at depth -hbf*zgrid(kl); the port passes -zgrid[kl] (no hbf factor), which is
        # the same number only for hbf = 1 (MITgcm's default, kpp_readparms.F:116, and the
        # value in every capture). The water type is MITgcm's hard-coded IA by default
        # (KPPParameters.jerlov_water_type, swfrac.F line 92; 1DMIX-080). swfrac returns exactly 0
        # below 200 m (swfrac.F:99-100, 1DMIX-085), here at -zgrid[kl] > 200 m; MITgcm's test is on
        # hbf*(-zgrid(kl)), the same for hbf = 1 (hbf at the trial level: 1DMIX-130).
        if config.shortwave_heating and config.select_penetrating_sw >= 1:
            frac_absorbed = 1.0 - swfrac(-zgrid[kl], config.jerlov_water_type)[0]
            bfsfc = bo + bosol * frac_absorbed
        else:
            bfsfc = bo + bosol

        # Salt-plume haline buoyancy forcing (1DMIX-034 part 2). MITgcm
        # bldepth (kpp_routines.F:534-549) evaluates SALT_PLUME_FRAC at
        # this trial level with fact=hbf and the RAW (negative) zgrid(kl)
        # -- the same (depth, fact) convention as the swfrac call above,
        # confirmed against kpp_forcing_surf.F/salt_plume_frac.F.
        if config.use_salt_plume:
            bfsfc = bfsfc + boplume * plume_frac(zgrid[kl], config.hbf, sp_depth)[0]

        stable_flag = 0.5 + np.sign(bfsfc) * 0.5
        sigma = stable_flag + (1.0 - stable_flag) * config.epsilon
        casea_depth = -zgrid[kl]

        # Compute turbulent velocity scales
        wm, ws = wscale(
            np.array([sigma]),
            np.array([casea_depth]),
            np.array([ustar]),
            np.array([bfsfc]),
            wmt, wst, config
        )

        # Turbulent shear contribution. Below the bottom cell there is no
        # kl+1 level, so mirror MITgcm's ghost point zgrid(Nrp1)=zgrid(Nr)*100
        # (a deep dummy level) rather than clamping the index, which would
        # make the denominator zero.
        zgrid_next = zg_ext[kl + 1] if kl + 1 < n_model else zg_ext[-1] * 100.0
        bvsq = 0.5 * (
            dbloc[kl-1] / (zgrid[kl-1] - zgrid[kl]) +
            dbloc[kl] / (zgrid[kl] - zgrid_next)
        )

        if bvsq == 0.0:
            vtsq = 0.0
        else:
            vtsq = -zgrid[kl] * ws[0] * np.sqrt(abs(bvsq)) * config.Vtc

        # Bulk Richardson number
        tempVar1 = dvsq[kl] + vtsq
        if config.smooth_regularisation:
            tempVar2 = tempVar1 + config.phepsi
        else:
            tempVar2 = max(tempVar1, config.phepsi)

        Rib[kl] = Ritop[kl] / tempVar2

        if config.debug and kl < 10:
            print(f"  k={kl:2d}: depth={-zgrid[kl]:6.1f}m, Rib={Rib[kl]:12.6e}, " +
                  f"Ritop={Ritop[kl]:12.6e}, denom={tempVar2:12.6e}, dvsq={dvsq[kl]:12.6e}, vtsq={vtsq:12.6e}")
            print(f"       bvsq={bvsq:12.6e}, ws={ws[0]:12.6e}, bfsfc={bfsfc:12.6e}, sigma={sigma:.6f}")

            # DETAILED DEBUG for k=1 (ARCH's request)
            if kl == 1:
                print(f"\n       === DETAILED DEBUG for k=1 ===")
                print(f"       bvsq calculation:")
                print(f"         dbloc[0] = {dbloc[0]:.15e}")
                print(f"         dbloc[1] = {dbloc[1]:.15e}")
                print(f"         zgrid[0] = {zgrid[0]:.15e}")
                print(f"         zgrid[1] = {zgrid[1]:.15e}")
                print(f"         zgrid[2] = {zgrid[2]:.15e}")
                print(f"         zgrid_next = {zgrid_next:.15e}")
                print(f"         term1 = dbloc[0]/(zgrid[0]-zgrid[1]) = {dbloc[0]/(zgrid[0]-zgrid[1]):.15e}")
                print(f"         term2 = dbloc[1]/(zgrid[1]-zgrid_next) = {dbloc[1]/(zgrid[1]-zgrid_next):.15e}")
                print(f"         bvsq = 0.5*(term1 + term2) = {bvsq:.15e}")
                print(f"       ws calculation:")
                print(f"         sigma = {sigma:.15e}")
                print(f"         casea_depth (hbl_in) = {casea_depth:.15e} m")
                print(f"         ustar = {ustar:.15e} m/s")
                print(f"         bfsfc = {bfsfc:.15e} m²/s³")
                print(f"         ws = {ws[0]:.15e} m/s")
                print(f"       vtsq calculation:")
                print(f"         -zgrid[1] = {-zgrid[1]:.15e} m (depth)")
                print(f"         sqrt(abs(bvsq)) = {np.sqrt(abs(bvsq)):.15e} s⁻¹")
                print(f"         Vtc = {config.Vtc:.15e}")
                print(f"         vtsq = -zgrid[1] * ws * sqrt(bvsq) * Vtc = {vtsq:.15e}")
                print(f"       Rib calculation:")
                print(f"         Ritop[1] = {Ritop[1]:.15e}")
                print(f"         dvsq[1] = {dvsq[1]:.15e}")
                print(f"         vtsq = {vtsq:.15e}")
                print(f"         tempVar1 = dvsq + vtsq = {tempVar1:.15e}")
                print(f"         phepsi = {config.phepsi:.15e}")
                print(f"         tempVar2 = max(tempVar1, phepsi) = {tempVar2:.15e}")
                print(f"         Rib = Ritop/tempVar2 = {Rib[kl]:.15e}")
                print(f"       === END DETAILED DEBUG ===\n")

    # Find where Rib exceeds Ricr
    # MITgcm logic (kpp_routines.F:655): IF (kbl(i).EQ.kmtj(i) .AND. Rib(i,kl).GT.Ricr) kbl(i) = kl
    # This means: only update kbl if it's still at the bottom (kmtj) and Rib > Ricr.
    # Once kbl is set, it stops updating. So this finds the FIRST level (shallowest) where Rib > Ricr.
    for kl in range(1, nz):
        if kbl == nz and Rib[kl] > config.Ricr:
            kbl = kl
            if config.debug:
                print(f"  -> Rib exceeds Ricr at kl={kl}, depth={-zgrid[kl]:.1f}m, kbl set")

    # Linearly interpolate to find hbl where Rib = Ricr.
    # BUG FIX (Finding 8b, Python porting error / off-by-one guard):
    # MITgcm bldepth (kpp_routines.F:666) guards the interpolation with
    #     IF (kl.GT.1 .AND. kl.LT.kmtj(i))
    # where kl is the 1-based Fortran kbl. With the 0-based Python convention
    # kbl_py = kbl_F - 1 (verified numerically), that guard maps to
    #     kbl > 0 AND kbl < nz - 1.
    if kbl > 0 and kbl < nz - 1:
        tempVar1 = Rib[kbl] - Rib[kbl-1]
        hbl = -zgrid[kbl-1] + (zgrid[kbl-1] - zgrid[kbl]) * (config.Ricr - Rib[kbl-1]) / tempVar1
    else:
        # Bottomed out (Ricr never exceeded, or kbl at the deepest level):
        # leave hbl at the default bottom depth -zgrid(kmtj) = -zgrid[-1],
        # matching the Fortran initialization.
        hbl = -zgrid[-1]

    if hbl_override is None:
        # Surface buoyancy forcing at the interpolated hbl, used only to LIMIT hbl
        # by the Ekman / Monin-Obukhov depths below. MITgcm recomputes bfsfc a
        # second time after the limit (see below); we mirror that ordering.
        if config.shortwave_heating and config.select_penetrating_sw >= 1:
            frac_absorbed = 1.0 - swfrac(np.array([hbl]), config.jerlov_water_type)[0]
            bfsfc = bo + bosol * frac_absorbed
        else:
            bfsfc = bo + bosol
        # Salt-plume haline buoyancy forcing (1DMIX-034 part 2). MITgcm
        # bldepth (kpp_routines.F:730-744) evaluates SALT_PLUME_FRAC here with
        # fact=minusone and the positive trial hbl -- the same (depth, fact)
        # convention as the swfrac call above (fact=minusone there too).
        if config.use_salt_plume:
            bfsfc = bfsfc + boplume * plume_frac(np.array([hbl]), -1.0, sp_depth)[0]
        stable = 0.5 + np.sign(bfsfc) * 0.5
        bfsfc = np.sign(bfsfc) * max(config.phepsi, abs(bfsfc))

        # Limit hbl by Ekman and Monin-Obukhov depths in stable conditions
        if config.limit_hbl_stable and bfsfc > 0.0:
            hekman = config.cekman * ustar / max(abs(coriol), config.phepsi)
            hmonob = config.cmonob * ustar**3 / config.vonk / bfsfc
            hlimit = stable * min(hekman, hmonob) + (stable - 1.0) * (-zg_ext[-1])
            hbl = min(hbl, hlimit)

        # Apply minimum hbl
        if config.min_kpp_hbl is not None:
            hbl = max(hbl, config.min_kpp_hbl)
        else:
            hbl = max(hbl, -zgrid[0])
    else:
        # 1DMIX-056 investigation override: use the supplied hbl directly as
        # the FINAL value, bypassing the Rib-derived pre-limit bfsfc calc and
        # the Ekman/Monin-Obukhov/minimum-hbl limiting above (the substituted
        # value -- e.g. the real Fortran KPPMIX's own hbl at this timestep --
        # already reflects whatever limiting its own source applied; re-
        # applying this port's limiting on top of it would not be a clean
        # substitution). kbl/casea/the final bfsfc/stable below are still
        # recomputed AT this hbl exactly as for a diagnosed value.
        hbl = hbl_override

    # Find new kbl for the (possibly limited) final hbl -- MITgcm bldepth, kpp_routines.F:805-824:
    #     kbl(i) = kmtj(i)                                                  (:807)
    #     DO kl = 2, Nr
    #        IF ( kbl(i).EQ.kmtj(i) .AND. (-zgrid(kl)).GT.hbl(i) ) kbl(i) = kl   (:818-824)
    # kmtj (the bottom wet level) is both the "none found yet" value and a legitimate result, so
    # when the first level below hbl IS the bottom wet level, or hbl is deeper than it, the scan
    # keeps going over the dry levels below (zgrid(kl), kl > kmtj, the model grid) and ends with
    # kbl = kmtj+1 whenever such a level exists (kmtj < Nr). This reproduces that exactly (it is
    # MITgcm's behaviour, not a port choice). 0-based: sentinel = nz-1 (kmtj-1), model axis zg_ext.
    # With no dry level below (the column is the full model depth, kmtj = Nr) "none found"
    # therefore returns nz-1 (MITgcm: kbl = Nr), not nz as before 1DMIX-075.
    kbl = nz - 1
    for kl in range(1, n_model):
        if kbl == nz - 1 and (-zg_ext[kl]) > hbl:
            kbl = kl

    # BUG FIX (Finding 7, Python porting error): recompute the surface buoyancy
    # forcing and stability flag for the FINAL hbl. MITgcm bldepth computes
    # bfsfc/stable twice -- once before the Ekman/Monin-Obukhov limit (used only
    # to compute that limit) and again afterwards for the returned value
    # (kpp_routines.F:823-904). The previous port returned the pre-limit bfsfc.
    # With shortwave penetration on, bfsfc depends on swfrac(hbl), so limiting
    # hbl changes bfsfc; without penetration the two are identical, but we
    # recompute unconditionally to match the reference exactly.
    if config.shortwave_heating and config.select_penetrating_sw >= 1:
        frac_absorbed = 1.0 - swfrac(np.array([hbl]), config.jerlov_water_type)[0]
        bfsfc = bo + bosol * frac_absorbed
    else:
        bfsfc = bo + bosol
    # Salt-plume haline buoyancy forcing (1DMIX-034 part 2), final (post-
    # limit) recomputation -- mirrors kpp_routines.F:867-881, same
    # fact=minusone/positive-hbl convention as the pre-limit call above.
    if config.use_salt_plume:
        bfsfc = bfsfc + boplume * plume_frac(np.array([hbl]), -1.0, sp_depth)[0]
    stable = 0.5 + np.sign(bfsfc) * 0.5
    bfsfc = np.sign(bfsfc) * max(config.phepsi, abs(bfsfc))

    # Determine case A vs case B.
    # BUG FIX (Finding 5, Python porting error / off-by-one): MITgcm
    # (kpp_routines.F:910-913) evaluates
    #     casea = p5 + sign(p5, -zgrid(kl) - p5*hwide(kl) - hbl),  kl = kbl_F
    # The Fortran level kl=kbl_F maps to Python index kbl (= kbl_F - 1), NOT
    # kbl-1. The previous port used zgrid[kbl-1]/hwide[kbl-1], one cell too
    # shallow, which flipped the caseA/caseB decision near the boundary and
    # corrupted the interior-vs-BL matching.
    # (1DMIX-075: kbl is a model-axis index (see the scan above), so zg_ext/hw_ext are indexed
    # directly -- no clamp is needed; when kbl is the first dry level these are MITgcm's
    # zgrid(kmtj+1)/hwide(kmtj+1).)
    casea = 0.5 + np.sign(-zg_ext[kbl] - 0.5*hw_ext[kbl] - hbl) * 0.5

    return hbl, bfsfc, stable, casea, kbl, Rib


def compute_bl_mixing(
    ustar: float,
    bfsfc: float,
    hbl: float,
    stable: float,
    casea: float,
    diffus_interior: Tuple[np.ndarray, np.ndarray, np.ndarray],
    kbl: int,
    zgrid: np.ndarray,
    hwide: np.ndarray,
    wmt: np.ndarray,
    wst: np.ndarray,
    config: KPPParameters,
    zgrid_below: np.ndarray = None,
    hwide_below: np.ndarray = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Tuple[float, float, float]]:
    """
    Compute boundary layer mixing coefficients.

    Corresponds to blmix routine in MITgcm kpp_routines.F.

    Parameters
    ----------
    ustar : float
        Friction velocity [m/s]
    bfsfc : float
        Surface buoyancy forcing [m^2/s^3]
    hbl : float
        Boundary layer depth [m]
    stable : float
        Stability flag (1 = stable, 0 = unstable)
    casea : float
        Case flag (1 = case A, 0 = case B)
    diffus_interior : tuple of np.ndarray
        Interior diffusivities (visc, salt, temp)
    kbl : int
        0-based model-axis index of MITgcm's kbl (see `diagnose_bl_depth`); may be
        >= nz (the first dry level below the column)
    zgrid : np.ndarray
        Vertical grid
    hwide : np.ndarray
        Cell thicknesses
    wmt, wst : np.ndarray
        Velocity scale lookup tables
    config : KPPParameters
        KPP configuration
    zgrid_below, hwide_below : np.ndarray, optional
        (1DMIX-075) grid of the model levels below the supplied wet column, as in
        `diagnose_bl_depth`; None = the column is the full model depth.

    The interior coefficients in `diffus_interior` are read the way MITgcm's blmix reads
    `diffus(i,0:Nrp1,*)` (kpp_routines.F:1534-1548): entry 0 (surface) is 0, the entries at
    and below the bottom wet interface (kpp_routines.F:208: `IF (k.GE.kmtj(i)) diffus = 0`)
    are 0 whatever the caller passes in `diffus_interior[nz-1]`, and `hwide(Nrp1)` is `phepsi`.

    Returns
    -------
    blmc_visc : np.ndarray, shape (nz,)
        BL viscosity profile [m^2/s]
    blmc_s : np.ndarray, shape (nz,)
        BL salt diffusivity profile [m^2/s]
    blmc_t : np.ndarray, shape (nz,)
        BL temperature diffusivity profile [m^2/s]
    ghat : np.ndarray, shape (nz,)
        Nonlocal transport coefficient [s/m^2]. Computed unconditionally,
        matching MITgcm's blmix (kpp_routines.F) -- `config.use_ghat`
        (KPP_GHAT) does NOT gate this value; it gates only whether the
        caller later applies it to a tracer flux (1DMIX-058).
    dkm1 : tuple of float
        BL diffusivities (visc, salt, temp) at the kbl-1 grid level, evaluated
        exactly as MITgcm blmix (kpp_routines.F:1653-1687). These are consumed
        by enhance_at_interface.
    """
    nz = len(zgrid)
    diffus_visc, diffus_s, diffus_t = diffus_interior
    # Model axis and MITgcm's diffus(0:Nrp1) layout (1DMIX-075). dext[f] is Fortran's diffus(f)
    # (f = 1-based level; dext[0] is the surface entry = 0): the wet interfaces 1..kmtj-1
    # hold the passed values, kmtj..Nrp1 are 0 (kpp_routines.F:208).
    if zgrid_below is not None and len(zgrid_below):
        zg_ext = np.concatenate([zgrid, np.asarray(zgrid_below, dtype=np.float64)])
        hw_ext = np.concatenate([hwide, np.asarray(hwide_below, dtype=np.float64)])
    else:
        zg_ext, hw_ext = zgrid, hwide
    n_model = len(zg_ext)          # MITgcm Nr
    hw_ext = np.append(hw_ext, config.phepsi)    # hwide(Nrp1) = phepsi (kpp_init_fixed.F:181)

    def _diffus_ext(d):
        e = np.zeros(n_model + 2)
        e[1:nz] = d[:nz - 1]
        return e
    dext_visc, dext_s, dext_t = _diffus_ext(diffus_visc), _diffus_ext(diffus_s), _diffus_ext(diffus_t)

    # NOTE: MITgcm does not regularize hbl itself in BLMIX (kpp_routines.F:1556-1562).
    # Instead, it relies on BLDEPTH to never produce zero or extremely small hbl values.
    # The minimum hbl is enforced in compute_bl_depth (lines 233-236).
    #
    # However, to prevent runtime warnings when hbl is exactly 0.0 (which can occur
    # in edge cases despite the minimum), we add a safety check here. This matches
    # MITgcm's implicit assumption that hbl > 0 always.
    if hbl == 0.0:
        import warnings
        warnings.warn(f"hbl=0.0 in compute_bl_mixing despite minimum check. "
                     f"ustar={ustar:.3e}, bfsfc={bfsfc:.3e}, stable={stable:.1f}",
                     RuntimeWarning)
        # Return zero mixing (physically correct for no boundary layer)
        blmc_visc = np.zeros(nz)
        blmc_s = np.zeros(nz)
        blmc_t = np.zeros(nz)
        ghat = np.zeros(nz)
        dkm1_visc = 0.0
        dkm1_s = 0.0
        dkm1_t = 0.0
        return blmc_visc, blmc_s, blmc_t, ghat, dkm1_visc, dkm1_s, dkm1_t

    # Compute velocity scales at sigma=1
    # MITgcm: kpp_routines.F:1477-1495
    sigma_one = stable * 1.0 + (1.0 - stable) * config.epsilon
    wm_one, ws_one = wscale(
        np.array([sigma_one]),
        np.array([hbl]),
        np.array([ustar]),
        np.array([bfsfc]),
        wmt, wst, config
    )

    # Regularize velocity scales (MITgcm: kpp_routines.F:1493-1495)
    # MITgcm Fortran: wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
    # IMPORTANT: Fortran's sign(1.0, x) returns +1.0 when x=0, but np.sign(0.0) returns 0.0!
    # We must handle the zero case explicitly to match MITgcm behavior.
    wm_one_mag = max(config.phepsi, abs(wm_one[0]))
    ws_one_mag = max(config.phepsi, abs(ws_one[0]))

    # Apply sign, defaulting to positive when exactly zero (Fortran behavior)
    if wm_one[0] == 0.0:
        wm_one = wm_one_mag
    else:
        wm_one = np.copysign(wm_one_mag, wm_one[0])

    if ws_one[0] == 0.0:
        ws_one = ws_one_mag
    else:
        ws_one = np.copysign(ws_one_mag, ws_one[0])

    # Find interior viscosities and derivatives at hbl (kpp_routines.F:1510-1555).
    # kn is a 0-based model-axis index (Fortran kn - 1); Fortran's diffus(kn) is dext[kn+1].
    kn = int(casea + config.phepsi) * (kbl - 1) + (1 - int(casea + config.phepsi)) * kbl
    # kn < 0 only for a single-wet-level column with no level below (kbl = 0, casea = 1), where
    # MITgcm would read zgrid(0)/hwide(0) = phepsi; nothing observable depends on it there
    # (ghat(1) is zeroed by `k.LT.kbl` and there is no interface), so keep the old clamp.
    kn = max(0, min(kn, n_model - 1))

    if config.match_diffusivities:
        if config.match_derivatives:
            # Match both value and derivative
            delhat = 0.5 * hw_ext[kn] - zg_ext[kn] - hbl
            R = 1.0 - delhat / hw_ext[kn]

            dvdzup = (dext_visc[kn] - dext_visc[kn + 1]) / hw_ext[kn]
            dvdzdn = (dext_visc[kn + 1] - dext_visc[kn + 2]) / hw_ext[kn + 1]
            viscp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))

            dvdzup = (dext_s[kn] - dext_s[kn + 1]) / hw_ext[kn]
            dvdzdn = (dext_s[kn + 1] - dext_s[kn + 2]) / hw_ext[kn + 1]
            difsp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))

            dvdzup = (dext_t[kn] - dext_t[kn + 1]) / hw_ext[kn]
            dvdzdn = (dext_t[kn + 1] - dext_t[kn + 2]) / hw_ext[kn + 1]
            diftp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))
        else:
            delhat = 0.5 * hw_ext[kn] - zg_ext[kn] - hbl
            viscp = 0.0
            difsp = 0.0
            diftp = 0.0

        visch = dext_visc[kn + 1] + viscp * delhat
        difsh = dext_s[kn + 1] + difsp * delhat
        difth = dext_t[kn + 1] + diftp * delhat
    else:
        visch = 0.0
        difsh = 0.0
        difth = 0.0
        viscp = 0.0
        difsp = 0.0
        diftp = 0.0

    # Shape function parameters at sigma=1 (MITgcm: kpp_routines.F:1550-1563)
    f1 = stable * config.conc1 * bfsfc / max(ustar**4, config.phepsi)

    # DIVIDE-BY-ZERO WARNING NOTES:
    # In edge cases with very weak forcing and stable stratification, hbl can be
    # extremely small (e.g., 1e-20), leading to divide-by-zero warnings here.
    # MITgcm does not explicitly check for this - it divides by hbl directly and
    # trusts that BLDEPTH enforces hbl >= -zgrid(1) (surface grid spacing).
    # However, when hbl approaches machine epsilon, the divisions produce inf/nan
    # which then propagate through but don't crash the code.
    #
    # This is a known limitation of the MITgcm implementation - with extremely weak
    # forcing, the velocity scales wm/ws approach zero (regularized to phepsi), and
    # hbl also approaches zero, creating numerical issues. The physically correct
    # result in this case is negligible boundary layer mixing, which is what the
    # inf/nan values effectively produce when multiplied by small hbl later.
    #
    # To match MITgcm exactly, we do NOT add extra checks here. The warnings can
    # be safely ignored - they indicate edge cases where BL mixing is negligible.
    gat1m = visch / hbl / wm_one
    dat1m = -viscp / wm_one + f1 * visch

    gat1s = difsh / hbl / ws_one
    dat1s = -difsp / ws_one + f1 * difsh

    gat1t = difth / hbl / ws_one
    dat1t = -diftp / ws_one + f1 * difth

    # Ensure derivatives are non-positive
    dat1m = min(dat1m, 0.0)
    dat1s = min(dat1s, 0.0)
    dat1t = min(dat1t, 0.0)

    # Compute profiles
    blmc_visc = np.zeros(nz)
    blmc_s = np.zeros(nz)
    blmc_t = np.zeros(nz)
    ghat = np.zeros(nz)

    for k in range(nz):
        # Normalized depth at interface (MITgcm: kpp_routines.F:1596-1597)
        sig = (-zgrid[k] + 0.5 * hwide[k]) / hbl
        sigma = stable * sig + (1.0 - stable) * min(sig, config.epsilon)

        # Velocity scales (MITgcm: kpp_routines.F:1606-1608)
        wm, ws = wscale(
            np.array([sigma]),
            np.array([hbl]),
            np.array([ustar]),
            np.array([bfsfc]),
            wmt, wst, config
        )

        # Shape functions (MITgcm: kpp_routines.F:1619-1626)
        sig = (-zgrid[k] + 0.5 * hwide[k]) / hbl
        a1 = sig - 2.0
        a2 = 3.0 - 2.0 * sig
        a3 = sig - 1.0

        Gm = a1 + a2 * gat1m + a3 * dat1m
        Gs = a1 + a2 * gat1s + a3 * dat1s
        Gt = a1 + a2 * gat1t + a3 * dat1t

        # Mixing coefficients
        blmc_visc[k] = hbl * wm[0] * sig * (1.0 + sig * Gm)
        blmc_s[k] = hbl * ws[0] * sig * (1.0 + sig * Gs)
        blmc_t[k] = hbl * ws[0] * sig * (1.0 + sig * Gt)

        # Nonlocal transport coefficient. MITgcm's blmix (kpp_routines.F:
        # 1636-1646) computes this UNCONDITIONALLY -- KPP_GHAT does not
        # appear anywhere in kpp_routines.F/blmix. `config.use_ghat` (KPP_GHAT)
        # instead gates only whether this coefficient is later APPLIED to the
        # tracer diffusive flux (kpp_transport_t.F/kpp_transport_s.F); see
        # MixingOutput.apply_ghat / UnifiedColumnDriver._apply_vertical_diffusion
        # (main/mixing_adapter.py, main/unified_driver.py) for that gate.
        # Fixed 1DMIX-058: this function previously zeroed ghat itself when
        # use_ghat was False, conflating "do not apply the nonlocal term to
        # the flux" with "do not compute the coefficient" -- confirmed wrong
        # against a real MITgcm capture (global_oce_latlon_720) whose own
        # KPP_GHAT is #undef'd (use_ghat=0) yet whose captured ghat output is
        # real and non-degenerate (376,577 nonzero values, max 205.7).
        tempVar = ws[0] * hbl
        if config.smooth_regularisation:
            ghat[k] = (1.0 - stable) * config.cg / (config.phepsi + tempVar)
        else:
            ghat[k] = (1.0 - stable) * config.cg / max(config.phepsi, tempVar)

    # Diffusivities at the kbl-1 grid level (dkm1), MITgcm blmix:1653-1687.
    # BUG FIX (Python porting error): the previous port computed dkm1 with a
    # crude placeholder in kpp_core (dat1m hard-coded to 0, gat1m reverse-
    # engineered from blmc, and dkm1_s/dkm1_t just copied from blmc[kbl-1]).
    # That corrupted the enhanced diffusivity at the mixed-layer base. Here we
    # reproduce the Fortran exactly: evaluate the SAME cubic shape functions
    # (with the already-computed gat1*/dat1* matching coefficients) at the
    # normalized depth of the kbl-1 CELL CENTRE, sig = -zgrid(kbl-1)/hbl.
    # Note the sigma used for wscale here uses the plain cell-centre depth
    # (-zgrid[kl-1]), NOT the +0.5*hwide interface offset used in the interface
    # loop above -- this matches the Fortran (line 1655 vs line 1596).
    kl = kbl
    klm1 = max(0, min(kl - 1, n_model - 1))
    sig_km1 = -zg_ext[klm1] / hbl
    sigma_km1 = stable * sig_km1 + (1.0 - stable) * min(sig_km1, config.epsilon)

    wm_km1, ws_km1 = wscale(
        np.array([sigma_km1]),
        np.array([hbl]),
        np.array([ustar]),
        np.array([bfsfc]),
        wmt, wst, config
    )

    a1 = sig_km1 - 2.0
    a2 = 3.0 - 2.0 * sig_km1
    a3 = sig_km1 - 1.0

    Gm = a1 + a2 * gat1m + a3 * dat1m
    Gs = a1 + a2 * gat1s + a3 * dat1s
    Gt = a1 + a2 * gat1t + a3 * dat1t

    dkm1_visc = hbl * wm_km1[0] * sig_km1 * (1.0 + sig_km1 * Gm)
    dkm1_s = hbl * ws_km1[0] * sig_km1 * (1.0 + sig_km1 * Gs)
    dkm1_t = hbl * ws_km1[0] * sig_km1 * (1.0 + sig_km1 * Gt)

    return blmc_visc, blmc_s, blmc_t, ghat, (dkm1_visc, dkm1_s, dkm1_t)


def enhance_at_interface(
    dkm1: Tuple[float, float, float],
    hbl: float,
    kbl: int,
    diffus_interior: Tuple[np.ndarray, np.ndarray, np.ndarray],
    casea: float,
    zgrid: np.ndarray,
    hwide: np.ndarray,
    blmc: Tuple[np.ndarray, np.ndarray, np.ndarray],
    ghat: np.ndarray,
    zgrid_below: np.ndarray = None,
    hwide_below: np.ndarray = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Enhance diffusivity at kbl-0.5 interface.

    Corresponds to enhance routine in MITgcm kpp_routines.F.

    Parameters
    ----------
    dkm1 : tuple of float
        BL diffusivities at kbl-1 level (visc, salt, temp)
    hbl : float
        Boundary layer depth [m]
    kbl : int
        0-based model-axis index of MITgcm's kbl (see `diagnose_bl_depth`)
    diffus_interior : tuple of np.ndarray
        Interior diffusivities
    casea : float
        Case flag
    zgrid : np.ndarray
        Vertical grid
    hwide : np.ndarray
        Cell thicknesses
    blmc : tuple of np.ndarray
        BL mixing coefficients
    ghat : np.ndarray
        Nonlocal transport
    zgrid_below, hwide_below : np.ndarray, optional
        (1DMIX-075) grid of the model levels below the supplied wet column; None = the
        column is the full model depth. `kbl-1` may be the bottom wet level (MITgcm
        kbl = kmtj+1); the interface below it is then the first dry level. When
        `kbl-1` is itself a dry level only dry-level entries would change, which the
        output drops (kpp_calc.F:585-592 mask), so nothing is done.

    Returns
    -------
    Enhanced versions of blmc_visc, blmc_s, blmc_t, ghat
    """
    blmc_visc, blmc_s, blmc_t = blmc
    diffus_visc, diffus_s, diffus_t = diffus_interior

    nz = len(zgrid)
    if zgrid_below is not None and len(zgrid_below):
        zg_ext = np.concatenate([zgrid, np.asarray(zgrid_below, dtype=np.float64)])
    else:
        zg_ext = zgrid
    n_model = len(zg_ext)          # MITgcm Nr
    ki = kbl - 1
    # BUG FIX (Finding 8, Python porting error / off-by-one guard):
    # MITgcm enhance (kpp_routines.F:1739-1741) guards with
    #     ki = kbl_F - 1;  IF ((ki .ge. 1) .AND. (ki .LT. Nr))
    # With the 0-based convention (Python index p <-> Fortran level p+1, so
    # Python kbl = kbl_F - 1), the enhanced level is ki = kbl - 1 and the guard
    # maps to  ki >= 0  AND  ki < Nr - 1  (Nr = model levels, 1DMIX-075; = nz for a
    # full-depth column). The previous port used `ki >= 1`,
    # which skipped enhancement of the SHALLOWEST boundary layers (kbl==1,
    # i.e. ki==0) -- exactly the thin mixed layers where the kbl-0.5 interface
    # enhancement matters most. ki >= nz would only modify dry-level entries (dropped).
    if ki >= 0 and ki < n_model - 1 and ki < nz:
        delta = (hbl + zgrid[ki]) / (zgrid[ki] - zg_ext[ki+1])

        # Viscosity
        dkmp5 = casea * diffus_visc[ki] + (1.0 - casea) * blmc_visc[ki]
        dstar = (1.0 - delta)**2 * dkm1[0] + delta**2 * dkmp5
        blmc_visc[ki] = (1.0 - delta) * diffus_visc[ki] + delta * dstar

        # Salt diffusivity
        dkmp5 = casea * diffus_s[ki] + (1.0 - casea) * blmc_s[ki]
        dstar = (1.0 - delta)**2 * dkm1[1] + delta**2 * dkmp5
        blmc_s[ki] = (1.0 - delta) * diffus_s[ki] + delta * dstar

        # Temperature diffusivity
        dkmp5 = casea * diffus_t[ki] + (1.0 - casea) * blmc_t[ki]
        dstar = (1.0 - delta)**2 * dkm1[2] + delta**2 * dkmp5
        blmc_t[ki] = (1.0 - delta) * diffus_t[ki] + delta * dstar

        # Nonlocal transport: (1 - casea) is 0 in case A, so ghat(kbl-1) is zeroed in case A and kept in case B
        ghat[ki] = (1.0 - casea) * ghat[ki]

    return blmc_visc, blmc_s, blmc_t, ghat
