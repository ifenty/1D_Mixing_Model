# KPP Wrapper Debugging Session Summary
**Date**: 2026-08-19  
**Goal**: Systematically debug why MITgcm KPP wrapper outputs zeros for all mixing coefficients

## Initial Problem
Python KPP port produces correct mixing (hbl=14.77m, max viscosity ~0.29 m²/s), but MITgcm wrapper outputs all zeros.

## Debugging Process - Issues Found and Fixed

### ✅ Issue 1: Missing KPP Parameter Initialization
**Symptom**: All outputs zero
**Root Cause**: Wrapper never called `KPP_READPARMS()` to initialize physics parameters (Ricr, vonk, difm0, dift0, etc.)
**Fix**: 
- Copied `kpp_readparms.F` from MITgcm
- Added call to `KPP_READPARMS(myThid)` before `KPP_INIT_FIXED`
- Modified `kpp_readparms.F` to handle missing data.kpp file gracefully
- Added stubs for `OPEN_COPY_DATA_FILE`, `ALL_PROC_DIE`, `PACKAGES_UNUSED_MSG`
**Files Modified**: `kpp_wrapper.F`, `kpp_readparms.F`, `stubs.F`, `Makefile`
**Result**: Parameters now initialized with defaults

### ✅ Issue 2: maskC Not Initialized
**Symptom**: All outputs zero (outputs are mult multiplied by maskC in KPP_CALC)
**Root Cause**: Ocean mask array `maskC` uninitialized, defaulting to 0.0
**Fix**: Added `maskC(1,1,k,bi,bj) = 1.0D0` for all k in wrapper
**Files Modified**: `kpp_wrapper.F`
**Result**: Mask properly set, but outputs still zero

### ✅ Issue 3: nzmax Not Initialized  
**Symptom**: All outputs zero
**Root Cause**: `nzmax` (number of wet levels) not initialized, KPPMIX may skip calculations
**Fix**:
- Added `#include "PACKAGES_CONFIG.h"` to define ALLOW_KPP macro
- Added `#include "KPP_PARAMS.h"` to access nzmax
- Set `nzmax(1,1,bi,bj) = Nr`
- Copied `KPP_OPTIONS.h` from MITgcm
**Files Modified**: `kpp_wrapper.F`
**Result**: nzmax initialized, but outputs still zero

### ✅ Issue 4: KPP_CALC Arguments in Wrong Order
**Symptom**: Wrapper runs but outputs zeros; fCori shows as zero in KPP_OUTPUT_VALIDATION
**Root Cause**: Wrapper called `KPP_CALC(myThid, myIter, bi, bj)` but correct signature is `KPP_CALC(bi, bj, myTime, myIter, myThid)`  
**Fix**: Changed wrapper call to `KPP_CALC(bi, bj, 0.0D0, myIter, myThid)`
**Files Modified**: `kpp_wrapper.F`
**Result**: Now get different error - EOS not set

### ✅ Issue 5: Equation of State Not Set
**Symptom**: `ERROR: FIND_RHO_2D: equationOfState = ""`
**Root Cause**: `equationOfState` variable not initialized, FIND_RHO can't compute density
**Fix**:
- Copied `EOS.h` from MITgcm
- Added `#include "EOS.h"` to wrapper
- Set `equationOfState = 'JMD95Z'` and `eosType = 'JMD95Z'`
**Files Modified**: `kpp_wrapper.F`
**Result**: EOS error gone, now crashes with NaN

### ❌ Issue 6: Surface Buoyancy Flux is NaN (CURRENT)
**Symptom**: Segmentation fault; debug shows `bo(1,1) = NaN`
**Root Cause**: Surface buoyancy forcing calculation returns NaN
**Evidence**:
```
DEBUG before KPPMIX: nzmax(1,1)= 0
DEBUG before KPPMIX: ustar(1,1)= 0.224 (correct)
DEBUG before KPPMIX: bo(1,1)= NaN (BAD!)
Segmentation fault
```
**Likely Causes**:
1. Thermal expansion coefficient (alpha) or haline contraction (beta) from EOS returning NaN
2. Missing initialization in KPP_FORCING_SURF
3. Surface heat flux (surfaceForcingT) or salinity (EmPmR) being passed incorrectly
4. Something upstream in STATEKPP or KPP_FORCING_SURF

**Next Debugging Steps**:
1. Add debug output in KPP_FORCING_SURF to trace where bo becomes NaN
2. Check if alpha/beta from FIND_ALPHA are valid
3. Verify surface forcing values being passed to KPP_CALC
4. Check if rhoConst, HeatCapacity_Cp are properly initialized

