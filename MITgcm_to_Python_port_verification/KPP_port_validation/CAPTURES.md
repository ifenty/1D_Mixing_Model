# Capture manifest — KPP_port_validation

Written under 1DMIX-046 to resolve "which versioned file is current" for every
experiment that has more than one capture on disk, and to document the two
oddly-located `_python.nc`-suffixed files (1DMIX-046 task 5). Experiments with
exactly one input/output/python-output set (`lab_sea_1000_0820T0946` — now single
after this issue removed its stray duplicate, see below —, `lab_sea_6mo`,
`seaice_obcs_1dmix034`, `global_oce_latlon_720`) need no entry beyond noting
that single-version status; `global_oce_latlon_720` gets one anyway below since
it is a brand-new capture (1DMIX-049) worth documenting at introduction.

## `global_oce_latlon_720` (720 timesteps, 4-tile 2×2 90×40×15, `global_oce_latlon` verification experiment)

Single version — regenerated fresh 2026-09-27 (1DMIX-049) after the original
1DMIX-027 capture was lost in a disk-space rescue; no superseded alternative
exists.

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_oce_latlon_720.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation_extended.py` (`DATA_GLOBAL_OCE_LATLON`), first 5 (of 720) timesteps replayed at full spatial resolution. |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_oce_latlon_720.nc` | **current** | Paired MITgcm output, same test. |

No `outputs_from_python/` file exists for this capture (only a bounded
5-timestep subsample was ever replayed through the Python port; a full
720-timestep replay, estimated ~1.5 h, remains a separate, not-yet-scoped
follow-up — see
`MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`'s
`global_oce_latlon` section).

## `1D_10` (10 timesteps, single column, `1D_ocean_ice_column` verification experiment)

