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
High for interpretation: the documented "known gaps" on multi-column captures (isomip diff_kz/tke_after, 90x40x15/cs32x15 GGL90, global_oce_latlon, lab_sea KPP and the new 1DMIX-054 lab_sea GGL90 and 90x40 KPP gaps) may be partly or wholly this replay-input artifact rather than port disagreement. Single-column captures are unaffected.

### Proposed action and acceptance
Make the replays reconstruct MITgcm's tracer-point velocities from neighbouring columns (with MITgcm's masks/halo conventions) and re-measure every multi-column comparison; separate the replay artifact from real gaps per field (as 1DMIX-070 did for print precision), updating known-gap assertions only with 16-vs-averaged evidence and never widening an upper tolerance. Acceptance: shear inputs reproduce MITgcm's captured shear to roundoff on every multi-column capture; each known-gap assertion is re-justified or removed.

## UNRESOLVED: the GGL90 port returns finite wrong values for pressure-coordinate input, and a declared GGL90 capture is pressure-coordinate

**Date Identified**: 2026-09-30T15:30:00Z
**Status**: Unresolved
**UUID**: 1DMIX-073
**Anchors**: `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.compute_mixing`; `Vertical_Mixing_Models/KPP/kpp_core_driver.py::validate_zcoordinate_geometry`; `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`

### Issue or research question
1DMIX-072 made KPP reject pressure-coordinate geometry. `GGL90Driver.compute_mixing` has no equivalent check. The declared GGL90 capture `global_ocean_cs32x15_idemix_10` (recipe G4, `OCEANICP`) is itself pressure-coordinate: positive Pa depths up to 4.95e7, `cell_thickness` 5.03e5 to 7.11e6. Its current tests therefore compare the port against MITgcm on geometry the port does not support (1DMIX-040).

### Evidence
Bob, 1DMIX-072 unit 4 (devel-loop/loop_state/bob-1DMIX-072-evidence.md): replaying steps 0-9 gives 813,820 wet cells, all finite, with `visc_az`/`diff_kz` capped at `GGL90viscMax`=100, `mixing_length` up to 1.449e7 m and `tke_after` up to 4.199e5. There is no raise and no geometry check anywhere in the GGL90 path.

### Scientific or engineering impact
It is the same silent-incorrect-result risk the contract records. Existing GGL90 cs32x15 known-gap assertions characterize unsupported input as if it were a port comparison.

### Proposed action and acceptance
Share the z-coordinate guard (move `validate_zcoordinate_geometry` to a common module) and call it from `GGL90Driver.compute_mixing`. Convert the GGL90 cs32x15 port-side tests to assert the ValueError, keeping MITgcm-side facts and recording historical numbers the way 1DMIX-072 did. Acceptance:
- every z-coordinate GGL90 capture and scenario is unaffected, with outputs bit-identical;
- the full suite passes;
- no tolerance is widened.
