# GGL90 validation results: does the Python port reproduce MITgcm?

This document is the deep-dive answer to one half of this project's central
question: **does the Python port of MITgcm's GGL90 prognostic turbulence
closure reproduce MITgcm's own Fortran output?** (The sibling KPP scheme has
its own document, `KPP_port_validation/KPP_VALIDATION_RESULTS.md`.) It
assumes no prior familiarity with this project. For a reader new to the
codebase, it explains, per tested MITgcm capture and per idealized scenario:
what was tested and why, the quantified agreement, and — wherever a real,
non-floating-point-roundoff discrepancy exists — its causal mechanism in
plain terms: what MITgcm's real Fortran does, what this port does
differently (or not at all), and why that difference produces the observed
numbers.

GGL90 (`Vertical_Mixing_Models/GGL90/`) is prognostic: its one state
variable, turbulent kinetic energy (`TKE`), evolves in time via
`∂TKE/∂t = P + B - ε + ∂/∂z(K_e ∂TKE/∂z)` (shear production `P`, buoyancy
flux `B`, dissipation `ε`), and the eddy viscosity/diffusivity
(`K_m = c_k·L·√TKE`, `K_h = K_m/α`) both depend on a Gaspar et al. (1990)
mixing length `L` that is itself bounded by distance to the surface and
seafloor. This document's per-capture sections follow the same real MITgcm
validation data as the companion KPP document; each report stands on its
own and does not forward-reference the other file's sections — the "Shared
infrastructure" section below states, from GGL90's own point of view, the
equation-of-state and grid conventions the two schemes hold in common, and
where the two schemes' own real MITgcm packages genuinely differ (GGL90's
package, unlike KPP's, has real pressure-coordinate handling in the actual
Fortran).

The GGL90-specific report source directory (`GGL90_port_validation/reports/`)
holds the generated PDF/markdown reports this document's numbers trace to.

## How to read the numbers below

Every table below reports, for each of the four compared fields (`visc_az`,
`diff_kz`, `mixing_length`, `tke_after`) over **every** wet cell in the
capture — no active-mixing threshold is applied, unlike the companion KPP
document's convention. GGL90 always maintains a non-zero background
viscosity/diffusivity floor at every wet cell, so every wet cell is a
physically meaningful comparison, not just the ones exceeding some
"active mixing" cutoff:

- **Absolute** statistics (`median|diff|`, `p95|diff|`, `max|diff|`) give
  the difference in the field's own physical units (m²/s for `visc_az`/
  `diff_kz`, m for `mixing_length`, m²/s² for `tke_after`).
- **Relative** statistics (`median rel`, `p95 rel`, `max rel`, plus the
  fraction of wet cells exceeding 1% relative error) use
  `rel = |python − mitgcm| / max(|mitgcm|, 1e-12)`. The `1e-12` floor in the
  denominator means a cell where MITgcm's own captured value is genuinely
  at or near zero can register an outsized relative error from a tiny
  absolute difference — where that happens below, the absolute statistic is
  the one that reflects the physically meaningful size of the discrepancy,
  and this document says so explicitly.
- Every statistic excludes cells below a column's real seafloor and, for
  `isomip`'s floating-ice-shelf columns, cells above the real ice draft —
  the Python replay marks that excluded region `NaN` rather than guessing
  MITgcm's own fill convention there, so those cells are genuinely not
  compared, not silently treated as a match.

