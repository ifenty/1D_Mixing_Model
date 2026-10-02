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
per experiment, and the plain-terms causal mechanism behind every real
discrepancy — see the two per-scheme reports:
[`KPP_port_validation/KPP_VALIDATION_RESULTS.md`](KPP_port_validation/KPP_VALIDATION_RESULTS.md)
and
[`GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`](GGL90_port_validation/GGL90_VALIDATION_RESULTS.md).
This README keeps the compact status table below; those two documents are
the deep dive a newcomer should read to actually understand the results.

## Directory guide

| Path | What it is |
|---|---|
| `scripts/` | The active comparison pipeline (parse MITgcm STDOUT → replay through the Python port → report). See `scripts/README.md`. |
| `mitgcm_verification_mods/` | This project's own MITgcm instrumentation (Fortran mods that dump validation data), one subdirectory per MITgcm verification experiment (`1D_ocean_ice_column/`, `lab_sea/`, `vermix/`), plus `kpp_mods/`/`ggl90_mods/` (the maintained source of truth, symlinked/copied into each experiment's `code_validation/`). Git-tracked, actively maintained — see its own `README.md`. |
| `mitgcm_verification_mods/kpp_standalone_driver/` | Standalone-subroutine harness that calls MITgcm's real `KPPMIX` directly (no full model) — step (2) of the three-way method, KPP only. Auto-detects grid size (`Nr`) from the input file, so it works for both real MITgcm captures (via `scripts/export_kpp_input_for_fortran.py`) and the idealized Python-port scenarios (via `scripts/export_scenario_to_fortran.py`, `scripts/compare_scenario_standalone.py`). |
| `KPP_port_validation/`, `GGL90_port_validation/` | Captured data (`inputs_from_mitgcm/`, `outputs_from_mitgcm/`, `outputs_from_python/`, gitignored `*.nc`) and format docs (`NETCDF_DATA_FORMAT.md`). Each holds its own standalone `{KPP,GGL90}_VALIDATION_RESULTS.md` narrative report (see above) and its own `CAPTURES.md` manifest, stating, for every experiment with more than one versioned capture, which file is current and why older ones are retained. Each also has a `reports/` directory holding generated PDF/markdown reports (`KPP_port_validation/reports/` additionally keeps two lessons-learned docs, `critical_lessons_fortran_to_python_porting.md`/`possible_kpp_bugs_in_mitgcm.md`) and its own gitignored `inputs_from_python_standalone/`/`outputs_from_python_standalone/` subdirectories holding the idealized-scenario standalone-driver data (see each directory's own `CONVENTIONS_STANDALONE_DATA.md` for provenance/regeneration). `KPP_port_validation/scripts/` (one ad hoc stats tool, `compute_validation_statistics.py`), `archive_2026-08-investigation/` (material explicitly disclaimed as superseded — read `closed_issues.md` for the current, accurate history, not those archived documents) and `SIMPLIFIED_API_SUMMARY.md` are KPP-only extras with no GGL90 counterpart. |
| `tests/` | Root-level pytest suite. `test_kpp_mitgcm_validation.py` runs real assertions against `run_python_kpp_on_dataset` for `1D_ocean_ice_column` and `lab_sea`. `test_kpp_mitgcm_validation_extended.py` extends KPP coverage to the 11,000-timestep `1D_ocean_ice_column` run, the 6-month `lab_sea` run, `seaice_obcs` (salt-plume), and `global_oce_latlon` (multi-tile, seasonally-complete). `test_ggl90_mitgcm_validation.py` is the GGL90 equivalent: real MITgcm-comparison regression assertions against `run_ggl90_from_netcdf_input.py::run` for `vermix`, `1D_ocean_ice_column` (11,000 timesteps), `isomip` (`ALLOW_SHELFICE`), `global_ocean_90x40x15` (IDEMIX) and `global_ocean_cs32x15` (pressure-coordinate, permanently out of scope: since 1DMIX-073 the port rejects its geometry with a `ValueError`, so the test asserts the rejection plus the MITgcm-side facts, no port replay). See the two per-scheme reports above for what each bounded gap means physically. |

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
#  comparing visc_az/diff_kz/mixing_length/tke_after instead of
#  KPP's hbl/visc_az/diff_kz_s/diff_kz_t/ghat)
```

`run_kpp_from_netcdf_input.py`/`run_ggl90_from_netcdf_input.py` both require
`PYTHONPATH` (or an equivalent `sys.path` insert) pointing at
`Vertical_Mixing_Models/`, since the two repos were split apart during a
2026-09-18 reorganization and several scripts still have a stale hardcoded
path — work around it with `PYTHONPATH` rather than editing the script, unless
you're specifically fixing that path issue as its own piece of work.

## Current validation status

One line per tested experiment; see the linked report for the quantified
result and causal mechanism behind any real discrepancy.

| Experiment | Scheme | Status |
|---|---|---|
| `1D_ocean_ice_column`, 10 timesteps | KPP | Excellent agreement — max `hbl` diff 1.3 cm. |
| `1D_ocean_ice_column`, 11,000 timesteps | KPP | This project's best KPP agreement; a small `hbl` tail from the Rib/Ricr threshold-sensitivity mechanism. |
| `lab_sea`, 999 timesteps (41 days) | KPP | First multi-column, real-bathymetry KPP capture; sub-centimetre typical `hbl` agreement. |
| `lab_sea`, 6-month run | KPP | Longest KPP temporal duration tested; same Rib/Ricr tail, wider at this longer scale. |
| `seaice_obcs` | KPP | Only salt-plume capture; the haline surface-buoyancy term is implemented and matches. |
| `global_oce_latlon`, 720 timesteps | KPP | Only multi-tile, seasonally-complete capture; agreement measurably tightened by this port's `wscale`-clamp default. |
| 6 idealized scenarios, standalone Fortran driver | KPP | 5 of 6 match to floating-point roundoff; `combined_storm`'s residual is explained by the same `wscale` mechanism. |
| `vermix`, 20 timesteps | GGL90 | Baseline single-column capture; every field agrees well within this project's 1% clean bar (max rel. error 0.07%-0.31%). |
| `1D_ocean_ice_column`, 11,000 timesteps (`mxlMaxFlag=3`) | GGL90 | This project's cleanest GGL90 experiment; exact to floating-point roundoff. |
| `isomip` | GGL90 | Only `ALLOW_SHELFICE` capture; a real, bounded residual near the ice-shelf-shifted surface level. |
| `global_ocean.90x40x15` | GGL90 | Clean z-coordinate IDEMIX capture; a decisively quantified missing-physics gap, not a port defect. |
| `global_ocean.cs32x15` | GGL90 | Pressure-coordinate configuration, permanently out of scope: the port rejects its geometry with a `ValueError` (1DMIX-073; it previously returned finite wrong values), so the capture is tested MITgcm-side plus a rejection test. |
| 6 idealized scenarios, standalone Fortran driver | GGL90 | All 4 fields, all 6 scenarios match to floating-point roundoff. |

Always check `open_issues.md`/`closed_issues.md` for the current, complete
picture — the table above is a snapshot, not a substitute.
