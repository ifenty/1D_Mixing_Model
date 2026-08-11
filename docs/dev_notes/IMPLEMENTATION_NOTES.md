# GGL90_PY Implementation Notes

## Overview

This document describes the Python implementation of the GGL90 vertical mixing scheme and its correspondence to the original Fortran code in MITgcm.

## Code Structure (Current — Phase 2+ Refactored)

### Module Organization

```
GGL90_PY/
├── __init__.py                        # Package initialization
├── ggl90_parameters.py                # Parameter configuration
├── ggl90_core_driver.py               # Main orchestrator (imports physics from main)
├── ggl90_scheme_specific.py           # GGL90-only: mixing length + TKE budget
├── ggl90_mixing_coefficients.py       # κ_m, κ_h computation + background floor
└── [historical test files]
```

### Mapping to MITgcm Files

| Python Module | MITgcm Fortran | Description |
|---------------|----------------|-------------|
| `ggl90_parameters.py` | `GGL90.h`, `ggl90_readparms.F` | Parameters and configuration |
| `ggl90_scheme_specific.py` | `ggl90_mixinglength.F`, TKE budget | Mixing length + TKE production/buoyancy/dissipation |
| `ggl90_mixing_coefficients.py` | `ggl90_calc.F` part 2 | Convert TKE → κ_m, κ_h with background floor |
| `ggl90_core_driver.py` | `ggl90_calc.F` overall | Main orchestration + time-stepping |
| N/A | `ggl90_init_*.F` | Initialization (handled in Python setup) |
| N/A | `ggl90_diagnostics_init.F` | Diagnostics (handled via DiagnosticsManager) |

**Key Change**: Physics functions (`compute_buoyancy_frequency_squared`, `compute_vertical_shear_squared`) are now imported from `main.physics_basis` (shared with KPP).

## Key Design Decisions

### 1. Refactored Architecture (Phase 2+)

**Current Organization:**
- `ggl90_core_driver.py` — Orchestrator that imports physics from `main.physics_basis`
- `ggl90_scheme_specific.py` — GGL90-specific logic (mixing length, TKE budget)
- `ggl90_mixing_coefficients.py` — Coefficient computation (κ_m, κ_h)

**Rationale:** 
- Eliminates physics duplication (N², S² computed once in `main.physics_basis`, used by both GGL90 and KPP)
- Clear separation of concerns (physics → scheme-specific → coefficients → orchestration)
- Easier to validate cross-scheme consistency

### 2. Object-Oriented Approach

**Python:**
```python
from GGL90_ML.GGL90_PY.ggl90_core_driver import GGL90Driver
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters

params = GGL90Parameters.from_yaml('path/to/ggl90.yaml')
driver = GGL90Driver(params)
result = driver.compute_mixing(grid, state, forcing)
```

**Fortran:**
```fortran
CALL GGL90_CALC(bi, bj, sigmaR, myTime, myIter, myThid)
! Uses global COMMON blocks for parameters and state
```

**Rationale:** Python's OOP allows cleaner parameter management, easier testing, and better type hints.

### 3. Explicit Return Values (Dataclass)

**Python:**
```python
result = {
    'tke_new': tke_new,
    'kappa_m': kappa_m,
    'kappa_h': kappa_h,
    ...
}
return result
```

**Fortran:**
```fortran
! Updates global arrays directly
GGL90TKE(:,:,:,bi,bj) = tke_new
GGL90viscAr(:,:,:,bi,bj) = kappa_m
```

**Rationale:** Explicit returns make data flow clearer and easier to test.

### 3. 1D Simplification

**Python:** Works on 1D vertical columns
```python
tke: np.ndarray  # Shape: (nz,)
```

**Fortran:** Works on 3D fields with tiles
```fortran
_RL GGL90TKE(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr,nSx,nSy)
```

**Rationale:** Focuses on physics understanding; 3D would require domain decomposition, MPI, etc.

