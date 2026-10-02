"""
Unit tests for the optional tracer-point inputs of `KPPDriver.compute_mixing` -- 1DMIX-071.

MITgcm forms KPP's `shsq` (kpp_calc.F:459-495), `dVsq` (kpp_forcing_surf.F:463-504) and,
through `SMOOTH_HORIZ`, the horizontally smoothed `dbloc` (kpp_calc.F:276-289,
kpp_routines.F:1311-1391) from the NEIGHBOURING columns (i+1, j+1, and for the smoothed
quantities i-1, j-1). A single-column driver cannot form them, so `compute_mixing` accepts
them as keyword-only optional inputs `shsq_forcing`, `dvsq_forcing`, `dbloc_smooth_forcing`
(default `None` = the column-local computation, an exact no-op), exactly like the
`ustar_forcing`/`bo_forcing`/`hbl_override` pattern. The replays
(`MITgcm_to_Python_port_verification/scripts/run_{kpp,ggl90}_from_netcdf_input.py`) supply them.

This module proves, for the driver alone (no MITgcm capture involved):

1. the no-op claim by golden digests: SHA-256 digests of every output field of five
   deterministic columns were taken from the driver BEFORE the three keywords were added
   (`GOLDEN_DIGESTS` below, taken on the unmodified 1DMIX-073-era driver); with all three
   keywords `None` the driver reproduces them bit for bit;
2. the plumbing claim: passing the driver's OWN column-local `shsq`/`dvsq`/`dbloc` as the
   keywords reproduces the `None`-path output bit for bit (so the keywords replace exactly the
   one value they name and nothing downstream changes);
3. each keyword really replaces its value (a doubled shear changes `shear_sq`/`dVsq`;
   `dbloc_smooth_forcing` changes the interior mixing but not `buoy_freq_sq`);
4. validation: wrong shape, non-finite and negative (`shsq`, `dvsq`) arrays raise `ValueError`.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from KPP.kpp_core_driver import KPPDriver
from KPP.kpp_parameters import KPPParameters

OUTPUT_FIELDS = ("visc_az", "diff_kz_s", "diff_kz_t", "ghat", "hbl", "bulk_ri", "bfsfc", "ustar",
                 "bo", "bosol", "shear_sq", "buoy_freq_sq", "dVsq", "Ritop")


def output_digest(out):
    """SHA-256 over the float64 bytes of every output field (None hashed as b'None')."""
    h = hashlib.sha256()
    for name in OUTPUT_FIELDS:
        val = getattr(out, name)
        h.update(name.encode())
        h.update(b"None" if val is None else np.asarray(val, dtype=np.float64).tobytes())
    return h.hexdigest()


def _layered(nz, dz0, growth):
    dz = dz0 * growth ** np.arange(nz)
    depth = -(np.cumsum(dz) - dz / 2.0)
    return depth, dz


def golden_cases():
    """Five deterministic columns -> {name: (driver, compute_mixing kwargs)}.

    Built only from fixed numbers and `np.random.default_rng(seed)`; no capture is read.
    """
    cases = {}
    # 1: smooth stratified column, uniform 10 m cells, raw-flux forcing (mode 2)
    dz = np.full(20, 10.0)
    depth = -(np.cumsum(dz) - dz / 2.0)
    cases["stratified_rawflux"] = (KPPDriver(KPPParameters()), dict(
        theta=np.linspace(20.0, 2.0, 20), salt=np.linspace(35.5, 34.7, 20),
        u_vel=np.linspace(0.05, 0.0, 20), v_vel=np.linspace(0.02, 0.0, 20),
        depth=depth, cell_thickness=dz,
        tau_x=0.05, tau_y=0.0, q_net=-300.0, q_sw=0.0, fw_flux=0.0, coriol=1.0e-4))
    # 2: stretched grid, random shear-rich profile, pre-computed forcing (mode 1)
    rng = np.random.default_rng(7)
    depth, dz = _layered(30, 5.0, 1.12)
    cases["shear_rich_precomputed"] = (KPPDriver(KPPParameters()), dict(
        theta=15.0 - 0.02 * np.arange(30) + 0.01 * rng.standard_normal(30),
        salt=35.0 + 0.005 * np.arange(30) + 0.002 * rng.standard_normal(30),
        u_vel=0.1 * rng.standard_normal(30), v_vel=0.1 * rng.standard_normal(30),
        depth=depth, cell_thickness=dz, coriol=1.0e-4,
        ustar_forcing=0.012, bo_forcing=-2.0e-8, bosol_forcing=-1.0e-9))
    # 3: convectively unstable column (warm below cold), surface cooling
    depth, dz = _layered(25, 8.0, 1.08)
    cases["convective"] = (KPPDriver(KPPParameters()), dict(
        theta=np.linspace(4.0, 12.0, 25), salt=np.full(25, 34.9),
        u_vel=np.full(25, 0.01), v_vel=np.zeros(25), depth=depth, cell_thickness=dz,
        coriol=1.2e-4, ustar_forcing=0.006, bo_forcing=3.0e-7, bosol_forcing=0.0))
    # 4: KPP_ESTIMATE_UREF branch (needs tau_x/tau_y/ustar)
    rng = np.random.default_rng(11)
    depth, dz = _layered(22, 4.0, 1.15)
    cases["estimate_uref"] = (KPPDriver(KPPParameters(estimate_uref=True)), dict(
        theta=np.linspace(12.0, 3.0, 22), salt=np.linspace(34.0, 34.9, 22),
        u_vel=np.linspace(0.2, 0.01, 22) + 0.01 * rng.standard_normal(22),
        v_vel=np.linspace(-0.05, 0.0, 22), depth=depth, cell_thickness=dz,
        tau_x=0.1 / 1030.0, tau_y=0.02 / 1030.0, coriol=1.0e-4,
        ustar_forcing=0.01, bo_forcing=-5.0e-9, bosol_forcing=0.0))
    # 5: salt-plume forcing
    depth, dz = _layered(18, 5.0, 1.1)
    cases["salt_plume"] = (KPPDriver(KPPParameters(use_salt_plume=True, allow_salt_plume=True)), dict(
        theta=np.linspace(-1.5, -1.7, 18), salt=np.linspace(33.0, 34.5, 18),
        u_vel=np.linspace(0.03, 0.0, 18), v_vel=np.linspace(0.0, 0.01, 18),
        depth=depth, cell_thickness=dz, coriol=1.3e-4,
        ustar_forcing=0.004, bo_forcing=1.0e-8, bosol_forcing=0.0,
        boplume_forcing=-4.0e-8, sp_depth_forcing=12.0))
    return cases


# SHA-256 digests of the five golden cases, taken from the driver BEFORE the 1DMIX-071 edit
# (git HEAD c6d8ffb source tree, the driver without the three keywords).
GOLDEN_DIGESTS = {
    "stratified_rawflux": "7c195064a6ac5c2fbd6af8a2eb4c55762eb833fb46085ed92ed3b6186853b0a9",
    "shear_rich_precomputed": "3afc7c06172928a4830342bff766fa3212aef38b7cb71a82193d35ecfefe9572",
    "convective": "70946d6da7e8b55885334531f9ead99b0e96122da574589c50b808d27535c20a",
    "estimate_uref": "88520bee03443d1268d636914503b536d6f2c4842926226f728acaa597ac33fc",
    "salt_plume": "bd2523f03846f5d2124aeddf6ba4a3da70aa5342349749830ae8e654e8494b01",
}


def test_golden_digests_unchanged_with_keywords_none():
    cases = golden_cases()
    assert set(GOLDEN_DIGESTS) == set(cases)
    for name, (driver, kwargs) in cases.items():
        assert output_digest(driver.compute_mixing(**kwargs)) == GOLDEN_DIGESTS[name], name


@pytest.mark.parametrize("name", sorted(GOLDEN_DIGESTS))
def test_driver_own_column_local_values_as_keywords_reproduce_none_path_bit_for_bit(name):
    """Plumbing: feeding back the driver's own `shear_sq`, `dVsq` and `buoy_freq_sq`
    (= the column-local shsq, dvsq and the unsmoothed dbloc) through the three keywords, singly and
    together, gives exactly the None-path output."""
    driver, kwargs = golden_cases()[name]
    base = driver.compute_mixing(**kwargs)
    ref = output_digest(base)
    assert ref == GOLDEN_DIGESTS[name]
    own = dict(shsq_forcing=base.shear_sq, dvsq_forcing=base.dVsq, dbloc_smooth_forcing=base.buoy_freq_sq)
    for combo in ({"shsq_forcing"}, {"dvsq_forcing"}, {"dbloc_smooth_forcing"},
                  {"shsq_forcing", "dvsq_forcing", "dbloc_smooth_forcing"}):
        out = driver.compute_mixing(**kwargs, **{k: own[k] for k in combo})
        assert output_digest(out) == ref, (name, sorted(combo))


def test_keywords_are_keyword_only():
    driver, kwargs = golden_cases()["stratified_rawflux"]
    import inspect
    sig = inspect.signature(driver.compute_mixing)
    for name in ("shsq_forcing", "dvsq_forcing", "dbloc_smooth_forcing"):
        assert sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters[name].default is None


def test_shsq_and_dvsq_forcing_replace_exactly_their_value():
    driver, kwargs = golden_cases()["shear_rich_precomputed"]
    base = driver.compute_mixing(**kwargs)
    out = driver.compute_mixing(**kwargs, shsq_forcing=2.0 * base.shear_sq, dvsq_forcing=3.0 * base.dVsq)
    np.testing.assert_array_equal(out.shear_sq, 2.0 * base.shear_sq)
    np.testing.assert_array_equal(out.dVsq, 3.0 * base.dVsq)
    np.testing.assert_array_equal(out.buoy_freq_sq, base.buoy_freq_sq)
    np.testing.assert_array_equal(out.Ritop, base.Ritop)


def test_dvsq_forcing_bypasses_reference_velocity_estimate():
    """With estimate_uref=True and no tau/ustar-compatible inputs the estimate would raise;
    an explicit dvsq_forcing must not call it at all."""
    driver, kwargs = golden_cases()["estimate_uref"]
    kw = {k: v for k, v in kwargs.items() if k not in ("tau_x", "tau_y")}
    with pytest.raises(ValueError, match="estimate_uref=True requires"):
        driver.compute_mixing(**kw)
    base = driver.compute_mixing(**kwargs)
    out = driver.compute_mixing(**kw, dvsq_forcing=base.dVsq)
    assert output_digest(out) == output_digest(base)


def test_dbloc_smooth_forcing_changes_interior_mixing_but_not_dbloc():
    driver, kwargs = golden_cases()["shear_rich_precomputed"]
    base = driver.compute_mixing(**kwargs)
    out = driver.compute_mixing(**kwargs, dbloc_smooth_forcing=0.25 * base.buoy_freq_sq)
    np.testing.assert_array_equal(out.buoy_freq_sq, base.buoy_freq_sq)
    assert not np.array_equal(out.visc_az, base.visc_az) or not np.array_equal(out.diff_kz_s, base.diff_kz_s)


@pytest.mark.parametrize("keyword", ["shsq_forcing", "dvsq_forcing", "dbloc_smooth_forcing"])
def test_wrong_shape_or_nonfinite_raises_value_error(keyword):
    driver, kwargs = golden_cases()["stratified_rawflux"]
    nz = len(kwargs["theta"])
    with pytest.raises(ValueError, match=keyword):
        driver.compute_mixing(**kwargs, **{keyword: np.ones(nz - 1)})
    with pytest.raises(ValueError, match=keyword):
        driver.compute_mixing(**kwargs, **{keyword: np.ones((nz, 1))})
    for bad in (np.nan, np.inf, -np.inf):
        arr = np.ones(nz)
        arr[3] = bad
        with pytest.raises(ValueError, match="finite"):
            driver.compute_mixing(**kwargs, **{keyword: arr})


@pytest.mark.parametrize("keyword", ["shsq_forcing", "dvsq_forcing"])
def test_negative_squared_quantity_raises_value_error(keyword):
    driver, kwargs = golden_cases()["stratified_rawflux"]
    arr = np.ones(len(kwargs["theta"]))
    arr[2] = -1e-12
    with pytest.raises(ValueError, match=">= 0"):
        driver.compute_mixing(**kwargs, **{keyword: arr})


def test_dbloc_smooth_forcing_may_be_negative():
    """dbloc is a buoyancy difference and can legitimately be negative (unstable)."""
    driver, kwargs = golden_cases()["convective"]
    base = driver.compute_mixing(**kwargs)
    assert np.any(base.buoy_freq_sq < 0.0)
    driver.compute_mixing(**kwargs, dbloc_smooth_forcing=base.buoy_freq_sq)


def test_inputs_are_not_mutated():
    driver, kwargs = golden_cases()["stratified_rawflux"]
    base = driver.compute_mixing(**kwargs)
    sh, dv, db = base.shear_sq.copy(), base.dVsq.copy(), base.buoy_freq_sq.copy()
    sh0, dv0, db0 = sh.copy(), dv.copy(), db.copy()
    out = driver.compute_mixing(**kwargs, shsq_forcing=sh, dvsq_forcing=dv, dbloc_smooth_forcing=db)
    out.shear_sq[:] = -1.0
    out.dVsq[:] = -1.0
    np.testing.assert_array_equal(sh, sh0)
    np.testing.assert_array_equal(dv, dv0)
    np.testing.assert_array_equal(db, db0)
