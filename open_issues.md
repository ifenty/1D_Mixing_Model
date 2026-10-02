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

## UNRESOLVED: the port's shortwave surface buoyancy forcing (`bfsfc`) differs from MITgcm's, leaving the remaining KPP mixing residuals

**Date Identified**: 2026-10-02T22:50:00Z
**Status**: Unresolved
**UUID**: 1DMIX-078
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`; `Vertical_Mixing_Models/KPP/kpp_routines.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
After 1DMIX-075 a few KPP cells still differ from MITgcm, and some moved slightly further away. Richard's review traced them to the surface buoyancy forcing `bfsfc`: the port's value differs systematically from MITgcm's captured `bfsfc_final` (median about 5e-9), in shallow and full-depth columns alike. The shortwave part is the suspect (the fraction of shortwave absorbed above the boundary layer, `swfrac`).

### Evidence
Richard, 1DMIX-075 review (devel-loop/loop_state/scratch/aef4cdd3c224c88b0/pop_bfsfc_latlon.txt, pop_bfsfc_labsea6mo.txt): with MITgcm's `bfsfc_final` substituted into the port, `visc_az`, `diff_kz` and `ghat` agree to 1e-13 on every hbl-equal global_oce_latlon column-step (wet levels 2 to 15) and to 1e-12 on lab_sea 6-month; without the substitution the same cells differ by up to 0.077 / 0.0945.

### Scientific or engineering impact
This is now the leading cause of the remaining KPP mixing-coefficient residuals on global_oce_latlon (62 `visc_az` and 1,136 `diff_kz_s` cells above 1% in the first 5 steps) and lab_sea. It may also explain part of 1DMIX-076.

### Proposed action and acceptance
Compare the port's `bfsfc` computation with MITgcm's (`kpp_routines.F` bldepth and blmix, `swfrac` and its water-type coefficients, the depth at which the shortwave fraction is evaluated) on a single-column witness, and find the first differing quantity. Acceptance: the cause is identified with file and line on both sides; the port is corrected to match, the captured `bfsfc_final` is reproduced to roundoff, and the latlon and lab_sea residuals are re-measured without widening any tolerance.

## UNRESOLVED: the stored `combined_storm` KPP standalone data predates 1DMIX-075, and two documents state its agreement without that qualification

**Date Identified**: 2026-10-02T22:50:00Z
**Status**: Unresolved
**UUID**: 1DMIX-079
**Anchors**: `MITgcm_to_Python_port_verification/tests/test_kpp_combined_storm_hbl_substitution.py`; `MITgcm_to_Python_port_verification/scripts/kpp_hbl_substitution_experiment.py`; `docs/model_contract.md`; `docs/code_map.md`

### Issue or research question
1DMIX-075 changed the `combined_storm` KPP trajectory from output time 9 on. The stored standalone datasets (`outputs_from_python_standalone/combined_storm`, the Python run and the Fortran driver output made from it) were not regenerated, so the test compares the current port with the Fortran output on the old run's states. That comparison is valid point by point (600 of 600 cells bit-exact) but is not a validation of the new trajectory.

### Evidence
Bob and Richard, 1DMIX-075: the Fortran side was not re-run (Bob cited no `gfortran` on the host; the project's MITgcm builds run in Docker). Richard's optional notes: `docs/model_contract.md` and `docs/code_map.md` say "now exactly 0" without "port re-run on stored diagnostics; Fortran not re-run"; the seaice `ghat` test docstring cites `kpp_scheme_specific.py:520-572`, a line range the change moved; `reports/kpp_scenario_standalone_summary.md` is a generated file whose narrative is hand-edited, so regenerating it would drop the 1DMIX-075 paragraph.

### Scientific or engineering impact
Declared external inputs no longer correspond to the port that the scenario runs with. The agreement is real but narrower than two documents state.

### Proposed action and acceptance
Regenerate the `combined_storm` KPP standalone datasets (Python run and Fortran driver, built in Docker) with the current port, record their provenance and hashes, and re-run the comparison on the new trajectory. Add the qualifying clause to the two documents until then, replace the stale line pointer with a symbol name, and make the summary report's 1DMIX-075 text survive regeneration. Acceptance: the declared datasets match the current port's `combined_storm` run, the comparison passes on them, and no document states the agreement more broadly than the evidence.
