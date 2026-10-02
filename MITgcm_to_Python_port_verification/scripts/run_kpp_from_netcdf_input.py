#!/usr/bin/env python3
"""
Run Python KPP port using MITgcm NetCDF inputs.

This script:
1. Reads MITgcm input Dataset (parameters, state, forcing)
2. Extracts parameters from global attributes
3. For each (time, x, y) column:
   - Extracts state variables and forcing
   - Runs Python KPP with MITgcm's exact parameters
   - Stores outputs
4. Creates Python port Dataset with UUID provenance tracking
5. Optionally compares with MITgcm outputs if available

Tracer-point inputs (1DMIX-071): MITgcm forms KPP's shsq (kpp_calc.F:459-495), dVsq
(kpp_forcing_surf.F:463-504) and the horizontally smoothed dbloc (kpp_calc.F:276-289,
smooth_horiz kpp_routines.F:1318-1398) from the NEIGHBOURING columns, which the single-column
port cannot see. By default (`tracer_point_inputs=True`) this replay rebuilds them from the
neighbouring columns of the whole capture (scripts/tracer_point_inputs.py; periodic wrap =
MITgcm's default exchange) and passes them to `KPPDriver.compute_mixing` through its keyword-only
`shsq_forcing` / `dvsq_forcing` / `dbloc_smooth_forcing`. `tracer_point_inputs=False` / `--column-local`
restores the former column-local replay (du**2 + dv**2, no horizontal smoothing). A capture
built with KPP_ESTIMATE_UREF, KPP_SMOOTH_DVSQ, KPP_SMOOTH_DENS, KPP_SMOOTH_VISC or KPP_SMOOTH_DIFF
raises NotImplementedError in the default mode. The smoothed dbloc is not captured, so its
reconstruction is validated only through its effect on the KPP outputs (docs: KPP_VALIDATION_RESULTS.md).

Usage:
  python run_kpp_from_netcdf_input.py <input_file.nc> [output_dir] [options]

Examples:
  python run_kpp_from_netcdf_input.py mitgcm_kpp_inputs_11k_1D.nc
  python run_kpp_from_netcdf_input.py inputs.nc outputs/
  python run_kpp_from_netcdf_input.py inputs.nc --first 0 --last 9 -j 8
  python run_kpp_from_netcdf_input.py inputs.nc --first 100 --last 199 -j 4 outputs/

Options:
  --first N, --first-timestep N   First timestep to process (0-indexed, default: 0)
  --last N, --last-timestep N     Last timestep to process (0-indexed, inclusive, default: all)
  -j N, --jobs N                  Number of parallel workers (default: 1 = serial)
  --column-local                  Column-local shear/dVsq/dbloc (pre-1DMIX-071 replay)

Output location logic:
- If input from inputs_from_mitgcm/: saves to outputs_from_python/ with matching name
- Else if output_dir provided: saves to output_dir/python_kpp_outputs.nc
- Else: saves to input directory as python_kpp_outputs.nc
"""

import sys
import numpy as np
import xarray as xr
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List, Any, Optional
from multiprocessing import Pool, cpu_count

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'Vertical_Mixing_Models'))

from KPP.kpp_core_driver import KPPDriver, validate_zcoordinate_geometry
from KPP.kpp_parameters import KPPParameters
from main.eos import compute_buoyancy_gradients

sys.path.insert(0, str(Path(__file__).parent))
import tracer_point_inputs as tpi  # noqa: E402

# Try to import tqdm for progress bar
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Global variables for worker processes (set by _init_worker)
_worker_inputs_ds = None
_worker_driver = None
_worker_background_params = None
_worker_depth = None
_worker_cell_thickness = None
_worker_tracer_point = None  # dict of (n_time, x, y, nz) arrays or None (1DMIX-071)


