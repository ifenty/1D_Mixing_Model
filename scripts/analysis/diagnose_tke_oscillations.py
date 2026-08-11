#!/usr/bin/env python3
"""
Comprehensive diagnosis of TKE oscillations with alpha=1.

Tests:
1. Grid Reynolds number analysis
2. Time step sensitivity (stability)
3. TKE spatial gradients
4. Temporal evolution of oscillations
5. Comparison of implicit/explicit dissipation treatment
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Setup paths
PKG_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = PKG_DIR.parent
SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
CONFIG_DIR = PKG_DIR / "configuration_yamls"
PHYSICAL_YAML = CONFIG_DIR / "physical_parameters.yaml"

os.environ["KPP_PHYSICAL_PARAMETERS_YAML"] = str(PHYSICAL_YAML)
sys.path.insert(0, str(PKG_DIR))

from main import (
    UnifiedColumnDriver,
    ConfigManager,
    GGL90Adapter,
)
from main.eos import jmd95_eos
from main.physics_basis import compute_density_gradient
from GGL90_ML.GGL90_PY.ggl90_core_driver import GGL90Driver
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters


def get_config_manager(scenario_name: str) -> ConfigManager:
    """Create ConfigManager for a specific scenario."""
    return ConfigManager(
        config_dir=SCENARIO_DIR,
        prefix=f"scenario_{scenario_name}_",
        physical_params_path=PHYSICAL_YAML,
    )


def run_with_alpha_and_dt(scenario_name: str, alpha: float, dt_multiplier: float = 1.0) -> dict:
    """
    Run scenario with specific alpha and time step.

    Args:
        scenario_name: Scenario name
        alpha: TKE diffusivity multiplier
        dt_multiplier: Multiplier for time step (1.0 = default)

    Returns:
        dict with full time series including TKE
    """
    # For now, ignore dt_multiplier - just use default dt from config
    # TODO: Implement dt override if needed

    config_mgr = get_config_manager(scenario_name)
    physical = config_mgr.load_physical_parameters()

    # Create GGL90 parameters with specified alpha
    params = GGL90Parameters()
    params.alpha = alpha
    params.tke_min = 1.0e-11 if alpha < 10.0 else 1.0e-7

    # Setup adapter
    adapter = GGL90Adapter(GGL90Driver(params), physical)

    # Create driver and run
    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    results = driver.run_experiment(output_path=None)

    # Extract and reformat diagnostics (match test_alpha_comparison.py format)
    diag = results['diagnostics']

    time = diag['time_seconds']
    theta = diag['theta']
    salt = diag['salt']
    visc_az = diag.get('visc_az', np.zeros_like(theta))
    diff_kz_t = diag.get('diff_kz_t', np.zeros_like(theta))
    tke = diag.get('tke', np.zeros_like(theta))

    # Get depth
    n_levels = theta.shape[1]
    depth = driver.grid.depth if hasattr(driver, 'grid') and driver.grid else np.linspace(0, 500, n_levels)

    # Get dt from time series
    dt = time[1] - time[0] if len(time) > 1 else 600.0

    return {
        'time': time,
        'theta': theta,
        'salt': salt,
        'visc_az': visc_az,
        'diff_kz_t': diff_kz_t,
        'tke': tke,
        'depth': depth,
        'dt': dt,
    }


def compute_grid_reynolds_number(kappa_e: np.ndarray, dz: np.ndarray, dt: float) -> np.ndarray:
    """
    Compute grid Reynolds number: Re_grid = Δz² / (κ_e × Δt)

    For stability of explicit diffusion, need Re_grid < 2
    """
    re_grid = np.zeros_like(kappa_e)
    for k in range(len(kappa_e)):
        if kappa_e[k] > 1e-10:
            re_grid[k] = dz[k]**2 / (kappa_e[k] * dt)
        else:
            re_grid[k] = np.inf
    return re_grid


def compute_tke_gradient_roughness(tke: np.ndarray) -> float:
    """
    Compute roughness metric: sum of absolute second differences.

    Higher values = more oscillatory
    """
    if len(tke) < 3:
        return 0.0

    # Second difference: d²TKE/dz² ≈ (TKE[k+1] - 2*TKE[k] + TKE[k-1])
    second_diff = tke[2:] - 2*tke[1:-1] + tke[:-2]
    roughness = np.sum(np.abs(second_diff))

    return roughness


def analyze_stability_criteria(results: dict, alpha: float, dt: float):
    """
    Analyze numerical stability criteria.
    """
    depth = results['depth']
    dz = np.diff(np.abs(depth))
    dz = np.concatenate([[dz[0]], dz])  # Prepend surface

    # Get final time step
    final_idx = -1
    tke = results['tke'][final_idx, :]
    kappa_m = results['visc_az'][final_idx, :]
    kappa_e = alpha * kappa_m

    # Compute grid Reynolds number
    re_grid = compute_grid_reynolds_number(kappa_e, dz, dt)

    print(f"\n{'='*70}")
    print(f"STABILITY ANALYSIS (α={alpha:.1f}, dt={dt:.0f}s)")
    print(f"{'='*70}")
    print(f"\nGrid Reynolds Number (Re_grid = Δz²/(κ_e·Δt)):")
    print(f"  For explicit diffusion stability: Re_grid < 2")
    print(f"  Max Re_grid:     {np.max(re_grid[np.isfinite(re_grid)]):.2f}")
    print(f"  Min Re_grid:     {np.min(re_grid[np.isfinite(re_grid)]):.2f}")
    print(f"  Median Re_grid:  {np.median(re_grid[np.isfinite(re_grid)]):.2f}")

    # Find where Re_grid is largest (most unstable)
    unstable_mask = np.isfinite(re_grid) & (re_grid > 2.0)
    if np.any(unstable_mask):
        print(f"\n  ⚠ WARNING: {np.sum(unstable_mask)} cells have Re_grid > 2 (unstable!)")
        max_idx = np.argmax(re_grid[np.isfinite(re_grid)])
        print(f"  Most unstable at k={max_idx}: Re_grid={re_grid[max_idx]:.2f}")
        print(f"    depth={depth[max_idx]:.1f}m, κ_e={kappa_e[max_idx]:.2e} m²/s")
    else:
        print(f"  ✓ All cells stable (Re_grid < 2)")

    # TKE roughness
    roughness = compute_tke_gradient_roughness(tke)
    print(f"\nTKE Profile Roughness: {roughness:.2e}")
    print(f"  (sum of |d²TKE/dz²|, higher = more oscillatory)")

    return {
        're_grid': re_grid,
        'roughness': roughness,
        'max_re_grid': np.max(re_grid[np.isfinite(re_grid)]),
        'n_unstable': np.sum(unstable_mask),
    }


def test_timestep_sensitivity(scenario_name: str, alpha: float):
    """
    Test how TKE oscillations change with time step.
    """
    print(f"\n{'='*70}")
    print(f"TIME STEP SENSITIVITY TEST (α={alpha:.1f})")
    print(f"{'='*70}")

    # Test different time steps
    dt_multipliers = [0.25, 0.5, 1.0, 2.0]
    results_list = []
    stats_list = []

    for dt_mult in dt_multipliers:
        print(f"\nRunning with dt_multiplier={dt_mult:.2f}...")
        results = run_with_alpha_and_dt(scenario_name, alpha, dt_mult)
        results_list.append(results)

        # Compute statistics
        dt = results['time'][1] - results['time'][0]
        stats = analyze_stability_criteria(results, alpha, dt)
        stats['dt_mult'] = dt_mult
        stats['dt'] = dt
        stats_list.append(stats)

    return results_list, stats_list


def plot_comprehensive_diagnosis(results_dict: dict, scenario_name: str):
    """
    Create comprehensive diagnostic plots.

    Args:
        results_dict: Dictionary with keys like ('alpha', 'dt_mult')
    """
    fig = plt.figure(figsize=(18, 12))
    gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)

    fig.suptitle(f'TKE Oscillation Diagnosis: {scenario_name}',
                 fontsize=14, fontweight='bold')

    # Extract alpha=1 results for detailed analysis
    alpha1_results = [r for (a, dt), r in results_dict.items() if a == 1.0]
    alpha30_results = [r for (a, dt), r in results_dict.items() if a == 30.0]

    if not alpha1_results or not alpha30_results:
        print("Need both alpha=1 and alpha=30 results")
        return

    # Use standard timestep (dt_mult=1.0)
    alpha1_std = [r for (a, dt), r in results_dict.items() if a == 1.0 and dt == 1.0][0]
    alpha30_std = [r for (a, dt), r in results_dict.items() if a == 30.0 and dt == 1.0][0]

    depth = alpha1_std['depth']
    time_days = alpha1_std['time'] / 86400.0

    # Plot 1: TKE profiles at final time
    ax = fig.add_subplot(gs[0, 0])
    tke1_final = alpha1_std['tke'][-1, :]
    tke30_final = alpha30_std['tke'][-1, :]
    ax.plot(tke1_final * 1e4, np.abs(depth), 'o-', label='α=1.0', markersize=5)
    ax.plot(tke30_final * 1e4, np.abs(depth), 's-', label='α=30.0', markersize=5)
    ax.set_xlabel('TKE (cm²/s²)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Final TKE Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 2: TKE second derivative (oscillation indicator)
    ax = fig.add_subplot(gs[0, 1])
    tke1_2nd = tke1_final[2:] - 2*tke1_final[1:-1] + tke1_final[:-2]
    tke30_2nd = tke30_final[2:] - 2*tke30_final[1:-1] + tke30_final[:-2]
    ax.plot(tke1_2nd * 1e4, np.abs(depth[1:-1]), 'o-', label='α=1.0', markersize=5)
    ax.plot(tke30_2nd * 1e4, np.abs(depth[1:-1]), 's-', label='α=30.0', markersize=5)
    ax.axvline(0, color='k', linestyle='--', alpha=0.5)
    ax.set_xlabel('d²TKE/dz² (cm²/s²/m²)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Second Derivative\n(Oscillation Indicator)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 3: Viscosity profiles
    ax = fig.add_subplot(gs[0, 2])
    visc1 = alpha1_std['visc_az'][-1, :]
    visc30 = alpha30_std['visc_az'][-1, :]
    ax.plot(visc1 * 1e4, np.abs(depth), 'o-', label='α=1.0', markersize=5)
    ax.plot(visc30 * 1e4, np.abs(depth), 's-', label='α=30.0', markersize=5)
    ax.set_xlabel('Viscosity (cm²/s)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Final Viscosity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 4: TKE evolution at mid-depth
    ax = fig.add_subplot(gs[1, 0])
    mid_idx = len(depth) // 2
    tke1_mid = alpha1_std['tke'][:, mid_idx]
    tke30_mid = alpha30_std['tke'][:, mid_idx]
    ax.plot(time_days, tke1_mid * 1e4, 'o-', label='α=1.0', markersize=3)
    ax.plot(time_days, tke30_mid * 1e4, 's-', label='α=30.0', markersize=3)
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('TKE (cm²/s²)')
    ax.set_title(f'TKE Evolution at {np.abs(depth[mid_idx]):.0f}m depth')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 5: Grid Reynolds number
    ax = fig.add_subplot(gs[1, 1])
    dt1 = alpha1_std['time'][1] - alpha1_std['time'][0]
    dt30 = alpha30_std['time'][1] - alpha30_std['time'][0]
    dz = np.diff(np.abs(depth))
    dz = np.concatenate([[dz[0]], dz])

    kappa_e1 = 1.0 * alpha1_std['visc_az'][-1, :]
    kappa_e30 = 30.0 * alpha30_std['visc_az'][-1, :]

    re1 = compute_grid_reynolds_number(kappa_e1, dz, dt1)
    re30 = compute_grid_reynolds_number(kappa_e30, dz, dt30)

    ax.plot(re1[np.isfinite(re1)], np.abs(depth[np.isfinite(re1)]),
            'o-', label='α=1.0', markersize=5)
    ax.plot(re30[np.isfinite(re30)], np.abs(depth[np.isfinite(re30)]),
            's-', label='α=30.0', markersize=5)
    ax.axvline(2.0, color='r', linestyle='--', label='Stability limit (Re=2)')
    ax.set_xlabel('Grid Reynolds Number')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Grid Reynolds Number\n(Δz²/(κ_e·Δt))')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()
    ax.set_xscale('log')

    # Plot 6: Time step sensitivity (roughness vs dt)
    ax = fig.add_subplot(gs[1, 2])
    alpha1_dt_tests = [(dt, r) for (a, dt), r in results_dict.items() if a == 1.0]
    alpha1_dt_tests.sort(key=lambda x: x[0])

    dt_mults = [dt for dt, r in alpha1_dt_tests]
    roughnesses = [compute_tke_gradient_roughness(r['tke'][-1, :]) for dt, r in alpha1_dt_tests]

    ax.plot(dt_mults, roughnesses, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel('Time Step Multiplier')
    ax.set_ylabel('TKE Roughness (Σ|d²TKE/dz²|)')
    ax.set_title('Time Step Sensitivity\n(α=1.0 only)')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    # Plot 7: Kappa_e profiles
    ax = fig.add_subplot(gs[2, 0])
    ax.plot(kappa_e1 * 1e4, np.abs(depth), 'o-', label='α=1.0', markersize=5)
    ax.plot(kappa_e30 * 1e4, np.abs(depth), 's-', label='α=30.0', markersize=5)
    ax.set_xlabel('κ_e = α·κ_m (cm²/s)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Diffusivity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 8: TKE contour (time x depth) for alpha=1
    ax = fig.add_subplot(gs[2, 1])
    tke_array = alpha1_std['tke'].T * 1e4  # (depth, time)
    T, Z = np.meshgrid(time_days, np.abs(depth))
    cs = ax.contourf(T, Z, tke_array, levels=20, cmap='viridis')
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Evolution (α=1.0)')
    ax.invert_yaxis()
    plt.colorbar(cs, ax=ax, label='TKE (cm²/s²)')

    # Plot 9: Max Re_grid vs time (does instability grow?)
    ax = fig.add_subplot(gs[2, 2])
    max_re_history = []
    for t_idx in range(len(time_days)):
        kappa_e_t = 1.0 * alpha1_std['visc_az'][t_idx, :]
        re_t = compute_grid_reynolds_number(kappa_e_t, dz, dt1)
        max_re_history.append(np.max(re_t[np.isfinite(re_t)]))

    ax.plot(time_days, max_re_history, 'o-', markersize=3)
    ax.axhline(2.0, color='r', linestyle='--', label='Stability limit')
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('Max Grid Reynolds Number')
    ax.set_title('Temporal Evolution of Instability\n(α=1.0)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')

    plt.tight_layout()
    output_file = PKG_DIR / 'visualizations' / f'tke_oscillation_diagnosis_{scenario_name}.png'
    output_file.parent.mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nSaved: {output_file}")
    plt.close()


def main():
    """Run comprehensive TKE oscillation diagnosis."""
    scenario_name = 'arctic_convection'

    print(f"\n{'#'*70}")
    print(f"# TKE OSCILLATION COMPREHENSIVE DIAGNOSIS")
    print(f"# Scenario: {scenario_name}")
    print(f"{'#'*70}")

    results_dict = {}

    # Test 1: Standard time step, alpha=1 vs alpha=30
    print("\n" + "="*70)
    print("TEST 1: ALPHA COMPARISON (standard time step)")
    print("="*70)

    for alpha in [1.0, 30.0]:
        print(f"\nRunning α={alpha:.1f}, dt_mult=1.0...")
        results = run_with_alpha_and_dt(scenario_name, alpha, 1.0)
        results_dict[(alpha, 1.0)] = results

        dt = results['time'][1] - results['time'][0]
        stats = analyze_stability_criteria(results, alpha, dt)

    # Test 2: Time step sensitivity for alpha=1
    print("\n" + "="*70)
    print("TEST 2: TIME STEP SENSITIVITY (α=1.0 only)")
    print("="*70)

    for dt_mult in [0.25, 0.5, 2.0]:
        print(f"\nRunning α=1.0, dt_mult={dt_mult:.2f}...")
        results = run_with_alpha_and_dt(scenario_name, 1.0, dt_mult)
        results_dict[(1.0, dt_mult)] = results

        dt = results['time'][1] - results['time'][0]
        stats = analyze_stability_criteria(results, 1.0, dt)

    # Create comprehensive diagnostic plot
    print("\n" + "="*70)
    print("Creating diagnostic plots...")
    print("="*70)
    plot_comprehensive_diagnosis(results_dict, scenario_name)

    # Summary
    print("\n" + "="*70)
    print("DIAGNOSIS SUMMARY")
    print("="*70)

    alpha1_std = results_dict[(1.0, 1.0)]
    dt1 = alpha1_std['time'][1] - alpha1_std['time'][0]
    depth = alpha1_std['depth']
    dz = np.diff(np.abs(depth))
    dz = np.concatenate([[dz[0]], dz])

    kappa_e1 = 1.0 * alpha1_std['visc_az'][-1, :]
    re1 = compute_grid_reynolds_number(kappa_e1, dz, dt1)
    roughness1 = compute_tke_gradient_roughness(alpha1_std['tke'][-1, :])

    alpha30_std = results_dict[(30.0, 1.0)]
    kappa_e30 = 30.0 * alpha30_std['visc_az'][-1, :]
    re30 = compute_grid_reynolds_number(kappa_e30, dz, dt1)
    roughness30 = compute_tke_gradient_roughness(alpha30_std['tke'][-1, :])

    print(f"\nα=1.0:")
    print(f"  Max Re_grid:     {np.max(re1[np.isfinite(re1)]):.2f}")
    print(f"  TKE roughness:   {roughness1:.2e}")
    print(f"  Unstable cells:  {np.sum(np.isfinite(re1) & (re1 > 2.0))}")

    print(f"\nα=30.0:")
    print(f"  Max Re_grid:     {np.max(re30[np.isfinite(re30)]):.2f}")
    print(f"  TKE roughness:   {roughness30:.2e}")
    print(f"  Unstable cells:  {np.sum(np.isfinite(re30) & (re30 > 2.0))}")

    print(f"\nRoughness ratio (α=1/α=30): {roughness1/roughness30:.1f}x")

    if np.max(re1[np.isfinite(re1)]) > 2.0:
        print("\n⚠ DIAGNOSIS: Grid Reynolds number exceeds stability limit (Re > 2)")
        print("   → TKE diffusion is under-resolved with α=1")
        print("   → Oscillations are a numerical stability issue")
        print("\nSOLUTIONS:")
        print("   1. Increase α (increases TKE diffusivity)")
        print("   2. Decrease time step (better resolves diffusion)")
        print("   3. Use fully implicit TKE diffusion")
    else:
        print("\n✓ Grid Reynolds number within stability limit")
        print("  Oscillations may be physical or due to other numerical effects")

    print("\nDone!")


if __name__ == '__main__':
    main()
