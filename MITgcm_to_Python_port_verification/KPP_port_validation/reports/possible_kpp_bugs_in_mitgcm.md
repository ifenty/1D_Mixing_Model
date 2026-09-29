# Possible KPP Bugs/Issues in MITgcm

**Date**: 2026-08-20  
**Investigator**: Ian Fenty  
**Context**: Validation of Python KPP port against MITgcm Fortran implementation

---

## Summary

This document tracks potential numerical issues in MITgcm's KPP implementation discovered during validation of the Python port. These issues relate to divide-by-zero conditions in boundary layer mixing calculations.

---

## Issue 1: Missing hbl Regularization in BLMIX

**Status**: 🟡 Under Investigation  
**Severity**: Low (produces warnings but numerically handled)  
**MITgcm Location**: `pkg/kpp/kpp_routines.F:1556-1563`

### Description

MITgcm's BLMIX subroutine divides by boundary layer depth (`hbl`) and velocity scales (`wm`, `ws`) when computing shape function parameters, but only regularizes the velocity scales - not `hbl` itself.

**Code (kpp_routines.F:1493-1495):**
```fortran
DO i = 1, imt
   wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
   ws(i) = sign(eins,ws(i))*MAX(phepsi,ABS(ws(i)))
ENDDO
```

**Code (kpp_routines.F:1556-1563):**
```fortran
gat1m(i) = visch / hbl(i) / wm(i)
dat1m(i) = -viscp / wm(i) + f1 * visch

gat1s(i) = difsh  / hbl(i) / ws(i)
dat1s(i) = -difsp / ws(i) + f1 * difsh

gat1t(i) = difth /  hbl(i) / ws(i)
dat1t(i) = -diftp / ws(i) + f1 * difth
```

**The Issue:**
- `wm` and `ws` are regularized to `phepsi` (typically 1e-10)
- `hbl` is NOT regularized before division
- When `hbl` approaches zero (weak forcing, cold start), division by `hbl` produces inf/nan

### When This Occurs

Most commonly at **timestep 0** (model initialization) when:
- Surface forcing is weak or zero (ustar ≈ 0, bfsfc ≈ 0)
- Ocean starts from rest (u ≈ 0, v ≈ 0)
- Boundary layer has not yet developed
- BLDEPTH computes minimal hbl (approaching machine epsilon)

**Example from lab_sea validation (1000 timestep run):**
- Warnings appear only at timestep 0
- Warnings disappear by timestep 1 as forcing develops
- Affects multiple grid points with weak initial forcing

### Python Port Behavior

**Code (kpp_scheme_specific.py:372-373) — original excerpt, 2026-08-20; superseded by 1DMIX-062.**
This one-line `np.sign`-based regularization is **no longer what ships**; the excerpt is
retained to preserve the original reasoning (and the original, accurate claim that it
"exactly replicates" MITgcm at the time this was written), not to describe current
behavior. See the "Superseded (1DMIX-062)" block immediately below for what changed, why,
and whether the change matters.

```python
# Regularize velocity scales (MITgcm: kpp_routines.F:1493-1495)
wm_one = np.sign(wm_one[0]) * max(config.phepsi, abs(wm_one[0]))
ws_one = np.sign(ws_one[0]) * max(config.phepsi, abs(ws_one[0]))
```

**Superseded (1DMIX-062, resolved).** The one-liner above is a genuinely different
algorithm from what the port now runs, not a citation-only drift — and the direction
matters. The old `np.sign(wm_one[0])` returns exactly `0.0` when `wm_one[0] == 0.0`
(IEEE 754 `sign(0.0) == 0.0`), so the whole product collapses to `0.0`. Real Fortran's
`sign(eins, wm(i))` returns `+1.0` at that same zero (confirmed both by reading the
Fortran-standard definition and empirically: `gfortran` evaluating `SIGN(1.0, 0.0)`
prints `1.00000000`), so the old Python one-liner **diverged from MITgcm** at exactly
this edge case — the one this Issue's own "When This Occurs" section says is common
(timestep 0, weak/zero forcing, `wm_one[0]` legitimately hitting `0.0`).

Current code (`kpp_scheme_specific.py:430-446`, verified against the working tree at the
time of this edit) replaces the one-liner with an explicit zero branch plus
`np.copysign`, and its own comment names the exact same divergence identified above:

