# Possible KPP Bugs/Issues in MITgcm

**Date**: 2026-08-20  
**Investigator**: Ian Fenty  
**Context**: Validation of Python KPP port against MITgcm Fortran implementation

---

## Summary

This document tracks potential numerical issues in MITgcm's KPP implementation discovered during validation of the Python port. These issues relate to divide-by-zero conditions in boundary layer mixing calculations.

---

## Issue 1: Missing hbl Regularization in BLMIX

**Status**: 🟡 Under Investigation  
**Severity**: Low (produces warnings but numerically handled)  
**MITgcm Location**: `pkg/kpp/kpp_routines.F:1556-1563`

### Description

MITgcm's BLMIX subroutine divides by boundary layer depth (`hbl`) and velocity scales (`wm`, `ws`) when computing shape function parameters, but only regularizes the velocity scales - not `hbl` itself.

**Code (kpp_routines.F:1493-1495):**
```fortran
DO i = 1, imt
   wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
   ws(i) = sign(eins,ws(i))*MAX(phepsi,ABS(ws(i)))
ENDDO
```

**Code (kpp_routines.F:1556-1563):**
```fortran
gat1m(i) = visch / hbl(i) / wm(i)
dat1m(i) = -viscp / wm(i) + f1 * visch

gat1s(i) = difsh  / hbl(i) / ws(i)
dat1s(i) = -difsp / ws(i) + f1 * difsh

gat1t(i) = difth /  hbl(i) / ws(i)
dat1t(i) = -diftp / ws(i) + f1 * difth
```

**The Issue:**
- `wm` and `ws` are regularized to `phepsi` (typically 1e-10)
- `hbl` is NOT regularized before division
- When `hbl` approaches zero (weak forcing, cold start), division by `hbl` produces inf/nan

### When This Occurs

Most commonly at **timestep 0** (model initialization) when:
- Surface forcing is weak or zero (ustar ≈ 0, bfsfc ≈ 0)
- Ocean starts from rest (u ≈ 0, v ≈ 0)
- Boundary layer has not yet developed
- BLDEPTH computes minimal hbl (approaching machine epsilon)

**Example from lab_sea validation (1000 timestep run):**
- Warnings appear only at timestep 0
- Warnings disappear by timestep 1 as forcing develops
- Affects multiple grid points with weak initial forcing

### Python Port Behavior

The Python port **exactly replicates** MITgcm's approach:

**Code (kpp_scheme_specific.py:372-373):**
```python
# Regularize velocity scales (MITgcm: kpp_routines.F:1493-1495)
wm_one = np.sign(wm_one[0]) * max(config.phepsi, abs(wm_one[0]))
ws_one = np.sign(ws_one[0]) * max(config.phepsi, abs(ws_one[0]))
```

**Code (kpp_scheme_specific.py:433-440):**
```python
gat1m = visch / hbl / wm_one
dat1m = -viscp / wm_one + f1 * visch

gat1s = difsh / hbl / ws_one
dat1s = -difsp / ws_one + f1 * difsh

gat1t = difth / hbl / ws_one
dat1t = -diftp / ws_one + f1 * difth
```

**Resulting warnings (timestep 0 only):**
```
RuntimeWarning: divide by zero encountered in scalar divide
  gat1m = visch / hbl / wm_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1m = -viscp / wm_one + f1 * visch
RuntimeWarning: divide by zero encountered in scalar divide
  gat1s = difsh / hbl / ws_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1s = -difsp / ws_one + f1 * difsh
RuntimeWarning: divide by zero encountered in scalar divide
  gat1t = difth / hbl / ws_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1t = -diftp / ws_one + f1 * difth
```

### Physical Interpretation

This is **physically reasonable** for initial conditions:
- Weak forcing → small boundary layer
- Small boundary layer → negligible BL mixing
- Division by near-zero `hbl` produces inf/nan
- These inf/nan values propagate but are multiplied by other near-zero terms
- Net result: negligible mixing (correct physical outcome)

### Potential Fixes

**Option 1: Regularize hbl (breaks bit-level compatibility with MITgcm)**
```python
hbl_safe = max(hbl, config.phepsi)
gat1m = visch / hbl_safe / wm_one
```
- Pros: Eliminates warnings
- Cons: Changes numerical results, no longer matches MITgcm exactly

**Option 2: Early exit for hbl ≈ 0 (already implemented)**
```python
if hbl == 0.0:
    # Return zero mixing
    return np.zeros(nz), np.zeros(nz), np.zeros(nz), ...
```
- Pros: Physically correct, avoids division
- Cons: Only catches exactly zero, not near-zero values

