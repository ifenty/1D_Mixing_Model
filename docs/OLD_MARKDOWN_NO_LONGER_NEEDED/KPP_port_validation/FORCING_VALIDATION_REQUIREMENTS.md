# Forcing Validation Requirements - Implementation Summary

**Date**: 2026-08-20  
**Status**: ✅ Complete and tested

---

## User Requirements

As specified by user:

1. **If raw fluxes (q_net, q_sw, fw_flux) AND pre-computed forcing (ustar, bo, bosol) are BOTH provided**:
   - `validate_forcing` MUST be `True`, OR
   - Program exits with clear error telling user to pick one or the other

2. **When `validate_forcing=True`**:
   - Python computes forcing from raw fluxes using `_compute_surface_forcing()`
   - Validates against MITgcm's pre-computed values

3. **Success criteria**: 
   - Differences < 1% relative error

4. **Output**:
   - Python-computed forcing (ustar_computed, bo_computed, bosol_computed) included in output NetCDF
   - Can be used for validation reporting

---

## Implementation

### 1. Validation Logic (kpp_core_driver.py)

**Error check**:
```python
if precomputed_forcing_provided and raw_fluxes_provided and not validate_forcing:
    raise ValueError(
        "Both pre-computed forcing AND raw surface fluxes are provided, "
        "but validate_forcing=False.\n\n"
        "When both are present, you must choose one of:\n"
        "  1. Set validate_forcing=True to validate Python forcing computation\n"
        "  2. Remove raw fluxes from input to use pre-computed forcing only"
    )
```

**Tolerance**: Changed from 1e-12 to **0.01 (1%)**

```python
rtol = 0.01  # 1% relative error
atol = 1e-16  # Absolute tolerance for near-zero values
```

**Validation**:
- Compares ustar, bo, bosol (Python vs MITgcm)
- Raises ValueError if any term exceeds 1% relative error
- Error message shows exact values and relative error for each failed term

### 2. Output Storage (KPPOutput dataclass)

Added three new optional fields:
```python
@dataclass
class KPPOutput:
    # ... existing fields ...
    
    # Forcing validation (Python-computed values)
    ustar_computed: Optional[float] = None
    bo_computed: Optional[float] = None
    bosol_computed: Optional[float] = None
```

Populated when:
- `validate_forcing=True` AND raw fluxes provided, OR
- No pre-computed forcing (standalone mode)

### 3. NetCDF Export (run_kpp_from_netcdf_input.py)

Added three output arrays:
```python
ustar_computed_out = np.full((n_time, nx, ny), np.nan)
bo_computed_out = np.full((n_time, nx, ny), np.nan)
bosol_computed_out = np.full((n_time, nx, ny), np.nan)
```

Exported to output NetCDF when not all NaN:
```python
if not np.all(np.isnan(ustar_computed_out)):
    data_vars['ustar_computed'] = (['time', 'x', 'y'], ustar_computed_out, {
        'long_name': 'Python-computed friction velocity',
        'units': 'm/s',
        'comment': 'Compare with input ustar to validate forcing computation'
    })
    # ... bo_computed, bosol_computed ...
```

### 4. Key Bug Fix

**Problem**: tau_x, tau_y are always present in datasets (used for other purposes), so the check `tau_x != 0 or tau_y != 0` incorrectly flagged standard validation runs.

**Solution**: Only check q_net, q_sw, fw_flux for "raw fluxes present":
```python
raw_fluxes_provided = (
    q_net != 0.0 or q_sw != 0.0 or fw_flux != 0.0
)
# tau_x, tau_y NOT included - they're always present
```

---

## Usage

### Standard Validation (No Forcing Validation)

**Input NetCDF has**:
- Pre-computed forcing: ustar, bo, bosol ✓
- Raw fluxes: (none)

**Code**:
```python
output = driver.compute_mixing(
    ...,
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    q_net=0.0,  # Zero or absent
    q_sw=0.0,
    fw_flux=0.0,
    validate_forcing=False  # Default
)
```

**Result**: Uses pre-computed forcing, no validation error ✅

### Forcing Validation Mode

**Input NetCDF has**:
- Pre-computed forcing: ustar, bo, bosol ✓
- Raw fluxes: q_net, q_sw, fw_flux ✓

**Code**:
```python
output = driver.compute_mixing(
    ...,
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    q_net=q_net_value,
    q_sw=q_sw_value,
    fw_flux=fw_flux_value,
    validate_forcing=True  # REQUIRED
)
```

**Result**: 
- Computes forcing from raw fluxes
- Validates against MITgcm (1% tolerance)
- If pass: uses pre-computed for mixing, stores computed in output
- If fail: raises ValueError with diagnostics

