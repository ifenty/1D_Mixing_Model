# GGL90 Source Code Summary

This document provides detailed summaries of each source file in the **MITgcm GGL90 package**.
- ivdc_kappa convective adjustment implementation

All 8 regression tests passing; full scenario suite (6 scenarios × 2 schemes) validated.

---

## Core Computation Files

### ggl90_calc.F (1,177 lines)

**Purpose:** Main computational routine called at each time step

**Key Responsibilities:**
1. Compute vertical shear: S² = (∂u/∂z)² + (∂v/∂z)²
2. Compute buoyancy frequency: N² = (g/ρ₀) ∂ρ/∂z
3. Calculate initial mixing length: L = √2 √TKE / √N²
4. Call ggl90_mixinglength to apply limiting
5. Compute viscosity: KappaM = c_k L √TKE
6. Compute diffusivity: KappaH = KappaM / α
7. Step TKE forward with implicit solver
8. Apply surface and bottom boundary conditions
9. Apply smoothing (if ALLOW_GGL90_SMOOTH)
10. Update GGL90viscAr and GGL90diffKr arrays

**Input Parameters:**
- `bi, bj` - Tile indices
- `sigmaR` - Vertical density gradient
- `myTime, myIter` - Time and iteration
- `myThid` - Thread ID

**Output Fields:**
- `GGL90TKE(i,j,k,bi,bj)` - Updated TKE field
- `GGL90viscArU/V(i,j,k,bi,bj)` - Eddy viscosity
- `GGL90diffKr(i,j,k,bi,bj)` - Eddy diffusivity

**Algorithm Flow:**
```
1. Initialize local arrays
2. IF (useIDEMIX) CALL GGL90_IDEMIX to get internal wave contribution
3. Compute N² and initial mixing length
4. CALL GGL90_MIXINGLENGTH to apply limits
5. Loop over vertical levels k=2,Nr:
   a. Compute vertical shear S²
   b. Compute KappaM and KappaH
   c. Build tridiagonal matrix for TKE equation
   d. Add shear production: +KappaM * S²
   e. Add buoyancy term: -KappaH * N²
   f. Add IDEMIX contribution (if enabled)
   g. Add horizontal diffusion (if enabled)
6. Apply surface BC: TKE(kTop) = m2 * u_star²
7. Apply bottom BC: TKE(kBot) = GGL90TKEbottom or ∂TKE/∂z = 0
8. Solve tridiagonal system for TKE^(n+1)
9. Apply smoothing (if enabled)
10. Update output arrays
11. Compute diagnostics
```

**Key Code Sections:**
- Lines 1-200: Declarations and initialization
- Lines 200-370: hFacI calculation and IDEMIX call
- Lines 370-500: Shear and mixing length calculation
- Lines 500-700: TKE time-stepping matrix assembly
- Lines 700-900: Boundary conditions and solver
- Lines 900-1000: Smoothing
- Lines 1000-1177: Diagnostics and output

**Coordinate System Handling:**
```fortran
IF ( usingPCoords ) THEN
  kSrf = Nr  ! Surface at highest index
  kTop = Nr
ELSE
  kSrf = 1   ! Surface at lowest index
  kTop = 2
ENDIF
```

**IFDEF Dependencies:**
- `ALLOW_GGL90_HORIZDIFF` - Horizontal TKE diffusion
- `ALLOW_GGL90_SMOOTH` - Spatial smoothing
- `ALLOW_GGL90_IDEMIX` - Internal wave coupling
- `ALLOW_GGL90_LANGMUIR` - Langmuir circulation
- `ALLOW_SHELFICE` - Ice shelf support
- `ALLOW_AUTODIFF_TAMC` - Adjoint checkpointing

---

### ggl90_mixinglength.F (421 lines)

**Purpose:** Compute mixing length with various limiting methods

**Method Selection (mxlMaxFlag):**

#### Method 0: Simple depth limit
```fortran
L(k) = min(L(k), water_column_depth)
```

