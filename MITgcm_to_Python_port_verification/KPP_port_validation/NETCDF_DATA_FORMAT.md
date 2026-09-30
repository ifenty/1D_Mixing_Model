# KPP Port Validation NetCDF Data Format

**Version**: 1.1  
**Date**: 2026-08-20  
**Format**: CF-1.8 compliant NetCDF4 with compression  
**Provenance**: UUID-based tracking linking outputs to inputs

---

## Overview

This document specifies the NetCDF file format for KPP validation datasets used to verify the Python port against MITgcm's Fortran implementation.

**Purpose**: Reference datasets from MITgcm KPP implementation for validating the Python port

**Key Features**:
- Self-documenting with CF-1.8 metadata
- UUID-based provenance tracking
- Split architecture (separate input/output files)
- Comprehensive diagnostics (mixing + stability metrics)
- Double-precision (64-bit) floating-point data
- Compressed storage (NetCDF4 with zlib)

---

## Directory Structure

```
KPP_port_validation/
├── inputs_from_mitgcm/     # State, forcing, grid, parameters from MITgcm
│   └── mitgcm_kpp_inputs_11k_1D.nc
├── outputs_from_mitgcm/    # Mixing coefficients, HBL from MITgcm KPP
│   └── mitgcm_kpp_outputs_11k_1D.nc
├── outputs_from_python/    # Mixing coefficients, HBL from Python KPP port
│   └── python_kpp_outputs_11k_1D.nc   # the current, actively-tested convention
└── [documentation files]
```

**Historical exception** (documented, not aspirational): `mitgcm_kpp_inputs_11k_1D_python.nc`
actually lives in `inputs_from_mitgcm/`, not `outputs_from_python/` as the tree above
would suggest by name — see step 4 below and `CAPTURES.md` in that directory
(1DMIX-046) for why it is retained there rather than relocated.

### File Naming Conventions

**Current validation dataset**:
- `mitgcm_kpp_inputs_11k_1D.nc` - 11,000 timesteps of inputs
- `mitgcm_kpp_outputs_11k_1D.nc` - 11,000 timesteps of MITgcm outputs
- `outputs_from_python/python_kpp_outputs_11k_1D.nc` - the current Python port
  output for this capture, exercised by `tests/test_kpp_mitgcm_validation_extended.py`
- `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` - an early (2026-08-20),
  pre-convention Python port output for the same capture, retained (not deleted)
  only because `KPP_port_validation/scripts/compute_validation_statistics.py`
  still opens it directly; see that directory's `CAPTURES.md`

**General format**: `kpp_{type}_{experiment}_{timestamp}.nc` or descriptive names like above

- **type**: `input` or `output`
- **experiment**: MITgcm verification experiment name (e.g., `1D_ocean_ice_column`, `lab_sea`)
- **timestamp**: Creation date/time in ISO 8601 compact format (YYYYMMDDTHHMMSS) when applicable

**Examples**:
- `kpp_input_1D_ocean_ice_column_20260819T165215.nc`
- `kpp_output_lab_sea_20260820T143022.nc`

**Note**: Input and output files from the same run share matching names/timestamps for easy pairing.

---

## Input Files (`inputs_from_mitgcm/`)

### Purpose

Complete specification of ocean state, forcing, grid, and model parameters needed to reproduce KPP mixing calculations.

### Dimensions

```
time:        Number of output timesteps (11000 for current dataset)
x:           Zonal grid dimension (1 for 1D column experiments)
y:           Meridional grid dimension (1 for 1D column experiments)
z:           Vertical cell centers (23 levels)
z_iface:     Vertical cell interfaces (23 levels)
```

### Coordinates

| Variable | Dimensions | Units | Description | Sign Convention |
|----------|-----------|-------|-------------|-----------------|
| `time` | (time) | timestep number | Model iteration number | Positive increasing |
| `depth` | (z) | m | Cell center depth | **Negative down** (0 at surface, -5m, -15m, etc.) |
| `depth_iface` | (z_iface) | m | Interface depth | **Negative down** (0 at surface, -10m, -20m, etc.) |
| `cell_thickness` | (z) | m | Vertical cell thickness | Positive (10m, 10m, ...) |

**Coordinate System**: MITgcm uses z-coordinate with **z positive up, depth negative down**. Surface is at z=0, seafloor at z < 0.

### State Variables (Inputs)

| Variable | Dimensions | Units | Description | Sign Convention | Location |
|----------|-----------|-------|-------------|-----------------|----------|
| `temperature` | (time, x, y, z) | °C | Potential temperature | Physical values (-2 to 30°C) | Cell centers |
| `salinity` | (time, x, y, z) | psu | Practical salinity | Physical values (0 to 40 psu) | Cell centers |
| `u_velocity` | (time, x, y, z) | m/s | Zonal (eastward) velocity | **Positive east** | Cell centers |
| `v_velocity` | (time, x, y, z) | m/s | Meridional (northward) velocity | **Positive north** | Cell centers |

### Forcing Variables (Inputs)

| Variable | Dimensions | Units | Description | Sign Convention |
|----------|-----------|-------|-------------|-----------------|
| `ustar` | (time, x, y) | m/s | Surface friction velocity | Positive (magnitude) |
| `bo` | (time, x, y) | m²/s³ | Turbulent buoyancy forcing | **Positive = buoyancy gain** (destabilizing) |
| `bosol` | (time, x, y) | m²/s³ | Radiative buoyancy forcing | **Positive = buoyancy gain** from shortwave |
| `tau_x` | (time, x, y) | m²/s² | Zonal wind stress / ρ₀ | **Positive east** (eastward stress) |
| `tau_y` | (time, x, y) | m²/s² | Meridional wind stress / ρ₀ | **Positive north** (northward stress) |
| `f_coriolis` | (time, x, y) | s⁻¹ | Coriolis parameter (2Ω sin φ) | **Positive in NH, negative in SH** |

