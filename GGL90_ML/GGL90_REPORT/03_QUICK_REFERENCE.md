# GGL90 Quick Reference Guide

One-page reference for GGL90 vertical mixing in MITgcm.

---

## Core Equations

```
∂TKE/∂t = KappaM·S² - KappaH·N² - ε·TKE^(3/2)/L + ∂/∂z(KappaE·∂TKE/∂z)

KappaM = c_k · L · √TKE              Viscosity (m²/s)
KappaH = KappaM / α                  Diffusivity (m²/s)
L = √2 · √TKE / √N²                  Mixing length (m)
ε = c_eps · TKE^(3/2) / L            Dissipation (m²/s³)
```

---

## Key Parameters (ECCOv4 R4 vs. Default)

| Parameter | Default | ECCOv4 R4 | Units | Effect |
|-----------|---------|-----------|-------|--------|
| **GGL90alpha** | 1.0 | **30.0** | - | KappaM/KappaH ratio |
| **GGL90TKEmin** | 1.0e-11 | **1.0e-7** | m²/s² | Minimum TKE |
| **GGL90TKEbottom** | 1.0e-11 | **1.0e-6** | m²/s² | Bottom TKE |
| **mxlMaxFlag** | 0 | **2** | - | Mixing length method |
| **mxlSurfFlag** | F | **T** | - | Force surface mixing |
| GGL90ck | 0.1 | 0.1 | - | Viscosity constant |
| GGL90ceps | 0.7 | 0.7 | - | Dissipation constant |
| GGL90m2 | 3.75 | 3.75 | - | Wind stress coefficient |
| GGL90TKEsurfMin | 1.0e-4 | 1.0e-4 | m²/s² | Min surface TKE |

---

## CPP Flags (ECCOv4 R4)

```fortran
#define ALLOW_GGL90                  ✅ Enable package
#define ALLOW_GGL90_SMOOTH           ✅ Spatial smoothing (OPA style)
#undef  ALLOW_GGL90_HORIZDIFF        ❌ Horizontal TKE diffusion
#undef  ALLOW_GGL90_IDEMIX           ❌ Internal wave model
#undef  ALLOW_GGL90_LANGMUIR         ❌ Langmuir circulation
#undef  GGL90_REGULARIZE_MIXINGLENGTH ❌ Adjoint-friendly L
```

---

## data.ggl90 Namelist (ECCOv4 R4)

```fortran
&GGL90_PARM01
  GGL90alpha = 30.,
  GGL90TKEmin = 1.e-7,
  GGL90TKEbottom = 1.e-6,
  mxlMaxFlag = 2,
  mxlSurfFlag = .TRUE.,
/
```

---

## Mixing Length Methods (mxlMaxFlag)

### 0: Simple Depth Limit
```
L(k) = min(L(k), total_depth)
```

### 1: Distance to Boundaries
```
L(k) = min(L(k), min(dist_to_surface, dist_to_bottom))
```

### 2: Two-Way Sweep (ECCOv4 R4) ⭐
```
Downward: L(k) = min(L(k), L(k-1) + Δz(k-1))
Upward:   L(k) = min(L(k), L(k+1) + Δz(k))
Final:    L(k) = min(L_down(k), L_up(k))
```

### 3: Geometric Mean
```
L(k) = √[L_up(k) · L_down(k)]
```

---

## Boundary Conditions

**Surface (Dirichlet):**
```
TKE(kTop) = max(m2 · u_star², TKE_surfMin)
u_star² = √(τ_x² + τ_y²) / ρ₀
```

**Bottom:**
- **Dirichlet (default):** `TKE(bottom) = TKE_bottom`
- **Neumann:** `∂TKE/∂z = 0`

---

## File Structure

| File | Lines | Purpose |
|------|-------|---------|
| ggl90_calc.F | 1177 | Main computation |
| ggl90_mixinglength.F | 421 | Mixing length limits |
| ggl90_readparms.F | 451 | Read parameters |
| ggl90_idemix.F | 598 | Internal waves (optional) |
| GGL90.h | 178 | Common blocks |
| GGL90_OPTIONS.h | 42 | CPP flags |

---

## Diagnostics

| Code | Description | Units |
|------|-------------|-------|
| GGL90TKE | Turbulent Kinetic Energy | m²/s² |
| GGL90ArU | Eddy viscosity (U-points) | m²/s |
| GGL90ArV | Eddy viscosity (V-points) | m²/s |
| GGL90Kr | Eddy diffusivity | m²/s |
| GGL90Lmx | Mixing length | m |
| GGL90Prd | TKE production | m²/s³ |
| GGL90Dsp | TKE dissipation | m²/s³ |
| GGL90N2 | Buoyancy frequency² | s⁻² |
| GGL90S2 | Vertical shear² | s⁻² |

---

## Common Tuning Scenarios

### Deeper Mixed Layer Needed
```fortran
GGL90alpha = 20.     ! Reduce from 30
mxlSurfFlag = .TRUE. ! Ensure enabled
```

### Shallower Mixed Layer Needed
```fortran
GGL90alpha = 40.     ! Increase from 30
```

