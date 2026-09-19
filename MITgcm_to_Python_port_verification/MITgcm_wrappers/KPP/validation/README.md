# KPP Wrapper Validation Framework

This directory contains scripts to validate the MITgcm KPP Fortran wrapper against the Python KPP port by comparing outputs on identical inputs across multiple timesteps.

## Workflow

```
┌─────────────────────┐
│ Python KPP Port     │  Run on scenario, export inputs/outputs
│ (export)            │  at each timestep
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Convert to Binary   │  Convert numpy arrays to Fortran binary format
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ MITgcm Wrapper      │  Run wrapper on each timestep independently
│ (batch run)         │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Compare Outputs     │  Compute differences, report pass/fail
└─────────────────────┘
```

## Quick Start

### One-Command Validation

```bash
./run_validation.sh \
    ../../1D_Mixing_Model/configuration_yamls/initial_conditions.yaml \
    ./validation_output \
    10
```

This runs the complete workflow:
1. Exports 10 timesteps from Python KPP port
2. Converts to binary format
3. Runs wrapper on all timesteps
4. Compares outputs

### Step-by-Step (for debugging)

#### Step 1: Export Python port data

```bash
python export_kpp_port_data.py \
    --scenario ../../1D_Mixing_Model/configuration_yamls/initial_conditions.yaml \
    --output_dir ./validation_output \
    --num_steps 10 \
    --export_interval 1
```

Creates:
```
validation_output/
  manifest.yaml
  timestep_0000/
    inputs.npz              # Grid, state, forcing
    outputs_expected.npz    # Expected mixing coefficients, hbl, ghat
  timestep_0001/
    ...
```

#### Step 2: Convert to wrapper format

```bash
python convert_to_wrapper_format.py \
    --input_dir ./validation_output
```

Adds `input.bin` to each timestep directory (Fortran big-endian binary).

#### Step 3: Run wrapper on all timesteps

```bash
./run_wrapper_batch.sh ./validation_output
```

Runs `kpp_wrapper` on each timestep, saves CSV output to `wrapper_output.csv`.

#### Step 4: Compare outputs

```bash
python compare_wrapper_vs_port.py \
    --validation_dir ./validation_output \
    --rtol 1e-12 \
    --verbose
```

Compares wrapper vs port for:
- `KPPviscAz` - Vertical viscosity
- `KPPdiffKzT` - Thermal diffusivity  
- `KPPdiffKzS` - Salinity diffusivity
- `KPPghat` - Counter-gradient term
- `KPPhbl` - Boundary layer depth

Reports:
- Max absolute difference
- RMS difference
- Correlation coefficient
- Pass/fail (relative tolerance 1e-12)

## Output Format

### Timestep Directory Structure

```
timestep_0000/
  inputs.npz              # Numpy: grid, state, forcing (from Python port)
  outputs_expected.npz    # Numpy: mixing outputs (from Python port)
  input.bin              # Binary: inputs for wrapper
  wrapper_output.csv     # CSV: wrapper outputs
```

### CSV Output Format (from wrapper)

```csv
===== KPP_GRID_GEOMETRY =====
GRID_GEOM,k,drF,rF,rC
===== KPP_VALIDATION_START =====
INPUT_STATE,i,j,k,theta,salt,uVel,vVel
INPUT_FORCING,i,j,tau_x,tau_y,q_net,qsw,fw_flux
INPUT_CORIOLIS,i,j,f
OUTPUT_MIXING,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat
OUTPUT_HBL,i,j,hbl
===== KPP_VALIDATION_END =====
```

## Scenarios

The validation framework can test any scenario defined in the Python port's YAML configs:

- **Arctic convection** - Deep winter mixing
- **Hurricane forcing** - Strong wind-driven mixing
- **Tropical warming** - Restratification
- **Freshwater event** - Surface stratification

To create a custom scenario:

1. Create YAML config with:
   - `grid`: drF array, Nr
   - `initial_conditions`: theta, salt, uVel, vVel profiles
   - `atmospheric_forcing`: tau_x, tau_y, Q_net, Q_sw, fw_flux
   - `kpp_parameters`: (optional) KPP tuning parameters

2. Run validation:
   ```bash
   ./run_validation.sh path/to/scenario.yaml ./output 50
   ```

## Interpreting Results

### Pass Criteria

A timestep **passes** if for all fields:
```
max(|wrapper - port|) / max(|port|) < rtol
```

Default `rtol = 1e-12` (near machine precision for double precision).

### Common Failure Modes

1. **Grid mismatch**: Check that Nr in wrapper SIZE.h matches scenario
2. **Missing initialization**: Wrapper may need additional parameters (data.kpp)
3. **Physics differences**: Wrapper uses different numerics than port
4. **Floating point differences**: Legitimate differences at ~1e-14 level

### Tolerance Guidelines

- `rtol < 1e-14`: Machine precision (perfect match)
- `rtol < 1e-12`: Excellent agreement (expected)
- `rtol < 1e-6`: Good agreement (minor numerics)
- `rtol > 1e-3`: Significant differences (investigate)

## Debugging Failed Tests

1. **Check inputs are identical**:
   ```python
   import numpy as np
   inputs = np.load('timestep_0000/inputs.npz')
   print(inputs['theta'])  # Should match wrapper INPUT_STATE
   ```

2. **Examine specific timestep**:
   ```bash
   python compare_wrapper_vs_port.py \
       --validation_dir ./validation_output \
       --verbose
   ```

3. **Test single timestep manually**:
   ```bash
   cd timestep_0000
   ../../kpp_wrapper < input.bin > debug_output.csv
   # Compare with outputs_expected.npz
   ```

4. **Check wrapper stdout for errors**:
   ```bash
   grep -i error timestep_*/wrapper_output.csv
   ```

## Requirements

- Python 3.9+ with numpy, pyyaml
- MITgcm wrapper built: `cd .. && make`
- Python KPP port: `../../1D_Mixing_Model/KPP/`
- Conda environment: `ecco` (or modify `PYTHON_ENV` in `run_validation.sh`)

## Files

- `run_validation.sh` - Master script (runs entire workflow)
- `export_kpp_port_data.py` - Export Python port data
- `convert_to_wrapper_format.py` - Convert to binary format
- `run_wrapper_batch.sh` - Run wrapper on all timesteps
- `compare_wrapper_vs_port.py` - Compare and report differences
- `README.md` - This file

## Notes

- Each wrapper invocation is **independent** (single timestep, no time integration)
- This tests **KPP physics only**, not full MITgcm integration
- Grid geometry must match between SIZE.h and scenario (recompile if needed)
- Wrapper expects `input.bin` in current directory or symlinked

## Future Enhancements

- [ ] Plot comparison profiles (--plot option)
- [ ] Test with varying KPP parameters
- [ ] Multi-timestep time-integrated tests
- [ ] Performance benchmarking (wrapper vs port speed)
- [ ] Automated regression testing (CI/CD)