**Output NetCDF includes**:
- `ustar_computed` - Python-computed from tau_x, tau_y
- `bo_computed` - Python-computed from q_net, fw_flux
- `bosol_computed` - Python-computed from q_sw

### Error Case: Both Provided, No Validation

**Input NetCDF has**:
- Pre-computed forcing: ustar, bo, bosol ✓
- Raw fluxes: q_net, q_sw, fw_flux ✓

**Code**:
```python
output = driver.compute_mixing(
    ...,
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    q_net=q_net_value,
    q_sw=q_sw_value,
    fw_flux=fw_flux_value,
    validate_forcing=False  # ❌ ERROR
)
```

**Result**: 
```
ValueError: Both pre-computed forcing AND raw surface fluxes are provided,
but validate_forcing=False.

When both are present, you must choose one of:
  1. Set validate_forcing=True to validate Python forcing computation
  2. Remove raw fluxes from input to use pre-computed forcing only
```

---

## Validation Report Generation

After running with forcing validation, you can generate a validation report showing:

1. **Mixing validation** (existing):
   - Python KPP outputs vs MITgcm outputs
   - HBL, diffusivities, nonlocal transport

2. **Forcing validation** (new):
   - Compare input `ustar` vs output `ustar_computed`
   - Compare input `bo` vs output `bo_computed`
   - Compare input `bosol` vs output `bosol_computed`
   - Report statistics: max error, mean error, % passing

Example analysis:
```python
import xarray as xr

# Load outputs
ds_out = xr.open_dataset('outputs_from_python/mitgcm_kpp_inputs_python.nc')
ds_in = xr.open_dataset('inputs_from_mitgcm/mitgcm_kpp_inputs.nc')

# Compute forcing validation statistics
if 'ustar_computed' in ds_out:
    ustar_err = np.abs(ds_out.ustar_computed - ds_in.ustar) / ds_in.ustar
    print(f"ustar: max_err={ustar_err.max().values:.2%}, "
          f"mean_err={ustar_err.mean().values:.2%}")
    
    bo_err = np.abs(ds_out.bo_computed - ds_in.bo) / np.abs(ds_in.bo)
    print(f"bo: max_err={bo_err.max().values:.2%}, "
          f"mean_err={bo_err.mean().values:.2%}")
```

---

## Testing Checklist

- [x] Error raised when both provided and validate_forcing=False
- [x] No error when only pre-computed forcing provided
- [x] No error when only raw fluxes provided (standalone mode)
- [x] Validation runs when both provided and validate_forcing=True
- [x] Computed forcing stored in output NetCDF
- [x] Tolerance set to 1% (0.01)
- [x] Clear error messages with actionable guidance
- [x] tau_x, tau_y don't trigger "raw fluxes" check

---

## Success Criteria Met

✅ **Requirement 1**: Program exits with error if both provided without validation  
✅ **Requirement 2**: Validation runs when validate_forcing=True  
✅ **Requirement 3**: Success threshold = 1% relative error  
✅ **Requirement 4**: Python-computed forcing in output NetCDF

---

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `kpp_core_driver.py` | 40-69, 213-277, 365-378, 455-498 | Add validation logic, output fields, 1% tolerance |
| `run_kpp_from_netcdf_input.py` | 286-295, 379-390, 436-460 | Store and export computed forcing |

---

## Example Error Messages

### Success (1% pass):
```
(no error - validation passes silently)
Output includes ustar_computed, bo_computed, bosol_computed
```

### Failure (>1% error):
```
ValueError: Forcing computation validation FAILED (tolerance: 1%):
bo: Python=5.123456e-08, MITgcm=5.234567e-08, rel_err=2.1e-02

The Python _compute_surface_forcing does not match MITgcm's
kpp_forcing_surf.F within 1% relative error tolerance.
This indicates a potential issue in the forcing computation port.
```

### Missing validation flag:
```
ValueError: Both pre-computed forcing AND raw surface fluxes are provided,
but validate_forcing=False.

When both are present, you must choose one of:
  1. Set validate_forcing=True to validate Python forcing computation
     (Python will compute forcing from raw fluxes and compare to MITgcm values)
  2. Remove raw fluxes (q_net, q_sw, fw_flux) from input to use pre-computed forcing only

Pre-computed forcing present: ustar, bo, bosol
Raw fluxes present: q_net, q_sw, fw_flux
```

---

## Summary

The implementation exactly meets all user requirements:
1. Enforces either validation=True or single forcing source
2. Validates with 1% tolerance
3. Stores Python-computed forcing in output for inspection
4. Provides clear error messages and diagnostics

Ready for testing with MITgcm data that includes raw surface fluxes!
