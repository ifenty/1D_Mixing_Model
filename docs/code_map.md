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
| GGL90 core (prognostic TKE) | `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.step_tke_forward`, `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing` | N², S², surface forcing → TKE(t+dt), K_m, K_h | `Vertical_Mixing_Models/tests/test_cross_scheme_validation.py`; see `Vertical_Mixing_Models/docs/GGL90/GGL90_package_description.tex` |
| KPP core (diagnostic BL) | `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`, `::_compute_surface_forcing`, `::_compute_shear` | N², S², surface forcing → hbl, K_m, K_h, ghat | `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py` (currently blocked at collection, open issue 1DMIX-010); `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py` (root; currently all-skip pending 1DMIX-010) |
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
