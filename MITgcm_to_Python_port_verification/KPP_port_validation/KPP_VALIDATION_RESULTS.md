# KPP validation results: does the Python port reproduce MITgcm?

This document is the deep-dive answer to one half of this project's central
question: **does the Python port of MITgcm's KPP diagnostic boundary-layer
scheme reproduce MITgcm's own Fortran output?** (The sibling GGL90 scheme has
its own document, `GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`.) It
assumes no prior familiarity with this project. For a reader new to the
codebase, it explains, per tested MITgcm capture and per idealized scenario:
what was tested and why, the quantified agreement, and — wherever a real,
non-floating-point-roundoff discrepancy exists — its causal mechanism in
plain terms: what MITgcm's real Fortran does, what this port does
differently (or not at all), and why that difference produces the observed
numbers.

KPP (`Vertical_Mixing_Models/KPP/`) is diagnostic: it carries no prognostic
state and no pickup/restart. Every timestep's mixing coefficients are
recomputed from the instantaneous column state by searching for the depth
`hbl` where a bulk Richardson number crosses a critical threshold
(`Ricr`), then applying a shape function over the resulting boundary layer.
This document's per-capture sections follow the same real MITgcm validation
data as the companion GGL90 document; each report stands on its own and
does not forward-reference the other file's sections — the "Shared
infrastructure" section below states, from KPP's own point of view, the
equation-of-state and grid conventions the two schemes hold in common.

The KPP-specific report source directory (`KPP_port_validation/reports/`)
holds the generated PDF/markdown reports this document's numbers trace to.

## How to read the numbers below

- **Boundary-layer depth (`hbl`, metres)** is reported as an absolute
  difference between the Python port and MITgcm's captured value — this is
  the physically meaningful unit for a depth. Where a source report instead
  states a relative percentage for `hbl` (the two 1D_ocean_ice_column/
  lab_sea captures that predate a later re-measurement round), that
  convention is kept and labeled explicitly rather than silently converted.
- **Mixing coefficients** (`visc_az`, `diff_kz_s`, `diff_kz_t`, `ghat`) are
  reported as **relative** percentage error, restricted to cells where
  MITgcm's own captured value exceeds a small "active mixing" threshold
  (`1e-6 m²/s`) so a background-floor cell is not compared against itself as
  if it carried a meaningful signal. A consequence worth understanding
  before reading any table below: because this is a threshold-gated
  *relative* error, a cell sitting right at the boundary between "MITgcm
  calls this active" and "MITgcm calls this background" can register a
  machine-precision absolute difference as an enormous percentage (MITgcm's
  own denominator there is tiny). This is why several tables below show a
  **median relative error of exactly 0%** alongside a **max relative error
  in the hundreds or thousands of percent**: the median describes the
  overwhelming majority of cells; the max describes a handful of boundary
  cells amplifying noise, not a systematic physics mismatch. The same
  flooring behavior affects `max_rel` for `ghat` in the idealized-scenario
  comparison below (a near-zero Fortran reference value floored at `1e-12`
  can turn a small absolute difference into an enormous reported
  percentage) — wherever that happens, this document reports the absolute
  statistic instead and says so.
- Every statistic excludes non-physical padding below a column's real
  seafloor before it is computed.

## Shared infrastructure (grid, driver, equation of state)

KPP runs on the same single 1-D vertical column representation GGL90 uses,
and both schemes reproduce MITgcm's staggered z-grid index-for-index: cell
centers hold tracers/velocities, and interface array index `k` is the top
face of cell `k` (`k=0` is the ocean surface), with the surface interface
carrying zero diffusive flux (`viscAz[0]=0`). KPP adds one convention beyond
this shared grid: `ghat` (the non-local transport coefficient) is
cell-centered, not interface-located, so it has real, non-zero values at
index 0 — the surface-zero-flux rule that applies to `visc_az`/`diff_kz_s`/
`diff_kz_t` does not apply to it. The shared implicit vertical-diffusion
solver (`main/shared_column_solver.py::solve_diffusion_implicit`) applies
`ghat` to the tracer flux exactly where MITgcm's `kpp_transport_t.F`/
`kpp_transport_s.F` do.

