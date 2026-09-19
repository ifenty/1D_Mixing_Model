# Simplified Forcing API - Final Implementation

**Date**: 2026-08-20  
**Status**: ✅ Complete

---

## Summary of Simplification

**Removed**: `validate_forcing` parameter (explicit flag)  
**Added**: Automatic mode detection based on which parameters are provided

**Result**: Cleaner, more intuitive API with clear error messages

---

## Three Usage Modes

Mode is determined **automatically** based on which parameters you provide:

### Mode 1: Pre-computed Forcing (Standard Validation)

**Provide**:
- `ustar_forcing` ✓
- `bo_forcing` ✓
- `bosol_forcing` ✓

**Omit** (or set to None):
- `tau_x`, `tau_y`, `q_net`, `q_sw`, `fw_flux`

**Behavior**: Uses pre-computed forcing for mixing calculation

**Use case**: Standard KPP validation (mixing scheme only)

```python
output = driver.compute_mixing(
    theta=theta, salt=salt, u_vel=u, v_vel=v,
    depth=depth, cell_thickness=dz,
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    # tau_x, tau_y, q_net, q_sw, fw_flux all None
)
```

### Mode 2: Compute Forcing (Standalone)

**Provide**:
- `tau_x` ✓
- `tau_y` ✓
- `q_net` ✓
- `q_sw` ✓
- `fw_flux` ✓

**Omit** (or set to None):
- `ustar_forcing`, `bo_forcing`, `bosol_forcing`

**Behavior**: Computes forcing from raw fluxes, uses for mixing

**Use case**: Standalone KPP runs without MITgcm reference

```python
output = driver.compute_mixing(
    theta=theta, salt=salt, u_vel=u, v_vel=v,
    depth=depth, cell_thickness=dz,
    tau_x=tau_x,
    tau_y=tau_y,
    q_net=q_net,
    q_sw=q_sw,
    fw_flux=fw_flux,
    # ustar_forcing, bo_forcing, bosol_forcing all None
)
```

### Mode 3: Forcing Validation (Automatic)

**Provide ALL EIGHT**:
- `tau_x` ✓
- `tau_y` ✓
- `q_net` ✓
- `q_sw` ✓
- `fw_flux` ✓
- `ustar_forcing` ✓
- `bo_forcing` ✓
- `bosol_forcing` ✓

**Behavior**:
1. Computes forcing from raw fluxes
2. Validates against MITgcm pre-computed (1% tolerance)
3. If validation passes: uses pre-computed for mixing
4. If validation fails: raises ValueError with diagnostics
5. Stores computed forcing in output (`ustar_computed`, `bo_computed`, `bosol_computed`)

**Use case**: Validate that Python forcing computation matches MITgcm

```python
output = driver.compute_mixing(
    theta=theta, salt=salt, u_vel=u, v_vel=v,
    depth=depth, cell_thickness=dz,
    # Raw fluxes
    tau_x=tau_x,
    tau_y=tau_y,
    q_net=q_net,
    q_sw=q_sw,
    fw_flux=fw_flux,
    # Pre-computed forcing (for comparison)
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    # No validate_forcing flag needed - automatically detected!
)

# Output includes computed values for inspection:
print(f"ustar: MITgcm={ustar} vs Python={output.ustar_computed}")
print(f"bo: MITgcm={bo} vs Python={output.bo_computed}")
print(f"bosol: MITgcm={bosol} vs Python={output.bosol_computed}")
```

---

## Error Handling

### Partial Pre-computed Forcing

```python
compute_mixing(..., ustar_forcing=ustar, bo_forcing=None, bosol_forcing=None)
```

**Error**:
```
ValueError: Incomplete pre-computed forcing provided.
Must provide ALL THREE of: ustar_forcing, bo_forcing, bosol_forcing
Got: ustar_forcing=True, bo_forcing=False, bosol_forcing=False
```

### Partial Raw Fluxes

```python
compute_mixing(..., tau_x=tau_x, tau_y=tau_y, q_net=None, q_sw=None, fw_flux=None)
```

**Error**:
```
ValueError: Incomplete surface forcing provided.
Must provide one of:
  1. ALL FIVE raw fluxes: tau_x, tau_y, q_net, q_sw, fw_flux
  2. ALL THREE pre-computed: ustar_forcing, bo_forcing, bosol_forcing
  3. ALL EIGHT (both sets above for forcing validation)

Got raw fluxes: tau_x=True, tau_y=True, q_net=False, q_sw=False, fw_flux=False
Got pre-computed: ustar_forcing=False, bo_forcing=False, bosol_forcing=False
```

### No Forcing Provided

```python
compute_mixing(..., all forcing params = None)
```

**Error**:
```
ValueError: No forcing provided.
Must provide one of:
  1. ALL FIVE raw fluxes: tau_x, tau_y, q_net, q_sw, fw_flux
  2. ALL THREE pre-computed: ustar_forcing, bo_forcing, bosol_forcing
  3. ALL EIGHT (both sets above for forcing validation)
```

---

## Validation Success Criteria

