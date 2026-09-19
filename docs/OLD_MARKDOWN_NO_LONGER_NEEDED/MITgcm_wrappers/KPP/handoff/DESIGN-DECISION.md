# KPP Wrapper Design Decision

**Date**: 2026-08-19  
**Author**: Bob (Builder)  
**Status**: Ready for Arch Review

---

## Executive Summary

**Recommendation: Option B — Python-to-Fortran Bridge**

This approach provides the best balance of:
- Minimal MITgcm dependency extraction (estimated 15-20 files)
- Bit-level accuracy guarantee (pure Fortran KPP execution)
- Clean separation of concerns (Python reads YAML, Fortran does physics)
- Straightforward build process (gfortran standalone, no MITgcm build system)
- Extensibility (can reuse Python prep script for GGL90 wrapper later)

---

## Architecture Choice: Option B — Python-to-Fortran Bridge

### Data Flow

```
YAML configs                     Binary input file              CSV output
(initial_conditions.yaml)        (kpp_input.bin)               (kpp_validation.csv)
(atmospheric_forcing.yaml)            |                              |
         |                            |                              |
         v                            v                              v
  +--------------+           +-------------------+          +------------------+
  | Python       |  writes   | Fortran Wrapper   |  calls   | KPP_CALC        |
  | prep_inputs  | --------> | kpp_wrapper.F     | -------> | KPPMIX          |
  | .py          |           | (standalone exe)  |          | STATEKPP        |
  +--------------+           +-------------------+          +------------------+
                                      |                              |
                                      |                              v
                                      |                    +------------------+
                                      |                    | KPP_OUTPUT_      |
                                      +-------------------> | VALIDATION.F    |
                                                           | (reused from     |
                                                           | lab_sea mods)    |
                                                           +------------------+
```

### Execution Flow

```bash
# Step 1: Python reads YAML, writes binary
python prep_inputs.py \
    --ic initial_conditions.yaml \
    --forcing atmospheric_forcing.yaml \
    --output kpp_input.bin

# Step 2: Fortran reads binary, runs KPP, writes CSV
./kpp_wrapper kpp_input.bin > kpp_validation.csv
```

### Why Option B Over Others

**Option A (Pure Fortran)** rejected because:
- Fortran YAML parsers add complexity and dependency
- Preprocessing YAML in Python is cleaner (reuse PyYAML)
- 1D column setup doesn't benefit from monolithic executable

**Option C (f2py Hybrid)** rejected because:
- f2py adds build complexity (mixed Python/Fortran compilation)
- Python calling Fortran directly loses ability to reuse existing MITgcm validation code cleanly
- Harder to debug (mixed-language stack traces)
- No performance benefit for 1D column (< 1 second runtime)

---

## MITgcm Dependencies

### Required Files from `pkg/kpp/`

**Core KPP physics (5 files)**:
1. `kpp_calc.F` — Main entry point (calls KPPMIX, STATEKPP, KPP_FORCING_SURF)
2. `kpp_routines.F` — Core physics (KPPMIX, STATEKPP, KPP_DOUBLEDIFF, plus internal: bldepth, blmix, wscale, Ri_iwmix, enhance, z121)
3. `kpp_forcing_surf.F` — Surface forcing preparation
4. `kpp_init_fixed.F` — Initialization of lookup tables
5. `kpp_output_validation.F` — Validation output (reused from lab_sea mods)

**Header files (3 files)**:
6. `KPP.h` — Common blocks for output arrays
7. `KPP_PARAMS.h` — Parameters and constants
8. `KPP_OPTIONS.h` — Compile-time flags

**Optional features**: SMOOTH_HORIZ, DIAGNOSTICS_FILL, SALT_PLUME, SHELFICE — can be ifdef'd out for 1D column.

### Required Files from `model/src/`

**Equation of state (3 files)**:
9. `find_rho.F` — Density calculation (includes FIND_RHO_2D)
10. `find_alpha.F` — Thermal expansion coefficient (FIND_ALPHA)
11. `find_beta.F` — Haline contraction coefficient (FIND_BETA)

**Shortwave radiation**:
12. `swfrac.F` — Shortwave penetration (SWFRAC)

**3D diffusivity (optional)**:
13. `calc_3d_diffusivity.F` — Can be stubbed out for 1D wrapper

### Required Files from `model/inc/`

