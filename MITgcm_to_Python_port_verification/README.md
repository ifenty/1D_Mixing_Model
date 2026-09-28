# MITgcm ↔ Python Port Verification

This directory holds everything needed to validate the Python ports of MITgcm's
**KPP** and **GGL90** vertical-mixing schemes (`Vertical_Mixing_Models/KPP`,
`Vertical_Mixing_Models/GGL90`) against the real MITgcm Fortran, using a
three-way comparison method:

1. **Full-model MITgcm** — run a real, instrumented MITgcm verification
   experiment (via Docker) to produce a captured "input" (column state,
   forcing, grid, parameters) and "output" (mixing coefficients, boundary
   layer depth, etc.) as paired NetCDF files.
2. **Standalone Fortran routine** — call the scheme's Fortran subroutine
   directly (no full model, no `genmake2`), fed the *same* "input", to check
   that the isolated-routine wrapper itself reproduces the full model exactly.
   (KPP only so far — see `mitgcm_verification_mods/kpp_standalone_driver/`.)
3. **Python port** — run the Python port on the *same* "input" and compare
   its "output" against MITgcm's captured "output".

(1)≈(2) validates the standalone-routine harness. (1)+(3)≈(2) validates the
Python port. Disagreements are either fixed (real port bugs) or documented
with a concrete, sourced reason they should differ (e.g. `docs/model_contract.md`'s
sign/staggering conventions). See the repo root's `open_issues.md` /
`closed_issues.md` for the full, evidence-based bug history — this README
summarizes current status but those files are the source of truth.

**For the full narrative** — what was tested and why, the quantified result
per experiment, and the plain-terms root cause behind every real
discrepancy (with citations to the closed issue that established it) — see
[`VALIDATION_RESULTS.md`](VALIDATION_RESULTS.md). This README keeps the
compact status table below; that document is the deep dive a newcomer
should read to actually understand the results (1DMIX-045).

## Directory guide

| Path | What it is |
|---|---|
| `scripts/` | The active comparison pipeline (parse MITgcm STDOUT → replay through the Python port → report). See `scripts/README.md`. |
| `mitgcm_verification_mods/` | This project's own MITgcm instrumentation (Fortran mods that dump validation data), one subdirectory per MITgcm verification experiment (`1D_ocean_ice_column/`, `lab_sea/`, `vermix/`), plus `kpp_mods/`/`ggl90_mods/` (the maintained source of truth, symlinked/copied into each experiment's `code_validation/`). Git-tracked, actively maintained — see its own `README.md`. |
| `mitgcm_verification_mods/kpp_standalone_driver/` | Standalone-subroutine harness that calls MITgcm's real `KPPMIX` directly (no full model) — step (2) of the three-way method, KPP only. Auto-detects grid size (`Nr`) from the input file, so it works for both real MITgcm captures (via `scripts/export_kpp_input_for_fortran.py`) and the idealized Python-port scenarios (via `scripts/export_scenario_to_fortran.py`, `scripts/compare_scenario_standalone.py`). |
| `KPP_port_validation/`, `GGL90_port_validation/` | Captured data (`inputs_from_mitgcm/`, `outputs_from_mitgcm/`, `outputs_from_python/`, gitignored `*.nc`) and format docs (`NETCDF_DATA_FORMAT.md`). Both have a `reports/` directory (symmetric since 1DMIX-044) holding generated PDF reports, freshly regenerated against current code/captures 2026-09-27; `KPP_port_validation/reports/` additionally keeps two still-relevant lessons-learned docs (`critical_lessons_fortran_to_python_porting.md`, `possible_kpp_bugs_in_mitgcm.md`). `KPP_port_validation/scripts/` (one ad hoc stats tool, `compute_validation_statistics.py`), `archive_2026-08-investigation/` and `SIMPLIFIED_API_SUMMARY.md` are KPP-only extras with no GGL90 counterpart needed; 1DMIX-046 removed `GGL90_port_validation/scripts/` (empty, unused) rather than manufacturing a matching one, and confirmed no other structural asymmetry remains. Each of `KPP_port_validation/`/`GGL90_port_validation/` has its own `CAPTURES.md` manifest (1DMIX-046) stating, for every experiment with more than one versioned capture, which file is current and why older ones are retained. `KPP_port_validation/archive_2026-08-investigation/` holds material explicitly disclaimed as superseded, including the outlier-debugging scripts/PNGs relocated there under 1DMIX-046 (see its own `README.md`); read `closed_issues.md` for the current, accurate history, not those archived documents. |
| `tests/` | Root-level pytest suite. `test_kpp_mitgcm_validation.py` runs real assertions against `run_python_kpp_on_dataset` for `1D_ocean_ice_column` and `lab_sea` (1DMIX-011, resolved 2026-09-19). `test_ggl90_mitgcm_validation.py` is the GGL90 equivalent (1DMIX-042): real MITgcm-comparison regression assertions against `run_ggl90_from_netcdf_input.py::run` for `vermix`, `1D_ocean_ice_column` (11,000 timesteps), `isomip` (`ALLOW_SHELFICE`, bounded known 1DMIX-038 gap), `global_ocean_90x40x15` (bounded known IDEMIX gap, 1DMIX-025) and `global_ocean_cs32x15` (bounded known pressure-coordinate gap, permanently out of scope per 1DMIX-040). |

