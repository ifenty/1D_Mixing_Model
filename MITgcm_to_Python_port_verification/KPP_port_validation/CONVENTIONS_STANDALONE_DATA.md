# Standalone-driver (Direction B) data conventions — KPP

Written under 1DMIX-053 to permanentize the 6-idealized-scenario
standalone-Fortran-`KPPMIX`-driver comparison data (previously only living in
the scratch, git-ignored `Vertical_Mixing_Models/output/<scenario>/` tree —
see that issue for why this had already been silently lost and regenerated
once) and to give it the same durable, inspectable home
`inputs_from_mitgcm/`/`outputs_from_mitgcm/` already give the MITgcm-capture
comparison ("Direction A"). This is genuinely a different comparison shape
from Direction A: no MITgcm run is involved at all here — a Python-port-driven
idealized scenario is replayed directly through the real Fortran `KPPMIX`
subroutine (three-way method step (2) vs. (3), see this directory's parent
`README.md`).

## What lives here

```
inputs_from_python_standalone/<scenario>/kpp_standalone_input.txt
outputs_from_python_standalone/<scenario>/kpp_standalone_output.txt
outputs_from_python_standalone/<scenario>/kpp_experiment.npz
```

for each of the 6 idealized scenarios: `calm_baseline`, `arctic_convection`,
`hurricane_wind`, `tropical_heating_diurnal`, `heavy_rain_freshening`,
`combined_storm`.

`kpp_experiment.npz` is filed under `outputs_from_python_standalone/`, not
`inputs_from_python_standalone/`, even though it is exported *from* to build
the driver's input: it is the Python port's own output (step (3) of the
three-way method), not an input fed to the Fortran driver. Only
`kpp_standalone_input.txt` is actually consumed by the Fortran driver.

All three files are byte-identical copies of the scratch files under
`Vertical_Mixing_Models/output/<scenario>/` (verified by direct sha256
comparison at copy time, 1DMIX-053) — copied, not moved; the scratch tree is
untouched and remains the normal day-to-day working location. These
directories are the durable, git-ignored (see repo-root `.gitignore`) record;
`esx/project.json:external_inputs` declares the two
`outputs_from_python_standalone/` files per scenario (the ones
`compare_scenario_standalone.py::compare` actually reads — the actual
comparison-establishing files) so their real bytes are hashed into every
verification receipt. `kpp_standalone_input.txt` is not separately declared:
no script or test reads it back (it is retained purely so a reader can see
exactly what was fed to the Fortran driver without rerunning anything).

## Provenance — which script produced each file

