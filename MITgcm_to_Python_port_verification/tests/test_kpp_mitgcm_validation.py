"""
Test Python KPP implementation against MITgcm validation data.

Compares Python KPP port outputs to MITgcm reference outputs for:
- 1D_ocean_ice_column (single column, 10 timesteps)
- lab_sea (20x16 grid, 9 timesteps)

Requires:
- MITgcm validation runs completed (output.npz files exist)
- Run parse_mitgcm_kpp_validation.py first to generate npz files

Usage:
    pytest test_kpp_mitgcm_validation.py -v
    pytest test_kpp_mitgcm_validation.py::test_1d_ocean_ice_column_timestep_1 -v

Corresponds to:
- MITgcm: pkg/kpp/kpp_calc.F, pkg/kpp/kpp_routines.F
- Python: KPP/kpp_core_driver.py, KPP/kpp_routines.py
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / '1D_Mixing_Model'))

from KPP.kpp_core_driver import KPPDriver
from KPP.kpp_parameters import KPPParameters


# Path to parsed MITgcm validation data
MITGCM_VERIFICATION = Path('/Users/ifenty/git_repo_others/MITgcm/verification')
DATA_1D = MITGCM_VERIFICATION / '1D_ocean_ice_column' / 'output_validation' / 'output.npz'
DATA_LABSEA = MITGCM_VERIFICATION / 'lab_sea' / 'output_validation' / 'output.npz'


def load_mitgcm_data(npz_path: Path):
    """
    Load parsed MITgcm validation data.

    Returns:
        dict with keys:
            'grid': dict with nr, drF, rF, rC
            'timesteps': dict mapping timestep number to data dict
    """
    if not npz_path.exists():
        pytest.skip(f"MITgcm validation data not found: {npz_path}\n"
                   f"Run: python scripts/parse_mitgcm_kpp_validation.py")

    data = np.load(npz_path)

    grid = {
        'nr': int(data['grid_nr'][0]),
        'drF': data['grid_drF'],
        'rF': data['grid_rF'],
        'rC': data['grid_rC']
    }

    # Extract timesteps
    timesteps = {}
    timestep_nums = set()
    for key in data.files:
        if key.startswith('timestep_'):
            ts_str = key.split('_')[1]
            timestep_nums.add(int(ts_str))

    for ts_num in sorted(timestep_nums):
        prefix = f'timestep_{ts_num:03d}'
        timesteps[ts_num] = {
            'inputs': {
                'theta': data[f'{prefix}_input_theta'],
                'salt': data[f'{prefix}_input_salt'],
                'u': data[f'{prefix}_input_u'],
                'v': data[f'{prefix}_input_v'],
                'tau_x': data[f'{prefix}_input_tau_x'],
                'tau_y': data[f'{prefix}_input_tau_y'],
                'q_net': data[f'{prefix}_input_q_net'],
                'q_sw': data[f'{prefix}_input_q_sw'],
                'fw_flux': data[f'{prefix}_input_fw_flux'],
                'f_coriolis': data[f'{prefix}_input_f_coriolis']
            },
            'outputs': {
                'visc_az': data[f'{prefix}_output_visc_az'],
                'diff_kz_s': data[f'{prefix}_output_diff_kz_s'],
                'diff_kz_t': data[f'{prefix}_output_diff_kz_t'],
                'ghat': data[f'{prefix}_output_ghat'],
                'hbl': data[f'{prefix}_output_hbl'],
                'k_truncate': data[f'{prefix}_output_k_truncate']
            }
        }

    return {'grid': grid, 'timesteps': timesteps}


def get_kpp_parameters_for_experiment(experiment: str) -> KPPParameters:
    """
    Get KPP parameters matching MITgcm configuration.

    Args:
        experiment: '1d' or 'lab_sea'

    Returns:
        KPPParameters instance configured to match MITgcm data.kpp
    """
    # TODO: Parse actual data.kpp files from MITgcm
    # For now, use defaults (most KPP parameters are defaults in both experiments)

    params = KPPParameters()

    if experiment == '1d':
        # 1D_ocean_ice_column specific parameters (if any differ from defaults)
        pass

    elif experiment == 'lab_sea':
        # lab_sea specific parameters (if any differ from defaults)
        pass

    return params


def run_python_kpp_single_column(
    theta: np.ndarray,  # (nr,)
    salt: np.ndarray,   # (nr,)
    u: np.ndarray,      # (nr,)
    v: np.ndarray,      # (nr,)
    drF: np.ndarray,    # (nr,)
    rF: np.ndarray,     # (nr,)
    tau_x: float,
    tau_y: float,
    q_net: float,
    q_sw: float,
    fw_flux: float,
    f_coriolis: float,
    params: KPPParameters
) -> dict:
    """
    Run Python KPP on a single column.

    Returns:
        dict with keys matching KPPOutput:
            visc_az, diff_kz_s, diff_kz_t, ghat, hbl
    """
    driver = KPPDriver(params=params)

    # Compute KPP mixing
    output = driver.compute_mixing(
        theta=theta,
        salt=salt,
        u_vel=u,
        v_vel=v,
        depth=-rF,  # KPP expects positive-down depths
        cell_thickness=drF,
        tau_x=tau_x,
        tau_y=tau_y,
        q_net=q_net,
        q_sw=q_sw,
        fw_flux=fw_flux,
        f_coriolis=f_coriolis
    )

    return {
        'visc_az': output.visc_az,
        'diff_kz_s': output.diff_kz_s,
        'diff_kz_t': output.diff_kz_t,
        'ghat': output.ghat,
        'hbl': output.hbl
    }


def compare_kpp_outputs(
    python_output: dict,
    mitgcm_output: dict,
    rtol: float = 1e-12,
    atol: float = 1e-14
) -> dict:
    """
    Compare Python KPP outputs to MITgcm outputs.

    Args:
        python_output: dict with visc_az, diff_kz_s, diff_kz_t, ghat, hbl
        mitgcm_output: dict with same keys
        rtol: relative tolerance (default: 1e-12 for ~12 digits)
        atol: absolute tolerance (default: 1e-14)

    Returns:
        dict with comparison results for each variable:
            {varname: {'max_abs_err': float, 'max_rel_err': float, 'pass': bool}}
    """
    results = {}

    for varname in ['visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat']:
        py_val = python_output[varname]
        mit_val = mitgcm_output[varname]

        # Compute errors (ignoring NaNs from land points)
        abs_err = np.abs(py_val - mit_val)
        rel_err = abs_err / (np.abs(mit_val) + atol)

        max_abs_err = np.nanmax(abs_err)
        max_rel_err = np.nanmax(rel_err)

        # Check if pass (using np.allclose logic)
        passes = np.allclose(py_val, mit_val, rtol=rtol, atol=atol, equal_nan=True)

        results[varname] = {
            'max_abs_err': max_abs_err,
            'max_rel_err': max_rel_err,
            'pass': passes
        }

    # HBL (scalar)
    py_hbl = python_output['hbl']
    mit_hbl = mitgcm_output['hbl']

    if np.isnan(py_hbl) and np.isnan(mit_hbl):
        hbl_pass = True
        hbl_abs_err = 0.0
        hbl_rel_err = 0.0
    elif np.isnan(py_hbl) or np.isnan(mit_hbl):
        hbl_pass = False
        hbl_abs_err = np.nan
        hbl_rel_err = np.nan
    else:
        hbl_abs_err = abs(py_hbl - mit_hbl)
        hbl_rel_err = hbl_abs_err / (abs(mit_hbl) + atol)
        hbl_pass = np.isclose(py_hbl, mit_hbl, rtol=rtol, atol=atol)

    results['hbl'] = {
        'max_abs_err': hbl_abs_err,
        'max_rel_err': hbl_rel_err,
        'pass': hbl_pass
    }

    return results


# ========================================================================
# 1D_ocean_ice_column Tests
# ========================================================================

@pytest.fixture(scope='module')
def data_1d():
    """Load 1D_ocean_ice_column validation data once for all tests."""
    return load_mitgcm_data(DATA_1D)


@pytest.fixture(scope='module')
def kpp_params_1d():
    """KPP parameters for 1D_ocean_ice_column."""
    return get_kpp_parameters_for_experiment('1d')


@pytest.mark.parametrize('timestep', [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_1d_ocean_ice_column_timestep(data_1d, kpp_params_1d, timestep):
    """
    Test Python KPP against 1D_ocean_ice_column for single timestep.

    1D_ocean_ice_column is a single column (1x1x23), ideal for detailed validation.
    """
    grid = data_1d['grid']
    ts_data = data_1d['timesteps'][timestep]

    # Extract column data (single column: i=0, j=0)
    inputs = ts_data['inputs']
    mitgcm_outputs = ts_data['outputs']

    theta = inputs['theta'][0, 0, :]
    salt = inputs['salt'][0, 0, :]
    u = inputs['u'][0, 0, :]
    v = inputs['v'][0, 0, :]
    tau_x = inputs['tau_x'][0, 0]
    tau_y = inputs['tau_y'][0, 0]
    q_net = inputs['q_net'][0, 0]
    q_sw = inputs['q_sw'][0, 0]
    fw_flux = inputs['fw_flux'][0, 0]
    f_coriolis = inputs['f_coriolis'][0, 0]

    # Run Python KPP
    py_output = run_python_kpp_single_column(
        theta=theta, salt=salt, u=u, v=v,
        drF=grid['drF'], rF=grid['rF'],
        tau_x=tau_x, tau_y=tau_y,
        q_net=q_net, q_sw=q_sw, fw_flux=fw_flux,
        f_coriolis=f_coriolis,
        params=kpp_params_1d
    )

    # Prepare MITgcm outputs (extract column)
    mitgcm_output = {
        'visc_az': mitgcm_outputs['visc_az'][0, 0, :],
        'diff_kz_s': mitgcm_outputs['diff_kz_s'][0, 0, :],
        'diff_kz_t': mitgcm_outputs['diff_kz_t'][0, 0, :],
        'ghat': mitgcm_outputs['ghat'][0, 0, :],
        'hbl': mitgcm_outputs['hbl'][0, 0]
    }

    # Compare
    results = compare_kpp_outputs(py_output, mitgcm_output, rtol=1e-12)

    # Report
    print(f"\nTimestep {timestep} comparison:")
    for var, res in results.items():
        status = "✓ PASS" if res['pass'] else "✗ FAIL"
        print(f"  {var:12s}: {status}  max_abs_err={res['max_abs_err']:.2e}  "
              f"max_rel_err={res['max_rel_err']:.2e}")

    # Assert all pass
    failed_vars = [var for var, res in results.items() if not res['pass']]
    if failed_vars:
        pytest.fail(f"Timestep {timestep} failed for variables: {failed_vars}")


# ========================================================================
# lab_sea Tests
# ========================================================================

@pytest.fixture(scope='module')
def data_labsea():
    """Load lab_sea validation data once for all tests."""
    return load_mitgcm_data(DATA_LABSEA)


@pytest.fixture(scope='module')
def kpp_params_labsea():
    """KPP parameters for lab_sea."""
    return get_kpp_parameters_for_experiment('lab_sea')


@pytest.mark.parametrize('timestep', [1, 2, 3, 4, 5])
def test_lab_sea_sample_columns_timestep(data_labsea, kpp_params_labsea, timestep):
    """
    Test Python KPP against lab_sea for sample columns at given timestep.

    Tests 5 representative ocean columns (skips land points).
    Full grid validation would be 20×16=320 columns × 9 timesteps = 2,880 tests.
    """
    grid = data_labsea['grid']
    ts_data = data_labsea['timesteps'][timestep]

    # Sample columns (ocean points only, determined by inspecting maskC)
    # These are known ocean points from lab_sea grid
    sample_columns = [
        (5, 5),   # Ocean interior
        (10, 8),  # Ocean interior
        (15, 10), # Ocean interior
        (8, 12),  # Near boundary
        (12, 6)   # Near boundary
    ]

    failed_columns = []

    for i, j in sample_columns:
        inputs = ts_data['inputs']
        mitgcm_outputs = ts_data['outputs']

        # Skip if land point (NaN theta at surface)
        if np.isnan(inputs['theta'][i, j, 0]):
            continue

        # Extract column
        theta = inputs['theta'][i, j, :]
        salt = inputs['salt'][i, j, :]
        u = inputs['u'][i, j, :]
        v = inputs['v'][i, j, :]
        tau_x = inputs['tau_x'][i, j]
        tau_y = inputs['tau_y'][i, j]
        q_net = inputs['q_net'][i, j]
        q_sw = inputs['q_sw'][i, j]
        fw_flux = inputs['fw_flux'][i, j]
        f_coriolis = inputs['f_coriolis'][i, j]

        # Run Python KPP
        py_output = run_python_kpp_single_column(
            theta=theta, salt=salt, u=u, v=v,
            drF=grid['drF'], rF=grid['rF'],
            tau_x=tau_x, tau_y=tau_y,
            q_net=q_net, q_sw=q_sw, fw_flux=fw_flux,
            f_coriolis=f_coriolis,
            params=kpp_params_labsea
        )

        # Prepare MITgcm outputs
        mitgcm_output = {
            'visc_az': mitgcm_outputs['visc_az'][i, j, :],
            'diff_kz_s': mitgcm_outputs['diff_kz_s'][i, j, :],
            'diff_kz_t': mitgcm_outputs['diff_kz_t'][i, j, :],
            'ghat': mitgcm_outputs['ghat'][i, j, :],
            'hbl': mitgcm_outputs['hbl'][i, j]
        }

        # Compare
        results = compare_kpp_outputs(py_output, mitgcm_output, rtol=1e-12)

        # Check for failures
        column_failed = any(not res['pass'] for res in results.values())
        if column_failed:
            failed_columns.append((i, j, results))

    # Report
    print(f"\nTimestep {timestep} lab_sea sample columns:")
    print(f"  Tested {len(sample_columns)} columns")
    if failed_columns:
        print(f"  Failed: {len(failed_columns)} columns")
        for i, j, results in failed_columns:
            print(f"    Column ({i},{j}):")
            for var, res in results.items():
                if not res['pass']:
                    print(f"      {var:12s}: FAIL  max_abs_err={res['max_abs_err']:.2e}  "
                          f"max_rel_err={res['max_rel_err']:.2e}")
        pytest.fail(f"Timestep {timestep}: {len(failed_columns)} columns failed")
    else:
        print(f"  ✓ All columns passed")


def test_lab_sea_full_grid_timestep_1(data_labsea, kpp_params_labsea):
    """
    Test Python KPP against ALL lab_sea columns for timestep 1.

    Comprehensive validation: tests all 320 grid points (many are land).
    This is slow (~30-60 seconds) but provides complete coverage.
    """
    timestep = 1
    grid = data_labsea['grid']
    ts_data = data_labsea['timesteps'][timestep]

    inputs = ts_data['inputs']
    mitgcm_outputs = ts_data['outputs']

    nx, ny, nr = inputs['theta'].shape
    failed_columns = []
    tested_columns = 0

    for i in range(nx):
        for j in range(ny):
            # Skip land points
            if np.isnan(inputs['theta'][i, j, 0]):
                continue

            tested_columns += 1

            # Extract column
            theta = inputs['theta'][i, j, :]
            salt = inputs['salt'][i, j, :]
            u = inputs['u'][i, j, :]
            v = inputs['v'][i, j, :]
            tau_x = inputs['tau_x'][i, j]
            tau_y = inputs['tau_y'][i, j]
            q_net = inputs['q_net'][i, j]
            q_sw = inputs['q_sw'][i, j]
            fw_flux = inputs['fw_flux'][i, j]
            f_coriolis = inputs['f_coriolis'][i, j]

            # Run Python KPP
            py_output = run_python_kpp_single_column(
                theta=theta, salt=salt, u=u, v=v,
                drF=grid['drF'], rF=grid['rF'],
                tau_x=tau_x, tau_y=tau_y,
                q_net=q_net, q_sw=q_sw, fw_flux=fw_flux,
                f_coriolis=f_coriolis,
                params=kpp_params_labsea
            )

            # Prepare MITgcm outputs
            mitgcm_output = {
                'visc_az': mitgcm_outputs['visc_az'][i, j, :],
                'diff_kz_s': mitgcm_outputs['diff_kz_s'][i, j, :],
                'diff_kz_t': mitgcm_outputs['diff_kz_t'][i, j, :],
                'ghat': mitgcm_outputs['ghat'][i, j, :],
                'hbl': mitgcm_outputs['hbl'][i, j]
            }

            # Compare
            results = compare_kpp_outputs(py_output, mitgcm_output, rtol=1e-12)

            # Check for failures
            column_failed = any(not res['pass'] for res in results.values())
            if column_failed:
                failed_columns.append((i, j, results))

    # Report
    print(f"\nTimestep {timestep} lab_sea FULL GRID:")
    print(f"  Tested {tested_columns} ocean columns")
    if failed_columns:
        print(f"  Failed: {len(failed_columns)} columns")
        print(f"  Pass rate: {100*(1 - len(failed_columns)/tested_columns):.1f}%")
        print(f"\n  First 5 failures:")
        for i, j, results in failed_columns[:5]:
            print(f"    Column ({i},{j}):")
            for var, res in results.items():
                if not res['pass']:
                    print(f"      {var:12s}: FAIL  max_abs_err={res['max_abs_err']:.2e}  "
                          f"max_rel_err={res['max_rel_err']:.2e}")
        pytest.fail(f"Timestep {timestep}: {len(failed_columns)}/{tested_columns} columns failed")
    else:
        print(f"  ✓ All {tested_columns} ocean columns passed")
