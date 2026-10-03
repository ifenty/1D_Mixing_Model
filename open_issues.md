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

Related findings filed 2026-10-02: the global_oce_latlon KPP capture is a constructed build with `KPP_GHAT` and smoothing undefined (1DMIX-116); the Jerlov default (1DMIX-080) and `swfrac` cut-off (1DMIX-085) bear on `hbl` and `ghat`.

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

Candidate causes filed 2026-10-02 from FABLE_FINDS.md: the port's Jerlov water type default IB where MITgcm hard-codes IA (1DMIX-080, measured to reduce the 11k_1D `hbl` maximum tenfold) and the missing 200 m `swfrac` cut-off (1DMIX-085). Resolve or re-measure this issue after them.

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

## UNRESOLVED: KPP Jerlov water type defaults to `"IB"`; MITgcm hard-codes type IA

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-080
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters`; `Vertical_Mixing_Models/KPP/kpp_shortwave.py::swfrac`; `Vertical_Mixing_Models/KPP/kpp_default_parameters.yaml`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
`KPPParameters.jerlov_water_type` defaults to `"IB"` (`kpp_parameters.py` line 199; `kpp_default_parameters.yaml` line 109), and `swfrac(depth_m, water_type="IB")` has the same default. It is used in `kpp_scheme_specific.py` (lines 152, 272, 333). MITgcm hard-codes type IA: `model/src/swfrac.F` line 92, `jwtype=2`, commented "Parameter jwtype is hardcoded to 2 for time being". There is no namelist entry, so no capture carries the value and the "take every parameter from the capture" rule cannot catch it.

### Evidence
FABLE_FINDS.md §A2. That file is the record of a library review by Claude (Fable 5.1) and its sub-agents, compiled and re-checked by Claude (Opus 5.5) on 2026-10-02. It checked HEAD 336a85a plus that afternoon's working tree against MITgcm d861cd501. The owner directed on 2026-10-02 that its findings be accepted as correct.
- **Measurement:** a replay of 2,000 steps of the 11,000-step single-column KPP capture, run with IA instead of IB. The median `hbl` difference fell from 2.2e-5 m to 1.6e-6 m, and the maximum from 4.3e-2 m to 4.2e-3 m.
- **Who ran it:** a library run, reproduced independently by a second reviewer. The script was not kept. Both defaults were re-read on 2026-10-02.
- **Detail:** `../MITgcm_porting_wisdom/Porting_MITgcm_to_Standalone_Python/02_pitfalls_and_gotchas.md`.

### Scientific or engineering impact
This affects every KPP full-model comparison wherever shortwave is non-zero; the effect is measured on one capture only.
- **1DMIX-078:** this is a direct candidate cause, since the port's `bfsfc` differs from MITgcm's and the shortwave fraction `swfrac` is the suspect.
- **`hbl` tail:** part of the tail previously attributed to threshold sensitivity may be this.
- **Priority:** the findings rank it first: a one-line change with a measured tenfold effect.

### Proposed action and acceptance
Default to `"IA"` in the dataclass, the YAML and `swfrac`, and document that the default is MITgcm's hard-coded value (`swfrac.F` line 92). Re-run every KPP full-model comparison and re-measure 1DMIX-076 and 1DMIX-078 before and after.

Acceptance:
- the default is IA, with a test that pins it to `swfrac.F`;
- the 11k_1D `hbl` reduction is reproduced from a kept script;
- every KPP capture's cells above 1% and max_abs are recorded old versus new, with no tolerance widened and bounds tightened where the figures allow;
- 1DMIX-078 is updated with what this explains.

## UNRESOLVED: the convective-adjustment mask compares in-situ densities at each level's own pressure; MITgcm compares at a common reference level (1DMIX-005 was closed wrongly)

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-081
**Anchors**: `Vertical_Mixing_Models/main/eos.py::compute_static_instability_mask`; `Vertical_Mixing_Models/main/unified_driver.py`; `closed_issues.md`; `docs/model_contract.md`

### Issue or research question
`compute_static_instability_mask` (`eos.py` line 468) is called only from `unified_driver.py` (line 123) when `ivdc_kappa != 0`. It computes in-situ density at every level with that level's own pressure, and flags interface `k` where `rho[k-1] > rho[k]`.

MITgcm compares two parcels at a common reference level in both criteria:
- `calc_ivdc.F` tests `-sigmaR*gravitySign > 0`, and `sigmaR` is formed in `do_oceanic_phys.F` by `FIND_RHO_2D` on levels `k-1` and `k` with the same reference level;
- `convective_adjustment.F` calls `FIND_RHO_2D` twice with the same `k+deltaK`.

In-situ density increases with depth through compression alone, so the port's mask hardly ever fires.

1DMIX-005 examined exactly this and closed it as a false positive. `closed_issues.md` line 742 says "also uses in-situ density on both sides — the sign test is density-type-independent". It cited the two same-reference `FIND_RHO_2D` calls and made no numerical check (FABLE_FINDS.md §D1).

### Evidence
FABLE_FINDS.md §A1 and §D1 (library review, 2026-10-02; the owner directed acceptance as correct).
- **Port:** a column with T rising from 2.0 to 2.4 °C over 2 km at constant S, which is unstable everywhere in potential density. The port flags 0 of 19 interfaces; re-run on 2026-10-02.
- **MITgcm:** a library reviewer's run found MITgcm's two criteria flag 19 of 19 on such a column.
- **Sources re-read on 2026-10-02:** the port, `calc_ivdc.F`, `convective_adjustment.F` and `do_oceanic_phys.F`.
- **Detail:** `../MITgcm_porting_wisdom/Porting_MITgcm_to_Standalone_Python/02_pitfalls_and_gotchas.md` and `04_physical_consistency.md`.

### Scientific or engineering impact
A silent incorrect result in every free-running scenario run with `ivdc_kappa != 0` (`--ivdc-kappa`): convective adjustment almost never applies. There is no effect on published MITgcm agreement, because the mask sits upstream of every comparison. A closed ledger entry states the wrong conclusion and can be quoted again.

### Proposed action and acceptance
Compare `rho(theta[k-1], salt[k-1], p_ref)` with `rho(theta[k], salt[k], p_ref)` at one reference level per interface, as `compute_ggl90_buoyancy_frequency_squared` already does for N². Add a forward pointer from the 1DMIX-005 closed entry to this issue. Check `docs/model_contract.md` for the same wrong statement.

Acceptance:
- a test on the unstable column above flags 19 of 19 interfaces;
- a stable column and a compression-only column flag none;
- the result agrees with MITgcm's criterion on a capture or a hand-computed `FIND_RHO_2D` reference;
- 1DMIX-005 carries the forward pointer;
- any affected scenario outputs are re-measured, with the cells counted.

## UNRESOLVED: KPP `bosol` has the opposite sign convention to `bo` in the port's surface-forcing routine

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-082
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver._compute_surface_forcing`; `Vertical_Mixing_Models/main/run_scenarios.py::run_one`

### Issue or research question
In `_compute_surface_forcing` (line 621), `bo = -g*(ttalpha*temp_flux + …)/rho_surf` treats the heat flux as positive into the ocean. `bosol = g*ttalpha*sw_flux/rho_surf` is a literal copy of `kpp_forcing_surf.F` lines 236–238, which is correct only for MITgcm's `Qsw`, positive upward. With one convention for both arguments, one of the two terms has the wrong sign.

### Evidence
FABLE_FINDS.md §A3 (library review, 2026-10-02; the owner directed acceptance as correct). With the scenarios' convention (positive = heating) and penetrating shortwave on, solar heating gives a destabilizing `bosol`. At 10 °C it is −8.0e-8 m²/s³ where +8.0e-8 is right. The code path was re-read on 2026-10-02; the number is from a library reviewer's run. Detail: `../MITgcm_porting_wisdom/Porting_MITgcm_to_Standalone_Python/04_physical_consistency.md`.

### Scientific or engineering impact
Any free-running use with `shortwave_heating` on gets solar heating with the wrong stability sign. This is masked in every tested path: the replay harness passes MITgcm-signed values, and all six scenarios leave penetration off.

