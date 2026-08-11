# 1D Mixing Model

Python ports of MITgcm's KPP and GGL90 vertical mixing schemes, designed for scenario-driven 1-D ocean column experiments. This codebase enables rapid testing of mixing physics, parameter sensitivity studies, and generation of ML training data without running the full 3-D ocean model.

## Key Features

- **Two mixing schemes**: K-Profile Parameterization (KPP) and GGL90 turbulence closure
- **Unified driver interface**: run identical experiments with either scheme using the same configuration files
- **Scenario-based configuration**: YAML-driven initial conditions, atmospheric forcing, and time integration
- **Built-in test scenarios**: arctic convection, hurricane wind, heavy rain freshening, combined storm, and more
- **Validated physics**: implements MITgcm's equation of state (JMD95), potential density gradients, Richardson number mixing, and TKE evolution
- **Comprehensive diagnostics**: time series of temperature, salinity, velocity, mixing layer depth, turbulent kinetic energy, and mixing coefficients

## Repository Structure

```
1D_Mixing_Model/
├── README.md              # This file
├── user_guide.md          # Complete end-to-end usage documentation
├── conftest.py            # Pytest configuration
├── main/                  # Unified driver, adapters, config manager, EOS, physics basis
├── GGL90_ML/GGL90_PY/     # GGL90 turbulence closure implementation
├── KPP_ML/KPP_PY/         # KPP boundary layer mixing implementation
├── configuration_yamls/   # Shared physical parameters
├── simulations/scenarios/ # Built-in scenario configuration files
├── output/                # Experiment results and visualizations
├── visualizations/        # Additional plots and analysis outputs
├── docs/
│   ├── GGL90/             # GGL90 reports, package description, implementation notes
│   ├── KPP/               # KPP reports, package description, physics explanations
│   └── dev_notes/         # Implementation notes, staggering docs, refactoring reports
├── tests/                 # All test modules
└── scripts/
    ├── analysis/          # Diagnostic scripts (alpha_min, TKE oscillations, thresholds)
    └── scenario_generation/ # Training data generation from MITgcm output
```

## Quick Start

### 1. Set up environment
```bash
conda activate ecco  # or your environment with numpy, matplotlib, pyyaml, xarray
```

### 2. Run built-in scenarios
```bash
# Run all scenarios with both schemes
python main/run_scenarios.py

# Run a single scenario with KPP only
python main/run_scenarios.py --scheme kpp --scenario arctic_convection

# Run the example experiment with GGL90
python main/run_experiment_example.py --scheme ggl90
```

### 3. Results
Output files and plots are written to `output/` (or `../output/` relative to configuration directory). Each scenario produces:
- `<scheme>_experiment.npz`: full time series data
- `<scheme>_profiles.png`: snapshot profiles of T, S, velocity, mixing coefficients
- `<scheme>_contours.png`: time-depth contours of key variables

## Requirements

- Python 3.10+
- numpy
- matplotlib
- pyyaml
- xarray (for training data generation from MITgcm NetCDF)
- pytest (for running tests)

Install via conda environment `ecco` or equivalent.

## Documentation

See `user_guide.md` for complete documentation covering:
- Running built-in scenarios and custom experiments
- Choosing and configuring mixing schemes
- Setting up initial conditions and atmospheric forcing
- Creating your own experiments
- Running tests and analysis scripts

See `docs/` for detailed scheme physics, MITgcm validation reports, and implementation notes.

## Testing

Run the full test suite:
```bash
python -m pytest tests/ -q
```

## More Information

This repository is part of the ECCO 1D Mixing Experiments project. For questions or issues, refer to the documentation in `docs/` or the comprehensive developer notes in `docs/dev_notes/`.