**Core headers (7 files)**:
14. `SIZE.h` — Grid dimensions (modified for 1D: sNx=1, sNy=1, Nr=configurable)
15. `PARAMS.h` — Model parameters
16. `DYNVARS.h` — Dynamic variables (theta, salt, uVel, vVel)
17. `GRID.h` — Grid geometry (drF, rF, rC, fCori)
18. `FFIELDS.h` — Surface forcing fields
19. `EOS.h` — Equation of state parameters (if used by find_rho.F)
20. `CPP_OPTIONS.h` — Compile-time options

### Required Files from `eesupp/inc/`

**Parallel execution stubs**:
21. `EEPARAMS.h` — Basic execution environment parameters

**Total estimated dependency count: ~20 files**

---

## Build Strategy

### Compiler
**gfortran** (standalone, no MITgcm genmake2 required)

Rationale:
- 1D wrapper is simple enough for manual compilation
- No autodifferentiation (no TAF/TAMC needed)
- No MPI (single column, single thread)
- No NetCDF output (CSV only)

### Compilation Approach

**1. Simplified headers**: Create minimal `SIZE.h` for 1D column:
```fortran
! SIZE.h for 1D KPP wrapper
      INTEGER sNx, sNy, OLx, OLy, Nr, nSx, nSy, nPx, nPy
      PARAMETER (
     &           sNx =   1,    ! Single column (x)
     &           sNy =   1,    ! Single column (y)
     &           OLx =   0,    ! No overlap
     &           OLy =   0,    ! No overlap
     &           Nr  =  50,    ! Max vertical levels (configurable)
     &           nSx =   1,    ! Single tile
     &           nSy =   1,
     &           nPx =   1,    ! No parallelization
     &           nPy =   1 )
```

**2. Stub out unnecessary features**:
- `#undef ALLOW_DIAGNOSTICS` — No diagnostics output
- `#undef ALLOW_SALT_PLUME` — Not needed for validation
- `#undef ALLOW_SHELFICE` — Not relevant to 1D column
- Stub `SMOOTH_HORIZ` as no-op (horizontal smoothing irrelevant for single column)
- Stub `CALC_3D_DIFFUSIVITY` as pass-through

**3. Minimal EEPARAMS**: Define only what's needed (myThid, bi, bj, standardMessageUnit)

### Makefile Structure
```makefile
FC = gfortran
FFLAGS = -O2 -fdefault-real-8 -fconvert=big-endian -I./include -I./mitgcm_src

OBJS = kpp_wrapper.o kpp_calc.o kpp_routines.o kpp_forcing_surf.o \
       kpp_init_fixed.o kpp_output_validation.o \
       find_rho.o find_alpha.o find_beta.o swfrac.o \
       stubs.o

kpp_wrapper: $(OBJS)
	$(FC) $(FFLAGS) -o $@ $(OBJS)

clean:
	rm -f *.o *.mod kpp_wrapper
```

### Dependencies
- **No NetCDF**: Output is CSV via WRITE statements
- **No MPI**: Single thread (myThid=1, bi=1, bj=1)
- **No TAF**: No autodifferentiation

### Estimated Compile Time
**5-10 seconds** (first build)  
**1-2 seconds** (incremental rebuild)

Much faster than 5-minute full MITgcm compile.

---

## Input/Output Format

### Input: Binary File (`kpp_input.bin`)

Python script writes sequential binary records:

```
Record 1: Metadata
  - Nr (INTEGER*4): Number of vertical levels
  - coriol (REAL*8): Coriolis parameter

Record 2: Grid geometry (Nr values each)
  - drF(Nr): Cell thickness [m]
  - rF(0:Nr): Interface depths [m, negative]
  - rC(Nr): Cell center depths [m, negative]

Record 3: Initial conditions (Nr values each)
  - theta(Nr): Potential temperature [°C]
  - salt(Nr): Salinity [PSU]
  - uVel(Nr): Zonal velocity [m/s]
  - vVel(Nr): Meridional velocity [m/s]

Record 4: Surface forcing (scalars)
  - surfaceForcingU: Zonal wind stress / rho [m^2/s^2]
  - surfaceForcingV: Meridional wind stress / rho [m^2/s^2]
  - surfaceForcingT: Net heat flux [W/m^2]
  - Qsw: Shortwave flux [W/m^2]
  - EmPmR: Freshwater flux [m/s]
```

Fortran reads with:
```fortran
OPEN(UNIT=10, FILE='kpp_input.bin', FORM='UNFORMATTED', STATUS='OLD')
READ(10) Nr, coriol
READ(10) drF, rF, rC
READ(10) theta, salt, uVel, vVel
READ(10) surfaceForcingU, surfaceForcingV, surfaceForcingT, Qsw, EmPmR
CLOSE(10)
```

