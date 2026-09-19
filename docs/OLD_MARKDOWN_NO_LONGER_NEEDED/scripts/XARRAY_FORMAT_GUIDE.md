# KPP Validation: xarray/NetCDF Format Guide

**Date**: August 19, 2026  
**Purpose**: Self-documenting, analyzable format for KPP validation

---

## Why xarray Instead of npz?

### Problems with npz:
- ❌ No dimension labels (is it `[time, x, y, z]` or `[x, y, time, z]`?)
- ❌ No coordinate information (what are the actual depths?)
- ❌ No units or metadata
- ❌ No standard tools for inspection
- ❌ Parameters stored as separate arrays, easy to lose track

### Advantages of xarray/NetCDF:
- ✅ Self-documenting with dimensions, coordinates, units
- ✅ Parameters as global attributes (can't lose them)
- ✅ CF-conventions compliant (standard in ocean modeling)
- ✅ Easy comparison: `ds_python - ds_mitgcm`
- ✅ Built-in plotting: `ds.hbl.plot()`
- ✅ Lazy loading for large datasets
- ✅ Standard tools: `ncdump`, `ncview`, xarray, Matlab, R, etc.

---

## Dataset Structure

### Dimensions
```
time:    Number of timesteps (10 for 1D_ocean_ice_column)
x:       Horizontal x dimension (1 for 1D)
y:       Horizontal y dimension (1 for 1D)
z:       Vertical levels - cell centers (23 for 1D_ocean_ice_column)
z_iface: Vertical interfaces - top of cells (23)
```

### Coordinates
```python
time: [0, 1, 2, ..., 9]              # Timestep numbers
depth: [-5.0, -15.0, -25.0, ...]     # Cell center depths [m], negative down
depth_iface: [0.0, -10.0, -20.0,...] # Interface depths [m]
cell_thickness: [10.0, 10.0, ...]    # Cell thickness [m]
```

### Input Variables (State)
```
temperature:  (time, x, y, z) [°C]      - Potential temperature
salinity:     (time, x, y, z) [psu]     - Salinity
u_velocity:   (time, x, y, z) [m/s]     - Zonal velocity
v_velocity:   (time, x, y, z) [m/s]     - Meridional velocity
```

### Input Variables (Forcing)
```
ustar:       (time, x, y) [m/s]        - Friction velocity
bo:          (time, x, y) [m²/s³]      - Turbulent buoyancy forcing
bosol:       (time, x, y) [m²/s³]      - Radiative buoyancy forcing
tau_x:       (time, x, y) [m²/s²]      - Zonal wind stress / rho
tau_y:       (time, x, y) [m²/s²]      - Meridional wind stress / rho
f_coriolis:  (time, x, y) [1/s]        - Coriolis parameter
```

### Output Variables (Mixing)
```
visc_az:    (time, x, y, z_iface) [m²/s]  - Vertical viscosity (at interfaces)
diff_kz_s:  (time, x, y, z_iface) [m²/s]  - Salt diffusivity (at interfaces)
diff_kz_t:  (time, x, y, z_iface) [m²/s]  - Temp diffusivity (at interfaces)
ghat:       (time, x, y, z) [s/m²]        - Nonlocal transport (at cell centers)
hbl:        (time, x, y) [m]              - Boundary layer depth
```

**Note on grid staggering**: 
- `visc_az`, `diff_kz_*` are at cell **interfaces** (top of cell k)
- `ghat` is at cell **centers** (bottom of cell k)
- This matches MITgcm's internal convention exactly

### Global Attributes (Parameters)
```python
# Model parameters (from MITgcm runtime)
viscAz = 1.93e-5              # Background vertical viscosity [m²/s]
diffKzS = 1.46e-7             # Background salt diffusivity [m²/s]
diffKzT = 1.46e-7             # Background temp diffusivity [m²/s]
gravity = 9.8156              # Gravity [m/s²]
rhoConst = 1027.0             # Reference density [kg/m³]
HeatCapacity_Cp = 3986.0      # Specific heat [J/(kg·K)]

# Metadata
title = "MITgcm KPP Validation Data"
source = "MITgcm with KPP instrumentation"
institution = "MITgcm verification experiment"
creation_date = "2026-08-19T16:29:57"
conventions = "CF-1.8"
description = "KPP inputs and outputs for Python port validation"
```

---

## Complete Workflow

### Step 1: Instrument and Run MITgcm
```bash
# Compile with instrumented code (includes parameter output)
cd /Users/ifenty/git_repo_others/MITgcm/verification
./experiment_compile.sh 1D_ocean_ice_column \
  -mods /path/to/code_validation \
  -build build_validation \
  -clean -j 4

# Run
./experiment_run_no_compile.sh 1D_ocean_ice_column \
  -build build_validation \
  -output output_validation
```

**Output**: `output_validation/output.txt` with parameters + data

### Step 2: Parse to NPZ (Intermediate)
```bash
cd /path/to/scripts
python parse_mitgcm_kpp_validation.py \
  ../verification/1D_ocean_ice_column/output_validation/output.txt \
  ../verification/1D_ocean_ice_column/output_validation/output.npz
```

**Output**: `output.npz` with parameters

### Step 3: Convert to xarray/NetCDF
```bash
python mitgcm_to_xarray.py \
  ../verification/1D_ocean_ice_column/output_validation/output.npz \
  ../verification/1D_ocean_ice_column/output_validation/mitgcm_kpp.nc
```

**Output**: `mitgcm_kpp.nc` - MITgcm inputs and outputs in xarray format

### Step 4: Run Python KPP
```bash
# Mode 1: Python outputs only
python run_kpp_from_netcdf_input.py mitgcm_kpp.nc python

# Mode 2: Comparison dataset (MITgcm + Python + differences)
python run_kpp_from_netcdf_input.py mitgcm_kpp.nc compare

# Mode 3: Both separate and comparison
python run_kpp_from_netcdf_input.py mitgcm_kpp.nc both
```

**Outputs**:
- `mitgcm_kpp_python.nc` - Python port outputs
- `mitgcm_kpp_comparison.nc` - Side-by-side comparison

---

## Usage Examples

### Python

#### Load and Inspect
```python
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

# Load MITgcm dataset
ds_mit = xr.open_dataset('mitgcm_kpp.nc')

# Inspect structure
print(ds_mit)

# Check parameters
print(f"Background viscosity: {ds_mit.attrs['viscAz']:.6e}")
print(f"Background diffusivity (salt): {ds_mit.attrs['diffKzS']:.6e}")

# Access data
hbl_timeseries = ds_mit.hbl.isel(x=0, y=0)
temperature_profile = ds_mit.temperature.isel(time=5, x=0, y=0)
```

#### Plot
```python
# HBL evolution
ds_mit.hbl.isel(x=0, y=0).plot()
plt.ylabel('HBL [m]')
plt.title('Boundary Layer Depth Evolution')
plt.show()

# Temperature profile
plt.plot(ds_mit.temperature.isel(time=5, x=0, y=0), ds_mit.depth)
plt.xlabel('Temperature [°C]')
plt.ylabel('Depth [m]')
plt.title('Temperature Profile at t=5')
plt.grid(True)
plt.show()

# Viscosity profile
plt.plot(ds_mit.visc_az.isel(time=5, x=0, y=0), ds_mit.depth_iface)
plt.xlabel('Viscosity [m²/s]')
plt.ylabel('Depth [m]')
plt.xscale('log')
plt.title('Vertical Viscosity')
plt.show()
```

#### Compare MITgcm vs Python
```python
# Load comparison dataset
ds_comp = xr.open_dataset('mitgcm_kpp_comparison.nc')

# HBL comparison
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

# Timeseries
ds_comp.hbl_mitgcm.isel(x=0, y=0).plot(ax=ax1, label='MITgcm')
ds_comp.hbl_python.isel(x=0, y=0).plot(ax=ax1, label='Python')
ax1.legend()
ax1.set_title('HBL Evolution')

# Difference
ds_comp.hbl_diff.isel(x=0, y=0).plot(ax=ax2)
ax2.set_title('HBL Difference (Python - MITgcm)')
ax2.axhline(0, color='k', linestyle='--')

plt.tight_layout()
plt.show()

# Mixing coefficient comparison at timestep 5
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

ts = 5
for ax, var, title in zip(axes, 
                          ['visc_az', 'diff_kz_s', 'diff_kz_t'],
                          ['Viscosity', 'Salt Diffusivity', 'Temp Diffusivity']):
    mit = ds_comp[f'{var}_mitgcm'].isel(time=ts, x=0, y=0)
    py = ds_comp[f'{var}_python'].isel(time=ts, x=0, y=0)
    
    ax.plot(mit, ds_comp.depth_iface, 'b-', label='MITgcm', linewidth=2)
    ax.plot(py, ds_comp.depth_iface, 'r--', label='Python', linewidth=2)
    ax.set_xlabel(f'{title} [m²/s]')
    ax.set_ylabel('Depth [m]')
    ax.set_xscale('log')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# Compute statistics
hbl_diff = ds_comp.hbl_diff.values.flatten()
hbl_diff = hbl_diff[~np.isnan(hbl_diff)]

print(f"HBL Statistics:")
print(f"  Mean |difference|: {np.mean(np.abs(hbl_diff)):.6f} m")
print(f"  Max |difference|:  {np.max(np.abs(hbl_diff)):.6f} m")
print(f"  RMS difference:    {np.sqrt(np.mean(hbl_diff**2)):.6f} m")
```

#### Select and Filter
```python
# Select timestep 5
ds_t5 = ds_mit.isel(time=5)

# Select depth range (upper 100m)
ds_upper = ds_mit.sel(z=slice(-100, 0))

# Get HBL > 30m timesteps
deep_bl = ds_mit.where(ds_mit.hbl > 30, drop=True)

# Compute means over time
mean_temp = ds_mit.temperature.mean(dim='time')
```

### Command Line (ncdump)
```bash
# Quick inspection
ncdump -h mitgcm_kpp.nc

# Show global attributes (parameters)
ncdump -h mitgcm_kpp.nc | grep ":"

# Extract specific variable
ncdump -v hbl mitgcm_kpp.nc

# Convert to text
ncdump mitgcm_kpp.nc > mitgcm_kpp.txt
```

### Matlab
```matlab
% Load dataset
ncinfo('mitgcm_kpp.nc')

% Read variables
hbl = ncread('mitgcm_kpp.nc', 'hbl');
depth = ncread('mitgcm_kpp.nc', 'depth');
visc_az = ncread('mitgcm_kpp.nc', 'visc_az');

% Read parameters
viscAz = ncreadatt('mitgcm_kpp.nc', '/', 'viscAz');
diffKzS = ncreadatt('mitgcm_kpp.nc', '/', 'diffKzS');

% Plot
plot(squeeze(hbl))
xlabel('Timestep')
ylabel('HBL [m]')
title('Boundary Layer Depth')
```

---

## Comparison Dataset Structure

The comparison dataset includes:

**Input variables** (from MITgcm, same for both):
- `temperature`, `salinity`, `u_velocity`, `v_velocity`
- `ustar`, `bo`, `bosol`, `tau_x`, `tau_y`, `f_coriolis`

**MITgcm outputs** (suffixed with `_mitgcm`):
- `visc_az_mitgcm`, `diff_kz_s_mitgcm`, `diff_kz_t_mitgcm`, `ghat_mitgcm`, `hbl_mitgcm`

**Python outputs** (suffixed with `_python`):
- `visc_az_python`, `diff_kz_s_python`, `diff_kz_t_python`, `ghat_python`, `hbl_python`

**Difference** (suffixed with `_diff`):
- `visc_az_diff`, `diff_kz_s_diff`, `diff_kz_t_diff`, `ghat_diff`, `hbl_diff`
- Computed as: `python - mitgcm`

---

## File Sizes

Typical sizes for 1D_ocean_ice_column (10 timesteps, 1 column, 23 levels):

| Format | Size | Notes |
|--------|------|-------|
| output.txt (MITgcm raw) | ~50 KB | Text format |
| output.npz (parsed) | ~20 KB | Compressed numpy arrays |
| mitgcm_kpp.nc (xarray) | ~90 KB | NetCDF with metadata |
| mitgcm_kpp_python.nc | ~45 KB | Python outputs only |
| mitgcm_kpp_comparison.nc | ~145 KB | Both + differences |

For lab_sea (320 columns, 9 timesteps, 23 levels):
- Comparison dataset: ~15 MB (still manageable)
- With compression: ~5 MB

---

## Best Practices

### 1. Always Include Parameters
Ensure MITgcm instrumentation outputs parameters:
```fortran
WRITE(standardMessageUnit,'(A,E16.8)') 'PARAM_viscAz=',viscAz
```

Verify in dataset:
```python
assert 'viscAz' in ds.attrs, "Parameters missing - update MITgcm instrumentation"
```

### 2. Check Dimensions
```python
# Ensure dimensions are labeled correctly
print(ds.temperature.dims)  # Should be ('time', 'x', 'y', 'z')

# Check coordinates
print(ds.depth.values)  # Should be negative (down)
```

### 3. Use CF Conventions
Include standard_name where applicable:
```python
ds['temperature'].attrs['standard_name'] = 'sea_water_potential_temperature'
ds['salinity'].attrs['standard_name'] = 'sea_water_salinity'
```

### 4. Document Cell Locations
```python
ds['visc_az'].attrs['cell_location'] = 'interface'  # Top of cell
ds['ghat'].attrs['cell_location'] = 'center'  # Bottom of cell
```

### 5. Use Compression
```python
encoding = {var: {'zlib': True, 'complevel': 4} for var in ds.data_vars}
ds.to_netcdf('output.nc', encoding=encoding)
```

---

## Troubleshooting

### Problem: Parameters not in dataset
```
KeyError: 'viscAz'
```

**Solution**: Re-run MITgcm with updated instrumentation that outputs parameters, OR use temporary defaults:
```python
python run_kpp_from_netcdf_input.py mitgcm_kpp.nc --use-defaults
```

### Problem: Dimensions mismatch
```
ValueError: operands could not be broadcast together
```

**Solution**: Check that z and z_iface are used correctly:
- `visc_az`, `diff_kz_*` → `z_iface`
- `ghat`, `temperature`, `salinity` → `z`

### Problem: Can't plot
```
AttributeError: 'Dataset' object has no attribute 'plot'
```

**Solution**: Select a variable first:
```python
ds.hbl.plot()  # Not ds.plot()
```

### Problem: File too large
**Solution**: 
1. Use compression (already enabled)
2. Save only necessary variables
3. Use chunking for very large datasets:
```python
ds.to_netcdf('output.nc', encoding={'temperature': {'chunksizes': (1, 1, 1, 23)}})
```

---

## Future Enhancements

1. **Add KPP-specific parameters**: `KPP_ghatUseTotalDiffus`, `KPPuseSWfrac3D` as global attributes
2. **Add diagnostic variables**: Bulk Richardson number, velocity scales, etc.
3. **Support multiple experiments**: Add `experiment` dimension
4. **Zarr format**: For very large datasets (TB scale)
5. **Dask integration**: Lazy loading and parallel processing

---

## Summary

**Key Benefits**:
- ✅ Self-documenting format
- ✅ Parameters guaranteed consistent
- ✅ Easy to compare MITgcm vs Python
- ✅ Standard tools work out of the box
- ✅ CF-conventions compliant

**Workflow**:
```
MITgcm run → parse → convert to xarray → run Python KPP → compare
```

**Result**: Clean, analyzable datasets ready for validation, visualization, and publication.
