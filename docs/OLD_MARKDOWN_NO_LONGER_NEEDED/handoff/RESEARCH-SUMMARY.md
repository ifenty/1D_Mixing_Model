# GGL90 LaTeX Documentation - Research Summary
## Bob's Research Phase Findings

**Date:** 2026-08-06  
**Task:** Step 3 - Create comprehensive LaTeX documentation for MITgcm GGL90 package

---

## 1. Package Overview

### Scientific Background
- **Primary reference:** Gaspar et al. (1990), JGR 95(C9), pp. 16,179-16,193
- **Implementation reference:** Blanke & Delecluse (1993), JPO 23, pp. 1363-1388
- **Model type:** Turbulent Kinetic Energy (TKE) based vertical mixing scheme
- **Theory:** One-equation turbulence closure with prognostic TKE

### Key Physics
1. **TKE Evolution:** Prognostic equation balancing production, buoyancy, and dissipation
2. **Mixing Length:** Multiple computation methods (0, 1, 2) following Blanke & Delecluse
3. **Eddy Coefficients:** κ_m (viscosity) and κ_h (diffusivity) from TKE and mixing length
4. **Stability Functions:** Empirical functions relating Prandtl number to Richardson number

---

## 2. MITgcm Source Files Analysis

### Core Computation Files (2,570 lines total)
1. **ggl90_calc.F** (1,177 lines) - Main driver, orchestrates entire calculation
2. **ggl90_mixinglength.F** (421 lines) - Three methods for limiting mixing length
3. **ggl90_calc_diff.F** (74 lines) - Transfer diffusivity to model arrays
4. **ggl90_calc_visc.F** (64 lines) - Transfer viscosity to model arrays

### Configuration Files (795 lines total)
5. **ggl90_readparms.F** (451 lines) - Parameter reading from data.ggl90
6. **ggl90_check.F** (166 lines) - Validation of parameter consistency
7. **GGL90.h** (178 lines) - State variable and parameter declarations

### Initialization Files (223 lines total)
8. **ggl90_init_fixed.F** (67 lines) - Time-invariant initialization
9. **ggl90_init_varia.F** (156 lines) - Time-varying initialization, TKE initial conditions

### I/O and Diagnostics (369 lines total)
10. **ggl90_diagnostics_init.F** (202 lines) - Register all diagnostic fields
11. **ggl90_output.F** (98 lines) - Output state to files
12. **ggl90_read_pickup.F** (69 lines) - Read restart files
13. **ggl90_write_pickup.F** (60 lines) - Write restart files

### Optional Features (677 lines total)
14. **ggl90_idemix.F** (598 lines) - Internal wave energy model (IDEMIX v1)
15. **ggl90_add_stokesdrift.F** (79 lines) - Langmuir circulation parameterization

### Utilities
16. **ggl90_exchanges.F** (48 lines) - Halo exchanges for parallel runs
17. **GGL90_OPTIONS.h** (42 lines) - Compile-time CPP flags
18. **ggl90_ad_*.h** (8 lines total) - Adjoint model directives

**Total:** ~3,958 lines of Fortran code

---

## 3. Key Parameters (with defaults from ggl90_readparms.F)

### Core Physics Parameters
| Parameter | Default | Units | Description | Line Ref |
|-----------|---------|-------|-------------|----------|
| GGL90ck | 0.1 | - | Constant in viscosity coefficient (eq. 10) | :108 |
| GGL90ceps | 0.7 | - | Dissipation constant (Kolmogorov 1942) | :109 |
| GGL90alpha | 1.0 | - | Relates viscosity to diffusivity | :110 |
| GGL90m2 | 3.75 | - | Surface TKE flux constant | :112 |
| GGL90TKEmin | 1.0e-11 | m²/s² | Minimum TKE (background) | :113 |
| GGL90TKEsurfMin | 1.0e-4 | m²/s² | Minimum surface TKE | :115 |
| GGL90TKEbottom | UNSET_RL | m²/s² | Bottom TKE (default=GGL90TKEmin) | :116 |
| GGL90mixingLengthMin | 1.0e-8 | m | Minimum mixing length | :120 |
| GGL90viscMax | 1.0e2 | m²/s | Maximum viscosity | :117 |
| GGL90diffMax | 1.0e2 | m²/s | Maximum diffusivity | :118 |