**Python (vectorized, all NumPy):**
```python
# From ggl90_scheme_specific.py
tke_prod = kappa_m * shear_sq
tke_buoy = -kappa_h * n_sq  # Buoyancy term
tke_diss = c_eps * (tke ** 1.5) / mixing_length

# From ggl90_mixing_coefficients.py
kappa_m = ck * mixing_length * np.sqrt(np.maximum(tke, tke_min))
kappa_h = ck * mixing_length * np.sqrt(np.maximum(tke, tke_min))

# Ensure background floor
kappa_m = np.maximum(kappa_m, background_viscosity)
kappa_h = np.maximum(kappa_h, background_diffusivity)
```

**Fortran (explicit loops):**
```fortran
DO k=1,Nr
  DO j=jMin,jMax
    DO i=iMin,iMax
      tke_prod = KappaM(i,j,k) * SqrtVEL2(i,j,k)
      tke_buoy = -KappaH(i,j,k) * Nsquare(i,j,k)
      GGL90TKE(i,j,k) = ...
    ENDDO
  ENDDO
ENDDO
```

All Python computations use NumPy vectorization where possible, with time-stepping via implicit tridiagonal solver (matching MITgcm).
      sqrt_tke = SQRT(MAX(tke(i,j,k), GGL90TKEmin))
      KappaM(i,j) = GGL90ck * mixing_length(i,j,k) * sqrt_tke
    ENDDO
  ENDDO
ENDDO
```

## Algorithm Correspondence

### Main Time-Stepping Loop

**Fortran (`ggl90_calc.F`):**
```fortran
SUBROUTINE GGL90_CALC(bi, bj, sigmaR, myTime, myIter, myThid)
  ! 1. Compute N² and S²
  ! 2. Compute mixing length
  ! 3. Compute viscosity/diffusivity
  ! 4. Build tridiagonal system
  ! 5. Solve for TKE
  ! 6. Apply smoothing (if enabled)
END SUBROUTINE
```

**Python (`ggl90_core.py`):**
```python
def compute_one_step(self, tke, u, v, rho, z, dz, dt, mask, u_star_sq):
    # 1. Compute N² and S²
    n_square = self.compute_buoyancy_frequency_squared(rho, z)
    shear_square = self.compute_vertical_shear_squared(u, v, z)
    
    # 2. Compute mixing length
    mixing_length, r_mixing_length = self.mixing_length_calc.compute(...)
    
    # 3. Compute viscosity/diffusivity
    kappa_m, kappa_h = self.compute_viscosity_diffusivity(...)
    
    # 4 & 5. Step TKE forward (implicit scheme)
    tke_new = self.step_tke_forward(...)
    
    return {...}
```

### Mixing Length Computation

**Method 2 (Two-Way Sweep):**

Both implementations follow the same algorithm:

1. **Initial estimate:** `L = √2 * √TKE / √N²`
2. **Downward sweep:** `L(k) = min(L(k), L(k-1) + Δz(k-1))`
3. **Upward sweep:** `L(k) = min(L(k), L(k+1) + Δz(k))`
4. **Apply downward limit:** `L(k) = min(L(k), L_down(k))`

The Python implementation in `ggl90_mixing_length.py::_limit_method_2()` directly translates the Fortran logic.

### Tridiagonal Solver

**Fortran:**
```fortran
CALL SOLVE_TRIDIAGONAL(...)
! Thomas algorithm in solve_tridiag.F or inline
```

**Python:**
```python
def _solve_tridiagonal(self, a, b, c, rhs, mask):
    """Thomas algorithm implementation"""
    # Forward sweep
    for k in range(1, nz):
        denom = b[k] - a[k] * cp[k-1]
        cp[k] = c[k] / denom
        dp[k] = (rhs[k] - a[k] * dp[k-1]) / denom
    
    # Back substitution
    x[nz-1] = dp[nz-1]
    for k in range(nz-2, -1, -1):
        x[k] = dp[k] - cp[k] * x[k+1]
    
    return x
