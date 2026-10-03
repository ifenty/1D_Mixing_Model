"""
1DMIX-080: the port's Jerlov water type is MITgcm's hard-coded type IA.
1DMIX-085: the port's `swfrac` has MITgcm's 200 m cut-off (section (D)).

MITgcm `model/src/swfrac.F` (checked at MITgcm d861cd501) sets `jwtype=2` in both branches of
`#ifdef ALLOW_CAL` (lines 92 and 94; header comment line 23: "Parameter jwtype is hardcoded to 2 for
time being"). Its type table (lines 71-76) maps jwtype 2 to Jerlov type IA: `rfac=0.62`, `a1=0.6`,
`a2=20.0`. No namelist parameter sets it, so no MITgcm capture records it; until 1DMIX-080 the port
defaulted to type IB (jwtype 3) in `KPPParameters.jerlov_water_type`, `kpp_default_parameters.yaml` and
`kpp_shortwave.py::swfrac`'s signature.

This module asserts:

(A) the default is IA in all three places, and `JERLOV_TABLE` equals swfrac.F's DATA statements
    (lines 74-76) for all five types;
(B) `swfrac(depth, "IA")` equals MITgcm's own SWFRAC output bit for bit. The reference values were
    computed by MITgcm itself, not by this project: every KPP capture carries `swatt`, MITgcm's
    `SWFrac3D` (written by `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_mods/
    kpp_calc.F:1345-1349` in format ES25.16, 17 significant digits). `model/src/ini_forcing.F:150-182`
    fills it with `CALL SWFRAC(Nr+1, oneRL, SWFracK, ...)`, `SWFracK(k) = rF(k) - rF(1)`, i.e. the
    compiled swfrac.F evaluated with jwtype=2 at each interface depth. `_MITGCM_SWFRAC` below is
    `swatt[t=0, x=0, y=0, k]` and `-depth_iface[k]` of `mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc`
    (the 1D_ocean_ice_column grid; identical at every timestep and in the 11k_1D capture) for the 17
    interfaces at or above 200 m. Below 200 m MITgcm returns exactly 0 (swfrac.F:99-100); since 1DMIX-085 the
    port does too, asserted on the next five interfaces of the same column (`_MITGCM_SWFRAC_BELOW_200`, 207.16
    to 378.18 m; the bottom interface is left out because ini_forcing.F zeroes it whatever SWFRAC returns). A
    second, separate check evaluates swfrac.F lines 102-103 with the DATA coefficients in 50-digit decimal
    arithmetic (`decimal.Decimal.exp`).
(C) golden digests (the `output_digest` recipe of test_kpp_tracer_point_inputs.py), taken BEFORE the
    1DMIX-080 edit on the unmodified driver (git HEAD 9a5dd85): with shortwave penetration ON, an
    explicit `jerlov_water_type="IB"` still reproduces the former default's output bit for bit (only the
    default moved, the IB path is untouched) and the new default reproduces the pre-edit explicit-IA
    output; with shortwave penetration OFF (every scenario, `KPPAdapter`) swfrac is never called, so the
    water type cannot matter and the output is the pre-edit digest for every type. 1DMIX-085 moved the two
    shortwave-ON digests on purpose (`_SW_GOLDEN_085`, before/after): both columns are deeper than 200 m, and
    bldepth's Rib scan evaluates swfrac at every trial level (kpp_routines.F:508), so their `bulk_ri` changed
    at the levels below 200 m and nothing else did (asserted in (D)).
(D) 1DMIX-085, swfrac.F:97-105: `facz = fact*swdk`; `IF (facz .LT. -200.) swdk = 0` (lines 99-100), else the
    double exponential (lines 102-103). The port's `facz` is `-depth_m`, so the fraction is exactly 0 strictly
    below 200 m and unchanged at 200 m and above: asserted at the boundary (the doubles just above, at and just
    below 200 m) for every water type, plus three driver-level witnesses with penetrating shortwave: a column
    wholly above 200 m (digest unchanged, taken before the edit), the two (C) columns (only `bulk_ri` below
    200 m changes), and a convective column with `hbl` > 200 m, whose final `bfsfc` is exactly `bo + bosol`
    (absorbed fraction 1), as MITgcm's bldepth computes it (kpp_routines.F:839-849).
"""

import decimal
import hashlib
import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_core_driver import KPPDriver
from KPP.kpp_parameters import KPPParameters
import KPP.kpp_scheme_specific as kpp_scheme_specific
from KPP.kpp_shortwave import JERLOV_TABLE, swfrac
from test_kpp_tracer_point_inputs import OUTPUT_FIELDS, output_digest, _layered

