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
2. `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/ggl90_standalone_output.txt` (requires the local MITgcm checkout at the path hardcoded in that script).
3. Copy the resulting 3 files into `inputs_from_python_standalone/<scenario>/` and `outputs_from_python_standalone/<scenario>/` per the layout above (no script currently automates this copy step; do it by hand, or write one — 1DMIX-053 did it once by hand for all 6 scenarios since the data already existed).
4. Rerun `generate_ggl90_scenario_report.py` to refresh the report from the new bytes.