**Replay inputs (1DMIX-071).** MITgcm forms GGL90's vertical shear at a tracer point from `uVel` at
(i, i+1) and `vVel` at (j, j+1) (`ggl90_calc.F:541-556`, `calcMeanVertShear=.FALSE.`), i.e. the shear of
`ubar=(u(i)+u(i+1))/2`, `vbar=(v(j)+v(j+1))/2`. The captures hold `uVel(i,j)`, `vVel(i,j)` of every column of
the global grid, so the replay (`scripts/run_ggl90_from_netcdf_input.py::run`, default
`tracer_point_velocities=True`) rebuilds `ubar`/`vbar` from the neighbouring captured columns
(`scripts/tracer_point_inputs.py`; periodic wrap, MITgcm's default exchange) and feeds those to the port;
that reproduces the captured `vertical_shear` to roundoff (max relative difference <= 8.1e-16 in interior,
tile-edge and domain-edge columns of `isomip`, `global_ocean.90x40x15` and both `lab_sea` captures;
`tests/test_tracer_point_inputs.py`). Every table below is measured in that default mode unless it says
"column-local", the former replay (`tracer_point_velocities=False` / `--column-local`, kept, with one
old-mode test on `isomip` and one on `lab_sea`). Single-column captures are unchanged exactly
(`0.5*(u+u) = u`). A capture with `calcMeanVertShear=1` cannot be reproduced by averaging; the replay raises
`ValueError` for it (`1DMIX-074` tracks the port ignoring that flag).

## Shared infrastructure (grid, driver, equation of state)

GGL90 runs on the same single 1-D vertical column representation KPP uses,
and both schemes reproduce MITgcm's staggered z-grid index-for-index: cell
centers hold tracers/velocities and TKE, and interface array index `k` is
the top face of cell `k` (`k=0` is the ocean surface), with the surface
interface carrying zero diffusive flux. GGL90's own mixing-length limiters
build the water-column-depth bound from **interface** depths, not
cell-center depths (`GGL90/ggl90_scheme_specific.py::GGL90MixingLength`'s
`depth_to_surface`/`depth_to_bottom`, matching `pkg/ggl90/
ggl90_mixinglength.F`'s own interface-to-interface span) — using
cell-center spacing instead would under-count the true water column depth by
half the top cell's thickness plus half the bottom cell's, which matters
here because the mixing length directly sets the ceiling on `K_m`/`K_h` in
weakly-stratified, well-mixed water.

GGL90's TKE budget and its mixing-length formula both depend on the
buoyancy frequency `N²`, which this port computes from potential density via
the full Jackett & McDougall (1995) equation of state
(`main/eos.py::jmd95_eos`). The pressure argument fed to that equation of
state is `_depth_to_eos_pressure(depth, rho_const, gravity) =
rho_const*gravity*1e-4*(-depth)`, matching MITgcm's real
`rho_const*gravity*1e-5` bar-per-metre conversion factor exactly for each
experiment's own configured constants, rather than a flat `0.1 bar/m`
approximation. This keeps `N²` accurate to floating-point roundoff at every
level, which matters specifically for GGL90 because its mixing length varies
as `L ∝ 1/√N²`: any small relative error in `N²` is amplified wherever a
real water column sits close to neutral stratification (`N²≈0`), producing a
visible absolute `mixing_length` difference from an otherwise-negligible
error. Since 1DMIX-070 the captures are 17-significant-digit (exact
doubles); the `N²`-amplification that earlier showed up as a `mixing_length`
residual in `isomip` and `1D_ocean_ice_column` turned out to come from the
16-digit *print quantization of the captured T/S/`sigma_r` inputs* fed to the
replay, not from any port or EOS discrepancy (see the `isomip` section
below and the "Print precision" note under "Reproducibility"). The
amplification itself is real and would reappear for any input with
~1e-16 relative error near neutral stratification.

**GGL90's own real MITgcm package, unlike KPP's, has genuine
pressure-coordinate handling — and that difference is directly visible in
this project's own results.** Real MITgcm applies an explicit `coordFac`
scaling (`1` in z-coordinates, `g·ρ_0` in pressure coordinates) throughout
`ggl90_calc.F`, `ggl90_idemix.F`, and `ggl90_mixinglength.F`, converting
every depth/thickness-dependent quantity correctly regardless of which
vertical coordinate the configuration uses. This port has no equivalent
conversion anywhere in its own depth/thickness handling
(`column_grid.py`'s grid spec assumes metres unconditionally). Because real
MITgcm's own GGL90 Fortran *does* correctly convert and this port does not,
feeding this port a genuine pressure-coordinate capture's grid geometry
(which is then in pascals, not metres) used to produce finite but wrong values
with no error (measured size: see `global_ocean.cs32x15` below); since 1DMIX-073
`GGL90Driver.compute_mixing` rejects such geometry with a `ValueError`
(`main/column_grid.py::validate_zcoordinate_geometry`, shared with KPP), so the
effect is now an explicit refusal, not a number. This is a different situation
from KPP's own real MITgcm package, which has no `coordFac` handling in its
own Fortran source at all; the coordinate-conversion gap is a property of
which real MITgcm package is being compared against, not just of this
port.

## The TKE buoyancy-term mechanism

One mechanism explains almost every `tke_after` disagreement below wherever
a capture's viscosity and diffusivity backgrounds differ, so it is worth
stating once here rather than re-deriving it per experiment.

MITgcm's real TKE tendency equation uses a specific quantity for its
buoyancy term: the eddy viscosity `KappaM`, floored only by its own
*viscosity* background, divided by the Prandtl number. This is subtly
different from the *exported*, diagnostic `diff_kz` field, which is
additionally floored by the *diffusivity* background and capped by a
maximum diffusivity — correct as an output, but not the quantity MITgcm's
own TKE equation actually uses internally. This port computes a separate,
internal-only `kappa_h_tendency = kappa_m / tke_prandtl_number` (unfloored
by the diffusivity background, uncapped) and feeds that — not the
diagnostic value — into the TKE buoyancy term
(`GGL90/ggl90_core_driver.py::GGL90Driver.step_tke_forward`); the diagnostic
`visc_az`/`diff_kz` outputs themselves never use this internal quantity and
are unaffected by it. The two quantities coincide, and this distinction is
invisible, whenever a configuration's viscosity and diffusivity backgrounds
happen to be numerically equal; every one of this project's 6 idealized
scenarios sets `viscAz=5e-5 ≠ diffKzS=1e-5`, so the two diverge at every
quiescent level in that comparison, which is exactly where the effect is
visible below. Confirmed by direct substitution at the single
worst-mismatching cell in each of the 6 scenarios: recomputing the buoyancy
term with the correct, unfloored quantity collapses the residual to
floating-point roundoff (1e-18–1e-20) in every case. `global_ocean.90x40x15`
and `global_ocean.cs32x15` are unaffected by this specific mechanism because
their own `viscAz` and `diffKzS` backgrounds coincide at `0`, or because
their disagreement is already dominated by the much larger IDEMIX/pressure-
coordinate mechanisms described in their own sections below.

## `vermix`, 20 timesteps — the baseline single-column capture

MITgcm's standard GGL90 verification experiment: a single column, 26
levels, `mxlMaxFlag=3` — the first GGL90 capture this project validated
against, and the one every later GGL90 change is regression-checked
against.

| Field | Median\|diff\| | P95\|diff\| | Max\|diff\| | Median rel | P95 rel | Max rel | >1% | N |
|---|---|---|---|---|---|---|---|---|
| `visc_az` | 0 | 0 | 1.320e-05 | 0 | 0 | 0.073% | 0% | 520 |
| `diff_kz` | 0 | 0 | 1.320e-05 | 0 | 0 | 0.219% | 0% | 520 |
| `mixing_length` | 7.97e-05 | 3.36e-04 | 7.76e-03 | 0.069% | 0.193% | 0.243% | 0% | 520 |
| `tke_after` | 0 | 1.02e-09 | 7.84e-07 | 0 | 0.030% | 0.307% | 0% | 520 |

Every field agrees comfortably within this project's 1% clean bar (max relative error 0.07%-0.31% across the four fields, per the table above): `visc_az`/
`diff_kz`/`mixing_length` never depend on the TKE buoyancy-term mechanism
above (they are diagnostic formulas, not the prognostic TKE update), and
`tke_after`'s own worst-case relative error (0.31%, applying the TKE
buoyancy-term mechanism above end-to-end through this experiment's coupled
implicit solve) stays comfortably below the 1% bar this project uses to call
a field's agreement clean.

## `1D_ocean_ice_column`, 11,000 timesteps (`mxlMaxFlag=3`) — cross-scheme test on a KPP-only-configured experiment

The same real MITgcm sea-ice-coupled, single-column configuration exercises
both this project's schemes: it is run through GGL90 here even though this
experiment's own MITgcm configuration enables only KPP by default — a
genuine test of GGL90 physics on a configuration that was never built with
GGL90 output validation in mind.

| Field | Median abs. diff | Max abs. diff | Max rel. err. | Fraction >1% rel. err. |
|---|---|---|---|---|
| `visc_az` | 0 (exact) | 3.3e-17 | 4.0e-13% | 0% |
| `diff_kz` | 0 (exact) | 1.2e-17 | 4.1e-13% | 0% |
| `mixing_length` | 1.5e-16 | 2.6e-13 | 3.8e-13% | 0% |
| `tke_after` | 0 (exact) | 5.4e-20 | 1.2e-12% | 0% |

(All statistics over the full 253,000 wet column-timesteps, on the
17-digit capture of 1DMIX-070. The previous, 16-digit capture of the same
run gave max abs 8.3e-10 / 8.3e-11 / 2.6e-5 / 2.9e-15 and max rel 3.8e-5% /
3.8e-5% / 3.8e-5% / 1.0e-7% with the same port — the earlier 1.8e-9 /
1.8e-10 / 5.6e-5 / 6.6e-15 figures of this table were the same quantity
before the 1DMIX-068 `N²` operation-order fix — and those residuals were
print quantization of the captured inputs, not port error.) This is this
project's cleanest GGL90 experiment — no IDEMIX, no floating ice shelf, no
pressure-coordinate confound — and it shows it: every field is exact to
floating-point roundoff, with zero cells exceeding even a strict 1e-4 m²/s
threshold on `visc_az`/`diff_kz`. `tke_after`'s own tiny remaining relative
error (1.2e-12%) is strong evidence the TKE buoyancy-term mechanism above is
handled correctly here, not merely coincidentally invisible: this
experiment's real `viscAz` (1.93e-5) and `diffKzS` (1.46e-7) backgrounds
differ by two orders of magnitude, which is exactly the condition under
which an incorrect implementation of that mechanism would produce its
largest error. The residual instead sitting at floating-point roundoff
confirms the internal `kappa_h_tendency` computation is exactly right, not
merely invisible the way it would be if the two backgrounds happened to
coincide.

## `isomip` — the only `ALLOW_SHELFICE` capture

An 8-tile (2×4, 50×100×30) domain under a floating ice shelf — the only
capture in this project where the real ocean surface is not always the
topmost array index: 2,401 of 4,851 wet columns have a real
dry-top-then-wet-below profile, because the ice draft masks the geometric
surface. Under a floating ice shelf, MITgcm's own effective ocean surface
(`kSrf`) shifts down to wherever the real top wet cell is, not always array
index 0.

| Field | Median\|diff\| | Max\|diff\| | Max rel | Fraction >1% rel | N |
|---|---|---|---|---|---|
| `visc_az` | 0 | 9.5e-18 | 3.9e-13% | 0% | 1,437,204 |
| `diff_kz` | 0 | 1.7e-18 | 3.9e-13% | 0% | 1,437,204 |
| `mixing_length` | 4.6e-18 | 1.1e-13 | 3.8e-13% | 0% | 1,437,204 |
| `tke_after` | 0 | 9.2e-06 | 100.0% | 1.12% (16,123 cells) | 1,437,204 |

(17-digit capture, 1DMIX-070. `visc_az` and `mixing_length` were previously
tabulated at 2.4e-10 and 4.3e-3 maximum absolute difference; the same port
on the earlier 16-digit capture gives 1.1e-10 and 3.25e-4 — 4.3e-3 predates
the 1DMIX-068 `N²` fix — and those two residuals were print quantization of
the captured inputs, see below. At 17 digits with the column-local replay the `diff_kz` and `tke_after`
rows were 1075 cells (max_abs 2.9e-3, 0.075%) and 17,934 cells (max_abs 9.081e-6, 1.25%, 232.7% max rel);
the table above is the 1DMIX-071 tracer-point replay: 1DMIX-071 removed the whole `diff_kz` row and 1,811
of the `tke_after` cells, see below.)

**`diff_kz`: the former `kSrf+1` residual (0.075% of cells, max_abs 2.9e-3) was a replay-input artifact
(1DMIX-071).** The 1,075 cells (1,069 at first-wet+1, 6 at +2) were attributed under 1DMIX-038 to the
background-floor convention at `kSrf`, but the replay fed the port column-local velocities, so its shear,
Richardson number and Prandtl number differed from MITgcm's at those near-neutral cells; with MITgcm's
tracer-point velocities the same port gives 0 cells above 1% and max_abs 1.7e-18 (max_rel 3.9e-15).
The old figures remain executable (`test_isomip_diff_kz_column_local_gap`). The `kSrf` convention below is
still what makes `diff_kz` exact AT `kSrf`. This
port's final background-floor assignment for `diff_kz` threads an explicit
`is_true_surface` flag through the mixing-coefficient code
(`ggl90_mixing_coefficients.py::compute_viscosity_diffusivity`) so that, at
a ShelfIce column's real `kSrf`, the port applies MITgcm's real captured
convention there — a plain background floor, not the ordinary
zero-diffusive-flux surface convention — rather than the fixed array-index-0
assumption that convention would otherwise apply at the wrong level.
`visc_az` needs no such flag: its own final-assignment order happens to
apply the background floor before the surface-zeroing step, the opposite
order from `diff_kz`, so it was never exposed to this defect in the first
place. `tke_after`'s post-solve minimum-TKE re-mask uses the same explicit
`is_true_surface` flag, since MITgcm forces `GGL90TKE` to exactly `0` at a
ShelfIce column's real `kSrf` rather than the ordinary surface-Dirichlet
value.

**`mixing_length` has no residual: the former "`kSrf+1` residual" was
print quantization (corrected by 1DMIX-070).** Through 1DMIX-069 this
document reported a `mixing_length` residual one level below `kSrf`
(max_abs 4.3e-3, later 3.25e-4 after the 1DMIX-068 `N²` fix; never above 1%
relative) and attributed it to a general near-neutral (`N²≈0`)
EOS-precision amplification, based on backing out each side's implied `N²`
from a mismatching cell (the two `N²` differed by ~0.1% relative). The
mechanism it described is real — `mixing_length ∝ 1/√N²` amplifies any
relative `N²` error at a near-neutral cell — but its source was the
capture, not the port: the declared capture printed T, S and `sigma_r` with
16 significant digits (`FORMAT E25.16`), so the `N²` computed from those
printed values had ~1e-16-relative input noise that near-neutral cells
amplified. Recapturing the identical run with 17 digits (`ES25.16`, exact
doubles; MITgcm's own fields agree between the two captures to <= 5.9e-16
relative) and replaying the same port gives `mixing_length` max_abs 1.07e-13
(max_rel 3.8e-15, 0 cells above 1%) versus 3.25e-4 on the 16-digit capture,
and `visc_az` 9.5e-18 versus 1.1e-10. The regression test
`test_isomip_mixing_length_ksrf_plus_1` accordingly no longer asserts a
lower-bounded gap (its old `1e-4 < max_abs` floor certified the artifact)
but a roundoff-level upper bound (`< 1e-11`, tightened from `< 0.01`).

**`tke_after`'s residual (1.12% of cells, 16,123 cells, max_abs 9.2e-6) is real, shear-independent and
identical at 16 and 17 digits (1DMIX-071 removed 1,811 of the former 17,934 cells).** It carries the `kSrf`
background-floor effect on the coupled TKE solve and the related first-wet `+1`/`+2` levels: with MITgcm's
tracer-point velocities its 16,123 cells above 1% sit at first-wet level `+1` (9,542 cells, max_abs 9.2e-6)
and `+2` (6,581 cells, max_abs 2.6e-8), all of them, and the same 9,542 + 6,581 cells appear with the
column-local replay. The other 1,811 cells of the column-local replay (first-wet+5..+7, rows y=50-52, steps
1-11, max_abs 9.3e-9) were replay-input artifacts and vanish. `mixing_length`
agrees to 1e-13 at every one of those levels. That rules `mixing_length`
(and hence the near-neutral `N²` amplification the earlier text invoked for
the `+1`/`+2`/row-50 part) out as their cause; a per-cell probe from
1DMIX-048 (`kappa_m`, mixing length, Prandtl number and `N²` all match
MITgcm at the affected locations) is consistent with that, and the
implicit TKE solve redistributing the `kSrf`-boundary effect is the
explanation this document carried before. The residual mechanism at the
`+1`/`+2` cells was not re-traced by 1DMIX-070 or 1DMIX-071 (a follow-up candidate: 9,542 + 6,581 cells); it
stays a documented known gap under 1DMIX-038/048, neither a print artifact nor a shear effect.

## `global_ocean.90x40x15` — the only clean, z-coordinate IDEMIX capture

A 36-tile (9×4, 90×40×15) real z-coordinate global configuration with
`useIDEMIX=.TRUE.` — GGL90's optional internal-wave-mixing extension. This
is the clean IDEMIX signal in this project's coverage because it is a
genuine z-coordinate ocean configuration, isolated from the
pressure-coordinate confound described in the next section.

| Field | Fraction >1% rel | Max abs. diff | N |
|---|---|---|---|
| `visc_az` | ~0.04% | 5.6 | 485,840 |
| `mixing_length` | ~0.04% | 15.5 | 485,840 |
| `diff_kz` | 50.9% | 2.7 | 485,840 |
| `tke_after` | 54.4% | 446 | 485,840 |

(1DMIX-071, tracer-point replay: `diff_kz` 247,442 cells (50.93%), `tke_after` 264,332 (54.41%); the
column-local replay gave 247,456 / 264,515, so the shear moves only 14 / 183 of these cells.
`visc_az` / `mixing_length` 183 / 206 cells are identical in both modes: that small tail is not a
shear or replay-input effect and is not root-caused here.)

**Root cause.** Real MITgcm's IDEMIX extension adds a genuine extra source
term to the TKE budget (`IDEMIX_gTKE`, internal-wave-energy dissipation) and
modifies the Prandtl-number formula that feeds `diff_kz`. This port
implements **no** IDEMIX physics at all: `GGL90Parameters.use_idemix` is a
declared field with no consumer anywhere in the port, confirmed by direct
read and a repository-wide search for its name — the same
declared-but-never-read pattern this port also has for
`calc_mean_vert_shear` (below). Instrumenting the real Fortran directly
captures `IDEMIX_gTKE` for comparison; the correlation between the size of
that captured, physically real term and the actual `tke_after` mismatch is
`corr = 0.998` over 243,692 column-timesteps — the port's error tracks the
real missing physics almost perfectly, not some unrelated numerical noise.
`visc_az`/`mixing_length`'s much smaller mismatch fraction (~0.04% vs.
`diff_kz`/`tke_after`'s 51%/54%) is itself consistent with this mechanism:
`KappaM`/mixing length do not depend on `IDEMIX_gTKE` at all in either
implementation; only the Prandtl-number formula (feeding `diff_kz`) and the
TKE update (feeding `tke_after`) do. This is a known, decisively-quantified,
by-design capability gap: implementing it would require porting MITgcm's
own internal-wave energy budget, a real physics addition, not a bug fix.

## `global_ocean.cs32x15` — the only pressure-coordinate capture (port side rejected since 1DMIX-073)

A 12-tile cubed-sphere (384×16×15) configuration, also `useIDEMIX=.TRUE.` —
surveyed as this project's other candidate IDEMIX capture, but this
configuration sets `buoyancyRelation='OCEANICP'`, which MITgcm maps directly
to `usingPCoords=.TRUE.`: its vertical grid spacing (`delR`) is genuinely
expressed in pascals, not metres.

**Status since 1DMIX-073.** `GGL90Driver.compute_mixing` now raises `ValueError`
on this capture's geometry (positive `depth`, max 4.9467e7 Pa;
`cell_thickness` 5.03e5 to 7.11e6), so there is no port replay of it any more
and the table and root-cause paragraph below are **HISTORICAL** (what the port
returned before the guard existed). The former test
`test_global_ocean_cs32x15_pressure_coordinate_gap` asserted these finite wrong
values as a "known gap"; it is replaced by
`test_global_ocean_cs32x15_port_rejects_pressure_coordinate_input` plus two MITgcm-side
tests (capture geometry; the `coordFac^2` factor in MITgcm's own `diff_kz`). The
numbers were **re-measured for 1DMIX-073 on the pre-change code** (a `git archive`
extraction of HEAD 65939cf; the full capture, 10 timesteps; statistics by the test module's
own `_diff_and_rel`; `bob-1DMIX-073-evidence.md` unit 0): fraction >1% rel 0.6251 / 0.6273 /
0.6272 / 0.6477 and max abs 99.99992 / 2.0149e9 / 1.4492e7 / 4.1995e5 for `visc_az` /
`diff_kz` / `mixing_length` / `tke_after`, identical to the rounded table. **What N counts**:
N = 813,820 is every cell the harness left non-NaN (all finite, 0 NaN, 0 inf). It is NOT
all ocean: 555,220 are computed ocean cells (non-zero input temperature) and 258,600 are
cells of land columns, which the harness zero-fills on the port side and which are zero in
MITgcm too, so they never exceed 1% and dilute the fractions. Restricted to the 555,220
ocean cells the same measurement gives fractions 0.9163 / 0.9195 / 0.9193 / 0.9494 (the
same counts of 508,739 / 510,536 / 510,393 / 527,111 cells above 1%) and the same max abs
(`frac_ocean_only.py`).
**Reading note**: the `diff_kz` 2.0149e9 is MITgcm's own captured value (the port's
`diff_kz` there is capped at 100). The instrumented MITgcm source says why
(`mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`): `coordFac = gravity * rhoConst` when
`usingPCoords` (line 257); the captured `visc_az` is `KappaM`, stored in `GGL90viscOutput`
(lines 518-519) before any `coordFac` scaling; and lines 1088-1090 set
`GGL90diffKr = MAX( MIN(visctmp/TKEPrandtlNumber, GGL90diffMax)*coordFac*coordFac, diffKrNrS )`.
So the captured `diff_kz` carries `coordFac^2` (Pa²/s scale) and is not a metres-scale
diffusivity. Checked on the capture over all 510,536 cells with `visc_az > 0`: that law,
with `TKEPrandtlNumber` from the capture and `GGL90diffMax`, `diffKzS`, `gravity`, `rhoConst` from
its attributes, reproduces `diff_kz` with maximum relative deviation 0.0 (the other 411,064
cells have `visc_az == 0` and `diff_kz == 0`; none reaches the `GGL90diffMax` cap); asserted
by `test_global_ocean_cs32x15_mitgcm_ggl90_diffkz_is_in_coordfac_squared_units`. The port-versus-MITgcm
`diff_kz` figure below therefore mostly records MITgcm's own units, not a port
error of that size. The tracked report
`reports/ggl90_validation_global_ocean_cs32x15_idemix_10.pdf` (and the gitignored
`outputs_from_python/python_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` it was built from)
are likewise pre-1DMIX-073 artefacts of the old port behaviour; `run_ggl90_from_netcdf_input.py::run`
cannot regenerate them, so they are kept as historical records only.

| Field | Fraction >1% rel (of N) | Max abs. diff | N (non-NaN cells, incl. 258,600 zero-filled land cells) |
|---|---|---|---|
| `visc_az` | 62.5% | 100 (at this port's `GGL90viscMax` cap) | 813,820 |
| `diff_kz` | 62.7% | ~2.0e9 | 813,820 |
| `mixing_length` | 62.7% | ~1.4e7 | 813,820 |
| `tke_after` | 64.8% | ~4.2e5 | 813,820 |

**Root cause (historical, pre-1DMIX-073 behaviour).** As described under "Shared infrastructure" above, this
port has no `coordFac`-equivalent unit conversion anywhere in its
depth/thickness handling, while real MITgcm's own GGL90 Fortran does. Every
length-based formula this port evaluates — mixing-length ceilings, the TKE
boundary condition, and so on — receives this capture's raw pressure values
and treats them as if they were depths. Point-verified at one cell: real
MITgcm computes `mixing_length = 1277 m` there; this port computes
`14,493,349 m` (14,493 km — larger than Earth's radius) — a roughly
10,000× error, which is why more than 62% of every field's N cells (91-95% of the 555,220 ocean cells, the rest of N being zero-filled land) exceed the
1% relative-error threshold. This is *not* primarily an IDEMIX signal: the
coordinate confound is roughly an order of magnitude larger than IDEMIX's
own contribution, which is why `global_ocean.90x40x15` above, not this
capture, is this project's clean IDEMIX-gap measurement. This capture's
disagreement is not a candidate for a future fix: pressure-coordinate
support is a permanent, deliberate scope boundary for this project (see
"Limitations" below), so the port refuses this geometry (1DMIX-073) unless that
scope decision itself is revisited.

A smaller, related, and still-undeveloped gap from the same capture:
`calc_mean_vert_shear`, a real, alternate vertical-shear formula this
experiment's own configuration enables, is likewise declared but never read
anywhere in this port — the same dead-placeholder pattern as `use_idemix`
above. It is deferred rather than implemented speculatively, since its only
observed instance so far is in this now-out-of-scope, pressure-coordinate
capture.

## `lab_sea` (999 timesteps and 6-month) — GGL90 on the KPP-native multi-column grid (1DMIX-054)

The first GGL90 capture of the grid whose existing captures are all KPP: `lab_sea`, 20x16 single
tile, 23 levels (10-500 m), real land columns, sea ice (SEAICE + EXF), GMRedi, `useCDscheme`,
JMD95Z, `deltaT=3600 s`. The run restarts from the stock `pickup.0000000001` exactly as the KPP
captures do and has the same two durations: **999 timesteps** (5,764,230 wet cells; all replayed)
and **4368 timesteps** (the 6-month run; steps 2000-2099 replayed, 577,000 wet cells -- its first
999 steps are bitwise identical to the 999-step capture, measured). The namelist is **constructed**
(no stock MITgcm experiment has a `data.ggl90` for this grid): **every GGL90 parameter is at the MITgcm
default** (`GGL90alpha=1`, `mxlMaxFlag=0`, `GGL90TKEmin=1e-11`, ...), because none of this project's
other GGL90 namelists (vermix / IDEMIX / ECCO-style) can be derived from `lab_sea`'s own geometry or
forcing; a constructed `pickup_ggl90.0000000001` carrying the cold-start TKE (`GGL90TKEmin`)
is needed because `nIter0=1` makes GGL90 require its own pickup. Details, justification and
recipes (G6/G7): `mitgcm_verification_mods/lab_sea/ggl90_input_validation/README.md`, `CAPTURES.md`.
The header is MITgcm's default `GGL90_OPTIONS.h` (an earlier scaffold's vermix-era header defining
`GGL90_MISSING_HFAC_BUG` was removed).

| Field | 999-step: median / max abs. diff | >1% rel. (cells) | 6-month (steps 2000-2099): max abs. diff | >1% rel. (cells) |
|---|---|---|---|---|
| `visc_az` | 0 / 1.3e-14 | 0 | 1.5e-14 | 0 |
| `mixing_length` | 0 / 1.1e-11 (values to ~3,300 m) | 0 | 1.5e-11 | 0 |
| `diff_kz` | 0 / 9.8e-15 | 0 | 8.4e-15 | 0 |
| `tke_after` | 0 / 1.6e-18 | 0 | 2.6e-19 | 0 |

All four fields are **clean to roundoff** on this multi-column, sea-ice-covered grid, with MITgcm's tracer-point
velocities (1DMIX-071, measured 2026-10-02; the clean-capture bounds of the test module are met without
being widened). Through 1DMIX-070 `diff_kz` and `tke_after` were asserted as labelled **known gaps**
(1DMIX-054) -- with the column-local replay they were `diff_kz` 1,800 cells (0.031%, max_abs 2.15) and `tke_after`
32,862 cells (0.570%, max_abs 1.07e-3) on the 999-step capture, 1,430 (0.248%, max_abs 1.56) and 6,497
(1.126%, max_abs 3.6e-5) on steps 2000-2099 -- and were REPLAY-INPUT ARTIFACTS, not port gaps. The old-mode numbers
stay executable (`test_lab_sea_6mo_column_local_gap`, exactly 1,430 / 6,497). The season dependence of the
column-local gap (four 100-step windows of the 6-month run: 0.131% / 0.97% at steps 1500-1599, 0.248% / 1.13% at
2000-2099, 0.057% / 0.90% at 3000-3099, 0.0175% / 0.36% at 4268-4367 in `diff_kz` / `tke_after`) is
recorded only as the old-mode behaviour; the clean tracer-point replay was measured on steps 2000-2099 and the
full 999-step capture, not re-measured on the other three windows.

**Mechanism (confirmed by the fix).** MITgcm's `verticalShear` at tracer point (i,j), level k is
`((ubar(k-1)-ubar(k))^2 + (vbar(k-1)-vbar(k))^2)/drC^2` with `ubar=(uVel(i)+uVel(i+1))/2`,
`vbar=(vVel(j)+vVel(j+1))/2` (`ggl90_calc.F:541-556`, the default `calcMeanVertShear=.FALSE.` branch), while the
former replay handed the port `uVel(i,j)`, `vVel(i,j)` only. Rebuilt from the neighbouring columns of the
capture, the shear matches MITgcm's captured `vertical_shear` to a relative error <= 8e-16 (first 300 steps,
all columns including domain edges; `tests/test_tracer_point_inputs.py` and
`test_lab_sea_999_shear_is_four_point_average`), while the column-local shear is off by a median 64-74%.
The column-local mismatches were 96.9% in levels 1-4 (`tke_after`, evenly spread over the run, 91.9% in
cells with `tke_before >= 1e-8`) and, for `diff_kz` (through `Pr = f(Ri)`,
`Ri = N^2/(shear^2 + GGL90eps)`), 95.4% near-neutral cells with shear below 1e-6. `visc_az` and
`mixing_length` do not depend on the shear and were always exact. No port source changed: the replay
script feeds different inputs (default `tracer_point_velocities=True`; the replay also gained optional
`first_timestep`/`last_timestep` under 1DMIX-054).

**Consequence for the other multi-column GGL90 captures (1DMIX-071, measured).** `isomip`: the `diff_kz` gap was a
replay-input artifact (1,075 -> 0 cells) and 1,811 of the 17,934 `tke_after` cells were (the remaining 16,123 at
first-wet+1/+2 are real); `global_ocean.90x40x15` (IDEMIX): unchanged (the missing-IDEMIX gap and its
`visc_az`/`mixing_length` tail are not shear effects); `global_ocean.cs32x15`: pressure coordinates, rejected by the
port since 1DMIX-073, no replay.

## The 6 idealized scenarios, standalone Fortran driver — isolating the physics from any capture noise

This project's own 6 idealized forcing scenarios (calm baseline, arctic
convection, hurricane wind, tropical heating, heavy rain freshening,
combined storm) have no MITgcm "ground truth" NetCDF — they were never run
through a full MITgcm model. Instead, this port's own computed column state
for each scenario is fed directly into the real, unmodified Fortran
`GGL90_CALC` via a standalone driver
(`mitgcm_verification_mods/ggl90_standalone_driver/`), isolating the
diagnostic mixing-coefficient formulas and the one prognostic variable
(TKE) from any capture/harness noise. The statistics below are
`compare_scenario_ggl90_standalone.py::compare`'s own output, reproduced
from the on-disk scenario data.

