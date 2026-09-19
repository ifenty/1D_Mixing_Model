"""
GGL90 mixing coefficient computation (viscosity and diffusivity).

This module converts TKE and mixing length into eddy viscosity (κ_m) and
eddy diffusivity (κ_h) using the GGL90 closure formulas.

Corresponds to mixing coefficient calculation in GGL90_CALC.F.

Reference:
    Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990), JGR, 95(C9), pp. 16,179
"""

import numpy as np
from typing import Tuple, Optional


def compute_viscosity_diffusivity(
    tke: np.ndarray,
    mixing_length: np.ndarray,
    mask: np.ndarray,
    params,
    n_square: Optional[np.ndarray] = None,
    shear_square: Optional[np.ndarray] = None,
    background_visc: float = 0.0,
    background_diff: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute eddy viscosity and diffusivity from TKE and mixing length.

    κ_m = max( c_k * L * √TKE, background_visc )
    κ_h = min( κ_m / Pr_T, diff_max ), floored by background_diff

    MITgcm computes the turbulent Prandtl number from the local
    Richardson number. The `alpha` parameter scales the TKE diffusivity
    used in the prognostic TKE equation.

    `background_visc`/`background_diff` are the model's background (floor)
    vertical viscosity/diffusivity (MITgcm's viscArNr/diffKrNrS) and are
    applied as a MAX floor exactly as ggl90_calc.F does.

    **Staggering**: κ_m[k]/κ_h[k] are at the TOP face of cell k
    (interface between cells k-1 and k), matching MITgcm's
    GGL90viscAz/GGL90diffKr index-for-index. Index 0 is the surface
    face and is set to 0 (no surface flux), consistent with the k=1
    surface start used by N²/shear/mixing-length.

    **MITgcm correspondence**: ggl90_calc.F:compute_viscosity_diffusivity

    Parameters
    ----------
    tke : np.ndarray, shape (nz,)
        Turbulent kinetic energy [m²/s²]
    mixing_length : np.ndarray, shape (nz,)
        Mixing length [m]
    mask : np.ndarray, shape (nz,)
        Vertical mask [0 or 1]
    params : GGL90Parameters
        Configuration object containing ck, ceps, alpha, visc_max, diff_max, etc.
    n_square : np.ndarray, optional
        Buoyancy frequency squared [s⁻²]. If provided, used to compute
        Richardson number for Prandtl number tuning.
    shear_square : np.ndarray, optional
        Vertical shear squared [s⁻²]. If provided with n_square, used for
        Richardson number computation.
    background_visc : float, optional
        Background (floor) vertical viscosity [m²/s], default 0.0
    background_diff : float, optional
        Background (floor) vertical diffusivity [m²/s], default 0.0

    Returns
    -------
    kappa_m : np.ndarray, shape (nz,)
        Eddy viscosity [m²/s], top face of cell k, index 0 = 0
    kappa_h : np.ndarray, shape (nz,)
        Eddy diffusivity [m²/s], top face of cell k, index 0 = 0
    """
    nz = len(tke)
    kappa_m = np.zeros(nz)
    kappa_h = np.zeros(nz)

    # Compute turbulent Prandtl number from Richardson number if available
    if n_square is None or shear_square is None:
        tke_prandtl_number = np.ones(nz)
    else:
        ri_number = np.maximum(n_square, 0.0) / (
            shear_square + params.ggl90_eps
        )
        tke_prandtl_number = np.ones(nz)
        stable = ri_number >= 0.2
        tke_prandtl_number[stable] = np.minimum(
            10.0, 5.0 * ri_number[stable]
        )

    # Start at k=1: index 0 is the surface face and stays 0. Interior faces
    # k=1..nz-1 carry the eddy coefficients.
    for k in range(1, nz):
        if mask[k] > 0:
            sqrt_tke = np.sqrt(max(tke[k], params.tke_min))
            kappa_raw = params.ck * mixing_length[k] * sqrt_tke

            # MITgcm floors KappaM with viscArNr(k) BEFORE it is used for
            # TKE production/KappaE/KappaH, then caps+re-floors the
            # exported coefficients (GGL90visctmp -> GGL90diffKr/viscAr).
            visc_tmp = max(kappa_raw, background_diff)
            kappa_m[k] = max(min(visc_tmp, params.visc_max),
                              background_visc)
            kappa_h[k] = max(min(visc_tmp / tke_prandtl_number[k],
                                  params.diff_max),
                              background_diff)

    return kappa_m, kappa_h
