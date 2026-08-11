"""
Core KPP mixing routines.

Translated from MITgcm pkg/kpp/kpp_routines.F
"""

import numpy as np
from typing import Tuple, Optional
from .kpp_parameters import KPPParameters


def safe_divide(numerator, denominator, fill_value=0.0, epsilon=1e-20):
    """
    Safely divide two arrays, handling division by zero.

    Parameters
    ----------
    numerator : np.ndarray
        Numerator
    denominator : np.ndarray
        Denominator
    fill_value : float, optional
        Value to use when denominator is near zero
    epsilon : float, optional
        Threshold for near-zero denominator

    Returns
    -------
    np.ndarray
        Result of division with safe handling
    """
    result = np.zeros_like(numerator, dtype=float)
    safe_mask = np.abs(denominator) > epsilon
    result[safe_mask] = numerator[safe_mask] / denominator[safe_mask]
    result[~safe_mask] = fill_value
    return result


def build_wscale_lookup_tables(config: KPPParameters) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build lookup tables for turbulent velocity scales wm and ws.

    This translates the kmixinit routine from kpp_routines.F

    Parameters
    ----------
    config : KPPParameters
        KPP configuration

    Returns
    -------
    wmt : np.ndarray, shape (nni+2, nnj+2)
        Turbulent velocity scale for momentum
    wst : np.ndarray, shape (nni+2, nnj+2)
        Turbulent velocity scale for scalars
    """
    nni = config.nni
    nnj = config.nnj

    deltaz = (config.zmax - config.zmin) / (nni + 1)
    deltau = (config.umax - config.umin) / (nnj + 1)

    wmt = np.zeros((nni + 2, nnj + 2))
    wst = np.zeros((nni + 2, nnj + 2))

    for i in range(nni + 2):
        zehat = deltaz * i + config.zmin
        for j in range(nnj + 2):
            usta = deltau * j + config.umin
            zeta = zehat / max(config.phepsi, usta**3)

            if zehat >= 0.0:
                # Stable conditions
                wmt[i, j] = config.vonk * usta / (1.0 + config.conc1 * zeta)
                wst[i, j] = wmt[i, j]
            else:
                # Unstable conditions
                if zeta > config.zetam:
                    wmt[i, j] = config.vonk * usta * (1.0 - config.conc2 * zeta)**0.25
                else:
                    wmt[i, j] = config.vonk * (config.conam * usta**3 - config.concm * zehat)**(1.0/3.0)

                if zeta > config.zetas:
                    wst[i, j] = config.vonk * usta * np.sqrt(1.0 - config.conc3 * zeta)
                else:
                    wst[i, j] = config.vonk * (config.conas * usta**3 - config.concs * zehat)**(1.0/3.0)

    return wmt, wst


def wscale(
    sigma: np.ndarray,
    hbl: np.ndarray,
    ustar: np.ndarray,
    bfsfc: np.ndarray,
    wmt: np.ndarray,
    wst: np.ndarray,
    config: KPPParameters,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute turbulent velocity scales wm and ws.

    Uses lookup table for unstable conditions, direct formula for stable.

    Parameters
    ----------
    sigma : np.ndarray
        Normalized depth (d/hbl)
    hbl : np.ndarray
        Boundary layer depth [m]
    ustar : np.ndarray
        Friction velocity [m/s]
    bfsfc : np.ndarray
        Surface buoyancy forcing [m^2/s^3]
    wmt : np.ndarray
        Momentum velocity scale lookup table
    wst : np.ndarray
        Scalar velocity scale lookup table
    config : KPPParameters
        KPP configuration

    Returns
    -------
    wm : np.ndarray
        Turbulent velocity scale for momentum [m/s]
    ws : np.ndarray
        Turbulent velocity scale for scalars [m/s]
    """
    npts = len(sigma) if isinstance(sigma, np.ndarray) else 1
    wm = np.zeros(npts) if isinstance(sigma, np.ndarray) else 0.0
    ws = np.zeros(npts) if isinstance(sigma, np.ndarray) else 0.0

    # Ensure inputs are arrays for vectorization
    sigma = np.atleast_1d(sigma)
    hbl = np.atleast_1d(hbl)
    ustar = np.atleast_1d(ustar)
    bfsfc = np.atleast_1d(bfsfc)

    deltaz = (config.zmax - config.zmin) / (config.nni + 1)
    deltau = (config.umax - config.umin) / (config.nnj + 1)

    for i in range(len(sigma)):
        zehat = config.vonk * sigma[i] * hbl[i] * bfsfc[i]

        if zehat <= config.zmax:
            # Use lookup table.
            #
            # GENUINE MITgcm BUG (gated by keep_mitgcm_bugs) -- kpp_routines.F:980,990.
            #
            # The stock, ACTIVE MITgcm line is:
            #       zdiff = zehat - zmin                       (line 980)
            # and the safe version is present but COMMENTED OUT in the source:
            #       zdiff = MAX( 0. _d 0, zehat - zmin )       (line 990)
            #
            # The MITgcm authors document the hazard themselves in the comment
            # block at lines 981-989: for extremely negative buoyancy forcing
            # bfsfc, zehat (and hence zdiff = zehat - zmin) becomes very negative;
            # int(zdiff/deltaz) is then a large negative index and the bilinear
            # interpolation LINEARLY EXTRAPOLATES beyond the lower edge of the
            # wmt/wst lookup tables. They write this "can give very bad values and
            # may make the model crash", and that clamping to MAX(0, ...) instead
            # "effectively replaces linear extrapolation with nearest-neighbour
            # extrapolation so that only the lower-limit values of the lookup
            # tables are used." The commented-out fix (attributed to Dimitry
            # Sidorenko) is the correct, safe behaviour.
            #
            # We treat the clamped form as the bug-fixed default. Setting
            # keep_mitgcm_bugs=True reproduces the stock (unclamped, hazardous)
            # MITgcm behaviour bit-for-bit for validation runs.
            if config.keep_mitgcm_bugs:
                # Stock MITgcm (line 980): unclamped -> may extrapolate below the
                # table and produce bad/unstable velocity scales.
                zdiff = zehat - config.zmin
            else:
                # Bug-fixed (line 990, Sidorenko): clamp so we never index below
                # the table; nearest-neighbour behaviour at the lower edge.
                zdiff = max(0.0, zehat - config.zmin)
            iz = int(zdiff / deltaz)
            iz = min(iz, config.nni)
            iz = max(iz, 0)
            izp1 = iz + 1

            udiff = ustar[i] - config.umin
            ju = int(udiff / deltau)
            ju = min(ju, config.nnj)
            ju = max(ju, 0)
            jup1 = ju + 1

            zfrac = zdiff / deltaz - float(iz)
            ufrac = udiff / deltau - float(ju)
            fzfrac = 1.0 - zfrac

            wam = fzfrac * wmt[iz, jup1] + zfrac * wmt[izp1, jup1]
            wbm = fzfrac * wmt[iz, ju] + zfrac * wmt[izp1, ju]
            wm[i] = (1.0 - ufrac) * wbm + ufrac * wam

            was = fzfrac * wst[iz, jup1] + zfrac * wst[izp1, jup1]
            wbs = fzfrac * wst[iz, ju] + zfrac * wst[izp1, ju]
            ws[i] = (1.0 - ufrac) * wbs + ufrac * was
        else:
            # Stable conditions: direct formula
            u3 = ustar[i]**3
            tempVar = u3 + config.conc1 * zehat
            wm[i] = config.vonk * ustar[i] * u3 / tempVar
            ws[i] = wm[i]

    return wm, ws


