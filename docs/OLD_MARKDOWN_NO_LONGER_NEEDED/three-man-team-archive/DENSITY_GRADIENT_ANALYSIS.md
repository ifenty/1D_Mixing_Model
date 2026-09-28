# Density Gradient Analysis: MITgcm vs. Python Port

**Date**: 2026-07-20  
**Reviewer**: Claude Code (Architect Agent)

## Executive Summary

✅ **VERIFIED**: Both MITgcm (KPP and GGL90) and the Python port use **potential density gradients** (iso-neutral density gradients), not in-situ density gradients.

❌ **DISCREPANCY FOUND**: The Python port's GGL90 implementation uses **in-situ density** directly, while MITgcm's GGL90 uses **potential density** computed at a common reference pressure.

---

## MITgcm Implementation Analysis

### 1. GGL90 Density Gradient Formulation

**Key Files:**
- `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ggl90_calc.F`
- `/Users/ifenty/git_repo_others/MITgcm/model/src/grad_sigma.F`
- `/Users/ifenty/git_repo_others/MITgcm/model/src/do_oceanic_phys.F`

**Documentation from ggl90_calc.F:55:**
```fortran
C     sigmaR :: Vertical gradient of iso-neutral density
```

**The Variable `sigmaR` (grad_sigma.F:90-98):**
```fortran
sigmaR(i,j,k) = maskC(i,j,k,bi,bj)*maskC(i,j,k-1,bi,bj)
     &                *recip_drC(k)*rkSign
     &                *(sigKp1(i,j)-sigKm1(i,j))
```

Where (from grad_sigma.F:32-33):
```fortran
C     sigKm1     :: upper level density computed at current pressure
C     sigKp1     :: lower level density computed at current pressure
```

**How These Are Computed (do_oceanic_phys.F:812-836):**

For Z-coordinates:
```fortran
! sigKp1 = in-situ density at level k
rhoKp1(i,j) = rhoInSitu(i,j,k,bi,bj)

! sigKm1 = potential density: T(k-1), S(k-1) evaluated at pressure k
CALL FIND_RHO_2D(
     I                 iMin, iMax, jMin, jMax, k,
     I                 theta(1-OLx,1-OLy,k-1,bi,bj),
     I                 salt (1-OLx,1-OLy,k-1,bi,bj),
     O                 rhoKm1,
     I                 k-1, bi, bj, myThid )
```

**Formula:**
```
sigmaR = [ρ(T(k), S(k), P(k)) - ρ(T(k-1), S(k-1), P(k))] / Δz
```

This is a **potential density gradient** because water from level k-1 is evaluated at the pressure of level k.

**Buoyancy Frequency (ggl90_calc.F:347-348):**
```fortran
C     buoyancy frequency
Nsquare(i,j,k) = gravity*gravitySign*recip_rhoConst
     &                  * sigmaR(i,j,k) * coordFac
```

---

### 2. KPP Density Gradient Formulation

**Key File:**
- `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_routines.F` (STATEKPP subroutine)

**Documentation (lines 1778-1782):**
```fortran
c      rho1   = potential density of surface layer                     (kg/m^3)
c      dbloc  = local buoyancy gradient at Nr interfaces
c               g/rho{k+1,k+1} * [ drho{k,k+1}-drho{k+1,k+1} ]          (m/s^2)
c      dbsfc  = buoyancy difference with respect to the surface
c               g * [ drho{1,k}/rho{1,k} - drho{k,k}/rho{k,k} ]         (m/s^2)
```

The notation `drho{i,j}` means: density of water with T(i), S(i) evaluated at pressure level j.

**Implementation (lines 1886-1900, 1930):**
```fortran
! RHOK = rho(T(k), S(k), P(k)) = in-situ density = drho{k,k}
CALL FIND_RHO_2D(
     I        1-OLx, sNx+OLx, 1-OLy, sNy+OLy, k,
     I        theta(1-OLx,1-OLy,k,bi,bj), salt(1-OLx,1-OLy,k,bi,bj),
     O        RHOK,
     I        k, bi, bj, myThid )

! RHOKM1 = rho(T(k-1), S(k-1), P(k)) = potential density = drho{k-1,k}
CALL FIND_RHO_2D(
     I        1-OLx, sNx+OLx, 1-OLy, sNy+OLy, k,
     I        theta(1-OLx,1-OLy,k-1,bi,bj),salt(1-OLx,1-OLy,k-1,bi,bj),
     O        RHOKM1,
     I        k-1, bi, bj, myThid )

DBLOC(i,j,k-1) = gravity * (RHOK(i,j) - RHOKM1(i,j)) /
     &                                    (RHOK(i,j) + rhoConst)
```

