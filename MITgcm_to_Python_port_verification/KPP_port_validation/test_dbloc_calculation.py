#!/usr/bin/env python3
"""
Test dbloc calculation to diagnose the 12-20x discrepancy.
"""

import sys
import numpy as np
import netCDF4 as nc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / '1D_Mixing_Model'))

from main.eos import compute_buoyancy_gradients, jmd95_eos


# Load data
ds_in = nc.Dataset('inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc', 'r')
ds_out = nc.Dataset('outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc', 'r')

# Timestep 2312 (0-indexed: 2311)
t_idx = 2311

theta = np.array(ds_in['temperature'][t_idx, 0, 0, :])
salt = np.array(ds_in['salinity'][t_idx, 0, 0, :])
depth = np.array(ds_in['depth'][:])

print('=' * 80)
print('Testing dbloc calculation at timestep 2312')
print('=' * 80)

# Test with Python defaults
print('\n--- Python (with default parameters) ---')
rho_surf_py, dbloc_py, dbsfc_py, ttalpha_py, ssbeta_py = compute_buoyancy_gradients(
    theta, salt, depth, rho_const=1029.0, gravity=9.81, use_jmd95=True
)

print(f'rho_surf = {rho_surf_py:.6f} kg/m³')
print('\ndbloc (first 5 levels):')
for k in range(5):
    print(f'  k={k}: dbloc={dbloc_py[k]:.15e} (m/s²)²')

# Test with MITgcm parameters
print('\n--- Python (with MITgcm parameters) ---')
rho_surf_mit, dbloc_mit_params, dbsfc_mit, ttalpha_mit, ssbeta_mit = compute_buoyancy_gradients(
    theta, salt, depth, rho_const=1027.0, gravity=9.8156, use_jmd95=True
)

print(f'rho_surf = {rho_surf_mit:.6f} kg/m³')
print('\ndbloc (first 5 levels):')
for k in range(5):
    print(f'  k={k}: dbloc={dbloc_mit_params[k]:.15e} (m/s²)²')

# Compare with MITgcm's N² (buoy_freq_sq)
print('\n--- MITgcm buoy_freq_sq (N²) from NetCDF ---')
bvsq_mit = ds_out['buoy_freq_sq'][t_idx, 0, 0, :]
print('Note: This is gradient Ri diagnostic N², not the same as dbloc!')
for k in range(5):
    print(f'  k={k}: N²={float(bvsq_mit[k]):.15e} (m/s²)²')

# Manual calculation to verify Python's formula
print('\n--- Manual verification of Python formula ---')
pressure = -depth
nz = len(theta)

# Get full density profile at each cell's own pressure
rho_full = np.zeros(nz)
for k in range(nz):
    rho_anom, _, _ = jmd95_eos(
        np.array([theta[k]]),
        np.array([salt[k]]),
        np.array([pressure[k]]),
        1027.0
    )
    rho_full[k] = rho_anom[0] + 1027.0

print('Density profile (first 5 levels):')
for k in range(5):
    print(f'  k={k} depth={depth[k]:.2f}m: ρ={rho_full[k]:.6f} kg/m³  T={theta[k]:.4f}°C  S={salt[k]:.3f}psu')

# Compute dbloc manually
print('\nManual dbloc calculation (k=0, interface between cells 0 and 1):')
k = 0
# Evaluate shallow cell (k=0) at deep cell pressure (k=1)
rho_anom_shal, _, _ = jmd95_eos(
    np.array([theta[k]]),
    np.array([salt[k]]),
    np.array([pressure[k+1]]),  # Deep pressure!
    1027.0
)
rho_shal_at_deep = rho_anom_shal[0] + 1027.0
rho_deep = rho_full[k+1]
dbloc_manual = 9.8156 * (rho_deep - rho_shal_at_deep) / rho_deep

print(f'  Shallow cell k={k}: T={theta[k]:.4f}°C, S={salt[k]:.3f}psu')
print(f'  Deep cell k={k+1}: T={theta[k+1]:.4f}°C, S={salt[k+1]:.3f}psu')
print(f'  ρ_shallow at own pressure   = {rho_full[k]:.6f} kg/m³')
print(f'  ρ_shallow at deep pressure  = {rho_shal_at_deep:.6f} kg/m³')
print(f'  ρ_deep at own pressure      = {rho_deep:.6f} kg/m³')
print(f'  Δρ = ρ_deep - ρ_shal@deep_P = {rho_deep - rho_shal_at_deep:.6f} kg/m³')
print(f'  dbloc = g * Δρ / ρ_deep     = {dbloc_manual:.15e} (m/s²)²')
print(f'  Python dbloc[{k}]            = {dbloc_mit_params[k]:.15e} (m/s²)²')
print(f'  Match: {abs(dbloc_manual - dbloc_mit_params[k]) < 1e-12}')

# Compare ratios
print('\n--- Ratio comparison ---')
print('Python dbloc / MITgcm N² (first 4 levels):')
for k in range(1, 5):
    ratio = dbloc_mit_params[k] / float(bvsq_mit[k]) if float(bvsq_mit[k]) != 0 else np.inf
    print(f'  k={k}: Python={dbloc_mit_params[k]:.6e}  MITgcm N²={float(bvsq_mit[k]):.6e}  ratio={ratio:.6f}')

ds_in.close()
ds_out.close()

print('\n' + '=' * 80)
print('Conclusion:')
print('If Python dbloc is 12-20x smaller than MITgcm N², and the formula is correct,')
print('then MITgcm N² must be computed differently (likely including layer thickness).')
print('=' * 80)
