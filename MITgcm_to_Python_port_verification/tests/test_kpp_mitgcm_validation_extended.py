"""
Extend KPP MITgcm-comparison regression coverage to three already-captured,
already-"validated" experiments that had zero pytest protection before this
issue: the 11,000-timestep `1D_ocean_ice_column` run, the 6-month/4368-
timestep `lab_sea` run, and `seaice_obcs` (salt-plume physics, 1DMIX-034).
Written for 1DMIX-043 as a sibling module to `test_kpp_mitgcm_validation.py`
(the existing 2-experiment file) and mirrors `test_ggl90_mitgcm_validation.py`
(1DMIX-042)'s own structure: `_require`-based skip-if-missing, module-scoped
fixtures, tolerances measured fresh this round (2026-09-27) against the
actual replay pipeline and the actual current source tree -- not stale or
aspirational numbers copied from a closed-issue writeup.

**1DMIX-049 update (2026-09-27)**: `global_oce_latlon` -- once explicitly OUT
of scope here (no capture existed anywhere in this repo; the original one
was lost in a disk-space rescue) -- has now been regenerated via a real,
fresh Docker MITgcm rerun of the full, unmodified `nTimeSteps=720`
configuration (one full 360-day periodic-forcing cycle; confirmed this is
the correct current count, NOT the "8760" figure that actually belongs to
`lab_sea`'s own hourly-timestep full year -- see this issue's `open_issues.md`
addendum) and reparsed (`mitgcm_kpp_{inputs,outputs}_global_oce_latlon_720.nc`,
648 MB / 998 MB, from a fresh 13.8 GB `output.txt`). Confirmed by direct
inspection: 2,315 wet columns at every one of the 720 timesteps (bathymetry
is time-invariant, as expected), 1,666,800 total wet column-timesteps for
`hbl` -- an exact match to 1DMIX-027's own historically-cited sample size,
confirming this rebuild reproduces the same real configuration. `frac_truncated`
measures 0.0% (this experiment's `code_validation/kpp_calc.F`/`kpp_routines.F`
were already confirmed byte-identical to the canonical, post-1DMIX-035-fix
`kpp_mods/` copies -- not stale, unlike some other experiments' history).

A **full** 3600-column Python-port replay across all 720 timesteps is
deliberately NOT attempted here (that actually is the multi-hour stage;
1DMIX-049's own build+run+parse timing estimate confirmed the MITgcm side
is fast, but the Python replay's per-column-timestep cost, measured
directly on this exact capture at ~2.2 ms/column-timestep, would need
~1.5 hours serially for the complete 720x2315=1,666,800-column-timestep
sample). Instead, mirroring `lab_sea_6mo`'s own first-100-timestep
subsample tradeoff below, this experiment uses the first **5** (of 720)
timesteps at **full spatial resolution** (all 2,315 wet columns per
timestep, not a further column subset -- this experiment's real value is
its multi-tile spatial breadth, so timesteps were subsampled instead of
columns): 11,575 ocean column-timesteps, measured at 25.4 s replay time
(after a 3.9 s `.load()` preload, same fix `lab_sea_6mo` needed). See
`_GLOBAL_OCE_LATLON_N` and the test class below.

**1DMIX-050 update (2026-09-27, this round)**: the two captures below that
used to carry the pre-1DMIX-035 `OUTPUT_MIXING` truncation defect --
`mitgcm_kpp_outputs_11k_1D.nc` and `mitgcm_kpp_outputs_lab_sea_6mo.nc` --
have now been **refreshed by a real Docker MITgcm rebuild+rerun** using the
current, fixed `kpp_calc.F` (both experiments' own
`code_validation/kpp_calc.F`/`kpp_routines.F` confirmed, by direct diff, to
already be non-stale symlinks to the canonical `kpp_mods/` copy -- no
separate stale-mirror bug found this round, unlike `lab_sea`'s own prior
1DMIX-038/039 history). Measured fresh against the new captures: **0.0%**
truncated-column fraction for `1D_ocean_ice_column` (11,000/11,000 wet
timesteps clean) and for `lab_sea_6mo` (exact wet-column-timestep count
measured fresh below in each experiment's own
`..._capture_is_not_truncated` test/docstring, not restated here to avoid
two sources of truth), matching `seaice_obcs`'s own already-clean
precedent exactly. The two stale originals were backed up to
`/tmp/1dmix050_backup/` (kept, not deleted) before being overwritten with
the fresh rebuild's output. The tests in this file were correspondingly
**widened back to full, unfiltered coverage** (`_clean_mask`/`clean_mask_*`
fixtures removed from the mixing/`ghat` comparisons; retained only as the
oracle-side evidence for each experiment's own new
`..._capture_is_not_truncated` test, mirroring `seaice_obcs`'s existing
pattern exactly) and tolerances were **remeasured fresh against the new
captures**, not copied from the old clean-subset numbers, per this issue's
own explicit instruction not to guess.

Original (pre-refresh) finding, kept here for provenance since it explains
*why* a rebuild was needed and documents the defect this refresh eliminated
-- both captures **used to** show 1DMIX-035's `OUTPUT_MIXING`
early-truncation defect (`visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat` zero-filled
at every real interior level for the affected timesteps, despite each
capture's own nonzero background-viscosity floor making that physically
impossible -- MITgcm's `Ri_iwmix` adds it unconditionally, 1DMIX-035's own
root cause): `1D_ocean_ice_column` (11k, file dated 2026-08-19, predating
the 2026-09-20 fix) showed 51.809% of all 11,000 timesteps affected; `lab_sea`
(6mo, file dated 2026-09-18) showed a real, subsample-dependent ~4.1%-48.9%
affected fraction. `seaice_obcs_1dmix034` (generated 2026-09-26, already
after the fix) was already confirmed clean and needed no refresh.

Given this, the tests below:
- Always test `hbl` (unaffected by the truncation defect even before this
  refresh: `OUTPUT_HBL` is a separate, always-unconditional write path --
  confirmed by 1DMIX-033's own closeout, "every previously-written
  OUTPUT_MIXING/OUTPUT_HBL/OUTPUT_TRUNCATED line stayed byte-identical").
- Test the mixing-coefficient (`visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat`)
  fields over the FULL sample for all three experiments -- no clean-subset
  filtering needed anywhere now, since all three captures are confirmed
  clean.
- For every experiment, lock in the measured truncated fraction as a
  bounded (`< 0.02`, matching `seaice_obcs`'s own established bound) "still
  clean" assertion, so a future capture swap that silently reintroduces the
  defect (or a fresh, not-yet-fixed capture for some other experiment) is
  caught rather than passing unnoticed.

`seaice_obcs_1dmix034`'s own capture has raw-flux forcing-validation columns
(1DMIX-013/1DMIX-022): running it prints known, expected, non-fatal
"`_compute_surface_forcing` does not match MITgcm's ... (see 1DMIX-022)"
warnings for many columns -- pre-existing, already-characterized behavior,
not something this issue touches; the mixing computation itself correctly
falls back to MITgcm's captured `ustar`/`bo`/`bosol`, which is what every
assertion below actually exercises.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

_VERIFICATION_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_VERIFICATION_ROOT / 'scripts'))
sys.path.insert(0, str(_VERIFICATION_ROOT.parent / 'Vertical_Mixing_Models'))

from run_kpp_from_netcdf_input import run_python_kpp_on_dataset  # noqa: E402

_INPUTS = _VERIFICATION_ROOT / 'KPP_port_validation' / 'inputs_from_mitgcm'
_OUTPUTS = _VERIFICATION_ROOT / 'KPP_port_validation' / 'outputs_from_mitgcm'

DATA_11K = _INPUTS / 'mitgcm_kpp_inputs_11k_1D.nc'
OUTPUTS_11K = _OUTPUTS / 'mitgcm_kpp_outputs_11k_1D.nc'

DATA_LABSEA_6MO = _INPUTS / 'mitgcm_kpp_inputs_lab_sea_6mo.nc'
OUTPUTS_LABSEA_6MO = _OUTPUTS / 'mitgcm_kpp_outputs_lab_sea_6mo.nc'

DATA_SEAICE_OBCS = _INPUTS / 'mitgcm_kpp_inputs_seaice_obcs_1dmix034.nc'
OUTPUTS_SEAICE_OBCS = _OUTPUTS / 'mitgcm_kpp_outputs_seaice_obcs_1dmix034.nc'

DATA_GLOBAL_OCE_LATLON = _INPUTS / 'mitgcm_kpp_inputs_global_oce_latlon_720.nc'
OUTPUTS_GLOBAL_OCE_LATLON = _OUTPUTS / 'mitgcm_kpp_outputs_global_oce_latlon_720.nc'

# lab_sea_6mo is a 222 MB NetCDF file whose on-disk chunking (chunksizes
# (2184, 7, 6, 8) -- half the time axis per chunk) makes
# `run_python_kpp_on_dataset`'s per-column `.isel(...).values` access
# pattern (the project's own established, unmodified replay entry point --
# not something this issue's scope touches) re-decompress a full chunk for
# nearly every individual (t, i, j) read against a lazy xarray/netCDF4-
# backed Dataset: measured at ~32 s/timestep x 320 columns, i.e. infeasible
# for a repeatable regression test. `.load()`-ing the small subsample into
# an in-memory, numpy-backed Dataset FIRST (this test's own preprocessing)
# collapsed that to ~0.28 s/timestep in direct measurement -- a >100x
# speedup with byte-identical results (same driver call, same data, just no
# longer re-decompressing per column).
_LABSEA_6MO_N = 100

# global_oce_latlon (1DMIX-049): 90x40x15, 4-tile, 2,315 wet columns at EVERY
# timestep (time-invariant bathymetry, confirmed by direct inspection). A full
# 720x2315=1,666,800-column-timestep replay is the real "hours" stage this
# issue's own build+run+parse timing already showed the MITgcm side is NOT --
# measured directly on this exact capture at ~2.2 ms/column-timestep, the full
# sample would take ~1.5 h serially. Subsampled to the first 5 (of 720)
# timesteps at FULL spatial resolution (all wet columns, no column subset --
# this experiment's distinguishing feature is its multi-tile spatial breadth,
# so timesteps were traded off instead of columns), matching `_LABSEA_6MO_N`'s
# own timestep-subsampling tradeoff rather than reinventing a different one:
# 11,575 ocean column-timesteps, measured at 25.4 s replay (+3.9 s `.load()`
# preload, same fix `lab_sea_6mo` needed for its own chunked on-disk layout).
_GLOBAL_OCE_LATLON_N = 5


def _require(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"Required MITgcm capture not found: {path}")


def _ocean_mask(theta: np.ndarray, salt: np.ndarray) -> np.ndarray:
    """True for a real ocean column.

    Mirrors `run_kpp_from_netcdf_input.py::_is_land_column`'s own land
    convention (1DMIX-011): a land column is exact 0.0 at every level for
    both theta and salt simultaneously, not NaN, for every capture used in
    this file.
    """
    is_land = np.all(theta == 0.0, axis=-1) & np.all(salt == 0.0, axis=-1)
    return ~is_land


def _clean_mask(mit_visc_az: np.ndarray, ocean: np.ndarray) -> np.ndarray:
    """True for a column-timestep NOT affected by the confirmed 1DMIX-035
    `OUTPUT_MIXING` early-truncation defect (see module docstring).

    A real wet interior interface level can never read exactly 0.0 for
    `visc_az` (MITgcm's own `Ri_iwmix` adds this capture's nonzero
    background floor unconditionally there) -- so a column-timestep whose
    entire interior (excluding the structurally-always-zero surface
    interface, index 0) reads exactly 0.0 is, by this project's own
    established diagnosis (1DMIX-035), truncated capture data, not real
    physics. Restricting to `ocean & ~all_zero_interior` isolates the
    genuinely trustworthy subset without needing a full capture
    regeneration.
    """
    interior = mit_visc_az[..., 1:]
    all_zero_interior = np.all(interior == 0.0, axis=-1)
    return ocean & (~all_zero_interior)


def _mixing_diff_rel(mit_field: np.ndarray, py_field: np.ndarray, mask: np.ndarray,
                      skip_surface: bool):
    """abs/rel diff for a mixing-coefficient field, restricted to `mask`
    column-timesteps.

    `skip_surface=True` additionally excludes the structurally-always-zero
    surface interface (index 0) for the three `z_iface`-located fields
    (`visc_az`/`diff_kz_s`/`diff_kz_t`) -- not applicable to `ghat`, which is
    `z`-located (cell center) and has no such convention (confirmed by
    direct inspection: real, comparable, sometimes-large nonzero values
    occur at its own index 0). Mirrors the `active = mitgcm > 1e-6`
    convention already established by this directory's own
    `test_kpp_mitgcm_validation.py`.
    """
    a = mit_field[mask]
    b = py_field[mask]
    if skip_surface:
        a = a[..., 1:]
        b = b[..., 1:]
    active = a > 1e-6
    diff = np.abs(b[active] - a[active])
    rel = diff / a[active]
    return diff, rel


# ========================================================================
# 1D_ocean_ice_column, 11,000-timestep capture: single column, no land,
# full-depth every level. Confirmed carrying the 1DMIX-035 OUTPUT_MIXING
# truncation defect at 51.8% of timesteps (see module docstring).
# ========================================================================

@pytest.fixture(scope='module')
def result_11k():
    _require(DATA_11K)
    _require(OUTPUTS_11K)
    inputs_ds = xr.open_dataset(DATA_11K)
    python_ds = run_python_kpp_on_dataset(inputs_ds, verbose=False)
    mitgcm_ds = xr.open_dataset(OUTPUTS_11K)
    return inputs_ds, python_ds, mitgcm_ds


@pytest.fixture(scope='module')
def ocean_mask_11k(result_11k):
    """1D_ocean_ice_column has no land (single always-wet column), but this
    fixture is kept for structural symmetry with the other two experiments'
    `ocean_mask_*` fixtures and to feed `_mixing_diff_rel` the same shape
    `_clean_mask` expects.
    """
    inputs_ds, _python_ds, _mitgcm_ds = result_11k
    theta = inputs_ds['temperature'].values[:, 0, 0, :]
    salt = inputs_ds['salinity'].values[:, 0, 0, :]
    return _ocean_mask(theta, salt)


def test_11k_ocean_ice_column_capture_is_not_truncated(result_11k, ocean_mask_11k):
    """Confirms this capture (rebuilt+rerun fresh under 1DMIX-050, replacing
    the stale 2026-08-19 capture that carried 1DMIX-035's OUTPUT_MIXING
    truncation defect at 51.809% of timesteps) is now clean -- measured
    fresh this round: 0.0% of all 11,000 real (always-wet) timesteps show
    the all-zero-interior truncation signature, matching `seaice_obcs`'s own
    already-clean precedent and confirming the refresh worked.
    """
    _inputs_ds, _python_ds, mitgcm_ds = result_11k
    clean = _clean_mask(mitgcm_ds['visc_az'].values[:, 0, 0, :], ocean_mask_11k)
    frac_truncated = 1.0 - (float(clean.sum()) / float(ocean_mask_11k.sum()))
    assert frac_truncated < 0.02, (
        f"11k_1D truncated-column fraction {frac_truncated:.4f} regressed from "
        "the confirmed-clean 0.0% this 1DMIX-050 refresh established -- this "
        "capture should stay clean unless replaced with a stale one again."
    )


def test_11k_ocean_ice_column_hbl(result_11k):
    """`hbl` was always tested over the full, untruncated 11,000 timesteps
    (unaffected by the OUTPUT_MIXING truncation defect even before this
    issue's capture refresh -- `OUTPUT_HBL` is a separate, always-
    unconditional write path). Remeasured fresh this round against the
    1DMIX-050-refreshed capture (values unchanged from before the refresh,
    as expected since `hbl` was never affected by the defect): median
    2.85e-5 m, max 20.28 m, 0.09% of timesteps exceed 5 m -- the same
    Rib/Ricr threshold-sensitivity tail characterized for lab_sea in
    1DMIX-019, confirmed at this scale for the single-column case too.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_11k
    diff = np.abs(python_ds['hbl'].values[:, 0, 0] - mitgcm_ds['hbl'].values[:, 0, 0])
    median = float(np.median(diff))
    frac_gt5m = float(np.mean(diff > 5.0))
    max_diff = float(np.max(diff))
    assert median < 0.001, f"11k hbl median diff {median:.4g} m regressed"
    assert frac_gt5m < 0.01, f"11k hbl fraction >5m diff {frac_gt5m:.4%} regressed"
    assert max_diff < 30.0, f"11k hbl max diff {max_diff:.4g} m regressed"