#### Method 1: Distance to boundaries
```fortran
MaxLength = min(depth_to_surface, depth_to_bottom)
L(k) = min(L(k), MaxLength)
```

#### Method 2: Two-way sweep (ECCOv4 R4 uses this)
```fortran
! Downward sweep
DO k = 2, Nr
  L_down(k) = min(L(k), L_down(k-1) + Δz(k-1))
ENDDO

! Upward sweep
DO k = Nr-1, 2, -1
  L(k) = min(L(k), L(k+1) + Δz(k))
ENDDO

! Apply downward limit
DO k = 2, Nr
  L(k) = min(L(k), L_down(k))
ENDDO
```

#### Method 3: Geometric mean
```fortran
L(k) = SQRT(L_upward(k) * L_downward(k))
```

**Surface Mixing Flag:**
```fortran
IF (mxlSurfFlag) THEN
  ! Force mixing between first two levels
  GGL90mixingLength(i,j,kTop) = drF(kSrf) * recip_coordFac
ENDIF
```

**Langmuir Amplification:**
```fortran
IF (useLANGMUIR) THEN
  IF (L(k) == L_downward_sweep(k)) THEN
    ! At mixed layer base - amplify
    LC_mixingLength(k) = LC_Gamma * L(k)
  ELSE
    LC_mixingLength(k) = L(k)
  ENDIF
ENDIF
```

**Minimum Length Application:**
```fortran
#ifdef GGL90_REGULARIZE_MIXINGLENGTH
  ! Smooth version for adjoint
  L(k) = SQRT(L(k)² + L_min²)
#else
  ! Standard version
  L(k) = MAX(L(k), L_min)
#endif
```

**Output:**
- `GGL90mixingLength(i,j,k)` - Final mixing length
- `rMixingLength(i,j,k)` - Inverse (1/L) for efficiency
- `LCmixingLength(i,j,k)` - Langmuir-modified (if enabled)

**IFDEF Dependencies:**
- `ALLOW_GGL90_LANGMUIR` - Langmuir circulation
- `GGL90_REGULARIZE_MIXINGLENGTH` - Adjoint-friendly formulation
- `ALLOW_SHELFICE` - Ice shelf support
- `ALLOW_AUTODIFF_TAMC` - Adjoint checkpointing

---

### ggl90_calc_diff.F (74 lines)

**Purpose:** Transfer GGL90 diffusivity to main model arrays

**Algorithm:**
```fortran
DO k=1,Nr
  DO j=jMin,jMax
    DO i=iMin,iMax
      ! Transfer to tracer diffusivity array
      KappaRT(i,j,k,bi,bj) = GGL90diffKr(i,j,k,bi,bj)
      
      ! Apply maximum limit
      KappaRT(i,j,k,bi,bj) = MIN(KappaRT(i,j,k,bi,bj), 
                                  GGL90diffMax * recip_coordFac²)
    ENDDO
  ENDDO
ENDDO
```

**Called from:** `do_oceanic_phys.F` after `ggl90_calc.F`

**Purpose:** Separate routine for modularity and potential future extensions

---

### ggl90_calc_visc.F (64 lines)

**Purpose:** Transfer GGL90 viscosity to main model arrays

**Algorithm:**
```fortran
DO k=1,Nr
  DO j=jMin,jMax
    DO i=iMin,iMax
      ! Transfer to momentum viscosity arrays
      KappaRU(i,j,k,bi,bj) = GGL90viscArU(i,j,k,bi,bj)
      KappaRV(i,j,k,bi,bj) = GGL90viscArV(i,j,k,bi,bj)
      
      ! Apply maximum limit
      KappaRU(i,j,k,bi,bj) = MIN(KappaRU(i,j,k,bi,bj), 
                                  GGL90viscMax * recip_coordFac²)
      KappaRV(i,j,k,bi,bj) = MIN(KappaRV(i,j,k,bi,bj), 
                                  GGL90viscMax * recip_coordFac²)
    ENDDO
  ENDDO
ENDDO
```

