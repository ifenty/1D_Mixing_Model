# 1D Mixing Model

Python ports of MITgcm's KPP and GGL90 vertical mixing schemes, designed for scenario-driven 1-D ocean column experiments. This codebase enables rapid testing of mixing physics, parameter sensitivity studies, and generation of ML training data without running the full 3-D ocean model.

## Key Features

- **Two mixing schemes**: K-Profile Parameterization (KPP) and GGL90 turbulence closure
- **Unified driver interface**: run identical experiments with either scheme using the same configuration files
- **Scenario-based configuration**: YAML-driven initial conditions, atmospheric forcing, and time integration
- **Built-in test scenarios**: arctic convection, hurricane wind, heavy rain freshening, combined storm, tropical diurnal heating, and a calm baseline
- **Validated physics**: implements MITgcm's equation of state (JMD95), potential density gradients, Richardson number mixing, and TKE evolution, with vertical staggering that overlays MITgcm output index-for-index
- **Comprehensive diagnostics**: time series of temperature, salinity, velocity, turbulent kinetic energy, mixing length, and mixing coefficients

## Repository Structure

```
1D_Mixing_Model/
├── README.md              # This file
├── user_guide.md          # Complete end-to-end usage documentation
├── conftest.py            # Pytest configuration
├── main/                  # Unified driver, adapters, config manager, EOS, physics basis, solver, plotter
├── GGL90_ML/GGL90_PY/     # GGL90 turbulence closure implementation + default parameter YAML
├── KPP_ML/KPP_PY/         # KPP boundary layer mixing implementation + default parameter YAML
├── configuration_yamls/   # Shared physical parameters + example GGL90 override configs
├── simulations/scenarios/ # Built-in scenario configuration files (6 scenarios × 3 files each)
├── tests/                 # All test modules
├── scripts/
│   ├── analysis/          # Diagnostic scripts (alpha_min, TKE oscillations, oscillation threshold)
│   └── scenario_generation/ # Training data generation from MITgcm output
└── docs/
    ├── GGL90/             # GGL90_package_description.tex (physics) + GGL90_port_description.tex (port map)
    ├── KPP/               # KPP_package_description.tex (physics) + KPP_port_description.tex (port map)
    ├── porting/           # porting_lessons.md — insights for future Fortran→Python porting work
    ├── dev_notes/         # Implementation notes, MITgcm staggering, physics explanations
    └── ML/                # ML draft notes
```

## Quick Start

### 1. Set up environment
```bash
conda activate ecco  # or your environment with numpy, matplotlib, pyyaml, xarray
```

### 2. Run built-in scenarios
```bash
# Run all 6 scenarios with both schemes
python main/run_scenarios.py

# Run a single scenario with KPP only
python main/run_scenarios.py --scheme kpp --scenario arctic_convection

# Run the example experiment with GGL90
python main/run_experiment_example.py --scheme ggl90
```

### 3. Results
Results are written to an `output/` directory in the repository root by default
(git-ignored); pass `--output-dir PATH` to choose another location. Each
scenario/scheme produces, under `output/<scenario_name>/`:
- `<scheme>_experiment.npz`: full time series data (load with `numpy.load()`)
- `<scheme>_profiles.png`: snapshot profiles of T, S, velocity, mixing coefficients
- `<scheme>_contours.png`: time-depth contours of key variables

Generated `output/` and `visualizations/` directories are git-ignored, so experiment
results and figures never clutter the repository.

## Requirements

- Python 3.10+
- numpy
- matplotlib
- pyyaml
- xarray (for training data generation from MITgcm NetCDF)
- pytest (for running tests)

Install via conda environment `ecco` or equivalent.

## Documentation

See `user_guide.md` for complete documentation covering running scenarios, choosing
and configuring mixing schemes, setting up initial conditions and forcing, and adding
your own experiments.

For the mixing physics and implementation, each scheme has two LaTeX reference documents
with identical structure (open them side-by-side to compare schemes):

| Scheme | Physics reference | Port reference (Fortran→Python map) |
|--------|-------------------|-------------------------------------|
| GGL90  | `docs/GGL90/GGL90_package_description.tex` | `docs/GGL90/GGL90_port_description.tex` |
| KPP    | `docs/KPP/KPP_package_description.tex`     | `docs/KPP/KPP_port_description.tex`     |

- **`*_package_description.tex`** — the physics of each mixing scheme (governing equations, boundary/interior mixing, diagnostics, validation).
- **`*_port_description.tex`** — how the Python port maps onto the MITgcm Fortran, organized by code flow with file + line-number references in both languages.
- **`docs/porting/porting_lessons.md`** — cross-cutting lessons (sign conventions, 1-based↔0-based indexing, vertical staggering, unit verification) for anyone extending the ports.

## Testing

Run the full test suite:
```bash
python -m pytest tests/ -q
```

## More Information

This repository is part of the ECCO 1D Mixing Experiments project. For deeper physics
and implementation background, see the LaTeX references above and the developer notes in
`docs/dev_notes/`.
