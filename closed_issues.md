# Closed issues

Move completed entries here using the original UUID. Status is Resolved or False
Positive. Preserve the evidence and the scientific bounds of the conclusion.

```markdown
## RESOLVED: <Brief title>

**Date Identified**: <UTC ISO timestamp>
**Date Resolved**: <UTC ISO timestamp>
**Status**: Resolved
**UUID**: <Original ID>

### Issue
<Original contract violation or question>

### Resolution and justification
<Implemented behavior or evidence establishing the finding>

### Verification and remaining bounds
<Regression witness, independent check, final suite receipts and untested conditions>

### Traceability
<Commit SHA or noncommit reason; iteration history/evidence references; related blockers>
```

## RESOLVED: GGL90 density gradient used in-situ instead of potential density

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-07-20T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-001

### Issue
GGL90 computed N² (buoyancy frequency squared) from in-situ density gradients. MITgcm's `grad_sigma.F` / `do_oceanic_phys.F` instead evaluate adjacent levels at a common reference pressure (potential density) before differencing. Including compressibility effects overestimated stratification in deep water (>1000 m) and could over-suppress mixing there.

### Resolution and justification
Added `compute_ggl90_buoyancy_frequency_squared()` in `1D_Mixing_Model/main/eos.py`; updated `main/mixing_adapter.py` and `GGL90/ggl90_core_driver.py` to call it, matching MITgcm's potential-density convention.

### Verification and remaining bounds
Migrated from the Three-Man-Team era `potential_bugs_and_inconsistencies.md`; no fresh ESX verification receipt exists for this historical fix (no `tools/esx/verify.py` evidence hash) — treat as source-evidence-supported, not re-verified under the current regime. Full derivation archived at `OLD_MARKDOWN_NO_LONGER_NEEDED/three-man-team-archive/GGL90_DENSITY_GRADIENT_FIX_SUMMARY.md` and `DENSITY_GRADIENT_ANALYSIS.md`.

### Traceability
No commit SHA recorded (root was not git-tracked at the time). Related archived record: `OLD_MARKDOWN_NO_LONGER_NEEDED/three-man-team-archive/potential_bugs_and_inconsistencies.md`.

---

## RESOLVED: Pressure conversion used `-depth/10.0` instead of `-depth`

**Date Identified**: historical, audited 2026-07-20T00:00:00Z
**Date Resolved**: 2026-07-20T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-002

### Issue
An earlier port computed pressure as `-depth / 10.0` (a factor of 10 too small — 1000 m would read as only 100 dbar), understating the EOS compressibility correction.

### Resolution and justification
Codebase-wide audit (grep for `depth / 10`, `depth * 0.1`, `10 * depth`) confirmed every current code path uses `pressure = -depth` (1 dbar ≈ 1 m); the only remaining occurrences are comments documenting the historical fix (`main/eos.py` ~lines 451-456, `mixing_adapter.py`, test files).

### Verification and remaining bounds
Audit-only (textual grep), no numerical regression receipt; migrated without a fresh ESX verification hash.

### Traceability
No commit SHA recorded (pre-ESX, root not git-tracked).

---

## RESOLVED: Test suite had stale imports and signatures

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-08-05T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-003

### Issue
Several tests imported from removed modules (e.g. `GGL90_ML.GGL90_PY.ggl90_core` → should be `ggl90_core_driver`) or called driver methods that no longer existed, masking regression coverage for both schemes.

### Resolution and justification
Fixed imports/signatures in `test_staggering.py`, `test_cross_scheme_validation.py`, `test_baseline_refactor.py`; changed the relative import in `GGL90/ggl90_core_driver.py:310` (`from ...main.eos` → `from main.eos`) that caused a top-level `ImportError`.

### Verification and remaining bounds
Per the archived `handoff/BUILD-LOG.md` 2026-08-05 entry, the reviewer (Richard) approved with zero blocking issues at the time; no fresh ESX verification receipt exists. The underlying CI/automation gap (nothing runs these tests automatically) was **not** resolved by this fix — see open issue for that.

### Traceability
No commit SHA recorded (pre-ESX, root not git-tracked).

---

## RESOLVED: Static instability mask density-type question

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-07-20T00:00:00Z
**Status**: False Positive
**UUID**: 1DMIX-005

