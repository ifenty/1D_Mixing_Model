# KPP Validation User Guide

This guide walks you through the complete workflow for validating the Python KPP port against MITgcm reference outputs.

## Quick Start

**Goal**: Generate input/output NetCDF files from MITgcm, run Python KPP, and compare results.

**Time Required**: ~30 minutes for first run, ~5 minutes for subsequent runs

**Prerequisites**:
- MITgcm compiled with KPP enabled
- Python environment with xarray, numpy, matplotlib
- Scripts: `parse_mitgcm_split.py`, `run_kpp_from_split.py`, `compare_kpp_outputs.py`

---

## Complete Validation Workflow

### Step 1: Run MITgcm with KPP Parameter Export

First, compile and run MITgcm with the modified `kpp_calc.F` that outputs validation data:

```bash
cd /path/to/MITgcm/verification/lab_sea
mkdir build && cd build
../../../tools/genmake2 -mods ../code -optfile /path/to/your/optfile
make depend
make
cd ..
mkdir run && cd run
ln -s ../input/* .
ln -s ../build/mitgcmuv .
./mitgcmuv > output.txt 2>&1
```

**What happens**: Modified `kpp_calc.F` writes validation data to STDOUT in tagged format:
- `OUTPUT_INPUTS`: Grid, forcing, state variables
- `OUTPUT_PARAMS`: Runtime parameters (Ri_c, nu0, etc.)
- `OUTPUT_DIAGNOSTICS`: Shear², buoyancy frequency², Richardson number
- `OUTPUT_MIXING`: Mixing coefficients (visc_az, diff_kz_s, diff_kz_t)
- `OUTPUT_NONLOCAL`: Non-local transport (ghat)
- `OUTPUT_HBL`: Boundary layer depth

**Check for success**:
```bash
grep "OUTPUT_INPUTS" output.txt | head -3
grep "OUTPUT_PARAMS" output.txt | head -1
```

You should see tagged CSV-style output lines. If empty, check that KPP is enabled in `data.pkg`.

---

### Step 2: Parse MITgcm Output to NetCDF Files

Convert raw STDOUT to split NetCDF format (inputs and outputs separate):

```bash
cd /path/to/mitgcm/run
python /path/to/1D_Mixing_Experiments/scripts/parse_mitgcm_split.py \
  output.txt \
  lab_sea
```

**Arguments**:
- `output.txt`: MITgcm STDOUT file containing tagged validation data
- `lab_sea`: Experiment name (optional, recorded in metadata)

**Outputs Created** (in same directory as output.txt):
- `mitgcm_kpp_inputs.nc`
- `mitgcm_kpp_outputs.nc`

**Check for success**:
```bash
ncdump -h mitgcm_kpp_inputs.nc | head -50
```

Should show dimensions (time, x, y, z, z_iface) and variables (temperature, salinity, u_velocity, v_velocity, etc.).

**Move to validation directory** (optional but recommended):
```bash
cd /path/to/1D_Mixing_Experiments
timestamp=$(date +%Y%m%dT%H%M%S)
mv /path/to/mitgcm/run/mitgcm_kpp_inputs.nc \
   KPP_port_validation/inputs_from_mitgcm/kpp_input_lab_sea_${timestamp}.nc
mv /path/to/mitgcm/run/mitgcm_kpp_outputs.nc \
   KPP_port_validation/outputs_from_mitgcm/kpp_output_lab_sea_${timestamp}.nc
```

**Common Issues**:
- **No output files created**: Check that `output.txt` contains tagged lines (`grep OUTPUT_INPUTS output.txt`)
- **Dimensions mismatch**: Verify MITgcm grid size matches expected shape
- **Missing data (zeros in NetCDF)**: Some grid points may have zero values if MITgcm output was truncated or KPP didn't activate there

---

### Step 3: Run Python KPP Port with MITgcm Inputs

Execute Python KPP using the MITgcm input file:

```bash
cd /path/to/1D_Mixing_Experiments
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/kpp_input_lab_sea_YYYYMMDDTHHMMSS.nc
```

Or specify output directory explicitly:

```bash
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/kpp_input_lab_sea_YYYYMMDDTHHMMSS.nc \
  KPP_port_validation/outputs_from_python
```