@pytest.mark.parametrize('field,median_bound,max_abs_bound,frac_gt1pct_bound', [
    ('visc_az', 1e-5, 0.015, 0.005),
    ('diff_kz_s', 1e-5, 0.03, 0.03),
    ('diff_kz_t', 1e-5, 0.03, 0.03),
])
def test_11k_ocean_ice_column_mixing(result_11k, ocean_mask_11k, field,
                                      median_bound, max_abs_bound,
                                      frac_gt1pct_bound):
    """Mixing-coefficient agreement over the FULL, now-clean 11,000-timestep
    sample (1DMIX-050 refresh -- no clean-subset filtering needed anymore).
    Measured fresh this round: `visc_az` median_abs 0 (exact), max_abs
    7.60e-3, 0.087% of active cells exceed 1% rel (n=242,000); `diff_kz_s`/
    `diff_kz_t` (identical values in this configuration) median_abs 2.38e-7,
    max_abs 1.73e-2, 1.19% exceed 1% rel (n=19,603) -- tighter bounds than
    the pre-refresh clean-subset numbers, as expected now that corrupted-
    zero comparisons are gone from the sample entirely.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_11k
    mit = mitgcm_ds[field].values[:, 0, 0, :]
    py = python_ds[field].values[:, 0, 0, :]
    diff, rel = _mixing_diff_rel(mit, py, ocean_mask_11k, skip_surface=True)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    frac_gt1pct = float(np.mean(rel > 0.01))
    assert median < median_bound, f"11k {field}: median abs diff {median:.4g} regressed"
    assert max_abs < max_abs_bound, f"11k {field}: max abs diff {max_abs:.4g} regressed"
    assert frac_gt1pct < frac_gt1pct_bound, (
        f"11k {field}: fraction >1% rel diff {frac_gt1pct:.4%} regressed"
    )


def test_11k_ocean_ice_column_ghat(result_11k, ocean_mask_11k):
    """`ghat` (cell-center nonlocal transport coefficient) over the full,
    now-clean sample. Measured fresh this round (via `_mixing_diff_rel`'s own
    `active = mitgcm_ghat > 1e-6` filter, applied here exactly as for the
    other mixing fields): median_abs 1.52e-3, max_abs 1321.7 (n=13,391;
    rare, tied to the same Rib/Ricr hbl-misdiagnosis tail
    `test_11k_ocean_ice_column_hbl` characterizes -- `ghat` is only nonzero
    inside the diagnosed boundary layer, so a misdiagnosed `hbl` can flip a
    whole near-surface region between "inside"/"outside", producing a large
    absolute swing even though the underlying formula is correct). Tighter
    max_abs bound than the pre-refresh clean-subset number (1907.6).
    """
    _inputs_ds, python_ds, mitgcm_ds = result_11k
    mit = mitgcm_ds['ghat'].values[:, 0, 0, :]
    py = python_ds['ghat'].values[:, 0, 0, :]
    diff, _rel = _mixing_diff_rel(mit, py, ocean_mask_11k, skip_surface=False)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    assert median < 0.01, f"11k ghat: median abs diff {median:.4g} regressed"
    assert max_abs < 1800.0, f"11k ghat: max abs diff {max_abs:.4g} regressed"


# ========================================================================
# lab_sea, 6-month/4368-timestep capture: 20x16 grid, real land columns and
# variable per-column bathymetry. Subsampled to the first 100 (of 4368)
# timesteps for test speed -- see `_LABSEA_6MO_N` and the module docstring
# for the preloading fix needed to make even that subsample tractable.
# Rebuilt+rerun fresh under 1DMIX-050 (2026-09-27): the full 4368-timestep/
# 655,200-wet-column-timestep capture measures 0.0% truncated (checked
# directly against MITgcm's own captured `visc_az`, no Python replay
# needed for that check) -- the 4.11%/~49% figures this module's own
# docstring used to cite for the stale pre-refresh capture no longer apply.
# ========================================================================

@pytest.fixture(scope='module')
def result_labsea_6mo():
    _require(DATA_LABSEA_6MO)
    _require(OUTPUTS_LABSEA_6MO)
    inputs_ds = xr.open_dataset(DATA_LABSEA_6MO).isel(time=slice(0, _LABSEA_6MO_N)).load()
    python_ds = run_python_kpp_on_dataset(inputs_ds, verbose=False)
    mitgcm_ds = xr.open_dataset(OUTPUTS_LABSEA_6MO).isel(time=slice(0, _LABSEA_6MO_N)).load()
    return inputs_ds, python_ds, mitgcm_ds


@pytest.fixture(scope='module')
def ocean_mask_labsea_6mo(result_labsea_6mo):
    inputs_ds, _python_ds, _mitgcm_ds = result_labsea_6mo
    return _ocean_mask(inputs_ds['temperature'].values, inputs_ds['salinity'].values)


def test_lab_sea_6mo_capture_is_not_truncated(result_labsea_6mo, ocean_mask_labsea_6mo):
    """Confirms this capture (rebuilt+rerun fresh under 1DMIX-050, replacing
    the stale 2026-09-18 capture that carried 1DMIX-035's OUTPUT_MIXING
    truncation defect at a real, subsample-dependent ~4.1%-48.9% fraction)
    is now clean. Measured fresh this round over this test file's own first-
    100-timestep subsample (15,000 wet column-timesteps): 0.0% truncated --
    and independently reconfirmed over the FULL 4368-timestep/655,200-wet-
    column-timestep capture directly against MITgcm's own `visc_az` (no
    Python replay needed for that broader check): also 0.0%, matching
    `seaice_obcs`'s own already-clean precedent and confirming the refresh
    worked across the entire run, not just this subsample.
    """
    _inputs_ds, _python_ds, mitgcm_ds = result_labsea_6mo
    clean = _clean_mask(mitgcm_ds['visc_az'].values, ocean_mask_labsea_6mo)
    frac_truncated = 1.0 - (float(clean.sum()) / float(ocean_mask_labsea_6mo.sum()))
    assert frac_truncated < 0.02, (
        f"lab_sea_6mo truncated-column fraction {frac_truncated:.4f} regressed "
        "from the confirmed-clean 0.0% this 1DMIX-050 refresh established -- "
        "this capture should stay clean unless replaced with a stale one again."
    )


def test_lab_sea_6mo_hbl_ocean_columns(result_labsea_6mo, ocean_mask_labsea_6mo):
    """`hbl` was always tested over the full ocean-column sample (unaffected
    by the OUTPUT_MIXING truncation defect even before this issue's capture
    refresh). Remeasured fresh this round against the 1DMIX-050-refreshed
    capture, over the first 100 (of 4368) timesteps' 15,000 ocean-column-
    timesteps: median 2.89e-3 m, max 40.72 m (0.68%/0.47% exceed 1 m/5 m) --
    the same Rib/Ricr threshold-sensitivity tail 1DMIX-019 characterized for
    this experiment's earlier 999-timestep capture.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_labsea_6mo
    diff = np.abs(python_ds['hbl'].values - mitgcm_ds['hbl'].values)[ocean_mask_labsea_6mo]
    median = float(np.median(diff))
    frac_gt5m = float(np.mean(diff > 5.0))
    max_diff = float(np.max(diff))
    assert median < 0.05, f"lab_sea_6mo hbl median diff {median:.4g} m regressed"
    assert frac_gt5m < 0.02, f"lab_sea_6mo hbl fraction >5m diff {frac_gt5m:.4%} regressed"
    assert max_diff < 50.0, f"lab_sea_6mo hbl max diff {max_diff:.4g} m regressed"