### Issue
Whether `compute_static_instability_mask()` in `main/eos.py` should use potential density instead of in-situ density for the instability sign test.

### Resolution and justification
Verified against MITgcm `model/src/convective_adjustment.F` lines 122-136: MITgcm's own instability test (`(rhoK - rhoKm1) * rkSign * gravitySign < 0`) also uses in-situ density on both sides — the sign test is density-type-independent. The Python implementation matches exactly; the existing code comment was correct.

### Verification and remaining bounds
Source-level comparison only; no numerical regression receipt.

### Traceability
No commit SHA (no code change made).

---

## RESOLVED: KPP buoyancy-gradient denominator convention question

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-07-20T00:00:00Z
**Status**: False Positive
**UUID**: 1DMIX-006

### Issue
Suspected sign and/or denominator error (double-counting `rho_const`) in `compute_buoyancy_gradients()` relative to MITgcm's KPP density-gradient formula.

### Resolution and justification
Verified against MITgcm `pkg/kpp/kpp_routines.F` lines 1886-1933 (`DBLOC = gravity * (RHOK - RHOKM1) / (RHOK + rhoConst)`, where RHOK/RHOKM1 are density *anomalies*). Python's `dbloc = gravity * (rho_deep - rho_shal_at_deep) / rho_deep` matches exactly once `rho_deep` is recognized as the full in-situ density (`rho_anom + rho_const`) — no double counting.

### Verification and remaining bounds
Source-level comparison only; no numerical regression receipt.

### Traceability
No commit SHA (no code change made).

---

## RESOLVED: Linear EOS validation status question

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-07-20T00:00:00Z
**Status**: False Positive
**UUID**: 1DMIX-007

### Issue
Unclear whether the `use_jmd95=False` linear-EOS fallback path in `main/eos.py` is validated against MITgcm or exercised in production.

### Resolution and justification
Audit confirmed every production call site passes `use_jmd95=True`; `linear_eos()` exists only as an intentional, unvalidated fallback for isolated testing/debugging and is not exercised by any shipped scenario or configuration. No action needed.

### Verification and remaining bounds
Grep-based audit only.

### Traceability
No commit SHA (no code change made).

---

## RESOLVED: No automated gate ran the test suite

**Date Identified**: 2026-07-20T00:00:00Z
**Date Resolved**: 2026-09-15T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-004

### Issue
No CI or pre-commit hook ran the test suite; only manual `pytest` invocations caught regressions. Two of the three previously-flagged "pre-existing failures" (`test_physics_basis.py`, `test_potential_density_gradient.py`) were un-triaged — unclear whether they indicated an oracle/tolerance defect or a genuine implementation defect.

### Resolution and justification
`esx/project.json:verification.focused/scientific` now wire `1D_Mixing_Model/tests` and root `tests/` into `tools/esx/verify.py`, making verification an enforced gate for every ESX issue closure rather than an optional manual step — this is this project's replacement for a GitHub Actions/pre-commit hook, not a literal one. Separately: re-running the full suite today found **zero failures** in the previously-flagged tests — `conda run -n ecco python3 -m pytest 1D_Mixing_Model/tests tests -q` → `42 passed, 19 skipped` (2026-09-15). The 19 skips are legitimate (missing external MITgcm comparison data — see closed issue 1DMIX-010 and open issue 1DMIX-011), not failures.

### Verification and remaining bounds
Fresh, real command output: `42 passed, 19 skipped, 0 failed` (43.63s). This supersedes the stale "42 passed / 3 pre-existing failures" figure in the archived `handoff/BUILD-LOG.md` (2026-08-10) — those 3 failures were evidently fixed sometime between 2026-08-10 and now, without an independent re-check being recorded at the time. No literal CI/pre-commit automation exists (e.g. no `.github/workflows/`); the ESX verification gate is the intentional substitute within this workflow, not a GitHub-native check.

### Traceability
No commit SHA (root not git-tracked at ESX-deployment level; `1D_Mixing_Model/` is a separate nested git repo untouched by this change).

---

## RESOLVED: `h5py` missing from the `ecco` environment blocked one test file's collection