### Mixing Length Control
| Parameter | Default | Description | Line Ref |
|-----------|---------|-------------|----------|
| mxlMaxFlag | 0 | Mixing length method (0, 1, or 2) | :121 |
| mxlSurfFlag | .FALSE. | Force mixing near surface | :123 |
| adMxlMaxFlag | UNSET_I | Method for adjoint (default=mxlMaxFlag) | :122 |

### Numerical Parameters
| Parameter | Default | Description | Line Ref |
|-----------|---------|-------------|----------|
| GGL90diffTKEh | 0.0 | Horizontal TKE diffusivity | :119 |
| GGL90_dirichlet | .TRUE. | Use Dirichlet boundary conditions | :125 |
| calcMeanVertShear | .FALSE. | Calculate mean vertical shear | :126 |

### IDEMIX Parameters (optional, ~10 parameters, lines 136-152)
### Langmuir Parameters (optional, 3 parameters, lines 159-161)

---

## 4. State Variables (from GGL90.h)

### Prognostic Variables
- **GGL90TKE(i,j,k)** - Turbulent kinetic energy (m²/s²), defined at interfaces

### Diagnostic Variables (updated each timestep)
- **GGL90viscArU(i,j,k)** - Viscosity at U-points (m²/s)
- **GGL90viscArV(i,j,k)** - Viscosity at V-points (m²/s)
- **GGL90diffKr(i,j,k)** - Diffusivity for T/S/tracers (m²/s)

### IDEMIX Variables (optional)
- **IDEMIX_E(i,j,k)** - Internal wave energy (m²/s²)
- **IDEMIX_F_B(i,j)** - Bottom forcing (tides)
- **IDEMIX_F_S(i,j)** - Surface forcing (wind)

---

## 5. Compile-Time Options (GGL90_OPTIONS.h)

| CPP Flag | Default | Description |
|----------|---------|-------------|
| ALLOW_GGL90_HORIZDIFF | #undef | Enable horizontal diffusion of TKE |
| ALLOW_GGL90_SMOOTH | #undef | Horizontal averaging (OPA method) |
| ALLOW_GGL90_IDEMIX | #undef | Enable IDEMIX internal wave model |
| ALLOW_GGL90_LANGMUIR | #undef | Enable Langmuir circulation |
| GGL90_REGULARIZE_MIXINGLENGTH | #undef | SQRT regularization for adjoint |
| GGL90_MISSING_HFAC_BUG | #undef | Recover old bug (pre-Jun 2023) |

---

## 6. Execution Flow (ggl90_calc.F structure)

### Main Subroutine: GGL90_CALC
**Input parameters:**
- bi, bj - Tile indices
- sigmaR - Vertical gradient of iso-neutral density
- myTime, myIter - Time information
- myThid - Thread ID

**Execution sequence:**
1. **Initialize** (lines ~190-300)
   - Set coordinate system (Z or P)
   - Initialize local arrays
   - Compute hFacI (interface thickness factors)

2. **Optional: IDEMIX** (lines ~259-266)
   - Call GGL90_IDEMIX if useIDEMIX=T
   - Compute IDEMIX_gTKE (internal wave → TKE conversion)

3. **Compute stratification and shear** (lines ~300-500)
   - N² (buoyancy frequency squared) from sigmaR
   - S² (vertical shear squared) from U, V
   - Surface stress (u*²) from wind forcing

4. **Optional: Langmuir** (lines ~450-550)
   - Add Stokes drift contribution to shear
   - Amplify mixing length