# ---------------------------------------------------------------------------------------------------
# (A) the default is MITgcm's hard-coded type
# ---------------------------------------------------------------------------------------------------

# swfrac.F:71-76 (`DATA rfac / ... /`, `DATA a1 / ... /`, `DATA a2 / ... /`), jwtype 1..5 = I, IA, IB, II, III.
_SWFRAC_F_DATA = {
    "I": (0.58, 0.35, 23.0),
    "IA": (0.62, 0.6, 20.0),
    "IB": (0.67, 1.0, 17.0),
    "II": (0.77, 1.5, 14.0),
    "III": (0.78, 1.4, 7.9),
}


def test_default_water_type_is_mitgcm_hardcoded_IA():
    """swfrac.F:92/94 `jwtype=2` = type IA (swfrac.F:71-73)."""
    assert KPPParameters().jerlov_water_type == "IA"
    assert KPPParameters.from_yaml().jerlov_water_type == "IA"  # kpp_default_parameters.yaml
    assert inspect.signature(swfrac).parameters["water_type"].default == "IA"


def test_jerlov_table_equals_swfrac_f_data_statements():
    assert JERLOV_TABLE == _SWFRAC_F_DATA


def test_scenario_and_validation_entry_points_inherit_IA():
    """`run_scenarios.py` builds `KPPParameters.from_yaml(None)` and `KPPDriver()` builds `KPPParameters()`;
    the MITgcm replay never sets the type (no capture carries it)."""
    assert KPPDriver().params.jerlov_water_type == "IA"


# ---------------------------------------------------------------------------------------------------
# (B) swfrac(., "IA") is MITgcm's SWFRAC output
# ---------------------------------------------------------------------------------------------------

# (depth [m] = -depth_iface[k], MITgcm SWFrac3D = swatt[0, 0, 0, k]); see the module docstring.
_MITGCM_SWFRAC = (
    (0.0, 1.0),
    (10.0, 0.23048168651284154),
    (20.0, 0.13979418764515017),
    (30.0, 0.08478946085640333),
    (40.0, 0.051427407629912825),
    (50.0, 0.031192299477081544),
    (60.0, 0.018919085979788298),
    (70.0, 0.01147500570048103),
    (80.01, 0.006956463676177992),
    (90.04, 0.0042129842843746336),
    (100.15, 0.002541288542821164),
    (110.47, 0.0015169037529744283),
    (121.27, 0.000883973011065395),
    (133.03, 0.0004909913603948632),
    (146.45, 0.00025099337182278396),
    (162.48999999999998, 0.00011255325998478456),
    (182.30999999999997, 4.178036664509673e-05),
)


# The next five interfaces of the same column, below 200 m: MITgcm's SWFRAC returned exactly 0 there
# (swatt[0, 0, 0, k], k = 17..21). k = 22, the bottom, is omitted (ini_forcing.F zeroes it regardless).
_MITGCM_SWFRAC_BELOW_200 = (
    (207.15999999999997, 0.0),
    (238.25999999999996, 0.0),
    (276.67999999999995, 0.0),
    (323.17999999999995, 0.0),
    (378.17999999999995, 0.0),
)


def test_swfrac_IA_reproduces_mitgcm_swfrac_bit_for_bit():
    depth = np.array([d for d, _ in _MITGCM_SWFRAC])
    mit = np.array([v for _, v in _MITGCM_SWFRAC])
    np.testing.assert_array_equal(swfrac(depth, "IA"), mit)
    np.testing.assert_array_equal(swfrac(depth), mit)  # the default


def test_swfrac_IA_reproduces_mitgcm_exact_zero_below_200m():
    """1DMIX-085: MITgcm's SWFRAC output is exactly 0 at the five interfaces below 200 m; before the cut-off the
    port returned 1.21e-5 at 207.16 m (measured 2026-10-03)."""
    depth = np.array([d for d, _ in _MITGCM_SWFRAC_BELOW_200])
    mit = np.array([v for _, v in _MITGCM_SWFRAC_BELOW_200])
    np.testing.assert_array_equal(swfrac(depth, "IA"), mit)
    full = np.array([d for d, _ in _MITGCM_SWFRAC + _MITGCM_SWFRAC_BELOW_200])
    ref = np.array([v for _, v in _MITGCM_SWFRAC + _MITGCM_SWFRAC_BELOW_200])
    np.testing.assert_array_equal(swfrac(full), ref)  # one array straddling 200 m, default type