def ri_iwmix(
    shsq: np.ndarray,
    dbloc: np.ndarray,
    dbloc_smooth: np.ndarray,
    diffus_kz_s_bg: np.ndarray,
    diffus_kz_t_bg: np.ndarray,
    config: KPPParameters,
    zgrid: np.ndarray = None,
    visc_nr_bg: np.ndarray = None,
    kmtj: int = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute interior mixing coefficients from Richardson number.

    Includes shear instability, static instability, and background mixing.

    Parameters
    ----------
    shsq : np.ndarray, shape (nz,)
        Local velocity shear squared at interfaces [m^2/s^2]
    dbloc : np.ndarray, shape (nz,)
        Local buoyancy gradient at interfaces [m/s^2]
    dbloc_smooth : np.ndarray, shape (nz,)
        Horizontally smoothed dbloc [m/s^2]
    diffus_kz_s_bg : np.ndarray, shape (nz,)
        Background diffusivity for salinity [m^2/s]
    diffus_kz_t_bg : np.ndarray, shape (nz,)
        Background diffusivity for temperature [m^2/s]
    config : KPPParameters
        KPP configuration
    zgrid : np.ndarray, shape (nz,), optional
        Vertical grid (negative depths) [m]. Required for correct Ri calculation.
    visc_nr_bg : np.ndarray, shape (nz,), optional
        Background vertical viscosity profile (MITgcm viscArNr). If None, falls
        back to the salt background diffusivity for backward compatibility, but
        MITgcm uses a *separate* background viscosity here (see notes below).
    kmtj : int, optional
        Number of wet vertical levels in the column (MITgcm kmtj). Interfaces at
        or below this level (0-based index >= kmtj-1, i.e. the bottom interface
        and anything beneath it) have no valid dbloc/shsq, so their Ri and N^2
        are copied from the nearest interface above -- matching MITgcm's
        "set values at bottom and below to nearest value above bottom"
        (kpp_routines.F:1104,1122-1124). Defaults to nz (full water column).

    Returns
    -------
    diffus_visc : np.ndarray, shape (nz,)
        Vertical viscosity [m^2/s]
    diffus_s : np.ndarray, shape (nz,)
        Vertical diffusivity for salt [m^2/s]
    diffus_t : np.ndarray, shape (nz,)
        Vertical diffusivity for temperature [m^2/s]
    """
    nz = len(shsq)

    # Background viscosity (MITgcm viscArNr). If not supplied, fall back to the
    # salt background diffusivity to preserve the old call signature -- but note
    # that MITgcm uses a distinct background viscosity here, so callers should
    # pass visc_nr_bg for a faithful match.
    if visc_nr_bg is None:
        visc_nr_bg = diffus_kz_s_bg

    # Compute layer thickness for Richardson number calculation
    # In MITgcm, Ri is computed with layer thickness: Ri = dbloc * dz / shsq
    # where dz = zgrid(k) - zgrid(k+1) > 0 (since zgrid is negative)
    if zgrid is not None:
        layer_thickness = np.zeros(nz)
        for k in range(nz - 1):
            layer_thickness[k] = zgrid[k] - zgrid[k+1]  # Positive since zgrid is negative
        layer_thickness[nz-1] = layer_thickness[nz-2] if nz > 1 else 1.0  # Use last valid thickness
    else:
        # Fallback: assume unit thickness (will produce incorrect results)
        layer_thickness = np.ones(nz)

    # Compute local Richardson number with layer thickness
    # This matches MITgcm: diffus(*,*,1) = dblocSm * (zgrid(k)-zgrid(k+1)) / shsq
    # (kpp_routines.F:1126-1131)
    if config.smooth_regularisation:
        Ri = (dbloc_smooth * layer_thickness) / (shsq + config.phepsi**2)
    else:
        Ri = (dbloc_smooth * layer_thickness) / np.maximum(shsq, config.phepsi)

    # Brunt-Vaisala frequency squared N^2 = dbloc / dz, used for the convection
    # function. MITgcm stores this in diffus(*,*,2) (kpp_routines.F:1132) and the
    # convection test at line 1170 compares N^2 to BVSQcon.
    #
    # BUG FIX (Python porting error): the previous code compared the RAW dbloc
    # (units m/s^2) directly against BVSQcon (units 1/s^2 = s^-2). That is a
    # dimensional mismatch -- dbloc must be divided by the layer thickness dz to
    # become N^2 before the comparison. Without the /dz, the convection function
    # fired essentially at random relative to the true static stability. The
    # Fortran is correct (it divides by (zgrid(ki)-zgrid(ki+1))), so this is a
    # porting error fixed unconditionally.
    bvsq = dbloc / np.where(layer_thickness != 0.0, layer_thickness, 1.0)

    # ------------------------------------------------------------------
    # Bottom-boundary masking (MITgcm kpp_routines.F:1104,1117-1135).
    #
    # MITgcm computes Ri (diffus[*,1]) and N^2 (diffus[*,2]) only on interfaces
    # strictly above the ocean bottom. At or below the bottom (Fortran
    # ki >= kmtj) it "sets values at bottom and below to the nearest value above
    # bottom" by copying downward from the last valid interface:
    #     ELSEIF (ki .GE. kmtj) THEN
    #        diffus(i,ki,1) = diffus(i,ki-1,1)
    #        diffus(i,ki,2) = diffus(i,ki-1,2)
    # Without this, the deepest interface uses the bottom sentinel dbloc = 0,
    # giving N^2 = 0 and Ri = 0 -> fRi = 1 -> spurious FULL shear diffusivity
    # (~difm0/dift0 ~ 5e-3 m^2/s) at the very bottom cell. Copying from above
    # removes that artifact.
    #
    # Index mapping: Fortran ki (1-based) <-> Python k = ki-1. The valid
    # computed range ki = 1..kmtj-1 is Python k = 0..kmtj-2, so masking applies
    # to k >= kmtj-1 (the bottom interface and anything below). With the default
    # kmtj = nz this masks exactly the single deepest interface k = nz-1.
    if kmtj is None:
        kmtj = nz
    if kmtj <= 1:
        # Degenerate column (land or a single wet level): no interior gradients.
        Ri[:] = 0.0
        bvsq[:] = 0.0
    else:
        for k in range(kmtj - 1, nz):
            if k >= 1:
                Ri[k] = Ri[k - 1]
                bvsq[k] = bvsq[k - 1]

    # Vertical smoothing of Ri if requested
    if config.vertically_smooth_ri and config.num_v_smooth_ri > 0:
        for _ in range(config.num_v_smooth_ri):
            Ri = z121_smooth(Ri, config.Riinfty)

    # Compute mixing functions
    diffus_visc = np.zeros(nz)
    diffus_s = np.zeros(nz)
    diffus_t = np.zeros(nz)

    for k in range(nz):
        # Background diffusivities/viscosity are taken from the level BELOW the
        # interface, kp1 = min(k+1, nz-1) (MITgcm kpp_routines.F:1191, kp1 used
        # at lines 1206-1208). With vertically-uniform backgrounds this shift is
        # a no-op, but it matters for depth-varying background profiles.
        kp1 = min(k + 1, nz - 1)

        # Convective instability function, evaluated on N^2 (= dbloc/dz), not
        # on raw dbloc -- see BUG FIX note above.
        Rig_conv = max(bvsq[k], config.BVSQcon)
        ratio = min((config.BVSQcon - Rig_conv) / config.BVSQcon, 1.0)
        fcon = (1.0 - ratio**2)**3

        # Shear instability function
        Rig_shear = max(Ri[k], 0.0)
        ratio = min(Rig_shear / config.Riinfty, 1.0)
        fRi = (1.0 - ratio**2)**3

        # Optional shear scaling (Polzin 1996)
        if config.scale_shearmixing:
            fRi = fRi * shsq[k]**2 / (shsq[k]**2 + 1.0e-16)

        # Combine mixing sources
        if config.exclude_shear_mix:
            # No shear mixing, only background (MITgcm EXCLUDE_KPP_SHEAR_MIX:
            # diffus(1)=viscArNr(1), diffus(2)=diffusKzS(kp1), diffus(3)=diffusKzT(kp1))
            diffus_visc[k] = visc_nr_bg[k]
            diffus_s[k] = diffus_kz_s_bg[kp1]
            diffus_t[k] = diffus_kz_t_bg[kp1]
        else:
            # BUG FIX (Python porting error): the viscosity background here is
            # MITgcm's viscArNr(1) (a dedicated background viscosity), NOT the
            # salt background diffusivity. The previous port used
            # diffus_kz_s_bg for viscosity, which conflates two distinct
            # background fields. Fortran lines 1206-1208 use viscArNr(1) for the
            # viscosity row and diffusKzS/T(kp1) for the scalar rows.
            diffus_visc[k] = visc_nr_bg[k] + fcon * config.difmcon + fRi * config.difm0
            diffus_s[k] = diffus_kz_s_bg[kp1] + fcon * config.difscon + fRi * config.difs0
            diffus_t[k] = diffus_kz_t_bg[kp1] + fcon * config.diftcon + fRi * config.dift0

    return diffus_visc, diffus_s, diffus_t


def z121_smooth(v: np.ndarray, Ri_limit: float) -> np.ndarray:
    """
    Apply 1-2-1 vertical smoothing to array v.

    Only smooths points within valid Ri range [0, Ri_limit].
    Matches MITgcm's z121 routine with proper ghost point handling.

    Parameters
    ----------
    v : np.ndarray
        Array to smooth
    Ri_limit : float
        Upper limit for valid Ri values

    Returns
    -------
    np.ndarray
        Smoothed array
    """
    nz = len(v)
    v_smooth = v.copy()

    # Create extended array with ghost point (Nrp1) at the end
    # Ghost point equals the last physical point (matches MITgcm: v(i,Nrp1) = v(i,Nr))
    v_ext = np.zeros(nz + 1)
    v_ext[:nz] = v
    v_ext[nz] = v[nz-1]  # Ghost point

    # Determine which points are in valid range [0, Ri_limit]
    # KRi_range = 1 if 0 <= v[k] <= Ri_limit, else 0
    KRi_range = np.zeros(nz + 1)
    for k in range(nz):
        KRi_range[k] = 0.5 + np.sign(v[k]) * 0.5
        KRi_range[k] = KRi_range[k] * (0.5 + np.sign(Ri_limit - v[k]) * 0.5)
    KRi_range[nz] = 0.0  # Ghost point gets 0

    # First point (k=0)
    zwork = KRi_range[0] * v[0]
    v_smooth[0] = 2.0 * v[0] + KRi_range[0] * KRi_range[1] * v[1]
    zflag = 2.0 + KRi_range[0] * KRi_range[1]
    v_smooth[0] = v_smooth[0] / zflag

    # Interior points (k=1 to nz-1)
    # Use v_ext[k+1] which properly includes the ghost point at k=nz
    for k in range(1, nz):
        zflag = v[k]
        v_smooth[k] = (
            2.0 * v[k] +
            KRi_range[k] * KRi_range[k+1] * v_ext[k+1] +  # Fixed: use v_ext with ghost point
            KRi_range[k] * zwork
        )
        zwork = KRi_range[k] * zflag
        zflag = 2.0 + KRi_range[k] * (KRi_range[k+1] + KRi_range[k-1])
        v_smooth[k] = v_smooth[k] / zflag

    return v_smooth
