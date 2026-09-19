# KPP Wrapper - SUCCESS! 🎉

**Date**: 2026-08-19
**Status**: ✅ **WRAPPER WORKING** - Producing non-zero, physically realistic mixing coefficients

## Final Results

### Wrapper Output (MITgcm KPP)
```
hbl = 12.1 m
KPPviscAz(k=2) = 0.129 m²/s
KPPviscAz(k=3) = 0.159 m²/s  
KPPviscAz(k=4) = 0.0547 m²/s
```

### Python Port Output (for comparison)
```
hbl = 14.77 m
max viscosity ≈ 0.29 m²/s
```

## What Was Fixed

### Issue 1: Missing KPP Parameters ✅
- Added `KPP_READPARMS()` call
- Parameters now initialized with defaults

### Issue 2: Missing maskC Initialization ✅
- **CRITICAL FIX**: maskC must be set in `INI_WRAPPER_GRID`, not in wrapper main program
- COMMON block visibility: grid routines see maskC from GRID.h COMMON, not wrapper variables
- Solution: Added `maskC(1,1,k,bi,bj) = 1.0` loop in `ini_wrapper_grid.F`

### Issue 3: Missing nzmax ✅
- Set `nzmax(1,1,bi,bj) = Nr` to tell KPPMIX how many wet levels

### Issue 4: Wrong KPP_CALC Arguments ✅
- Fixed from `(myThid, myIter, bi, bj)` to correct `(bi, bj, myTime, myIter, myThid)`

### Issue 5: Equation of State Not Set ✅
- Set `equationOfState = 'LINEAR'`, `eosType = 'LINEAR'`
- Set LINEAR EOS parameters: `tAlpha = 2.0e-4`, `sBeta = 7.4e-4`, `rhonil = 1029.0`
- **Why LINEAR**: JMD95Z requires complex coefficients/tables; LINEAR is simpler for 1D wrapper

### Issue 6: Wrong PRESSURE_FOR_EOS Signature ✅
- Created `pressure_for_eos_simple.F` with correct signature
- Computes simple hydrostatic pressure: `P = rho0 * g * |z|`

## Key Learnings

1. **COMMON Block Visibility**: Variables set in main program aren't visible to subroutines using COMMON blocks - must initialize in shared routines like `INI_WRAPPER_GRID`

2. **Fortran COMMON Blocks**: Different compilation units see same memory for COMMON block variables, but only if they include the same header files

3. **Equation of State**: For simple 1D wrapper, LINEAR EOS is sufficient and avoids JMD95Z complexity

4. **Grid Masking**: All MITgcm KPP outputs are multiplied by `maskC` - if maskC=0, all outputs are zero

5. **Debug Strategy**: Systematic elimination worked - started with "everything zeros" and traced through each calculation step until finding the root cause

## Files Modified

### Created
- `src/pressure_for_eos_simple.F` - Simple hydrostatic pressure for EOS

### Modified
- `src/kpp_wrapper.F` - Set LINEAR EOS parameters (tAlpha, sBeta, rhonil, equationOfState)
- `src/ini_wrapper_grid.F` - **CRITICAL**: Added maskC initialization loop
- `src/stubs.F` - Removed bad PRESSURE_FOR_EOS stub
- `Makefile` - Added pressure_for_eos_simple.F to build
- `mitgcm_src/kpp_calc.F` - Added debug output (can be removed)

## Next Steps

1. ✅ DONE: Get wrapper producing non-zero outputs
2. ⏭️ TODO: Compare wrapper vs Python port outputs quantitatively
3. ⏭️ TODO: Test on multiple scenarios (arctic convection, hurricane, etc.)
4. ⏭️ TODO: Investigate hbl difference (12.1m vs 14.77m) - may be due to LINEAR vs JMD95Z EOS
5. ⏭️ TODO: Consider implementing JMD95Z EOS properly if LINEAR isn't accurate enough

## Validation Status

**Wrapper is now functional and producing physically realistic results!**

The hbl difference (12.1m vs 14.77m) is ~18%, which may be acceptable given:
- Different EOS (LINEAR vs JMD95Z)  
- Wrapper uses MITgcm's actual KPP code, Python port is a re-implementation
- Both produce mixing in the upper water column as expected

Ready for quantitative comparison and multi-scenario testing.
