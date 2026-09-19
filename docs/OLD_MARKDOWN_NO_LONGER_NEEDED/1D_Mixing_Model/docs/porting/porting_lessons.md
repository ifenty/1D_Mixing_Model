# Porting Lessons: MITgcm Fortran to Python

This document captures key insights and lessons learned from porting MITgcm's GGL90 and KPP vertical mixing schemes from Fortran to Python. These lessons may be useful for future porting work or understanding critical implementation details.

## General Porting Principles

### Sign Conventions and Coordinate Systems

**Lesson**: Always verify sign conventions match between Fortran and Python, especially for vertical gradients and fluxes.

**Context**: MITgcm uses specific sign conventions that must be preserved:
- Depth stored as negative values (negative-downward convention)
- Vertical gradients computed as `d/dz` where z is positive upward
- Buoyancy frequency N² = -(g/ρ₀)(dρ/dz) requires explicit minus sign

**Impact**: Incorrect signs can produce physically unrealistic results (e.g., stable stratification appearing unstable).

### Array Indexing: Fortran 1-based vs Python 0-based

**Lesson**: MITgcm Fortran uses 1-based indexing with k=1 at the surface, while Python uses 0-based indexing with index 0 at the surface.

**Context**: 
- **Fortran**: Vertical levels indexed k=1 (surface) to k=Nr (bottom), where Nr is the total number of levels
- **Python**: Vertical levels indexed k=0 (surface) to k=Nr-1 (bottom)
- **MITgcm convention**: k increases downward (k=1 is shallowest, k=Nr is deepest)

**Common Translation Patterns**:
```fortran
! Fortran: Surface boundary condition at k=1
DO k=1,Nr
  IF (k .EQ. 1) THEN
    ! Surface layer special case
  ENDIF
ENDDO
```

```python
# Python: Surface boundary condition at k=0
for k in range(Nr):
    if k == 0:
        # Surface layer special case
```

**Why It Matters**: 
- Hardcoded `k=1` in Fortran must become `k=0` in Python
- Loop ranges `1:Nr` in Fortran become `0:Nr` or `range(Nr)` in Python
- Array slicing differs: Fortran `array(2:Nr)` excludes surface; Python `array[1:]` excludes surface
- Off-by-one errors in boundary conditions are common if this isn't carefully handled

**Verification Strategy**: 
- Always verify surface (k=0 Python, k=1 Fortran) and bottom (k=Nr-1 Python, k=Nr Fortran) boundary conditions separately
- Check that special-case logic for first/last vertical levels translates correctly
- Test with small Nr (e.g., 5 levels) to make index errors obvious

### Verifying Units Against the Fortran Source

**Lesson**: Trust the MITgcm Fortran source comments as the authoritative unit specification. Do not infer units from dimensional analysis alone, and never document a "unit difference" between Python and Fortran without confirming it in the source.

**Context**: MITgcm consistently documents variable units in the header comment blocks of each subroutine (e.g., `pkg/kpp/kpp_routines.F` documents every argument with its units in parentheses). These comments are the ground truth. When porting, the Python variable should carry the *same* units as the Fortran variable it replaces — a genuine unit difference is rare and almost always a documentation mistake, not an intentional design choice.

**Concrete Example (ghat)**: The KPP nonlocal transport coefficient `ghat` was at one point documented as `[1/s]` in Fortran and `[s/m²]` in Python, implying a conversion was needed. Checking the source settled it immediately:
```fortran
c     ghat   (imt)    - nonlocal transport coefficient                  (s/m^2)
```
Both implementations use `[s/m²]`. The "difference" was purely a documentation error. Dimensional analysis confirms it: `ghat = cg / (ws × hbl)` gives `[1] / ([m/s] × [m]) = [s/m²]`.

**Why It Matters**:
- A wrongly documented unit invites a "fix" (spurious multiply/divide by a length or time scale) that silently corrupts results.
- Unit mismatches between coupled terms are a leading cause of physically plausible but quantitatively wrong output — the model runs, but the answer is off by a factor.