## Running the pipeline

```bash
# 1. Capture a fresh MITgcm run (only if you don't already have inputs_from_mitgcm/*.nc)
#    See mitgcm_verification_mods/README.md for the Docker compile/run commands,
#    then parse its STDOUT:
conda run -n ecco python3 scripts/parse_mitgcm_split.py <mitgcm_output.txt> <experiment_name>
# (GGL90 experiments use scripts/parse_mitgcm_ggl90_split.py instead)

# 2. Replay through the Python port and compare
PYTHONPATH="../Vertical_Mixing_Models:$PYTHONPATH" conda run -n ecco python3 \
  scripts/run_kpp_from_netcdf_input.py <inputs.nc> -o <python_outputs.nc>
# (GGL90: scripts/run_ggl90_from_netcdf_input.py + scripts/compare_ggl90.py)

# 3. Generate a full report
conda run -n ecco python3 scripts/generate_kpp_validation_report.py \
  <mitgcm_outputs.nc> <python_outputs.nc> <report.pdf>
# (GGL90: scripts/generate_ggl90_validation_report.py, same CLI shape,
#  1DMIX-044 -- compares visc_az/diff_kz/mixing_length/tke_after instead of
#  KPP's hbl/visc_az/diff_kz_s/diff_kz_t/ghat)
```

`run_kpp_from_netcdf_input.py`/`run_ggl90_from_netcdf_input.py` both require
`PYTHONPATH` (or an equivalent `sys.path` insert) pointing at
`Vertical_Mixing_Models/`, since the two repos were split apart during a
2026-09-18 reorganization and several scripts still have a stale hardcoded
path — work around it with `PYTHONPATH` rather than editing the script, unless
you're specifically fixing that path issue as its own piece of work.

## Current validation status (2026-09-19)

Compact reference table below; see [`VALIDATION_RESULTS.md`](VALIDATION_RESULTS.md)
for the fresh (2026-09-27), quantified per-experiment narrative and root-cause
explanations this table only summarizes.