```python
    # Regularize velocity scales (MITgcm: kpp_routines.F:1493-1495)
    # MITgcm Fortran: wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
    # IMPORTANT: Fortran's sign(1.0, x) returns +1.0 when x=0, but np.sign(0.0) returns 0.0!
    # We must handle the zero case explicitly to match MITgcm behavior.
    wm_one_mag = max(config.phepsi, abs(wm_one[0]))
    ws_one_mag = max(config.phepsi, abs(ws_one[0]))

    # Apply sign, defaulting to positive when exactly zero (Fortran behavior)
    if wm_one[0] == 0.0:
        wm_one = wm_one_mag
    else:
        wm_one = np.copysign(wm_one_mag, wm_one[0])

    if ws_one[0] == 0.0:
        ws_one = ws_one_mag
    else:
        ws_one = np.copysign(ws_one_mag, ws_one[0])
```

**Landing commit** (traced with `git log --follow -S 'copysign' -- Vertical_Mixing_Models/KPP/kpp_scheme_specific.py`,
which crosses the later file-move/rename that `git log -S` against only the current path
would miss): `cd4b2bcfdbd364ebfae2d3c4b172f6b2edabd490`, **2026-09-17 09:19:50 -0700**,
author `ifenty`, subject **"1D update"** (at that commit the file lived at the pre-move
path `KPP/kpp_scheme_specific.py`; the `Vertical_Mixing_Models/` prefix and the
`KPP_ML/KPP_PY`→`KPP` consolidation both predate this commit, and the later
`b68b847` "Reorganize repo" commit that `git log -S` against the current path alone
stops at is a pure rename with an empty diff for this file — confirmed via
`git show b68b847 --stat`, which shows a `0` line-change rename entry). The introducing
diff hunk (`git show cd4b2bc -- KPP/kpp_scheme_specific.py`):

```diff
-    wm_one = np.sign(wm_one[0]) * max(config.phepsi, abs(wm_one[0]))
-    ws_one = np.sign(ws_one[0]) * max(config.phepsi, abs(ws_one[0]))
+    # Regularize velocity scales (MITgcm: kpp_routines.F:1493-1495)
+    # MITgcm Fortran: wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
+    # IMPORTANT: Fortran's sign(1.0, x) returns +1.0 when x=0, but np.sign(0.0) returns 0.0!
+    # We must handle the zero case explicitly to match MITgcm behavior.
+    wm_one_mag = max(config.phepsi, abs(wm_one[0]))
+    ws_one_mag = max(config.phepsi, abs(ws_one[0]))
+
+    # Apply sign, defaulting to positive when exactly zero (Fortran behavior)
+    if wm_one[0] == 0.0:
+        wm_one = wm_one_mag
+    else:
+        wm_one = np.copysign(wm_one_mag, wm_one[0])
+
+    if ws_one[0] == 0.0:
+        ws_one = ws_one_mag
+    else:
+        ws_one = np.copysign(ws_one_mag, ws_one[0])
```

**Correspondence with real MITgcm, checked directly** (not taken from the port's own
comment): `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_routines.F` lines 1493-1495 read
exactly:
```fortran
      DO i = 1, imt
         wm(i) = sign(eins,wm(i))*MAX(phepsi,ABS(wm(i)))
         ws(i) = sign(eins,ws(i))*MAX(phepsi,ABS(ws(i)))
      ENDDO
```
(`wm`/`ws` assignments on real lines 1493/1494, `ENDDO` on 1495 — the port comment's
`:1493-1495` citation is exactly right, not off-by-one.) Fortran's `SIGN(A,B)` intrinsic is
defined as `|A|` when `B >= 0` and `-|A|` when `B < 0` — zero is on the `>=` branch, so
`SIGN(1.0, 0.0)` is `+1.0`, empirically confirmed (`gfortran` on a 3-line test program
printed `1.00000000`). **Current port behavior (the `copysign`/explicit-zero-branch form)
matches this exactly.** The pre-`cd4b2bc` one-liner did not.

