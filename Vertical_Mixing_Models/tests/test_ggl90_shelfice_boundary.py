#!/usr/bin/env python3
"""
Unit tests for the `is_true_surface` boundary flag -- regression coverage for
1DMIX-038 (GGL90 port's surface-boundary-condition placement for
`ALLOW_SHELFICE` columns, e.g. `isomip`).

Background: for an `ALLOW_SHELFICE` column, MITgcm moves the effective
"surface" level for GGL90's boundary conditions from the fixed array index
`kSrf=1` to `kSrf=MAX(1,kTopC)` -- the true top wet cell under a floating ice
shelf. `run_ggl90_from_netcdf_input.py` (fixed 1DMIX-025) already feeds this
port a column slice starting at the real `kSrf`, so local index 0 IS that
real `kSrf`. This file tests that `compute_viscosity_diffusivity` and
`step_tke_forward`/`compute_mixing` reproduce MITgcm's real behavior AT that
shifted index (`is_true_surface=False`), while defaulting to today's exact,
already-validated behavior everywhere else (`is_true_surface=True`).

Root-cause mechanism (derived directly from `ggl90_calc.F`, confirmed against
every one of 28812 real ice-shelf column-timesteps in the `isomip` capture,
zero exceptions -- see `open_issues.md`'s 1DMIX-038 entry and this project's
`ggl90_mixing_coefficients.py`/`ggl90_core_driver.py` docstrings for the full
derivation):

  - `GGL90diffKr`'s final floor (`MAX(tmpVisc,diffKrNrS(k))`) is applied
    UNMASKED at every k the "proper k-loop" visits (k=2..Nr, Fortran
    1-based) -- at a real, shifted `kSrf>1`, this floor still applies even
    though the intermediate value feeding it was masked to 0 by the dry cell
    immediately above. Result: kappa_h[0] = the plain background diffusivity
    floor, not 0, when `is_true_surface=False`.
  - The post-solve "impose minimum TKE" loop (`maskC(k)*maskC(k-1)*
    MAX(GGL90TKE(k),GGL90TKEmin)`) ALSO runs over the same fixed k=2..Nr
    range and, at a real shifted `kSrf>1`, unconditionally zeroes the
    Dirichlet-assigned surface TKE via `maskC(kSrf-1)=0`. Result:
    tke_new[0] = 0.0 exactly, not `MAX(tke_surf_min, m2*u_star_sq)`, when
    `is_true_surface=False`.
  - `kappa_m[0]` needs no equivalent change: MITgcm's own viscosity output
    is masked AFTER its floor is applied, so it stays exactly 0 regardless
    of `is_true_surface` -- confirmed by 0 real visc_az mismatch at kSrf
    across all 58212 wet column-timesteps (ShelfIce and non-ShelfIce alike).

Round 2 addition (`mixing_length`'s own `is_true_surface` plumbing into
`GGL90MixingLength.compute()`/`_limit_method_2`'s `mxl_down[0]` seed): a
real, small, independently-derived fix (see those functions' own
docstrings) -- but verified NOT to explain the reported `kSrf+1` bimodal
mismatch in the real `isomip` capture. That mismatch is a
numerical-conditioning effect of `mixing_length`'s `1/sqrt(N²)` formula
amplifying an apparently general, small N² computation discrepancy near
N²≈0 -- confirmed to occur equally in ordinary, fully-wet
(`is_true_surface=True`) columns within the same capture. See
open_issues.md's 1DMIX-038 (this round's honest finding) and 1DMIX-039
(the newly-filed, separate, general N²/EOS precision question).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from GGL90.ggl90_core_driver import GGL90Driver
from GGL90.ggl90_parameters import GGL90Parameters
from GGL90.ggl90_mixing_coefficients import compute_viscosity_diffusivity
from GGL90.ggl90_scheme_specific import GGL90MixingLength

TOL = 1e-12


def test_diffusivity_default_is_true_surface_matches_zero_flux_convention():
    """is_true_surface defaults to True: kappa_h[0]=kappa_m[0]=0, unchanged
    from every pre-existing non-ShelfIce comparison."""
    params = GGL90Parameters.from_yaml()
    nz = 5
    tke = np.full(nz, 1.0e-3)
    mixing_length = np.full(nz, 5.0)
    mask = np.ones(nz)

    # 1DMIX-048: third return value (kappa_h_tendency) unused by this
    # test -- it exercises kappa_h/kappa_m's own is_true_surface
    # behavior, unaffected by that fix.
    kappa_m, kappa_h, _kappa_h_tendency = compute_viscosity_diffusivity(
        tke, mixing_length, mask, params,
        background_visc=1.0e-4, background_diff=1.0e-5,
    )
    assert kappa_m[0] == 0.0
    assert kappa_h[0] == 0.0
    print("PASS test_diffusivity_default_is_true_surface_matches_zero_flux_convention")


def test_diffusivity_shifted_surface_floors_kappa_h_but_not_kappa_m():
    """is_true_surface=False: kappa_h[0] becomes the plain background
    diffusivity floor (matching MITgcm's real diffKr(kSrf) exactly -- the
    local mixing_length/TKE magnitude at index 0 is discarded, not blended
    in), while kappa_m[0] stays exactly 0 (MITgcm's real viscAz(kSrf))."""
    params = GGL90Parameters.from_yaml()
    nz = 5
    # A deliberately LARGE local TKE/mixing_length at index 0, so that if
    # the raw physics were (incorrectly) blended into kappa_h[0] instead of
    # being discarded by MITgcm's own masked-then-unmasked-refloor
    # mechanism, kappa_h[0] would come out far above the background floor.
    tke = np.array([10.0, 1.0e-3, 1.0e-3, 1.0e-3, 1.0e-3])
    mixing_length = np.full(nz, 100.0)
    mask = np.ones(nz)
    background_visc = 1.0e-4
    background_diff = 1.0e-5

    # 1DMIX-048: third return value (kappa_h_tendency) unused by this
    # test -- see note above.
    kappa_m, kappa_h, _kappa_h_tendency = compute_viscosity_diffusivity(
        tke, mixing_length, mask, params,
        background_visc=background_visc, background_diff=background_diff,
        is_true_surface=False,
    )
    assert kappa_m[0] == 0.0, "viscosity must stay 0 at a shifted kSrf too"
    assert abs(kappa_h[0] - background_diff) < TOL, (
        "diffusivity at a shifted kSrf must be exactly the background "
        "floor, not blended with the local (masked-away) raw physics"
    )
    # Interior levels (k=1..nz-1) are completely unaffected by the flag.
    assert kappa_h[1] > background_diff
    print("PASS test_diffusivity_shifted_surface_floors_kappa_h_but_not_kappa_m")


def test_tke_default_is_true_surface_keeps_dirichlet_value():
    """is_true_surface defaults to True: tke_new[0] keeps the ordinary
    surface Dirichlet value, unchanged from every pre-existing comparison
    (matches test_staggering.py's own
    test_ggl90_surface_tke_boundary_is_not_first_interior_face)."""
    params = GGL90Parameters.from_yaml()
    params.tke_surf_min = 1.0e-3
    params.tke_bottom = params.tke_min
    drv = GGL90Driver(params)
    nz = 4
    tke = np.full(nz, params.tke_min)
    zeros = np.zeros(nz)

    tke_new = drv.step_tke_forward(
        tke=tke, production=zeros, buoyancy=zeros,
        mixing_length=np.full(nz, 10.0), dz=np.ones(nz), dt=600.0,
        mask=np.ones(nz), u_star_sq=1e-4,
    )
    assert abs(tke_new[0] - params.tke_surf_min) < TOL
    print("PASS test_tke_default_is_true_surface_keeps_dirichlet_value")


def test_tke_shifted_surface_discards_dirichlet_value():
    """is_true_surface=False: tke_new[0] is forced to exactly 0.0, matching
    MITgcm's real post-solve masking at a shifted kSrf -- even with a large
    surface forcing that would otherwise make the Dirichlet value large."""
    params = GGL90Parameters.from_yaml()
    params.tke_surf_min = 1.0e-3
    params.tke_bottom = params.tke_min
    drv = GGL90Driver(params)
    nz = 4
    tke = np.full(nz, params.tke_min)
    zeros = np.zeros(nz)

    tke_new = drv.step_tke_forward(
        tke=tke, production=zeros, buoyancy=zeros,
        mixing_length=np.full(nz, 10.0), dz=np.ones(nz), dt=600.0,
        mask=np.ones(nz), u_star_sq=10.0,  # large forcing
        is_true_surface=False,
    )
    assert tke_new[0] == 0.0, "TKE at a shifted kSrf must be exactly 0.0"
    # Interior levels are unaffected by the flag.
    assert tke_new[1] > params.tke_min
    print("PASS test_tke_shifted_surface_discards_dirichlet_value")


def test_compute_mixing_threads_is_true_surface_end_to_end():
    """GGL90Driver.compute_mixing passes is_true_surface through to both
    compute_viscosity_diffusivity and step_tke_forward, and defaults to
    today's exact (is_true_surface=True) behavior when the caller omits it."""
    params = GGL90Parameters.from_yaml()
    nz = 6
    tke = np.full(nz, 1.0e-3)
    u = np.linspace(0.1, 0.0, nz)
    v = np.linspace(0.05, 0.0, nz)
    theta = np.linspace(-1.8, -1.9, nz)
    salt = np.linspace(34.4, 34.6, nz)
    dz = np.full(nz, 20.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    z = -depth
    mask = np.ones(nz)
    background_visc = 1.0e-4
    background_diff = 1.0e-5

    drv = GGL90Driver(params)

    out_default = drv.compute_mixing(
        tke=tke, u=u, v=v, theta=theta, salt=salt, depth=depth, z=z, dz=dz,
        dt=600.0, mask=mask, u_star_sq=1.0e-4,
        background_visc=background_visc, background_diff=background_diff,
    )
    assert out_default.kappa_h[0] == 0.0
    assert out_default.kappa_m[0] == 0.0

    out_shifted = drv.compute_mixing(
        tke=tke, u=u, v=v, theta=theta, salt=salt, depth=depth, z=z, dz=dz,
        dt=600.0, mask=mask, u_star_sq=1.0e-4,
        background_visc=background_visc, background_diff=background_diff,
        is_true_surface=False,
    )
    assert abs(out_shifted.kappa_h[0] - background_diff) < TOL
    assert out_shifted.kappa_m[0] == 0.0
    assert out_shifted.tke_new[0] == 0.0

    # Interior output is identical regardless of the flag (it only ever
    # touches local index 0).
    assert np.array_equal(out_default.kappa_m[1:], out_shifted.kappa_m[1:])
    # mixing_length itself: with mxl_max_flag=0 (this test's default, per
    # ggl90_default_parameters.yaml), is_true_surface never reaches
    # _limit_method_2 at all (only mxl_max_flag in {2,3} builds mxl_down),
    # so both flag values give byte-identical mixing_length here -- NOT a
    # general claim for mxl_max_flag in {2,3} (see the mxl_down[0]-seed
    # tests below).
    assert np.array_equal(out_default.mixing_length, out_shifted.mixing_length)
    print("PASS test_compute_mixing_threads_is_true_surface_end_to_end")


def test_limit_method_2_mxl_down_seed_matches_true_surface_default():
    """is_true_surface defaults to True: mxl_down[0]=mixing_length_min,
    matching Fortran's real, kSrf-independent mxLength_Dn(1) boundary
    condition (ggl90_mixinglength.F:131) -- exact no-op, every
    pre-existing (non-ShelfIce) call site."""
    params = GGL90Parameters.from_yaml()
    params.mxl_max_flag = 2
    calc = GGL90MixingLength(params)
    nz = 3
    mixing_length = np.array([params.mixing_length_min, 100.0, 100.0])
    dz = np.full(nz, 0.5)
    mask = np.ones(nz)

    _, mxl_down = calc._limit_method_2(mixing_length, dz, mask)
    assert mxl_down[0] == params.mixing_length_min
    print("PASS test_limit_method_2_mxl_down_seed_matches_true_surface_default")


def test_limit_method_2_mxl_down_seed_is_zero_for_shifted_surface():
    """is_true_surface=False: mxl_down[0]=0.0 exactly, matching MITgcm's
    real mxLength_Dn(kSrf) -- accumulated to exactly 0.0 (not
    GGL90mixingLengthMin) by cascading MIN(0,...)=0 through every dry
    level above a real, shifted kSrf (see `_limit_method_2`'s own
    docstring). A small but real, independently-derived fix: when the
    downward-sweep envelope (mxl_down[k-1]+dz[k-1]) is the active MIN()
    branch (exercised here with a thin dz[0]=0.5 m surface cell and a
    deliberately huge raw mixing_length[1], as from a near-zero N²), the
    resulting mxl_down[1] differs from the is_true_surface=True case by
    exactly mixing_length_min -- confirmed NOT to be the mechanism behind
    the reported real `isomip` kSrf+1 bimodal mismatch (open_issues.md's
    1DMIX-038/1DMIX-039): that capture's own uniform 30 m cells never make
    this branch binding, so this fix's real-world effect there is
    numerically negligible even though it is exercised here."""
    params = GGL90Parameters.from_yaml()
    params.mxl_max_flag = 2
    calc = GGL90MixingLength(params)
    nz = 3
    mixing_length = np.array([params.mixing_length_min, 1.0e4, 1.0e4])
    dz = np.full(nz, 0.5)
    mask = np.ones(nz)

    _, mxl_down_true = calc._limit_method_2(mixing_length, dz, mask, is_true_surface=True)
    _, mxl_down_shifted = calc._limit_method_2(mixing_length, dz, mask, is_true_surface=False)

    assert mxl_down_true[0] == params.mixing_length_min
    assert mxl_down_shifted[0] == 0.0
    # Envelope branch is binding at k=1 (raw 1e4 >> dz[0]=0.5): both should
    # equal dz[0] plus their own seed, exactly.
    assert abs(mxl_down_true[1] - (params.mixing_length_min + dz[0])) < TOL
    assert abs(mxl_down_shifted[1] - dz[0]) < TOL
    assert abs(mxl_down_true[1] - mxl_down_shifted[1] - params.mixing_length_min) < TOL
    print("PASS test_limit_method_2_mxl_down_seed_is_zero_for_shifted_surface")


def test_mixing_length_compute_is_true_surface_default_matches_pre_round2():
    """GGL90MixingLength.compute()'s new is_true_surface parameter defaults
    to True -- exact behavioral no-op for every pre-existing (mxl_max_flag
    in {0,1,2,3}) call site, since mxl_down[0]'s seed is unchanged from
    before this parameter existed."""
    params = GGL90Parameters.from_yaml()
    params.mxl_max_flag = 2
    calc = GGL90MixingLength(params)
    nz = 5
    tke = np.array([1e-3, 1.0, 1e-3, 1e-3, 1e-3])
    n_square = np.array([0.0, 1e-8, 1e-4, 1e-4, 1e-4])
    dz = np.full(nz, 0.5)
    depth_to_surface = np.cumsum(dz) - dz
    depth_to_bottom = np.sum(dz) - np.cumsum(dz) + dz
    mask = np.ones(nz)

    ml_explicit, _ = calc.compute(
        tke, n_square, dz, depth_to_surface, depth_to_bottom, mask,
        is_true_surface=True,
    )
    ml_default, _ = calc.compute(
        tke, n_square, dz, depth_to_surface, depth_to_bottom, mask,
    )
    assert np.array_equal(ml_explicit, ml_default)
    print("PASS test_mixing_length_compute_is_true_surface_default_matches_pre_round2")


if __name__ == "__main__":
    test_diffusivity_default_is_true_surface_matches_zero_flux_convention()
    test_diffusivity_shifted_surface_floors_kappa_h_but_not_kappa_m()
    test_tke_default_is_true_surface_keeps_dirichlet_value()
    test_tke_shifted_surface_discards_dirichlet_value()
    test_compute_mixing_threads_is_true_surface_end_to_end()
    test_limit_method_2_mxl_down_seed_matches_true_surface_default()
    test_limit_method_2_mxl_down_seed_is_zero_for_shifted_surface()
    test_mixing_length_compute_is_true_surface_default_matches_pre_round2()
