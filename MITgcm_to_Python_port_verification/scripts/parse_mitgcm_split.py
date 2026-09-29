#!/usr/bin/env python3
"""
Parse MITgcm KPP validation output to separate input and output xarray files.

Creates two files:
  - mitgcm_kpp_inputs.nc:  State, forcing, grid, parameters (UUID-tagged)
  - mitgcm_kpp_outputs.nc: Mixing coefficients, HBL (UUID-linked)

This allows:
  - Reusing inputs with different Python versions
  - Comparing outputs from multiple runs
  - Clear provenance tracking
"""

import re
import sys
import uuid
import numpy as np
import xarray as xr
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

# Fortran's fixed-width E-format (e.g. E16.8/E20.12, used throughout this
# project's KPP validation WRITE statements) drops the "E" when the exponent
# needs 3 digits to fit the field width, e.g. '0.105188567206-104' instead of
# '0.105188567206E-104'. This silently breaks for vanishingly tiny (but
# physically real) values like shsq at quiescent deep levels -- Python's
# float() raises ValueError on the "E"-less form, which every call site here
# was catching via a blanket except-continue, silently dropping the entire
# line (including otherwise-valid sibling fields like dbloc/Ritop) and
# leaving pre-initialized zeros in their place (1DMIX-012).
_FORTRAN_BARE_EXPONENT = re.compile(r'^([+-]?\d*\.\d+)([+-]\d+)$')

# kpp_calc.F's TIMESTEP header (format '(A,I10,A,I3,A,I3)') always carries the
# tile indices BI=/BJ=, even for single-tile (nSx=nSy=1) experiments (where
# they're always 1,1). Every dict key parsed below is tile-local (i,j)
# -- for a real multi-tile domain (e.g. global_oce_latlon's nSx=2,nSy=2),
# distinct tiles reuse the same local index range, so tile-local keys alone
# collide across tiles and silently overwrite each other. This regex lets
# parse_mitgcm_split remap tile-local (i,j) to global (x,y) using the
# tile size inferred from the data itself (see _remap_tiles_to_global).
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


