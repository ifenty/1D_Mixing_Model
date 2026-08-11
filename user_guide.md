# 1D Mixing Model User Guide

Complete end-to-end guide for running ocean mixing experiments with Python implementations of MITgcm's KPP and GGL90 schemes.

## Table of Contents
1. [Installation and Environment](#1-installation-and-environment)
2. [Repository Layout](#2-repository-layout)
3. [Running Built-in Scenarios](#3-running-built-in-scenarios)
4. [Choosing a Mixing Scheme](#4-choosing-a-mixing-scheme)
5. [Setting Up Initial Conditions](#5-setting-up-initial-conditions)
6. [Setting Up Atmospheric Forcing](#6-setting-up-atmospheric-forcing)
7. [Time Integration Configuration](#7-time-integration-configuration)
8. [Adding Your Own Experiment](#8-adding-your-own-experiment)
9. [Running Tests and Analysis Scripts](#9-running-tests-and-analysis-scripts)

---

## 1. Installation and Environment

### Requirements
- Python 3.10 or later
- numpy
- matplotlib
- pyyaml
- xarray (for training data generation)
- pytest (for running tests)

### Setup
Activate the conda environment with required dependencies:
```bash
conda activate ecco
```

All commands in this guide assume you are in the repository root (`1D_Mixing_Model/`) and have activated the environment.

---

## 2. Repository Layout

```
1D_Mixing_Model/
├── main/                     # Core driver and physics
│   ├── unified_column_driver.py  # Main experiment orchestration
│   ├── config_manager.py         # YAML configuration loader
│   ├── kpp_adapter.py, ggl90_adapter.py  # Scheme adapters
│   ├── eos.py                    # Equation of state (JMD95)
│   ├── physics_basis.py          # Shared physics (N², S², Ri)
│   ├── run_scenarios.py          # Run all built-in scenarios
│   └── run_experiment_example.py # Example single-experiment runner
├── GGL90_ML/GGL90_PY/        # GGL90 turbulence closure
│   ├── ggl90_core_driver.py
│   ├── ggl90_parameters.py
│   └── ggl90_*.py (scheme-specific modules)
├── KPP_ML/KPP_PY/            # KPP boundary layer mixing
│   ├── kpp_core_driver.py
│   ├── kpp_parameters.py
│   └── kpp_*.py (scheme-specific modules)
├── configuration_yamls/
│   └── physical_parameters.yaml  # Shared physical constants
├── simulations/scenarios/    # Built-in scenario YAML configs
├── output/                   # Results directory (created on first run)
├── tests/                    # Test suite
├── scripts/
│   ├── analysis/             # Diagnostic analysis tools
│   └── scenario_generation/  # Training data generation
└── docs/                     # Detailed reports and implementation notes
```

---

## 3. Running Built-in Scenarios

The repository includes several pre-configured scenarios demonstrating different ocean mixing regimes.

### Available Scenarios
- `arctic_convection`: deep winter convection with strong surface cooling
- `calm_baseline`: control case with light wind and moderate heat flux
- `combined_storm`: simultaneous hurricane-force wind and heavy precipitation
- `heavy_rain_freshening`: strong freshwater flux causing stratification
- `hurricane_wind`: extreme wind stress driving deep mixing
- `intermediate_wind`: moderate wind conditions
- `mild_convection`: modest surface cooling

### Run All Scenarios
```bash
python main/run_scenarios.py
```

This runs every scenario with both KPP and GGL90, writing results to `output/<scenario_name>/`.

### Run Specific Scenarios
```bash
# Run only arctic convection and hurricane wind
python main/run_scenarios.py --scenario arctic_convection hurricane_wind

# Run all scenarios with KPP only
python main/run_scenarios.py --scheme kpp

# Run with GGL90 only
python main/run_scenarios.py --scheme ggl90
```

### Run a Single Experiment
For more control over a single experiment, use `run_experiment_example.py`:
```bash
# Run with both schemes
python main/run_experiment_example.py

# Run KPP only
python main/run_experiment_example.py --scheme kpp

# Run GGL90 only
python main/run_experiment_example.py --scheme ggl90

# Skip plot generation (faster)
python main/run_experiment_example.py --no-plots

# Use custom configuration directory
python main/run_experiment_example.py --config-dir /path/to/configs

# Override convective adjustment diffusivity
python main/run_experiment_example.py --ivdc-kappa 10.0
```

### Command-Line Options

**`run_scenarios.py` options:**
- `--scheme {kpp,ggl90,both}`: which mixing scheme(s) to run (default: both)
- `--scenario NAME [NAME ...]`: run only specified scenarios (default: all)
- `--output-dir PATH`: output directory (default: `output/`)
- `--ggl90-yaml PATH`: GGL90 parameter override file
- `--kpp-yaml PATH`: KPP parameter override file
- `--ivdc-kappa FLOAT`: convective adjustment diffusivity (m^2/s)
- `--no-plots`: skip plot generation

**`run_experiment_example.py` options:**
- `--scheme {kpp,ggl90,both}`: which mixing scheme(s) to run (default: both)
- `--config-dir PATH`: configuration directory (default: `configuration_yamls/`)
- `--output-dir PATH`: output directory (default: `config-dir/../output`)
- `--n-profiles INT`: number of profile snapshots in plots (default: 5)
- `--no-plots`: skip figure generation
- `--kpp-yaml PATH`: KPP parameter override file
- `--ggl90-yaml PATH`: GGL90 parameter override file
- `--ivdc-kappa FLOAT`: convective adjustment diffusivity (m^2/s)

### Output Files
For each scenario and scheme, the following files are created in `output/<scenario_name>/`:
- `<scheme>_experiment.npz`: full time series data (load with `numpy.load()`)
- `<scheme>_profiles.png`: snapshot profiles of temperature, salinity, velocity, mixing coefficients
- `<scheme>_contours.png`: time-depth contours of temperature, salinity, velocity, MLD

---

## 4. Choosing a Mixing Scheme

### KPP (K-Profile Parameterization)
- **Best for**: surface boundary layer mixing, wind-driven entrainment, convective adjustment
- **Physics**: determines boundary layer depth based on bulk Richardson number criterion, applies shape functions for mixing within the boundary layer, handles interior shear and double-diffusive mixing
- **Key parameters**:
  - `crit_bulk_richardson`: bulk Richardson number threshold for boundary layer depth (default: 0.3)
  - `epsilon`: interior mixing efficiency (default: 0.1)
  - `vonkarman`: von Karman constant (default: 0.4)
  - `background_visc`, `background_diff`: minimum mixing coefficients

**Use KPP when** your scenario involves strong surface forcing (wind, cooling, heating) and you need to capture sharp transitions at the base of the mixed layer.

### GGL90 (Turbulence Closure)
- **Best for**: interior turbulence, stratified shear layers, time-evolving turbulent kinetic energy
- **Physics**: solves a prognostic TKE equation, applies local mixing based on TKE and mixing length, handles stable and unstable stratification, includes pressure-strain interaction
- **Key parameters**:
  - `alpha`: pressure-strain coefficient (default: 1.0; ECCOv4r4 uses 30.0)
  - `mxl_max_flag`: mixing length criterion (0=simple, 1=N-based, 2=N+S-based; default: 2)
  - `min_tke`: minimum TKE threshold to prevent numerical oscillations (default: 1e-6)
  - `background_visc`, `background_diff`: minimum mixing coefficients

**Use GGL90 when** you need to resolve interior mixing processes, stratified shear instabilities, or track TKE evolution over time.

**Important GGL90 notes:**
- The `alpha` parameter controls the partitioning of TKE production into dissipation vs. mixing. Small values (alpha=1) can produce numerical oscillations in the TKE field on coarse grids. ECCOv4 Release 4 uses alpha=30 to suppress these. See `docs/GGL90/00_GGL90_COMPREHENSIVE_REPORT.md` for analysis of alpha stability and the grid Reynolds number criterion.
- The mixing length method (`mxl_max_flag`) significantly affects mixed layer depth behavior. Method 2 (N+S-based) is the most physically complete but may produce deeper MLDs under weak stratification.

### Overriding Scheme Parameters
Both schemes load default parameters from built-in YAML files. You can override any parameter by providing a custom YAML:

**Example GGL90 override (`my_ggl90.yaml`):**
```yaml
alpha: 30.0
mxl_max_flag: 1
min_tke: 1.0e-5
background_visc: 1.0e-5
background_diff: 1.0e-5
```

**Example KPP override (`my_kpp.yaml`):**
```yaml
crit_bulk_richardson: 0.25
epsilon: 0.15
background_visc: 1.0e-4
background_diff: 1.0e-5
```

Use with:
```bash
python main/run_scenarios.py --ggl90-yaml my_ggl90.yaml --kpp-yaml my_kpp.yaml
```

---

## 5. Setting Up Initial Conditions

Initial condition files define the ocean column state at t=0. They follow the naming convention:
```
scenario_<name>_initial_conditions.yaml
```

### Required Fields
```yaml
initial_conditions:
  drF: [1.09, 1.16, ..., 26.14]     # Cell thicknesses (m), surface to bottom
  theta: [22.0, 22.0, ..., 6.0]     # Potential temperature (°C)
  salt: [35.5, 35.5, ..., 34.6]     # Salinity (PSU)
  u_vel: [0.0, 0.0, ..., 0.0]       # Zonal velocity (m/s)
  v_vel: [0.0, 0.0, ..., 0.0]       # Meridional velocity (m/s)
  coriol: 0.0001                    # Coriolis parameter (1/s)
```

### Conventions
- **Depth sign**: negative downward cell centers (depth[k] < 0 for all k)
- **Grid**: `drF` defines cell thickness; depth is computed as cumulative sum of face positions
- **Units**: velocities in m/s, salinity in PSU, temperature in °C

### Vertical Grid Design
The `drF` array controls vertical resolution. Common strategies:
- **Surface-refined**: fine resolution near surface (O(1m)) coarsening with depth (O(10-100m)). Captures sharp gradients in the mixed layer.
- **Uniform**: constant cell thickness. Simplest but may miss surface processes.
- **MITgcm-matched**: copy `drF` from MITgcm's `data` namelist to match a specific configuration (e.g., ECCOv4).

Example: 50-level surface-refined grid suitable for mixed-layer studies:
```yaml
drF: [1.09, 1.16, 1.24, 1.32, 1.41, 1.51, ..., 24.50, 26.14]  # exponentially stretching
```

### Initial Stratification
- **Stable stratification**: temperature and salinity decrease with depth (light over heavy)
- **Unstable stratification**: temperature decreases more slowly than needed to maintain stable density; drives convection
- **Uniform mixed layer**: constant T and S in surface layer (mimics pre-existing mixing)

**Example: Arctic convection initial condition**
```yaml
theta: [0.0, 0.0, 0.0, ..., 0.0, 0.5, 1.0, ..., 4.0]  # cold surface, warming at depth
salt: [34.0, 34.0, ..., 34.0, 34.2, 34.4, ..., 34.6]  # fresh surface, saltier below
```

---

## 6. Setting Up Atmospheric Forcing

Forcing files define surface fluxes that drive mixing. They follow the naming convention:
```
scenario_<name>_atmospheric_forcing.yaml
```

### Required Fields
```yaml
atmospheric_forcing:
  tau_x: 1.393e-05      # Zonal wind stress (m^2/s^2)
  tau_y: 0.0            # Meridional wind stress (m^2/s^2)
  q_net: -20.0          # Net surface heat flux (W/m^2, positive = ocean gains heat)
  q_sw: 100.0           # Shortwave radiation (W/m^2, positive = ocean gains heat)
  fw_flux: 0.0          # Freshwater flux (m/s, positive = precipitation/runoff into ocean)
  rho_water: 1029.0     # Reference seawater density (kg/m^3)
```

### Time Dependence
All built-in scenarios use time-invariant forcing (constant throughout the simulation). For time-varying forcing, modify the driver to read time-series data.

### Wind Stress
- Units: m^2/s^2 (already divided by rho_water)
- Typical values:
  - Light wind (3 m/s): tau ~ 1.4e-5 m^2/s^2
  - Moderate wind (10 m/s): tau ~ 1.5e-4 m^2/s^2
  - Hurricane (50 m/s): tau ~ 3.8e-3 m^2/s^2
- Conversion from 10m wind speed:
  ```
  tau = rho_air * Cd * U10^2 / rho_water
  ```
  where `Cd = 1.3e-3` (drag coefficient), `rho_air = 1.225 kg/m^3`

### Heat Fluxes
- `q_net`: total heat flux (longwave, latent, sensible). Negative = ocean loses heat (cooling).
- `q_sw`: shortwave (solar) radiation. Positive = ocean gains heat (heating).
- Net surface heating = `q_net + q_sw` (both are added to the ocean)
- Typical values:
  - Strong cooling (winter, high latitude): q_net = -200 W/m^2, q_sw = 50 W/m^2
  - Moderate heating (summer, mid-latitude): q_net = -20 W/m^2, q_sw = 200 W/m^2

### Freshwater Flux
- Units: m/s (equivalent volumetric flux)
- Positive = freshwater into ocean (precipitation, runoff, ice melt)
- Negative = evaporation or brine rejection
- Typical values:
  - Heavy rain: fw_flux = 1.0e-6 m/s (~ 86 mm/day)
  - Moderate rain: fw_flux = 1.0e-7 m/s (~ 8.6 mm/day)

**Example: Hurricane wind scenario**
```yaml
atmospheric_forcing:
  tau_x: 3.825e-03   # 50 m/s wind
  tau_y: 0.0
  q_net: -50.0       # Moderate cooling
  q_sw: 50.0         # Low solar (cloudy)
  fw_flux: 1.0e-6    # Heavy rain
  rho_water: 1029.0
```

---

## 7. Time Integration Configuration

Time integration files control simulation duration and output frequency. They follow the naming convention:
```
scenario_<name>_time_integration.yaml
```

### Required Fields
```yaml
time_integration:
  dt_seconds: 600.0              # Time step (seconds)
  n_steps: 288                   # Total number of time steps
  output_frequency_steps: 6      # Save output every N steps
```

### Time Step Selection
- **Stability**: choose `dt_seconds` small enough to satisfy CFL condition for diffusion and advection
- **Typical values**:
  - Fast processes (strong wind, shallow grid): dt = 60-300 seconds
  - Moderate processes: dt = 600 seconds (10 minutes)
  - Slow processes (deep column, weak forcing): dt = 1200-3600 seconds
- **Rule of thumb**: dt < (dz^2) / (2 * max(kappa_vertical))

### Duration and Output
- Total simulation time = `dt_seconds * n_steps`
- Output frequency = `dt_seconds * output_frequency_steps`
- Example: dt=600s, n_steps=288, output_frequency_steps=6
  - Total duration: 288 * 600 = 172,800 seconds = 48 hours
  - Output interval: 6 * 600 = 3,600 seconds = 1 hour
  - Number of output snapshots: 288 / 6 = 48

**Example: 48-hour simulation with hourly output**
```yaml
time_integration:
  dt_seconds: 600.0
  n_steps: 288
  output_frequency_steps: 6
```

**Example: 7-day simulation with 6-hour output**
```yaml
time_integration:
  dt_seconds: 600.0
  n_steps: 1008         # 7 days * 24 hours * 6 steps/hour
  output_frequency_steps: 36  # 6 hours * 6 steps/hour
```

---

## 8. Adding Your Own Experiment

Follow these steps to create a custom mixing experiment.

### Step 1: Choose a Scenario Name
Pick a descriptive name for your experiment (e.g., `my_experiment`, `spring_bloom`, `eddyA`).

### Step 2: Create Three YAML Files
Copy template files from an existing scenario (e.g., `calm_baseline`) and rename them:
```bash
cd simulations/scenarios/
cp scenario_calm_baseline_initial_conditions.yaml scenario_my_experiment_initial_conditions.yaml
cp scenario_calm_baseline_atmospheric_forcing.yaml scenario_my_experiment_atmospheric_forcing.yaml
cp scenario_calm_baseline_time_integration.yaml scenario_my_experiment_time_integration.yaml
```

### Step 3: Edit Initial Conditions
Open `scenario_my_experiment_initial_conditions.yaml` and modify:
1. **Vertical grid**: adjust `drF` to match your resolution needs
2. **Temperature profile**: edit `theta` to set initial stratification
3. **Salinity profile**: edit `salt` to set initial density structure
4. **Velocity**: edit `u_vel` and `v_vel` if starting with non-zero flow
5. **Coriolis**: edit `coriol` to match latitude (f = 2 * Omega * sin(lat), where Omega = 7.292e-5 rad/s)

**Example: Mid-latitude stratified column**
```yaml
initial_conditions:
  drF: [2.0, 2.0, 2.0, ..., 50.0, 50.0]  # 50 levels, surface-refined
  theta: [20.0, 19.8, 19.6, ..., 8.0, 7.5, 7.0]  # warm surface, cold deep
  salt: [35.0, 35.0, 35.0, ..., 34.8, 34.8, 34.8]  # uniform salinity
  u_vel: [0.05, 0.05, ..., 0.01, 0.0, 0.0]  # weak eastward flow, decaying with depth
  v_vel: [0.0, 0.0, ..., 0.0]  # no meridional flow
  coriol: 1.0e-4  # ~40°N
```

### Step 4: Edit Atmospheric Forcing
Open `scenario_my_experiment_atmospheric_forcing.yaml` and set surface fluxes:
```yaml
atmospheric_forcing:
  tau_x: 1.5e-4      # 10 m/s wind
  tau_y: 0.0
  q_net: -50.0       # Moderate cooling
  q_sw: 150.0        # Daytime solar heating
  fw_flux: 0.0       # No precipitation
  rho_water: 1029.0
```

### Step 5: Edit Time Integration
Open `scenario_my_experiment_time_integration.yaml` and set:
```yaml
time_integration:
  dt_seconds: 600.0       # 10-minute time step
  n_steps: 1440           # 10 days (1440 steps * 600s = 10 days)
  output_frequency_steps: 12  # Save every 2 hours (12 steps * 600s)
```

### Step 6: Run Your Experiment
```bash
python main/run_scenarios.py --scenario my_experiment
```

Or run with a specific scheme and custom parameters:
```bash
python main/run_scenarios.py --scenario my_experiment --scheme ggl90 --ggl90-yaml my_ggl90_params.yaml
```

### Step 7: Analyze Results
Results are written to `output/my_experiment/`:
- Load the NPZ file to analyze time series:
  ```python
  import numpy as np
  data = np.load('output/my_experiment/ggl90_experiment.npz')
  print(data.files)  # List all variables
  temperature = data['temperature']  # Shape: (n_times, n_depths)
  mld = data['mld']  # Mixed layer depth time series
  ```
- View the generated plots in `output/my_experiment/ggl90_profiles.png` and `ggl90_contours.png`

---

## 9. Running Tests and Analysis Scripts

### Test Suite
The repository includes unit tests, integration tests, and validation tests covering:
- Physics basis functions (N², S², Ri)
- Equation of state (JMD95)
- Scheme-specific logic (KPP boundary layer, GGL90 TKE evolution)
- Cross-scheme consistency
- Full scenario validation

Run all tests:
```bash
python -m pytest tests/ -q
```

Run a specific test module:
```bash
python -m pytest tests/test_physics_basis.py -v
```

Run tests with detailed output:
```bash
python -m pytest tests/ -v --tb=short
```

### Analysis Scripts
Three diagnostic scripts are available in `scripts/analysis/`:

#### 1. Diagnose TKE Oscillations
Analyzes TKE oscillation behavior in GGL90 simulations:
```bash
python scripts/analysis/diagnose_tke_oscillations.py
```
Examines grid Reynolds number, time step sensitivity, TKE spatial gradients, and dissipation treatment.

#### 2. Diagnose Oscillation Threshold
Systematically tests alpha values to identify oscillation onset:
```bash
python scripts/analysis/diagnose_oscillation_threshold.py
```
Runs a scenario with varying alpha and reports amplitude metrics.

#### 3. Compute Alpha Minimum
Computes the minimum stable alpha based on grid Reynolds number criterion:
```bash
python scripts/analysis/compute_alpha_min.py
```
Post-processes simulation results to determine alpha_min from Re_grid throughout the time series. See `docs/GGL90/00_GGL90_COMPREHENSIVE_REPORT.md` for details on the alpha stability criterion.

### Training Data Generation
Generate ML training data from MITgcm NetCDF output:
```bash
python scripts/scenario_generation/generate_training_data.py \
    /path/to/mitgcm_output.nc \
    /path/to/training_data.npz \
    --config my_kpp_params.yaml \
    --time-indices 0 10 20 30 \
    --spatial-stride 2
```

Options:
- `--config`: KPP parameter override YAML
- `--time-indices`: subset of time steps to process
- `--spatial-stride`: spatial sampling rate (1 = all grid points)
- `--vertical-subsample N`: subsample to N vertical levels
- `--no-diagnostics`: skip saving diagnostic fields
- `--physical-parameters-yaml`: path to shared physical constants

Note: Requires MITgcm output in NetCDF format with standard variable names (T, S, U, V, etc.).

---

## Summary

This guide covers the complete workflow for running ocean mixing experiments:
1. Set up your conda environment with required packages
2. Choose a mixing scheme (KPP or GGL90) based on your physics goals
3. Run built-in scenarios to familiarize yourself with the interface
4. Create custom experiments by editing three YAML files (initial conditions, forcing, time integration)
5. Analyze results using the generated NPZ files and plots
6. Run tests to verify code behavior and physics consistency
7. Use analysis scripts to diagnose TKE oscillations, alpha stability, and other diagnostics

For deeper understanding of the mixing physics, consult the detailed reports in `docs/GGL90/` and `docs/KPP/`. For implementation details and refactoring history, see `docs/dev_notes/`.

Happy mixing!