**Critical Notes**:

1. **Forcing values are KPP-specific**: These are NOT raw surface fluxes, but the derived forcing values computed by MITgcm's `kpp_forcing_surf.F` subroutine. They account for sea ice modification and other surface effects.

2. **Buoyancy Forcing Sign Convention**:
   - `bo > 0`: Buoyancy **gain** at surface (cooling or evaporation → dense water → convection)
   - `bo < 0`: Buoyancy **loss** at surface (heating or precipitation → light water → stratification)
   - `bosol > 0`: Shortwave penetration adds buoyancy below surface

3. **Wind Stress Convention**:
   - Pre-divided by reference density ρ₀ (units: m²/s² not N/m²)
   - `tau_x > 0`: Wind stress toward **east** (drives eastward surface current)
   - `tau_y > 0`: Wind stress toward **north** (drives northward surface current)

### Optional: Raw Surface Flux Variables (For Forcing Validation)

To enable validation of the forcing computation itself (not just the mixing scheme), MITgcm parsers can optionally export the raw surface fluxes that were used to compute `ustar`, `bo`, and `bosol`:

| Variable | Dimensions | Units | Description | Sign Convention |
|----------|-----------|-------|-------------|-----------------|
| `q_net` | (time, x, y) | W/m² | Net surface heat flux (excluding shortwave) | **Positive = into ocean** (warming) |
| `q_sw` | (time, x, y) | W/m² | Surface shortwave radiation | **Positive = into ocean** (heating) |
| `fw_flux` | (time, x, y) | kg/m²/s | Freshwater flux (E - P - R) | **Positive = into ocean** (freshening) |

**When present**, the Python validation script will:
1. Compute forcing from raw fluxes using `_compute_surface_forcing()`
2. Compare computed `(ustar, bo, bosol)` against the pre-computed MITgcm values
3. Validate that the Python forcing computation matches MITgcm within tolerance
4. Then proceed with mixing calculation using pre-computed forcing

**When absent**, validation uses pre-computed forcing directly (mixing scheme validation only).

**How to enable**: Set `validate_forcing=True` in `KPPDriver.compute_mixing()` when raw flux fields are present in the NetCDF input file.

### Global Attributes (Metadata)

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `title` | string | Yes | Dataset description | "MITgcm KPP Inputs" |
| `source` | string | Yes | Data source | "MITgcm with KPP instrumentation" |
| `institution` | string | Yes | Origin | "MITgcm" |
| `experiment` | string | Yes | Experiment name | "1D_ocean_ice_column" |
| `output_file_path` | string | Yes | Path to MITgcm output.txt | "/path/to/output.txt" |
| `creation_date` | string | Yes | ISO 8601 timestamp | "2026-08-19T16:52:15" |
| `uuid` | string | **Yes** | **Unique identifier** | "bc076d31-32b4-41fb-bed5-b030b81170df" |
| `conventions` | string | Yes | Metadata convention | "CF-1.8" |
| `description` | string | No | Additional info | "KPP inputs from MITgcm 1D_ocean_ice_column" |

### Model Parameters (Global Attributes)

**Critical**: These parameters are exported directly from MITgcm runtime (not namelist files) to guarantee exact values used in the simulation.

For bit-level validation between MITgcm and Python KPP, **64 runtime and compile-time parameters** are exported from MITgcm and stored as NetCDF global attributes. These fully define the KPP configuration used in a MITgcm run.

#### Physical Constants (3)

| Parameter | Type | Units | Description | Typical Value |
|-----------|------|-------|-------------|---------------|
| `gravity` | float64 | m/s² | Gravitational acceleration | 9.8156 |
| `rhoConst` | float64 | kg/m³ | Reference density | 1027.0 |
| `HeatCapacity_Cp` | float64 | J/(kg·K) | Specific heat capacity | 3986.0 |

#### Background Mixing (3)

| Parameter | Type | Units | Description | Typical Value |
|-----------|------|-------|-------------|---------------|
| `viscAz` | float64 | m²/s | Background vertical viscosity | 1.93×10⁻⁵ |
| `diffKzS` | float64 | m²/s | Background vertical diffusivity for salt | 1.46×10⁻⁷ |
| `diffKzT` | float64 | m²/s | Background vertical diffusivity for temperature | 1.46×10⁻⁷ |

#### Boundary Layer Depth Parameters (6)

| Parameter | Type | Description | Typical Value |
|-----------|------|-------------|---------------|
| `Ricr` | float64 | Critical bulk Richardson number | 0.3 |
| `cekman` | float64 | Ekman depth coefficient | 0.7 |
| `cmonob` | float64 | Monin-Obukhov depth coefficient | 1.0 |
| `concv` | float64 | Ratio of interior to entrainment buoyancy frequency | 1.8 |
| `hbf` | float64 | Fraction of hbl for absorbed solar radiation | 1.0 |
| `minKPPhbl` | float64 | Minimum boundary layer depth [m] | 10.0 |

#### Surface Layer Parameters (3)

| Parameter | Type | Description | Typical Value |
|-----------|------|-------------|---------------|
| `epsilon` | float64 | Non-dimensional extent of surface layer | 0.1 |
| `vonk` | float64 | Von Karman constant | 0.4 |
| `dB_dz` | float64 | Maximum dB/dz in mixed layer [1/s²] | 5.0×10⁻⁵ |

#### Interior Mixing Parameters (9)