def parse_mitgcm_split(output_file: Path,
                       experiment_name: str = None) -> Tuple[xr.Dataset, xr.Dataset]:
    """
    Parse MITgcm output to separate input and output Datasets.

    Returns
    -------
    inputs_ds, outputs_ds : tuple of xr.Dataset
        Input dataset with UUID, output dataset with linked UUID
    """
    print(f"Parsing MITgcm KPP validation output: {output_file}")

    # Generate UUID for this run
    run_uuid = str(uuid.uuid4())

    # Auto-detect experiment name from path if not provided
    if experiment_name is None:
        # Try to extract from path (e.g., ".../1D_ocean_ice_column/output.txt")
        parts = output_file.parts
        for i, part in enumerate(parts):
            if i < len(parts) - 1 and 'output' in parts[i + 1]:
                experiment_name = part
                break
        if experiment_name is None:
            experiment_name = "unknown_experiment"

    print(f"  Experiment: {experiment_name}")
    print(f"  UUID: {run_uuid}")

    # Parse data
    params = {}
    grid_info = {}
    timestep_data = {}
    nx_max, ny_max, nz_max = 0, 0, 0
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

            # Parse parameters
            if line == '===== KPP_MODEL_PARAMETERS =====':
                params = _parse_parameters(f)
                continue

            # Parse grid
            if line == '===== KPP_GRID_GEOMETRY =====':
                grid_info = _parse_grid(f)
                nz_max = grid_info['nr']
                continue

            # Skip headers
            if line == '===== KPP_DATA_HEADERS =====':
                _skip_until(f, '===== KPP_DATA_HEADERS_END =====')
                continue

            # Validation block
            if line == '===== KPP_VALIDATION_START =====':
                in_validation_block = True
                continue

            if in_validation_block and line.startswith('TIMESTEP='):
                m = _TIMESTEP_HEADER.match(line)
                if m:
                    current_timestep = int(m.group(1))
                    current_bi, current_bj = int(m.group(2)), int(m.group(3))
                else:
                    # Older/malformed header without BI=/BJ= -- treat as
                    # the single-tile case (kpp_calc.F always emits BI/BJ
                    # in current captures, so this should not trigger).
                    current_timestep = int(line.split(',')[0].split('=')[1].strip())
                    current_bi, current_bj = 1, 1
                bi_max = max(bi_max, current_bi)
                bj_max = max(bj_max, current_bj)
                timesteps.add(current_timestep)

                if current_timestep not in timestep_data:
                    timestep_data[current_timestep] = {
                        'state': {}, 'forcing': {}, 'coriolis': {},
                        'mixing': {}, 'hbl': {}, 'diagnostics': {},
                        'swatt': {}, 'bulk_ri': {}, 'bfsfc_final': {},
                        'saltplume': {}
                    }
                continue

            if line == '===== KPP_VALIDATION_END =====':
                in_validation_block = False
                current_timestep = None
                continue

            # Parse data
            if not in_validation_block or not line or current_timestep is None:
                continue

            parts = line.split(',')
            if len(parts) < 2:
                continue

            tag = parts[0]

            try:
                # Every dict below is keyed by (bi, bj, i, j[, k]) -- i,j
                # are tile-local (0-based). local_i_max/local_j_max/bi_max/
                # bj_max let _remap_tiles_to_global convert these to global
                # (x,y) after the full file has been parsed (see module
                # docstring on _TIMESTEP_HEADER for why this is needed).
                if tag in ('INPUT_STATE', 'OUTPUT_MIXING', 'OUTPUT_HBL',
                           'OUTPUT_RIB', 'OUTPUT_BFSFC'):
                    i, j = int(parts[1])-1, int(parts[2])-1
                    local_i_max, local_j_max = max(local_i_max, i), max(local_j_max, j)

                if tag == 'INPUT_STATE':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['state'][(current_bi,current_bj,i,j,k)] = {
                        'theta': _ffloat(parts[4]), 'salt': _ffloat(parts[5]),
                        'u': _ffloat(parts[6]), 'v': _ffloat(parts[7])
                    }

                elif tag == 'INPUT_FORCING':
                    i, j = int(parts[1])-1, int(parts[2])-1
                    forcing_dict = {
                        'ustar': _ffloat(parts[3]), 'bo': _ffloat(parts[4]),
                        'bosol': _ffloat(parts[5]), 'tau_x': _ffloat(parts[6]),
                        'tau_y': _ffloat(parts[7])
                    }
                    # Optional: raw surface fluxes for forcing validation (backwards compatible)
                    # Legacy extended format (pre-1DMIX-013 fix; still emitted by
                    # some older captures -- q_net/fw_flux there are actually
                    # MITgcm's surfaceForcingT/surfaceForcingS, NOT true raw
                    # Qnet/EmPmR, see 1DMIX-013):
                    #   INPUT_FORCING,i,j,ustar,bo,bosol,tau_x,tau_y,q_net,q_sw,fw_flux
                    # 1DMIX-013 fix: new format emits genuinely raw MITgcm
                    # state (Qnet, Qsw, EmPmR, saltFlux -- all FFIELDS.h
                    # COMMON-block fields, upward-positive convention) instead
                    # of the pre-converted surfaceForcingT/S. Distinct *_raw
                    # keys so this never collides with the legacy (buggy)
                    # q_net/fw_flux semantics below. Mutually exclusive with
                    # the legacy branch (exact part-count dispatch) since a
                    # 12-part new-format line also satisfies ">= 11".
                    #   INPUT_FORCING,i,j,ustar,bo,bosol,tau_x,tau_y,
                    #     Qnet_raw,Qsw_raw,EmPmR_raw,saltFlux_raw
                    if len(parts) == 12:
                        forcing_dict['qnet_raw'] = _ffloat(parts[8])
                        forcing_dict['qsw_raw'] = _ffloat(parts[9])
                        forcing_dict['empmr_raw'] = _ffloat(parts[10])
                        forcing_dict['saltflux_raw'] = _ffloat(parts[11])
                    elif len(parts) >= 11:
                        forcing_dict['q_net'] = _ffloat(parts[8])
                        forcing_dict['q_sw'] = _ffloat(parts[9])
                        forcing_dict['fw_flux'] = _ffloat(parts[10])
                    timestep_data[current_timestep]['forcing'][(current_bi,current_bj,i,j)] = forcing_dict

                elif tag == 'INPUT_CORIOLIS':
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['coriolis'][(current_bi,current_bj,i,j)] = _ffloat(parts[3])

                elif tag == 'INPUT_SALTPLUME':
                    # 1DMIX-034 part 2: boplume(i,j,1) and SaltPlumeDepth(i,j),
                    # both already computed locally by KPP_FORCING_SURF/salt
                    # plume depth diagnosis -- new, purely additive capture
                    # (kpp_calc.F INPUT_FORCING dump, guarded #ifdef
                    # ALLOW_SALT_PLUME exactly like INPUT_SWATT, emitting
                    # 0.0/0.0 when compiled out). Needed to port the
                    # salt-plume term in diagnose_bl_depth's bfsfc.
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['saltplume'][(current_bi,current_bj,i,j)] = {
                        'boplume': _ffloat(parts[3]), 'sp_depth': _ffloat(parts[4])
                    }

                elif tag == 'INPUT_SWATT':
                    # KPPMIX direct "I" argument (bldepth) whenever
                    # SHORTWAVE_HEATING is active; k runs 1..Nr+1 (one
                    # more level than shsq/dbloc/dVsq/Ritop).
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['swatt'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

                elif tag == 'OUTPUT_MIXING':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['mixing'][(current_bi,current_bj,i,j,k)] = {
                        'visc_az': _ffloat(parts[4]), 'diff_kz_s': _ffloat(parts[5]),
                        'diff_kz_t': _ffloat(parts[6]), 'ghat': _ffloat(parts[7])
                    }

                elif tag == 'OUTPUT_HBL':
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['hbl'][(current_bi,current_bj,i,j)] = _ffloat(parts[3])

                elif tag == 'OUTPUT_DIAGNOSTICS':
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    diag = {
                        'shear_sq': _ffloat(parts[4]),
                        'buoy_freq_sq': _ffloat(parts[5]),
                        'richardson': _ffloat(parts[6])
                    }
                    # dVsq/Ritop: KPPMIX's direct "I"-only arguments, dumped
                    # verbatim (unmodified by KPPMIX) so the standalone
                    # KPPMIX-only harness can replay it without STATEKPP/
                    # KPP_FORCING_SURF. Older captures predate these columns.
                    if len(parts) >= 9:
                        diag['dVsq'] = _ffloat(parts[7])
                        diag['Ritop'] = _ffloat(parts[8])
                    timestep_data[current_timestep]['diagnostics'][(current_bi,current_bj,i,j,k)] = diag

                elif tag == 'OUTPUT_RIB':
                    # 1DMIX-025: bldepth's own real bulk Richardson number
                    # (kpp_routines.F), exposed via KPPMIX's new output
                    # argument -- ground truth for the Python port's own
                    # Rib profile, distinct from 'richardson' above (which
                    # is dbloc/shsq, the *local* Ri used by Ri_iwmix, not
                    # bldepth's bulk Rib).
                    i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
                    timestep_data[current_timestep]['bulk_ri'][(current_bi,current_bj,i,j,k)] = _ffloat(parts[4])

                elif tag == 'OUTPUT_BFSFC':
                    # 1DMIX-025: bldepth's final (post-LimitHblStable-clamp)
                    # surface buoyancy forcing, exposed via KPPMIX's new
                    # kppBfsfc output argument.
                    i, j = int(parts[1])-1, int(parts[2])-1
                    timestep_data[current_timestep]['bfsfc_final'][(current_bi,current_bj,i,j)] = _ffloat(parts[3])

            except (ValueError, IndexError):
                continue

    # sNx/sNy (uniform per-tile size) inferred from the tile-local index
    # range actually observed -- MITgcm's decomposition is exact (every
    # tile is exactly sNx x sNy, no partial edge tiles), so the maximum
    # local index seen over ALL tiles equals sNx-1/sNy-1.
    sNx, sNy = local_i_max + 1, local_j_max + 1
    nx_max, ny_max = bi_max * sNx, bj_max * sNy
    timestep_data = _remap_tiles_to_global(timestep_data, sNx, sNy)

    print(f"  Parsed: {len(timesteps)} timesteps, grid {nx_max}×{ny_max}×{nz_max}"
          f" ({bi_max}×{bj_max} tiles of {sNx}×{sNy})")

    # Create datasets
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
    (bi=bj=1 always) this is the identity map.
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
    """Parse KPP parameters from MITgcm output.

    Handles float, integer, and boolean (0/1) parameters.
    """
    params = {}
    # List of known boolean parameters (runtime flags and CPP options)
    boolean_params = {
        'KPP_ghatUseTotalDiffus', 'KPPuseDoubleDiff', 'LimitHblStable',
        'KPPwriteState', 'KPPuseSWfrac3D',
        # CPP compile-time options
        'use_ghat', 'smooth_shsq', 'smooth_dvsq', 'smooth_dbloc',
        'smooth_dens', 'smooth_visc', 'smooth_diff', 'estimate_uref',
        'match_diffusivities', 'match_derivatives', 'smooth_regularisation',
        'scale_shearmixing', 'exclude_shear_mix', 'exclude_doublediff',
        'vertically_smooth_ri', 'shortwave_heating',
        'useSALT_PLUME', 'allow_salt_plume',
        # 1DMIX-034 part 2: compile-time SALT_PLUME_VOLUME variant flag.
        'salt_plume_volume'
    }

    for line in f:
        line = line.strip()
        if line == '===== KPP_MODEL_PARAMETERS_END =====':
            break
        if line.startswith('PARAM_'):
            parts = line.split('=', 1)
            if len(parts) == 2:
                param_name = parts[0].replace('PARAM_', '')
                value_str = parts[1].strip()

                # Determine type and convert
                if param_name in boolean_params:
                    # Store as int (0 or 1) since NetCDF doesn't support bool attributes
                    params[param_name] = int(value_str)
                elif param_name in ('num_v_smooth_Ri', 'selectPenetratingSW',
                                     # 1DMIX-034 part 2: integer salt-plume
                                     # distribution parameters (SALT_PLUME.h),
                                     # only emitted when ALLOW_SALT_PLUME is
                                     # compiled in.
                                     'PlumeMethod', 'Npower'):
                    params[param_name] = int(value_str)
                else:
                    params[param_name] = float(value_str)
    return params


def _parse_grid(f) -> Dict:
    drF, rF, rC = [], [], []
    for line in f:
        line = line.strip()
        if line == '===== KPP_GRID_GEOMETRY_END =====':
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
    """Create inputs Dataset with UUID, parameters, and metadata."""

    n_time = len(timesteps)

    # Allocate arrays (use zeros instead of NaN for truncated data)
    temperature = np.zeros((n_time, nx, ny, nz))
    salinity = np.zeros((n_time, nx, ny, nz))
    u_velocity = np.zeros((n_time, nx, ny, nz))
    v_velocity = np.zeros((n_time, nx, ny, nz))

    ustar = np.zeros((n_time, nx, ny))
    bo = np.zeros((n_time, nx, ny))
    bosol = np.zeros((n_time, nx, ny))
    tau_x = np.zeros((n_time, nx, ny))
    tau_y = np.zeros((n_time, nx, ny))
    f_coriolis = np.zeros((n_time, nx, ny))

    # Optional: raw surface fluxes for forcing validation (legacy format;
    # see 1DMIX-013 -- q_net/fw_flux here are actually surfaceForcingT/S)
    q_net = np.zeros((n_time, nx, ny))
    q_sw = np.zeros((n_time, nx, ny))
    fw_flux = np.zeros((n_time, nx, ny))
    has_raw_fluxes = False

    # 1DMIX-013 fix: genuinely raw MITgcm state (Qnet, Qsw, EmPmR,
    # saltFlux -- FFIELDS.h COMMON-block fields, upward-positive
    # convention). See kpp_calc.F::KPP_OUTPUT_VALIDATION's INPUT_FORCING
    # comment and run_kpp_from_netcdf_input.py's forcing-derivation for
    # the exact citation of how these combine into the raw-flux
    # convention _compute_surface_forcing's q_net/q_sw/fw_flux expect.
    qnet_raw = np.zeros((n_time, nx, ny))
    qsw_raw = np.zeros((n_time, nx, ny))
    empmr_raw = np.zeros((n_time, nx, ny))
    saltflux_raw = np.zeros((n_time, nx, ny))
    has_raw_mitgcm_fields = False

    # Optional: shortwave attenuation profile (KPPMIX direct "I" input
    # when SHORTWAVE_HEATING is active). One more level than shsq/dbloc.
    swatt = np.zeros((n_time, nx, ny, nz + 1))
    has_swatt = False

    # Optional: salt-plume surface haline buoyancy forcing and its
    # penetration depth (1DMIX-034 part 2). Scalar per column, like bo/
    # bosol. Absent (all-zero, has_saltplume=False) for every capture
    # that predates this fix or never compiled ALLOW_SALT_PLUME in.
    boplume = np.zeros((n_time, nx, ny))
    sp_depth = np.zeros((n_time, nx, ny))
    has_saltplume = False

    # Fill arrays
    for t_idx, ts in enumerate(timesteps):
        ts_data = timestep_data[ts]

        for (i,j,k), vals in ts_data['state'].items():
            temperature[t_idx, i, j, k] = vals['theta']
            salinity[t_idx, i, j, k] = vals['salt']
            u_velocity[t_idx, i, j, k] = vals['u']
            v_velocity[t_idx, i, j, k] = vals['v']

        for (i,j), vals in ts_data['forcing'].items():
            ustar[t_idx, i, j] = vals['ustar']
            bo[t_idx, i, j] = vals['bo']
            bosol[t_idx, i, j] = vals['bosol']
            tau_x[t_idx, i, j] = vals['tau_x']
            tau_y[t_idx, i, j] = vals['tau_y']
            # Optional: raw fluxes for forcing validation (legacy format)
            if 'q_net' in vals:
                q_net[t_idx, i, j] = vals['q_net']
                q_sw[t_idx, i, j] = vals['q_sw']
                fw_flux[t_idx, i, j] = vals['fw_flux']
                has_raw_fluxes = True
            # 1DMIX-013 fix: genuinely raw MITgcm state
            if 'qnet_raw' in vals:
                qnet_raw[t_idx, i, j] = vals['qnet_raw']
                qsw_raw[t_idx, i, j] = vals['qsw_raw']
                empmr_raw[t_idx, i, j] = vals['empmr_raw']
                saltflux_raw[t_idx, i, j] = vals['saltflux_raw']
                has_raw_mitgcm_fields = True

        for (i,j), val in ts_data['coriolis'].items():
            f_coriolis[t_idx, i, j] = val

        for (i,j,k), val in ts_data.get('swatt', {}).items():
            swatt[t_idx, i, j, k] = val
            has_swatt = True

        for (i,j), vals in ts_data.get('saltplume', {}).items():
            boplume[t_idx, i, j] = vals['boplume']
            sp_depth[t_idx, i, j] = vals['sp_depth']
            has_saltplume = True

    # Coordinates
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

    # Data variables
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
            'long_name': 'Zonal velocity', 'units': 'm/s',
            'standard_name': 'eastward_sea_water_velocity'
        }),
        'v_velocity': (['time', 'x', 'y', 'z'], v_velocity, {
            'long_name': 'Meridional velocity', 'units': 'm/s',
            'standard_name': 'northward_sea_water_velocity'
        }),
        'ustar': (['time', 'x', 'y'], ustar, {
            'long_name': 'Friction velocity', 'units': 'm/s',
            'description': 'Surface friction velocity from wind stress'
        }),
        'bo': (['time', 'x', 'y'], bo, {
            'long_name': 'Turbulent buoyancy forcing', 'units': 'm^2/s^3',
            'description': 'Non-penetrating buoyancy forcing at surface'
        }),
        'bosol': (['time', 'x', 'y'], bosol, {
            'long_name': 'Radiative buoyancy forcing', 'units': 'm^2/s^3',
            'description': 'Penetrating shortwave buoyancy forcing'
        }),
        'tau_x': (['time', 'x', 'y'], tau_x, {
            'long_name': 'Zonal wind stress per unit density', 'units': 'm^2/s^2'
        }),
        'tau_y': (['time', 'x', 'y'], tau_y, {
            'long_name': 'Meridional wind stress per unit density', 'units': 'm^2/s^2'
        }),
        'f_coriolis': (['time', 'x', 'y'], f_coriolis, {
            'long_name': 'Coriolis parameter', 'units': '1/s',
            'standard_name': 'coriolis_parameter'
        }),
    }

    # Add optional raw surface fluxes if present (for forcing validation)
    if has_raw_fluxes:
        data_vars['q_net'] = (['time', 'x', 'y'], q_net, {
            'long_name': 'Net surface heat flux (excluding shortwave)',
            'units': 'W/m^2',
            'standard_name': 'surface_net_heat_flux',
            'description': 'Positive into ocean (warming)',
            'comment': 'Used to compute bo; for forcing validation only'
        })
        data_vars['q_sw'] = (['time', 'x', 'y'], q_sw, {
            'long_name': 'Surface shortwave radiation',
            'units': 'W/m^2',
            'standard_name': 'surface_shortwave_flux',
            'description': 'Positive into ocean (heating)',
            'comment': 'Used to compute bosol; for forcing validation only'
        })
        data_vars['fw_flux'] = (['time', 'x', 'y'], fw_flux, {
            'long_name': 'Freshwater flux (E-P-R)',
            'units': 'kg/m^2/s',
            'standard_name': 'freshwater_flux',
            'description': 'Positive into ocean (freshening)',
            'comment': 'Used to compute bo; for forcing validation only'
        })

    # 1DMIX-013 fix: genuinely raw MITgcm state (distinct *_raw names from
    # the legacy q_net/q_sw/fw_flux above, which are actually MITgcm's
    # already-converted surfaceForcingT/surfaceForcingS -- see kpp_calc.F
    # ::KPP_OUTPUT_VALIDATION and model/src/external_forcing_surf.F:
    # 217-234,296-320). All four are plain FFIELDS.h COMMON-block fields,
    # MITgcm's own "upward positive" sign convention (model/inc/FFIELDS.h:
    # 17-38,44-53) -- NOT yet converted to the "positive into ocean"
    # convention _compute_surface_forcing's raw-flux parameters expect.
    # scripts/run_kpp_from_netcdf_input.py's forcing-derivation applies
    # the exact (derived-and-verified, see 1DMIX-013 evidence) combination
    # before calling KPPDriver.compute_mixing.
    if has_raw_mitgcm_fields:
        data_vars['qnet_raw'] = (['time', 'x', 'y'], qnet_raw, {
            'long_name': 'Net upward surface heat flux (incl. shortwave)',
            'units': 'W/m^2',
            'standard_name': 'surface_upward_heat_flux_in_air',
            'description': (
                'MITgcm FFIELDS.h Qnet, verbatim: latent+sensible+'
                'net longwave+net shortwave, UPWARD positive '
                '(typical range -250..600). NOT the sign convention '
                '_compute_surface_forcing documents for its own q_net '
                'parameter -- see run_kpp_from_netcdf_input.py.'
            ),
            'comment': '1DMIX-013: raw capture, replaces mislabeled legacy q_net'
        })
        data_vars['qsw_raw'] = (['time', 'x', 'y'], qsw_raw, {
            'long_name': 'Net upward shortwave radiation',
            'units': 'W/m^2',
            'standard_name': 'surface_upward_shortwave_flux_in_air',
            'description': (
                'MITgcm FFIELDS.h Qsw, verbatim: upward positive '
                '(typical range -350..0). Was already raw before '
                '1DMIX-013; renamed for consistency with the other '
                '*_raw fields.'
            ),
            'comment': '1DMIX-013: raw capture'
        })
        data_vars['empmr_raw'] = (['time', 'x', 'y'], empmr_raw, {
            'long_name': 'Net upward freshwater flux (Evap-Precip-Runoff)',
            'units': 'kg/m^2/s',
            'standard_name': 'water_evaporation_flux',
            'description': (
                'MITgcm FFIELDS.h EmPmR, verbatim: upward positive '
                '(typical range -1e-4..1e-4).'
            ),
            'comment': '1DMIX-013: raw capture, replaces mislabeled legacy fw_flux'
        })
        data_vars['saltflux_raw'] = (['time', 'x', 'y'], saltflux_raw, {
            'long_name': 'Net upward salt flux',
            'units': 'g/m^2/s',
            'description': (
                'MITgcm FFIELDS.h saltFlux, verbatim: upward positive; '
                'g/kg * kg/m^2/s = g/m^2/s (FFIELDS.h:38). For this '
                'sea-ice column experiment this is set by '
                'pkg/seaice/seaice_growth.F (brine rejection/freshening '
                'during ice growth/melt) and combines with empmr_raw '
                'inside external_forcing_surf.F:233-234,314-317 to form '
                'surfaceForcingS -- omitting it under-represents the true '
                'salt forcing for ice-covered columns.'
            ),
            'comment': '1DMIX-013: raw capture, no legacy equivalent (new term)'
        })

    if has_swatt:
        data_vars['swatt'] = (['time', 'x', 'y', 'z_swatt'], swatt, {
            'long_name': 'Shortwave attenuation fraction (KPPMIX direct input)',
            'units': 'dimensionless',
            'description': (
                'Fraction of solar shortwave flux penetrating to each '
                'level (SWFrac3D); Nr+1 levels. Direct KPPMIX "I" '
                'argument, needed whenever SHORTWAVE_HEATING is active.'
            )
        })

    if has_saltplume:
        data_vars['boplume'] = (['time', 'x', 'y'], boplume, {
            'long_name': 'Surface haline buoyancy forcing from salt plumes',
            'units': 'm^2/s^3',
            'description': (
                '1DMIX-034: boplume(i,j,1), KPP_FORCING_SURF\'s surface-'
                'level (SALT_PLUME_VOLUME-undef branch) haline buoyancy '
                'forcing from rejected brine (kpp_forcing_surf.F:262-273). '
                'Direct KPPMIX "I" argument, needed whenever useSALT_PLUME '
                'is active; 0.0 otherwise.'
            )
        })
        data_vars['sp_depth'] = (['time', 'x', 'y'], sp_depth, {
            'long_name': 'Salt plume penetration depth',
            'units': 'm',
            'description': (
                '1DMIX-034: SaltPlumeDepth(i,j), the e-folding depth used '
                'by SALT_PLUME_FRAC to distribute boplume vertically '
                '(pkg/salt_plume/salt_plume_calc_depth.F). Direct KPPMIX '
                '"I" argument (SPDepth), needed whenever useSALT_PLUME is '
                'active; 0.0 otherwise.'
            )
        })

    ds = xr.Dataset(data_vars=data_vars, coords=coords)

    # Global attributes
    ds.attrs['title'] = 'MITgcm KPP Inputs'
    ds.attrs['source'] = 'MITgcm with KPP instrumentation'
    ds.attrs['institution'] = 'MITgcm'
    ds.attrs['experiment'] = experiment_name
    ds.attrs['output_file_path'] = str(output_path.absolute())
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['uuid'] = run_uuid
    ds.attrs['description'] = 'KPP inputs (state, forcing, grid) from MITgcm for validation'
    ds.attrs['conventions'] = 'CF-1.8'
    ds.attrs['forcing_validation_data'] = (
        'present' if (has_raw_fluxes or has_raw_mitgcm_fields) else 'absent'
    )
    ds.attrs['swatt_data'] = 'present' if has_swatt else 'absent'
    ds.attrs['saltplume_data'] = 'present' if has_saltplume else 'absent'

    # Model parameters
    for param_name, param_value in params.items():
        ds.attrs[param_name] = param_value
        ds.attrs[f'{param_name}_units'] = _get_param_units(param_name)
        ds.attrs[f'{param_name}_description'] = _get_param_description(param_name)

    return ds