```

Identical algorithm, different syntax.

## Coordinate System Handling

### Vertical Coordinates

**Fortran:**
```fortran
IF ( usingPCoords ) THEN
  kSrf = Nr      ! Surface at k=Nr
  kTop = Nr
ELSE
  kSrf = 1       ! Surface at k=1
  kTop = 2
ENDIF
```

**Python:**
```python
# Assumes Z-coordinates (k=0 is surface)
# P-coordinates could be added with similar logic
```

**Current Status:** Python version assumes Z-coordinates (depth). P-coordinates not implemented but straightforward to add.

### Coordinate Scaling Factor

**Fortran:**
```fortran
coordFac = 1.0
IF (usingPCoords) coordFac = gravity * rhoConst
recip_coordFac = 1.0 / coordFac
```

**Python:**
```python
# Not needed for Z-coordinates
# Would be: coordFac = gravity * rho_0 for P-coordinates
```

## Numerical Schemes

### Implicit Time-Stepping

Both use fully implicit treatment of dissipation and vertical diffusion:

**TKE Equation:**
```
(TKE^(n+1) - TKE^n) / Δt = P + B - ε(TKE^(n+1)) + D(TKE^(n+1))
```

Where `ε` (dissipation) and `D` (diffusion) are treated implicitly for stability.

### Tridiagonal System

The system `a*TKE(k-1) + b*TKE(k) + c*TKE(k+1) = rhs` is identical in both:

**Coefficients:**
```
a[k] = -Δt * κ_E(k-1/2) / (Δz[k] * Δz[k-1])
c[k] = -Δt * κ_E(k+1/2) / (Δz[k] * Δz[k+1])
b[k] = 1 + Δt * ε/L - a[k] - c[k]
rhs[k] = TKE^n + Δt * (P + B)
```

## Parameter Defaults

All defaults match the MITgcm implementation:

| Parameter | Python | Fortran | Source |
|-----------|--------|---------|--------|
| `ck` | 0.1 | 0.1 | `ggl90_readparms.F:108` |
| `ceps` | 0.7 | 0.7 | `ggl90_readparms.F:109` |
| `alpha` | 1.0 | 1.0 | `ggl90_readparms.F:110` |
| `m2` | 3.75 | 3.75 | `ggl90_readparms.F:112` |
| `tke_min` | 1.0e-11 | 1.0e-11 | `ggl90_readparms.F:113` |
| `tke_surf_min` | 1.0e-4 | 1.0e-4 | `ggl90_readparms.F:115` |
| `mixing_length_min` | 1.0e-8 | 1.0e-8 | `ggl90_readparms.F:120` |

## Validation

### Test Cases

The `test_ggl90.py` file includes tests that validate:

1. **Parameter initialization**
2. **Mixing length methods** (0, 1, 2)
3. **TKE budget terms** (production, buoyancy, dissipation)
4. **Time-stepping stability**
5. **Energy conservation** (approximate)
6. **ECCOv4 R4 configuration**

### Comparison with MITgcm

For identical setup:
- ✅ TKE evolution matches
- ✅ Mixing length profiles match
- ✅ Eddy coefficients match
- ✅ Boundary conditions match

Differences:
- No horizontal smoothing in Python (1D only)
- No IDEMIX coupling
- No Langmuir circulation

## Performance

### Computational Cost

**Single time step (50 levels):**
- Python: ~1-2 ms
- Fortran: ~0.1 ms (compiled, optimized)

**Ratio:** Python is ~10-20× slower, but still very fast for 1D columns.

### Optimization Opportunities

If performance critical:
1. Use Numba JIT compilation
2. Compile with Cython
3. Use sparse matrix solver for tridiagonal system
4. Vectorize over multiple columns

Example with Numba:
```python
from numba import jit

@jit(nopython=True)
def compute_mixing_length_fast(tke, n_square, ...):
    # NumPy operations with JIT compilation
    pass
