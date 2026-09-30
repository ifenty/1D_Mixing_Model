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
- lab_sea (1DMIX-054: 20x16 single tile, 23 levels, sea ice, real land columns;
  the FIRST GGL90 capture of this KPP-native grid, a CONSTRUCTED all-defaults
  `data.ggl90`; a 999-timestep and a 4368-timestep/6-month run started from the
  same state as the existing KPP captures of these durations)

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

# lab_sea (1DMIX-054): GGL90 on the grid whose existing captures are all KPP.
DATA_LABSEA_999 = _INPUTS / 'mitgcm_ggl90_inputs_lab_sea_999.nc'
OUTPUTS_LABSEA_999 = _OUTPUTS / 'mitgcm_ggl90_outputs_lab_sea_999.nc'
DATA_LABSEA_6MO = _INPUTS / 'mitgcm_ggl90_inputs_lab_sea_6mo.nc'
OUTPUTS_LABSEA_6MO = _OUTPUTS / 'mitgcm_ggl90_outputs_lab_sea_6mo.nc'


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


def _run_replay(inputs_nc: Path, tmp_path_factory, tag: str, first_timestep=None,
                last_timestep=None) -> xr.Dataset:
    out_dir = tmp_path_factory.mktemp(f'ggl90_{tag}')
    return run_python_ggl90_on_dataset(inputs_nc, out_dir / f'python_ggl90_outputs_{tag}.nc',
                                       first_timestep=first_timestep, last_timestep=last_timestep)


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


# ========================================================================
# lab_sea + GGL90 (1DMIX-054): 20x16 single tile, 23 levels (10 m ... 500 m),
# real land columns, sea ice (SEAICE + EXF), GMRedi, useCDscheme, JMD95Z,
# deltaT=3600 s. The FIRST GGL90 capture of the grid whose existing captures
# are all KPP. The `data.ggl90` is CONSTRUCTED and contains NO non-default
# parameter (all MITgcm defaults: GGL90alpha=1, mxlMaxFlag=0,
# GGL90TKEmin=1e-11, ...): no tuning of this project's other GGL90 namelists
# can be derived from lab_sea's own geometry/forcing, so none was carried
# over (see lab_sea/ggl90_input_validation/README.md). The run restarts from
# the stock `pickup.0000000001` (as the existing KPP captures do) with a
# constructed `pickup_ggl90.0000000001` holding the cold-start TKE
# (GGL90TKEmin everywhere), because nIter0=1 makes GGL90 require its own
# pickup. Header: MITgcm's default GGL90_OPTIONS.h (no IDEMIX, no Langmuir,
# no GGL90_MISSING_HFAC_BUG). The 999-timestep capture is replayed in full
# (5,764,230 wet cells); the 6-month/4368-timestep capture is subsampled to
# its LAST 100 timesteps (the first 999 steps of both runs are the same
# trajectory and are already covered by the 999 capture).
#
# Bounds follow the conventions of this file: fields that are clean on
# comparable captures (1D_ocean_ice_column, isomip `visc_az`) are asserted
# clean with the same bounds (0 cells >1% rel; max_abs < 1e-7 `visc_az`,
# < 1e-3 `mixing_length`); `diff_kz` and `tke_after` are NOT clean on this
# multi-column capture and exceed the clean bounds, so they are asserted as
# labelled KNOWN GAPS (upper guards only, never by widening a clean bound) whose
# mechanism is a replay-input effect (1DMIX-071: the replay feeds column-local
# velocities where MITgcm averages (i,i+1),(j,j+1)), not a port gap.
# ========================================================================

@pytest.fixture(scope='module')
def result_lab_sea_999(tmp_path_factory):
    _require(DATA_LABSEA_999)
    _require(OUTPUTS_LABSEA_999)
    python_ds = _run_replay(DATA_LABSEA_999, tmp_path_factory, 'lab_sea_999')
    mitgcm_ds = xr.open_dataset(OUTPUTS_LABSEA_999).load()
    return python_ds, mitgcm_ds