**Called from:** `do_oceanic_phys.F` after `ggl90_calc.F`

---

## Configuration and Initialization Files

### ggl90_readparms.F (451 lines)

**Purpose:** Read runtime parameters from data.ggl90

**Structure:**
1. **Default parameter initialization** (lines 104-162)
2. **Open data.ggl90 file** (lines 98-101)
3. **Read GGL90_PARM01** (lines 174-185)
4. **Read GGL90_PARM02** if useIDEMIX (lines 188-205)
5. **Read GGL90_PARM03** if useLANGMUIR (lines 209-226)
6. **Validate parameters** (lines 250-310)
7. **Print configuration** (lines 313-441)

**Default Values:**
```fortran
GGL90ck              = 0.1
GGL90ceps            = 0.7
GGL90alpha           = 1.0
GGL90m2              = 3.75
GGL90TKEmin          = 1.0e-11
GGL90TKEsurfMin      = 1.0e-4
GGL90TKEbottom       = UNSET_RL → GGL90TKEmin
GGL90viscMax         = 100.0
GGL90diffMax         = 100.0
GGL90diffTKEh        = 0.0
GGL90mixingLengthMin = 1.0e-8
mxlMaxFlag           = 0
mxlSurfFlag          = .FALSE.
GGL90_dirichlet      = .TRUE.
calcMeanVertShear    = .FALSE.
useIDEMIX            = .FALSE.
useLANGMUIR          = .FALSE.
```

**Validation Checks:**
- `GGL90TKEmin > 0`
- `GGL90TKEbottom ≥ 0`
- `GGL90mixingLengthMin > 0`
- `GGL90viscMax > 0`
- `GGL90diffMax > 0`
- If useIDEMIX: `OLx ≥ 3` and `OLy ≥ 3`

**Retired Parameters:**
- `GGL90taveFreq` - Now use diagnostics instead

---

### ggl90_check.F (166 lines)

**Purpose:** Validate package configuration and dependencies

**Checks Performed:**

1. **Required implicit solvers:**
```fortran
IF (.NOT. implicitDiffusion) THEN
  ERROR: "GGL90 needs implicitDiffusion to be enabled"
ENDIF
IF (.NOT. implicitViscosity) THEN
  ERROR: "GGL90 needs implicitViscosity to be enabled"
ENDIF
```

2. **Package incompatibilities:**
```fortran
IF (useKPP) ERROR: "GGL90 and KPP cannot be used together"
IF (usePP81) ERROR: "GGL90 and PP81 cannot be used together"
IF (useMY82) ERROR: "GGL90 and MY82 cannot be used together"
```

3. **Langmuir limitations:**
```fortran
IF (useLANGMUIR .AND. useAbsVorticity) THEN
  ERROR: "Missing Coriolis contribution from Langmuir"
ENDIF
IF (useLANGMUIR .AND. useCDscheme) THEN
  ERROR: "Missing Coriolis contribution from Langmuir"
ENDIF
```

4. **Adjoint warnings:**
```fortran
IF (useGGL90inAdMode .AND. adMxlMaxFlag > 1) THEN
  WARNING: "adMxlMaxFlag > 1 tends to be unstable"
ENDIF
```

5. **IDEMIX requirements:**
```fortran
IF (useIDEMIX .AND. (OLx < 3 .OR. OLy < 3)) THEN
  ERROR: "OLx/OLy must be ≥ 3 for IDEMIX"
ENDIF
```

**Called from:** `packages_check.F` during model initialization

---

### ggl90_init_fixed.F (67 lines)

**Purpose:** Initialize fixed (time-invariant) fields

**Operations:**
1. Initialize corner mask for smoothing (if ALLOW_GGL90_SMOOTH)
```fortran
DO k=1,Nr
  DO j=1-OLy+1,sNy+OLy
    DO i=1-OLx+1,sNx+OLx
      mskCor(i,j,bi,bj) = maskC(i,j,k,bi,bj) 
                        * maskC(i-1,j,k,bi,bj)
                        * maskC(i,j-1,k,bi,bj)
                        * maskC(i-1,j-1,k,bi,bj)
    ENDDO
  ENDDO
ENDDO
```