**Date Identified**: 2026-09-15T00:00:00Z
**Date Resolved**: 2026-09-15T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-010

### Issue
`1D_Mixing_Model/tests/test_mitgcm_kpp_lab_sea_validation.py` failed at pytest *collection* with `ModuleNotFoundError: No module named 'h5py'` under the `ecco` conda environment. Fixing the dependency alone then exposed two further, independent authoring bugs in the same file: (1) `generate_test_cases(pytest.lazy_fixture('mitgcm_data'))` at module level — `pytest.lazy_fixture` is not real pytest API (it required a long-deprecated third-party plugin) and this could never have worked, since a fixture's value does not exist at collection time; (2) the `kpp_params` fixture built `KPPParameters()` with library defaults (`rho_const=1029.0`, `gravity=9.81`) while the test's own assertion expected the lab_sea-specific MITgcm values (`rho_const=1027.0`, `gravity=9.8156`) — the fixture never actually configured lab_sea parameters despite its docstring saying it would.

### Resolution and justification
1. `pip install h5py` into the `ecco` conda environment (approved by the Project Owner as part of closing out ESX-migration issues).
2. Rewrote the parametrization using the standard `pytest_generate_tests(metafunc)` hook, loading the HDF5 dataset directly (via a shared `_load_mitgcm_data()` helper) instead of misusing a fixture at collection time; parametrizing with an empty case list when the dataset file is absent, so pytest reports a clean skip instead of a collection error.
3. Fixed the `kpp_params` fixture to construct `KPPParameters(rho_const=1027.0, gravity=9.8156)` explicitly, matching the lab_sea `data` values the test itself already asserted.

### Verification and remaining bounds
`conda run -n ecco python3 -m pytest 1D_Mixing_Model/tests/test_mitgcm_kpp_lab_sea_validation.py -v` → `1 passed, 3 skipped` (`test_kpp_parameters` now passes; `test_kpp_column`, `test_mitgcm_data_loaded`, `test_all_columns_summary` correctly skip because the underlying `mitgcm_instrumentation/lab_sea_kpp_data.h5` dataset does not exist in this repo — that remaining data gap is tracked separately as open issue 1DMIX-011, not fabricated as passing here). Full suite: `1D_Mixing_Model/tests tests` → `42 passed, 19 skipped, 0 failed` (2026-09-15). `esx/project.json` no longer needs to `--ignore` this file.

### Traceability
No commit SHA (root not git-tracked; `1D_Mixing_Model/` is a separate nested git repo — this fix should be committed there under that repo's own commit policy, not yet done pending Project Owner go-ahead per `commit_policy.mode = owner_authorization`).

---

## RESOLVED: GGL90 alpha-minimum resolution-ratio metric re-verified against shipped scripts

**Date Identified**: 2026-08-10T00:00:00Z (flagged during Step 4 reorg closeout as explicitly separate from the reorg itself)
**Date Resolved**: 2026-09-15T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-009

### Issue
The archived `handoff/BUILD-LOG.md` 2026-08-10 entry flagged that the alpha-minimum section's "resolution-ratio metric looked inconsistent" and was never re-checked before that reorg closed out.

### Resolution and justification
Traced the actual metric implementation: `1D_Mixing_Model/scripts/analysis/diagnose_oscillation_threshold.py::compute_gradient_length_scale` computes `resolution_ratio = median_length_scale / mean(dz)` and `under_resolved_fraction = mean(length_scales < 2·mean(dz))` — exactly the "median $L/\Delta z$ + fraction of under-resolved layers" metric the package description's own "Note on metric choice" paragraph (§Minimum Alpha for Oscillation-Free Solutions) says it deliberately uses *instead of* a single minimum $L/\Delta z$ (explicitly called "not informative" there, because a TKE profile's steepest single transition drives the minimum toward zero at every α regardless). The doc and the script already agree with each other — the inconsistency BUILD-LOG flagged does not currently reproduce; either it was fixed during the Step 3 GGL90 doc work (2026-08-06, before this note was written) without the open item being explicitly closed, or the note was raised out of caution and the metric was already correct.