**Report-date check: undetermined, not measured** (corrected 1DMIX-062 correction round 2;
see "Published Figures: Measured vs. Undetermined" below for the full correction and its
own verification). This report's header self-declares `2026-08-20`, but `git log --all
--follow` on this file's own path shows tracking begins only at `b68b847` (2026-09-18, a
pure `create mode` add, not a rename) — one day **after** the `cd4b2bc` fix (2026-09-17) —
so git cannot corroborate any authorship date earlier than 2026-09-18, let alone
2026-08-20. The only support for 2026-08-20 is the circumstantial `0820T0946` timestamp
embedded in an unrelated input-capture filename. Whether the report's Issue 1 narrative
(including the "Python Port Behavior... exactly replicates" claim and the
lab_sea-timestep-0 discussion below) was written before or after the fix is therefore
**undetermined by git**, not confirmed.

**Code (kpp_scheme_specific.py:506-513):** *(line numbers corrected 1DMIX-062 — originally
cited as `433-440`; pure line drift from unrelated intervening edits, content byte-identical
to the original excerpt below, re-verified verbatim against the current working tree.)*
```python
gat1m = visch / hbl / wm_one
dat1m = -viscp / wm_one + f1 * visch

gat1s = difsh / hbl / ws_one
dat1s = -difsp / ws_one + f1 * difsh

gat1t = difth / hbl / ws_one
dat1t = -diftp / ws_one + f1 * difth
```

**Resulting warnings (timestep 0 only):**
```
RuntimeWarning: divide by zero encountered in scalar divide
  gat1m = visch / hbl / wm_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1m = -viscp / wm_one + f1 * visch
RuntimeWarning: divide by zero encountered in scalar divide
  gat1s = difsh / hbl / ws_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1s = -difsp / ws_one + f1 * difsh
RuntimeWarning: divide by zero encountered in scalar divide
  gat1t = difth / hbl / ws_one
RuntimeWarning: invalid value encountered in scalar divide
  dat1t = -diftp / ws_one + f1 * difth
