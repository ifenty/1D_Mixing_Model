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

## UNRESOLVED: multi-column MITgcm replays give the port column-local velocities, while MITgcm forms tracer-point shear from neighbour-averaged velocities

**Date Identified**: 2026-09-30T14:20:00Z
**Status**: Unresolved
**UUID**: 1DMIX-071
**Anchors**: `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
MITgcm computes shear at a tracer point from velocities averaged over (i,i+1) and (j,j+1) (`ggl90_calc.F`, `kpp_calc.F`, `kpp_forcing_surf.F`); the replay scripts hand the single-column port only `uVel(i,j)`, `vVel(i,j)`. Every multi-column comparison therefore feeds the port a different shear than MITgcm used.

### Evidence
Bob, 1DMIX-054 (dispatch 893d4f73; devel-loop/loop_state/bob-1DMIX-054-evidence.md): for lab_sea GGL90, rebuilding ubar/vbar from neighbouring capture columns reproduces MITgcm's `vertical_shear` to median 1.25e-16 while column-local shear is off by a median 64%; for KPP 90x40x15 (no-smoothing rerun) the 4-point formula reproduces `shear_sq` exactly while column-local is off by a median 50%.

### Scientific or engineering impact
High for interpretation: the documented "known gaps" on multi-column captures (isomip diff_kz/tke_after, 90x40x15 GGL90, global_oce_latlon, lab_sea KPP and the new 1DMIX-054 lab_sea GGL90 and 90x40 KPP gaps; the cs32x15 captures are pressure-coordinate and are rejected by the port since 1DMIX-072/073, so they are not port comparisons) may be partly or wholly this replay-input artifact rather than port disagreement. Single-column captures are unaffected.

### Proposed action and acceptance
Make the replays reconstruct MITgcm's tracer-point velocities from neighbouring columns (with MITgcm's masks/halo conventions) and re-measure every multi-column comparison; separate the replay artifact from real gaps per field (as 1DMIX-070 did for print precision), updating known-gap assertions only with 16-vs-averaged evidence and never widening an upper tolerance. Acceptance: shear inputs reproduce MITgcm's captured shear to roundoff on every multi-column capture; each known-gap assertion is re-justified or removed.
