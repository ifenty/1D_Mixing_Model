"""
1DMIX-080: the port's Jerlov water type is MITgcm's hard-coded type IA.

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
    interfaces at or above 200 m. Below 200 m MITgcm returns exactly 0 (swfrac.F:99-100), a cut-off the
    port does not have yet (open issue 1DMIX-085), so those interfaces are not used here. A second,
    separate check evaluates swfrac.F lines 102-103 with the DATA coefficients in 50-digit decimal
    arithmetic (`decimal.Decimal.exp`).
(C) golden digests (the `output_digest` recipe of test_kpp_tracer_point_inputs.py), taken BEFORE the
    1DMIX-080 edit on the unmodified driver (git HEAD 9a5dd85): with shortwave penetration ON, an
    explicit `jerlov_water_type="IB"` still reproduces the former default's output bit for bit (only the
    default moved, the IB path is untouched) and the new default reproduces the pre-edit explicit-IA
    output; with shortwave penetration OFF (every scenario, `KPPAdapter`) swfrac is never called, so the
    water type cannot matter and the output is the pre-edit digest for every type.
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
from KPP.kpp_shortwave import JERLOV_TABLE, swfrac
from test_kpp_tracer_point_inputs import output_digest, _layered

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


def test_swfrac_IA_reproduces_mitgcm_swfrac_bit_for_bit():
    depth = np.array([d for d, _ in _MITGCM_SWFRAC])
    mit = np.array([v for _, v in _MITGCM_SWFRAC])
    np.testing.assert_array_equal(swfrac(depth, "IA"), mit)
    np.testing.assert_array_equal(swfrac(depth), mit)  # the default


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
_SW_GOLDEN = {
    "sw_unstable": {"IB": "5d1815487149009856a8dad21309f155b632a36a8332adc1f6f7ea975e65c0d2",
                    "IA": "d4d314721e1fdc5ca8251c299f796bb61a5ca2abd9493613be0fa9f3a4abba05"},
    "sw_stable": {"IB": "eeb7d00131cc25626ed8070cfd38d7d9687e130499b99dffa757a420377d4248",
                  "IA": "7c77682dd959e3232d0eac83f2eca839aab2f0869f10e77cb336be488c07235e"},
}


@pytest.mark.parametrize("name", sorted(_SW_GOLDEN))
def test_shortwave_on_explicit_IB_is_the_former_default_and_default_is_former_IA(name):
    kwargs = _shortwave_columns()[name]
    golden = _SW_GOLDEN[name]
    assert golden["IA"] != golden["IB"]  # the column does feel the water type
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