**Arguments**:
- `<input_file.nc>`: Path to KPP input NetCDF file (required)
- `[output_dir]`: Output directory (optional, see output location logic below)

**What happens**:
1. Loads input NetCDF (temperature, salinity, velocities, forcing, parameters)
2. Initializes Python KPP with extracted parameters
3. Runs KPP for each timestep and column
4. Saves outputs (automatically determines location)

**Output Location Logic**:
The script intelligently determines where to save outputs:

1. **If input from `inputs_from_mitgcm/`**: Automatically saves to `outputs_from_python/` with matching filename
   - Input: `inputs_from_mitgcm/kpp_input_lab_sea_20260819T143022.nc`
   - Output: `outputs_from_python/kpp_output_lab_sea_20260819T143022.nc`

2. **Else if `output_dir` provided**: Saves to specified directory as `python_kpp_outputs.nc`

3. **Else**: Saves to same directory as input file as `python_kpp_outputs.nc`

**Provenance Tracking**: Python output includes:
- `input_uuid`: UUID from input file (traceable back to MITgcm run)
- `input_file_name`: Name of input file used
- `input_file_path`: Absolute path to input file

**Check for success**:
```bash
ncdump -h ../KPP_port_validation/outputs_from_python/kpp_output_*.nc | grep input_uuid
```

Should show the UUID matching the input file.

**Quick Comparison**: If `mitgcm_kpp_outputs.nc` exists in same directory as inputs, the script automatically performs a quick comparison and prints statistics (HBL differences, mixing coefficient errors).

**Current Validation Results** (11,000 timestep 1D_ocean_ice_column):
- Mean relative error: 0.18%
- RMS error: 0.72 m
- 99.63% of timesteps within 10% error
- Median relative error: 0.0005%
- Status: ✅ **VALIDATION SUCCESSFUL**

**Common Issues**:
- **Import errors**: Activate correct conda environment (`conda activate ecco`)
- **NaN outputs**: Check input data quality (e.g., zero/missing fields in MITgcm)
- **Shape mismatches**: Verify grid dimensions consistent between input and Python arrays
- **Output location confusion**: Check output location logic above - script may save to different location than expected

---

### Step 4: Generate Validation Report

Compare MITgcm vs Python KPP outputs and create comprehensive PDF validation report:

```bash
cd /path/to/1D_Mixing_Experiments
python scripts/generate_kpp_validation_report.py \
  KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc \
  KPP_port_validation/outputs_from_python/mitgcm_kpp_inputs_11k_1D_python.nc \
  KPP_port_validation/reports/validation_report.pdf
```

Or with explicit file paths:

```bash
python scripts/generate_kpp_validation_report.py \
  outputs_from_mitgcm/kpp_output_lab_sea_YYYYMMDDTHHMMSS.nc \
  outputs_from_python/kpp_output_lab_sea_YYYYMMDDTHHMMSS.nc \
  reports/validation_lab_sea.pdf
```

**Arguments**:
- First file: MITgcm reference output (required)
- Second file: Python port output (required)
- Third file: Output PDF report path (optional, defaults to `kpp_validation_report_YYYYMMDDTHHMMSS.pdf`)

**Report Contents** (multi-page PDF):
1. **Title Page**: Metadata, dimensions, UUID provenance check
2. **HBL Comparison**: Time series, scatter plot, difference histogram, statistics
3. **Mixing Coefficient Profiles**: Vertical profiles for visc_az, diff_kz_s, diff_kz_t (if 1D column)
4. **Mixing Statistics**: Detailed error analysis for all mixing coefficients
5. **Validation Summary**: Overall pass/fail assessment with acceptance criteria

**Acceptance Criteria**:
- **✅ EXCELLENT**: HBL < 0.1m, mixing < 0.1% median error
- **✅ GOOD**: HBL < 1.0m, mixing < 1.0% median error
- **⚠️ CHECK**: Exceeds thresholds - requires investigation

**Check report**:
```bash
open KPP_port_validation/reports/validation_report.pdf
```

Look for green checkmarks (✅) in the summary page. Any warnings (⚠️) require investigation.