5. **Compute mixing length** (lines ~550-600)
   - Call GGL90_MIXINGLENGTH
   - Methods 0, 1, or 2 (user specified)

6. **Compute eddy coefficients** (lines ~600-750)
   - κ_m = c_k * L * √TKE (viscosity)
   - κ_h = κ_m / alpha (diffusivity)
   - Apply background floors (TKEmin)
   - Cap at maximum values

7. **TKE budget terms** (lines ~750-900)
   - Production: P = κ_m * S²
   - Buoyancy: B = -κ_h * N²
   - Dissipation: ε = c_eps * TKE^(3/2) / L

8. **Build tridiagonal system** (lines ~900-1000)
   - Implicit treatment of dissipation and diffusion
   - Surface BC: TKE flux from wind
   - Bottom BC: TKE floor or drag

9. **Solve TKE equation** (lines ~1000-1050)
   - Thomas algorithm (tridiagonal solver)
   - Update GGL90TKE array

10. **Optional: Horizontal smoothing** (lines ~1050-1100)
    - If ALLOW_GGL90_SMOOTH defined
    - Average κ to U/V points

11. **Transfer to model arrays** (lines ~1100-1150)
    - Call GGL90_CALC_VISC (for GGL90viscArU/V)
    - Call GGL90_CALC_DIFF (for GGL90diffKr)

12. **Diagnostics** (lines ~1150-1177)
    - Fill diagnostic arrays if requested

---

## 7. Input/Output Mapping (for Appendix B)

### External Inputs (from main model, per timestep)
1. **Temperature (T)** → via sigmaR (density gradient)
2. **Salinity (S)** → via sigmaR (density gradient)
3. **Zonal velocity (U)** → for vertical shear
4. **Meridional velocity (V)** → for vertical shear
5. **Surface wind stress (τ_x, τ_y)** → for u*² (surface TKE flux)
6. **Surface buoyancy flux** → via N² at surface
7. **Grid geometry** → drF, drC, hFacC, hFacW, hFacS
8. **Time step** → dTtracerLev

### Package Outputs (to main model, per timestep)
1. **GGL90viscArU(i,j,k)** → Vertical viscosity for momentum (U)
2. **GGL90viscArV(i,j,k)** → Vertical viscosity for momentum (V)
3. **GGL90diffKr(i,j,k)** → Vertical diffusivity for T, S, tracers

### Internal State (prognostic, carried between timesteps)
1. **GGL90TKE(i,j,k)** → Turbulent kinetic energy

### IDEMIX Inputs (optional)
1. **IDEMIX_F_B** → Tidal energy forcing (2D field, read from file)
2. **IDEMIX_F_S** → Wind energy forcing (2D field, read from file)

### IDEMIX Outputs (optional)
1. **IDEMIX_gTKE** → TKE source from internal wave dissipation

---

## 8. Mixing Length Methods (from ggl90_mixinglength.F)

### Method 0 (mxlMaxFlag=0): Distance to boundaries
```
L(k) = min(L_Gaspar(k), z_from_surface(k), z_from_bottom(k))
```

### Method 1 (mxlMaxFlag=1): One-way downward sweep
```
1. L(k) = L_Gaspar(k)
2. L(k) = min(L(k), L(k-1) + Δz(k-1))  [downward pass]
3. L(k) = min(L(k), z_from_bottom(k))
```

### Method 2 (mxlMaxFlag=2): Two-way sweep (ECCOv4 default)
```
1. L(k) = L_Gaspar(k)
2. L(k) = min(L(k), L(k-1) + Δz(k-1))  [downward pass]
3. L(k) = min(L(k), L(k+1) + Δz(k))    [upward pass]
4. L(k) = min(L(k), z_from_bottom(k))  [final limit]
```

Where **L_Gaspar = √2 * √TKE / √N²** (from Gaspar et al. 1990, eq. 9)

---

## 9. Key Equations

