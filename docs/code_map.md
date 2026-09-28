# Developer code map

Python AST locations below were obtained with
`python3 tools/esx/orient.py --outline <file.py>`; they do not prove a dynamic
call graph — check imports/dispatch when asserting an actual dependency. YAML
configuration files are referenced as `<file>` (no `::<module>` suffix; use a
bounded source search for non-Python content).

## Pipeline

| Stage | Source and owning symbol | Input → output | Contract / nearest test |
|---|---|---|---|
| Scenario config loading | `Vertical_Mixing_Models/main/config_manager.py` | scenario YAML (`simulations/scenarios/`, `configuration_yamls/`) → physical/forcing/IC/time-integration dicts | `configuration_yamls/validate_yaml.py` |
| Column grid & state | `Vertical_Mixing_Models/main/column_grid.py::ColumnGrid`, `Vertical_Mixing_Models/main/column_state.py::ColumnState` | grid spec (`drF`) + initial conditions → discretized column arrays, MITgcm staggering | `Vertical_Mixing_Models/tests/test_staggering.py` |
| Equation of state | `Vertical_Mixing_Models/main/eos.py::jmd95_eos`, `::compute_buoyancy_gradients`, `::compute_ggl90_buoyancy_frequency_squared` | T, S, pressure → density anomaly, N² (potential-density convention) | `Vertical_Mixing_Models/tests/test_potential_density_gradient.py` |
| Shared physics basis | `Vertical_Mixing_Models/main/physics_basis.py::compute_buoyancy_frequency_squared`, `::compute_vertical_shear_squared`, `::compute_richardson_number` | ρ, u, v, z → N², S², Ri | `Vertical_Mixing_Models/tests/test_physics_basis.py` |
| Scheme dispatch | `Vertical_Mixing_Models/main/mixing_adapter.py::KPPAdapter.compute_mixing`, `::GGL90Adapter.compute_mixing` | `ColumnState` → `MixingOutput` (K_m, K_h, ...) | `Vertical_Mixing_Models/tests/test_cross_scheme_validation.py` |
| GGL90 core (prognostic TKE) | `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.step_tke_forward`, `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing` | N², S², surface forcing → TKE(t+dt), K_m, K_h | `Vertical_Mixing_Models/tests/test_cross_scheme_validation.py` (Python-only unit coverage); `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py` (root; real MITgcm-comparison regression coverage across vermix/1D_ocean_ice_column/isomip/global_ocean_90x40x15/global_ocean_cs32x15, issue 1DMIX-042); see `Vertical_Mixing_Models/docs/GGL90/GGL90_package_description.tex` |
| KPP core (diagnostic BL) | `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`, `::_compute_surface_forcing`, `::_compute_shear`, `::_estimate_reference_velocity` | N², S², surface forcing → hbl, K_m, K_h, ghat | `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py` (currently blocked at collection, open issue 1DMIX-010); `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py` (root; rewritten under 1DMIX-011 and confirmed passing — `4 passed`, not the stale "all-skip pending 1DMIX-010" this row previously claimed); `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py` (root; real MITgcm-comparison regression coverage extended to the 11,000-timestep `1D_ocean_ice_column` run, the 6-month/4368-timestep `lab_sea` run, and `seaice_obcs` (salt-plume, 1DMIX-034), issue 1DMIX-043 — 2 of these 3 captures were confirmed carrying the separately-tracked 1DMIX-035 `OUTPUT_MIXING` truncation defect and handled via an explicit clean-subset filter at that time; 1DMIX-050 (2026-09-27) rebuilt+reran both via Docker MITgcm against the already-fixed `kpp_calc.F`, replacing the two stale captures (0.0% truncated now, confirmed) and widening every test back to full, unfiltered coverage — the clean-subset filter is no longer needed anywhere in this file); `Vertical_Mixing_Models/tests/test_kpp_estimate_uref.py` (`KPP_ESTIMATE_UREF` branch, issue 1DMIX-032) |
| Time integration / driver | `Vertical_Mixing_Models/main/unified_driver.py::UnifiedColumnDriver.run_experiment`, `::_apply_vertical_diffusion`, `::_apply_convective_adjustment` | forcing + mixing coefficients → stepped `ColumnState` trajectory | `Vertical_Mixing_Models/tests/test_full_scenario_validation.py` |
| Diagnostics & serialization | `Vertical_Mixing_Models/main/diagnostics.py::DiagnosticsManager.save_snapshot`, `::get_diagnostics` | `ColumnState` trajectory → density/shear diagnostics, `.npz`/NetCDF | output under `Vertical_Mixing_Models/output/` (generated, git-ignored, not source-controlled) |
| Scenario CLI / plotting | `Vertical_Mixing_Models/main/run_scenarios.py`; `Vertical_Mixing_Models/main/unified_plotter.py::make_figures` | CLI args + scenario set → runs all scenarios, renders figures | `Vertical_Mixing_Models/user_guide.md` §"Running the built-in scenarios" |

## Verification routes

Focused/structural checks: `python3 tools/esx/verify.py --suite focused --owner <role>` and
`--suite structural`, both driven by `esx/project.json:verification`. The focused suite
currently runs `Vertical_Mixing_Models/tests` excluding `test_mitgcm_kpp_lab_sea_validation.py`
(blocked by missing `h5py`, open issue 1DMIX-010) — see `esx/project_profile.md` Runtime
section for the required `ecco` conda environment.

