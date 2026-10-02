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
(which is then in pascals, not metres) produces a real, large, and fully
explained disagreement rather than a silent one — see `global_ocean.cs32x15`
below for the measured size of this effect. This is a different situation
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
| `diff_kz` | 0 | 2.9e-03 | 300.0% | 0.075% | 1,437,204 |
| `mixing_length` | 4.6e-18 | 1.1e-13 | 3.8e-13% | 0% | 1,437,204 |
| `tke_after` | 0 | 9.1e-06 | 232.7% | 1.25% | 1,437,204 |

(17-digit capture, 1DMIX-070. `visc_az` and `mixing_length` were previously
tabulated at 2.4e-10 and 4.3e-3 maximum absolute difference; the same port
on the earlier 16-digit capture gives 1.1e-10 and 3.25e-4 — 4.3e-3 predates
the 1DMIX-068 `N²` fix — and those two residuals were print quantization of
the captured inputs, see below. The `diff_kz` and `tke_after` rows are real
and did not change: 1102 -> 1075 `diff_kz` cells above 1%, `tke_after`
17,934 cells and 9.081e-6 identical at both precisions.)

**`diff_kz`'s `kSrf` residual (0.075% of cells, max_abs 2.9e-3).** This
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

**`tke_after`'s residual (1.25% of cells, max_abs 9.1e-6) is real and is
identical at 16 and 17 digits.** It carries the `kSrf` background-floor
effect on the coupled TKE solve and the related first-wet `+1`/`+2` levels
and one specific latitude row: at 17 digits its 17,934 cells above 1% sit
at first-wet level `+1` (9,542 cells, max_abs 9.1e-6), `+2` (6,581 cells,
max_abs 2.6e-8) and deeper (1,811 cells, 9.3e-9), while `mixing_length`
agrees to 1e-13 at every one of those levels. That rules `mixing_length`
(and hence the near-neutral `N²` amplification the earlier text invoked for
the `+1`/`+2`/row-50 part) out as their cause; a per-cell probe from
1DMIX-048 (`kappa_m`, mixing length, Prandtl number and `N²` all match
MITgcm at the affected locations) is consistent with that, and the
implicit TKE solve redistributing the `kSrf`-boundary effect is the
explanation this document carried before. The residual mechanism at the
`+2` and row-50 cells was not re-traced by 1DMIX-070; it stays a documented
known gap under 1DMIX-038/048, not a print artifact.

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

## `global_ocean.cs32x15` — the only pressure-coordinate capture

A 12-tile cubed-sphere (384×16×15) configuration, also `useIDEMIX=.TRUE.` —
surveyed as this project's other candidate IDEMIX capture, but this
configuration sets `buoyancyRelation='OCEANICP'`, which MITgcm maps directly
to `usingPCoords=.TRUE.`: its vertical grid spacing (`delR`) is genuinely
expressed in pascals, not metres.

