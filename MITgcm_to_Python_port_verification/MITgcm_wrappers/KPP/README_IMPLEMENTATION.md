# KPP Standalone Wrapper - Implementation Guide

## Overview

This directory contains a standalone Fortran wrapper for MITgcm's KPP mixing parameterization. The wrapper runs KPP physics on 1D column inputs without requiring a full MITgcm compilation, enabling rapid validation testing against Python implementations.

**Status**: Wrapper compiles successfully (2026-08-19)

## Directory Structure

```
MITgcm_wrappers/KPP/
├── src/
│   ├── kpp_wrapper.F           ← Main Fortran program
│   ├── prep_inputs.py          ← Python: YAML configs → binary input
│   └── stubs.F                 ← Stub implementations for unused MITgcm functions
├── include/
│   ├── SIZE.h                  ← Grid dimensions (1D: sNx=1, sNy=1, Nr=50)
│   ├── EEPARAMS.h              ← Execution environment parameters
│   ├── PACKAGES_CONFIG.h       ← Package enablement (ALLOW_KPP)
│   ├── CPP_EEMACROS.h          ← Type definitions (_RL, _RS, etc.)
│   └── CPP_EEOPTIONS.h         ← Execution environment options
├── mitgcm_src/
│   ├── kpp_calc.F              ← KPP main driver (from mitgcm_verification_mods/)
│   ├── kpp_output_validation.F ← CSV output with E25.16 precision (instrumented)
│   ├── kpp_routines.F          ← KPP physics routines
│   ├── kpp_init_fixed.F        ← KPP initialization
│   ├── kpp_forcing_surf.F      ← Surface forcing handling
│   ├── find_rho.F              ← Equation of state (density)
│   ├── find_alpha.F            ← Thermal expansion coefficient
│   ├── swfrac.F                ← Shortwave radiation penetration
│   └── *.h                     ← MITgcm header files
├── build/                      ← Object files (created by make)
├── test/                       ← Validation tests (TODO)
├── Makefile                    ← Build system
├── kpp_wrapper                 ← Executable (created by make)
└── README_IMPLEMENTATION.md    ← This file
```

## Building

### Prerequisites

- **gfortran** (tested with version compatible with macOS arm64)
- **make**

### Compile

```bash
make clean
make
```

**Output**: `kpp_wrapper` executable (~97KB)

### Build Configuration

The `Makefile` uses:
- `-fdefault-real-8`: Double precision by default
- `-fconvert=big-endian`: Match Python numpy big-endian output
- `-ffixed-line-length-132`: Fixed-form Fortran with extended lines
- `-fallow-argument-mismatch`: Suppress type mismatch warnings (gfortran 10+)
- `-cpp -D_d=d`: Preprocess MITgcm's `_d 0` → `d 0` double precision literals

## Usage

### 1. Prepare Binary Input

Convert YAML configurations to binary input using `prep_inputs.py`:

```bash
python src/prep_inputs.py \
    --ic <initial_conditions.yaml> \
    --forcing <atmospheric_forcing.yaml> \
    --physical <physical_parameters.yaml> \
    --output input.bin
```

**Binary format** (big-endian):
- `Nr` (int32): Number of vertical levels
- `coriol` (float64): Coriolis parameter [1/s]
- `drF(Nr)` (float64): Cell thicknesses [m]
- `rF(Nr+1)` (float64): Interface depths [m] (0 at surface, negative down)
- `rC(Nr)` (float64): Cell center depths [m] (negative down)
- `theta(Nr)` (float64): Potential temperature [°C]
- `salt(Nr)` (float64): Salinity [psu]
- `uVel(Nr)` (float64): Zonal velocity [m/s]
- `vVel(Nr)` (float64): Meridional velocity [m/s]
- `surfaceForcingU` (float64): Surface u-momentum forcing [m²/s²]
- `surfaceForcingV` (float64): Surface v-momentum forcing [m²/s²]
- `surfaceForcingT` (float64): Surface heat forcing [°C·m/s]
- `Qsw` (float64): Shortwave radiation [W/m²]
- `EmPmR` (float64): Freshwater flux [m/s]

### 2. Run Wrapper

```bash
./kpp_wrapper < input.bin > output.csv
```

**Output format**: CSV with E25.16 precision to stdout

```csv
===== KPP_VALIDATION_START =====
TIMESTEP=1,BI=1,BJ=1
INPUT_STATE,1,1,1,<theta>,<salt>,<uVel>,<vVel>
INPUT_STATE,1,1,2,...
...
INPUT_FORCING,1,1,<tau_x>,<tau_y>,<q_net>,<qsw>,<fw_flux>
INPUT_CORIOLIS,1,1,<f>
OUTPUT_MIXING,1,1,1,<visc_az>,<diff_kz_s>,<diff_kz_t>,<ghat>
OUTPUT_MIXING,1,1,2,...
...
OUTPUT_HBL,1,1,<hbl>
===== KPP_VALIDATION_END =====
```

