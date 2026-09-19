# MITgcm KPP Wrapper vs Python Port Comparison

**Date**: 2026-08-19  
**Test Case**: test_case_001  
**Status**: ⚠️ Significant differences found - requires investigation

## Input Verification ✅

All inputs match between wrapper and Python port:

| Parameter | Value | Source |
|-----------|-------|--------|
| Grid spacing (drF) | [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30] m | ✅ Verified |
| Total depth | 140 m | ✅ Verified |
| Nr (levels) | 12 | ✅ Verified |
| Theta (surface) | 22.0°C | ✅ Verified |
| Salt (surface) | 34.6 psu | ✅ Verified |
| surfaceForcingT | -2.92e-5 °C·m/s | ✅ Verified |
| Qsw | 45.0 W/m² | ✅ Verified |
| EmPmR | 0.0 m/s | ✅ Verified |
| Coriolis (f) | 1.0e-4 s⁻¹ | ✅ Verified |
| Gravity | 9.81 m/s² | ✅ Verified |
| rho0 | 1029 kg/m³ | ✅ Verified |
| Cp | 3994 J/(kg·K) | ✅ Verified |

## KPP Parameters ✅

| Parameter | MITgcm Default | Python Port | Wrapper |
|-----------|----------------|-------------|---------|
| Ricr | 0.3 | 0.3 | 0.3 ✅ |
| vonk | 0.4 | 0.4 | 0.4 ✅ |
| difm0 | 5.0e-3 m²/s | 5.0e-3 m²/s | 5.0e-3 m²/s ✅ |
| match_diffusivities | ON | ON | ON ✅ |
| match_derivatives | ON | ON | ON ✅ |
| use_ghat | ON | ON | ON ✅ |

## Output Comparison ❌

### Boundary Layer Depth (hbl)

| Implementation | hbl (m) | Difference |
|----------------|---------|------------|
| Python Port | **14.77** | baseline |
| MITgcm Wrapper | **10.81** | **-27%** ⚠️ |

### Vertical Viscosity (KPPviscAz) at key levels

| Level | Depth (m) | Python Port (m²/s) | Wrapper (m²/s) | Difference |
|-------|-----------|-------------------|----------------|------------|
| 0 (surf) | 0 | 0.000 | 0.000 | ✅ Match |
| 1 | 1 | 0.195 | 0.123 | -37% |
| 2 | 3.5 | 0.286 | 0.134 | -53% |
| 3 | 7 | 0.180 | 0.016 | -91% |
| 4 | 12 | 0.008 | 0.000 | -100% |

**Maximum viscosity:**
- Python port: 0.286 m²/s at level 2 (depth ~3.5m)
- Wrapper: 0.134 m²/s at level 3 (depth ~7m)
- Difference: **-53%** ⚠️

## EOS Verification ✅

Wrapper uses JMD95Z equation of state:
- TTALPHA (thermal expansion): -0.279 kg/(m³·°C) ✅
- SSBETA (haline contraction): 0.760 kg/(m³·psu) ✅  
- rhoSurf (surface density): 1023.9 kg/m³ ✅
- bo (surface buoyancy flux): -7.81e-8 m²/s³ ✅

All values are physically reasonable (not NaN, not zero).

## Physics Calculation Status ✅

Wrapper physics is working correctly:
- ✅ No segfaults or crashes
- ✅ No NaN values in outputs
- ✅ ustar (friction velocity) = 0.232 m/s (reasonable)
- ✅ Mixing only in upper layers (correct vertical structure)
- ✅ Zero mixing below hbl (correct)

## Analysis: Why 27% hbl Difference?

### Verified as NOT the cause:
1. ❌ Input differences - All inputs match
2. ❌ Grid differences - Grid matches exactly
3. ❌ Parameter differences - All KPP parameters match
4. ❌ EOS differences - Both use JMD95Z, values are reasonable
5. ❌ Match settings - Both have matching enabled
6. ❌ Background viscosity - Set to correct values

### Likely causes (requires investigation):

1. **Richardson number calculation** 
   - hbl is determined by Ri > Ricr
   - Small differences in N² or S² could shift hbl depth
   - Need to compare Ri profile between wrapper and port

2. **Velocity shear (S²) calculation**
   - Python port may use different staggering/averaging
   - MITgcm has specific cell-face conventions
   - Need to verify S² matches at each level

3. **Stratification (N²) calculation**
   - JMD95Z alpha/beta used differently?
   - Pressure reference level differences?
   - Need to verify N² matches at each level

4. **Monin-Obukhov length scale**
   - Affects hbl in convective cases
   - bo = -7.81e-8 m²/s³ (negative = destabilizing)
   - Surface cooling + buoyancy loss from freshwater

5. **Ekman depth calculation**
   - Uses f (Coriolis) and ustar
   - Wrapper: f=1e-4 s⁻¹, ustar=0.232 m/s
   - Ekman depth ~ ustar/f ~ 2300 m (should not limit hbl)

6. **Grid staggering conventions**
   - MITgcm uses specific interface/center conventions
   - Python port may have subtle differences
   - Affects where variables are defined relative to hbl

## Recommendations

### Immediate Actions

1. **Add detailed debug output to wrapper**
   - Output Ri, N², S² at each level
   - Output component contributions to hbl determination
   - Compare level-by-level with Python port

2. **Run Python port with same exact grid**
   - Verify Python port was actually run with this grid
   - Check if there are any rounding differences

3. **Check for KPP_OPTIONS differences**
   - Some #define flags may affect hbl calculation
   - Compare wrapper KPP_OPTIONS.h vs Python port settings

### Long-term Investigation

1. **Step-through debugging**
   - Add WRITE statements in KPPMIX/BLDEPTH routines
   - Trace hbl calculation step-by-step
   - Compare with Python port line-by-line

2. **Intermediate variable validation**
   - Export all intermediate arrays from wrapper
   - Compare N², S², Ri, shear, stratification
   - Find exactly where divergence occurs

3. **Test with simpler cases**
   - Uniform grid (all drF = 10m)
   - No stratification (constant T, S)
   - Isolate which complexity causes difference

## Current Status

**Wrapper is functional but not validated**: The wrapper produces physically realistic results, but the 27% hbl difference and 53% viscosity difference from the Python port are too large to ignore. Since the user stated "these should be almost identical", further investigation is required to identify and fix the source of discrepancy.

**Most likely issue**: Subtle difference in how Richardson number or its components (N², S²) are calculated between the MITgcm Fortran implementation and the Python port. This could stem from:
- Different averaging/interpolation schemes
- Grid staggering interpretation differences
- Reference level choices for pressure in EOS

**Next step**: Add debug output for Ri, N², S² at each level and compare against Python port to pinpoint exact location of divergence.
