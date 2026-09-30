# Scientific model or analysis contract

This project ports two MITgcm vertical-mixing parameterizations to a 1-D Python
column model. Every non-trivial function must cite the MITgcm source file and
line numbers it corresponds to; any deviation from MITgcm physics must be
explicitly justified in a code comment and, if uncertain, opened as an issue
(see `open_issues.md`/`closed_issues.md` for the current and historical record).

## Coordinate and unit conventions

- `z` positive **up**; `depth` positive **down**; `z = -depth`.
- Pressure is positive and increases with depth. The EOS pressure argument fed to
  `jmd95_eos`'s pressure-dependent bulk-modulus terms is `main/eos.py::
  _depth_to_eos_pressure(depth, rho_const, gravity)` = `rho_const*gravity*1e-4 *
  (-depth)`, matching MITgcm's real `pRef4EOS`/`SItoBar` conversion
  (`rho_const*gravity*1e-5` bar per metre) exactly — **not** a flat "1 dbar ≈ 1 m"
  (fixed 1DMIX-039; that flat form implicitly assumed `rho_const*gravity == 1e4`,
  true for none of this project's captures, and produced a ~1e-5–1e-4 relative,
  depth-growing N²/density error, invisible in aggregate stats but amplified by
  `mixing_length`'s `1/√N²` wherever a real column's N² sits near zero — see
  1DMIX-039 for the derivation and numeric confirmation).
  A prior port bug computed `pressure = -depth / 10.0` (10× too small) — fixed and
  audited, see closed issue 1DMIX-002. Watch for regressions of this exact form.
- Density: `rho_const = 1029.0 kg/m³` (reference); `rho = rho_anom + rho_const`
  where `rho_anom` is the JMD95 equation-of-state anomaly (`Vertical_Mixing_Models/main/eos.py::jmd95_eos`).
- Grid staggering matches MITgcm exactly (index-for-index, no re-indexing/interpolation):
  cell centers hold tracers/velocities; interface-array index `k` is the **top face
  of cell k** (`k=0` = ocean surface); the surface interface carries zero diffusive
  flux (`diffKz[0] = viscAz[0] = 0`). Full array-to-array mapping, including KPP's
  half-level `ghat` offset, is in `Vertical_Mixing_Models/docs/dev_notes/MITGCM_STAGGERING.md`
  and enforced by `Vertical_Mixing_Models/tests/test_staggering.py`.
  **Exception, fixed (1DMIX-038)**: for a GGL90 `ALLOW_SHELFICE` column
  (floating ice shelf; MITgcm's own effective surface level shifts from array
  index 0 to `kSrf=kTopC>0`, the true top wet cell — see `isomip`), MITgcm's
  real captured output applies the zero-flux convention to `viscAz` at `kSrf`
  but **not** to `diffKz` (plain background floor there) or to `GGL90TKE`
  (forced to exactly 0 there, not the ordinary surface-Dirichlet value). The
  Python GGL90 port (`ggl90_mixing_coefficients.py::compute_viscosity_
  diffusivity`, `ggl90_core_driver.py::GGL90Driver.step_tke_forward`) takes an
  explicit `is_true_surface` flag (default `True`, exact behavioral no-op for
  every non-`ALLOW_SHELFICE` experiment) that the MITgcm-comparison harness
  (`run_ggl90_from_netcdf_input.py`) sets `False` whenever it feeds a column
  sliced from a real `kSrf>0`; with the flag set, `diffKz[0]`/`GGL90TKE[0]`
  reproduce MITgcm's real values instead of the zero-flux/Dirichlet-survives
  convention. Confirmed exactly (0 mismatch) against all 28812 real ice-shelf
  column-timesteps in the `isomip` capture. This exception is exercised only
  by the MITgcm-comparison verification harness, not by this project's own
  scenario-driving code path (`main/mixing_adapter.py`), which has no
  `ALLOW_SHELFICE` support and always uses `is_true_surface=True`. See
  1DMIX-038 for full evidence. `GGL90MixingLength.compute()`/`_limit_method_2`
  also take the same `is_true_surface` flag (round 2) for a real but narrow
  fix to their internal `mxl_down[0]` (Fortran `mxLength_Dn(1)`) seed — but
  the `mixing_length[kSrf+1]` mismatch this was investigating turned out NOT
  to be a boundary-condition defect at all: it is a general
  numerical-conditioning effect (`mixing_length`'s `1/√N²` formula amplifying
  a small, apparently pre-existing N² computation discrepancy near `N²≈0`),
  confirmed to occur equally in ordinary fully-wet columns within the same
  capture — see 1DMIX-038's round-2 entry and the newly-filed 1DMIX-039
  (general N²/EOS precision question, not ShelfIce-specific).
- **z-coordinates only — no pressure-coordinate (`usingPCoords`) support, and
  never will be: permanently out of scope (resolved, 1DMIX-040)**: every
  depth/thickness quantity in this port (`column_grid.py`'s grid spec,
  GGL90's mixing-length ceilings, TKE boundary terms) is assumed to already
  be in metres. MITgcm's own real code applies a `coordFac` scaling (`1` in
  z-coordinates, `g·ρ_0` in pressure coordinates, set from
  `buoyancyRelation='OCEANICP'` → `usingPCoords=.TRUE.`,
  `model/src/ini_parms.F:454-455`) throughout
  `ggl90_calc.F`/`ggl90_idemix.F`/`ggl90_mixinglength.F`; this port has no
  equivalent conversion anywhere. Feeding a genuine p-coordinate MITgcm
  capture's grid geometry (`rC`/`rF`/`drF`, which are then in Pa, ~1e7, not
  metres) directly into this port silently produces wildly wrong results
  (confirmed: a real `mixing_length` of `1277m` vs. this port's `14493km` for
  the same cell, `global_ocean.cs32x15/input.in_p`) rather than an error —
  a silent-incorrect-result risk for any future p-coordinate MITgcm
  configuration, not merely a coverage gap. **Resolved (1DMIX-040)**: Arch
  decided pressure-coordinate support is permanently out of scope rather than
  implementing real `coordFac`-equivalent support — this project's own
  Primary Goal and every one of its own captures/scenarios are z-coordinate
  ocean configurations, only 1 of the 6 captures surveyed under 1DMIX-025
  ever used pressure coordinates, and real `coordFac` support would require
  a cross-cutting rewrite of `column_grid.py` and both schemes' core
  mixing-length/TKE-boundary kernels, risking regression of the
  z-coordinate paths this project actually validates for no presently
  demonstrated need. This is a final scope statement, not a pending
  decision; it will not be revisited absent a new demonstrated need. See
  1DMIX-040 (closed) for the full evidence.

## Equation of state

`Vertical_Mixing_Models/main/eos.py::jmd95_eos` — full Jackett & McDougall (1995) nonlinear EOS. Stratification
(N²) **must** use potential density (adjacent levels evaluated at a common reference
pressure), not in-situ density — see `Vertical_Mixing_Models/main/eos.py::compute_ggl90_buoyancy_frequency_squared`
and closed issue 1DMIX-001 (a real historical bug used in-situ density here). The
static-instability sign test (`compute_static_instability_mask`) is the one place
in-situ density is *correct*, verified against MITgcm's
`model/src/convective_adjustment.F` (closed issue 1DMIX-005) — do not "fix" this to
potential density without re-checking that source.

**Resolved (1DMIX-039)**: a small, general, monotonically depth-growing relative
N² discrepancy (~1e-5 near the surface to ~1e-4 near the seafloor, confirmed in
an ordinary fully-wet `isomip` column, not ShelfIce-specific) was root-caused to
the EOS **pressure-conversion factor**, not the EOS polynomial itself. The
opening hypothesis ("real MITgcm runs use `eosType='JMD95Z'`'s level-pre-factored
`eosC(1..9,kRef)` coefficients, not bit-identical to the generic polynomial") was
directly checked against `model/src/ini_eos.F` and found **wrong**: `JMD95Z`'s
coefficient tables and `FIND_RHO_2D`'s term-by-term formula structure are
identical to the generic polynomial this port's `jmd95_eos` already implements
(`eosC(kRef)` is `POLY3`'s own unrelated per-level table). The real mechanism was
`jmd95_eos`'s callers hardcoding a flat `0.1 bar/m` pressure conversion instead of
MITgcm's real `rho_const*gravity*1e-5` bar/m (see the pressure convention note
above and `main/eos.py::_depth_to_eos_pressure`) — confirmed numerically to
reproduce the exact observed relative-error magnitude/depth-growth and to
collapse it to floating-point noise once corrected. Fixed in
`compute_buoyancy_gradients`/`compute_ggl90_buoyancy_frequency_squared`/
`compute_static_instability_mask`.

**Resolved (1DMIX-068) -- bit-level operation order of the GGL90 N²**: the
port already matched MITgcm's *formula* (potential density, k-1 water at level
k's pressure; 1DMIX-001/039), but not its floating-point *association order*,
which moves ρ by ~1 ulp (2.3e-13 kg/m³ near 1027 kg/m³) in about half of all
cells. In a near-neutral cell at the TKE floor N² is itself about one such
quantum, and `Ri = N²/GGL90eps` then crossed the 0.2 Prandtl threshold that
MITgcm's did not (attempt-A capture of 1DMIX-066: bottom-face N² 6.4e-17 vs
MITgcm 3.2e-17, Ri 0.289 vs 0.144). MITgcm's exact chain, reproduced operation
for operation by `main/eos.py::compute_ggl90_buoyancy_frequency_squared` and
`::jmd95_eos`:

```
p(k)      = (top_Pres + rhoConst*(rC(k)-rF(1))*gravity*gravitySign) * SItoBar   set_ref_state.F:96-97, find_rho.F
rho'(k)   = rhoP0/(1 - p/bulkMod) - rhoConst                      find_rho.F  (anomaly, not full rho)
  rhoP0   = rfresh + (s*(..) + s3o2*(..) + c9*s*s)                FIND_RHOP0: salt terms summed FIRST
  bulkMod = bMfresh + bMsalt + bMpres                             FIND_BULKMOD: three group sums added last
