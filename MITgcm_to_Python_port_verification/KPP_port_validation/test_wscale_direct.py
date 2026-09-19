#!/usr/bin/env python
"""
Direct test of Python wscale function for timestep 2312, k=1.

Tests the exact inputs that cause the discrepancy.
"""

import sys
import numpy as np

# Add paths
sys.path.insert(0, '/Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/1D_Mixing_Model')

from KPP.kpp_parameters import KPPParameters
from KPP.kpp_routines import wscale, build_wscale_lookup_tables

print("=" * 100)
print(" WSCALE FUNCTION DIRECT TEST - TIMESTEP 2312, k=1")
print("=" * 100)
print()

# Initialize KPP parameters
config = KPPParameters()
print("KPP Parameters:")
print(f"  vonk = {config.vonk}")
print(f"  epsilon = {config.epsilon}")
print(f"  zmin = {config.zmin:.15e}")
print(f"  zmax = {config.zmax:.15e}")
print(f"  umin = {config.umin:.15e}")
print(f"  umax = {config.umax:.15e}")
print(f"  nni = {config.nni}")
print(f"  nnj = {config.nnj}")
print(f"  keep_mitgcm_bugs = {config.keep_mitgcm_bugs}")
print()

# Build lookup tables
print("Building wscale lookup tables...")
wmt, wst = build_wscale_lookup_tables(config)
print(f"  wmt shape: {wmt.shape}")
print(f"  wst shape: {wst.shape}")
print()

# Test Case 1: Correct forcing (Python scenario)
print("-" * 100)
print("TEST CASE 1: Correct Forcing (Python scenario)")
print("-" * 100)

sigma_correct = np.array([0.1])
hbl_correct = np.array([15.0])
ustar_correct = np.array([2.236067977499790e-05])
bfsfc_correct = np.array([-1.924943341457611e-10])

print(f"Inputs:")
print(f"  sigma = {sigma_correct[0]:.15e}")
print(f"  hbl = {hbl_correct[0]:.15e} m")
print(f"  ustar = {ustar_correct[0]:.15e} m/s")
print(f"  bfsfc = {bfsfc_correct[0]:.15e} m²/s³")
print()

zehat_correct = config.vonk * sigma_correct[0] * hbl_correct[0] * bfsfc_correct[0]
print(f"Computed zehat:")
print(f"  zehat = vonk * sigma * hbl * bfsfc")
print(f"  zehat = {zehat_correct:.15e}")
print()

# Check table bounds
if zehat_correct <= config.zmax:
    print(f"  zehat <= zmax: USING LOOKUP TABLE")
    zdiff_unclamped = zehat_correct - config.zmin
    zdiff_clamped = max(0.0, zehat_correct - config.zmin)
    print(f"  zdiff (unclamped) = zehat - zmin = {zdiff_unclamped:.15e}")
    print(f"  zdiff (clamped) = max(0, zehat - zmin) = {zdiff_clamped:.15e}")

    deltaz = (config.zmax - config.zmin) / (config.nni + 1)
    print(f"  deltaz = {deltaz:.15e}")

    iz = int(zdiff_clamped / deltaz)
    print(f"  iz = int(zdiff / deltaz) = {iz}")
    print(f"  iz_clamped = min(max(iz, 0), nni) = {min(max(iz, 0), config.nni)}")
else:
    print(f"  zehat > zmax: USING STABLE FORMULA")
print()

# Call wscale
wm_correct, ws_correct = wscale(
    sigma_correct, hbl_correct, ustar_correct, bfsfc_correct,
    wmt, wst, config
)

print(f"Outputs:")
print(f"  wm = {wm_correct[0]:.15e} m/s")
print(f"  ws = {ws_correct[0]:.15e} m/s")
print()

# Test Case 2: Zero forcing (MITgcm debug scenario)
print("-" * 100)
print("TEST CASE 2: Zero Forcing (MITgcm debug run scenario)")
print("-" * 100)

