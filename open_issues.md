# Open issues

Fenced examples are templates and are excluded by the gate. Use stable unique IDs.
Statuses: Unresolved, Investigating, Blocked. A blocked entry requires Blocked-By:
a project issue ID, EXTERNAL or OWNER-DECISION, followed by ` — ` and an explanation.
A closed dependency prompts reconsideration; it does not automatically unblock work.

```markdown
## UNRESOLVED: <Brief title>

**Date Identified**: <UTC ISO timestamp>
**Status**: Unresolved
**UUID**: <PROJECT-ISSUE-001>
**Anchors**: <owning path::symbol>; <nearest test path::symbol>

### Issue or research question
<Observed behavior, expected contract and what remains uncertain>

### Evidence
<Executed command, cwd, source/input identity, environment and measured result>

### Scientific or engineering impact
<Effect on correctness, interpretation, users or resources>

### Proposed action and acceptance
<Hypothesis, bounded change/inquiry, independent oracle, tolerances and completion criteria>
```

## UNRESOLVED: `GGL90Parameters.calc_mean_vert_shear` is accepted but never read, so `True` is silently ignored

**Date Identified**: 2026-10-02T18:45:00Z
**Status**: Unresolved
**UUID**: 1DMIX-074
**Anchors**: `Vertical_Mixing_Models/GGL90/ggl90_parameters.py::GGL90Parameters`; `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing`; `esx/project_profile.md`

### Issue or research question
MITgcm's `calcMeanVertShear` selects between two shear formulas in `ggl90_calc.F` (lines 526-540 and 541-556). The port's `GGL90Parameters.calc_mean_vert_shear` (`ggl90_parameters.py` line 176) is accepted and stored but no code reads it, so a configuration that sets it to `True` runs the `False` formula without any error.

### Evidence
Bob, 1DMIX-071 Phase 1 (devel-loop/loop_state/bob-1DMIX-071-evidence.md): source inspection of the parameter and its uses. All six z-coordinate GGL90 captures have calcMeanVertShear=0, so no declared comparison is affected.

### Scientific or engineering impact
A silent-ignore of a physics switch. With `True`, MITgcm sums four separate squared differences, which a single column cannot reproduce from one velocity profile.

### Proposed action and acceptance
Decide between rejecting `calc_mean_vert_shear=True` with a ValueError (the project profile's unsupported-input rule) and supporting it through an optional precomputed-shear input like the KPP one from 1DMIX-071. Acceptance: `True` either raises with a clear message or is implemented and tested against a MITgcm capture built with calcMeanVertShear=1; default behaviour is bit-identical.

## UNRESOLVED: residual KPP differences after tracer-point inputs: `ghat` exactly zero where MITgcm is nonzero, one `hbl` column, and global_oce_latlon

**Date Identified**: 2026-10-02T20:35:00Z
**Status**: Unresolved
**UUID**: 1DMIX-076
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py`

### Issue or research question
Three KPP differences remain that are neither replay-input artifacts (1DMIX-071) nor the boundary-layer bottom handling fixed in 1DMIX-075:
- The port returns `ghat` exactly 0 in a few cells where MITgcm is nonzero: 8 cells in seaice_obcs, 2 in global_oce_latlon (first 5 steps), 2 in the lab_sea 6-month window (first 100 steps), 127 in the lab_sea 999-step capture and 13 in 11k_1D.
- One lab_sea 6-month column-timestep (t=90, i=17, j=6) has `hbl` 66.71 m in MITgcm against 45.00 m in the port.
- global_oce_latlon (built with no smoothing), first 5 steps: `hbl` max 3.09 m, `ghat` max 116 with 9 cells above 1%, and 62 `visc_az` and 1,136 `diff_kz_s` cells above 1%.

### Evidence
Bob 1DMIX-071 Phase 2 re-measurement, reproduced by Richard in both replay modes. Bob 1DMIX-075 Phase 2 (devel-loop/loop_state/bob-1DMIX-075-evidence.md, unit P2-6) measured what that fix changed: of the exact-zero `ghat` cells it explained 1 of 3 in global_oce_latlon and none in seaice_obcs or lab_sea 6-month; it explained 244 of 306 `visc_az` and 325 of 1,461 `diff_kz_s` latlon cells; the `hbl` column and the latlon `hbl` and `ghat` figures did not change, because `hbl` is computed before the changed code.

### Scientific or engineering impact
These are now the leading KPP port-versus-MITgcm differences on multi-column captures. The exact-zero `ghat` cells suggest a gate or index-offset difference rather than a tolerance effect.

### Proposed action and acceptance
Take one exact-zero `ghat` cell and the single `hbl` column as single-column witnesses and trace each to the diverging line on both sides. Decide whether global_oce_latlon shares a cause with either. Acceptance: each of the three is explained with file and line, and fixed in the port or documented as a capture limitation, with the affected bounds tightened where a fix lands.

## UNRESOLVED: GGL90 `tke_after` disagrees with MITgcm at the first two wet levels under the ice shelf (isomip)

**Date Identified**: 2026-10-02T20:35:00Z
**Status**: Unresolved
**UUID**: 1DMIX-077
**Anchors**: `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing`; `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`

### Issue or research question
With tracer-point replay inputs (1DMIX-071) the isomip GGL90 capture still has 16,123 `tke_after` cells differing by more than 1%, all at first-wet+1 (9,542 cells) and first-wet+2 (6,581 cells) beneath the ice shelf. The shear-dependent part of the old gap (1,811 cells) is gone; this part does not depend on shear.

### Evidence
Bob 1DMIX-071 Phase 2; Richard's review reproduced 16,123 cells with the same split and 17,934 in column-local mode.

### Scientific or engineering impact
A real difference in the ice-shelf surface boundary treatment of TKE (the kSrf levels), the last unexplained GGL90 gap on a z-coordinate capture other than the missing IDEMIX physics.

### Proposed action and acceptance
Reduce one sub-ice-shelf column to a single-column witness and compare the TKE surface boundary condition and its first interior levels in `ggl90_calc.F` (kSrf handling, SHELFICE friction velocity) with the port. Acceptance: the mechanism is identified with file and line on both sides, and the port is corrected to match MITgcm or the difference is documented with its cause.
