# Critical Lessons Learned: Fortran to Python Porting

**Project**: MITgcm KPP & GGL90 Python Port  
**Date**: 2026-08-20  
**Purpose**: Document critical differences between Fortran and Python that caused bugs during porting

---

## Executive Summary

Porting MITgcm's ocean mixing schemes from Fortran 77 to Python revealed numerous subtle language differences that caused bugs despite careful implementation. This document consolidates all porting lessons learned to help future developers avoid these pitfalls.

**Key Finding**: Language differences in sign conventions, array indexing, intrinsic functions, and numerical precision caused more bugs than algorithm misunderstandings.

---

## Table of Contents

1. [Sign Function Behavior](#1-sign-function-behavior-critical)
2. [Array Indexing (0-based vs 1-based)](#2-array-indexing-0-based-vs-1-based)
3. [Density Gradient Conventions](#3-density-gradient-conventions)
4. [Pressure Units and Conversions](#4-pressure-units-and-conversions)
5. [Division by Zero Handling](#5-division-by-zero-handling)
6. [Floating Point Comparisons](#6-floating-point-comparisons)
7. [Lookup Table Extrapolation](#7-lookup-table-extrapolation)
8. [Parameter Passing and Defaults](#8-parameter-passing-and-defaults)
9. [Grid Staggering and Interfaces](#9-grid-staggering-and-interfaces)
10. [CPP Conditionals and Build Options](#10-cpp-conditionals-and-build-options)

---

## 1. Sign Function Behavior (CRITICAL)

### The Bug

**File**: `kpp_scheme_specific.py:372-373` (discovered 2026-08-20)

**Symptom**: Divide-by-zero warnings in boundary layer mixing despite regularization code

**Root Cause**: Fortran's `SIGN` intrinsic and Python's `np.sign()` behave differently for zero inputs.

### Fortran vs Python Behavior

| Input | Fortran `SIGN(1.0, x)` | Python `np.sign(x)` |
|-------|------------------------|---------------------|
| `x > 0` | `+1.0` | `+1.0` |
| `x < 0` | `-1.0` | `-1.0` |
| **`x = 0`** | **`+1.0`** ✓ | **`0.0`** ✗ |

### The MITgcm Code

```fortran
! kpp_routines.F:1493-1495
DO i = 1, imt
   wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
   ws(i) = sign(eins,ws(i))*MAX(phepsi,ABS(ws(i)))
ENDDO
```

Where `eins = 1.0` and `phepsi = 1e-10`.

**Fortran logic**: When `wm(i) = 0`, the result is `+1.0 * phepsi = +1e-10` (regularized to positive)

### The Buggy Python Translation

```python
# BUGGY VERSION - DO NOT USE
wm_one = np.sign(wm_one[0]) * max(config.phepsi, abs(wm_one[0]))
ws_one = np.sign(ws_one[0]) * max(config.phepsi, abs(ws_one[0]))
```

**Python behavior**: When `wm_one[0] = 0`:
- `max(config.phepsi, abs(0.0))` = `1e-10` ✓
- `np.sign(0.0)` = `0.0` ✗
- Result: `0.0 * 1e-10` = `0.0` (regularization defeated!)

### The Correct Python Translation

```python
# CORRECT VERSION
wm_one_mag = max(config.phepsi, abs(wm_one[0]))
ws_one_mag = max(config.phepsi, abs(ws_one[0]))

# Apply sign, defaulting to positive when exactly zero (Fortran behavior)
if wm_one[0] == 0.0:
    wm_one = wm_one_mag
else:
    wm_one = np.copysign(wm_one_mag, wm_one[0])

if ws_one[0] == 0.0:
    ws_one = ws_one_mag
else:
    ws_one = np.copysign(ws_one_mag, ws_one[0])
```

### Lesson Learned

**⚠️ CRITICAL**: Never directly translate Fortran `SIGN(a, b)` to Python `np.sign(b) * a`. Always handle the zero case explicitly.

**General pattern**:
```python
# Fortran: result = SIGN(magnitude, value)
# Python equivalent:
if value == 0.0:
    result = abs(magnitude)  # Fortran returns positive for zero
else:
    result = np.copysign(magnitude, value)
```

---

## 2. Array Indexing (0-based vs 1-based)

### The Issue

**Fortran**: Arrays are 1-indexed by default
**Python**: Arrays are 0-indexed

This is well-known but still causes bugs when:
1. MITgcm hardcodes `1` for surface level
2. Loop bounds are copied directly (e.g., `DO k=1,Nr` → `for k in range(1, Nr+1)` is WRONG)
3. Comments refer to "level 1" meaning different things

### Example: Surface Level References

**MITgcm Fortran**:
```fortran
! Surface is at k=1
hbl_min = -rC(1)  ! First cell center depth
```

**Python Translation**:
```python
# Surface is at k=0
hbl_min = -depth[0]  # First cell center depth
```

### Example: Loop Indexing

**Fortran**:
```fortran
DO k = 1, Nr
   ! Process level k
   density(k) = ...
ENDDO
```

**Python (WRONG)**:
```python
for k in range(1, Nr+1):  # WRONG - creates array indices 1..Nr
    density[k] = ...  # IndexError when k=Nr
```

**Python (CORRECT)**:
```python
for k in range(Nr):  # Creates indices 0..Nr-1
    density[k] = ...
```

### Example: Interface vs Cell Center

**MITgcm convention**: Interface k is between cell k and k+1 (1-indexed)

**Python translation**:
```python
# Interface k is between cell k and k+1 (0-indexed)
# Interface 0 is at the surface (above cell 0)
# Interface k=Nr is at the bottom (below cell Nr-1)

for k in range(Nr):
    # Cell k boundaries:
    # - Upper interface: k
    # - Lower interface: k+1
```

### Lesson Learned

**Best Practice**:
1. Use 0-indexed loops in Python: `range(Nr)` not `range(1, Nr+1)`
2. Add comments mapping Fortran levels to Python indices
3. Search for hardcoded `1` in Fortran and verify it means "first element"
4. Test boundary conditions (surface and bottom) explicitly

---

## 3. Density Gradient Conventions

### The Bug

**File**: Multiple files (discovered 2026-07-20)

**Symptom**: Two bugs in `compute_buoyancy_gradients()`:
1. Sign error: computed `rho[k] - rho[k+1]` (shallow - deep) instead of `rho[k+1] - rho[k]` (deep - shallow)
2. Denominator error: divided by `rho[k+1] + rho_const` instead of just `rho[k+1]`

### MITgcm Formula

```fortran
! kpp_routines.F:1930-1931 (STATEKPP subroutine)
! RHOK, RHOKM1 are density ANOMALIES (rho - rho_const)
! Positive dbloc means unstable (denser fluid above)
DBLOC = gravity * (RHOK - RHOKM1) / (RHOK + rhoConst)
```

Where:
- `RHOK` = density anomaly at level k
- `RHOKM1` = density anomaly at level k-1, evaluated at pressure of level k (potential density reference)
- `RHOK + rhoConst` = full in-situ density at level k

### Buggy Python Version (Historical)

```python
# BUGGY - DO NOT USE
# Bug 1: Wrong sign (shallow - deep instead of deep - shallow)
# Bug 2: Double-counted rho_const in denominator
dbloc = gravity * (rho[k] - rho[k+1]) / (rho[k+1] + rho_const)
```

### Correct Python Version

```python
# Correct implementation (eos.py:513)
# rho_deep is FULL in-situ density (includes rho_const already)
# rho_shal_at_deep is density at shallow level, evaluated at deep pressure
dbloc = gravity * (rho_deep - rho_shal_at_deep) / rho_deep
```

### Lesson Learned

**Critical distinction**:
- MITgcm often stores **density anomaly** (ρ - ρ₀) 
- Python often stores **full density** (ρ)
- When translating, check whether `rho_const` / `rhoConst` is already included

**Sign convention**:
- Positive buoyancy gradient = unstable stratification (heavy over light)
- Formula: `(deep - shallow)` not `(shallow - deep)`
- Always verify sign by checking: stable stratification should give negative values

---

## 4. Pressure Units and Conversions

### The Bug

**File**: Multiple files (discovered and fixed before 2026-07-20)

**Symptom**: Factor of 10 error in pressure conversion from depth

### The Issue

MITgcm uses **decibars** (dbar) for pressure, where:
- 1 dbar ≈ 1 meter of seawater
- Pressure in dbar ≈ -depth in meters (with sign flip)

### Historical Bug

```python
# BUGGY - DO NOT USE
pressure = -depth / 10.0  # WRONG! Off by factor of 10
```

This would put 1000m at only 100 dbar, dramatically under-stating compressibility effects.

### Correct Conversion

```python
# Correct (current implementation)
pressure = -depth  # 1 dbar ≈ 1 m depth
```

### Related Note: Surface Pressure

MITgcm typically uses:
- `pressure = 0` at sea surface
- Depth is negative downward (`depth[0] = -5m` for 5m deep cell center)
- Therefore: `pressure = -depth`

### Lesson Learned

**Best Practice**:
1. Always verify pressure units in equations (dbar, Pa, or atm?)
2. MITgcm EOS expects pressure in **decibars**
3. Check sign convention: pressure increases with depth (positive), depth increases downward (negative)
4. Add unit tests: verify EOS at known P/T/S points

---

## 5. Division by Zero Handling

### The Issue

Fortran and Python handle division by zero differently:
- **Fortran**: Often produces `Inf` or `NaN` without warning (depends on compiler flags)
- **Python**: Raises `RuntimeWarning` by default, making issues visible

### Example: Boundary Layer Mixing

**MITgcm code**:
```fortran
! kpp_routines.F:1556
! Divides by hbl without checking for zero
gat1m(i) = visch / hbl(i) / wm(i)
```

When `hbl` or `wm` approach zero (weak forcing, stable stratification), this produces `Inf`/`NaN` that propagate through but don't crash the model.

**Python warning**:
```
RuntimeWarning: divide by zero encountered in scalar divide
  gat1m = visch / hbl / wm_one
```

### Lesson Learned

**Don't blindly suppress warnings**. Instead:

1. **Understand the physics**: Is zero a valid edge case?
2. **Check MITgcm source**: Does it handle this case explicitly?
3. **Match MITgcm behavior**: If MITgcm divides without checking, Python should too (for bit-level compatibility)
4. **Document the issue**: Add comments explaining why division by near-zero is acceptable

**Example comment**:
```python
# NOTE: MITgcm does not check for hbl=0 before division (kpp_routines.F:1556).
# In edge cases with weak forcing, this produces Inf/NaN which propagate but
# result in negligible mixing (the physically correct outcome). To match MITgcm
# exactly, we do NOT add extra checks here. The warnings can be ignored.
```

---

## 6. Floating Point Comparisons

### The Issue

Direct floating-point equality tests are unreliable due to numerical precision, but sometimes necessary for exact MITgcm reproduction.

### Example: Zero Check in Sign Regularization

```python
# Need exact zero check to match Fortran behavior
if wm_one[0] == 0.0:  # Intentional exact comparison
    wm_one = wm_one_mag
else:
    wm_one = np.copysign(wm_one_mag, wm_one[0])
```

This is correct because:
1. The value is directly computed and assigned (not result of subtraction)
2. We're checking for exactly zero, not near-zero
3. Fortran `SIGN` behaves differently for exactly `0.0`

### Example: Early Exit Check

```python
# Checking for exactly zero hbl
if hbl == 0.0:
    warnings.warn(...)
    return np.zeros(nz), ...
```

### When to Use Exact Comparisons

**Use `==` when**:
- Checking for exactly zero after initialization
- Values directly assigned (not computed)
- Matching Fortran conditional logic that uses `.EQ.`

**Use tolerance when**:
- Comparing computed results
- Checking convergence
- Validating against reference data

```python
# Tolerance comparison
if abs(computed - expected) < 1e-12:
    ...
```

### Lesson Learned

**Best Practice**:
1. Understand whether the Fortran uses `.EQ.` (exact) or `.LT.`/`.GT.` (relational)
2. For bit-level validation, sometimes exact `==` is necessary
3. Document why exact comparison is used (reference Fortran line)
4. For scientific validation, always use tolerances

---

## 7. Lookup Table Extrapolation

### The Bug

**File**: `kpp_routines.py:170-177` (flagged with `keep_mitgcm_bugs`)

**Issue**: MITgcm has a documented bug where negative buoyancy forcing can cause linear extrapolation beyond lookup table bounds, producing unstable values.

### MITgcm Code

```fortran
! kpp_routines.F:980
zdiff = zehat - zmin  ! Can be negative!

! The commented-out fix (line 990):
! zdiff = MAX( 0. _d 0, zehat - zmin )
```

MITgcm developers documented this (lines 981-989) but left the buggy version active.

### Python Implementation

```python
if config.keep_mitgcm_bugs:
    # Stock MITgcm (line 980): unclamped -> may extrapolate
    zdiff = zehat - config.zmin
else:
    # Bug-fixed (line 990, Sidorenko): clamp to prevent negative index
    zdiff = max(0.0, zehat - config.zmin)
```

### Lesson Learned

**When porting known bugs**:
1. Implement the **correct** version as default
2. Add a compatibility flag (`keep_mitgcm_bugs`) for validation
3. Document the bug thoroughly with MITgcm line references
4. Include the developer's own comments about the hazard

**Validation strategy**:
- Set `keep_mitgcm_bugs=True` only for bit-level validation against MITgcm
- Use `keep_mitgcm_bugs=False` (default) for production runs
- Document that results will differ (for the better)

---

## 8. Parameter Passing and Defaults

### The Bug

**File**: `run_kpp_from_netcdf_input.py` (discovered 2026-08-20)

**Symptom**: Parameters extracted from NetCDF but not passed to `KPPParameters`

### The Code

```python
# Extracted from NetCDF
params_dict = {
    'gravity': float(inputs_ds.gravity),
    'rho_const': float(inputs_ds.rho_const),
    ...
}

# But not passed to KPPParameters!
kpp_params = KPPParameters(
    ghat_use_total_diffus=True,
    use_sw_frac_3d=False,
    # gravity=params_dict['gravity'],        # MISSING
    # rho_const=params_dict['rho_const']     # MISSING
)
```

Result: Used Python defaults instead of MITgcm values (minimal impact: 0.05%)

### Lesson Learned

**Best Practice**:
1. Explicitly pass ALL parameters that could vary
2. Don't rely on defaults matching between Fortran and Python
3. Add validation: check that parameters match between input file and driver
4. Use dataclasses to make parameter passing explicit

**Example validation**:
```python
# Validate parameters match
if abs(kpp_params.gravity - inputs_ds.attrs['gravity']) > 1e-10:
    raise ValueError(f"Gravity mismatch: {kpp_params.gravity} vs {inputs_ds.attrs['gravity']}")
```

---

## 9. Grid Staggering and Interfaces

### The Issue

MITgcm uses "top-of-cell" staggering:
- **Cell centers** (T-points): temperature, salinity, density
- **Cell interfaces** (W-points): vertical velocity, mixing coefficients

### Critical Convention Differences

| Concept | Fortran 1-indexed | Python 0-indexed |
|---------|-------------------|------------------|
| Surface interface | k=1 | k=0 |
| Interface between cells 1 and 2 | k=2 | k=1 |
| Bottom interface | k=Nr+1 | k=Nr |
| Number of interfaces | Nr+1 | Nr+1 |

### Example: Diffusivity Arrays

**MITgcm**:
```fortran
! KPPdiffKzT(i,j,k) is diffusivity at interface k
! k=1 is surface, k=Nr+1 is bottom
DO k = 1, Nr
   flux(k) = KPPdiffKzT(i,j,k) * (T(k-1) - T(k)) / dzC(k)
ENDDO
```

**Python**:
```python
# diff_kz_t[k] is diffusivity at interface k (0-indexed)
# k=0 is surface, k=Nr is bottom
for k in range(Nr):
    if k == 0:
        # Surface flux: no cell above
        flux[k] = ...
    else:
        flux[k] = diff_kz_t[k] * (T[k-1] - T[k]) / dz[k]
```

### Lesson Learned

**Best Practice**:
1. Draw a diagram showing cell centers and interfaces with BOTH indexing schemes
2. Add extensive comments for boundary conditions (k=0 and k=Nr)
3. Verify flux arrays have correct dimension: `Nr+1` interfaces for `Nr` cells
4. Test explicitly at boundaries

---

## 10. CPP Conditionals and Build Options

### The Issue

MITgcm uses C preprocessor (CPP) to enable/disable code at compile time:
```fortran
#ifdef ALLOW_AUTODIFF_TAMC
CADJ STORE ...
#endif
```

Python has no equivalent preprocessor, so conditional logic must be explicit.

### Example: Lookup Table Regularization

**MITgcm**:
```fortran
f1 = stable(i) * conc1 * bfsfc(i) /
#ifdef KPP_SMOOTH_REGULARISATION
     &        (ustar(i)**4 + phepsi)
#else
     &        MAX(ustar(i)**4,phepsi)
#endif
```

**Python Translation**:
```python
if config.smooth_regularization:
    f1 = stable * config.conc1 * bfsfc / (ustar**4 + config.phepsi)
else:
    f1 = stable * config.conc1 * bfsfc / max(ustar**4, config.phepsi)
```

### Common CPP Flags in KPP

| Flag | Purpose | Python Equivalent |
|------|---------|-------------------|
| `ALLOW_KPP` | Enable KPP | Always enabled |
| `KPP_SMOOTH_REGULARISATION` | Smooth vs hard regularization | `config.smooth_regularization` |
| `ALLOW_DIAGNOSTICS` | Enable diagnostics output | `config.save_diagnostics` |
| `SHORTWAVE_HEATING` | Penetrating shortwave | `config.shortwave_heating` |

### Lesson Learned

**Best Practice**:
1. Search MITgcm source for all `#ifdef` blocks in relevant files
2. Add corresponding boolean flags to Python configuration classes
3. Document which MITgcm CPP flag each Python parameter corresponds to
4. Set Python defaults to match MITgcm's most common build configuration
5. Add validation tests for each CPP branch

**Example configuration**:
```python
@dataclass
class KPPParameters:
    # Corresponds to MITgcm CPP flag KPP_SMOOTH_REGULARISATION
    smooth_regularization: bool = False  # MITgcm default is hard MAX
```

---

## Summary Checklist for Porting

When translating MITgcm Fortran to Python, verify:

- [ ] **Sign functions**: Handle `SIGN(a, 0.0)` correctly (returns positive `a`)
- [ ] **Array indexing**: Convert 1-indexed loops to 0-indexed (`DO k=1,Nr` → `range(Nr)`)
- [ ] **Surface references**: Fortran level 1 → Python index 0
- [ ] **Density types**: Check if anomaly (ρ - ρ₀) or full density (ρ)
- [ ] **Pressure units**: Verify decibars vs Pascals (`pressure = -depth` for dbar)
- [ ] **Division by zero**: Match MITgcm behavior, document edge cases
- [ ] **Float comparisons**: Use exact `==` only when justified, otherwise tolerance
- [ ] **Lookup tables**: Handle extrapolation (clamp or allow like MITgcm)
- [ ] **Parameter defaults**: Explicitly pass all parameters, don't rely on defaults
- [ ] **Grid staggering**: Document interface vs cell center indexing
- [ ] **CPP conditionals**: Add Python flags for all MITgcm `#ifdef` blocks
- [ ] **Sign conventions**: Verify deep-shallow vs shallow-deep for gradients
- [ ] **Boundary conditions**: Test k=0 (surface) and k=Nr-1 (bottom) explicitly

---

## Testing Recommendations

### Unit Tests for Language Differences

```python
def test_sign_function_zero():
    """Verify sign regularization handles zero correctly (Fortran SIGN behavior)"""
    value = 0.0
    magnitude = 1e-10
    
    # Fortran: SIGN(magnitude, value) returns +magnitude when value=0
    if value == 0.0:
        result = magnitude
    else:
        result = np.copysign(magnitude, value)
    
    assert result == 1e-10  # Not 0.0!

def test_array_indexing():
    """Verify 0-indexing matches Fortran 1-indexing logic"""
    Nr = 10
    # Fortran: DO k=1,Nr processes 10 levels
    # Python: range(Nr) also processes 10 levels (0..9)
    count = 0
    for k in range(Nr):
        count += 1
    assert count == Nr

def test_pressure_conversion():
    """Verify pressure in decibars matches depth convention"""
    depth = np.array([-5.0, -15.0, -25.0])  # Negative downward
    pressure = -depth
    assert np.allclose(pressure, [5.0, 15.0, 25.0])  # Positive increasing
```

### Validation Against MITgcm

```python
def test_bit_level_validation():
    """Compare Python output against MITgcm reference"""
    # Load MITgcm outputs
    mitgcm_data = load_mitgcm_reference()
    
    # Run Python version
    python_data = run_python_version(mitgcm_data.inputs)
    
    # Bit-level comparison (adjust tolerance as needed)
    for field in ['hbl', 'visc_az', 'diff_kz_s', 'diff_kz_t']:
        np.testing.assert_allclose(
            python_data[field],
            mitgcm_data[field],
            rtol=1e-14,  # ~machine precision for 64-bit
            err_msg=f"Mismatch in {field}"
        )
```

---

## References

### Bug Reports and Fixes
- `potential_bugs_and_inconsistencies.md` - Complete bug tracking
- `KPP_port_validation/FINAL_STATUS.md` - Validation summary
- `KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md` - MITgcm bugs found

### MITgcm Source Files
- `pkg/kpp/kpp_routines.F` - Core KPP subroutines
- `pkg/kpp/kpp_calc.F` - KPP driver
- `pkg/ggl90/ggl90_calc.F` - GGL90 driver
- `model/src/convective_adjustment.F` - Static instability handling

### Python Implementation
- `1D_Mixing_Model/KPP/kpp_scheme_specific.py` - Boundary layer mixing
- `1D_Mixing_Model/KPP/kpp_routines.py` - Interior mixing, wscale
- `1D_Mixing_Model/main/eos.py` - Equation of state, buoyancy gradients
- `1D_Mixing_Model/main/physics_basis.py` - Shared physics functions

---

**Document Version**: 1.0  
**Last Updated**: 2026-08-20  
**Contributors**: Identified through comprehensive validation against MITgcm lab_sea experiment

**Note**: This is a living document. Add new lessons learned as they are discovered during ongoing validation work.