@pytest.mark.parametrize('field,median_bound,max_abs_bound,frac_gt1pct_bound', [
    ('visc_az', 1e-5, 0.06, 0.2),
    ('diff_kz_s', 1e-5, 0.1, 0.2),
    ('diff_kz_t', 1e-5, 0.1, 0.2),
])
def test_lab_sea_6mo_mixing(result_labsea_6mo, ocean_mask_labsea_6mo, field,
                             median_bound, max_abs_bound, frac_gt1pct_bound):
    """Mixing-coefficient agreement over the FULL, now-clean ocean-column
    sample (1DMIX-050 refresh -- no clean-subset filtering needed anymore;
    the 4.11%-affected fraction this subsample used to carry barely moved
    the aggregate statistics even before the refresh, since it was already
    small here). Measured fresh this round: `visc_az` median_abs 0 (exact),
    max_abs 3.49e-2, 13.35% of active cells exceed 1% rel (n=171,000);
    `diff_kz_s`/`diff_kz_t` (identical values here) median_abs 0, max_abs
    7.60e-2, 12.27% exceed 1% rel (n=171,000). The >1%-rel fraction is much
    larger than 11k's own fraction -- expected for this multi-column,
    variable-bathymetry, real-land experiment, where the same Rib/Ricr
    hbl-threshold sensitivity flips many more individual columns' boundary-
    layer diagnosis than the single-column case; the absolute-error bounds
    (what actually matters physically) stay small and comparable.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_labsea_6mo
    diff, rel = _mixing_diff_rel(mitgcm_ds[field].values, python_ds[field].values,
                                  ocean_mask_labsea_6mo, skip_surface=True)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    frac_gt1pct = float(np.mean(rel > 0.01))
    assert median < median_bound, f"lab_sea_6mo {field}: median abs diff {median:.4g} regressed"
    assert max_abs < max_abs_bound, f"lab_sea_6mo {field}: max abs diff {max_abs:.4g} regressed"
    assert frac_gt1pct < frac_gt1pct_bound, (
        f"lab_sea_6mo {field}: fraction >1% rel diff {frac_gt1pct:.4%} regressed"
    )


def test_lab_sea_6mo_ghat(result_labsea_6mo, ocean_mask_labsea_6mo):
    """`ghat` over the full, now-clean ocean-column sample. Measured fresh
    this round (via `_mixing_diff_rel`'s own `active = mitgcm_ghat > 1e-6`
    filter, applied here exactly as for the other mixing fields): median_abs
    2.40e-2, max_abs 362.4 (n=34,540) -- same hbl-misdiagnosis-tail mechanism
    as `test_11k_ocean_ice_column_ghat`. Tighter max_abs bound than the
    pre-refresh clean-subset number (500.0).
    """
    _inputs_ds, python_ds, mitgcm_ds = result_labsea_6mo
    diff, _rel = _mixing_diff_rel(mitgcm_ds['ghat'].values, python_ds['ghat'].values,
                                   ocean_mask_labsea_6mo, skip_surface=False)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    assert median < 0.05, f"lab_sea_6mo ghat: median abs diff {median:.4g} regressed"
    assert max_abs < 450.0, f"lab_sea_6mo ghat: max abs diff {max_abs:.4g} regressed"


# ========================================================================
# seaice_obcs_1dmix034: 10x8 grid, salt-plume physics (1DMIX-034), 5
# timesteps. Capture regenerated 2026-09-26, AFTER the 1DMIX-035
# OUTPUT_MIXING fix landed -- confirmed clean (0.0% truncated columns), so
# every field is tested directly with no clean-subset filtering needed.
# ========================================================================

@pytest.fixture(scope='module')
def result_seaice_obcs():
    _require(DATA_SEAICE_OBCS)
    _require(OUTPUTS_SEAICE_OBCS)
    inputs_ds = xr.open_dataset(DATA_SEAICE_OBCS)
    python_ds = run_python_kpp_on_dataset(inputs_ds, verbose=False)
    mitgcm_ds = xr.open_dataset(OUTPUTS_SEAICE_OBCS)
    return inputs_ds, python_ds, mitgcm_ds


@pytest.fixture(scope='module')
def ocean_mask_seaice_obcs(result_seaice_obcs):
    inputs_ds, _python_ds, _mitgcm_ds = result_seaice_obcs
    return _ocean_mask(inputs_ds['temperature'].values, inputs_ds['salinity'].values)


def test_seaice_obcs_capture_is_not_truncated(result_seaice_obcs, ocean_mask_seaice_obcs):
    """Confirms this capture (regenerated after the 1DMIX-035 fix) is the
    clean reference case, distinguishing it from 11k/lab_sea_6mo above --
    measured fresh this round: 0.0% of its 295 real ocean columns show the
    all-zero-interior truncation signature.
    """
    _inputs_ds, _python_ds, mitgcm_ds = result_seaice_obcs
    clean = _clean_mask(mitgcm_ds['visc_az'].values, ocean_mask_seaice_obcs)
    frac_truncated = 1.0 - (float(clean.sum()) / float(ocean_mask_seaice_obcs.sum()))
    assert frac_truncated < 0.02, (
        f"seaice_obcs_1dmix034 truncated-column fraction {frac_truncated:.4f} "
        "regressed from the confirmed-clean 0.0% -- this capture postdates the "
        "1DMIX-035 OUTPUT_MIXING fix and should stay clean unless replaced."
    )


def test_seaice_obcs_hbl(result_seaice_obcs, ocean_mask_seaice_obcs):
    """Measured fresh this round over the 295 real ocean columns: median
    3.46e-2 m, p99 19.15 m, max 20.43 m (9.15%/2.71% exceed 1 m/5 m) --
    matches 1DMIX-034's own cited full-grid numbers ("median |diff|=0.033m
    ... up to 20.4m") almost exactly, confirming this fresh measurement
    reproduces that closed issue's own finding rather than diverging from
    it. The wide tail is the same 1DMIX-019/1DMIX-022 Rib/Ricr threshold-
    sensitivity mechanism 1DMIX-034's own closeout attributed it to, not a
    new defect.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_seaice_obcs
    diff = np.abs(python_ds['hbl'].values - mitgcm_ds['hbl'].values)[ocean_mask_seaice_obcs]
    median = float(np.median(diff))
    frac_gt5m = float(np.mean(diff > 5.0))
    max_diff = float(np.max(diff))
    assert median < 0.5, f"seaice_obcs hbl median diff {median:.4g} m regressed"
    assert frac_gt5m < 0.05, f"seaice_obcs hbl fraction >5m diff {frac_gt5m:.4%} regressed"
    assert max_diff < 25.0, f"seaice_obcs hbl max diff {max_diff:.4g} m regressed"