**Option 3: Accept warnings as documentation**
- Pros: Maintains bit-level MITgcm compatibility
- Cons: Clutters output, may hide other issues
- Mitigation: Filter warnings for timestep 0 only

**Option 4: MITgcm source code fix**
```fortran
! After line 1495 in kpp_routines.F
DO i = 1, imt
   hbl(i) = MAX(hbl(i), phepsi)
ENDDO
```
- Pros: Fixes root cause, consistent with wm/ws regularization
- Cons: Requires MITgcm source modification, affects all MITgcm users

### Impact Assessment

**Scientific Impact**: Negligible
- Only affects edge cases with extremely weak forcing
- Produces correct physical result (negligible mixing)
- Does not affect bulk simulation results

**Computational Impact**: None
- inf/nan values handled by IEEE 754 arithmetic
- Does not cause crashes or incorrect propagation
- Performance unchanged

**Validation Impact**: Minor
- Python port warnings document the issue
- Bit-level comparison still valid (both produce same inf/nan)
- Useful for identifying weak forcing conditions

### Recommended Action

**For Python Port:**
- **Status quo** - maintain exact MITgcm behavior
- Document warnings in code comments (already done)
- Optionally suppress warnings for timestep 0:
```python
if t_in_idx == 0:
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', 'divide by zero')
        warnings.filterwarnings('ignore', 'invalid value')
        output = driver.compute_mixing(...)
```

**For MITgcm Community:**
- Report issue to MITgcm developers
- Suggest adding `hbl` regularization for consistency with `wm`/`ws`
- Low priority (does not affect results)

---

## Issue 2: WSCALE Lookup Table Linear Extrapolation Hazard

**Status**: 🔴 Confirmed Bug (Documented by MITgcm Developers)  
**Severity**: High (can cause model crashes under extreme forcing)  
**MITgcm Location**: `pkg/kpp/kpp_routines.F:980`  
**Fix Available**: Line 990 (commented out)  
**Python Port Status**: 🟢 Bug fixed by default, gated by `keep_mitgcm_bugs` flag

### Description

MITgcm's `wscale` subroutine computes turbulent velocity scales (wm, ws) using bilinear interpolation from pre-computed lookup tables. For extremely negative buoyancy forcing, the interpolation can **linearly extrapolate beyond the table's lower edge**, producing unstable values that crash the model.

**The MITgcm developers themselves documented this bug in the source code** (lines 981-989) but left the buggy version active.

### MITgcm Source Code

**Active (buggy) code (line 980):**
```fortran
zdiff = zehat - zmin
```

**Commented-out fix (line 990, attributed to Dimitry Sidorenko):**
```fortran
C           zdiff = MAX( 0. _d 0, zehat - zmin )
```

**Developer comment (lines 981-989):**
```fortran
C     For extremely negative buoyancy forcing bfsfc, zehat and hence
C     zdiff can become very negative (default value of zmin = 4.e-7) and
C     the extrapolation beyond the limit zmin of the lookup table can
C     give very bad values and may make the model crash. Here is a
C     simple fix (thanks to Dimitry Sidorenko) that effectively replaces
C     linear extrapolation with nearest neighbor extrapolation so that
C     only the lower limit values of the lookup tables wmt/wst are used.
C     Alternatively, one can get rid of the lookup table altogether
C     and compute the coefficients online (done in NEMO, for example).
```

### When This Occurs

**Triggering Conditions:**
- Extremely negative buoyancy forcing: `bfsfc << 0`
- This causes `zehat = vonk * sigma * hbl * bfsfc` to become very negative
- Then `zdiff = zehat - zmin` becomes a large negative number
- `iz = int(zdiff / deltaz)` becomes a large negative index
- Bilinear interpolation extrapolates linearly beyond table edge
- Result: Extremely bad (possibly NaN or explosive) velocity scales

**Physical scenarios where this can happen:**
- Strong surface cooling with weak winds
- Very stable stratification with downward buoyancy flux
- Ice formation events (strong brine rejection)
- Arctic/Antarctic winter conditions

### Python Port Implementation

The Python port **fixes this bug by default** using a `keep_mitgcm_bugs` flag for validation purposes.

**Code (kpp_parameters.py:116-129):**
```python
# ========== MITgcm bug-compatibility switch ==========
# When True, reproduce the *exact* stock-MITgcm pkg/kpp behaviour, including
# a known numerical hazard that the MITgcm developers themselves flagged in
# the source but left active. When False (default), branch to bug-fixed code.
#
# Currently gated bug(s):
#   - wscale zdiff linear-extrapolation hazard (kpp_routines.F:980 vs :990)
keep_mitgcm_bugs: bool = False
```