**Called from:** `packages_init_fixed.F`

---

### ggl90_init_varia.F (156 lines)

**Purpose:** Initialize prognostic variables (TKE and IDEMIX fields)

**Operations:**

1. **Initialize TKE to minimum:**
```fortran
DO k=1,Nr
  DO j=1-OLy,sNy+OLy
    DO i=1-OLx,sNx+OLx
      GGL90TKE(i,j,k,bi,bj) = GGL90TKEmin
    ENDDO
  ENDDO
ENDDO
```

2. **Read TKE initial condition (if provided):**
```fortran
IF (GGL90TKEFile .NE. ' ') THEN
  CALL READ_FLD_XYZ_RL(GGL90TKEFile, ' ', GGL90TKE, 0, myThid)
ENDIF
```

3. **Initialize IDEMIX fields (if enabled):**
```fortran
IF (useIDEMIX) THEN
  IDEMIX_E(:,:,:,bi,bj) = 0.0
  
  ! Read tidal forcing
  IF (IDEMIX_tidal_file .NE. ' ') THEN
    CALL READ_FLD_XY_RL(IDEMIX_tidal_file, ' ', IDEMIX_F_B, 0, myThid)
  ENDIF
  
  ! Read wind forcing
  IF (IDEMIX_wind_file .NE. ' ') THEN
    CALL READ_FLD_XY_RL(IDEMIX_wind_file, ' ', IDEMIX_F_S, 0, myThid)
  ENDIF
ENDIF
```

4. **Apply exchange for parallel execution:**
```fortran
CALL GGL90_EXCHANGES(myThid)
```

**Called from:** `packages_init_variables.F`

---

## I/O and Diagnostics Files

### ggl90_diagnostics_init.F (202 lines)

**Purpose:** Register diagnostic fields for output

**Available Diagnostics:**

| Code | Description | Units | Grid |
|------|-------------|-------|------|
| GGL90TKE | Turbulent Kinetic Energy | m²/s² | SMR |
| GGL90Lmx | Mixing length | m | SMR |
| GGL90Prd | TKE production (shear) | m²/s³ | SMR |
| GGL90Dsp | TKE dissipation | m²/s³ | SMR |
| GGL90ArU | Eddy viscosity at U | m²/s | UUR |
| GGL90ArV | Eddy viscosity at V | m²/s | VVR |
| GGL90Kr | Eddy diffusivity | m²/s | SMR |
| GGL90N2 | Squared buoyancy frequency | s⁻² | SMR |
| GGL90S2 | Squared vertical shear | s⁻² | SMR |
| GGL90Emn | Minimum TKE applied | m²/s² | SMR |
| GGL90tkS | Surface TKE flux | m³/s³ | SM |
| GGL90TkP | Pressure work on TKE | m²/s³ | SMR |

**IDEMIX Diagnostics (if enabled):**

| Code | Description | Units | Grid |
|------|-------------|-------|------|
| IDEMIX_E | Internal wave energy | J/m³ | SMR |
| IDEMIXtd | Dissipation time scale | s | SMR |
| IDEMIXc0 | Vertical group velocity | m/s | SMR |
| IDEMIXv0 | Horizontal group velocity | m/s | SMR |
| IDEMIXFb | Bottom forcing | W/m² | SM |
| IDEMIXFs | Surface forcing | W/m² | SM |
| IDEMIXgT | TKE source from IW | m²/s³ | SMR |
| IDEMIXKr | Osborn diffusivity | m²/s | SMR |

**Grid Codes:**
- SM = Scalar at cell center (2D)
- SMR = Scalar at cell center (3D)
- UUR = U-velocity point (3D)
- VVR = V-velocity point (3D)

**Called from:** `diagnostics_main_init.F`

---