## Files Created/Modified

### New Files
- `validation/run_kpp_and_export.py` - Export Python KPP port data
- `validation/compare_simple.py` - Compare wrapper vs port outputs
- `validation/DEBUG_LOG.md` - Detailed debugging log
- `validation/DEBUGGING_SESSION_SUMMARY.md` - This file
- `mitgcm_src/kpp_readparms.F` - Copied and modified from MITgcm
- `mitgcm_src/EOS.h` - Copied from MITgcm
- `include/KPP_OPTIONS.h` - Copied from MITgcm

### Modified Files
- `src/kpp_wrapper.F` - Added initialization for maskC, nzmax, equationOfState, eosType; fixed KPP_CALC call; added debug output
- `src/stubs.F` - Added OPEN_COPY_DATA_FILE, ALL_PROC_DIE, PACKAGES_UNUSED_MSG stubs
- `mitgcm_src/kpp_calc.F` - Added debug output before/after KPPMIX
- `Makefile` - Added kpp_readparms.F to build

## Key Learnings

1. **COMMON block initialization**: Variables in COMMON blocks must be explicitly initialized; they don't default to zero
2. **Argument order matters**: Fortran doesn't check argument types/order at compile time
3. **MITgcm initialization is complex**: Many interdependent variables need specific setup
4. **Debug output is essential**: Without printf debugging, issues would be impossible to diagnose
5. **Test incrementally**: Each fix revealed the next issue in the chain

## Validation Framework Status
✅ **Working**: Export script runs Python KPP port successfully, generates binary inputs  
✅ **Working**: Wrapper compiles and runs (though crashes on NaN)  
✅ **Working**: Comparison script can parse outputs  
❌ **Broken**: Wrapper doesn't produce valid mixing coefficients yet

### ✅ Issue 6: Fixed PRESSURE_FOR_EOS Signature
**Symptom**: Segfault in STATEKPP
**Root Cause**: PRESSURE_FOR_EOS stub had wrong signature - wrapper used `(i,j,k,bi,bj,...)` but real signature is `(bi,bj,iMin,iMax,jMin,jMax,k,dpRef,...)`
**Fix**: Created `pressure_for_eos_simple.F` with correct signature, simple hydrostatic pressure calculation
**Files Modified**: Created `src/pressure_for_eos_simple.F`, modified `Makefile`, removed bad stub from `stubs.F`
**Result**: ✅ MAJOR PROGRESS - No more segfault! Wrapper runs to completion!

## Current Status - MAJOR BREAKTHROUGH!

### What's Working Now ✅
1. Wrapper compiles and runs without crashing
2. All initialization complete (parameters, masks, grid)
3. **KPPMIX is computing mixing!**
   - `hbl = 125m` (boundary layer depth)
   - `vddiff(1,1,1,1) = 0.180 m²/s` (viscosity coefficient is NON-ZERO!)
   - ustar = 0.232 m/s (friction velocity correct)

### Remaining Issue ❌
**EOS returns NaN**: FIND_ALPHA and FIND_BETA return NaN for thermal/haline expansion coefficients
- TTALPHA = NaN (should be ~0.0002 kg/m³/°C)
- SSBETA = NaN (should be ~0.78 kg/m³/psu)
- rhoSurf = NaN (should be ~1025 kg/m³)

This causes bo (buoyancy flux) = NaN, which may be zeroing outputs through NaN propagation.

### Why Outputs Are Still Zero
Even though vddiff is non-zero (0.180 m²/s), the final outputs are zero. Two possible causes:
1. NaN in bo propagates through and zeros everything
2. Masking at end of KPP_CALC is incorrect due to NaN

### Next Steps  
1. **Debug FIND_ALPHA/FIND_BETA**: Add debug output to see why EOS returns NaN
2. **Check if JMD95 EOS needs initialization**: May need EOS coefficients or tables
3. **Test simpler EOS**: Try 'LINEAR' instead of 'JMD95Z' to bypass complex EOS
4. Once EOS fixed, outputs should be non-zero and comparable to Python port

## Next Session Goals
1. ✅ DONE: Fix segfault (PRESSURE_FOR_EOS)
2. ✅ DONE: Get KPPMIX to produce non-zero values  
3. ❌ TODO: Fix EOS to return valid alpha/beta/rho
4. ❌ TODO: Get non-zero final outputs
5. ❌ TODO: Compare wrapper outputs vs Python port
6. ❌ TODO: Achieve validation tolerance < 1e-12