sigmaR(k) = recip_drC(k) * rkSign * (rho'(k) - rho'(k-1 @ p(k)))  grad_sigma.F:93-95 (rkSign = -1)
  recip_drC(k) = 1/drC(k),  drC(k) = 0.5*(delR(k-1)+delR(k))      ini_vertical_grid.F:123-127
Nsquare(k)= gravity*gravitySign*recip_rhoConst*sigmaR(k)          ggl90_calc.F:353-354 (gravitySign = -1)
```

Every operation is the same IEEE-754 double operation in the same order
(MITgcm built `-O0`, no FMA, non-factorised EOS). `compute_ggl90_buoyancy_
frequency_squared` therefore takes the layer thicknesses (`cell_thickness=dz`
from `GGL90Driver.compute_mixing`) to form `drC` as MITgcm does (subtracting
adjacent centre depths is only the fallback and differs by ~1 ulp), and calls
`jmd95_eos(..., pressure_bar=...)` with `main/eos.py::_mitgcm_eos_pressure_bar`
so the pressure conversion has MITgcm's rounding too. `jmd95_eos`'s
`rho_surf`/`bulkmod` sums are now associated as `FIND_RHOP0`/`FIND_BULKMOD`
(this also applies to its other callers, e.g. KPP's `compute_buoyancy_gradients`.
There the change moves full ρ by up to 2 ulp -- measured on 3M random samples,
0.07-0.5% exceed 1 ulp -- and KPP cell-level outputs can shift non-monotonically
by up to ~4e-5 through branch flips, while aggregate statistics stay unchanged
or improve (Richard, 1DMIX-068 review: 1D_10, 11k, lab_sea_1000); the KPP tests
pass unchanged. The port's KPP path is not yet fully MITgcm-ordered: its
pressure order and full-ρ handling in `compute_buoyancy_gradients` still differ.)
**Caveat on N² bit-identity**: it assumes `depth` equals MITgcm's `rC`
exactly, which the capture/replay path supplies. `ColumnGrid.from_thickness`
builds centres from face midpoints, which differ from `rC` at ulp level in
about 0.1% of faces (74 of 69,000; up to 3e-11 relative), so scenario-driven
columns match MITgcm's N² to that level rather than bit-for-bit.
Regression coverage: `Vertical_Mixing_Models/tests/test_ggl90_n2_mitgcm_bit_order.py`
(real captured witnesses with exact MITgcm sigma_r/Ri, plus bit-equality against
an independent restatement of `find_rho.F`/`grad_sigma.F` over 66,000 faces).

**Known limit of the capture, not of the port (1DMIX-068)**: the instrumented
`ggl90_calc.F`/`kpp_calc.F` print T, S, sigma_r, Ri and shear with `FORMAT E25.16`,
i.e. 16 significant digits (a double needs 17). The captured T, S are therefore
not bit-exact MITgcm inputs (S≈30 is quantised at 1e-14), so ~1.7% of faces
(4341 of 242,000 in the attempt-A capture) legitimately come out one density
quantum away from MITgcm's own sigma_r; every one of them is reproduced exactly
by some T,S that prints identically to the captured values (a control target 3
quanta away is reproduced by none). Feeding MITgcm's captured sigma_r instead
of recomputed N² makes the whole replay agree with MITgcm to ~1e-15 relative,
so nothing downstream of N² is limited. A bit-for-bit N² check needs the capture
format widened to 17 significant digits and the capture redone.

**Resolved for new captures (1DMIX-069)**: the instrumented files now print `ES25.16`
(17 significant digits). Re-running the same attempt-A configuration (11,000 steps,
253,000 wet cells) with that format and no tolerance widened passes all four
`test_1d_ocean_ice_column_clean` bounds (`mixing_length` max abs 2.2e-13 versus
1.9e-1 at 16 digits; `diff_kz` 0 cells above 1% versus 19), so the residual was
print quantisation. The captures declared in `esx/project.json:external_inputs`
were all produced at 16 digits through 1DMIX-069; **1DMIX-070 recaptured every one of them
at 17 digits** (same recipes, same names) after also widening the PARAM_* scalar prints and the
KPP standalone driver's result formats, so the limit above no longer applies to the declared
captures. Every MITgcm field agrees with its 16-digit predecessor to <= 6e-16 relative
(print quantisation only), the KPP residuals are unchanged (the Rib/Ricr tail is real), and the
GGL90 rows that were print quantisation (`1D_ocean_ice_column` all fields, `isomip` `mixing_length`
and `visc_az`) dropped to roundoff; `isomip` `diff_kz` (kSrf) and `tke_after`, `global_ocean.90x40x15`
and `global_ocean.cs32x15` are unchanged and remain real gaps. Instrumented
Fortran fidelity (only output-only hunks versus stock MITgcm d861cd501, after
fixing the `ggl90_calc.F` SHELFICE `DO i=jMin,jMax` transcription error): see
`MITgcm_to_Python_port_verification/mitgcm_verification_mods/README.md`.

## GGL90 (prognostic TKE closure)

Governing equation (full derivation: `Vertical_Mixing_Models/docs/GGL90/GGL90_package_description.tex`
§"Governing Equations (overview)"):

```
∂TKE/∂t + u·∇TKE = P + B - ε + ∂/∂z(K_e ∂TKE/∂z)
  P = K_m·S²        (shear production)
  B = -K_h·N²       (buoyancy flux)
  ε = c_ε·TKE^1.5/L (dissipation)
  K_m = c_k·L·√TKE,  K_h = K_m/α   (c_k = 0.1; α = Prandtl number, default 1.0, ECCOv4r4 = 30.0)