def test_lab_sea_999_configuration(result_lab_sea_999):
    """Structural sanity of the new capture, measured fresh (1DMIX-054): 999
    timesteps on the 20x16x23 single tile with the constructed all-defaults
    GGL90 namelist (GGL90alpha=1, GGL90TKEmin=1e-11, mxlMaxFlag=0,
    GGL90viscMax=100), the stock lab_sea background mixing (viscAz=1.93e-5,
    diffKzS=1.46e-5), deltaT=3600 s and 5,764,230 wet cells.
    """
    python_ds, _mitgcm_ds = result_lab_sea_999
    inputs = xr.open_dataset(DATA_LABSEA_999)
    assert dict(inputs.sizes)['time'] == 999 and inputs.sizes['x'] == 20 and inputs.sizes['y'] == 16
    a = inputs.attrs
    assert (a['GGL90alpha'], a['GGL90TKEmin'], int(a['mxlMaxFlag']), a['GGL90viscMax']) == (1.0, 1.0e-11, 0, 100.0)
    assert (a['viscAz'], a['diffKzS'], a['deltaT']) == (1.93e-5, 1.46e-5, 3600.0)
    assert int((~np.isnan(python_ds['visc_az'].values)).sum()) == 5764230


@pytest.mark.parametrize('field,max_abs_bound', [('visc_az', 1e-7), ('mixing_length', 1e-3)])
def test_lab_sea_999_clean_fields(result_lab_sea_999, field, max_abs_bound):
    """`visc_az` and `mixing_length` are clean on this multi-column capture,
    measured fresh (1DMIX-054) over 5,764,230 wet cells: 0 cells above 1% rel,
    max_abs 1.29e-14 (`visc_az`, max_rel 4.0e-15) and 1.14e-11
    (`mixing_length`, max_rel 3.8e-15, values up to ~3,300 m) -- roundoff. The
    bounds are the `1D_ocean_ice_column` clean-capture bounds of this file
    (1e-7 / 1e-3), which are NOT tightened to the measurement. (Both fields
    depend on TKE and stratification only, not on the shear, see the gap
    tests below.)
    """
    python_ds, mitgcm_ds = result_lab_sea_999
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    assert (rel > 0.01).sum() == 0, f"lab_sea_999 {field}: mismatches >1% rel regressed"
    assert np.max(diff) < max_abs_bound, f"lab_sea_999 {field}: max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_999_diff_kz_known_gap(result_lab_sea_999):
    """KNOWN-GAP CHARACTERIZATION (1DMIX-054). Replay-input mechanism, not a port gap (1DMIX-071): with neighbour-averaged velocities
    (Richard's review measurement, 1DMIX-054 round 1, steps 500-509) `diff_kz` and `tke_after`
    mismatches above 1% go to 0 and max_abs to 3.4e-15 / 3.0e-19.

    Measured fresh over 5,764,230
    wet cells: 1,800 cells (0.031%) exceed 1% rel, max_abs 2.146 (max_rel 3.0),
    median/p95 0. This exceeds the clean-capture `diff_kz` bound of this file
    (1e-8, `1D_ocean_ice_column`) and is NOT clean like `visc_az`; it is not
    widened. Since `visc_az` and `mixing_length` agree to roundoff, the
    difference sits in the Prandtl number Pr = f(Ri), Ri = N^2/(shear^2 +
    GGL90eps): 1,150 of the 1,800 mismatch cells have MITgcm `ri_number` in
    (0,1) (Pr unsaturated; 1,490 cells overall lie in that range) and 1,718
    have shear < 1e-6 (near-neutral cells where Ri is set by a tiny N^2, the
    documented EOS-precision amplification, see CAPTURES.md G5, and where a
    shear that differs as in `test_lab_sea_999_shear_is_four_point_average`
    moves Ri directly); with neighbour-averaged velocities the mismatch goes to 0,
    i.e. it is entirely the shear (1DMIX-071), not an EOS effect.
    Upper guards only (the mismatch fraction is season dependent, so a lower
    guard would be fragile; 1DMIX-054 round 1): fraction < 0.005 (the `isomip`
    kSrf upper band) and max_abs < 5.0 (the `global_ocean_90x40x15` diff_kz
    bound, 2.3x the measured maximum).
    """
    python_ds, mitgcm_ds = result_lab_sea_999
    diff, rel = _diff_and_rel(mitgcm_ds['diff_kz'].values, python_ds['diff_kz'].values)
    frac = float((rel > 0.01).mean())
    assert frac < 0.005, f"lab_sea_999 diff_kz mismatch fraction {frac:.5f} exceeds the known band"
    assert np.max(diff) < 5.0, f"lab_sea_999 diff_kz max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_999_tke_after_known_gap(result_lab_sea_999):
    """KNOWN-GAP CHARACTERIZATION (1DMIX-054). Replay-input mechanism, not a port gap (1DMIX-071): with neighbour-averaged velocities
    (Richard's review measurement, 1DMIX-054 round 1, steps 500-509) `diff_kz` and `tke_after`
    mismatches above 1% go to 0 and max_abs to 3.4e-15 / 3.0e-19.

    Measured fresh over 5,764,230
    wet cells: 32,862 cells (0.570%) exceed 1% rel (max_rel 5.6e3), max_abs
    1.07e-3, median 0, p95 1.4e-8. The clean-capture bound of this file
    (`tke_after` < 1e-12, `1D_ocean_ice_column`) is not met and NOT widened.
    The mismatches sit in levels 1-4 (centres 15-65 m; per-level counts 8,676 /
    10,396 / 10,595 / 2,171 = 96.9% of them; none at the surface or below level
    8), are spread evenly over the 999 timesteps (per-decile 2,766-3,760) and
    91.9% of them have tke_before >= 1e-8, i.e. cells where shear production
    is not negligible. Mechanism (measured,
    `test_lab_sea_999_shear_is_four_point_average`): MITgcm's shear at a
    tracer point is built from the velocities at (i,i+1) and (j,j+1) while the
    replay feeds the port the column-local uVel(i,j), vVel(i,j) only, so the
    port's shear production differs (median 64% in the shear itself).
    Upper guards only (season dependent fraction; 1DMIX-054 round 1): fraction
    < 0.03 (the `isomip` tke_after upper band); max_abs < 3e-3 (2.8x the measured maximum; no existing
    max_abs bound of this file applies: 5e-5 isomip and 1e-12 clean are both
    exceeded, 700 for the IDEMIX capture is not informative).
    """
    python_ds, mitgcm_ds = result_lab_sea_999
    diff, rel = _diff_and_rel(mitgcm_ds['tke_after'].values, python_ds['tke_after'].values)
    frac = float((rel > 0.01).mean())
    assert frac < 0.03, f"lab_sea_999 tke_after mismatch fraction {frac:.5f} exceeds the known band"
    assert np.max(diff) < 3e-3, f"lab_sea_999 tke_after max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_999_shear_is_four_point_average():
    """Oracle-side mechanism check for the two known gaps above (no port
    involved; replay-input effect, 1DMIX-071, not a port gap). MITgcm's `verticalShear` at tracer point (i,j), level k is
    ((ubar(k-1)-ubar(k))^2 + (vbar(k-1)-vbar(k))^2)/drC^2 with
    ubar=(uVel(i)+uVel(i+1))/2 and vbar=(vVel(j)+vVel(j+1))/2 (ggl90_calc.F,
    calcMeanVertShear=.FALSE. branch). The capture holds every column's
    uVel(i,j)/vVel(i,j), so ubar/vbar can be rebuilt from the neighbouring
    columns of the same capture. Measured fresh on the first 300 timesteps
    (458,013 cells with shear > 1e-14, interior i<19, j<15): rebuilt vs
    MITgcm's captured `vertical_shear` median rel 1.25e-16, max 6.6e-16; the
    column-local shear the replay effectively uses is off by median rel 0.64
    (99% of cells differ by more than 1%). Asserted: the rebuilt value matches
    to 1e-12 and the column-local one does not (median rel > 0.1).
    """
    _require(DATA_LABSEA_999)
    _require(OUTPUTS_LABSEA_999)
    inputs = xr.open_dataset(DATA_LABSEA_999).isel(time=slice(0, 300)).load()
    outputs = xr.open_dataset(OUTPUTS_LABSEA_999).isel(time=slice(0, 300)).load()
    u = inputs['u_velocity'].values
    v = inputs['v_velocity'].values
    drc = np.abs(np.diff(inputs['depth'].values))
    ubar = 0.5 * (u[:, :-1, :, :] + u[:, 1:, :, :])[:, :, :-1, :]
    vbar = 0.5 * (v[:, :, :-1, :] + v[:, :, 1:, :])[:, :-1, :, :]
    rebuilt = ((ubar[..., :-1] - ubar[..., 1:]) ** 2 + (vbar[..., :-1] - vbar[..., 1:]) ** 2) / drc ** 2
    local = ((u[:, :-1, :-1, :-1] - u[:, :-1, :-1, 1:]) ** 2
             + (v[:, :-1, :-1, :-1] - v[:, :-1, :-1, 1:]) ** 2) / drc ** 2
    captured = outputs['vertical_shear'].values[:, :-1, :-1, 1:]
    theta = inputs['temperature'].values
    wet = (theta[:, :-1, :-1, 1:] != 0) & (theta[:, :-1, :-1, :-1] != 0)
    sel = wet & (captured > 1e-14)
    assert int(sel.sum()) > 100000
    rel_rebuilt = np.abs(captured - rebuilt)[sel] / captured[sel]
    rel_local = np.abs(captured - local)[sel] / captured[sel]
    assert float(np.max(rel_rebuilt)) < 1e-12, "four-point-averaged shear no longer reproduces the capture"
    assert float(np.median(rel_local)) > 0.1, "column-local shear now matches MITgcm's: the known gap has closed"


