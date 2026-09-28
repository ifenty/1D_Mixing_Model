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
