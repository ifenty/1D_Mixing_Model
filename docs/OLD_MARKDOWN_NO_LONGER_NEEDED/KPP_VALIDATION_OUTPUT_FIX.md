# KPP Validation Output Fix - Thread ID Bug

## Date
2026-08-19

## Status
RESOLVED

## Summary
The KPP validation output wasn't appearing because of an incorrect thread ID check. MITgcm uses 1-based thread numbering, but the validation code was checking for thread 0.

## Root Cause
In `/mitgcm_verification_mods/lab_sea/code_validation/kpp_output_validation.F` at line 47:

```fortran
IF ( myThid .NE. 0 ) RETURN
```

This check was intended to ensure only one thread writes output (avoiding duplicates), but MITgcm threads are numbered starting from 1, not 0. The check was rejecting all threads, including thread 1 which should be doing the writing.

## Evidence
1. Binary contained the validation subroutine and call (verified with `nm` and `strings`)
2. KPP_CALC was running (confirmed by timing output)
3. Model output showed `(PID.TID 0000.0001)` format - thread ID is 1, not 0
4. Standard MITgcm pattern in `model/src/plot_field.F` uses `IF ( myThid .EQ. 1 ) THEN`

## Fix Applied
Changed line 47 from:
```fortran
C     Only thread 0 writes (avoid duplicate output)
IF ( myThid .NE. 0 ) RETURN
```

To:
```fortran
C     Only thread 1 writes (avoid duplicate output)
IF ( myThid .NE. 1 ) RETURN
```

## Verification
After recompiling and running:
- DEBUG output now appears: `DEBUG: KPP_OUTPUT_VALIDATION, myIter= 1 myThid= 1`
- Validation markers present: `===== KPP_VALIDATION_START =====`
- Data output working: `INPUT_STATE`, `INPUT_GEOM`, `INPUT_FORCING`, `OUTPUT_MIXING`, `OUTPUT_HBL`
- Output file size: 27MB (vs 364KB before fix)
- Captured 9 timesteps of validation data

## Testing
Compiled and ran successfully:
```bash
cd /Users/ifenty/git_repo_others/MITgcm/verification
./experiment_compile.sh lab_sea -mods /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/lab_sea/code_validation -output output_validation -j 12
./experiment_run_no_compile.sh lab_sea -output output_validation 2>&1 | tee /tmp/mitgcm_run_output_fixed.txt
```

Output now contains high-precision (E25.16) validation data suitable for `rtol=1e-12` testing.

## Files Modified
- `/Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/mitgcm_verification_mods/lab_sea/code_validation/kpp_output_validation.F`

## Next Steps
1. Extract validation data from stdout
2. Parse into structured format for Python validation tests
3. Run Python KPP port against this reference data