When Mode 3 (forcing validation) is active:

**Tolerance**: 1% relative error for each term

**Success**: All three terms within tolerance
- `|ustar_python - ustar_mitgcm| / ustar_mitgcm < 0.01`
- `|bo_python - bo_mitgcm| / bo_mitgcm < 0.01`
- `|bosol_python - bosol_mitgcm| / bosol_mitgcm < 0.01`

**Failure**: Any term exceeds tolerance
```
ValueError: Forcing computation validation FAILED (tolerance: 1%):
bo: Python=5.123456e-08, MITgcm=5.234567e-08, rel_err=2.1e-02

The Python _compute_surface_forcing does not match MITgcm's
kpp_forcing_surf.F within 1% relative error tolerance.
This indicates a potential issue in the forcing computation port.
```

---

## Benefits of Simplified API

### Before (with validate_forcing flag):

```python
# Confusing: need to set flag explicitly
compute_mixing(
    ...,
    tau_x=0.0, tau_y=0.0, q_net=0.0, q_sw=0.0, fw_flux=0.0,  # zeros? really?
    ustar_forcing=ustar, bo_forcing=bo, bosol_forcing=bosol,
    validate_forcing=False  # Must remember to set this
)

# Error prone: easy to forget flag
compute_mixing(
    ...,
    tau_x=tau_x, tau_y=tau_y, q_net=q_net, q_sw=q_sw, fw_flux=fw_flux,
    ustar_forcing=ustar, bo_forcing=bo, bosol_forcing=bosol,
    # Forgot validate_forcing=True → error!
)
```

### After (automatic detection):

```python
# Clear: just provide what you have
compute_mixing(
    ...,
    # tau_x, tau_y, etc. = None (not provided)
    ustar_forcing=ustar, bo_forcing=bo, bosol_forcing=bosol
    # Mode 1 automatically
)

# Intuitive: provide everything = validate everything
compute_mixing(
    ...,
    tau_x=tau_x, tau_y=tau_y, q_net=q_net, q_sw=q_sw, fw_flux=fw_flux,
    ustar_forcing=ustar, bo_forcing=bo, bosol_forcing=bosol
    # Mode 3 automatically - no flag needed!
)
```

---

## Default Values

All surface forcing parameters default to `None`:

```python
def compute_mixing(
    self,
    theta: np.ndarray,
    salt: np.ndarray,
    u_vel: np.ndarray,
    v_vel: np.ndarray,
    depth: np.ndarray,
    cell_thickness: np.ndarray,
    tau_x: float = None,         # ← None, not 0.0
    tau_y: float = None,         # ← None, not 0.0
    q_net: float = None,         # ← None, not 0.0
    q_sw: float = None,          # ← None, not 0.0
    fw_flux: float = None,       # ← None, not 0.0
    coriol: float = 1.0e-4,
    background_visc: float = 1.0e-4,
    background_diff_s: float = 1.0e-5,
    background_diff_t: float = 1.0e-5,
    ustar_forcing: float = None,
    bo_forcing: float = None,
    bosol_forcing: float = None,
) -> KPPOutput:
```

**Why None?**: Explicitly means "not provided" (vs 0.0 which is ambiguous)

---

## Files Modified

| File | Changes | Purpose |
|------|---------|---------|
| `kpp_core_driver.py` | Removed `validate_forcing` param, added auto-detection logic | Simplify API |
| `run_kpp_from_netcdf_input.py` | Removed `validate_forcing_enabled` variable | Auto-detection handles it |

---

## Backwards Compatibility

**Scripts using pre-computed forcing only**: ✅ No changes needed
- Just don't provide raw fluxes → Mode 1 automatically

**Scripts with raw fluxes in NetCDF**: ✅ Automatic
- Both present → Mode 3 automatic validation
- Only pre-computed → Mode 1 (old behavior)

---

## Testing Checklist

- [x] Mode 1: Pre-computed only → works
- [x] Mode 2: Raw fluxes only → works
- [x] Mode 3: Both provided → validates automatically
- [x] Partial pre-computed → clear error
- [x] Partial raw fluxes → clear error
- [x] No forcing → clear error
- [x] All error messages descriptive
- [x] None defaults work correctly
- [x] Validation tolerance at 1%
- [x] Computed forcing in output NetCDF

---

## User Experience

**Old way** (explicit flag):
```python
# User thinks: "Do I need validation? What flag do I set?"
# Easy to forget or set wrong
```

**New way** (automatic):
```python
# User thinks: "I have all 8 values" → provides all 8
# Validation happens automatically - no flag to remember!
```

**Result**: Simpler mental model, fewer errors, clearer intent

---

## Summary

✅ **API simplified**: No more `validate_forcing` flag  
✅ **Mode auto-detected**: Based on which parameters provided  
✅ **Clear errors**: Explicit about what's needed  
✅ **Better defaults**: None instead of 0.0  
✅ **Same validation**: 1% tolerance, detailed diagnostics  
✅ **Output includes**: Computed forcing for inspection

The API now follows the principle: **"Make the common case simple, and impossible states impossible."**
