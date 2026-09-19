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

## UNRESOLVED: Harmonize GGL90/KPP package_description.tex structure ("Step 5")

**Date Identified**: 2026-08-11T00:00:00Z (briefed by Project Owner)
**Status**: Unresolved
**UUID**: 1DMIX-008
**Anchors**: 1D_Mixing_Model/docs/GGL90/GGL90_package_description.tex; 1D_Mixing_Model/docs/KPP/KPP_package_description.tex

### Issue or research question
`docs/GGL90/` and `docs/KPP/` must become structural mirror images (Project Owner decision: "fully identical section list") so the two schemes are side-by-side comparable.

### Evidence — **reassessed 2026-09-15, scope is much narrower than originally recorded**
The archived `handoff/` snapshot (frozen 2026-08-11) said `port_description.tex` was "new, to be assembled" and that KPP "lacks Appendices B/C". Both claims are **stale** — real work happened after that snapshot was taken and was never written back into the handoff records:
- `1D_Mixing_Model/docs/GGL90/GGL90_port_description.tex` and `docs/KPP/KPP_port_description.tex` **both already exist** (written 2026-08-11, with compiled `.pdf`/`.aux`/`.log`/`.toc` artifacts), with an **identical** 6-section structure (Introduction; Overview of Code Flow; Step-by-Step Code Mapping; Supporting Infrastructure; File-to-File Correspondence Table; Quick Reference: Key Variables). This part of Step 5 is done.
- `package_description.tex` section lists were compared directly (`grep '^\section{'` on both files): GGL90 has 19 sections + Appendices A (I/O Mapping), B (ECCOv4 Configuration), C (Adjoint Model Considerations). KPP has the same 19 sections + Appendix A + Appendix C (Adjoint Model Considerations, already written) — **only Appendix B (ECCOv4 Configuration) is genuinely missing for KPP.**
- `GGL90_Report.tex` and `KPP_Report.tex` no longer exist anywhere in the repo — already folded/deleted. `docs/ML/1D_ML_draft.tex` (898 lines) is the one legacy file still outstanding; its disposition (fold vs. delete) was never carried out.

### Scientific or engineering impact
Documentation-only, no code/physics risk. Writing KPP's "ECCOv4 Configuration" appendix requires citing an **actual ECCOv4 release's** KPP namelist (`data.kpp`), not a generic MITgcm verification-experiment `data.kpp` (e.g. the `1D_ocean_ice_column`/`seaice_obcs` ones found under `/Users/ifenty/git_repo_others/MITgcm/verification/`, which are different configurations) — sourcing the wrong `data.kpp` would produce a confidently-wrong appendix, which is worse than leaving it absent.