KPP's boundary-layer search and its interior mixing coefficients both depend
on the buoyancy frequency `N²`, which this port computes from potential
density via the full Jackett & McDougall (1995) equation of state
(`main/eos.py::jmd95_eos`). The pressure argument fed to that equation of
state is `_depth_to_eos_pressure(depth, rho_const, gravity) =
rho_const*gravity*1e-4*(-depth)`, matching MITgcm's real
`rho_const*gravity*1e-5` bar-per-metre conversion factor exactly for each
experiment's own configured constants. This factor is close to, but not
identically, `0.1 bar/m` for every capture in this project (0.81%-1.92% off
across the different captures' constants); using the true, experiment-
specific factor rather than a flat `0.1` keeps `N²` accurate to floating-
point roundoff at every level, including levels close to neutral
stratification (`N²≈0`) where a small relative pressure error would
otherwise be amplified — this matters here because KPP's `Ri_iwmix` interior
mixing path uses the gradient Richardson number `N²/S²` directly. Confirmed
on the `1D_ocean_ice_column` capture (a real KPP experiment where this
fix's own before/after effect was directly measured): the corrected
pressure conversion produced a mild, consistent, non-regressing
improvement — `hbl` median absolute difference `1.18e-4 m → 8.65e-5 m`,
`visc_az` median absolute difference `9.46e-6 → 8.36e-6` — with every
field's max absolute difference unchanged to displayed precision, since
this capture's active-mixing cells apparently never sit close enough to
`N²≈0` for a large absolute effect.

No pressure-coordinate (`usingPCoords`) MITgcm configuration is validated
against, and none can meaningfully be: the real MITgcm `pkg/kpp` source has
**zero** `coordFac`/pressure-coordinate handling anywhere in it (confirmed by
direct read of `kpp_calc.F`/`kpp_routines.F`), and `kpp_check.F` contains no
runtime guard that rejects a pressure-coordinate configuration either. A
genuine pressure-coordinate KPP capture would therefore not exercise a real
coordinate-conversion difference between MITgcm and this port at all — both
sides would be equally unaware of the unit mismatch, so a clean-looking
comparison would agree for the wrong reason rather than fail visibly. This
project's own captures and idealized scenarios are all z-coordinate ocean
configurations, which is the only configuration this validation exercise is
designed to say anything meaningful about.

## Two mechanisms that explain most of the tail below

Two causal mechanisms account for the great majority of every non-roundoff
discrepancy in the per-experiment sections that follow. Both are stated once
here rather than re-derived per experiment.

**The Rib/Ricr threshold-crossing sensitivity.** KPP diagnoses `hbl` by
searching down the column for the first level where the bulk Richardson
number `Rib` crosses the fixed critical value `Ricr` (default 0.3) — a hard
threshold. MITgcm's Fortran and this port are independent implementations of
the same physics, each accumulating its own floating-point rounding from a
different order of operations and different equation-of-state call sites.
At the overwhelming majority of levels this is invisible: `Rib` is nowhere
near `Ricr`, so a machine-precision difference changes nothing. But whenever
a real column's `Rib` sits within a fraction of a percent of `Ricr` at some
level, the two implementations can disagree about whether that level is
still inside the boundary layer — once that one bit flips, the search locks
onto a different level, sometimes tens of metres away. This has been
decisively confirmed rather than merely hypothesized: feeding MITgcm's own
captured intermediate values (`shsq`, `dbloc`, `dVsq`, `Ritop`) directly into
the port's own search reproduces MITgcm's `hbl` exactly at every tested level
for the single-column captures below, and for the multi-column `lab_sea`
capture the two independently-computed `Ritop` profiles at the column
originally used to investigate this match to 4 significant figures at every
level — the underlying physics computation is correct; only the hard
threshold near an already-tiny margin amplifies the residual. This is an
inherent property of any finite-precision implementation of a
hard-thresholded diagnostic, not a fixable defect in the search algorithm or
the underlying formulas.

**The `wscale` lookup-table clamp (`keep_mitgcm_bugs`).**
`Vertical_Mixing_Models/KPP/kpp_routines.py::wscale` computes the turbulent
velocity scales `wm`/`ws` by bilinear interpolation into a lookup table
indexed by `zdiff = zehat - zmin` (`zehat = vonk·sigma·hbl·bfsfc`). Real
MITgcm (`pkg/kpp/kpp_routines.F:980`) uses the raw, unclamped `zdiff`
unconditionally; for extremely negative `bfsfc` this linearly extrapolates
below the table's lower edge, a hazard the MITgcm developers documented in
their own source comment but left active in the compiled code (the fix,
clamping `zdiff` to a minimum of 0, is present at line 990 but commented
out). This port's `KPPParameters.keep_mitgcm_bugs` flag controls which
behavior it reproduces: `True` (the default) reproduces MITgcm's real,
unmodified Fortran behavior bit-for-bit, including the hazard; `False`
instead applies the never-activated Fortran fix, trading exact MITgcm
correspondence for protection against the hazard's documented crash risk
under extreme forcing. The default is `True` because this project's own
governing constraint is exact MITgcm correspondence, not production
robustness against a hazard MITgcm's own authors chose to leave active; the
`False` opt-out remains available for callers who need the safety clamp
more than exact correspondence, and is exercised explicitly where noted
below. This is not a theoretical difference: it is the measured, dominant
cause of the largest discrepancy in the idealized-scenario comparison below,
and of a substantial part of the `global_oce_latlon` capture's own tail.

## `1D_ocean_ice_column`, 10 timesteps — the fastest smoke test

A single-column, sea-ice-coupled MITgcm configuration, 23 levels, one
column — the fastest end-to-end regression test for the whole KPP replay
pipeline.

| Field | Median rel. err. | Mean rel. err. | Max rel. err. | P95 rel. err. | N |
|---|---|---|---|---|---|
| `hbl` | — | 0.0123% | max\|diff\|=0.012891 m | — | 10 |
| `visc_az` | 0.000000% | 0.043477% | 1.461992% | 0.208271% | 220 |
| `diff_kz_s` | 0.037038% | 0.245251% | 1.473498% | 0.787811% | 40 |
| `diff_kz_t` | 0.037038% | 0.245251% | 1.473498% | 0.787811% | 40 |
| `ghat` | 0.012150% | 0.020643% | — | — | 28 |

Agreement is excellent throughout: `hbl`'s largest absolute disagreement is
1.3 cm, and `visc_az`'s largest relative disagreement (1.5%) occurs at a
single cell. This capture's own raw surface-flux forcing (`bo`, `bosol`)
matches MITgcm's captured values within 1% at every one of the 10
timesteps; the small remaining differences at the cell level are explained
by ordinary floating-point roundoff propagating through the Richardson-
number search and the equation-of-state pressure conversion described in
"Shared infrastructure" above. A direct instrumented `wscale` check on this
capture shows the clamp-differentiating branch described above is entered
at 1.2%-4.4% of evaluation points, but produces **zero** measurable
difference in any output field regardless of `keep_mitgcm_bugs` — the
affected evaluations are on trial boundary-layer-depth candidates that
never end up selected as the final `hbl`, so the difference never
propagates to the output.

## `1D_ocean_ice_column`, 11,000 timesteps — the longest single-column run

The same sea-ice-coupled configuration extended to 11,000 timesteps — the
longest continuous single-column duration validated anywhere in this
project, a check for whether small per-step disagreements accumulate over a
long integration. Every real wet interior interface level in this capture's
own `visc_az` is confirmed non-zero (MITgcm's `Ri_iwmix` adds a non-zero
background floor unconditionally there), so a per-timestep all-zero-interior
signature would indicate a corrupted capture; measured fresh, 0.0% of the
11,000 timesteps show that signature.

**`hbl`** (absolute difference, `N=11,000`): median `2.85e-5 m`, max
`20.28 m`, with 0.09% of timesteps exceeding a 5 m difference. They do not
accumulate over the run — the median stays five orders of magnitude below
the one genuine outlier. That outlier is the Rib/Ricr threshold-crossing
mechanism above at its most sensitive: a real sharp-thermocline event where
the two implementations' `Rib` values disagree about which side of `Ricr`
they fall on.

**Mixing coefficients** (relative error, active cells only):

| Field | Median abs. diff | Max abs. diff | Fraction >1% rel. err. | N (active) |
|---|---|---|---|---|
| `visc_az` | 0 (exact) | 7.60e-3 | 0.087% | 242,000 |
| `diff_kz_s` | 2.38e-7 | 1.73e-2 | 1.19% | 19,603 |
| `diff_kz_t` | 2.38e-7 | 1.73e-2 | 1.19% | 19,603 |

**`ghat`**: median absolute difference `1.521e-3`, max `1321.7` (`N=13,391`
active cells). This residual is measurably driven by `hbl` disagreement, not
assumed by analogy: over all 13,391 active cells, `|hbl diff|` and
`|ghat diff|` correlate at Pearson `r=0.73` (`r=0.81` excluding 13 outlier
cells). The global worst cell has MITgcm's `hbl=24.574 m` against the
port's `15.024 m`, a 9.55 m disagreement — inside the same Rib/Ricr tail
`hbl` itself shows above. Thirteen cells (0.097% of active cells, 26.2% of
the total absolute-difference sum) show the port's `ghat` at exactly `0.0`
against a large MITgcm value; at the largest of these, `bfsfc` (the surface
buoyancy-forcing sign that governs which physical branch KPP takes) lands on
the identical, unstable branch in both implementations — this is not a
stability-branch disagreement, it is simply the most extreme member of the
same `hbl`-disagreement tail, and these 13 cells' own `hbl` disagreement
(median 10.75 m, max 20.28 m) is itself large. Bulk/typical cells show `hbl`
agreeing to within about 6e-5 m and a correspondingly tiny `ghat` difference
(about 1.5e-3), consistent with the same continuous relationship holding at
small scale too.

## `lab_sea`, 999 timesteps (41 days) — the first multi-column real-ocean grid

MITgcm's real Lab Sea configuration: a 20×16 spherical grid with real
bathymetry and sea ice — the first capture in this project with more than
one water column, and the first requiring correct land/seafloor masking.

| Field | Median rel. err. | Mean rel. err. | Max rel. err. | P95 rel. err. | N |
|---|---|---|---|---|---|
| `hbl` | 0.0083% | 0.2838% | max\|diff\|=53.908 m | — | 149,850 |
| `visc_az` | 0.000000% | 33.14% | 173,184.7% | 22.93% | 1,637,981 |
| `diff_kz_s` | 0.000000% | 45.23% | 491,254.1% | 15.01% | 1,637,981 |
| `diff_kz_t` | 0.000000% | 45.23% | 491,254.1% | 15.01% | 1,637,981 |
| `ghat` | 0.132176% | 0.734684% | — | — | 391,574 |

`hbl`'s median difference over 149,850 real ocean column-timesteps is a
fraction of a centimetre; the mean absolute difference is 8 cm. The large
mean/max relative-error percentages for `visc_az`/`diff_kz` are the same
active-mixing-threshold boundary artifact described under "How to read the
numbers below" (the median stays exactly 0%); this project's own convention
for characterizing the real, bounded tail on this experiment uses absolute
`hbl` statistics instead, which is why the tail below is phrased in metres,
not percent. A direct instrumented `wscale` check on a 20-timestep subsample
of this capture finds a real but small effect from the `keep_mitgcm_bugs`
clamp choice (`hbl` differing by up to 3.9e-3 m, mixing coefficients by
1e-3–7.6e-2 m²/s between the two settings) — dwarfed by, and unrelated to,
the much larger Rib/Ricr tail described next.

## `lab_sea`, 6-month run (4368 timesteps, first 100 subsampled) — the longest temporal duration

The same Lab Sea grid run for a full 6 months instead of 41 days — this
project's longest real-multi-column temporal duration, testing whether the
Rib/Ricr sensitivity above changes character over a much longer,
climatologically representative run. The full 4368-timestep/655,200-wet-
column-timestep capture is impractical to fully replay on every report
refresh, so the results below use the leading 100-of-4368 timesteps
(15,000 wet column-timesteps); the capture itself is confirmed clean
(0.0% truncated) over both this subsample and the full run, checked
directly against MITgcm's own captured `visc_az` for the latter.

**`hbl`** (absolute difference, `N=15,000`): median `2.89e-3 m`, max
`40.72 m`, with 0.68%/0.47% of column-timesteps exceeding a 1 m/5 m
difference — the same Rib/Ricr threshold-sensitivity tail as the shorter
41-day capture above. A separate, larger characterization was previously
reported at the full 655,200-wet-column-timestep scale (not this
100-timestep subsample): `hbl` median difference `0.0011 m`, with a wider
tail — 3.6%/1.5%/0.31% of column-timesteps exceeding 1 m/5 m/20 m, and one
extreme outlier of 112.5 m at a near-degenerate, weakly-stratified polar
column where MITgcm reports full-column convection and the port a shallow
5 m layer. **These are historical figures from an earlier build of this
capture's own instrumentation, predating this experiment's later
tau-averaging and truncation-instrumentation fixes** — they do not
describe the capture currently on disk and have not been re-verified
against it; they are retained here only as a historical record, not as a
current measurement. The 100-timestep subsample above, drawn from the
current, confirmed-clean capture, remains this section's own current `hbl`
evidence; a full 4368-timestep recomputation against the corrected capture
is not reported here.

**Mixing coefficients** (relative error, active cells only):

| Field | Median abs. diff | Max abs. diff | Fraction >1% rel. err. | N (active) |
|---|---|---|---|---|
| `visc_az` | 0 (exact) | 3.49e-2 | 13.35% | 171,000 |
| `diff_kz_s` | 0 (exact) | 7.60e-2 | 12.27% | 171,000 |
| `diff_kz_t` | 0 (exact) | 7.60e-2 | 12.27% | 171,000 |

The fraction exceeding 1% relative error is much larger than the
single-column `1D_ocean_ice_column` capture's own fraction — expected for
this multi-column, variable-bathymetry, real-land experiment, where the same
Rib/Ricr threshold sensitivity flips many more individual columns' boundary-
layer diagnosis than the single-column case does. The absolute-error bounds,
which are what matters physically, stay small and comparable to the
single-column result.

**`ghat`**: median absolute difference `2.404e-2`, max `362.4`
(`N=34,540` active cells). Measured directly rather than inherited by
analogy: the global worst cell (MITgcm `hbl=10.491 m` vs. the port's
`9.965 m`, only a 5% disagreement) straddles this capture's 10 m grid-cell
boundary — MITgcm places all of the surface cell inside the boundary layer
while the port places it just outside, flipping `ghat` from 362.4 to
exactly `0.0`; `bfsfc` lands on the identical unstable branch in both
implementations, ruling out a stability-branch disagreement at this cell.
Fifty-four cells (0.156% of active cells, 52.6% of the total absolute-
difference sum) show this same exact-zero signature. Of those, 42 cluster
at a persistent, small (0.24–0.25 m) `hbl` offset at a single column,
confined to the last several timesteps of this subsample (so this cluster's
extent beyond the subsample's own last timestep is not established here);
6 more show genuinely large `hbl` disagreement (17.4–22.1 m, matching the
Rib/Ricr tail directly); a remaining 6 fit neither pattern cleanly and are
left uncharacterized rather than force-fit into either route. Over all
active cells, `|hbl diff|` and `|ghat diff|` correlate at `r=0.22`
(`r=0.48` excluding the 54 zero-signature cells) — weaker than the
single-column capture's correlation, because most of this capture's
zero-signature cells come from a small edge-of-boundary-layer offset rather
than a large misdiagnosis. `hbl` disagreement is the measured driver of
this residual's largest cells via at least two distinct routes — a handful
of genuine large `hbl` misses, and a larger cluster of small offsets that
happen to straddle a grid-cell edge — with a small remainder not
characterized further.

## `seaice_obcs` — the only salt-plume capture

Sea ice, open boundary conditions, and — uniquely among every KPP
experiment tested here — `useSALT_PLUME=.TRUE.`, MITgcm's haline-convection
parameterization under sea ice: brine rejected during ice formation sinks
as a plume and contributes its own buoyancy forcing to the boundary-layer
search, distinct from the ordinary surface heat/freshwater flux. This port
implements that contribution: `bfsfc` (the surface buoyancy forcing term
`diagnose_bl_depth` evaluates at 3 points down the column) gains an added
term `boplume(1)*plume_frac(z, fact, SPDepth)`
(`Vertical_Mixing_Models/KPP/kpp_salt_plume.py`), matching the real
`salt_plume_frac.F` formula for MITgcm's default `PlumeMethod=1`/
`Npower=0` configuration with `SALT_PLUME_VOLUME` unset — the only variant
any tested salt-plume capture uses. A configuration using a different
`PlumeMethod`/`Npower`/`SALT_PLUME_VOLUME` combination is not supported:
`KPPParameters.__post_init__` raises `NotImplementedError` rather than
silently applying the wrong plume formula.

**`hbl`** (absolute difference, `N=295` real ocean columns): median
`3.46e-2 m`, p99 `19.15 m`, max `20.43 m`, with 9.15%/2.71% of columns
exceeding a 1 m/5 m difference. The wide tail is the Rib/Ricr threshold-
sensitivity mechanism above, not a separate defect — this experiment's own
haline forcing term shifts `bfsfc` at every affected column, but both
implementations compute that shift the same way; what differs downstream is
the same hard-threshold search behavior already characterized.

A second, narrower, genuinely open scientific question remains for a
handful of this capture's columns: at extremely weak wind forcing, `hbl`
disagrees even where the salt-plume contribution is too small to flip
`bfsfc`'s sign. Tracing one such column by hand shows the boundary-layer
search hits a stability-limiting clamp (`hlimit = min(hekman, hmonob)`)
whose `hmonob` term divides by the surface buoyancy forcing — a ratio
MITgcm's own Fortran source comments flag as numerically delicate when that
denominator is near zero. Whether MITgcm's own real internal values are
equally fragile there (in which case this is inert, the same category as
the Rib/Ricr mechanism) or a genuine, separate port defect exists for
extremely-weak-shear columns specifically has not been distinguished; doing
so needs new Fortran instrumentation dumping `bldepth`'s internal `Rib`/
`bfsfc` values directly, which does not currently exist. This is reported
as unresolved physics, not as a claim of correctness.

**Mixing coefficients** (relative error, active cells only):

| Field | Median abs. diff | P99 abs. diff | Max abs. diff | Fraction >1% rel. err. | N (active) |
|---|---|---|---|---|---|
| `visc_az` | 0 (exact) | 4.79e-3 | 1.84e-2 | 13.9% | — |
| `diff_kz_s` | — | 4.87e-3 | 3.41e-2 | 13.9% | — |
| `diff_kz_t` | — | 4.87e-3 | 3.41e-2 | 13.9% | — |

**`ghat`**: median absolute difference `0.386`, p99 `124.4`, max `572.4`
(`N=209` active cells). Measured directly rather than assumed to match the
other captures' mechanisms, and this capture's residual is genuinely
different from theirs: 12 of the 209 active cells (5.7%) show the port's
`ghat` at exactly `0.0` against a large MITgcm value, and those 12 cells
carry 75.8% of the total absolute-difference sum, including the entire
maximum. At the single worst of the 12 (`hbl` differing by only 0.12 m,
1.2% of a 10.07 m boundary layer — not a large misdiagnosis), `bfsfc` sits
on the identical unstable branch in both implementations, both regularized
to exactly the same numerical floor — ruling out both a stability-branch
flip and a large `hbl` disagreement as the driver at that specific cell.
The port's own diagnosed boundary-layer index places this cell inside the
boundary layer (the ordinary in-layer evaluation path, not the separate
outside-layer zeroing that applies below the boundary layer), yet the
shape-function evaluation there still returns exactly `0.0`; the deeper
numerical trigger inside that evaluation is not established by this
measurement, and is flagged as a candidate for future investigation rather
than asserted. This exact-zero group is not uniform: one other member
(`mit_hbl=28.035 m` vs. the port's `14.891 m`, a 13.14 m disagreement) *is*
driven by the ordinary Rib/Ricr `hbl` mismatch, on the same branch in both
models. The remaining 197 active cells (median `0.386`) correlate only
moderately with `hbl` disagreement (`r=0.71`) while `hbl` itself matches
closely there too (median `0.009 m`) — so `hbl` mismatch is at most a
partial contributor to the ordinary residual, not an established dominant
cause.

## `global_oce_latlon` — a real global, multi-tile, seasonally-complete capture

A real global-bathymetry, spherical-polar, 4-tile (2×2, 90×40×15) KPP
configuration run for a full 360-day periodic-forcing cycle (720
timesteps) — this project's only genuinely multi-tile, seasonally-complete
capture, and the only one exercising `useCDscheme`, `useGMRedi`, and
climatological surface restoring. This capture has 2,315 wet columns at
every one of its 720 timesteps (bathymetry is time-invariant, confirmed by
direct inspection), giving 1,666,800 total wet column-timesteps for `hbl`.
A full 720-timestep×2,315-column Python-port replay is estimated at roughly
1.5 hours serially (measured directly on this capture at ~2.2 ms per
column-timestep); the results below instead use the first 5 of 720
timesteps at full spatial resolution — all 2,315 wet columns per timestep —
giving 11,575 ocean column-timesteps. The capture is confirmed clean (0.0%
truncated).

The numbers below use this port's actual default, `keep_mitgcm_bugs=True`
(see "Two mechanisms" above), which measurably improves correspondence with
real MITgcm on this specific capture: flipping the flag alone — no other
change — cuts `hbl`'s own worst-case disagreement from 33.9 m to 3.09 m
(11×), `visc_az`'s max absolute difference from 0.332 to 0.096 m²/s (3.5×),
and `diff_kz_s`/`diff_kz_t`'s max absolute difference from 0.959 to
0.110 m²/s (8.7×); the count of `hbl` cells disagreeing by more than 1%
drops from 146 to 10 of 11,575. Most of this capture's own worst-case tail
is therefore the `wscale` clamp difference, not an independent Rib/Ricr
effect, even though the Rib/Ricr mechanism is still present and responsible
for the smaller remaining tail.

**`hbl`** (absolute difference, `N=11,575`): median `1.35e-3 m`, p95
`0.0187 m`, p99 `0.0563 m`, max `3.09 m`, with 0.035%/0% of column-timesteps
exceeding a 1 m/5 m difference.

**Mixing coefficients** (relative error, active cells only, `N=134,970`):

| Field | Median abs. diff | Max abs. diff | Fraction >1% rel. err. |
|---|---|---|---|
| `visc_az` | 0 (exact) | 0.096 | 0.23% |
| `diff_kz_s` | 0 (exact) | 0.110 | 1.11% |
| `diff_kz_t` | 0 (exact) | 0.110 | 1.11% |

This experiment's own forcing-validation gate falls back to MITgcm's own
captured `ustar`/`bo`/`bosol` for the actual mixing computation, so the
diagnostic-only mismatch between this port's raw-flux reconstruction and
MITgcm's climatologically-restored flux (a known, purely diagnostic gap —
the climate-restoring contribution is not replicated in the raw-flux
reconstruction pipeline) does not propagate into any of the numbers above.

**`ghat`**: median absolute difference `1.4999e-3`, max `115.97`
(`N=394` active cells, of which 2.54% now exceed 1% relative error). This
experiment is this project's only registered capture with `KPP_GHAT`
`#undef`'d in MITgcm's own compile-time options (`use_ghat=0`). MITgcm's
real `blmix` (`kpp_routines.F`) computes `ghat` unconditionally regardless
of `KPP_GHAT` — that macro only gates whether the computed coefficient is
later *applied* to the tracer diffusive flux, not whether it is computed at
all. This port's `compute_bl_mixing` reproduces exactly that: it always
computes `ghat`, and `KPPParameters.use_ghat` gates only its later
application via `MixingOutput.apply_ghat`, consumed by the shared implicit
diffusion solver — matching `kpp_transport_t.F`/`kpp_transport_s.F`, the
only place real MITgcm's `KPP_GHAT` actually has any effect. The 394 active
cells split into two groups: 391 with a small genuine residual (median
`1.48e-3`), and 3 where the port's `ghat` is exactly `0.0` — those 3 alone
carry the entire 58–116 magnitude range and the full maximum. At the worst
of the 3, the two implementations land on opposite sides of the
stability-branch sign test (`bfsfc`'s sign, which selects the stable or
unstable shape function) at `bfsfc = +4.42e-9` — a value effectively
indistinguishable from zero in either implementation. This is reported as
the measured driver at that cell; the deeper reason the two implementations'
tiny, near-zero `bfsfc` values land on opposite sides of zero is not
root-caused further here.

## The 6 idealized scenarios, standalone Fortran driver — isolating the physics from any capture noise

This project's own 6 idealized forcing scenarios (calm baseline, arctic
convection, hurricane wind, tropical heating, heavy rain freshening,
combined storm) have no MITgcm "ground truth" NetCDF — they were never run
through a full MITgcm model. Instead, this port's own computed column state
and forcing at every timestep is fed directly into the real, unmodified
Fortran `KPPMIX` subroutine via a standalone driver
(`mitgcm_verification_mods/kpp_standalone_driver/`), isolating agreement on
the physics formulas themselves from any capture/harness noise. The
comparison statistics are `compare_scenario_standalone.py::compare`'s own
output, reproduced from the on-disk scenario data in
`KPP_port_validation/outputs_from_python_standalone/`.

**Five of the six scenarios** (`calm_baseline`, `arctic_convection`,
`hurricane_wind`, `tropical_heating_diurnal`, `heavy_rain_freshening`) match
the real Fortran `KPPMIX` to floating-point roundoff: worst `max_rel` across
all five scenarios and all fields is about `2.3e-15`, and zero cells (of
24–2,400 per scenario per field) exceed 1% relative error anywhere.

**`combined_storm`** (the most extreme scenario: boundary-layer depth
deepens from 70 m to 387 m over the run) is the only one where a real,
physically explained difference from the Fortran driver persists beyond
roundoff, and it depends entirely on the `keep_mitgcm_bugs` choice described
in "Two mechanisms" above. Under this port's actual default
(`keep_mitgcm_bugs=True`), `hbl` collapses to floating-point roundoff
(max absolute difference `2.8e-14 m`, the same order as the other five
scenarios), and the fraction of mixing-coefficient cells exceeding 1%
relative error drops to 2–4 of 600 per field — confined to the two deepest
grid cells (of 50) at the two timesteps where the boundary layer has
deepened to the full column depth. That small residual is not further
characterized here. If `keep_mitgcm_bugs` is instead set to its non-default
`False` (available as an explicit opt-out, trading exact correspondence for
protection against the documented extrapolation hazard), the same scenario
shows a real, much larger disagreement: 45–51% of cells exceed 1% relative
error in `visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat`, with absolute differences
up to `6.1e-2 m²/s`. This was measured directly, not inferred: substituting
the real Fortran `KPPMIX`'s own `hbl` at each timestep into the port (a
targeted experiment testing the alternative hypothesis that `hbl`'s own
small difference alone explains the disagreement) leaves the mismatch
almost completely intact — `visc_az`'s cell count exceeding 1% moves only
from 270 to 261 of 600, and the maximum absolute difference is unchanged —
so `hbl` is not the dominant mechanism; the surviving residual concentrates
where `sigma*hbl*bfsfc` is most negative, growing smoothly with depth and
time rather than clustering at `hbl`, matching the `wscale` extrapolation
mechanism directly. `arctic_convection` and `hurricane_wind` technically
enter the same clamp-differentiating branch too (at a much lower rate), but
produce no measurable difference in either setting — `combined_storm`'s
forcing is, among these six scenarios, the only one extreme enough for the
clamp choice to change the result. `ghat`'s own reported `max_rel` for
`combined_storm` (`9.05e+11`) is the near-zero-reference flooring artifact
described under "How to read the numbers below", not a near-total mismatch
in absolute terms — its `max_abs` there is `0.905`, the same order of
magnitude as the field's own active-mixing range.

## Limitations

These are physical and methodological properties of this validation
exercise and this port, not open action items:

- **No pressure-coordinate awareness at all.** As described under "Shared
  infrastructure" above, real MITgcm's own `pkg/kpp` has zero
  `coordFac`/pressure-coordinate handling, and this port has none either. A
  pressure-coordinate KPP configuration is out of scope for this project
  entirely — not merely untested — because a comparison run under one would
  not exercise any real coordinate-conversion difference between the two
  sides; it would agree for the wrong reason rather than fail visibly. Every
  capture and idealized scenario validated here is a z-coordinate ocean
  configuration.
- **Double-diffusion (`KPP_DOUBLEDIFF`) is not implemented.** Real MITgcm
  optionally adds a double-diffusive contribution to the interior salt and
  temperature diffusivities — salt fingering in salt-stratified,
  heat-unstable water, diffusive convection in the opposite regime — gated
  by the runtime flag `KPPuseDoubleDiff` (off by default in stock MITgcm).
  This port's interior-mixing path (`kpp_routines.py::ri_iwmix`) has no code
  for either branch. `KPPParameters` raises `NotImplementedError` if a
  capture's `KPPuseDoubleDiff` flag is `True`, rather than silently running
  incomplete physics; every capture this project currently validates
  against carries `KPPuseDoubleDiff=0`, so this gap has not been exercised
  by any of the results above, but a future capture that enables it would
  need real development before it could be replayed at all.
- **Salt-plume support covers exactly one MITgcm configuration variant.**
  This port's `plume_frac` implements MITgcm's default
  `PlumeMethod=1`/`Npower=0` formula with `SALT_PLUME_VOLUME` unset — the
  only variant `seaice_obcs` (this project's one salt-plume capture) uses.
  Any other `PlumeMethod`/`Npower`/`SALT_PLUME_VOLUME` combination raises
  `NotImplementedError` rather than being silently mishandled.
- **The `wscale` lookup-table hazard is reproduced, not fixed.** This port's
  default (`keep_mitgcm_bugs=True`) deliberately reproduces a documented
  MITgcm extrapolation hazard under extremely negative surface buoyancy
  forcing, rather than protecting against it, because this project's
  governing goal is exact MITgcm correspondence. A caller that needs
  protection against that hazard more than exact correspondence must set
  `keep_mitgcm_bugs=False` explicitly and accept the resulting, measured
  divergence from MITgcm's real output under extreme forcing.
- **The Rib/Ricr hard threshold means no `hbl` agreement bound can be made
  arbitrarily tight.** Because `hbl` is defined by a threshold crossing, any
  two independent floating-point implementations of the same physics will
  occasionally disagree about which side of the threshold a marginal level
  falls on, producing an occasional large `hbl` disagreement even when the
  underlying physics computation is correct at every level. This is a
  property of the diagnostic itself, not a bound this port could tighten by
  further debugging.
- **The largest, multi-tile, seasonally-complete capture is validated on a
  timestep subsample, not the full run.** `global_oce_latlon`'s full
  720-timestep×2,315-column Python-port replay is estimated at roughly 1.5
  hours serially; the results above use the first 5 of 720 timesteps at
  full spatial resolution instead. A full-run replay remains a real,
  not-yet-scoped follow-up rather than something the numbers above should
  be read as already covering.

## Reproducibility

The `1D_ocean_ice_column` (10-step), `lab_sea` (999-step) statistics above
come from the PDF validation reports generated by
`scripts/generate_kpp_validation_report.py::compute_hbl_statistics`/
`compute_mixing_statistics`, run against the paired NetCDF captures under
`KPP_port_validation/{inputs,outputs}_from_mitgcm/`. The `1D_ocean_ice_column`
(11,000-step), `lab_sea` (6-month), `seaice_obcs`, and `global_oce_latlon`
statistics come from the regression assertions and docstrings in
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`,
which drive the same replay entry point
(`scripts/run_kpp_from_netcdf_input.py::run_python_kpp_on_dataset`) against
the same paired captures. The idealized-scenario statistics come from
`KPP_port_validation/reports/kpp_scenario_standalone_summary.md`, generated
by `compare_scenario_standalone.py::compare` against the standalone-Fortran-
driver data under `KPP_port_validation/outputs_from_python_standalone/`. The
`keep_mitgcm_bugs`/`wscale` correspondence and the `KPP_GHAT`
compute-versus-apply correspondence are documented in `docs/model_contract.md`.
Regenerate the PDF reports themselves (which additionally render plots the
tables above summarize numerically) via the commands in this directory's
parent `README.md`.