def test_former_default_IB_does_not_reproduce_mitgcm():
    """The reference discriminates: type IB misses MITgcm by up to 4.7e-2 (measured 2026-10-02,
    0.0472 at 10 m)."""
    depth = np.array([d for d, _ in _MITGCM_SWFRAC])
    mit = np.array([v for _, v in _MITGCM_SWFRAC])
    err = np.abs(swfrac(depth, "IB") - mit)
    assert err[0] == 0.0 and np.all(err[1:] > 0.0)
    assert 0.04 < err.max() < 0.05


def test_swfrac_IA_matches_50_digit_evaluation_of_swfrac_f():
    """swfrac.F:102-103, `rfac*exp(facz/a1) + (1-rfac)*exp(facz/a2)` with `facz = -depth` (the exact binary
    depth), evaluated in 50-digit decimal arithmetic from the DATA literals as written in swfrac.F:74-76.
    Agreement to 4 ulp relative; measured max 2.15 ulp (4.8e-16) on 2026-10-02, at the deep interfaces where
    the double-precision rounding of the exponent `facz/a2` (up to 9.1 in magnitude) dominates -- MITgcm's
    double-precision value carries the same rounding, which is why (B) above is exact equality."""
    ctx = decimal.Context(prec=50)
    rfac, a1, a2 = (decimal.Decimal(s) for s in ("0.62", "0.6", "20.0"))
    ulp = decimal.Decimal(2) ** -52
    for depth, _ in _MITGCM_SWFRAC:
        facz = -decimal.Decimal(depth)
        ref = ctx.plus(rfac * ctx.exp(ctx.divide(facz, a1)) + (1 - rfac) * ctx.exp(ctx.divide(facz, a2)))
        port = decimal.Decimal(swfrac(depth, "IA")[0])
        assert abs(port - ref) <= 4 * ulp * abs(ref), depth


# ---------------------------------------------------------------------------------------------------
# (C) golden digests taken before the edit
# ---------------------------------------------------------------------------------------------------

def _shortwave_columns():
    """Two deterministic columns with penetrating shortwave (pre-computed forcing, MITgcm's bosol > 0 for
    heating, magnitudes of the 11k_1D capture): an unstable column (net surface cooling) and a stable one
    (net heating). Only fixed numbers and np.random.default_rng(seed); no capture is read."""
    cols = {}
    rng = np.random.default_rng(80)
    depth, dz = _layered(30, 5.0, 1.1)
    cols["sw_unstable"] = dict(
        theta=np.linspace(6.0, 2.0, 30) + 0.01 * rng.standard_normal(30),
        salt=np.linspace(33.8, 34.8, 30), u_vel=np.linspace(0.08, 0.0, 30), v_vel=np.linspace(0.0, 0.03, 30),
        depth=depth, cell_thickness=dz, coriol=1.0e-4,
        ustar_forcing=3.0e-4, bo_forcing=-2.0e-8, bosol_forcing=5.0e-9)
    depth, dz = _layered(23, 10.0, 1.05)
    cols["sw_stable"] = dict(
        theta=np.linspace(-1.0, -1.7, 23), salt=np.linspace(32.5, 34.6, 23),
        u_vel=np.linspace(0.05, 0.0, 23), v_vel=np.zeros(23),
        depth=depth, cell_thickness=dz, coriol=1.4e-4,
        ustar_forcing=2.0e-3, bo_forcing=1.0e-9, bosol_forcing=4.0e-8)
    return cols


def _sw_params(**kw):
    return KPPParameters(shortwave_heating=True, select_penetrating_sw=1, **kw)


# Pre-edit digests (HEAD 9a5dd85, default type IB): 'IB' = default output = explicit "IB"; 'IA' = explicit "IA".
# Historical since 1DMIX-085: the current values are the 'after' entries of `_SW_GOLDEN_085`.
_SW_GOLDEN = {
    "sw_unstable": {"IB": "5d1815487149009856a8dad21309f155b632a36a8332adc1f6f7ea975e65c0d2",
                    "IA": "d4d314721e1fdc5ca8251c299f796bb61a5ca2abd9493613be0fa9f3a4abba05"},
    "sw_stable": {"IB": "eeb7d00131cc25626ed8070cfd38d7d9687e130499b99dffa757a420377d4248",
                  "IA": "7c77682dd959e3232d0eac83f2eca839aab2f0869f10e77cb336be488c07235e"},
}


