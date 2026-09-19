# MITgcm KPP Instrumentation for Python Port Validation

This directory contains instrumentation code to validate the KPP Python port against MITgcm's Fortran implementation using the lab_sea verification experiment.

## Files

- **`kpp_output_validation.F`** - Fortran subroutine that outputs KPP inputs and outputs in CSV format with E25.16 precision
- **`kpp_calc_instrumentation.patch`** - Patch file showing the modification to `kpp_calc.F`
- **`instrument_mitgcm_kpp.sh`** - Script to apply instrumentation to lab_sea experiment
- **`lab_sea_compile.log`** - Compilation log (generated)
- **`lab_sea_kpp_validation.txt`** - Model output with KPP data (generated)

## Instrumentation Workflow

### Step 1: Instrument MITgcm Code

```bash
cd /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments
./scripts/instrument_mitgcm_kpp.sh
```

This copies:
- `kpp_output_validation.F` → `lab_sea/code/`
- Modified `kpp_calc.F` → `lab_sea/code/`

### Step 2: Compile lab_sea

```bash
cd /Users/ifenty/git_repo_others/MITgcm/verification
./experiment_compile.sh lab_sea -j 12
```

### Step 3: Run Instrumented Model

```bash
./experiment_run_no_compile.sh lab_sea > lab_sea_kpp_validation.txt 2>&1
```

Output file will contain:
- Standard MITgcm output
- Interspersed CSV blocks with KPP I/O data

### Step 4: Parse Output

```bash
cd /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments
python scripts/mitgcm_kpp_parser.py \
    /Users/ifenty/git_repo_others/MITgcm/verification/lab_sea_kpp_validation.txt \
    -o mitgcm_instrumentation/lab_sea_kpp_data.h5
```

### Step 5: Run Validation Tests

```bash
pytest tests/test_mitgcm_kpp_lab_sea_validation.py -v
```

## Output Format

The instrumentation outputs CSV-formatted data blocks for each timestep:

```
===== KPP_VALIDATION_START =====
TIMESTEP=      2,BI=  1,BJ=  1
INPUT_STATE,  1,  1,  1, 2.3045678901234567E+01, 3.4650000000000000E+01, ...
INPUT_STATE,  1,  1,  2, 2.2034567890123456E+01, 3.4750000000000000E+01, ...
...
INPUT_GEOM,  1,  1,  1, 1.0000000000000000E+01, -5.0000000000000000E+00, ...
...
INPUT_FORCING,  1,  1, 1.2345678901234567E-04, 2.3456789012345678E-05, ...
INPUT_CORIOLIS,  1,  1, 1.0000000000000000E-04
OUTPUT_MIXING,  1,  1,  1, 1.2345678901234567E-03, 2.3456789012345678E-04, ...
OUTPUT_MIXING,  1,  1,  2, 3.4567890123456789E-03, 4.5678901234567890E-04, ...
...
OUTPUT_HBL,  1,  1, 5.6789012345678901E+01
===== KPP_VALIDATION_END =====
```

### Field Descriptions

**INPUT_STATE** (per cell center, k=1..Nr):
- i, j, k: Grid indices
- theta: Potential temperature [°C]
- salt: Salinity [psu]
- uvel: Zonal velocity [m/s]
- vvel: Meridional velocity [m/s]
- depth: Cell center depth (negative) [m]

**INPUT_GEOM** (per cell, k=1..Nr):
- i, j, k: Grid indices
- drF: Cell thickness [m]
- rF: Interface depth (top of cell) [m]
- rC: Cell center depth [m]

**INPUT_FORCING** (per column):
- i, j: Grid indices
- tau_x: Zonal wind stress / rho [m²/s²]
- tau_y: Meridional wind stress / rho [m²/s²]
- q_net: Net surface heat flux [W/m²]
- q_sw: Shortwave radiation [W/m²]
- fw_flux: Freshwater flux (E-P-R) [m/s]

**INPUT_CORIOLIS** (per column):
- i, j: Grid indices
- f: Coriolis parameter [1/s]

**OUTPUT_MIXING** (per interface, k=1..Nr):
- i, j, k: Grid indices
- visc_az: Vertical viscosity [m²/s]
- diff_kz_s: Vertical diffusivity for salt [m²/s]
- diff_kz_t: Vertical diffusivity for temperature [m²/s]
- ghat: Nonlocal transport coefficient [s/m²]
- depth: Interface depth [m]

**OUTPUT_HBL** (per column):
- i, j: Grid indices
- hbl: Boundary layer depth [m]

## Precision

All floating-point values use E25.16 format (25 characters total, 16 significant digits after decimal), which provides sufficient precision for rtol=1e-12 validation testing.

## Lab_sea Configuration

- **Domain**: 20×16 horizontal grid, 23 vertical levels
- **Timesteps**: 10 (startTime=3600s, endTime=36000s, deltaTmom=3600s)
- **Output**: 3,200 test cases (20×16 columns × 10 timesteps)
- **KPP Parameters**: Mostly defaults (see `lab_sea/input/data.kpp`)

## Next Steps

After validation tests complete:
1. Document results in `docs/KPP/kpp_lab_sea_validation_report.md`
2. Update `potential_bugs_and_inconsistencies.md` with any bugs found
3. Fix any discrepancies between Python port and MITgcm
4. Rerun validation until all tests pass with rtol ≤ 1e-12
