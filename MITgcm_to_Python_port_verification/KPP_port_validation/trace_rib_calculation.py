#!/usr/bin/env python3
"""
Detailed trace of Rib calculation for timestep 2312 to find numerical discrepancy.
"""

import sys
import numpy as np
import netCDF4 as nc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / '1D_Mixing_Model'))

from KPP.kpp_parameters import KPPParameters
from KPP.kpp_scheme_specific import diagnose_bl_depth, build_wscale_lookup_tables
from main.eos import compute_buoyancy_gradients


def trace_timestep(t_idx: int = 2311):
    """Trace Rib calculation for given timestep."""

    # Load inputs
    ds_in = nc.Dataset('inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc', 'r')
    ds_mit = nc.Dataset('outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc', 'r')
    ds_py = nc.Dataset('outputs_from_python/python_kpp_outputs_11k_1D.nc', 'r')

    print(f'=' * 80)
    print(f'Timestep {t_idx+1} - Detailed Rib Calculation Trace')
    print(f'=' * 80)

    # Get forcing
    ustar = float(ds_in['ustar'][t_idx])
    bo = float(ds_in['bo'][t_idx])
    bosol = float(ds_in['bosol'][t_idx])
    f = float(ds_in['f_coriolis'][t_idx])

    print(f'\n--- Input Forcing ---')
    print(f'ustar  = {ustar:.15e} m/s')
    print(f'bo     = {bo:.15e} m²/s³')
    print(f'bosol  = {bosol:.15e} m²/s³')
    print(f'bfsfc  = {bo + bosol:.15e} m²/s³')
    print(f'f      = {f:.15e} s⁻¹')

    # Get profiles
    theta = np.array(ds_in['temperature'][t_idx, 0, 0, :])
    salt = np.array(ds_in['salinity'][t_idx, 0, 0, :])
    u_vel = np.array(ds_in['u_velocity'][t_idx, 0, 0, :])
    v_vel = np.array(ds_in['v_velocity'][t_idx, 0, 0, :])
    depth = np.array(ds_in['depth'][:])
    cell_thickness = np.array(ds_in['cell_thickness'][:])

    nz = len(theta)

    print(f'\n--- Water Column (top 8 levels) ---')
    for k in range(8):
        print(f'k={k:2d} depth={depth[k]:7.2f}m  T={theta[k]:8.4f}°C  S={salt[k]:7.3f}psu  '
              f'u={u_vel[k]:9.5f}  v={v_vel[k]:9.5f}')

    # Initialize KPP parameters
    params = KPPParameters()

    print(f'\n--- KPP Parameters ---')
    print(f'Ricr     = {params.Ricr:.15e}')
    print(f'epsilon  = {params.epsilon:.15e}')
    print(f'vonk     = {params.vonk:.15e}')
    print(f'Vtc      = {params.Vtc:.15e}')
    print(f'rho_const= {params.rho_const:.15e} kg/m³')
    print(f'gravity  = {params.gravity:.15e} m/s²')

    # Step 1: Compute buoyancy gradients
    print(f'\n--- Step 1: Buoyancy Gradients ---')
    rho_surf, dbloc, dbsfc, ttalpha, ssbeta = compute_buoyancy_gradients(
        theta, salt, depth, params.rho_const, params.gravity, use_jmd95=True
    )

    print(f'rho_surf = {rho_surf:.15e} kg/m³')
    print(f'\nTop 8 levels - dbloc (local buoyancy gradient):')
    for k in range(8):
        print(f'  k={k:2d}: dbloc={dbloc[k]:.15e} (m/s²)²')

    print(f'\nTop 8 levels - dbsfc (surface-referenced buoyancy):')
    for k in range(8):
        print(f'  k={k:2d}: dbsfc={dbsfc[k]:.15e} (m/s²)²')

    # Step 2: Compute velocity shear
    print(f'\n--- Step 2: Velocity Shear ---')

    # Compute dvsq - velocity shear squared
    dvsq = np.zeros(nz)
    for k in range(nz):
        if k == 0:
            # Surface level: shear from surface to level 1
            du = u_vel[0] - 0.0  # Assume zero wind-driven surface current for now
            dv = v_vel[0] - 0.0
            dz = abs(depth[0])  # Distance from surface (0) to cell center
        else:
            # Interior: shear between cell centers
            du = u_vel[k] - u_vel[k-1]
            dv = v_vel[k] - v_vel[k-1]
            dz = abs(depth[k] - depth[k-1])

        if dz > 0:
            dvsq[k] = (du**2 + dv**2) / dz**2
        else:
            dvsq[k] = 0.0

    print(f'Top 8 levels - dvsq (velocity shear squared):')
    for k in range(8):
        print(f'  k={k:2d}: dvsq={dvsq[k]:.15e} (m/s)²')

    # Step 3: Compute Ritop
    print(f'\n--- Step 3: Ritop (Bulk Richardson Numerator) ---')
    Ritop = np.zeros(nz)
    for k in range(nz):
        Ritop[k] = (depth[0] - depth[k]) * dbsfc[k]

    print(f'Top 8 levels - Ritop:')
    for k in range(8):
        print(f'  k={k:2d}: Ritop={(depth[0] - depth[k]):7.2f} * {dbsfc[k]:.15e} = {Ritop[k]:.15e}')

    # Step 4: Build wscale lookup tables
    print(f'\n--- Step 4: Wscale Lookup Tables ---')
    wmt, wst = build_wscale_lookup_tables(params)
    print(f'wmt shape: {wmt.shape}  (stable: wmt[0,:], unstable: wmt[1,:])')
    print(f'wst shape: {wst.shape}  (stable: wst[0,:], unstable: wst[1,:])')

    # Step 5: Diagnose boundary layer depth (this calls wscale internally)
    print(f'\n--- Step 5: Diagnose Boundary Layer Depth ---')

    # Call diagnose_bl_depth
    hbl, bfsfc, stable, casea, kbl, bulk_ri = diagnose_bl_depth(
        dvsq, dbloc, Ritop, ustar, bo, bosol, f,
        depth, cell_thickness, wmt, wst, params
    )

    print(f'\nOutput:')
    print(f'  hbl    = {hbl:.15e} m')
    print(f'  bfsfc  = {bfsfc:.15e} m²/s³')
    print(f'  stable = {stable}')
    print(f'  casea  = {casea}')
    print(f'  kbl    = {kbl}')

    print(f'\nbulk_ri (Rib) profile (top 10 levels):')
    for k in range(min(10, len(bulk_ri))):
        exceeds = " *** > Ricr" if bulk_ri[k] > params.Ricr else ""
        print(f'  k={k:2d}: Rib={bulk_ri[k]:.15e}{exceeds}')

    # Compare with MITgcm
    hbl_mit = float(ds_mit['hbl'][t_idx])
    hbl_py = float(ds_py['hbl'][t_idx])

    print(f'\n--- Comparison ---')
    print(f'MITgcm HBL  = {hbl_mit:.15e} m')
    print(f'Python HBL  = {hbl_py:.15e} m  (from full run)')
    print(f'This trace  = {hbl:.15e} m  (should match Python)')
    print(f'Difference  = {hbl_mit - hbl_py:.15e} m')
    print(f'Percent err = {100 * (hbl_mit - hbl_py) / hbl_mit:.2f}%')

    # Check that the manual calculation matches the stored output
    if abs(hbl - hbl_py) < 1e-6:
        print(f'\n✓ Manual calculation matches stored Python output')
    else:
        print(f'\n✗ WARNING: Manual calculation differs from stored Python output!')
        print(f'  Difference: {abs(hbl - hbl_py):.6e} m')

    ds_in.close()
    ds_mit.close()
    ds_py.close()

    return {
        'hbl': hbl,
        'bulk_ri': bulk_ri,
        'kbl': kbl,
        'Ritop': Ritop,
        'dvsq': dvsq,
        'dbloc': dbloc,
        'dbsfc': dbsfc,
    }


if __name__ == '__main__':
    # Trace timestep 2312 (0-indexed: 2311) - worst discrepancy
    result = trace_timestep(2311)

    print(f'\n' + '=' * 80)
    print(f'Analysis: Where does Python diverge from MITgcm?')
    print(f'=' * 80)
    print(f'\nPython finds kbl={result["kbl"]} (HBL at level {result["kbl"]})')
    print(f'MITgcm finds HBL=35.12m (approximately level 3-4)')
    print(f'\nKey question: What causes Rib to exceed Ricr at different depths?')
    print(f'\nNext steps:')
    print(f'  1. Check if MITgcm debug output shows different Rib values')
    print(f'  2. Verify wscale lookup table values match MITgcm')
    print(f'  3. Check for any unit conversion or sign errors')