A separate, unrelated script, `1D_Mixing_Model/scripts/analysis/compute_alpha_min.py`, computes a grid-Reynolds-number **stability** criterion (`Re_grid = Δz²/(α·κ_m·Δt) < 2`) — a different metric entirely, and one the package description explicitly disclaims as the actual mechanism ("this is a resolution issue, not a stability issue"). That script's output is not what the documented table or the "Minimum: use α ≥ 5" recommendation is based on; its similar name/location alongside the resolution-based scripts is a plausible source of the original "looked inconsistent" concern, but it does not itself contradict the documented resolution-ratio table.

### Verification and remaining bounds
Freshly executed today: `cd 1D_Mixing_Model && conda run -n ecco python3 scripts/analysis/diagnose_oscillation_threshold.py` (arctic convection scenario, α ∈ {1,3,5,7.5,10,15,20,30,50}). Under-resolved fractions reproduced **exactly** match the documented table: 0.53, 0.27, 0.06, 0.06, 0.12, 0.12, 0.12, 0.12, 0.12 for α=1.0 through 50.0 respectively; α=50.0's full row also matches exactly (TKE roughness 2.15e-04, normalized 0.055, oscillation count 1). This is a real, independent reproduction, not a re-read of the same document. Not verified: whether the same holds for scenarios other than arctic convection, or whether `compute_alpha_min.py`'s stability-based framing should be relabeled/removed to avoid future confusion (left as a documentation-clarity nit, not reopened as a correctness issue).

### Traceability
No commit SHA (no file changed; investigation only).

## RESOLVED: Python GGL90 port's mixing-length limiter applied `mixing_length_min` as an incorrect blanket floor for `mxlMaxFlag=3`

**Date Identified**: 2026-09-16T00:00:00Z
**Date Resolved**: 2026-09-16T00:00:00Z
**Status**: Resolved
**UUID**: 1DMIX-014

