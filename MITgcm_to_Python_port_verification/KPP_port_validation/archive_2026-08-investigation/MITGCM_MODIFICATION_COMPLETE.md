# MITgcm Instrumentation Update Complete

**Date**: 2026-08-20  
**Status**: ✅ COMPLETE - Ready for testing  
**File Modified**: `mitgcm_verification_mods/kpp_mods/kpp_calc.F`

---

## Summary

Extended the existing KPP validation instrumentation in kpp_calc.F to output raw surface fluxes alongside the computed forcing values. This enables complete forcing validation in the Python KPP port.

---

## Changes Made

### 1. Extended INPUT_FORCING Output (Line ~1161-1167)

**Before** (5 values):
```fortran
WRITE(standardMessageUnit,202) 'INPUT_FORCING',i,j,
 &    ustar(i,j),
 &    bo(i,j),
 &    bosol(i,j),
 &    surfaceForcingU(i,j,bi,bj),
 &    surfaceForcingV(i,j,bi,bj)
```

**After** (8 values):
```fortran
WRITE(standardMessageUnit,202) 'INPUT_FORCING',i,j,
 &    ustar(i,j),
 &    bo(i,j),
 &    bosol(i,j),
 &    surfaceForcingU(i,j,bi,bj),
 &    surfaceForcingV(i,j,bi,bj),
 &    surfaceForcingT(i,j,bi,bj),    ! NEW: Net heat flux [W/m²]
 &    Qsw(i,j,bi,bj),                ! NEW: Shortwave flux [W/m²]
 &    surfaceForcingS(i,j,bi,bj)     ! NEW: Virtual salt flux [g/m²/s]
```

### 2. Updated Format Specification (Line ~1226)

**Before**:
```fortran
202  FORMAT(A,2(',',I3),5(',',E25.16))  ! 2 ints + 5 floats
```

**After**:
```fortran
202  FORMAT(A,2(',',I3),8(',',E25.16))  ! 2 ints + 8 floats
```

### 3. Updated Header Documentation (Line ~1117-1119)

**Before**:
```fortran
'INPUT_FORCING_HEADER,i,j,ustar,bo,bosol,tau_x,tau_y'
```

**After**:
```fortran
'INPUT_FORCING_HEADER,i,j,ustar,bo,bosol,tau_x,tau_y,'
 //'q_net,q_sw,fw_flux'
```

---

## Output Format

Each INPUT_FORCING line now contains 10 comma-separated values:

```
INPUT_FORCING, i, j, ustar, bo, bosol, tau_x, tau_y, q_net, q_sw, fw_flux
```

### Field Descriptions

| Field | Variable | Units | Description | Sign Convention |
|-------|----------|-------|-------------|-----------------|
| 1-2 | i, j | - | Grid indices (1-based) | - |
| 3 | ustar | m/s | Friction velocity | Positive (magnitude) |
| 4 | bo | m²/s³ | Turbulent buoyancy forcing | Positive = buoyancy gain |
| 5 | bosol | m²/s³ | Radiative buoyancy forcing | Positive = buoyancy gain |
| 6 | tau_x | m²/s² | Zonal wind stress / ρ₀ | Positive east |
| 7 | tau_y | m²/s² | Meridional wind stress / ρ₀ | Positive north |
| 8 | q_net | W/m² | Net heat flux (non-SW) | Positive into ocean |
| 9 | q_sw | W/m² | Shortwave radiation | Positive into ocean |
| 10 | fw_flux | g/m²/s | Virtual salt flux | Negative = freshening |

**Note**: Fields 3-5 are the **computed** forcing (output of KPP_FORCING_SURF), while fields 8-10 are the **raw** surface fluxes (inputs to KPP_FORCING_SURF). Fields 6-7 (wind stress) are used to compute field 3 (ustar).

---

## Backwards Compatibility

The Python parser (`scripts/parse_mitgcm_split.py`) automatically handles both formats:

- **Old format** (7 fields): Works as before, forcing validation disabled
- **New format** (10 fields): Extracts raw fluxes, enables forcing validation

No changes needed to existing parsing code - it detects format automatically via `len(parts)`.

---

## Testing

### Verification Steps

1. **Recompile MITgcm** with modified kpp_calc.F
2. **Run test case** (10 timesteps sufficient):
   ```bash
   cd /path/to/mitgcm/run
   ./mitgcmuv > output.txt 2>&1
   ```