| Scenario | n×nz | `visc_az` max_abs / max_rel | `mixing_length` max_abs / max_rel | `tke_after` max_abs / max_rel (n>1%/total) |
|---|---|---|---|---|
| `calm_baseline` | 288×50 | 1.06e-15 / 4.0e-15 | 1.19e-12 / 4.0e-15 | 7.59e-19 / 8.8e-14 (0/14,400) |
| `arctic_convection` | 5000×23 | 2.22e-15 / 4.3e-15 | 1.14e-12 / 4.3e-15 | 2.17e-18 / 9.5e-13 (0/115,000) |
| `hurricane_wind` | 144×50 | 1.87e-14 / 4.1e-15 | 1.48e-12 / 4.1e-15 | 4.44e-16 / 1.4e-11 (0/7,200) |
| `tropical_heating_diurnal` | 144×50 | 2.78e-16 / 4.0e-15 | 1.42e-12 / 4.2e-15 | 1.08e-19 / 1.3e-13 (0/7,200) |
| `heavy_rain_freshening` | 144×50 | 9.02e-17 / 4.1e-15 | 1.25e-12 / 4.2e-15 | 1.56e-17 / 3.0e-14 (0/7,200) |
| `combined_storm` | 72×50 | 2.13e-14 / 4.2e-15 | 1.42e-12 / 4.0e-15 | 1.55e-15 / 7.9e-14 (0/3,600) |