### Issue
Found on the first end-to-end run of the new GGL90 full-pipeline validation harness (mirrors the existing KPP pipeline; `mitgcm_verification_mods/ggl90_mods/ggl90_calc.F` instrumentation + `scripts/{parse_mitgcm_ggl90_split,run_ggl90_from_netcdf_input}.py`, run via MITgcm's own `vermix` verification experiment). `GGL90MixingLength.compute()` (`1D_Mixing_Model/GGL90/ggl90_scheme_specific.py`) applied `mixing_length[k] = max(mixing_length[k], self.params.mixing_length_min)` unconditionally to every level for every `mxl_max_flag` value. Initial triage (before implementation) hypothesized this floor was wrong for both `mxlMaxFlag` 2 and 3; the real root cause, found during implementation, was narrower and different: MITgcm's `ggl90_mixinglength.F:381-416` branches `IF (locMxlMaxFlag.EQ.3) ... ELSE ...` — flags 0/1/2 (`ELSE` branch) do apply a genuine blanket `MAX(L,min)` floor (so the pre-fix Python code was actually correct there), while flag 3 specifically (this project's documented ECCOv4r4 default) floors only the *reciprocal*, via `1/MAX(SQRT(L(k)*mxLength_Dn(k)), min)`, and never reassigns `L` itself.

### Resolution and justification
`1D_Mixing_Model/GGL90/ggl90_scheme_specific.py::GGL90MixingLength.compute` now branches on `mxl_max_flag==3` vs. `{0,1,2}` exactly as the real Fortran does, seeding `mixing_length[0]=mixing_length_min` explicitly (previously an accidental side effect of the removed blanket floor). Three additional bugs found and fixed during independent verification against `ggl90_mixinglength.F`/`ggl90_calc.F`, all confirmed against exact cited Fortran lines: (1) `_limit_method_2` was missing the bottom-boundary clamp (`ggl90_mixinglength.F:264-267`) — added, and its return signature changed to `(result, mxl_down)` since the flag-3 formula needs `mxl_down`; (2) `_limit_method_0`/`_limit_method_1` incorrectly included the surface level in their loops (real Fortran loops are `DO k=2,Nr`) — fixed to `range(1, nz)`; (3) `compute_tke_dissipation` divided by `mixing_length` instead of multiplying by `r_mixing_length` (`ggl90_calc.F:601-603`) — required because `r_mixing_length != 1/mixing_length` for flag 3; wired `r_mixing_length` through `GGL90Driver.step_tke_forward`/`compute_mixing` (previously computed but discarded). A separate, unrelated bug was also fixed in `step_tke_forward`: the `c[k]` tridiagonal coefficient used `dr_c[k]` where it must use `dr_c[k-1]` (same as `a[k]`), per `ggl90_calc.F:691-694,713-716` both using the identical `recip_drC(k)` term.

### Verification and remaining bounds
Acceptance oracle (`scripts/run_ggl90_from_netcdf_input.py` + `scripts/compare_ggl90.py` against `GGL90_port_validation/outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20.nc`, 20 timesteps, single column, `mxlMaxFlag=3`): `mixing_length` 489/520 mismatched (>1% rel, max_rel 26x) -> **0/520** (max_rel 8.9e-4); `diff_kz` 26/520 -> **0/520** (max_rel 2.3e-3). `visc_az` (476/520) and `tke_after` (40/520) remain mismatched but are independently traced to two separate, pre-existing harness defects (not the Python port) — tracked as open issues **1DMIX-015** and **1DMIX-016**. Richard independently re-verified the central Fortran branch claim by reading `ggl90_mixinglength.F:381-416` and `GGL90_OPTIONS.h:36` directly, re-ran the acceptance oracle fresh (own `/tmp` output, reproduced Bob's numbers exactly), built an independent from-scratch numeric witness at `(t=5, level k=2)` of the real capture (old formula: exactly 3.000000 m, 2587% error vs. MITgcm's 0.111638 m; new formula: 0.111553 m, 0.076% error), grepped for regressions from the two changed function signatures (none found), and ran the full focused suite fresh under his own owner identity (46 passed, 3 skipped [pre-existing 1DMIX-010 h5py gap, unrelated], 0 failed). Verdict: **APPROVE**, must_fix: none. New regression test `1D_Mixing_Model/tests/test_ggl90_mixing_length.py` (4 tests); Richard confirmed 2 of the 4 would have failed against the pre-fix code by hand-checking. Non-blocking follow-up noted by Richard: no dedicated unit test yet isolates the `dr_c[k-1]` fix or the `r_mixing_length` wiring in isolation (currently covered only by the full oracle pipeline).

### Traceability
Files changed: `1D_Mixing_Model/GGL90/ggl90_scheme_specific.py`, `1D_Mixing_Model/GGL90/ggl90_core_driver.py`, `1D_Mixing_Model/tests/test_ggl90_mixing_length.py` (new), `1D_Mixing_Model/docs/GGL90/GGL90_package_description.tex` (corrected the "Bottom boundary condition"/"Regularization" sections, which had stated the blanket-floor claim as universal — the likely documentation-level origin of the original bug). Committed `09a7a72` in the `1D_Mixing_Model` repo ("Fix GGL90 mixing-length limiter's incorrect blanket floor for mxlMaxFlag=3"), with Project Owner authorization (commit_policy=owner_authorization). Evidence: `devel-loop/loop_state/verification/bf33f4fbd3a775ec4e70c60e68546f343eb4d12001a5f6298c7084bffcbada74.json` (Bob, focused suite), `devel-loop/loop_state/verification/5eb21b12995d20f0061c6634c18c0460c73fa6d8a24167a949a939484a083854.json` (Richard, focused suite, fresh/independent), `devel-loop/loop_state/maintenance/dd7b02bd8c61d1160c519e90e81aa2f6e2b1c1ba0e56c9bf91c5f59e70548fec.json` (sealed documentation disposition, confirmed non-stale by Richard via `doc_contract.py check` -> valid:true). Related open issues: 1DMIX-015, 1DMIX-016 (both harness-only, discovered during this fix's verification, do not affect this resolution's validity).

## RESOLVED: GGL90 validation harness's `visc_az` output column captured `GGL90visctmp` (a diffusivity-floor intermediate), not the real exported viscosity

**Date Identified**: 2026-09-16T00:00:00Z
**Date Resolved**: 2026-09-17T23:19:00Z
**Status**: Resolved
**UUID**: 1DMIX-016

### Issue
The instrumented `ggl90_calc.F`'s `GGL90_OUTPUT_VALIDATION` call passed `GGL90visctmp` (`MAX(KappaM_raw, diffKrNrS(k))`, a diffusivity-floored intermediate used only to derive `GGL90diffKr`) as the dumped `"visc_az"` column, instead of the real exported momentum viscosity (`KappaM`, floored by `viscArNr(k)`). Confirmed by several mismatched captured values equaling exactly `1e-5` = `diffKzS`, not `viscAz=1e-4`.

### Resolution and justification
`KappaM` itself could not be substituted directly: it is a 2D scratch array `(i,j)` overwritten every iteration of the outer `k` loop, so it never retains a per-level history by the time `GGL90_OUTPUT_VALIDATION` is called after the loop. `GGL90viscArU`/`GGL90viscArV` (the persisted, per-level face-interpolated diagnostics) were considered but rejected: `vermix`'s domain is `sNx=sNy=1` with `no_slip_sides=.TRUE.` and no `bathyFile` (default flat-bottom, single active column) — their horizontal-face masking semantics are an unnecessary complication with no counterpart in the Python port's cell-centered 1-D grid. Added a new persisted 3D array `GGL90viscOutput(i,j,k)` (declared/zeroed alongside `GGL90visctmp`, populated immediately after `KappaM`'s own `viscArNr` floor is applied) and passed it to `GGL90_OUTPUT_VALIDATION` instead; also renamed the subroutine's dummy argument `visctmp`→`viscAzOut` for clarity. Applied identically to both tracked copies of the file (`mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`, the issue's anchor, and `mitgcm_verification_mods/vermix/code_validation/ggl90_calc.F`, the copy `experiment_compile.sh -mods` actually builds from — confirmed byte-identical before this fix; no symlink connects them, a minor pre-existing repo-hygiene gap not fixed here since out of scope).

### Verification and remaining bounds
Rebuilt the instrumented `vermix` experiment via the project's Docker helpers (`arch -arm64` not needed; this host runs native arm64) — `experiment_compile.sh vermix -mods .../mitgcm_verification_mods/vermix/code_validation -build build_docker_ggl90_1dmix016 -j 8`, then `experiment_run_no_compile.sh vermix input_ggl90_merged -build build_docker_ggl90_1dmix016 -output output_docker_ggl90_1dmix016` (20 timesteps, `mxlMaxFlag=3`, `useGGL90=.TRUE.`; first attempt used the wrong `-mods`/input dir — a sparse `ggl90_mods/` missing `SIZE.h` et al. hit MITgcm's deliberate-error template `SIZE.h`, and the default `input/` runs KPP not GGL90 — both corrected before the run used as evidence). Reparsed via `scripts/parse_mitgcm_ggl90_split.py`, reran `scripts/run_ggl90_from_netcdf_input.py` + `scripts/compare_ggl90.py`: `visc_az` **476/520 → 0/520** (max_rel 9.0 → 7.6e-4, now comparable to `diff_kz`/`mixing_length`); `diff_kz`/`mixing_length` unchanged (0/520); `tke_after` unchanged (40/520, the separate open 1DMIX-015 dt-derivation bug, not in scope). Structural suite (`tools/esx/verify.py --suite structural`) and focused suite (`--suite focused`, full pytest) both `EXECUTED PASS` after the change (evidence: `devel-loop/loop_state/verification/786c815eb...685.json`, `.../72e9b6a3a...28b.json`). New capture saved alongside (not replacing) the original: `GGL90_port_validation/{inputs,outputs}_from_mitgcm/mitgcm_ggl90_{inputs,outputs}_vermix_20_1dmix016_fix.nc`, `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix016_fix.nc`; originals confirmed byte-unchanged (MD5) before/after. Not independently reviewed by Richard — classified `harness_change` (Fortran instrumentation only, no scientific kernel touched), whose acceptance per the Arch operating contract is the structural suite plus actual harness failure modes, both satisfied above.

### Traceability
Files changed: `mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`, `mitgcm_verification_mods/vermix/code_validation/ggl90_calc.F` (both outside any Git repository — `mitgcm_verification_mods/` and the project root are untracked; no commit SHA applies). MITgcm build/run artifacts: `/Users/ifenty/git_repo_others/MITgcm/verification/vermix/{build,output}_docker_ggl90_1dmix016/` (outside this project, MITgcm's own untracked verification tree).