### ggl90_output.F (98 lines)

**Purpose:** Write state to snapshot and averaging files

**Operations:**

1. **Write instantaneous snapshots:**
```fortran
IF (DIFFERENT_MULTIPLE(GGL90dumpFreq, myTime, deltaTClock)) THEN
  CALL WRITE_FLD_XYZ_RL('GGL90TKE.', suff, GGL90TKE, myIter, myThid)
  IF (GGL90writeState) THEN
    CALL WRITE_FLD_XYZ_RL('GGL90ArU.', suff, GGL90viscArU, myIter, myThid)
    CALL WRITE_FLD_XYZ_RL('GGL90ArV.', suff, GGL90viscArV, myIter, myThid)
    CALL WRITE_FLD_XYZ_RL('GGL90Kr.', suff, GGL90diffKr, myIter, myThid)
  ENDIF
ENDIF
```

2. **Write IDEMIX fields (if enabled):**
```fortran
IF (useIDEMIX) THEN
  CALL WRITE_FLD_XYZ_RL('IDEMIX_E.', suff, IDEMIX_E, myIter, myThid)
ENDIF
```

**Called from:** `do_the_model_io.F`

---

### ggl90_read_pickup.F (69 lines)

**Purpose:** Read restart (pickup) files

**Format:**
- Either **legacy format** (separate .data files) or **modern format** (netCDF)

**Fields Read:**
1. `GGL90TKE` - Always read
2. `IDEMIX_E` - If useIDEMIX

**Algorithm:**
```fortran
IF (pickupSuff == ' ') THEN
  ! Try legacy format: pickup.ggl90.data
  CALL READ_MFLDS_SET(fn, ...)
  CALL READ_MFLDS_3D_RL('GGL90TKE', GGL90TKE, 1, myThid)
  IF (useIDEMIX) THEN
    CALL READ_MFLDS_3D_RL('IDEMIX_E', IDEMIX_E, 1, myThid)
  ENDIF
ELSE
  ! Modern format: pickup.0000036000.ggl90.nc
  CALL MDS_READ_FIELD(...)
ENDIF

CALL GGL90_EXCHANGES(myThid)
```

**Called from:** `the_model_main.F` at initialization if restarting

---

### ggl90_write_pickup.F (60 lines)

**Purpose:** Write restart (pickup) files

**Format:** Same as read (legacy or modern)

**Fields Written:**
1. `GGL90TKE`
2. `IDEMIX_E` (if useIDEMIX)

**Algorithm:**
```fortran
CALL WRITE_MFLDS_SET(fn, ...)
CALL WRITE_MFLDS_3D_RL('GGL90TKE', GGL90TKE, 1, myIter, myThid)
IF (useIDEMIX) THEN
  CALL WRITE_MFLDS_3D_RL('IDEMIX_E', IDEMIX_E, 1, myIter, myThid)
ENDIF
```

**Called from:** `do_the_model_io.F` at specified intervals

---

## Parallel Execution Support

### ggl90_exchanges.F (48 lines)

**Purpose:** Exchange halo regions for parallel execution

**Operations:**
```fortran
! Exchange TKE
CALL EXCH_3D_RL(GGL90TKE, Nr, myThid)

! Exchange viscosity and diffusivity
CALL EXCH_3D_RL(GGL90viscArU, Nr, myThid)
CALL EXCH_3D_RL(GGL90viscArV, Nr, myThid)
CALL EXCH_3D_RL(GGL90diffKr, Nr, myThid)

! Exchange IDEMIX fields (if enabled)
IF (useIDEMIX) THEN
  CALL EXCH_3D_RL(IDEMIX_E, Nr, myThid)
  CALL EXCH_XY_RL(IDEMIX_F_B, myThid)
  CALL EXCH_XY_RL(IDEMIX_F_S, myThid)
ENDIF
```

**When Called:**
- After initialization
- After TKE update (if horizontal diffusion enabled)
- After reading pickup files

