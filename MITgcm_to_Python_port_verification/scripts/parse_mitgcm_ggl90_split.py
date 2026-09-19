#!/usr/bin/env python3
"""
Parse MITgcm GGL90 validation output (mitgcm_verification_mods/ggl90_mods/
ggl90_calc.F's GGL90_OUTPUT_VALIDATION dump) to separate input and output
xarray Datasets, mirroring parse_mitgcm_split.py's KPP format/structure.

Creates two files:
  - mitgcm_ggl90_inputs.nc:  state, TKE(t), forcing, grid, parameters (UUID-tagged)
  - mitgcm_ggl90_outputs.nc: mixing coefficients, TKE(t+1) (UUID-linked)

GGL90 is prognostic (unlike KPP): TKE(t) is captured as an explicit input
(before this timestep's call mutates it), and TKE(t+1) as the output, so a
single-step-replay comparison (feed the Python port MITgcm's own TKE(t), not
its own evolving state) is possible without accumulating drift.
"""

import sys
import uuid
import numpy as np
import xarray as xr
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple


def parse_mitgcm_ggl90_split(output_file: Path,
                              experiment_name: str = None) -> Tuple[xr.Dataset, xr.Dataset]:
    print(f"Parsing MITgcm GGL90 validation output: {output_file}")

    run_uuid = str(uuid.uuid4())
    if experiment_name is None:
        experiment_name = "unknown_experiment"

    print(f"  Experiment: {experiment_name}")
    print(f"  UUID: {run_uuid}")

    params = {}
    grid_info = {}
    timestep_data = {}
    nx_max, ny_max, nz_max = 0, 0, 0
    timesteps = set()

    with open(output_file, 'r') as f:
        in_validation_block = False
        current_timestep = None

        for line in f:
            line = line.strip()

            if line == '===== GGL90_MODEL_PARAMETERS =====':
                params = _parse_parameters(f)
                continue

            if line == '===== GGL90_GRID_GEOMETRY =====':
                grid_info = _parse_grid(f)
                nz_max = grid_info['nr']
                continue

            if line == '===== GGL90_DATA_HEADERS =====':
                _skip_until(f, '===== GGL90_DATA_HEADERS_END =====')
                continue

            if line == '===== GGL90_VALIDATION_START =====':
                in_validation_block = True
                continue

            if in_validation_block and line.startswith('TIMESTEP='):
                current_timestep = int(line.split(',')[0].split('=')[1].strip())
                timesteps.add(current_timestep)
                if current_timestep not in timestep_data:
                    timestep_data[current_timestep] = {
                        'state': {}, 'tke_before': {}, 'forcing': {},
                        'mixing': {}, 'tke_after': {}
                    }
                continue

            if line == '===== GGL90_VALIDATION_END =====':
                in_validation_block = False
                current_timestep = None
                continue

            if not in_validation_block or not line or current_timestep is None:
                continue

            parts = line.split(',')
            if len(parts) < 2:
                continue

            tag = parts[0]

            try:
                if tag in ('INPUT_STATE', 'OUTPUT_MIXING'):
                    i, j = int(parts[1]) - 1, int(parts[2]) - 1
                    nx_max, ny_max = max(nx_max, i + 1), max(ny_max, j + 1)

                if tag == 'INPUT_STATE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['state'][(i,j,k)] = {
                        'theta': float(parts[4]), 'salt': float(parts[5]),
                        'u': float(parts[6]), 'v': float(parts[7])
                    }

                elif tag == 'INPUT_TKE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['tke_before'][(i,j,k)] = float(parts[4])

                elif tag == 'INPUT_FORCING':
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['forcing'][(i,j)] = {
                        'tau_x': float(parts[3]), 'tau_y': float(parts[4]),
                        'u_star_sq': float(parts[5])
                    }

                elif tag == 'OUTPUT_MIXING':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['mixing'][(i,j,k)] = {
                        'visc_az': float(parts[4]), 'diff_kz': float(parts[5]),
                        'mixing_length': float(parts[6])
                    }

                elif tag == 'OUTPUT_TKE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['tke_after'][(i,j,k)] = float(parts[4])

            except (ValueError, IndexError):
                continue

    print(f"  Parsed: {len(timesteps)} timesteps, grid {nx_max}x{ny_max}x{nz_max}")

    inputs_ds = _create_inputs_dataset(
        timestep_data, grid_info, params,
        nx_max, ny_max, nz_max, sorted(timesteps),
        run_uuid, experiment_name, output_file
    )
    outputs_ds = _create_outputs_dataset(
        timestep_data, grid_info,
        nx_max, ny_max, nz_max, sorted(timesteps),
        run_uuid, experiment_name
    )

    return inputs_ds, outputs_ds


