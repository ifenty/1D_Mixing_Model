# Potential Bugs and Inconsistencies with MITgcm

This file tracks suspected bugs or inconsistencies between the Python port and MITgcm that require investigation.

**Status Legend**:
- 🔴 **Unresolved** - Needs investigation
- 🟡 **Investigating** - Work in progress
- 🟢 **Resolved** - Fixed and verified
- ⚪ **Not a bug** - False alarm, working as intended

---

## 🟢 RESOLVED: GGL90 Density Gradient Calculation

**Date Identified**: 2026-07-20  
**Date Resolved**: 2026-07-20  
**Status**: Fixed

### Issue
GGL90 was using in-situ density gradients instead of potential density gradients to compute N² (buoyancy frequency squared).

### Evidence
- MITgcm's `grad_sigma.F` and `do_oceanic_phys.F` explicitly compute potential density by evaluating T(k-1), S(k-1) at pressure P(k)
- Python port computed `rho[k] = ρ(T(k), S(k), P(k))` at each level, then took gradients
- This included compressibility effects that should be removed

### Impact
- Overestimated stratification in deep water (>1000m)
- Could suppress mixing more than MITgcm
- Errors increase with depth due to compressibility

### Resolution
- Created `compute_ggl90_buoyancy_frequency_squared()` in `eos.py`
- Updated GGL90 adapter and driver to use new function
- See `GGL90_DENSITY_GRADIENT_FIX_SUMMARY.md` for details

---

## 🔴 UNRESOLVED: Test File Maintenance Issues

**Date Identified**: 2026-07-20  
**Status**: Unresolved - Low Priority

### Issue
Several test files had outdated imports and function signatures:
- `test_staggering.py` imported from non-existent `ggl90_core` module (should be `ggl90_core_driver`)
- Tests called methods that don't exist on current driver classes
- Tests assumed old function signatures

### Evidence
```python
# In test_staggering.py (line 37)
from GGL90_ML.GGL90_PY.ggl90_core import GGL90Driver  # Module doesn't exist

# Tests called methods like:
n2 = drv.compute_buoyancy_frequency_squared(rho, z, gravity=9.81)
# But this method doesn't exist on GGL90Driver
```

### Potential Impact
- Tests were not being run or were failing
- Could mask regressions in refactoring
- Suggests test suite may not be part of regular CI/validation

### Recommended Action
1. Audit all test files for correct imports and signatures
2. Run full test suite to identify failures
3. Consider adding test suite to CI/pre-commit hooks
4. Review test coverage for GGL90 and KPP modules

---

## ⚪ NOT A BUG: Static Instability Mask - Density Type Verification

**Date Identified**: 2026-07-20  
**Date Investigated**: 2026-07-20  
**Status**: Verified correct

### Issue
`compute_static_instability_mask()` in `eos.py` uses in-situ density to test for instability. The comment says:

> "MITgcm's own instability test only depends on the SIGN of the density gradient (`-sigmaR*gravitySign > 0`), not on any particular scaling of N^2, so this only needs in-situ density"

This needs verification against MITgcm source.

### Evidence
```python
# From eos.py lines 362-403
def compute_static_instability_mask(...):
    pressure = -depth  # dbar
    rho_anom, _, _ = jmd95_eos(theta, salt, pressure, rho_const)
    rho = rho_anom + rho_const
    
    unstable = np.zeros(nz, dtype=bool)
    unstable[1:] = rho[:-1] > rho[1:]  # Uses in-situ density
    return unstable
```

### Questions to Resolve
1. Does MITgcm's `convective_weights.F` or `calc_ivdc.F` use in-situ or potential density for instability testing?
2. Is the sign test actually independent of density type, or does it matter for edge cases?
3. Should this use `sigmaR` (potential density gradient) for consistency?

### Resolution
**Verified against MITgcm source** (`model/src/convective_adjustment.F` lines 122-136):

