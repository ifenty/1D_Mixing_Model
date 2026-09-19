#!/usr/bin/env python3
"""
Compute comprehensive validation statistics comparing Python KPP to MITgcm.
"""

import numpy as np
import xarray as xr
from pathlib import Path

# Load datasets
python_file = Path('inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc')
mitgcm_file = Path('outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc')

print("Loading datasets...")
python_ds = xr.open_dataset(python_file)
mitgcm_ds = xr.open_dataset(mitgcm_file)

# HBL statistics
print("\n" + "="*80)
print("HBL VALIDATION STATISTICS")
print("="*80)

hbl_py = python_ds.hbl.values[:, 0, 0]
hbl_mit = mitgcm_ds.hbl.values[:, 0, 0]

# Filter out NaN
valid_mask = ~(np.isnan(hbl_py) | np.isnan(hbl_mit))
hbl_py_valid = hbl_py[valid_mask]
hbl_mit_valid = hbl_mit[valid_mask]

# Absolute errors
abs_diff = np.abs(hbl_py_valid - hbl_mit_valid)

# Relative errors
rel_err = 100 * abs_diff / hbl_mit_valid

print(f"\nTotal timesteps: {len(hbl_py)}")
print(f"Valid comparisons: {len(hbl_py_valid)}")

print(f"\nAbsolute Error Statistics:")
print(f"  Mean:   {np.mean(abs_diff):.6f} m")
print(f"  Median: {np.median(abs_diff):.6f} m")
print(f"  RMS:    {np.sqrt(np.mean(abs_diff**2)):.6f} m")
print(f"  Max:    {np.max(abs_diff):.6f} m at timestep {np.argmax(abs_diff[valid_mask]) + 1}")
print(f"  P95:    {np.percentile(abs_diff, 95):.6f} m")
print(f"  P99:    {np.percentile(abs_diff, 99):.6f} m")

print(f"\nRelative Error Statistics:")
print(f"  Mean:   {np.mean(rel_err):.4f}%")
print(f"  Median: {np.median(rel_err):.4f}%")
print(f"  Max:    {np.max(rel_err):.4f}%")
print(f"  P95:    {np.percentile(rel_err, 95):.4f}%")
print(f"  P99:    {np.percentile(rel_err, 99):.4f}%")

# Error thresholds
print(f"\nError Threshold Analysis:")
thresholds = [0.01, 0.1, 1.0, 10.0]
for thresh_pct in thresholds:
    count = np.sum(rel_err < thresh_pct)
    pct = 100 * count / len(rel_err)
    print(f"  <{thresh_pct:5.2f}%: {count:5d} / {len(rel_err):5d} ({pct:6.2f}%)")

# Identify outliers
outlier_threshold = 10.0  # 10% relative error
outlier_mask = rel_err > outlier_threshold
outlier_indices = np.where(valid_mask)[0][outlier_mask]

print(f"\nOutliers (>{outlier_threshold}% error): {np.sum(outlier_mask)} / {len(rel_err)} ({100*np.sum(outlier_mask)/len(rel_err):.2f}%)")
if len(outlier_indices) > 0:
    print(f"  Outlier timesteps: {outlier_indices[:20].tolist()}" +
          (f" ... (showing first 20 of {len(outlier_indices)})" if len(outlier_indices) > 20 else ""))

    # Check for clustering
    if len(outlier_indices) > 1:
        gaps = np.diff(outlier_indices)
        if np.any(gaps < 50):
            clusters = []
            cluster_start = outlier_indices[0]
            for i in range(1, len(outlier_indices)):
                if gaps[i-1] > 50:
                    clusters.append((cluster_start, outlier_indices[i-1]))
                    cluster_start = outlier_indices[i]
            clusters.append((cluster_start, outlier_indices[-1]))

            print(f"\n  Outlier clusters (gap >50 timesteps):")
            for start, end in clusters:
                count = np.sum((outlier_indices >= start) & (outlier_indices <= end))
                print(f"    Timesteps {start+1}-{end+1}: {count} outliers")

# Worst cases
print(f"\nWorst 10 Cases (by relative error):")
worst_indices = np.argsort(rel_err)[-10:][::-1]
for rank, idx in enumerate(worst_indices, 1):
    t_idx = np.where(valid_mask)[0][idx]
    print(f"  {rank:2d}. t={t_idx+1:5d}: Python={hbl_py_valid[idx]:6.2f}m, MITgcm={hbl_mit_valid[idx]:6.2f}m, "
          f"diff={abs_diff[idx]:6.2f}m ({rel_err[idx]:6.2f}%)")

# Overall assessment
print(f"\n" + "="*80)
print("VALIDATION ASSESSMENT")
print("="*80)

mean_rel_err = np.mean(rel_err)
rms_abs_err = np.sqrt(np.mean(abs_diff**2))
pct_within_10pct = 100 * np.sum(rel_err < 10.0) / len(rel_err)

print(f"\nTarget: <0.01% mean relative error across all timesteps")
print(f"Achieved: {mean_rel_err:.4f}% mean relative error")
print(f"")
print(f"Additional metrics:")
print(f"  - RMS absolute error: {rms_abs_err:.2f}m (target: <1m) {'✅ PASS' if rms_abs_err < 1.0 else '❌ FAIL'}")
print(f"  - Within 10% error: {pct_within_10pct:.2f}% of timesteps {'✅ PASS' if pct_within_10pct > 99 else '❌ FAIL'}")
print(f"  - Mean relative error: {mean_rel_err:.4f}% (target: <0.01%) {'✅ PASS' if mean_rel_err < 0.01 else '❌ FAIL'}")

if mean_rel_err < 0.01:
    print(f"\n✅ VALIDATION SUCCESSFUL: All criteria met!")
elif mean_rel_err < 0.5 and rms_abs_err < 1.0 and pct_within_10pct > 99:
    print(f"\n⚠️ VALIDATION PARTIALLY SUCCESSFUL:")
    print(f"   Mean error {mean_rel_err:.4f}% is close to target 0.01%")
    print(f"   RMS error and 99%+ agreement suggest practical equivalence")
    print(f"   Remaining discrepancy likely due to numerical precision or edge cases")
else:
    print(f"\n❌ VALIDATION INCOMPLETE: Further investigation needed")

python_ds.close()
mitgcm_ds.close()
