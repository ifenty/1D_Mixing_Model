"""
Tests for MITgcm's bottom/surface conventions in KPP's boundary-layer code and the new
`depth_below` / `cell_thickness_below` inputs of `KPPDriver.compute_mixing` -- 1DMIX-075.

Background (measured in 1DMIX-075, `devel-loop/loop_state/bob-1DMIX-075-evidence.md`): on the
`global_ocean_90x40x15` KPP capture 456 `visc_az` / 520 `diff_kz_s` cells differed from MITgcm by more
than 1% (367 / 345 of them at k=1 of the two-wet-level columns). Three MITgcm behaviours were missing:

1. the `kbl` scan (`kpp_routines.F:807` and `:818-824`): `kbl = kmtj` is both "none found" and a legitimate
   result, so when the first level below `hbl` is the bottom wet level (or `hbl` is deeper) the scan
   continues over the DRY levels below and ends at `kbl = kmtj+1` (when `kmtj < Nr`); for a full-depth
   column `kmtj = Nr` and "none found" is `Nr`. The driver reproduces this with the optional keyword-only
   `depth_below` / `cell_thickness_below` (the dry model levels; default None = full depth).
2. `IF (k.GE.kmtj(i)) diffus(i,k,md) = 0.0` (`kpp_routines.F:208`): the interior coefficients at and below
   the bottom wet interface are zero when `blmix` reads `diffus(kn)`, `diffus(kn+1)` (`:1534-1548`).
3. `diffus(i,0,*) = 0` (`kpp_routines.F:1224-1228`): `blmix` reads it as `diffus(kn-1)` when `kn = 1`;
   the port used to wrap to the BOTTOM entry (Python index -1).

Contents: (A) reduced single-column witnesses whose expected values are the MITgcm capture (the fixture
`data/kpp_075_witnesses.npz`, built by `MITgcm_to_Python_port_verification/scripts/make_kpp_075_witnesses.py`);
(B) golden digests, taken BEFORE the edit, for columns the change must not affect; (C) each behaviour in
isolation; (D) input validation.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_core_driver import KPPDriver
from KPP.kpp_parameters import KPPParameters
from KPP.kpp_scheme_specific import compute_bl_mixing, diagnose_bl_depth

from test_kpp_tracer_point_inputs import output_digest

_FIXTURE = Path(__file__).resolve().parent / "data" / "kpp_075_witnesses.npz"


# ---------------------------------------------------------------------------
# (A) witnesses with MITgcm expected values
# ---------------------------------------------------------------------------

def _witness(name):
    z = np.load(_FIXTURE)
    meta = json.loads(str(z["meta_json"]))[name]
    kw = {k.split("/")[2]: z[k] for k in z.files if k.startswith(name + "/in/")}
    exp = {k.split("/")[2]: z[k] for k in z.files if k.startswith(name + "/mit/")}
    return meta, kw, exp


def _run(meta, kw):
    return KPPDriver(KPPParameters(**meta["params"])).compute_mixing(**kw)


# name -> (tolerance on visc_az/diff_kz_s/diff_kz_t, ghat, hbl) taken from the MEASURED agreement
# (make_kpp_075_witnesses.py prints it): the three two-wet witnesses and the three-wet one agree with
# the MITgcm capture EXACTLY (0.0); 11k_1D t=70 to 3.0e-10 / 0 / 1.2e-5 m (its hbl differs by 1.2e-5 m).
_WITNESS_TOL = {
    "g90_t5_i72_j35": (1e-12, 1e-12, 1e-12),
    "g90_t0_i0_j34": (1e-12, 1e-12, 1e-12),
    "g90_t3_i30_j18": (1e-12, 1e-12, 1e-12),
    "g90_t0_i86_j36_three_wet": (1e-12, 1e-12, 1e-12),
    "k11_t70": (1e-9, 1e-12, 3e-5),
}
# Maximum |port - MITgcm| over visc_az/diff_kz_s/ghat of the same witness BEFORE 1DMIX-075 (git HEAD
# 336a85a, measured): the fix removes 4 to 9 orders of magnitude of it.
_WITNESS_PRE_075_MAX_ERR = {
    "g90_t5_i72_j35": 0.0521,       # MITgcm visc_az 0.0491172, port 0.0010462 (k=1 of two wet levels)
    "g90_t0_i0_j34": 10.22,         # port ghat 10.22, MITgcm exactly 0 (hidden by the >1% statistic)
    "g90_t3_i30_j18": 1.63e-3,      # MITgcm diff_kz_s 1.6615e-3, port 3e-5 (the background)
    "g90_t0_i86_j36_three_wet": 4.06,   # port ghat 4.06, MITgcm exactly 0
    "k11_t70": 2.5e-5,              # 11k_1D t=70: MITgcm visc_az 2.1219e-5, port 4.6325e-5 (diffus(0) wrap)
}


@pytest.mark.parametrize("name", sorted(_WITNESS_TOL))
def test_witness_matches_mitgcm_capture(name):
    meta, kw, exp = _witness(name)
    out = _run(meta, kw)
    tol_mix, tol_ghat, tol_hbl = _WITNESS_TOL[name]
    n = len(kw["depth"])
    for f in ("visc_az", "diff_kz_s", "diff_kz_t"):
        err = np.max(np.abs(getattr(out, f) - exp[f][:n]))
        assert err <= tol_mix, f"{name} {f}: max|port - MITgcm| = {err:.3g} > {tol_mix}"
    err = np.max(np.abs(out.ghat - exp["ghat"][:n]))
    assert err <= tol_ghat, f"{name} ghat: max|port - MITgcm| = {err:.3g} > {tol_ghat}"
    assert abs(out.hbl - float(exp["hbl"])) <= tol_hbl
    pre = _WITNESS_PRE_075_MAX_ERR[name]
    new = max(np.max(np.abs(getattr(out, f) - exp[f][:n])) for f in ("visc_az", "diff_kz_s", "ghat"))
    assert new < 1e-3 * pre, f"{name}: error {new:.3g} is not far below the pre-1DMIX-075 {pre:.3g}"


def test_two_wet_witness_needs_the_dry_levels():
    """t=5, i=72, j=35 of the global_ocean_90x40x15 capture: MITgcm visc_az[1] = 0.0491171855518 at the
    only interior interface of the two-wet-level column. Fed as a FULL-DEPTH two-level column (no
    `depth_below`) the same driver gives a different, MITgcm-incompatible answer: the dry levels carry
    information (kbl = kmtj+1 = 3, not 2). Asserts the dry-level input is what makes the difference."""
    meta, kw, exp = _witness("g90_t5_i72_j35")
    with_dry = _run(meta, kw)
    kw_full = {k: v for k, v in kw.items() if k not in ("depth_below", "cell_thickness_below")}
    full = _run(meta, kw_full)
    assert abs(with_dry.visc_az[1] - 0.0491171855518) < 1e-12
    assert abs(full.visc_az[1] - with_dry.visc_az[1]) > 1e-3


def test_empty_levels_below_equals_none():
    meta, kw, _ = _witness("k11_t70")
    a = _run(meta, kw)
    b = _run(meta, dict(kw, depth_below=np.zeros(0), cell_thickness_below=np.zeros(0)))
    assert output_digest(a) == output_digest(b)


# ---------------------------------------------------------------------------
# (B) golden digests: inputs the change must not affect
# ---------------------------------------------------------------------------
# Regime that must be bit-identical: a FULL-DEPTH column (no dry levels below) whose boundary-layer base lies
# in the interior, i.e. MITgcm's kn (0-based, kn = kbl-1 in case A, kbl in case B) satisfies
# 1 <= kn <= nz-3. There diffus(kn-1), diffus(kn), diffus(kn+1) are interior entries (none is the surface
# entry, none the zeroed bottom entry), kbl is not the bottom level and `enhance` acts at ki < nz-1, so
# none of the three corrected behaviours is reached and the arithmetic is operation-for-operation the
# pre-1DMIX-075 one. Digests (the `output_digest` recipe of test_kpp_tracer_point_inputs.py) were taken
# at git HEAD 336a85a BEFORE the edit. The five older goldens of test_kpp_tracer_point_inputs.py are
# re-asserted by that module; two of them (kn = 1) are in this regime, the other three (kn = 0) are in the
# item-3 regime and happen to be unchanged because the bottom entry does not exceed the surface entry there.

def _mixed_layer_case(K, ustar, bo):
    nz = 40
    dz = np.full(nz, 5.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    i = np.arange(nz)
    return dict(theta=np.where(i < K, 16.0, 16.0 - 0.3 * (i - K + 1)), salt=np.full(nz, 35.0),
                u_vel=np.where(i < K, 0.1, 0.0), v_vel=np.zeros(nz), depth=depth, cell_thickness=dz,
                coriol=1e-4, ustar_forcing=ustar, bo_forcing=bo, bosol_forcing=0.0)


def _stretched_random():
    from test_kpp_tracer_point_inputs import _layered
    rng = np.random.default_rng(23)
    depth, dz = _layered(35, 3.0, 1.1)
    return dict(theta=18.0 - 0.15 * np.arange(35) + 0.02 * rng.standard_normal(35),
                salt=35.0 + 0.004 * np.arange(35), u_vel=0.1 * rng.standard_normal(35),
                v_vel=0.1 * rng.standard_normal(35), depth=depth, cell_thickness=dz,
                coriol=1.0e-4, ustar_forcing=0.015, bo_forcing=-5.0e-8, bosol_forcing=-1.0e-9)


def _shear_driven():
    nz = 40
    dz = np.full(nz, 5.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    return dict(theta=np.linspace(15.0, 14.0, nz), salt=np.full(nz, 34.8), u_vel=np.linspace(0.3, 0.0, nz),
                v_vel=np.linspace(0.0, 0.1, nz), depth=depth, cell_thickness=dz, coriol=1.2e-4,
                ustar_forcing=0.02, bo_forcing=1.0e-9, bosol_forcing=0.0)


_INTERIOR_GOLDEN = {
    "mixed_layer_caseA_12": (lambda: _mixed_layer_case(12, 0.015, -3e-7),
                              "5a4a22bda1b61b6530ff9eaf8dd5e4afeb05c2776c6a9eea04a1c2ae04cbff13"),
    "mixed_layer_caseB_12": (lambda: _mixed_layer_case(12, 0.008, -3e-7),
                              "62f3c98f87100b866b7ad80e7d4b5cc365305a7bef7c2de135d5a4cbcc775f36"),
    "mixed_layer_caseA_18": (lambda: _mixed_layer_case(18, 0.015, -1e-8),
                              "39b00dc17790d97f3a8717c089210dd3c57c4fd037f91237848cd5971f142c69"),
    "mixed_layer_caseA_24": (lambda: _mixed_layer_case(24, 0.008, -1e-8),
                              "9138668c67370a483e7e01c339f61995d66e60c591d4233840b1dcd782ec4ee4"),
    "interior_stretched_random": (_stretched_random,
                                   "cb5b5000040ab4310466ba0439cdaac7784805d14829fad84f4d36374f070c08"),
    "interior_shear_driven": (_shear_driven,
                               "e96f508c1eb5c8999b473e598f41c6bc5a98e40280df3ec456f66555d1edc476"),
}


def _kn_zero_based(depth, dz, hbl):
    nz = len(depth)
    kbl = nz - 1
    for kl in range(1, nz):
        if kbl == nz - 1 and -depth[kl] > hbl:
            kbl = kl
    casea = (-depth[kbl] - 0.5 * dz[kbl] - hbl) > 0.0
    return (kbl - 1) if casea else kbl


@pytest.mark.parametrize("name", sorted(_INTERIOR_GOLDEN))
def test_interior_boundary_layer_columns_are_bit_identical_to_pre_075(name):
    build, digest = _INTERIOR_GOLDEN[name]
    kw = build()
    out = KPPDriver(KPPParameters()).compute_mixing(**kw)
    nz = len(kw["depth"])
    kn = _kn_zero_based(kw["depth"], kw["cell_thickness"], out.hbl)
    assert 1 <= kn <= nz - 3, f"{name}: kn={kn} is outside the regime this golden is meant to cover"
    assert output_digest(out) == digest


# ---------------------------------------------------------------------------
# (C) each behaviour in isolation
# ---------------------------------------------------------------------------
_CFG = KPPParameters()
_DRV = KPPDriver(_CFG)
_NZ = 10
_DZ = np.full(_NZ, 2.0)
_Z = -(np.cumsum(_DZ) - _DZ / 2.0)       # -1, -3, ..., -19


def _interior(last):
    d = np.full(_NZ, 1.2e-3)
    d[0] = 1.0e-3
    d[3] = 2.0e-3
    d[-1] = last
    return d


def _blmix(hbl, casea, kbl, last, **kw):
    d = _interior(last)
    return compute_bl_mixing(0.01, 1e-8, hbl, 1.0, casea, (d.copy(), 0.1 * d, 0.1 * d), kbl, _Z, _DZ,
                             _DRV.wmt, _DRV.wst, _CFG, **kw)


def test_item3_surface_entry_is_zero_not_the_wrapped_bottom_entry():
    """kn = 0 (hbl = 1.5 m in 2 m cells: kbl = 1, case A): kpp_routines.F:1534 reads diffus(i,kn-1,*) =
    diffus(i,0,*) = 0 (:1224-1228). The port used `diffus[kn-1] = diffus[-1]`, the BOTTOM entry. Here the
    only bottom-entry read is that wrap (kn+1 and kn+2 are interior), so the result must not depend on it.
    Pre-1DMIX-075 (HEAD 336a85a, measured): last=0.05 gave blmc_visc[0] = -0.00208369, last=1e-3 gave
    0.0014416; now both 0.0014416."""
    a = _blmix(1.5, 1.0, 1, 1.0e-3)
    b = _blmix(1.5, 1.0, 1, 5.0e-2)
    for x, y in zip(a[:4], b[:4]):
        np.testing.assert_array_equal(x, y)
    assert a[4] == b[4]
    assert abs(a[0][0] - 0.0014416) < 5e-8
    assert abs(b[0][0] - (-0.00208369)) > 1e-3        # the pre-1DMIX-075 value is gone


def test_item2_bottom_interior_entry_is_zeroed_before_blmix_reads_it():
    """kn = nz-2 (hbl = 17.5 m, case A, kbl = nz-1): kpp_routines.F:1535 reads diffus(i,kn+1,*) which is the
    bottom entry, zeroed by `IF (k.GE.kmtj(i)) diffus = 0` (:208). The result must not depend on the value
    the caller passes there. Pre-1DMIX-075 (measured): blmc_visc[0] = 0.00610758 (last=1e-3) and
    0.00609092 (last=0.05); now 0.0062142 for both."""
    a = _blmix(17.5, 1.0, 9, 1.0e-3)
    b = _blmix(17.5, 1.0, 9, 5.0e-2)
    for x, y in zip(a[:4], b[:4]):
        np.testing.assert_array_equal(x, y)
    assert abs(a[0][0] - 0.0062142) < 5e-8
    assert abs(a[0][0] - 0.00610758) > 1e-4


def _scan(hbl_override, **below):
    nz = _NZ
    zeros = np.zeros(nz)
    return diagnose_bl_depth(zeros, zeros, zeros, 0.01, 1e-8, 0.0, 1e-4, _Z, _DZ, _DRV.wmt, _DRV.wst, _CFG,
                             hbl_override=hbl_override, **below)


_DRY_Z = np.array([-21.0, -23.0, -25.0])
_DRY_DZ = np.full(3, 2.0)


def test_item1_kbl_scan_full_depth_none_found_is_the_bottom_level():
    """kpp_routines.F:807,818-824 with kmtj = Nr: no level deeper than hbl -> kbl stays kmtj = Nr
    (0-based nz-1); the pre-1DMIX-075 port returned nz."""
    assert _scan(100.0)[4] == _NZ - 1
    assert _scan(18.5)[4] == _NZ - 1            # first level below hbl IS the bottom level
    assert _scan(5.0)[4] == 3                    # interior: first -zgrid > 5 is level 3 (centre 7 m)


def test_item1_kbl_scan_continues_below_the_bottom_when_dry_levels_exist():
    """The aliasing: with dry levels (kmtj < Nr) a hbl whose first deeper level is the bottom wet level, or
    that is deeper than it, ends at the first dry level (kmtj+1; 0-based nz); a deeper hbl goes further."""
    below = dict(zgrid_below=_DRY_Z, hwide_below=_DRY_DZ)
    assert _scan(5.0, **below)[4] == 3                       # interior result unaffected by the dry levels
    assert _scan(18.5, **below)[4] == _NZ                    # bottom wet level found -> scan goes on -> first dry
    assert _scan(19.0, **below)[4] == _NZ                    # hbl = bottom centre: strict .GT. -> first dry
    assert _scan(22.0, **below)[4] == _NZ + 1                # dry centres 21, 23: first -zgrid > 22 is the 2nd dry level (index nz+1)
    assert _scan(100.0, **below)[4] == _NZ - 1               # deeper than every level: kbl stays kmtj


def test_item1_casea_uses_the_dry_level_grid():
    """kpp_routines.F:917-921: casea = 0.5 + sign(0.5, -zgrid(kbl) - 0.5*hwide(kbl) - hbl) at kbl = kmtj+1,
    i.e. 'is the bottom of the wet column deeper than hbl'."""
    below = dict(zgrid_below=_DRY_Z, hwide_below=_DRY_DZ)
    assert _scan(18.5, **below)[3] == 1.0          # 21 - 1 - 18.5 = 1.5 > 0 : case A
    assert _scan(20.5, **below)[3] == 0.0          # first deeper centre 21 (kbl = first dry): 21 - 1 - 20.5 < 0 : case B


def test_full_depth_bottomed_out_column_has_no_ghat_at_the_bottom_level():
    """Unstable forcing, hbl deepens to the whole column (MITgcm: kbl = Nr). KPPMIX's combine loop
    (`IF (k .LT. kbl(i))` ... `ELSE ghat(i,k) = 0`) leaves ghat(Nr) = 0 while ghat(Nr-1) is kept (the port
    returned the nonzero blmix value at Nr, because its 'none found' kbl was nz)."""
    nz = 6
    dz = np.full(nz, 5.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    out = KPPDriver(KPPParameters()).compute_mixing(
        theta=np.full(nz, 10.0), salt=np.full(nz, 35.0), u_vel=np.zeros(nz), v_vel=np.zeros(nz),
        depth=depth, cell_thickness=dz, coriol=1e-4, ustar_forcing=0.01, bo_forcing=-1e-6, bosol_forcing=0.0)
    assert out.hbl == pytest.approx(-depth[-1])
    assert out.ghat[-1] == 0.0
    assert out.ghat[-2] != 0.0


# ---------------------------------------------------------------------------
# (D) validation of the new inputs
# ---------------------------------------------------------------------------

def _good():
    meta, kw, _ = _witness("g90_t5_i72_j35")
    return meta, kw


@pytest.mark.parametrize("mutate,match", [
    (lambda kw: kw.pop("cell_thickness_below"), "given together"),
    (lambda kw: kw.pop("depth_below"), "given together"),
    (lambda kw: kw.update(depth_below=kw["depth_below"][:-1]), "same length"),
    (lambda kw: kw.update(depth_below=kw["depth_below"].reshape(1, -1), cell_thickness_below=kw["cell_thickness_below"].reshape(1, -1)), "1-D"),
    (lambda kw: kw.update(depth_below=np.where(np.arange(len(kw["depth_below"])) == 1, np.nan, kw["depth_below"])), "finite"),
    (lambda kw: kw.update(cell_thickness_below=np.where(np.arange(len(kw["depth_below"])) == 2, np.inf, kw["cell_thickness_below"])), "finite"),
    (lambda kw: kw.update(cell_thickness_below=np.where(np.arange(len(kw["depth_below"])) == 0, 0.0, kw["cell_thickness_below"])), "> 0"),
    (lambda kw: kw.update(cell_thickness_below=-kw["cell_thickness_below"]), "> 0"),
    (lambda kw: kw.update(depth_below=-kw["depth_below"]), "<= 0"),
    (lambda kw: kw.update(depth_below=kw["depth_below"][::-1].copy()), "deeper"),
    (lambda kw: kw.update(depth_below=np.concatenate([[kw["depth"][-1]], kw["depth_below"][1:]])), "deeper"),
    # combined column must pass the shared z-coordinate guard (extent <= 11,000 m)
    (lambda kw: kw.update(cell_thickness_below=np.full(len(kw["depth_below"]), 20000.0)), "z-coordinate"),
])
def test_levels_below_validation_raises_valueerror(mutate, match):
    meta, kw = _good()
    kw = dict(kw)
    mutate(kw)
    with pytest.raises(ValueError, match=match):
        _run(meta, kw)