**Common Issues**:
- **UUID mismatch warning**: Files from different input runs, not directly comparable
- **Large HBL differences**: Check for bug in boundary layer depth calculation
- **High relative errors in mixing**: Look for indexing errors, missing terms, or sign flips

---

## Directory Structure After Complete Run

```
KPP_port_validation/
├── NETCDF_FORMAT.md                    # Technical specification (this file)
├── USER_GUIDE.md                       # Workflow guide
│
├── inputs_from_mitgcm/
│   ├── kpp_input_lab_sea_20260819T143022.nc
│   └── kpp_input_1D_ocean_ice_20260820T091545.nc
│
├── outputs_from_mitgcm/
│   ├── kpp_output_lab_sea_20260819T143022.nc
│   └── kpp_output_1D_ocean_ice_20260820T091545.nc
│
├── inputs_from_python/
│   └── (typically empty - Python uses MITgcm inputs)
│
├── outputs_from_python/
│   ├── kpp_output_lab_sea_20260819T143022.nc
│   └── kpp_output_1D_ocean_ice_20260820T091545.nc
│
└── reports/
    ├── validation_report_lab_sea.pdf
    └── validation_report_1D_ocean_ice.pdf
```

**Key Points**:
- Matching timestamps ensure input/output correspondence
- UUIDs provide full provenance chain
- Python outputs reference their input files explicitly

---

## Advanced Usage

### Running Subsets of Timesteps

If MITgcm output is very large, you can parse only specific timesteps:

```bash
python parse_mitgcm_split.py output.txt lab_sea \
  --timesteps 0,5,10  # Only parse timesteps 0, 5, and 10
```

### Custom Parameter Files

If you want to override MITgcm parameters in Python run:

```python
from run_kpp_from_split import run_kpp_from_split_file
from KPP.kpp_parameters import KPPParameters

# Load custom parameters
custom_params = KPPParameters(
    Ri_c=0.30,  # Different critical Richardson number
    # ... other overrides
)

run_kpp_from_split_file(
    input_file="inputs_from_mitgcm/kpp_input_lab_sea_*.nc",
    params=custom_params
)
```

**Warning**: Using custom parameters breaks provenance - output won't match MITgcm!

### Comparing Multiple Experiments

Generate batch comparison reports:

```bash
for exp in lab_sea 1D_ocean_ice tutorial_plume_on_slope; do
  python compare_kpp_outputs.py \
    outputs_from_mitgcm/kpp_output_${exp}_*.nc \
    outputs_from_python/kpp_output_${exp}_*.nc \
    reports/validation_${exp}.pdf
done
```

### Extracting Specific Grid Columns

For debugging specific locations, extract single column from NetCDF:

```python
import xarray as xr

ds = xr.open_dataset("inputs_from_mitgcm/kpp_input_lab_sea_*.nc")
column = ds.isel(x=10, y=8)  # Extract column at (i=10, j=8)
column.to_netcdf("debug_column_10_8.nc")
```

Then run Python KPP on this single column for detailed analysis.

---

## Validation Criteria

### Acceptable Tolerance Levels

For publication-quality validation:

| Quantity | Acceptable Tolerance | Notes |
|----------|---------------------|-------|
| HBL | < 0.1 m | Boundary layer depth |
| visc_az (active) | < 0.1% relative | Where > 1e-6 m²/s |
| diff_kz_s (active) | < 0.1% relative | Where > 1e-6 m²/s |
| diff_kz_t (active) | < 0.1% relative | Where > 1e-6 m²/s |
| ghat (active) | < 1% relative | Where |ghat| > 1e-10 |
| shear_sq | < 1% relative | S² diagnostic |
| buoy_freq_sq | < 1% relative | N² diagnostic |
| richardson | < 1% relative | Ri = N²/S² |

### Interpreting Results

**Perfect Agreement (✅✅)**:
- All metrics within acceptable tolerance
- UUID provenance matches
- No warnings in comparison report

**Good Agreement (✅)**:
- 95%+ of test cases pass
- Max differences within 10× tolerance
- Discrepancies isolated to edge cases

**Needs Investigation (⚠️)**:
- Any test case fails by >10× tolerance
- Systematic bias in differences
- Physical implausibility in outputs