# 1DMIX-085 (swfrac.F's 200 m cut-off) moved both: name -> type -> (digest before 1DMIX-085 = `_SW_GOLDEN`, after),
# measured 2026-10-03 at the 1DMIX-085 edit (HEAD 0437195 plus the edit). Both columns are deeper than 200 m and
# their trial-level `bulk_ri` below 200 m is the only output that changed (test_cutoff_changes_only_bulk_ri_below_200m).
_SW_GOLDEN_085 = {
    "sw_unstable": {"IB": (_SW_GOLDEN["sw_unstable"]["IB"],
                           "8ac365d04433f19195dc53cb2fbc02c795472ca48d3d662a35c4f6979056c80b"),
                    "IA": (_SW_GOLDEN["sw_unstable"]["IA"],
                           "980aef11556ad0b938ac03edd4632a5677165028decf83c1ad9f1476a289f3b8")},
    "sw_stable": {"IB": (_SW_GOLDEN["sw_stable"]["IB"],
                         "3f85017b649a01f57a0d00ce6b668ce0ed2ae6cc284ba46a59ed968ad5dba2ec"),
                  "IA": (_SW_GOLDEN["sw_stable"]["IA"],
                         "541196d4d547120f4297535af04577f73c1ea3be1bdf5739a1e58f9abdee8613")},
}


@pytest.mark.parametrize("name", sorted(_SW_GOLDEN))
def test_shortwave_on_explicit_IB_is_the_former_default_and_default_is_former_IA(name):
    """1DMIX-080 relation (explicit IB = former default, default = former explicit IA), now on the post-1DMIX-085
    digests: the cut-off moved both types' digests, and the relation between them is unchanged."""
    kwargs = _shortwave_columns()[name]
    golden = {wt: after for wt, (before, after) in _SW_GOLDEN_085[name].items()}
    assert {wt: before for wt, (before, after) in _SW_GOLDEN_085[name].items()} == _SW_GOLDEN[name]
    assert golden["IA"] != golden["IB"]  # the column does feel the water type
    assert golden["IA"] != _SW_GOLDEN[name]["IA"] and golden["IB"] != _SW_GOLDEN[name]["IB"]
    explicit_ib = output_digest(KPPDriver(_sw_params(jerlov_water_type="IB")).compute_mixing(**kwargs))
    default = output_digest(KPPDriver(_sw_params()).compute_mixing(**kwargs))
    explicit_ia = output_digest(KPPDriver(_sw_params(jerlov_water_type="IA")).compute_mixing(**kwargs))
    assert explicit_ib == golden["IB"]
    assert default == golden["IA"]
    assert explicit_ia == golden["IA"]


# Pre-edit digest of the shortwave-ON "sw_unstable" column with penetration switched OFF (default
# shortwave_heating=False, the scenario configuration): every water type must give it.
_SW_OFF_GOLDEN = "a86d477446e3c1a690d1c1c09fe85cb3ab6720d2b0d5caad7486f4ea7c4cfe65"


@pytest.mark.parametrize("water_type", sorted(JERLOV_TABLE))
def test_shortwave_off_output_does_not_depend_on_water_type(water_type):
    kwargs = _shortwave_columns()["sw_unstable"]
    out = KPPDriver(KPPParameters(jerlov_water_type=water_type)).compute_mixing(**kwargs)
    assert output_digest(out) == _SW_OFF_GOLDEN


# ---------------------------------------------------------------------------------------------------
# (D) 1DMIX-085: swfrac.F's 200 m cut-off
# ---------------------------------------------------------------------------------------------------

# swfrac.F:74-76 DATA literals exactly as written, for the 50-digit evaluation of lines 102-103.
_SWFRAC_F_DATA_LITERALS = {
    "I": ("0.58", "0.35", "23.0"),
    "IA": ("0.62", "0.6", "20.0"),
    "IB": ("0.67", "1.0", "17.0"),
    "II": ("0.77", "1.5", "14.0"),
    "III": ("0.78", "1.4", "7.9"),
}
_JUST_ABOVE_200 = float(np.nextafter(200.0, 0.0))     # 199.99999999999997 m: facz > -200
_AT_200 = 200.0                                       # facz = -200: `.LT.` is false
_JUST_BELOW_200 = float(np.nextafter(200.0, np.inf))  # 200.00000000000003 m: facz < -200