```

TKE is GGL90's only prognostic variable — implemented in
`Vertical_Mixing_Models/GGL90/ggl90_core_driver.py::GGL90Driver.step_tke_forward` /
`::compute_mixing`. Mixing length `L(z)` follows Gaspar et al. (1990), bounded by
distance to boundaries (von Kármán constant `κ = 0.4`). Surface TKE boundary
condition is forced by friction velocity `u*` (coefficient `B1 ≈ 16.6`); this is a
distinct constant from the mixing-length parameter `GGL90m2 = 3.75` documented
elsewhere in the package description — do not conflate the two (this exact
confusion was a real documentation bug, corrected 2026-08-06 per the archived
`handoff/BUILD-LOG.md`, not tracked as a code-correctness issue here since it
never affected the Python port itself).

Mixing-length depth limiters (`mxl_max_flag` 0/1, `GGL90/ggl90_scheme_specific.py::
GGL90MixingLength._limit_method_0`/`_limit_method_1`) bound the raw Gaspar-formula
length by the INTERFACE-to-interface water column depth
(`Ro_surf-R_low`/`Ro_surf-rF(k)`/`rF(k)-R_low`, `pkg/ggl90/ggl90_mixinglength.F:
163-193`), not the cell-center-to-cell-center span — `GGL90/ggl90_core_driver.py::
GGL90Driver.compute_mixing` builds `depth_to_surface`/`depth_to_bottom` from
interface depths (mirroring `ColumnGrid.interfaces`: `interfaces[0]=0=Ro_surf`,
`interfaces[nz]=-total_depth=R_low`) for exactly this reason (fixed 1DMIX-030,
which found the previous cell-center-based construction short by half the top
cell's thickness plus half the bottom cell's — up to ~1.8 m²/s absolute
`visc_az`/`diff_kz` divergence from real MITgcm in weakly-stratified,
well-mixed conditions; re-verified to floating-point roundoff against the
standalone-`GGL90_CALC`-driver on all 6 idealized scenarios plus a vermix
regression check — see closed_issues.md).

## KPP (diagnostic Richardson-number boundary layer)

No prognostic state, no pickup/restart — every timestep's mixing coefficients are
recomputed from the instantaneous column state. Boundary-layer depth `hbl` is
diagnosed where the bulk Richardson number crosses a critical value:

```
Ri_bulk = (z_ref - z)·Δb / (ΔV² + V_t²)   ≡ Ricr   (defines hbl)
```

Interior mixing uses the gradient Richardson number `Ri = N²/S²`
(`Vertical_Mixing_Models/main/physics_basis.py::compute_richardson_number`) via the `Ri_iwmix`-equivalent
path. Implementation: `Vertical_Mixing_Models/KPP/kpp_core_driver.py::KPPDriver.compute_mixing`,
`::_compute_surface_forcing`, `::_compute_shear`. Full variable-flow table:
`Vertical_Mixing_Models/docs/KPP/KPP_package_description.tex` §"Governing Equations".

The surface-relative shear term `dVsq(k)=(Uref-U(k))²+(Vref-V(k))²` has two
MITgcm formulas selected by the `KPP_ESTIMATE_UREF` compile flag
(`kpp_forcing_surf.F:309-461`): the default (`#undef`, used by every tested
experiment except `vermix`) simply takes `Uref=U(1)` (top-cell velocity);
the `#define` branch instead estimates a resolution-independent `Uref`/`Vref`
at a mixed-layer-depth-dependent reference level `zRef` (log-profile
extrapolation if `zRef<drF(1)`, depth-weighted average otherwise). Both are
ported (`KPPDriver._compute_shear`/`::_estimate_reference_velocity`), gated by
`KPPParameters.estimate_uref` (default `False`, matching MITgcm's own
`#undef`). See issue 1DMIX-032 (`vermix`'s `#define KPP_ESTIMATE_UREF`
was previously unwired, causing ~9 m mean `hbl` error on that experiment
specifically) and `Vertical_Mixing_Models/tests/test_kpp_estimate_uref.py`.
Non-local transport (`ghat`) is active only under unstable surface buoyancy forcing
(`bfsfc < 0`, i.e. net surface cooling/freshening dominates) — see
`Vertical_Mixing_Models/docs/dev_notes/KPP_PHYSICS_EXPLANATION.md` for the worked sign logic.
`KPPParameters.use_ghat` (MITgcm `KPP_GHAT`) gates whether this coefficient is
*applied* to the tracer diffusive flux (`MixingOutput.apply_ghat`, consumed by
`UnifiedColumnDriver._apply_vertical_diffusion`/`main/shared_column_solver.py::
solve_diffusion_implicit`, matching `kpp_transport_t.F`/`kpp_transport_s.F`) —
it does NOT gate whether `ghat` itself is *computed*: MITgcm's `blmix`
(`kpp_routines.F`) computes it unconditionally, with no `KPP_GHAT` reference
anywhere in that routine (confirmed by direct read). Fixed 1DMIX-058: this
port previously zeroed the computed coefficient itself whenever `use_ghat`
was `False`, which is the root cause described just below.