UUIDs cross-checked directly (`input_uuid` in each output matches its own input's
`uuid`, 2026-09-27).

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | The capture `tests/test_kpp_mitgcm_validation.py` actually loads (`DATA_1D`). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | Paired MITgcm output for the above, same test. |
| `outputs_from_python/python_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | Regenerated 2026-09-27; the file `reports/kpp_validation_1D_ocean_ice_column_10.pdf` was built from (see `MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`'s Reproducibility section). |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend.nc` | superseded, retained | **Documented-buggy legacy capture** — `scripts/run_kpp_from_netcdf_input.py::derive_raw_flux_forcing`'s own docstring (1DMIX-013) states this capture's `q_net`/`fw_flux` columns are *not* real raw fluxes despite the name (they hold MITgcm's own already-converted `surfaceForcingT`/`surfaceForcingS`, a pre-fix `KPP_OUTPUT_VALIDATION` bug) — feeding them through the raw-flux formula double-applies the conversion. This is why `_rawflux_fix` was captured. No active test/script loads this file's data (the one reference is that explanatory comment, not a load path). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend.nc` | superseded, retained | Paired MITgcm output for the legacy capture above. No active reference. |
| `outputs_from_mitgcm_standalone/mitgcm_kpp_outputs_standalone_1D_10.nc` | superseded, retained | Standalone-Fortran-driver output (three-way method step 2) paired (by `input_uuid`) to the *legacy* `_kppmix_extend.nc` capture, not the current `_rawflux_fix` one — from the KPP standalone driver's original bring-up test (README's own status table, "`1D_ocean_ice_column` \| KPP standalone (step 2)" row, 1DMIX-012, resolved: exact match to floating-point roundoff). Not re-run against the corrected capture since 1DMIX-012 closed; no active script/test references this file by name. The raw-flux bug above affects `q_net`/`fw_flux` specifically, which the standalone driver never consumes (it calls `KPPMIX` directly with `ustar`/`bo`/`bosol`), so this historical result is not itself invalidated by that bug — it simply predates the fix and has not been re-verified against it. |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10.nc` | superseded, retained | Original 2026-08-19 capture, predates both later re-captures. No active reference; no paired output file exists for it (its would-be `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10.nc` was never kept). |
| `outputs_from_python/python_kpp_outputs_1D_10_precomputed_forcing.nc` | superseded, retained (orphaned) | A 2026-09-16 Python-port output for a *different*, one-off experiment (`input_file_name` attribute reads `mitgcm_kpp_inputs_precomputed_forcing_only.nc`, not any file above) whose own input capture is no longer present in this repo. Not part of the `1D_10` version family despite the shared filename prefix; not referenced by any active script/test. Kept rather than deleted only because its originating input can no longer be inspected to confirm it is safe to discard. |

## `11k_1D` (11,000 timesteps, single sea-ice-coupled column, `1D_ocean_ice_column`)

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation_extended.py` (`DATA_11K`) and by `KPP_port_validation/scripts/compute_validation_statistics.py` (as `mitgcm_file`'s sibling). Single version — no superseded alternative exists. |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | **current** | Paired MITgcm output, same test; also loaded directly by `compute_validation_statistics.py`. |
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | **current** | The standard-convention Python output the active test suite actually asserts against; source of `reports/kpp_validation_1D_ocean_ice_column_11000.pdf`. |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | **anomalous — retained, not "current"** (1DMIX-046 task 5) | **Investigated.** Despite its name and location (inside `inputs_from_mitgcm/`, not `outputs_from_python/`), this file's own embedded NetCDF metadata is unambiguous: `title="Python KPP Port Outputs"`, `source="Python KPP port"`, `description="KPP outputs from Python port using MITgcm inputs"` — it **is** a Python-port output, not an MITgcm input, mislocated by an earlier (2026-08-20) version of the pipeline that saved a `<input_basename>_python.nc` file alongside its input by default, before the current `outputs_from_python/python_kpp_outputs_<tag>.nc` convention existed (see `NETCDF_DATA_FORMAT.md`'s own now-corrected step-4 walkthrough, which still documents this exact historical behavior). It shares the real capture's `uuid` (provenance-verified). **Not deleted**: `KPP_port_validation/scripts/compute_validation_statistics.py` still opens this exact file by name as its `python_file`. It is listed in `esx/project.json:external_inputs` (mislabeled there as an "MITgcm-derived" input, which it is not — left as-is rather than edited further, since removing the file itself would require a coupled `project.json` edit, and this file, unlike the `lab_sea` one below, is not safe to delete). |

## `lab_sea_1000_0820T0946` (999-timestep, 20×16-grid `lab_sea` run — the "41-day" capture)

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation.py`. Single version now (see below). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_1000_0820T0946.nc` | **current** | Paired MITgcm output, same test. |
| `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc` | **current** | Standard-convention Python output the test asserts against; source of `reports/kpp_validation_lab_sea_999.pdf`. |
| ~~`inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946_python.nc`~~ | **deleted, 1DMIX-046 task 5** | Investigated and confirmed safe to delete (not merely "retained-with-uncertainty"): same "Python-port-output-mislocated-as-input" pattern as the `11k_1D` anomaly above (identical `title`/`source`/`description` metadata), but **also confirmed incomplete** — only 1 of the real capture's 999 timesteps (`dims: time=1` vs. the real input's `time=999`), i.e. an abandoned partial snapshot, not even a full early replay. Zero references anywhere in `{scripts,tests}` (grep-confirmed). It **was** listed in `esx/project.json:external_inputs`; that entry was removed in the same patch so the environment probe's required-file hash check (`tools/esx/project.py::environment`) does not fail on the now-deleted file. Not git-tracked (gitignored `*.nc`), so no history is lost by deleting outright either way. |

## Standalone-driver outputs and `outputs_from_python` general note

`outputs_from_mitgcm_standalone/` and the `1D_10`-family standalone file above are
the only KPP standalone-Fortran-driver (three-way method step 2) captures kept
under real MITgcm data; the 6 idealized-scenario standalone-driver runs
(1DMIX-023/-041/-048) instead write to `Vertical_Mixing_Models/output/<scenario>/`
and are out of this manifest's scope (no real-MITgcm capture involved there).