**All four fields, in every one of the six scenarios, match the real
Fortran `GGL90_CALC` to floating-point roundoff.** The worst `max_rel`
across every scenario and every field is about `1.4e-11`, and zero of
618,400 total field-cells (across all six scenarios) exceed 1% relative
error anywhere. `visc_az`/`diff_kz`/`mixing_length` are diagnostic formulas
that never touch the TKE buoyancy-term mechanism above, so they were always
exact here; `tke_after`, the one prognostic field this comparison exercises,
reaches the same floating-point-roundoff bar once that mechanism (described
under "The TKE buoyancy-term mechanism" above) is applied correctly — this
is the most direct evidence available that the mechanism is complete and
correct, since every one of these six scenarios sets `viscAz≠diffKzS` and
would otherwise expose exactly the divergence that mechanism describes.
GGL90's own `combined_storm` scenario shows no distinguishing behavior of
its own here: it matches the other five scenarios' floating-point-roundoff
agreement exactly, a genuinely different outcome from this same idealized
scenario's own KPP-side comparison, which depends on a different,
KPP-specific numerical switch this document does not need to discuss.

## Limitations

These are physical and methodological properties of this validation
exercise and this port, not open action items:

- **No IDEMIX internal-wave-mixing physics.** This port implements none of
  MITgcm's optional internal-wave-driven mixing extension: no
  `IDEMIX_gTKE` source term in the TKE budget, and no corresponding
  modification to the Prandtl-number formula that feeds `diff_kz`.
  `GGL90Parameters.use_idemix` is declared but has no consumer anywhere in
  the port. Any configuration that enables `useIDEMIX` will show a real,
  physically meaningful disagreement in `diff_kz`/`tke_after` that scales
  with the true size of the missing internal-wave source term, as measured
  on `global_ocean.90x40x15` above — this is a capability gap, not
  something a future numerical fix could close without porting real new
  physics.