| Parameter | Type | Units | Description | Typical Value |
|-----------|------|-------|-------------|---------------|
| `Riinfty` | float64 | - | Local Richardson number limit for shear instability | 0.7 |
| `BVSQcon` | float64 | 1/s² | Brunt-Vaisala squared threshold for convection | -0.0002 |
| `difm0` | float64 | m²/s | Maximum viscosity due to shear instability | 0.005 |
| `difs0` | float64 | m²/s | Maximum scalar diffusivity due to shear instability | 0.005 |
| `dift0` | float64 | m²/s | Maximum temperature diffusivity due to shear instability | 0.005 |
| `difmcon` | float64 | m²/s | Viscosity due to convective instability | 0.1 |
| `difscon` | float64 | m²/s | Scalar diffusivity due to convective instability | 0.1 |
| `diftcon` | float64 | m²/s | Temperature diffusivity due to convective instability | 0.1 |
| `num_v_smooth_Ri` | int | - | Number of vertical smoothing passes for Ri | 0 |

#### Nonlocal Transport (1)

| Parameter | Type | Description | Typical Value |
|-----------|------|-------------|---------------|
| `cstar` | float64 | Proportionality coefficient for nonlocal transport | 10.0 |

#### Shape Function Coefficients (10)

Momentum shape function:
- `conc1`, `conam`, `concm`, `conc2`, `zetam`

Scalar shape function:
- `conas`, `concs`, `conc3`, `zetas`

#### Double Diffusion Parameters (2)

| Parameter | Type | Units | Description | Typical Value |
|-----------|------|-------|-------------|---------------|
| `Rrho0` | float64 | - | Density ratio limit for double diffusion | 1.9 |
| `dsfmax` | float64 | m²/s | Maximum diffusivity for salt fingering | 0.001 |

#### Regularization Parameters (2)

| Parameter | Type | Description | Typical Value |
|-----------|------|-------------|---------------|
| `epsln` | float64 | Small number for regularization | 1.0×10⁻²⁰ |
| `phepsi` | float64 | Small number for regularization | 1.0×10⁻¹⁰ |

#### Lookup Table Parameters (6)

| Parameter | Type | Units | Description | Typical Value |
|-----------|------|-------|-------------|---------------|
| `zmin` | float64 | m³/s³ | Minimum zehat in lookup table | 0.0 |
| `zmax` | float64 | m³/s³ | Maximum zehat in lookup table | 2.5×10⁻⁸ |
| `umin` | float64 | m/s | Minimum ustar in lookup table | 0.0 |
| `umax` | float64 | m/s | Maximum ustar in lookup table | 0.024 |
| `deltaz` | float64 | m³/s³ | Delta zehat in lookup table (not used by Python) | - |
| `deltau` | float64 | m/s | Delta ustar in lookup table (not used by Python) | - |

#### Runtime Boolean Flags (5)

| Parameter | Type | Description | Typical Value |
|-----------|------|-------------|---------------|
| `KPP_ghatUseTotalDiffus` | bool | Use total diffusivity (not just KPP) for ghat | True/False |
| `KPPuseDoubleDiff` | bool | Include double diffusion contributions -- **NOT IMPLEMENTED** in the Python port; `KPPParameters(use_doublediff=True)` raises `NotImplementedError` on replay (1DMIX-059) | True/False |
| `LimitHblStable` | bool | Limit hbl depth under stable conditions | True/False |
| `KPPwriteState` | bool | Write KPP state to file (diagnostic only) | True/False |
| `KPPuseSWfrac3D` | bool | Use 3D spatially-varying shortwave water type | True/False |

#### CPP Compile-Time Options (14)

Extracted from `KPP_OPTIONS.h` in the build directory:

