# Implementation Notes

## SIZE.h Configuration Fix

**Issue**: Original lab_sea SIZE.h had `nPx=2, nPy=1` (2 MPI processes), but we're running without MPI.

**Solution**: Modified SIZE.h for single-processor run:
- `sNx = 20` (full domain width, was 10)
- `sNy = 16` (full domain height, was 8)
- `nPx = 1, nPy = 1` (single processor, was 2×1)
- `nSx = 1, nSy = 1` (single tile per processor, was 1×2)

This maintains the full domain size of 20×16×23 but runs on a single processor.

**Affected files**:
- `/Users/ifenty/git_repo_others/MITgcm/verification/lab_sea/code/SIZE.h` - modified
- Original multi-processor version saved as `SIZE.h_mpi`

## Compilation History

1. **First compilation** (2026-08-19 09:38): Success with instrumented code
2. **First run attempt**: Failed with processor mismatch error
3. **SIZE.h fix**: Changed to single-processor configuration
4. **Second compilation** (2026-08-19 09:42): In progress...

## Next Steps After Successful Run

1. Verify KPP validation blocks appear in output
2. Parse output with `mitgcm_kpp_parser.py`
3. Create validation test suite
4. Run tests and document results
