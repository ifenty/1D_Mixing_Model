"""
Test the Python GGL90 implementation against real MITgcm validation captures.

Written for 1DMIX-042: before this file existed, `MITgcm_to_Python_port_verification/
tests/` contained exactly one file (`test_kpp_mitgcm_validation.py`, KPP only) --
every real, hard-won GGL90 finding recorded in closed_issues.md had zero
regression protection. Mirrors that file's structure exactly (`_require`-based
skip-if-missing, module-scoped fixtures, tolerances from measured agreement,
not aspirational values) but drives GGL90's own replay entry point,
`scripts/run_ggl90_from_netcdf_input.py::run` (the GGL90 equivalent of
`run_kpp_from_netcdf_input.py::run_python_kpp_on_dataset`), against
already-captured NetCDF data for five experiments:

- vermix (single column, 20 timesteps, `mxlMaxFlag=3`)
- 1D_ocean_ice_column (single sea-ice-coupled column, 11,000 timesteps --
  the longest single-column GGL90 capture in this project)
- isomip (`ALLOW_SHELFICE`, 8-tile domain, 12 timesteps, 2401/4851 wet
  columns dry-top-then-wet-below under a floating ice shelf)
- global_ocean_90x40x15 (`ALLOW_GGL90_IDEMIX`, 36-tile domain, 10 timesteps
  -- a real, characterized missing-physics gap, not a port defect)
- global_ocean_cs32x15 (`usingPCoords`, 12-tile cubed-sphere domain, 10
  timesteps -- a real, permanently out-of-scope structural gap, 1DMIX-040)

Every tolerance below was measured fresh this round (2026-09-27) by running
the actual replay pipeline against the actual captures and the actual
current source tree -- see this issue's own closed-issue entry for the exact
commands and full per-field median/p95/max numbers. Where a prior closed
issue (1DMIX-015/016/024/025/038/039/040/048) already reports a number, the
fresh measurement here reproduces it; where 1DMIX-048's TKE-buoyancy-term fix
changed the ground truth (`vermix`/`1D_ocean_ice_column` `tke_after`), this
file locks in the current, post-fix numbers, not the stale pre-fix ones.
"""

import sys
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest
import xarray as xr

_VERIFICATION_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_VERIFICATION_ROOT / 'scripts'))
sys.path.insert(0, str(_VERIFICATION_ROOT.parent / 'Vertical_Mixing_Models'))

from run_ggl90_from_netcdf_input import run as run_python_ggl90_on_dataset  # noqa: E402

_INPUTS = _VERIFICATION_ROOT / 'GGL90_port_validation' / 'inputs_from_mitgcm'
_OUTPUTS = _VERIFICATION_ROOT / 'GGL90_port_validation' / 'outputs_from_mitgcm'

# vermix: newest of the 4 versioned captures (1dmix015_fix, 1dmix016_fix,
# 1dmix024 -- see this issue's own closed-issue entry for why 1dmix024 is the
# current one to use: it postdates both the dt fix (1DMIX-015) and the
# visc_az capture fix (1DMIX-016), and adds the ri_shear_pr/mxl instrumentation).
DATA_VERMIX = _INPUTS / 'mitgcm_ggl90_inputs_vermix_20_1dmix024.nc'
OUTPUTS_VERMIX = _OUTPUTS / 'mitgcm_ggl90_outputs_vermix_20_1dmix024.nc'

# 1D_ocean_ice_column: 11,000-timestep capture, regenerated/re-permanentized
# this issue from the raw MITgcm STDOUT Bob's 1DMIX-048 fix used for its own
# before/after check (previously only in /tmp, never given a permanent name).
DATA_1D = _INPUTS / 'mitgcm_ggl90_inputs_1D_ocean_ice_column_11000.nc'
OUTPUTS_1D = _OUTPUTS / 'mitgcm_ggl90_outputs_1D_ocean_ice_column_11000.nc'