### TKE Evolution (Gaspar et al. 1990, eq. 5)
```
∂TKE/∂t = P + B - ε + D
```
Where:
- **P = κ_m * S²** (shear production)
- **B = -κ_h * N²** (buoyancy term, can be source or sink)
- **ε = c_eps * TKE^(3/2) / L** (dissipation)
- **D = ∂/∂z(κ_E * ∂TKE/∂z)** (vertical diffusion of TKE)

### Eddy Viscosity (eq. 10)
```
κ_m = c_k * L * √TKE
```

### Eddy Diffusivity (eq. 11)
```
κ_h = κ_m / α
```

### Mixing Length (eq. 9, before limiting)
```
L = √2 * √TKE / N
```

### Stability Function (Prandtl number)
Not explicitly in Gaspar paper - uses constant α (GGL90alpha)

---

## 10. Document Structure Plan

### Sections (matching KPP template)
1. **Introduction and Scientific Background** (3-4 pages)
   - Physical motivation
   - GGL90 vs KPP comparison
   - Key equations overview

2. **Package Architecture and Call Flow** (4-5 pages)
   - Initialization sequence
   - Main timestep flow diagram (TikZ)
   - File organization

3. **Parameter Initialization** (3-4 pages)
   - Complete parameter table with defaults
   - Physical interpretation of each parameter

4. **Main Driver: GGL90_CALC** (5-6 pages)
   - Step-by-step execution with code snippets
   - Line number references throughout

5. **Mixing Length Computation** (4-5 pages)
   - Three methods explained
   - Code snippets from ggl90_mixinglength.F
   - Diagrams showing profiles

6. **TKE Evolution and Budget** (5-6 pages)
   - Production term
   - Buoyancy term
   - Dissipation term
   - Time integration scheme
   - Code snippets from ggl90_calc.F

7. **Eddy Coefficient Calculation** (3-4 pages)
   - Viscosity computation
   - Diffusivity computation
   - Background floors
   - Code snippets

8. **Boundary Conditions** (3-4 pages)
   - Surface: wind-driven TKE flux
   - Bottom: drag or minimum TKE
   - Code snippets

9. **Model Interface Routines** (2-3 pages)
   - ggl90_calc_visc.F
   - ggl90_calc_diff.F
   - How outputs couple to main model

10. **Initialization and Restart** (2-3 pages)
    - ggl90_init_fixed.F
    - ggl90_init_varia.F
    - ggl90_read/write_pickup.F

11. **Compile-Time Options** (2-3 pages)
    - Table of all CPP flags
    - Impact of each flag

12. **Output and Diagnostics** (2-3 pages)
    - Available diagnostics
    - ggl90_diagnostics_init.F

13. **IDEMIX Extension (Optional)** (2-3 pages)
    - Brief overview
    - Parameters
    - When to use

14. **Frequently Encountered Issues** (2-3 pages)
    - Parameter tuning guidance
    - Common mistakes
    - Troubleshooting

15. **Conclusions** (1 page)

16. **Appendix A: Glossary** (2 pages)

17. **Appendix B: Input/Output Mapping** (3-4 pages) ★★★ CRITICAL
    - Table: External inputs with sources
    - Table: Package outputs with consumers
    - Data flow diagram (TikZ)
    - State variable evolution

**Estimated Total:** 55-70 pages, ~1,800-2,200 lines of LaTeX

---

## 11. Critical Implementation Notes

### Line Number Verification Strategy
- All line numbers verified against MITgcm source (Sep 2025 checkpoint)
- Format: `(filename:L###)` in text, full caption in code listings

### Code Snippet Strategy
- Show 10-30 line chunks with context
- Always include file name and line range
- Use Fortran90KPP lstlisting style (from KPP doc)

### TikZ Diagrams
1. **Main call flow:** GGL90_CALC → subroutines
2. **Mixing length methods:** Visual comparison of 3 methods
3. **Appendix B data flow:** Inputs → GGL90 → Outputs