# ------------------------------------------------------------------------
# lab_sea + GGL90, 6-month / 4368-timestep capture (1DMIX-054). Its first 999
# timesteps are bitwise identical to the 999 capture above (measured: every
# input and output variable), so only a later window is replayed. Four 100-step
# windows were measured when this test was written (`diff_kz` / `tke_after`
# fraction above 1% rel): steps 1500-1599 0.131% / 0.971%; 2000-2099 0.248% /
# 1.126%; 3000-3099 0.057% / 0.902%; 4268-4367 0.0175% / 0.364% -- the
# mismatch fraction depends on the season (weakest in the late, quiet window,
# so only upper guards are used). Steps 2000-2099 (mid-run,
# ~ mid-March of the 182-day run) are used: the window with the largest
# measured fractions, a coverage choice, not a tolerance choice -- the bands
# are the same ones as for the 999 capture.
# ------------------------------------------------------------------------

_LABSEA_6MO_FIRST = 2000
_LABSEA_6MO_LAST = 2099


@pytest.fixture(scope='module')
def result_lab_sea_6mo(tmp_path_factory):
    _require(DATA_LABSEA_6MO)
    _require(OUTPUTS_LABSEA_6MO)
    python_ds = _run_replay(DATA_LABSEA_6MO, tmp_path_factory, 'lab_sea_6mo',
                            first_timestep=_LABSEA_6MO_FIRST, last_timestep=_LABSEA_6MO_LAST)
    mitgcm_ds = xr.open_dataset(OUTPUTS_LABSEA_6MO).isel(
        time=slice(_LABSEA_6MO_FIRST, _LABSEA_6MO_LAST + 1)).load()
    return python_ds, mitgcm_ds