### Proposed action and acceptance
Pick one sign convention for `q_net` and `q_sw` at this boundary, state it in the docstring and `docs/model_contract.md`, and make `bo` and `bosol` consistent with it.

Acceptance: a test with non-zero `q_sw` shows solar heating giving a positive (stabilizing) `bosol` equal to the hand value. The replay path keeps MITgcm-signed inputs and stays bit-identical. Scenario outputs are bit-identical, or each change is counted and explained.

## UNRESOLVED: eight KPP `np.sign` sites differ from Fortran `SIGN` at exactly zero, so at `bfsfc = 0` the port skips the Ekman/Monin–Obukhov limit

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-083
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py::diagnose_bl_depth`; `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py::compute_bl_mixing`; `Vertical_Mixing_Models/KPP/kpp_routines.py::z121_smooth`

### Issue or research question
Fortran `p5 + SIGN(p5, x)` is 1 at `x = 0`, whereas `0.5 + np.sign(x)*0.5` is 0.5. Fortran `SIGN(1,x)*MAX(phepsi,ABS(x))` is `+phepsi` at `x = 0`, whereas the port's form is 0.

The eight sites:

| Site | Port line | Fortran `kpp_routines.F` |
| --- | --- | --- |
| `KRi_range` in `kpp_routines.py` | 426, 427 | 1279–1281 |
| `stable_flag` in `kpp_scheme_specific.py` | 165 | 577 |
| `stable`, `bfsfc` | 282, 283 | 765–766 |
| `stable`, `bfsfc` | 342, 343 | 902–903 |
| `casea` | 356 | 913 |

The file already uses the right idiom at line 488, where a comment states this exact hazard, but only at that one site.

Consequence at `bfsfc == 0`:
- **MITgcm:** gets `stable = 1` and `bfsfc = +phepsi > 0`, so it applies the Ekman and Monin–Obukhov limit to `hbl` (`kpp_routines.F` lines 781–790).
- **Port:** gets `bfsfc = 0`; the test `bfsfc > 0.0` at line 286 is false, so the limit is skipped.

### Evidence
FABLE_FINDS.md §A7 (library review, 2026-10-02; the owner directed acceptance as correct). The sites were re-listed by grep on 2026-10-02, and the line numbers were re-confirmed after 1DMIX-075. The Fortran lines were re-read. The effect has not been measured.

### Scientific or engineering impact
Wrong `hbl` and mixing at exactly zero buoyancy forcing, for example a start from rest with zero flux or a synthetic scenario. No reference enters this branch, so no comparison sees it.

### Proposed action and acceptance
Use `np.copysign(0.5, x)` and `np.copysign(1.0, x)` (Fortran `SIGN` semantics, including the sign of zero) at all eight sites.

Acceptance:
- a test at exactly `bfsfc = 0` shows the Ekman/Monin–Obukhov limit applied, matching a hand-traced `kpp_routines.F` value;
- a unit test of each site at `x = 0`, `+0.0`, `-0.0` and non-zero values;
- all replays and scenarios are bit-identical away from exact zeros, or each change is counted.

## UNRESOLVED: KPP friction-velocity floor differs from `KPP_FORCING_SURF`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-084
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver._compute_surface_forcing`

### Issue or research question
The port does `if tau_mag_sq < phepsi**2: ustar = sqrt(phepsi)`. MITgcm's `kpp_forcing_surf.F` (lines 198–204) uses the threshold `phepsi²·drF(1)²` and the floor `SQRT(p5*phepsi*drF(1))`, both of which depend on the top-cell thickness. The port's do not.

### Evidence
FABLE_FINDS.md §A9 (library review, 2026-10-02; the owner directed acceptance as correct). With `phepsi = 1e-10` the port's floor is 1.0e-5 m/s, against MITgcm's 2.2e-5 m/s for a 10 m top cell. Both were re-read on 2026-10-02. The effect has not been measured.

### Scientific or engineering impact
Scenario runs at very weak wind get a different `ustar`, and hence different velocity scales and `hbl`. This sits upstream of the replay harness, which passes MITgcm's `ustar`, so no comparison can see it.

### Proposed action and acceptance
Use MITgcm's threshold and floor with the column's top-cell thickness.

Acceptance: a weak-wind test (`tau` below threshold, two top-cell thicknesses) reproduces `SQRT(p5*phepsi*drF(1))`. Scenarios are bit-identical, or each change is counted.

## UNRESOLVED: the port's `swfrac` has no 200 m cut-off

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-085
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_shortwave.py::swfrac`

### Issue or research question
MITgcm's `swfrac.F` (line 99) sets the shortwave fraction to exactly zero below 200 m. The port's `swfrac` has no such cut-off, so it returns a tiny non-zero fraction where MITgcm has an exact zero.

### Evidence
FABLE_FINDS.md §A10 (library review, 2026-10-02; the owner directed acceptance as correct). The port file was re-read on 2026-10-02 and has no cut-off. The effect has not been measured.

### Scientific or engineering impact
This matters for bit-identity, for exact-zero tests below 200 m, and possibly for `bfsfc` in deep boundary layers. It is a candidate contributor to 1DMIX-078 and to the exact-zero `ghat` cells in 1DMIX-076.

### Proposed action and acceptance
Add the cut-off exactly as `swfrac.F` line 99 has it, including the comparison's direction and the depth's sign convention. Resolve it with or after 1DMIX-080.

Acceptance:
- a test shows an exact 0 just below 200 m and the unchanged value above;
- the KPP replays are re-measured, with each changed cell counted;
- no tolerance is widened.

## UNRESOLVED: GGL90 `sqrt_two = np.sqrt(2.0)` is not MITgcm's truncated `SQRTTWO` literal

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-086
**Anchors**: `Vertical_Mixing_Models/GGL90/ggl90_parameters.py::GGL90Parameters`; `Vertical_Mixing_Models/GGL90/ggl90_scheme_specific.py`

### Issue or research question
`ggl90_parameters.py` line 188 has `sqrt_two = np.sqrt(2.0)`, used in `ggl90_scheme_specific.py` line 142. MITgcm's `pkg/ggl90/GGL90.h` line 67 has `PARAMETER ( SQRTTWO = 1.41421356237310D0 )`, a truncated literal that differs from √2 by 3.5e-15 relative.

### Evidence
FABLE_FINDS.md §A5 (library review, 2026-10-02; the owner directed acceptance as correct). Both lines were re-read on 2026-10-02. Detail: `../MITgcm_porting_wisdom/Verification_and_Validation/12_bit_identical_gold_standard.md`.

### Scientific or engineering impact
The mixing length cannot be bit-identical where the `sqrt(2*TKE)/N` branch is active. The difference is consistent in size with the remaining ~1e-13 m mixing-length residual, but substitution has not tested that link; it is a hypothesis.

### Proposed action and acceptance
Set `sqrt_two: float = 1.41421356237310`.

Acceptance: a test pins the literal to `GGL90.h`. The GGL90 replays are re-measured, and it is recorded whether the mixing-length residual reaches exact equality. No tolerance is widened.

## UNRESOLVED: KPP cubes are written `**3` where MITgcm multiplies (or gfortran expands to a product)

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-087
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_routines.py::wscale`; `Vertical_Mixing_Models/KPP/kpp_routines.py::build_wscale_lookup_tables`; `Vertical_Mixing_Models/KPP/kpp_routines.py::ri_iwmix`; `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py::diagnose_bl_depth`

### Issue or research question
For a Python float or NumPy scalar, `x**3` goes through `pow` and differs from `x*x*x` in the last bit for a fraction of values. The sites:
- `kpp_routines.py` line 207: `u3 = ustar[i]**3`. Fortran (`kpp_routines.F` line 1016): `ustar(i)*ustar(i)*ustar(i)`.
- `kpp_scheme_specific.py` line 288: `hmonob = config.cmonob * ustar**3 / …`. Fortran (line 785): `cmonob*ustar(i)*ustar(i)*ustar(i)`.
- `kpp_routines.py` lines 70, 81 and 86 (lookup-table construction): `usta**3`. Fortran (`kpp_init_fixed.F` lines 139, 147, 152) also writes `usta**3`, but gfortran evaluates it as the product.
- Also check `(1.0 - ratio**2)**3` at lines 362 and 367 against `kpp_routines.F` lines 1171–1179, which uses `ratio * ratio` and builds the cube in separate statements.