**Purpose:** Ensures consistency of overlap (halo) regions when domain is decomposed across multiple processors

---

## Optional Feature Files

### ggl90_idemix.F (598 lines)

**Purpose:** Compute internal wave energy and mixing contribution

**Reference:** Olbers and Eden (2013), JPO

**Main Subroutine: GGL90_IDEMIX**

**Algorithm:**

1. **Compute buoyancy frequency N(z):**
```fortran
Nsquare(k) = gravity * gravitySign * recip_rhoConst * sigmaR(k) * coordFac
```

2. **Compute vertical group velocity c_0:**
```fortran
! Integral of N over depth
bN0(i,j) = Σ_k [√N(k) * Δz(k)]

! Vertical structure function
c_star(k) = IDEMIX_hofx1(k/Nr) * bN0 / (π * j_star)

! Mean vertical group velocity
c_0(k) = IDEMIX_gamma * c_star(k) / IDEMIX_tau_v
```

3. **Compute horizontal group velocity v_0:**
```fortran
v_0(k) = IDEMIX_gamma * bN0 / (IDEMIX_tau_h * π * j_star)
```

4. **Compute dissipation time scale τ_d:**
```fortran
! Intermediate function
fxa = IDEMIX_gofx2(c_0² / N² / IDEMIX_jstar)

! Dissipation parameter
tau_d(k) = IDEMIX_mu0 * N(k) * fxa * √(bN0 / (π * j_star * E))
```

5. **Add forcing:**
```fortran
! Bottom forcing (tides)
forc(kBot) = IDEMIX_frac_F_b * IDEMIX_F_B(i,j) / Δz(kBot)

! Surface forcing (near-inertial winds)
forc(kSrf) = IDEMIX_frac_F_s * IDEMIX_F_S(i,j) / Δz(kSrf)

! GM eddy forcing (if enabled)
IF (IDEMIX_include_GM) THEN
  forc(k) = forc(k) + GM_energy_flux(k)
ENDIF
```

6. **Time-step E with implicit vertical diffusion:**
```fortran
! Tri-diagonal system for ∂E/∂t - ∇·(c_0*E) = F - τ_d*E²
a(k) = -Δt * c_0(k) / Δz²
b(k) = 1 + Δt * τ_d(k) * E(k)
c(k) = -Δt * c_0(k) / Δz²
rhs(k) = E(k) + Δt * forc(k)

CALL SOLVE_TRIDIAGONAL(a, b, c, rhs, E_new)
```

7. **Compute TKE source:**
```fortran
gTKE(k) = τ_d(k) * E²(k)
```

8. **Compute Osborn diffusivity (diagnostic):**
```fortran
osborn_diff(k) = IDEMIX_mixing_efficiency * gTKE(k) / N²(k)
osborn_diff(k) = MIN(osborn_diff(k), IDEMIX_diff_max)
```

**Helper Functions:**

**IDEMIX_gofx2(x):**
```fortran
! Integral: ∫₀¹ (1 - z²)^(-1/2) * [1 - h(z)]^(-3/2) dz
! Where h(z) = z² / (1 + x*z)
! Approximated by polynomial fit
```

**IDEMIX_hofx1(x):**
```fortran
! Vertical structure function h(x)
! h(x) = sin(π*x) for simple case
! More complex forms for realistic stratification
```

**IFDEF Dependencies:**
- `ALLOW_GGL90_IDEMIX` - Must be defined
- `GGL90_IDEMIX_CVMIX_VERSION` - Use CVMIX regularizations
- `ALLOW_GMREDI` - For GM eddy coupling
- `ALLOW_AUTODIFF_TAMC` - Adjoint checkpointing

---

### ggl90_add_stokesdrift.F (79 lines)

**Purpose:** Add Stokes drift contribution for Langmuir circulation

**Physical Basis:**
- Surface waves create **Stokes drift**: a net forward motion
- Interaction with Eulerian current creates **Langmuir circulation**
- This enhances vertical mixing in the surface boundary layer

