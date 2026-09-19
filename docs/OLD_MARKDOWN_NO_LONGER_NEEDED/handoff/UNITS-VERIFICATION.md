# Units Verification Task

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Systematically verify the units of ALL variables in the four main documentation files, cross-referencing with MITgcm Fortran source code.

## Context

User found unit error: `ghat` was incorrectly documented as `[1/s]` in Fortran when it's actually `[s/m²]` (same as Python). This suggests there may be other unit errors in the documentation.

## Files to Verify

1. `docs/GGL90/GGL90_package_description.tex` (4,459 lines)
2. `docs/GGL90/GGL90_port_description.tex` (596 lines)
3. `docs/KPP/KPP_package_description.tex` (2,810 lines)
4. `docs/KPP/KPP_port_description.tex` (779 lines)

## Verification Strategy

### Phase 1: Extract All Variable Definitions

For each file, compile a list of:
- Variable names
- Their stated units in the documentation
- Location (section, line number)

Look for patterns like:
- `[units]` in square brackets
- Units in parentheses after variable descriptions
- Table entries with unit columns
- Variable lists in "Quick Reference" or "Glossary" sections

### Phase 2: Cross-Reference with MITgcm Source

For each variable, check MITgcm Fortran source code:

**GGL90 sources**:
- `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/GGL90.h` (parameter declarations)
- `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ggl90_calc.F` (variable comments)
- `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ggl90_readparms.F` (parameter descriptions)

**KPP sources**:
- `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/KPP.h` (parameter declarations)
- `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_routines.F` (variable comments, extensive documentation)
- `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_readparms.F` (parameter descriptions)

### Phase 3: Dimensional Analysis

For key equations, verify dimensional consistency:

**Example**: TKE equation
```
∂TKE/∂t = P + B - ε
```
All terms must have units `[m²/s³]` (energy per unit mass per unit time)

**Example**: Mixing length
```
ℓ = √(2×TKE) / N
```
Check: `√[m²/s²] / [1/s] = [m]` ✓

### Phase 4: Common Variable Classes

Verify standard units for common variable types:

**Physical quantities**:
- Length/depth: `[m]`
- Time: `[s]`
- Velocity: `[m/s]`
- Temperature: `[°C]` or `[K]`
- Salinity: `[psu]` or dimensionless
- Density: `[kg/m³]`
- Pressure: `[Pa]` or `[dbar]`

**Mixing parameters**:
- TKE: `[m²/s²]`
- Buoyancy frequency N²: `[1/s²]` or `[s⁻²]`
- Shear frequency S²: `[1/s²]` or `[s⁻²]`
- Mixing length: `[m]`
- Eddy viscosity/diffusivity: `[m²/s]`
- Dissipation rate: `[m²/s³]`

**Dimensionless parameters**:
- Richardson number: dimensionless
- Turbulent Prandtl number (α): dimensionless
- Shape function coefficients: dimensionless

**Flux quantities**:
- Heat flux: `[W/m²]` or `[m·K/s]`
- Buoyancy flux: `[m²/s³]`
- Momentum flux (stress): `[m²/s²]` or `[N/m²]`

**Special cases**:
- Coriolis parameter: `[1/s]` or `[rad/s]`
- Gravity: `[m/s²]`
- Specific heat: `[J/(kg·K)]`

## Detailed Verification Checklist

### GGL90 Variables to Verify

**Parameters (from GGL90_package_description.tex)**:
- [ ] GGL90TKEmin: minimum TKE
- [ ] GGL90TKEsurfMin: minimum surface TKE
- [ ] GGL90m2: parameter m² in ℓ equation
- [ ] GGL90alpha: turbulent Prandtl number
- [ ] GGL90ck: TKE surface boundary condition coefficient
- [ ] GGL90ceps: dissipation coefficient
- [ ] GGL90diffTKEh: horizontal TKE diffusivity
- [ ] GGL90diffKrS: background vertical diffusivity for salt
- [ ] GGL90diffKrT: background vertical diffusivity for temperature
- [ ] GGL90mixingLengthMin: minimum mixing length
- [ ] GGL90TKEbottom: bottom TKE

**State variables**:
- [ ] TKE: turbulent kinetic energy
- [ ] N²: buoyancy frequency squared
- [ ] S²: shear frequency squared
- [ ] ℓ: mixing length
- [ ] κₑ: eddy diffusivity
- [ ] νₑ: eddy viscosity

**Fluxes and forcings**:
- [ ] u*: friction velocity
- [ ] Surface TKE forcing
- [ ] Buoyancy forcing

### KPP Variables to Verify

**Parameters (from KPP_package_description.tex)**:
- [ ] KPPRi0: critical bulk Richardson number
- [ ] KPPviscAr: background vertical viscosity
- [ ] KPPdiffKrS: background vertical diffusivity for salt
- [ ] KPPdiffKrT: background vertical diffusivity for temperature
- [ ] KPPhbl: boundary layer depth
- [ ] KPPghat: nonlocal transport coefficient (VERIFIED: [s/m²])
- [ ] KPPcg: nonlocal transport shape function coefficient

**State variables**:
- [ ] hbl: boundary layer depth
- [ ] Rib: bulk Richardson number
- [ ] u*: friction velocity
- [ ] w*: convective velocity scale
- [ ] wm: velocity scale in boundary layer
- [ ] ws: scalar velocity scale in boundary layer

**Shape functions** (should all be dimensionless):
- [ ] G(σ): generic shape function
- [ ] Gm(σ): momentum shape function
- [ ] Gs(σ): scalar shape function

**Fluxes**:
- [ ] bo: surface buoyancy forcing
- [ ] bosol: solar buoyancy forcing

## Output Format

Create a verification report: `UNITS-VERIFICATION-REPORT.md` with:

1. **Summary**: Total variables checked, errors found, corrections made
2. **Errors Found**: List of incorrect units with:
   - Variable name
   - Documented unit (incorrect)
   - Correct unit (from MITgcm source)
   - File and line number
   - MITgcm source reference
3. **Corrections Made**: Git diff showing fixes
4. **Verification Tables**: For each file, table of all variables with verified units

## Tools to Use

```bash
# Search for variable declarations in Fortran
grep -n "variable_name" /path/to/fortran/file.F

# Search for units in documentation
grep -n "\[.*\]" docs/file.tex

# Extract parameter tables
# Look for tabular environments with unit columns
```

## Success Criteria

- All variables in all four documents have units verified against MITgcm source
- All dimensional equations checked for consistency
- All errors corrected and documented
- Verification report provides complete audit trail
- Future readers can trust unit specifications

## References

- MITgcm GGL90 source: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
- MITgcm KPP source: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
- Gaspar et al. (1990) - GGL90 original paper
- Large et al. (1994) - KPP original paper

---

**Builder (Bob)**: Execute all 4 phases, create verification report, fix all errors.  
**Reviewer (Richard)**: Spot-check 10+ variables per file, verify corrections, approve commit.  
**Architect (Arch)**: Launch Bob, monitor progress, coordinate Richard review.