```

### Physical Interpretation

This is **physically reasonable** for initial conditions:
- Weak forcing → small boundary layer
- Small boundary layer → negligible BL mixing
- Division by near-zero `hbl` produces inf/nan
- These inf/nan values propagate but are multiplied by other near-zero terms
- Net result: negligible mixing (correct physical outcome)

### Published Figures: Measured vs. Undetermined (1DMIX-062)

**Undetermined (authorship date, corrected 1DMIX-062 correction round 1 — the previous
version of this paragraph wrongly claimed `git log` corroboration it does not have).** This
report's header declares `**Date**: 2026-08-20`, but that is the document's own
self-declared claim, not something git independently confirms. `git log --all --follow`
on this file's own path returns exactly one commit: `b68b847` (2026-09-18 17:13:47 -0700).
That commit's own record for this path is a pure `create mode 100644` addition — confirmed
with `git show b68b847 -M5% --name-status`, which reports status `A` (add), not `R`
(rename) — so no earlier history is being carried forward under a different name; there is
no commit before it that touches this path. Git tracking of this file therefore begins
**2026-09-18 — one day after** the `cd4b2bc` fix (2026-09-17 09:19:50 -0700), and cannot
corroborate any authorship date earlier than that, let alone 2026-08-20. The only support
for 2026-08-20 is circumstantial: the `0820T0946` timestamp embedded in the input capture
filename this report's own Testing Methodology section cites
(`mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc`, filesystem mtime `2026-08-20 06:46:30`,
checked directly) is consistent with an August 20th investigation session, but a filename
convention on an unrelated input capture is not proof of when this markdown file's own text
was written. **The exact authorship date, and therefore whether this report's narrative was
written before or after the fix, is undetermined by git** — it rests on the header's own
unverified self-declaration plus this one piece of circumstantial corroboration, not on any
git history for this file.

**Measured**, for the five rendered validation PDFs currently checked into
`KPP_port_validation/reports/` (`kpp_validation_1D_ocean_ice_column_10.pdf`,
`_11000.pdf`, `_lab_sea_6mo.pdf`, `_lab_sea_999.pdf`, `_seaice_obcs_1dmix034.pdf`,
all added in commit `1482fe5`, 2026-09-27): `pdfinfo` on every one of the five reports a
Matplotlib `CreationDate` between `2026-09-27 05:57 PDT` and `2026-09-27 10:25 PDT` — all
**after** the `cd4b2bc` landing commit (2026-09-17 09:19:50 -0700). `KPP_port_validation/CAPTURES.md`
independently states, for each of these, that the underlying `outputs_from_python/*.nc`
capture it was built from is the "**current**" one and was regenerated on `2026-09-27`
(e.g. the `lab_sea_999` entry names `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc`
explicitly as the "source of `reports/kpp_validation_lab_sea_999.pdf`"). That `.nc` file's
own filesystem mtime (`2026-09-27 05:56:10`, checked directly with `stat`) is two minutes
before its PDF's `CreationDate` (`05:58:25`) — internally consistent with a same-session
regenerate-then-plot on 2026-09-27, i.e. after the fix. **None of these five currently-published
figures were measured under the divergent pre-fix `np.sign` behavior.**

**Undetermined, stated explicitly rather than checked and asserted:**
- The `.nc` captures are gitignored (`*.nc`), so the above rests on filesystem mtimes and
  `CAPTURES.md`'s own textual claim, not on independent git-commit provenance for the data
  itself — only the PDFs and `CAPTURES.md` are git-tracked. A determination with
  cryptographic/commit-level confidence would require the capture pipeline to record a
  content hash or timestamp inside the `.nc` file's own metadata (checked: the files' NetCDF
  attributes recorded in `CAPTURES.md` for provenance are `title`/`source`/`description`/`uuid`,
  not a generation timestamp) or a git-tracked capture log with run timestamps.
- I did not verify that any of these five captures' forcing actually drives `wm_one[0]`
  (or `ws_one[0]`) to exactly `0.0` at any timestep — i.e. that they exercise the specific
  code path this Issue is about, as opposed to merely postdating the fix commit generically.
  Confirming that would require re-instrumenting `compute_bl_mixing` (as the "direct
  instrumented `wscale` check" mentioned elsewhere in this project's validation docs already
  does for the unrelated `keep_mitgcm_bugs` clamp) and is not done here.
- This check covers only `KPP_port_validation/reports/`. Two further documents that discuss
  related statistics for these same captures (`KPP_port_validation/KPP_VALIDATION_RESULTS.md`,
  `KPP_port_validation/reports/kpp_scenario_standalone_summary.md`) are, as of this writing,
  **uncommitted, untracked working-tree files** (confirmed via `git status`/`git ls-files`) —
  not yet published in any commit at all, so the question of whether they predate the fix
  does not yet apply to them; this is noted, not resolved, since their eventual commit is
  outside this issue's scope.
- No other report/document in this project was searched exhaustively for embedded figures
  or numbers tied to this specific code path beyond the `grep` performed for this issue
  (`wm_one`, `copysign`, `sign(eins`, `hbl.*divide` across `MITgcm_to_Python_port_verification/`,
  `docs/`, `Vertical_Mixing_Models/docs/`), which returned only this report file itself.

### Potential Fixes

**Option 1: Regularize hbl (breaks bit-level compatibility with MITgcm)**
```python
hbl_safe = max(hbl, config.phepsi)
gat1m = visch / hbl_safe / wm_one
```
- Pros: Eliminates warnings
- Cons: Changes numerical results, no longer matches MITgcm exactly

**Option 2: Early exit for hbl ≈ 0 (already implemented)**
```python
if hbl == 0.0:
    # Return zero mixing
    return np.zeros(nz), np.zeros(nz), np.zeros(nz), ...
```
- Pros: Physically correct, avoids division
- Cons: Only catches exactly zero, not near-zero values

**Option 3: Accept warnings as documentation**
- Pros: Maintains bit-level MITgcm compatibility
- Cons: Clutters output, may hide other issues
- Mitigation: Filter warnings for timestep 0 only

**Option 4: MITgcm source code fix**
```fortran
! After line 1495 in kpp_routines.F
DO i = 1, imt
   hbl(i) = MAX(hbl(i), phepsi)
ENDDO
```
- Pros: Fixes root cause, consistent with wm/ws regularization
- Cons: Requires MITgcm source modification, affects all MITgcm users

### Impact Assessment

**Scientific Impact**: Negligible
- Only affects edge cases with extremely weak forcing
- Produces correct physical result (negligible mixing)
- Does not affect bulk simulation results

**Computational Impact**: None
- inf/nan values handled by IEEE 754 arithmetic
- Does not cause crashes or incorrect propagation
- Performance unchanged

**Validation Impact**: Minor
- Python port warnings document the issue
- Bit-level comparison still valid (both produce same inf/nan)
- Useful for identifying weak forcing conditions

### Recommended Action

**For Python Port:**
- **Status quo** - maintain exact MITgcm behavior
- Document warnings in code comments (already done)
- Optionally suppress warnings for timestep 0:
```python
if t_in_idx == 0:
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', 'divide by zero')
        warnings.filterwarnings('ignore', 'invalid value')
        output = driver.compute_mixing(...)
```

**For MITgcm Community:**
- Report issue to MITgcm developers
- Suggest adding `hbl` regularization for consistency with `wm`/`ws`
- Low priority (does not affect results)

---

## Issue 2: WSCALE Lookup Table Linear Extrapolation Hazard

**Status**: 🔴 Confirmed Bug (Documented by MITgcm Developers)  
**Severity**: High (can cause model crashes under extreme forcing)  
**MITgcm Location**: `pkg/kpp/kpp_routines.F:980`  
**Fix Available**: Line 990 (commented out)  
**Python Port Status**: 🟡 Bug reproduced by default since 1DMIX-057 (`keep_mitgcm_bugs=True`); the never-activated Fortran clamp/fix remains available via `keep_mitgcm_bugs=False`. *(Original 2026-08-20 read "🟢 Bug fixed by default"; superseded by 1DMIX-057 — see the Superseded block under Recommended Action below.)*

### Description

MITgcm's `wscale` subroutine computes turbulent velocity scales (wm, ws) using bilinear interpolation from pre-computed lookup tables. For extremely negative buoyancy forcing, the interpolation can **linearly extrapolate beyond the table's lower edge**, producing unstable values that crash the model.

**The MITgcm developers themselves documented this bug in the source code** (lines 981-989) but left the buggy version active.

### MITgcm Source Code

**Active (buggy) code (line 980):**
```fortran
zdiff = zehat - zmin
```

**Commented-out fix (line 990, attributed to Dimitry Sidorenko):**
```fortran
C           zdiff = MAX( 0. _d 0, zehat - zmin )
```

**Developer comment (lines 981-989):**
```fortran
C     For extremely negative buoyancy forcing bfsfc, zehat and hence
C     zdiff can become very negative (default value of zmin = 4.e-7) and
C     the extrapolation beyond the limit zmin of the lookup table can
C     give very bad values and may make the model crash. Here is a
C     simple fix (thanks to Dimitry Sidorenko) that effectively replaces
C     linear extrapolation with nearest neighbor extrapolation so that
C     only the lower limit values of the lookup tables wmt/wst are used.
C     Alternatively, one can get rid of the lookup table altogether
C     and compute the coefficients online (done in NEMO, for example).
```

### When This Occurs

**Triggering Conditions:**
- Extremely negative buoyancy forcing: `bfsfc << 0`
- This causes `zehat = vonk * sigma * hbl * bfsfc` to become very negative
- Then `zdiff = zehat - zmin` becomes a large negative number
- `iz = int(zdiff / deltaz)` becomes a large negative index
- Bilinear interpolation extrapolates linearly beyond table edge
- Result: Extremely bad (possibly NaN or explosive) velocity scales

**Physical scenarios where this can happen:**
- Strong surface cooling with weak winds
- Very stable stratification with downward buoyancy flux
- Ice formation events (strong brine rejection)
- Arctic/Antarctic winter conditions

### Python Port Implementation

The Python port **fixes this bug by default** using a `keep_mitgcm_bugs` flag for validation purposes.
*(Original, 2026-08-20; superseded by 1DMIX-057.* The default is now `True`, so the port reproduces
MITgcm's unclamped extrapolation instead of fixing it. See the Superseded block below.*)*

**Code (kpp_parameters.py:116-129) — original excerpt, 2026-08-20; superseded by 1DMIX-057.**
The `False` default shown here is no longer what ships; the excerpt is retained to preserve the
original reasoning, not to describe current configuration.

```python
# ========== MITgcm bug-compatibility switch ==========
# When True, reproduce the *exact* stock-MITgcm pkg/kpp behaviour, including
# a known numerical hazard that the MITgcm developers themselves flagged in
# the source but left active. When False (default), branch to bug-fixed code.
#
# Currently gated bug(s):
#   - wscale zdiff linear-extrapolation hazard (kpp_routines.F:980 vs :990)
keep_mitgcm_bugs: bool = False
```

**Code (kpp_routines.py:175-182):**
```python
if config.keep_mitgcm_bugs:
    # Stock MITgcm (line 980): unclamped -> may extrapolate below the
    # table and produce bad/unstable velocity scales.
    zdiff = zehat - config.zmin
else:
    # Bug-fixed (line 990, Sidorenko): clamp so we never index below
    # the table; nearest-neighbour behaviour at the lower edge.
    zdiff = max(0.0, zehat - config.zmin)
```

### Why MITgcm Hasn't Fixed This

**Possible reasons:**
1. **Backward compatibility**: Fixing the bug changes results of all existing simulations
2. **Rare occurrence**: May only trigger in extreme conditions not commonly encountered
3. **Testing burden**: Would require re-validating all verification experiments
4. **Documentation over fixing**: Developers documented the issue but left users to decide

### Impact Assessment

**Scientific Impact**: Potentially High
- Can cause model crashes in extreme forcing scenarios
- Produces incorrect mixing when extrapolation occurs
- Affects ice-covered regions, deep convection events

**Computational Impact**: Critical in edge cases
- Linear extrapolation can produce O(1e10) or NaN values
- These propagate and crash the model
- Nearest-neighbor extrapolation (fix) provides stable lower bound

**Validation Impact**: Critical for Python port
*(Original, 2026-08-20; superseded by 1DMIX-057 — the parenthesised default below is inverted from
what now ships. See the Superseded block immediately following.)*
- Python port must be able to reproduce MITgcm bugs for validation
- `keep_mitgcm_bugs=False` (default at the time of writing; **no longer the default**) uses the safe, fixed behavior
- `keep_mitgcm_bugs=True` (**now the shipped default**) reproduces MITgcm exactly

### Recommended Action

**Superseded (1DMIX-057, resolved):** the "Recommended Action"/"For End Users"/
"Testing" subsections below describe the ORIGINAL decision
(`keep_mitgcm_bugs=False` default). That default has since been **flipped to
`True`** on measured evidence, not reverted here: on the real MITgcm capture
`global_oce_latlon`, the flip cuts `hbl` max_abs disagreement with real
MITgcm from 3.390e+01 m to 3.092e+00 m and cells exceeding 1% relative error
from 146/11575 to 10/11575 (`mixing_length`/`visc_az`/`diff_kz_s`/
`diff_kz_t` similarly improve 3.5x-8.7x) -- the port now reproduces the real,
unmodified Fortran unclamped extrapolation by default. See
`docs/model_contract.md`'s KPP section for the full evidence and
`Vertical_Mixing_Models/KPP/kpp_parameters.py::KPPParameters.keep_mitgcm_bugs`
for the current default and rationale. The analysis below is kept as
historical record of the reasoning that led to the original `False` default,
not as current guidance.

**For Python Port (original, 2026-08-20; superseded above):**
- ✅ **Already implemented** - bug fixed by default
- ✅ Validation mode available via `keep_mitgcm_bugs=True`
- ✅ Comprehensively documented in code comments
- **Default behavior**: Use bug-fixed code for all production runs
- **Validation runs**: Set `keep_mitgcm_bugs=True` only when comparing against buggy MITgcm output

**For MITgcm Community:**
- **Strongly recommend** uncommenting line 990 (the Sidorenko fix)
- Alternatively: Remove lookup tables entirely and compute wscale online (NEMO approach)
- Document that this changes results but improves stability
- Provide `KPP_SAFE_WSCALE` CPP option for users who need backward compatibility

**For End Users (original, 2026-08-20; superseded -- default is now `True`):**
- If using Python port: Keep default `keep_mitgcm_bugs=False`
- If using MITgcm: Consider manually uncommenting line 990 in `kpp_routines.F`
- Monitor for suspiciously large velocity scales under extreme forcing
- If model crashes with KPP, check if applying the Sidorenko fix resolves it

### Testing

**Python port testing (original, 2026-08-20):**
- Validated that `keep_mitgcm_bugs=True` reproduces MITgcm exactly (including bug)
- Validated that `keep_mitgcm_bugs=False` produces stable results under extreme forcing
- Confirmed nearest-neighbor behavior prevents negative table indexing

**MITgcm scenarios to test the fix:**
- Arctic winter convection with strong surface cooling
- Ice formation with brine rejection
- Deep water formation events
- Any scenario with strongly negative `bfsfc`

---

## Testing Methodology

Issues documented here were discovered through:

1. **Bit-level validation** against MITgcm using lab_sea verification experiment
2. **Instrumented comparison** of Python vs Fortran intermediate values
3. **Edge case analysis** at timestep 0 with weak initial forcing
4. **Systematic numerical testing** across 1000 timesteps, 20×16 grid

**Test Configuration:**
- Experiment: `lab_sea` (MITgcm verification)
- Grid: 20×16 horizontal, 23 vertical levels
- Duration: 1000 timesteps
- Python script: `scripts/run_kpp_from_netcdf_input.py`
- Input file: `mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc`

---

## References

### MITgcm Source Files
- `pkg/kpp/kpp_routines.F` - Main KPP subroutines (BLMIX, BLDEPTH, etc.)
- `pkg/kpp/kpp_calc.F` - KPP driver

### Python Port Files
*(paths corrected 1DMIX-062 — originally `1D_Mixing_Model/KPP/...`, which predates the
`Vertical_Mixing_Models/` reorganization; not a quoted-code citation, so corrected silently.)*
- `Vertical_Mixing_Models/KPP/kpp_scheme_specific.py` - Boundary layer mixing implementation
- `Vertical_Mixing_Models/KPP/kpp_core_driver.py` - Main KPP driver

### Related Documentation
- MITgcm KPP documentation: [MITgcm manual, Section 2.5](https://mitgcm.readthedocs.io/en/latest/phys_pkgs/kpp.html)
- Large et al. (1994): "Oceanic vertical mixing: A review and a model with a nonlocal boundary layer parameterization"
- `potential_bugs_and_inconsistencies.md` - General bug tracking across GGL90 and KPP

---

## Revision History

- **2026-08-20**: Initial documentation of hbl divide-by-zero issue
  - Identified during lab_sea validation
  - Confirmed to only affect timestep 0
  - Determined to be present in MITgcm source (not a Python port bug)
- **1DMIX-062** (this issue; documentation-only, no production code changed): repaired two
  stale code citations against a source-of-truth audit.
  - Issue 1's `kpp_scheme_specific.py:372-373` quotation was a genuine content divergence,
    not line drift: the quoted `np.sign`-based one-liner has been replaced (landing commit
    `cd4b2bc`, 2026-09-17, "1D update") by an explicit-zero-branch/`np.copysign` form that
    fixes a real MITgcm-fidelity gap at `wm_one[0]==0.0`. Original excerpt retained with a
    superseded marker; current behavior, the landing commit, and the real
    `pkg/kpp/kpp_routines.F:1493-1495` correspondence are all recorded above. Confirmed:
    current code matches Fortran's `SIGN` at zero; the pre-`cd4b2bc` one-liner did not.
  - Issue 1's `kpp_scheme_specific.py:433-440` quotation was pure line drift (now
    `506-513`) with byte-identical content; corrected in place.
  - Full remaining-citation audit performed against real source
    (`pkg/kpp/kpp_routines.F`, `Vertical_Mixing_Models/KPP/kpp_routines.py`): all other
    quoted code blocks in this file resolve exactly at their cited lines. Two stale
    (pre-reorganization) bare file-path references in "References" corrected silently
    (no quoted code, no behavioral claim).
  - Published-figure provenance check: whether this report's own text predates the fix
    is **undetermined by git**, not measured — the 2026-08-20 header date is the
    document's own self-declared claim, corroborated only circumstantially by the
    embedded `0820T0946` timestamp in an unrelated input-capture filename; git tracking
    of this file begins 2026-09-18 (`b68b847`, a pure create, not a rename), one day
    **after** the fix, and so cannot corroborate an earlier authorship date (corrected
    1DMIX-062 correction round 2, having survived round 1's retraction at this same
    claim's original location — see "Published Figures: Measured vs. Undetermined"
    above, which this bullet must match). The five currently-committed KPP validation
    PDFs in this same `reports/` directory, by contrast, **are** measured: all rendered
    2026-09-27, after the fix; see that same section above for exactly what is measured
    vs. undetermined (in particular: capture-pipeline provenance rests on gitignored
    `.nc` mtimes plus `CAPTURES.md`'s own claim, not on independent git history for the
    data).
