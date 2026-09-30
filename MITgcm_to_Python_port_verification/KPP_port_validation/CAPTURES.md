# Capture manifest — KPP_port_validation

Written under 1DMIX-046 to resolve "which versioned file is current" for every
experiment that has more than one capture on disk, and to document the two
oddly-located `_python.nc`-suffixed files (1DMIX-046 task 5). Experiments with
exactly one input/output/python-output set (`lab_sea_1000_0820T0946` — now single
after this issue removed its stray duplicate, see below —, `lab_sea_6mo`,
`seaice_obcs_1dmix034`, `global_oce_latlon_720`) need no entry beyond noting
that single-version status; `global_oce_latlon_720` gets one anyway below since
it is a brand-new capture (1DMIX-049) worth documenting at introduction.

## Regenerated on WSL, 1DMIX-065 (2026-09-30)

The repo moved to a fresh WSL checkout on 2026-09-29 and every gitignored `*.nc`
capture was absent. 1DMIX-065 regenerated the KPP files below from scratch on
that host, using this repo's instrumented `mitgcm_verification_mods/*/code_validation`
trees and the Docker workflow (`~/Projects/MITgcm_verification_docker`,
image `mitgcm:latest`, `x86_64`, optfile `linux_amd64_gfortran`). Recorded per
file: the recipe that produced it, the MITgcm commit, the date and the sha256.
No Python-port output was used as an MITgcm reference and no MITgcm file was
produced by the Python port: the `*_from_mitgcm/` files come only from an
MITgcm run (parsed by `parse_mitgcm_split.py`); the `outputs_from_python/`
files (and the historically-mislocated `mitgcm_kpp_inputs_11k_1D_python.nc`)
come only from replaying the port on the paired input capture.

- **MITgcm commit**: `d861cd501f21303825de860eb3caa0a8a7ae22f8` (2026-09-06,
  `~/Projects/MITgcm`, tracked tree unmodified; build/run directories are
  untracked dirs under `verification/`).
- **Date**: runs and replays on 2026-09-30 (UTC; the host clock read 2026-09-29
  PDT). **Docker image**: `mitgcm:latest` (id `6cc66b8957d8`).
- **Parser**: all `mitgcm_kpp_*` files were parsed with the streaming
  `scripts/parse_mitgcm_split.py` (see below), so they carry fresh run UUIDs
  and use an unlimited `time` dimension (one HDF5 chunk per timestep, so the
  small captures are several times larger on disk than the old files; values
  and attributes are identical in content).

### Recipes (cwd `~/Projects/MITgcm/verification` unless stated; `<mods>` = `<repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods`)