| Experiment | Scheme | Coverage | Result |
|---|---|---|---|
| `1D_ocean_ice_column` | KPP | Full-model + Python port, 10 timesteps, single column | `bo`/`bosol` forcing within 1% at 10/10 timesteps (1DMIX-013); `hbl` max diff 0.013 m, `visc_az` max rel err 1.5% |
| `1D_ocean_ice_column` | KPP | Full-model + Python port, **11,000 timesteps**, single sea-ice-coupled column — the longest single-column run validated | Best agreement of any experiment tested: `hbl` median diff 0.0001 m, p99 0.08 m, only 0.38%/0.25% of timesteps exceed 1 m/5 m; `visc_az` median diff exactly 0, **zero** active cells exceed 1e-2 (1DMIX-029, resolved). The pre-existing stale capture (dated before this session) *was* affected by 1DMIX-012's bug, but only in diagnostic-only columns never used for this comparison. |
| `lab_sea` | KPP | Full-model + Python port, **41-day (999-timestep) and 6-month (4368-timestep) full 20×16-grid runs** (149,850 and 655,200 real ocean column-timesteps respectively) | 41-day: `hbl` median diff 0.004 m, p99 0.55 m, 0.25-0.6% of columns exceed 5 m/1 m. 6-month (longer, more representative sample): `hbl` median diff *improved* to 0.001 m, but the tail is measurably wider — 3.6%/1.5%/0.31% of column-timesteps exceed 1 m/5 m/20 m, worst case 112.5 m (full-column convection vs. a 5 m diagnosis) at a near-degenerate, weakly-stratified polar column. Same Rib/Ricr floating-point-threshold mechanism as the 41-day sample, now confirmed at a more extreme scale — not a new or different cause, still not a port defect (1DMIX-019, resolved/characterized, addendum 2026-09-19). |
| `1D_ocean_ice_column` | KPP standalone (step 2) | Standalone-Fortran vs. full-model, 10 timesteps | Exact match, max diff 1.77e-17 (floating-point roundoff) at every timestep/level (1DMIX-012, resolved — was a silent float-parsing bug in the capture pipeline, not a physics or standalone-driver defect) |
| `vermix` | GGL90 | Full-model + Python port, 20 timesteps, single column | `mixing_length`/`diff_kz` exact (0/520 mismatches); `visc_az` 0/520 (1DMIX-016); `tke_after` **0/520** (max rel 3.1e-3, roundoff-level) since the 1DMIX-048 TKE-buoyancy-term fix — was 2/520 (max rel 4.9%) after fixing the harness's `dt` bug (1DMIX-015), and 40/520 before that fix. 1DMIX-041's own single-worst-cell substitution test had concluded this specific residual was *not* explained by the buoyancy-term bug (at those 2 cells the raw turbulent value already exceeded both background floors, so the two `KappaH` formulas coincided there) — that conclusion held for those 2 cells in isolation, but the real fix changes every quiescent level's buoyancy term simultaneously, and the coupled implicit TKE solve propagates that column-wide correction into these 2 cells too; re-verified fresh under 1DMIX-048, both cells collapse to ~1e-7 relative error. |
| `1D_ocean_ice_column` | GGL90 (`mxlMaxFlag=3`) | Full-model + Python port, **11,000 timesteps**, single sea-ice-coupled column — first GGL90 cross-test on a KPP-only-configured experiment | `visc_az`/`diff_kz`: median exactly 0, **zero** of 253,000 column-timesteps exceed even a strict 1e-4 m²/s threshold — best GGL90 agreement of any experiment tested. `mixing_length`: median 5.7e-7 m, p99 0.0089 m, max 0.522 m (0.80% of column-timesteps exceed 0.01 m) — a small, bounded tail plausibly the same discrete-threshold floating-point sensitivity already characterized for KPP's `hbl`/Rib-Ricr crossing, not independently traced to a specific mechanism (1DMIX-028, investigating). `tke_after` (checked fresh under 1DMIX-048, not previously reported in this row): this experiment's `viscAz=1.93e-05 != diffKzS=1.46e-07`, so it was a real (previously unchecked) candidate for the TKE-buoyancy-term bug — confirmed: **6622/253,000 mismatches (max rel 56x) before the fix, 0/253,000 (max rel 5.1e-9, roundoff) after** — the largest single before/after improvement measured for this fix. |
| `global_oce_latlon` | KPP | Full-model + Python port, **720 timesteps (one full 360-day periodic-forcing cycle)**, real global bathymetry, **4-tile domain (2×2, 90×40×15)** — first genuinely multi-tile, seasonally-complete capture | Historical full-sample result (1DMIX-027): `hbl` median diff 0.00735 m, p95 0.274 m, p99 3.03 m, max 513.7 m over 1,666,800 wet column-timesteps; `visc_az`/`diff_kz_s` (active mixing only) median exactly 0, p99 0.033/0.081 m²/s, 1.55%/1.80% of active cells exceed the 1e-2 m²/s threshold. Same Rib/Ricr threshold-crossing-sensitivity pattern already characterized for `lab_sea` (1DMIX-019) — the tail widens with the much larger, seasonally-complete sample but no new mechanism or defect found. Two real bugs were found and fixed getting the pipeline itself working (still valid, found on the original 4-timestep smoke test): `tau_x`/`tau_y` capture didn't match KPP's actual C-grid-staggered usage, and a hard forcing-validation gate was destroying ~99.5% of columns as NaN before mixing coefficients were even computed — now a diagnostic warning, since the mixing computation never depended on it (1DMIX-022, resolved). **1DMIX-049 update (2026-09-27)**: the original capture was lost in a disk-space rescue; regenerated fresh via a real Docker MITgcm rerun of the unmodified `nTimeSteps=720` config (confirmed 2,315 wet columns at every timestep, exactly matching the historical 1,666,800-sample size) and permanentized as `mitgcm_kpp_{inputs,outputs}_global_oce_latlon_720.nc`. A bounded 5-timestep/11,575-column-timestep Python-port replay (full spatial resolution, a full 720-timestep replay estimated at ~1.5 h) now locks in `hbl` median diff 1.36e-3 m/max 33.9 m and `visc_az`/`diff_kz_{s,t}` median exactly 0/max_abs 0.33–0.96, consistent with the historical full-sample magnitudes — see `test_kpp_mitgcm_validation_extended.py`'s `global_oce_latlon` test class. |
| 6 idealized scenarios (`calm_baseline`, `arctic_convection`, `hurricane_wind`, `tropical_heating_diurnal`, `heavy_rain_freshening`, `combined_storm`) | KPP standalone (step 2), no MITgcm involved | Python-port-driven state/forcing replayed through the real Fortran `KPPMIX` directly | **5 of 6 exact to floating-point roundoff** (max abs diff ≤6.1e-16). `combined_storm` has a bounded residual (`hbl` max diff 0.32 m while the boundary layer actively deepens from 70→387 m) with the identical signature already characterized in 1DMIX-019 (Rib/Ricr threshold sensitivity) — not a new defect (1DMIX-023, resolved). |
| 6 idealized scenarios (same 6 as above) | GGL90 standalone (step 2), no MITgcm involved | Python-port-driven state/forcing (dense, `output_frequency_steps=1` re-run) replayed through the real Fortran `GGL90_CALC` directly, all 6 scenarios exported/built/run/compared fresh (rerun again, post-fix, 2026-09-27 under 1DMIX-048) | `visc_az`/`diff_kz`/`mixing_length`: **exact to floating-point roundoff in every scenario** (max abs diff ≤2.0e-14, max rel ≤5.0e-15, 0 cells >1% at any scenario) — unaffected by the fix, as expected. `tke_after`: **also now exact to floating-point roundoff in every scenario** (max abs diff ≤4.0e-06, max rel ≤1.4e-11, 0 cells >1% at any scenario) — fixed by 1DMIX-048; was a real, fully root-caused mismatch in every scenario before the fix (max abs diff up to 4.0e-06; up to 4082/115,000 cells >1% rel. err. for `arctic_convection`). See "GGL90 standalone driver: 6-scenario results and the TKE-tendency bug fix" below and 1DMIX-041/1DMIX-048. |
| `isomip` (`input.obcs`) | GGL90 + `ALLOW_SHELFICE` | Full-model + Python port, 12 timesteps, **8-tile domain (2×4, 50×100×30)**, first `ALLOW_SHELFICE` (floating-ice-shelf) capture — 2401 of 4851 wet columns have a dry-top-then-wet-below profile (ice draft masks the real surface; `kTopC` from 6 to 22) | `visc_az`/`mixing_length`/`tke_after` mostly clean (median 0 for `visc_az`/`tke_after`); `diff_kz` has an exact, fully root-caused mismatch of one `background_diff` unit (5e-05) at every ice-shelf column's own shifted surface level (`kSrf=kTopC`, 28812/1,437,204 cells) — the Python port's `kappa_h[0]=0` "no surface flux" convention doesn't hold at a `ALLOW_SHELFICE`-shifted `kSrf>0`; `tke_after`/`mixing_length` have smaller, related, not-yet-fully-traced mismatches near `kSrf`. Real physics-port defect, not a harness artifact — split to **1DMIX-038** (open). Getting a valid capture at all required fixing two real harness bugs first (1DMIX-025): the Fortran capture's own land-exclusion check silently discarded the entire ice-shelf-covered half of the domain, and the Python replay's `_wet_level_count` assumed the wet region always starts at index 0. **1DMIX-048 `tke_after` before/after** (this experiment's `viscAz=0.001 != diffKzS=5e-05`, a real candidate): worst-case magnitude improved sharply (max rel **246x → 2.3x**), but the >1%-mismatch *count* rose slightly (17109/1,437,204 → 17934/1,437,204: 179 cells crossed into agreement, 1004 crossed out) — investigated, not averaged away: 955/1004 (95%) of the newly-crossed cells sit at exactly 2 grid levels below each column's own `kSrf`, and a direct probe of one such cell confirms `kappa_m`/mixing length/Prandtl number (=10, capped) all match MITgcm's own captured diagnostics exactly, and `N²` (cross-checked directly against the captured `sigma_r` input) agrees to ~2e-7 relative — i.e. the fixed formula itself is exactly right at this cell. The residual is a downstream effect of the coupled implicit TKE solve redistributing the now-corrected, column-wide buoyancy-term change into the SAME already-open near-`kSrf` region 1DMIX-038 itself flags as "not-yet-fully-traced" — not a defect in this fix (confirmed clean, zero-regression end-to-end on the uncontaminated 6-scenario oracle and on `vermix`/`1D_ocean_ice_column` below). Logged as additional evidence for **1DMIX-038** (not a new issue). |
| `global_ocean.90x40x15` (`input.idemix`) | GGL90 + `ALLOW_GGL90_IDEMIX` | Full-model + Python port, 10 timesteps, **36-tile domain (9×4, 90×40×15)**, first `useIDEMIX` capture, real z-coordinate experiment | Clean, decisive quantification of the (expected) missing-physics gap: `corr(deltaT·IDEMIX_gTKE, MITgcm_tke_after − python_tke_after) = 0.998` over 243,692 column-timesteps — the Python port's zero-IDEMIX-physics mismatch tracks the real, captured missing source term almost perfectly. `diff_kz`/`tke_after` (51%/54% of 485,840 cells exceed 1% rel. err.) are far more affected than `visc_az`/`mixing_length` (~0.04%), matching the formulas exactly (only `TKEPrandtlNumber`/the TKE update depend on `IDEMIX_gTKE`). Python GGL90 port confirmed to have **no** IDEMIX physics at all (`use_idemix` is a dead placeholder). Not a port defect — expected, documented physics gap (1DMIX-025, resolved for this experiment). |
| `global_ocean.cs32x15` (`input.in_p`) | GGL90 + `ALLOW_GGL90_IDEMIX` | Full-model + Python port, 10 timesteps, **12-tile cubed-sphere domain (384×16×15)**, first `usingPCoords` (pressure-coordinate) capture | Capture itself real/complete (`STOP NORMAL END`, all fields present). **Comparison confounded, not usable as an IDEMIX signal**: this experiment runs in pressure coordinates (`buoyancyRelation='OCEANICP'`), which this port has no support for at all — grid geometry captured in Pa is fed through length-ceiling formulas that assume metres, producing errors up to ~4 orders of magnitude (one point-verified cell: real `mixing_length=1277m` vs. Python `14493km`). `diff_kz`/`mixing_length`/`tke_after` all have >60% of cells exceeding 1% rel. err., dominated by this confound, not IDEMIX. New, separate physics-port gap — split to **1DMIX-040** (open). |

