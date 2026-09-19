# KPP Forcing Computation Validation

**Date**: 2026-08-20  
**Status**: Implemented, ready for testing

---

## Overview

The Python KPP port includes two-tier validation:

1. **Mixing Scheme Validation** (primary, always active): Validates that Python KPP produces the same mixing coefficients as MITgcm when given the same inputs and forcing
2. **Forcing Computation Validation** (optional, new): Validates that Python `_compute_surface_forcing()` computes the same `ustar`, `bo`, `bosol` as MITgcm's `kpp_forcing_surf.F` when given raw surface fluxes

---

## Why Separate Validation?

**Separation of concerns**: When validating a complex physics module, it's critical to isolate what's being tested:

- **Mixing scheme**: Richardson number calculations, boundary layer depth, diffusivity profiles, nonlocal transport
- **Forcing computation**: Conversion of raw fluxes (wind stress, heat flux, freshwater flux) to derived forcing terms (friction velocity, buoyancy forcing)

By validating these independently:
- **Faster debugging**: If results differ, we know exactly where the bug is
- **Bit-level validation**: Mixing validation can achieve machine precision because we eliminate forcing computation as a variable
- **Complete coverage**: Both components are tested against MITgcm reference

---

## Implementation

### Core Logic (kpp_core_driver.py)

Added `validate_forcing` parameter to `KPPDriver.compute_mixing()`:

```python
def compute_mixing(
    self,
    # ... state variables ...
    tau_x: float,
    tau_y: float,
    q_net: float,
    q_sw: float = 0.0,
    fw_flux: float = 0.0,
    # ... other params ...
    ustar_forcing: float = None,
    bo_forcing: float = None,
    bosol_forcing: float = None,
    validate_forcing: bool = False,  # NEW
) -> KPPOutput:
```

**When `validate_forcing=True` and both pre-computed forcing AND raw fluxes are provided**:

1. Compute forcing from fluxes: `ustar_computed, bo_computed, bosol_computed = _compute_surface_forcing(...)`
2. Compare against MITgcm values: `_validate_forcing_computation(ustar_mitgcm, bo_mitgcm, bosol_mitgcm, ustar_computed, bo_computed, bosol_computed)`
3. If mismatch > tolerance: raise `ValueError` with diagnostic info
4. If validation passes: use pre-computed MITgcm forcing for mixing calculation

### Validation Method

```python
def _validate_forcing_computation(
    self,
    ustar_mitgcm, bo_mitgcm, bosol_mitgcm,
    ustar_python, bo_python, bosol_python,
) -> None:
    """
    Validate Python forcing computation matches MITgcm.
    
    Tolerance: rtol=1e-12, atol=1e-16
    Raises: ValueError if any term differs beyond tolerance
    """
```

**Tolerance rationale**: Looser than mixing validation (1e-12 vs 1e-14) because floating-point operation order can differ between Fortran and Python, especially for multi-step computations involving thermal expansion, haline contraction, and flux conversions.

### Validation Script (run_kpp_from_netcdf_input.py)

Automatically detects when raw flux variables are present:

```python
# Read pre-computed forcing (always required)
ustar = float(inputs_ds.ustar.isel(time=t_idx, x=i, y=j).values)
bo = float(inputs_ds.bo.isel(time=t_idx, x=i, y=j).values)
bosol = float(inputs_ds.bosol.isel(time=t_idx, x=i, y=j).values)

# Check for optional raw fluxes
if 'q_net' in inputs_ds and 'q_sw' in inputs_ds and 'fw_flux' in inputs_ds:
    q_net_val = float(inputs_ds.q_net.isel(...).values)
    q_sw_val = float(inputs_ds.q_sw.isel(...).values)
    fw_flux_val = float(inputs_ds.fw_flux.isel(...).values)
    validate_forcing_enabled = True
else:
    # Use zeros (forcing computation will be bypassed)
    q_net_val = 0.0
    q_sw_val = 0.0
    fw_flux_val = 0.0
    validate_forcing_enabled = False

# Run KPP with validation
output = driver.compute_mixing(
    ...,
    q_net=q_net_val,
    q_sw=q_sw_val,
    fw_flux=fw_flux_val,
    ustar_forcing=ustar,
    bo_forcing=bo,
    bosol_forcing=bosol,
    validate_forcing=validate_forcing_enabled  # Enable if raw fluxes present
)
```

**Backwards compatible**: Existing validation datasets without raw fluxes will work unchanged (forcing validation is skipped, mixing validation proceeds as before).

---

## NetCDF Format Extension

### Required Fields (unchanged)

