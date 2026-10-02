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