- **No pressure-coordinate (`coordFac`) unit conversion.** Real MITgcm's
  own GGL90 Fortran converts every depth/thickness-dependent quantity by an
  explicit `coordFac` scaling that differs between z-coordinate and
  pressure-coordinate configurations; this port has no equivalent anywhere
  in its depth/thickness handling and assumes metres unconditionally. A
  pressure-coordinate configuration is out of scope for this project
  permanently, not merely untested: every one of this project's own
  captures and idealized scenarios is a z-coordinate ocean configuration,
  which is the only configuration this validation exercise is designed to
  say anything meaningful about. Both schemes now REJECT such geometry with a
  `ValueError` (`main/column_grid.py::validate_zcoordinate_geometry`, step 0 of
  `KPPDriver.compute_mixing` since 1DMIX-072 and of `GGL90Driver.compute_mixing`
  since 1DMIX-073). Before the guards: the equivalent KPP limitation was expected
  to produce a misleading close agreement; measured under 1DMIX-054 it did not (MITgcm's own KPP
  aborts at iteration 1 and the port returned NaN in most interior cells; see
  `KPP_VALIDATION_RESULTS.md`), and GGL90 returned finite but wrong values
  (`global_ocean.cs32x15` above), the harder failure to notice.
- **`calc_mean_vert_shear` is declared but not implemented.** This
  configuration flag (a real, alternate vertical-shear formula) has no
  consumer anywhere in the port, the same declared-but-dead pattern as
  `use_idemix`. Its only observed instance in this project's own captures
  is the now-permanently-out-of-scope pressure-coordinate capture, so it
  remains deferred rather than implemented speculatively for a
  configuration this project does not otherwise validate against. The
  tracer-point replay (1DMIX-071) refuses such a capture with a `ValueError`
  (MITgcm's `calcMeanVertShear=.TRUE.` shear is a sum of squares of four
  separate differences, not the shear of an averaged velocity); the flag
  being ignored by `GGL90Driver` is tracked as 1DMIX-074.