| File | Producing command |
|---|---|
| `kpp_experiment.npz` | `Vertical_Mixing_Models/main/run_scenarios.py` (the Python KPP port's own run of the scenario) |
| `kpp_standalone_input.txt` | `MITgcm_to_Python_port_verification/scripts/export_scenario_to_fortran.py <scenario>` (reads the `kpp_experiment.npz` above; exports state/forcing to the standalone driver's flat-text input format; writes no comparison logic itself) |
| `kpp_standalone_output.txt` | `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_standalone_driver/build_and_run.sh kpp_standalone_input.txt kpp_standalone_output.txt` (compiles and runs MITgcm's real, unmodified `kpp_routines.F` `KPPMIX` directly, no full model) |

## Regenerated on WSL, 1DMIX-065 (2026-09-30)

The gitignored files under `inputs_from_python_standalone/` and
`outputs_from_python_standalone/` were absent on the fresh WSL checkout (2026-09-29)
and were regenerated from scratch under 1DMIX-065 with the commands in the
provenance table above, for all 6 scenarios, on 2026-09-30 (UTC) against MITgcm
commit `d861cd501f21303825de860eb3caa0a8a7ae22f8` (`~/Projects/MITgcm`, tracked
tree unmodified), Docker image `mitgcm:latest` (`6cc66b8957d8`), `x86_64`.
The Fortran side comes only from the real standalone driver (`kpp_standalone_driver/build_and_run.sh` compiling MITgcm's pristine `pkg/kpp/kpp_routines.F`);
the Python side (``kpp_experiment.npz``) only from the Python port; neither was used to
produce the other's file. Producing commands, run from the repo root with
`MITGCM_ROOT=~/Projects/MITgcm` (the driver scripts' new host-independence
override; default unchanged):

```
python3 Vertical_Mixing_Models/main/run_scenarios.py --scenario <scenario> --scheme kpp --no-plots
python3 MITgcm_to_Python_port_verification/scripts/export_scenario_to_fortran.py <scenario>
MITGCM_ROOT=~/Projects/MITgcm MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_standalone_driver/build_and_run.sh \
    Vertical_Mixing_Models/output/<scenario>/kpp_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/kpp_standalone_output.txt
# then copy the 3 files into inputs_from_python_standalone/<scenario>/ and outputs_from_python_standalone/<scenario>/
```

`build_and_run.sh` regenerates `SIZE.h` in the driver directory on every run
(`Nr` is auto-detected); the tracked copy was left as committed. Compile-time
inputs the driver needs were built once with
`experiment_compile.sh 1D_ocean_ice_column -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/1D_ocean_ice_column/code_validation -build build_docker_kppmix_extend -j 8` (run in `~/Projects/MITgcm/verification`; it supplies `PACKAGES_CONFIG.h`/`CPP_OPTIONS.h`)`.

Statistics of the regenerated set (`generate_*_scenario_report.py`, run to a
scratch path, not over the tracked report): the five scenarios other than `combined_storm` are at floating-point roundoff with 0 cells above 1% (worst `max_rel` 3.2e-15, arctic_convection; the Mac-era report's worst was 2.3e-15); `combined_storm` under the current default `keep_mitgcm_bugs=True` has `hbl` `max_abs` 5.7e-14 m and 4/600 (`visc_az`), 2/600 (`diff_kz_s`, `diff_kz_t`), 3/600 (`ghat`) cells above 1%, matching `KPP_VALIDATION_RESULTS.md`. The tracked `reports/kpp_scenario_standalone_summary.md` still shows the older `keep_mitgcm_bugs=False` numbers (45-51% above 1%) and was not regenerated by 1DMIX-065.

sha256 of every regenerated file (bytes on the WSL checkout):

| Scenario | File | sha256 |
|---|---|---|
| `calm_baseline` | `inputs_from_python_standalone/calm_baseline/kpp_standalone_input.txt` | `3da3b983fc0cb3df7aa38d24f50f3d45f07e0c3c084ee9f2eacc6502eee5da36` |
| `calm_baseline` | `outputs_from_python_standalone/calm_baseline/kpp_standalone_output.txt` | `764942d96ac608f1caeca577cb178c486069273f07325da96e3e7f47b2289709` |
| `calm_baseline` | `outputs_from_python_standalone/calm_baseline/kpp_experiment.npz` | `ed5c3ab837813e68c8c59d779d98f64a2f874dc65f99f6a3d20a6d40b28a0871` |
| `arctic_convection` | `inputs_from_python_standalone/arctic_convection/kpp_standalone_input.txt` | `ef593cc39b0d6c42d92e8091ae119e2c16e8cf1d205eddf6e99c1935acc89e96` |
| `arctic_convection` | `outputs_from_python_standalone/arctic_convection/kpp_standalone_output.txt` | `896f8844b07013ab5eb592d8047191482bcad43635cf3b765f489404c998ff1d` |
| `arctic_convection` | `outputs_from_python_standalone/arctic_convection/kpp_experiment.npz` | `ffa6e60115d57c77c7ddf59835ad8d7148e9472e2114d761108e83d7fa263fc4` |
| `hurricane_wind` | `inputs_from_python_standalone/hurricane_wind/kpp_standalone_input.txt` | `857d842b5441419c94b274e5170ed1a133656191beea0b2fe816286b8e5feb7e` |
| `hurricane_wind` | `outputs_from_python_standalone/hurricane_wind/kpp_standalone_output.txt` | `ff40db88029847f9dae681dcb736f7e32726fecc990409f9daa87a6bfc9e6adb` |
| `hurricane_wind` | `outputs_from_python_standalone/hurricane_wind/kpp_experiment.npz` | `5d1185e777665e25ae2203e6f62120c0a57ced753d530d7ccb7f9510d17cb825` |
| `tropical_heating_diurnal` | `inputs_from_python_standalone/tropical_heating_diurnal/kpp_standalone_input.txt` | `0361301d9cc2aa7360a08287888bc5d808ec85d0b0bb7492d1c6a7b948adab54` |
| `tropical_heating_diurnal` | `outputs_from_python_standalone/tropical_heating_diurnal/kpp_standalone_output.txt` | `10fc51bc1bd01a4f6e9b175c015fcbf6a36875a267484277fdf053e27c5cae5b` |
| `tropical_heating_diurnal` | `outputs_from_python_standalone/tropical_heating_diurnal/kpp_experiment.npz` | `bfe52ebdb3b5d7e32e12415a8f5054946ad763ebfd6924f9b5e78992eab1a716` |
| `heavy_rain_freshening` | `inputs_from_python_standalone/heavy_rain_freshening/kpp_standalone_input.txt` | `db622ea7ed28afe769a2a77e83e37a81764d6c56624c07bab54d0cde846c4b23` |
| `heavy_rain_freshening` | `outputs_from_python_standalone/heavy_rain_freshening/kpp_standalone_output.txt` | `8a459416dfec9f1fd888abda3a5af01d3cebb965cd97b212d3c9046650a2e2a9` |
| `heavy_rain_freshening` | `outputs_from_python_standalone/heavy_rain_freshening/kpp_experiment.npz` | `05ce708d04162878497e167027ea527268a489c8b132a49a4c8790bc04a40f56` |
| `combined_storm` | `inputs_from_python_standalone/combined_storm/kpp_standalone_input.txt` | `76cd22ceb32540ce204287095c8c767a462de1d52395b48f4ef4d27300ff10c0` |
| `combined_storm` | `outputs_from_python_standalone/combined_storm/kpp_standalone_output.txt` | `dd1660f3fe97f60d068ae93bad73ebc7f33be44e371043fd3bca5dda120cc809` |
| `combined_storm` | `outputs_from_python_standalone/combined_storm/kpp_experiment.npz` | `e6594cfd7b588f3a05d0ebfe3d2b90054513fd7f6f52a3c99b8a6b2a587bf266` |

## Comparison and report

`MITgcm_to_Python_port_verification/scripts/compare_scenario_standalone.py::compare`
reads `kpp_experiment.npz` + `kpp_standalone_output.txt` from one
`outputs_from_python_standalone/<scenario>/` directory and returns, per field
(`visc_az`, `diff_kz_s`, `diff_kz_t`, `ghat`, `hbl`), the statistic dict
(`max_abs`/`median_abs`/`p95_abs`/`max_rel`/`n_gt_1pct`/`n_total`) produced by
`compare_scenario_ggl90_standalone.py::summarize` — imported and called
unmodified, the same scheme-agnostic function the GGL90 comparison already
uses (1DMIX-053; before this, `compare()` had no return value at all and only
printed a max/mean absolute difference — that gap is what 1DMIX-053 closed,
since a sibling report to GGL90's needed the same statistic set).
`MITgcm_to_Python_port_verification/scripts/generate_kpp_scenario_report.py`
(1DMIX-053) formats that returned dict into
[`reports/kpp_scenario_standalone_summary.md`](reports/kpp_scenario_standalone_summary.md)
— no comparison logic reimplemented in the generator. That report found a
real, quantified discrepancy in `combined_storm` (see the report itself).

## Regenerating from scratch

1. `conda run -n ecco python3 Vertical_Mixing_Models/main/run_scenarios.py <scenario>` (or however the scenario is normally run) → `Vertical_Mixing_Models/output/<scenario>/kpp_experiment.npz`.
2. `conda run -n ecco python3 MITgcm_to_Python_port_verification/scripts/export_scenario_to_fortran.py <scenario>` → `Vertical_Mixing_Models/output/<scenario>/kpp_standalone_input.txt`.
3. `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_standalone_driver/build_and_run.sh Vertical_Mixing_Models/output/<scenario>/kpp_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/kpp_standalone_output.txt` (requires a local MITgcm checkout: the script's default is the original macOS path `/Users/ifenty/git_repo_others/MITgcm`; on any other host set the `MITGCM_ROOT` environment variable — 1DMIX-065 added that override, default unchanged — e.g. `MITGCM_ROOT=~/Projects/MITgcm`. It also needs the genmake2-generated build directory `$MITGCM_ROOT/verification/1D_ocean_ice_column/build_docker_kppmix_extend`, created by `experiment_compile.sh 1D_ocean_ice_column -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/1D_ocean_ice_column/code_validation -build build_docker_kppmix_extend`).
4. Copy the resulting 3 files into `inputs_from_python_standalone/<scenario>/` and `outputs_from_python_standalone/<scenario>/` per the layout above (no script currently automates this copy step; do it by hand, or write one — 1DMIX-053 did it once by hand for all 6 scenarios since the data already existed).
5. Rerun `generate_kpp_scenario_report.py` to refresh the report from the new bytes.
