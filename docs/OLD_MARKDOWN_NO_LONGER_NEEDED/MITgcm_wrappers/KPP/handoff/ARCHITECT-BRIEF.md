# Architect Brief: MITgcm KPP Standalone Wrapper

---

## Objective

Create a Fortran wrapper that runs MITgcm's KPP package standalone (no full MITgcm run required), using the same 1D column inputs as the Python port in `1D_Mixing_Model/KPP/`. Output high-precision validation data matching the format from `kpp_output_validation.F`.

**Why**: Enable direct bit-level comparison between MITgcm Fortran KPP and Python KPP port using identical inputs, without the 5-minute overhead of compiling/running full MITgcm experiments.

---

## Step 1 — Analysis and Design ✅ COMPLETE

**Status**: Approved by Arch and Project Owner

**Architecture**: Option B — Python-to-Fortran Bridge
- Python reads YAML configs → writes binary input
- Fortran wrapper reads binary → calls KPP → writes CSV validation output
- ~20 MITgcm files needed, gfortran standalone build
- Single timestep validation focus
- Estimated: 15 hours (2 work days)

See `handoff/DESIGN-DECISION.md` for full analysis.

---

## Step 2 — Implementation

### What Bob Must Build

**2.1 Python Prep Script** (`prep_inputs.py`)
- Read YAML configs: `initial_conditions.yaml`, `atmospheric_forcing.yaml`
- Write binary input file with:
  - Metadata: Nr, coriol
  - Grid: drF, rF, rC
  - State: theta, salt, uVel, vVel
  - Forcing: surfaceForcingU/V/T, Qsw, EmPmR
- CLI: `python prep_inputs.py --ic <file> --forcing <file> --output <bin>`

**2.2 Fortran Wrapper** (`kpp_wrapper.F`)
- Read binary input file
- Populate MITgcm common blocks (PARAMS, GRID, DYNVARS, FFIELDS, KPP)
- Call `KPP_INIT_FIXED` (initialization)
- Call `KPP_CALC` (main physics)
- Call `KPP_OUTPUT_VALIDATION` (CSV output to stdout)
- Main program structure: simple sequential execution

**2.3 MITgcm Dependencies**

**CRITICAL**: Use instrumented KPP files from:
`/Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/kpp_mods/`

These files contain:
- `kpp_calc.F` — Modified with validation output calls
- `kpp_output_validation.F` — High-precision E25.16 CSV output (thread fix applied)

**DO NOT** use stock MITgcm KPP files. The instrumented versions already have the validation directives we need.

Extract from standard MITgcm (`/Users/ifenty/git_repo_others/MITgcm`):
- `pkg/kpp/`: kpp_routines.F, kpp_forcing_surf.F, kpp_init_fixed.F, KPP.h, KPP_PARAMS.h, KPP_OPTIONS.h
- `model/src/`: find_rho.F, find_alpha.F, find_beta.F, swfrac.F
- `model/inc/`: SIZE.h, PARAMS.h, DYNVARS.h, GRID.h, FFIELDS.h, EOS.h, CPP_OPTIONS.h, EEPARAMS.h

Create simplified versions where needed (SIZE.h, EEPARAMS.h).

**2.4 Directory Structure**
```
MITgcm_wrappers/KPP/
├── src/
│   ├── kpp_wrapper.F           ← Main program
│   ├── prep_inputs.py          ← Python YAML → binary converter
│   └── stubs.F                 ← Stubbed functions (SMOOTH_HORIZ, etc.)
├── include/
│   ├── SIZE.h                  ← 1D simplified (sNx=1, sNy=1, Nr=50)
│   └── EEPARAMS.h              ← Minimal version
├── mitgcm_src/                 ← Extracted MITgcm dependencies
│   ├── kpp_calc.F              ← FROM mitgcm_verification_mods/kpp_mods/
│   ├── kpp_output_validation.F ← FROM mitgcm_verification_mods/kpp_mods/
│   ├── kpp_routines.F          ← Standard MITgcm
│   ├── ... (other extracted files)
│   └── *.h                     ← Headers
├── Makefile                    ← Build script
├── test/
│   └── compare_with_mitgcm.sh  ← Validation test (NEW)
└── README_IMPLEMENTATION.md    ← Usage instructions
```

**2.5 Validation Test Script** (NEW REQUIREMENT)

Create `test/compare_with_mitgcm.sh`:
- Runs Python prep on a test YAML config
- Runs wrapper to generate CSV output
- Compares wrapper output against reference CSV from full MITgcm lab_sea run
- Reports: PASS (bit-identical) or FAIL (differences found)

Purpose: Proves wrapper produces identical results to full MITgcm.

**2.6 Makefile**
- Target: `kpp_wrapper` executable
- Flags: `-fdefault-real-8 -fconvert=big-endian -O2`
- Include paths: `-I./include -I./mitgcm_src`
- Clean target

### Constraints

- **Reuse instrumented KPP code**: Use files from `mitgcm_verification_mods/kpp_mods/` (already has validation output calls)
- **Single timestep**: Wrapper runs one KPP_CALC call only
- **No MPI**: myThid=1, bi=1, bj=1 hardcoded
- **No NetCDF**: CSV output only
- **Binary endianness**: Match between Python (numpy) and Fortran (big-endian)

### Flags for Arch

- **File extraction blockers**: Any MITgcm files that are problematic to extract?
- **Binary format issues**: Any problems with Python/Fortran binary I/O?
- **Build errors**: Report compilation issues early
- **Validation test status**: Does wrapper output match full MITgcm?

---

## Step 2 Deliverables

1. `src/prep_inputs.py` — Functional Python YAML→binary converter
2. `src/kpp_wrapper.F` — Functional Fortran wrapper
3. `mitgcm_src/` — All extracted dependencies (correctly instrumented)
4. `Makefile` — Working build system
5. `test/compare_with_mitgcm.sh` — Validation test script
6. `README_IMPLEMENTATION.md` — Usage instructions and examples
7. `handoff/REVIEW-REQUEST.md` — Request Richard review when complete

### Success Criteria

- Wrapper compiles without errors
- Wrapper runs on test input and produces CSV output
- Output format matches `kpp_output_validation.F` specification
- Validation test shows bit-identical match with full MITgcm (PASS)

---

## Step 3 — Review (Pending Step 2 completion)

Richard will review:
- Code correctness and MITgcm correspondence
- Binary I/O format correctness
- Build system robustness
- Validation test results
- Documentation completeness

---

## Notes

**Instrumented KPP Files**: The `kpp_mods/` directory contains KPP files with validation output directives already integrated. These are the versions debugged and tested against lab_sea. DO NOT replace them with stock MITgcm versions—we need those validation calls.

**Thread Fix**: The `kpp_output_validation.F` in kpp_mods/ has the thread ID fix (`myThid .NE. 1` instead of `myThid .NE. 0`). This is critical for output to appear.

Signal completion: "Step 2 complete — wrapper functional, validation test passes"