### Output: CSV File (`kpp_validation.csv`)

Reuses existing `kpp_output_validation.F` format:
- E25.16 precision (16 decimal places)
- CSV headers: `INPUT_STATE`, `INPUT_GEOM`, `INPUT_FORCING`, `INPUT_CORIOLIS`, `OUTPUT_KPP`
- One row per interface for mixing coefficients
- Format identical to what lab_sea experiments produce

---

## Risk Assessment

### Bit-Level Accuracy Risks

**Risk 1: Incorrect common block initialization**  
**Mitigation**: Use existing `kpp_init_fixed.F` unmodified. Validate against full MITgcm run initially.

**Risk 2: Missing dependencies for equation of state**  
**Mitigation**: `find_rho.F` may pull in additional EOS files (e.g., JMD95 or MDJWF). Check at compile time.

**Risk 3: Hardcoded array sizes in MITgcm code**  
**Mitigation**: Review all included files for hardcoded `sNx`, `sNy` assumptions. 1D column should work since MITgcm supports arbitrary tile sizes.

### Build Complexity Risks

**Risk 4: Include file dependencies**  
**Mitigation**: Start with minimal set, add as compilation errors reveal missing includes. Most MITgcm header files are self-contained.

**Risk 5: Fortran module dependencies**  
**Mitigation**: MITgcm uses `.h` includes, not Fortran modules. No module dependency ordering issues expected.

**Risk 6: Precision/endianness mismatch**  
**Mitigation**: Force `-fdefault-real-8` and `-fconvert=big-endian` in gfortran. Match Python numpy binary output endianness.

### Hardest Dependencies to Extract

**1. FIND_RHO.F complexity**: 
- This file is 36KB and may include multiple EOS formulations (JMD95, TEOS-10)
- May need additional `#ifdef` guards to isolate JMD95 path
- Estimated effort: 30 minutes to review and test

**2. PARAMS.h scope**:
- Large header with many model parameters
- May need to create stripped-down version with only KPP-relevant parameters
- Estimated effort: 45 minutes to extract minimal set

**3. Grid geometry assumptions**:
- MITgcm code may assume multi-column grid in some places
- Need to verify that `sNx=1, sNy=1` works correctly
- Estimated effort: 20 minutes of code review

---

## Development Time Estimate

### Step 2 Implementation (Bob)
- **Python prep script**: 2 hours
  - YAML reading (30 min)
  - Binary output formatting (1 hour)
  - Command-line interface (30 min)
- **Fortran wrapper driver**: 3 hours
  - Main program (1 hour)
  - Binary input reading (1 hour)
  - Common block population (1 hour)
- **Dependency extraction**: 2 hours
  - Copy/modify header files (1 hour)
  - Create stubs for unused features (1 hour)
- **Makefile and build**: 1 hour
- **Testing and debug**: 2 hours
  - **Total: 10 hours**

### Step 3 Validation (Richard)
- **Code review**: 1 hour
- **Test against full MITgcm**: 2 hours
- **Debugging discrepancies**: 2 hours (contingency)
  - **Total: 5 hours**

### Overall Project Estimate: 15 hours (2 work days)

---

## Open Questions for Arch

1. **Initial test case**: Which scenario from `configuration_yamls/` should be the first validation target?
   - Recommendation: Use `initial_conditions.yaml` + `atmospheric_forcing.yaml` (simplest baseline)

2. **Vertical resolution**: Should wrapper support variable `Nr` or fix to specific value?
   - Recommendation: Make `Nr` runtime-configurable via binary input (max 50 levels hardcoded in SIZE.h)

3. **Timestep handling**: Should wrapper run single timestep or multiple?
   - Recommendation: Single timestep only (validation focus). Multi-step would require storing state between calls.

4. **Output verbosity**: Should wrapper output only final CSV or also intermediate debug info?
   - Recommendation: CSV to stdout by default. Add `--debug` flag to Python prep script for verbose Fortran output.

---

## Next Steps (Pending Arch Approval)

Once approved:
1. Bob proceeds to Step 2 implementation
2. Create directory structure: `src/`, `include/`, `inputs/`, `outputs/`
3. Implement Python prep script first (enables early testing of binary format)
4. Extract MITgcm dependencies and build Fortran wrapper
5. Initial validation against full MITgcm lab_sea run

---

**Signal: Step 1 complete — design decision written to handoff/DESIGN-DECISION.md**