@pytest.mark.parametrize('field,max_abs_bound', [('visc_az', 1e-7), ('mixing_length', 1e-3)])
def test_lab_sea_6mo_clean_fields(result_lab_sea_6mo, field, max_abs_bound):
    """Steps 2000-2099 (577,000 wet cells), measured fresh (1DMIX-054):
    `visc_az` max_abs 1.5e-14 and `mixing_length` 1.5e-11, 0 cells above 1%
    rel (max_rel 4.0e-15 / 3.8e-15) -- roundoff, same as the 999 capture; same
    bounds as `test_lab_sea_999_clean_fields`.
    """
    python_ds, mitgcm_ds = result_lab_sea_6mo
    diff, rel = _diff_and_rel(mitgcm_ds[field].values, python_ds[field].values)
    assert (rel > 0.01).sum() == 0, f"lab_sea_6mo {field}: mismatches >1% rel regressed"
    assert np.max(diff) < max_abs_bound, f"lab_sea_6mo {field}: max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_6mo_diff_kz_known_gap(result_lab_sea_6mo):
    """KNOWN-GAP CHARACTERIZATION (1DMIX-054), same replay-input mechanism
    (1DMIX-071, not a port gap) and upper guards as
    `test_lab_sea_999_diff_kz_known_gap`. Steps 2000-2099, measured fresh: 1,430 of
    577,000 cells (0.248%) exceed 1% rel, max_abs 1.562 (max_rel 4.0).
    """
    python_ds, mitgcm_ds = result_lab_sea_6mo
    diff, rel = _diff_and_rel(mitgcm_ds['diff_kz'].values, python_ds['diff_kz'].values)
    frac = float((rel > 0.01).mean())
    assert frac < 0.005, f"lab_sea_6mo diff_kz mismatch fraction {frac:.5f} exceeds the known band"
    assert np.max(diff) < 5.0, f"lab_sea_6mo diff_kz max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_6mo_tke_after_known_gap(result_lab_sea_6mo):
    """KNOWN-GAP CHARACTERIZATION (1DMIX-054), same replay-input mechanism
    (1DMIX-071, not a port gap) and upper guards as
    `test_lab_sea_999_tke_after_known_gap`. Steps 2000-2099, measured fresh:
    6,497 of 577,000 cells (1.126%) exceed 1% rel, max_abs 3.56e-5 (max_rel 5.5e3).
    """
    python_ds, mitgcm_ds = result_lab_sea_6mo
    diff, rel = _diff_and_rel(mitgcm_ds['tke_after'].values, python_ds['tke_after'].values)
    frac = float((rel > 0.01).mean())
    assert frac < 0.03, f"lab_sea_6mo tke_after mismatch fraction {frac:.5f} exceeds the known band"
    assert np.max(diff) < 3e-3, f"lab_sea_6mo tke_after max_abs {np.max(diff):.3e} regressed"