Pre-computed forcing from MITgcm's `kpp_forcing_surf.F`:
- `ustar(time, x, y)` - Friction velocity [m/s]
- `bo(time, x, y)` - Turbulent buoyancy forcing [m²/s³]
- `bosol(time, x, y)` - Radiative buoyancy forcing [m²/s³]
- `tau_x(time, x, y)` - Zonal wind stress / ρ₀ [m²/s²]
- `tau_y(time, x, y)` - Meridional wind stress / ρ₀ [m²/s²]

### Optional Fields (new, for forcing validation)

Raw surface fluxes that MITgcm used to compute the forcing terms:
- `q_net(time, x, y)` - Net surface heat flux excluding shortwave [W/m²]
- `q_sw(time, x, y)` - Surface shortwave radiation [W/m²]
- `fw_flux(time, x, y)` - Freshwater flux (E - P - R) [kg/m²/s]

**Sign conventions** (MITgcm standard):
- Heat fluxes: **Positive = into ocean** (warming/heating)
- Freshwater flux: **Positive = into ocean** (freshening, dilution)

See `NETCDF_DATA_FORMAT.md` for complete specification.

---

## MITgcm Instrumentation Modification

The raw surface fluxes are **already passed into** kpp_calc.F as arguments, so we just need to expand the existing `INPUT_FORCING` output line to include them.

### Current Output (from kpp_calc.F instrumentation)

```fortran
C     Current format (after KPP_FORCING_SURF computes derived quantities)
      WRITE(6,'(A,I8,2(A,I4),5(A,E16.8))') 
     &   'INPUT_FORCING,', i, ',', j, ',',
     &   ustar, ',', bo, ',', bosol, ',', tau_x, ',', tau_y
```

### Proposed Modification (add raw fluxes)

Simply extend the same line to include the raw fluxes that were passed to KPP_FORCING_SURF:

```fortran
C     Extended format (includes raw fluxes for validation)
      WRITE(6,'(A,I8,2(A,I4),8(A,E16.8))') 
     &   'INPUT_FORCING,', i, ',', j, ',',
     &   ustar, ',', bo, ',', bosol, ',', tau_x, ',', tau_y, ',',
     &   q_net, ',', q_sw, ',', fw_flux
```

**Where to add**: In kpp_calc.F at the point where `INPUT_FORCING` is currently written (after calling KPP_FORCING_SURF, so both computed and raw values are available).

