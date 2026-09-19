# Handoff Documentation Directory

This directory contains all documentation for the MITgcm KPP wrapper development session (2026-08-19).

## Start Here

**HANDOFF.md** - Complete handoff document with:
  - Current status summary
  - What was accomplished (9 critical fixes)
  - Known issues
  - Next steps for investigation
  - How to build and run
  - File locations
  - Key code patterns

## Supporting Documents

**COMPARISON_RESULTS.md** - Detailed comparison between wrapper and Python port
  - Shows 27% hbl difference, 53% viscosity difference
  - Verified all inputs match
  - Analysis of potential causes

**COMMON_BLOCK_ISSUE.md** - Deep dive on Fortran COMMON block alignment problem
  - Why maskC/fCori must be set in main program
  - Evidence and workarounds
  - Impact assessment (no effect on physics)

**DEBUGGING_SESSION_SUMMARY.md** - Chronological history of debugging
  - All 9 issues found and fixed
  - Step-by-step progression

**DEBUG_LOG.md** - Detailed log of each debugging attempt
  - Hypothesis, action, result, conclusion for each attempt

**SUCCESS_SUMMARY.md** - Initial success report when wrapper first produced non-zero output

**FINAL_STATUS.md** - Comprehensive status report before handoff
  - Working features
  - Remaining issues
  - Validation status

## Quick Reference

Current Output:
  - hbl: 10.8m (Python port: 14.77m, 27% diff)
  - Max viscosity: 0.13 m²/s (Python port: 0.29 m²/s, 53% diff)

Next Task:
  - Add debug output for Richardson number, N², S²
  - Compare level-by-level with Python port
  - Find where calculations diverge

Build:
  cd /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/MITgcm_wrappers/KPP
  make clean && make
  ./kpp_wrapper > output.txt 2>&1

Test Case:
  validation/test_case_001/
    - input.bin (binary input)
    - outputs_kpp_port.npz (expected outputs from Python port)