**Verification Strategy**:
- For every ported variable, locate its unit in the Fortran subroutine header comment and copy that unit verbatim into the Python docstring / documentation.
- Cross-check dimensional consistency of each equation as a *secondary* confirmation, not the primary source.
- When a term combines several variables, verify the composite units resolve to the expected result (e.g., all terms in the TKE budget must be `[m²/s³]`).
- Treat any claimed Python-vs-Fortran unit difference as a red flag: confirm it in the source before documenting it, since the ports are meant to preserve physics exactly.
- Grep the Fortran headers directly: `grep -n "variable_name" pkg/<scheme>/*.F` usually lands on the documented unit.

### Vertical Grid Staggering (Cell Centers vs Interfaces)

**Lesson**: Reproduce MITgcm's vertical staggering *exactly* so ported output arrays overlay MITgcm output index-for-index — no re-indexing, no interpolation, no half-cell averaging. Decide up front which quantities live at cell centers and which live at interfaces (W-points), and preserve that placement end-to-end.

**Context**:
- **Cell-centered quantities** (tracers, velocities): `theta[k]`, `salt[k]`, `u_vel[k]` sit at the center of cell `k` (MITgcm `rC(k)`).
- **Interface (W-point) quantities** (diffusivities, viscosities, mixing length, N²): index `k` = **top face of cell k**, i.e. the interface between cell `k-1` (above) and cell `k` (below). Index `k=0` is the ocean surface face (MITgcm `rF(k)` layout).
- **Surface face carries no diffusive flux**: `diffKz[0] = viscAz[0] = 0` (MITgcm `KPPdiffKzT(1)=0`).
- Combined with 1-based↔0-based indexing: `PythonArray[k] ↔ MITgcmArray(k+1)` for both center and interface quantities. No half-cell shift for these.
- The vertical diffusive flux through the top face of cell `k` is `-K[k] * (C[k] - C[k-1]) / drC[k]`, where `drC[k] = depth[k-1] - depth[k]` is the center-to-center distance (MITgcm `gad_diff_r.F`).

**Why It Matters**: If centers and interfaces are conflated, or an array is silently shifted, the model still runs and produces plausible profiles — but fluxes are computed across the wrong faces and comparison against MITgcm output requires ad hoc re-indexing that masks real discrepancies.

**Verification Strategy**:
- Encode the intended placement of every array as explicit assertions in a staggering test (see `tests/test_staggering.py`), and confirm output overlays a MITgcm baseline with `max|Δ| = 0`.
- The staggering map is documented in `docs/dev_notes/MITGCM_STAGGERING.md` — keep it in sync when adding new output fields.
- EOS choice is orthogonal to staggering: the grid layout is identical for linear and JMD95 EOS.

---

## GGL90 Porting Lessons

### 1. Buoyancy Frequency Calculation (Critical)

**Issue**: Initial Python port used in-situ density gradients for N², which introduced spurious compressibility effects.

