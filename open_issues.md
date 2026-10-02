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

## UNRESOLVED: KPP mixing coefficients disagree with MITgcm at k=1 of two-wet-level columns (global_ocean_90x40x15)

**Date Identified**: 2026-10-02T20:35:00Z
**Status**: Unresolved
**UUID**: 1DMIX-075
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`; `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
With tracer-point replay inputs (1DMIX-071) the 90x40x15 KPP capture still has 456 `visc_az` and 520 `diff_kz_s` cells differing by more than 1%. 367 of the 456 `visc_az` cells sit at k=1 of the 610 columns that have exactly two wet levels. Example: t=5, i=72, j=35, MITgcm 0.0491 against port 0.0010, with an `hbl` difference of 0.

### Evidence
Bob 1DMIX-071 Phase 2 (devel-loop/loop_state/bob-1DMIX-071-evidence.md, bob-1DMIX-071-remeasure-kpp.json.txt). Richard's review: at k=1 of those columns `visc_az` has the same maximum 4.807e-2 and median 3.87e-4 with column-local and tracer-point inputs, and the same 367 cells, so it does not depend on the replay inputs.

### Scientific or engineering impact
A real port-versus-MITgcm difference in very shallow columns. It bounds the 90x40 KPP mixing agreement at 0.048 where the rest of the capture agrees far more closely.

### Proposed action and acceptance
Reduce one two-wet-level column to a single-column witness, trace `visc_az` at k=1 through the boundary-layer and interior branches in MITgcm (`kpp_routines.F`) and in the port, and find where they diverge. Acceptance: the mechanism is identified with file and line on both sides, and either the port is corrected to match MITgcm (the bound tightens) or the difference is shown to be a capture or replay limitation and documented.

## UNRESOLVED: residual KPP differences after tracer-point inputs: `ghat` exactly zero where MITgcm is nonzero, one `hbl` column, and global_oce_latlon

**Date Identified**: 2026-10-02T20:35:00Z
**Status**: Unresolved
**UUID**: 1DMIX-076
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py`

### Issue or research question
Three KPP differences remain that 1DMIX-071 showed are not replay-input artifacts:
- The port returns `ghat` exactly 0 in a few cells where MITgcm is nonzero: 8 cells in seaice_obcs (90.8% of the `ghat` absolute difference), 3 in global_oce_latlon (97.6%), 2 in the lab_sea 6-month window.
- One lab_sea 6-month column-timestep (t=90, i=17, j=6) has `hbl` 66.71 m in MITgcm against 45.00 m in the port.
- global_oce_latlon (built with no smoothing) is unchanged by the new inputs: `hbl` max 3.09 m, `ghat` max 116, and 306 `visc_az`, 1,461 `diff_kz_s` and 9 `ghat` cells above 1% in the first 5 steps.

### Evidence
Bob 1DMIX-071 Phase 2 re-measurement; Richard's review reproduced the global_oce_latlon figures in both replay modes (`hbl` max 3.0916 m and `ghat` max 115.97 in both).

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