**Critical Failure (🔴)**:
- Crashes or NaN outputs
- Sign flips or order-of-magnitude errors
- HBL differences > 10 m

---

## Troubleshooting Guide

### Problem: "No OUTPUT_INPUTS found in MITgcm output"

**Diagnosis**: Modified `kpp_calc.F` not being used in compilation.

**Solutions**:
1. Check that `kpp_calc.F` is in `verification/lab_sea/code/` directory
2. Run `make CLEAN` and recompile from scratch
3. Verify KPP is enabled: `grep useKPP data.pkg` should show `useKPP=.TRUE.`

### Problem: "UUID mismatch warning in comparison"

**Diagnosis**: Comparing outputs from different input runs.

**Solutions**:
1. Check timestamps match in filenames
2. Verify UUIDs: `ncdump -h file.nc | grep input_uuid`
3. If intentional (testing sensitivity), document it in report notes

### Problem: "Large HBL differences (> 10 m)"

**Diagnosis**: Major bug in boundary layer depth calculation.

**Investigation Steps**:
1. Plot HBL time series for both runs
2. Check bulk Richardson number at HBL base
3. Verify temperature and salinity profiles match
4. Compare stratification (N²) and shear (S²) diagnostics
5. Review BLDEPTH routine in Python vs Fortran

### Problem: "Python KPP produces NaN outputs"

**Diagnosis**: Numerical instability or invalid input data.

**Solutions**:
1. Check input data ranges: `python -c "import xarray as xr; ds = xr.open_dataset('input.nc'); print(ds.describe())"`
2. Look for division by zero or log(negative) operations
3. Verify grid thickness is positive everywhere
4. Check for uninitialized variables in MITgcm output

### Problem: "Comparison script fails with dimension mismatch"

**Diagnosis**: Grid dimensions differ between files.

**Solutions**:
1. Check grid size: `ncdump -h file.nc | grep "x ="`
2. Verify both files from same experiment run
3. Ensure Python output used correct input dimensions

### Problem: "High relative errors in mixing coefficients"

**Diagnosis**: Small absolute differences amplified by small denominator.

**Investigation**:
1. Check if errors only in weakly mixed regions (mixing ≈ background)
2. Plot absolute differences vs relative differences
3. Verify masking threshold (1e-6 m²/s) is appropriate
4. Compare where mixing is strong (> 1e-4 m²/s)

---

## Data Quality Assurance

Before running validation, check input data quality:

### 1. Physical Sanity Checks

```python
import xarray as xr
import numpy as np

ds = xr.open_dataset("inputs_from_mitgcm/kpp_input_lab_sea_*.nc")

# Temperature range
assert ds.theta.min() > -5.0 and ds.theta.max() < 40.0, "Temperature out of range"

# Salinity range
assert ds.salt.min() > 0.0 and ds.salt.max() < 45.0, "Salinity out of range"

# Depth monotonic
assert np.all(np.diff(ds.depth) > 0), "Depth not monotonic"

# Cell thickness positive
assert np.all(ds.cell_thickness > 0), "Negative cell thickness"

print("✅ Input data passes sanity checks")
```

### 2. Grid Consistency

```python
# Verify interface-center relationship
depth_centers = ds.depth.values
depth_ifaces = ds.depth_iface.values
thickness = ds.cell_thickness.values

for k in range(len(thickness)):
    computed_thickness = depth_ifaces[k+1] - depth_ifaces[k]
    assert np.abs(computed_thickness - thickness[k]) < 1e-10, \
        f"Grid inconsistency at k={k}"

print("✅ Grid consistent")
```

### 3. Provenance Validation

```python
# Check UUID provenance chain
input_ds = xr.open_dataset("inputs_from_mitgcm/kpp_input_*.nc")
output_ds = xr.open_dataset("outputs_from_python/kpp_output_*.nc")

input_uuid = input_ds.attrs['uuid']
output_input_uuid = output_ds.attrs['input_uuid']

assert input_uuid == output_input_uuid, "Provenance chain broken!"
print(f"✅ Provenance valid: {input_uuid[:16]}...")
```

---

## Best Practices

