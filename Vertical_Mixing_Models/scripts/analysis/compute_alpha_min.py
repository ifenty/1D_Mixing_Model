#!/usr/bin/env python3
"""
Compute minimum stable alpha by analyzing Re_grid throughout the simulation.
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

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
from GGL90.ggl90_core_driver import GGL90Driver
from GGL90.ggl90_parameters import GGL90Parameters


def compute_alpha_min_from_results(results: dict, alpha: float) -> dict:
    """
    Compute minimum stable alpha from full time series.

    Args:
        results: Diagnostics dict with time series
        alpha: Alpha value used in this run

    Returns:
        dict with alpha_min analysis
    """
    time = results['time']
    dt = results['dt']
    depth = results['depth']
    visc_az = results['visc_az']  # κ_m

    # Compute grid spacing
    dz = np.diff(np.abs(depth))
    dz = np.concatenate([[dz[0]], dz])

    nz = len(depth)
    nt = len(time)

    # Compute κ_e = α · κ_m at each time step
    kappa_e = alpha * visc_az  # (nt, nz)

    # Compute Re_grid at each time and depth
    # Note: kappa_e.shape = (nt, nz), be careful with indexing
    re_grid = np.zeros_like(kappa_e)
    actual_nt, actual_nz = kappa_e.shape

    for t in range(actual_nt):
        for k in range(actual_nz):
            if kappa_e[t, k] > 1e-10:
                re_grid[t, k] = dz[k]**2 / (kappa_e[t, k] * dt)
            else:
                re_grid[t, k] = np.inf

    # Find maximum Re_grid over all time and space
    finite_mask = np.isfinite(re_grid)
    max_re = np.max(re_grid[finite_mask]) if np.any(finite_mask) else 0.0

    # Find where and when max occurs
    if np.any(finite_mask):
        max_idx = np.unravel_index(np.argmax(re_grid * finite_mask), re_grid.shape)
        max_t_idx, max_k_idx = max_idx
        max_time = time[max_t_idx] / 86400.0  # days
        max_depth = depth[max_k_idx]
        max_kappa_e = kappa_e[max_t_idx, max_k_idx]
        max_dz = dz[max_k_idx]
    else:
        max_t_idx = max_k_idx = 0
        max_time = max_depth = max_kappa_e = max_dz = 0.0

    # Compute minimum stable alpha
    # For Re < 2: α > Δz² / (2 · κ_m · Δt)
    # Current Re = Δz² / (α_current · κ_m · Δt)
    # So: α_min = α_current · Re_max / 2
    alpha_min = alpha * max_re / 2.0

    # Also compute alpha needed for Re < 1 (more conservative)
    alpha_conservative = alpha * max_re

    return {
        'alpha_min': alpha_min,
        'alpha_conservative': alpha_conservative,
        'max_re': max_re,
        'max_time_days': max_time,
        'max_depth': max_depth,
        'max_kappa_e': max_kappa_e,
        'max_dz': max_dz,
        'dt': dt,
        're_grid_timeseries': re_grid,
    }


def run_scenario(scenario_name: str, alpha: float) -> dict:
    """Run scenario and return results."""
    config_mgr = ConfigManager(
        config_dir=SCENARIO_DIR,
        prefix=f"scenario_{scenario_name}_",
        physical_params_path=PHYSICAL_YAML,
    )
    physical = config_mgr.load_physical_parameters()

    params = GGL90Parameters()
    params.alpha = alpha
    params.tke_min = 1.0e-11 if alpha < 10.0 else 1.0e-7

    adapter = GGL90Adapter(GGL90Driver(params), physical)
    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    results = driver.run_experiment(output_path=None)

    diag = results['diagnostics']
    time = diag['time_seconds']
    theta = diag['theta']
    visc_az = diag.get('visc_az', np.zeros_like(theta))

    n_levels = theta.shape[1]
    depth = driver.grid.depth if hasattr(driver, 'grid') and driver.grid else np.linspace(0, 500, n_levels)
    dt = time[1] - time[0] if len(time) > 1 else 600.0

    return {
        'time': time,
        'visc_az': visc_az,
        'depth': depth,
        'dt': dt,
    }


def plot_alpha_min_analysis(results_dict: dict, scenario_name: str):
    """Plot alpha_min analysis."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Minimum Stable Alpha Analysis: {scenario_name}',
                 fontsize=14, fontweight='bold')

    # Plot 1: α_min vs α_tested
    ax = axes[0, 0]
    alphas = sorted(results_dict.keys())
    alpha_mins = [results_dict[a]['alpha_min'] for a in alphas]
    alpha_cons = [results_dict[a]['alpha_conservative'] for a in alphas]

    ax.plot(alphas, alpha_mins, 'o-', label='α_min (Re<2)', markersize=8, linewidth=2)
    ax.plot(alphas, alpha_cons, 's-', label='α_conservative (Re<1)', markersize=8, linewidth=2)
    ax.plot(alphas, alphas, 'k--', label='α_test', linewidth=1, alpha=0.5)
    ax.set_xlabel('α tested')
    ax.set_ylabel('α required for stability')
    ax.set_title('Minimum Stable Alpha')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Plot 2: Max Re_grid vs alpha
    ax = axes[0, 1]
    max_res = [results_dict[a]['max_re'] for a in alphas]
    ax.plot(alphas, max_res, 'o-', markersize=8, linewidth=2, color='red')
    ax.axhline(2.0, color='orange', linestyle='--', label='Stability limit (Re=2)', linewidth=2)
    ax.axhline(1.0, color='green', linestyle='--', label='Conservative (Re=1)', linewidth=2)
    ax.set_xlabel('α')
    ax.set_ylabel('Max Grid Reynolds Number')
    ax.set_title('Maximum Re_grid vs Alpha')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Plot 3: Time when max Re occurs
    ax = axes[1, 0]
    max_times = [results_dict[a]['max_time_days'] for a in alphas]
    ax.plot(alphas, max_times, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel('α')
    ax.set_ylabel('Time of max Re (days)')
    ax.set_title('When Does Maximum Re Occur?')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    # Plot 4: Depth where max Re occurs
    ax = axes[1, 1]
    max_depths = [np.abs(results_dict[a]['max_depth']) for a in alphas]
    ax.plot(alphas, max_depths, 'o-', markersize=8, linewidth=2)
    ax.set_xlabel('α')
    ax.set_ylabel('Depth of max Re (m)')
    ax.set_title('Where Does Maximum Re Occur?')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    plt.tight_layout()
    output_file = PKG_DIR / 'visualizations' / f'alpha_min_analysis_{scenario_name}.png'
    output_file.parent.mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nSaved: {output_file}")
    plt.close()


def main():
    """Compute minimum stable alpha."""
    scenario_name = 'arctic_convection'

    print(f"\n{'#'*70}")
    print(f"# MINIMUM STABLE ALPHA ANALYSIS")
    print(f"# Scenario: {scenario_name}")
    print(f"{'#'*70}\n")

    # Test multiple alpha values
    alphas_to_test = [1.0, 5.0, 10.0, 20.0, 30.0, 50.0]
    results_dict = {}

    for alpha in alphas_to_test:
        print(f"Testing α={alpha:.1f}...")
        results = run_scenario(scenario_name, alpha)
        analysis = compute_alpha_min_from_results(results, alpha)
        results_dict[alpha] = analysis

        print(f"  dt:                  {analysis['dt']:.1f} s")
        print(f"  Max Re_grid:         {analysis['max_re']:.2f}")
        print(f"  α_min (Re<2):        {analysis['alpha_min']:.2f}")
        print(f"  α_conservative (Re<1): {analysis['alpha_conservative']:.2f}")
        print(f"  Max at t={analysis['max_time_days']:.1f} days, z={analysis['max_depth']:.1f} m")
        print(f"  κ_e at max:          {analysis['max_kappa_e']:.2e} m²/s")

        if analysis['max_re'] < 2.0:
            print(f"  ✓ STABLE (Re < 2)")
        else:
            print(f"  ✗ UNSTABLE (Re > 2)")
        print()

    # Create plots
    print("Creating analysis plots...")
    plot_alpha_min_analysis(results_dict, scenario_name)

    # Final summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    # Find first stable alpha
    stable_alphas = [a for a, r in results_dict.items() if r['max_re'] < 2.0]
    if stable_alphas:
        min_stable = min(stable_alphas)
        print(f"Minimum stable α (tested): {min_stable:.1f}")
        print(f"  Max Re_grid: {results_dict[min_stable]['max_re']:.2f}")
    else:
        print("⚠ No tested alpha was stable!")
        # Extrapolate
        alpha1_data = results_dict[1.0]
        predicted_min = alpha1_data['alpha_min']
        print(f"Predicted α_min from α=1.0 data: {predicted_min:.1f}")

    print(f"\nStability criterion: Re_grid = Δz²/(α·κ_m·Δt) < 2")
    print(f"\nα_min depends on:")
    print(f"  1. (Δz)² - grid spacing squared (quadratic!)")
    print(f"  2. 1/Δt  - inversely proportional to time step")
    print(f"  3. 1/κ_m - inversely proportional to eddy viscosity")
    print(f"\nMost restrictive: deep water with weak mixing (small κ_m)")

    print("\nDone!")


if __name__ == '__main__':
    main()