Two real port-independent harness bugs were found and fixed while extending
coverage to `lab_sea` (never previously exercised as a multi-column case):
land-mask convention mismatch, and no per-column bathymetry/seafloor
awareness (both tracked in closed issue 1DMIX-018). Extending coverage to
`global_oce_latlon` (the first genuinely multi-tile, 4-tile domain) found and
fixed three more real, independent bugs — leftover uncommitted debug
instrumentation in `kpp_mods/kpp_routines.F` that broke compilation
(1DMIX-020), a silent multi-tile data-collision bug in
`parse_mitgcm_split.py` from never having parsed the `BI=`/`BJ=` tile indices
kpp_calc.F always writes (1DMIX-021), and a C-grid-staggering capture gap
plus an overly-strict forcing-validation gate that together destroyed ~99.5%
of this experiment's columns as NaN (1DMIX-022). Always check
`open_issues.md`/`closed_issues.md` for the current, complete picture — the
table above is a snapshot, not a substitute.

## GGL90 standalone driver: 6-scenario results and the TKE-tendency bug fix (1DMIX-041/1DMIX-048)

`mitgcm_verification_mods/ggl90_standalone_driver/` (built under 1DMIX-024) and
`scripts/export_scenario_to_ggl90_driver.py`/`scripts/compare_scenario_ggl90_standalone.py`
(written the same 2026-09-19 session) had never actually been exercised against
any of the 6 idealized scenarios before 1DMIX-041 — pre-existing files under
`Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_*` dated 2026-09-19
were found on disk but confirmed **stale**: `Vertical_Mixing_Models/GGL90/*.py`
and `main/eos.py`/`main/unified_driver.py` were all modified after that
timestamp (as recently as 2026-09-26, e.g. the 1DMIX-039 EOS-pressure fix), so
those artifacts predate several real port fixes and were not reused. All 6
scenarios were exported, built, run and compared fresh under 1DMIX-041
(2026-09-27), then re-exported/rebuilt/rerun fresh again after 1DMIX-048's fix
(same day) — the table below reflects the **post-fix** state; see "The fix and
its verification" below for the original bug and the before/after evidence.

