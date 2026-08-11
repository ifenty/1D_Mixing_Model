#!/usr/bin/env python3
"""
Test different GGL90 alpha values to identify the real culprit.

Tests alpha=1.0 (default) vs alpha=30.0 (ECCOv4r4) with same mixing length method.
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Setup paths
PKG_DIR = Path(__file__).resolve().parent.parent
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


def run_scenario_with_alpha(scenario_name: str, alpha: float, mxl_max_flag: int = 0, mxl_surf_flag: bool = False) -> dict:
    """
    Run a scenario with specific alpha and mixing length method.
    
    Args:
        scenario_name: Name of scenario (e.g., 'arctic_convection')
        alpha: TKE diffusivity multiplier
        mxl_max_flag: Mixing length flag (0, 1, 2)
        mxl_surf_flag: Whether to enforce surface layer mixing
    
    Returns:
        Dictionary with time series: time, theta, salt, visc_az, depth
    """
    # Load configuration
    config_mgr = get_config_manager(scenario_name)
    physical = config_mgr.load_physical_parameters()
    
    # Create GGL90 parameters with specified alpha
    params = GGL90Parameters()
    params.alpha = alpha
    params.tke_min = 1.0e-11 if alpha < 10.0 else 1.0e-7
    params.mxl_max_flag = mxl_max_flag
    params.mxl_surf_flag = mxl_surf_flag
    
    # Setup adapter
    adapter = GGL90Adapter(GGL90Driver(params), physical)
    
    # Create driver and run
    driver = UnifiedColumnDriver(adapter, config_mgr, physical)
    results = driver.run_experiment(output_path=None)
    
    # Extract diagnostics
    diag = results['diagnostics']
    
    time = diag['time_seconds']
    theta = diag['theta']
    salt = diag['salt']
    visc_az = diag.get('visc_az', np.zeros_like(theta))
    diff_kz_t = diag.get('diff_kz_t', np.zeros_like(theta))
    
    # Get depth
    n_levels = theta.shape[1]
    depth = driver.grid.depth if hasattr(driver, 'grid') and driver.grid else np.linspace(0, 500, n_levels)
    
    return {
        'time': time,
        'theta': theta,
        'salt': salt,
        'visc_az': visc_az,
        'diff_kz_t': diff_kz_t,
        'depth': depth,
    }


def compute_density_mld(depth: np.ndarray, theta: np.ndarray, salt: np.ndarray,
                       drho_dz_threshold: float = 0.02, rho_const: float = 1029.0) -> np.ndarray:
    """Compute MLD time series based on density gradient."""
    ntime = theta.shape[0]
    mld = np.zeros(ntime)
    
    for t in range(ntime):
        pressure = -depth
        eos_result = jmd95_eos(theta[t, :], salt[t, :], pressure, rho_const=rho_const)
        rho = eos_result[0] if isinstance(eos_result, tuple) else eos_result
        drho_dz = compute_density_gradient(rho, depth)
        
        mld_indices = np.where(np.abs(drho_dz) > drho_dz_threshold)[0]
        
        if len(mld_indices) > 0:
            k_mld = mld_indices[0]
            if k_mld < len(depth) - 1:
                grad_curr = np.abs(drho_dz[k_mld])
                grad_prev = np.abs(drho_dz[k_mld-1]) if k_mld > 0 else drho_dz_threshold
                
                if grad_curr > drho_dz_threshold and grad_prev <= drho_dz_threshold:
                    frac = (drho_dz_threshold - grad_prev) / (grad_curr - grad_prev + 1e-12)
                    mld[t] = depth[k_mld-1] + frac * (depth[k_mld] - depth[k_mld-1])
                else:
                    mld[t] = depth[k_mld]
            else:
                mld[t] = depth[k_mld]
        else:
            mld[t] = depth[-1]
    
    return mld


def plot_alpha_comparison(results: dict, scenario_name: str):
    """Create comparison plots for different alpha values."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'GGL90 Alpha Parameter Comparison: {scenario_name}', fontsize=14, fontweight='bold')

    # Create labels dynamically based on keys
    labels = {}
    for key in results.keys():
        alpha, mxl_flag, mxl_surf = key
        labels[key] = f"α={alpha:.1f}"
    
    # Plot 1: MLD time series
    ax = axes[0, 0]
    for key, result in results.items():
        mld_ts = compute_density_mld(result['depth'], result['theta'], result['salt'])
        time_days = result['time'] / 86400.0
        label = labels.get(key, f"α={key[0]}")
        ax.plot(time_days, np.abs(mld_ts), 'o-', label=label, markersize=4)
    
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('MLD (m)')
    ax.set_title('MLD Time Series')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Final temperature profile
    ax = axes[0, 1]
    depth = results[list(results.keys())[0]]['depth']
    final_idx = -1
    
    for key, result in results.items():
        theta_final = result['theta'][final_idx, :]
        label = labels.get(key, f"α={key[0]}")
        ax.plot(theta_final, np.abs(depth), 's-', label=label, markersize=4)
    
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Temperature Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Final viscosity profile
    ax = axes[1, 0]
    for key, result in results.items():
        visc_final = result['visc_az'][final_idx, :]
        label = labels.get(key, f"α={key[0]}")
        ax.semilogy(visc_final + 1e-10, np.abs(depth), 's-', label=label, markersize=4)
    
    ax.set_xlabel('Viscosity (m²/s)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Viscosity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3, which='both')
    
    # Plot 4: Final diffusivity profile
    ax = axes[1, 1]
    for key, result in results.items():
        diff_final = result['diff_kz_t'][final_idx, :]
        label = labels.get(key, f"α={key[0]}")
        ax.semilogy(diff_final + 1e-10, np.abs(depth), 's-', label=label, markersize=4)
    
    ax.set_xlabel('Diffusivity (m²/s)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Thermal Diffusivity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3, which='both')
    
    plt.tight_layout()
    output_file = PKG_DIR / 'visualizations' / f'alpha_comparison_{scenario_name}.png'
    output_file.parent.mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()


def main():
    """Run comparison of alpha values."""
    scenario_name = 'arctic_convection'
    print(f"\nTesting alpha parameter for: {scenario_name}")
    print("=" * 70)

    results = {}

    # Test configurations - varying alpha with same mixing length method
    test_configs = [
        (1.0, 0, False, "α=1.0 (default)"),
        (10.0, 0, False, "α=10.0"),
        (30.0, 0, False, "α=30.0 (ECCOv4r4)"),
        (50.0, 0, False, "α=50.0"),
    ]
    
    for alpha, mxl_flag, mxl_surf, desc in test_configs:
        print(f"\nRunning: {desc}...")
        try:
            result = run_scenario_with_alpha(scenario_name, alpha, mxl_flag, mxl_surf)
            results[(alpha, mxl_flag, mxl_surf)] = result
            
            # Print summary
            mld_ts = compute_density_mld(result['depth'], result['theta'], result['salt'])
            final_mld = np.abs(mld_ts[-1])
            final_sst = result['theta'][-1, 0]
            final_visc_surface = result['visc_az'][-1, 0]
            final_diff_surface = result['diff_kz_t'][-1, 0]
            
            print(f"  ✓ Completed")
            print(f"    Final MLD:         {final_mld:7.1f} m")
            print(f"    Final SST:         {final_sst:7.2f} °C")
            print(f"    Final visc@surf:   {final_visc_surface:10.3e} m²/s")
            print(f"    Final diff@surf:   {final_diff_surface:10.3e} m²/s")
            
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    if len(results) > 1:
        print("\nCreating comparison plots...")
        plot_alpha_comparison(results, scenario_name)
        print("\nDone!")
    else:
        print("\nNot enough successful runs for comparison.")


if __name__ == '__main__':
    main()
