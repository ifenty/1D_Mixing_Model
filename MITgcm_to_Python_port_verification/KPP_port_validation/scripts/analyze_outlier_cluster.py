#!/usr/bin/env python3
"""
Analyze forcing conditions during the outlier cluster (timesteps 2275-2350).
"""

import xarray as xr
import numpy as np

# Load input forcing
ds_in = xr.open_dataset('inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc')

# Check timesteps 2270-2355 (around the outlier cluster)
t_start, t_end = 2270, 2355

print('Forcing conditions during outlier cluster (timesteps 2275-2350):')
print('')
print(f'Timestep range: {t_start}-{t_end}')
print('')

ustar = ds_in.ustar.isel(time=slice(t_start, t_end), x=0, y=0).values
bo = ds_in.bo.isel(time=slice(t_start, t_end), x=0, y=0).values
bosol = ds_in.bosol.isel(time=slice(t_start, t_end), x=0, y=0).values
temp = ds_in.temperature.isel(time=slice(t_start, t_end), x=0, y=0, z=0).values
salt = ds_in.salinity.isel(time=slice(t_start, t_end), x=0, y=0, z=0).values

print(f'ustar  range: [{np.min(ustar):.6e}, {np.max(ustar):.6e}]')
print(f'bo     range: [{np.min(bo):.6e}, {np.max(bo):.6e}]')
print(f'bosol  range: [{np.min(bosol):.6e}, {np.max(bosol):.6e}]')
print(f'bfsfc  range: [{np.min(bo+bosol):.6e}, {np.max(bo+bosol):.6e}]')
print(f'SST    range: [{np.min(temp):.2f}°C, {np.max(temp):.2f}°C]')
print(f'SSS    range: [{np.min(salt):.3f}psu, {np.max(salt):.3f}psu]')

# Compare to typical values across all timesteps
print('')
print('For comparison, typical values across all 11k timesteps:')
ustar_all = ds_in.ustar.isel(x=0, y=0).values
bo_all = ds_in.bo.isel(x=0, y=0).values
bfsfc_all = bo_all + ds_in.bosol.isel(x=0, y=0).values
print(f'ustar  typical: median={np.median(ustar_all):.6e}, p5={np.percentile(ustar_all,5):.6e}, p95={np.percentile(ustar_all,95):.6e}')
print(f'bfsfc  typical: median={np.median(bfsfc_all):.6e}, p5={np.percentile(bfsfc_all,5):.6e}, p95={np.percentile(bfsfc_all,95):.6e}')

print('')
print('Interpretation:')
print('  - Very weak forcing (ustar ~1e-5 to 2e-5 m/s)')
print('  - Cooling dominated (bo negative)')
print('  - Solar heating small but positive (bosol positive)')
print('  - Net surface buoyancy flux near zero or slightly negative')
print('')
print('  This combination (weak shear + weak cooling + strong stratification)')
print('  is a challenging regime for boundary layer diagnosis.')
print('  Small numerical differences can cause Rib to cross Ricr=0.3 at')
print('  different depths, leading to large relative HBL errors.')

ds_in.close()