**`ghat` has no momentum analogue (1DMIX-061, invariant confirmed correct,
coverage added).** In real MITgcm, `ghat` appears only in the tracer
transport routines `kpp_transport_t.F`, `kpp_transport_s.F` and
`kpp_transport_ptr.F` — nothing in `pkg/kpp` applies it to the momentum
flux. `UnifiedColumnDriver._apply_vertical_diffusion` mirrors this exactly:
`theta`/`salt` share one `ghat_to_apply` variable passed to
`solve_diffusion_implicit`, while the `u_vel`/`v_vel` calls omit the `ghat=`
keyword entirely (it defaults to `None`). This is a tracer-transport term,
not a general vertical-diffusion feature — do not add a `ghat=` argument to
either momentum call under any future refactor of this function. Guarded by
`Vertical_Mixing_Models/tests/test_kpp_ghat_gate.py::
test_momentum_solve_never_receives_ghat`, which spies on the keyword
arguments `_apply_vertical_diffusion` passes into `solve_diffusion_implicit`
(rather than comparing evolved velocities) and asserts the `u_vel`/`v_vel`
calls never carry a non-`None` `ghat`. Measured before this test existed
(1DMIX-061 design): a mutant routing `u_vel` through `ghat_to_apply` was
caught by none of `test_kpp_ghat_gate.py`'s prior 3 tests nor by
`test_full_scenario_validation.py`/`test_cross_scheme_validation.py`/
`test_staggering.py` (13 passed).

**Coverage of this invariant is two-layered (1DMIX-063).** The 1DMIX-061
reviewer demonstrated that a call-level spy on one keyword catches only one
leak *shape*, not the invariant itself: two other implementations of the
same bug — folding `ghat` into the `visc_az` array handed to the momentum
solve (keyword absent, `k_interface` contaminated instead), and a post-hoc
counter-gradient correction applied to `u_vel`/`v_vel` after
`solve_diffusion_implicit` returns (keyword absent, no contaminated array
either) — were both measured passing all 68 tests that existed at the time,
including `test_momentum_solve_never_receives_ghat` itself. Two witnesses
are now registered, each guarding a different boundary of the same
invariant:

- `test_momentum_solve_never_receives_ghat` — call-level: spies on the exact
  keyword arguments `_apply_vertical_diffusion` passes into
  `solve_diffusion_implicit` and asserts `u_vel`/`v_vel` never carry a
  non-`None` `ghat=`. Catches an explicit `ghat=` keyword leak into either
  momentum call. Does not catch a leak that keeps the keyword absent.
