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
| Column grid & state | `Vertical_Mixing_Models/main/column_grid.py::ColumnGrid`, `Vertical_Mixing_Models/main/column_grid.py::validate_zcoordinate_geometry` (shared z-coordinate input guard of both schemes: `ValueError` for non-metres-scale geometry, 1DMIX-072/073; bounds in `::MAX_ZCOORD_EXTENT_M`), `Vertical_Mixing_Models/main/column_state.py::ColumnState` | grid spec (`drF`) + initial conditions → discretized column arrays, MITgcm staggering | `Vertical_Mixing_Models/tests/test_staggering.py`; `Vertical_Mixing_Models/tests/test_kpp_zcoordinate_guard.py`, `Vertical_Mixing_Models/tests/test_ggl90_zcoordinate_guard.py` (guard behaviour per scheme) |
| Equation of state | `Vertical_Mixing_Models/main/eos.py::jmd95_eos`, `::compute_buoyancy_gradients`, `::compute_ggl90_buoyancy_frequency_squared` | T, S, pressure → density anomaly, N² (potential-density convention; N² and `jmd95_eos` reproduce MITgcm's floating-point operation order, 1DMIX-068) | `Vertical_Mixing_Models/tests/test_potential_density_gradient.py`; `Vertical_Mixing_Models/tests/test_ggl90_n2_mitgcm_bit_order.py` (exact captured-MITgcm witnesses and bit-equality to an independent `find_rho.F`/`grad_sigma.F` reference) |
| Shared physics basis | `Vertical_Mixing_Models/main/physics_basis.py::compute_buoyancy_frequency_squared`, `::compute_vertical_shear_squared`, `::compute_richardson_number` | ρ, u, v, z → N², S², Ri | `Vertical_Mixing_Models/tests/test_physics_basis.py` |
| Scheme dispatch | `Vertical_Mixing_Models/main/mixing_adapter.py::KPPAdapter.compute_mixing`, `::GGL90Adapter.compute_mixing` | `ColumnState` → `MixingOutput` (K_m, K_h, ...) | `Vertical_Mixing_Models/tests/test_cross_scheme_validation.py` |
| GGL90 core (prognostic TKE) | `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.step_tke_forward`, `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing` (step 0 calls the shared input guard `Vertical_Mixing_Models/main/column_grid.py::validate_zcoordinate_geometry`, 1DMIX-073) | N², S², surface forcing → TKE(t+dt), K_m, K_h (`ValueError` for non-z-coordinate geometry, 1DMIX-073) | `Vertical_Mixing_Models/tests/test_cross_scheme_validation.py` (Python-only unit coverage); `Vertical_Mixing_Models/tests/test_ggl90_zcoordinate_guard.py` (guard, 1DMIX-073: Pa-scaled/positive/non-finite/non-positive-thickness columns raise, the 11,000 m boundary column passes, outputs on valid input bit-identical with and without the guard, adapter inherits it; the real `cs32x15` capture is asserted in the root GGL90 module below); `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py` (root; real MITgcm-comparison regression coverage across vermix/1D_ocean_ice_column/isomip/global_ocean_90x40x15/global_ocean_cs32x15, issue 1DMIX-042); see `Vertical_Mixing_Models/docs/GGL90/GGL90_package_description.tex` |
| KPP core (diagnostic BL) | `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing` (keyword-only optional `shsq_forcing`/`dvsq_forcing`/`dbloc_smooth_forcing`, default `None` = exact no-op, 1DMIX-071; keyword-only optional `depth_below`/`cell_thickness_below` = the dry model levels below a truncated column, default `None` = full-depth column, and MITgcm's `kbl` scan, zeroed bottom `diffus` and zero surface `diffus` entry, 1DMIX-075, `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py::diagnose_bl_depth`/`::compute_bl_mixing`/`::enhance_at_interface`; step 0 calls the shared input guard `Vertical_Mixing_Models/main/column_grid.py::validate_zcoordinate_geometry`, re-exported by this module), `::_compute_surface_forcing`, `::_compute_shear`, `::_estimate_reference_velocity` | N², S², surface forcing → hbl, K_m, K_h, ghat (`ValueError` for non-z-coordinate geometry, 1DMIX-072) | `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py` (currently blocked at collection, open issue 1DMIX-010); `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py` (root; rewritten under 1DMIX-011 and confirmed passing — `4 passed`, not the stale "all-skip pending 1DMIX-010" this row previously claimed); `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py` (root; real MITgcm-comparison regression coverage extended to the 11,000-timestep `1D_ocean_ice_column` run, the 6-month/4368-timestep `lab_sea` run, and `seaice_obcs` (salt-plume, 1DMIX-034), issue 1DMIX-043 — 2 of these 3 captures were confirmed carrying the separately-tracked 1DMIX-035 `OUTPUT_MIXING` truncation defect and handled via an explicit clean-subset filter at that time; 1DMIX-050 (2026-09-27) rebuilt+reran both via Docker MITgcm against the already-fixed `kpp_calc.F`, replacing the two stale captures (0.0% truncated now, confirmed) and widening every test back to full, unfiltered coverage — the clean-subset filter is no longer needed anywhere in this file); `Vertical_Mixing_Models/tests/test_kpp_estimate_uref.py` (`KPP_ESTIMATE_UREF` branch, issue 1DMIX-032); `Vertical_Mixing_Models/tests/test_kpp_tracer_point_inputs.py` (the three optional tracer-point inputs, issue 1DMIX-071: golden-digest proof that `None` is an exact no-op, own-values plumbing identity, validation); `Vertical_Mixing_Models/tests/test_kpp_levels_below.py` (issue 1DMIX-075: single-column witnesses with MITgcm capture values from `tests/data/kpp_075_witnesses.npz`, built by `MITgcm_to_Python_port_verification/scripts/make_kpp_075_witnesses.py`; golden digests for the interior-boundary-layer regime that must not change; the three MITgcm conventions in isolation; validation of `depth_below`/`cell_thickness_below`); `MITgcm_to_Python_port_verification/tests/test_tracer_point_inputs.py` (replay-side reconstruction vs the captured `vertical_shear`/`shear_sq`/`dVsq`, hand-computed `smooth_horiz`); `Vertical_Mixing_Models/tests/test_kpp_ghat_gate.py` (`use_ghat`/`KPP_GHAT` compute-vs-apply split, issue 1DMIX-058 — guards the `ghat` application-site gate in `Vertical_Mixing_Models/main/unified_driver.py::UnifiedColumnDriver._apply_vertical_diffusion`, a path the MITgcm-capture comparison above cannot exercise; also `::test_momentum_solve_never_receives_ghat`, issue 1DMIX-061 — spies on the `solve_diffusion_implicit` call arguments to guard that `ghat` never reaches the `u_vel`/`v_vel` momentum solve, matching MITgcm's `ghat` application being confined to `kpp_transport_t.F`/`kpp_transport_s.F`/`kpp_transport_ptr.F` with no momentum analogue; also `::test_momentum_invariant_to_ghat_value`, issue 1DMIX-063 — quantity-level complement: asserts `u_vel`/`v_vel` are exactly bit-identical when only `ghat` is varied, catching leak shapes (contaminated `visc_az`, post-hoc correction) that keep the `ghat=` keyword absent and so pass the call-level spy above — also `::test_real_pipeline_momentum_invariant_to_ghat`, issue 1DMIX-064 — first witness driving the real `KPPAdapter.compute_mixing` -> `_apply_vertical_diffusion` path (ghat varied at the KPPDriver->adapter boundary; exact `visc_az` and `u_vel`/`v_vel` invariance), catching adapter-side leaks the hand-built witnesses cannot see; see `docs/model_contract.md`'s "coverage of this invariant is two-layered" and "Real-pipeline witness" notes for which witness catches which route); `Vertical_Mixing_Models/tests/test_kpp_zcoordinate_guard.py` (`validate_zcoordinate_geometry` z-coordinate input guard, issue 1DMIX-072; moved to `main/column_grid.py` and shared with GGL90 under 1DMIX-073 — Pa-scaled/positive/non-finite/non-positive-thickness columns raise `ValueError`, the 11,000 m boundary column passes, and outputs on valid input are bit-identical with and without the guard; the real `cs32x15` capture geometry is asserted in the root extended module, see below); `Vertical_Mixing_Models/tests/test_kpp_doublediff_guard.py` (`use_doublediff`/`KPPuseDoubleDiff` unimplemented-option guard in `Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters.__post_init__`, issue 1DMIX-059 — `KPP_DOUBLEDIFF` has no code path anywhere in `Vertical_Mixing_Models/KPP/kpp_routines.py::ri_iwmix`; confirms `use_doublediff=True` raises `NotImplementedError` and `exclude_doublediff`/the default do not) |
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
global_ocean_cs32x15, and, from 1DMIX-054, lab_sea 999-step and 6-month) live under `MITgcm_to_Python_port_verification/GGL90_port_validation/{inputs,outputs}_from_mitgcm/`
and are exercised by `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`
(issue 1DMIX-042) via `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py::run`
(except `global_ocean_cs32x15`: since 1DMIX-073 the port rejects it, so that test module asserts the rejection and the
MITgcm-side facts only; see the 1DMIX-054 paragraph below).

**Capture route (1DMIX-065)**: an MITgcm `output.txt` becomes the `inputs_from_mitgcm/`/`outputs_from_mitgcm/`
NetCDF pair through `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py::parse_mitgcm_split` (KPP) or
`MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py::parse_mitgcm_ggl90_split_to_files` (GGL90); both are
thin specs on the shared streaming engine `MITgcm_to_Python_port_verification/scripts/capture_stream.py::stream_convert`,
which holds one timestep in memory (the previous whole-file parsers exhausted 27 GB on the 13.8 GB
`global_oce_latlon_720` capture); nearest test `MITgcm_to_Python_port_verification/tests/test_capture_stream_parsers.py`
(synthetic multi-tile files, never skips). Regenerating the gitignored captures/standalone sets on a new host is documented in
`MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md` ("Regenerated on WSL, 1DMIX-065") and the two
`CONVENTIONS_STANDALONE_DATA.md`; the standalone-driver `build_and_run.sh` scripts take `MITGCM_ROOT` from the environment.
The remaining test captures (the five GGL90 ones and KPP `lab_sea_6mo`/`seaice_obcs_1dmix034`) were regenerated the
same way under 1DMIX-066: recipes, per-file sha256 and the INFERRED labels (`lab_sea_6mo`'s `endTime` edit, the
`1D_ocean_ice_column` GGL90 namelist) are in `MITgcm_to_Python_port_verification/GGL90_port_validation/CAPTURES.md`
and `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md` ("Regenerated on WSL, 1DMIX-066"); the
streaming GGL90 parser was proven byte-identical to the pre-1DMIX-065 parser on the 36-tile and 12-tile captures.
Their 14 MITgcm-side files (inputs and outputs) and the three previously unlisted KPP `outputs_from_mitgcm` files
(`11k_1D`, `lab_sea_1000_0820T0946`, `1D_10_kppmix_extend_rawflux_fix`) are declared in `esx/project.json:external_inputs`
(47 entries then; 55 after 1DMIX-054), so their bytes are hashed into every verification receipt and their absence blocks instead of skipping;
the Python replay files are not, because the tests regenerate them.

**1DMIX-054 (cross-scheme captures, geometry-matched)**: the second mixing scheme was captured on three grids that
had only ever had one, with new `-mods` trees `mitgcm_verification_mods/global_ocean_90x40x15/kpp_code_validation/`,
`global_ocean_cs32x15/kpp_code_validation/` and `lab_sea/ggl90_code_validation/` (stock `code/` headers unmodified
except the listed package swap and, for lab_sea, its single-tile `SIZE.h`; instrumented `.F` files symlinked to
`kpp_mods/`/`ggl90_mods/` and declared in `esx/project.json:mirrored_paths`; every header/package difference is in
`mitgcm_verification_mods/README.md`). The run-input namelists are **constructed** (no stock MITgcm experiment has them;
`<scheme>_input_validation/` next to each tree, every non-stock value justified in its README; recipes R7/R8 in
`KPP_port_validation/CAPTURES.md`, G6/G7 in `GGL90_port_validation/CAPTURES.md`). Four permanent captures (8 MITgcm-side
files, `external_inputs` now 55 entries): KPP `global_ocean_90x40x15_10` (10 steps, 36 tiles, tested in
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`), KPP `global_ocean_cs32x15_pcoords_1`, GGL90 `lab_sea_999` and `lab_sea_6mo`
(tested in `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`;
`MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py::run` gained optional
`first_timestep`/`last_timestep` and now `.load()`s the selected inputs once). **The `cs32x15` KPP capture is a known-gap
characterization, not a validation** (pressure coordinates: MITgcm's `pkg/kpp` has no `coordFac`/`usingPCoords` handling,
its own run aborts at iteration 1, and the port returned NaN in 91% of interior cells before 1DMIX-072, so the "shared unit error gives a
close, misleading agreement" scenario anticipated by the issue occurred only for `ghat`; measured details in
`KPP_VALIDATION_RESULTS.md`). Since 1DMIX-072 the port has no replay of that capture: `KPPDriver.compute_mixing` raises `ValueError` on it
(`Vertical_Mixing_Models/main/column_grid.py::validate_zcoordinate_geometry`, re-exported by `kpp_core_driver.py`; nearest tests
`Vertical_Mixing_Models/tests/test_kpp_zcoordinate_guard.py` and
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py::test_global_ocean_cs32x15_port_rejects_pressure_coordinate_input`).
The GGL90 capture of the same experiment (`global_ocean_cs32x15_idemix_10`, recipe G4) is the same Pa grid and is likewise MITgcm-side evidence only
since 1DMIX-073: `GGL90Driver.compute_mixing` (which until then returned finite wrong values there) shares the guard, so
`MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py::run` raises on it (that script has no `except` clause, and in its default tracer-point mode it calls the same guard up front before its calcMeanVertShear check, so the geometry `ValueError` wins;
nearest test `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py::test_global_ocean_cs32x15_port_rejects_pressure_coordinate_input`; the last measured port-side
numbers are historical, in `GGL90_VALIDATION_RESULTS.md`/`CAPTURES.md`). **Replay inputs (1DMIX-071)**: MITgcm's KPP and GGL90 shear at a tracer point uses the `(i,i+1)`/`(j,j+1)` velocities
(and KPP's smoothed `shsq`/`dbloc` the 3x3 neighbourhood), which the replays used to replace by `uVel(i,j)`/`vVel(i,j)` only.
`MITgcm_to_Python_port_verification/scripts/tracer_point_inputs.py` now rebuilds them from the neighbouring captured columns
(periodic wrap; nearest test `MITgcm_to_Python_port_verification/tests/test_tracer_point_inputs.py`, which checks them against the
captured `vertical_shear`/`shear_sq`/`dVsq` in every edge class); the GGL90 replay feeds the averaged velocities, the KPP replay passes `shsq`/`dVsq`/smoothed `dbloc`
through `KPPDriver.compute_mixing`'s keyword-only `shsq_forcing`/`dvsq_forcing`/`dbloc_smooth_forcing` (default `None`, exact no-op; nearest test
`Vertical_Mixing_Models/tests/test_kpp_tracer_point_inputs.py`; contract in `docs/model_contract.md`). Both replays default to it
(`tracer_point_velocities`/`tracer_point_inputs`), keep the column-local mode as an option, and many "known gap" assertions of the two
root test modules were re-decided (artifact or real) on that evidence; see the GGL90 and KPP results documents.
**KPP dry levels below truncated columns (1DMIX-075)**: the KPP replay also hands `KPPDriver.compute_mixing` the model levels below each
truncated column (`depth_below`/`cell_thickness_below`, `MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py::_levels_below_kwargs`), because MITgcm's
`bldepth` scans `kbl` over all `Nr` levels (`kpp_routines.F:807,818-824`), ending at `kmtj+1` when the first level below `hbl` is the bottom
wet level; together with the zeroed bottom/surface interior coefficients (`:208`, `:1224-1228`) this removed the k=1 cells of the 610 two-wet-level
columns of `global_ocean_90x40x15` (456 -> 7 `visc_az` cells above 1%, 520 -> 27 `diff_kz`), 285 `ghat` cells where MITgcm is exactly 0 and the port was not, and
the `combined_storm` standalone-Fortran residual (now 0); contract in `docs/model_contract.md`, measurements in `KPP_VALIDATION_RESULTS.md`.

Both schemes also have a second, symmetric validation direction ("Direction B",
vs. "Direction A" for the MITgcm-capture comparisons above): a Python-port-driven
idealized scenario replayed directly through the real Fortran standalone-
subroutine driver (`mitgcm_verification_mods/{kpp,ggl90}_standalone_driver/`),
no MITgcm run involved at all. Per scheme: an exporter script reads/reruns the
Python port's own scenario output and writes the driver's flat-text input
(`MITgcm_to_Python_port_verification/scripts/export_scenario_to_fortran.py` for
KPP; `export_scenario_to_ggl90_driver.py` for GGL90, which also reruns the
scenario dense at `output_frequency_steps=1` in the same call); the driver's own
`build_and_run.sh` produces the paired text output; and the comparison function
reads both back —
`MITgcm_to_Python_port_verification/scripts/compare_scenario_standalone.py::compare`
(KPP, issue 1DMIX-023) and
`MITgcm_to_Python_port_verification/scripts/compare_scenario_ggl90_standalone.py::compare`
(GGL90, issue 1DMIX-041/1DMIX-048). As of 1DMIX-053 (when KPP's own
`compare()` was given a return value it previously lacked), both comparison
functions return the identical per-field statistic dict
(`max_abs`/`median_abs`/`p95_abs`/`max_rel`/`n_gt_1pct`/`n_total`) produced by
one shared, scheme-agnostic function,
`MITgcm_to_Python_port_verification/scripts/compare_scenario_ggl90_standalone.py::summarize`
— so both schemes' numbers mean literally the same thing, not just look alike.

All 6 scenarios' Direction-B data — previously living only in the scratch,
git-ignored `Vertical_Mixing_Models/output/<scenario>/` tree, where it had
already been silently lost and regenerated once — is permanentized (1DMIX-053)
under `MITgcm_to_Python_port_verification/KPP_port_validation/{inputs,outputs}_from_python_standalone/<scenario>/`
and `MITgcm_to_Python_port_verification/GGL90_port_validation/{inputs,outputs}_from_python_standalone/<scenario>/`
(driver-input `.txt` under `inputs_from_python_standalone/`; both the driver's
text output and the Python port's own `.npz` under `outputs_from_python_standalone/`,
since the `.npz` is an output of the comparison, not an input to the driver).
These directories are git-ignored (`.gitignore`, same treatment as Direction A's
`*.nc` captures — 108 MB of `.txt`/`.npz`, not pushed); the files each scheme's
comparison function actually reads are declared in
`esx/project.json:external_inputs` so their real bytes are hashed into every
verification receipt. Each scheme's own `CONVENTIONS_STANDALONE_DATA.md`
(`KPP_port_validation/CONVENTIONS_STANDALONE_DATA.md`,
`GGL90_port_validation/CONVENTIONS_STANDALONE_DATA.md`) states exactly which
script produced each file and how to regenerate it.

Each scheme has its own freshly-reproducible markdown report generator, reusing
its scheme's `compare()` unmodified with no comparison logic duplicated in
either generator:
`MITgcm_to_Python_port_verification/scripts/generate_kpp_scenario_report.py`
(issue 1DMIX-053) writing
`MITgcm_to_Python_port_verification/KPP_port_validation/reports/kpp_scenario_standalone_summary.md`,
and `MITgcm_to_Python_port_verification/scripts/generate_ggl90_scenario_report.py`
(issue 1DMIX-051, split from 1DMIX-044 since that PDF generator's NetCDF-shaped
structure doesn't fit this comparison) writing
`MITgcm_to_Python_port_verification/GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md`.
The KPP report (1DMIX-053) found a real, newly-quantified discrepancy in
`combined_storm` (45-51% of cells exceed 1% relative error in
`visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat` — not just the previously-documented
`hbl` residual). 1DMIX-056 measured, rather than inferred, the mechanism:
substituting the real Fortran `KPPMIX`'s own `hbl` into the Python port at
each `combined_storm` timestep (`MITgcm_to_Python_port_verification/scripts/
kpp_hbl_substitution_experiment.py`) left the coefficient disagreement almost
unchanged (`visc_az` `n_gt_1pct` 270→261/600), disproving the Rib/Ricr/`hbl`-
propagation attribution this paragraph previously stated. The actual cause is
`Vertical_Mixing_Models/KPP/kpp_routines.py::wscale`'s pre-existing `keep_mitgcm_bugs` switch
(`kpp_routines.F:980`'s unclamped lookup-table extrapolation vs. the
commented-out `:990` fix the port's default clamps to): two of the other 5
scenarios also technically enter the clamp-differentiating branch (measured;
see the report), but only `combined_storm`'s excursion is large enough for
the clamp-vs-no-clamp difference to change the result. Setting
`keep_mitgcm_bugs=True` (no `hbl` override needed) collapses
`hbl` to floating-point roundoff and the coefficient mismatch to 2-4/600
cells, confined to the deepest 2 cells at the 2 timesteps where `hbl` bottoms
out at the full column depth — a small residual left unexplained until 1DMIX-075,
which found it (MITgcm's "none found" `kbl` is `Nr`, `kpp_routines.F:807,818-824`, not the
port's former `nz`) and removed it: now exactly 0. See
`docs/model_contract.md`'s KPP section and the report itself for the full
numbers; the other 5 KPP scenarios and all 6 GGL90 scenarios match to
floating-point roundoff.

**Resolved (1DMIX-057)**: `Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters`'s
`keep_mitgcm_bugs` field now defaults to `True` (was `False`). Decided on measured evidence, not just
the idealized scenarios above: both full local suites (`Vertical_Mixing_Models/tests`,
`MITgcm_to_Python_port_verification/tests`) ran identically (`113 passed, 3 skipped`)
at `False` and at `True`, and directly instrumenting `wscale`'s clamp-differentiating
branch across this project's 4 real MITgcm captures showed 3 of them (`1D_ocean_ice_column`,
`lab_sea`, `seaice_obcs_1dmix034`) genuinely unaffected, but the 4th
(`global_oce_latlon_720`) measurably **improved**: flipping to `True` cut that
capture's own worst-case Python-vs-real-MITgcm disagreement roughly 3.5x-11x
(`hbl` max_abs 33.9 m → 3.09 m; `visc_az` 0.332 → 0.096 m²/s; `diff_kz_s`/`diff_kz_t`
0.959 → 0.110 m²/s), correcting the same Rib/Ricr-only mis-attribution this
paragraph's own `combined_storm` finding already corrected once. See
`docs/model_contract.md`'s KPP section for the full evidence and
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py::test_global_oce_latlon_hbl`/
`::test_global_oce_latlon_mixing` for the re-derived (tightened, not widened)
tolerances. `global_oce_latlon`'s own `ghat` mismatch is unchanged by this flag
either way (394/394 active cells >1% both settings) — a real, separate,
pre-existing defect this issue did not investigate, flagged for its own issue.

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
KPP captures, and the 1DMIX-042 GGL90 captures. The GGL90 `global_ocean_cs32x15_idemix_10` report
(`GGL90_port_validation/reports/ggl90_validation_global_ocean_cs32x15_idemix_10.pdf`) is a
**historical, pre-1DMIX-073 artefact**: the port now rejects that pressure-coordinate capture, so the
report's Python-side input cannot be regenerated (the other four 1DMIX-042 GGL90 reports can).
`MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`
and `MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`
are the per-scheme narrative synthesis of these reports: per-experiment
what/why/result/causal-mechanism, for a reader with no prior context.
`MITgcm_to_Python_port_verification/VALIDATION_RESULTS.md` is a short pointer to
both.
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
