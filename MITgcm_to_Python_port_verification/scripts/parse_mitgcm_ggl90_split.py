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

import re
import sys
import uuid
import numpy as np
import xarray as xr
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

# Fortran's fixed-width E-format drops the "E" when the exponent needs 3
# digits to fit the field width, e.g. '0.105188567206-104' instead of
# '0.105188567206E-104'. This broke parse_mitgcm_split.py's KPP parsing for
# vanishingly tiny (but physically real) values at quiescent levels -- see
# closed issue 1DMIX-012. Applying the same fix here proactively, since this
# parser shares the identical _ffloat(parts[N])-in-a-blanket-except pattern.
_FORTRAN_BARE_EXPONENT = re.compile(r'^([+-]?\d*\.\d+)([+-]\d+)$')

# ggl90_calc.F's TIMESTEP header (mirroring kpp_calc.F's own format) always
# carries the tile indices BI=/BJ=, even for single-tile (nSx=nSy=1)
# experiments (where they're always 1,1). Every dict key parsed below is
# tile-local (i,j) -- for a real multi-tile domain (e.g. global_oce_latlon's
# nSx=2,nSy=2), distinct tiles reuse the same local index range, so
# tile-local keys alone collide across tiles and silently overwrite each
# other. This regex lets parse_mitgcm_ggl90_split remap tile-local (i,j) to
# global (x,y) using the tile size inferred from the data itself (see
# parse_mitgcm_split.py's identical _TIMESTEP_HEADER/_remap_tiles_to_global,
# which this mirrors).
_TIMESTEP_HEADER = re.compile(r'^TIMESTEP=\s*(-?\d+),BI=\s*(\d+),BJ=\s*(\d+)$')