- `test_momentum_invariant_to_ghat_value` — quantity-level: holds
  `apply_ghat=True` fixed and varies only the `ghat` array between two runs,
  asserting the stepped `u_vel`/`v_vel` are EXACTLY (bit-identical, no
  tolerance — momentum's true dependence on `ghat` is exactly zero, not
  small) unchanged, while asserting `theta`/`salt` genuinely change between
  the same two runs (so the test cannot pass vacuously on a `ghat`-insensitive
  fixture). Indifferent to *how* a leak reaches momentum — a keyword, a
  contaminated `visc_az`, or a post-hoc correction all change `u_vel` when
  `ghat` changes, so all three are caught by this one property. Demonstrated
  (1DMIX-063 design) failing under all three mutants above, including the
  two that this file's other three tests, `test_momentum_solve_never_
  receives_ghat` included, do not catch.

Neither of the first two witnesses alone covers every route; the
real-pipeline witness below adds the adapter boundary.

**Real-pipeline witness (1DMIX-064).** Both witnesses above hand-build a
`MixingOutput` and call `_apply_vertical_diffusion` directly, so they guard
the driver function they call, not the pipeline that feeds it: a
`ghat`-dependent term added to `MixingOutput.visc_az` inside
`KPPAdapter.compute_mixing` (measured: `visc_az[0]` 0.0 -> 5.837e-3) escaped
both and the whole 69-test focused suite. A third witness now drives the real
path:

- `test_real_pipeline_momentum_invariant_to_ghat` — real-pipeline: runs
  `KPPAdapter.compute_mixing` -> `UnifiedColumnDriver._apply_vertical_
  diffusion` with no hand-built `MixingOutput`; only `ghat` is varied, by
  wrapping the `KPPDriver.compute_mixing` instance attribute at the
  driver->adapter boundary (adapter and driver code run unmodified). Variants
  (each compared to the unmodified run; `nz = 20` faces, index 0 = surface):
  x4 and x0 of the real `ghat`; "interior" (real `ghat` + 50 at face 3 and +20
  at face 8); "allfaces" (real `ghat` + `10*(1..nz)` at every face: strictly
  positive at faces 1..nz-1, maximum > 100); "signed" (same magnitudes with
  alternating sign, so about half the faces are negative); "face0neg"
  (`-ghat - 10*(1..nz)` with a further -100 at face 0: every face negative,
  face 0 about -116, so face 0 is negative with |face 0| > 100); "face0pos"
  (allfaces with a further +100 at face 0: face 0 about +116, positive and > 100).
  The two face-0 variants (1DMIX-067) are separate because a threshold leak
  keyed to positive `ghat[0] > 100` is not reached by a negative face 0, and
  vice versa. Asserts, with exact
  equality (no tolerance), that the adapter's `visc_az` (the only adapter
  field feeding the u/v solve) and the stepped `u_vel`/`v_vel` are
  bit-identical across variants, and asserts non-vacuity (nonzero `ghat`
  differing across runs, "allfaces" nonzero at every interior face and > 100,
  "signed" containing both signs, "face0neg" negative at every face with
  |face 0| > 100, "face0pos" face 0 > 100, tracers responding to every
  variant, nonzero `tau`, momentum evolving). The interior, allfaces and signed variants are
  needed because real KPP `ghat` on the fixture is nonzero only at index 0 (the
  surface face, ignored by the implicit solve), so scaling it alone cannot make
  an interior leak visible. Correction round 1 (1DMIX-064): the first version
  (x4, x0, interior at faces 3 and 8 only, positive only) let leaks confined to
  faces >= 10, the last face, faces 1-2, negative `ghat`, or `ghat.max() > 100`
  pass; the allfaces and signed variants close those. Before 1DMIX-067 face 0,
  the only face with real nonzero `ghat` on the fixture, took only 0, 5.8, 15.8
  or 23 across all variants; the face0neg and face0pos variants close a leak
  keyed to a face-0 condition alone (negative `ghat[0]`, or `ghat[0]` above
  100 or below -100), at the sampled face-0 values only. They do not close a
  leak that conjoins a face-0 condition with a condition on another face (see
  the still-uncovered list).

Coverage map (what a passing test establishes; per scratch mutant, 1DMIX-064
correction round 1, each mutated in a copy of the tree and run against
`test_kpp_ghat_gate.py`; additional scratch mutants also caught by the
real-pipeline witness: a one-face-shifted `visc_az` term, a face-0 `ghat` term
into `visc_az[1]`, an adapter write to `state.u_vel`, and `ghat[0]` added to
the u surface flux):

- Adapter -> `visc_az` boundary (`visc_az += c*ghat` in
  `KPPAdapter.compute_mixing`): real-pipeline witness only. Caught: all faces;
  faces >= 10 only; last face only; faces 1-2 only; negative-`ghat`-only;
  leak only when `ghat.max() > 100`. Face 0 (1DMIX-067; scratch mutants N1
  and N5 from Richard's 1DMIX-064 review, which the earlier five variants
  passed 6/6; both are leaks keyed to a face-0 condition alone): `visc_az[1] += 1e-3*min(ghat[0], 0)` (negative face 0) is
  caught by face0neg alone; `visc_az[1] += 1e-3*ghat[0]*(ghat[0] > 100)`
  (positive face 0 above 100) is caught by face0pos alone. Also caught (N6,
  N7): a leak keyed to the count of nonzero `ghat` entries in 2..5, and a leak
  keyed to `ghat[6]/max|ghat|`.
- `ghat=` keyword into the momentum solve: all three witnesses.
- Contaminated `k_interface` inside `_apply_vertical_diffusion` (u, or v only,
  all faces): quantity-level and real-pipeline witnesses (call-level spy
  misses). Same contamination confined to faces >= 10: real-pipeline witness
  only.
- Post-hoc momentum correction (`u_vel += c*ghat`, all faces): quantity-level
  and real-pipeline witnesses. Confined to the last face, or `v_vel` from
  negative `ghat` only: real-pipeline witness only.

Still uncovered (the guarantee is per-boundary, per-variant, not absolute):

- a leak that depends on `ghat` only outside the tested values: a magnitude
  window not reached by the variants (for example active only for
  `0 < |ghat[5]| < 1`, or only for `60 < |ghat[10]| < 100`; both measured
  escaping, scratch mutants N4 and N3 of 1DMIX-064, still open). Leaks keyed
  to a face-0 sign or |ghat[0]| > 100 condition alone are covered (1DMIX-067),
  but face 0 still takes only
  about -116, 0, 5.8 (base and interior), 15.8 (allfaces and signed), 23 (4x)
  and +116 across the baseline plus seven variants, so a magnitude window at
  face 0 between or beyond those values (for example 30 < |ghat[0]| < 100, or
  |ghat[0]| > 116) remains uncovered; likewise any window above the allfaces
  maximum of about 200; the variants are a finite sample of `ghat` space, not
  a proof of independence;
- a leak that conjoins a face-0 sign/threshold/magnitude condition with the
  sign, threshold or extremum of another face (1DMIX-067 correction round 1,
  measured escaping the tests 6/6 by Richard as scratch mutants: M2,
  `ghat[0] < 0` and `ghat[5] > 0`; M3, `ghat[0] > 100` and `ghat[1] < 0`; M4,
  `ghat[0] < -100` and `ghat[3] > 0`; also face 0 positive with every other
  face negative, face 0 negative with all other faces zero, and face 0 as
  the array extremum). The witness certifies invariance only across its
  sampled variants; any condition that distinguishes untested `ghat`
  configurations is uncovered by construction;
- a leak gated on a quantity other than `ghat` (state, forcing, `dt`, step
  count) that is not exercised by this single-step fixture, or a `ghat`-like
  quantity recomputed inside the adapter from `state` (the wrapper varies only
  the `KPPOutput.ghat` array);
- a leak that appears only after several steps (the fixture is a single
  step);
- leaks in `run_experiment`'s own loop outside these two functions;
- GGL90's adapter (which has no `ghat`).

Salt-plume haline buoyancy forcing (`ALLOW_SALT_PLUME`/`useSALT_PLUME`, e.g.
`seaice_obcs`'s brine-rejection-driven plumes) adds a term to `bfsfc` at each of
`diagnose_bl_depth`'s 3 evaluation points: `bfsfc += boplume(1)*plume_frac(z, fact,
SPDepth)`, where `plume_frac` (`Vertical_Mixing_Models/KPP/kpp_salt_plume.py`) is
the cumulative-fraction-of-plume-already-distributed-by-depth analogue of `swfrac`
(`salt_plume_frac.F:93-107`; note it is the complement convention, unlike `swfrac`
which returns the fraction *remaining*). Only `PlumeMethod=1`/`Npower=0` (MITgcm's
own default; confirmed the only variant any tested salt-plume experiment uses) with
`SALT_PLUME_VOLUME` unset (the single-surface-level `boplume` branch) is ported;
`KPPParameters.__post_init__` raises `NotImplementedError` for any other
`PlumeMethod`/`Npower`/`SALT_PLUME_VOLUME` combination rather than silently
mishandling it. Gated by `KPPParameters.use_salt_plume` (default `False`, matching
MITgcm's own default-off `useSALT_PLUME`). See issue 1DMIX-034 (root-caused a
`seaice_obcs` `bfsfc` sign flip and `hbl` clamped to the `minKPPhbl` floor to this
previously-entirely-missing term) and
`MITgcm_to_Python_port_verification/KPP_port_validation/outputs_from_python/python_kpp_outputs_seaice_obcs_1dmix034.nc`
for the captured validation evidence.

**Double diffusion (`KPP_DOUBLEDIFF`), known unported option (1DMIX-059):**
Real MITgcm's interior mixing step (`pkg/kpp/kpp_calc.F`) optionally adds a
double-diffusive contribution to the salt/temperature diffusivities via
`kpp_routines.F::KPP_DOUBLEDIFF` (salt fingering when the water column is
salt-stratified/heat-unstable, diffusive convection in the opposite case),
called whenever `EXCLUDE_KPP_DOUBLEDIFF` is `#undef` **and** the runtime flag
`KPPuseDoubleDiff` is `.TRUE.`. `EXCLUDE_KPP_DOUBLEDIFF` is `#undef` by
default in stock MITgcm (`pkg/kpp/KPP_OPTIONS.h:68`) — i.e. the
double-diffusion code is compiled in by default — while the runtime switch
`KPPuseDoubleDiff` itself defaults `.FALSE.` (`pkg/kpp/kpp_readparms.F:84`),
so the physics is dormant unless a configuration's `data.kpp` explicitly
turns it on.