### More Interior Mixing
```fortran
GGL90TKEmin = 1.e-6  ! Increase from 1.e-7
```

### Less Interior Mixing
```fortran
GGL90TKEmin = 1.e-8  ! Decrease from 1.e-7
```

### Enhanced Bottom Mixing
```fortran
GGL90TKEbottom = 1.e-5  ! Increase from 1.e-6
```

### Grid-Scale Noise Issues
```fortran
#define ALLOW_GGL90_SMOOTH  ! In GGL90_OPTIONS.h
mxlMaxFlag = 2              ! In data.ggl90
```

### Adjoint Instability
```fortran
mxlMaxFlag = 0 or 1         ! Simpler methods
adMxlMaxFlag = 0            ! Override in AD mode
```

---

## Compatibility

### ✅ Works With:
- SEAICE
- SHELFICE
- GMREDI
- LAYERS
- Adjoint (with appropriate settings)

### ❌ Incompatible With:
- KPP (K-Profile Parameterization)
- PP81 (Pacanowski-Philander)
- MY82 (Mellor-Yamada)

### ⚠️ Requires:
```fortran
implicitDiffusion = .TRUE.
implicitViscosity = .TRUE.
```

---

## Typical Values

### Surface Mixed Layer
```
TKE:     1e-4 to 1e-2 m²/s²
KappaM:  1e-3 to 1e-1 m²/s
KappaH:  3e-5 to 3e-3 m²/s (α=30)
L:       10 to 100 m
```

### Thermocline
```
TKE:     1e-7 to 1e-5 m²/s²
KappaM:  1e-5 to 1e-4 m²/s
KappaH:  3e-7 to 3e-6 m²/s (α=30)
L:       1 to 50 m
```

### Deep Ocean
```
TKE:     1e-7 m²/s² (= TKE_min)
KappaM:  3e-6 m²/s
KappaH:  1e-7 m²/s (α=30)
L:       1e-8 m (= L_min)
```

---

## Troubleshooting

### Problem: MLD Too Deep
**Solutions:**
- Increase `GGL90alpha` (try 40-50)
- Check wind forcing (may be too strong)
- Verify surface heat flux

### Problem: MLD Too Shallow
**Solutions:**
- Decrease `GGL90alpha` (try 10-20)
- Enable `mxlSurfFlag`
- Check surface boundary condition

### Problem: Weak Thermocline
**Solutions:**
- Increase `GGL90alpha` (30-50)
- Reduce `GGL90TKEmin` (try 1e-8)
- Check vertical resolution

### Problem: Model Crashes
**Solutions:**
- Check `implicitDiffusion = .TRUE.`
- Check `implicitViscosity = .TRUE.`
- Increase `GGL90TKEmin` (try 1e-6)
- Disable conflicting packages (KPP, PP81, MY82)

### Problem: Grid-Scale Noise
**Solutions:**
- Enable `ALLOW_GGL90_SMOOTH`
- Use `mxlMaxFlag = 2`
- Check resolution (may be too coarse)

### Problem: Adjoint Issues
**Solutions:**
- Use `mxlMaxFlag = 0 or 1`
- Set `adMxlMaxFlag = 0`
- Enable `ALLOW_GGL90_SMOOTH`
- Consider `GGL90_REGULARIZE_MIXINGLENGTH`

---

## Quick Start: Enabling GGL90

### 1. code/packages.conf
```
ggl90
```

### 2. code/GGL90_OPTIONS.h
```fortran
#define ALLOW_GGL90_SMOOTH
```

### 3. input/data
```fortran
&PARM01
  implicitDiffusion = .TRUE.,
  implicitViscosity = .TRUE.,
/

&PARM04
  useGGL90 = .TRUE.,
/
```

### 4. input/data.ggl90
```fortran
&GGL90_PARM01
  GGL90alpha = 30.,
  GGL90TKEmin = 1.e-7,
  GGL90TKEbottom = 1.e-6,
  mxlMaxFlag = 2,
  mxlSurfFlag = .TRUE.,
/
```

### 5. Compile and Run
```bash
cd build
../../../tools/genmake2 -mods=../code -optfile=../../../tools/build_options/[your_optfile]
make depend
make
cd ../run
ln -s ../build/mitgcmuv .
./mitgcmuv > output.txt
```

---

## References

**Primary:**
- Gaspar et al. (1990), JGR, 95(C9), pp. 16,179-16,193
- Blanke & Delecluse (1993), JPO, 23, pp. 1363-1388

**IDEMIX:**
- Olbers & Eden (2013), JPO, doi:10.1175/JPO-D-12-0207.1

**Langmuir:**
- Tak, Song et al. (2022), Ocean Modelling, doi:10.1016/j.ocemod.2021.101942

**ECCOv4:**
- Forget et al. (2015), GMD, 8, pp. 3071-3104

---

## Contact / More Information

- **MITgcm Documentation:** https://mitgcm.readthedocs.io/
- **MITgcm Repository:** https://github.com/MITgcm/MITgcm
- **ECCOv4 Website:** https://ecco-group.org/
- **Support:** mitgcm-support@mitgcm.org

---

**End of Quick Reference**