**Stokes Drift Profile:**
```fortran
! Exponential decay with depth
u_Stokes(z) = u_Stokes(0) * exp(-4π * z / λ)

! Where:
! λ = LC_lambda = 40 m (typical)
! u_Stokes(0) ~ u_star * √(u_star / c_phase) from wave theory
```

**Contribution to Shear:**
```fortran
! Vertical derivative of Stokes drift
dU_Stokes/dz = -(4π/λ) * u_Stokes(z)
dV_Stokes/dz = -(4π/λ) * v_Stokes(z)

! Add to total shear for TKE production
S²_total = S²_Eulerian + (dU_Stokes/dz)² + (dV_Stokes/dz)²
            + 2 * (dU/dz * dU_Stokes/dz + dV/dz * dV_Stokes/dz)
```

**Called from:** `ggl90_calc.F` if `useLANGMUIR = .TRUE.`

**IFDEF Dependencies:**
- `ALLOW_GGL90_LANGMUIR` - Must be defined

---

## Header Files

### GGL90.h (178 lines)

**Purpose:** Define common blocks and parameter declarations

**Structure:**

1. **Physical constants:**
```fortran
PARAMETER (SQRTTWO = 1.41421356237310)
PARAMETER (GGL90eps = 2.23e-16)  ! Small number for regularization
```

2. **Runtime parameters (REAL):**
```fortran
COMMON /GGL90_PARMS_R/
  GGL90ck, GGL90ceps, GGL90alpha, GGL90m2,
  GGL90diffTKEh, GGL90mixingLengthMin,
  GGL90TKEmin, GGL90TKEsurfMin, GGL90TKEbottom,
  GGL90viscMax, GGL90diffMax,
  GGL90dumpFreq, mxlMaxFlag, adMxlMaxFlag
```

3. **Runtime parameters (LOGICAL):**
```fortran
COMMON /GGL90_PARMS_L/
  GGL90isOn, GGL90mixingMaps, GGL90writeState,
  GGL90_dirichlet, mxlSurfFlag, calcMeanVertShear,
  useIDEMIX, useLANGMUIR
```

4. **Runtime parameters (CHARACTER):**
```fortran
COMMON /GGL90_PARMS_C/
  GGL90TKEFile
```

5. **Prognostic fields:**
```fortran
COMMON /GGL90_FIELDS/
  GGL90TKE(1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr, nSx, nSy),
  GGL90viscArU(...), GGL90viscArV(...), GGL90diffKr(...)
```

6. **Smoothing mask (if ALLOW_GGL90_SMOOTH):**
```fortran
#ifdef ALLOW_GGL90_SMOOTH
COMMON /GGL90_CORNER/
  mskCor(1-OLx:sNx+OLx, 1-OLy:sNy+OLy, nSx, nSy)
#endif
```

7. **IDEMIX fields (if ALLOW_GGL90_IDEMIX):**
```fortran
#ifdef ALLOW_GGL90_IDEMIX
COMMON /GGL90_IDEMIX_VARS/
  IDEMIX_E(1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr, nSx, nSy),
  IDEMIX_F_B(...), IDEMIX_F_S(...)
  
COMMON /GGL90_IDEMIX_R/
  IDEMIX_tau_v, IDEMIX_tau_h, IDEMIX_gamma, IDEMIX_jstar,
  IDEMIX_mu0, IDEMIX_mixing_efficiency, IDEMIX_diff_max, ...
  
COMMON /GGL90_IDEMIX_C/
  IDEMIX_tidal_file, IDEMIX_wind_file
  
COMMON /GGL90_IDEMIX_L/
  IDEMIX_include_GM, IDEMIX_include_GM_bottom
#endif
```

8. **Langmuir parameters (if ALLOW_GGL90_LANGMUIR):**
```fortran
#ifdef ALLOW_GGL90_LANGMUIR
COMMON /GGL90_LCPARA/
  LC_Gamma, LC_num, LC_lambda
#endif
```

---