**Formula:**
```
DBLOC = g × [ρ(T(k), S(k), P(k)) - ρ(T(k-1), S(k-1), P(k))] / (ρ(k) + ρ₀)
```

This is also a **potential density gradient**.

---

## Python Port Implementation Analysis

### 1. Physics Basis Module

**File:** [physics_basis.py](../../../Vertical_Mixing_Models/main/physics_basis.py)

**Function:** `compute_buoyancy_frequency_squared` (lines 26-107)

**Documentation (lines 33-54):**
```python
"""
Compute squared buoyancy frequency (Brunt-Väisälä frequency squared).

N² = -(g/ρ₀) * ∂ρ/∂z   (z positive upward)

**Discretization**: Density gradient at interface k is:
∂ρ/∂z|_k ≈ (ρ_{k-1} - ρ_k) / (z_{k-1} - z_k)
matching two-point centered difference between cells.

**MITgcm correspondence**: Computed in GGL90_CALC.F and used throughout 
ggl90_mixinglength.F for mixing-length diagnosis. In KPP, equivalent 
information comes from compute_buoyancy_gradients().
"""
```

**Implementation (lines 100-106):**
```python
# Compute N² at each interface (k=1..nz-1)
for k in range(1, nz):
    # Density gradient (using two-point difference)
    drho_dz = (rho[k-1] - rho[k]) / (z[k-1] - z[k])
    # Brunt-Väisälä frequency squared with gravity factor
    n_square[k] = -(gravity / rho_0) * drho_dz
```