| Parameter | Description | CPP Define |
|-----------|-------------|------------|
| `use_ghat` | Apply nonlocal transport term to tracer flux (gates `kpp_transport_t.F`/`kpp_transport_s.F`; MITgcm's `blmix` computes `ghat` unconditionally regardless, 1DMIX-058) | `#define KPP_GHAT` |
| `smooth_shsq` | Smooth shear horizontally | `#define KPP_SMOOTH_SHSQ` |
| `smooth_dvsq` | Smooth dVsq horizontally | `#define KPP_SMOOTH_DVSQ` |
| `smooth_dbloc` | Smooth dbloc horizontally | `#define KPP_SMOOTH_DBLOC` |
| `smooth_dens` | Smooth all density variables | `#define KPP_SMOOTH_DENS` |
| `smooth_visc` | Smooth vertical viscosity | `#define KPP_SMOOTH_VISC` |
| `smooth_diff` | Smooth vertical diffusivity | `#define KPP_SMOOTH_DIFF` |
| `estimate_uref` | Resolution-independent surface velocity | `#define KPP_ESTIMATE_UREF` |
| `match_diffusivities` | Match diffusivities at BL base | `NOT #define KPP_DO_NOT_MATCH_DIFFUSIVITIES` |
| `match_derivatives` | Match derivatives at BL base | `NOT #define KPP_DO_NOT_MATCH_DERIVATIVES` |
| `smooth_regularisation` | Smooth regularization | `#define KPP_SMOOTH_REGULARISATION` |
| `scale_shearmixing` | Scale shear mixing via Polzin | `#define KPP_SCALE_SHEARMIXING` |
| `exclude_shear_mix` | Exclude shear mixing | `#define EXCLUDE_KPP_SHEAR_MIX` |
| `exclude_doublediff` | Exclude double diffusion | `#define EXCLUDE_KPP_DOUBLEDIFF` |
| `vertically_smooth_ri` | Vertically smooth Richardson number | `#define ALLOW_KPP_VERTICALLY_SMOOTH` |

#### Implementation Notes

**MITgcm Parameter Export** (`kpp_calc.F`):
Parameters are written to STDOUT on the **first call** to `KPP_OUTPUT_VALIDATION` (handles pickup restarts):

```fortran
IF ( firstCall ) THEN
  firstCall = .FALSE.
  WRITE(standardMessageUnit,'(A)') '===== KPP_MODEL_PARAMETERS ====='
  WRITE(standardMessageUnit,'(A,ES25.16)') 'PARAM_Ricr=',Ricr   ! E16.8 before 1DMIX-070
  ! ... 64 parameters total
#ifdef KPP_GHAT
  WRITE(standardMessageUnit,'(A,I1)') 'PARAM_use_ghat=',1
#else
  WRITE(standardMessageUnit,'(A,I1)') 'PARAM_use_ghat=',0
#endif
  ! ... more CPP options
  WRITE(standardMessageUnit,'(A)') '===== KPP_MODEL_PARAMETERS_END ====='
ENDIF
```

**Python Parser**: Extracts parameters from STDOUT and stores as NetCDF global attributes:
- Float parameters: standard conversion
- Integer parameters: `num_v_smooth_Ri`
- Boolean parameters: converted from 0/1 to True/False

**Python Initialization** (`run_kpp_from_split.py`):
Reads NetCDF attributes and initializes `KPPParameters`:

```python
kpp_params_dict, background_params, found_params, missing_params = \
    extract_parameters_from_inputs(inputs_ds, verbose=True)

kpp_params = KPPParameters(**kpp_params_dict)
driver = KPPDriver(params=kpp_params)
```

**Validation Coverage**:
- **Total Parameters in KPPParameters**: 70
- **Parameters Exported from MITgcm**: 64
- **Successfully Mapped**: 59
- **Will Use Python Defaults**: 11 (unimplemented features: salt plume, shelf ice; constants: mdiff=3, nni=890, nnj=480)
- **Coverage**: 84% (59/70) with full physics coverage

**Key Points**:
1. All physics parameters are exported and mapped correctly
2. CPP compile-time options are extracted from build-time `KPP_OPTIONS.h` via `#ifdef` blocks
3. Runtime flags from `data.kpp` are exported as boolean values
4. Computed parameters (`Vtc`, `cg`) are derived in Python's `__post_init__`, not exported
5. Unimplemented features (salt plume, shelf ice) use Python defaults but don't affect standard validation scenarios

---

## Output Files (`outputs_from_mitgcm/` and `outputs_from_python/`)

### Purpose

KPP-computed vertical mixing coefficients, boundary layer depth, and stability diagnostics from MITgcm reference implementation or Python port.

### Dimensions

Same as input files: `(time, x, y, z)` and `(time, x, y, z_iface)`

### Coordinates

Same as input files (copied for self-containment).

### Mixing Coefficient Variables

| Variable | Dimensions | Units | Description | Sign Convention | Location |
|----------|-----------|-------|-------------|-----------------|----------|
| `visc_az` | (time, x, y, z_iface) | m²/s | Vertical eddy viscosity | Positive (magnitude) | **Interface** (top of cell) |
| `diff_kz_s` | (time, x, y, z_iface) | m²/s | Vertical diffusivity for salt | Positive (magnitude) | **Interface** (top of cell) |
| `diff_kz_t` | (time, x, y, z_iface) | m²/s | Vertical diffusivity for temperature | Positive (magnitude) | **Interface** (top of cell) |
| `ghat` | (time, x, y, z) | s/m² | Nonlocal transport coefficient | Dimensionless shape function | **Center** (bottom of cell) |
| `hbl` | (time, x, y) | m | Boundary layer depth | **Positive depth** (10m, 50m, 100m) | Surface |

**Sign Conventions**:
- All mixing coefficients are **positive** (represent magnitude of mixing)
- `hbl` is **positive depth** in meters (e.g., hbl=50m means mixing down to 50m depth, which is z=-50m)
- Below boundary layer: coefficients → background values
- Within boundary layer: coefficients >> background (enhanced mixing)

### Diagnostic Variables

| Variable | Dimensions | Units | Description | Sign Convention | Location |
|----------|-----------|-------|-------------|-----------------|----------|
| `shear_sq` | (time, x, y, z_iface) | s⁻² | Vertical shear squared (S²) | Positive (magnitude) | **Interface** (top of cell) |
| `buoy_freq_sq` | (time, x, y, z_iface) | s⁻² | Buoyancy frequency squared (N²) | **Positive = stable** | **Interface** (top of cell) |
| `richardson` | (time, x, y, z_iface) | - | Gradient Richardson number (Ri) | Dimensionless | **Interface** (top of cell) |

**Diagnostic Definitions**:

1. **S² (shear squared)**: S² = (∂u/∂z)² + (∂v/∂z)²
   - Measures vertical velocity shear
   - Always positive
   - Large S² → strong shear → potential for shear instability

2. **N² (buoyancy frequency squared)**: N² = -(g/ρ₀)(∂ρ/∂z)
   - Measures stratification strength
   - N² > 0: stable stratification (dense below, light above)
   - N² < 0: unstable stratification (convection)
   - N² ≈ 0: neutral (well-mixed)

3. **Ri (Richardson number)**: Ri = N²/S²
   - Ratio of stabilizing (stratification) to destabilizing (shear) forces
   - Ri > 0.25: stable, suppressed mixing (stratification dominates)
   - Ri < 0.25: unstable, enhanced mixing (shear dominates)
   - Critical value Ri_c = 0.25 is the Miles-Howard stability criterion

**Note**: The `buoy_freq_sq` variable in MITgcm output is N² diagnostic output (dbloc without division by layer thickness), NOT the same as `bvsq` used internally in HBL calculation.

### Grid Staggering

- **Mixing coefficients** (`visc_az`, `diff_kz_*`): At cell **interfaces** (z_iface dimension)
  - Index k represents the interface at the **top** of cell k
  - k=1 is surface (z=0), k=Nr is bottom interface
- **Nonlocal transport** (`ghat`): At cell **centers** (z dimension)
  - Index k represents the center of cell k
- **Boundary layer depth** (`hbl`): Surface scalar per column
- **Diagnostics** (`shear_sq`, `buoy_freq_sq`, `richardson`): At cell **interfaces** (z_iface dimension)

### Global Attributes - MITgcm Output Files

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `title` | string | Yes | Dataset description | "MITgcm KPP Outputs" |
| `source` | string | Yes | Data source | "MITgcm KPP" |
| `institution` | string | Yes | Origin | "MITgcm" |
| `experiment` | string | Yes | Experiment name | "1D_ocean_ice_column" |
| `creation_date` | string | Yes | ISO 8601 timestamp | "2026-08-19T16:52:15" |
| `input_uuid` | string | **Yes** | **Links to input file** | "bc076d31-32b4-41fb-bed5-b030b81170df" |
| `conventions` | string | Yes | Metadata convention | "CF-1.8" |
| `description` | string | No | Additional info | "KPP outputs from MITgcm" |

**UUID Provenance**: The `input_uuid` in the output file **must match** the `uuid` in the corresponding input file, establishing traceability.

### Global Attributes - Python Output Files

| Attribute | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `title` | string | Yes | Dataset description | "Python KPP Outputs" |
| `source` | string | Yes | Data source | "Python KPP port" |
| `institution` | string | Yes | Origin | "ECCO 1D Mixing Model" |
| `experiment` | string | Yes | Experiment name | "1D_ocean_ice_column" |
| `creation_date` | string | Yes | ISO 8601 timestamp | "2026-08-19T17:08:42" |
| `input_uuid` | string | **Yes** | **Links to input file** | "bc076d31-32b4-41fb-bed5-b030b81170df" |
| `input_file_name` | string | **Yes** | **Input filename** | "kpp_input_1D_ocean_ice_column_20260819T165215.nc" |
| `input_file_path` | string | **Yes** | **Full input path** | "/path/to/KPP_port_validation/inputs_from_mitgcm/..." |
| `conventions` | string | Yes | Metadata convention | "CF-1.8" |
| `description` | string | No | Additional info | "Python KPP port outputs" |

**Enhanced Provenance**: Python outputs track:
1. **UUID** - Links to exact input dataset
2. **Filename** - Which specific input file was used
3. **Full path** - Complete location for reproducibility

This ensures complete traceability: given a Python output file, you can always find the exact input file that produced it.

---

## Python Input Files (`inputs_from_python/`)

**Status (1DMIX-046)**: this directory was removed — it had sat empty and
untracked since this document was first written (2026-08-20) with no file
ever matching the convention below. Documented here as an available,
never-yet-exercised convention rather than deleted outright: recreate the
directory if a genuine synthetic/Python-only input is ever needed.

### Purpose

Custom or synthetic input datasets for Python-only testing scenarios where MITgcm reference data is not available or needed.

### Use Cases

- **Idealized test cases**: Uniform stratification, linear profiles, step functions
- **Edge cases**: Extreme parameter values, boundary conditions
- **Unit tests**: Simplified scenarios to test specific code paths
- **Sensitivity studies**: Systematic parameter variations

### Format

Identical structure to MITgcm input files (same dimensions, coordinates, variables) to maintain compatibility with the Python KPP driver.

### Creation Example

```python
import numpy as np
import xarray as xr
import uuid
from datetime import datetime

# Create synthetic input dataset
nz = 23
depth = -np.arange(5, 235, 10)  # -5m to -225m
temp = 20 - 0.1 * np.arange(nz)  # Linear stratification

ds = xr.Dataset({
    'temperature': (['time', 'x', 'y', 'z'], temp[None, None, None, :]),
    # ... other variables
}, coords={
    'time': [0],
    'depth': (['z'], depth),
    # ... other coords
})

# Add metadata
ds.attrs['uuid'] = str(uuid.uuid4())
ds.attrs['experiment'] = 'synthetic_linear_stratification'
# ... other attributes

ds.to_netcdf('inputs_from_python/kpp_input_synthetic_YYYYMMDDTHHMMSS.nc')
```

---

## UUID-Based Provenance Tracking

### Purpose

Guarantee that outputs can always be traced back to the exact inputs used, preventing parameter mismatch errors.

### Implementation

1. **Input file creation**: Generate unique UUID (UUID4) and store in `uuid` attribute
2. **Output file creation**: Copy UUID to `input_uuid` attribute
3. **Python outputs**: Also record `input_file_name` and `input_file_path`

### Validation Example

```python
import xarray as xr

inputs = xr.open_dataset('kpp_input_*.nc')
outputs = xr.open_dataset('kpp_output_*.nc')

assert inputs.attrs['uuid'] == outputs.attrs['input_uuid'], \
    "UUID mismatch - outputs not from these inputs!"
```

### Benefits

- **Prevents parameter mismatches**: Can't accidentally use wrong inputs
- **Version tracking**: Compare multiple output versions with same inputs
- **Reproducibility**: Unambiguous input-output pairing for publications
- **Debugging**: Quickly identify which input produced problematic output

---

## Sign Convention Summary

### Critical Sign Conventions

| Quantity | Positive Direction | Notes |
|----------|-------------------|-------|
| **z-coordinate** | Upward | Surface = 0, deeper = more negative |
| **Depth** | Downward (negative z) | depth = -5m means z = -5m |
| **Velocity (u)** | Eastward | Standard oceanographic convention |
| **Velocity (v)** | Northward | Standard oceanographic convention |
| **Wind stress (τₓ)** | Eastward force | Pre-divided by ρ₀ |
| **Wind stress (τᵧ)** | Northward force | Pre-divided by ρ₀ |
| **Buoyancy forcing (bo)** | Buoyancy gain | bo > 0 → destabilizing (cooling) |
| **Coriolis (f)** | Positive in NH | f = 2Ω sin(latitude) |
| **HBL** | Positive depth | hbl = 50m means mixed to 50m depth |
| **Mixing coefficients** | Positive magnitude | Always κ > 0 |
| **Shear squared (S²)** | Positive magnitude | Always S² ≥ 0 |
| **Stratification (N²)** | Positive = stable | N² > 0: stable, N² < 0: unstable |
| **Richardson (Ri)** | N²/S² | Ri > 0.25: stable, Ri < 0.25: unstable |

### Common Pitfalls

⚠️ **Buoyancy forcing sign**: MITgcm convention has `bo > 0` for **cooling** (buoyancy gain → denser → convection)  
⚠️ **Depth vs z**: `depth = -z` when z < 0. Cell at depth=50m has z=-50m  
⚠️ **HBL**: Always positive. hbl=100m means boundary layer extends to depth=100m (z=-100m)  
⚠️ **Interface location**: `visc_az[k]` is at **top** of cell k, not bottom  
⚠️ **N² sign**: N² > 0 means **stable** stratification (dense below). Opposite sign convention exists in some literature!  
⚠️ **Richardson number**: Ri is only meaningful where shear exists (S² > 0). When S²→0, Ri→∞ (infinitely stable)  
⚠️ **Unstable stratification**: N² < 0 typically only in surface mixed layer with active convection  
⚠️ **Diagnostic N² vs internal bvsq**: MITgcm's `buoy_freq_sq` diagnostic is NOT the same as `bvsq` used in HBL calculation

---

## Physical Interpretation of Diagnostics

### Stratification (N²)

**Definition**: N² = -(g/ρ₀)(∂ρ/∂z)

**Physical Meaning**: 
- Measures the restoring force when a fluid parcel is displaced vertically
- N is the buoyancy frequency (natural oscillation frequency of displaced parcel)
- Strong stratification (large N²) → stable → suppresses vertical mixing

**Typical Values**:
- Surface mixed layer: N² ≈ 10⁻⁷ to 10⁻⁶ s⁻² (weakly stratified)
- Thermocline: N² ≈ 10⁻⁵ to 10⁻⁴ s⁻² (strongly stratified)
- Deep ocean: N² ≈ 10⁻⁷ s⁻² (weakly stratified)
- Convective layer: N² < 0 (unstable, active overturning)

**In KPP Context**:
- Within boundary layer: N² typically small or negative (weak stratification allows mixing)
- Below boundary layer: N² positive and increasing with depth (stratification limits mixing)
- N² = 0 defines neutral stability (fully mixed)

### Shear Squared (S²)

**Definition**: S² = (∂u/∂z)² + (∂v/∂z)²

**Physical Meaning**:
- Measures velocity shear that can extract energy from mean flow
- Strong shear (large S²) → Kelvin-Helmholtz instability → generates turbulence
- Shear production of turbulence is proportional to S²

**Typical Values**:
- Surface boundary layer: S² ≈ 10⁻⁶ to 10⁻⁵ s⁻² (wind-driven shear)
- Equatorial undercurrent: S² ≈ 10⁻⁵ to 10⁻⁴ s⁻² (strong shear)
- Deep ocean: S² ≈ 10⁻⁸ to 10⁻⁷ s⁻² (weak shear)

**In KPP Context**:
- Within boundary layer: S² large due to surface wind stress
- Below boundary layer: S² small in absence of strong currents
- S² → 0 in regions of no velocity shear

### Richardson Number (Ri)

**Definition**: Ri = N²/S²

**Physical Meaning**:
- Ratio of stabilizing (buoyancy) to destabilizing (shear) forces
- **Ri > 0.25**: Stable - stratification suppresses shear instability, minimal mixing
- **Ri < 0.25**: Unstable - shear overcomes stratification, turbulence and mixing
- **Ri ≈ 0.25**: Critical - Miles-Howard stability criterion

**Critical Threshold (Ri = 0.25)**:
- Theoretical result from linear stability analysis
- Below this value, stratified shear flows are unstable to small perturbations
- KPP and many mixing schemes use this as a key criterion

**Typical Values**:
- Unstable shear layer: Ri < 0.25 (active mixing)
- Stable shear layer: Ri > 1 (suppressed mixing)
- Thermocline: Ri > 10 (very stable, minimal mixing)
- Mixed layer base: Ri ≈ 0.25-0.5 (transition region)

**In KPP Context**:
- KPP uses bulk Richardson number to determine boundary layer depth
- Ri is computed iteratively from surface downward
- Boundary layer depth occurs where Ri reaches critical value (typically 0.3 in KPP)
- Within BL: Ri < critical → enhanced mixing
- Below BL: Ri > critical → background mixing only

### Interpreting the Diagnostics Together

**Well-Mixed Layer** (e.g., surface after storm):
- N² ≈ 0 (neutral stratification)
- S² moderate (wind stress)
- Ri ≈ 0 (unstable, active mixing)

**Strongly Stratified Thermocline**:
- N² large (strong stratification)
- S² small (weak shear)
- Ri >> 1 (very stable, minimal mixing)

**Shear-Driven Mixing** (e.g., near strong current):
- N² moderate (some stratification)
- S² large (strong shear)
- Ri < 0.25 (shear overcomes stratification → mixing)

**Convective Mixed Layer** (e.g., surface cooling):
- N² < 0 (unstable stratification)
- S² variable (wind shear)
- Ri < 0 (negative → strong convective mixing)

---

## File Format Details

### Compression

All files use NetCDF4 with:
- `zlib=True` (gzip compression)
- `complevel=4` (balanced speed/size)

### Typical File Sizes

1D column, 11,000 timesteps, 23 levels:
- **Input files**: ~989 KB (state, forcing, grid, parameters)
- **Output files**: ~990 KB (mixing + diagnostics when included)

1D column, 10 timesteps, 23 levels:
- **Input files**: ~63 KB
- **Output files**: ~70 KB with diagnostics
  - ~47 KB without diagnostics (S², N², Ri)
  - ~23 KB for diagnostic variables

### Precision

- **Floating-point data**: 64-bit (double precision)
- **Output format from MITgcm**: ES25.16 (17 significant digits, exact for a double) for every declared capture since 1DMIX-070 (E25.16, 16 digits, before it; the `PARAM_*` scalar lines were `E16.8`, 8 digits, and are `ES25.16` from 1DMIX-070 too). The parsers read both
- **Validation tolerance**: rtol=1e-12 (achievable with double precision)

### Variable Attributes

All variables include:
- `long_name`: Descriptive name
- `units`: CF-compliant units string
- `description`: Additional context
- `cell_location`: "center" or "interface" (where applicable)
- `standard_name`: CF standard name (where applicable)

---

## Usage Examples

### Loading and Inspecting

```python
import xarray as xr
import numpy as np

# Load input file
inputs = xr.open_dataset('KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc')

# Check metadata
print(f"Experiment: {inputs.attrs['experiment']}")
print(f"UUID: {inputs.attrs['uuid']}")
print(f"Parameters: viscAz={inputs.attrs['viscAz']:.6e}")

# Extract a profile at timestep 5
temp_profile = inputs.temperature.isel(time=5, x=0, y=0)
depth_profile = inputs.depth.values

# Load output file
outputs = xr.open_dataset('KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc')

# Verify provenance
assert outputs.attrs['input_uuid'] == inputs.attrs['uuid'], "UUID mismatch!"

# Extract mixing at same timestep
visc_profile = outputs.visc_az.isel(time=5, x=0, y=0)
hbl = outputs.hbl.isel(time=5, x=0, y=0).values

print(f"Boundary layer depth: {hbl:.1f} m")
```

### Plotting with Correct Orientation

```python
import matplotlib.pyplot as plt

# Extract data
z = inputs.depth.values  # Negative values (e.g., -5, -15, -25, ...)
temp = inputs.temperature.isel(time=5, x=0, y=0).values
visc = outputs.visc_az.isel(time=5, x=0, y=0).values

# Plot with depth on y-axis (positive down)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 6))

ax1.plot(temp, -z)  # Convert z to positive depth
ax1.set_xlabel('Temperature (°C)')
ax1.set_ylabel('Depth (m)')
ax1.invert_yaxis()  # Depth increases downward

ax2.plot(visc, -z)
ax2.set_xlabel('Viscosity (m²/s)')
ax2.set_xscale('log')
ax2.invert_yaxis()

plt.tight_layout()
plt.show()
```

### Extracting Parameters for Python Port

```python
import xarray as xr

inputs = xr.open_dataset('KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc')

# Extract parameters (guaranteed to match MITgcm runtime values)
params = {
    'background_visc': float(inputs.attrs['viscAz']),
    'background_diff_s': float(inputs.attrs['diffKzS']),
    'background_diff_t': float(inputs.attrs['diffKzT']),
    'gravity': float(inputs.attrs['gravity']),
    'rho_const': float(inputs.attrs['rhoConst']),
    'heat_capacity': float(inputs.attrs['HeatCapacity_Cp']),
}

print("Parameters for Python KPP:")
for key, val in params.items():
    print(f"  {key}: {val:.6e}")
```

### Analyzing Diagnostic Variables

```python
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np

# Load output file with diagnostics
outputs = xr.open_dataset('KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc')

# Extract diagnostics at timestep 5, column (0,0)
t_idx = 5
Ri = outputs.richardson.isel(time=t_idx, x=0, y=0).values
N2 = outputs.buoy_freq_sq.isel(time=t_idx, x=0, y=0).values
S2 = outputs.shear_sq.isel(time=t_idx, x=0, y=0).values
hbl = outputs.hbl.isel(time=t_idx, x=0, y=0).values
depth_iface = outputs.depth_iface.values

# Plot profiles
fig, axes = plt.subplots(1, 3, figsize=(12, 6), sharey=True)

# Stratification N²
axes[0].plot(N2, -depth_iface, 'b-', linewidth=2)
axes[0].axhline(-hbl, color='r', linestyle='--', label=f'HBL={hbl:.1f}m')
axes[0].axvline(0, color='k', linestyle='-', alpha=0.3)
axes[0].set_xlabel('N² (s⁻²)')
axes[0].set_ylabel('Depth (m)')
axes[0].set_title('Stratification')
axes[0].grid(True, alpha=0.3)
axes[0].legend()

# Shear S²
axes[1].semilogx(S2 + 1e-20, -depth_iface, 'g-', linewidth=2)
axes[1].axhline(-hbl, color='r', linestyle='--', label=f'HBL={hbl:.1f}m')
axes[1].set_xlabel('S² (s⁻²)')
axes[1].set_title('Shear Squared')
axes[1].grid(True, alpha=0.3)

# Richardson number
axes[2].plot(Ri, -depth_iface, 'orange', linewidth=2)
axes[2].axhline(-hbl, color='r', linestyle='--', label=f'HBL={hbl:.1f}m')
axes[2].axvline(0.25, color='k', linestyle='--', label='Ri=0.25 (critical)')
axes[2].set_xlabel('Richardson Number')
axes[2].set_title('Stability')
axes[2].set_xlim([-1, 2])
axes[2].grid(True, alpha=0.3)
axes[2].legend()

plt.tight_layout()
plt.show()
```

---

## Validation Workflow

### 1. Generate Reference Data from MITgcm

```bash
# Compile MITgcm with parameter-exporting KPP
cd /path/to/MITgcm_verification_docker
./scripts/experiment_compile.sh 1D_ocean_ice_column \
  -mods /path/to/code_validation \
  -build bbx \
  -j 4
```

### 2. Run Experiment

```bash
./scripts/experiment_run_no_compile.sh 1D_ocean_ice_column \
  -build bbx \
  -output output_validation
```

### 3. Parse to NetCDF Format

```bash
cd /path/to/1D_Mixing_Experiments/scripts
python parse_mitgcm_split.py /path/to/output_validation/output.txt <experiment_name>
```

This creates (next to `output.txt`):
- `mitgcm_kpp_inputs.nc` (with UUID and parameters)
- `mitgcm_kpp_outputs.nc` (with input_uuid link)

The parser streams (1DMIX-065): `output.txt` is read line by line and each
completed timestep (all tiles) is appended to the two files and dropped, so
memory use is one timestep, independent of file length (a 13.8 GB
`global_oce_latlon_720` capture exhausted 27 GB of RAM under the previous
accumulate-then-write implementation). The written files have the variables,
dimensions, attributes, dtypes and values described in this document; the only
on-disk difference from files written by the old parser is that `time` is an
unlimited (appendable) dimension. See `scripts/capture_stream.py` and
`scripts/README.md`.

### 4. Run Python Port and Compare

```bash
cd /path/to/1D_Mixing_Experiments
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc
```

This automatically:
- Extracts parameters from input file
- Runs Python KPP on all columns
- Saves to `KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc`
- Adds provenance metadata: `input_uuid`, `input_file_name`, `input_file_path`
- Compares with MITgcm outputs if available
- Reports validation statistics

### 5. Verify Provenance Chain

```bash
python -c "
import xarray as xr

inp = xr.open_dataset('KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc')
mit = xr.open_dataset('KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc')
py = xr.open_dataset('KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc')

uuid = inp.attrs['uuid']
assert mit.attrs['input_uuid'] == uuid, 'MITgcm UUID mismatch'
assert py.attrs['input_uuid'] == uuid, 'Python UUID mismatch'

print(f'✅ Complete provenance chain verified')
print(f'   UUID: {uuid}')
print(f'   All outputs traceable to inputs')
"
```

---

## Data Quality Assurance

### Checks Performed During Parsing

1. **Completeness**: All expected grid points present for each timestep
2. **Physical ranges**: 
   - Temperature: -2°C to 40°C
   - Salinity: 0 to 45 psu
   - Velocities: reasonable magnitude
3. **Grid consistency**: depth, depth_iface, cell_thickness relationships
4. **Parameter validity**: All required parameters present and non-zero

### Expected Validation Metrics

When Python port is correct:
- **HBL**: Mean relative error < 0.2%, RMS < 1.0 m
- **Mixing coefficients**: Median relative error < 0.1% (where significant mixing occurs)
- **Background values**: Match to input parameters (within floating-point precision)
- **Diagnostics (S², N², Ri)**: Should match to machine precision if using same algorithm

**Actual Results (11,000 timestep validation)**:
- Mean relative error: 0.18%
- RMS error: 0.72 m
- 99.63% of timesteps within 10% error
- Median relative error: 0.0005%

---

## References

### MITgcm KPP Implementation
- Source: `/MITgcm/pkg/kpp/`
- Key files: `kpp_calc.F`, `kpp_routines.F`
- Documentation: MITgcm manual, Chapter 7 (Parameterizations)

### KPP Algorithm
- Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). "Oceanic vertical mixing: A review and a model with a nonlocal boundary layer parameterization." Reviews of Geophysics, 32(4), 363-403.

### Mixing Dynamics
- Miles, J. W. (1961). "On the stability of heterogeneous shear flows." Journal of Fluid Mechanics, 10(4), 496-508. (Richardson number criterion)
- Howard, L. N. (1961). "Note on a paper of John W. Miles." Journal of Fluid Mechanics, 10(4), 509-512. (Miles-Howard theorem)
- Turner, J. S. (1973). "Buoyancy Effects in Fluids." Cambridge University Press. (Stratification and mixing)

### CF Conventions
- Version: CF-1.8
- URL: http://cfconventions.org/

---

## Maintenance Notes

### Adding New Experiments

When adding validation data from new experiments (e.g., lab_sea):

1. Ensure experiment name is descriptive and matches MITgcm verification directory
2. Generate timestamp from file creation date (not current time)
3. Verify UUID is unique (automatically generated by parser)
4. Check parameters are appropriate for experiment (e.g., lab_sea may have different viscAz)

### Version Control

These data files are **reference datasets** and should be:
- Version controlled (git-lfs for large files if needed)
- Immutable once validated (create new files rather than modifying)
- Documented in changelog when updated

---

**Last Updated**: 2026-08-20  
**Format Version**: 1.1  
**Contact**: ECCO 1D Mixing Model Team