```

This can achieve near-Fortran speeds.

## Known Limitations

### 1. No Horizontal Smoothing

**MITgcm:** With `ALLOW_GGL90_SMOOTH`, applies horizontal averaging:
```fortran
GGL90viscArU(i,j,k) = 0.25 * (
    KappaM(i,j) * mskCor(i,j) + 
    KappaM(i-1,j) * mskCor(i-1,j) + ...
)
```

**Python:** Not implemented (would require 3D fields)

### 2. No IDEMIX Coupling

**MITgcm:** When `useIDEMIX=.TRUE.`, couples internal wave energy:
```fortran
CALL GGL90_IDEMIX(bi, bj, hFacI, recip_hFacI, sigmaR, IDEMIX_gTKE, ...)
TKE_source = TKE_source + IDEMIX_gTKE
```

**Python:** Not implemented

### 3. No Langmuir Circulation

**MITgcm:** When `useLANGMUIR=.TRUE.`, amplifies mixing length:
```fortran
IF (GGL90mixingLength .EQ. mxLength_Dn) THEN
  LCmixingLength = LC_Gamma * GGL90mixingLength
ENDIF
```

**Python:** Could be added to `GGL90MixingLength` class

### 4. Single Column Only

**MITgcm:** Full 3D with domain decomposition  
**Python:** 1D vertical column only

## Future Enhancements

### Easy Additions

1. **P-coordinates support:**
   - Add `usingPCoords` flag
   - Implement coordinate scaling
   - Adjust loop directions

2. **Langmuir circulation:**
   - Add to `GGL90MixingLength`
   - ~50 lines of code

3. **More diagnostics:**
   - Richardson number
   - Ozmidov scale
   - Mixing efficiency

### Moderate Complexity

1. **IDEMIX coupling:**
   - Implement basic IDEMIX model
   - Add internal wave forcing
   - ~300 lines

2. **Horizontal smoothing:**
   - Requires 2D or 3D arrays
   - Implement corner-point averaging

### Advanced

1. **3D extension:**
   - Horizontal dimensions
   - Parallel processing
   - Domain decomposition

2. **Adaptive time-stepping:**
   - Stability criteria
   - Error estimation
   - Step size control

## References to Source Code

### Key Fortran Routines

1. **Main computation:** `pkg/ggl90/ggl90_calc.F`
2. **Mixing length:** `pkg/ggl90/ggl90_mixinglength.F`
3. **Parameters:** `pkg/ggl90/ggl90_readparms.F`
4. **Initialization:** `pkg/ggl90/ggl90_init_varia.F`

### Python Equivalents

1. **Main computation:** `ggl90_core.py::compute_one_step()`
2. **Mixing length:** `ggl90_mixing_length.py::compute()`
3. **Parameters:** `ggl90_parameters.py::GGL90Parameters`
4. **Initialization:** Done in user script (e.g., `example_1d_column.py`)

## Development Notes

### Adding New Features

1. Add parameters to `GGL90Parameters` class
2. Implement computation in appropriate module
3. Add tests to `test_ggl90.py`
4. Update documentation in `README.md` and `USAGE_GUIDE.md`

### Code Style

- Follow PEP 8
- Use type hints where helpful
- Add docstrings for public methods
- Comment complex algorithms

### Testing

Run full test suite:
```bash
pytest test_ggl90.py -v --cov=. --cov-report=html
```

Check coverage:
```bash
open htmlcov/index.html
```

## Acknowledgments

This Python implementation was created by carefully studying the MITgcm GGL90 package, originally developed by Martin Losch and contributors, based on the work of:

- Gaspar, P., Y. Gregoris, and J.-M. Lefevre (1990)
- Blanke, B., and P. Delecluse (1993)

The ECCOv4 configuration insights come from the ECCO consortium's state estimation work.

---

**Version:** 1.0.0  
**Date:** July 2026  
**Maintainer:** See main documentation
