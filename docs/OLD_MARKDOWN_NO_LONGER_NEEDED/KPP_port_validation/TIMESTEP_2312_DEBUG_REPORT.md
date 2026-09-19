# Timestep 2312 Debug Report

**Date**: 2026-08-20  
**Agent**: Bob (Builder)  
**Task**: Debug timestep 2312 with corrected parameters (gravity=9.8156, rho_const=1027.0)

---

## Executive Summary

Python KPP port produces **HBL = 13.82m** while MITgcm produces **HBL = 35.12m** for timestep 2312 (0-indexed: 2311). This is a **60.7% discrepancy** (21.3m difference).

**Root Cause**: Python's bulk Richardson number (Rib) exceeds the critical value Ricr=0.3 at the **first level (k=1, 15m depth)**, causing premature termination of boundary layer growth. At k=3 (35m depth), Rib drops to 0.021, well below Ricr, indicating the boundary layer should extend deeper.

---

## Input Conditions (Timestep 2311)

### Forcing
- `ustar = 2.236e-05 m/s` - Very weak wind stress
- `bo = -3.604e-10 m²/s³` - Weak negative buoyancy forcing (cooling)
- `bosol = 1.679e-10 m²/s³` - Weak shortwave radiation
- `bfsfc = -1.925e-10 m²/s³` - Net surface buoyancy forcing
- `f = 1.000e-04 s⁻¹` - Coriolis parameter

### Water Column
Weak stratification (ΔT ≈ -0.0001°C/m) from surface to 35m, then **sharp thermocline** at 35-45m (ΔT ≈ -0.084°C/m).

```
Depth(m)   T(°C)      S(psu)
  -5.0    -1.9467    29.6518
 -15.0    -1.9459    29.6519
 -25.0    -1.9454    29.6519
 -35.0    -1.9446    29.6521
 -45.0    -1.1078    30.2166  ← Sharp thermocline
```

---

## Corrected Parameters

The following parameters were extracted from `mitgcm_kpp_inputs_11k_1D.nc` global attributes:

```
gravity       = 9.8156 m/s²       (was 9.81 in Python default)
rho_const     = 1027.0 kg/m³      (was 1029.0 in Python default)
heat_capacity = 3986.0 J/(kg·K)   (was 3994.0 in Python default)
Ricr          = 0.3
epsilon       = 0.1
vonk          = 0.4
Vtc (computed)= 5.331095
phepsi        = 1.0e-10
```

---

## Detailed Rib Calculation Results

### Level k=1 (15m depth)
```
Ritop     = 1.357080e-06    (buoyancy stratification numerator)
dvsq      = 7.030e-17       (velocity shear squared ≈ zero)
bvsq      = 1.806e-08       (buoyancy frequency squared)
ws        = 3.711e-04       (scalar turbulent velocity scale)
vtsq      = 3.988e-06       (turbulent velocity contribution)
denom     = 3.988e-06       (max(dvsq + vtsq, phepsi))
Rib       = 0.340           > Ricr = 0.3  *** STOPS HERE ***
```

### Level k=2 (25m depth)
```
Ritop     = 7.177e-06
bvsq      = 7.458e-08
ws        = 6.125e-04
vtsq      = 2.229e-05
denom     = 2.229e-05
Rib       = 0.322           > Ricr = 0.3  (barely)
```

### Level k=3 (35m depth)
```
Ritop     = 4.863e-05
bvsq      = 2.126e-04       (stronger stratification starts)
ws        = 8.540e-04
vtsq      = 2.323e-03
denom     = 2.323e-03
Rib       = 0.021           < Ricr = 0.3  *** BOUNDARY LAYER SHOULD EXTEND HERE ***
```

### Level k=4 (45m depth - strong thermocline)
```
Ritop     = 1.701e-01       (sharp jump due to thermocline)
bvsq      = 7.361e-04
ws        = 1.095e-03
vtsq      = 7.130e-03
denom     = 7.130e-03
Rib       = 23.85           >> Ricr  (expected, strong stratification)
```

---

## Key Observations

1. **Python finds kbl=1** because Rib(k=1) = 0.340 > Ricr = 0.3
2. **Interpolates between k=0 and k=1** to find HBL where Rib = Ricr exactly
3. **Result**: HBL = 13.82m ✓ (matches stored Python output exactly)

4. **At k=3 (35m)**, Rib = 0.021 << Ricr, indicating the boundary layer should extend to at least this depth
5. **MITgcm HBL = 35.12m** suggests MITgcm finds kbl ≈ 3 or 4

