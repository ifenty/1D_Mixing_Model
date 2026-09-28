#!/usr/bin/env python3
"""
Comprehensive debug of timestep 2312 (0-indexed: 2311) after parameter fix.

This script traces the EXACT Rib calculation using the corrected parameters
(gravity=9.8156, rho_const=1027.0) to determine why Python produces HBL=13.82m
while MITgcm produces HBL=35.12m.

Author: Bob (Builder)
Date: 2026-08-20
"""

import sys
import numpy as np
import netCDF4 as nc
from pathlib import Path

# Add 1D_Mixing_Model to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / '1D_Mixing_Model'))

from KPP.kpp_parameters import KPPParameters
from KPP.kpp_scheme_specific import diagnose_bl_depth, build_wscale_lookup_tables
from KPP.kpp_routines import wscale
from main.eos import compute_buoyancy_gradients


def debug_timestep_2312():
    """
    Detailed trace of timestep 2312 (0-indexed: 2311) with corrected parameters.
    """

    print("=" * 100)
    print(" TIMESTEP 2312 DEBUG - WITH CORRECTED PARAMETERS")
    print("=" * 100)
    print()

    # ========== STEP 1: Load data ==========
    print("STEP 1: Loading data from NetCDF files")
    print("-" * 100)

    ds_in = nc.Dataset('inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc', 'r')
    ds_mit = nc.Dataset('outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc', 'r')
    ds_py = nc.Dataset('outputs_from_python/python_kpp_outputs_11k_1D.nc', 'r')

    t_idx = 2311  # 0-indexed timestep 2311 = timestep 2312

    # Extract forcing
    ustar = float(ds_in.variables['ustar'][t_idx])
    bo = float(ds_in.variables['bo'][t_idx])
    bosol = float(ds_in.variables['bosol'][t_idx])
    f_coriolis = float(ds_in.variables['f_coriolis'][t_idx])

    # Extract profiles
    theta = np.array(ds_in.variables['temperature'][t_idx, 0, 0, :])
    salt = np.array(ds_in.variables['salinity'][t_idx, 0, 0, :])
    u_vel = np.array(ds_in.variables['u_velocity'][t_idx, 0, 0, :])
    v_vel = np.array(ds_in.variables['v_velocity'][t_idx, 0, 0, :])
    depth = np.array(ds_in.variables['depth'][:])
    cell_thickness = np.array(ds_in.variables['cell_thickness'][:])

    # Extract expected outputs
    hbl_mit = float(ds_mit.variables['hbl'][t_idx])
    hbl_py = float(ds_py.variables['hbl'][t_idx])

    nz = len(theta)

    print(f"Timestep: {t_idx+1} (0-indexed: {t_idx})")
    print(f"Grid levels: {nz}")
    print()

    # ========== STEP 2: Initialize KPP with CORRECTED parameters ==========
    print("STEP 2: Initialize KPP with CORRECTED parameters from NetCDF")
    print("-" * 100)

    # Extract parameters from NetCDF global attributes
    params_dict = {}

    # Physical constants (CRITICAL - these were the parameter fix!)
    params_dict['gravity'] = float(ds_in.gravity)
    params_dict['rho_const'] = float(ds_in.rhoConst)
    params_dict['heat_capacity_cp'] = float(ds_in.HeatCapacity_Cp)

    # Background mixing
    params_dict['difm0'] = float(ds_in.viscAz)
    params_dict['difs0'] = float(ds_in.diffKzS)
    params_dict['dift0'] = float(ds_in.diffKzT)

    # Boundary layer parameters
    params_dict['Ricr'] = float(ds_in.Ricr)

    # Check for other parameters that might differ
    param_attrs = [
        'cekman', 'cmonob', 'concv', 'hbf', 'epsilon', 'vonk', 'dB_dz',
        'Riinfty', 'BVSQcon', 'difmcon', 'difscon', 'diftcon',
        'cstar', 'conc1', 'conam', 'concm', 'conc2', 'zetam',
        'conas', 'concs', 'conc3', 'zetas', 'Rrho0', 'dsfmax',
        'epsln', 'phepsi', 'zmin', 'zmax', 'umin', 'umax'
    ]

    for attr in param_attrs:
        if hasattr(ds_in, attr):
            params_dict[attr] = float(getattr(ds_in, attr))

    # Boolean flags
    bool_attrs = [
        'use_ghat', 'smooth_shsq', 'smooth_dvsq', 'smooth_dbloc',
        'smooth_dens', 'smooth_visc', 'smooth_diff', 'estimate_uref',
        'match_diffusivities', 'match_derivatives', 'smooth_regularisation',
        'scale_shearmixing', 'exclude_shear_mix', 'exclude_doublediff',
        'vertically_smooth_ri', 'use_doublediff', 'limit_hbl_stable',
        'ghat_use_total_diffus'
    ]

    for attr in bool_attrs:
        if hasattr(ds_in, attr):
            val = getattr(ds_in, attr)
            # Convert 0/1 to bool
            if isinstance(val, (int, np.integer)):
                params_dict[attr] = bool(val)
            else:
                params_dict[attr] = val

    # Create KPPParameters with MITgcm values
    params = KPPParameters(**params_dict)

    print(f"CORRECTED PARAMETERS:")
    print(f"  gravity       = {params.gravity:.15e} m/s²  (was 9.81 in default)")
    print(f"  rho_const     = {params.rho_const:.15e} kg/m³  (was 1029.0 in default)")
    print(f"  heat_capacity = {params.heat_capacity_cp:.15e} J/(kg·K)  (was 3994.0 in default)")
    print(f"  Ricr          = {params.Ricr:.15e}")
    print(f"  epsilon       = {params.epsilon:.15e}")
    print(f"  vonk          = {params.vonk:.15e}")
    print(f"  Vtc (computed)= {params.Vtc:.15e}")
    print(f"  phepsi        = {params.phepsi:.15e}")
    print()

    # ========== STEP 3: Display input conditions ==========
    print("STEP 3: Input conditions")
    print("-" * 100)

    print(f"FORCING:")
    print(f"  ustar  = {ustar:.15e} m/s  (very weak wind stress)")
    print(f"  bo     = {bo:.15e} m²/s³  (weak negative = weak cooling)")
    print(f"  bosol  = {bosol:.15e} m²/s³  (weak shortwave)")
    print(f"  bfsfc  = {bo + bosol:.15e} m²/s³  (net buoyancy forcing)")
    print(f"  f      = {f_coriolis:.15e} s⁻¹  (Coriolis)")
    print()

    print(f"WATER COLUMN (top 10 levels):")
    print(f"{'k':>3} {'Depth(m)':>9} {'T(°C)':>9} {'S(psu)':>9} {'u(m/s)':>11} {'v(m/s)':>11}")
    for k in range(min(10, nz)):
        print(f"{k:3d} {depth[k]:9.2f} {theta[k]:9.4f} {salt[k]:9.4f} {u_vel[k]:11.6e} {v_vel[k]:11.6e}")
    print()

    # ========== STEP 4: Compute buoyancy gradients ==========
    print("STEP 4: Compute buoyancy gradients (using CORRECTED gravity and rho_const)")
    print("-" * 100)

    rho_surf, dbloc, dbsfc, ttalpha, ssbeta = compute_buoyancy_gradients(
        theta, salt, depth, params.rho_const, params.gravity, use_jmd95=True
    )

    print(f"Surface density: rho_surf = {rho_surf:.15e} kg/m³")
    print()
    print(f"dbloc (local buoyancy gradient) [m/s²]² - top 10 levels:")
    for k in range(min(10, nz)):
        print(f"  k={k:2d}: dbloc = {dbloc[k]:15.9e}")
    print()
    print(f"dbsfc (surface-referenced buoyancy) [m/s²]² - top 10 levels:")
    for k in range(min(10, nz)):
        print(f"  k={k:2d}: dbsfc = {dbsfc[k]:15.9e}")
    print()

    # ========== STEP 5: Compute velocity shear ==========
    print("STEP 5: Compute velocity shear squared (dvsq)")
    print("-" * 100)

    dvsq = np.zeros(nz)
    for k in range(nz):
        if k == 0:
            # Surface level: shear from surface (u=0, v=0) to level 0
            du = u_vel[0] - 0.0
            dv = v_vel[0] - 0.0
            dz = abs(depth[0])
        else:
            # Interior: shear between cell centers k-1 and k
            du = u_vel[k] - u_vel[k-1]
            dv = v_vel[k] - v_vel[k-1]
            dz = abs(depth[k] - depth[k-1])

        if dz > 0:
            dvsq[k] = (du**2 + dv**2) / dz**2
        else:
            dvsq[k] = 0.0

    print(f"dvsq (velocity shear squared) [(m/s)²] - top 10 levels:")
    for k in range(min(10, nz)):
        print(f"  k={k:2d}: dvsq = {dvsq[k]:15.9e}")
    print()

    # ========== STEP 6: Compute Ritop ==========
    print("STEP 6: Compute Ritop (bulk Richardson numerator)")
    print("-" * 100)

    Ritop = np.zeros(nz)
    for k in range(nz):
        Ritop[k] = (depth[0] - depth[k]) * dbsfc[k]

    print(f"Ritop = (depth[0] - depth[k]) * dbsfc[k] - top 10 levels:")
    for k in range(min(10, nz)):
        print(f"  k={k:2d}: Ritop = ({depth[0]:7.2f} - {depth[k]:7.2f}) * {dbsfc[k]:15.9e} = {Ritop[k]:15.9e}")
    print()

    # ========== STEP 7: Build wscale lookup tables ==========
    print("STEP 7: Build wscale lookup tables")
    print("-" * 100)

    wmt, wst = build_wscale_lookup_tables(params)
    print(f"wmt shape: {wmt.shape}  (wmt[0,:] = stable, wmt[1,:] = unstable)")
    print(f"wst shape: {wst.shape}  (wst[0,:] = stable, wst[1,:] = unstable)")
    print()

    # ========== STEP 8: Manually compute Rib for first few levels ==========
    print("STEP 8: Manual Rib computation for levels 1-5 (detailed breakdown)")
    print("-" * 100)

    bfsfc = bo + bosol
    stable_flag = 0.5 + np.sign(bfsfc) * 0.5

    print(f"bfsfc = {bfsfc:.15e} m²/s³")
    print(f"stable_flag = {stable_flag:.1f} (1=stable, 0=unstable)")
    print()

    for kl in range(1, min(6, nz)):
        print(f"Level k={kl} (depth={-depth[kl]:.1f}m):")
        print(f"-" * 80)

        # Sigma computation
        sigma = stable_flag + (1.0 - stable_flag) * params.epsilon
        casea_depth = -depth[kl]

        print(f"  sigma = {sigma:.15e}")
        print(f"  casea_depth = {casea_depth:.15e} m")

        # Compute turbulent velocity scales using wscale
        wm, ws = wscale(
            np.array([sigma]),
            np.array([casea_depth]),
            np.array([ustar]),
            np.array([bfsfc]),
            wmt, wst, params
        )

        print(f"  wm (momentum velocity scale) = {wm[0]:.15e} m/s")
        print(f"  ws (scalar velocity scale)   = {ws[0]:.15e} m/s")

        # Compute bvsq (buoyancy frequency squared)
        if kl + 1 < nz:
            zgrid_below = depth[kl + 1]
        else:
            zgrid_below = depth[-1] * 100.0  # Mirror MITgcm ghost point

        bvsq = 0.5 * (
            dbloc[kl-1] / (depth[kl-1] - depth[kl]) +
            dbloc[kl] / (depth[kl] - zgrid_below)
        )

        print(f"  dbloc[{kl-1}] = {dbloc[kl-1]:.15e}")
        print(f"  dbloc[{kl}] = {dbloc[kl]:.15e}")
        print(f"  depth[{kl-1}] = {depth[kl-1]:.15e} m")
        print(f"  depth[{kl}] = {depth[kl]:.15e} m")
        print(f"  zgrid_below = {zgrid_below:.15e} m")
        print(f"  bvsq = {bvsq:.15e} s⁻²")

        # Compute vtsq (turbulent velocity contribution)
        if bvsq == 0.0:
            vtsq = 0.0
        else:
            vtsq = -depth[kl] * ws[0] * np.sqrt(abs(bvsq)) * params.Vtc

        print(f"  vtsq = -depth * ws * sqrt(|bvsq|) * Vtc")
        print(f"       = {-depth[kl]:.6f} * {ws[0]:.9e} * {np.sqrt(abs(bvsq)):.9e} * {params.Vtc:.9e}")
        print(f"       = {vtsq:.15e}")

        # Compute Rib denominator
        tempVar1 = dvsq[kl] + vtsq
        if params.smooth_regularisation:
            tempVar2 = tempVar1 + params.phepsi
        else:
            tempVar2 = max(tempVar1, params.phepsi)

        print(f"  dvsq[{kl}] = {dvsq[kl]:.15e}")
        print(f"  tempVar1 = dvsq + vtsq = {tempVar1:.15e}")
        print(f"  tempVar2 = max(tempVar1, phepsi) = {tempVar2:.15e}")

        # Compute Rib
        Rib_kl = Ritop[kl] / tempVar2

        print(f"  Rib[{kl}] = Ritop[{kl}] / tempVar2")
        print(f"         = {Ritop[kl]:.15e} / {tempVar2:.15e}")
        print(f"         = {Rib_kl:.15e}")

        if Rib_kl > params.Ricr:
            print(f"  *** Rib > Ricr ({params.Ricr}) - would set kbl={kl} ***")
        else:
            print(f"  Rib < Ricr ({params.Ricr}) - boundary layer extends deeper")

        print()

    # ========== STEP 9: Call diagnose_bl_depth ==========
    print("STEP 9: Call diagnose_bl_depth (full computation)")
    print("-" * 100)

    # Temporarily disable debug output in diagnose_bl_depth by monkey-patching
    import KPP.kpp_scheme_specific
    original_diagnose = KPP.kpp_scheme_specific.diagnose_bl_depth

    # Create a wrapper that disables DEBUG
    def diagnose_no_debug(*args, **kwargs):
        import KPP.kpp_scheme_specific as kss
        # Save original DEBUG value
        lines = open(kss.__file__).readlines()
        # Just call original
        return original_diagnose(*args, **kwargs)

    hbl, bfsfc_out, stable_out, casea_out, kbl, Rib = diagnose_bl_depth(
        dvsq, dbloc, Ritop, ustar, bo, bosol, f_coriolis,
        depth, cell_thickness, wmt, wst, params
    )

    print(f"OUTPUT:")
    print(f"  hbl    = {hbl:.15e} m")
    print(f"  kbl    = {kbl}")
    print(f"  bfsfc  = {bfsfc_out:.15e} m²/s³")
    print(f"  stable = {stable_out}")
    print(f"  casea  = {casea_out}")
    print()

    print(f"Rib profile (levels where Rib > Ricr marked with ***):")
    for k in range(min(15, len(Rib))):
        marker = " ***" if Rib[k] > params.Ricr else ""
        print(f"  k={k:2d} (depth={-depth[k]:6.1f}m): Rib={Rib[k]:15.9e}{marker}")
    print()

    # ========== STEP 10: Compare with expected results ==========
    print("STEP 10: Comparison with MITgcm and previous Python run")
    print("-" * 100)

    print(f"HBL Results:")
    print(f"  MITgcm HBL        = {hbl_mit:10.6f} m  (expected)")
    print(f"  Python HBL (this) = {hbl:10.6f} m  (computed)")
    print(f"  Python HBL (file) = {hbl_py:10.6f} m  (from NetCDF)")
    print(f"  Difference        = {hbl_mit - hbl:10.6f} m  ({100*(hbl_mit-hbl)/hbl_mit:6.2f}%)")
    print()

    if abs(hbl - hbl_py) < 1e-6:
        print(f"✓ Manual calculation matches stored Python output")
    else:
        print(f"✗ Manual calculation differs from stored Python output by {abs(hbl - hbl_py):.6e} m")
    print()

    # ========== STEP 11: Analysis ==========
    print("STEP 11: Analysis and Hypothesis")
    print("-" * 100)

    print(f"KEY FINDINGS:")
    print()

    # Find first level where Rib > Ricr
    first_exceed = None
    for k in range(1, len(Rib)):
        if Rib[k] > params.Ricr:
            first_exceed = k
            break

    if first_exceed is not None:
        print(f"1. Python finds Rib > Ricr at level k={first_exceed} (depth={-depth[first_exceed]:.1f}m)")
        print(f"   This causes kbl={first_exceed}, leading to HBL={hbl:.1f}m after interpolation")
        print()
        print(f"2. MITgcm produces HBL={hbl_mit:.1f}m, suggesting it finds kbl around level 3-4")
        print()
        print(f"3. At level k={first_exceed}:")
        print(f"   Ritop     = {Ritop[first_exceed]:.6e}  (buoyancy stratification)")
        print(f"   dvsq      = {dvsq[first_exceed]:.6e}  (velocity shear - essentially zero)")
        print(f"   vtsq      ≈ {dvsq[first_exceed] + Ritop[first_exceed]/(Rib[first_exceed]+1e-20):.6e}  (turbulent contribution)")
        print(f"   Rib       = {Rib[first_exceed]:.6f}  (bulk Richardson number)")
        print()
        print(f"HYPOTHESIS:")
        print(f"  The discrepancy is in the turbulent velocity scale (ws) or buoyancy gradient (bvsq)")
        print(f"  calculation. With correct parameters (gravity={params.gravity}, rho_const={params.rho_const}),")
        print(f"  Python computes small vtsq values at shallow depths, leading to large Rib that")
        print(f"  exceeds Ricr=0.3 prematurely.")
        print()
        print(f"  If MITgcm computes larger vtsq (larger denominator), Rib would be smaller and")
        print(f"  the boundary layer would extend deeper to ~35m.")
        print()
        print(f"POSSIBLE CAUSES:")
        print(f"  1. Difference in wscale lookup table interpolation")
        print(f"  2. Difference in buoyancy gradient calculation (EOS formulation)")
        print(f"  3. Smoothing operations in MITgcm (smooth_dbloc=1) affecting dbloc array")
        print(f"  4. Horizontal smoothing (but on 1x1 grid should be no-op)")
        print(f"  5. Numerical precision differences in intermediate calculations")
    else:
        print(f"1. Python does NOT find any level where Rib > Ricr")
        print(f"   This should not happen if formulas are correct!")
        print(f"   HBL bottomed out at {hbl:.1f}m")

    print()
    print("=" * 100)
    print(" END OF DEBUG")
    print("=" * 100)

    ds_in.close()
    ds_mit.close()
    ds_py.close()

    return {
        'hbl': hbl,
        'kbl': kbl,
        'Rib': Rib,
        'Ritop': Ritop,
        'dvsq': dvsq,
        'dbloc': dbloc,
        'dbsfc': dbsfc,
        'hbl_mit': hbl_mit,
        'hbl_py': hbl_py,
        'params': params,
    }


if __name__ == '__main__':
    result = debug_timestep_2312()

    print()
    print("SUMMARY FOR ARCH:")
    print("-" * 100)
    print(f"Computed HBL: {result['hbl']:.6f} m")
    print(f"Expected HBL: {result['hbl_mit']:.6f} m")
    print(f"Discrepancy:  {result['hbl_mit'] - result['hbl']:.6f} m ({100*(result['hbl_mit']-result['hbl'])/result['hbl_mit']:.1f}%)")
    print()
    print(f"First level where Rib > Ricr: k={result['kbl']}")
    print(f"This sets HBL to ~{result['hbl']:.1f}m instead of ~{result['hbl_mit']:.1f}m")
    print()
    print("All detailed diagnostics printed above. Ready for Richard's review.")