### Proposed action and acceptance
Remaining work is now narrowly scoped to: (1) locate the actual ECCOv4-release `data.kpp` (not a verification-experiment one) and write KPP's Appendix B mirroring GGL90's Appendix B structure; (2) decide fold-vs-delete for `docs/ML/1D_ML_draft.tex` and execute it. This is genuine scientific-writing work best done as a dedicated Bob+Richard round (comparable precedent: Step 3's GGL90 appendix took ~30 Bob-hours + review) rather than compressed into an unrelated migration session — not attempted here to avoid rushing sourced scientific content. Acceptance oracle: Richard confirms the ECCOv4 `data.kpp` source is the genuine release configuration (not a verification fixture) and that both `package_description.tex` files have an identical section/appendix list.

---

## UNRESOLVED: Root MITgcm-comparison test suite has no generated `.npz` inputs (and a stale script reference)

**Date Identified**: 2026-09-15T00:00:00Z
**Status**: Unresolved
**UUID**: 1DMIX-011
**Anchors**: tests/test_kpp_mitgcm_validation.py::* (root)

### Issue or research question
Root `tests/test_kpp_mitgcm_validation.py` collects 16 parametrized cases (1-D ocean-ice column, Lab Sea grid) but all 16 currently skip: its docstring says to "Run `parse_mitgcm_kpp_validation.py` first to generate npz files", but no file of that name exists anywhere in the repo. The real, documented MITgcm-comparison pipeline (README.md) is a three-step chain — `scripts/parse_mitgcm_split.py` (parse instrumented MITgcm STDOUT) → `scripts/run_kpp_from_netcdf_input.py` (replay through the Python port) → `scripts/generate_kpp_validation_report.py` (report) — not a single script, and it is not currently run to produce the `.npz` fixtures this test expects.

### Evidence
`conda run -n ecco python3 -m pytest tests/test_kpp_mitgcm_validation.py -q` → `16 skipped`. `find . -iname 'parse_mitgcm_kpp_validation.py'` → no match. No `.npz` files matching this test's expected fixture locations exist under the repo (only unrelated `.npz` outputs from `run_scenarios.py` and an unrelated `.venv` numpy test fixture).

### Scientific or engineering impact
This suite is the intended MITgcm-comparison oracle for the 1-D ocean-ice-column and Lab Sea grid cases at the KPP level; until it actually executes, `esx/project.json`'s `verification.scientific` suite runs it as a structural no-op (16 skips), not real evidence. Do not cite this file as validation evidence until it executes with real assertions (see `docs/model_contract.md` "Verification routes and evidence limits").

### Proposed action and acceptance
Either (a) run the documented 3-step pipeline against real instrumented MITgcm STDOUT/NetCDF to produce the `.npz` fixtures this test expects, and fix the docstring's stale script name, or (b) if that pipeline no longer matches this test's expected fixture format, rewrite the test to consume `scripts/run_kpp_from_netcdf_input.py`'s actual output format directly. Acceptance: the 16 cases execute (pass or fail on real data), not skip.

## UNRESOLVED: Standalone KPPMIX harness diverges from full-model MITgcm at the deepest grid levels when the boundary layer reaches the domain bottom

**Date Identified**: 2026-09-16T00:00:00Z
**Status**: Unresolved
**UUID**: 1DMIX-012
**Anchors**: mitgcm_verification_mods/kpp_standalone_driver/kpp_standalone_main.F; MITgcm/pkg/kpp/kpp_routines.F::KPPMIX,Ri_iwmix,blmix,enhance

### Issue or research question
A new standalone-subroutine harness (`mitgcm_verification_mods/kpp_standalone_driver/`) compiles and calls `KPPMIX` directly (no full model, no genmake2), fed by the exact inputs a real instrumented full-model run used. Across 10 captured timesteps (1D_ocean_ice_column, `input/`, Nr=23), `hbl` and `ghat` match the full-model run to floating-point roundoff (~1e-14) at every timestep, and `visc_az`/`diff_kz_s`/`diff_kz_t` match at every level for timestep 0. But from timestep 1 onward, those three fields diverge by a bounded but real amount (~5e-3 m²/s, roughly 260x the background value) at the deepest 1-4 interior grid levels specifically — the same regime where the boundary layer depth (`hbl`≈33-35m) reaches/exceeds the domain's deepest grid level, i.e. `kbl(i)` approaches `kmtj(i)=Nr`. Root cause not yet isolated: `hbl`/`kbl` themselves match exactly (same formula, same matching zgrid/hbl inputs), and the raw `shsq`/`dbloc` captured inputs are verified identical (both exactly zero) at the affected levels for both matching (t=0) and diverging (t=1+) timesteps — ruling out the obvious "different Ri_iwmix inputs" explanation. Suspected mechanism: `blmix`'s boundary-adjacent derivative-matching (`dvdzup`/`dvdzdn` via `diffus(i,kn-1/kn+1,...)`) or `enhance`'s `kbl(i)-1` interface treatment, sensitive to a not-yet-identified difference between the standalone driver's single-column (imt=1) memory layout and the full model's actual (imt=49, tiled) layout.

### Evidence
`scripts/compare_three_way_kpp.py` run against `KPP_port_validation/{inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend.nc, outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend.nc, outputs_from_mitgcm_standalone/mitgcm_kpp_outputs_standalone_1D_10.nc}`: standalone vs. full-model shows 39/230 (visc_az), 39/230 (diff_kz_s), 39/230 (diff_kz_t) values with max_abs=5.000e-03, while `ghat` (0/230) and `hbl` (0/10) show max_abs ≤ 2.1e-14. Direct Python recomputation of `Ri_iwmix`'s pre-overwrite Richardson number from the captured raw `shsq`/`dbloc` confirms both are exactly 0.0 at the affected levels for t=0 through t=9 alike, yet only t=0 matches.

### Scientific or engineering impact
Does not affect the existing full-model-vs-Python-port validation route (unaffected, see 1DMIX-013's comparison [3] for continued small pre-existing discrepancy there). Affects only the new standalone-subroutine three-way comparison's fidelity at the deepest 1-4 grid levels in a boundary-layer-reaches-bottom regime. Low risk for typical (non-shallow, boundary-layer-not-reaching-bottom) configurations, since the divergence provably requires `kbl(i)` at or near `kmtj(i)`.

### Proposed action and acceptance
Bounded follow-up: add read-only instrumentation printing `blmc`/`dkm1`/`kn` at the affected level from a throwaway local copy of `kpp_routines.F` (never committed/mixed into the pristine reference), compare against equivalent values reconstructed by hand from the full-model STDOUT dump, to localize the exact divergent quantity. Acceptance: either the standalone driver is corrected to match at these levels, or the mechanism is identified and documented as an inherent limitation of single-column (imt=1) standalone replay (in which case downstream three-way comparisons should exclude/flag levels where `kbl` is within a small margin of `kmtj`).

## BLOCKED: Python KPP port's forcing-validation path (`_compute_surface_forcing`) fails sign/magnitude check against raw-flux-derived `bo`/`bosol` on the 1D_ocean_ice_column quick-test capture

**Date Identified**: 2026-09-16T00:00:00Z
**Status**: Blocked
**Blocked-By**: 1DMIX-017 — the only remaining acceptance-oracle failures (bo at t=9, bosol at all 10 timesteps) are proven, independently by both Bob and Richard via from-scratch monkeypatches of `eos.py::jmd95_eos`'s pressure-derivative term, to be fully and solely attributable to 1DMIX-017. This issue's own root cause is fixed and independently verified; it cannot fully close until 1DMIX-017 is fixed and the 1% oracle passes end-to-end.
**UUID**: 1DMIX-013
**Anchors**: 1D_Mixing_Model/KPP/kpp_core_driver.py::KPPDriver._compute_surface_forcing; scripts/run_kpp_from_netcdf_input.py; mitgcm_verification_mods/1D_ocean_ice_column/code_validation/kpp_calc.F

### Issue or research question
Found incidentally while building the KPPMIX standalone harness (1DMIX-012), not caused by it. Running `scripts/run_kpp_from_netcdf_input.py` against a freshly-captured `1D_ocean_ice_column` (`input/`, 10-timestep quick-test) NetCDF that includes the raw-flux fields (`q_net`, `q_sw`, `fw_flux`, already part of the pre-existing instrumentation, unrelated to 1DMIX-012's changes) triggers the driver's own internal forcing-validation check, which fails at every timestep except t=0: e.g. at t=1, Python-recomputed `bo=1.88e-6` vs. MITgcm's captured `bo=-6.68e-8` (opposite sign, ~28x magnitude), and `bosol`: Python=0.0 vs. MITgcm=3.0e-10 (both tiny, but exactly-zero-vs-nonzero).

### Round 0 (Bob + Richard, both independent): root cause is NOT the Python port
`_compute_surface_forcing` itself is correct — verified against real scenario runs via `main/mixing_adapter.py::KPPAdapter.compute_mixing`. The real defect is in this project's own MITgcm instrumentation: `mitgcm_verification_mods/1D_ocean_ice_column/code_validation/kpp_calc.F`'s `KPP_OUTPUT_VALIDATION` `WRITE(...,202)` statement declares columns `q_net,q_sw,fw_flux` in its header but actually supplies MITgcm's already-converted `surfaceForcingT`/`surfaceForcingS` in the `q_net`/`fw_flux` argument slots. Confirmed independently by Bob and by Richard (via a completely different code path/sample points): treating the captured values as already-converted (no further unit conversion) reproduces MITgcm's `bo` to within 0.12%–1.27%, versus 22–29x with opposite sign under the documented-but-wrong raw-flux interpretation. The `surfForcTice`/`adjustColdSST_diag` and ice/cold-SST hypotheses were both ruled out (`allowFreezing=.FALSE.` in the real run config). Round 0 also fixed one confirmed, independent, in-scope bug: `scripts/run_kpp_from_netcdf_input.py::extract_parameters_from_inputs` was missing a `selectPenetratingSW`→`select_penetrating_sw` mapping, forcing `bosol=0.0` unconditionally; fixed, independently verified by Richard (correct sign, ~5% residual, down from 100% error). Richard's round-0 review: APPROVE_WITH_FIXES (one Arch-owned Must Fix: `scripts` was missing from `esx/project.json:source_paths`, fixed).

### Round 1 (owner-authorized MITgcm rebuild, Bob + Richard, both independent): actual capture defect fixed
Bob fixed `KPP_OUTPUT_VALIDATION`'s `WRITE` statement to emit genuinely raw MITgcm `FFIELDS.h` state (`Qnet`, `Qsw`, `EmPmR`, `saltFlux`) instead of the pre-converted `surfaceForcingT`/`surfaceForcingS`, with in-file citation comments to `external_forcing_surf.F`/`kpp_forcing_surf.F`/`ini_parms.F`. Rebuilt and reran the instrumented `1D_ocean_ice_column` MITgcm experiment via the documented Docker helpers (`experiment_compile.sh`/`experiment_run_no_compile.sh`, working around a pre-existing, unrelated Rosetta/`uname -m` arch-detection bug in the external `MITgcm_verification_docker` repo with `arch -arm64`, documented in `mitgcm_verification_mods/README.md`). Added a new `scripts/run_kpp_from_netcdf_input.py::derive_raw_flux_forcing` function combining the raw fields into the forcing terms `_compute_surface_forcing` expects. New capture saved as `KPP_port_validation/{inputs,outputs}_from_mitgcm/mitgcm_kpp_{inputs,outputs}_1D_10_kppmix_extend_rawflux_fix.nc`, added to `esx/project.json:external_inputs` alongside (not replacing) the originals; both original `*_kppmix_extend.nc` files (1DMIX-012's evidence) confirmed byte-identical (MD5/SHA256) before and after, independently by Bob and Richard, and Richard additionally confirmed them unchanged relative to his own round-0 records.

**Result on the corrected capture**: `bo` passes 9/10 timesteps (fails only t=9, rel_err=1.27%, was 22–29x opposite-sign at all 10); `bosol` fails at all 10 (rel_err 4.7–5.2%, was 100%/always-zero). Both Bob and Richard independently proved (via non-persisted, in-memory-only monkeypatches of `eos.py::jmd95_eos`'s pressure-derivative term — not real fixes, not committed) that with that term corrected, all 10/10 timesteps pass both `bo` and `bosol` with zero warnings — i.e. the entire remaining gap is fully and only attributable to 1DMIX-017. Richard independently re-derived `derive_raw_flux_forcing`'s combination formula from the cited Fortran lines from scratch (without reading Bob's derivation first) and got an exact match; independently re-derived 1DMIX-017's correct chain-rule term from scratch and reproduced the same sign-flip at a different sample point (theta=-0.5, salt=33, p=2500 dbar: buggy ratio=-0.28, fixed ratio=1.0000). Richard's round-1 review: APPROVE_WITH_FIXES (two Arch-owned documentation-disposition corrections: `mitgcm_verification_mods/kpp_mods/kpp_calc.F` — the real file behind two symlinks, one of which was already correctly marked "updated" — and `mitgcm_verification_mods/README.md`, both mistakenly bulk-marked "reviewed_unchanged"; both corrected). Richard also flagged an undisclosed consequence: `kpp_mods/kpp_calc.F` is symlinked into both `1D_ocean_ice_column` and `lab_sea` code_validation dirs, so this fix also silently changes `lab_sea`'s future capture format — not currently harmful since `lab_sea`'s validation route is separately blocked by 1DMIX-010.

### Scientific or engineering impact
The Python KPP port's forcing computation (`_compute_surface_forcing`) is confirmed correct; the originally-reported mismatch was a data-capture-instrumentation defect in this project's own MITgcm mods, now fixed and independently double-verified. The sole remaining blocker to this issue's full acceptance oracle (all 10 timesteps within 1% on both `bo` and `bosol`) is 1DMIX-017's EOS pressure-derivative bug, tracked separately.

### Proposed action and acceptance
Re-run `conda run -n ecco python3 scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` once 1DMIX-017 is fixed and confirm all 10/10 timesteps pass `_validate_forcing_computation`'s 1% check for both `bo` and `bosol` with zero warnings — this has already been demonstrated ad hoc via monkeypatch by both Bob and Richard. On that confirmation, move this issue to `closed_issues.md`.

## UNRESOLVED: GGL90 validation harness's `run_ggl90_from_netcdf_input.py` derives `dt` from the netCDF time coordinate (raw iteration index) instead of the real MITgcm `deltaT`

**Date Identified**: 2026-09-16T00:00:00Z
**Status**: Unresolved
**UUID**: 1DMIX-015
**Anchors**: scripts/run_ggl90_from_netcdf_input.py

### Issue or research question
Found and independently confirmed while fixing/reviewing 1DMIX-014 (closed_issues.md). `scripts/run_ggl90_from_netcdf_input.py` computes `dt = float(np.diff(inputs_ds['time'].values)[0])`, but the captured `time` coordinate is the raw MITgcm iteration index (0..19 for the `vermix` 20-timestep capture), not seconds — giving `dt=1.0` instead of the real `deltaT=1200.` (`MITgcm/verification/vermix/input/data:45`).

### Evidence
Both Bob and Richard independently reran the comparison with `dt=1200` substituted (outside the committed script): `tke_after` mismatches against `mitgcm_ggl90_outputs_vermix_20.nc` drop from 40/520 (max_rel 0.85) to 2/520 (max_rel 0.049). This is the dominant remaining source of `tke_after` disagreement now that 1DMIX-014 is fixed.

### Scientific or engineering impact
Understates the real single-step-replay agreement of the GGL90 port — `tke_after` looks worse than it is. Does not affect `mixing_length`/`diff_kz` (dt-independent) or any conclusion about the Python port's physics itself (1DMIX-014's fix stands on those two fields alone). Harness-only defect.

### Proposed action and acceptance
Capture the real `deltaT` (or `dTtracerLev(1)`) into the instrumented `mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`'s PARAMETERS dump (mirroring how KPP's grid/parameter capture works), and have `run_ggl90_from_netcdf_input.py` read it from there instead of differencing the iteration-index time coordinate. Acceptance: rerun against `mitgcm_ggl90_outputs_vermix_20.nc` and confirm `tke_after` mismatches drop to ~2/520 as already demonstrated ad hoc.

## UNRESOLVED: `eos.py::jmd95_eos`'s analytic `ttalpha`/`ssbeta` pressure-derivative term has a sign and denominator error

**Date Identified**: 2026-09-17T02:37:34Z (found by Bob while investigating 1DMIX-013; explicitly out of scope for that issue per `docs/model_contract.md` and the assigned brief's invariants — filed separately per Arch scope decision)
**Status**: Unresolved
**UUID**: 1DMIX-017
**Anchors**: 1D_Mixing_Model/main/eos.py::jmd95_eos; 1D_Mixing_Model/tests/test_potential_density_gradient.py

### Issue or research question
`jmd95_eos`'s analytic partial derivative of density with respect to temperature/salinity (`ttalpha`/`ssbeta`), used by KPP's `_compute_surface_forcing` (`bo`/`bosol`) among other consumers, disagrees with a finite-difference recomputation of the same quantity — including a sign flip at higher pressure — indicating the analytic pressure-derivative term itself (not just the surface, p≈0, case) is wrong.

### Evidence
Bob's finite-difference check (theta=-1.93°C, salt=29.0 psu): at p=5 dbar, analytic ttalpha=-6.1287e-3 vs finite-difference=-6.4613e-3 (ratio 0.9485, ~5% off); at p=500 dbar, analytic ttalpha=+0.0102 vs finite-difference=-0.0229 (opposite sign, not just magnitude). This was surfaced as the explanation for 1DMIX-013's ~4.7-5.2% residual `bosol` mismatch that remains even after that issue's confirmed `selectPenetratingSW` mapping fix.

**Independently reproduced by Richard (2026-09-17) at different sample points**: theta=10°C, salt=35 psu at p=50/1500 dbar, plus a pressure scan (theta=5°C, salt=34.5 psu, p=0..4000 dbar). Result: the analytic/finite-difference `ttalpha` ratio is **exact (1.0000) at p=0** and **degrades monotonically to 0.115 by p=4000 dbar** — this is not a bug specific to Bob's sample point but a genuine, reproducible **pressure-scaling defect** in the analytic derivative term (correct at the surface, increasingly wrong with depth).

### Depth/consumer note
Because the defect is exact at p≈0 and only grows with depth, KPP's surface-only use (`bo`/`bosol`) sees a small residual (~5%), but any consumer evaluating `ttalpha`/`ssbeta` well below the surface would see much larger errors per Richard's scan — check GGL90 and any interior-column `N²`/buoyancy-gradient use of these derivatives for the same exposure before assuming this is a KPP-only, surface-only issue.

### Scientific or engineering impact
`project_profile.md` flags `main/eos.py` density-gradient/pressure-conversion logic as this project's highest-risk area (real prior bugs 1DMIX-001/1DMIX-002). If real, this affects every consumer of `ttalpha`/`ssbeta` at nonzero pressure — not just KPP's surface forcing (which only needs the p≈0 surface value) — so any interior-column or deeper-boundary use of these derivatives should be treated as suspect until this is resolved. Sign flip at depth (not just a magnitude error) means downstream `N²`/buoyancy calculations using this term below the surface could have the wrong stability sign, which is a silent-incorrect-result class risk per `devel-loop/issue_priority.md`.

### Proposed action and acceptance
Trace `jmd95_eos`'s analytic `ttalpha`/`ssbeta` pressure-derivative formula line-by-line against its MITgcm/JMD95 source reference (`main/eos.py` should already cite the formula's origin per the project's MITgcm-correspondence requirement — locate and re-verify that citation first). Reproduce Bob's finite-difference check independently at multiple (theta, salt, pressure) points spanning the range actually used by both GGL90 and KPP (not just the one sample point above) before concluding the fix is complete. Acceptance: analytic derivative matches finite-difference to a defensible tolerance (document the chosen tolerance and why) across representative (theta, salt, pressure) triples, and 1DMIX-013's `bosol` residual is re-measured after the fix to confirm it also improves.