The prose table below was, until 1DMIX-051, the only record of these results
— unlike the 10 MITgcm-capture experiments (1DMIX-044), there was no
generated, freshly-reproducible report artifact for this comparison shape
(Fortran-standalone-driver output vs. Python port, not MITgcm-capture vs.
Python port — doesn't fit `generate_ggl90_validation_report.py`'s NetCDF-
shaped structure). `scripts/generate_ggl90_scenario_report.py` (1DMIX-051)
now generates
[`GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md`](GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md)
fresh from the same on-disk `Vertical_Mixing_Models/output/<scenario>/`
artifacts, reusing `compare_scenario_ggl90_standalone.py::compare` directly
(same numbers as the table below, just machine-generated and rerunnable
rather than hand-maintained prose).

| Scenario | n_out × nz | `visc_az` max_abs / max_rel | `diff_kz_s` max_abs / max_rel | `mixing_length` max_abs / max_rel | `tke_after` max_abs / max_rel (n>1% / total) |
|---|---|---|---|---|---|
| `calm_baseline` | 288×50 | 1.06e-15 / 3.99e-15 | 1.08e-16 / 4.18e-15 | 1.19e-12 / 4.05e-15 | 7.59e-19 / 8.78e-14 (0/14400) |
| `arctic_convection` | 5000×23 | 2.22e-15 / 4.30e-15 | 6.38e-16 / 4.82e-15 | 1.14e-12 / 4.26e-15 | 2.17e-18 / 9.52e-13 (0/115000) |
| `hurricane_wind` | 144×50 | 1.87e-14 / 4.14e-15 | 1.87e-14 / 4.65e-15 | 1.48e-12 / 4.12e-15 | 4.44e-16 / 1.39e-11 (0/7200) |
| `tropical_heating_diurnal` | 144×50 | 2.78e-16 / 3.99e-15 | 2.78e-17 / 4.49e-15 | 1.42e-12 / 4.15e-15 | 1.08e-19 / 1.35e-13 (0/7200) |
| `heavy_rain_freshening` | 144×50 | 9.02e-17 / 4.13e-15 | 1.08e-17 / 4.43e-15 | 1.25e-12 / 4.21e-15 | 1.56e-17 / 2.97e-14 (0/7200) |
| `combined_storm` | 72×50 | 2.13e-14 / 4.18e-15 | 1.16e-14 / 4.45e-15 | 1.42e-12 / 4.02e-15 | 1.55e-15 / 7.93e-14 (0/3600) |

