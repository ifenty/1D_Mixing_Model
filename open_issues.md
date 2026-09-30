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

## UNRESOLVED: `global_ocean_90x40x15`/`global_ocean_cs32x15` have never been captured with KPP, and `lab_sea` has never been captured with GGL90 — every real MITgcm capture in this project uses exactly one scheme per grid, missing real cross-scheme coverage

**Date Identified**: 2026-09-27T21:00:00Z
**Status**: Unresolved
**UUID**: 1DMIX-054
**Anchors**: `MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_ocean_90x40x15/code_validation/`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_ocean_cs32x15/code_validation/`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/lab_sea/code_validation/`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/vermix/kpp_code_validation/`; `MITgcm_to_Python_port_verification/mitgcm_verification_mods/1D_ocean_ice_column/ggl90_code_validation/`

### Issue or research question
Directly confirmed via each experiment's own `packages.conf`: `global_ocean_90x40x15/code_validation/packages.conf` explicitly disables KPP (`-kpp`) and enables `ggl90`; `global_ocean_cs32x15/code_validation/packages.conf` likewise has `ggl90` with no `kpp` line at all; `lab_sea/code_validation/packages.conf` enables KPP (via the `oceanic` package group) with no `ggl90` line at all. Every one of these three grids has therefore only ever been captured and regression-tested with a single mixing scheme, even though this project's own precedent shows dual-scheme testing of the *same* grid is both possible and valuable: `vermix` already has a second, sibling `kpp_code_validation/` directory alongside its primary GGL90 `code_validation/` (built but never actually captured/tested — confirmed no `*vermix*kpp*` capture file exists anywhere in the repo), and `1D_ocean_ice_column` already has a working, captured, tested `ggl90_code_validation/` alongside its primary KPP `code_validation/` (1DMIX-028's real GGL90 cross-test on this KPP-native grid — currently this project's *best*-agreeing GGL90 result of any experiment, per `VALIDATION_RESULTS.md`). The owner wants the same treatment applied to `global_ocean_90x40x15`/`global_ocean_cs32x15` (add KPP) and `lab_sea` (add GGL90, at both its existing 999-timestep and 6-month capture durations).

### Evidence
Unblocked 2026-09-30: 1DMIX-065 restored every external_inputs capture and verified the Docker MITgcm route (~/Projects/MITgcm at d861cd501) on this checkout.

`packages.conf` quotes: `global_ocean_90x40x15/code_validation/packages.conf` line 4 is `-kpp`, line 7 is `ggl90`. `global_ocean_cs32x15/code_validation/packages.conf` line 5 is `ggl90`, no `kpp`/`-kpp` line present at all. `lab_sea/code_validation/packages.conf` has no `ggl90` line; KPP is enabled via the `oceanic` package group (confirmed via `lab_sea/code_validation/README`'s own "KPP Validation Instrumentation" framing). Confirmed no `data.kpp` exists anywhere upstream for `global_ocean.90x40x15`/`global_ocean.cs32x15` in `/Users/ifenty/git_repo_others/MITgcm/verification/`, and no `data.ggl90` exists upstream for `lab_sea` either (`find ... -iname data.kpp`/`data.ggl90` both empty for the relevant experiment/config) — unlike `global_oce_latlon`, which does have a real, ready-to-use `input_validation/data.kpp` this project already uses (1DMIX-049), and unlike the 3 experiments 1DMIX-028 found already had owner-provided `data.ggl90` (`global_ocean.90x40x15/input.idemix/data.ggl90`, `global_ocean.cs32x15/input.in_p/data.ggl90`, `isomip/input.obcs/data.ggl90` — those already back this project's *existing* GGL90 captures for the two `global_ocean` grids). This means the new KPP namelists for both `global_ocean` grids, and the new GGL90 namelist for `lab_sea`, need to be hand-constructed (adapting an existing scheme-specific namelist/header from elsewhere in this project), not simply toggled from an already-provided upstream file.

### Scientific or engineering impact
Every currently-tested grid/scheme combination in this project is confounded with that grid's own specific geometry, forcing, and package set — there is no clean "same physical setup, different scheme" comparison anywhere except `1D_ocean_ice_column`'s existing GGL90 cross-test. Adding KPP to the two `global_ocean` grids and GGL90 to `lab_sea` would let real, geometry-matched cross-scheme comparisons corroborate (or contradict) findings currently only established on a single grid each — e.g. whether `lab_sea`'s own Rib/Ricr floating-point-threshold-sensitivity tail (currently only characterized for KPP) has any GGL90 analogue, and whether the IDEMIX missing-physics gap currently only measured with GGL90 on the `global_ocean` grids would show comparably in KPP's own (unrelated) diagnostic pathway.

**Known risk for `global_ocean_cs32x15`+KPP specifically, more subtle than the existing GGL90 confound — flag explicitly, do not rediscover or misread as a clean pass**: `cs32x15` runs in pressure coordinates (`buoyancyRelation='OCEANICP'`). For GGL90, MITgcm's real `pkg/ggl90/ggl90_calc.F` explicitly converts via a `coordFac = gravity*rhoConst` factor threaded through every depth-dependent formula when `usingPCoords`; the Python port has no equivalent, so GGL90's existing `cs32x15` capture shows a real, large, visible MITgcm-vs-port disagreement (1DMIX-040) — an honest, informative gap. **KPP is different: directly confirmed via `grep -rn 'coordFac\|usingPCoords' pkg/kpp/*.F` in the real MITgcm source, MITgcm's own upstream KPP package has *zero* pressure-coordinate handling anywhere** — `hbl`/`bosol`/etc. are computed directly from `rF`/`drF` with no unit conversion, and MITgcm has no runtime guard preventing `useKPP=.TRUE.` with `usingPCoords=.TRUE.`. This means a `cs32x15`+KPP run will not "fail" or show an obvious large mismatch the way GGL90's does — MITgcm's own real KPP output is *itself* unit-confused on this grid (treating pressure as if it were metres), and if the Python port does the same (plausible, since it has no p-coordinate handling either), the two could show *close agreement* — a false, misleading validation result: both sides making the identical physical error relative to real units, not the port faithfully reproducing correct behavior. Any `cs32x15`+KPP report/test must explicitly state this mechanism, not present a clean-looking pass as genuine port fidelity.

### Proposed action and acceptance
For each of the 3 new (grid, scheme) pairs: (1) create a new sibling `code_validation` variant directory following the already-established `<scheme>_code_validation/` naming convention (`global_ocean_90x40x15/kpp_code_validation/`, `global_ocean_cs32x15/kpp_code_validation/`, `lab_sea/ggl90_code_validation/`), symlinking the target scheme's Fortran source from the canonical `kpp_mods/`/`ggl90_mods/` (never copying, per this project's own established convention), copying the grid's own real headers/`packages.conf` unmodified except for the scheme package swap. (2) Hand-construct the missing namelist (`data.kpp` for the two `global_ocean` grids, `data.ggl90` for `lab_sea`) by adapting the closest existing working example in this project (e.g. `global_oce_latlon/input_validation/data.kpp` for the KPP namelists; `vermix`'s or `1D_ocean_ice_column/ggl90_code_validation`'s own real `GGL90_OPTIONS.h`/namelist values for the GGL90 one) — verify every adapted parameter against the target grid's own real forcing/geometry, don't blindly copy defaults tuned for a different grid. (3) Build+run+capture via the same Docker pipeline used throughout this project (budget real wall-clock time per grid size — the two `global_ocean` grids are comparable in size to `global_oce_latlon`'s own ~15-minute run per 1DMIX-049's measured precedent; `lab_sea` at 999 and 6-month/4368 timesteps should reuse the existing capture durations exactly, for direct comparability against the existing KPP captures at those same durations). (4) Permanentize into `KPP_port_validation/`/`GGL90_port_validation/` with clear, scheme-disambiguating filenames, add regression tests mirroring the existing per-experiment test-class conventions (bounded/subsampled where a full replay would be impractical, per this project's own established `lab_sea_6mo`/`global_oce_latlon` precedent). Acceptance: 4 new real MITgcm captures exist (90x40x15-KPP, cs32x15-KPP, lab_sea-GGL90-999, lab_sea-GGL90-6mo), each permanently stored and declared in `esx/project.json:external_inputs`, each with at least one numeric-tolerance regression test measured fresh against the actual new capture; `cs32x15-KPP`'s own report/test explicitly states the mechanism above (MITgcm's own real KPP has no `coordFac`-equivalent conversion either, so close port-vs-MITgcm agreement here would reflect a shared unit error, not genuine port fidelity) rather than presenting any resulting close agreement as a clean validation pass; full pytest suite passes.