def _create_outputs_dataset(timestep_data, grid_info,
                            nx, ny, nz, timesteps, run_uuid, experiment_name):
    """Create outputs Dataset with UUID linking back to inputs."""

    n_time = len(timesteps)

    # Allocate arrays (use zeros instead of NaN for truncated data)
    visc_az = np.zeros((n_time, nx, ny, nz))
    diff_kz_s = np.zeros((n_time, nx, ny, nz))
    diff_kz_t = np.zeros((n_time, nx, ny, nz))
    ghat = np.zeros((n_time, nx, ny, nz))
    hbl = np.zeros((n_time, nx, ny))
    shear_sq = np.zeros((n_time, nx, ny, nz))
    buoy_freq_sq = np.zeros((n_time, nx, ny, nz))
    richardson = np.zeros((n_time, nx, ny, nz))
    dvsq = np.zeros((n_time, nx, ny, nz))
    ritop = np.zeros((n_time, nx, ny, nz))
    bulk_ri = np.zeros((n_time, nx, ny, nz))
    bfsfc_final = np.zeros((n_time, nx, ny))
    has_kppmix_direct_inputs = False
    has_bulk_ri = False
    has_bfsfc_final = False

    # Fill arrays
    for t_idx, ts in enumerate(timesteps):
        ts_data = timestep_data[ts]

        for (i,j,k), vals in ts_data['mixing'].items():
            visc_az[t_idx, i, j, k] = vals['visc_az']
            diff_kz_s[t_idx, i, j, k] = vals['diff_kz_s']
            diff_kz_t[t_idx, i, j, k] = vals['diff_kz_t']
            ghat[t_idx, i, j, k] = vals['ghat']

        for (i,j), val in ts_data['hbl'].items():
            hbl[t_idx, i, j] = val

        for (i,j,k), vals in ts_data['diagnostics'].items():
            shear_sq[t_idx, i, j, k] = vals['shear_sq']
            buoy_freq_sq[t_idx, i, j, k] = vals['buoy_freq_sq']
            richardson[t_idx, i, j, k] = vals['richardson']
            if 'dVsq' in vals:
                dvsq[t_idx, i, j, k] = vals['dVsq']
                ritop[t_idx, i, j, k] = vals['Ritop']
                has_kppmix_direct_inputs = True

        for (i,j,k), val in ts_data.get('bulk_ri', {}).items():
            bulk_ri[t_idx, i, j, k] = val
            has_bulk_ri = True

        for (i,j), val in ts_data.get('bfsfc_final', {}).items():
            bfsfc_final[t_idx, i, j] = val
            has_bfsfc_final = True

    # Coordinates (matching inputs)
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

    # Data variables
    data_vars = {
        'visc_az': (['time', 'x', 'y', 'z_iface'], visc_az, {
            'long_name': 'Vertical viscosity (MITgcm KPP)', 'units': 'm^2/s',
            'description': 'KPP vertical viscosity at cell interfaces',
            'cell_location': 'interface'
        }),
        'diff_kz_s': (['time', 'x', 'y', 'z_iface'], diff_kz_s, {
            'long_name': 'Vertical diffusivity for salt (MITgcm KPP)', 'units': 'm^2/s',
            'description': 'KPP vertical diffusivity for salinity',
            'cell_location': 'interface'
        }),
        'diff_kz_t': (['time', 'x', 'y', 'z_iface'], diff_kz_t, {
            'long_name': 'Vertical diffusivity for temperature (MITgcm KPP)', 'units': 'm^2/s',
            'description': 'KPP vertical diffusivity for temperature',
            'cell_location': 'interface'
        }),
        'ghat': (['time', 'x', 'y', 'z'], ghat, {
            'long_name': 'Nonlocal transport (MITgcm KPP)', 'units': 's/m^2',
            'description': 'KPP nonlocal transport at cell centers',
            'cell_location': 'center'
        }),
        'hbl': (['time', 'x', 'y'], hbl, {
            'long_name': 'Boundary layer depth (MITgcm KPP)', 'units': 'm',
            'description': 'KPP boundary layer depth',
            'standard_name': 'ocean_mixed_layer_thickness_defined_by_sigma_theta'
        }),
        'shear_sq': (['time', 'x', 'y', 'z_iface'], shear_sq, {
            'long_name': 'Vertical shear squared', 'units': '1/s^2',
            'description': 'Square of vertical velocity shear at cell interfaces',
            'cell_location': 'interface'
        }),
        'buoy_freq_sq': (['time', 'x', 'y', 'z_iface'], buoy_freq_sq, {
            'long_name': 'Buoyancy frequency squared (N²)', 'units': '1/s^2',
            'description': 'Square of buoyancy frequency (stratification) at cell interfaces',
            'cell_location': 'interface'
        }),
        'richardson': (['time', 'x', 'y', 'z_iface'], richardson, {
            'long_name': 'Richardson number', 'units': 'dimensionless',
            'description': 'Gradient Richardson number (Ri = N²/S²) at cell interfaces',
            'cell_location': 'interface'
        }),
    }

    if has_kppmix_direct_inputs:
        data_vars['dVsq'] = (['time', 'x', 'y', 'z_iface'], dvsq, {
            'long_name': 'Velocity shear squared relative to surface',
            'units': 'm^2/s^2',
            'description': (
                'Direct KPPMIX "I"-only input (dVsq), dumped verbatim/'
                'unmodified. Semantically an input to KPPMIX, not an '
                'MITgcm output; captured here (not in the inputs file) '
                'because it is only produced as a side effect of the '
                'full model run, following the existing shear_sq/'
                'buoy_freq_sq precedent.'
            ),
            'cell_location': 'interface'
        })
        data_vars['Ritop'] = (['time', 'x', 'y', 'z_iface'], ritop, {
            'long_name': 'Numerator of bulk Richardson number',
            'units': 'm^2/s^2',
            'description': (
                'Direct KPPMIX "I"-only input (Ritop), dumped verbatim/'
                'unmodified. See dVsq description for why it lives here.'
            ),
            'cell_location': 'interface'
        })

    if has_bulk_ri:
        data_vars['bulk_ri'] = (['time', 'x', 'y', 'z_iface'], bulk_ri, {
            'long_name': "bldepth's real bulk Richardson number",
            'units': 'dimensionless',
            'description': (
                '1DMIX-025: bldepth\'s own Rib(kl) = Ritop(kl)/(dVsq(kl)+vtsq(kl)) '
                '(kpp_routines.F), exposed via a new KPPMIX output argument '
                'added for this issue -- real ground truth, distinct from '
                "'richardson' above (which is dbloc/shsq, the *local* Ri used "
                'by the separate Ri_iwmix routine, not this bulk Rib).'
            ),
            'cell_location': 'interface'
        })

    if has_bfsfc_final:
        data_vars['bfsfc_final'] = (['time', 'x', 'y'], bfsfc_final, {
            'long_name': "bldepth's final surface buoyancy forcing",
            'units': 'm^2/s^3',
            'description': (
                "1DMIX-025: bldepth's bfsfc AFTER the LimitHblStable Ekman/"
                'Monin-Obukhov clamp is applied (the value used to compute '
                'that clamp, not the earlier per-trial-level bfsfc used '
                'inside the Rib search loop), exposed via a new KPPMIX '
                'output argument added for this issue.'
            )
        })

    ds = xr.Dataset(data_vars=data_vars, coords=coords)

    # Global attributes
    ds.attrs['title'] = 'MITgcm KPP Outputs'
    ds.attrs['source'] = 'MITgcm KPP'
    ds.attrs['institution'] = 'MITgcm'
    ds.attrs['experiment'] = experiment_name
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['input_uuid'] = run_uuid
    ds.attrs['description'] = 'KPP outputs (mixing coefficients, HBL) from MITgcm'
    ds.attrs['conventions'] = 'CF-1.8'
    ds.attrs['kppmix_direct_inputs'] = 'present' if has_kppmix_direct_inputs else 'absent'

    return ds