| Id | Steps |
|---|---|
| **R1** `1D_10_kppmix_extend_rawflux_fix` (10 steps) | `./experiment_compile.sh 1D_ocean_ice_column -mods <mods>/1D_ocean_ice_column/code_validation -build build_docker_kppmix_extend -j 8`; `./experiment_run_no_compile.sh 1D_ocean_ice_column -build build_docker_kppmix_extend -output output_validation_1D10_rawflux_fix` (stock `input/`, `nTimeSteps=10`); parse (repo root): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py <run>/output.txt 1D_ocean_ice_column`, then copy the resulting `mitgcm_kpp_inputs.nc`/`mitgcm_kpp_outputs.nc` to the documented names. |
| **R2** `11k_1D` (11,000 steps) | same build as R1; run input dir `input_validation_11k` = `cp -r input input_validation_11k` with the single edit in `data` swapping `nTimeSteps= 10` / `# nTimeSteps= 11000` (as `1D_ocean_ice_column/README_11K_TIME_STEP_SIMULATION.TXT` describes): `./experiment_run_no_compile.sh 1D_ocean_ice_column input_validation_11k -build build_docker_kppmix_extend -output output_validation_11k`; parse as R1. |
| **R3** `lab_sea_1000_0820T0946` (999 steps) | `./experiment_compile.sh lab_sea -mods <mods>/lab_sea/code_validation -build build_docker_kpp_validation -j 8`; run input dir `input_validation_1000` = `cp -r input input_validation_1000` with the single edit in `data` `endTime=36000.` -> `endTime=3600000.` (`startTime=3600`, `deltaT=3600` => 999 steps): `./experiment_run_no_compile.sh lab_sea input_validation_1000 -build build_docker_kpp_validation -output output_validation_1000`; parse as R1 with experiment name `lab_sea`. |
| **R4** `global_oce_latlon_720` (720 steps x 4 tiles) | `./experiment_compile.sh global_oce_latlon -mods <mods>/global_oce_latlon/code_validation -build build_docker_kpp_fwd -j 8`; run directory `global_oce_latlon/input_docker_kpp_fwd` assembled exactly as `<mods>/global_oce_latlon/input_validation/README.md` "Reproducing the run directory" describes; `./experiment_run_no_compile.sh global_oce_latlon input_docker_kpp_fwd -build build_docker_kpp_fwd -output output_validation_720` (9 min, `output.txt` 13,823,541,777 bytes); parse as R1 with experiment name `global_oce_latlon` (7.5 min wall, peak RSS 0.155 GB under a `ulimit -v` 8 GB bound). |
| **P1** / **P2** / **P3** | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_<tag>.nc -o KPP_port_validation/outputs_from_python/python_kpp_outputs_<tag>.nc -j N` for `<tag>` = `1D_10_kppmix_extend_rawflux_fix` (P1), `11k_1D` (P2), `lab_sea_1000_0820T0946` (P3). |
| **P2b** | the same command as P2 with `-o KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` (the historically-mislocated name `compute_validation_statistics.py` opens; see the `11k_1D` section below). |

The two `data` edits (R2, R3) were not recorded anywhere in the repo before
1DMIX-065; they are inferred from the capture names, the captured time
dimensions (10 / 11,000 / 999) and the experiment README, so they reproduce
those runs' step counts but were not checked against the original Mac-era run
directories, which are not available. The regenerated `lab_sea` 999-step
capture is clean of the `OUTPUT_MIXING` truncation defect (0 of 149,850 ocean
column-timesteps; exactly 1710 active `visc_az` cells per timestep), whereas
the Mac-era file's documented active-cell count (1,637,981, i.e. 1639.6 per
timestep) implies it was not; that is why its relative-error statistics differ
slightly from `KPP_VALIDATION_RESULTS.md` while every other capture reproduces
the documented statistics to all printed digits.

### File provenance (sha256 of the bytes on the WSL checkout)

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | R2 | 23352759 | `ccdc7c99d2f3c55c2ff876d4ba0ca96ac1820b99ff22484b445da21eac7c17e4` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | P2b | 1614204 | `f59ee889989c7fd5ad0de690a36b78245475d0e450a404d8eddeddd09b04e789` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 129296 | `bf77754a8d59935ed81b11e4727552bd981172622695378cf90867a8559f3aef` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_oce_latlon_720.nc` | R4 | 704325331 | `89b324673fce191fe5e8995d7cbd86337e96cd4a5973e1cf731a8677bcc9d124` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc` | R3 | 73433208 | `6b8f7946eceee3d326c6bbb3701208f649b0c3187d8e472e04e0cb4be5183d75` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | R2 | 21556047 | `3730eb4bbd19da9f7260350b850b41dd9bde39487a8792b75557f7b85eb8012c` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 104890 | `8fad79bc2fd464274e2096c7d490fde738986cc74c3fe7b844cede7db93cd15a` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_oce_latlon_720.nc` | R4 | 1090886385 | `ada88d19bd2272fc58659c2518e64bb069ef5cf9569846267ff27bcac5cfe9e6` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_1000_0820T0946.nc` | R3 | 124875004 | `bed79b942d995f186f4fc05a5409da032dc5b99f7852213a2278ecb3304efca8` |
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | P2 | 1614204 | `ffb39a04e336d0c35d8594b97c01108c541cbaa97c74a7a5fbfdfb1148f58b49` |
| `outputs_from_python/python_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | P1 | 66309 | `ae691c9ad1a7e086680528cb3b982f14261758dca793a306a47d78285f68c97c` |
| `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc` | P3 | 27497628 | `d59fafbc942b55eaa8bf526ab610d2188ee8f8fc8bd550153f029f8fbe2eaf4f` |

### Streaming parser (why the capture step changed)

The previous `parse_mitgcm_split.py` kept every value of every timestep in
Python dicts and built the arrays at the end. On this 27 GB host the 13.8 GB
`global_oce_latlon_720` capture held >24 GB for more than 25 minutes without
finishing. The parser now streams (engine `scripts/capture_stream.py`): each
completed timestep is appended to the NetCDF files and dropped. Measured on the
same file under a `ulimit -v` 8 GB bound: 449.6 s wall, **peak RSS 0.155 GB**.
Output content was verified identical to the old parser's on the 10-step,
11,000-step and 999-step `lab_sea` captures and a 4-timestep, 4-tile slice of
`global_oce_latlon`, variable by variable and byte for byte (only `uuid`,
`creation_date`, `output_file_path` and `input_uuid` excluded); see
`scripts/README.md` and `devel-loop/loop_state/bob-1DMIX-065-evidence.md`.

