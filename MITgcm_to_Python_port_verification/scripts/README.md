# KPP Validation Scripts

This directory contains the core validation pipeline for the Python KPP port.

## Active Validation Scripts

**Complete validation workflow** (use these scripts):

1. **`parse_mitgcm_split.py`** - Parse MITgcm STDOUT to NetCDF files
   - Input: MITgcm `output.txt` with validation data
   - Output: `mitgcm_kpp_inputs.nc` and `mitgcm_kpp_outputs.nc`

2. **`run_kpp_from_netcdf_input.py`** - Run Python KPP from NetCDF inputs
   - Input: NetCDF input file (from step 1 or custom)
   - Output: Python KPP outputs with UUID provenance tracking
   - Automatically compares with MITgcm outputs if available

3. **`generate_kpp_validation_report.py`** - Generate comprehensive PDF validation report
   - Inputs: MITgcm output NetCDF + Python output NetCDF
   - Output: Multi-page PDF with HBL comparison, mixing profiles, statistics, pass/fail assessment

## Documentation

- **`../KPP_port_validation/NETCDF_DATA_FORMAT.md`** - NetCDF format specification
- **`../KPP_port_validation/SIMPLIFIED_API_SUMMARY.md`** - Forcing API reference

## Example Usage

```bash
# Step 1: Parse MITgcm output
cd /path/to/mitgcm/run
python /path/to/scripts/parse_mitgcm_split.py output.txt lab_sea

# Step 2: Run Python KPP
cd /path/to/1D_Mixing_Experiments
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs.nc

# Step 3: Generate validation report
python scripts/generate_kpp_validation_report.py \
  KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs.nc \
  KPP_port_validation/outputs_from_python/mitgcm_kpp_inputs_python.nc \
  KPP_port_validation/reports/validation_report.pdf
```

## Current Validation Status

**Dataset**: 11,000 timesteps from 1D_ocean_ice_column experiment

**Results**:
- Mean relative error: 0.18%
- RMS error: 0.72 m
- 99.63% of timesteps within 10% error
- Median relative error: 0.0005%
- **Status**: ✅ VALIDATION SUCCESSFUL

See `../KPP_port_validation/INVESTIGATION_CONCLUSION.md` for complete validation report.

## Archive Directory

The `archive/` subdirectory contains:
- Debug scripts used during investigation (2026-08-20)
- Old/superseded parsers
- Parameter investigation tools
- Sign convention testing scripts
- Investigation documentation

These are kept for reference but are not part of the active validation workflow.

## Reports Directory

Generated PDF validation reports are stored in:
- `../KPP_port_validation/reports/`

## See Also

- NetCDF format spec: `../KPP_port_validation/NETCDF_DATA_FORMAT.md`
- Investigation conclusion: `../KPP_port_validation/INVESTIGATION_CONCLUSION.md`