This Python port implements neither the salt-fingering nor the
diffusive-convection branch: `Vertical_Mixing_Models/KPP/kpp_routines.py::
ri_iwmix` (this port's `Ri_iwmix`-equivalent, where MITgcm's `KPP_DOUBLEDIFF`
call site lives) has no double-diffusion code path at all, and the two
associated physical constants declared on `KPPParameters`
(`Rrho0`, density-ratio limit for salt fingering; `dsfmax`, max
salt-fingering diffusivity) have no consumer anywhere in the port — confirmed
by direct read of `ri_iwmix` and a repo-wide search for both names. Until
1DMIX-059, the port's `use_doublediff` (`KPPuseDoubleDiff`) flag was declared
but completely unguarded: a caller (or a replayed MITgcm capture) that set it
`True` would silently get ordinary interior mixing with no double-diffusive
term and no indication anything was missing. `KPPParameters.__post_init__`
now raises `NotImplementedError` if `use_doublediff=True`, matching the
existing `allow_shelfice`/unported-salt-plume idiom. Physical consequence of
the omission (for any configuration that does legitimately need it): no
salt-fingering contribution to `diffus_s`/`diffus_t` in stably-salt-stratified,
heat-destabilized water (density ratio `0 < Rrho < Rrho0`), and no
diffusive-convection contribution in the opposite (heat-stratified,
salt-destabilized) regime — the interior mixing coefficients would be too
small wherever that regime actually occurs. Currently dormant in practice:
all 4 MITgcm captures this project regression-tests against
(`1D_ocean_ice_column`, `lab_sea`, `seaice_obcs_1dmix034`,
`global_oce_latlon_720`) carry `KPPuseDoubleDiff=0` in their own captured
NetCDF input attributes (measured directly, not assumed), so the guard does
not currently fire for any registered test. `exclude_doublediff`
(`EXCLUDE_KPP_DOUBLEDIFF`, the *compile-time* exclusion flag) is deliberately
**not** guarded: it is trivially satisfied at either value, since this port
never compiles the double-diffusion code in regardless of the flag — guarding
it would incorrectly reject configurations that set it in either direction
for reasons unrelated to this gap. See
`Vertical_Mixing_Models/tests/test_kpp_doublediff_guard.py` for the guard's
regression coverage, and
`MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py`/
`run_kpp_from_netcdf_input.py`, which already surface `KPPuseDoubleDiff` from
a capture and thread it into `KPPParameters(use_doublediff=...)` on replay —
so a future capture with `KPPuseDoubleDiff=1` raises this same
`NotImplementedError` on replay instead of being silently run through
unimplemented physics.

