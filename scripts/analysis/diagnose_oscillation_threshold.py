#!/usr/bin/env python3
"""
Diagnose the exact cause of TKE oscillations and find minimum alpha threshold.

Since diffusion is implicit, oscillations are a NUMERICAL ACCURACY issue, not stability.

Hypothesis: With small α, TKE stays localized in cells, creating sharp gradients that
the finite-difference discretization cannot resolve smoothly.

Tests:
1. Measure oscillation amplitude vs alpha
2. Check TKE gradient length scale vs grid spacing
3. Identify threshold where oscillations become negligible
4. Diagnose physical mechanism
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
from GGL90_ML.GGL90_PY.ggl90_core_driver import GGL90Driver
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters


def compute_oscillation_metrics(field: np.ndarray) -> dict:
    """
    Compute multiple oscillation metrics for a vertical profile.

    Args:
        field: 1D array (vertical profile)

    Returns:
        dict with oscillation metrics
    """
    if len(field) < 3:
        return {'roughness': 0.0, 'max_gradient_ratio': 0.0, 'oscillation_count': 0}

    # Metric 1: Roughness (sum of absolute second differences)
    # d²f/dz² ≈ f[k+1] - 2*f[k] + f[k-1]
    second_diff = field[2:] - 2*field[1:-1] + field[:-2]
    roughness = np.sum(np.abs(second_diff))

    # Metric 2: Maximum gradient reversal ratio
    # Measures sharpness of direction changes
    first_diff = np.diff(field)
    if len(first_diff) > 1:
        # Look for sign changes (oscillations)
        sign_changes = np.diff(np.sign(first_diff))
        oscillation_count = np.sum(np.abs(sign_changes) > 0)

        # Ratio of consecutive gradient magnitudes
        grad_ratios = np.abs(first_diff[1:] / (first_diff[:-1] + 1e-20))
        max_gradient_ratio = np.max(grad_ratios) if len(grad_ratios) > 0 else 0.0
    else:
        oscillation_count = 0
        max_gradient_ratio = 0.0

    # Metric 3: Normalized variation (like coefficient of variation)
    mean_val = np.mean(np.abs(field[field != 0]))
    if mean_val > 1e-20:
        normalized_roughness = roughness / (mean_val * len(field))
    else:
        normalized_roughness = 0.0

    return {
        'roughness': roughness,
        'normalized_roughness': normalized_roughness,
        'max_gradient_ratio': max_gradient_ratio,
        'oscillation_count': oscillation_count,
    }


def compute_gradient_length_scale(field: np.ndarray, depth: np.ndarray) -> float:
    """
    Compute characteristic length scale of vertical gradients.

    Length scale L = |f| / |df/dz|

    Small L compared to Δz → under-resolved gradient → oscillations
    """
    dz = np.abs(np.diff(depth))
    dz = np.concatenate([[dz[0]], dz])

    # Compute gradient
    df_dz = np.gradient(field, depth)

    # Compute local length scale
    length_scales = []
    for k in range(len(field)):
        if np.abs(df_dz[k]) > 1e-10 and np.abs(field[k]) > 1e-10:
            L = np.abs(field[k]) / np.abs(df_dz[k])
            length_scales.append(L)

    length_scales = np.array(length_scales)
    if len(length_scales) > 0:
        min_length_scale = np.min(length_scales)
        median_length_scale = np.median(length_scales)
        # Fraction of sampled layers whose gradient is under-resolved (L < 2*dz).
        under_resolved_fraction = float(np.mean(length_scales < 2.0 * np.mean(dz)))
    else:
        min_length_scale = np.inf
        median_length_scale = np.inf
        under_resolved_fraction = 0.0

    # Resolution ratio uses the MEDIAN length scale: the minimum is dominated by
    # a single sharp transition point in a TKE profile spanning many orders of
    # magnitude, which makes it ~0 regardless of alpha and thus uninformative.
    return {
        'min_length_scale': min_length_scale,
        'median_length_scale': median_length_scale,
        'grid_spacing_mean': np.mean(dz),
        'resolution_ratio': median_length_scale / np.mean(dz),  # median-based; should be >~ 1
        'min_resolution_ratio': min_length_scale / np.mean(dz),  # kept for reference
        'under_resolved_fraction': under_resolved_fraction,
    }


def run_scenario(scenario_name: str, alpha: float) -> dict:
    """Run scenario and return full diagnostics."""
    config_mgr = ConfigManager(
        config_dir=SCENARIO_DIR,
        prefix=f"scenario_{scenario_name}_",
        physical_params_path=PHYSICAL_YAML,
    )
    physical = config_mgr.load_physical_parameters()

    params = GGL90Parameters()
    params.alpha = alpha
    params.tke_min = 1.0e-11

    adapter = GGL90Adapter(GGL90Driver(params), physical)
    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    results = driver.run_experiment(output_path=None)

    diag = results['diagnostics']
    time = diag['time_seconds']
    theta = diag['theta']
    visc_az = diag.get('visc_az', np.zeros_like(theta))
    tke = diag.get('tke', np.zeros_like(theta))

    n_levels = theta.shape[1]
    depth = driver.grid.depth if hasattr(driver, 'grid') and driver.grid else np.linspace(0, 500, n_levels)

    return {
        'time': time,
        'visc_az': visc_az,
        'tke': tke,
        'depth': depth,
        'alpha': alpha,
    }


def analyze_oscillations(results: dict) -> dict:
    """Analyze oscillations in TKE and mixing coefficients."""
    depth = results['depth']
    tke = results['tke']
    visc = results['visc_az']

    # Analyze final time step
    tke_final = tke[-1, :]
    visc_final = visc[-1, :]

    # Compute oscillation metrics
    tke_metrics = compute_oscillation_metrics(tke_final)
    visc_metrics = compute_oscillation_metrics(visc_final)

    # Compute gradient length scales
    tke_length_scale = compute_gradient_length_scale(tke_final, depth)
    visc_length_scale = compute_gradient_length_scale(visc_final, depth)

    # Temporal analysis: does oscillation grow or persist?
    tke_roughness_history = []
    for t in range(len(results['time'])):
        metrics = compute_oscillation_metrics(tke[t, :])
        tke_roughness_history.append(metrics['roughness'])

    return {
        'tke_roughness': tke_metrics['roughness'],
        'tke_normalized_roughness': tke_metrics['normalized_roughness'],
        'tke_oscillation_count': tke_metrics['oscillation_count'],
        'tke_max_gradient_ratio': tke_metrics['max_gradient_ratio'],
        'tke_length_scale': tke_length_scale,
        'visc_roughness': visc_metrics['roughness'],
        'visc_normalized_roughness': visc_metrics['normalized_roughness'],
        'visc_oscillation_count': visc_metrics['oscillation_count'],
        'visc_max_gradient_ratio': visc_metrics['max_gradient_ratio'],
        'visc_length_scale': visc_length_scale,
        'tke_roughness_history': tke_roughness_history,
    }


def plot_comprehensive_diagnosis(results_dict: dict, scenario_name: str):
    """Create comprehensive diagnostic plots."""
    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle(f'Oscillation Diagnosis (Implicit Diffusion): {scenario_name}',
                 fontsize=14, fontweight='bold')

    alphas = sorted(results_dict.keys())

    # Plot 1: TKE roughness vs alpha
    ax = fig.add_subplot(gs[0, 0])
    roughnesses = [results_dict[a]['analysis']['tke_roughness'] for a in alphas]
    ax.plot(alphas, roughnesses, 'o-', markersize=8, linewidth=2, color='red')
    ax.set_xlabel('α')
    ax.set_ylabel('TKE Roughness (Σ|d²TKE/dz²|)')
    ax.set_title('Oscillation Amplitude vs Alpha')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Add threshold line (10% of max)
    threshold = max(roughnesses) * 0.1
    ax.axhline(threshold, color='green', linestyle='--', label=f'10% threshold', linewidth=2)
    ax.legend()

    # Plot 2: Normalized roughness (fair comparison across alphas)
    ax = fig.add_subplot(gs[0, 1])
    norm_rough = [results_dict[a]['analysis']['tke_normalized_roughness'] for a in alphas]
    ax.plot(alphas, norm_rough, 'o-', markersize=8, linewidth=2, color='blue')
    ax.set_xlabel('α')
    ax.set_ylabel('Normalized Roughness')
    ax.set_title('Relative Oscillation Intensity')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Plot 3: Oscillation count
    ax = fig.add_subplot(gs[0, 2])
    osc_counts = [results_dict[a]['analysis']['tke_oscillation_count'] for a in alphas]
    ax.plot(alphas, osc_counts, 'o-', markersize=8, linewidth=2, color='purple')
    ax.set_xlabel('α')
    ax.set_ylabel('Number of Sign Reversals')
    ax.set_title('Oscillation Count in Vertical Profile')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    # Plot 4: TKE profiles for low alphas
    ax = fig.add_subplot(gs[1, 0])
    for alpha in [a for a in alphas if a <= 10.0]:
        res = results_dict[alpha]['results']
        depth = res['depth']
        tke_final = res['tke'][-1, :] * 1e4
        ax.plot(tke_final, np.abs(depth), 'o-', label=f'α={alpha:.1f}', markersize=4)
    ax.set_xlabel('TKE (cm²/s²)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Profiles (Low Alpha)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 5: TKE profiles for high alphas
    ax = fig.add_subplot(gs[1, 1])
    for alpha in [a for a in alphas if a >= 15.0]:
        res = results_dict[alpha]['results']
        depth = res['depth']
        tke_final = res['tke'][-1, :] * 1e4
        ax.plot(tke_final, np.abs(depth), 's-', label=f'α={alpha:.1f}', markersize=4)
    ax.set_xlabel('TKE (cm²/s²)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Profiles (High Alpha)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 6: TKE second derivative (shows oscillations directly)
    ax = fig.add_subplot(gs[1, 2])
    for alpha in [1.0, 5.0, 10.0, 30.0]:
        if alpha in results_dict:
            res = results_dict[alpha]['results']
            depth = res['depth']
            tke_final = res['tke'][-1, :] * 1e4
            tke_2nd = tke_final[2:] - 2*tke_final[1:-1] + tke_final[:-2]
            ax.plot(tke_2nd, np.abs(depth[1:-1]), 'o-', label=f'α={alpha:.1f}', markersize=4)
    ax.axvline(0, color='k', linestyle='--', alpha=0.5)
    ax.set_xlabel('d²TKE/dz² (cm²/s²/m²)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('TKE Second Derivative (Oscillation Indicator)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 7: Gradient length scale vs grid spacing
    ax = fig.add_subplot(gs[2, 0])
    resolution_ratios = [results_dict[a]['analysis']['tke_length_scale']['resolution_ratio']
                         for a in alphas]
    ax.plot(alphas, resolution_ratios, 'o-', markersize=8, linewidth=2, color='green')
    ax.axhline(2.0, color='orange', linestyle='--', label='Well-resolved (L/Δz=2)', linewidth=2)
    ax.axhline(1.0, color='red', linestyle='--', label='Marginally resolved (L/Δz=1)', linewidth=2)
    ax.set_xlabel('α')
    ax.set_ylabel('L_gradient / Δz')
    ax.set_title('Gradient Resolution Ratio\n(Higher = Better Resolved)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Plot 8: Viscosity roughness vs alpha
    ax = fig.add_subplot(gs[2, 1])
    visc_rough = [results_dict[a]['analysis']['visc_roughness'] for a in alphas]
    ax.plot(alphas, visc_rough, 'o-', markersize=8, linewidth=2, color='brown')
    ax.set_xlabel('α')
    ax.set_ylabel('Viscosity Roughness')
    ax.set_title('Mixing Coefficient Oscillations')
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')
    ax.set_yscale('log')

    # Plot 9: Temporal evolution of oscillations
    ax = fig.add_subplot(gs[2, 2])
    for alpha in [1.0, 5.0, 10.0, 30.0]:
        if alpha in results_dict:
            res = results_dict[alpha]['results']
            time_days = res['time'] / 86400.0
            roughness_history = results_dict[alpha]['analysis']['tke_roughness_history']
            ax.plot(time_days, roughness_history, 'o-', label=f'α={alpha:.1f}', markersize=3)
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('TKE Roughness')
    ax.set_title('Temporal Evolution of Oscillations')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')

    # Plot 10: Viscosity profiles comparison
    ax = fig.add_subplot(gs[3, 0])
    for alpha in [1.0, 5.0, 10.0, 30.0]:
        if alpha in results_dict:
            res = results_dict[alpha]['results']
            depth = res['depth']
            visc_final = res['visc_az'][-1, :] * 1e4
            ax.plot(visc_final, np.abs(depth), 'o-', label=f'α={alpha:.1f}', markersize=4)
    ax.set_xlabel('Viscosity (cm²/s)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Viscosity Profiles')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.invert_yaxis()

    # Plot 11: Summary metrics heatmap
    ax = fig.add_subplot(gs[3, 1:])

    # Create summary table
    metrics_names = ['TKE Roughness', 'Normalized Roughness', 'Oscillation Count',
                     'Max Gradient Ratio', 'Resolution Ratio (L/Δz)']
    data = []
    for alpha in alphas:
        analysis = results_dict[alpha]['analysis']
        row = [
            analysis['tke_roughness'],
            analysis['tke_normalized_roughness'],
            analysis['tke_oscillation_count'],
            analysis['tke_max_gradient_ratio'],
            analysis['tke_length_scale']['resolution_ratio'],
        ]
        data.append(row)

    data = np.array(data).T

    # Normalize each metric to [0, 1] for color mapping
    data_norm = np.zeros_like(data)
    for i in range(len(metrics_names)):
        row_max = np.max(data[i])
        row_min = np.min(data[i])
        if row_max > row_min:
            data_norm[i] = (data[i] - row_min) / (row_max - row_min)

    im = ax.imshow(data_norm, cmap='RdYlGn_r', aspect='auto')
    ax.set_xticks(range(len(alphas)))
    ax.set_xticklabels([f'{a:.1f}' for a in alphas])
    ax.set_yticks(range(len(metrics_names)))
    ax.set_yticklabels(metrics_names)
    ax.set_xlabel('α')
    ax.set_title('Oscillation Metrics Heatmap\n(Red=Bad, Green=Good)')

    # Add text annotations
    for i in range(len(metrics_names)):
        for j in range(len(alphas)):
            text = ax.text(j, i, f'{data[i, j]:.1e}' if data[i, j] < 0.01 else f'{data[i, j]:.2f}',
                          ha="center", va="center", color="black", fontsize=8)

    plt.colorbar(im, ax=ax, label='Normalized Value (0=best, 1=worst)')

    plt.tight_layout()
    output_file = PKG_DIR / 'visualizations' / f'oscillation_threshold_diagnosis_{scenario_name}.png'
    output_file.parent.mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nSaved: {output_file}")
    plt.close()


def main():
    """Find minimum alpha threshold for oscillation-free solutions."""
    scenario_name = 'arctic_convection'

    print(f"\n{'#'*70}")
    print(f"# OSCILLATION THRESHOLD DIAGNOSIS (Implicit Diffusion)")
    print(f"# Scenario: {scenario_name}")
    print(f"{'#'*70}\n")

    print("Hypothesis: Oscillations are due to under-resolved TKE gradients")
    print("when alpha is too small, not numerical instability.\n")

    # Test fine-grained alpha range
    alphas_to_test = [1.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 50.0]
    results_dict = {}

    for alpha in alphas_to_test:
        print(f"Testing α={alpha:.1f}...")
        results = run_scenario(scenario_name, alpha)
        analysis = analyze_oscillations(results)
        results_dict[alpha] = {
            'results': results,
            'analysis': analysis,
        }

        print(f"  TKE roughness:           {analysis['tke_roughness']:.2e}")
        print(f"  Normalized roughness:    {analysis['tke_normalized_roughness']:.3f}")
        print(f"  Oscillation count:       {analysis['tke_oscillation_count']}")
        ls = analysis['tke_length_scale']
        print(f"  Median L/Δz:             {ls['resolution_ratio']:.2f}  (min L/Δz={ls['min_resolution_ratio']:.3f})")
        print(f"  Under-resolved fraction: {ls['under_resolved_fraction']:.2f}")
        print()

    # Create comprehensive diagnostic plot
    print("Creating diagnostic plots...")
    plot_comprehensive_diagnosis(results_dict, scenario_name)

    # Find threshold
    print(f"\n{'='*70}")
    print("THRESHOLD ANALYSIS")
    print(f"{'='*70}\n")

    # Method 1: 10% of maximum oscillation amplitude
    roughnesses = [(a, results_dict[a]['analysis']['tke_roughness']) for a in alphas_to_test]
    max_rough = max(r[1] for r in roughnesses)
    threshold_10pct = max_rough * 0.1

    print(f"Maximum TKE roughness: {max_rough:.2e} (α={roughnesses[0][0]:.1f})")
    print(f"10% threshold:         {threshold_10pct:.2e}")
    print()

    alpha_threshold_rough = None
    for alpha, rough in roughnesses:
        if rough <= threshold_10pct:
            alpha_threshold_rough = alpha
            print(f"✓ First α with roughness < 10% max: α={alpha:.1f} (roughness={rough:.2e})")
            break

    # Method 2: Resolution ratio (median-based) + under-resolved fraction
    print("\nResolution Ratio (median L_gradient / Δz) and under-resolved fraction:")
    for alpha in alphas_to_test:
        ls = results_dict[alpha]['analysis']['tke_length_scale']
        ratio = ls['resolution_ratio']
        frac = ls['under_resolved_fraction']
        status = "✓" if ratio >= 2.0 else ("⚠" if ratio >= 1.0 else "✗")
        print(f"  α={alpha:5.1f}:  median L/Δz = {ratio:6.2f}  {status}   under-resolved={frac:.2f}")

    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)

    if alpha_threshold_rough:
        print(f"\nMinimum α for oscillation-free solution: {alpha_threshold_rough:.1f}")
        print(f"\nWith implicit diffusion, oscillations arise from:")
        print(f"  1. TKE gradients too sharp to be resolved on the grid")
        print(f"  2. Gradient length scale L < ~2×Δz (under-resolved)")
        print(f"  3. Finite-difference truncation errors manifest as oscillations")
        print(f"\nECCOv4's α=30 provides:")
        print(f"  - Safety factor of {30.0/alpha_threshold_rough:.1f}× above threshold")
        print(f"  - Smooth, well-resolved TKE profiles")
        print(f"  - No numerical artifacts")
    else:
        print("\nAll tested alphas still show some oscillations.")
        print("Threshold may be > 50.")

    print("\nDone!")


if __name__ == '__main__':
    main()