### Legacy `mitgcm_kpp_inputs_1D_10.nc`: removed from `esx/project.json:external_inputs`

The original 2026-08-19 capture cannot be faithfully re-made: it predates
the `_kppmix_extend` and `_kppmix_extend_rawflux_fix` re-captures and the
instrumentation fixes that produced them, its would-be paired output was never
kept, and nothing loads it (grep-confirmed 2026-09-30 over `*.py`, `*.sh`,
`*.yaml`, `*.json` and the docs: the only references were its own
`external_inputs` entry and the manifest row below). Rather than fabricate a
file under that name, the entry was removed from `esx/project.json`; the
declared external inputs are now 30 files, all present.

## `global_oce_latlon_720` (720 timesteps, 4-tile 2×2 90×40×15, `global_oce_latlon` verification experiment)

Single version — regenerated fresh 2026-09-27 (1DMIX-049) after the original
1DMIX-027 capture was lost in a disk-space rescue; no superseded alternative
exists. Regenerated again on the WSL checkout 2026-09-30 (1DMIX-065, recipe R4
above; same 2,315 wet columns at all 720 timesteps, statistics reproduce the
documented ones to every printed digit).

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
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10.nc` | **removed** (1DMIX-065, 2026-09-30) | Original 2026-08-19 capture, predates both later re-captures. No active reference; no paired output file exists for it (its would-be `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10.nc` was never kept). Not present on the WSL checkout and cannot be faithfully re-made; its entry was removed from `esx/project.json:external_inputs` instead of fabricating a file under this name (rationale in "Regenerated on WSL, 1DMIX-065" above). |
| `outputs_from_python/python_kpp_outputs_1D_10_precomputed_forcing.nc` | superseded, retained (orphaned) | A 2026-09-16 Python-port output for a *different*, one-off experiment (`input_file_name` attribute reads `mitgcm_kpp_inputs_precomputed_forcing_only.nc`, not any file above) whose own input capture is no longer present in this repo. Not part of the `1D_10` version family despite the shared filename prefix; not referenced by any active script/test. Kept rather than deleted only because its originating input can no longer be inspected to confirm it is safe to discard. |

## `11k_1D` (11,000 timesteps, single sea-ice-coupled column, `1D_ocean_ice_column`)

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation_extended.py` (`DATA_11K`) and by `KPP_port_validation/scripts/compute_validation_statistics.py` (as `mitgcm_file`'s sibling). Single version — no superseded alternative exists. |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | **current** | Paired MITgcm output, same test; also loaded directly by `compute_validation_statistics.py`. |
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | **current** | The standard-convention Python output the active test suite actually asserts against; source of `reports/kpp_validation_1D_ocean_ice_column_11000.pdf`. |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | **anomalous — retained, not "current"** (1DMIX-046 task 5) | **Investigated.** Despite its name and location (inside `inputs_from_mitgcm/`, not `outputs_from_python/`), this file's own embedded NetCDF metadata is unambiguous: `title="Python KPP Port Outputs"`, `source="Python KPP port"`, `description="KPP outputs from Python port using MITgcm inputs"` — it **is** a Python-port output, not an MITgcm input, mislocated by an earlier (2026-08-20) version of the pipeline that saved a `<input_basename>_python.nc` file alongside its input by default, before the current `outputs_from_python/python_kpp_outputs_<tag>.nc` convention existed (see `NETCDF_DATA_FORMAT.md`'s own now-corrected step-4 walkthrough, which still documents this exact historical behavior). It shares the real capture's `uuid` (provenance-verified). **Not deleted**: `KPP_port_validation/scripts/compute_validation_statistics.py` still opens this exact file by name as its `python_file`. It is listed in `esx/project.json:external_inputs` (mislabeled there as an "MITgcm-derived" input, which it is not — left as-is rather than edited further, since removing the file itself would require a coupled `project.json` edit, and this file, unlike the `lab_sea` one below, is not safe to delete). **Regenerated 1DMIX-065 (2026-09-30)**: produced by replaying the port on the regenerated 11k capture (recipe P2b above, sha256 in the provenance table), with the current `run_kpp_from_netcdf_input.py` CLI; it therefore shares the regenerated capture's `uuid` and is content-equivalent to `outputs_from_python/python_kpp_outputs_11k_1D.nc`. |

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
Their durable copies (`{inputs,outputs}_from_python_standalone/`) were
regenerated on the WSL checkout under 1DMIX-065; the per-file recipe, MITgcm
commit and sha256 are in `CONVENTIONS_STANDALONE_DATA.md` ("Regenerated on
WSL, 1DMIX-065").