def extract_parameters_from_inputs(ds: xr.Dataset, verbose: bool = True) -> Tuple[Dict, Dict, List, List]:
    """
    Extract KPP parameters from inputs Dataset global attributes.

    Only extracts parameters that are present in the NetCDF file.
    KPPParameters will use defaults for any missing parameters.

    Parameters
    ----------
    ds : xr.Dataset
        Input dataset with parameters in global attributes
    verbose : bool
        Print parameter extraction details

    Returns
    -------
    kpp_params : dict
        Parameters for KPPParameters() initialization
    background_params : dict
        Background mixing for compute_mixing() call
    found_params : list
        List of parameter names found in NetCDF
    missing_params : list
        List of parameter names NOT found (will use defaults)
    """

    # Map NetCDF attribute names to KPPParameters argument names
    param_map = {
        # Background mixing (special: used in compute_mixing(), not KPPParameters)
        'viscAz': 'background_visc',
        'diffKzS': 'background_diff_s',
        'diffKzT': 'background_diff_t',
        # Physical constants
        'gravity': 'gravity',
        'rhoConst': 'rho_const',
        'HeatCapacity_Cp': 'heat_capacity_cp',
        # Boundary layer depth parameters
        'Ricr': 'Ricr',
        'cekman': 'cekman',
        'cmonob': 'cmonob',
        'concv': 'concv',
        'hbf': 'hbf',
        'minKPPhbl': 'min_kpp_hbl',
        # Surface layer parameters
        'epsilon': 'epsilon',
        'vonk': 'vonk',
        'dB_dz': 'dB_dz',
        # Interior mixing parameters
        'Riinfty': 'Riinfty',
        'BVSQcon': 'BVSQcon',
        'difm0': 'difm0',
        'difs0': 'difs0',
        'dift0': 'dift0',
        'difmcon': 'difmcon',
        'difscon': 'difscon',
        'diftcon': 'diftcon',
        'num_v_smooth_Ri': 'num_v_smooth_ri',
        # Nonlocal transport
        'cstar': 'cstar',
        # Shape function coefficients
        'conc1': 'conc1',
        'conam': 'conam',
        'concm': 'concm',
        'conc2': 'conc2',
        'zetam': 'zetam',
        'conas': 'conas',
        'concs': 'concs',
        'conc3': 'conc3',
        'zetas': 'zetas',
        # Double diffusion
        'Rrho0': 'Rrho0',
        'dsfmax': 'dsfmax',
        # Regularization
        'epsln': 'epsln',
        'phepsi': 'phepsi',
        # Lookup table parameters
        'zmin': 'zmin',
        'zmax': 'zmax',
        'umin': 'umin',
        'umax': 'umax',
        'deltaz': 'deltaz',  # Not used by Python, computed internally
        'deltau': 'deltau',  # Not used by Python, computed internally
        # Boolean flags - runtime
        'KPP_ghatUseTotalDiffus': 'ghat_use_total_diffus',
        # 1DMIX-059: KPPuseDoubleDiff maps straight into
        # KPPParameters.use_doublediff, whose __post_init__ now raises
        # NotImplementedError if the captured value is nonzero -- this port
        # has no double-diffusion code path, so a future capture that
        # enables it is caught here rather than replayed blind.
        'KPPuseDoubleDiff': 'use_doublediff',
        'LimitHblStable': 'limit_hbl_stable',
        'KPPwriteState': 'kpp_write_state',
        'KPPuseSWfrac3D': 'use_sw_frac_3d',
        # Boolean flags - CPP compile-time options
        'use_ghat': 'use_ghat',
        'smooth_shsq': 'smooth_shsq',
        'smooth_dvsq': 'smooth_dvsq',
        'smooth_dbloc': 'smooth_dbloc',
        'smooth_dens': 'smooth_dens',
        'smooth_visc': 'smooth_visc',
        'smooth_diff': 'smooth_diff',
        'estimate_uref': 'estimate_uref',
        'match_diffusivities': 'match_diffusivities',
        'match_derivatives': 'match_derivatives',
        'smooth_regularisation': 'smooth_regularisation',
        'scale_shearmixing': 'scale_shearmixing',
        'exclude_shear_mix': 'exclude_shear_mix',
        'exclude_doublediff': 'exclude_doublediff',
        'vertically_smooth_ri': 'vertically_smooth_ri',
        'shortwave_heating': 'shortwave_heating',
        # 1DMIX-034: salt plume runtime + compile-time flags. Without
        # these, KPPParameters silently defaulted both to False for any
        # capture with salt plume active (e.g. seaice_obcs), bypassing
        # its own deliberate NotImplementedError guard (salt-plume
        # physics is not ported) and silently producing wrong bfsfc/hbl.
        'useSALT_PLUME': 'use_salt_plume',
        'allow_salt_plume': 'allow_salt_plume',
        # 1DMIX-034 part 2: salt-plume distribution parameters, needed so
        # KPPParameters' narrowed NotImplementedError guard can tell a
        # ported configuration (PlumeMethod=1, Npower=0, SALT_PLUME_VOLUME
        # unset) from an unported one, instead of defaulting silently to
        # the ported values regardless of what the captured MITgcm run
        # actually used.
        'PlumeMethod': 'plume_method',
        'Npower': 'npower',
        'salt_plume_volume': 'salt_plume_volume',
        # Shortwave penetration runtime flag (int, mirrors MITgcm
        # selectPenetratingSW; 0=off, >=1=on). Distinct from the
        # shortwave_heating CPP flag above -- both must be set for
        # KPPDriver._compute_surface_forcing's use_penetrating_sw gate
        # (kpp_core_driver.py) to activate, matching kpp_calc.F's own
        # `IF (selectPenetratingSW .GE. 1)` (kpp_forcing_surf.F:231).
        # Previously missing from this map, so select_penetrating_sw kept
        # its KPPParameters default of 0 even when the captured MITgcm run
        # had selectPenetratingSW=1, silently forcing bosol=0.0 for every
        # such run regardless of the source run's actual configuration.
        'selectPenetratingSW': 'select_penetrating_sw',
    }

    # Extract parameters present in NetCDF
    kpp_params = {}
    background_params = {}  # For compute_mixing() call
    found_params = []
    missing_params = []

    # Boolean parameter names for type conversion
    boolean_params = {
        'KPP_ghatUseTotalDiffus', 'KPPuseDoubleDiff', 'LimitHblStable',
        'KPPwriteState', 'KPPuseSWfrac3D',
        'use_ghat', 'smooth_shsq', 'smooth_dvsq', 'smooth_dbloc',
        'smooth_dens', 'smooth_visc', 'smooth_diff', 'estimate_uref',
        'match_diffusivities', 'match_derivatives', 'smooth_regularisation',
        'scale_shearmixing', 'exclude_shear_mix', 'exclude_doublediff',
        'vertically_smooth_ri', 'shortwave_heating',
        'useSALT_PLUME', 'allow_salt_plume',
        # 1DMIX-034 part 2: compile-time SALT_PLUME_VOLUME variant flag.
        'salt_plume_volume'
    }

    for nc_name, py_name in param_map.items():
        if nc_name in ds.attrs:
            value = ds.attrs[nc_name]

            # Convert type appropriately
            if nc_name in ('num_v_smooth_Ri', 'selectPenetratingSW',
                           # 1DMIX-034 part 2: integer salt-plume
                           # distribution parameters.
                           'PlumeMethod', 'Npower'):
                value = int(value)
            elif nc_name in boolean_params:
                # Boolean params stored as int (0 or 1) in NetCDF
                value = bool(int(value))
            else:
                value = float(value)

            # Route to appropriate dict
            if nc_name == 'viscAz':
                background_params['background_visc'] = value
            elif nc_name == 'diffKzS':
                background_params['background_diff_s'] = value
            elif nc_name == 'diffKzT':
                background_params['background_diff_t'] = value
            elif nc_name in ['deltaz', 'deltau']:
                # Skip - computed internally by Python
                pass
            else:
                kpp_params[py_name] = value

            found_params.append(nc_name)
        else:
            missing_params.append(nc_name)

    if verbose:
        print(f"\n  ===== KPP PARAMETER SUMMARY =====")
        print(f"  Found in NetCDF:   {len(found_params)}")
        print(f"  Missing (default): {len(missing_params)}")

        if found_params:
            print(f"\n  Found parameters by category:")
            categories = {
                'Background mixing': ['viscAz', 'diffKzS', 'diffKzT'],
                'Physical constants': ['gravity', 'rhoConst', 'HeatCapacity_Cp'],
                'Boundary layer': ['Ricr', 'cekman', 'cmonob', 'concv', 'hbf', 'minKPPhbl'],
                'Surface layer': ['epsilon', 'vonk', 'dB_dz'],
                'Interior mixing': ['Riinfty', 'BVSQcon', 'difm0', 'difs0', 'dift0',
                                   'difmcon', 'difscon', 'diftcon', 'num_v_smooth_Ri'],
                'Nonlocal transport': ['cstar'],
                'Shape functions': ['conc1', 'conam', 'concm', 'conc2', 'zetam',
                                   'conas', 'concs', 'conc3', 'zetas'],
                'Double diffusion': ['Rrho0', 'dsfmax'],
                'Regularization': ['epsln', 'phepsi'],
                'Lookup table': ['zmin', 'zmax', 'umin', 'umax'],
                'Runtime flags': ['KPP_ghatUseTotalDiffus', 'KPPuseDoubleDiff',
                                 'LimitHblStable', 'KPPwriteState', 'KPPuseSWfrac3D',
                                 'selectPenetratingSW', 'useSALT_PLUME',
                                 'PlumeMethod', 'Npower', 'salt_plume_volume'],
                'CPP options': ['use_ghat', 'smooth_shsq', 'smooth_dvsq', 'smooth_dbloc',
                               'smooth_dens', 'smooth_visc', 'smooth_diff', 'estimate_uref',
                               'match_diffusivities', 'match_derivatives', 'smooth_regularisation',
                               'scale_shearmixing', 'exclude_shear_mix', 'exclude_doublediff',
                               'vertically_smooth_ri', 'shortwave_heating', 'allow_salt_plume']
            }

            for category, params_in_cat in categories.items():
                found_in_cat = [p for p in params_in_cat if p in found_params]
                if found_in_cat:
                    print(f"    {category}: {', '.join(found_in_cat)}")

        print(f"  =================================\n")

    return kpp_params, background_params, found_params, missing_params


def _init_worker(inputs_file_str: str, kpp_params_dict: Dict, background_params: Dict,
                 tracer_point: Optional[Dict] = None):
    """
    Initialize worker process with shared data.

    Called once per worker process to load the dataset and initialize KPP driver.
    This avoids reloading the dataset for every column.
    """
    global _worker_inputs_ds, _worker_driver, _worker_background_params
    global _worker_depth, _worker_cell_thickness, _worker_tracer_point

    # Need to set up path again in worker process
    sys.path.insert(0, str(Path(__file__).parent.parent / '1D_Mixing_Model'))

    import xarray as xr
    from KPP.kpp_core_driver import KPPDriver
    from KPP.kpp_parameters import KPPParameters

    _worker_inputs_ds = xr.open_dataset(inputs_file_str)
    kpp_params = KPPParameters(**kpp_params_dict)
    _worker_driver = KPPDriver(params=kpp_params)
    _worker_background_params = background_params
    _worker_depth = _worker_inputs_ds.depth.values
    _worker_cell_thickness = _worker_inputs_ds.cell_thickness.values
    _worker_tracer_point = tracer_point