### GGL90_OPTIONS.h (42 lines)

**Purpose:** Compile-time configuration options

**Content:**
```fortran
#ifdef ALLOW_GGL90

! Enable horizontal diffusion of TKE
#undef ALLOW_GGL90_HORIZDIFF

! Use horizontal averaging (OPA style)
#undef ALLOW_GGL90_SMOOTH

! Allow IDEMIX internal wave model
#undef ALLOW_GGL90_IDEMIX
#ifdef ALLOW_GGL90_IDEMIX
  ! Use CVMIX version regularizations
  #define GGL90_IDEMIX_CVMIX_VERSION
#endif

! Include Langmuir circulation
#undef ALLOW_GGL90_LANGMUIR

! Adjoint-friendly mixing length
#undef GGL90_REGULARIZE_MIXINGLENGTH

! Recover old bug (pre-June 2023)
#undef GGL90_MISSING_HFAC_BUG

#endif /* ALLOW_GGL90 */
```

**How to Use:**
- Copy to `code/` directory in your run configuration
- Change `#undef` to `#define` to enable features
- Recompile model

---

## Adjoint-Related Files

### ggl90_ad_diff.list (191 lines)

**Purpose:** List of subroutines for which AD compiler generates differentiated code

**Format:**
```
ggl90_calc
ggl90_mixinglength
ggl90_idemix
ggl90_add_stokesdrift
ggl90_calc_diff
ggl90_calc_visc
```

**Used by:** TAF (Transformation of Algorithms in Fortran) compiler

---

### ggl90_ad_check_lev*_dir.h

**Purpose:** Directives for AD checkpointing at different levels

**Files:**
- `ggl90_ad_check_lev1_dir.h` - Level 1 (innermost loops)
- `ggl90_ad_check_lev2_dir.h` - Level 2
- `ggl90_ad_check_lev3_dir.h` - Level 3
- `ggl90_ad_check_lev4_dir.h` - Level 4 (outermost)

**Content Example (lev1):**
```fortran
CADJ STORE GGL90TKE = comlev1_bibj_k, key=kkey, kind=isbyte
CADJ STORE GGL90mixingLength = comlev1_bibj_k, key=kkey, kind=isbyte
CADJ STORE rMixingLength = comlev1_bibj_k, key=kkey, kind=isbyte
```

**Purpose:** Tells AD compiler which variables to checkpoint (store) for later use in reverse pass

---

## Summary Table

| File | Lines | Type | Main Purpose |
|------|-------|------|-------------|
| ggl90_calc.F | 1177 | Computation | Main TKE calculation |
| ggl90_idemix.F | 598 | Optional | Internal wave model |
| ggl90_readparms.F | 451 | Config | Read parameters |
| ggl90_mixinglength.F | 421 | Computation | Mixing length limiting |
| ggl90_diagnostics_init.F | 202 | I/O | Register diagnostics |
| GGL90.h | 178 | Header | Common blocks |
| ggl90_check.F | 166 | Config | Validate setup |
| ggl90_init_varia.F | 156 | Init | Initialize variables |
| ggl90_output.F | 98 | I/O | Write output |
| ggl90_add_stokesdrift.F | 79 | Optional | Langmuir circulation |
| ggl90_calc_diff.F | 74 | Computation | Transfer diffusivity |
| ggl90_read_pickup.F | 69 | I/O | Read restart |
| ggl90_init_fixed.F | 67 | Init | Initialize fixed fields |
| ggl90_calc_visc.F | 64 | Computation | Transfer viscosity |
| ggl90_write_pickup.F | 60 | I/O | Write restart |
| ggl90_exchanges.F | 48 | Parallel | Halo exchange |
| GGL90_OPTIONS.h | 42 | Header | Compile options |
| ggl90_ad_diff.list | 191 | Adjoint | AD directives |
| ggl90_ad_check_lev*.h | 5-237 | Adjoint | AD checkpointing |

**Total:** 3,958 lines of source code

---

**End of Source Code Summary**