### Appendix B Priority
- This is user's top requirement
- Must be crystal clear
- Include example timestep walkthrough
- Diagram showing where each variable comes from/goes to

---

## 12. Open Questions / Decisions Made

### ✅ IDEMIX Scope
**Decision:** Brief subsection (~2-3 pages) as optional extension. Not deep-dive.

### ✅ Appendix B Scope
**Decision:** Only timestep-varying I/O. Parameters go in main sections.

### ✅ Line Number Format
**Decision:** Both in-text `(file.F:L###)` and code caption format.

### ✅ LaTeX Compilation
**Decision:** Not required during development. Test at end if time permits.

### To Verify During Writing
- Exact line numbers for all code snippets (may have shifted slightly)
- ECCOv4 R4 specific settings (GGL90alpha=30, etc.) - include as examples
- Whether ggl90_exchanges.F needs detailed coverage (probably brief mention)

---

## 13. Checkpoint Plan

**After Phase 3 (Architecture complete):** Report to Arch  
**After Phase 6 (Physics complete):** Report to Arch before starting Appendix B  
**After Phase 14 (Appendix B complete):** Final report to Arch

---

## 14. Estimated Time Breakdown

| Phase | Task | Hours |
|-------|------|-------|
| 0 | Research (DONE) | 4 |
| 1 | Skeleton + preamble | 2 |
| 2-4 | Intro + Architecture + Parameters | 7 |
| 5-9 | Core physics sections (TKE, mixing length, coefficients, BC) | 10 |
| 10-13 | Interface + Options + Diagnostics + IDEMIX | 5 |
| 14 | **Appendix B** (CRITICAL) | 5 |
| 15-16 | Issues + Conclusions + Glossary | 2 |
| 17-18 | Verification + Polish | 3 |
| **Total** | | **32** |

---

## 15. Key MITgcm Files to Reference

**Most Critical:**
- ggl90_calc.F (1,177 lines) - MAIN FILE, reference most
- ggl90_mixinglength.F (421 lines) - mixing length section
- ggl90_readparms.F (451 lines) - parameter defaults
- GGL90.h (178 lines) - variable declarations

**Important:**
- ggl90_calc_diff.F, ggl90_calc_visc.F - interface
- ggl90_init_*.F - initialization
- ggl90_check.F - validation logic
- GGL90_OPTIONS.h - CPP flags

**Optional (brief mention):**
- ggl90_idemix.F - if covering IDEMIX
- ggl90_diagnostics_init.F - for diagnostics section
- ggl90_*_pickup.F - for restart section

---

## 16. References for Scientific Background

### Primary Literature
1. **Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990)**  
   "A simple eddy kinetic energy model for simulations of the oceanic vertical mixing"  
   *JGR*, 95(C9), pp. 16,179-16,193  
   doi:10.1029/JC095iC09p16179

2. **Blanke, B., and P. Delecluse (1993)**  
   "Variability of the Tropical Atlantic Ocean Simulated by a General Circulation Model"  
   *JPO*, 23, pp. 1363-1388  
   doi:10.1175/1520-0485(1993)023<1363:VOTTAO>2.0.CO;2

### Optional Features
3. **Olbers, D., and C. Eden (2013)** - IDEMIX  
   "A Global Model for the Diapycnal Diffusivity Induced by Internal Gravity Waves"  
   *JPO*, 43, pp. 1759-1779

4. **Tak, Y.-J., Y. Song, et al. (2022)** - Langmuir  
   "Development of a Langmuir circulation parameterization for GGL90"  
   *Ocean Modelling*, 170, 101942

### MITgcm
5. **MITgcm Documentation** - https://mitgcm.readthedocs.io/

---

**Research Phase Complete: 2026-08-06, 4 hours**  
**Next: Begin Phase 1 (LaTeX Skeleton)**

---
**End of Research Summary**