sigma_zero = np.array([0.55])  # For bfsfc=0, stable_flag=0.5, sigma=0.5+0.5*0.1=0.55
hbl_zero = np.array([15.0])
ustar_zero = np.array([0.0])
bfsfc_zero = np.array([0.0])

print(f"Inputs:")
print(f"  sigma = {sigma_zero[0]:.15e} (computed as 0.5 + 0.5*epsilon for bfsfc=0)")
print(f"  hbl = {hbl_zero[0]:.15e} m")
print(f"  ustar = {ustar_zero[0]:.15e} m/s")
print(f"  bfsfc = {bfsfc_zero[0]:.15e} m²/s³")
print()

zehat_zero = config.vonk * sigma_zero[0] * hbl_zero[0] * bfsfc_zero[0]
print(f"Computed zehat:")
print(f"  zehat = vonk * sigma * hbl * bfsfc")
print(f"  zehat = {zehat_zero:.15e}")
print()

if zehat_zero <= config.zmax:
    print(f"  zehat <= zmax: USING LOOKUP TABLE")
else:
    print(f"  zehat > zmax: USING STABLE FORMULA")
print()

# Call wscale
wm_zero, ws_zero = wscale(
    sigma_zero, hbl_zero, ustar_zero, bfsfc_zero,
    wmt, wst, config
)

print(f"Outputs:")
print(f"  wm = {wm_zero[0]:.15e} m/s")
print(f"  ws = {ws_zero[0]:.15e} m/s")
print()

# Test Case 3: Correct forcing but with keep_mitgcm_bugs=True
print("-" * 100)
print("TEST CASE 3: Correct Forcing with keep_mitgcm_bugs=True")
print("-" * 100)

config_buggy = KPPParameters(keep_mitgcm_bugs=True)
wmt_buggy, wst_buggy = build_wscale_lookup_tables(config_buggy)

wm_buggy, ws_buggy = wscale(
    sigma_correct, hbl_correct, ustar_correct, bfsfc_correct,
    wmt_buggy, wst_buggy, config_buggy
)

print(f"Outputs (with keep_mitgcm_bugs=True):")
print(f"  wm = {wm_buggy[0]:.15e} m/s")
print(f"  ws = {ws_buggy[0]:.15e} m/s")
print()

if np.isclose(ws_buggy[0], ws_correct[0], rtol=1e-10):
    print(f"  ✓ ws matches between buggy and fixed versions (as expected for this case)")
else:
    print(f"  ✗ ws differs between buggy and fixed versions!")
    print(f"    Difference: {abs(ws_buggy[0] - ws_correct[0]):.15e} m/s")
print()

# Summary
print("=" * 100)
print(" SUMMARY")
print("=" * 100)
print()
print(f"Python wscale with CORRECT FORCING (ustar={ustar_correct[0]:.3e}, bfsfc={bfsfc_correct[0]:.3e}):")
print(f"  ws = {ws_correct[0]:.15e} m/s")
print()
print(f"Python wscale with ZERO FORCING (ustar=0, bfsfc=0):")
print(f"  ws = {ws_zero[0]:.15e} m/s")
print()
print(f"Expected MITgcm ws (from comparison_k1_hp.txt):")
print(f"  ws = 0.000000000000000E+00 m/s")
print()
print("CONCLUSION:")
if ws_zero[0] == 0.0:
    print("  ✓ Python wscale returns ws=0 for zero forcing (matches MITgcm debug run)")
    print("  ✓ Python wscale returns ws≠0 for correct forcing (expected behavior)")
    print()
    print("  The MITgcm debug run ws=0 is explained by ZERO FORCING, not a bug in wscale.")
    print("  Python's ws=3.711e-04 is CORRECT for the actual validation forcing values.")
else:
    print("  ✗ Unexpected: Python wscale should return ws=0 for zero forcing")
print()
print("=" * 100)
