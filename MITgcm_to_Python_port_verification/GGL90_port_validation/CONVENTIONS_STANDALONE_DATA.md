# Standalone-driver (Direction B) data conventions — GGL90

Written under 1DMIX-053 to permanentize the 6-idealized-scenario
standalone-Fortran-`GGL90_CALC`-driver comparison data (previously only living
in the scratch, git-ignored `Vertical_Mixing_Models/output/<scenario>/` tree —
see that issue for why this had already been silently lost and regenerated
once) and to give it the same durable, inspectable home
`inputs_from_mitgcm/`/`outputs_from_mitgcm/` already give the MITgcm-capture
comparison ("Direction A"). This is genuinely a different comparison shape
from Direction A: no MITgcm run is involved at all here — a Python-port-driven
idealized scenario (rerun dense, `output_frequency_steps=1`) is replayed
directly through the real Fortran `GGL90_CALC` subroutine (three-way method
step (2) vs. (3), see this directory's parent `README.md`, "GGL90 standalone
driver" section, 1DMIX-041/1DMIX-048).

## What lives here

```
inputs_from_python_standalone/<scenario>/ggl90_standalone_input.txt
outputs_from_python_standalone/<scenario>/ggl90_standalone_output.txt
outputs_from_python_standalone/<scenario>/ggl90_experiment_dense.npz
```

for each of the 6 idealized scenarios: `calm_baseline`, `arctic_convection`,
`hurricane_wind`, `tropical_heating_diurnal`, `heavy_rain_freshening`,
`combined_storm`.

`ggl90_experiment_dense.npz` is filed under `outputs_from_python_standalone/`,
not `inputs_from_python_standalone/`, even though it is exported *from* to
build the driver's input: it is the Python port's own dense-trajectory output
(step (3) of the three-way method), not an input fed to the Fortran driver.
Only `ggl90_standalone_input.txt` is actually consumed by the Fortran driver.
Note this dense npz is a *separate* trajectory from the scenario's normal
(coarser) `ggl90_experiment.npz` — same physics, `output_frequency_steps=1`
instead of the scenario's own coarser setting, needed for a row-per-timestep
match against the driver's own per-step output (see
`export_scenario_to_ggl90_driver.py`'s module docstring for the full
index-alignment derivation).

All three files are byte-identical copies of the scratch files under
`Vertical_Mixing_Models/output/<scenario>/` (verified by direct sha256
comparison at copy time, 1DMIX-053) — copied, not moved; the scratch tree is
untouched and remains the normal day-to-day working location. These
directories are the durable, git-ignored (see repo-root `.gitignore`) record;
`esx/project.json:external_inputs` declares the two
`outputs_from_python_standalone/` files per scenario (the ones
`compare_scenario_ggl90_standalone.py::compare` actually reads — the actual
comparison-establishing files) so their real bytes are hashed into every
verification receipt. `ggl90_standalone_input.txt` is not separately
declared: no script or test reads it back (it is retained purely so a reader
can see exactly what was fed to the Fortran driver without rerunning
anything).

## Provenance — which script produced each file