def _swfrac_f_lines_102_103(depth, water_type):
    """swfrac.F:102-103 in 50-digit decimal arithmetic, facz = -depth (the exact binary depth)."""
    ctx = decimal.Context(prec=50)
    rfac, a1, a2 = (decimal.Decimal(v) for v in _SWFRAC_F_DATA_LITERALS[water_type])
    facz = -decimal.Decimal(float(depth))
    return ctx.plus(rfac * ctx.exp(ctx.divide(facz, a1)) + (1 - rfac) * ctx.exp(ctx.divide(facz, a2)))


def test_swfrac_f_data_literals_are_the_table():
    assert {k: tuple(float(v) for v in vals) for k, vals in _SWFRAC_F_DATA_LITERALS.items()} == _SWFRAC_F_DATA


@pytest.mark.parametrize("water_type", sorted(JERLOV_TABLE))
def test_swfrac_cutoff_at_the_200m_boundary(water_type):
    """swfrac.F:99, `IF ( facz .LT. -200. _d 0 )` with `facz = -depth`: just above 200 m and at exactly 200 m the
    test is false and lines 102-103 apply (a positive fraction); one double below 200 m it is true and the fraction
    is exactly 0. The cut-off does not depend on the water type. Expected positive values: the 50-digit evaluation
    of lines 102-103, agreement 1e-14 relative (measured 2026-10-03: at most 5.0 ulp = 1.1e-15, type IB at 200 m,
    the double rounding of the exponent; IA 1.79 / 0.23 ulp)."""
    got = swfrac(np.array([_JUST_ABOVE_200, _AT_200, _JUST_BELOW_200]), water_type)
    assert got[2] == 0.0
    for depth, value in zip((_JUST_ABOVE_200, _AT_200), got[:2]):
        ref = _swfrac_f_lines_102_103(depth, water_type)
        assert value > 0.0
        assert abs(decimal.Decimal(float(value)) - ref) <= decimal.Decimal("1e-14") * ref, depth
    # scalar and array calls agree
    assert swfrac(_AT_200, water_type)[0] == got[1]
    assert swfrac(_JUST_BELOW_200, water_type)[0] == 0.0


def test_swfrac_IA_at_and_above_200m_is_unchanged_and_below_is_zero():
    """Type IA (MITgcm's): the values just above and at 200 m are bit for bit the pre-1DMIX-085 swfrac (measured
    before the edit, 2026-10-03: 1.7251973309744275e-05 and 1.7251973309744244e-05; the edit only adds the
    cut-off) and within 4 ulp of the 50-digit evaluation (the convention of (B); measured 1.79 and 0.23 ulp).
    Below 200 m: exactly 0 (before: 1.7251973309744214e-05 one double below 200 m, 6.3466463002933506e-06 at 220 m),
    also far below, where the exponentials underflow anyway."""
    assert swfrac(_JUST_ABOVE_200, "IA")[0] == 1.7251973309744275e-05
    assert swfrac(_AT_200, "IA")[0] == 1.7251973309744244e-05
    ulp = decimal.Decimal(2) ** -52
    for depth in (_JUST_ABOVE_200, _AT_200):
        ref = _swfrac_f_lines_102_103(depth, "IA")
        assert abs(decimal.Decimal(float(swfrac(depth, "IA")[0])) - ref) <= 4 * ulp * ref
    np.testing.assert_array_equal(swfrac(np.array([_JUST_BELOW_200, 220.0, 1000.0, 1.0e4]), "IA"), 0.0)


def _sw_shallow_column():
    """Penetrating shortwave, grid wholly above 200 m (deepest face 172.6 m), unstable forcing; hbl 4.61 m."""
    rng = np.random.default_rng(85)
    depth, dz = _layered(15, 8.0, 1.05)
    return dict(theta=np.linspace(8.0, 3.0, 15) + 0.01 * rng.standard_normal(15), salt=np.linspace(33.9, 34.7, 15),
                u_vel=np.linspace(0.06, 0.0, 15), v_vel=np.linspace(0.0, 0.02, 15), depth=depth, cell_thickness=dz,
                coriol=1.0e-4, ustar_forcing=5.0e-3, bo_forcing=-2.0e-8, bosol_forcing=5.0e-9)


