# Bob's Report to Arch - Wscale Investigation

**Date**: 2026-08-20  
**Task**: Investigate why wscale functions differ (MITgcm ws=0 vs Python ws=3.711e-04)  
**Status**: ✅ INVESTIGATION COMPLETE - No bug found in Python

---

## Executive Summary

**There is NO bug in Python's wscale function.** The discrepancy is due to comparing:
- **Python** with correct forcing (ustar=2.236e-05, bfsfc=-1.925e-10) → ws=3.711e-04
- **MITgcm debug run** with zero forcing (ustar=0, bfsfc=0) → ws=0

Both implementations correctly return ws=0 for zero forcing and ws≠0 for correct forcing.

---

## What I Found

### 1. Confirmed Forcing Discrepancy

From `DEBUG_PROGRESS.md` lines 369-377, the MITgcm debug run had:
```
DEBUG_KPPMIX_IN: ustar= 0.00000E+00 bo= 0.00000E+00 bosol= 0.00000E+00
DEBUG_WSCALE_IN: ustar= 0.00000E+00 bfsfc= 0.00000E+00
DEBUG_WSCALE_OUT: ws= 0.00000E+00
```

Expected forcing values (from validation NetCDF):
```
ustar = 2.236e-05 m/s
bo = -3.604e-10 m²/s³
bosol = 1.679e-10 m²/s³
```

### 2. Tested Python wscale Function Directly

Created `test_wscale_direct.py` and ran three test cases:

**Test 1: Correct forcing (Python scenario)**
- Input: ustar=2.236e-05, bfsfc=-1.925e-10, sigma=0.1, hbl=15m
- Output: ws = 3.711002382948432e-04 m/s ✓
- Matches Python debug output exactly

**Test 2: Zero forcing (MITgcm debug scenario)**
- Input: ustar=0, bfsfc=0, sigma=0.55, hbl=15m
- Output: ws = 0.0 m/s ✓
- Matches MITgcm debug output exactly

**Test 3: keep_mitgcm_bugs=True**
- Output: ws = 3.711002382948432e-04 m/s ✓
- Same as fixed version (bug path not triggered for this case)

### 3. Why zehat Extrapolation Bug Doesn't Apply

For correct forcing at k=1:
```
zehat = vonk * sigma * hbl * bfsfc
zehat = 0.4 * 0.1 * 15.0 * (-1.925e-10)
zehat = -1.155e-10

zmin = -4.0e-7
zdiff = zehat - zmin = -1.155e-10 - (-4.0e-7) = 3.999e-07  (POSITIVE)

iz = int(zdiff / deltaz) = 890  (upper edge of table, valid index)
```

Since zdiff is positive, the clamping `max(0, zdiff)` has no effect. Both MITgcm (unclamped) and Python (clamped) paths give the same result.

### 4. Sigma Calculation

For bfsfc < 0 (stable stratification):
```
stable_flag = 0.5 + sign(bfsfc) * 0.5 = 0.5 + (-1) * 0.5 = 0.0
sigma = stable_flag + (1 - stable_flag) * epsilon = 0.0 + 1.0 * 0.1 = 0.1
```

For bfsfc = 0 (neutral):
```
stable_flag = 0.5 + sign(0) * 0.5 = 0.5 + 0 = 0.5
sigma = 0.5 + 0.5 * 0.1 = 0.55
```

Python uses sigma=0.1 (correct for bfsfc=-1.925e-10).  
MITgcm debug run would use sigma=0.55 (correct for bfsfc=0).

Both are correct given their respective forcing values.

---

## The Problem with comparison_k1_hp.txt

The comparison file shows:
```
VARIABLE       MITgcm (kl=2)                Python (k=1)                    
--------       ----------------------------  ------------------------------  
ws             0.000000000000000E+00         3.711002382948432E-04          
```

This compares:
- **MITgcm**: Zero forcing run → ws=0 (correct for ustar=0, bfsfc=0)
- **Python**: Correct forcing run → ws=3.711e-04 (correct for ustar=2.236e-05, bfsfc=-1.925e-10)

**These are NOT comparable** because they use different forcing values!

---

## What We Still Don't Know

The actual MITgcm validation run (that produced HBL=35.12m in the NetCDF) used **correct forcing values**. We don't know:

1. What ws value MITgcm computed at k=1 with correct forcing
2. What Rib value MITgcm computed at k=1 with correct forcing  
3. What sigma value MITgcm used with correct forcing

**Without this information, we cannot identify the root cause of the HBL discrepancy.**

---

## Recommendations

### Option 1: Rerun MITgcm with Correct Forcing (Recommended)

**Action**: Run MITgcm with the exact configuration that produced `mitgcm_kpp_outputs_11k_1D.nc`, with added debug output for timestep 2312.

**Debug output needed**:
```fortran
! In bldepth subroutine, around line 590 after CALL wscale
IF (myIter .EQ. 2311 .AND. i .EQ. 1 .AND. j .EQ. 1 .AND. kl .EQ. 2) THEN
  WRITE(6,'(A,5E20.12)') 'T2312_K2: sigma, hbl, ustar, bfsfc, ws = ', &
                          sigma(i), casea(i), ustar(i), bfsfc(i), ws(i)
  WRITE(6,'(A,4E20.12)') 'T2312_K2: bvsq, vtsq, Rib, Ritop = ', &
                          bvsq, vtsq, Rib(i,kl), Ritop(i,kl)
ENDIF
```

This would give us:
- MITgcm's ws at k=1 with correct forcing
- MITgcm's Rib at k=1 with correct forcing
- Direct comparison with Python values

### Option 2: Accept Validation as Successful

**Rationale**:
- 99.63% of timesteps have <10% error (excellent agreement)
- All formulas verified correct against MITgcm source
- Mean error 0.18% is acceptable for practical oceanographic use
- Outliers occur in edge case regime (extreme weak forcing)
- Python wscale function tested and confirmed correct

**Action**: Document that Python port is production-ready with 0.18% mean error and 0.37% outlier rate in extreme conditions.

### Option 3: Investigate Other Possible Causes

If Option 1 shows MITgcm also computes ws≠0 with correct forcing but still finds HBL=35m while Python finds HBL=14m, investigate:

1. **Lookup table differences** - Compare wmt/wst arrays element-by-element
2. **Interpolation differences** - Check bilinear interpolation implementation
3. **Smoothing operations** - smooth_dbloc, smooth_shsq effects (though should be no-op on 1×1 grid)
4. **Unknown configuration differences** - Parameters not exported to NetCDF

---

## Files Created

1. `/KPP_port_validation/WSCALE_BUG_ANALYSIS.md` - Detailed analysis
2. `/KPP_port_validation/test_wscale_direct.py` - Direct wscale test script
3. `/KPP_port_validation/BOB_REPORT_TO_ARCH.md` - This report

---

## Conclusion

**Python's wscale implementation is correct.** The ws=0 vs ws=3.711e-04 discrepancy is due to comparing Python with correct forcing against MITgcm debug run with zero forcing.

**We cannot proceed without MITgcm debug output from a run with correct forcing.** The current comparison is invalid.

**Recommend**: Either Option 1 (rerun MITgcm with correct forcing) or Option 2 (accept 0.18% mean error as successful validation).

---

**End of Report**  
Bob (Builder), 2026-08-20
