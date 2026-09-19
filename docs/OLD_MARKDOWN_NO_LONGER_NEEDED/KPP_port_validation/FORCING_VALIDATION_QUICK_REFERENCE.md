# Forcing Validation Quick Reference

**Status**: Python ready, needs MITgcm instrumentation

---

## What This Validates

✅ **Python `_compute_surface_forcing()` matches MITgcm `kpp_forcing_surf.F`**

Validates conversion of:
- Wind stress → friction velocity (ustar)
- Heat fluxes + freshwater flux → buoyancy forcing (bo)
- Shortwave radiation → radiative forcing (bosol)

---

## MITgcm Modification (One Line!)

**File**: `pkg/kpp/kpp_calc.F`

**Find**:
```fortran
WRITE(6,'(A,2I4,5E16.8)') 'INPUT_FORCING,',
 &   i, j, ustar, bo, bosol, tau_x, tau_y
```

**Replace with**:
```fortran
WRITE(6,'(A,2I4,8E16.8)') 'INPUT_FORCING,',
 &   i, j, ustar, bo, bosol, tau_x, tau_y,
 &   q_net, q_sw, fw_flux
```

(Adjust variable names as needed - see `MITGCM_INSTRUMENTATION_FORCING.md`)

---

## Python Side (Already Done!)

✅ Parser handles extended format (backwards compatible)  
✅ Validation script auto-detects raw fluxes  
✅ Driver validates forcing before mixing computation  
✅ Documentation complete

---

## How to Use

### Option 1: Mixing Validation Only (Current)

**Use existing datasets** (no raw fluxes):
```bash
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs.nc
```
→ Output: "Forcing validation: DISABLED"

### Option 2: Complete Validation (After MITgcm Update)

**After modifying MITgcm**:
1. Re-run MITgcm (10 timesteps sufficient)
2. Parse: `python scripts/parse_mitgcm_split.py output.txt experiment_name`
3. Validate: `python scripts/run_kpp_from_netcdf_input.py inputs.nc`

→ Output: "Forcing validation: ENABLED"

---

## Expected Results

### If Forcing Validation Passes

```
Forcing validation: ENABLED (raw fluxes present)
  -> Will validate Python forcing computation against MITgcm
Processing 11000 columns...
[100%] Completed
```

✅ Python forcing computation is correct!

### If Forcing Validation Fails

```
ValueError: Forcing computation validation FAILED:
bo: Python=5.123456e-08, MITgcm=5.234567e-08, rel_err=2.1e-02

The Python _compute_surface_forcing does not match MITgcm's
kpp_forcing_surf.F within tolerance (rtol=1e-12).
```

❌ Bug in Python forcing computation - check `_compute_surface_forcing()` in kpp_core_driver.py

---

## Quick Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Forcing validation: DISABLED" | No raw fluxes in NetCDF | Update MITgcm instrumentation |
| "list index out of range" | Wrong number of fields | Check WRITE format in kpp_calc.F |
| ValueError with large rel_err | Sign or unit mismatch | Check sign conventions in MITGCM_INSTRUMENTATION_FORCING.md |
| All raw fluxes are zero | Variables not found | Check variable names in kpp_calc.F |

---

## Documentation

- **Implementation**: `IMPLEMENTATION_SUMMARY_FORCING_VALIDATION.md`
- **MITgcm guide**: `MITGCM_INSTRUMENTATION_FORCING.md`
- **Full details**: `FORCING_VALIDATION.md`
- **NetCDF format**: `NETCDF_DATA_FORMAT.md` (optional fields section)

---

## Summary

**Effort**: 30 minutes to modify MITgcm  
**Benefit**: Complete validation of forcing computation  
**Status**: Python ready, MITgcm pending