**`wscale` lookup-table extrapolation, `keep_mitgcm_bugs` (measured, 1DMIX-056
/ 1DMIX-057 — decided, default now `True`):**
`Vertical_Mixing_Models/KPP/kpp_routines.py::wscale` computes the turbulent
velocity scales `wm`/`ws` via bilinear interpolation into a precomputed
lookup table indexed by `zdiff = zehat - zmin` (`zehat = vonk·sigma·hbl·bfsfc`).
Real MITgcm (`pkg/kpp/kpp_routines.F:980`) uses the raw, unclamped `zdiff`
unconditionally; for extremely negative `bfsfc` this linearly extrapolates
below the table's lower edge, a hazard the MITgcm developers documented in
their own source comment but left active (the fix, `zdiff = MAX(0, zehat -
zmin)`, is present at line 990 but commented out). `KPPParameters.
keep_mitgcm_bugs=True` (the **default**, since 1DMIX-057) reproduces this
real, unmodified Fortran behavior — including the hazard — bit-for-bit;
`keep_mitgcm_bugs=False` instead applies the never-activated Fortran fix
(clamping `zdiff` to 0), trading exact MITgcm correspondence for protection
against the hazard's documented crash risk under extreme forcing
(`Vertical_Mixing_Models/KPP/kpp_routines.py:148-182`). Confirmed
(`wscale`'s own only currently-gated site, 1DMIX-057; `main/eos.py`'s one
`keep_mitgcm_bugs` mention is a comment stating explicitly that no gate is
needed there — a genuine second gated site would have widened this decision's
scope, and none was found).

This is not a theoretical difference: it is the measured, dominant cause of
`combined_storm`'s standalone-driver disagreement (`KPP_port_validation/
reports/kpp_scenario_standalone_summary.md`) **and** of a real, previously
mis-attributed disagreement on the actual MITgcm-capture comparison suite
(1DMIX-057), not just an idealized-scenario artifact. 1DMIX-056 first tested
and disproved the alternative hypothesis for `combined_storm` — substituting
the real Fortran's own `hbl` at each timestep into the Python port
(`MITgcm_to_Python_port_verification/scripts/
kpp_hbl_substitution_experiment.py`) left `visc_az`'s `n_gt_1pct` at 261/600
(was 270/600) and `max_abs` unchanged (3.064e-02 m²/s) — `hbl` itself is not
the dominant mechanism. Setting `keep_mitgcm_bugs=True` instead (no `hbl`
override needed) collapsed `hbl` to floating-point roundoff (max_abs
2.8e-14 m) and `visc_az`/`diff_kz_s`/`diff_kz_t`'s `n_gt_1pct` to 2-4/600,
confined to the two deepest grid cells at the two timesteps where `hbl` has
deepened to the full column depth (`kbl==nz`) — a small residual left
unexplained. `combined_storm`'s extreme cooling+wind forcing is, among this
project's 6 idealized scenarios, the only one whose excursion is large
enough for the clamp-vs-no-clamp difference to change the *result*, though
`arctic_convection` (25/2350 `wscale` evaluation points) and `hurricane_wind`
(277/2424) technically enter the clamp-differentiating branch too with no
measurable effect; the other 4 KPP scenarios (and all 6 GGL90 scenarios) are
unaffected and match to floating-point roundoff regardless of this switch.

**1DMIX-057's own contribution**: does flipping the default change any
*registered MITgcm-capture* comparison result — the real oracle this
project's fidelity claims actually rest on, not the idealized scenarios?
Both full local suites (`Vertical_Mixing_Models/tests
MITgcm_to_Python_port_verification/tests`) were run at `keep_mitgcm_bugs`
`False` and `True`: **identical `113 passed, 3 skipped` both times** — no
currently-registered test's pass/fail outcome depends on this flag. But
pass/fail alone understates it: directly instrumenting `wscale` across all 4
real capture datasets this project regression-tests
(`devel-loop/loop_state/1dmix057-wscale-capture-branch-counts.txt`) found the
clamp-differentiating branch entered at 1.2%-12.9% of evaluation points in
**every** capture — much higher than the idealized scenarios' near-zero rate
for anything but `combined_storm` — so "enters the branch" alone does not
predict "measurably affects the output"; a direct field-level A/B
(`1dmix057-wscale-ab-diff.txt`) was required to settle it per-capture:
- `1D_ocean_ice_column` (10-step and full 11,000-step) and
  `seaice_obcs_1dmix034`: **exactly zero** field difference between
  `keep_mitgcm_bugs=False` and `True`, despite nonzero branch entry (1.2%-
  4.4%) — the affected `wscale` evaluations are on trial boundary-layer-depth
  candidates that never end up selected as `hbl`, so the difference never
  propagates to output. Genuinely unaffected, not just untested.
- `lab_sea` (20-step and 6-month/100-step subsample): a real but tiny A/B
  difference (`hbl` max_abs ~3.9e-3 m; mixing coefficients ~1e-3-7.6e-2
  m²/s) — dwarfed by, and unrelated to, this experiment's own large,
  already-characterized Rib/Ricr threshold-sensitivity tail (1DMIX-019: max
  `hbl` diff vs. MITgcm 26-41 m). Confirmed by a three-way check
  (`1dmix057-wscale-capture-threeway.txt`): `Python(False)` and
  `Python(True)` vs. MITgcm max_abs/median_abs are identical to displayed
  precision for every field; `n_gt_1pct` shifts by only ~5 cells out of
  ~32,700-171,000. Practically unaffected.
- **`global_oce_latlon_720` (2,315-wet-column, 5-of-720-timestep subsample):
  materially affected, and improved.** The three-way check shows
  `keep_mitgcm_bugs=True` cuts this capture's own worst-case disagreement
  with real captured MITgcm output: `hbl` max_abs 33.90 m → 3.09 m (11x);
  `visc_az` max_abs 0.332 → 0.096 m²/s (3.5x); `diff_kz_s`/`diff_kz_t` max_abs
  0.959 → 0.110 m²/s (8.7x); `n_gt_1pct` for `hbl` drops 146→10 of 11,575.
  These are the exact values `test_kpp_mitgcm_validation_extended.py`'s own
  `test_global_oce_latlon_hbl`/`test_global_oce_latlon_mixing` docstrings
  previously attributed *entirely* to "the same Rib/Ricr threshold-
  sensitivity tail... mechanism as the other three experiments" — that
  attribution is now shown to be substantially wrong for this capture, the
  same way the pre-1DMIX-056 `combined_storm` "hbl propagation" attribution
  was: most of `global_oce_latlon`'s own worst-case tail is this same
  `wscale` clamp, not an independent Rib/Ricr effect. `ghat`'s own mismatch
  (max_abs 116.0, 394/394 active cells >1% both ways) was **unchanged** by
  this flag either way — a real, separate defect this issue did not
  investigate further (flagged for a future issue). **Root-caused and fixed
  by 1DMIX-058**: `global_oce_latlon_720` is this project's only registered
  capture with `KPP_GHAT` `#undef`'d (`use_ghat=0`); the port's
  `compute_bl_mixing` was zeroing the `ghat` *computation* itself whenever
  `use_ghat` was `False`, instead of only gating its later *application* to
  the tracer flux (which is all real MITgcm's `KPP_GHAT` actually gates —
  `blmix` computes `ghat` unconditionally). That fully explained the 394-of-
  394 (100%, not a tail) mismatch: MITgcm produced real nonzero `ghat`, the
  port produced all zeros. See `KPPParameters.use_ghat` and
  `MixingOutput.apply_ghat` above for the corrected gate location, and
  `test_global_oce_latlon_ghat`'s own docstring for the re-measured bound.

