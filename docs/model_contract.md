# Scientific model or analysis contract

This project ports two MITgcm vertical-mixing parameterizations to a 1-D Python
column model. Every non-trivial function must cite the MITgcm source file and
line numbers it corresponds to; any deviation from MITgcm physics must be
explicitly justified in a code comment and, if uncertain, opened as an issue
(see `open_issues.md`/`closed_issues.md` for the current and historical record).

## Coordinate and unit conventions

- `z` positive **up**; `depth` positive **down**; `z = -depth`.
- Pressure is positive and increases with depth: `pressure = -depth` (1 dbar ≈ 1 m).
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

## Equation of state

`Vertical_Mixing_Models/main/eos.py::jmd95_eos` — full Jackett & McDougall (1995) nonlinear EOS. Stratification
(N²) **must** use potential density (adjacent levels evaluated at a common reference
pressure), not in-situ density — see `Vertical_Mixing_Models/main/eos.py::compute_ggl90_buoyancy_frequency_squared`
and closed issue 1DMIX-001 (a real historical bug used in-situ density here). The
static-instability sign test (`compute_static_instability_mask`) is the one place
in-situ density is *correct*, verified against MITgcm's
`model/src/convective_adjustment.F` (closed issue 1DMIX-005) — do not "fix" this to
potential density without re-checking that source.

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
Non-local transport (`ghat`) is active only under unstable surface buoyancy forcing
(`bfsfc < 0`, i.e. net surface cooling/freshening dominates) — see
`Vertical_Mixing_Models/docs/dev_notes/KPP_PHYSICS_EXPLANATION.md` for the worked sign logic.

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
