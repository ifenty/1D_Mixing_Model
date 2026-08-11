# KPP Physics Explanation

## Understanding KPP Output: Common Questions

### Q1: Why is the nonlocal transport (ghat) zero?

**Answer**: Nonlocal transport is only active during **unstable stratification** (convection).

#### The Physics

The nonlocal transport coefficient `γ` (ghat) represents counter-gradient flux during convection. It's controlled by:

```python
ghat = (1 - stable) * c_g / (w_s * h_bl)
```

Where:
- `stable = 1` when `bfsfc > 0` (stable stratification) → `ghat = 0`
- `stable = 0` when `bfsfc < 0` (unstable stratification) → `ghat > 0`

#### Surface Buoyancy Forcing (bfsfc)

The sign of `bfsfc` determines stability:

```
bfsfc = -g * (α * Q_net / (ρ * c_p) + β * (E-P-R) * S_surf) + absorbed_shortwave
```

Where:
- `α` = thermal expansion coefficient (positive)
- `β` = haline contraction coefficient (positive)
- `Q_net` = net heat flux (positive = into ocean = warming)
- `E-P-R` = freshwater flux (positive = into ocean = freshening)

**Unstable (bfsfc < 0)**: Cooling or freshening at surface
- Surface water becomes denser
- Sinks (convection)
- Nonlocal transport active

**Stable (bfsfc > 0)**: Heating or evaporation at surface
- Surface water becomes lighter
- Floats (no convection)
- Nonlocal transport OFF

#### Example Scenarios

**Scenario 1: Net Cooling (ghat > 0)**
```python
q_net = -150 W/m²  # Strong cooling
q_sw = 100 W/m²    # Moderate shortwave
# Net effect: cooling dominates → bfsfc < 0 → UNSTABLE → ghat > 0
```

**Scenario 2: Net Heating (ghat = 0)**
```python
q_net = -50 W/m²   # Weak cooling
q_sw = 200 W/m²    # Strong shortwave
# Net effect: heating dominates → bfsfc > 0 → STABLE → ghat = 0
```

**Scenario 3: Winter Cooling (ghat > 0)**
```python
q_net = -200 W/m²  # Strong cooling (winter night)
q_sw = 50 W/m²     # Weak shortwave (winter day)
# → Deep convection with strong nonlocal transport
```

---

### Q2: Why is hbl so deep (reaching bottom)?

**Answer**: The bulk Richardson criterion is never satisfied, causing `hbl` to extend to the domain bottom.

#### The Physics

The boundary layer depth `hbl` is diagnosed where:

```
Ri_bulk = (z_ref - z) * Δb / (ΔV² + V_t²) = Ricr
```

Where:
- `Ricr = 0.3` (critical Richardson number)
- `Δb` = buoyancy difference from surface
- `ΔV²` = velocity shear squared from surface
- `V_t²` = turbulent velocity contribution

**If `Ri_bulk < Ricr` everywhere**: hbl extends to bottom

#### Common Causes

**1. Weak Stratification**

If temperature/salinity gradients are too weak:
- `Δb` is small
- `Ri_bulk` stays small
- Never exceeds `Ricr`

**Fix**: Use stronger stratification:
```python
# Weak (bad): shallow e-folding scale
theta = 20.0 - 15.0 * (1.0 - np.exp(depth / 500.0))  # Too gradual

# Strong (good): steep e-folding scale  
theta = 20.0 - 15.0 * (1.0 - np.exp(depth / 150.0))  # Steeper thermocline
```

**2. Strong Forcing**

If wind stress or cooling is too strong:
- Turbulence penetrates deeply
- `V_t²` term is large
- `Ri_bulk` stays small

**Fix**: Use moderate forcing:
```python
# Too strong
tau_x = 0.5  # Unrealistic hurricane-force winds

# Reasonable
tau_x = 0.1  # Typical moderate winds
```

**3. Uniform Initial Conditions**

If ocean is too homogeneous:
- No density gradient to resist mixing
- Mixing extends everywhere

**Fix**: Add realistic structure:
```python
# Bad: uniform
theta = np.full(nz, 20.0)

# Good: stratified
theta = 20.0 - 15.0 * (1.0 - np.exp(depth / 150.0))
salt = 35.0 + 1.0 * (1.0 - np.exp(depth / 200.0))
```

#### Realistic hbl Values

- **Summer, weak winds**: hbl ~ 10-30 m
- **Spring/fall, moderate winds**: hbl ~ 30-100 m  
- **Winter, strong winds + cooling**: hbl ~ 100-500 m
- **Deep convection (polar regions)**: hbl ~ 500-2000 m
- **Reaches bottom**: Usually indicates problem (unless shallow seas)

---

### Q3: What controls the magnitude of mixing coefficients?

#### Boundary Layer Mixing

Inside the boundary layer (z > -hbl):

```
K(z) = h_bl * w * σ * (1 + σ * G(σ))
```

Where:
- `w` = turbulent velocity scale ~ `u_*` (friction velocity)
- `σ = -z / h_bl` = normalized depth (0 at surface, 1 at hbl)
- `G(σ)` = shape function (cubic polynomial)