### Evidence
FABLE_FINDS.md §A6 (library run; script in `../MITgcm_porting_wisdom/Porting_MITgcm_to_Julia_Oceananigans/code_appendix/08_*`). All five port lines and the Fortran lines were re-read on 2026-10-02.
- **Velocity scales:** 25 of 112 stable-branch `wscale` test points differ in the last bit; gfortran agrees with the product form in 112 of 112.
- **Lookup tables:** tables built in Julia and in NumPy differ in 2–4% of entries, by at most 4.4e-16 relative. Which one equals MITgcm's table is undetermined.
- **Test lesson (FABLE_FINDS.md §D11):** a scratch mutation check had one mutant that changed sign as well as operation order, so its detection proves nothing about ordering. Also, `-(g/rhoConst)` versus `g*(-1)*(1/rhoConst)` is an equivalent mutant at round constants.

### Scientific or engineering impact
Last-bit differences in the velocity scales, which the `hbl` threshold can amplify. No statistic separates them out.

### Proposed action and acceptance
Write each cube as MITgcm's product form, and match the `ratio` cube's statement structure.

Acceptance:
- bit-order tests use random, non-round constants;
- the 112-point `wscale` comparison against a gfortran product reference is exact;
- the lookup table equals MITgcm's, where obtainable, or the residual is recorded;
- the KPP replays are re-measured, and it is recorded whether the stable branch reaches exact equality.

## UNRESOLVED: `GGL90viscArU` / `GGL90viscArV` have never been compared with MITgcm (the standalone driver never sets `maskW`/`maskS`)

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-088
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/ggl90_standalone_main.F`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`; `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`

### Issue or research question
`ggl90_standalone_main.F` never assigns `maskW` or `maskS`; there is no occurrence in the file. `ggl90_calc.F` forms the U- and V-point viscosities with `_maskW(i,j,k-1)*_maskW(i,j,k)` (lines 1042 and 1065), so in the driver they fall back to the background value. Neither array is captured or compared anywhere.

### Evidence
FABLE_FINDS.md §B1 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
One of GGL90's outputs to the model has no verification at all, in either the full-model leg or the driver leg.

### Proposed action and acceptance
Set the masks in the driver, add `GGL90viscArU/V` to the instrumentation and parser, and compare them with the port's U/V-point viscosities.

Acceptance: the arrays are captured for at least one single-column and one multi-column GGL90 experiment and compared with stated tolerances, with a non-vacuity count of cells off the background value. The driver reproduces the full model's values.

## UNRESOLVED: replay harnesses fall back silently to default physical constants when a capture attribute is missing

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-089
**Anchors**: `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py`

### Issue or research question
`run_ggl90_from_netcdf_input.py` lines 203–206 use `attrs.get('gravity', 9.81)`, `attrs.get('rhoConst', 1029.0)`, `attrs.get('viscAz', 0.0)` and `attrs.get('diffKzS', 0.0)`.

### Evidence
FABLE_FINDS.md §B4 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. There is no effect on the current captures.

### Scientific or engineering impact
A capture missing an attribute is replayed with a default and no message. This is exactly the failure the "constants come from the capture" rule exists to prevent.

### Proposed action and acceptance
Index the attributes (`attrs['gravity']`) so that absence raises, and audit both replay scripts for other `.get(…, default)` uses on physical constants.

Acceptance: a test with an attribute removed raises a clear error, and replays of the existing captures are bit-identical.

## UNRESOLVED: the KPP replay turns any per-column exception into a NaN cell and continues

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-090
**Anchors**: `MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
`run_kpp_from_netcdf_input.py` (lines 1047–1050, `except Exception … continue`, and the worker's error dictionary) records a failed column as missing data. The script's own comment at line 833 describes the hazard. The geometry guard added for 1DMIX-072 covers only one cause.

### Evidence
FABLE_FINDS.md §B6 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
A vacuity risk. Any port exception, for instance the 1DMIX-106 crash path, is reported as missing data rather than as a failure, and tests that mask NaN then compare fewer cells without saying so.

### Proposed action and acceptance
Count per-column failures, report them with the first exception, and fail the run when the count is non-zero, unless an explicit, documented allowance names the cause.

Acceptance: a test injecting an exception in one column makes the replay fail. Existing replays report zero failures.

## UNRESOLVED: the capture parser skips unrecognized lines silently

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-091
**Anchors**: `MITgcm_to_Python_port_verification/scripts/capture_stream.py`; `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py`; `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py`

### Issue or research question
`capture_stream.py` (`continue` at lines 182–212) and the per-package line grammars drop a tagged line they cannot parse, without counting it.

### Evidence
FABLE_FINDS.md §B7 (library review, 2026-10-02; the owner directed acceptance as correct). Read on 2026-10-02; the behaviour was described by the library's V&V 01–07 author and reviewer.

### Scientific or engineering impact
A truncated or corrupted capture line vanishes, and the capture looks complete.

### Proposed action and acceptance
Count dropped tagged lines, report them, and fail above zero. Keep streaming with bounded memory, per the owner's rule.

Acceptance: a test with a truncated tagged line fails with the count and the line number. The existing captures parse with zero drops.

## UNRESOLVED: the `lab_sea` captures use a single 20×16 tile; stock is 2×2 of 10×8, and the runs differ

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-092
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/lab_sea/code_validation/SIZE.h`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/lab_sea/ggl90_code_validation/SIZE.h`; `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md`; `MITgcm_to_Python_port_verification/GGL90_port_validation/CAPTURES.md`

### Issue or research question
Both capture `SIZE.h` files have `sNx=20, sNy=16, nSx=1, nSy=1`; stock `verification/lab_sea/code/SIZE.h` has `sNx=10, sNy=8, nSx=2, nSy=2`. The sea-ice dynamics (LSR) solver works tile by tile and converges differently on one tile, so the surface forcing differs from the first step.

### Evidence
FABLE_FINDS.md §C1. Library run, re-run by a reviewer from the saved captures. Both `SIZE.h` files were re-read on 2026-10-02.
- `testreport` on the single-tile build fails with 2 matching digits.
- 134 of 1,350 forcing records are identical between the layouts, with a maximum relative difference of 1.67.
- With the solver's full-domain option compiled into both layouts, the largest difference falls to 1.5e-8.
- Detail: `../MITgcm_porting_wisdom/Verification_and_Validation/15_platform_specific_testing.md` and `16_parallel_testing.md`.

### Scientific or engineering impact
Single-step replay against these captures remains valid, because the port is fed what MITgcm computed. But they cannot be called "the `lab_sea` verification experiment", and nobody had run `testreport` on the capture build.

### Proposed action and acceptance
Either recapture `lab_sea` in the stock tile layout, or run `testreport` on the changed layout and record the result. In both cases state the layout with every number quoted from these captures.

Acceptance: CAPTURES.md and the results documents state the layout and the `testreport` result. No document calls the captures the stock experiment unless they are recaptured in the stock layout.

## UNRESOLVED: the constructed KPP capture on `global_ocean.90x40x15` ran horizontal smoothing with a 3-point overlap

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-093
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_ocean_90x40x15/kpp_code_validation/SIZE.h`; `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md`; `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`

### Issue or research question
`mitgcm_verification_mods/global_ocean_90x40x15/kpp_code_validation/` has no `KPP_OPTIONS.h`, so it uses the stock one, which defines `KPP_SMOOTH_SHSQ` and `KPP_SMOOTH_DBLOC`. Its `SIZE.h` has `OLx = 3`, and the capture's attributes confirm `smooth_shsq = 1` and `smooth_dbloc = 1`. `kpp_check.F` documents that smoothing needs `OLx = OLy = 4`. The check is compiled only under `KPP_REACTIVATE_OL4`, which is defined nowhere in the tracked tree, so the model does not stop.

