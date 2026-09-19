# MITgcm Instrumentation for Forcing Validation

**Date**: 2026-08-20  
**Purpose**: Add raw surface flux output to enable forcing computation validation  
**File to modify**: `MITgcm/pkg/kpp/kpp_calc.F`

---

## Overview

The Python KPP port validation currently validates the mixing scheme (diffusivity computation) but **not** the forcing computation (conversion of raw fluxes to ustar, bo, bosol). To complete validation coverage, we need MITgcm to output the raw surface fluxes alongside the computed forcing terms.

## Current Instrumentation

The existing validation instrumentation in `kpp_calc.F` outputs:

```fortran
C     Format: INPUT_FORCING, i, j, ustar, bo, bosol, tau_x, tau_y
      WRITE(6,'(A,2I4,5E16.8)') 'INPUT_FORCING,',
     &     i, j, ustar(i,j), bo(i,j), bosol(i,j), 
     &     tau_x(i,j), tau_y(i,j)
```

This provides the **computed** forcing values but not the raw fluxes used to compute them.

## Required Modification

Extend the `INPUT_FORCING` line to include 3 additional fields: raw heat fluxes and freshwater flux.

### Extended Format

```fortran
C     Extended format: INPUT_FORCING, i, j, ustar, bo, bosol, tau_x, tau_y, q_net, q_sw, fw_flux
      WRITE(6,'(A,2I4,8E16.8)') 'INPUT_FORCING,',
     &     i, j, 
     &     ustar(i,j), bo(i,j), bosol(i,j), 
     &     tau_x(i,j), tau_y(i,j),
     &     q_net_local, q_sw_local, fw_flux_local
```

**Key change**: Added 3 values at the end (8 total floats instead of 5).

## Variable Identification

The exact variable names depend on how `kpp_calc.F` receives surface forcing. Typical candidates:

### Heat Fluxes

**q_net** (net non-shortwave heat flux):
- Likely: `surfaceForcingT(i,j,bi,bj)` or `Qnet(i,j,bi,bj)`
- Units: W/m² (positive = into ocean = warming)
- Note: If `SHORTWAVE_HEATING` is enabled, this should be the **non-shortwave** component only

**q_sw** (shortwave radiation):
- Likely: `Qsw(i,j,bi,bj)` 
- Units: W/m² (positive = into ocean = heating)
- Note: Only non-zero if `SHORTWAVE_HEATING` is compiled in

### Freshwater Flux

**fw_flux** (E - P - R):
- Likely: `EmPmR(i,j,bi,bj)` or `surfaceForcingS(i,j,bi,bj)`
- Units: Check if m/s (need to multiply by rhoConst) or kg/m²/s (use directly)
- Sign: Positive = into ocean = freshening

### Wind Stress (already output)

- `tau_x`, `tau_y` already included, should be pre-divided by ρ₀
- Units: m²/s² (not N/m²)

## Implementation Steps

1. **Locate the `INPUT_FORCING` write statement** in `kpp_calc.F`
   - Should be after the call to `KPP_FORCING_SURF` (which computes ustar, bo, bosol)
   - Likely in the main i,j loop over horizontal grid points

2. **Identify the raw flux variables** available at that point
   - Check subroutine arguments and USE statements
   - Verify units (W/m² for heat, kg/m²/s or m/s for freshwater)

3. **Add local variables** if needed to store the right values:
   ```fortran
   _RL q_net_local, q_sw_local, fw_flux_local
   ```

4. **Assign values** (example, adjust variable names as needed):
   ```fortran
   q_net_local = surfaceForcingT(i,j,bi,bj)
   q_sw_local = Qsw(i,j,bi,bj)
   fw_flux_local = EmPmR(i,j,bi,bj) * rhoConst  ! If EmPmR is m/s, convert to kg/m²/s
   ```

5. **Update WRITE statement** to output 8 floats instead of 5

6. **Compile and test** on a short run (10 timesteps sufficient)

## Verification

After implementing:

1. **Check output.txt format**:
   ```
   INPUT_FORCING,   1,   1,  1.234567E-02,  5.678901E-08, -3.456789E-09,  2.345678E-05,  1.234567E-05,  1.500000E+02, -2.000000E+02,  3.000000E-06
   ```
   Should have 10 comma-separated values (tag, 2 ints, 8 floats)

2. **Physical sanity checks**:
   - q_net: typically -200 to +300 W/m² (negative = ocean heating)
   - q_sw: 0 to 1000 W/m² (positive)
   - fw_flux: typically -1e-5 to +1e-5 kg/m²/s (positive = freshening)

3. **Parse with updated parser**:
   ```bash
   cd /path/to/mitgcm/run
   python /path/to/scripts/parse_mitgcm_split.py output.txt lab_sea
   ```
   Should see: "Forcing validation data: present"

4. **Run Python validation**:
   ```bash
   python scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs.nc
   ```
   Should see: "Forcing validation: ENABLED"

5. **Check for errors**:
   - If forcing validation fails, error message will show Python vs MITgcm values
   - Typical issues: wrong sign convention, wrong units, missing unit conversion

## Sign Convention Reference

MITgcm uses these conventions (verify in your version):

| Flux | Positive Direction | Physical Meaning |
|------|-------------------|------------------|
| Heat flux (q_net, q_sw) | Into ocean | Ocean warming/heating |
| Freshwater flux (fw_flux) | Into ocean | Ocean freshening (dilution) |
| Wind stress (tau_x, tau_y) | Along coordinate axis | Momentum transfer |

**Buoyancy forcing sign**:
- bo > 0: Buoyancy **gain** = dense water formation = convection (cooling, evaporation)
- bo < 0: Buoyancy **loss** = light water formation = stratification (heating, precipitation)

Note the **sign flip**: positive heat flux (warming) gives **negative** buoyancy forcing (stabilizing).

## Example: Lab_sea Configuration

For `verification/lab_sea/`, the variables are likely:

```fortran
C     In kpp_calc.F, after calling KPP_FORCING_SURF:
      q_net_local = surfaceForcingT(i,j,bi,bj)  ! From thermodynamics_do
      q_sw_local = Qsw(i,j,bi,bj)                ! From shortwave package
      fw_flux_local = EmPmR(i,j,bi,bj) * rhoConst  ! From seaice/ocean coupling

      WRITE(6,'(A,2I4,8E16.8)') 'INPUT_FORCING,',
     &     i, j,
     &     uStar(i,j,bi,bj), 
     &     Bo(i,j,bi,bj), 
     &     BoSol(i,j,bi,bj),
     &     fu(i,j,bi,bj) / rhoConst,  ! tau_x (if fu not pre-divided)
     &     fv(i,j,bi,bj) / rhoConst,  ! tau_y
     &     q_net_local,
     &     q_sw_local,
     &     fw_flux_local
```

**Note**: This is a template - actual variable names depend on MITgcm version and configuration.

## Troubleshooting

### Parser fails with "list index out of range"

**Cause**: MITgcm output has wrong number of fields.

**Solution**: Check WRITE format in kpp_calc.F matches expectation (2 ints, 8 floats).

### Forcing validation raises ValueError

**Cause**: Python computed forcing doesn't match MITgcm.

**Solutions**:
1. Check sign conventions match
2. Verify unit conversions (especially freshwater flux)
3. Ensure `q_net` excludes shortwave when `SHORTWAVE_HEATING` is on
4. Check that `_compute_surface_forcing` uses same thermal expansion / haline contraction as MITgcm

### All raw fluxes are zero

**Cause**: Variables not correctly identified or sea ice covering all points.

**Solutions**:
1. Check variable names in kpp_calc.F
2. Verify timestep has open water (no ice cover)
3. Add debug WRITE statements to confirm values before output

---

## Summary

**Change required**: Add 3 values to existing `INPUT_FORCING` output line in `kpp_calc.F`

**Effort**: ~30 minutes (identify variables, modify WRITE, test)

**Benefit**: Complete validation coverage of Python KPP port (forcing computation + mixing scheme)

**Backwards compatible**: Updated parser handles both old (7 fields) and new (10 fields) formats automatically.