**Decision (1DMIX-057)**: the project's own stated constraint — "the ports
must replicate MITgcm and any deviation is a bug" — plus this measured
evidence (flipping breaks no registered test, is a no-op on 3 of 4 real
captures, and *measurably improves* correspondence with real MITgcm on the
4th) argues for `True` with no material counter-evidence found. The
counter-consideration (the lookup-table hazard is a genuine, MITgcm-author-
documented crash risk under extreme forcing) is real but does not argue for
a *default* of `False` in a project whose own primary goal is bit-accurate
correspondence with MITgcm, not production robustness against MITgcm's own
known hazards — so `keep_mitgcm_bugs` defaults to `True` and remains
available as an explicit `False` opt-out for callers who need the safety
clamp more than exact correspondence. `test_global_oce_latlon_hbl`/
`test_global_oce_latlon_mixing`'s tolerances and docstrings were re-derived
from the `True`-variant measurements above (tightened, not widened — see
`MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation_extended.py`).
The 1DMIX-056 witness tests (`test_kpp_combined_storm_hbl_substitution.py`)
pin `keep_mitgcm_bugs` explicitly per variant and are unaffected by this
default change.

## Invariants

- TKE ≥ 0 (GGL90); K_m, K_h ≥ 0 (both schemes).
- N² > 0 ⟺ stable stratification; N² < 0 ⟺ unstable (static instability triggers
  convective adjustment).
- Static-instability sign test is density-type-independent (verified, 1DMIX-005) —
  do not add a potential-density variant "for consistency" without re-deriving.

## Verification routes and evidence limits

- **Bit-level port fidelity** (the correct bar — both implementations should compute
  the identical formula): `Vertical_Mixing_Models/tests/test_mitgcm_kpp_lab_sea_validation.py`,
  `rtol=1e-12, atol=1e-15` against parsed MITgcm output. Currently blocked at
  collection by a missing `h5py` dependency in the `ecco` environment — open issue
  1DMIX-010.
- **Physical sanity / regression**: `Vertical_Mixing_Models/tests/{test_physics_basis,
  test_staggering,test_potential_density_gradient,test_cross_scheme_validation,
  test_full_scenario_validation}.py` — 41 passed / 0 failed as of 2026-09-15
  (excluding the h5py-blocked file).
- **Root-level MITgcm comparison**: `MITgcm_to_Python_port_verification/tests/test_kpp_mitgcm_validation.py` (1-D
  ocean-ice column, Lab Sea grid) — collects 16 tests but all currently *skip*
  because the required `.npz` comparison inputs were never generated from
  `parse_mitgcm_kpp_validation.py`. This is a real, open evidence gap (1DMIX-010),
  not a passing oracle — do not cite this file as validation evidence until it
  executes with real assertions.
- No claim of validation extends beyond the scenarios and MITgcm runs actually
  compared; see `esx/project_profile.md` "Known capability boundaries".
