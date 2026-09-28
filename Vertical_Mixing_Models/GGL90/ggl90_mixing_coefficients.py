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
    is_true_surface: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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

    **1DMIX-048 fix**: also returns `kappa_h_tendency`, a THIRD quantity
    distinct from both `kappa_m` and `kappa_h`. MITgcm's real TKE
    buoyancy term (`ggl90_calc.F:661,673`, `-KappaH*Nsquare(k)`) uses
    `KappaH = KappaM(i,j)/TKEPrandtlNumber(k)`, where `KappaM(i,j)` at
    that point has already been reassigned (`ggl90_calc.F:512-514`,
    `KappaM(i,j) = MAX(KappaM_raw,viscArNr(k))*maskC*maskC`) to carry
    ONLY its own viscosity floor -- the exact same value this function
    returns as `kappa_m`/exports as `GGL90viscOutput` (confirmed exact to
    floating-point roundoff against MITgcm in every capture checked so
    far, unaffected by this fix). This is a genuinely different quantity
    from `GGL90visctmp` (`ggl90_calc.F:507-509`, floored by the
    *diffusivity* background `diffKrNrS` instead), which is what
    eventually becomes the *exported* `GGL90diffKr`/`kappa_h` after an
    additional `diffMax` cap and `diffKrNrS` re-floor
    (`ggl90_calc.F:1086-1088`) -- correct for `kappa_h` as a diagnostic
    output, but NOT the quantity the real buoyancy term actually uses.
    The two coincide only when `background_visc == background_diff` (or
    the raw turbulent value already exceeds both floors) -- neither held
    for any of the 6 idealized scenarios (`viscAz=5e-5 != diffKzS=1e-5`),
    which is exactly how this bug was found (1DMIX-041). Root-caused and
    fixed via `kappa_h_tendency = kappa_m / tke_prandtl_number`: no
    additional flooring by `background_diff`, no `diff_max` cap -- only
    `kappa_m`'s own viscosity floor applies, matching MITgcm's real
    `KappaM` exactly. Callers must feed `kappa_h_tendency` (not
    `kappa_h`) to `compute_tke_buoyancy`; `kappa_h` remains exactly as
    before (untouched) for every other use.

    **Staggering**: κ_m[k]/κ_h[k] are at the TOP face of cell k
    (interface between cells k-1 and k), matching MITgcm's
    GGL90viscAz/GGL90diffKr index-for-index. Index 0 is the surface
    face; κ_m[0] is always 0 (no surface flux for viscosity).

    **1DMIX-038 fix**: κ_h[0] is 0 only when `is_true_surface=True`
    (default, every pre-existing call site -- exact behavioral no-op).
    For an `ALLOW_SHELFICE` column, MITgcm moves the effective surface to
    `kSrf=MAX(1,kTopC)` and the caller feeds this function a column slice
    starting there (`is_true_surface=False`); local index 0 then
    represents that real, interior `kSrf`, not the model's fixed k=1
    array boundary. Derived directly from `ggl90_calc.F` (isomip
    `code_validation/ggl90_calc.F`, read fresh for this issue) and
    confirmed against every one of 28812 real ice-shelf column-timesteps
    in the `isomip` capture (zero exceptions):

    - `GGL90diffKr`'s "proper k-loop" (`DO k=2,Nr`, Fortran 1-based --
      i.e. every array index except the true k=1 surface, which this
      loop never visits) computes an intermediate `GGL90visctmp(k)`
      masked by `maskC(k)*maskC(k-1)` (ggl90_calc.F:491-493) -- at
      `k=kSrf`, `maskC(kSrf-1)=0` (the ice-shelf-masked cell immediately
      above the slice), so `GGL90visctmp(kSrf)=0` regardless of the real
      mixing_length/TKE there. But the FINAL `GGL90diffKr` assignment
      (ggl90_calc.F:1061, `MAX(tmpVisc,diffKrNrS(k))`) applies the
      background floor **unmasked**, so `GGL90diffKr(kSrf) =
      MAX(0,diffKrNrS(kSrf)) = diffKrNrS(kSrf)` exactly -- the plain
      background floor, discarding the local physics entirely (point
      check: `isomip` x=1,y=1, kSrf=22, `mit_diff_kz[22]=5e-05=
      PARAM_diffKzS`). For the true k=1 surface (`is_true_surface=True`),
      k=1 is outside the proper k-loop's `k=2,Nr` range and `GGL90diffKr`
      is never touched here at all, keeping its zero-initialized value
      (unchanged, matches every previously-validated non-ShelfIce
      experiment).
    - `GGL90viscOutput` (the κ_m diagnostic) needs no analogous change:
      its own final assignment (ggl90_calc.F:496-499) applies the
      `viscArNr` floor **then** multiplies by `maskC(k)*maskC(k-1)`, so
      it stays exactly 0 at `kSrf` too (confirmed: 0 visc_az mismatch at
      `kSrf` across all 58212 wet column-timesteps, ShelfIce and
      non-ShelfIce alike) -- this function's unconditional
      `kappa_m[0]=0` already matches that regardless of
      `is_true_surface`.

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
    is_true_surface : bool, optional
        True (default) when index 0 is the model's true k=1 array
        boundary (every non-ShelfIce experiment): κ_h[0] stays 0. Set
        False when the caller has sliced a column starting at a real,
        shifted `kSrf>1` (an `ALLOW_SHELFICE` column): κ_h[0] becomes the
        plain `background_diff` floor instead, matching MITgcm's real
        behavior there (see 1DMIX-038 note above). Does not affect
        κ_m[0], which is 0 in both cases.

    Returns
    -------
    kappa_m : np.ndarray, shape (nz,)
        Eddy viscosity [m²/s], top face of cell k, index 0 = 0
    kappa_h : np.ndarray, shape (nz,)
        Eddy diffusivity [m²/s], top face of cell k, index 0 = 0 if
        `is_true_surface`, else the background diffusivity floor. This
        is the diagnostic/output quantity (`GGL90diffKr`) -- do not feed
        it to `compute_tke_buoyancy` (see 1DMIX-048 note above).
    kappa_h_tendency : np.ndarray, shape (nz,)
        `kappa_m / tke_prandtl_number` [m²/s], top face of cell k, index
        0 = 0 always (mirrors `kappa_m[0]`, not `kappa_h[0]`'s
        ShelfIce-specific floor -- see 1DMIX-048 note above). This is
        the internal, tendency-only quantity the real TKE buoyancy term
        uses (MITgcm's `KappaH`, `ggl90_calc.F:661`); feed THIS to
        `compute_tke_buoyancy`, not `kappa_h`.
    """
    nz = len(tke)
    kappa_m = np.zeros(nz)
    kappa_h = np.zeros(nz)
    kappa_h_tendency = np.zeros(nz)

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

            # 1DMIX-048: MITgcm's real TKE buoyancy term
            # (ggl90_calc.F:661,673) divides the viscosity-floored-only
            # KappaM (kappa_m[k], already computed above) by the Prandtl
            # number -- NOT the diffusivity-floored/capped kappa_h[k].
            # No further flooring/capping here; kappa_m[k] already
            # carries its own (viscosity) floor.
            kappa_h_tendency[k] = kappa_m[k] / tke_prandtl_number[k]

    # 1DMIX-038: for an ALLOW_SHELFICE column (is_true_surface=False),
    # local index 0 is a real, interior kSrf>1, not the model's true k=1
    # boundary -- MITgcm's own GGL90diffKr floor applies unmasked there
    # (see docstring), discarding the local physics and leaving exactly
    # the background floor. kappa_m[0] needs no change (stays 0 in both
    # cases -- see docstring).
    if not is_true_surface:
        kappa_h[0] = max(min(0.0, params.diff_max), background_diff)
    # kappa_h_tendency[0] intentionally does NOT get the same
    # ShelfIce-specific floor as kappa_h[0]: MITgcm's real KappaM(kSrf)
    # (the value the buoyancy term's KappaH divides by TKEPrandtlNumber)
    # is masked to exactly 0 at kSrf by the same maskC(kSrf-1)=0 that
    # keeps kappa_m[0]=0 there (ggl90_calc.F:512-514) -- unlike
    # GGL90diffKr's floor, which is applied UNMASKED afterward
    # (ggl90_calc.F:1088, see kappa_h's own docstring/1DMIX-038). This
    # has no observable effect regardless: step_tke_forward's own
    # 1DMIX-038 fix unconditionally overwrites tke_new[0]=0.0 for
    # is_true_surface=False, so whatever value reaches buoyancy[0] here
    # never propagates to any output.

    return kappa_m, kappa_h, kappa_h_tendency
