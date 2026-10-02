# KPP standalone-driver 6-scenario validation summary

Generated: 2026-09-28T04:04:11Z

Compares the real Fortran `KPPMIX` standalone driver (`mitgcm_verification_mods/kpp_standalone_driver/`) against the Python KPP port, one idealized scenario at a time -- a genuinely different comparison shape from the MITgcm-capture reports (`generate_kpp_validation_report.py`): Fortran-standalone-driver text output vs. Python port, not MITgcm-capture NetCDF vs. Python port, so this is a markdown table rather than a PDF forced into that generator's NetCDF-shaped structure (1DMIX-053, closing the KPP/GGL90 report asymmetry left by 1DMIX-051's GGL90-only report; see `open_issues.md`/`closed_issues.md`).

Every number below comes directly from `compare_scenario_standalone.py::compare` (1DMIX-023's own established per-scenario comparison, which as of 1DMIX-053 shares `compare_scenario_ggl90_standalone.py::summarize` with the GGL90 report -- same statistic function, both schemes) -- no comparison logic is reimplemented in this report generator.

`max_rel = max(|Fortran - Python| / max(|Fortran|, 1e-12))` over all cells; `frac_gt_1pct` is the fraction of cells with relative error > 1%.

## `calm_baseline` (n_out=48, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 2.168e-18 | 0.000e+00 | 4.337e-19 | 2.089e-15 | 0.0000% | 0/2400 |
| diff_kz_s (K_h, salt) [m^2/s] | 3.469e-18 | 0.000e+00 | 8.674e-19 | 2.274e-15 | 0.0000% | 0/2400 |
| diff_kz_t (K_h, temp) [m^2/s] | 3.469e-18 | 0.000e+00 | 8.674e-19 | 2.274e-15 | 0.0000% | 0/2400 |
| ghat (non-local flux term) [s/m^2] | 1.705e-13 | 0.000e+00 | 5.684e-14 | 9.683e-16 | 0.0000% | 0/2400 |
| hbl (boundary layer depth) [m] | 5.329e-15 | 2.665e-15 | 5.329e-15 | 3.745e-16 | 0.0000% | 0/48 |

## `arctic_convection` (n_out=50, nz=23)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 1.388e-17 | 0.000e+00 | 3.469e-18 | 5.062e-16 | 0.0000% | 0/1150 |
| diff_kz_s (K_h, salt) [m^2/s] | 2.082e-17 | 0.000e+00 | 3.469e-18 | 1.211e-15 | 0.0000% | 0/1150 |
| diff_kz_t (K_h, temp) [m^2/s] | 2.082e-17 | 0.000e+00 | 3.469e-18 | 1.211e-15 | 0.0000% | 0/1150 |
| ghat (non-local flux term) [s/m^2] | 1.421e-14 | 0.000e+00 | 7.105e-15 | 4.682e-16 | 0.0000% | 0/1150 |
| hbl (boundary layer depth) [m] | 7.105e-15 | 0.000e+00 | 7.105e-15 | 2.018e-16 | 0.0000% | 0/50 |

## `hurricane_wind` (n_out=24, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 5.551e-17 | 0.000e+00 | 5.551e-17 | 4.497e-16 | 0.0000% | 0/1200 |
| diff_kz_s (K_h, salt) [m^2/s] | 6.106e-16 | 0.000e+00 | 5.551e-17 | 1.242e-15 | 0.0000% | 0/1200 |
| diff_kz_t (K_h, temp) [m^2/s] | 6.106e-16 | 0.000e+00 | 5.551e-17 | 1.242e-15 | 0.0000% | 0/1200 |
| ghat (non-local flux term) [s/m^2] | 1.776e-15 | 1.110e-16 | 8.882e-16 | 4.946e-16 | 0.0000% | 0/1200 |
| hbl (boundary layer depth) [m] | 5.684e-14 | 0.000e+00 | 4.050e-14 | 3.838e-16 | 0.0000% | 0/24 |

## `tropical_heating_diurnal` (n_out=24, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 1.355e-20 | 0.000e+00 | 0.000e+00 | 2.098e-16 | 0.0000% | 0/1200 |
| diff_kz_s (K_h, salt) [m^2/s] | 6.776e-21 | 0.000e+00 | 0.000e+00 | 2.589e-16 | 0.0000% | 0/1200 |
| diff_kz_t (K_h, temp) [m^2/s] | 6.776e-21 | 0.000e+00 | 0.000e+00 | 2.589e-16 | 0.0000% | 0/1200 |
| ghat (non-local flux term) [s/m^2] | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.0000% | 0/1200 |
| hbl (boundary layer depth) [m] | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.0000% | 0/24 |

## `heavy_rain_freshening` (n_out=24, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 1.301e-18 | 0.000e+00 | 0.000e+00 | 5.313e-16 | 0.0000% | 0/1200 |
| diff_kz_s (K_h, salt) [m^2/s] | 8.674e-19 | 0.000e+00 | 3.388e-21 | 5.081e-16 | 0.0000% | 0/1200 |
| diff_kz_t (K_h, temp) [m^2/s] | 8.674e-19 | 0.000e+00 | 3.388e-21 | 5.081e-16 | 0.0000% | 0/1200 |
| ghat (non-local flux term) [s/m^2] | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.0000% | 0/1200 |
| hbl (boundary layer depth) [m] | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.000e+00 | 0.0000% | 0/24 |

## `combined_storm` (n_out=12, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 3.064e-02 | 1.070e-03 | 2.715e-02 | 2.159e-01 | 45.0000% | 270/600 |
| diff_kz_s (K_h, salt) [m^2/s] | 6.141e-02 | 2.091e-03 | 5.421e-02 | 2.050e-01 | 51.3333% | 308/600 |
| diff_kz_t (K_h, temp) [m^2/s] | 6.141e-02 | 2.091e-03 | 5.421e-02 | 2.050e-01 | 51.3333% | 308/600 |
| ghat (non-local flux term) [s/m^2] | 9.053e-01 | 1.798e-02 | 5.070e-02 | 9.053e+11 | 51.1667% | 307/600 |
| hbl (boundary layer depth) [m] | 3.186e-01 | 3.499e-02 | 2.883e-01 | 9.397e-04 | 0.0000% | 0/12 |

## Summary

- Worst `max_rel` across all scenarios/fields: 9.053e+11
- Total cells with >1% relative error, all scenarios/fields combined: 1193/31182
- Status: NEEDS REVIEW -- see per-scenario tables above for the affected field(s)/scenario(s).

**`calm_baseline`/`arctic_convection`/`hurricane_wind`/`tropical_heating_diurnal`/`heavy_rain_freshening`** match to floating-point roundoff (worst `max_rel` ~2.3e-15, 0 cells >1% anywhere in these 5 scenarios).

**`combined_storm` does not** -- and the discrepancy is real and larger than the pre-1DMIX-053 comparison (which only ever computed max/mean absolute difference for KPP, never percentiles or relative error) had quantified: 45-51% of cells exceed 1% relative error in `visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat` (max_abs up to 6.1e-02 m^2/s), not just `hbl`.

**Measured, not inferred by consistency (1DMIX-056):** the prior wording above attributed this to `hbl`'s own small absolute difference (0.32 m) propagating through the boundary-layer shape function -- a plausible mechanism, never actually tested. It was tested directly: substituting the real Fortran `KPPMIX`'s own `hbl` at each timestep into the Python port (`MITgcm_to_Python_port_verification/scripts/kpp_hbl_substitution_experiment.py::run_experiment`) leaves the disagreement almost completely intact -- `visc_az` `n_gt_1pct` moves only 270->261/600, `max_abs` is unchanged (3.064e-02), `diff_kz_s`/`diff_kz_t` move 308->306/600. **`hbl` is not the (or at least not the dominant) mechanism.**

Root-causing the surviving residual (the mismatching cells concentrate where `sigma*hbl*bfsfc` is most negative, growing smoothly with depth/time rather than clustering at `hbl`) identified the actual mechanism: `Vertical_Mixing_Models/KPP/kpp_routines.py::wscale`'s own pre-existing `keep_mitgcm_bugs` validation-mode switch (kpp_routines.F:980 vs. the commented-out :990 Sidorenko fix; see `possible_kpp_bugs_in_mitgcm.md`, "Issue 2"). The Python port's default (`keep_mitgcm_bugs=False`) deliberately clamps the `wscale` lookup-table extrapolation; the real, unmodified Fortran `KPPMIX` this standalone driver actually compiles and runs has no such clamp. Instrumenting `wscale()` directly across all 6 scenarios (Richard, round 2) shows the clamp-differentiating negative-`zdiff` branch is technically *entered* by two of the other five as well -- `arctic_convection` (25/2350 within-boundary-layer evaluation points) and `hurricane_wind` (277/2424) -- but A/B-toggling `keep_mitgcm_bugs` on the real pipeline for all 6 scenarios produces zero measurable change for any of the 5 calmer scenarios (identical to displayed floating-point precision) and only `combined_storm`'s excursion is large enough for the clamp-vs-no-clamp difference to change the measured result. Setting `keep_mitgcm_bugs=True` for `combined_storm` (`run_all_variants()`'s `keep_mitgcm_bugs` key, no `hbl` override needed at all) collapses `hbl` itself to floating-point roundoff (max_abs 2.8e-14 m, same order as the other 5 scenarios) and drops `visc_az`/`diff_kz_s`/`diff_kz_t`'s `n_gt_1pct` from 270-308/600 to 2-4/600. The previously-reported 0.32 m `hbl` residual was itself a downstream *symptom* of this same `wscale` difference (`wscale` feeds `diagnose_bl_depth`'s own Rib/bfsfc search), not an independent `hbl` defect.