### Evidence
FABLE_FINDS.md §C3 (library review, 2026-10-02; the owner directed acceptance as correct). All re-read on 2026-10-02; the attributes were read from the capture file.

### Scientific or engineering impact
Unexamined. Columns near tile edges may have been smoothed with halo values that MITgcm's own comment says are not valid. This is a candidate contributor to the 90x40x15 residual (7 / 27 cells after 1DMIX-075) and to tile-edge residuals.

### Proposed action and acceptance
Rebuild with `OLx = OLy = 4`, recapture, and compare the two captures at tile-edge columns.

Acceptance: the tile-edge differences between the OL3 and OL4 captures are counted. The port's residual is re-measured against the OL4 capture, and the declared capture is replaced or the layout stated with every number.

## UNRESOLVED: KPP capture variables `buoy_freq_sq`, `shear_sq`, `richardson` and `ghat` are mislabelled

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-094
**Anchors**: `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py`

### Issue or research question
The variable table in `parse_mitgcm_split.py` (lines 607–631) mislabels four variables:

| Variable | Labelled as | Actually holds |
| --- | --- | --- |
| `buoy_freq_sq` | N², in `1/s^2` | `dbloc(k)`: a buoyancy difference between adjacent levels, in m/s², on the bottom face of cell `k` |
| `shear_sq` | shear squared, in `1/s^2` | `shsq(k)`: a squared velocity difference, in m²/s² |
| `richardson` | Ri = N²/S², dimensionless | `dbloc/shsq`, in 1/m: a quantity that exists nowhere in MITgcm (`Ri_iwmix` uses `dblocSm*Δz/MAX(shsq, phepsi)`). The parser's own comment at line 661 already says so. |
| `ghat` | declared on `('x','y','z')`, `cell_location: center` | a bottom-face array |

### Evidence
FABLE_FINDS.md §C4 (library review, 2026-10-02; the owner directed acceptance as correct). The parser table was re-read on 2026-10-02, and the instrumented writes were read by two library authors. A library harness that compared Oceananigans' N² with `buoy_freq_sq` hit exactly this. Detail: `../MITgcm_porting_wisdom/Verification_and_Validation/04_io_schema_and_netcdf.md`.

### Scientific or engineering impact
The values are right, and the port is fed what `KPPMIX` receives. Anyone who trusts the metadata is off by a layer thickness.

### Proposed action and acceptance
Rename to `dbloc` and `shsq`, correct the units and locations, and drop or rename `richardson`. Keep read compatibility for existing captures or migrate them.

Acceptance: a regenerated capture carries the correct names, units and locations, and every reader of the old names is updated. Replays are bit-identical.

## UNRESOLVED: captures lack `deltaT` (KPP), `eosType`, `selectP_inEOS_Zc`, tile sizes and the MITgcm commit; the attribute is `conventions`, not `Conventions`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-095
**Anchors**: `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py`; `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py`

### Issue or research question
Two KPP input files were checked (`…1D_10_kppmix_extend_rawflux_fix.nc` and `…global_oce_latlon_720.nc`, 220 attributes each). They have no `deltaT`, `eosType`, `selectP_inEOS_Zc`, `useRealFreshWaterFlux`, tile sizes or MITgcm commit. The global attribute is `conventions`, where CF requires `Conventions`. The `build_info.txt` and `run_info.txt` written by `MITgcm_verification_docker` record neither the MITgcm commit nor a hash of the mods tree.

### Evidence
FABLE_FINDS.md §C5 (library review, 2026-10-02; the owner directed acceptance as correct). Read from the two capture files on 2026-10-02.

### Scientific or engineering impact
The EOS a capture ran with, its time step and the `external_forcing_surf.F` branch that formed the salt flux cannot be read from the file. A replay has to trust the experiment's `data` file.

### Proposed action and acceptance
Print and parse these values at the next recapture (with 1DMIX-094 and 1DMIX-096). Record the MITgcm commit and a mods-tree hash in the build records, and rename the attribute to `Conventions`.

Acceptance: a new capture carries every listed attribute. The replay refuses a capture whose `eosType` the port does not implement.

## UNRESOLVED: the GGL90 capture prints `dTtracerLev(1)`; the routine uses `dTtracerLev(kSrf)`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-096
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`; `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py`

### Issue or research question
`ggl90_mods/ggl90_calc.F` line 254 uses `deltaTloc = dTtracerLev(kSrf)`, while line 1395 prints `'PARAM_deltaT=',dTtracerLev(1)`. The file's own comment at line 1391 notes the difference.

### Evidence
FABLE_FINDS.md §C6 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
The two are equal in z-coordinates with a uniform tracer time step. They differ in a pressure-coordinate run (now accepted since 1DMIX-073) or with a level-dependent `dTtracerLev`.

### Proposed action and acceptance
Print `dTtracerLev(kSrf)`, or both values, in every instrumented `ggl90_calc.F` copy at the next recapture.

Acceptance: the printed value is the one the routine uses, and the parser reads it.

## UNRESOLVED: the 1DMIX-046 "preserved lesson" about COMMON blocks is false

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-097
**Anchors**: `closed_issues.md`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/ggl90_standalone_main.F`

### Issue or research question
`closed_issues.md` (line 1440) says that COMMON-block variables assigned in a wrapper's main program are not visible to subroutines, and that later drivers avoid this by using the `genmake2` build. Fortran COMMON storage is global. `ggl90_standalone_main.F` assigns COMMON arrays in its main program and is built by its own script without `genmake2`, yet it reproduces the full model bit for bit. The real cause of the abandoned wrapper's failure was never established.