### 1. Organize by Experiment

Keep validation data organized by physical scenario:

```
KPP_port_validation/
├── lab_sea/
│   ├── kpp_input_*.nc
│   ├── kpp_output_mitgcm_*.nc
│   ├── kpp_output_python_*.nc
│   └── validation_report.pdf
├── 1D_ocean_ice/
│   └── ...
└── tutorial_plume_on_slope/
    └── ...
```

### 2. Version Control Validation Data

For critical validation runs:
1. Tag MITgcm commit used: `git tag validation_lab_sea_v1.0`
2. Record Python port commit: `git rev-parse HEAD`
3. Store metadata in report or separate file
4. Archive input/output NetCDF files (use compression!)

### 3. Automate Regression Testing

Create validation test suite:

```bash
#!/bin/bash
# validate_all_experiments.sh

experiments=("lab_sea" "1D_ocean_ice" "tutorial_plume_on_slope")

for exp in "${experiments[@]}"; do
  echo "Validating $exp..."
  
  # Run MITgcm
  cd /path/to/mitgcm/verification/$exp
  ./run_experiment.sh
  
  # Parse to NetCDF
  cd /path/to/scripts
  python parse_mitgcm_split.py /path/to/$exp/output.txt $exp
  
  # Run Python
  python run_kpp_from_split.py ../KPP_port_validation/inputs_from_mitgcm/kpp_input_${exp}_*.nc
  
  # Compare
  python compare_kpp_outputs.py \
    ../KPP_port_validation/outputs_from_mitgcm/kpp_output_${exp}_*.nc \
    ../KPP_port_validation/outputs_from_python/kpp_output_${exp}_*.nc \
    ../KPP_port_validation/reports/validation_${exp}.pdf
done

echo "✅ All experiments validated!"
```

### 4. Document Validation Results

For each validation run, record:
- Experiment name
- MITgcm version/commit
- Python port version/commit  
- Date run
- Summary statistics from comparison report
- Any warnings or issues encountered
- Resolution of any bugs found

Store in version-controlled `VALIDATION_LOG.md`.

---

## References

### Technical Documentation
- **NETCDF_FORMAT.md**: Detailed specification of file format, variables, conventions
- **KPP_port_validation/README.md**: Original comprehensive documentation (deprecated, see NETCDF_FORMAT.md)

### MITgcm Documentation
- **KPP Implementation**: `MITgcm/pkg/kpp/kpp_calc.F`, `kpp_routines.F`
- **Lab_sea Test Case**: `MITgcm/verification/lab_sea/`

### Python Implementation
- **Main Driver**: `1D_Mixing_Model/KPP/kpp_core_driver.py`
- **Boundary Layer**: `1D_Mixing_Model/KPP/kpp_scheme_specific.py`
- **Mixing Routines**: `1D_Mixing_Model/KPP/kpp_routines.py`

### Scientific References
- Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing: A review and a model with a nonlocal boundary layer parameterization. *Reviews of Geophysics*, 32(4), 363-403.
- Miles, J. W. (1961). On the stability of heterogeneous shear flows. *Journal of Fluid Mechanics*, 10(4), 496-508.
- Howard, L. N. (1961). Note on a paper of John W. Miles. *Journal of Fluid Mechanics*, 10(4), 509-512.

---

## Getting Help

### Common Questions

**Q: How long should validation take?**  
A: Typical 1D column (Nx=Ny=1, Nr=50, Nt=100): ~30 seconds total. Large 3D domain (20×16×23, 100 timesteps): ~5-10 minutes.

**Q: What if I don't have MITgcm outputs yet?**  
A: Use provided test cases in `KPP_port_validation/test_data/` for initial testing.

**Q: Can I validate against other models (ROMS, NEMO)?**  
A: Yes, but you'll need to create custom parsers to convert to the split NetCDF format.

**Q: How do I report bugs found during validation?**  
A: Document in `potential_bugs_and_inconsistencies.md` at project root. Use template provided.

### Contact

For questions about this validation framework:
- Issues: GitHub repository issue tracker
- Documentation errors: Submit PR with corrections
- Scientific questions: Consult original KPP papers (Large et al. 1994)