MITgcm computes:
- `rhoKm1` = T(k-1), S(k-1) at pressure k-1 (in-situ)
- `rhoK` = T(k), S(k) at pressure k (in-situ)

Instability test: `(rhoK - rhoKm1) * rkSign * gravitySign < 0`

**Both densities are IN-SITU**. The Python implementation matches MITgcm exactly. The comment in `eos.py` is correct: the sign test depends only on the sign of the density difference, and using in-situ density is the correct approach for detecting static instability.

---

## 🟢 RESOLVED: Pressure Conversion History

**Date Identified**: 2026-07-20 (historical issue)  
**Date Investigated**: 2026-07-20  
**Status**: Verified fixed throughout codebase

### Issue
Comments in `eos.py` and `mixing_adapter.py` reference a bug fix where pressure was incorrectly computed as `-depth / 10.0` instead of `-depth`.

```python
# From eos.py line 451-456
# NOTE (bug fix): the previous port used `-depth / 10.0`, which is a
# factor of 10 too small (it would put 1000 m at only 100 dbar). That
# under-stated the compressibility correction in the EOS.
```

### Questions to Resolve
1. Was this bug present in both GGL90 and KPP paths?
2. Has it been completely removed from all code paths?
3. Are there any lingering effects (e.g., tuned parameters that compensated for the bug)?

### Resolution
**Audit completed** (2026-07-20):

Searched entire codebase for patterns: `depth / 10`, `depth * 0.1`, `10 * depth`

**Findings**:
- All current code uses correct formula: `pressure = -depth` (1 dbar ≈ 1 m)
- Only references found are comments documenting the historical bug fix
- Found in: `eos.py` (lines 451-456), `mixing_adapter.py`, `test_full_scenario_validation.py`

**Verified files**:
- `main/eos.py` - 4 instances, all correct
- `main/mixing_adapter.py` - corrected (see comments)
- Test files - all correct

The bug was fully fixed in a previous update. No action needed.

---

## ⚪ NOT A BUG: KPP Buoyancy Gradients - Denominator Convention

**Date Identified**: 2026-07-20  
**Date Investigated**: 2026-07-20  
**Status**: Verified correct

### Issue
Comments in `eos.py` mention two bugs that were fixed in `compute_buoyancy_gradients()`:
1. Sign error (deeper-minus-shallower vs shallower-minus-deeper)
2. Denominator error (double-counting rho_const)

The comment says "Neither behaviour exists in MITgcm" but this needs source-level verification.

### Evidence
```python
# From eos.py lines 487-498
# TWO bugs are fixed here relative to the previous port, both of which made
# this a Python porting error (the Fortran is correct):
#   1. SIGN: it computed (rho[k]-rho[k+1]) = shallower-minus-deeper, which is
#      negative under stable stratification.
#   2. DENOMINATOR: it divided by (rho[k+1] + rho_const) ~ 2070, double
#      counting rhoConst (rho[k+1] is already the full in-situ density).
```

### Questions to Resolve
1. Verify against MITgcm's `kpp_routines.F` (STATEKPP) that sign is correct
2. Confirm denominator should be `rho_deep` not `rho_deep + rho_const`
3. Check if these bugs affected any published results or tuned parameters

### Resolution
**Verified against MITgcm source** (`pkg/kpp/kpp_routines.F` lines 1886-1933):

MITgcm formula (line 1930-1931):
```fortran
DBLOC = gravity * (RHOK - RHOKM1) / (RHOK + rhoConst)
```

Where:
- `RHOK` = density ANOMALY (ρ(k) - ρ₀) 
- `RHOKM1` = density ANOMALY (ρ(k-1,at_P(k)) - ρ₀)
- `RHOK + rhoConst` = full in-situ density at k

Python implementation (`eos.py` line 513):
```python
dbloc = gravity * (rho_deep - rho_shal_at_deep) / rho_deep
```

Where `rho_deep` is the **full in-situ density** (line 467: `rho = rho_anom + rho_const`).

