# GGL90 standalone-driver 6-scenario validation summary

Generated: 2026-09-27T15:58:13Z

Compares the real Fortran `GGL90_CALC` standalone driver (`mitgcm_verification_mods/ggl90_standalone_driver/`) against the Python GGL90 port, one idealized scenario at a time -- a genuinely different comparison shape from the 10 MITgcm-capture reports (`generate_ggl90_validation_report.py`, 1DMIX-044): Fortran-standalone-driver text output vs. Python port, not MITgcm-capture NetCDF vs. Python port, so this is a markdown table rather than a PDF forced into that generator's NetCDF-shaped structure (1DMIX-051, split from 1DMIX-044; see `open_issues.md`/`closed_issues.md` for the full scope-split rationale).

Every number below comes directly from `compare_scenario_ggl90_standalone.py::compare` (1DMIX-024/1DMIX-041's own established per-scenario comparison) -- no comparison logic is reimplemented in this report generator.

`max_rel = max(|Python - Fortran| / max(|Fortran|, 1e-12))` over all wet cells; `frac_gt_1pct` is the fraction of cells with relative error > 1%. `tke_after` compares the Fortran driver's `tke_after[i]` against the Python port's `tke[i+1]` (index-shifted by one timestep -- see `compare_scenario_ggl90_standalone.py` module docstring for the derivation).

## `calm_baseline` (n_out=288, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 1.055e-15 | 0.000e+00 | 5.551e-17 | 3.987e-15 | 0.0000% | 0/14400 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 1.076e-16 | 0.000e+00 | 5.551e-17 | 4.182e-15 | 0.0000% | 0/14400 |
| mixing_length (L) [m] | 1.194e-12 | 1.735e-18 | 2.109e-15 | 4.048e-15 | 0.0000% | 0/14400 |
| tke_after [m^2/s^2] | 7.589e-19 | 0.000e+00 | 1.762e-19 | 8.775e-14 | 0.0000% | 0/14400 |

## `arctic_convection` (n_out=5000, nz=23)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 2.220e-15 | 0.000e+00 | 6.939e-17 | 4.300e-15 | 0.0000% | 0/115000 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 6.384e-16 | 0.000e+00 | 5.378e-17 | 4.823e-15 | 0.0000% | 0/115000 |
| mixing_length (L) [m] | 1.137e-12 | 4.770e-18 | 3.908e-14 | 4.255e-15 | 0.0000% | 0/115000 |
| tke_after [m^2/s^2] | 2.168e-18 | 0.000e+00 | 1.247e-18 | 9.521e-13 | 0.0000% | 0/115000 |

## `hurricane_wind` (n_out=144, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 1.865e-14 | 7.286e-17 | 7.994e-15 | 4.143e-15 | 0.0000% | 0/7200 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 1.865e-14 | 5.551e-17 | 5.107e-15 | 4.645e-15 | 0.0000% | 0/7200 |
| mixing_length (L) [m] | 1.478e-12 | 1.066e-14 | 6.253e-13 | 4.124e-15 | 0.0000% | 0/7200 |
| tke_after [m^2/s^2] | 4.441e-16 | 8.674e-18 | 6.592e-17 | 1.388e-11 | 0.0000% | 0/7200 |

## `tropical_heating_diurnal` (n_out=144, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 2.776e-16 | 0.000e+00 | 8.674e-19 | 3.986e-15 | 0.0000% | 0/7200 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 2.776e-17 | 0.000e+00 | 9.487e-20 | 4.487e-15 | 0.0000% | 0/7200 |
| mixing_length (L) [m] | 1.421e-12 | 4.120e-18 | 2.047e-14 | 4.151e-15 | 0.0000% | 0/7200 |
| tke_after [m^2/s^2] | 1.084e-19 | 0.000e+00 | 4.659e-21 | 1.346e-13 | 0.0000% | 0/7200 |

## `heavy_rain_freshening` (n_out=144, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 9.021e-17 | 0.000e+00 | 1.572e-18 | 4.129e-15 | 0.0000% | 0/7200 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 1.084e-17 | 0.000e+00 | 6.505e-19 | 4.430e-15 | 0.0000% | 0/7200 |
| mixing_length (L) [m] | 1.251e-12 | 3.903e-18 | 3.109e-15 | 4.209e-15 | 0.0000% | 0/7200 |
| tke_after [m^2/s^2] | 1.561e-17 | 0.000e+00 | 1.328e-18 | 2.973e-14 | 0.0000% | 0/7200 |

## `combined_storm` (n_out=72, nz=50)

| Field | max_abs | median_abs | p95_abs | max_rel | frac >1% rel | n>1% / n_total |
|---|---|---|---|---|---|---|
| visc_az (K_m) [m^2/s] | 2.132e-14 | 4.441e-16 | 6.217e-15 | 4.177e-15 | 0.0000% | 0/3600 |
| diff_kz_s (K_h, == diff_kz_t) [m^2/s] | 1.155e-14 | 3.053e-16 | 4.441e-15 | 4.451e-15 | 0.0000% | 0/3600 |
| mixing_length (L) [m] | 1.421e-12 | 4.619e-14 | 7.404e-13 | 4.021e-15 | 0.0000% | 0/3600 |
| tke_after [m^2/s^2] | 1.554e-15 | 1.041e-17 | 6.072e-17 | 7.934e-14 | 0.0000% | 0/3600 |

## Summary

- Worst `max_rel` across all scenarios/fields: 1.388e-11
- Total cells with >1% relative error, all scenarios/fields combined: 0/618400
- Status: All 4 fields, all 6 scenarios, match to floating-point roundoff (worst max_rel ~1e-11, 0 cells >1% anywhere). `visc_az`/`diff_kz_s`/`mixing_length` were always exact (diagnostic formulas); `tke_after` (the one prognostic field) reached this state after 1DMIX-048's TKE-buoyancy-term fix -- see `closed_issues.md` 1DMIX-041/1DMIX-048 for the pre-fix numbers and root cause.

## Reproducibility

Data source: `Vertical_Mixing_Models/output/<scenario>/{ggl90_experiment_dense.npz,ggl90_standalone_output.txt}`. To regenerate from scratch for a given scenario: rerun `export_scenario_to_ggl90_driver.py <scenario>` (Python-port side) then `mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh <scenario>` (Fortran-driver side, well under a minute per scenario), then rerun this script -- the numbers above are computed fresh from whatever is currently on disk, not cached or hand-copied from a prior run.
