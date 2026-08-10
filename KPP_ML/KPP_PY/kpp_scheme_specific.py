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
        Index of first grid level below hbl
    Rib : np.ndarray, shape (nz,)
        Bulk Richardson number profile
    """
    nz = len(zgrid)

    # Initialize
    Rib = np.zeros(nz)
    Rib[0] = 0.0
    kbl = nz
    hbl = -zgrid[-1]  # Bottom as default

    # Compute bulk Richardson number at each level
    for kl in range(1, nz):
        # Buoyancy forcing felt at this depth: bo is the non-penetrating (turbulent)
        # part, bosol*(1-swfrac(z)) is the fraction of shortwave already absorbed
        # above this depth (and thus already contributing to local buoyancy forcing).
        if config.shortwave_heating and config.select_penetrating_sw >= 1:
            frac_absorbed = 1.0 - swfrac(-zgrid[kl], config.jerlov_water_type)[0]
            bfsfc = bo + bosol * frac_absorbed
        else:
            bfsfc = bo + bosol

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
        zgrid_below = zgrid[kl + 1] if kl + 1 < nz else zgrid[-1] * 100.0
        bvsq = 0.5 * (
            dbloc[kl-1] / (zgrid[kl-1] - zgrid[kl]) +
            dbloc[kl] / (zgrid[kl] - zgrid_below)
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

    # Find where Rib exceeds Ricr
    for kl in range(1, nz):
        if kbl == nz and Rib[kl] > config.Ricr:
            kbl = kl

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

    # Surface buoyancy forcing at the interpolated hbl, used only to LIMIT hbl
    # by the Ekman / Monin-Obukhov depths below. MITgcm recomputes bfsfc a
    # second time after the limit (see below); we mirror that ordering.
    if config.shortwave_heating and config.select_penetrating_sw >= 1:
        frac_absorbed = 1.0 - swfrac(np.array([hbl]), config.jerlov_water_type)[0]
        bfsfc = bo + bosol * frac_absorbed
    else:
        bfsfc = bo + bosol
    stable = 0.5 + np.sign(bfsfc) * 0.5
    bfsfc = np.sign(bfsfc) * max(config.phepsi, abs(bfsfc))

    # Limit hbl by Ekman and Monin-Obukhov depths in stable conditions
    if config.limit_hbl_stable and bfsfc > 0.0:
        hekman = config.cekman * ustar / max(abs(coriol), config.phepsi)
        hmonob = config.cmonob * ustar**3 / config.vonk / bfsfc
        hlimit = stable * min(hekman, hmonob) + (stable - 1.0) * (-zgrid[-1])
        hbl = min(hbl, hlimit)

    # Apply minimum hbl
    if config.min_kpp_hbl is not None:
        hbl = max(hbl, config.min_kpp_hbl)
    else:
        hbl = max(hbl, -zgrid[0])

    # Find new kbl for the (possibly limited) final hbl.
    kbl = nz
    for kl in range(1, nz):
        if kbl == nz and (-zgrid[kl]) > hbl:
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
    stable = 0.5 + np.sign(bfsfc) * 0.5
    bfsfc = np.sign(bfsfc) * max(config.phepsi, abs(bfsfc))

    # Determine case A vs case B.
    # BUG FIX (Finding 5, Python porting error / off-by-one): MITgcm
    # (kpp_routines.F:910-913) evaluates
    #     casea = p5 + sign(p5, -zgrid(kl) - p5*hwide(kl) - hbl),  kl = kbl_F
    # The Fortran level kl=kbl_F maps to Python index kbl (= kbl_F - 1), NOT
    # kbl-1. The previous port used zgrid[kbl-1]/hwide[kbl-1], one cell too
    # shallow, which flipped the caseA/caseB decision near the boundary and
    # corrupted the interior-vs-BL matching. When bottomed out (kbl==nz) the
    # Fortran references zgrid(kmtj); clamp the index to stay in-bounds.
    kbl_idx = min(kbl, nz - 1)
    casea = 0.5 + np.sign(-zgrid[kbl_idx] - 0.5*hwide[kbl_idx] - hbl) * 0.5

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
        Index of first level below hbl
    zgrid : np.ndarray
        Vertical grid
    hwide : np.ndarray
        Cell thicknesses
    wmt, wst : np.ndarray
        Velocity scale lookup tables
    config : KPPParameters
        KPP configuration

    Returns
    -------
    blmc_visc : np.ndarray, shape (nz,)
        BL viscosity profile [m^2/s]
    blmc_s : np.ndarray, shape (nz,)
        BL salt diffusivity profile [m^2/s]
    blmc_t : np.ndarray, shape (nz,)
        BL temperature diffusivity profile [m^2/s]
    ghat : np.ndarray, shape (nz,)
        Nonlocal transport coefficient [s/m^2]
    dkm1 : tuple of float
        BL diffusivities (visc, salt, temp) at the kbl-1 grid level, evaluated
        exactly as MITgcm blmix (kpp_routines.F:1653-1687). These are consumed
        by enhance_at_interface.
    """
    nz = len(zgrid)
    diffus_visc, diffus_s, diffus_t = diffus_interior

    # Compute velocity scales at sigma=1
    sigma_one = stable * 1.0 + (1.0 - stable) * config.epsilon
    wm_one, ws_one = wscale(
        np.array([sigma_one]),
        np.array([hbl]),
        np.array([ustar]),
        np.array([bfsfc]),
        wmt, wst, config
    )

    wm_one = np.sign(wm_one[0]) * max(config.phepsi, abs(wm_one[0]))
    ws_one = np.sign(ws_one[0]) * max(config.phepsi, abs(ws_one[0]))

    # Find interior viscosities and derivatives at hbl
    kn = int(casea + config.phepsi) * (kbl - 1) + (1 - int(casea + config.phepsi)) * kbl
    # Ensure kn is within valid bounds [0, nz-1]
    kn = max(0, min(kn, nz - 1))

    if config.match_diffusivities:
        if config.match_derivatives:
            # Match both value and derivative
            delhat = 0.5 * hwide[kn] - zgrid[kn] - hbl
            R = 1.0 - delhat / hwide[kn]

            dvdzup = (diffus_visc[kn-1] - diffus_visc[kn]) / hwide[kn]
            dvdzdn = (diffus_visc[kn] - diffus_visc[min(kn+1, nz-1)]) / hwide[min(kn+1, nz-1)]
            viscp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))

            dvdzup = (diffus_s[kn-1] - diffus_s[kn]) / hwide[kn]
            dvdzdn = (diffus_s[kn] - diffus_s[min(kn+1, nz-1)]) / hwide[min(kn+1, nz-1)]
            difsp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))

            dvdzup = (diffus_t[kn-1] - diffus_t[kn]) / hwide[kn]
            dvdzdn = (diffus_t[kn] - diffus_t[min(kn+1, nz-1)]) / hwide[min(kn+1, nz-1)]
            diftp = 0.5 * ((1.0 - R) * (dvdzup + abs(dvdzup)) + R * (dvdzdn + abs(dvdzdn)))
        else:
            delhat = 0.5 * hwide[kn] - zgrid[kn] - hbl
            viscp = 0.0
            difsp = 0.0
            diftp = 0.0

        visch = diffus_visc[kn] + viscp * delhat
        difsh = diffus_s[kn] + difsp * delhat
        difth = diffus_t[kn] + diftp * delhat
    else:
        visch = 0.0
        difsh = 0.0
        difth = 0.0
        viscp = 0.0
        difsp = 0.0
        diftp = 0.0

    # Shape function parameters at sigma=1
    f1 = stable * config.conc1 * bfsfc / max(ustar**4, config.phepsi)

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
        # Normalized depth at interface
        sig = (-zgrid[k] + 0.5 * hwide[k]) / hbl
        sigma = stable * sig + (1.0 - stable) * min(sig, config.epsilon)

        # Velocity scales
        wm, ws = wscale(
            np.array([sigma]),
            np.array([hbl]),
            np.array([ustar]),
            np.array([bfsfc]),
            wmt, wst, config
        )

        # Shape functions
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

        # Nonlocal transport
        if config.use_ghat:
            tempVar = ws[0] * hbl
            if config.smooth_regularisation:
                ghat[k] = (1.0 - stable) * config.cg / (config.phepsi + tempVar)
            else:
                ghat[k] = (1.0 - stable) * config.cg / max(config.phepsi, tempVar)
        else:
            ghat[k] = 0.0

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
    klm1 = max(0, min(kl - 1, nz - 1))
    sig_km1 = -zgrid[klm1] / hbl
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
        Index of first level below hbl
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

    Returns
    -------
    Enhanced versions of blmc_visc, blmc_s, blmc_t, ghat
    """
    blmc_visc, blmc_s, blmc_t = blmc
    diffus_visc, diffus_s, diffus_t = diffus_interior

    nz = len(zgrid)
    ki = kbl - 1
    # BUG FIX (Finding 8, Python porting error / off-by-one guard):
    # MITgcm enhance (kpp_routines.F:1739-1741) guards with
    #     ki = kbl_F - 1;  IF ((ki .ge. 1) .AND. (ki .LT. Nr))
    # With the 0-based convention (Python index p <-> Fortran level p+1, so
    # Python kbl = kbl_F - 1), the enhanced level is ki = kbl - 1 and the guard
    # maps to  ki >= 0  AND  ki < nz - 1.  The previous port used `ki >= 1`,
    # which skipped enhancement of the SHALLOWEST boundary layers (kbl==1,
    # i.e. ki==0) -- exactly the thin mixed layers where the kbl-0.5 interface
    # enhancement matters most. The array accesses (zgrid[ki], zgrid[ki+1],
    # diffus[ki], blmc[ki]) are already consistent with the Fortran and unchanged.
    if ki >= 0 and ki < nz - 1:
        delta = (hbl + zgrid[ki]) / (zgrid[ki] - zgrid[ki+1])

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

        # Nonlocal transport (turn off in case B)
        ghat[ki] = (1.0 - casea) * ghat[ki]

    return blmc_visc, blmc_s, blmc_t, ghat