**Correct Implementation**: Must use potential density gradients (MITgcm's `sigmaR`), not in-situ density gradients.

**Why It Matters**: In-situ density varies with depth even for well-mixed water columns due to compressibility. Using potential density removes this artifact and matches the Fortran implementation exactly.

**Location**:
- Fortran: `pkg/ggl90/ggl90_calc.F` uses `sigmaR` for stratification
- Python: Corrected to use `compute_potential_density_gradient()` in `eos.py`

**Formula**:
```
N² = -(g/ρ₀) × (dρ_potential/dz)  [NOT dρ_in_situ/dz]
```

### 2. Mixing Length Distance Calculations

**Issue**: Computing distance to boundaries requires careful handling of cell-center vs cell-face positions.

**Correct Implementation**: 
- Use cell-center depths for computing distance to surface/bottom
- Ensure consistent reference frame (z positive up)
- Account for non-uniform grid spacing

**Why It Matters**: Mixing length scale directly affects TKE production and dissipation. Errors in distance calculations can lead to incorrect boundary layer depths and mixing intensities.

### 3. Static Instability Handling

**Issue**: MITgcm includes an optional convective adjustment feature (`ivdc_kappa`) that enhances diffusivity in statically unstable regions.

**Correct Implementation**: Python port must include this feature as a separate post-processing step, applied after GGL90 computes its base diffusivities.

**Why It Matters**: Without this feature, convective events may not be adequately parameterized in coarse-resolution models.

**Integration**: Implemented in `main/convective_adjustment.py`, called from unified driver after mixing scheme step.

---

## KPP Porting Lessons

### 1. Boundary Layer Depth Interpolation

**Issue**: Off-by-one error in interpolation guard when searching for the depth where bulk Richardson number exceeds threshold.

**Correct Implementation**: When interpolating between levels k and k+1, ensure array bounds check prevents accessing k+1 when k is already at the bottom level.

**Why It Matters**: Boundary layer depth is the fundamental diagnostic in KPP. Errors here cascade into all subsequent mixing calculations.

**Fix Pattern**:
```python
# Ensure k+1 exists before interpolating
if k < len(depth) - 1:
    # Safe to interpolate between depth[k] and depth[k+1]
    ...
else:
    # Use depth[k] as boundary layer base
    ...
```

### 2. Shape Function Implementation

**Issue**: KPP uses cubic polynomial shape functions G(σ) where σ = z/h (normalized depth in boundary layer). Coefficient values and evaluation order matter.

**Correct Implementation**: Use exact polynomial coefficients from Large et al. (1994):
- Momentum: `G_m(σ) = a₀ + a₁σ + a₂σ² + a₃σ³`
- Tracers: `G_s(σ)` with different coefficients

**Why It Matters**: Shape functions control the vertical profile of enhanced mixing in the boundary layer. Small coefficient errors can significantly change mixed layer depth and heat/momentum fluxes.

### 3. Nonlocal Transport Term

**Issue**: Nonlocal transport (counter-gradient flux) is unique to KPP and has no direct analog in other mixing schemes.

**Correct Implementation**: 
- Only applied within boundary layer (z < h)
- Computed from surface buoyancy flux and boundary layer depth
- Has correct sign to transport against local gradient when appropriate

**Why It Matters**: Nonlocal transport is essential for capturing convective plumes and other non-gradient-flux processes. Omitting or mis-signing this term produces incorrect tracer profiles.

### 4. The `ghat` Half-Level Offset (Do Not "Fix" It)

**Issue**: In MITgcm, `ghat` (nonlocal transport) is deliberately staggered half a level away from the diffusivities: `diffKz` lives at the **top** face of cell `k`, while `ghat[k]` lives at the **bottom** face of cell `k` (`kpp_transport_t.F:21-25`). The diffusion flux through the top face of cell `k` pairs `diffKz[k]` with `ghat[k-1]`.

**Correct Implementation**: Preserve this offset exactly. In the Python port, `ghat` is **not** shifted onto the same grid as `diffKz`; the solver pairs `diffKz[k]` with `ghat[k-1]` (`kpp_core_driver.py`).

**Why It Matters**: This looks like an inconsistency and invites a well-meaning "fix" that re-aligns `ghat` with `diffKz`. Doing so silently changes the tracer tendencies. The offset is intentional MITgcm design, not a bug.

### 5. KPP Internal Grid vs Output Grid (+1 Shift)

**Issue**: KPP internally computes diffusivities on a **bottom-of-cell** grid (MITgcm `kpp_routines.F`, `diffus(i,k,mr)`), then **shifts by +1 on output** (`kpp_calc.F:574-588`, `vddiff(k-1) -> KPPdiffKzT(k)`).

**Correct Implementation**: The Python port mirrors this: internal computation on the bottom-of-cell grid, then a +1 shift on output (`kpp_core.py` Step 9). Always compare against MITgcm's **output** arrays (`KPPdiffKzT`, etc.), never its internal `diffus`.

**Why It Matters**: Comparing the Python output against MITgcm's *internal* `diffus` array (rather than its output arrays) will show a spurious one-level mismatch and lead to chasing a nonexistent bug. The relabel is a pure index shift plus a symmetric solver update, provably leaving the time-stepped tracer solution unchanged.

### 6. Diagnostic vs Prognostic State

**Issue**: Unlike GGL90 (which carries prognostic TKE), KPP is fully diagnostic and recomputes all mixing coefficients each timestep.

**Correct Implementation**: Python port must not store or advance any KPP state variables between timesteps. All inputs come from current ocean state (T, S, U, V).

**Why It Matters**: This is a fundamental difference between schemes. KPP has no initialization or restart requirements beyond parameter setup.

---

## Common Patterns Across Both Schemes

### 1. Parameter Handling

**Lesson**: Use YAML configuration files for parameters rather than hardcoding values.

**Benefits**:
- Easy to compare default vs ECCOv4 vs custom parameter sets
- Clear separation of physics constants vs tuning parameters
- Enables automated parameter sensitivity studies

**Implementation**: 
- `configuration_yamls/ggl90_default.yaml`, `ggl90_eccov4r4.yaml`
- `configuration_yamls/kpp_default.yaml`

### 2. Grid and Coordinate Abstraction

**Lesson**: Create a unified grid representation (`ColumnGrid` class) that both schemes can use.

**Benefits**:
- Handles depth/z coordinate conversions in one place
- Provides consistent interface for both schemes
- Simplifies testing with different vertical resolutions

**Implementation**: `main/column_grid.py`

### 3. Equation of State (EOS)

**Lesson**: Use the same EOS implementation for both schemes to ensure consistency.

**Benefits**:
- Eliminates EOS as a source of scheme-to-scheme differences
- Matches MITgcm's JMD95 polynomial implementation
- Handles special cases (e.g., temperature clipping) identically

**Implementation**: `main/eos.py` provides `jmd95_density()` used by both schemes

### 4. Testing Strategy

**Lesson**: Scenario-based validation with realistic ocean profiles is more effective than unit tests alone.

**Benefits**:
- Catches integration issues between components
- Tests physically realistic conditions (convection, storms, diurnal cycles)
- Provides interpretable output (profiles, time series)

**Implementation**: 6 scenarios in `simulations/scenarios/`, batch runner in `main/run_scenarios.py`

---

## Recommendations for Future Porting Work

1. **Start with Sign Conventions**: Document coordinate system, gradient definitions, and flux directions before writing any physics code.

2. **Port Incrementally**: Implement one major component at a time (e.g., stratification first, then mixing length, then TKE evolution) with validation at each step.

3. **Use MITgcm as Ground Truth**: When in doubt, trust the Fortran implementation. Python adaptations should only deviate when there's a clear benefit (e.g., cleaner array handling).

4. **Preserve Physics Exactly**: Avoid "improvements" or "modernizations" to the physics during porting. Port first, then optimize or enhance in separate, well-documented steps.

5. **Test with Edge Cases**: Include scenarios with:
   - Static instability (convection)
   - Strong stratification (thermocline)
   - Weak forcing (calm baseline)
   - Extreme forcing (hurricanes, arctic conditions)

6. **Document Differences**: If Python must differ from Fortran (e.g., due to language constraints), document why in the code and in porting notes.

7. **Version Control Physics Constants**: Keep physical constants (g, ρ₀, Cₚ) in a single source of truth (`physical_parameters.yaml`) to avoid inconsistencies.

---

## Known Limitations of Current Ports

Both Python ports are **1D column models** and do not include:
- Horizontal advection
- Horizontal diffusion
- 3D effects (lateral boundaries, topography)
- Coupling to ice models
- MPI parallelization

These are intentional simplifications for research and validation purposes. The ports faithfully represent the vertical mixing physics but are not full ocean models.

---

## References

- MITgcm source: `/Users/ifenty/git_repo_others/MITgcm/`
- GGL90 package description: `docs/GGL90/GGL90_package_description.tex`
- KPP package description: `docs/KPP/KPP_package_description.tex`
- GGL90 port reference: `docs/GGL90/GGL90_port_description.tex`
- KPP port reference: `docs/KPP/KPP_port_description.tex`