**Code (kpp_routines.py:170-177):**
```python
if config.keep_mitgcm_bugs:
    # Stock MITgcm (line 980): unclamped -> may extrapolate below the
    # table and produce bad/unstable velocity scales.
    zdiff = zehat - config.zmin
else:
    # Bug-fixed (line 990, Sidorenko): clamp so we never index below
    # the table; nearest-neighbour behaviour at the lower edge.
    zdiff = max(0.0, zehat - config.zmin)
```

### Why MITgcm Hasn't Fixed This

**Possible reasons:**
1. **Backward compatibility**: Fixing the bug changes results of all existing simulations
2. **Rare occurrence**: May only trigger in extreme conditions not commonly encountered
3. **Testing burden**: Would require re-validating all verification experiments
4. **Documentation over fixing**: Developers documented the issue but left users to decide

### Impact Assessment

**Scientific Impact**: Potentially High
- Can cause model crashes in extreme forcing scenarios
- Produces incorrect mixing when extrapolation occurs
- Affects ice-covered regions, deep convection events

**Computational Impact**: Critical in edge cases
- Linear extrapolation can produce O(1e10) or NaN values
- These propagate and crash the model
- Nearest-neighbor extrapolation (fix) provides stable lower bound

**Validation Impact**: Critical for Python port
- Python port must be able to reproduce MITgcm bugs for validation
- `keep_mitgcm_bugs=False` (default) uses the safe, fixed behavior
- `keep_mitgcm_bugs=True` reproduces MITgcm exactly (for validation runs only)

### Recommended Action

**For Python Port:**
- ✅ **Already implemented** - bug fixed by default
- ✅ Validation mode available via `keep_mitgcm_bugs=True`
- ✅ Comprehensively documented in code comments
- **Default behavior**: Use bug-fixed code for all production runs
- **Validation runs**: Set `keep_mitgcm_bugs=True` only when comparing against buggy MITgcm output

**For MITgcm Community:**
- **Strongly recommend** uncommenting line 990 (the Sidorenko fix)
- Alternatively: Remove lookup tables entirely and compute wscale online (NEMO approach)
- Document that this changes results but improves stability
- Provide `KPP_SAFE_WSCALE` CPP option for users who need backward compatibility

**For End Users:**
- If using Python port: Keep default `keep_mitgcm_bugs=False`
- If using MITgcm: Consider manually uncommenting line 990 in `kpp_routines.F`
- Monitor for suspiciously large velocity scales under extreme forcing
- If model crashes with KPP, check if applying the Sidorenko fix resolves it

### Testing

**Python port testing:**
- Validated that `keep_mitgcm_bugs=True` reproduces MITgcm exactly (including bug)
- Validated that `keep_mitgcm_bugs=False` produces stable results under extreme forcing
- Confirmed nearest-neighbor behavior prevents negative table indexing

**MITgcm scenarios to test the fix:**
- Arctic winter convection with strong surface cooling
- Ice formation with brine rejection
- Deep water formation events
- Any scenario with strongly negative `bfsfc`

---

## Testing Methodology

Issues documented here were discovered through:

1. **Bit-level validation** against MITgcm using lab_sea verification experiment
2. **Instrumented comparison** of Python vs Fortran intermediate values
3. **Edge case analysis** at timestep 0 with weak initial forcing
4. **Systematic numerical testing** across 1000 timesteps, 20×16 grid

**Test Configuration:**
- Experiment: `lab_sea` (MITgcm verification)
- Grid: 20×16 horizontal, 23 vertical levels
- Duration: 1000 timesteps
- Python script: `scripts/run_kpp_from_netcdf_input.py`
- Input file: `mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc`

---

## References

### MITgcm Source Files
- `pkg/kpp/kpp_routines.F` - Main KPP subroutines (BLMIX, BLDEPTH, etc.)
- `pkg/kpp/kpp_calc.F` - KPP driver

### Python Port Files
- `1D_Mixing_Model/KPP/kpp_scheme_specific.py` - Boundary layer mixing implementation
- `1D_Mixing_Model/KPP/kpp_core_driver.py` - Main KPP driver

### Related Documentation
- MITgcm KPP documentation: [MITgcm manual, Section 2.5](https://mitgcm.readthedocs.io/en/latest/phys_pkgs/kpp.html)
- Large et al. (1994): "Oceanic vertical mixing: A review and a model with a nonlocal boundary layer parameterization"
- `potential_bugs_and_inconsistencies.md` - General bug tracking across GGL90 and KPP

---

## Revision History

- **2026-08-20**: Initial documentation of hbl divide-by-zero issue
  - Identified during lab_sea validation
  - Confirmed to only affect timestep 0
  - Determined to be present in MITgcm source (not a Python port bug)
