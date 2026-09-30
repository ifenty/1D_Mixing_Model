#!/usr/bin/env python3
"""
Parse MITgcm KPP validation output to separate input and output NetCDF files.

Creates two files:
  - mitgcm_kpp_inputs.nc:  State, forcing, grid, parameters (UUID-tagged)
  - mitgcm_kpp_outputs.nc: Mixing coefficients, HBL (UUID-linked)

This allows:
  - Reusing inputs with different Python versions
  - Comparing outputs from multiple runs
  - Clear provenance tracking

Streaming (1DMIX-065): ``output.txt`` is read line by line and each completed
timestep (all tiles) is appended to the NetCDF files and then dropped, so peak
memory is one timestep of arrays plus the fixed metadata, independent of file
length. The old implementation accumulated every value of every timestep in
Python dicts and built the arrays at the end; a 13.8 GB ``global_oce_latlon``
capture (720 timesteps x 4 tiles) then exhausted 27 GB of RAM. The engine
(two passes, ordering requirements, what is guaranteed identical to the old
output) is documented in ``capture_stream.py``; this file supplies the KPP
line grammar, variable tables, parameter/grid blocks and global attributes.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import xarray as xr

from capture_stream import (ParserSpec, VarDef, ffloat, now_iso,
                            stream_convert)


def parse_mitgcm_split(output_file: Path, inputs_path: Path,
                       outputs_path: Path,
                       experiment_name: str = None) -> str:
    """Stream ``output_file`` into ``inputs_path`` / ``outputs_path``.

    Memory is bounded by one timestep (see module docstring). Returns the run
    UUID recorded as ``uuid`` in the inputs file and ``input_uuid`` in the
    outputs file.
    """
    output_file = Path(output_file)
    print(f"Parsing MITgcm KPP validation output: {output_file}")

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

    return stream_convert(output_file, experiment_name, SPEC,
                          inputs_path, outputs_path)


def _parse_line(tag: str, parts: List[str]) -> Optional[List[tuple]]:
    """One KPP data line -> [(variable, i, j, k, value), ...] (tile-local,
    zero-based i/j/k; k=None for horizontal variables), or None for an
    unrecognised tag. A malformed field raises ValueError/IndexError and the
    caller drops the whole line, as the old parser did."""
    if tag == 'INPUT_STATE':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('temperature', i, j, k, ffloat(parts[4])),
                ('salinity', i, j, k, ffloat(parts[5])),
                ('u_velocity', i, j, k, ffloat(parts[6])),
                ('v_velocity', i, j, k, ffloat(parts[7]))]

    if tag == 'INPUT_FORCING':
        i, j = int(parts[1])-1, int(parts[2])-1
        updates = [('ustar', i, j, None, ffloat(parts[3])),
                   ('bo', i, j, None, ffloat(parts[4])),
                   ('bosol', i, j, None, ffloat(parts[5])),
                   ('tau_x', i, j, None, ffloat(parts[6])),
                   ('tau_y', i, j, None, ffloat(parts[7]))]
        # Optional: raw surface fluxes for forcing validation (backwards
        # compatible). Legacy extended format (pre-1DMIX-013 fix; still
        # emitted by some older captures -- q_net/fw_flux there are actually
        # MITgcm's surfaceForcingT/surfaceForcingS, NOT true raw Qnet/EmPmR,
        # see 1DMIX-013):
        #   INPUT_FORCING,i,j,ustar,bo,bosol,tau_x,tau_y,q_net,q_sw,fw_flux
        # 1DMIX-013 fix: new format emits genuinely raw MITgcm state (Qnet,
        # Qsw, EmPmR, saltFlux -- all FFIELDS.h COMMON-block fields,
        # upward-positive convention) instead of the pre-converted
        # surfaceForcingT/S. Distinct *_raw keys so this never collides with
        # the legacy (buggy) q_net/fw_flux semantics. Mutually exclusive with
        # the legacy branch (exact part-count dispatch) since a 12-part
        # new-format line also satisfies ">= 11".
        #   INPUT_FORCING,i,j,ustar,bo,bosol,tau_x,tau_y,
        #     Qnet_raw,Qsw_raw,EmPmR_raw,saltFlux_raw
        if len(parts) == 12:
            updates += [('qnet_raw', i, j, None, ffloat(parts[8])),
                        ('qsw_raw', i, j, None, ffloat(parts[9])),
                        ('empmr_raw', i, j, None, ffloat(parts[10])),
                        ('saltflux_raw', i, j, None, ffloat(parts[11]))]
        elif len(parts) >= 11:
            updates += [('q_net', i, j, None, ffloat(parts[8])),
                        ('q_sw', i, j, None, ffloat(parts[9])),
                        ('fw_flux', i, j, None, ffloat(parts[10]))]
        return updates

    if tag == 'INPUT_CORIOLIS':
        i, j = int(parts[1])-1, int(parts[2])-1
        return [('f_coriolis', i, j, None, ffloat(parts[3]))]

    if tag == 'INPUT_SALTPLUME':
        # 1DMIX-034 part 2: boplume(i,j,1) and SaltPlumeDepth(i,j), both
        # already computed locally by KPP_FORCING_SURF/salt plume depth
        # diagnosis -- new, purely additive capture (kpp_calc.F INPUT_FORCING
        # dump, guarded #ifdef ALLOW_SALT_PLUME exactly like INPUT_SWATT,
        # emitting 0.0/0.0 when compiled out). Needed to port the salt-plume
        # term in diagnose_bl_depth's bfsfc.
        i, j = int(parts[1])-1, int(parts[2])-1
        return [('boplume', i, j, None, ffloat(parts[3])),
                ('sp_depth', i, j, None, ffloat(parts[4]))]

    if tag == 'INPUT_SWATT':
        # KPPMIX direct "I" argument (bldepth) whenever SHORTWAVE_HEATING is
        # active; k runs 1..Nr+1 (one more level than shsq/dbloc/dVsq/Ritop).
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('swatt', i, j, k, ffloat(parts[4]))]

    if tag == 'OUTPUT_MIXING':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('visc_az', i, j, k, ffloat(parts[4])),
                ('diff_kz_s', i, j, k, ffloat(parts[5])),
                ('diff_kz_t', i, j, k, ffloat(parts[6])),
                ('ghat', i, j, k, ffloat(parts[7]))]

    if tag == 'OUTPUT_HBL':
        i, j = int(parts[1])-1, int(parts[2])-1
        return [('hbl', i, j, None, ffloat(parts[3]))]

    if tag == 'OUTPUT_DIAGNOSTICS':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        updates = [('shear_sq', i, j, k, ffloat(parts[4])),
                   ('buoy_freq_sq', i, j, k, ffloat(parts[5])),
                   ('richardson', i, j, k, ffloat(parts[6]))]
        # dVsq/Ritop: KPPMIX's direct "I"-only arguments, dumped verbatim
        # (unmodified by KPPMIX) so the standalone KPPMIX-only harness can
        # replay it without STATEKPP/KPP_FORCING_SURF. Older captures predate
        # these columns.
        if len(parts) >= 9:
            updates += [('dVsq', i, j, k, ffloat(parts[7])),
                        ('Ritop', i, j, k, ffloat(parts[8]))]
        return updates

    if tag == 'OUTPUT_RIB':
        # 1DMIX-025: bldepth's own real bulk Richardson number
        # (kpp_routines.F), exposed via KPPMIX's new output argument --
        # ground truth for the Python port's own Rib profile, distinct from
        # 'richardson' above (which is dbloc/shsq, the *local* Ri used by
        # Ri_iwmix, not bldepth's bulk Rib).
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('bulk_ri', i, j, k, ffloat(parts[4]))]

    if tag == 'OUTPUT_BFSFC':
        # 1DMIX-025: bldepth's final (post-LimitHblStable-clamp) surface
        # buoyancy forcing, exposed via KPPMIX's new kppBfsfc output argument.
        i, j = int(parts[1])-1, int(parts[2])-1
        return [('bfsfc_final', i, j, None, ffloat(parts[3]))]

    return None


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
            drF.append(ffloat(parts[2]))
            rF.append(ffloat(parts[3]))
            rC.append(ffloat(parts[4]))
    return {'nr': len(drF), 'drF': np.array(drF), 'rF': np.array(rF), 'rC': np.array(rC)}


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


def _inputs_coords(grid_info: Dict) -> Dict:
    return {
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


def _outputs_coords(grid_info: Dict) -> Dict:
    return {
        'depth': (['z'], grid_info['rC'], {
            'long_name': 'Cell center depth', 'units': 'm', 'positive': 'up'
        }),
        'depth_iface': (['z_iface'], grid_info['rF'], {
            'long_name': 'Interface depth', 'units': 'm', 'positive': 'up'
        }),
    }


def _dim_sizes(nx: int, ny: int, nz: int) -> Dict[str, int]:
    # z_swatt has one more level than z (swatt runs 1..Nr+1).
    return {'x': nx, 'y': ny, 'z': nz, 'z_iface': nz, 'z_swatt': nz + 1}


# Variable tables. `optional` variables exist in the file only if at least one
# data line supplied a value for them (the old parser's has_* flags).
_INPUT_VARS = [
    VarDef('temperature', ('x', 'y', 'z'), {
        'long_name': 'Potential temperature', 'units': 'degC',
        'standard_name': 'sea_water_potential_temperature'
    }),
    VarDef('salinity', ('x', 'y', 'z'), {
        'long_name': 'Salinity', 'units': 'psu',
        'standard_name': 'sea_water_salinity'
    }),
    VarDef('u_velocity', ('x', 'y', 'z'), {
        'long_name': 'Zonal velocity', 'units': 'm/s',
        'standard_name': 'eastward_sea_water_velocity'
    }),
    VarDef('v_velocity', ('x', 'y', 'z'), {
        'long_name': 'Meridional velocity', 'units': 'm/s',
        'standard_name': 'northward_sea_water_velocity'
    }),
    VarDef('ustar', ('x', 'y'), {
        'long_name': 'Friction velocity', 'units': 'm/s',
        'description': 'Surface friction velocity from wind stress'
    }),
    VarDef('bo', ('x', 'y'), {
        'long_name': 'Turbulent buoyancy forcing', 'units': 'm^2/s^3',
        'description': 'Non-penetrating buoyancy forcing at surface'
    }),
    VarDef('bosol', ('x', 'y'), {
        'long_name': 'Radiative buoyancy forcing', 'units': 'm^2/s^3',
        'description': 'Penetrating shortwave buoyancy forcing'
    }),
    VarDef('tau_x', ('x', 'y'), {
        'long_name': 'Zonal wind stress per unit density', 'units': 'm^2/s^2'
    }),
    VarDef('tau_y', ('x', 'y'), {
        'long_name': 'Meridional wind stress per unit density', 'units': 'm^2/s^2'
    }),
    VarDef('f_coriolis', ('x', 'y'), {
        'long_name': 'Coriolis parameter', 'units': '1/s',
        'standard_name': 'coriolis_parameter'
    }),
    # Optional: raw surface fluxes for forcing validation (legacy format;
    # see 1DMIX-013 -- q_net/fw_flux here are actually surfaceForcingT/S)
    VarDef('q_net', ('x', 'y'), {
        'long_name': 'Net surface heat flux (excluding shortwave)',
        'units': 'W/m^2',
        'standard_name': 'surface_net_heat_flux',
        'description': 'Positive into ocean (warming)',
        'comment': 'Used to compute bo; for forcing validation only'
    }, optional=True),
    VarDef('q_sw', ('x', 'y'), {
        'long_name': 'Surface shortwave radiation',
        'units': 'W/m^2',
        'standard_name': 'surface_shortwave_flux',
        'description': 'Positive into ocean (heating)',
        'comment': 'Used to compute bosol; for forcing validation only'
    }, optional=True),
    VarDef('fw_flux', ('x', 'y'), {
        'long_name': 'Freshwater flux (E-P-R)',
        'units': 'kg/m^2/s',
        'standard_name': 'freshwater_flux',
        'description': 'Positive into ocean (freshening)',
        'comment': 'Used to compute bo; for forcing validation only'
    }, optional=True),
    # 1DMIX-013 fix: genuinely raw MITgcm state (distinct *_raw names from
    # the legacy q_net/q_sw/fw_flux above, which are actually MITgcm's
    # already-converted surfaceForcingT/surfaceForcingS -- see kpp_calc.F
    # ::KPP_OUTPUT_VALIDATION and model/src/external_forcing_surf.F:
    # 217-234,296-320). All four are plain FFIELDS.h COMMON-block fields,
    # MITgcm's own "upward positive" sign convention (model/inc/FFIELDS.h:
    # 17-38,44-53) -- NOT yet converted to the "positive into ocean"
    # convention _compute_surface_forcing's raw-flux parameters expect.
    # scripts/run_kpp_from_netcdf_input.py's forcing-derivation applies the
    # exact (derived-and-verified, see 1DMIX-013 evidence) combination before
    # calling KPPDriver.compute_mixing.
    VarDef('qnet_raw', ('x', 'y'), {
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
    }, optional=True),
    VarDef('qsw_raw', ('x', 'y'), {
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
    }, optional=True),
    VarDef('empmr_raw', ('x', 'y'), {
        'long_name': 'Net upward freshwater flux (Evap-Precip-Runoff)',
        'units': 'kg/m^2/s',
        'standard_name': 'water_evaporation_flux',
        'description': (
            'MITgcm FFIELDS.h EmPmR, verbatim: upward positive '
            '(typical range -1e-4..1e-4).'
        ),
        'comment': '1DMIX-013: raw capture, replaces mislabeled legacy fw_flux'
    }, optional=True),
    VarDef('saltflux_raw', ('x', 'y'), {
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
    }, optional=True),
    VarDef('swatt', ('x', 'y', 'z_swatt'), {
        'long_name': 'Shortwave attenuation fraction (KPPMIX direct input)',
        'units': 'dimensionless',
        'description': (
            'Fraction of solar shortwave flux penetrating to each '
            'level (SWFrac3D); Nr+1 levels. Direct KPPMIX "I" '
            'argument, needed whenever SHORTWAVE_HEATING is active.'
        )
    }, optional=True),
    VarDef('boplume', ('x', 'y'), {
        'long_name': 'Surface haline buoyancy forcing from salt plumes',
        'units': 'm^2/s^3',
        'description': (
            '1DMIX-034: boplume(i,j,1), KPP_FORCING_SURF\'s surface-'
            'level (SALT_PLUME_VOLUME-undef branch) haline buoyancy '
            'forcing from rejected brine (kpp_forcing_surf.F:262-273). '
            'Direct KPPMIX "I" argument, needed whenever useSALT_PLUME '
            'is active; 0.0 otherwise.'
        )
    }, optional=True),
    VarDef('sp_depth', ('x', 'y'), {
        'long_name': 'Salt plume penetration depth',
        'units': 'm',
        'description': (
            '1DMIX-034: SaltPlumeDepth(i,j), the e-folding depth used '
            'by SALT_PLUME_FRAC to distribute boplume vertically '
            '(pkg/salt_plume/salt_plume_calc_depth.F). Direct KPPMIX '
            '"I" argument (SPDepth), needed whenever useSALT_PLUME is '
            'active; 0.0 otherwise.'
        )
    }, optional=True),
]

_OUTPUT_VARS = [
    VarDef('visc_az', ('x', 'y', 'z_iface'), {
        'long_name': 'Vertical viscosity (MITgcm KPP)', 'units': 'm^2/s',
        'description': 'KPP vertical viscosity at cell interfaces',
        'cell_location': 'interface'
    }),
    VarDef('diff_kz_s', ('x', 'y', 'z_iface'), {
        'long_name': 'Vertical diffusivity for salt (MITgcm KPP)', 'units': 'm^2/s',
        'description': 'KPP vertical diffusivity for salinity',
        'cell_location': 'interface'
    }),
    VarDef('diff_kz_t', ('x', 'y', 'z_iface'), {
        'long_name': 'Vertical diffusivity for temperature (MITgcm KPP)', 'units': 'm^2/s',
        'description': 'KPP vertical diffusivity for temperature',
        'cell_location': 'interface'
    }),
    VarDef('ghat', ('x', 'y', 'z'), {
        'long_name': 'Nonlocal transport (MITgcm KPP)', 'units': 's/m^2',
        'description': 'KPP nonlocal transport at cell centers',
        'cell_location': 'center'
    }),
    VarDef('hbl', ('x', 'y'), {
        'long_name': 'Boundary layer depth (MITgcm KPP)', 'units': 'm',
        'description': 'KPP boundary layer depth',
        'standard_name': 'ocean_mixed_layer_thickness_defined_by_sigma_theta'
    }),
    VarDef('shear_sq', ('x', 'y', 'z_iface'), {
        'long_name': 'Vertical shear squared', 'units': '1/s^2',
        'description': 'Square of vertical velocity shear at cell interfaces',
        'cell_location': 'interface'
    }),
    VarDef('buoy_freq_sq', ('x', 'y', 'z_iface'), {
        'long_name': 'Buoyancy frequency squared (N²)', 'units': '1/s^2',
        'description': 'Square of buoyancy frequency (stratification) at cell interfaces',
        'cell_location': 'interface'
    }),
    VarDef('richardson', ('x', 'y', 'z_iface'), {
        'long_name': 'Richardson number', 'units': 'dimensionless',
        'description': 'Gradient Richardson number (Ri = N²/S²) at cell interfaces',
        'cell_location': 'interface'
    }),
    VarDef('dVsq', ('x', 'y', 'z_iface'), {
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
    }, optional=True),
    VarDef('Ritop', ('x', 'y', 'z_iface'), {
        'long_name': 'Numerator of bulk Richardson number',
        'units': 'm^2/s^2',
        'description': (
            'Direct KPPMIX "I"-only input (Ritop), dumped verbatim/'
            'unmodified. See dVsq description for why it lives here.'
        ),
        'cell_location': 'interface'
    }, optional=True),
    VarDef('bulk_ri', ('x', 'y', 'z_iface'), {
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
    }, optional=True),
    VarDef('bfsfc_final', ('x', 'y'), {
        'long_name': "bldepth's final surface buoyancy forcing",
        'units': 'm^2/s^3',
        'description': (
            "1DMIX-025: bldepth's bfsfc AFTER the LimitHblStable Ekman/"
            'Monin-Obukhov clamp is applied (the value used to compute '
            'that clamp, not the earlier per-trial-level bfsfc used '
            'inside the Rib search loop), exposed via a new KPPMIX '
            'output argument added for this issue.'
        )
    }, optional=True),
]


def _inputs_attrs(experiment_name, output_file, run_uuid, params, seen) -> Dict:
    attrs = {
        'title': 'MITgcm KPP Inputs',
        'source': 'MITgcm with KPP instrumentation',
        'institution': 'MITgcm',
        'experiment': experiment_name,
        'output_file_path': str(Path(output_file).absolute()),
        'creation_date': now_iso(),
        'uuid': run_uuid,
        'description': 'KPP inputs (state, forcing, grid) from MITgcm for validation',
        'conventions': 'CF-1.8',
        'forcing_validation_data': (
            'present' if ('q_net' in seen or 'qnet_raw' in seen) else 'absent'
        ),
        'swatt_data': 'present' if 'swatt' in seen else 'absent',
        'saltplume_data': 'present' if 'boplume' in seen else 'absent',
    }
    # Model parameters
    for param_name, param_value in params.items():
        attrs[param_name] = param_value
        attrs[f'{param_name}_units'] = _get_param_units(param_name)
        attrs[f'{param_name}_description'] = _get_param_description(param_name)
    return attrs


def _outputs_attrs(experiment_name, run_uuid, seen) -> Dict:
    return {
        'title': 'MITgcm KPP Outputs',
        'source': 'MITgcm KPP',
        'institution': 'MITgcm',
        'experiment': experiment_name,
        'creation_date': now_iso(),
        'input_uuid': run_uuid,
        'description': 'KPP outputs (mixing coefficients, HBL) from MITgcm',
        'conventions': 'CF-1.8',
        'kppmix_direct_inputs': 'present' if 'dVsq' in seen else 'absent',
    }


SPEC = ParserSpec(
    prefix='KPP',
    # Tags whose (i, j) fix the tile-local index extent (sNx/sNy).
    extent_tags=frozenset({'INPUT_STATE', 'OUTPUT_MIXING', 'OUTPUT_HBL',
                           'OUTPUT_RIB', 'OUTPUT_BFSFC'}),
    parse_parameters=_parse_parameters,
    parse_grid=_parse_grid,
    parse_line=_parse_line,
    inputs_vars=_INPUT_VARS,
    outputs_vars=_OUTPUT_VARS,
    inputs_coords=_inputs_coords,
    outputs_coords=_outputs_coords,
    dim_sizes=_dim_sizes,
    inputs_attrs=_inputs_attrs,
    outputs_attrs=_outputs_attrs,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_mitgcm_split.py <output.txt> [experiment_name]")
        print("\nExample:")
        print("  python parse_mitgcm_split.py output_validation/output.txt 1D_ocean_ice_column")
        print("\nCreates (next to output.txt):")
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

    inputs_file = output_file.parent / 'mitgcm_kpp_inputs.nc'
    outputs_file = output_file.parent / 'mitgcm_kpp_outputs.nc'

    # Parse and save (streamed: files are written timestep by timestep)
    print(f"\nSaving files...")
    parse_mitgcm_split(output_file, inputs_file, outputs_file, experiment_name)
    print(f"  Inputs:  {inputs_file} ({inputs_file.stat().st_size/1024:.1f} KB)")
    print(f"  Outputs: {outputs_file} ({outputs_file.stat().st_size/1024:.1f} KB)")

    with xr.open_dataset(inputs_file) as inputs_ds:
        attrs = dict(inputs_ds.attrs)

    print(f"\n✅ Success!")
    print(f"   UUID: {attrs['uuid']}")
    print(f"   Experiment: {attrs['experiment']}")
    print(f"   Forcing validation data: {attrs['forcing_validation_data']}")
    if attrs['forcing_validation_data'] == 'present':
        print("     -> Python validation will verify forcing computation (ustar, bo, bosol)")
    else:
        print("     -> Only mixing scheme will be validated (forcing assumed correct)")

    # Show key parameters if present
    key_params = ['viscAz', 'diffKzS', 'diffKzT', 'gravity', 'rhoConst',
                  'Ricr', 'Riinfty', 'difm0', 'epsilon', 'vonk']
    present_params = [k for k in key_params if k in attrs]
    if present_params:
        print(f"\n   Key Parameters (showing {len(present_params)} of {len([k for k in attrs if k.startswith('PARAM_') or k in key_params])}):")
        for p in present_params:
            print(f"     {p}: {attrs[p]:.6e}")

    print("\n" + "="*70)
    print("Next step: python run_kpp_from_split.py mitgcm_kpp_inputs.nc")
    print("="*70)


if __name__ == '__main__':
    main()