Independent oracle: MITgcm Fortran reference output. NetCDF inputs/outputs generated from
real MITgcm runs live under `MITgcm_to_Python_port_verification/KPP_port_validation/inputs_from_mitgcm/`
(declared in `esx/project.json:external_inputs`) and `MITgcm_to_Python_port_verification/KPP_port_validation/outputs_from_mitgcm/`.
Of these, the 11,000-timestep `1D_ocean_ice_column` run, the 6-month/4368-timestep `lab_sea`
run, `seaice_obcs` (salt-plume, 1DMIX-034) and `global_oce_latlon` (720-timestep, 4-tile,
regenerated fresh via Docker MITgcm under 1DMIX-049 after the original 1DMIX-027 capture was
lost in a disk-space rescue) are exercised by
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py` (issues
1DMIX-043, 1DMIX-049) via the same
`MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py::run_python_kpp_on_dataset`
entry point the original `test_kpp_mitgcm_validation.py` uses. `global_oce_latlon`'s own
Python-port replay is subsampled to the first 5 (of 720) timesteps at full (all wet columns)
spatial resolution — a full 720-timestep replay across all 2,315 wet columns is estimated at
~1.5 h serially (measured directly at ~2.2 ms/column-timestep on this capture) and remains a
separate, not-yet-scoped follow-up, not something this regression test attempts.
The GGL90 equivalent captures (vermix, 1D_ocean_ice_column, isomip, global_ocean_90x40x15,
global_ocean_cs32x15) live under `MITgcm_to_Python_port_verification/GGL90_port_validation/{inputs,outputs}_from_mitgcm/`
and are exercised by `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`
(issue 1DMIX-042) via `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py::run`.

The 6 idealized scenarios' GGL90 standalone-Fortran-driver comparison
(`MITgcm_to_Python_port_verification/scripts/compare_scenario_ggl90_standalone.py::compare`, issue 1DMIX-041/1DMIX-048 —
a different shape than the MITgcm-capture comparisons above: real Fortran
`GGL90_CALC` standalone driver output vs. Python port, no MITgcm-capture
NetCDF) has its own freshly-reproducible markdown report generator,
`MITgcm_to_Python_port_verification/scripts/generate_ggl90_scenario_report.py`
(issue 1DMIX-051, split from 1DMIX-044 since that PDF generator's NetCDF-shaped
structure doesn't fit this comparison), writing
`MITgcm_to_Python_port_verification/GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md`.

Freshly-dated (2026-09-27), quantified (median/p95/max abs and relative error, not just
pass/fail) PDF validation reports for every experiment above are generated by
`MITgcm_to_Python_port_verification/scripts/generate_kpp_validation_report.py` (KPP:
`hbl`/`visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat`) and its GGL90 counterpart
`MITgcm_to_Python_port_verification/scripts/generate_ggl90_validation_report.py`
(GGL90: `visc_az`/`diff_kz`/`mixing_length`/`tke_after`, issue 1DMIX-044) into
`MITgcm_to_Python_port_verification/KPP_port_validation/reports/` and
`MITgcm_to_Python_port_verification/GGL90_port_validation/reports/` respectively — both
directories are now structurally symmetric. The GGL90 generator reuses
`MITgcm_to_Python_port_verification/scripts/compare_ggl90.py`'s established
field-name/wet-mask (NaN-exclusion for a partially-wet column's
below-seafloor/above-ice-shelf padding, per
`MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py::run`'s
own truncation note) convention rather than reinventing it. Covers, per
report: the original 10-timestep `1D_ocean_ice_column` and
999-timestep `lab_sea` KPP captures, the 1DMIX-043 11,000-timestep
`1D_ocean_ice_column`/6-month `lab_sea` (first 100 of 4368 timesteps, matching
`test_kpp_mitgcm_validation_extended.py`'s own documented subsample — the full run's
222 MB chunked capture is impractical to re-replay on every report refresh)/`seaice_obcs`
KPP captures, and all 5 1DMIX-042 GGL90 captures.
`MITgcm_to_Python_port_verification/VALIDATION_RESULTS.md` (issue 1DMIX-045) is the
narrative synthesis of these reports plus the closed-issue history: per-scheme,
per-experiment what/why/result/root-cause, for a reader with no prior context.
`Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py` is the tightest oracle
(`rtol=1e-12, atol=1e-15`) once its dependency gap is resolved. Full qualification route:
`python3 tools/esx/final_verification.py run --review <packet> --owner <role>` per
`devel-loop/verification.md`, using `esx/project.json:verification.scientific`.

## Framework routes

| Responsibility | Owning operation |
|---|---|
| Project configuration and source signatures | `tools/esx/project.py::config`, `tools/esx/project.py::source_signature` |
| Issue selection and acceptance | `tools/esx/loop_gate.py::Gate.prepare`, `tools/esx/loop_gate.py::Gate.check_done` |
| Verification and reuse | `tools/esx/verify.py::run`, `tools/esx/verify.py::load_evidence` |
| Map navigation and documentation coverage | `tools/esx/doc_contract.py::navigate`, `tools/esx/doc_contract.py::validate_report` |
| Commit, notification and iteration history | `tools/esx/records.py::save_history` |
| Hook completion receipts | `tools/esx/hooks.py::capture` |

## Maintenance

Update stage ownership, input/output contracts and check routes when their source
changes. Keep line numbers out of manual tables; resolve them from live source.
A MAP-OK disposition explains which routes remain accurate for the actual patch.

## Review packet and runtime recovery

- `tools/esx/workflow_handoff.py::assemble` constructs explicit candidate/report/brief handoffs.
- `tools/esx/workflow_handoff.py::readiness` collects prerequisite failures without dispatching agents.
- `tools/esx/runtime_recovery.py::compatibility` checks canonical configuration and assessed transitions.
- `tools/esx/runtime_recovery.py::hook_doctor` attributes configured hooks without executing them.
- `tools/esx/doc_contract.py::validate_orientation` diagnoses the changed dependency slice.

The owning procedure is [Evidence handoff and recovery](../devel-loop/recovery.md).