def test_lab_sea_6mo_first_999_steps_identical_to_999_capture():
    """Determinism/consistency of the two new captures (measured fresh,
    1DMIX-054): the first 999 timesteps of the 6-month run reproduce the 999
    capture bit for bit (every input and output variable, first 20 steps
    asserted here). A difference would mean one of the two files was
    regenerated with a different configuration.
    """
    _require(DATA_LABSEA_999)
    _require(DATA_LABSEA_6MO)
    _require(OUTPUTS_LABSEA_999)
    _require(OUTPUTS_LABSEA_6MO)
    n = 20
    a_in = xr.open_dataset(DATA_LABSEA_999).isel(time=slice(0, n))
    b_in = xr.open_dataset(DATA_LABSEA_6MO).isel(time=slice(0, n))
    a_out = xr.open_dataset(OUTPUTS_LABSEA_999).isel(time=slice(0, n))
    b_out = xr.open_dataset(OUTPUTS_LABSEA_6MO).isel(time=slice(0, n))
    for v in ('temperature', 'salinity', 'u_velocity', 'v_velocity', 'tke_before', 'sigma_r', 'u_star_sq'):
        assert np.array_equal(a_in[v].values, b_in[v].values), f"input {v} differs"
    for v in ('visc_az', 'diff_kz', 'mixing_length', 'tke_after', 'ri_number', 'vertical_shear'):
        assert np.array_equal(a_out[v].values, b_out[v].values), f"output {v} differs"