**The implementations match exactly.** The comment about "double counting" refers to a bug that was already fixed before this investigation - the current code is correct.

---

## 🟡 INVESTIGATING: Test Suite Coverage and CI Integration

**Date Identified**: 2026-07-20  
**Date Updated**: 2026-08-05  
**Status**: Partially resolved, ongoing work

### Issue
Multiple test files were found to be outdated or non-functional:
- Imports from deleted modules
- Function signatures that don't match current implementation
- No evidence of regular test execution

### Evidence
- Fixed 4+ test files during density gradient fix
- No test failures were caught before manual code review
- Test files existed but weren't preventing regressions

### Progress (2026-07-20)

**Fixed**:
- `test_staggering.py` - All 8 tests now passing
  - Fixed depth/z convention confusion (depth should be negative-down)
  - Fixed import paths (`kpp_core` → `kpp_core_driver`, `ggl90_core` → `ggl90_core_driver`)
  - Removed invalid parameters from function calls
- `test_cross_scheme_validation.py` - Updated GGL90 calls to use new signature
- `test_potential_density_gradient.py` - Created as part of density gradient fix

### Progress (2026-08-05)

**Fixed**:
- `test_baseline_refactor.py` - ✅ **RESOLVED**
  - Changed relative import `from ...main.eos` to absolute import `from main.eos` in `ggl90_core_driver.py` (line 310)
  - Test now passes successfully with exit code 0
  - Verified all GGL90 baseline functionality working correctly

**Remaining Issues**:
1. No CI/pre-commit hooks in place
2. No documented test execution procedure

**Recommended Next Actions**:
1. Create `TESTING.md` with test execution procedures
2. Add pre-commit hook or GitHub Actions workflow to run tests
3. Consider pytest configuration for easier test discovery

---

## ⚪ NOT A BUG: Linear EOS Consistency

**Date Identified**: 2026-07-20  
**Date Investigated**: 2026-07-20  
**Status**: Dead code, kept for testing

### Issue
Code includes linear EOS option (`use_jmd95=False`) but it's unclear if:
1. Linear EOS coefficients match MITgcm's linear EOS option
2. This is used in production or only for testing
3. Linear EOS path has been validated against MITgcm

### Evidence
Multiple functions accept `use_jmd95` parameter but no documentation on when/why to use linear EOS.

### Resolution
**Audit completed** (2026-07-20):

Searched all code for `use_jmd95` parameter - **all calls use `use_jmd95=True`** (JMD95 EOS).

**Findings**:
- `linear_eos()` function exists in `eos.py` but is never called in production
- Present in 3 functions as fallback when `use_jmd95=False`:
  - `compute_buoyancy_gradients()` 
  - `compute_ggl90_buoyancy_frequency_squared()`
  - Implicit in conditionals
- No configuration or test uses linear EOS

**Recommendation**: Keep as-is. The linear EOS provides:
1. Simplified testing when compressibility doesn't matter
2. Fallback for debugging (isolate EOS complexity)
3. Minimal maintenance burden (simple linear formula)

No action needed. This is intentional dead code for testing/debugging purposes.

---

## Template for New Entries

```markdown
## 🔴 UNRESOLVED: [Brief Title]

**Date Identified**: YYYY-MM-DD  
**Status**: Unresolved

### Issue
[Clear description of the suspected bug or inconsistency]

### Evidence
[Code snippets, MITgcm references, or observations that led to suspicion]

### Potential Impact
[What could go wrong if this is actually a bug?]

### Recommended Action
[Steps to investigate and resolve]
```

---

**Last Updated**: 2026-07-20  
**Total Issues**: 7
- 🟢 Resolved: 2 (GGL90 density gradient, Pressure conversion)
- 🟡 Investigating: 1 (Test suite maintenance - partially fixed)
- ⚪ Not a bug: 3 (Static instability mask, KPP denominator, Linear EOS)
- 🔴 Unresolved: 1 (remaining test file import issues)
