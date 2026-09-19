# 1D Mixing Experiments: GGL90 and KPP Python Ports

A **1D column model for ocean vertical mixing** containing Python ports of two MITgcm
parameterization schemes:

- **GGL90** — prognostic, TKE-based turbulence closure
- **KPP** — diagnostic, Richardson-number based boundary layer scheme

Both ports target bit-level correspondence with their MITgcm Fortran originals. Any deviation is
treated as a bug to be investigated, not a tuning knob.

The project has two complementary validation tracks:

1. **Scenario validation** — run both schemes across 6 physically distinct scenarios and compare
   them against each other for physical plausibility.
2. **MITgcm validation** — instrument MITgcm's own KPP, capture its exact inputs and outputs, feed
   those inputs to the Python port, and compare numerically.

## Status

**KPP port: validated against MITgcm.** Across 11,000 timesteps of the `1D_ocean_ice_column`
verification experiment:

| Metric | Result |
|---|---|
| Mean relative error | 0.18% |
| Median relative error | 0.0005% |
| RMS error | 0.72 m |
| Timesteps within 10% | 99.63% |

The residual outliers (41 timesteps, 0.37%) occur during extreme weak forcing and are explained by
floating-point behavior in a near-critical Richardson-number regime, not by implementation error.
See `KPP_port_validation/INVESTIGATION_CONCLUSION.md` for the full analysis.

**GGL90 port:** scenario-validated; not yet put through the MITgcm capture-and-compare pipeline.

Open issues live in `open_issues.md` (resolved/false-positive history in `closed_issues.md`) —
see those files for the current list.

## Quick Start

```bash
conda activate ecco          # /Users/ifenty/miniforge3/envs/ecco — Python 3.11.10
cd 1D_Mixing_Model
```

Run both schemes across all 6 scenarios:

```bash
python main/run_scenarios.py
```

Run one scenario with one scheme:

```bash
python main/run_scenarios.py --scenario arctic_convection --scheme ggl90
```

Useful flags (`--help` for the full list):

| Flag | Purpose |
|---|---|
| `--scheme {kpp,ggl90,both}` | Which scheme(s) to run. Default `both`. |
| `--scenario NAME [NAME ...]` | Restrict to named scenarios. Default: all discovered. |
| `--no-plots` | Skip figure generation (faster). |
| `--ggl90-yaml` / `--kpp-yaml` | Override scheme defaults from a YAML file. |
| `--ivdc-kappa` | Convective-adjustment diffusivity (MITgcm `ivdc_kappa`). ECCOv4r4 uses 10. |
| `--output-dir` | Output root. Default `1D_Mixing_Model/output`. |

Full cross-scheme validation suite:

```bash
python tests/test_full_scenario_validation.py
```

Results land in `1D_Mixing_Model/output/`, with the generated cross-scheme report at
`output/scenario_comparison/scenario_comparison_report.md`.

## Repository Layout

```
1D_Mixing_Experiments/
├── CLAUDE.md                        AI project context — read first
├── open_issues.md / closed_issues.md   Issue tracking (ESX format)
├── esx/                             ESX project config and scientific profile
├── docs/                            ESX-owned code map and model contract
├── .claude/agents/                  Bob, Richard, Scout, Prober, Bisector, Auditor
│
├── 1D_Mixing_Model/                 Main codebase
│   ├── main/                        Shared physics and orchestration
│   │   ├── unified_driver.py        Master orchestrator (both schemes)
│   │   ├── run_scenarios.py         CLI entry point
│   │   ├── mixing_adapter.py        Adapter shared by both schemes
│   │   ├── eos.py                   JMD95 equation of state
│   │   ├── physics_basis.py         Shared physics (N², S², Ri)
│   │   ├── column_grid.py           Vertical grid (z positive up)
│   │   ├── column_state.py          State variables
│   │   ├── shared_column_solver.py  Implicit vertical solver
│   │   ├── diagnostics.py           Diagnostic output
│   │   ├── config_manager.py        YAML loader
│   │   └── unified_plotter.py       Profile and contour figures
│   │
│   ├── GGL90/                       GGL90 scheme
│   │   ├── ggl90_core_driver.py
│   │   ├── ggl90_scheme_specific.py
│   │   ├── ggl90_mixing_coefficients.py
│   │   ├── ggl90_parameters.py
│   │   └── ggl90_default_parameters.yaml
│   │
│   ├── KPP/                         KPP scheme
│   │   ├── kpp_core_driver.py
│   │   ├── kpp_scheme_specific.py   Boundary layer depth, BL mixing
│   │   ├── kpp_routines.py          Interior mixing
│   │   ├── kpp_shortwave.py         Shortwave penetration
│   │   ├── kpp_parameters.py
│   │   └── kpp_default_parameters.yaml
│   │
│   ├── configuration_yamls/         Shared config (physical params, GGL90 tunings)
│   ├── simulations/scenarios/       6 scenarios × 3 YAML files each
│   ├── tests/                       Test suite
│   ├── scripts/                     Analysis and scenario-generation utilities
│   ├── output/                      Run outputs and generated reports
│   └── docs/
│       ├── GGL90/                   LaTeX package + port descriptions (.tex/.pdf)
│       ├── KPP/                     LaTeX package + port descriptions (.tex/.pdf)
│       ├── dev_notes/               Implementation notes, staggering, KPP physics
│       └── porting/
│
├── scripts/                         KPP-vs-MITgcm validation pipeline
├── KPP_port_validation/             Validation data, analyses, reports
├── mitgcm_verification_mods/        Instrumented MITgcm sources (kpp_mods/)
├── MITgcm_wrappers/                 Standalone Fortran KPP wrapper (superseded path)
├── mitgcm_instrumentation/          Earlier instrumentation attempt
└── OLD_MARKDOWN_NO_LONGER_NEEDED/   Archived superseded documentation (includes the
                                     retired Three-Man-Team role files and handoff/)
```