`visc_az`/`diff_kz_s`/`mixing_length` are exact to floating-point roundoff in
**every** scenario (max_rel ~4-5e-15 throughout, `n_gt_1pct=0` everywhere) —
the strongest possible confirmation that GGL90's *diagnostic* mixing-coefficient
formulas match MITgcm's real `GGL90_CALC` exactly for these 6 scenarios, and
**byte-for-byte unaffected by 1DMIX-048's fix below** (confirmed identical to
the pre-fix values reported originally under 1DMIX-041).

`tke_after` (the one prognostic field) **also now matches to floating-point
roundoff in every scenario** (max_rel ≤1.4e-11, `n_gt_1pct=0` everywhere) —
this is the direct, end-to-end confirmation of 1DMIX-048's fix, mirroring the
hand-verified single-cell substitution test below at full scale. Before the
fix (1DMIX-041, original numbers), `tke_after` did **not** match in any of the
6 scenarios: max abs diff up to 4.0e-06, up to 4082/115,000 cells >1% rel.
err. for `arctic_convection` — investigated per that issue's own instruction,
not averaged away.

### The bug and its root cause (1DMIX-041)

MITgcm's real TKE tendency equation (`ggl90_calc.F:661`,
`KappaH = KappaM(i,j)/TKEPrandtlNumber(k)`, used at line 673's
`- KappaH*Nsquare(k)` term) uses `KappaM` **after only its own viscosity
floor** (`viscArNr`, the same quantity captured/compared as `visc_az` — exact
above) divided by the Prandtl number. This is a different quantity from the
*exported* `GGL90diffKr` (`diff_kz`, exact above too): that output
additionally floors the pre-Prandtl-division intermediate by the
*diffusivity* background (`diffKrNrS`) and caps the result by `diffMax`
(ggl90_calc.F:1086-1088). Before the fix,
`Vertical_Mixing_Models/GGL90/ggl90_core_driver.py`'s `compute_mixing` passed
the single `kappa_h` returned by
`ggl90_mixing_coefficients.py::compute_viscosity_diffusivity` to **both** the
diagnostic output *and* `ggl90_scheme_specific.py::compute_tke_buoyancy` (the
TKE tendency's buoyancy term) — correct only when `background_visc ==
background_diff` (or the raw turbulent value exceeds both floors). All 6
scenarios' `configuration_yamls/physical_parameters.yaml` sets
`viscAz=5e-5 ≠ diffKzS=1e-5`, so the two floors diverged at every
quiescent/weakly-turbulent level, which is exactly where every one of the
1DMIX-041-era mismatches occurred. Verified by direct substitution:
recomputing `KappaM/TKEPrandtlNumber` (instead of `kappa_h`) for the buoyancy
term at the single worst-mismatching `(timestep, level)` cell in **every one
of the 6 scenarios** collapsed the residual from up to 4.0e-06 absolute
(≈90%+ relative in several cases) to 1e-18–1e-20 (floating-point roundoff) in
every case — an exact, not approximate, confirmation of the mechanism.

### The fix and its verification (1DMIX-048)

**Applied and verified.** `ggl90_mixing_coefficients.py::compute_viscosity_diffusivity`
now returns a third value, `kappa_h_tendency = kappa_m / tke_prandtl_number`
— unfloored by `background_diff`, uncapped by `diff_max` (only `kappa_m`'s
own viscosity floor applies, matching MITgcm's real `KappaM` exactly).
`GGL90Driver.compute_mixing` feeds `kappa_h_tendency` (not `kappa_h`) to
`compute_tke_buoyancy`; the existing `kappa_h` (correct as the
diagnostic/output quantity) is untouched everywhere else. This is a
`scientific_change` (Richard's independent review required before it lands),
per this issue's own brief.

Beyond the clean 6-scenario oracle above, every existing real GGL90 MITgcm
capture was re-checked for `background_visc != background_diff` and its
`tke_after` before/after this fix, per this issue's own instruction (not just
pass/fail):

| Capture | `viscAz` vs `diffKzS` | `tke_after` before → after (n>1% / total) | max_rel before → after |
|---|---|---|---|
| `vermix` | 1e-4 ≠ 1e-5 | 2/520 → **0/520** | 4.87e-2 → 3.07e-3 |
| `1D_ocean_ice_column` (`mxlMaxFlag=3`, 11,000 steps) | 1.93e-5 ≠ 1.46e-7 | 6622/253,000 → **0/253,000** | 56.1 → 5.1e-9 |
| `global_ocean.90x40x15` (IDEMIX) | 0.0 = 0.0 | 264515/485,840 → 264515/485,840 (unchanged, byte-identical) | 3.5e7 → 3.5e7 (unaffected; dominated entirely by the separate, already-documented IDEMIX missing-physics gap, 1DMIX-025) |
| `global_ocean.cs32x15` (p-coord) | 0.0 = 0.0 | 527111/813,820 → 527111/813,820 (only 110/813,820 cells change at all, max change 0.076, no threshold crossing either way) | 4.3e15 → 4.3e15 (already-confounded p-coordinate capture, 1DMIX-040, out of scope; negligible effect) |
| `isomip` (`ALLOW_SHELFICE`) | 1e-3 ≠ 5e-5 | 17109/1,437,204 → 17934/1,437,204 (179 improved, 1004 regressed) | 246 → 2.33 |

`visc_az`/`diff_kz`/`mixing_length` are byte-for-byte identical before vs.
after in **every one of these 5 captures** — confirming the fix's scope is
exactly as narrow as intended (only the buoyancy term's own internal
quantity changed; every diagnostic output is untouched).

`vermix` and `1D_ocean_ice_column` show unambiguous, zero-regression
improvement (every previously-mismatching cell improves; nothing crosses the
other way). `global_ocean.90x40x15`/`global_ocean.cs32x15` are unaffected (as
expected: `viscAz=diffKzS=0` there, so `kappa_h_tendency` and `kappa_h`
coincide exactly, and `cs32x15`'s already-known p-coordinate confound,
1DMIX-040, swamps any residual effect regardless). `isomip` is the one
genuinely mixed result — investigated in the status table's own `isomip` row
above (not glossed over here): worst-case magnitude improves by two orders of
magnitude, but the >1%-mismatch *count* rises slightly (+825 cells, 0.06
percentage points), concentrated (95%) at cells exactly 2 grid levels below
each ShelfIce column's own `kSrf` and directly attributable — via a per-cell
probe confirming `kappa_m`/Prandtl/`N²` all match MITgcm exactly there — to
the coupled implicit TKE solve interacting with the *already-open*,
*already-documented* near-`kSrf` residual 1DMIX-038 itself describes as
"not-yet-fully-traced", not to any defect in this fix.

**Correcting 1DMIX-041's own side-investigation**: that issue concluded the
buoyancy-term bug does **not** explain `vermix`'s long-standing 2/520
`tke_after` residual, because at those 2 cells the raw turbulent value
already exceeded both background floors (so `KappaM/Prandtl` and the exported
`kappa_h` coincided there numerically) — a correct statement about those 2
cells *in isolation*, verified again above (substituting one value for the
other at only those 2 cells, with everything else unchanged, still makes no
difference). What that single-point substitution test could not detect: the
real fix changes `kappa_h_tendency` at **every** quiescent level throughout
the column simultaneously, and the coupled implicit TKE solve (the
tridiagonal system's off-diagonal `KappaE` coupling between adjacent levels)
propagates those other levels' corrections into cells whose own local
buoyancy term was already exact — which is exactly what resolves `vermix`'s
2 previously-unexplained cells once the fix is applied end-to-end rather than
hand-substituted at a single point. `vermix`'s residual is therefore now
resolved by 1DMIX-048, not separately unexplained.

## Known gaps

- `bo`'s raw-flux-reproduction validation still shows elevated relative error specifically for experiments using climatological surface restoring (`tauThetaClimRelax`/`tauSaltClimRelax`, e.g. `global_oce_latlon`) — `external_forcing_surf.F`'s `FORCING_SURF_RELAX` contribution isn't captured/replicated in the raw-flux pipeline (1DMIX-022's root cause 2). Diagnostic-only now (doesn't affect mixing coefficients), not fixed at the formula level; low priority.
- `1D_ocean_ice_column`, `lab_sea`, `vermix`, and now `global_oce_latlon` have real captured data. The `lab_sea` 6-month run (`input_6mo`/`output_6mo`) is fully complete on both the MITgcm-capture and Python-replay sides (see the status table above and 1DMIX-019's addendum).
- The 6 idealized scenarios are now run through **both** standalone drivers (KPP: 1DMIX-023, resolved; GGL90: 1DMIX-041, found the bug; 1DMIX-048, fixed and verified) — see the "GGL90 standalone driver" section above.
- Other MITgcm verification experiments that enable KPP or GGL90: `seaice_obcs`, `isomip`, `global_ocean.90x40x15`, and `global_ocean.cs32x15` are now all captured/compared (see the table above and 1DMIX-025/1DMIX-034/1DMIX-038/1DMIX-040 for real findings from each) — this issue's original survey scope is now fully closed. `tutorial_tracer_adjsens` is out of scope entirely (`useKPP=.FALSE.` in both its input decks, confirmed no GGL90 either).
- `isomip`'s real `ALLOW_SHELFICE` capture found a genuine GGL90-port surface-boundary-condition defect (the port's index-0 "no diffusive flux" convention doesn't hold at a ShelfIce-shifted `kSrf>0`) — see **1DMIX-038** (open, `kind: scientific_change`).
- `global_ocean.cs32x15`'s real `usingPCoords` (pressure-coordinate) capture found this port has **no pressure-coordinate support at all** (silently produces mixing-length/diffusivity values wrong by up to ~4 orders of magnitude, not an error) — a substantial-scope question (implement real `coordFac` support vs. declare p-coordinate configs out of scope), plus a smaller, related `calc_mean_vert_shear` dead-placeholder finding (declared/mapped from the real MITgcm parameter, never actually read by any physics function) — see **1DMIX-040** (open).
- ~~GGL90's TKE buoyancy term uses the wrong `KappaH` whenever `background_visc != background_diff`~~ — **fixed and verified, 1DMIX-048** (found under 1DMIX-041); see the "GGL90 standalone driver" section above. Pending Richard's required independent review (`scientific_change`) before this issue closes. One real, investigated side effect surfaced while checking every existing capture: `isomip`'s already-open near-`kSrf` `tke_after` residual (1DMIX-038) gets slightly more visible in mismatch *count* (not magnitude) once the buoyancy term is corrected — see the `isomip` row in the status table above; logged as additional 1DMIX-038 evidence, not a new issue.
