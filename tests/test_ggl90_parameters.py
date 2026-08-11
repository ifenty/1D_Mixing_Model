"""
Quick diagnostic: Compare GGL90 arctic_convection with default vs. ECCOv4r4 parameters.
"""

import sys
import os
from pathlib import Path
import numpy as np

PKG_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = PKG_DIR.parent
SCENARIO_DIR = PKG_DIR / "simulations" / "scenarios"
CONFIG_DIR = PKG_DIR / "configuration_yamls"
PHYSICAL_YAML = CONFIG_DIR / "physical_parameters.yaml"
GGL90_ECCOV4R4_YAML = CONFIG_DIR / "ggl90_eccov4r4.yaml"
GGL90_DEFAULT_YAML = PKG_DIR / "GGL90_ML" / "GGL90_PY" / "ggl90_default_parameters.yaml"

os.environ["KPP_PHYSICAL_PARAMETERS_YAML"] = str(PHYSICAL_YAML)
sys.path.insert(0, str(PKG_DIR))

from main import UnifiedColumnDriver, ConfigManager, GGL90Adapter
from GGL90_ML.GGL90_PY.ggl90_parameters import GGL90Parameters


def run_arctic_with_params(ggl90_yaml_path):
    """Run arctic_convection with specified GGL90 parameters."""
    # Load scenario configs
    ic_file = SCENARIO_DIR / "scenario_arctic_convection_initial_conditions.yaml"
    atm_file = SCENARIO_DIR / "scenario_arctic_convection_atmospheric_forcing.yaml"
    time_file = SCENARIO_DIR / "scenario_arctic_convection_time_integration.yaml"
    
    cfg_mgr = ConfigManager(ic_file, atm_file, time_file)
    cfg_mgr.load_all()
    
    # Create unified driver with GGL90 using specified parameters
    ggl90_params = GGL90Parameters.from_yaml(ggl90_yaml_path)
    
    driver = UnifiedColumnDriver(
        initial_conditions=cfg_mgr.initial_conditions,
        atmospheric_forcing=cfg_mgr.atmospheric_forcing,
        time_integration=cfg_mgr.time_integration,
        ggl90_parameters=ggl90_params,
        scheme='ggl90',
        physical_parameters_yaml=str(PHYSICAL_YAML),
    )
    
    # Run for 51 steps (output every 100 model steps, matching the test)
    results = {'theta': [], 'salt': [], 'visc_az': [], 'diff_kz_t': []}
    
    for step in range(5100):  # 51 * 100
        driver.step()
        
        if step % 100 == 0:
            results['theta'].append(driver.state.theta.copy())
            results['salt'].append(driver.state.salt.copy())
            results['visc_az'].append(driver.mixing_state.visc_az.max())
            results['diff_kz_t'].append(driver.mixing_state.diff_kz_t.max())
    
    return {
        'theta': np.array(results['theta']),
        'salt': np.array(results['salt']),
        'visc_max': np.array(results['visc_az']),
        'diff_max': np.array(results['diff_kz_t']),
    }


if __name__ == '__main__':
    print("Running arctic_convection with DEFAULT GGL90 parameters...")
    result_default = run_arctic_with_params(GGL90_DEFAULT_YAML)
    
    print("Running arctic_convection with ECCOv4r4 GGL90 parameters...")
    result_eccov4r4 = run_arctic_with_params(GGL90_ECCOV4R4_YAML)
    
    print("\n" + "="*70)
    print("COMPARISON: DEFAULT vs. ECCOv4r4 Parameters")
    print("="*70)
    
    # Compare surface temperature evolution
    print("\nSurface Temperature Evolution (°C):")
    print(f"{'Hour':<10} {'DEFAULT':<15} {'ECCOv4r4':<15} {'Diff':<10}")
    print("-" * 50)
    for i in [0, 5, 10, 25, 50]:
        if i < len(result_default['theta']):
            t_default = result_default['theta'][i, 0]
            t_eccov4r4 = result_eccov4r4['theta'][i, 0]
            hour = i * 100 * 600 / 3600
            print(f"{hour:<10.1f} {t_default:<15.2f} {t_eccov4r4:<15.2f} {t_default - t_eccov4r4:<10.3f}")
    
    # Compare mixing intensity
    print("\nMax Viscosity Evolution (m²/s):")
    print(f"{'Hour':<10} {'DEFAULT':<15} {'ECCOv4r4':<15}")
    print("-" * 40)
    for i in [0, 5, 10, 25, 50]:
        if i < len(result_default['visc_max']):
            hour = i * 100 * 600 / 3600
            print(f"{hour:<10.1f} {result_default['visc_max'][i]:<15.2e} {result_eccov4r4['visc_max'][i]:<15.2e}")
    
    # Final profile comparison
    print("\nFinal Profile Comparison (t=833.3h):")
    print(f"{'Depth(m)':<10} {'DEFAULT T':<12} {'ECCOv4r4 T':<12}")
    print("-" * 35)
    for k in [0, 5, 10, 15, 20, 22]:
        if k < result_default['theta'].shape[1]:
            z = np.abs(driver.state.grid.depth[k])
            t_default = result_default['theta'][-1, k]
            t_eccov4r4 = result_eccov4r4['theta'][-1, k]
            print(f"{z:<10.1f} {t_default:<12.2f} {t_eccov4r4:<12.2f}")