@pytest.mark.parametrize('field,median_bound,max_abs_bound,frac_gt1pct_bound', [
    ('visc_az', 1e-4, 0.05, 0.25),
    ('diff_kz_s', 1e-4, 0.06, 0.25),
    ('diff_kz_t', 1e-4, 0.06, 0.25),
])
def test_seaice_obcs_mixing(result_seaice_obcs, ocean_mask_seaice_obcs, field,
                             median_bound, max_abs_bound, frac_gt1pct_bound):
    """Measured fresh this round over the 295 real ocean columns: `visc_az`
    median_abs 0 (exact), p99_abs 4.79e-3, max_abs 1.84e-2, 13.9% exceed 1%
    rel; `diff_kz_s`/`diff_kz_t` (identical here) p99_abs 4.87e-3, max_abs
    3.41e-2, 13.9% exceed 1% rel -- the salt-plume `boplume` term (1DMIX-034)
    is included via this capture's own `boplume`/`sp_depth` columns, already
    wired through `run_python_kpp_on_dataset`'s replay path.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_seaice_obcs
    diff, rel = _mixing_diff_rel(mitgcm_ds[field].values, python_ds[field].values,
                                  ocean_mask_seaice_obcs, skip_surface=True)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    frac_gt1pct = float(np.mean(rel > 0.01))
    assert median < median_bound, f"seaice_obcs {field}: median abs diff {median:.4g} regressed"
    assert max_abs < max_abs_bound, f"seaice_obcs {field}: max abs diff {max_abs:.4g} regressed"
    assert frac_gt1pct < frac_gt1pct_bound, (
        f"seaice_obcs {field}: fraction >1% rel diff {frac_gt1pct:.4%} regressed"
    )


def test_seaice_obcs_ghat(result_seaice_obcs, ocean_mask_seaice_obcs):
    """Measured fresh this round: median_abs 0.386, p99_abs 124.4, max_abs
    572.4 -- the same hbl-misdiagnosis-tail mechanism as the other two
    experiments' own `ghat` tests, here additionally interacting with the
    salt-plume `boplume` term's own bfsfc sign-sensitivity near the
    `phepsi=1e-10` regularization floor (1DMIX-034's own characterized
    residual).
    """
    _inputs_ds, python_ds, mitgcm_ds = result_seaice_obcs
    diff, _rel = _mixing_diff_rel(mitgcm_ds['ghat'].values, python_ds['ghat'].values,
                                   ocean_mask_seaice_obcs, skip_surface=False)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    assert median < 2.0, f"seaice_obcs ghat: median abs diff {median:.4g} regressed"
    assert max_abs < 700.0, f"seaice_obcs ghat: max abs diff {max_abs:.4g} regressed"


# ========================================================================
# global_oce_latlon, 720-timestep capture (1DMIX-049): 90x40x15, 4-tile
# (2x2, sNx=45,sNy=20), real global bathymetry, spherical-polar grid,
# useCDscheme, useGMRedi, climatological surface restoring -- this
# project's only genuinely multi-tile, seasonally-complete KPP capture.
# Regenerated fresh via Docker MITgcm this round (the original 1DMIX-027
# capture was lost in a disk-space rescue, see 1DMIX-049's `open_issues.md`
# addendum for the full build/timestep-reconciliation evidence). Subsampled
# to the first 5 (of 720) timesteps at FULL spatial resolution for the
# Python-port replay -- see `_GLOBAL_OCE_LATLON_N`'s module-level comment
# for why (timesteps, not columns, were traded off).
# ========================================================================

@pytest.fixture(scope='module')
def result_global_oce_latlon():
    _require(DATA_GLOBAL_OCE_LATLON)
    _require(OUTPUTS_GLOBAL_OCE_LATLON)
    inputs_ds = xr.open_dataset(DATA_GLOBAL_OCE_LATLON).isel(
        time=slice(0, _GLOBAL_OCE_LATLON_N)).load()
    python_ds = run_python_kpp_on_dataset(inputs_ds, verbose=False)
    mitgcm_ds = xr.open_dataset(OUTPUTS_GLOBAL_OCE_LATLON).isel(
        time=slice(0, _GLOBAL_OCE_LATLON_N)).load()
    return inputs_ds, python_ds, mitgcm_ds


@pytest.fixture(scope='module')
def ocean_mask_global_oce_latlon(result_global_oce_latlon):
    inputs_ds, _python_ds, _mitgcm_ds = result_global_oce_latlon
    return _ocean_mask(inputs_ds['temperature'].values, inputs_ds['salinity'].values)


def test_global_oce_latlon_wet_column_count_is_stable(result_global_oce_latlon,
                                                        ocean_mask_global_oce_latlon):
    """Sanity check specific to this experiment's real, time-invariant
    bathymetry (1DMIX-049): every one of the (subsampled) timesteps must show
    the exact same 2,315 wet columns -- bathymetry does not change in time,
    only forcing does, so a per-timestep count that drifted would indicate a
    parsing/tiling bug (e.g. a regressed BI/BJ remap, 1DMIX-021), not real
    physics. Measured fresh this round, confirmed over the FULL 720-timestep
    capture too (not just this 5-timestep subsample): 2,315 wet columns at
    every single timestep, exactly matching 1DMIX-027's own historically-cited
    1,666,800 = 720x2,315 wet-column-timestep sample size.
    """
    _inputs_ds, _python_ds, _mitgcm_ds = result_global_oce_latlon
    per_timestep_counts = ocean_mask_global_oce_latlon.sum(axis=(1, 2))
    assert np.all(per_timestep_counts == 2315), (
        f"global_oce_latlon wet-column count drifted across timesteps: "
        f"{per_timestep_counts.tolist()} -- expected a constant 2315 (time-"
        "invariant bathymetry)."
    )


def test_global_oce_latlon_capture_is_not_truncated(result_global_oce_latlon,
                                                      ocean_mask_global_oce_latlon):
    """Confirms this fresh (2026-09-27) Docker MITgcm rebuild is clean --
    `code_validation/kpp_calc.F`/`kpp_routines.F` were confirmed byte-identical
    to the canonical, post-1DMIX-035-fix `kpp_mods/` copies before this
    capture was built. Measured fresh this round: 0.0% of the 11,575 real
    ocean column-timesteps (first 5 of 720 timesteps) show the all-zero-
    interior truncation signature.
    """
    _inputs_ds, _python_ds, mitgcm_ds = result_global_oce_latlon
    clean = _clean_mask(mitgcm_ds['visc_az'].values, ocean_mask_global_oce_latlon)
    frac_truncated = 1.0 - (float(clean.sum()) / float(ocean_mask_global_oce_latlon.sum()))
    assert frac_truncated < 0.02, (
        f"global_oce_latlon_720 truncated-column fraction {frac_truncated:.4f} "
        "-- this fresh capture was confirmed clean at build time and should "
        "stay clean unless replaced with a stale one."
    )


def test_global_oce_latlon_hbl(result_global_oce_latlon, ocean_mask_global_oce_latlon):
    """Measured fresh this round over the first 5 (of 720) timesteps' 11,575
    ocean column-timesteps: median 1.36e-3 m, p95 0.0239 m, p99 0.672 m, max
    33.9 m (0.78%/0.16% exceed 1 m/5 m) -- the same Rib/Ricr threshold-
    sensitivity tail 1DMIX-019 characterized for every other multi-column
    experiment, at a magnitude fully consistent with 1DMIX-027's own
    historical result for this same experiment (median 0.0074 m, max 513.7 m
    over the full 720-timestep sample) despite the much smaller subsample
    here.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_global_oce_latlon
    diff = np.abs(python_ds['hbl'].values - mitgcm_ds['hbl'].values)[
        ocean_mask_global_oce_latlon]
    median = float(np.median(diff))
    frac_gt5m = float(np.mean(diff > 5.0))
    max_diff = float(np.max(diff))
    assert median < 0.02, f"global_oce_latlon hbl median diff {median:.4g} m regressed"
    assert frac_gt5m < 0.01, f"global_oce_latlon hbl fraction >5m diff {frac_gt5m:.4%} regressed"
    assert max_diff < 60.0, f"global_oce_latlon hbl max diff {max_diff:.4g} m regressed"