def _get_param_units(param: str) -> str:
    """Get units for KPP parameters."""
    units_map = {
        # Background mixing
        'viscAz': 'm^2/s', 'diffKzS': 'm^2/s', 'diffKzT': 'm^2/s',
        # Physical constants
        'gravity': 'm/s^2', 'rhoConst': 'kg/m^3', 'HeatCapacity_Cp': 'J/(kg*K)',
        # Boundary layer depth parameters
        'Ricr': 'dimensionless', 'cekman': 'dimensionless', 'cmonob': 'dimensionless',
        'concv': 'dimensionless', 'hbf': 'dimensionless',
        # Surface layer parameters
        'epsilon': 'dimensionless', 'vonk': 'dimensionless', 'dB_dz': '1/s^2',
        # Interior mixing parameters
        'Riinfty': 'dimensionless', 'BVSQcon': '1/s^2',
        'difm0': 'm^2/s', 'difs0': 'm^2/s', 'dift0': 'm^2/s',
        'difmcon': 'm^2/s', 'difscon': 'm^2/s', 'diftcon': 'm^2/s',
        # Shape function coefficients
        'conc1': 'dimensionless', 'conam': 'dimensionless', 'concm': 'dimensionless',
        'conc2': 'dimensionless', 'zetam': 'dimensionless',
        'conas': 'dimensionless', 'concs': 'dimensionless',
        'conc3': 'dimensionless', 'zetas': 'dimensionless',
        # Double diffusion
        'Rrho0': 'dimensionless', 'dsfmax': 'm^2/s',
        # Regularization
        'epsln': 'dimensionless', 'phepsi': 'dimensionless',
        # Nonlocal transport
        'cstar': 'dimensionless',
        # Minimum boundary layer depth
        'minKPPhbl': 'm',
        # Lookup table parameters
        'zmin': 'm^3/s^3', 'zmax': 'm^3/s^3',
        'umin': 'm/s', 'umax': 'm/s',
        'deltaz': 'm^3/s^3', 'deltau': 'm/s',
        # Integer parameters
        'num_v_smooth_Ri': 'dimensionless',
        # 1DMIX-034 part 2: salt-plume distribution parameters
        'PlumeMethod': 'dimensionless', 'Npower': 'dimensionless',
        'salt_plume_volume': 'boolean',
        # Boolean flags - runtime
        'KPP_ghatUseTotalDiffus': 'boolean',
        'KPPuseDoubleDiff': 'boolean',
        'LimitHblStable': 'boolean',
        'KPPwriteState': 'boolean',
        'KPPuseSWfrac3D': 'boolean',
        # Boolean flags - CPP compile-time options
        'use_ghat': 'boolean',
        'smooth_shsq': 'boolean',
        'smooth_dvsq': 'boolean',
        'smooth_dbloc': 'boolean',
        'smooth_dens': 'boolean',
        'smooth_visc': 'boolean',
        'smooth_diff': 'boolean',
        'estimate_uref': 'boolean',
        'match_diffusivities': 'boolean',
        'match_derivatives': 'boolean',
        'smooth_regularisation': 'boolean',
        'scale_shearmixing': 'boolean',
        'exclude_shear_mix': 'boolean',
        'exclude_doublediff': 'boolean',
        'vertically_smooth_ri': 'boolean',
        'shortwave_heating': 'boolean'
    }
    return units_map.get(param, '')