**Input:** `rho` array (no documentation of which pressure it's evaluated at)

---

### 2. EOS Module - KPP Path

**File:** [eos.py](../../../Vertical_Mixing_Models/main/eos.py)

**Function:** `compute_buoyancy_gradients` (lines 406-529)

This function correctly implements **potential density gradients** for KPP:

**Documentation (lines 472-499):**
```python
# ------------------------------------------------------------------
# Local buoyancy gradient dbloc and surface buoyancy difference dbsfc.
#
# This reproduces MITgcm statekpp (kpp_routines.F:1930-1933):
#     DBLOC(k-1) = g*(RHOK - RHOKM1)/(RHOK + rhoConst)
#     DBSFC(k)   = g*(RHOK - RHO1K )/(RHOK + rhoConst)
# where RHOK (deeper), RHOKM1 (shallower) and RHO1K (surface T/S) are ALL
# evaluated at a SINGLE reference pressure -- the pressure of the deeper
# level k (FIND_RHO_2D is called with the same kRef for all three). Using a
# common reference pressure removes the compressibility contribution, so the
# difference reflects only the adiabatic (potential) density contrast that
# actually drives buoyancy.
```

**Implementation (lines 503-513):**
```python
if use_jmd95:
    # dbloc[k]: interface between shallower cell k and deeper cell k+1.
    # Reference pressure = deeper cell's pressure. rho[k+1] is already that
    # cell at its own pressure; only the shallower cell must be re-evaluated
    # at the deeper reference pressure.
    pref_deep = pressure[1:nz]
    rho_shal_at_deep = (
        jmd95_eos(theta[:nz-1], salt[:nz-1], pref_deep, rho_const)[0] + rho_const
    )
    rho_deep = rho[1:nz]
    dbloc[:nz-1] = gravity * (rho_deep - rho_shal_at_deep) / rho_deep
```

✅ **This correctly implements potential density gradients for KPP**.

---

### 3. GGL90 Adapter - THE PROBLEM

**File:** [mixing_adapter.py](../../../Vertical_Mixing_Models/main/mixing_adapter.py)

**Lines 225-234:**
```python
from .eos import jmd95_eos

# Pressure in dbar ~ depth in meters (1 dbar per m of seawater);
# grid.depth is negative-downward, so pressure = -depth.
pressure = -grid.depth
rho, _, _ = jmd95_eos(state.theta, state.salt, pressure, self.rho_const)
rho_full = rho + self.rho_const
```

**This computes in-situ density at each level:**
- `pressure[k]` = pressure at level k
- `rho[k]` = ρ(T(k), S(k), P(k)) = in-situ density

**Then passes to GGL90 (lines 246-250):**
```python
ggl90_output = self.ggl90_driver.compute_mixing(
    tke=tke,
    u=state.u_vel,
    v=state.v_vel,
    rho=rho_full,  # <-- IN-SITU DENSITY
```

**Then in ggl90_core_driver.py (line 299):**
```python
n_square = compute_buoyancy_frequency_squared(rho, z, gravity)
```

This computes:
```
N² = -(g/ρ₀) × [ρ(T(k-1), S(k-1), P(k-1)) - ρ(T(k), S(k), P(k))] / Δz
```

❌ **This is an IN-SITU density gradient, NOT a potential density gradient**.

---

## The Difference

### In-Situ Density Gradient (Current GGL90 Port)
```
∂ρ/∂z = [ρ(T(k-1), S(k-1), P(k-1)) - ρ(T(k), S(k), P(k))] / Δz
```
This includes both:
1. Adiabatic density change (potential density)
2. Compressibility effects (pressure-dependent density change)

### Potential Density Gradient (MITgcm GGL90 and KPP)
```
∂ρ/∂z = [ρ(T(k-1), S(k-1), P(k)) - ρ(T(k), S(k), P(k))] / Δz
```
This isolates:
1. Only the adiabatic density change
2. Removes compressibility effects by evaluating at a common reference pressure

---

## Physical Significance

**Potential density gradients** are the physically correct quantity for assessing static stability because:

1. **Adiabatic Test**: When testing if a water parcel will sink or float, you must compare densities after adiabatic displacement to the same pressure level.

2. **Compressibility**: All seawater is compressible - deeper water is denser due to compression alone, even if it has the same T and S. This compression doesn't drive convection.

3. **Neutral Surfaces**: Potential density defines neutral surfaces - surfaces along which water parcels can move without buoyancy forces.

**Magnitude of the Error:**
- For shallow water (< 100 m): negligible difference
- For deep water (1000+ m): significant difference
- The in-situ gradient will **overestimate** stratification (makes water appear more stable than it really is)

---

## Recommendation

### Fix for GGL90 Adapter

Modify [mixing_adapter.py](../../../Vertical_Mixing_Models/main/mixing_adapter.py) to compute potential density gradients similar to the KPP path.

**Option 1: Use the same approach as `compute_buoyancy_gradients`**

Evaluate all densities at a common reference pressure (e.g., the deeper level's pressure).

**Option 2: Separate function for GGL90**

Create a function that mirrors MITgcm's `grad_sigma.F` logic:
```python
def compute_potential_density_for_ggl90(theta, salt, depth, rho_const):
    """
    Compute potential density for GGL90 stratification calculation.
    
    Mimics MITgcm's sigmaR calculation where each interface k uses:
    - rho(k) at P(k) [in-situ]
    - rho(k-1) at P(k) [potential]
    """
    nz = len(theta)
    pressure = -depth
    
    # In-situ densities
    rho_insitu, _, _ = jmd95_eos(theta, salt, pressure, rho_const)
    rho = rho_insitu + rho_const
    
    # For interface k (between k-1 and k), compute potential density
    # This is equivalent to MITgcm's sigmaR formulation
    return rho  # Needs modification to include potential density re-evaluation
```

---

## Verification Needed

After implementing the fix:

1. **Unit Test**: Compare N² values from the port against MITgcm outputs for the same T/S/P profiles
2. **Deep Water Test**: Run scenarios with depths > 1000m where compressibility matters
3. **Stratification Test**: Verify that a uniformly stratified column (constant ∂θ/∂z, ∂S/∂z) produces consistent N² values

---

## References

### MITgcm Source Files
- `pkg/ggl90/ggl90_calc.F` - GGL90 N² calculation
- `model/src/grad_sigma.F` - Potential density gradient calculation
- `model/src/do_oceanic_phys.F` - Density evaluation strategy
- `pkg/kpp/kpp_routines.F` - KPP STATEKPP subroutine

### Port Files
- `Vertical_Mixing_Models/main/physics_basis.py` - Shared physics functions
- `Vertical_Mixing_Models/main/eos.py` - Equation of state and buoyancy gradients
- `Vertical_Mixing_Models/main/mixing_adapter.py` - GGL90 adapter (needs fix)
- `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py` - GGL90 driver

---

**Analysis completed by**: Claude Code (Architect Agent)  
**Analysis date**: 2026-07-20