@pytest.mark.parametrize('field,median_bound,max_abs_bound,frac_gt1pct_bound', [
    ('visc_az', 1e-5, 0.5, 0.02),
    ('diff_kz_s', 1e-5, 1.2, 0.03),
    ('diff_kz_t', 1e-5, 1.2, 0.03),
])
def test_global_oce_latlon_mixing(result_global_oce_latlon, ocean_mask_global_oce_latlon,
                                   field, median_bound, max_abs_bound, frac_gt1pct_bound):
    """Mixing-coefficient agreement over the first 5 (of 720) timesteps' full
    spatial sample (11,575 ocean column-timesteps, 134,970 active interior
    cells). Measured fresh this round: `visc_az` median_abs 0 (exact), max_abs
    0.332, 0.42% of active cells exceed 1% rel; `diff_kz_s`/`diff_kz_t`
    (identical here, `diffKzS=diffKzT` in this configuration) median_abs 0,
    max_abs 0.959, 1.31% exceed 1% rel. This is this project's only
    `useCDscheme`+`useGMRedi`+climatological-restoring KPP capture; the
    forcing-validation gate correctly falls back to MITgcm's own captured
    `ustar`/`bo`/`bosol` for the actual mixing computation regardless of the
    known, diagnostic-only `bo` mismatch (1DMIX-022's root cause 2, climate-
    restoring flux not replicated in the raw-flux pipeline) -- confirmed by
    these bounds matching, not exceeding, the other multi-column experiments'
    own established magnitudes.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_global_oce_latlon
    diff, rel = _mixing_diff_rel(mitgcm_ds[field].values, python_ds[field].values,
                                  ocean_mask_global_oce_latlon, skip_surface=True)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    frac_gt1pct = float(np.mean(rel > 0.01))
    assert median < median_bound, f"global_oce_latlon {field}: median abs diff {median:.4g} regressed"
    assert max_abs < max_abs_bound, f"global_oce_latlon {field}: max abs diff {max_abs:.4g} regressed"
    assert frac_gt1pct < frac_gt1pct_bound, (
        f"global_oce_latlon {field}: fraction >1% rel diff {frac_gt1pct:.4%} regressed"
    )


def test_global_oce_latlon_ghat(result_global_oce_latlon, ocean_mask_global_oce_latlon):
    """Measured fresh this round (via `_mixing_diff_rel`'s own
    `active = mitgcm_ghat > 1e-6` filter): median_abs 8.64, max_abs 115.97
    (n=394) -- same hbl-misdiagnosis-tail mechanism as the other three
    experiments' own `ghat` tests. `KPP_GHAT` is `#undef`'d in this
    experiment's own `KPP_OPTIONS.h` (the nonlocal-transport term is not
    applied to the diffusive flux), but the raw `ghat` diagnostic array is
    still computed and captured unconditionally by `KPPMIX`/`kpp_calc.F` --
    confirmed non-degenerate by direct inspection (real nonzero values, not
    uniformly zero) before this bound was set.
    """
    _inputs_ds, python_ds, mitgcm_ds = result_global_oce_latlon
    diff, _rel = _mixing_diff_rel(mitgcm_ds['ghat'].values, python_ds['ghat'].values,
                                   ocean_mask_global_oce_latlon, skip_surface=False)
    median = float(np.median(diff))
    max_abs = float(np.max(diff))
    assert median < 15.0, f"global_oce_latlon ghat: median abs diff {median:.4g} regressed"
    assert max_abs < 150.0, f"global_oce_latlon ghat: max abs diff {max_abs:.4g} regressed"