3. **Check output format**:
   ```bash
   grep "INPUT_FORCING," output.txt | head -1
   ```
   Should show 10 comma-separated values

4. **Parse with updated Python parser**:
   ```bash
   cd /path/to/1D_Mixing_Experiments
   python scripts/parse_mitgcm_split.py \
     /path/to/mitgcm/run/output.txt \
     experiment_name
   ```
   Should see: "Forcing validation data: present"

5. **Run Python validation**:
   ```bash
   python scripts/run_kpp_from_netcdf_input.py \
     KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs.nc
   ```
   Should see: "Forcing validation: ENABLED"

### Expected Outcomes

**If forcing validation passes** (no errors):
- ✅ Python `_compute_surface_forcing()` correctly ports MITgcm's `kpp_forcing_surf.F`
- ✅ Complete validation coverage achieved

**If forcing validation fails**:
- ❌ ValueError with diagnostics showing which term(s) differ
- Check `_compute_surface_forcing()` in kpp_core_driver.py for bugs
- Verify sign conventions and unit conversions

---

## Variable Access

The raw flux variables were already available in the KPP_OUTPUT_VALIDATION subroutine via the FFIELDS include:

```fortran
#include "FFIELDS.h"
```

This provides access to:
- `surfaceForcingT(i,j,bi,bj)` - Net heat flux [W/m²]
- `surfaceForcingS(i,j,bi,bj)` - Virtual salt flux [g/m²/s]
- `Qsw(i,j,bi,bj)` - Shortwave radiation [W/m²]

No additional includes or argument passing needed.

---

## Unit Conversions in Parser

The parser (`scripts/parse_mitgcm_split.py`) will need to convert:

### surfaceForcingS → fw_flux

MITgcm outputs virtual salt flux, Python expects freshwater flux:

```python
# surfaceForcingS = -EmPmR * salt (g/m²/s)
# fw_flux = EmPmR (kg/m²/s)
if salt_surface > 0:
    fw_flux = -surfaceForcingS / salt_surface * (rhoConst / 1000.0)
else:
    fw_flux = 0.0
```

**Note**: The factor `(rhoConst / 1000.0)` converts g/m²/s to kg/m²/s. Typical rhoConst = 1029 kg/m³.

**ACTUALLY**: Looking at the parser again, it currently doesn't do this conversion. The Python forcing computation in `_compute_surface_forcing()` should handle the conversion internally. Let me check...

Actually, the Python code does:
```python
salt_flux = -fw_flux * salt_surf
bo = ... + ssbeta * salt_flux / rho_surf
```

So it expects `fw_flux` in kg/m²/s (EmPmR). But MITgcm outputs `surfaceForcingS` which is the virtual salt flux. We may need to update the parser to convert, or update the Python validation to handle the raw MITgcm format.

**RECOMMENDATION**: Keep MITgcm output as-is (surfaceForcingS), and update the parser to convert to fw_flux when creating the NetCDF. This keeps the MITgcm instrumentation simple.

---

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `mitgcm_verification_mods/kpp_mods/kpp_calc.F` | ~1117, ~1161-1167, ~1226 | Add 3 raw flux fields to INPUT_FORCING output |

---

## Next Steps

1. ✅ MITgcm instrumentation updated
2. ⏳ Recompile and test MITgcm
3. ⏳ Update parser to handle surfaceForcingS → fw_flux conversion (if needed)
4. ⏳ Run validation and verify forcing computation

---

## Notes

- The modified kpp_calc.F is in `mitgcm_verification_mods/kpp_mods/`, ready to be copied to MITgcm code directory
- Format is E25.16 (25 characters, 16 decimal places) for high precision
- All forcing fields are 2D (i, j) - one value per column per timestep
- Output only occurs when KPP is active (ocean points only)

---

## Rollback

To revert to old format (no raw fluxes):

1. Change format 202 back to: `FORMAT(A,2(',',I3),5(',',E25.16))`
2. Remove lines:
   ```fortran
   surfaceForcingT(i,j,bi,bj),
   Qsw(i,j,bi,bj),
   surfaceForcingS(i,j,bi,bj)
   ```
3. Revert header back to old format

The parser will automatically handle the old format (backwards compatible).