**Variables to add** (should be available in kpp_calc.F's argument list or local variables):
- `surfaceForcingT(i,j,bi,bj)` or equivalent → `q_net` - Net heat flux [W/m²]
- `Qsw(i,j,bi,bj)` or equivalent → `q_sw` - Shortwave radiation [W/m²]  
- `surfaceForcingS(i,j,bi,bj)` or EmPmR → `fw_flux` - Freshwater flux [kg/m²/s or m/s]

**Note**: Exact variable names depend on how kpp_calc.F receives surface forcing. Check the subroutine signature and local variable declarations.

## Parser Modification

Update `scripts/parse_mitgcm_split.py` to handle the extended `INPUT_FORCING` line:

### Current Parser (line 123-129)

```python
elif tag == 'INPUT_FORCING':
    i, j = int(parts[1])-1, int(parts[2])-1
    timestep_data[current_timestep]['forcing'][(i,j)] = {
        'ustar': float(parts[3]), 'bo': float(parts[4]),
        'bosol': float(parts[5]), 'tau_x': float(parts[6]),
        'tau_y': float(parts[7])
    }
```

### Proposed Update

```python
elif tag == 'INPUT_FORCING':
    i, j = int(parts[1])-1, int(parts[2])-1
    forcing_dict = {
        'ustar': float(parts[3]), 'bo': float(parts[4]),
        'bosol': float(parts[5]), 'tau_x': float(parts[6]),
        'tau_y': float(parts[7])
    }
    # Optional: raw fluxes for forcing validation (if present)
    if len(parts) >= 11:
        forcing_dict['q_net'] = float(parts[8])
        forcing_dict['q_sw'] = float(parts[9])
        forcing_dict['fw_flux'] = float(parts[10])
    timestep_data[current_timestep]['forcing'][(i,j)] = forcing_dict
```

**Backwards compatible**: If the MITgcm output only has 7 fields (old format), parser still works. If it has 10 fields (new format), it extracts raw fluxes too.

### NetCDF Export (line 247-267, 308-320)

Add optional arrays and export if raw fluxes were captured:

```python
# Allocate arrays (add these)
q_net = np.zeros((n_time, nx, ny))
q_sw = np.zeros((n_time, nx, ny))
fw_flux = np.zeros((n_time, nx, ny))
has_raw_fluxes = False

# Populate (in column loop)
if 'q_net' in vals:
    q_net[t_idx, i, j] = vals['q_net']
    q_sw[t_idx, i, j] = vals['q_sw']
    fw_flux[t_idx, i, j] = vals['fw_flux']
    has_raw_fluxes = True

# Add to input dataset (if present)
if has_raw_fluxes:
    data_vars['q_net'] = (['time', 'x', 'y'], q_net, {
        'standard_name': 'surface_net_heat_flux',
        'long_name': 'Net surface heat flux (excluding shortwave)',
        'units': 'W/m2',
        'positive': 'into_ocean'
    })
    data_vars['q_sw'] = (['time', 'x', 'y'], q_sw, {
        'standard_name': 'surface_shortwave_flux',
        'long_name': 'Surface shortwave radiation',
        'units': 'W/m2',
        'positive': 'into_ocean'
    })
    data_vars['fw_flux'] = (['time', 'x', 'y'], fw_flux, {
        'standard_name': 'freshwater_flux',
        'long_name': 'Freshwater flux (E-P-R)',
        'units': 'kg/m2/s',
        'positive': 'into_ocean'
    })
```

---

## Testing Strategy

### Phase 1: Verify Forcing Computation (Current MITgcm Dataset)

With existing 11,000-timestep dataset:
1. Add raw flux instrumentation to MITgcm `kpp_forcing_surf.F`
2. Re-run MITgcm 1D_ocean_ice_column experiment
3. Parse new output to NetCDF with `q_net`, `q_sw`, `fw_flux` fields
4. Run `scripts/run_kpp_from_netcdf_input.py` (will auto-detect raw fluxes and enable forcing validation)
5. Verify:
   - All 11,000 timesteps pass forcing validation (no ValueError raised)
   - Log reports "Forcing validation: ENABLED" in output

**Expected result**: 100% pass rate if `_compute_surface_forcing` correctly ports MITgcm's `kpp_forcing_surf.F`.

### Phase 2: Diagnose Failures (If Any)

If forcing validation fails:
1. Review error messages (show Python vs MITgcm values, relative error)
2. Check for porting errors in `_compute_surface_forcing` (lines 334-421 in kpp_core_driver.py)
3. Verify MITgcm instrumentation captures correct variables (pre- or post-sea-ice modification?)
4. Check unit conversions in parser
5. Document any intentional differences (bug fixes) in `potential_bugs_and_inconsistencies.md`

### Phase 3: End-to-End Test

Once forcing validation passes:
1. Run Python KPP with computed forcing (NOT pre-computed): set `ustar_forcing=None`
2. Compare outputs against MITgcm mixing outputs
3. Should match within tolerance (now testing full end-to-end: forcing + mixing)

---

## Current Status

| Component | Status | File |
|-----------|--------|------|
| Core validation logic | ✅ Implemented | `1D_Mixing_Model/KPP/kpp_core_driver.py:223-246, 422-472` |
| Validation script | ✅ Implemented | `scripts/run_kpp_from_netcdf_input.py:295-320, 327-358` |
| NetCDF format spec | ✅ Documented | `KPP_port_validation/NETCDF_DATA_FORMAT.md:123-146` |
| MITgcm instrumentation | ⏳ Pending | Needs modification to `pkg/kpp/kpp_forcing_surf.F` |
| Parser update | ⏳ Pending | Needs modification to `scripts/parse_mitgcm_split.py` |
| Testing | ⏳ Pending | Awaits MITgcm re-run with flux instrumentation |

---

## References

**MITgcm Source**:
- `pkg/kpp/kpp_forcing_surf.F:191-238` - Forcing computation
- `pkg/kpp/kpp_calc.F:112-145` - Calls `KPP_FORCING_SURF`, passes forcing to `KPPMIX`

**Python Port**:
- `kpp_core_driver.py:334-421` - `_compute_surface_forcing()` method
- `kpp_core_driver.py:422-472` - `_validate_forcing_computation()` method

**Validation Docs**:
- `NETCDF_DATA_FORMAT.md` - NetCDF format specification
- `INVESTIGATION_CONCLUSION.md` - Mixing scheme validation results
- `potential_bugs_and_inconsistencies.md` - Known issues tracker

---

## Summary

The forcing validation framework is **fully implemented in Python** and ready for testing. To activate it:

1. **Short-term** (use existing implementation, no forcing validation): Continue using current workflow with pre-computed forcing only
2. **Complete validation** (validate forcing + mixing): Add MITgcm instrumentation for raw fluxes, re-run, and the Python validation script will automatically enable forcing validation

**Key benefit**: This provides **independent validation** that the Python port correctly implements **both** components of MITgcm KPP: forcing computation AND mixing physics.