# isomip: 12-timestep, 8-tile ALLOW_SHELFICE capture, likewise regenerated/
# re-permanentized this issue from 1DMIX-048's own /tmp evidence.
DATA_ISOMIP = _INPUTS / 'mitgcm_ggl90_inputs_isomip_12.nc'
OUTPUTS_ISOMIP = _OUTPUTS / 'mitgcm_ggl90_outputs_isomip_12.nc'

# global_ocean_90x40x15 / global_ocean_cs32x15: already-permanent IDEMIX
# captures (1DMIX-025), used as-is.
DATA_90X40X15 = _INPUTS / 'mitgcm_ggl90_inputs_global_ocean_90x40x15_idemix_10.nc'
OUTPUTS_90X40X15 = _OUTPUTS / 'mitgcm_ggl90_outputs_global_ocean_90x40x15_idemix_10.nc'

DATA_CS32X15 = _INPUTS / 'mitgcm_ggl90_inputs_global_ocean_cs32x15_idemix_10.nc'
OUTPUTS_CS32X15 = _OUTPUTS / 'mitgcm_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc'


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"Required MITgcm capture not found: {path}")


def _diff_and_rel(mitgcm: np.ndarray, python: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """abs diff and rel diff, excluding below-seafloor/above-ice-shelf NaN.

    Mirrors `scripts/compare_ggl90.py::summarize`'s own wet-mask convention
    (1DMIX-028/1DMIX-025): the Python replay marks a partially-wet column's
    excluded region (below the real seafloor, or above a real ice-shelf
    draft) as NaN rather than guessing MITgcm's own non-trivial fill there;
    those cells are genuinely not compared, not silently treated as a match.
    """
    wet = ~np.isnan(python)
    a = mitgcm[wet]
    b = python[wet]
    diff = np.abs(a - b)
    rel = diff / np.maximum(np.abs(a), 1e-12)
    return diff, rel


def _run_replay(inputs_nc: Path, tmp_path_factory, tag: str) -> xr.Dataset:
    out_dir = tmp_path_factory.mktemp(f'ggl90_{tag}')
    return run_python_ggl90_on_dataset(inputs_nc, out_dir / f'python_ggl90_outputs_{tag}.nc')


# ========================================================================
# vermix: single column, mxlMaxFlag=3 -- 1DMIX-015/016/024/048's own
# experiment. `tke_after` is now clean (0/520) post-1DMIX-048; it was 2/520
# (max_rel 4.9e-2) between 1DMIX-015 and 1DMIX-048, and 40/520 before that.
# ========================================================================

@pytest.fixture(scope='module')
def result_vermix(tmp_path_factory):
    _require(DATA_VERMIX)
    _require(OUTPUTS_VERMIX)
    python_ds = _run_replay(DATA_VERMIX, tmp_path_factory, 'vermix')
    mitgcm_ds = xr.open_dataset(OUTPUTS_VERMIX)
    return python_ds, mitgcm_ds


@pytest.mark.parametrize('field', ['visc_az', 'diff_kz', 'mixing_length', 'tke_after'])
def test_vermix_clean_bit_level(result_vermix, field):
    """All 4 fields hit this project's established bit-level bar (0
    mismatches >1% rel, same bar 1DMIX-024/1DMIX-030 use for the standalone
    driver). Measured fresh this round: max_rel 7.3e-4 (visc_az) to 3.1e-3
    (tke_after), 0/520 mismatches on every field.
    """
    python_ds, mitgcm_ds = result_vermix
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    assert (rel > 0.01).sum() == 0, f"vermix {field}: mismatches >1% rel regressed"
    assert np.max(rel) < 0.01, f"vermix {field}: max_rel {np.max(rel):.3e} regressed past the bit-level bar"


def test_vermix_tke_after_max_abs(result_vermix):
    """1DMIX-048 fix collapsed tke_after from 2/520 (max_rel 4.9e-2) to
    0/520 (max_rel 3.1e-3, max_abs 7.8e-7) -- lock in the post-fix number,
    not the stale pre-fix one.
    """
    python_ds, mitgcm_ds = result_vermix
    diff, _ = _diff_and_rel(mitgcm_ds['tke_after'].values, python_ds['tke_after'].values)
    assert np.max(diff) < 5e-6, f"vermix tke_after max_abs {np.max(diff):.3e} regressed"


# ========================================================================
# 1D_ocean_ice_column: single sea-ice-coupled column, 11,000 timesteps,
# mxlMaxFlag=3. Should be clean/exact post-1DMIX-048 (no IDEMIX, no
# ShelfIce, no pressure-coordinate confound). tke_after was 6622/253000
# mismatched (max_rel 56x) before 1DMIX-048's fix -- now 0/253000.
# ========================================================================

@pytest.fixture(scope='module')
def result_1d_ocean_ice_column(tmp_path_factory):
    _require(DATA_1D)
    _require(OUTPUTS_1D)
    python_ds = _run_replay(DATA_1D, tmp_path_factory, '1d_ocean_ice_column')
    mitgcm_ds = xr.open_dataset(OUTPUTS_1D)
    return python_ds, mitgcm_ds


@pytest.mark.parametrize('field,max_abs_bound', [
    ('visc_az', 1e-7),
    ('diff_kz', 1e-8),
    ('mixing_length', 1e-3),
    ('tke_after', 1e-12),
])
def test_1d_ocean_ice_column_clean(result_1d_ocean_ice_column, field, max_abs_bound):
    """Over all 253,000 wet column-timesteps. On the 17-digit (ES25.16)
    capture of 1DMIX-070 the residuals are roundoff: max_abs 3.3e-17 (visc_az)
    / 1.2e-17 (diff_kz) / 2.6e-13 (mixing_length) / 5.4e-20 (tke_after),
    max_rel 4e-15 / 4e-15 / 3.8e-15 / 1.2e-14. The same port replayed on the
    previous 16-digit (E25.16) capture of the same run gave max_abs
    8.3e-10 / 8.3e-11 / 2.6e-5 / 2.9e-15 (max_rel 3.8e-7 / 3.8e-7 / 3.8e-7 /
    1.0e-9; the 1DMIX-066-era figures 1.8e-9 / 1.8e-10 / 5.6e-5 / 6.6e-15 were
    the same quantity before the 1DMIX-068 N^2 order fix): those were print
    quantization of the captured T/S/sigma_r, not port error (see
    `devel-loop/loop_state/bob-1DMIX-070-evidence.md`). The bounds below were
    set from the 16-digit figures and are deliberately left UNCHANGED (never
    widened); they now have 3-8 orders of magnitude of headroom over the
    17-digit residuals and could be tightened in a follow-up. This is this
    project's cleanest GGL90 experiment -- no IDEMIX, no ShelfIce, no
    pressure-coordinate confound.
    """
    python_ds, mitgcm_ds = result_1d_ocean_ice_column
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    assert (rel > 0.01).sum() == 0, f"1D_ocean_ice_column {field}: mismatches >1% rel regressed"
    assert np.max(diff) < max_abs_bound, (
        f"1D_ocean_ice_column {field}: max_abs {np.max(diff):.3e} exceeds {max_abs_bound:.1e}"
    )


# ========================================================================
# isomip: ALLOW_SHELFICE, 8-tile domain, 12 timesteps. NOT clean and never
# claimed to be: diff_kz has the exact, root-caused kSrf background-floor
# mismatch (1DMIX-038); tke_after carries that plus the related-but-not-
# fully-traced kSrf+1/kSrf+2/y=50 residuals 1DMIX-048's review additionally
# found (logged there as "additional evidence", not reopened as a new
# issue). The diff_kz and tke_after bounds have headroom on the upper side
# and a nonzero floor on the lower side -- this locks in that a real, known,
# bounded mismatch stays present, rather than either silently tightening (a
# false clean pass) or silently loosening (papering over a regression).
# mixing_length is NOT a known gap: its former lower-bounded "kSrf+1"
# residual was 16-digit print quantization and is asserted clean to roundoff
# (1DMIX-070, see that test's docstring).
# ========================================================================

@pytest.fixture(scope='module')
def result_isomip(tmp_path_factory):
    _require(DATA_ISOMIP)
    _require(OUTPUTS_ISOMIP)
    python_ds = _run_replay(DATA_ISOMIP, tmp_path_factory, 'isomip')
    mitgcm_ds = xr.open_dataset(OUTPUTS_ISOMIP)
    return python_ds, mitgcm_ds


def test_isomip_visc_az_clean(result_isomip):
    """visc_az has no kSrf-boundary defect (only diff_kz's own final
    assignment order is affected, per 1DMIX-038) -- over 1,437,204 wet cells
    (362,796 excluded as above-ice-shelf/below-seafloor NaN), 0 mismatches
    >1% rel. max_abs is 9.5e-18 on the 17-digit capture (1DMIX-070) and was
    1.1e-10 for the same port on the 16-digit capture (2.4e-10 in the older
    1DMIX-038-era measurement): print quantization, not physics. The 1e-8
    bound is unchanged (never widened) and now has ~10 orders of headroom.
    """
    python_ds, mitgcm_ds = result_isomip
    diff, rel = _diff_and_rel(mitgcm_ds['visc_az'].values, python_ds['visc_az'].values)
    assert (rel > 0.01).sum() == 0, "isomip visc_az: mismatches >1% rel regressed"
    assert np.max(diff) < 1e-8, f"isomip visc_az max_abs {np.max(diff):.3e} regressed"


def test_isomip_diff_kz_ksrf_gap(result_isomip):
    """1DMIX-038's root-caused kSrf background-diffusivity-floor mismatch.
    REAL gap, unchanged at 17 digits (1DMIX-070): 1075/1,437,204 cells
    (0.075%) exceed 1% rel on the 17-digit capture, max_abs 2.905e-3 (1102
    cells, same max_abs, on the 16-digit capture: the 27 cells that differ
    had rel 1.7%-51% at 16 digits and <= 0.26% at 17, i.e. were print
    artifacts; the 1075 that remain are at k = first-wet+1 (1069, max_abs
    2.9e-3) and +2 (6, max_abs 1.3e-5)).
    Bounded both sides: >0.02% keeps this a real, known, nonzero gap (a
    silent drop to 0 would mean the kSrf convention changed without
    1DMIX-038 being reopened); <0.5% catches an unexplained worsening.
    """
    python_ds, mitgcm_ds = result_isomip
    diff, rel = _diff_and_rel(mitgcm_ds['diff_kz'].values, python_ds['diff_kz'].values)
    frac = float((rel > 0.01).mean())
    assert 0.0002 < frac < 0.005, f"isomip diff_kz kSrf-mismatch fraction {frac:.5f} outside the known 1DMIX-038 bound"
    assert np.max(diff) < 0.01, f"isomip diff_kz max_abs {np.max(diff):.3e} regressed"


def test_isomip_mixing_length_ksrf_plus_1(result_isomip):
    """isomip mixing_length is CLEAN to roundoff on the 17-digit capture
    (1DMIX-070). Through 1DMIX-069 this test asserted a *known gap*
    (`1e-4 < max_abs < 0.01`) for what 1DMIX-038 called the kSrf+1
    "N^2-precision-amplified" residual. That residual was print
    quantization of the E25.16 (16-digit) capture, not physics: the
    replayed T/S/sigma_r inputs carried ~1e-16 relative print error, which
    mixing_length ~ 1/sqrt(N^2) amplifies at near-neutral cells. Recapturing
    the identical run with ES25.16 (17 significant digits, exact for a
    double; `devel-loop/loop_state/bob-1DMIX-070-evidence.md` Unit 3/4) and
    replaying the same port gives max_abs 1.07e-13 (max_rel 3.8e-15,
    0 cells above 1%) versus 3.25e-4 for the same port on the 16-digit
    capture (4.3e-3 in the original 1DMIX-038 measurement, before the
    1DMIX-068 N^2 operation-order fix). The MITgcm fields themselves agree
    between the two captures to <= 5.9e-16 relative (pure print
    quantization), so no physics changed.

    The lower bound therefore certified an artifact and is removed; the
    upper bound is TIGHTENED (never widened) from 0.01 to 1e-11, ~90x above
    the measured 1.07e-13 (a margin that absorbs platform/BLAS roundoff
    without admitting any physical-size residual). The genuine isomip gaps
    (diff_kz kSrf floor, tke_after) are unchanged at 17 digits and keep
    their assertions below.
    """
    python_ds, mitgcm_ds = result_isomip
    diff, _ = _diff_and_rel(mitgcm_ds['mixing_length'].values, python_ds['mixing_length'].values)
    assert np.max(diff) < 1e-11, f"isomip mixing_length max_abs {np.max(diff):.3e} regressed (17-digit roundoff level is 1.07e-13)"


def test_isomip_tke_after_ksrf_region(result_isomip):
    """tke_after carries the kSrf mismatch plus the related kSrf+1/kSrf+2/
    y=50 residuals 1DMIX-048's review logged as additional evidence for
    1DMIX-038 (not reopened as a separate issue). REAL gap, identical at 16
    and 17 digits (1DMIX-070): 17934/1,437,204 cells (1.25%) exceed 1% rel,
    max_abs 9.081e-6 -- matches 1DMIX-048's own cited post-fix count
    exactly. At 17 digits they sit at first-wet+1 (9542 cells), +2 (6581),
    and 1811 deeper cells (the y=50 row), while mixing_length agrees to
    1e-13 at every one of those levels, so mixing_length is not their cause.
    """
    python_ds, mitgcm_ds = result_isomip
    diff, rel = _diff_and_rel(mitgcm_ds['tke_after'].values, python_ds['tke_after'].values)
    frac = float((rel > 0.01).mean())
    assert 0.005 < frac < 0.03, f"isomip tke_after mismatch fraction {frac:.5f} outside the known 1DMIX-038/048 bound"
    assert np.max(diff) < 5e-5, f"isomip tke_after max_abs {np.max(diff):.3e} regressed"


# ========================================================================
# global_ocean_90x40x15: ALLOW_GGL90_IDEMIX, 36-tile domain, 10 timesteps.
# The Python port has zero IDEMIX physics (1DMIX-025, dead `use_idemix`
# placeholder) -- diff_kz/tke_after carry the real, characterized,
# missing-physics gap (corr(deltaT*IDEMIX_gTKE, mismatch)=0.998, 1DMIX-025);
# visc_az/mixing_length are unaffected (IDEMIX only enters via
# TKEPrandtlNumber/the TKE budget, confirmed by the formulas in
# ggl90_calc.F). Asserting the known bounded gap, not a false clean pass.
# ========================================================================

@pytest.fixture(scope='module')
def result_90x40x15(tmp_path_factory):
    _require(DATA_90X40X15)
    _require(OUTPUTS_90X40X15)
    python_ds = _run_replay(DATA_90X40X15, tmp_path_factory, '90x40x15')
    mitgcm_ds = xr.open_dataset(OUTPUTS_90X40X15)
    return python_ds, mitgcm_ds


@pytest.mark.parametrize('field,max_abs_bound', [('visc_az', 10.0), ('mixing_length', 20.0)])
def test_global_ocean_90x40x15_idemix_unaffected_fields(result_90x40x15, field, max_abs_bound):
    """visc_az/mixing_length don't depend on IDEMIX_gTKE at all (only
    TKEPrandtlNumber/the TKE update do) -- measured fresh this round,
    183/206 of 485,840 cells (~0.04%) exceed 1% rel (a separate, small,
    already-noted 1DMIX-028-style tail, not IDEMIX), max_abs 5.6/15.5.
    """
    python_ds, mitgcm_ds = result_90x40x15
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    frac = float((rel > 0.01).mean())
    assert frac < 0.002, f"global_ocean_90x40x15 {field}: mismatch fraction {frac:.5f} regressed beyond the known small tail"
    assert np.max(diff) < max_abs_bound, f"global_ocean_90x40x15 {field} max_abs {np.max(diff):.3e} regressed"


@pytest.mark.parametrize('field,max_abs_bound', [('diff_kz', 5.0), ('tke_after', 700.0)])
def test_global_ocean_90x40x15_idemix_gap(result_90x40x15, field, max_abs_bound):
    """The real, characterized IDEMIX-missing-physics gap (1DMIX-025):
    diff_kz/tke_after depend on IDEMIX_gTKE via TKEPrandtlNumber/the TKE
    budget. Measured fresh this round: 50.9%/54.4% of 485,840 cells exceed
    1% rel (matching 1DMIX-025's own cited 51%/54%), max_abs 2.7/446.
    Bounded both sides -- a false-clean drop toward 0% would mean IDEMIX
    physics was silently added or the gap silently hidden; this is not a
    port defect and is not expected to close without implementing IDEMIX.
    """
    python_ds, mitgcm_ds = result_90x40x15
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    frac = float((rel > 0.01).mean())
    assert 0.3 < frac < 0.7, f"global_ocean_90x40x15 {field}: IDEMIX-gap fraction {frac:.4f} outside the known 1DMIX-025 bound"
    assert np.max(diff) < max_abs_bound, f"global_ocean_90x40x15 {field} max_abs {np.max(diff):.3e} regressed"


# ========================================================================
# global_ocean_cs32x15: usingPCoords, 12-tile cubed-sphere domain, 10
# timesteps. 1DMIX-040: pressure-coordinate support is PERMANENTLY out of
# scope for this project (Arch's explicit scope decision) -- this port has
# no coordFac-equivalent conversion anywhere, so grid geometry captured in
# Pa is fed through length-ceiling formulas that assume metres, producing
# errors up to ~4 orders of magnitude. Asserting the known large bound
# (not skipping) per this issue's own acceptance criterion that every
# capture get at least one locked-in numeric assertion -- a silent
# improvement here without a documented scope-decision reversal would be
# at least as suspicious as a regression.
# ========================================================================

@pytest.fixture(scope='module')
def result_cs32x15(tmp_path_factory):
    _require(DATA_CS32X15)
    _require(OUTPUTS_CS32X15)
    python_ds = _run_replay(DATA_CS32X15, tmp_path_factory, 'cs32x15')
    mitgcm_ds = xr.open_dataset(OUTPUTS_CS32X15)
    return python_ds, mitgcm_ds


@pytest.mark.parametrize('field,min_max_abs,max_max_abs', [
    ('visc_az', 90.0, 1e3),
    ('diff_kz', 1e8, 1e12),
    ('mixing_length', 1e6, 1e9),
    ('tke_after', 1e4, 1e9),
])
def test_global_ocean_cs32x15_pressure_coordinate_gap(result_cs32x15, field, min_max_abs, max_max_abs):
    """1DMIX-040's known, permanently-out-of-scope pressure-coordinate gap.
    Measured fresh this round over 813,820 wet cells: 62.5-64.8% exceed 1%
    rel on every field; max_abs 100 (visc_az, at its GGL90viscMax=100 cap)/
    2.0e9 (diff_kz)/1.4e7 (mixing_length, matching 1DMIX-040's own cited
    ~4-order-of-magnitude cell: 1277 m real vs. 14,493 km ported)/4.2e5
    (tke_after). Lower bound keeps this a real, known, large gap (a drop
    below it would mean the p-coordinate confound shrank, which -- absent a
    scope-decision reversal implementing coordFac support -- would itself
    need investigation, not silent acceptance); upper bound is a basic
    finite-value sanity check.
    """
    python_ds, mitgcm_ds = result_cs32x15
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    frac = float((rel > 0.01).mean())
    assert frac > 0.5, f"global_ocean_cs32x15 {field}: mismatch fraction {frac:.4f} below the known 1DMIX-040 bound"
    assert min_max_abs < np.max(diff) < max_max_abs, (
        f"global_ocean_cs32x15 {field} max_abs {np.max(diff):.3e} outside the known 1DMIX-040 bound "
        f"[{min_max_abs:.1e}, {max_max_abs:.1e}]"
    )