- **The replay's neighbour rule is periodic wrap.** `tracer_point_velocities`
  assumes MITgcm's default periodic exchange at the domain edge (closed basins
  are closed by land columns); no capture records its periodicity, so the rule is
  validated only against the captured `vertical_shear` (exact in every class of
  every in-scope multi-column capture; a zero-fill rule is wrong at the wet
  domain edges of `global_ocean.90x40x15`). Where the periodic-wrap rule is actually verified (wrap and zero-fill give different reconstructions and wrap matches the capture; counts from this issue and from Richard's review): x on `global_ocean.90x40x15` (GGL90 2,790 of 3,830 domain-edge interfaces; KPP 6,039 of 10,220), `global_oce_latlon` (1,610 cells, review) and `seaice_obcs` (245); y only on `seaice_obcs` and the 1x1 single-column captures. NOT verified: y on the global grids and on every GGL90 capture, and both axes on `lab_sea` and `isomip`, because wrap and zero-fill give identical reconstructions there (closed basins whose edge columns are land).
- **The `ALLOW_SHELFICE` `is_true_surface` handling is exercised only by
  the MITgcm-comparison verification harness, not by this project's own
  scenario-driving code path.** `main/mixing_adapter.py` (the entry point
  this project's own idealized scenarios use) has no `ALLOW_SHELFICE`
  support and always uses the ordinary array-index-0 surface convention;
  the explicit `is_true_surface` flag described under `isomip` above is set
  by the MITgcm-replay harness only, for columns it knows are sliced from a
  real floating-ice-shelf capture.
- **The Rib/Ricr-style threshold sensitivity that was credited with several KPP
  discrepancies (1DMIX-071 showed much of the multi-column KPP `hbl` tail to be a
  replay-input effect instead, and 1DMIX-080 showed most of the rest to be KPP's Jerlov
  water type; no remaining KPP figure is attributed to it by measurement) has no direct GGL90 analogue.** GGL90 has no hard
  Richardson-number threshold anywhere in its own formulas; its
  discrepancies are instead governed by the mechanisms in this document
  (the TKE buoyancy-term distinction, the `isomip` `kSrf` boundary
  convention, and the fact that `mixing_length ∝ 1/√N²` amplifies any input
  noise near neutral stratification — which, in the 16-digit captures, was
  the print quantization of the captured T/S/`sigma_r`, not a port
  discrepancy; see the `isomip` section), all of which are bounded,
  understood numerical effects rather than a hard-threshold-crossing
  phenomenon.

## Reproducibility

The `vermix` and `1D_ocean_ice_column` (11,000-step) statistics above come
from the PDF validation reports generated by
`scripts/generate_ggl90_validation_report.py::compute_field_statistics`,
run against the paired NetCDF captures under
`GGL90_port_validation/{inputs,outputs}_from_mitgcm/`; these are
cross-checked against, and consistent with, the regression assertions and
docstrings in
`MITgcm_to_Python_port_verification/tests/test_ggl90_mitgcm_validation.py`,
which drive the same replay entry point
(`scripts/run_ggl90_from_netcdf_input.py::run`). The `isomip`,
`global_ocean.90x40x15` and (1DMIX-054) `lab_sea` statistics come from
that same test module's own fresh measurements (default tracer-point replay since 1DMIX-071; the
`--column-local` option of the replay script reproduces the former figures). The `global_ocean.cs32x15` statistics are
**historical**: the test module no longer measures them (the port rejects that capture since
1DMIX-073). They were measured once on 2026-10-02 on the pre-change code, by replaying the
full capture through a `git archive` extraction of HEAD 65939cf with the same replay entry
point and the module's own `_diff_and_rel` (section `global_ocean.cs32x15` above;
`devel-loop/loop_state/bob-1DMIX-073-evidence.md` unit 0).