### 3. Validate Against MITgcm

(TODO: Complete validation test script)

```bash
./test/compare_with_mitgcm.sh
```

## Implementation Notes

### 1D Column Simplification

The wrapper is configured for **1D column mode**:
- `sNx = 1, sNy = 1`: Single horizontal grid point
- `Nr = 50`: Maximum 50 vertical levels (runtime-configurable via input)
- `nPx = 1, nPy = 1`: No domain decomposition
- `OLx = 1, OLy = 1`: Minimal overlap (unused in 1D)

### Instrumented KPP Files

The wrapper uses **instrumented KPP files** from `/mitgcm_verification_mods/kpp_mods/`:
- `kpp_calc.F`: Modified to call `KPP_OUTPUT_VALIDATION`
- `kpp_output_validation.F`: High-precision CSV output (E25.16) with thread fix

**CRITICAL**: Do NOT replace these with stock MITgcm versions — the validation output directives are required.

### Stubbed Functions

The following MITgcm functions are stubbed as no-ops in `src/stubs.F` (not needed for 1D column):
- `EXCH_XY_*`, `EXCH_XYZ_*`: Horizontal exchange (no neighbors in 1D)
- `BARRIER`: Thread barrier (single thread)
- `CALC_3D_DIFFUSIVITY`: Generic diffusivity (KPP handles its own)
- `DIFFERENT_MULTIPLE`: Time interval check (always false for single timestep)
- `PRESSURE_FOR_EOS`: Hydrostatic pressure (`p = ρ₀ g |z|`)
- `PRINT_ERROR`, `PRINT_MESSAGE`: Simple stdout wrappers
- `WRITE_FLD_XYZ_RL`, `MDS_WRITE_FIELD`: File I/O (not used)
- `GLOBAL_MAX_R8`, `GLOBAL_MIN_R8`, `GLOBAL_SUM_R8`: MPI reductions (no-op for single process)

### Fixed-Form Fortran Conventions

MITgcm uses **fixed-form Fortran** (`.F` extension):
- Columns 1-5: Statement labels
- Column 6: Continuation marker (`&` or non-zero digit)
- Columns 7-72: Code
- Column 73+: Comments (ignored)

**Include placement**: `#include` directives must appear AFTER the `PROGRAM`/`SUBROUTINE` statement in the declaration section, NOT before the program unit.

### Known Limitations

- **Single timestep only**: Wrapper runs one `KPP_CALC` call (no time-stepping loop)
- **No NetCDF output**: Uses CSV to stdout
- **No MPI**: Single process, single thread
- **No horizontal smoothing**: `SMOOTH_HORIZ` is a no-op in 1D

## Debugging

### Build Issues

1. **"Unexpected PROGRAM statement"**: Check that `#include` statements are AFTER `PROGRAM KPP_WRAPPER`, not before.

2. **Missing header files**: Copy from `/Users/ifenty/git_repo_others/MITgcm`:
   - `CPP_EEMACROS.h`: `eesupp/inc/`
   - `CPP_EEOPTIONS.h`: `eesupp/inc/`
   - `GAD.h`: `pkg/generic_advdiff/`

3. **"Missing kind-parameter" errors**: Ensure Makefile has `-cpp -D_d=d` to preprocess MITgcm's double precision literals.

4. **Undefined symbols at link time**: Add missing function stubs to `src/stubs.F`.

### Runtime Issues

1. **"SIZE MISMATCH" error**: Input binary Nr doesn't match `SIZE.h` Nr (default 50). Regenerate input or recompile with correct Nr.

2. **No CSV output**: Check that `myThid .NE. 1` condition in `kpp_output_validation.F` matches the thread ID being used (should be 1 for standalone).

3. **Segmentation fault**: Check that all grid/state arrays are properly initialized in the binary input file.

## References

- **MITgcm Source**: `/Users/ifenty/git_repo_others/MITgcm`
- **Instrumented KPP**: `/mitgcm_verification_mods/kpp_mods/`
- **Python Port**: `/1D_Mixing_Model/KPP/`
- **Design Document**: `../../OLD_MARKDOWN_NO_LONGER_NEEDED/MITgcm_wrappers/KPP/handoff/DESIGN-DECISION.md` (archived)

## Next Steps

- [ ] Create validation test script comparing wrapper vs full MITgcm
- [ ] Test wrapper with actual lab_sea or test case inputs
- [ ] Document expected runtime and memory usage
- [ ] Add error handling for malformed binary inputs

---

**Last Updated**: 2026-08-19  
**Status**: Build system complete, wrapper compiles successfully