| Field | Fraction >1% rel | Max abs. diff | N |
|---|---|---|---|
| `visc_az` | 62.5% | 100 (at this port's `GGL90viscMax` cap) | 813,820 |
| `diff_kz` | 62.7% | ~2.0e9 | 813,820 |
| `mixing_length` | 62.7% | ~1.4e7 | 813,820 |
| `tke_after` | 64.8% | ~4.2e5 | 813,820 |

**Root cause.** As described under "Shared infrastructure" above, this
port has no `coordFac`-equivalent unit conversion anywhere in its
depth/thickness handling, while real MITgcm's own GGL90 Fortran does. Every
length-based formula this port evaluates — mixing-length ceilings, the TKE
boundary condition, and so on — receives this capture's raw pressure values
and treats them as if they were depths. Point-verified at one cell: real
MITgcm computes `mixing_length = 1277 m` there; this port computes
`14,493,349 m` (14,493 km — larger than Earth's radius) — a roughly
10,000× error, which is why more than 62% of every field's cells exceed the
1% relative-error threshold. This is *not* primarily an IDEMIX signal: the
coordinate confound is roughly an order of magnitude larger than IDEMIX's
own contribution, which is why `global_ocean.90x40x15` above, not this
capture, is this project's clean IDEMIX-gap measurement. This capture's
disagreement is not a candidate for a future fix: pressure-coordinate
support is a permanent, deliberate scope boundary for this project (see
"Limitations" below), so this gap is expected to persist unless that scope
decision itself is revisited.

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
| `diff_kz` | 0 / 2.15 | 1,800 (0.031%) | 1.56 | 1,430 (0.248%) |
| `tke_after` | 0 / 1.07e-3 | 32,862 (0.570%) | 3.6e-5 | 6,497 (1.126%) |

`visc_az` and `mixing_length` are clean to roundoff on a multi-column, sea-ice-covered grid (same
bounds as the `1D_ocean_ice_column` clean captures). `diff_kz` and `tke_after` are **not clean and
exceed the clean-capture bounds of the test module, which are not widened**; they are asserted as labelled
known gaps (replay-input mechanism, 1DMIX-071) with upper guards only (the mismatch fraction is season dependent). Four 100-step windows of the 6-month run gave `diff_kz` /
`tke_after` fractions of 0.131% / 0.97% (steps 1500-1599), 0.248% / 1.13% (2000-2099), 0.057% / 0.90%
(3000-3099) and 0.0175% / 0.36% (4268-4367): the mismatch fraction follows the season.

**Measured mechanism (the replay feeds the port column-local velocities).** MITgcm's `verticalShear`
at tracer point (i,j), level k is `((ubar(k-1)-ubar(k))^2 + (vbar(k-1)-vbar(k))^2)/drC^2` with
`ubar=(uVel(i)+uVel(i+1))/2`, `vbar=(vVel(j)+vVel(j+1))/2` (`ggl90_calc.F`, the default
`calcMeanVertShear=.FALSE.` branch), while the replay hands the port `uVel(i,j)`, `vVel(i,j)` only.
Because the capture holds every column's velocities, `ubar`/`vbar` can be rebuilt from the neighbouring
columns of the same capture: over the first 300 timesteps (458,013 cells, interior i<19, j<15) the rebuilt
shear matches MITgcm's captured `vertical_shear` to a median relative error of 1.25e-16 (max 6.6e-16),
while the column-local shear the replay effectively uses is off by a median 64% (99% of cells differ by
more than 1%) -- asserted by `test_lab_sea_999_shear_is_four_point_average`. This fits the pattern of
the two gaps: `tke_after` mismatches are 96.9% in levels 1-4 (centres 15-65 m), evenly spread over the
run, and 91.9% in cells with `tke_before >= 1e-8` where shear production matters; `diff_kz` mismatches
(through `Pr = f(Ri)`, `Ri = N^2/(shear^2 + GGL90eps)`) are 95.4% near-neutral cells with shear below 1e-6
(where a tiny `N^2` amplifies any shear difference); with neighbour-averaged velocities the `diff_kz` mismatch
goes to zero, i.e. it is entirely the shear, not an EOS effect (review measurement, steps 500-509: `diff_kz` and
`tke_after` mismatches above 1% go to 0, max_abs to 3.4e-15 / 3.0e-19). `visc_az` and `mixing_length` do not
depend on the shear and are exact. This is the replay-input effect **1DMIX-071**, not a port gap and not a defect in `GGL90Driver`; no port source or
replay semantic was changed (the replay script gained optional `first_timestep`/`last_timestep` and loads the
selected inputs once, numerically identical).

**Consequence for the other multi-column GGL90 captures (1DMIX-071).** `isomip`, `global_ocean.90x40x15` and
`global_ocean.cs32x15` are also replayed with column-local velocities; their `tke_after`/`diff_kz` residuals
(attributed above to the kSrf floor, missing IDEMIX physics and pressure coordinates) may include
this effect. It has not been separated there; a follow-up that rebuilds tracer-point velocities from the
neighbouring columns for all multi-column replays would do so.

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
  say anything meaningful about. The equivalent KPP limitation was expected
  to produce a misleading close agreement; measured under 1DMIX-054 it does not (MITgcm's own KPP
  aborts at iteration 1 and the port returned NaN in most interior cells before 1DMIX-072, which
  now makes `KPPDriver` raise `ValueError` on such geometry instead; see
  `KPP_VALIDATION_RESULTS.md`), so for both schemes a pressure-coordinate capture gives a large,
  visible disagreement -- see `global_ocean.cs32x15` above for the measured size for GGL90.
- **`calc_mean_vert_shear` is declared but not implemented.** This
  configuration flag (a real, alternate vertical-shear formula) has no
  consumer anywhere in the port, the same declared-but-dead pattern as
  `use_idemix`. Its only observed instance in this project's own captures
  is the now-permanently-out-of-scope pressure-coordinate capture, so it
  remains deferred rather than implemented speculatively for a
  configuration this project does not otherwise validate against.
- **The `ALLOW_SHELFICE` `is_true_surface` handling is exercised only by
  the MITgcm-comparison verification harness, not by this project's own
  scenario-driving code path.** `main/mixing_adapter.py` (the entry point
  this project's own idealized scenarios use) has no `ALLOW_SHELFICE`
  support and always uses the ordinary array-index-0 surface convention;
  the explicit `is_true_surface` flag described under `isomip` above is set
  by the MITgcm-replay harness only, for columns it knows are sliced from a
  real floating-ice-shelf capture.
- **The Rib/Ricr-style threshold sensitivity that dominates several KPP
  discrepancies has no direct GGL90 analogue.** GGL90 has no hard
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
`global_ocean.90x40x15`, `global_ocean.cs32x15` and (1DMIX-054) `lab_sea` statistics come from
that same test module's own fresh measurements.

**Print precision (1DMIX-070).** All five captures above were recaptured on
2026-09-30 with the instrumented Fortran printing 17 significant digits
(`ES25.16`, exact for a double; the earlier captures used `E25.16`, 16
digits), and the PARAM_* scalars likewise. Per capture, every MITgcm field
agrees with the previous 16-digit file to <= ~5.9e-16 relative (print
quantization only; `vermix`, `isomip`, `global_ocean.90x40x15`,
`global_ocean.cs32x15` and `1D_ocean_ice_column` all confirmed), so no MITgcm
physics changed. Replaying the same port on the old and new captures: the
`vermix`, `global_ocean.90x40x15` and `global_ocean.cs32x15` statistics are
identical at both precisions to the displayed digits (real gaps or clean
agreement; nothing in them was print quantization); the `1D_ocean_ice_column`
and `isomip` rows named above (`visc_az`, `mixing_length`, and the
`1D_ocean_ice_column` `diff_kz`/`tke_after` roundoff rows) were print
quantization and dropped to roundoff; the `isomip` `diff_kz` and `tke_after`
gaps are real and unchanged. Evidence and per-file provenance:
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