def derive_raw_flux_forcing(
    inputs_ds: 'xr.Dataset',
    t_in_idx: int,
    i: int,
    j: int,
    salt_surf: float,
    rho_const: float,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Derive KPPDriver.compute_mixing's (q_net, q_sw, fw_flux) raw-flux
    arguments from whichever raw-forcing columns this input NetCDF
    captured.

    1DMIX-013 finding (round 0): KPPDriver._compute_surface_forcing's raw
    -flux formula is a correct port of kpp_forcing_surf.F:224-238 fed by
    MITgcm's own raw-to-forcing conversion in
    model/src/external_forcing_surf.F:217-234,296-320, and it is
    genuinely exercised with real physical fluxes by
    main/mixing_adapter.py::KPPAdapter.compute_mixing for production
    scenario runs -- it must not be changed. The legacy
    `mitgcm_kpp_inputs_1D_10_kppmix_extend.nc` capture's q_net/fw_flux
    columns are NOT raw fluxes despite the name: kpp_calc.F::
    KPP_OUTPUT_VALIDATION wrote MITgcm's own already-converted
    surfaceForcingT/surfaceForcingS into them (see that file's
    INPUT_FORCING_HEADER comment, pre-fix). Feeding those directly into
    _compute_surface_forcing's raw-flux formula double-applies the
    Cp/rhoConst/sign conversion, producing the ~22-29x, opposite-sign
    `bo` mismatch that motivated this issue.

    1DMIX-013 fix (round 1): new captures instead emit genuinely raw
    MITgcm state -- qnet_raw/qsw_raw/empmr_raw/saltflux_raw, i.e. FFIELDS.h's
    Qnet/Qsw/EmPmR/saltFlux verbatim (upward-positive convention,
    model/inc/FFIELDS.h:17-53). This function applies the exact
    combination (derived from external_forcing_surf.F:217-234,296-320 and
    empirically verified against MITgcm's own bo/bosol ground truth to
    <1.3% -- limited by the separate, out-of-scope 1DMIX-017 EOS ttalpha
    bug, not by this derivation) that reproduces the true
    surfaceForcingT/surfaceForcingS MITgcm itself would have computed,
    THEN inverts _compute_surface_forcing's own (unmodified) formula to
    recover the (q_net, q_sw, fw_flux) values that make it reconstruct
    that surfaceForcingT/surfaceForcingS exactly:

      surfaceForcingT = -(Qnet - Qsw) / (Cp * rhoConst)   [SHORTWAVE_HEATING,
                                                             external_forcing_surf.F:226-231]
      surfaceForcingS = -saltFlux/rhoConst + EmPmR*salt_surf/rhoConst
                                                            [external_forcing_surf.F:233-234,314-317;
                                                             convertFW2Salt=-1 branch, confirmed via
                                                             ini_parms.F:648-651 given
                                                             useRealFreshWaterFlux=.TRUE.]

    _compute_surface_forcing (use_penetrating_sw=True, matching this
    capture's shortwave_heating=True/selectPenetratingSW=1) computes:
      q_non_sw   = q_net - q_sw ;  temp_flux = q_non_sw/(rho_const*Cp)
      salt_flux  = -fw_flux * salt_surf
    Requiring temp_flux == surfaceForcingT and salt_flux ==
    surfaceForcingS for ALL (ttalpha, ssbeta) -- i.e. matching
    kpp_forcing_surf.F's bo/bosol term-by-term, not just numerically at
    one timestep -- and q_sw == Qsw (bosol's formula is standalone and
    only matches MITgcm with q_sw fed unflipped; verified independently
    against a raw MDS Qsw/Qnet snapshot, see 1DMIX-013 round-1 evidence)
    forces:
      q_net = 2*Qsw - Qnet
      fw_flux = saltFlux/(rhoConst*salt_surf) - EmPmR/rhoConst

    Both were verified to reproduce MITgcm's actual bo (heat- and
    salt-term contributions individually, and the full sum) using this
    experiment's own captured Qnet/Qsw/EmPmR/saltFlux snapshot values
    to <1.3e-9 absolute / <1.3% relative -- the residual is the known,
    separately-filed, out-of-scope 1DMIX-017 ttalpha bug, not this
    formula.

    Falls back to the legacy (buggy, pre-1DMIX-013-fix) q_net/q_sw/
    fw_flux columns if only those are present, for backward
    compatibility with not-yet-regenerated captures -- callers should
    prefer regenerated captures with qnet_raw/qsw_raw/empmr_raw/
    saltflux_raw.

    Returns
    -------
    (q_net, q_sw, fw_flux) : each float or None if no raw-forcing
        columns are present in `inputs_ds` at all.
    """
    if ('qnet_raw' in inputs_ds and 'qsw_raw' in inputs_ds
            and 'empmr_raw' in inputs_ds and 'saltflux_raw' in inputs_ds):
        qnet = float(inputs_ds.qnet_raw.isel(time=t_in_idx, x=i, y=j).values)
        qsw = float(inputs_ds.qsw_raw.isel(time=t_in_idx, x=i, y=j).values)
        empmr = float(inputs_ds.empmr_raw.isel(time=t_in_idx, x=i, y=j).values)
        saltflux = float(inputs_ds.saltflux_raw.isel(time=t_in_idx, x=i, y=j).values)
        q_net_val = 2.0 * qsw - qnet
        q_sw_val = qsw
        fw_flux_val = saltflux / (rho_const * salt_surf) - empmr / rho_const
        return q_net_val, q_sw_val, fw_flux_val

    if 'q_net' in inputs_ds and 'q_sw' in inputs_ds and 'fw_flux' in inputs_ds:
        # Legacy format: known mislabeled (surfaceForcingT/S, not raw
        # Qnet/EmPmR) per 1DMIX-013 -- kept only for old, not-yet-
        # regenerated captures. Do not trust for new forcing validation.
        q_net_val = float(inputs_ds.q_net.isel(time=t_in_idx, x=i, y=j).values)
        q_sw_val = float(inputs_ds.q_sw.isel(time=t_in_idx, x=i, y=j).values)
        fw_flux_val = float(inputs_ds.fw_flux.isel(time=t_in_idx, x=i, y=j).values)
        return q_net_val, q_sw_val, fw_flux_val

    return None, None, None


def _is_land_column(theta: np.ndarray, salt: np.ndarray) -> bool:
    """True if this column is masked out (not real ocean).

    MITgcm's own land convention is capture-dependent: some captures (e.g.
    single-column 1D_ocean_ice_column) never have land and never emit NaN;
    others (e.g. multi-column lab_sea) mask land columns with exact 0.0 at
    every level for every field (confirmed by inspecting the raw capture
    directly), not NaN -- so checking NaN alone silently missed every land
    column there (1DMIX-011), feeding degenerate all-zero T/S into KPP and
    producing a nonsensical fallback hbl at the domain bottom. A real ocean
    column is never all NaN and never exactly 0.0 for both theta and salt at
    every level simultaneously, so both checks are safe.

    Rechecked (1DMIX-025) for the ALLOW_SHELFICE case (no KPP+ShelfIce
    capture exists yet, but this helper is shared with GGL90's identical
    isomip case, which does): this check already handles a column masked
    (dry) at the TOP with real wet ocean below correctly without
    modification, since it requires EVERY level to be 0.0/NaN, not just
    level 0 -- see _wet_level_range.
    """
    return bool(np.all(np.isnan(theta)) or (np.all(theta == 0.0) and np.all(salt == 0.0)))


def _wet_level_range(theta: np.ndarray) -> Tuple[int, int]:
    """(start, count) of a column's real, contiguous wet region (1DMIX-011).

    Was `_wet_level_count(theta) -> int`, which assumed the wet region
    always starts at index 0 and returned only its length -- correct for
    every previously-tested KPP experiment, where a column shallower than
    the grid's deepest level is zero-padded by MITgcm below its real
    seafloor only (bathymetry masking is monotonic from the surface: wet
    from level 0 down to the seafloor, dry below). For a real captured
    lab_sea column with true depth 45 m (top 4 of 23 levels wet), the
    untruncated driver call returns hbl=5450.0 (the grid's deepest level);
    truncating the column to just its 4 wet levels (start=0, count=4)
    returns hbl=45.0, an exact match to MITgcm.

    Generalized (1DMIX-025) for GGL90's identical helper's ALLOW_SHELFICE
    case (isomip): a column under a floating ice shelf is masked (dry, exact
    0.0) from the surface down to kTopC-1, then wet from kTopC to the real
    seafloor -- start>0 there. No KPP+ShelfIce capture exists yet to
    exercise this directly, but this helper is shared verbatim with
    run_ggl90_from_netcdf_input.py's identical fix (confirmed live and
    necessary for isomip's real GGL90 capture), so the same latent gap
    applies here for any future KPP+ShelfIce experiment; fixing both now
    keeps them mirrored rather than leaving KPP's copy stale.

    Returns (0, len(theta)) for a fully wet column (every previously-tested
    KPP experiment's common case) -- an exact behavioral no-op there.

    Raises
    ------
    ValueError
        If the wet region is not contiguous (a dry level sandwiched between
        two wet levels) -- see run_ggl90_from_netcdf_input.py's identical
        function for why this is not supported.
    """
    wet = np.flatnonzero(theta != 0.0)
    if wet.size == 0:
        return 0, 0
    start, end = int(wet[0]), int(wet[-1])
    count = end - start + 1
    if count != wet.size:
        raise ValueError(
            "Column has a non-contiguous wet region (dry level(s) "
            "sandwiched between wet levels) -- not supported by this "
            "harness's single-contiguous-slice driver call convention."
        )
    return start, count


def build_tracer_point_arrays(inputs_ds: xr.Dataset, kpp_params: KPPParameters,
                              first_timestep: int, last_timestep: int,
                              periodic_x: bool = True, periodic_y: bool = True,
                              chunk: int = 8) -> Dict[str, Optional[np.ndarray]]:
    """MITgcm's neighbour-dependent KPP inputs for timesteps first..last (1DMIX-071).

    Returns {'shsq', 'dvsq', 'dbloc_smooth'}, each (n_time, x, y, nz) (index 0 = `first_timestep`);
    'dbloc_smooth' is None when the capture was built without KPP_SMOOTH_DBLOC (the driver's own
    unsmoothed dbloc is then exactly what MITgcm used). Formulas and their MITgcm line
    numbers: scripts/tracer_point_inputs.py. The raw dbloc of every wet column is the port's own
    `compute_buoyancy_gradients` on the column's wet range (the same call the driver makes).
    Processes `chunk` timesteps at a time (bounded memory; the arrays only couple columns of one
    timestep). Raises NotImplementedError for capture options this does not reproduce.
    """
    tpi.check_supported_kpp_options(inputs_ds.attrs)
    smooth_shsq = bool(int(inputs_ds.attrs.get('smooth_shsq', 0)))
    smooth_dbloc = bool(int(inputs_ds.attrs.get('smooth_dbloc', 0)))
    n_time = last_timestep - first_timestep + 1
    nx, ny, nz = len(inputs_ds.x), len(inputs_ds.y), len(inputs_ds.z)
    depth = inputs_ds.depth.values
    shsq = np.zeros((n_time, nx, ny, nz))
    dvsq = np.zeros((n_time, nx, ny, nz))
    dbs = np.zeros((n_time, nx, ny, nz)) if smooth_dbloc else None
    for c0 in range(0, n_time, chunk):
        c1 = min(n_time, c0 + chunk)
        sl = slice(first_timestep + c0, first_timestep + c1)
        u = inputs_ds.u_velocity.isel(time=sl).values
        v = inputs_ds.v_velocity.isel(time=sl).values
        shsq[c0:c1] = tpi.kpp_shsq(u, v, smooth_shsq, periodic_x, periodic_y)
        dvsq[c0:c1] = tpi.kpp_dvsq(u, v, periodic_x, periodic_y)
        if smooth_dbloc:
            theta = inputs_ds.temperature.isel(time=sl).values
            salt = inputs_ds.salinity.isel(time=sl).values
            raw = np.zeros_like(theta)
            for t in range(theta.shape[0]):
                for i in range(nx):
                    for j in range(ny):
                        if _is_land_column(theta[t, i, j], salt[t, i, j]):
                            continue
                        ws, n = _wet_level_range(theta[t, i, j])
                        w = slice(ws, ws + n)
                        raw[t, i, j, w] = compute_buoyancy_gradients(
                            theta[t, i, j, w], salt[t, i, j, w], depth[w], kpp_params.rho_const,
                            kpp_params.gravity, use_jmd95=True)[1]
            dbs[c0:c1] = tpi.kpp_dbloc_smooth(raw, theta != 0.0, periodic_x, periodic_y)
    return {'shsq': shsq, 'dvsq': dvsq, 'dbloc_smooth': dbs}


def _tracer_point_kwargs(tp: Optional[Dict], t_out_idx: int, i: int, j: int,
                         wet_start: int, wet_end: int) -> Dict[str, np.ndarray]:
    """The three keyword-only driver inputs for one column's wet range ({} if `tp` is None)."""
    if tp is None:
        return {}
    kw = {'shsq_forcing': tp['shsq'][t_out_idx, i, j, wet_start:wet_end],
          'dvsq_forcing': tp['dvsq'][t_out_idx, i, j, wet_start:wet_end]}
    if tp['dbloc_smooth'] is not None:
        kw['dbloc_smooth_forcing'] = tp['dbloc_smooth'][t_out_idx, i, j, wet_start:wet_end]
    return kw


def _process_column(task: Tuple[int, int, int, int]) -> Optional[Dict]:
    """
    Worker function to process one (t, i, j) column.

    Parameters
    ----------
    task : tuple
        (t_in_idx, t_out_idx, i, j) - timestep indices and spatial coordinates

    Returns
    -------
    dict or None
        Results dictionary with outputs, or None if skipped (land point)
    """
    t_in_idx, t_out_idx, i, j = task

    # Use global worker data
    inputs_ds = _worker_inputs_ds
    driver = _worker_driver
    background_params = _worker_background_params
    depth = _worker_depth
    cell_thickness = _worker_cell_thickness

    # Extract inputs for this column
    theta = inputs_ds.temperature.isel(time=t_in_idx, x=i, y=j).values
    salt = inputs_ds.salinity.isel(time=t_in_idx, x=i, y=j).values
    u = inputs_ds.u_velocity.isel(time=t_in_idx, x=i, y=j).values
    v = inputs_ds.v_velocity.isel(time=t_in_idx, x=i, y=j).values

    # Pre-computed forcing values
    ustar = float(inputs_ds.ustar.isel(time=t_in_idx, x=i, y=j).values)
    bo = float(inputs_ds.bo.isel(time=t_in_idx, x=i, y=j).values)
    bosol = float(inputs_ds.bosol.isel(time=t_in_idx, x=i, y=j).values)
    tau_x = float(inputs_ds.tau_x.isel(time=t_in_idx, x=i, y=j).values)
    tau_y = float(inputs_ds.tau_y.isel(time=t_in_idx, x=i, y=j).values)
    f_coriolis = float(inputs_ds.f_coriolis.isel(time=t_in_idx, x=i, y=j).values)

    # Salt-plume forcing (1DMIX-034 part 2; optional -- absent for every
    # capture that predates this fix or never compiled ALLOW_SALT_PLUME in).
    if 'boplume' in inputs_ds and 'sp_depth' in inputs_ds:
        boplume_val = float(inputs_ds.boplume.isel(time=t_in_idx, x=i, y=j).values)
        sp_depth_val = float(inputs_ds.sp_depth.isel(time=t_in_idx, x=i, y=j).values)
    else:
        boplume_val, sp_depth_val = 0.0, 0.0

    # Raw surface fluxes (optional, for forcing validation) -- see
    # derive_raw_flux_forcing's docstring (1DMIX-013) for the exact
    # raw-to-forcing derivation and its citations.
    q_net_val, q_sw_val, fw_flux_val = derive_raw_flux_forcing(
        inputs_ds, t_in_idx, i, j, salt_surf=salt[0],
        rho_const=driver.params.rho_const,
    )

    # Skip land points (see _is_land_column for why this checks both NaN and
    # all-zero conventions -- 1DMIX-011)
    if _is_land_column(theta, salt):
        return None

    # Truncate to this column's real wet (start, count) range -- see
    # _wet_level_range (1DMIX-025, superseding the former dry-bottom-only
    # _wet_level_count; 1DMIX-011). Full-depth grid arrays are truncated the
    # same way so indices still line up.
    wet_start, nz_wet = _wet_level_range(theta)
    nz_full = len(theta)
    wet_end = wet_start + nz_wet

    try:
        output = driver.compute_mixing(
            theta=theta[wet_start:wet_end],
            salt=salt[wet_start:wet_end],
            u_vel=u[wet_start:wet_end],
            v_vel=v[wet_start:wet_end],
            depth=depth[wet_start:wet_end],
            cell_thickness=cell_thickness[wet_start:wet_end],
            tau_x=tau_x,
            tau_y=tau_y,
            q_net=q_net_val,
            q_sw=q_sw_val,
            fw_flux=fw_flux_val,
            coriol=f_coriolis,
            background_visc=background_params.get('background_visc', 1.0e-4),
            background_diff_s=background_params.get('background_diff_s', 1.0e-5),
            background_diff_t=background_params.get('background_diff_t', 1.0e-5),
            ustar_forcing=ustar,
            bo_forcing=bo,
            bosol_forcing=bosol,
            boplume_forcing=boplume_val,
            sp_depth_forcing=sp_depth_val,
            **_tracer_point_kwargs(_worker_tracer_point, t_out_idx, i, j, wet_start, wet_end),
        )

        # Pad profile fields back to the full grid depth with zeros outside
        # the real wet range (below the real seafloor, or -- 1DMIX-025,
        # untested for KPP yet -- above a real ice-shelf draft), matching
        # MITgcm's own zero-padding convention there (confirmed directly on
        # its visc_az/ghat output for a known-shallow column) -- hbl needs
        # no padding, it is already a scalar.
        def _pad(arr):
            if nz_wet == nz_full:
                return arr
            return np.concatenate([
                np.zeros(wet_start), arr, np.zeros(nz_full - wet_end),
            ])

        # Return results as dict (need to convert arrays to lists for pickling)
        return {
            't_out_idx': t_out_idx,
            'i': i,
            'j': j,
            'visc_az': _pad(output.visc_az),
            'diff_kz_s': _pad(output.diff_kz_s),
            'diff_kz_t': _pad(output.diff_kz_t),
            'ghat': _pad(output.ghat),
            'hbl': output.hbl,
            'ustar_computed': output.ustar_computed,
            'bo_computed': output.bo_computed,
            'bosol_computed': output.bosol_computed,
        }

    except Exception as e:
        return {
            'error': str(e),
            't_in_idx': t_in_idx,
            't_out_idx': t_out_idx,
            'i': i,
            'j': j
        }


def run_python_kpp_on_dataset(inputs_ds: xr.Dataset, verbose: bool = True,
                               first_timestep: int = None, last_timestep: int = None,
                               n_jobs: int = 1, inputs_file: Path = None,
                               tracer_point_inputs: bool = True, periodic_x: bool = True,
                               periodic_y: bool = True) -> xr.Dataset:
    """
    Run Python KPP on all columns from inputs Dataset.

    Parameters
    ----------
    inputs_ds : xr.Dataset
        Inputs with state, forcing, grid, parameters
    verbose : bool
        Print progress
    first_timestep : int, optional
        First timestep to process (0-indexed). If None, start from 0.
    last_timestep : int, optional
        Last timestep to process (0-indexed, inclusive). If None, process to end.
    n_jobs : int, optional
        Number of parallel worker processes. If 1 (default), run serially.
        If > 1, use multiprocessing to parallelize across columns.
    inputs_file : Path, optional
        Path to input NetCDF file (required if n_jobs > 1 for workers to reload dataset)
    tracer_point_inputs : bool, optional
        (1DMIX-071, default True) pass MITgcm's neighbour-dependent shsq, dVsq and smoothed dbloc,
        rebuilt from the neighbouring captured columns (`build_tracer_point_arrays`), to the
        driver. False reproduces the former column-local replay. NotImplementedError if the
        capture was built with KPP_ESTIMATE_UREF/SMOOTH_DVSQ/SMOOTH_DENS/SMOOTH_VISC/SMOOTH_DIFF.
    periodic_x, periodic_y : bool, optional
        Neighbour rule beyond the domain edge (True = MITgcm's default periodic exchange).

    Returns
    -------
    xr.Dataset
        Python KPP outputs with UUID provenance tracking

    Raises
    ------
    ValueError
        If the input grid (`depth`/`cell_thickness`) is not a metres-scale
        z-coordinate column (1DMIX-072; e.g. the pressure-coordinate
        `global_ocean.cs32x15` capture, 1DMIX-040), raised by
        `main.column_grid.validate_zcoordinate_geometry` (re-exported by
        `KPP.kpp_core_driver`) before any column is
        run. (Per-column exceptions are otherwise recorded as NaN cells.)
    """

    if verbose:
        print("Running Python KPP...")
        print(f"  Experiment: {inputs_ds.attrs.get('experiment', 'unknown')}")
        print(f"  Input UUID: {inputs_ds.attrs['uuid']}")

        # Check if forcing validation data is available
        forcing_val_status = inputs_ds.attrs.get('forcing_validation_data', 'absent')
        has_raw_flux_vars = (
            ('q_net' in inputs_ds and 'q_sw' in inputs_ds and 'fw_flux' in inputs_ds)
            or ('qnet_raw' in inputs_ds and 'qsw_raw' in inputs_ds
                and 'empmr_raw' in inputs_ds and 'saltflux_raw' in inputs_ds)
        )
        if forcing_val_status == 'present' or has_raw_flux_vars:
            print("  Forcing validation: ENABLED (raw fluxes present)")
            print("    -> Will validate Python forcing computation against MITgcm")
        else:
            print("  Forcing validation: DISABLED (raw fluxes not present)")
            print("    -> Using pre-computed forcing only (mixing scheme validation)")

    # Extract parameters from global attributes
    kpp_params_dict, background_params, found_params, missing_params = \
        extract_parameters_from_inputs(inputs_ds, verbose=verbose)

    # Initialize KPP driver with parameters from NetCDF
    kpp_params = KPPParameters(**kpp_params_dict)
    driver = KPPDriver(params=kpp_params)

    # Get dimensions
    n_time_full = len(inputs_ds.time)
    nx = len(inputs_ds.x)
    ny = len(inputs_ds.y)
    nz = len(inputs_ds.z)

    # Determine timestep range to process
    if first_timestep is None:
        first_timestep = 0
    if last_timestep is None:
        last_timestep = n_time_full - 1

    # Validate timestep range
    first_timestep = max(0, first_timestep)
    last_timestep = min(n_time_full - 1, last_timestep)

    if first_timestep > last_timestep:
        raise ValueError(f"Invalid timestep range: first={first_timestep}, last={last_timestep}")

    n_time = last_timestep - first_timestep + 1

    if verbose:
        if first_timestep > 0 or last_timestep < n_time_full - 1:
            print(f"  Processing timesteps {first_timestep} to {last_timestep} (of {n_time_full} total)")
        else:
            print(f"  Processing all {n_time} timesteps")

    # Extract grid info
    depth = inputs_ds.depth.values
    cell_thickness = inputs_ds.cell_thickness.values

    # Fail fast on non-z-coordinate geometry (1DMIX-072). KPPDriver.compute_mixing
    # rejects it too, but both column loops below turn ANY per-column exception
    # into a NaN cell ("except Exception ... continue" / the worker's error dict),
    # which would re-create the silent all-NaN output the driver guard exists to
    # prevent (e.g. the pressure-coordinate global_ocean.cs32x15 capture, 1DMIX-040).
    validate_zcoordinate_geometry(depth, cell_thickness, scheme="KPP")

    # Allocate output arrays
    visc_az_out = np.full((n_time, nx, ny, nz), np.nan)
    diff_kz_s_out = np.full((n_time, nx, ny, nz), np.nan)
    diff_kz_t_out = np.full((n_time, nx, ny, nz), np.nan)
    ghat_out = np.full((n_time, nx, ny, nz), np.nan)
    hbl_out = np.full((n_time, nx, ny), np.nan)

    # Forcing validation outputs (Python-computed forcing)
    ustar_computed_out = np.full((n_time, nx, ny), np.nan)
    bo_computed_out = np.full((n_time, nx, ny), np.nan)
    bosol_computed_out = np.full((n_time, nx, ny), np.nan)

    # Process each timestep and column
    total_columns = n_time * nx * ny

    # MITgcm's neighbour-dependent shsq / dVsq / smoothed dbloc (1DMIX-071)
    tracer_point = None
    if tracer_point_inputs:
        tracer_point = build_tracer_point_arrays(
            inputs_ds, kpp_params, first_timestep, last_timestep, periodic_x, periodic_y)

    # Choose serial or parallel processing
    if n_jobs > 1:
        # PARALLEL PROCESSING
        if inputs_file is None:
            raise ValueError("inputs_file must be provided when n_jobs > 1")

        if verbose:
            print(f"  Using {n_jobs} parallel workers")

        # Build list of all tasks
        tasks = []
        for t_out_idx, t_in_idx in enumerate(range(first_timestep, last_timestep + 1)):
            for i in range(nx):
                for j in range(ny):
                    tasks.append((t_in_idx, t_out_idx, i, j))

        # Process in parallel with progress bar
        processed = 0
        failed = 0

        with Pool(processes=n_jobs,
                  initializer=_init_worker,
                  initargs=(str(inputs_file), kpp_params_dict, background_params,
                            tracer_point)) as pool:

            # Use imap_unordered for better progress reporting
            if HAS_TQDM and verbose:
                results_iter = tqdm(pool.imap_unordered(_process_column, tasks, chunksize=10),
                                    total=len(tasks),
                                    desc="Processing columns",
                                    unit="col")
            else:
                results_iter = pool.imap_unordered(_process_column, tasks, chunksize=10)

            for result in results_iter:
                if result is None:
                    # Land point, skip
                    continue

                if 'error' in result:
                    if verbose and failed < 10:  # Only print first 10 errors
                        print(f"  Warning: Failed at t={result['t_in_idx']}, "
                              f"i={result['i']}, j={result['j']}: {result['error']}")
                    failed += 1
                    continue

                # Store outputs
                t_out_idx = result['t_out_idx']
                i = result['i']
                j = result['j']

                visc_az_out[t_out_idx, i, j, :] = result['visc_az']
                diff_kz_s_out[t_out_idx, i, j, :] = result['diff_kz_s']
                diff_kz_t_out[t_out_idx, i, j, :] = result['diff_kz_t']
                ghat_out[t_out_idx, i, j, :] = result['ghat']
                hbl_out[t_out_idx, i, j] = result['hbl']

                if result['ustar_computed'] is not None:
                    ustar_computed_out[t_out_idx, i, j] = result['ustar_computed']
                    bo_computed_out[t_out_idx, i, j] = result['bo_computed']
                    bosol_computed_out[t_out_idx, i, j] = result['bosol_computed']

                processed += 1

        if verbose and not HAS_TQDM:
            print(f"\n✅ Parallel processing complete: {processed}/{total_columns} columns processed, "
                  f"{failed} failed")
            if failed > 10:
                print(f"   (suppressed {failed-10} additional error messages)")

    else:
        # SERIAL PROCESSING (original code)
        processed = 0

        for t_out_idx, t_in_idx in enumerate(range(first_timestep, last_timestep + 1)):
            for i in range(nx):
                for j in range(ny):
                    # Extract inputs for this column
                    theta = inputs_ds.temperature.isel(time=t_in_idx, x=i, y=j).values
                    salt = inputs_ds.salinity.isel(time=t_in_idx, x=i, y=j).values
                    u = inputs_ds.u_velocity.isel(time=t_in_idx, x=i, y=j).values
                    v = inputs_ds.v_velocity.isel(time=t_in_idx, x=i, y=j).values

                    # Pre-computed forcing values (always present for validation)
                    ustar = float(inputs_ds.ustar.isel(time=t_in_idx, x=i, y=j).values)
                    bo = float(inputs_ds.bo.isel(time=t_in_idx, x=i, y=j).values)
                    bosol = float(inputs_ds.bosol.isel(time=t_in_idx, x=i, y=j).values)
                    tau_x = float(inputs_ds.tau_x.isel(time=t_in_idx, x=i, y=j).values)
                    tau_y = float(inputs_ds.tau_y.isel(time=t_in_idx, x=i, y=j).values)
                    f_coriolis = float(inputs_ds.f_coriolis.isel(time=t_in_idx, x=i, y=j).values)

                    # Salt-plume forcing (1DMIX-034 part 2; optional -- see
                    # _process_column's identical derivation above).
                    if 'boplume' in inputs_ds and 'sp_depth' in inputs_ds:
                        boplume_val = float(inputs_ds.boplume.isel(time=t_in_idx, x=i, y=j).values)
                        sp_depth_val = float(inputs_ds.sp_depth.isel(time=t_in_idx, x=i, y=j).values)
                    else:
                        boplume_val, sp_depth_val = 0.0, 0.0

                    # Raw surface fluxes (optional, for forcing validation).
                    # If present, forcing validation happens automatically
                    # (Mode 3) -- see derive_raw_flux_forcing's docstring
                    # (1DMIX-013) for the exact raw-to-forcing derivation.
                    q_net_val, q_sw_val, fw_flux_val = derive_raw_flux_forcing(
                        inputs_ds, t_in_idx, i, j, salt_surf=salt[0],
                        rho_const=driver.params.rho_const,
                    )

                    # Skip land points (see _is_land_column -- 1DMIX-011)
                    if _is_land_column(theta, salt):
                        continue

                    # Truncate to this column's real wet (start, count)
                    # range -- see _wet_level_range (1DMIX-025, superseding
                    # the former dry-bottom-only _wet_level_count; 1DMIX-011).
                    wet_start, nz_wet = _wet_level_range(theta)
                    nz_full = len(theta)
                    wet_end = wet_start + nz_wet

                    # Run Python KPP with pre-computed MITgcm forcing
                    # All forcing values (ustar, bo, bosol) are pre-computed by MITgcm's
                    # kpp_forcing_surf.F and stored in the input NetCDF file.
                    #
                    # If raw surface fluxes are also provided, validate_forcing=True will
                    # verify that the Python port's _compute_surface_forcing matches MITgcm's
                    # forcing computation before proceeding with mixing calculation.
                    try:
                        output = driver.compute_mixing(
                            # ===== State Variables (3D) =====
                            theta=theta[wet_start:wet_end],  # Potential temperature [°C]
                            salt=salt[wet_start:wet_end],    # Salinity [psu]
                            u_vel=u[wet_start:wet_end],      # Zonal velocity [m/s]
                            v_vel=v[wet_start:wet_end],      # Meridional velocity [m/s]

                            # ===== Grid Geometry (1D) =====
                            depth=depth[wet_start:wet_end],  # Cell interface depths [m], negative down
                            cell_thickness=cell_thickness[wet_start:wet_end],  # Cell thickness [m], positive

                            # ===== Surface Fluxes (for forcing validation when available) =====
                            tau_x=tau_x,                    # Zonal wind stress [N/m²]
                            tau_y=tau_y,                    # Meridional wind stress [N/m²]
                            q_net=q_net_val,                # Net surface heat flux [W/m²]
                            q_sw=q_sw_val,                  # Shortwave radiation flux [W/m²]
                            fw_flux=fw_flux_val,            # Freshwater flux [kg/m²/s]

                            # ===== Physical Parameters =====
                            coriol=f_coriolis,              # Coriolis parameter [1/s]

                            # ===== Background Mixing =====
                            background_visc=background_params.get('background_visc', 1.0e-4),     # [m²/s]
                            background_diff_s=background_params.get('background_diff_s', 1.0e-5), # [m²/s]
                            background_diff_t=background_params.get('background_diff_t', 1.0e-5), # [m²/s]

                            # ===== Pre-computed Forcing (from MITgcm kpp_forcing_surf.F) =====
                            ustar_forcing=ustar,            # Friction velocity [m/s]
                            bo_forcing=bo,                  # Turbulent buoyancy forcing [m²/s³]
                            bosol_forcing=bosol,            # Radiative (shortwave) buoyancy forcing [m²/s³]
                            boplume_forcing=boplume_val,     # Salt-plume haline buoyancy forcing [m²/s³] (1DMIX-034)
                            sp_depth_forcing=sp_depth_val,   # Salt plume penetration depth [m] (1DMIX-034)
                            # MITgcm's neighbour-dependent shsq/dVsq/smoothed dbloc (1DMIX-071; {} = column-local)
                            **_tracer_point_kwargs(tracer_point, t_out_idx, i, j, wet_start, wet_end),
                            # Note: Mode determined automatically based on which params provided
                            # - If raw fluxes present → Mode 3 (forcing validation)
                            # - If only pre-computed → Mode 1 (use pre-computed)
                        )

                        # Store outputs, zero-padding profile fields outside
                        # the real wet range (below the real seafloor, or --
                        # 1DMIX-025, untested for KPP yet -- above a real
                        # ice-shelf draft) to match MITgcm's own convention
                        # there (see _wet_level_range).
                        pad_before, pad_after = wet_start, nz_full - wet_end
                        visc_az_out[t_out_idx, i, j, :] = np.pad(output.visc_az, (pad_before, pad_after))
                        diff_kz_s_out[t_out_idx, i, j, :] = np.pad(output.diff_kz_s, (pad_before, pad_after))
                        diff_kz_t_out[t_out_idx, i, j, :] = np.pad(output.diff_kz_t, (pad_before, pad_after))
                        ghat_out[t_out_idx, i, j, :] = np.pad(output.ghat, (pad_before, pad_after))
                        hbl_out[t_out_idx, i, j] = output.hbl

                        # Store Python-computed forcing (if validation was performed)
                        if output.ustar_computed is not None:
                            ustar_computed_out[t_out_idx, i, j] = output.ustar_computed
                            bo_computed_out[t_out_idx, i, j] = output.bo_computed
                            bosol_computed_out[t_out_idx, i, j] = output.bosol_computed

                        processed += 1

                    except Exception as e:
                        if verbose:
                            print(f"  Warning: Failed at t={t_in_idx}, i={i}, j={j}: {e}")
                        continue

            if verbose:
                print(f"  Completed timestep {t_in_idx+1} (output index {t_out_idx+1}/{n_time}) ({processed}/{total_columns} columns)")

        if verbose:
            print(f"\n✅ Serial processing complete: {processed}/{total_columns} columns processed")

    # Create output Dataset
    # Use only the timesteps that were processed
    time_slice = inputs_ds.time.isel(time=slice(first_timestep, last_timestep + 1))

    coords = {
        'time': time_slice,
        'x': inputs_ds.x,
        'y': inputs_ds.y,
        'depth': inputs_ds.depth,
        'depth_iface': inputs_ds.depth_iface,
    }

    data_vars = {
        'visc_az': (['time', 'x', 'y', 'z_iface'], visc_az_out, {
            'long_name': 'Vertical viscosity (Python KPP)',
            'units': 'm^2/s',
            'description': 'Python KPP vertical viscosity at cell interfaces',
            'cell_location': 'interface'
        }),
        'diff_kz_s': (['time', 'x', 'y', 'z_iface'], diff_kz_s_out, {
            'long_name': 'Vertical diffusivity for salt (Python KPP)',
            'units': 'm^2/s',
            'description': 'Python KPP vertical diffusivity for salinity',
            'cell_location': 'interface'
        }),
        'diff_kz_t': (['time', 'x', 'y', 'z_iface'], diff_kz_t_out, {
            'long_name': 'Vertical diffusivity for temperature (Python KPP)',
            'units': 'm^2/s',
            'description': 'Python KPP vertical diffusivity for temperature',
            'cell_location': 'interface'
        }),
        'ghat': (['time', 'x', 'y', 'z'], ghat_out, {
            'long_name': 'Nonlocal transport coefficient (Python KPP)',
            'units': 's/m^2',
            'description': 'Python KPP nonlocal transport at cell centers',
            'cell_location': 'center'
        }),
        'hbl': (['time', 'x', 'y'], hbl_out, {
            'long_name': 'Boundary layer depth (Python KPP)',
            'units': 'm',
            'description': 'Python KPP boundary layer depth',
            'standard_name': 'ocean_mixed_layer_thickness_defined_by_sigma_theta'
        }),
    }

    # Add Python-computed forcing if validation was performed
    if not np.all(np.isnan(ustar_computed_out)):
        data_vars['ustar_computed'] = (['time', 'x', 'y'], ustar_computed_out, {
            'long_name': 'Python-computed friction velocity',
            'units': 'm/s',
            'description': 'Friction velocity computed by Python _compute_surface_forcing (for validation)',
            'comment': 'Compare with input ustar to validate forcing computation'
        })
        data_vars['bo_computed'] = (['time', 'x', 'y'], bo_computed_out, {
            'long_name': 'Python-computed turbulent buoyancy forcing',
            'units': 'm^2/s^3',
            'description': 'Turbulent buoyancy forcing computed by Python (for validation)',
            'comment': 'Compare with input bo to validate forcing computation'
        })
        data_vars['bosol_computed'] = (['time', 'x', 'y'], bosol_computed_out, {
            'long_name': 'Python-computed radiative buoyancy forcing',
            'units': 'm^2/s^3',
            'description': 'Radiative buoyancy forcing computed by Python (for validation)',
            'comment': 'Compare with input bosol to validate forcing computation'
        })

    outputs_ds = xr.Dataset(data_vars=data_vars, coords=coords)

    # Global attributes with UUID provenance
    outputs_ds.attrs['title'] = 'Python KPP Port Outputs'
    outputs_ds.attrs['source'] = 'Python KPP port'
    outputs_ds.attrs['institution'] = 'ECCO 1D Mixing Model'
    outputs_ds.attrs['experiment'] = inputs_ds.attrs.get('experiment', 'unknown')
    outputs_ds.attrs['creation_date'] = datetime.now().isoformat()
    outputs_ds.attrs['input_uuid'] = inputs_ds.attrs['uuid']  # Provenance link
    outputs_ds.attrs['conventions'] = 'CF-1.8'
    outputs_ds.attrs['description'] = 'KPP outputs from Python port using MITgcm inputs'

    # Placeholders for provenance tracking (set by caller)
    outputs_ds.attrs['input_file_name'] = ''
    outputs_ds.attrs['input_file_path'] = ''

    # Copy parameter attributes from inputs for reference
    for attr in inputs_ds.attrs:
        if attr.startswith(('viscAz', 'diffKz', 'gravity', 'rho', 'Heat', 'Ricr', 'epsilon')):
            outputs_ds.attrs[attr] = inputs_ds.attrs[attr]

    return outputs_ds


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run Python KPP port using MITgcm NetCDF inputs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_kpp_from_netcdf_input.py inputs.nc -o outputs.nc
  python run_kpp_from_netcdf_input.py inputs.nc --output python_kpp_results.nc
  python run_kpp_from_netcdf_input.py inputs.nc -o out.nc --first 0 --last 9
  python run_kpp_from_netcdf_input.py inputs.nc -o out.nc -j 8 --first 100 --last 199

Required arguments:
  input_file            Input NetCDF file with MITgcm KPP forcing data
  -o, --output          Output NetCDF file path (required)
""")

    parser.add_argument('input_file', type=str,
                        help='Input NetCDF file with MITgcm data')
    parser.add_argument('-o', '--output', type=str, required=True,
                        dest='output_file',
                        help='Output NetCDF file path (required)')
    parser.add_argument('--first', '--first-timestep', type=int, default=None,
                        dest='first_timestep',
                        help='First timestep to process (0-indexed, default: 0)')
    parser.add_argument('--last', '--last-timestep', type=int, default=None,
                        dest='last_timestep',
                        help='Last timestep to process (0-indexed, inclusive, default: all)')
    parser.add_argument('-j', '--jobs', '--n-jobs', type=int, default=1,
                        dest='n_jobs',
                        help=f'Number of parallel worker processes (default: 1, max: {cpu_count()})')
    parser.add_argument('--column-local', action='store_true',
                        help='column-local shsq/dVsq/dbloc (the pre-1DMIX-071 replay) instead of '
                             "MITgcm's neighbour-dependent tracer-point inputs")

    args = parser.parse_args()

    inputs_file = Path(args.input_file)
    outputs_file = Path(args.output_file)

    if not inputs_file.exists():
        print(f"Error: Input file not found: {inputs_file}")
        sys.exit(1)

    # Create output directory if it doesn't exist
    outputs_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Run Python KPP from NetCDF Inputs")
    print("=" * 70)
    print(f"\nInput: {inputs_file}")

    # Load inputs
    print("\nLoading input dataset...")
    inputs_ds = xr.open_dataset(inputs_file)

    print(f"  Dimensions: time={len(inputs_ds.time)}, x={len(inputs_ds.x)}, "
          f"y={len(inputs_ds.y)}, z={len(inputs_ds.z)}")
    print(f"  UUID: {inputs_ds.attrs['uuid']}")
    print(f"  Experiment: {inputs_ds.attrs.get('experiment', 'unknown')}")

    # Validate n_jobs
    if args.n_jobs < 1:
        print(f"Error: -j/--jobs must be >= 1, got {args.n_jobs}")
        sys.exit(1)
    if args.n_jobs > cpu_count():
        print(f"Warning: Requested {args.n_jobs} workers but only {cpu_count()} CPUs available")
        args.n_jobs = cpu_count()

    # Run Python KPP
    outputs_ds = run_python_kpp_on_dataset(
        inputs_ds,
        verbose=True,
        first_timestep=args.first_timestep,
        last_timestep=args.last_timestep,
        n_jobs=args.n_jobs,
        inputs_file=inputs_file,
        tracer_point_inputs=not args.column_local,
    )

    # Add input file provenance
    outputs_ds.attrs['input_file_name'] = inputs_file.name
    outputs_ds.attrs['input_file_path'] = str(inputs_file.absolute())
    outputs_ds.attrs['output_file_path'] = str(outputs_file.absolute())

    print(f"\nSaving outputs: {outputs_file}")

    # Write with compression
    encoding = {var: {'zlib': True, 'complevel': 4} for var in outputs_ds.data_vars}
    outputs_ds.to_netcdf(outputs_file, encoding=encoding)

    print(f"  Size: {outputs_file.stat().st_size / 1024:.1f} KB")
    print(f"  Linked to input UUID: {outputs_ds.attrs['input_uuid']}")
    print(f"  Input file: {outputs_ds.attrs['input_file_name']}")

    # Quick comparison if MITgcm outputs exist
    # Look for MITgcm reference outputs in standard validation directory structure
    mitgcm_outputs_file = None

    # Pattern 1: inputs_from_mitgcm/file.nc -> outputs_from_mitgcm/file.nc (replace inputs with outputs)
    if inputs_file.parent.name == 'inputs_from_mitgcm':
        candidate = inputs_file.parent.parent / 'outputs_from_mitgcm' / inputs_file.name.replace('inputs', 'outputs')
        if candidate.exists():
            mitgcm_outputs_file = candidate

    # Pattern 2: Same directory, just change inputs->outputs in filename
    if not mitgcm_outputs_file:
        candidate = inputs_file.parent / inputs_file.name.replace('inputs', 'outputs')
        if candidate.exists():
            mitgcm_outputs_file = candidate

    if mitgcm_outputs_file:
        print("\n" + "=" * 70)
        print("Quick Comparison with MITgcm")
        print("=" * 70)
        print(f"Loading MITgcm outputs: {mitgcm_outputs_file}")

        mit_ds = xr.open_dataset(mitgcm_outputs_file)

        # Check UUIDs match
        if mit_ds.attrs['input_uuid'] != outputs_ds.attrs['input_uuid']:
            print("⚠ WARNING: UUID mismatch!")
            print(f"  MITgcm: {mit_ds.attrs['input_uuid']}")
            print(f"  Python: {outputs_ds.attrs['input_uuid']}")
        else:
            print(f"✅ UUIDs match: {outputs_ds.attrs['input_uuid']}")

        # Restrict MITgcm data to the timesteps we actually processed
        # outputs_ds has time indices 0, 1, 2, ... corresponding to args.first_timestep, args.first_timestep+1, ...
        # mit_ds has all timesteps, so we need to select args.first_timestep:args.last_timestep+1
        first_t = args.first_timestep if args.first_timestep is not None else 0
        last_t = args.last_timestep if args.last_timestep is not None else len(mit_ds.time) - 1
        mit_ds_subset = mit_ds.isel(time=slice(first_t, last_t + 1))

        # HBL comparison
        hbl_diff = (outputs_ds.hbl - mit_ds_subset.hbl).values
        hbl_diff = hbl_diff[~np.isnan(hbl_diff)]

        if len(hbl_diff) > 0:
            print(f"\nHBL Comparison:")
            print(f"  Mean |diff|: {np.mean(np.abs(hbl_diff)):.6f} m")
            print(f"  Max |diff|:  {np.max(np.abs(hbl_diff)):.6f} m")
            print(f"  RMS diff:    {np.sqrt(np.mean(hbl_diff**2)):.6f} m")

            if np.max(np.abs(hbl_diff)) < 0.1:
                print("  ✅ EXCELLENT - within 10 cm")
            elif np.mean(np.abs(hbl_diff)) < 1.0:
                print("  ✅ GOOD - within 1 m average")

        # Mixing coefficients within boundary layer
        mask = mit_ds_subset.visc_az.values > 1e-6
        if np.any(mask):
            visc_mit = mit_ds_subset.visc_az.values[mask]
            visc_py = outputs_ds.visc_az.values[mask]
            visc_rel = 100 * np.abs(visc_py - visc_mit) / visc_mit

            print(f"\nMixing Coefficients (active mixing, visc_az > 1e-6):")
            print(f"  visc_az median rel error: {np.median(visc_rel):.4f}%")
            print(f"  visc_az max rel error:    {np.max(visc_rel):.4f}%")

            if np.median(visc_rel) < 0.1:
                print("  ✅ EXCELLENT - within 0.1%")
            elif np.median(visc_rel) < 1.0:
                print("  ✅ GOOD - within 1%")

        mask = mit_ds_subset.diff_kz_s.values > 1e-6
        if np.any(mask):
            diff_mit = mit_ds_subset.diff_kz_s.values[mask]
            diff_py = outputs_ds.diff_kz_s.values[mask]
            diff_rel = 100 * np.abs(diff_py - diff_mit) / diff_mit

            print(f"  diff_kz_s median rel error: {np.median(diff_rel):.4f}%")
            print(f"  diff_kz_s max rel error:    {np.max(diff_rel):.4f}%")

    print("\n" + "=" * 70)
    print("✅ Complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