---

## Hypothesis: Why the Discrepancy?

The discrepancy is in the **denominator of the bulk Richardson number**:
```
Rib = Ritop / (dvsq + vtsq)
```

Since `dvsq ≈ 0` (negligible velocity shear), the key is `vtsq`:
```
vtsq = -depth * ws * sqrt(bvsq) * Vtc
```

At k=1 (15m):
- Python: `vtsq = 3.988e-06` → `Rib = 0.340` (exceeds Ricr)
- MITgcm: **presumably computes larger vtsq** → smaller Rib → deeper HBL

### Possible Root Causes

1. **wscale lookup table interpolation**: Python and MITgcm may interpolate turbulent velocity scales differently
   - Python `ws = 3.711e-04` at k=1
   - Need to verify MITgcm's `ws` value

2. **Buoyancy gradient (bvsq) calculation**: Difference in how `dbloc` is computed
   - Python `bvsq = 1.806e-08` at k=1
   - EOS formulation (JMD95) should be identical, but numerical precision matters

3. **Horizontal smoothing** (MITgcm has `smooth_dbloc=1`):
   - On a 1×1 grid, this should be a no-op
   - But implementation details might matter

4. **Numerical precision**: Weak forcing (bfsfc ≈ -1.9e-10) and weak stratification make calculations sensitive to roundoff

5. **Parameter differences we haven't found yet**: Check viscAz, diffKzS, diffKzT, etc.

---

## Verification Status

✅ **Correct parameters loaded**: gravity=9.8156, rho_const=1027.0  
✅ **Manual calculation reproduces stored Python output**: HBL = 13.816289m  
✅ **Rib formula matches MITgcm exactly**: Line-by-line comparison with kpp_routines.F  
✅ **kbl search logic matches MITgcm**: Finds first level where Rib > Ricr  

❌ **Python HBL ≠ MITgcm HBL**: 13.82m vs 35.12m (60.7% error)

---

## Next Steps (for Arch)

1. **Compare intermediate values with MITgcm debug output**:
   - Print `ws`, `bvsq`, `vtsq`, `denom`, `Rib` at each level from MITgcm
   - Check if MITgcm computes same `ws = 3.711e-04` at k=1
   - Check if MITgcm computes same `bvsq = 1.806e-08` at k=1

2. **Verify wscale lookup table**:
   - Python builds tables with `build_wscale_lookup_tables()`
   - MITgcm builds tables in `bldepth()` initialization
   - Compare table values at the exact interpolation point used for k=1

3. **Check for hidden parameter differences**:
   - Are all 64 parameters from `PARAMETER_EXPORT_SUMMARY.md` correctly mapped?
   - Check background mixing: `viscAz`, `diffKzS`, `diffKzT`

4. **Test with MITgcm debug run** (if forcing is fixed):
   - Run MITgcm with correct forcing (ustar=2.236e-05, bo=-3.604e-10)
   - Capture Rib profile at timestep 2312
   - Compare element-by-element with Python

5. **Consider the possibility that MITgcm output is wrong**:
   - From `DEBUG_PROGRESS.md`, the debug MITgcm run had **zero forcing** (ustar=0, bo=0)
   - This led to ws=0, vtsq=0, denom=phepsi=1e-10, Rib=11,773
   - The stored HBL=35.12m might be from a **different MITgcm run** with different physics

---

## Files Generated

- `/KPP_port_validation/scripts/debug_timestep_2312.py` - Comprehensive debug script
- `/KPP_port_validation/TIMESTEP_2312_DEBUG_REPORT.md` - This report

**Script Usage**:
```bash
cd /path/to/1D_Mixing_Experiments/KPP_port_validation
/Users/ifenty/miniforge3/envs/ecco/bin/python scripts/debug_timestep_2312.py
```

---

## Conclusion

The Python KPP port is **internally self-consistent** and correctly implements the bulk Richardson criterion. The discrepancy with MITgcm appears to be in the **turbulent velocity scale (ws)** or **buoyancy gradient (bvsq)** calculation, leading to a denominator that is too small (vtsq too small), causing Rib to exceed Ricr prematurely.

**Critical Next Step**: Obtain MITgcm debug output with **correct forcing** to compare `ws`, `bvsq`, and `vtsq` values element-by-element. The zero-forcing debug run from `DEBUG_PROGRESS.md` is not representative of the validation scenario.

---

**End of Report**  
Bob (Builder), 2026-08-20