**Print precision (1DMIX-070).** All five captures above were recaptured on
2026-09-30 with the instrumented Fortran printing 17 significant digits
(`ES25.16`, exact for a double; the earlier captures used `E25.16`, 16
digits), and the PARAM_* scalars likewise. Per capture, every MITgcm field
agrees with the previous 16-digit file to <= ~5.9e-16 relative (print
quantization only; `vermix`, `isomip`, `global_ocean.90x40x15`,
`global_ocean.cs32x15` and `1D_ocean_ice_column` all confirmed), so no MITgcm
physics changed. Replaying the same port on the old and new captures: the
`vermix`, `global_ocean.90x40x15` and (historical: pre-1DMIX-073 port behaviour, not reproducible
now) `global_ocean.cs32x15` statistics are
identical at both precisions to the displayed digits (real gaps or clean
agreement; nothing in them was print quantization); the `1D_ocean_ice_column`
and `isomip` rows named above (`visc_az`, `mixing_length`, and the
`1D_ocean_ice_column` `diff_kz`/`tke_after` roundoff rows) were print
quantization and dropped to roundoff; the `isomip` `diff_kz` and `tke_after`
gaps were unchanged by print precision (1DMIX-071 later showed the `diff_kz` gap and 1,811 `tke_after` cells to be
replay-input artifacts, see the `isomip` section). Evidence and per-file provenance:
`devel-loop/loop_state/bob-1DMIX-070-evidence.md`, and
`GGL90_port_validation/CAPTURES.md`. The idealized-scenario
statistics come from
`GGL90_port_validation/reports/ggl90_scenario_standalone_summary.md`,
generated by `compare_scenario_ggl90_standalone.py::compare` against the
standalone-Fortran-driver data under `Vertical_Mixing_Models/output/`. The
GGL90 correspondence statements this document relies on (`coordFac`, the
mixing-length interface-depth convention, the `is_true_surface` boundary
handling) are documented in `docs/model_contract.md`. Regenerate the PDF
reports themselves (which additionally render plots the tables above
summarize numerically) via the commands in this directory's parent
`README.md`.