def _ffloat(s: str) -> float:
    """float() that also accepts Fortran's E-less bare-exponent form."""
    try:
        return float(s)
    except ValueError:
        m = _FORTRAN_BARE_EXPONENT.match(s.strip())
        if m:
            return float(m.group(1) + 'E' + m.group(2))
        raise


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
    nz_max = 0
    timesteps = set()

    # Tile-local index bookkeeping for the BI/BJ -> global (x,y) remap
    # (see _TIMESTEP_HEADER / _remap_tiles_to_global).
    local_i_max, local_j_max = 0, 0
    bi_max, bj_max = 1, 1

    with open(output_file, 'r') as f:
        in_validation_block = False
        current_timestep = None
        current_bi, current_bj = 1, 1

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
                m = _TIMESTEP_HEADER.match(line)
                if m:
                    current_timestep = int(m.group(1))
                    current_bi, current_bj = int(m.group(2)), int(m.group(3))
                else:
                    # Older/malformed header without BI=/BJ= -- treat as
                    # the single-tile case (ggl90_calc.F always emits BI/BJ
                    # in current captures, so this should not trigger).
                    current_timestep = int(line.split(',')[0].split('=')[1].strip())
                    current_bi, current_bj = 1, 1
                bi_max = max(bi_max, current_bi)
                bj_max = max(bj_max, current_bj)
                timesteps.add(current_timestep)
                if current_timestep not in timestep_data:
                    timestep_data[current_timestep] = {
                        'state': {}, 'tke_before': {}, 'sigma_r': {},
                        'forcing': {}, 'mixing': {}, 'tke_after': {},
                        'ri_shear_pr': {}, 'idemix': {}
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
                # Every dict below is keyed by (bi, bj, i, j[, k]) -- i,j are
                # tile-local (0-based); remapped to global (x,y) by
                # _remap_tiles_to_global after the full file is parsed.
                if tag in ('INPUT_STATE', 'OUTPUT_MIXING'):
                    i, j = int(parts[1]) - 1, int(parts[2]) - 1
                    local_i_max, local_j_max = max(local_i_max, i), max(local_j_max, j)

                if tag == 'INPUT_STATE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['state'][(current_bi,current_bj,i,j,k)] = {
                        'theta': _ffloat(parts[4]), 'salt': _ffloat(parts[5]),
                        'u': _ffloat(parts[6]), 'v': _ffloat(parts[7])
                    }

                elif tag == 'INPUT_TKE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['tke_before'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

                elif tag == 'INPUT_SIGMAR':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['sigma_r'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

                elif tag == 'INPUT_FORCING':
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['forcing'][(current_bi,current_bj,i,j)] = {
                        'tau_x': _ffloat(parts[3]), 'tau_y': _ffloat(parts[4]),
                        'u_star_sq': _ffloat(parts[5])
                    }

                elif tag == 'OUTPUT_MIXING':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['mixing'][(current_bi,current_bj,i,j,k)] = {
                        'visc_az': _ffloat(parts[4]), 'diff_kz': _ffloat(parts[5]),
                        'mixing_length': _ffloat(parts[6])
                    }

                elif tag == 'OUTPUT_TKE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['tke_after'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

                elif tag == 'OUTPUT_RI_SHEAR_PR':
                    # 1DMIX-028: RiNumber, verticalShear(i,j) and
                    # TKEPrandtlNumber(i,j,k), ground-truthing the
                    # diff_kz-level residual found on global_oce_latlon.
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['ri_shear_pr'][(current_bi,current_bj,i,j,k)] = {
                        'ri_number': _ffloat(parts[4]), 'vertical_shear': _ffloat(parts[5]),
                        'tke_prandtl_number': _ffloat(parts[6])
                    }

                elif tag == 'OUTPUT_IDEMIX':
                    # 1DMIX-025: IDEMIX_gTKE(i,j,k), the real additional
                    # TKE source term (dissipation of internal-wave energy)
                    # ALLOW_GGL90_IDEMIX adds -- the Python GGL90 port has
                    # no IDEMIX physics, so this quantifies the real,
                    # expected physics gap rather than feeding a Python-
                    # side implementation. Always present in a capture
                    # from the fixed ggl90_calc.F (this project's own
                    # instrumentation, always-declared/zeroed there), and
                    # is genuinely 0 for any non-IDEMIX experiment.
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['idemix'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

            except (ValueError, IndexError):
                continue

    # sNx/sNy (uniform per-tile size) inferred from the tile-local index
    # range actually observed -- MITgcm's decomposition is exact (every
    # tile is exactly sNx x sNy, no partial edge tiles), so the maximum
    # local index seen over ALL tiles equals sNx-1/sNy-1.
    sNx, sNy = local_i_max + 1, local_j_max + 1
    nx_max, ny_max = bi_max * sNx, bj_max * sNy
    timestep_data = _remap_tiles_to_global(timestep_data, sNx, sNy)

    print(f"  Parsed: {len(timesteps)} timesteps, grid {nx_max}x{ny_max}x{nz_max}"
          f" ({bi_max}x{bj_max} tiles of {sNx}x{sNy})")

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


def _remap_tiles_to_global(timestep_data: Dict, sNx: int, sNy: int) -> Dict:
    """Replace tile-local (bi,bj,i,j[,k]) dict keys with global (x,y[,k]).

    x = (bi-1)*sNx + i, y = (bj-1)*sNy + j. For single-tile captures
    (bi=bj=1 always) this is the identity map. Mirrors parse_mitgcm_split.py's
    identical KPP-side remap.
    """
    def remap(d: Dict) -> Dict:
        out = {}
        for key, value in d.items():
            bi, bj = key[0], key[1]
            rest = key[2:]
            x = (bi - 1) * sNx + rest[0]
            y = (bj - 1) * sNy + rest[1]
            out[(x, y) + rest[2:]] = value
        return out

    return {
        ts: {category: remap(d) for category, d in categories.items()}
        for ts, categories in timestep_data.items()
    }


def _parse_parameters(f) -> Dict:
    params = {}
    int_params = {'mxlMaxFlag'}
    bool_params = {'GGL90_dirichlet', 'calcMeanVertShear', 'mxlSurfFlag'}
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
            drF.append(_ffloat(parts[2]))
            rF.append(_ffloat(parts[3]))
            rC.append(_ffloat(parts[4]))
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
    sigma_r = np.zeros((n_time, nx, ny, nz))
    have_sigma_r = False
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
        for (i,j,k), val in ts_data.get('sigma_r', {}).items():
            sigma_r[t_idx, i, j, k] = val
            have_sigma_r = True
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
        'sigma_r': (['time', 'x', 'y', 'z'], sigma_r, {
            'long_name': 'Vertical gradient of iso-neutral density (sigmaR)',
            'units': 'kg/m^4',
            'description': (
                'GGL90_CALC\'s one explicit array argument (1DMIX-024). '
                'Captured directly from the real Fortran call (not derived '
                'from theta/salt in Python) since this run uses '
                "eosType='MDJWF' and the Python port only implements JMD95 "
                '-- deriving it here would inject a wrong-EOS confound into '
                'a bit-exact replay check. Feed directly to the standalone '
                'GGL90_CALC driver (ggl90_standalone_driver/).'
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
    ds.attrs['sigma_r_data'] = 'present' if have_sigma_r else 'absent'

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
    ri_number = np.zeros((n_time, nx, ny, nz))
    vertical_shear = np.zeros((n_time, nx, ny, nz))
    tke_prandtl_number = np.ones((n_time, nx, ny, nz))
    idemix_gtke = np.zeros((n_time, nx, ny, nz))
    have_ri_shear_pr = False
    have_idemix_gtke = False

    for t_idx, ts in enumerate(timesteps):
        ts_data = timestep_data[ts]
        for (i,j,k), vals in ts_data['mixing'].items():
            visc_az[t_idx, i, j, k] = vals['visc_az']
            diff_kz[t_idx, i, j, k] = vals['diff_kz']
            mixing_length[t_idx, i, j, k] = vals['mixing_length']
        for (i,j,k), val in ts_data['tke_after'].items():
            tke_after[t_idx, i, j, k] = val
        for (i,j,k), vals in ts_data.get('ri_shear_pr', {}).items():
            ri_number[t_idx, i, j, k] = vals['ri_number']
            vertical_shear[t_idx, i, j, k] = vals['vertical_shear']
            tke_prandtl_number[t_idx, i, j, k] = vals['tke_prandtl_number']
            have_ri_shear_pr = True
        for (i,j,k), val in ts_data.get('idemix', {}).items():
            idemix_gtke[t_idx, i, j, k] = val
            have_idemix_gtke = True

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
        'ri_number': (['time', 'x', 'y', 'z'], ri_number, {
            'long_name': 'GGL90 local Richardson number (RiNumber)', 'units': '1',
            'description': (
                '1DMIX-028: MAX(Nsquare,0)/(verticalShear+GGL90eps), the exact '
                'quantity ggl90_calc.F branches TKEPrandtlNumber on '
                '(RiNumber>=0.2). Absent from captures predating this fix '
                '(stays 0).'
            )
        }),
        'vertical_shear': (['time', 'x', 'y', 'z'], vertical_shear, {
            'long_name': 'GGL90 (squared) vertical shear', 'units': '1/s^2',
            'description': '1DMIX-028: verticalShear(i,j) at this level, before it is overwritten by the next k iteration.'
        }),
        'tke_prandtl_number': (['time', 'x', 'y', 'z'], tke_prandtl_number, {
            'long_name': 'GGL90 turbulent Prandtl number (TKEPrandtlNumber)', 'units': '1',
            'description': '1DMIX-028: direct capture, not inferred from visc_az/diff_kz ratios. Absent from captures predating this fix (stays 1, the Fortran init value).'
        }),
        'idemix_gtke': (['time', 'x', 'y', 'z'], idemix_gtke, {
            'long_name': 'IDEMIX internal-wave-energy dissipation (IDEMIX_gTKE)', 'units': 'm^2/s^3',
            'description': (
                '1DMIX-025: the real additional TKE source term '
                'ALLOW_GGL90_IDEMIX/useIDEMIX adds (tau_d*IDEMIX_E**2, see '
                'S/R GGL90_IDEMIX) -- the Python GGL90 port has no IDEMIX '
                'physics, so this is captured to quantify the real, '
                'expected physics gap, not to feed a Python-side '
                'implementation. Genuinely 0 for any non-IDEMIX experiment '
                '(and absent from captures predating this fix, where it '
                'defaults to 0 too, indistinguishable from a real-zero '
                'non-IDEMIX run -- check have_idemix_gtke to tell them apart).'
            )
        }),
    }

    ds = xr.Dataset(data_vars=data_vars, coords=coords)

    ds.attrs['title'] = 'MITgcm GGL90 Outputs'
    ds.attrs['source'] = 'MITgcm GGL90'
    ds.attrs['institution'] = 'MITgcm'
    ds.attrs['experiment'] = experiment_name
    ds.attrs['ri_shear_pr_data'] = 'present' if have_ri_shear_pr else 'absent'
    ds.attrs['idemix_gtke_data'] = 'present' if have_idemix_gtke else 'absent'
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