## Core Concepts

### The Two Schemes

| Feature | GGL90 | KPP |
|---|---|---|
| Type | Prognostic (solves a TKE equation) | Diagnostic (bulk Richardson number) |
| Spinup | Required — TKE evolves gradually | None — responds immediately |
| Tuning | `alpha`, `mxl_max_flag` | `Ricr`, `cekman`, `cmonob` |
| Best for | Long spinup, climate runs | Immediate response, brief events |

### Scenarios

Six scenarios, each defined by three YAML files (initial conditions, atmospheric forcing, time
integration) in `1D_Mixing_Model/simulations/scenarios/`:

`arctic_convection`, `calm_baseline`, `combined_storm`, `heavy_rain_freshening`,
`hurricane_wind`, `tropical_heating_diurnal`

### Conventions

These match MITgcm and are load-bearing throughout the code:

- **Vertical coordinate**: z positive up — the surface is 0, depths are negative.
- **Staggering**: tracers at cell centers, diffusivities at interfaces ("top-of-cell").
- **Pressure**: positive, increasing with depth.
- **Surface heat flux (MITgcm side)**: negative means heat *into* the ocean. The Python KPP driver
  uses the opposite sign, so conversions at the boundary need care.

See `1D_Mixing_Model/docs/dev_notes/MITGCM_STAGGERING.md` for the index-by-index mapping.

## MITgcm Validation Pipeline

MITgcm's KPP is instrumented to emit its inputs and outputs at full precision, which are then
replayed through the Python port. Critically, the instrumentation captures `ustar`, `bo`, and
`bosol` — the friction velocity and buoyancy forcing terms that `KPP_FORCING_SURF` computes and KPP
actually consumes — rather than raw surface fluxes. This avoids having to reconstruct them and
inherit assumptions about `rhoConst` and `HeatCapacity_Cp`.

Three steps, run from the project root:

```bash
# 1. Parse instrumented MITgcm STDOUT into split input/output NetCDF
python scripts/parse_mitgcm_split.py output.txt <label>

# 2. Replay through the Python port (auto-compares if MITgcm outputs are present)
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/<inputs>.nc

# 3. Generate the PDF validation report
python scripts/generate_kpp_validation_report.py \
  KPP_port_validation/outputs_from_mitgcm/<mitgcm>.nc \
  KPP_port_validation/outputs_from_python/<python>.nc \
  KPP_port_validation/reports/validation_report.pdf
```

Building and running the instrumented MITgcm goes through the Docker helpers symlinked into
`MITgcm/verification/` (`experiment_compile.sh`, `experiment_run_no_compile.sh`); invoking
`genmake2` by hand hits assembler errors on arm64. Instrumented sources live in
`mitgcm_verification_mods/kpp_mods/`, and `mitgcm_verification_mods/FORTRAN_RULES.md` documents the
fixed-form constraints any edit must respect.

Open thread: lab_sea has parsed MITgcm outputs and inputs but no generated report yet — only the
1D 11k-timestep report exists in `KPP_port_validation/reports/`.

## Documentation

| Document | Contents |
|---|---|
| `CLAUDE.md` | Project context, coding standards; routes to the ESX-Team workflow |
| `esx/project_profile.md`, `docs/model_contract.md` | Full scientific/numerical contract |
| `open_issues.md` / `closed_issues.md` | Every suspected MITgcm inconsistency, with status |
| `scripts/README.md` | Validation pipeline reference |
| `KPP_port_validation/INVESTIGATION_CONCLUSION.md` | Final KPP validation verdict |
| `KPP_port_validation/VALIDATION_SUMMARY.md` | Headline validation statistics |
| `KPP_port_validation/NETCDF_DATA_FORMAT.md` | NetCDF format specification |
| `KPP_port_validation/reports/critical_lessons_fortran_to_python_porting.md` | Consolidated porting lessons |
| `KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md` | Suspected MITgcm-side KPP bugs |
| `1D_Mixing_Model/user_guide.md` | End-to-end model user guide |
| `1D_Mixing_Model/docs/{GGL90,KPP}/` | LaTeX package and port descriptions |
| `GGL90_DENSITY_GRADIENT_FIX_SUMMARY.md`, `DENSITY_GRADIENT_ANALYSIS.md` | GGL90 potential-density fix |

Superseded and stale documentation has been moved to `OLD_MARKDOWN_NO_LONGER_NEEDED/`, which mirrors
the original directory structure.

## Environment

- **Python**: 3.11.10 (conda env `ecco` at `/Users/ifenty/miniforge3/envs/ecco`)
- **Packages**: numpy, scipy, matplotlib, xarray, netCDF4, pyyaml, pytest
- **Run from**: `1D_Mixing_Model/` for model commands, project root for validation scripts
- **MITgcm reference source**: `/Users/ifenty/git_repo_others/MITgcm`
- **MITgcm Docker helpers**: `/Users/ifenty/git_repo_others/MITgcm_verification_docker`

## Contributing Notes

Two rules matter more than the rest:

1. **Every non-trivial function cites its MITgcm counterpart** — source file and line numbers, in a
   comment or docstring.
2. **Any suspected inconsistency with MITgcm gets documented in `open_issues.md` immediately**,
   using the blank template in that file, before any fix is attempted.
