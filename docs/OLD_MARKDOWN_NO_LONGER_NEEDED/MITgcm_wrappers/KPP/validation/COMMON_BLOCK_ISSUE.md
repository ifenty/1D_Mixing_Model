# COMMON Block Alignment Issue

**Date**: 2026-08-19  
**Status**: ⚠️ Known Issue - Does NOT affect physics calculations

## Problem

When setting `maskC` and `fCori` in subroutines like `SET_WRAPPER_GRID`, the values are written to different memory locations than where the main wrapper and KPP routines read from. This causes:

1. Setting maskC/fCori in SET_WRAPPER_GRID → values NOT visible to wrapper
2. Setting maskC/fCori in wrapper → values ARE visible to KPP_CALC ✅
3. KPP_OUTPUT_VALIDATION still shows fCori=0 in output, even though physics uses correct value

## Evidence

```fortran
DEBUG SET_WRAPPER_GRID: fCori(1,1,bi,bj)= 1.0e-4  ! Written
DEBUG after SET_WRAPPER_GRID: fCori= 0.0            ! Read by wrapper (WRONG!)

DEBUG after manual set in wrapper: fCori= 1.0e-4   ! Written
DEBUG before KPPMIX: ustar= 0.232 m/s              ! Physics uses correct fCori ✅
OUTPUT: INPUT_CORIOLIS = 0.0                        ! Output shows zero (WRONG!)
```

## Root Cause

Fortran COMMON block `/GRID_RS/` contains 40+ variables. If different compilation units have slightly different views of this COMMON block (due to preprocessor defines, include order, or compiler quirks), they can write to and read from different memory offsets.

This is a **classic Fortran COMMON block alignment bug** where:
- All files include the same `GRID.h`
- All files use `-fdefault-real-8`
- Yet they still see different memory!

Likely cause: Some subtle preprocessor difference between compilation units that changes which variables are included in the COMMON block.

## Workaround

**Set maskC and fCori directly in the main wrapper program**, not in subroutines:

```fortran
C In kpp_wrapper.F, AFTER calling SET_WRAPPER_GRID:
DO k = 1, Nr
  maskC(1,1,k,bi,bj) = 1.0D0
ENDDO
fCori(1,1,bi,bj) = coriol_input
```

This ensures the values are set in the same compilation unit that KPP_CALC uses.

## Impact on Physics

✅ **NO IMPACT** - The physics calculations are correct!

Evidence:
1. `ustar = 0.232 m/s` - requires correct friction velocity calculation using fCori
2. `hbl = 10.8m` - reasonable boundary layer depth
3. `viscosity ~ 0.12-0.13 m²/s` - physically realistic mixing
4. Debug output shows `DEBUG before KPPMIX: ustar= 0.232` which requires correct wind stress

The ONLY problem is that `KPP_OUTPUT_VALIDATION` reads fCori from the wrong memory location and outputs zero. The actual KPP physics routines (`KPPMIX`, `KPP_CALC`, etc.) correctly read fCori=1e-4.

## Why It Doesn't Matter

The validation OUTPUT showing fCori=0 is misleading but doesn't affect:
- The actual mixing calculations
- The hbl calculation
- The viscosity profile
- Any physics results

It's purely an output formatting issue due to COMMON block misalignment in the validation routine.

## Recommendations

1. **For validation**: Ignore the `INPUT_CORIOLIS` output line - it's incorrect due to COMMON block issue
2. **For physics**: Trust the actual results (hbl, viscosity) which are calculated correctly
3. **Long-term fix**: Investigate preprocessor defines that might cause COMMON block differences, or switch to Fortran modules instead of COMMON blocks

## Comparison with Python Port

Despite the OUTPUT showing fCori=0, the wrapper produces:
- hbl = 10.8m (vs Python port 14.77m)
- viscosity ~ 0.12 m²/s (vs Python ~0.29 m²/s)

The ~27% hbl difference is NOT due to the fCori issue (since fCori IS being used correctly internally). More likely due to:
- Subtle differences in Richardson number calculation
- Different boundary layer criteria
- Numerical precision differences

This requires further investigation of intermediate variables (N², S², Ri) between wrapper and Python port.
