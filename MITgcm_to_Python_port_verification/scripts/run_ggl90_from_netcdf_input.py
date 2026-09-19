#!/usr/bin/env python3
"""
Run the Python GGL90 port using MITgcm NetCDF inputs, in single-step-replay
mode: at each captured timestep, feed the port MITgcm's own TKE(t) (not the
port's own evolving state) and compare only the one-step update against
MITgcm's captured TKE(t+1)/viscosity/diffusivity. This isolates agreement on
the physics formula itself and avoids trajectory-drift confounds -- mirrors
scripts/run_kpp_from_netcdf_input.py's role for KPP.

Usage:
  python run_ggl90_from_netcdf_input.py <inputs.nc> -o <output.nc>
"""

import sys
import argparse
import numpy as np
import xarray as xr
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / '1D_Mixing_Model'))

from GGL90.ggl90_core_driver import GGL90Driver
from GGL90.ggl90_parameters import GGL90Parameters


# Maps MITgcm PARAM_<name> (netCDF global attrs) -> GGL90Parameters field name
PARAM_MAP = {
    'GGL90ck': 'ck',
    'GGL90ceps': 'ceps',
    'GGL90alpha': 'alpha',
    'GGL90m2': 'm2',
    'GGL90TKEmin': 'tke_min',
    'GGL90TKEsurfMin': 'tke_surf_min',
    'GGL90TKEbottom': 'tke_bottom',
    'GGL90mixingLengthMin': 'mixing_length_min',
    'mxlMaxFlag': 'mxl_max_flag',
    'GGL90viscMax': 'visc_max',
    'GGL90diffMax': 'diff_max',
    'GGL90_dirichlet': 'use_dirichlet',
    'calcMeanVertShear': 'calc_mean_vert_shear',
}
BOOL_FIELDS = {'use_dirichlet', 'calc_mean_vert_shear'}
INT_FIELDS = {'mxl_max_flag'}


def build_params(inputs_ds: xr.Dataset) -> GGL90Parameters:
    kwargs = {}
    for mitgcm_name, field_name in PARAM_MAP.items():
        if mitgcm_name not in inputs_ds.attrs:
            continue
        value = inputs_ds.attrs[mitgcm_name]
        if field_name in BOOL_FIELDS:
            value = bool(int(value))
        elif field_name in INT_FIELDS:
            value = int(value)
        else:
            value = float(value)
        kwargs[field_name] = value
    return GGL90Parameters(**kwargs)


def run(inputs_nc: Path, output_nc: Path) -> xr.Dataset:
    inputs_ds = xr.open_dataset(inputs_nc)
    params = build_params(inputs_ds)
    driver = GGL90Driver(params=params)

    background_visc = float(inputs_ds.attrs.get('viscAz', 0.0))
    background_diff = float(inputs_ds.attrs.get('diffKzS', 0.0))
    gravity = float(inputs_ds.attrs.get('gravity', 9.81))
    rho_const = float(inputs_ds.attrs.get('rhoConst', 1029.0))

    ntime = inputs_ds.sizes['time']
    nx = inputs_ds.sizes['x']
    ny = inputs_ds.sizes['y']
    nz = inputs_ds.sizes['z']

    depth = inputs_ds['depth'].values
    cell_thickness = inputs_ds['cell_thickness'].values
    mask = np.ones(nz)  # single-column captures are wet-only (see kpp precedent)

    kappa_m = np.zeros((ntime, nx, ny, nz))
    kappa_h = np.zeros((ntime, nx, ny, nz))
    mixing_length = np.zeros((ntime, nx, ny, nz))
    tke_new = np.zeros((ntime, nx, ny, nz))

    dt_values = np.diff(inputs_ds['time'].values)
    dt = float(dt_values[0]) if len(dt_values) else 1.0

    for t in range(ntime):
        for i in range(nx):
            for j in range(ny):
                tke = inputs_ds['tke_before'].values[t, i, j, :]
                theta = inputs_ds['temperature'].values[t, i, j, :]
                salt = inputs_ds['salinity'].values[t, i, j, :]
                u = inputs_ds['u_velocity'].values[t, i, j, :]
                v = inputs_ds['v_velocity'].values[t, i, j, :]
                u_star_sq = float(inputs_ds['u_star_sq'].values[t, i, j])

                out = driver.compute_mixing(
                    tke=tke, u=u, v=v, theta=theta, salt=salt,
                    depth=depth, z=depth, dz=cell_thickness, dt=dt,
                    mask=mask, u_star_sq=u_star_sq,
                    gravity=gravity, rho_const=rho_const,
                    background_visc=background_visc,
                    background_diff=background_diff,
                )
                kappa_m[t, i, j, :] = out.kappa_m
                kappa_h[t, i, j, :] = out.kappa_h
                mixing_length[t, i, j, :] = out.mixing_length
                tke_new[t, i, j, :] = out.tke_new

    coords = {
        'time': inputs_ds['time'].values,
        'x': inputs_ds['x'].values,
        'y': inputs_ds['y'].values,
        'depth': inputs_ds['depth'],
    }
    data_vars = {
        'visc_az': (['time', 'x', 'y', 'z'], kappa_m, {
            'long_name': 'Vertical eddy viscosity (Python GGL90)', 'units': 'm^2/s'
        }),
        'diff_kz': (['time', 'x', 'y', 'z'], kappa_h, {
            'long_name': 'Vertical eddy diffusivity (Python GGL90)', 'units': 'm^2/s'
        }),
        'mixing_length': (['time', 'x', 'y', 'z'], mixing_length, {
            'long_name': 'GGL90 mixing length (Python)', 'units': 'm'
        }),
        'tke_after': (['time', 'x', 'y', 'z'], tke_new, {
            'long_name': 'TKE at t+1, single-step replay (Python)', 'units': 'm^2/s^2',
            'description': (
                'Computed from MITgcm\'s own captured tke_before(t), not '
                'the port\'s own evolving state -- isolates one-step '
                'formula agreement.'
            )
        }),
    }
    outputs_ds = xr.Dataset(data_vars=data_vars, coords=coords)
    outputs_ds.attrs['title'] = 'Python GGL90 Outputs (single-step replay)'
    outputs_ds.attrs['source'] = 'Python GGL90Driver.compute_mixing'
    outputs_ds.attrs['creation_date'] = datetime.now().isoformat()
    outputs_ds.attrs['input_uuid'] = inputs_ds.attrs.get('uuid', '')

    output_nc.parent.mkdir(parents=True, exist_ok=True)
    outputs_ds.to_netcdf(output_nc)
    print(f"Wrote {output_nc}")
    return outputs_ds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', type=str)
    parser.add_argument('-o', '--output', type=str, required=True)
    args = parser.parse_args()
    run(Path(args.input_file), Path(args.output))


if __name__ == '__main__':
    main()