| File | Producing command |
|---|---|
| `ggl90_standalone_input.txt`, `ggl90_experiment_dense.npz` | `MITgcm_to_Python_port_verification/scripts/export_scenario_to_ggl90_driver.py <scenario>` (reruns the scenario dense, `output_frequency_steps=1`, saving that trajectory to the `.npz`; exports it to the standalone driver's flat-text input format in the same call — see that script's own docstring) |
| `ggl90_standalone_output.txt` | `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh ggl90_standalone_input.txt ggl90_standalone_output.txt` (compiles and runs MITgcm's real, unmodified `ggl90_calc.F` `GGL90_CALC` directly, no full model) |

## Regenerated on WSL, 1DMIX-065 (2026-09-30)

The gitignored files under `inputs_from_python_standalone/` and
`outputs_from_python_standalone/` were absent on the fresh WSL checkout (2026-09-29)
and were regenerated from scratch under 1DMIX-065 with the commands in the
provenance table above, for all 6 scenarios, on 2026-09-30 (UTC) against MITgcm
commit `d861cd501f21303825de860eb3caa0a8a7ae22f8` (`~/Projects/MITgcm`, tracked
tree unmodified), Docker image `mitgcm:latest` (`6cc66b8957d8`), `x86_64`.
The Fortran side comes only from the real standalone driver (`ggl90_standalone_driver/build_and_run.sh` compiling the vermix instrumentation copy of `ggl90_calc.F` (sha256 `a0fa9c3838bc29b026b60add3d13c50f27b2acdf42fcb671e8090e8d47d8a80f`, identical to canonical `ggl90_mods/ggl90_calc.F`) plus MITgcm's pristine `pkg/ggl90/ggl90_mixinglength.F` and `model/src/solve_tridiagonal.F`);
the Python side (``ggl90_experiment_dense.npz``) only from the Python port; neither was used to
produce the other's file. Producing commands, run from the repo root with
`MITGCM_ROOT=~/Projects/MITgcm` (the driver scripts' new host-independence
override; default unchanged):

```
python3 MITgcm_to_Python_port_verification/scripts/export_scenario_to_ggl90_driver.py <scenario>
MITGCM_ROOT=~/Projects/MITgcm MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh \
    Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_output.txt
# then copy the 3 files into inputs_from_python_standalone/<scenario>/ and outputs_from_python_standalone/<scenario>/
```

`build_and_run.sh` regenerates `SIZE.h` in the driver directory on every run
(`Nr` is auto-detected); the tracked copy was left as committed. Compile-time
inputs the driver needs were built once with
`experiment_compile.sh vermix -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/vermix/code_validation -build build_docker_ggl90_1dmix024 -j 8` (run in `~/Projects/MITgcm/verification`; it supplies `PACKAGES_CONFIG.h`/`CPP_OPTIONS.h` and the dereferenced `vermix/code_validation` copy)`.

Statistics of the regenerated set (`generate_*_scenario_report.py`, run to a
scratch path, not over the tracked report): all scenarios/fields at floating-point roundoff, 0 cells above 1%, worst `max_rel` 1.237e-11 (hurricane_wind; the tracked Mac-era report's worst was 1.388e-11). The in-memory parse of `ggl90_standalone_output.txt` now goes through the streaming parser (`scripts/parse_mitgcm_ggl90_split.py`); the regenerated report is identical to the one produced with the old parser apart from its `Generated:` timestamp.

sha256 of every regenerated file (bytes on the WSL checkout):

| Scenario | File | sha256 |
|---|---|---|
| `calm_baseline` | `inputs_from_python_standalone/calm_baseline/ggl90_standalone_input.txt` | `380ea919b92db7284a6d2110d536fe3f3df42cb457a2ad88229d3ef1cea6297b` |
| `calm_baseline` | `outputs_from_python_standalone/calm_baseline/ggl90_standalone_output.txt` | `7bfe84355ba60c65d936e8b7e1a2c50505d5687b803ad3cf35c9605d09aae0b1` |
| `calm_baseline` | `outputs_from_python_standalone/calm_baseline/ggl90_experiment_dense.npz` | `cefc932f6714d2a22da6fb37aad139eed5c62850ebde25096648fbf72de1fbba` |
| `arctic_convection` | `inputs_from_python_standalone/arctic_convection/ggl90_standalone_input.txt` | `fadcaf95f69448ff7d1dcd968db6afc240b8ab189a44d681797cf39cbb40bf25` |
| `arctic_convection` | `outputs_from_python_standalone/arctic_convection/ggl90_standalone_output.txt` | `34a65b12e576633378bc9df5b811f8781a309aaf394152d5b5158da339c14fa7` |
| `arctic_convection` | `outputs_from_python_standalone/arctic_convection/ggl90_experiment_dense.npz` | `5d37b29d2dd82a3c879dc79bbb30e88121b133592de3b27fe190a2d46d207279` |
| `hurricane_wind` | `inputs_from_python_standalone/hurricane_wind/ggl90_standalone_input.txt` | `78441edf54742e60f9487113f996e482eea3ed803c9232379ffcef11dc029f20` |
| `hurricane_wind` | `outputs_from_python_standalone/hurricane_wind/ggl90_standalone_output.txt` | `b97f7ad044faebb4377ddfc8d5ac1b8b369e689ad344b956579f3156026b1296` |
| `hurricane_wind` | `outputs_from_python_standalone/hurricane_wind/ggl90_experiment_dense.npz` | `8724acdc8d1a7e7116118466bde93aaab42da664c03550f6ef8cbf5a02a88972` |
| `tropical_heating_diurnal` | `inputs_from_python_standalone/tropical_heating_diurnal/ggl90_standalone_input.txt` | `66fb74ab10f2bd317b8972e0af97c2d9655069de47b1adee6296a8842eb9cece` |
| `tropical_heating_diurnal` | `outputs_from_python_standalone/tropical_heating_diurnal/ggl90_standalone_output.txt` | `f93ec6f24a98c891d44e053c7d56b03f61d49c83c565bbe34f8da8b607241ea2` |
| `tropical_heating_diurnal` | `outputs_from_python_standalone/tropical_heating_diurnal/ggl90_experiment_dense.npz` | `6f30732529e81e50492e555d8607a7214e33b2a0345c1d04ebb97ff7c70b235b` |
| `heavy_rain_freshening` | `inputs_from_python_standalone/heavy_rain_freshening/ggl90_standalone_input.txt` | `728e69a1b85304b46e8b9ea31bc5755c0fa42d204723f98fadec97ceba85dd9f` |
| `heavy_rain_freshening` | `outputs_from_python_standalone/heavy_rain_freshening/ggl90_standalone_output.txt` | `f0d3fe0303926032f270f1a826ec92778452796d01784924a4e213cd4aabb7fc` |
| `heavy_rain_freshening` | `outputs_from_python_standalone/heavy_rain_freshening/ggl90_experiment_dense.npz` | `e868f74437eb34b65034a3c58fc38664b6a46b39878526af5fb9b9010d9bf1c2` |
| `combined_storm` | `inputs_from_python_standalone/combined_storm/ggl90_standalone_input.txt` | `393d7c50fee267ec07b3aa52239746cd1b6bd524fb4d135fd0f6fb0ce5681398` |
| `combined_storm` | `outputs_from_python_standalone/combined_storm/ggl90_standalone_output.txt` | `80e726f031505f3267b77a730cdff3d7e33b3c41562e29752dccfbbe8826eedd` |
| `combined_storm` | `outputs_from_python_standalone/combined_storm/ggl90_experiment_dense.npz` | `c1e86ddc139a488f772ed6116fe1cdc16554c00cc43f469da0ffab07121e29f4` |

## Regenerated at 17 digits, 1DMIX-070 (2026-09-30)

The `ggl90_standalone_output.txt` files were regenerated with the real standalone driver
(`build_and_run.sh`, `MITGCM_ROOT=~/Projects/MITgcm`, Docker `mitgcm:latest` `6cc66b8957d8`, MITgcm
`d861cd501`, tree unmodified) after widening its print formats: `ggl90_mods/ggl90_calc.F` (via the vermix instrumented copy the driver compiles; FORMAT 101/200-203 already `ES25.16` from 1DMIX-069, `PARAM_*` lines `E16.8` -> `ES25.16` in 1DMIX-070; the driver has no result FORMAT of its own). The Python side
(`ggl90_experiment_dense.npz`) and the driver input
`ggl90_standalone_input.txt` were **not** regenerated (unchanged); only the Fortran output changed. Old
outputs are kept under `devel-loop/loop_state/scratch/bob-1DMIX-070/old16/`. Line-by-line comparison
(`scratch/.../cmp_standalone_txt.out`): all six scenarios have identical line counts and identical
non-numeric lines, and every numeric field agrees with the 16-digit file to <= 5.80e-16 relative
(0 above 6e-16). `compare_scenario_*_standalone.py::compare` statistics
(`stats_standalone_16v17.out`) are unchanged at every reported digit that is not roundoff-level:
every scenario and field stays at roundoff with 0 cells above 1% (worst `max_rel` 1.237e-11, hurricane_wind `tke_after`, identical at both precisions).
So none of the standalone gaps or agreements was a print artifact. The tracked `reports/*_scenario_standalone_summary.md` was not regenerated.

sha256 of the regenerated files (bytes on the WSL checkout):

| Scenario | File | Bytes | sha256 |
|---|---|---|---|
| `calm_baseline` | `GGL90_port_validation/outputs_from_python_standalone/calm_baseline/ggl90_standalone_output.txt` | 7854518 | `47c035af29218afd131b270450c5dff8c58d6fa6e82dcc3b4128df1faf955430` |
| `arctic_convection` | `GGL90_port_validation/outputs_from_python_standalone/arctic_convection/ggl90_standalone_output.txt` | 63228458 | `a7d69c62ec0dd1f4f12555bcd29b6aa4aaf84469518c654800b09aefb3ae6841` |
| `hurricane_wind` | `GGL90_port_validation/outputs_from_python_standalone/hurricane_wind/ggl90_standalone_output.txt` | 3930230 | `1f57ffd8a83639e318ba89d5691da9cc42bf5445d241a755593315b505a8dc2d` |
| `tropical_heating_diurnal` | `GGL90_port_validation/outputs_from_python_standalone/tropical_heating_diurnal/ggl90_standalone_output.txt` | 3930230 | `cb08d129afe8f5e789a52258c378d5ba24be0aec43ef0aad05d1a593d9b0ea65` |
| `heavy_rain_freshening` | `GGL90_port_validation/outputs_from_python_standalone/heavy_rain_freshening/ggl90_standalone_output.txt` | 3930230 | `9680e7b77b7b8b7eb70c2cbcd28d5e22289cb158a1999520106996b1f8840126` |
| `combined_storm` | `GGL90_port_validation/outputs_from_python_standalone/combined_storm/ggl90_standalone_output.txt` | 1968086 | `486c0e5ca1af8dd6b883fd0f5b5a73bf739eb348441a39bb3f0609ca34320ac7` |

## Comparison and report

`MITgcm_to_Python_port_verification/scripts/compare_scenario_ggl90_standalone.py::compare`
reads `ggl90_experiment_dense.npz` + `ggl90_standalone_output.txt` from one
`outputs_from_python_standalone/<scenario>/` directory and returns, per field
(`visc_az`, `diff_kz_s`, `mixing_length`, `tke_after`), `max_abs`/
`median_abs`/`p95_abs`/`max_rel`/`n_gt_1pct`/`n_total` — see that module's own
docstring/source for the exact derivation (`tke_after`'s one-timestep index
shift in particular). `generate_ggl90_scenario_report.py` (1DMIX-051) formats
those returned values into
[`reports/ggl90_scenario_standalone_summary.md`](reports/ggl90_scenario_standalone_summary.md).

## Regenerating from scratch

1. `conda run -n ecco python3 MITgcm_to_Python_port_verification/scripts/export_scenario_to_ggl90_driver.py <scenario>` → `Vertical_Mixing_Models/output/<scenario>/{ggl90_experiment_dense.npz,ggl90_standalone_input.txt}` (well under a minute per scenario per that script's own report-generator docstring).
2. `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_output.txt` (requires a local MITgcm checkout: the script's default is the original macOS path `/Users/ifenty/git_repo_others/MITgcm`; on any other host set the `MITGCM_ROOT` environment variable — 1DMIX-065 added that override, default unchanged — e.g. `MITGCM_ROOT=~/Projects/MITgcm`. It also needs the genmake2-generated build directory `$MITGCM_ROOT/verification/vermix/build_docker_ggl90_1dmix024` and the `$MITGCM_ROOT/verification/vermix/code_validation` copy, both created by `experiment_compile.sh vermix -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/vermix/code_validation -build build_docker_ggl90_1dmix024`).
3. Copy the resulting 3 files into `inputs_from_python_standalone/<scenario>/` and `outputs_from_python_standalone/<scenario>/` per the layout above (no script currently automates this copy step; do it by hand, or write one — 1DMIX-053 did it once by hand for all 6 scenarios since the data already existed).
4. Rerun `generate_ggl90_scenario_report.py` to refresh the report from the new bytes.
