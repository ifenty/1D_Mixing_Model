#!/usr/bin/env python3
"""Check if hbf parameter affects bfsfc computation during Rib iteration."""

import sys
sys.path.insert(0, '../1D_Mixing_Model')

import numpy as np
import xarray as xr
from KPP.kpp_shortwave import swfrac

# Load data
ds = xr.open_dataset('mitgcm_kpp_inputs_11k_1D.nc')

# Extract timestep 2311 (0-indexed, corresponds to MITgcm timestep 2312)
tidx = 2311
bo = float(ds['Bo'].isel(time=tidx).values)
bosol = float(ds['Bosol'].isel(time=tidx).values)

print(f"Timestep {tidx} (MITgcm 2312):")
print(f"  bo = {bo:.6e} m²/s³")
print(f"  bosol = {bosol:.6e} m²/s³")

# Grid depths
zgrid = ds['zC'].values  # Cell centers (negative)
print(f"\nFirst 5 zgrid values: {zgrid[:5]}")

# Test shortwave penetration at different depths
depths_to_test = [-zgrid[0], -zgrid[1], -zgrid[2], -zgrid[3]]
hbf_values = [0.5, 1.0, 1.5, 2.0]

print(f"\n{'Depth (m)':>10} | ", end='')
for hbf in hbf_values:
    print(f"hbf={hbf:3.1f} | ", end='')
print()
print('-' * (10 + 10 * len(hbf_values) + len(hbf_values) * 3))

for depth in depths_to_test:
    print(f"{depth:10.2f} | ", end='')
    for hbf in hbf_values:
        # Compute swfrac at hbf * depth
        sw_remaining = swfrac(np.array([hbf * depth]), jerlov_water_type=2)[0]
        sw_absorbed = 1.0 - sw_remaining
        bfsfc = bo + bosol * sw_absorbed
        print(f"{bfsfc:8.2e} | ", end='')
    print()

# Compare with Python's current implementation (hbf=1.0 implicit)
print(f"\nPython's current implementation (hbf=1.0 implicit):")
for i, depth in enumerate(depths_to_test):
    sw_remaining = swfrac(np.array([depth]), jerlov_water_type=2)[0]
    sw_absorbed = 1.0 - sw_remaining
    bfsfc = bo + bosol * sw_absorbed
    print(f"  depth={depth:6.1f}m: swfrac={sw_remaining:.6f}, absorbed={sw_absorbed:.6f}, bfsfc={bfsfc:.6e}")