**A small residual remained with `keep_mitgcm_bugs=True` (explained and removed by 1DMIX-075, next paragraph)**: 2-4 of 600 cells per field (0.3-0.7%), confined to the two deepest grid cells (k=48,49 of 50) at the two timesteps where the boundary layer has deepened to the full column (`kbl==nz`) -- not further root-caused in this issue (1DMIX-056); a candidate follow-up. This is a measured investigation finding, not a fix: `keep_mitgcm_bugs` already existed (default `False`) before 1DMIX-056 and is unchanged by it; no port default was altered, and no tolerance here was widened to absorb the disagreement.

**1DMIX-075 (2026-10-02) explained and removed that residual.** At those timesteps the boundary layer fills the column and MITgcm's `bldepth` leaves `kbl = kmtj = Nr` (`kpp_routines.F:807`, `:818-824`: `kmtj` is both the "not found" value and a legitimate result, and with no dry level below the scan never moves it); the port's "none found" value was `nz` (one past the bottom level), which changed `blmix`'s matching level, skipped `enhance` and kept `ghat` at the bottom level, where MITgcm zeroes it. The port now returns `kbl = Nr` (0-based `nz-1`) and, as MITgcm does after `Ri_iwmix` (`kpp_routines.F:208`), zeroes the bottom interior coefficients before `blmix` reads them. Re-running the port on the stored `combined_storm` diagnostics (`scripts/kpp_hbl_substitution_experiment.py::run_variant`, `keep_mitgcm_bugs=True`) against the same standalone-Fortran output: `visc_az` 4 -> 0 of 600 cells above 1% (`max_abs` 2.7e-3 -> 0.0), `diff_kz_s`/`diff_kz_t` 2 -> 0 (2.7e-3 -> 0.0), `ghat` 3 -> 0 (0.858 -> 0.0), `hbl` 0 -> 0: bit-exact against the real Fortran `KPPMIX`. The other five scenarios are unchanged (worst `max_abs` <= 8.5e-14). The `.npz`/`.txt` data under `outputs_from_python_standalone/` were NOT regenerated (the Fortran driver needs `gfortran`, absent on this host), so the tables of this report, which read those files, still show the numbers of the Python run that produced them; the re-evaluation above is the current state of the port against that Fortran output. In the scenario runs themselves (`main/run_scenarios.py`) only `combined_storm`'s KPP output changes, from the output time at which `hbl` first equals the column depth (3 of 12 output times, 147 of 600 `visc_az` cells, largest change 2.8e-3 m^2/s, then the state by feedback).

`ghat`'s own `max_rel` in `combined_storm` (9.05e+11) is an artifact of this report's relative-error formula flooring a near-zero Fortran reference value at 1e-12, not a near-total mismatch in absolute terms (`max_abs` there is 0.905, the same order of magnitude as the field's own active-mixing range) -- treat `max_abs`/`median_abs`/`p95_abs` as the meaningful statistics for near-zero-reference fields; this is the same known property of the shared `summarize()` relative-error formula visible elsewhere in this project's reports (e.g. `global_ocean.cs32x15`'s reported 4.3e15).

## Reproducibility

Data source: `KPP_port_validation/outputs_from_python_standalone/<scenario>/{kpp_experiment.npz,kpp_standalone_output.txt}` (permanentized 1DMIX-053; see `CONVENTIONS_STANDALONE_DATA.md` in this directory for provenance and how to regenerate from scratch). Rerunning this script against unchanged on-disk artifacts reproduces byte-identical numbers -- not cached or hand-copied from a prior run.