### Evidence
FABLE_FINDS.md §D2 (library review, 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
A false lesson in the record, which future work could follow.

### Proposed action and acceptance
Add a correction with a forward pointer to the 1DMIX-046 entry, and correct any lesson or document that repeats the claim.

Acceptance: a grep for the claim finds only corrected text.

## UNRESOLVED: 1DMIX-069 and the mods README call an upstream MITgcm loop-bound bug a "transcription error"

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-098
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/README.md`; `closed_issues.md`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`

### Issue or research question
`mitgcm_verification_mods/README.md` (line 109) and ledger 1DMIX-069 describe `DO i=jMin,jMax` in the instrumented `ggl90_calc.F` as a transcription error. It was an upstream bug:
- **MITgcm history** (`git log -S'DO i=jMin,jMax' -- pkg/ggl90/ggl90_calc.F`): introduced by `f18a893d4` (2022-08-02, "ggl90 with shelfice (#597)") and fixed by `09a9aa1d4` (2026-08-10, "Fix loop limits in pkg/ggl90/ggl90_calc.F").
- **Reviewer diff:** a library reviewer diffed the pre-correction instrumented file against the older upstream source and found zero changed stock lines.

What happened: the instrumented file was derived from an older MITgcm and compiled into a newer checkout. `-mods` replaces whole files, so the upstream fix was silently dropped. Captures built between the checkout update and 2026-09-30 ran a hybrid of a new model and an old package file. The bug was dormant in all of them because the tiles were square.

### Evidence
FABLE_FINDS.md §D3 (library review, 2026-10-02; the owner directed acceptance as correct). `git log` was re-run and the README line re-read on 2026-10-02. Detail: `../MITgcm_porting_wisdom/Verification_and_Validation/06_instrumenting_mitgcm.md` and `17_identifying_mitgcm_bugs.md`.

### Scientific or engineering impact
The record misattributes the cause and hides the real hazard: an instrumented file silently drops upstream fixes when the checkout moves.

### Proposed action and acceptance
Correct the README and add a forward-pointing correction to 1DMIX-069. Record the MITgcm commit each instrumented file was derived from, and add a check that re-derives or diffs them whenever the checkout moves.

Acceptance: every instrumented file names its base commit, and a script reports any upstream change to the stock lines since that commit.

## UNRESOLVED: "Issue 1" of `possible_kpp_bugs_in_mitgcm.md` is not an MITgcm bug

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-099
**Anchors**: `MITgcm_to_Python_port_verification/KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md`

### Issue or research question
The report's Issue 1, "Missing hbl Regularization in BLMIX", says `hbl` can reach a division unregularized. But:
- `kpp_routines.F` line 799, at the end of `bldepth`, sets `hbl(i) = MAX(hbl(i),minKPPhbl)`;
- `kpp_init_fixed.F` lines 162–163 set `minKPPhbl = -rC(1)` when it is left unset;
- `KPPMIX` changes nothing between `bldepth` and `blmix`.

The only real routes to a non-positive `hbl` are a user setting `minKPPhbl = 0`, and pressure coordinates, where `-rC(1)` is negative. Issue 2, the `wscale` lookup-table extrapolation with its fix sitting commented out, stands. The ledger records no upstream submission of either.

### Evidence
FABLE_FINDS.md §D4 (library review, 2026-10-02; the owner directed acceptance as correct). All three source lines were re-read on 2026-10-02.

### Scientific or engineering impact
If Issue 1 were sent upstream, it would be a false bug report against MITgcm.

### Proposed action and acceptance
Mark Issue 1 withdrawn in the report, with the three source lines and the two real routes, and keep Issue 2.

Acceptance: the report no longer presents Issue 1 as a bug, and nothing about it goes upstream.

## UNRESOLVED: the account that only `combined_storm` reached the `wscale` lookup-table extrapolation is wrong

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-100
**Anchors**: `closed_issues.md`; `MITgcm_to_Python_port_verification/KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md`; `MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`

### Issue or research question
The received account is that only the `combined_storm` scenario reached the extrapolating branch. The project's own final resolutions (1DMIX-056 and -057) show that all four real KPP captures entered it, at 1.2% to 12.9% of evaluations, and that two other scenarios entered it with no measurable effect. The disagreement was in the real captures all along and had been attributed to threshold sensitivity.

### Evidence
FABLE_FINDS.md §D5 (library review, 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
Documents understate where MITgcm's extrapolation acts, and misattribute part of the residual.

### Proposed action and acceptance
Find every statement of the received account and correct it to the 1DMIX-056/-057 figures, with a pointer.

Acceptance: a grep finds no statement that only `combined_storm` reaches the branch.

## UNRESOLVED: the root `README.md` status section is stale

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-101
**Anchors**: `README.md`

### Issue or research question
`README.md` lines 21–35 say three things that were superseded weeks ago:
- "KPP port: validated against MITgcm";
- that the outliers come from floating-point behaviour near the critical Richardson number;
- that the GGL90 port is "not yet put through the MITgcm capture-and-compare pipeline".

### Evidence
FABLE_FINDS.md §D6 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
The project's front page misstates its validation status.

### Proposed action and acceptance
Rewrite the status section from the current results documents and the open issues, stating the residuals and pointing to the ledger rather than restating figures.

Acceptance: every status statement is traceable to a current results document.

## UNRESOLVED: the `.tex` package and port descriptions contain factual errors

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-102
**Anchors**: `Vertical_Mixing_Models/docs/KPP/KPP_package_description.tex`; `Vertical_Mixing_Models/docs/GGL90/GGL90_package_description.tex`; `Vertical_Mixing_Models/docs/KPP/KPP_port_description.tex`; `Vertical_Mixing_Models/docs/GGL90/GGL90_port_description.tex`

### Issue or research question
Found by the library's documentation author and reviewer, who opened each description against the MITgcm source. Two errors were re-read on 2026-10-02:
- **`dsfmax`:** `KPP_package_description.tex` line 659 gives `dsfmax` as 10⁻³. MITgcm has `dsfmax = 10. _d -3`, which is 1e-2 (`kpp_readparms.F` line 143), and the port has 1e-2. An archived review "corrected" the right value to the wrong one by misreading the literal.
- **Trailing text:** `GGL90_package_description.tex` has 473 lines after `\end{document}` (line 4067 of 4540).

As recorded by the reviewer, not re-read on 2026-10-02:
- eight duplicated labels in the GGL90 package description;
- a listing captioned as verified against the real MITgcm source that cites the wrong line range, drops a three-line adjoint-directive block and adds a comment not in the source;
- invented names in the KPP port description (`KPPRicr`, `KPPVtc`, a `zref = 10.0 m` parameter);
- a reference to a non-existent `main/convective_adjustment.py`;
- stale Python line ranges;
- salt plume listed as excluded while `kpp_salt_plume.py` exists.

### Evidence
FABLE_FINDS.md §D7 (library review, 2026-10-02; the owner directed acceptance as correct). Detail, with an error catalogue of 16 classes: `../MITgcm_porting_wisdom/Documentation/02_documenting_the_original_parameterization.md`.

### Scientific or engineering impact
The descriptions are useful for their outline but unreliable as fact sources. One wrong default (`dsfmax`) is still present.

### Proposed action and acceptance
Correct each listed error against the MITgcm source and the port. Remove the text after `\end{document}`. Replace line ranges with symbol names where possible.

Acceptance: each item is fixed or shown not present, and the documents compile without duplicate-label warnings.

## UNRESOLVED: `critical_lessons_fortran_to_python_porting.md` still teaches `pressure = -depth`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-103
**Anchors**: `MITgcm_to_Python_port_verification/KPP_port_validation/reports/critical_lessons_fortran_to_python_porting.md`

### Issue or research question
Lines 254–277 conclude `pressure = -depth` (1 dbar per metre). 1DMIX-039 established that MITgcm's EOS pressure is `rhoConst*gravity*|z|*1e-5` bar, which is 0.8–1.9% away from that.

### Evidence
FABLE_FINDS.md §D8 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
A "critical lessons" document teaches a superseded rule.

### Proposed action and acceptance
Correct the passage to the 1DMIX-039 rule, with a pointer.

Acceptance: a grep for the old rule in teaching documents finds only corrected text.

## UNRESOLVED: physical constants are not single-sourced; `KPP_PHYSICAL_PARAMETERS_YAML` is set in eight files and read by none

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-104
**Anchors**: `Vertical_Mixing_Models/main/run_scenarios.py::run_one`; `Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters`; `Vertical_Mixing_Models/configuration_yamls/physical_parameters.yaml`

### Issue or research question
`run_one` builds `KPPParameters.from_yaml(kpp_yaml)` without passing `gravity`, `rho_const` or `heat_capacity_cp` from `configuration_yamls/physical_parameters.yaml`, and `KPPParameters` has its own defaults (lines 222–224).

`KPP_PHYSICAL_PARAMETERS_YAML` is assigned in eight files and read by none. The files are `main/run_scenarios.py`, `main/run_experiment_example.py`, `tests/test_staggering.py`, `tests/test_full_scenario_validation.py`, three `scripts/analysis/*.py`, and `MITgcm_to_Python_port_verification/scripts/export_scenario_to_ggl90_driver.py`.

### Evidence
FABLE_FINDS.md §A4 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02, with a grep of the whole project.

### Scientific or engineering impact
None today, because the YAML values equal the dataclass defaults and replays take constants from the capture. But changing the YAML would change the driver's constants and not KPP's.

### Proposed action and acceptance
Pass the physical constants into both parameter classes in `run_one`, and delete the environment variable.

Acceptance: a test shows that changing `physical_parameters.yaml` changes KPP's and GGL90's constants. Scenario outputs are bit-identical with the current YAML.

## UNRESOLVED: the linear-EOS branch of the GGL90 N² function has the wrong sign

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-105
**Anchors**: `Vertical_Mixing_Models/main/eos.py::compute_ggl90_buoyancy_frequency_squared`; `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py`

### Issue or research question
In the `else` branch (lines 771–778), `depth` is negative downward, so `dz = depth[k] - depth[k-1] < 0`. For a stable column `rho[k-1] - rho[k] < 0`, so the quotient is positive, and `n_square = -(g/rho0)*drho_dz` comes out negative.

### Evidence
FABLE_FINDS.md §A8 (library review, 2026-10-02; the owner directed acceptance as correct). Re-run on 2026-10-02 with a stable column (T 20 → 10 °C, S = 35): `use_jmd95=True` gives +2.7e-4 s⁻², and `use_jmd95=False` gives −2.2e-4 s⁻².

### Scientific or engineering impact
None today: the only caller (`ggl90_core_driver.py` line 442) hard-codes `use_jmd95=True`. The branch is wrong the day it is switched on.

### Proposed action and acceptance
Correct the sign or delete the branch.

Acceptance: a test shows the linear branch gives positive N² on a stable column, consistent with the JMD95 branch, or the branch is removed and its callers refuse the option.

## UNRESOLVED: `compute_bl_mixing` returns seven values on its `hbl == 0` path; the caller unpacks five

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-106
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py::compute_bl_mixing`; `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`

### Issue or research question
The `hbl == 0.0` guard returns seven values (line 473 at the time of the finding). The normal path returns five, the last a tuple (line 669). The caller (`kpp_core_driver.py` line 550) unpacks five.

### Evidence
FABLE_FINDS.md §A11 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. The guard is not reached in any current run.

### Scientific or engineering impact
If the guard is ever reached (for example `minKPPhbl = 0`, or pressure coordinates; see 1DMIX-099), the caller raises a `ValueError` on unpacking instead of returning zero mixing. In the replay harness that exception becomes a NaN cell (1DMIX-090).

### Proposed action and acceptance
Make the guard return the same shape as the normal path, with the values MITgcm would produce for `hbl = 0`, or raise a clear error if MITgcm cannot reach it.

Acceptance: a test drives `hbl == 0` through `KPPDriver.compute_mixing` and checks the result.

## UNRESOLVED: `GGL90Parameters.use_idemix` is accepted, never read, and not mapped from captures

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-107
**Anchors**: `Vertical_Mixing_Models/GGL90/ggl90_parameters.py::GGL90Parameters`; `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py`

### Issue or research question
`use_idemix` (line 179) is accepted and printed but never read by the physics. No script maps a capture's `useIDEMIX` to it (grep of `MITgcm_to_Python_port_verification/scripts`). It is the sibling of 1DMIX-074 (`calc_mean_vert_shear`).

### Evidence
FABLE_FINDS.md §A12 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
A capture made with IDEMIX on would be replayed with no sign that the port lacks it.

### Proposed action and acceptance
Raise `NotImplementedError` when the flag is `True`, and map the capture attribute so the harness refuses such a capture. Consider resolving this together with 1DMIX-074.

Acceptance: tests show `use_idemix=True` raises, and a capture with `useIDEMIX` set is refused. Default behaviour is bit-identical.

## UNRESOLVED: the column driver applies `ivdc_kappa` together with KPP, a configuration MITgcm refuses

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-108
**Anchors**: `Vertical_Mixing_Models/main/unified_driver.py`

### Issue or research question
`unified_driver.py` applies `ivdc_kappa` on top of whatever scheme is active. MITgcm's `pkg/kpp/kpp_check.F` (lines 128–129) stops the model when `cAdjFreq != 0` or `ivdc_kappa != 0` with KPP. `pp81_check.F` does the same; `ggl90_check.F` only prints a notice.

### Evidence
FABLE_FINDS.md §A13 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02.

### Scientific or engineering impact
The port can run a configuration MITgcm refuses, so there is no reference for it. Combined with 1DMIX-081, the step also does not do what MITgcm's does.

### Proposed action and acceptance
Refuse `ivdc_kappa != 0` with KPP with a ValueError, as `kpp_check.F` does. Keep GGL90's behaviour, and print a notice as `ggl90_check.F` does.

Acceptance: tests cover both schemes, and the scenarios are unaffected.

## UNRESOLVED: minor parameter-class untidiness: duplicated `epsln`/`phepsi`, unused `to_dict()`, and a wrong GGL90 `alpha` default in the port description

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-109
**Anchors**: `Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters`; `Vertical_Mixing_Models/KPP/kpp_core_driver.py`; `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py`; `Vertical_Mixing_Models/docs/GGL90/GGL90_port_description.tex`

### Issue or research question
- **Duplicated fields:** `KPPParameters` declares `epsln` and `phepsi` twice (lines 87–88 and 227–228). The values are the same today, and the second silently wins.
- **Unused methods:** `KPPOutput.to_dict()` and `GGL90Output.to_dict()` are never called (grep).
- **`alpha` default:** `GGL90/ggl90_default_parameters.yaml` sets `alpha: 10.0` on purpose and says so, whereas MITgcm's default is 1.0 (`ggl90_readparms.F` line 110). But `GGL90_port_description.tex` line 566 still says "(default: 1.0)". A caller relying on the port's defaults does not reproduce MITgcm's.

### Evidence
FABLE_FINDS.md §A14 (library review, 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
Tidiness, plus one documentation statement about a physics default that is wrong.

### Proposed action and acceptance
Remove the duplicate declarations. Delete or test the `to_dict()` methods. Correct the description's `alpha` default and state where the port's default departs from MITgcm's.

Acceptance: each field is declared once, and the description matches the YAML and names MITgcm's value.

## UNRESOLVED: the GGL90 standalone driver forms `drC` differently from the model

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-110
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/ggl90_standalone_main.F`

### Issue or research question
The driver (lines 153–161) uses `drC(k) = rC(k-1) - rC(k)`, while the model (`ini_vertical_grid.F`) uses `0.5*(delR(k-1)+delR(k))`. These are algebraically equal but not guaranteed to be bit-equal.

### Evidence
FABLE_FINDS.md §B2 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. The difference has not been observed: in a library run the driver reproduced the full-model `vermix` capture bit for bit on 2,080 of 2,080 values.

### Scientific or engineering impact
A latent last-bit trap for other grids.

### Proposed action and acceptance
Form `drC` as `ini_vertical_grid.F` does.

Acceptance: the driver still reproduces the `vermix` capture bit for bit, and a non-uniform grid case matches the model's `drC` exactly.

## UNRESOLVED: the GGL90 driver build reads option headers from a leftover `code_validation` directory in the MITgcm tree

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-111
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_standalone_driver/build_and_run.sh`

### Issue or research question
`build_and_run.sh` lines 28–31 set `PKGCONFIG_DIR="$VERMIX_DIR/build_docker_ggl90_1dmix024"` and `CPPOPTS_DIR="$VERMIX_DIR/code_validation"`. `verification/<exp>/code_validation` holds whatever the last `experiment_compile.sh -mods` left there, not the tree in this repository, so a later `-mods` build of another variant changes what the driver compiles against. The script also writes its build products into the tracked driver directory. A library author needed an extra `-Ipkg/generic_advdiff` to build it out of tree.

### Evidence
FABLE_FINDS.md §B3 (library review, 2026-10-02; the owner directed acceptance as correct). Script re-read on 2026-10-02.

### Scientific or engineering impact
A hidden, mutable build dependency: driver results may not be reproducible from this repository.

### Proposed action and acceptance
Point the build at `mitgcm_verification_mods/vermix/code_validation` in this repository, build out of tree, and add the needed include path.

Acceptance: a clean build from this repository alone reproduces the `vermix` driver results bit for bit.

## UNRESOLVED: replay harnesses find the wet range from `theta != 0.0`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-112
**Anchors**: `MITgcm_to_Python_port_verification/scripts/run_ggl90_from_netcdf_input.py`; `MITgcm_to_Python_port_verification/scripts/run_kpp_from_netcdf_input.py`

### Issue or research question
`run_ggl90_from_netcdf_input.py` line 125 and `run_kpp_from_netcdf_input.py` line 509 both use `wet = np.flatnonzero(theta != 0.0)`.

### Evidence
FABLE_FINDS.md §B5 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. No case has been observed.

### Scientific or engineering impact
A wet cell at exactly 0 °C is treated as land.

### Proposed action and acceptance
Use the captured mask or `hFacC`, adding them to the capture if missing (see 1DMIX-095).

Acceptance: a test with a 0 °C wet cell keeps it wet, and replays of the existing captures are bit-identical.

## UNRESOLVED: the instrumentation is not thread-safe and prints no tile size or process offset

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-113
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_mods/kpp_calc.F`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`; `MITgcm_to_Python_port_verification/scripts/capture_stream.py`

### Issue or research question
The instrumentation writes to the standard message unit with no lock, and prints no tile size, tile count or global offset. The parser infers the tile size from the largest index seen.

### Evidence
FABLE_FINDS.md §B8. Library run on `lab_sea` (9 steps, five layouts), re-run by a reviewer from the saved captures. Script: `../MITgcm_porting_wisdom/Verification_and_Validation/code_appendix/16_compare_tile_layouts.py`.
- **2 MPI processes:** bitwise identical to serial in all 163,350 records, once the two `STDOUT.000N` files are merged with the right offset. But both files label their tiles `BI=1`, and the parser accepts one file alone as a complete 10×16 domain.
- **2 threads:** the capture is corrupt (6,012 conflicting keys, 68,581 records missing), yet it still parses without error.

### Scientific or engineering impact
A threaded capture is silently corrupt, and a single MPI part-file parses as the whole domain.

### Proposed action and acceptance
Print `sNx`, `sNy`, `nSx`, `nSy`, `myXGlobalLo` and `myYGlobalLo` in the header. Refuse to run the instrumented build with `nTx*nTy > 1`. Make the parser check completeness against the printed layout.

Acceptance: a single MPI part-file is refused as incomplete, a threaded build refuses to run, and the existing captures still parse.

## UNRESOLVED: `kpp_mods/kpp_calc.F` still uses a level-1 land test and one literal `WRITE(6,…)`

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-114
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_mods/kpp_calc.F`

### Issue or research question
- **Land test:** line 1258 still uses the level-1 land test (`IF ( maskC(i,j,1,bi,bj) .EQ. 0. ) CYCLE`). The GGL90 instrumentation was changed to test all levels because ice-shelf columns are dry at the top; KPP's was not.
- **Message unit:** line 906 has a literal `WRITE(6,…)` where every other write uses `standardMessageUnit`.

### Evidence
FABLE_FINDS.md §B9 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. No effect has been observed.

### Scientific or engineering impact
A KPP ice-shelf capture would silently skip columns that are dry at the top, and one write bypasses the message unit.

### Proposed action and acceptance
Apply the GGL90 all-levels land test and use `standardMessageUnit`, in `kpp_mods` and every per-experiment copy.

Acceptance: all KPP instrumented copies agree on both points, and a rebuilt capture is unchanged on the existing experiments.

## UNRESOLVED: `compare_ggl90.py` does not check `input_uuid`, prints a fixed "Python port" banner and fails on an absent variable

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-115
**Anchors**: `MITgcm_to_Python_port_verification/scripts/compare_ggl90.py`

### Issue or research question
The script prints the fixed banner "MITgcm vs. Python port" whatever it is given (line 54). It does not check that the two files' `input_uuid` values match, and it fails when a variable is absent.

### Evidence
FABLE_FINDS.md §B10 (library review, 2026-10-02; the owner directed acceptance as correct). The banner was re-read on 2026-10-02. The rest was reported by the Julia-chapter author and reviewer, who fed the script another code's output.

### Scientific or engineering impact
Two unrelated files can be compared without warning, and the output mislabels what was compared.

### Proposed action and acceptance
Refuse mismatched `input_uuid` values, label the banner from the files' metadata, and report absent variables by name.

Acceptance: tests cover a mismatched uuid (refused), an absent variable (named), and a non-port file (correct banner).

## UNRESOLVED: the KPP `global_oce_latlon` capture is a constructed build, not a stock experiment

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-116
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_oce_latlon/input_validation/README.md`; `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md`

### Issue or research question
Stock `verification/global_oce_latlon/code/packages.conf` does not compile KPP. The capture was built from a forward variant assembled from the former `code_oad` / `input_oad.kpp` configuration (see the `input_validation/README.md`). That configuration is no longer in the pinned MITgcm tree, which now has only `code_ad` and `code_tap`. Its `KPP_OPTIONS.h` undefines `KPP_GHAT` and all smoothing.

### Evidence
FABLE_FINDS.md §C2 (library review, 2026-10-02; the owner directed acceptance as correct). The README, `packages.conf` and the options header were re-read on 2026-10-02.

### Scientific or engineering impact
Statements that this capture exercises a stock MITgcm KPP experiment are wrong. It bears on how the global_oce_latlon residuals in 1DMIX-076 are read.

### Proposed action and acceptance
Give it the same CONSTRUCTED label and per-setting justification as the other constructed experiments, and correct any document that calls it stock.

Acceptance: CAPTURES.md labels it constructed, with its provenance, and a grep finds no "stock" claim for it.

## UNRESOLVED: the `vermix` GGL90 capture is a weak reference for the coefficient formula, and `test_vermix_clean_bit_level` asserts only 1%

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-117
**Anchors**: `MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py::test_vermix_clean_bit_level`

### Issue or research question
On the `vermix_20` capture only 25 of 500 interior cells are off a background floor. `test_vermix_clean_bit_level` (line 140) asserts only `max_rel < 0.01`, so "bit-level" in its name is a misnomer.

### Evidence
FABLE_FINDS.md §C7. Library run, re-run by a reviewer (`../MITgcm_porting_wisdom/Porting_MITgcm_to_Julia_Oceananigans/code_appendix/08_python_to_julia_kernels.jl`). A translation of the coefficient formula matched MITgcm in 520 of 520 cells, and so did a mutant with the TKE floor dropped.

### Scientific or engineering impact
"520 of 520 cells agree" on this capture says little about the formula, and the test's name overstates what it checks.

### Proposed action and acceptance
Add a non-vacuity assertion: the count of cells off the floor, with a minimum. Rename the test or tighten it to its measured figure under an existing convention. Add or identify a capture that exercises the formula off the floor.

Acceptance: a dropped-floor mutant fails at least one GGL90 test.

## UNRESOLVED: `vermix` runs `MDJWF` with `selectP_inEOS_Zc = 2`, the port has neither, and `eos.py` documents it wrongly

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-118
**Anchors**: `Vertical_Mixing_Models/main/eos.py`; `MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py`; `MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`

### Issue or research question
`vermix` runs `eosType='MDJWF'` (`verification/vermix/input/data` line 24). For that EOS, `set_parms.F` (lines 275–281) sets `selectP_inEOS_Zc = 2`, so MITgcm takes the EOS pressure from the model's own hydrostatic pressure. A library author confirmed this in the `vermix` STDOUT echo.

The port implements JMD95 with a depth-derived pressure only. The parser text already notes the EOS mismatch (`parse_mitgcm_ggl90_split.py` line 236), and the harness feeds the captured `sigmaR` to avoid it. The `eos.py` module docstring (lines 34–37) wrongly lists `vermix` among the experiments on the "non-iterative reference-pressure branch, `selectP_inEOS_Zc<=1`" (FABLE_FINDS.md §A15).

The GGL90 results document gives no cause for the 0.07–0.31% maximum relative differences on `vermix`, while the other single-column capture is at roundoff. Hypothesis: some remaining density-dependent quantity in the replay is still computed with JMD95 at a depth-derived pressure. This has not been tested.

### Evidence
FABLE_FINDS.md §C8 and §A15 (library review, 2026-10-02; the owner directed acceptance as correct). The docstring, `set_parms.F`, the `data` file and the parser text were re-read on 2026-10-02.

### Scientific or engineering impact
An unexplained GGL90 residual on a single-column capture, and a wrong documented physics assumption.

### Proposed action and acceptance
Correct the docstring. Then test the hypothesis by finding every density-dependent quantity in the `vermix` replay and substituting captured values.

Acceptance: the 0.07–0.31% residual is explained with file and line and fixed, or documented as an EOS limitation. The docstring states the branch correctly.

## UNRESOLVED: the `lab_sea` secondary input set `hb87` fails `testreport` at 5 digits in every build tried

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-119
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/lab_sea/code_validation/SIZE.h`; `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md`

### Issue or research question
The secondary input set `input.hb87` matches the reference output to only 5 digits in every build tried, including the stock 2×2 layout at `-O0`. The primary set passes at 16 digits in the stock layout. All those builds used the instrumented sources, so this may be the platform, the toolchain or the instrumentation.

### Evidence
FABLE_FINDS.md §C9 (library run; the owner directed acceptance as correct). Detail: `../MITgcm_porting_wisdom/Verification_and_Validation/15_platform_specific_testing.md`.

### Scientific or engineering impact
Unexplained. If the instrumentation causes it, captures from instrumented builds are not faithful to stock behaviour.

### Proposed action and acceptance
Run `testreport` on stock `lab_sea` `hb87` with no `-mods`, in the project's Docker toolchain.

Acceptance: the cause is placed in the platform, the toolchain or the instrumentation, and recorded. If it is the instrumentation, it is fixed or bounded.

## UNRESOLVED: no capture holds the state after the implicit vertical solve

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-120
**Anchors**: `Vertical_Mixing_Models/main/unified_driver.py`; `docs/model_contract.md`

### Issue or research question
No capture holds the state after `IMPLDIFF`. The port's diffusion operator, its placement of the non-local term, and the unified driver's time stepping have therefore never been compared with MITgcm; only the coefficients have.

### Evidence
FABLE_FINDS.md §C10 (library review, 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
A verification gap covering everything downstream of the mixing coefficients in the scenario runs.

### Proposed action and acceptance
Instrument the post-`IMPLDIFF` tracer and velocity state (and the `ghat` application) in one single-column experiment. Replay one step of the port's solver from the captured pre-solve state.

Acceptance: one-step post-solve T, S, U and V agree with MITgcm within a stated tolerance, with a non-vacuity count, and the non-local term's placement is confirmed.

## UNRESOLVED: scenario provenance contradicts its own step count (`combined_storm` and one other scenario)

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-121
**Anchors**: `Vertical_Mixing_Models/simulations/scenarios/scenario_combined_storm_time_integration.yaml`

### Issue or research question
`scenario_combined_storm_time_integration.yaml` has `duration_hours: 24.0`, `dt_seconds: 3600.0` and `n_steps_formula: round(duration_hours*3600/dt_seconds)`, which gives 24. But it also has `n_steps: 72`. A library checker (`../MITgcm_porting_wisdom/Verification_and_Validation/code_appendix/08_check_scenario.py`) flagged stale provenance in two of the six scenarios.

### Evidence
FABLE_FINDS.md §C11 (library review, 2026-10-02; the owner directed acceptance as correct). Re-read on 2026-10-02. The second scenario is not named in the findings.

### Scientific or engineering impact
The run length a scenario actually uses cannot be trusted from its own description.

### Proposed action and acceptance
Find both scenarios, determine which value the runner uses, and make the provenance consistent. Add a test that checks `n_steps` against the formula for every scenario.

Acceptance: the test passes for all six scenarios, and scenario outputs are unchanged unless the run length is corrected deliberately and recorded.

## UNRESOLVED: dead or always-skipping code presented as live

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-122
**Anchors**: `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py`; `Vertical_Mixing_Models/generate_extreme_scenario_yamls.py`

### Issue or research question
- `test_mitgcm_kpp_lab_sea_validation.py` points at `mitgcm_instrumentation/lab_sea_kpp_data.h5`, in a tree that no longer exists, so it always skips. It is the only test asserting `rtol=1e-12`.
- `generate_extreme_scenario_yamls.py` documents and imports `KPP_PY/extreme_scenarios.py`, which does not exist.

### Evidence
FABLE_FINDS.md §D9 (library review, 2026-10-02; the owner directed acceptance as correct). Both re-read on 2026-10-02.

### Scientific or engineering impact
A skipped test looks like coverage, and the strictest tolerance in the suite is never applied.

### Proposed action and acceptance
Point the lab_sea test at a current capture and keep its tolerance only if it passes as measured, or delete it. Fix or delete the generator.

Acceptance: no test skips because of a missing legacy path, and every skip in the full pytest run is explained.

## UNRESOLVED: `kpp_mods/kpp_calc.F.bak` is neither stock nor current

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-123
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/kpp_mods/kpp_calc.F.bak`

### Issue or research question
It differs from stock `pkg/kpp/kpp_calc.F` in 434 lines, and also from the current instrumented file. It is an earlier instrumented version, not a copy of stock as one survey described it.

### Evidence
FABLE_FINDS.md §D10 (library review, 2026-10-02; the owner directed acceptance as correct). Compared on 2026-10-02 with `cmp` and `diff`.

### Scientific or engineering impact
A misleading file in the mods tree.

### Proposed action and acceptance
Delete it (git history keeps it), or rename and describe it.

Acceptance: no file in the mods tree is mistaken for stock.

## UNRESOLVED: capture recipes marked INFERRED, and capture files read by tests but not declared as external inputs

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-124
**Anchors**: `MITgcm_to_Python_port_verification/KPP_port_validation/CAPTURES.md`; `MITgcm_to_Python_port_verification/GGL90_port_validation/CAPTURES.md`; `esx/project.json`

### Issue or research question
Five capture recipes are marked INFERRED in the two `CAPTURES.md` files, and 17 capture files are read by tests but not declared as external inputs.

### Evidence
FABLE_FINDS.md §D11 (reported by the library's worked-example and V&V authors; not re-read on 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
Reference data whose provenance is reconstructed, and test inputs outside the declared input contract.

### Proposed action and acceptance
Recover or reconstruct each INFERRED recipe and verify it by rebuilding where feasible, or keep the label with the reason. Declare all 17 files as external inputs with hashes.

Acceptance: every file a test reads is declared, and every recipe is verified or labelled with its reason.

## UNRESOLVED: ledger entries cite evidence receipts and scratch scripts that no longer exist

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-125
**Anchors**: `closed_issues.md`; `devel-loop/documentation_contract.md`

### Issue or research question
Evidence receipts that the ledger cites by hash lived under the git-ignored `devel-loop/loop_state/` and were lost in the host move. The same applies to several decisive scratch scripts.

### Evidence
FABLE_FINDS.md §D11 (reported by the library's worked-example and V&V authors; not re-read on 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
Closed conclusions cannot be re-checked from the evidence they cite.

### Proposed action and acceptance
Identify the closed entries whose decisive evidence is lost, and annotate each. Decide where decisive scripts and receipts must be kept so that they survive a host move, for example a tracked evidence directory.

Acceptance: each affected entry states that its receipt is lost, and the retention rule is recorded in the project profile or the documentation contract.

## UNRESOLVED: the validation result documents contain about 30 issue-id citations each, against their stated criterion of none

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-126
**Anchors**: `MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`; `MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`

### Issue or research question
The two validation result documents contain about 30 issue-id citations each, against a stated acceptance criterion of none.

### Evidence
FABLE_FINDS.md §D11 (reported by the library's worked-example and V&V authors; not re-read on 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
The results documents do not meet their own standard, and they depend on the ledger to be read.

### Proposed action and acceptance
Count the citations, then either restate each cited point in place or revise the criterion with its reason.

Acceptance: the documents meet whichever criterion is recorded.

## UNRESOLVED: `mitgcm_verification_mods/TAF_*.md` are stale

**Date Identified**: 2026-10-02T21:47:00Z
**Status**: Unresolved
**UUID**: 1DMIX-128
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/TAF_DOCKER_USAGE.md`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/TAF_QUICK_START.md`

### Issue or research question
The TAF documents give paths from the previous host, and they predate the toolchain's `-adm`/`-tlm` support.

### Evidence
FABLE_FINDS.md §D11 (reported by the library's worked-example and V&V authors; not re-read on 2026-10-02; the owner directed acceptance as correct).

### Scientific or engineering impact
The instructions do not work as written.

### Proposed action and acceptance
Update them to the current host and toolchain, or move them to the documentation archive.

Acceptance: the documents describe a procedure that runs on this host, or are archived.
