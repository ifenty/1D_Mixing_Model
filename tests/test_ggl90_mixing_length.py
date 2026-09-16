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
    test_limit_method_2_bottom_boundary_treatment()