def _parse_parameters(f) -> Dict:
    params = {}
    int_params = {'mxlMaxFlag'}
    bool_params = {'GGL90_dirichlet', 'calcMeanVertShear'}
    for line in f:
        line = line.strip()
        if line == '===== GGL90_MODEL_PARAMETERS_END =====':
            break
        if line.startswith('PARAM_'):
            parts = line.split('=', 1)
            if len(parts) == 2:
                name = parts[0].replace('PARAM_', '')
                value_str = parts[1].strip()
                if name in int_params or name in bool_params:
                    params[name] = int(value_str)
                else:
                    params[name] = float(value_str)
    return params


def _parse_grid(f) -> Dict:
    drF, rF, rC = [], [], []
    for line in f:
        line = line.strip()
        if line == '===== GGL90_GRID_GEOMETRY_END =====':
            break
        if line.startswith('GRID_GEOM,'):
            parts = line.split(',')
            drF.append(float(parts[2]))
            rF.append(float(parts[3]))
            rC.append(float(parts[4]))
    return {'nr': len(drF), 'drF': np.array(drF), 'rF': np.array(rF), 'rC': np.array(rC)}


def _skip_until(f, marker):
    for line in f:
        if line.strip() == marker:
            break


def _create_inputs_dataset(timestep_data, grid_info, params,
                            nx, ny, nz, timesteps, run_uuid,
                            experiment_name, output_path):
    n_time = len(timesteps)

    temperature = np.zeros((n_time, nx, ny, nz))
    salinity = np.zeros((n_time, nx, ny, nz))
    u_velocity = np.zeros((n_time, nx, ny, nz))
    v_velocity = np.zeros((n_time, nx, ny, nz))
    tke_before = np.zeros((n_time, nx, ny, nz))
    tau_x = np.zeros((n_time, nx, ny))
    tau_y = np.zeros((n_time, nx, ny))
    u_star_sq = np.zeros((n_time, nx, ny))

    for t_idx, ts in enumerate(timesteps):
        ts_data = timestep_data[ts]
        for (i,j,k), vals in ts_data['state'].items():
            temperature[t_idx, i, j, k] = vals['theta']
            salinity[t_idx, i, j, k] = vals['salt']
            u_velocity[t_idx, i, j, k] = vals['u']
            v_velocity[t_idx, i, j, k] = vals['v']
        for (i,j,k), val in ts_data['tke_before'].items():
            tke_before[t_idx, i, j, k] = val
        for (i,j), vals in ts_data['forcing'].items():
            tau_x[t_idx, i, j] = vals['tau_x']
            tau_y[t_idx, i, j] = vals['tau_y']
            u_star_sq[t_idx, i, j] = vals['u_star_sq']

    coords = {
        'time': timesteps,
        'x': np.arange(nx),
        'y': np.arange(ny),
        'depth': (['z'], grid_info['rC'], {
            'long_name': 'Cell center depth', 'units': 'm', 'positive': 'up', 'axis': 'Z'
        }),
        'depth_iface': (['z_iface'], grid_info['rF'], {
            'long_name': 'Interface depth', 'units': 'm', 'positive': 'up', 'axis': 'Z'
        }),
        'cell_thickness': (['z'], grid_info['drF'], {
            'long_name': 'Cell thickness', 'units': 'm'
        }),
    }

    data_vars = {
        'temperature': (['time', 'x', 'y', 'z'], temperature, {
            'long_name': 'Potential temperature', 'units': 'degC',
            'standard_name': 'sea_water_potential_temperature'
        }),
        'salinity': (['time', 'x', 'y', 'z'], salinity, {
            'long_name': 'Salinity', 'units': 'psu',
            'standard_name': 'sea_water_salinity'
        }),
        'u_velocity': (['time', 'x', 'y', 'z'], u_velocity, {
            'long_name': 'Zonal velocity', 'units': 'm/s'
        }),
        'v_velocity': (['time', 'x', 'y', 'z'], v_velocity, {
            'long_name': 'Meridional velocity', 'units': 'm/s'
        }),
        'tke_before': (['time', 'x', 'y', 'z'], tke_before, {
            'long_name': 'Turbulent kinetic energy at t (input)', 'units': 'm^2/s^2',
            'description': (
                'GGL90TKE captured before this call mutates it -- feed this '
                'directly to the Python port for single-step-replay '
                'comparison against tke_after (in outputs), not the port\'s '
                'own evolving TKE state.'
            )
        }),
        'tau_x': (['time', 'x', 'y'], tau_x, {
            'long_name': 'Zonal wind stress per unit density', 'units': 'm^2/s^2'
        }),
        'tau_y': (['time', 'x', 'y'], tau_y, {
            'long_name': 'Meridional wind stress per unit density', 'units': 'm^2/s^2'
        }),
        'u_star_sq': (['time', 'x', 'y'], u_star_sq, {
            'long_name': 'MITgcm uStarSquare (post-sqrt; = sqrt(tau_x^2+tau_y^2))',
            'units': 'm^2/s^2',
            'description': (
                'Despite the name, this is the final in-use value at the '
                'GGL90m2*uStarSquare Dirichlet-BC term -- matches Python '
                'GGL90Driver.compute_mixing\'s u_star_sq argument directly '
                '(mixing_adapter.py computes it the same way: '
                'sqrt(tau_x**2+tau_y**2)).'
            )
        }),
    }

    ds = xr.Dataset(data_vars=data_vars, coords=coords)

    ds.attrs['title'] = 'MITgcm GGL90 Inputs'
    ds.attrs['source'] = 'MITgcm with GGL90 instrumentation'
    ds.attrs['institution'] = 'MITgcm'
    ds.attrs['experiment'] = experiment_name
    ds.attrs['output_file_path'] = str(output_path.absolute())
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['uuid'] = run_uuid
    ds.attrs['description'] = 'GGL90 inputs (state, TKE(t), forcing, grid) from MITgcm for validation'
    ds.attrs['conventions'] = 'CF-1.8'

    for name, value in params.items():
        ds.attrs[name] = value

    return ds