def _get_param_description(param: str) -> str:
    """Get description for KPP parameters."""
    desc_map = {
        # Background mixing
        'viscAz': 'Background vertical viscosity',
        'diffKzS': 'Background vertical diffusivity for salt',
        'diffKzT': 'Background vertical diffusivity for temperature',
        # Physical constants
        'gravity': 'Acceleration due to gravity',
        'rhoConst': 'Reference density',
        'HeatCapacity_Cp': 'Specific heat capacity of seawater',
        # Boundary layer depth parameters
        'Ricr': 'Critical bulk Richardson number for boundary layer depth',
        'cekman': 'Coefficient for Ekman depth',
        'cmonob': 'Coefficient for Monin-Obukhov depth',
        'concv': 'Ratio of interior to entrainment buoyancy frequency',
        'hbf': 'Fraction of hbl for absorbed solar radiation contribution',
        # Surface layer parameters
        'epsilon': 'Non-dimensional extent of surface layer',
        'vonk': 'Von Karman constant',
        'dB_dz': 'Maximum dB/dz in mixed layer',
        # Interior mixing parameters
        'Riinfty': 'Local Richardson number limit for shear instability',
        'BVSQcon': 'Brunt-Vaisala squared threshold for convection',
        'difm0': 'Maximum viscosity due to shear instability',
        'difs0': 'Maximum scalar diffusivity due to shear instability',
        'dift0': 'Maximum temperature diffusivity due to shear instability',
        'difmcon': 'Viscosity due to convective instability',
        'difscon': 'Scalar diffusivity due to convective instability',
        'diftcon': 'Temperature diffusivity due to convective instability',
        # Shape function coefficients
        'conc1': 'Shape function coefficient c1',
        'conam': 'Shape function coefficient am',
        'concm': 'Shape function coefficient cm',
        'conc2': 'Shape function coefficient c2',
        'zetam': 'Shape function coefficient zetam',
        'conas': 'Shape function coefficient as',
        'concs': 'Shape function coefficient cs',
        'conc3': 'Shape function coefficient c3',
        'zetas': 'Shape function coefficient zetas',
        # Double diffusion
        'Rrho0': 'Density ratio limit for double diffusion',
        'dsfmax': 'Maximum diffusivity for salt fingering',
        # Regularization
        'epsln': 'Small number for regularization',
        'phepsi': 'Small number for regularization',
        # Nonlocal transport
        'cstar': 'Proportionality coefficient for nonlocal transport',
        # Minimum boundary layer depth
        'minKPPhbl': 'Minimum boundary layer depth',
        # Lookup table parameters
        'zmin': 'Minimum zehat in lookup table',
        'zmax': 'Maximum zehat in lookup table',
        'umin': 'Minimum ustar in lookup table',
        'umax': 'Maximum ustar in lookup table',
        'deltaz': 'Delta zehat in lookup table',
        'deltau': 'Delta ustar in lookup table',
        # Integer parameters
        'num_v_smooth_Ri': 'Number of vertical smoothing passes for Richardson number',
        # 1DMIX-034 part 2: salt-plume distribution parameters
        'PlumeMethod': 'Salt plume vertical distribution method (1=power/uniform, '
                       'this port only implements 1; 2=exp, 3=overshoot, 5=dump-at-top, 6=reverse-of-1)',
        'Npower': 'Salt plume distribution power for PlumeMethod=1 (0=uniform, this port only implements 0)',
        'salt_plume_volume': 'SALT_PLUME_VOLUME compile-time variant (accumulate boplume over levels, not implemented)',
        # Boolean flags - runtime
        'KPP_ghatUseTotalDiffus': 'Use total diffusivity (not just KPP) for ghat computation',
        # 1DMIX-059: captured here so a future capture that enables this is
        # detected, not replayed blind -- the Python port has NO
        # double-diffusion code path (KPP_DOUBLEDIFF is unported), and
        # run_kpp_from_netcdf_input.py's KPPuseDoubleDiff->use_doublediff
        # map feeds this value straight into KPPParameters, whose
        # __post_init__ now raises NotImplementedError if it is nonzero
        # rather than silently running the capture through unimplemented
        # physics.
        'KPPuseDoubleDiff': 'Include double diffusion contributions '
                            '(NOT IMPLEMENTED in the Python port -- '
                            'KPPParameters raises NotImplementedError if '
                            'True, 1DMIX-059)',
        'LimitHblStable': 'Limit hbl depth under stable conditions',
        'KPPwriteState': 'Write KPP state to file (diagnostic only)',
        'KPPuseSWfrac3D': 'Use 3D spatially-varying shortwave water type',
        # Boolean flags - CPP compile-time options
        # KPP_GHAT gates applying ghat to the tracer flux, not computing it --
        # MITgcm's blmix computes ghat unconditionally regardless of this flag
        # (1DMIX-058).
        'use_ghat': 'Apply nonlocal transport term to tracer flux (KPP_GHAT)',
        'smooth_shsq': 'Smooth shear horizontally (KPP_SMOOTH_SHSQ)',
        'smooth_dvsq': 'Smooth dVsq horizontally (KPP_SMOOTH_DVSQ)',
        'smooth_dbloc': 'Smooth dbloc horizontally (KPP_SMOOTH_DBLOC)',
        'smooth_dens': 'Smooth all density variables (KPP_SMOOTH_DENS)',
        'smooth_visc': 'Smooth vertical viscosity (KPP_SMOOTH_VISC)',
        'smooth_diff': 'Smooth vertical diffusivity (KPP_SMOOTH_DIFF)',
        'estimate_uref': 'Resolution-independent surface velocity (KPP_ESTIMATE_UREF)',
        'match_diffusivities': 'Match diffusivities at BL base (NOT KPP_DO_NOT_MATCH_DIFFUSIVITIES)',
        'match_derivatives': 'Match derivatives at BL base (NOT KPP_DO_NOT_MATCH_DERIVATIVES)',
        'smooth_regularisation': 'Smooth regularization (KPP_SMOOTH_REGULARISATION)',
        'scale_shearmixing': 'Scale shear mixing via Polzin (KPP_SCALE_SHEARMIXING)',
        'exclude_shear_mix': 'Exclude shear mixing (EXCLUDE_KPP_SHEAR_MIX)',
        'exclude_doublediff': 'Exclude double diffusion (EXCLUDE_KPP_DOUBLEDIFF)',
        'vertically_smooth_ri': 'Vertically smooth Richardson number (ALLOW_KPP_VERTICALLY_SMOOTH)',
        'shortwave_heating': 'Shortwave penetration enabled (SHORTWAVE_HEATING)'
    }
    return desc_map.get(param, '')


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_mitgcm_split.py <output.txt> [experiment_name]")
        print("\nExample:")
        print("  python parse_mitgcm_split.py output_validation/output.txt 1D_ocean_ice_column")
        print("\nCreates:")
        print("  mitgcm_kpp_inputs.nc  - Inputs with UUID and parameters")
        print("  mitgcm_kpp_outputs.nc - Outputs with UUID link")
        sys.exit(1)

    output_file = Path(sys.argv[1])
    experiment_name = sys.argv[2] if len(sys.argv) >= 3 else None

    if not output_file.exists():
        print(f"Error: File not found: {output_file}")
        sys.exit(1)

    print("="*70)
    print("MITgcm KPP Validation: Split Input/Output Format")
    print("="*70)

    # Parse
    inputs_ds, outputs_ds = parse_mitgcm_split(output_file, experiment_name)

    # Save
    inputs_file = output_file.parent / 'mitgcm_kpp_inputs.nc'
    outputs_file = output_file.parent / 'mitgcm_kpp_outputs.nc'

    print(f"\nSaving files...")
    encoding = {var: {'zlib': True, 'complevel': 4} for var in inputs_ds.data_vars}
    inputs_ds.to_netcdf(inputs_file, encoding=encoding)
    print(f"  Inputs:  {inputs_file} ({inputs_file.stat().st_size/1024:.1f} KB)")

    encoding = {var: {'zlib': True, 'complevel': 4} for var in outputs_ds.data_vars}
    outputs_ds.to_netcdf(outputs_file, encoding=encoding)
    print(f"  Outputs: {outputs_file} ({outputs_file.stat().st_size/1024:.1f} KB)")

    print(f"\n✅ Success!")
    print(f"   UUID: {inputs_ds.attrs['uuid']}")
    print(f"   Experiment: {inputs_ds.attrs['experiment']}")
    print(f"   Forcing validation data: {inputs_ds.attrs['forcing_validation_data']}")
    if inputs_ds.attrs['forcing_validation_data'] == 'present':
        print("     -> Python validation will verify forcing computation (ustar, bo, bosol)")
    else:
        print("     -> Only mixing scheme will be validated (forcing assumed correct)")

    # Show key parameters if present
    key_params = ['viscAz', 'diffKzS', 'diffKzT', 'gravity', 'rhoConst',
                  'Ricr', 'Riinfty', 'difm0', 'epsilon', 'vonk']
    present_params = [k for k in key_params if k in inputs_ds.attrs]
    if present_params:
        print(f"\n   Key Parameters (showing {len(present_params)} of {len([k for k in inputs_ds.attrs if k.startswith('PARAM_') or k in key_params])}):")
        for p in present_params:
            print(f"     {p}: {inputs_ds.attrs[p]:.6e}")

    print("\n" + "="*70)
    print("Next step: python run_kpp_from_split.py mitgcm_kpp_inputs.nc")
    print("="*70)


if __name__ == '__main__':
    main()
