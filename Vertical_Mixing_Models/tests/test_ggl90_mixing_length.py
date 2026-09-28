"""
Unit tests for GGL90MixingLength.compute() -- regression coverage for 1DMIX-014.

1DMIX-014 root cause (verified against
/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ggl90_mixinglength.F, the real
MITgcm source this project ports): compute()'s final "impose minimum" step
previously applied `mixing_length[k] = max(mixing_length[k], mixing_length_min)`
unconditionally to every level, for every mxl_max_flag.

Reading ggl90_mixinglength.F:381-416 (the final floor-and-reciprocal step)
shows this is only correct for mxl_max_flag in {0,1,2} (the ELSE branch,
ggl90_mixinglength.F:401-416: a genuine blanket MAX(L,min) applied to both
GGL90mixingLength and its reciprocal). mxl_max_flag==3 takes a DIFFERENT IF
branch (ggl90_mixinglength.F:383-400): GGL90mixingLength itself is NOT
reassigned there -- it keeps its raw (possibly sub-minimum) two-way-sweep
value; only the reciprocal is floored, using
sqrt(L(k)*mxLength_Dn(k)) clamped at mixing_length_min.

Note this means the fix is scoped to mxl_max_flag==3 specifically, not to
"the two-way-sweep methods (2 and 3)" as originally hypothesized when this
issue was opened -- mxl_max_flag==2 legitimately still floors L via the ELSE
branch. Both behaviors are covered below so a future change cannot silently
regress either one.

Also covers 1DMIX-030 (mxl_max_flag=0's `_limit_method_0` ceiling, plus the
`GGL90Driver.compute_mixing` construction that feeds it): the ceiling must
be the INTERFACE-to-interface water column depth (`Ro_surf-R_low`), not the
cell-center-to-cell-center span, which is short by half the top cell's
thickness plus half the bottom cell's -- see
`test_limit_method_0_ceiling_is_interface_span_not_cell_center` and
`test_compute_mixing_builds_interface_derived_ceiling` below.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from GGL90.ggl90_parameters import GGL90Parameters
from GGL90.ggl90_scheme_specific import GGL90MixingLength

TOL = 1e-12


def _stratified_calm_column(nz=6, dz_val=10.0, n2_val=1.0e-4, params=None):
    """A column with TKE pinned at tke_min and uniform strong stratification.

    With TKE this small, the Gaspar formula L = sqrt(2*TKE)/sqrt(N^2)
    (ggl90_calc.F:352-354, eq. 2.35) produces a raw mixing length far below
    any physically reasonable mixing_length_min -- exactly the regime 1DMIX-014
    was found in (MITgcm's own vermix capture: mixing_length[1:4] =
    [0.760, 0.112, 0.112] against mixing_length_min=3.0).
    """
    dz = np.full(nz, dz_val)
    mask = np.ones(nz)
    tke = np.full(nz, params.tke_min)
    n_square = np.full(nz, n2_val)
    depth_to_surface = np.cumsum(dz) - dz  # unused by method 2, harmless for 0/1
    depth_to_bottom = np.sum(dz) - depth_to_surface - dz
    return tke, n_square, dz, depth_to_surface, depth_to_bottom, mask


def test_mxl_max_flag_3_allows_submin_mixing_length():
    """mxl_max_flag==3: mixing_length itself must NOT be floored to
    mixing_length_min at depth (ggl90_mixinglength.F:387-400), even though its
    reciprocal is floored (ggl90_mixinglength.F:395)."""
    params = GGL90Parameters(mxl_max_flag=3, mixing_length_min=3.0)
    calc = GGL90MixingLength(params)
    tke, n_square, dz, d_surf, d_bot, mask = _stratified_calm_column(params=params)

    mixing_length, r_mixing_length = calc.compute(
        tke, n_square, dz, d_surf, d_bot, mask
    )

    assert mixing_length[0] == params.mixing_length_min, (
        "surface level (k=0) is seeded to mixing_length_min "
        "(ggl90_calc.F:276) and never touched by GGL90_MIXINGLENGTH"
    )
    assert np.any(mixing_length[1:] < params.mixing_length_min), (
        "mxl_max_flag==3 must allow sub-minimum mixing length at depth "
        "for a low-TKE, strongly stratified column"
    )
    assert np.all(mixing_length[1:] > 0.0), "mixing length must stay positive"
    # The reciprocal must still be regularized (never blows up / divides by
    # a near-zero length): 1/r_mixing_length >= mixing_length_min.
    assert np.all(r_mixing_length[1:] > 0.0)
    implied_length = 1.0 / r_mixing_length[1:]
    assert np.all(implied_length >= params.mixing_length_min - TOL), (
        "reciprocal mixing length must be floored via "
        "sqrt(L(k)*mxLength_Dn(k)) clamped at mixing_length_min "
        "(ggl90_mixinglength.F:391-396), even though L itself is unfloored"
    )
    print("PASS test_mxl_max_flag_3_allows_submin_mixing_length")


def test_mxl_max_flag_2_still_floors_mixing_length():
    """Contrast case: mxl_max_flag==2 takes the ELSE branch
    (ggl90_mixinglength.F:401-416) and DOES apply a blanket MAX(L,min) floor
    to mixing_length itself. Same raw (sub-minimum) physics input as the
    flag==3 test above, to isolate the flag-dependent floor behavior."""
    params = GGL90Parameters(mxl_max_flag=2, mixing_length_min=3.0)
    calc = GGL90MixingLength(params)
    tke, n_square, dz, d_surf, d_bot, mask = _stratified_calm_column(params=params)

    mixing_length, r_mixing_length = calc.compute(
        tke, n_square, dz, d_surf, d_bot, mask
    )

    assert np.all(mixing_length[1:] == params.mixing_length_min), (
        "mxl_max_flag==2 must floor every interior level to mixing_length_min"
    )
    assert np.allclose(
        r_mixing_length[1:], 1.0 / params.mixing_length_min, atol=0, rtol=TOL
    ), "for mxl_max_flag==2 the reciprocal must be exactly 1/mixing_length_min"
    print("PASS test_mxl_max_flag_2_still_floors_mixing_length")


def test_mxl_max_flag_0_and_1_float_mixing_length_and_still_floor():
    """mxl_max_flag in {0,1} take the same ELSE branch as flag==2
    (ggl90_mixinglength.F:401-416): blanket floor applies. Also checks the
    surface level (k=0) is excluded from these limiters
    (ggl90_mixinglength.F:168-179, :183-193 both run `DO k=2,Nr`) and keeps
    the mixing_length_min seed."""
    for flag in (0, 1):
        params = GGL90Parameters(mxl_max_flag=flag, mixing_length_min=3.0)
        calc = GGL90MixingLength(params)
        tke, n_square, dz, d_surf, d_bot, mask = _stratified_calm_column(params=params)

        mixing_length, r_mixing_length = calc.compute(
            tke, n_square, dz, d_surf, d_bot, mask
        )

        assert mixing_length[0] == params.mixing_length_min
        assert np.all(mixing_length[1:] == params.mixing_length_min), (
            f"mxl_max_flag=={flag} must floor every interior level"
        )
    print("PASS test_mxl_max_flag_0_and_1_float_mixing_length_and_still_floor")


def test_limit_method_0_ceiling_is_interface_span_not_cell_center():
    """Regression test for 1DMIX-030: the mxl_max_flag=0 ceiling passed into
    `_limit_method_0` must be the INTERFACE-to-interface water column depth
    (`Ro_surf-R_low`, ggl90_mixinglength.F:168-179), not the cell-center-to-
    cell-center span (`z[0]-z[-1]`) a previous version of
    `ggl90_core_driver.py::GGL90Driver.compute_mixing` used to build
    `depth_to_surface`/`depth_to_bottom` -- short by half the top cell's
    thickness plus half the bottom cell's. Uses an asymmetric-cell grid
    (top cell 2 m, bottom cell 40 m) so the two candidate ceilings are
    provably, meaningfully different (21 m apart here), then directly
    reproduces both the fixed and the old, buggy construction to confirm
    `_limit_method_0` picks up whichever ceiling it is given -- i.e. this
    exercises the exact real-Fortran-vs-Python divergence found via the
    standalone-GGL90_CALC-driver scenario check (e.g. arctic_convection:
    diff exactly 40.790 m = that scenario's own half-cell offset)."""
    dz = np.array([2.0, 10.0, 10.0, 10.0, 40.0])
    nz = len(dz)
    mask = np.ones(nz)

    total_depth = float(np.sum(dz))  # Ro_surf - R_low (the correct ceiling)

    # Cell-center span (the OLD, pre-1DMIX-030-fix formula) -- provably
    # smaller by exactly half the top cell's thickness plus half the
    # bottom cell's.
    z = np.zeros(nz)
    z[0] = -0.5 * dz[0]
    for k in range(1, nz):
        z[k] = z[k - 1] - 0.5 * dz[k - 1] - 0.5 * dz[k]
    cell_center_span = z[0] - z[-1]
    half_cell_offset = 0.5 * dz[0] + 0.5 * dz[-1]
    assert abs(total_depth - cell_center_span - half_cell_offset) < 1e-9
    assert total_depth - cell_center_span > 1.0, (
        "grid must be asymmetric enough that the two candidate ceilings "
        "are meaningfully (not just roundoff) different"
    )

    # Correct (interface-derived) depth_to_surface/depth_to_bottom, matching
    # ggl90_core_driver.py::GGL90Driver.compute_mixing's fixed construction
    # (interfaces[0]=0=Ro_surf, interfaces[nz]=-total_depth=R_low).
    interfaces = np.zeros(nz + 1)
    interfaces[1:] = -np.cumsum(dz)
    depth_to_surface = -interfaces[:nz]
    depth_to_bottom = interfaces[:nz] - interfaces[nz]

    params = GGL90Parameters(mxl_max_flag=0, mixing_length_min=0.5)
    calc = GGL90MixingLength(params)

    huge_raw_length = np.full(nz, 1.0e6)  # far above either candidate ceiling
    clamped = calc._limit_method_0(
        huge_raw_length, depth_to_surface, depth_to_bottom, mask
    )
    assert np.allclose(clamped[1:], total_depth, atol=1e-9), (
        "mxl_max_flag=0 ceiling must equal the interface-to-interface "
        f"water column depth ({total_depth} m), got {clamped[1:]}"
    )

    # The OLD (buggy) construction must give the smaller, wrong ceiling --
    # demonstrating this test would have failed against the pre-fix code.
    old_depth_to_surface = z[0] - z
    old_depth_to_bottom = z - z[-1]
    old_clamped = calc._limit_method_0(
        huge_raw_length, old_depth_to_surface, old_depth_to_bottom, mask
    )
    assert np.allclose(old_clamped[1:], cell_center_span, atol=1e-9)
    assert not np.allclose(old_clamped[1:], clamped[1:]), (
        "the fixed (interface-derived) and old (cell-center-derived) "
        "ceilings must differ on this asymmetric-cell grid"
    )
    print("PASS test_limit_method_0_ceiling_is_interface_span_not_cell_center")


def test_compute_mixing_builds_interface_derived_ceiling():
    """Integration-level regression for 1DMIX-030: checks
    `GGL90Driver.compute_mixing` itself (not just `_limit_method_0` in
    isolation) builds `depth_to_surface`/`depth_to_bottom` from interface
    depths, not cell centers. Forces a huge raw (unclamped) Gaspar mixing
    length (large TKE, exactly-uniform T/S -> N²=0 -> the `ggl90_eps` floor
    applies) on the same asymmetric-cell grid as the test above, so the
    ceiling is guaranteed to bind, then checks the actual clamped output
    against the true interface-to-interface total depth (not the shorter
    cell-center span the pre-fix driver produced)."""
    from GGL90.ggl90_core_driver import GGL90Driver

    dz = np.array([2.0, 10.0, 10.0, 10.0, 40.0])
    nz = len(dz)
    total_depth = float(np.sum(dz))

    z = np.zeros(nz)
    z[0] = -0.5 * dz[0]
    for k in range(1, nz):
        z[k] = z[k - 1] - 0.5 * dz[k - 1] - 0.5 * dz[k]
    cell_center_span = z[0] - z[-1]
    assert total_depth - cell_center_span > 1.0  # meaningfully different

    params = GGL90Parameters(mxl_max_flag=0)
    driver = GGL90Driver(params=params)

    tke = np.full(nz, 100.0)
    u = np.zeros(nz)
    v = np.zeros(nz)
    theta = np.full(nz, 10.0)  # exactly uniform -> N^2 = 0 exactly
    salt = np.full(nz, 35.0)

    out = driver.compute_mixing(
        tke=tke, u=u, v=v, theta=theta, salt=salt,
        depth=z, z=z, dz=dz, dt=100.0, mask=np.ones(nz), u_star_sq=0.01,
    )

    assert np.allclose(out.mixing_length[1:], total_depth, atol=1e-6), (
        f"expected mixing_length clamped to the interface-to-interface "
        f"total depth ({total_depth} m), got {out.mixing_length[1:]} -- if "
        f"this equals the cell-center span ({cell_center_span} m) instead, "
        f"the 1DMIX-030 bug has regressed"
    )
    print("PASS test_compute_mixing_builds_interface_derived_ceiling")


def test_limit_method_2_bottom_boundary_treatment():
    """1DMIX-014 follow-up finding: the two-way sweep's upward pass must
    apply the bottom-boundary special treatment
    (ggl90_mixinglength.F:264-267 for z-coordinates: `L(Nr) = MIN(L(Nr),
    mixing_length_min + drF(Nr))`) BEFORE sweeping upward, not leave the
    bottom level's raw value unclamped. Use a non-uniform grid with a large
    raw mixing length at the bottom so the clamp is exercised."""
    params = GGL90Parameters(mxl_max_flag=2, mixing_length_min=3.0)
    calc = GGL90MixingLength(params)
    nz = 4
    dz = np.array([10.0, 10.0, 10.0, 5.0])
    mask = np.ones(nz)
    # Very energetic + weakly stratified bottom level -> huge raw Gaspar
    # length, to check it gets clamped by mixing_length_min + dz[-1] = 8.0
    # before/through the upward sweep, not left at its raw (huge) value.
    tke = np.array([params.tke_min, params.tke_min, params.tke_min, 10.0])
    n_square = np.full(nz, params.ggl90_eps)  # ~unstratified -> huge raw L

    mixing_length, _ = calc._limit_method_2(
        np.array([params.mixing_length_min, 0.0, 0.0, 1.0e6]), dz, mask
    )
    assert mixing_length[-1] <= params.mixing_length_min + dz[-1] + TOL, (
        "bottom level must be capped by mixing_length_min + dz[-1] before "
        "the upward sweep uses it (ggl90_mixinglength.F:264-267)"
    )
    print("PASS test_limit_method_2_bottom_boundary_treatment")


if __name__ == "__main__":
    test_mxl_max_flag_3_allows_submin_mixing_length()
    test_mxl_max_flag_2_still_floors_mixing_length()
    test_mxl_max_flag_0_and_1_float_mixing_length_and_still_floor()
    test_limit_method_0_ceiling_is_interface_span_not_cell_center()
    test_compute_mixing_builds_interface_derived_ceiling()
    test_limit_method_2_bottom_boundary_treatment()