def _sw_deep_column():
    """Penetrating shortwave, 30 cells of 20 m, well mixed to 300 m under strong surface cooling: hbl 304.69 m."""
    nz = 30
    dz = np.full(nz, 20.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    theta = np.where(-depth < 300.0, 4.0, 4.0 - 0.01 * (-depth - 300.0))
    return dict(theta=theta, salt=np.full(nz, 34.9), u_vel=np.linspace(0.05, 0.0, nz), v_vel=np.zeros(nz),
                depth=depth, cell_thickness=dz, coriol=1.2e-4, ustar_forcing=1.5e-2, bo_forcing=-1.0e-7,
                bosol_forcing=5.0e-9)


# Taken BEFORE the 1DMIX-085 edit (HEAD 0437195, devel-loop scratch `bob-1DMIX-085/digests_before.txt`), default IA.
_SW_SHALLOW_GOLDEN = "bd6cedf67b4fefd002cc66b934cbfb4dbce090fb439930d9f13007f589b0b50a"
# (before, after) the 1DMIX-085 edit, default IA.
_SW_DEEP_GOLDEN_085 = ("26d5e383099cd95cb25d348ed8698ed42f8bf2e40c97af147519a33636ffb7c1",
                       "6c1e6e91eed6f3abbd670332883777c2c0bad74082185b5be24089e30c1370d3")


def _swfrac_without_cutoff(depth_m, water_type="IA"):
    """The pre-1DMIX-085 `swfrac` body (kpp_shortwave.py before the edit), used only to show what the cut-off
    changes; it reproduces the pre-edit goldens `_SW_GOLDEN` (asserted below)."""
    r, d1, d2 = JERLOV_TABLE[water_type]
    z = np.atleast_1d(np.asarray(depth_m, dtype=float))
    return r * np.exp(-z / d1) + (1.0 - r) * np.exp(-z / d2)


def test_shortwave_column_above_200m_is_unchanged_by_the_cutoff():
    """No depth the column can reach exceeds 200 m, so the cut-off is never active: the pre-edit digest."""
    kw = _sw_shallow_column()
    assert float(np.max(-kw["depth"] + 0.5 * kw["cell_thickness"])) < 200.0
    assert output_digest(KPPDriver(_sw_params()).compute_mixing(**kw)) == _SW_SHALLOW_GOLDEN


def test_deep_boundary_layer_bfsfc_is_bo_plus_bosol():
    """`hbl` > 200 m: MITgcm's final SWFRAC call (kpp_routines.F:839, fact = -1 on hbl) returns exactly 0
    (swfrac.F:99-100), so `bfsfc = bo + bosol*(1. - 0.)` (kpp_routines.F:849) = `bo + bosol` exactly. Before the
    cut-off the port's bfsfc differed from that by -bosol*swfrac_IA(hbl) = -4.6e-16 here (measured 2026-10-03;
    the same mechanism as the 5.63e-14 global_oce_latlon difference)."""
    out = KPPDriver(_sw_params()).compute_mixing(**_sw_deep_column())
    assert float(out.hbl) > 200.0
    assert float(out.bfsfc) == float(out.bo) + float(out.bosol)
    before, after = _SW_DEEP_GOLDEN_085
    digest = output_digest(out)
    assert digest != before
    assert digest == after


@pytest.mark.parametrize("name", sorted(_SW_GOLDEN))
def test_cutoff_changes_only_bulk_ri_below_200m(name, monkeypatch):
    """The two (C) columns are deeper than 200 m with a shallow boundary layer (hbl 3.30 m / 5.0 m). bldepth's Rib
    scan evaluates swfrac at every trial level (kpp_routines.F:508; port kpp_scheme_specific.py, trial-level call),
    so the cut-off changes `bulk_ri` at trial levels below 200 m -- and nothing else, since `hbl` is set far
    above. Measured 2026-10-03: sw_unstable 11 of its 13 levels below 200 m change (max 2.8e-5), sw_stable 9 of 9
    (max 6.55e-5); every other output field bit-identical."""
    kw = _shortwave_columns()[name]
    new = KPPDriver(_sw_params()).compute_mixing(**kw)
    monkeypatch.setattr(kpp_scheme_specific, "swfrac", _swfrac_without_cutoff)
    old = KPPDriver(_sw_params()).compute_mixing(**kw)
    assert output_digest(old) == _SW_GOLDEN[name]["IA"]  # the stand-in is the pre-edit code on this column
    deep = -np.asarray(kw["depth"]) > 200.0
    for field in OUTPUT_FIELDS:
        a, b = getattr(old, field), getattr(new, field)
        if field != "bulk_ri":
            assert (a is None and b is None) or np.array_equal(np.asarray(a), np.asarray(b)), field
            continue
        changed = np.asarray(a) != np.asarray(b)
        assert changed.any()
        assert not np.any(changed & ~deep), "bulk_ri changed above 200 m"

