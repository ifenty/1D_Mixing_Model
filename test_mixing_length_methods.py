#!/usr/bin/env python3
"""
Test different GGL90 mixing length criteria to diagnose MLD behavior.

Runs arctic_convection with mxl_max_flag = 0, 1, 2 to see how mixing length
method affects the resulting MLD and temperature profiles.
"""

import sys
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Setup paths
PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parent
SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
CONFIG_DIR = PKG_DIR / "configuration_yamls"
PHYSICAL_YAML = CONFIG_DIR / "physical_parameters.yaml"

os.environ["KPP_PHYSICAL_PARAMETERS_YAML"] = str(PHYSICAL_YAML)
sys.path.insert(0, str(PKG_DIR))

from main import (
    UnifiedColumnDriver,
    ConfigManager,
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


def run_scenario_with_mxl_flag(scenario_name: str, mxl_max_flag: int) -> dict:
    """
    Run a scenario with specific mixing length criteria.
    
    Args:
        scenario_name: Name of scenario (e.g., 'arctic_convection')
        mxl_max_flag: Mixing length flag (0, 1, 2)
    
    Returns:
        Dictionary with time series: time, theta, salt, visc_az, diff_kz_t, depth
    """
    from main import GGL90Adapter
    
    # Load configuration
    config_mgr = get_config_manager(scenario_name)
    physical = config_mgr.load_physical_parameters()
    
    # Create GGL90 parameters with specified mixing length method
    params = GGL90Parameters()
    params.alpha = 1.0  # Use default alpha
    params.tke_min = 1.0e-11
    params.mxl_max_flag = mxl_max_flag
    params.mxl_surf_flag = False  # Disable surface enforcement for clarity
    
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
    """
    Compute MLD time series based on density gradient.
    
    Args:
        depth: Depth levels (nz,) [m, positive downward]
        theta: Temperature array (ntime, nz) [°C]
        salt: Salinity array (ntime, nz) [PSU]
        drho_dz_threshold: Density gradient threshold [kg/m⁴]
        rho_const: Reference density [kg/m³]
    
    Returns:
        MLD time series (ntime,) [m]
    """
    ntime = theta.shape[0]
    mld = np.zeros(ntime)
    
    for t in range(ntime):
        # Convert depth to pressure (dbar, roughly 1 dbar per 10 m)
        pressure = -depth
        
        # Compute density using JMD95 EOS - returns (rho, ttalpha, ssbeta)
        eos_result = jmd95_eos(theta[t, :], salt[t, :], pressure, rho_const=rho_const)
        rho = eos_result[0] if isinstance(eos_result, tuple) else eos_result
        
        # Compute density gradient
        drho_dz = compute_density_gradient(rho, depth)
        
        # Find MLD as first depth where |dρ/dz| > threshold
        mld_indices = np.where(np.abs(drho_dz) > drho_dz_threshold)[0]
        
        if len(mld_indices) > 0:
            k_mld = mld_indices[0]
            # Linear interpolation for smoother MLD
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
            mld[t] = depth[-1]  # Full column
    
    return mld


def plot_comparison(results: dict, scenario_name: str):
    """
    Create comparison plots for different mixing length methods.
    
    Args:
        results: Dictionary mapping mxl_max_flag -> result dict
        scenario_name: Name of scenario for title
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'GGL90 Mixing Length Method Comparison: {scenario_name}', fontsize=14, fontweight='bold')
    
    # Plot 1: MLD time series
    ax = axes[0, 0]
    for flag, result in results.items():
        mld_ts = compute_density_mld(
            result['depth'],
            result['theta'],
            result['salt']
        )
        time_days = result['time'] / 86400.0
        ax.plot(time_days, mld_ts, 'o-', label=f'mxl_max_flag={flag}', markersize=4)
    
    ax.set_xlabel('Time (days)')
    ax.set_ylabel('MLD (m)')
    ax.set_title('MLD Time Series')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Final temperature profile comparison
    ax = axes[0, 1]
    depth = results[0]['depth']
    final_idx = -1
    
    for flag, result in results.items():
        theta_final = result['theta'][final_idx, :]
        ax.plot(theta_final, depth, 's-', label=f'mxl_max_flag={flag}', markersize=4)
    
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Temperature Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Viscosity at final time
    ax = axes[1, 0]
    for flag, result in results.items():
        visc_final = result['visc_az'][final_idx, :]
        ax.semilogy(visc_final + 1e-10, depth, 's-', label=f'mxl_max_flag={flag}', markersize=4)
    
    ax.set_xlabel('Viscosity (m²/s)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Viscosity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3, which='both')
    
    # Plot 4: Salinity at final time
    ax = axes[1, 1]
    for flag, result in results.items():
        salt_final = result['salt'][final_idx, :]
        ax.plot(salt_final, depth, 's-', label=f'mxl_max_flag={flag}', markersize=4)
    
    ax.set_xlabel('Salinity (PSU)')
    ax.set_ylabel('Depth (m)')
    ax.invert_yaxis()
    ax.set_title('Final Salinity Profile')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = PKG_DIR / 'visualizations' / f'mixing_length_comparison_{scenario_name}.png'
    output_file.parent.mkdir(exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}")
    plt.close()


def main():
    """Run comparison of mixing length methods."""
    scenario_name = 'arctic_convection'
    print(f"\nTesting mixing length criteria for: {scenario_name}")
    print("=" * 70)
    
    results = {}
    
    for mxl_flag in [0, 1, 2]:
        print(f"\nRunning with mxl_max_flag={mxl_flag}...")
        try:
            result = run_scenario_with_mxl_flag(scenario_name, mxl_flag)
            results[mxl_flag] = result
            
            # Print summary
            mld_ts = compute_density_mld(result['depth'], result['theta'], result['salt'])
            print(f"  Initial MLD: {mld_ts[0]:.1f} m")
            print(f"  Final MLD:   {mld_ts[-1]:.1f} m")
            print(f"  Final SST:   {result['theta'][-1, 0]:.2f} °C")
            print(f"  Final bottom T: {result['theta'][-1, -1]:.2f} °C")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    if len(results) > 1:
        print("\nCreating comparison plots...")
        plot_comparison(results, scenario_name)
        print("\nDone!")
    else:
        print("\nNot enough successful runs for comparison.")


if __name__ == '__main__':
    main()
