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
3. `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_standalone_driver/build_and_run.sh Vertical_Mixing_Models/output/<scenario>/kpp_standalone_input.txt Vertical_Mixing_Models/output/<scenario>/kpp_standalone_output.txt` (requires the local MITgcm checkout at the path hardcoded in that script).
4. Copy the resulting 3 files into `inputs_from_python_standalone/<scenario>/` and `outputs_from_python_standalone/<scenario>/` per the layout above (no script currently automates this copy step; do it by hand, or write one — 1DMIX-053 did it once by hand for all 6 scenarios since the data already existed).
5. Rerun `generate_kpp_scenario_report.py` to refresh the report from the new bytes.
