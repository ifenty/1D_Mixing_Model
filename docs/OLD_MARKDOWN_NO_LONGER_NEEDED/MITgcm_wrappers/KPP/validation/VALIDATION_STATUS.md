# KPP Validation Framework - Status Report

## ✅ What Works

### 1. Export Script (`run_kpp_and_export.py`)
- **Status**: ✅ Working
- **Functionality**:
  - Loads YAML configuration files (initial conditions, forcing, physical parameters)
  - Runs Python KPP port with `KPPDriver.compute_mixing()`
  - Exports inputs and outputs in both numpy (.npz) and binary formats
  - Generates human-readable README with test case summary

**Test Run Results**:
```
Nr = 12 levels
Depth = 140.0 m
KPPhbl = 14.77 m (boundary layer depth from Python port)
Max KPPviscAz = 2.86e-01 m²/s (Python port produces non-zero mixing!)
```

### 2. MITgcm Wrapper
- **Status**: ✅ Compiles and runs
- **Functionality**:
  - Reads binary input correctly
  - Initializes grid geometry
  - Calls `KPP_INIT_FIXED` and `KPP_CALC`
  - Outputs CSV format with correct structure

**Problem**: Mixing coefficients are all **zero**
```
Max KPPviscAz = 0.0 m²/s (wrapper outputs zeros)
Max KPPdiffKzT = 0.0 m²/s
Max KPPdiffKzS = 0.0 m²/s
KPPhbl = 0.0 m
```

### 3. Comparison Script
- **Status**: ✅ Working
- **Functionality**:
  - Parses wrapper CSV output
  - Loads expected outputs from Python port
  - Computes differences and relative errors
  - Reports pass/fail with configurable tolerance

## 🔴 Current Issue: Wrapper Outputs Zero Mixing

### Evidence
From `test_case_001`:

| Field | Python Port | Wrapper | Difference |
|-------|-------------|---------|------------|
| KPPviscAz (max) | 2.86e-01 m²/s | 0.0 m²/s | -2.86e-01 |
| KPPdiffKzT (max) | 2.85e-01 m²/s | 0.0 m²/s | -2.85e-01 |
| KPPdiffKzS (max) | 2.85e-01 m²/s | 0.0 m²/s | -2.85e-01 |
| KPPghat (max) | 3.29 m/s² | 0.0 m/s² | -3.29 |
| KPPhbl | 14.77 m | 0.0 m | -14.77 |

### Possible Causes

1. **Missing KPP Parameter Initialization**
   - The wrapper may need KPP-specific parameters (like those in `data.kpp`)
   - Example parameters from MITgcm:
     ```
     KPPdiffKzS = background salinity diffusivity
     KPPdiffKzT = background temperature diffusivity
     KPPviscAz = background viscosity
     KPPRi0 = critical Richardson number
     KPPshsq = minimum shear squared
     ```

2. **COMMON Block Initialization**
   - KPP parameters may reside in COMMON blocks that aren't being initialized
   - Check: `KPP.h` COMMON blocks vs what's initialized in `KPP_INIT_FIXED`

3. **Missing Initialization Routines**
   - May need to call additional MITgcm initialization routines before `KPP_CALC`
   - Check: `KPP_INIT_VARIA`, `KPP_INIT_PARAMS`, etc.

4. **Different Physics Behavior**
   - Wrapper might require specific conditions to trigger mixing
   - E.g., may check flags or thresholds that prevent mixing calculation

## 📋 Next Steps

### Immediate (Debugging)

1. **Check wrapper debug output**:
   ```bash
   grep -i "kpp" validation/test_case_001/wrapper_output.csv | head -20
   ```

2. **Add debug output to wrapper**:
   - Print KPP parameters after `KPP_INIT_FIXED`
   - Print intermediate KPP calculations (hbl, ustar, etc.)

3. **Compare with MITgcm reference run**:
   - Run MITgcm's 1D_ocean_ice_column verification case
   - Check what parameters it uses in `data.kpp`

### Short-term (Implementation)

4. **Add KPP parameter initialization**:
   - Create stub `KPP_READPARMS` or hardcode parameters in `KPP_INIT_FIXED`
   - Match default parameters from Python port's `kpp_default_parameters.yaml`

5. **Add data.kpp reading capability**:
   - Create namelist file format matching MITgcm
   - Read parameters at runtime

### Long-term (Validation)

6. **Once mixing outputs are non-zero**:
   - Run validation on multiple scenarios (arctic, hurricane, tropical)
   - Test varying grid resolutions
   - Test time-integration (multi-timestep)

## 📁 Files Created

### Validation Framework
- `validation/run_kpp_and_export.py` - Export tool (✅ working)
- `validation/compare_simple.py` - Comparison tool (✅ working)
- `validation/test_case_001/` - Test case directory
  - `inputs.npz` - Numpy inputs
  - `outputs_kpp_port.npz` - Expected outputs (non-zero!)
  - `input.bin` - Binary input for wrapper
  - `wrapper_output.csv` - Wrapper output (zeros)
  - `README.txt` - Test case summary

### Documentation
- `validation/VALIDATION_STATUS.md` - This file

## 🎯 Success Criteria

The validation framework will be fully functional when:

1. ✅ Python port produces non-zero mixing (DONE)
2. ✅ Wrapper reads inputs correctly (DONE)
3. ❌ Wrapper produces non-zero mixing matching port (TODO)
4. ❌ Relative difference < 1e-12 for all fields (TODO)

## 💡 Key Insight

The infrastructure for validation is **complete and working**. The remaining work is **physics debugging** in the wrapper to understand why KPP isn't producing mixing coefficients.

The Python port proves the inputs are physically reasonable (it computes hbl=14.77m and mixing O(0.1) m²/s), so the wrapper's zero output is a bug/configuration issue, not bad input data.