**Typical values**:
- Surface (σ=0): K ~ 0 (zero-flux boundary condition)
- Mid-BL (σ=0.5): K ~ 0.01-0.1 m²/s
- Base of BL (σ=1): K ~ matching to interior

**Controls**:
1. **Wind stress** → larger `u_*` → larger `w` → larger K
2. **Convection** → negative `bfsfc` → larger `w` → larger K
3. **Boundary layer depth** → larger `h_bl` → larger K

#### Interior Mixing

Below the boundary layer (z < -hbl):

```
K_interior = K_background + K_shear + K_convection
```

Where:
- `K_background` ~ 1e-5 m²/s (internal waves)
- `K_shear` = function of Richardson number
- `K_convection` = active when local Ri < 0

**Typical values**:
- Stable, low shear: K ~ 1e-5 m²/s (background only)
- Moderate shear: K ~ 1e-4 to 1e-3 m²/s
- Strong shear or convection: K ~ 1e-3 to 1e-2 m²/s

---

## Diagnostic Plots Explained

### Row 1: Ocean Structure

**Temperature**: Should show surface warm layer with thermocline

**Salinity**: May show halocline (usually less pronounced than thermocline)

**Velocity**: Should decay with depth (Ekman spiral)

**Density**: Combines T and S effects; controls stratification

### Row 2: Mixing Coefficients

**Viscosity**: Momentum mixing (velocity)

**Diffusivity**: Scalar mixing (T, S)
- Usually similar to viscosity
- Can differ due to different Prandtl numbers

**Nonlocal Transport (γ)**:
- Zero in stable conditions
- Non-zero in unstable conditions (convection)
- Located within boundary layer only

**Bulk Richardson Number**:
- Shows where Ri = Ricr (0.3)
- Determines hbl
- Should cross Ricr somewhere above bottom

### Row 3: Diagnostics

**Surface Forcing**:
- Lists all forcing terms
- Check if Q_total is positive (heating) or negative (cooling)
- Wind stress magnitude determines mechanical forcing

**Velocity Shear**:
- Higher near surface
- Controls shear instability
- Should decay with depth

**Buoyancy Frequency (N)**:
- Shows stratification strength
- High N → strong stratification → shallow hbl
- Low N → weak stratification → deep hbl

**Summary**:
- Quick reference of key output
- Stability indicator
- Maximum mixing values

---

## Troubleshooting Guide

### Problem: ghat is always zero

**Check**:
1. Is `q_net + q_sw` positive (net heating)?
   - **Fix**: Increase cooling or reduce shortwave
2. Is `use_ghat = True` in config?
   - **Fix**: Check configuration file

**Example fix**:
```python
column = create_test_column(scenario='unstable_convection')
# This sets q_net = -150, q_sw = 100 → net cooling
```

### Problem: hbl reaches bottom

**Check**:
1. Is stratification too weak?
   - **Fix**: Use steeper temperature/salinity gradients
2. Is forcing too strong?
   - **Fix**: Reduce wind stress or heat flux
3. Print bulk Richardson number to diagnose

**Example fix**:
```python
# Steeper thermocline (stronger stratification)
theta = 20.0 - 15.0 * (1.0 - np.exp(depth / 150.0))  # Was 500.0
salt = 35.0 + 1.0 * (1.0 - np.exp(depth / 200.0))    # Was 0.5
```

### Problem: Mixing coefficients too large/small

**Check**:
1. What is `u_*` (friction velocity)?
   - Typical: 0.005-0.02 m/s
   - If >> 0.1 m/s: wind stress too strong
2. What is `h_bl`?
   - K scales with h_bl
3. Is output in correct units?
   - Should be m²/s, not cm²/s

---

## Physical Intuition

### The KPP Model Philosophy

1. **Boundary Layer**: Region of active turbulence driven by surface forcing
   - Wind stress provides mechanical energy
   - Buoyancy flux adds/removes potential energy
   - Mixing is strong and determined by surface forcing

2. **Interior**: Region below BL with weaker turbulence
   - Background internal wave breaking
   - Shear instability (Ri-dependent)
   - Double diffusion (if T/S compensating)

3. **Nonlocal Transport**: Large convective eddies during cooling
   - Carries properties from surface to depth
   - Counter-gradient flux (against mean gradient)
   - Important for deep winter mixing

### Real Ocean Scenarios

**Summer**:
- Net heating (bfsfc > 0) → stable
- Shallow mixed layer (10-50m)
- ghat = 0
- Light winds → small K

**Winter**:
- Net cooling (bfsfc < 0) → unstable  
- Deep mixed layer (100-500m)
- ghat > 0 (active convection)
- Strong winds → large K

**Polar Regions**:
- Extreme cooling
- Sea ice formation (brine rejection)
- Very deep convection (>1000m)
- Forms deep water masses

---

## References

1. Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing: A review and a model with a nonlocal boundary layer parameterization. *Reviews of Geophysics*, 32(4), 363-403.

2. MITgcm KPP Documentation: https://mitgcm.readthedocs.io/en/latest/phys_pkgs/kpp.html