def _create_outputs_dataset(timestep_data, grid_info,
                             nx, ny, nz, timesteps, run_uuid, experiment_name):
    n_time = len(timesteps)

    visc_az = np.zeros((n_time, nx, ny, nz))
    diff_kz = np.zeros((n_time, nx, ny, nz))
    mixing_length = np.zeros((n_time, nx, ny, nz))
    tke_after = np.zeros((n_time, nx, ny, nz))

    for t_idx, ts in enumerate(timesteps):
        ts_data = timestep_data[ts]
        for (i,j,k), vals in ts_data['mixing'].items():
            visc_az[t_idx, i, j, k] = vals['visc_az']
            diff_kz[t_idx, i, j, k] = vals['diff_kz']
            mixing_length[t_idx, i, j, k] = vals['mixing_length']
        for (i,j,k), val in ts_data['tke_after'].items():
            tke_after[t_idx, i, j, k] = val

    coords = {
        'time': timesteps,
        'x': np.arange(nx),
        'y': np.arange(ny),
        'depth': (['z'], grid_info['rC'], {
            'long_name': 'Cell center depth', 'units': 'm', 'positive': 'up'
        }),
        'depth_iface': (['z_iface'], grid_info['rF'], {
            'long_name': 'Interface depth', 'units': 'm', 'positive': 'up'
        }),
    }

    data_vars = {
        'visc_az': (['time', 'x', 'y', 'z'], visc_az, {
            'long_name': 'Vertical eddy viscosity (GGL90, cell-centered pre-stagger)',
            'units': 'm^2/s',
            'description': 'GGL90visctmp: cell-centered KappaM before U/V staggering'
        }),
        'diff_kz': (['time', 'x', 'y', 'z'], diff_kz, {
            'long_name': 'Vertical eddy diffusivity (GGL90)', 'units': 'm^2/s',
            'description': 'GGL90diffKr'
        }),
        'mixing_length': (['time', 'x', 'y', 'z'], mixing_length, {
            'long_name': 'GGL90 mixing length', 'units': 'm'
        }),
        'tke_after': (['time', 'x', 'y', 'z'], tke_after, {
            'long_name': 'Turbulent kinetic energy at t+1 (output)', 'units': 'm^2/s^2',
            'description': 'GGL90TKE after this call\'s implicit tridiagonal solve'
        }),
    }

    ds = xr.Dataset(data_vars=data_vars, coords=coords)

    ds.attrs['title'] = 'MITgcm GGL90 Outputs'
    ds.attrs['source'] = 'MITgcm GGL90'
    ds.attrs['institution'] = 'MITgcm'
    ds.attrs['experiment'] = experiment_name
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['input_uuid'] = run_uuid
    ds.attrs['description'] = 'GGL90 outputs (mixing coefficients, TKE(t+1)) from MITgcm'
    ds.attrs['conventions'] = 'CF-1.8'

    return ds


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_mitgcm_ggl90_split.py <output.txt> [experiment_name]")
        sys.exit(1)

    output_file = Path(sys.argv[1])
    experiment_name = sys.argv[2] if len(sys.argv) >= 3 else None

    if not output_file.exists():
        print(f"Error: File not found: {output_file}")
        sys.exit(1)

    inputs_ds, outputs_ds = parse_mitgcm_ggl90_split(output_file, experiment_name)

    inputs_file = output_file.parent / 'mitgcm_ggl90_inputs.nc'
    outputs_file = output_file.parent / 'mitgcm_ggl90_outputs.nc'

    encoding = {var: {'zlib': True, 'complevel': 4} for var in inputs_ds.data_vars}
    inputs_ds.to_netcdf(inputs_file, encoding=encoding)
    print(f"  Inputs:  {inputs_file} ({inputs_file.stat().st_size/1024:.1f} KB)")

    encoding = {var: {'zlib': True, 'complevel': 4} for var in outputs_ds.data_vars}
    outputs_ds.to_netcdf(outputs_file, encoding=encoding)
    print(f"  Outputs: {outputs_file} ({outputs_file.stat().st_size/1024:.1f} KB)")

    print(f"UUID: {inputs_ds.attrs['uuid']}")


if __name__ == '__main__':
    main()
