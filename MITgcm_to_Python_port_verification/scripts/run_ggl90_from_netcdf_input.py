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
from typing import Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'Vertical_Mixing_Models'))

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
    'mxlSurfFlag': 'mxl_surf_flag',
}
BOOL_FIELDS = {'use_dirichlet', 'calc_mean_vert_shear', 'mxl_surf_flag'}
INT_FIELDS = {'mxl_max_flag'}


def _is_land_column(theta: np.ndarray, salt: np.ndarray) -> bool:
    """True if this column is masked out (not real ocean).

    Mirrors run_kpp_from_netcdf_input.py's identical _is_land_column
    (1DMIX-011): MITgcm masks land columns with exact 0.0 at every level for
    every field, not NaN. This was never needed before this function's first
    real multi-column, real-bathymetry caller (global_oce_latlon, 1DMIX-028)
    -- every prior GGL90 capture (vermix, 1D_ocean_ice_column's single
    column) was always fully wet, so no land-skip was ever exercised. Without
    it, this replay fed degenerate all-zero T/S into GGL90Driver.compute_mixing
    for every land column, producing large spurious nonzero mixing_length
    (up to ~2460 m) where MITgcm correctly reports exactly 0.0 -- confirmed
    directly: 1285/3600 columns in the global_oce_latlon capture are land by
    this check, and the mismatch was concentrated exactly there.

    Rechecked (1DMIX-025) for isomip's ALLOW_SHELFICE columns, which can be
    masked (dry) at the TOP with real wet ocean below (see
    _wet_level_range) rather than only below a real seafloor: this check
    already handles that case correctly without modification, since it
    requires EVERY level to be 0.0/NaN, not just level 0 -- a real
    ice-shelf-covered-but-wet column has nonzero theta/salt at its wet
    levels and is correctly classified as not land.
    """
    return bool(np.all(np.isnan(theta)) or (np.all(theta == 0.0) and np.all(salt == 0.0)))


def _wet_level_range(theta: np.ndarray) -> Tuple[int, int]:
    """(start, count) of a column's real, contiguous wet region.

    Was `_wet_level_count(theta) -> int` (1DMIX-028, mirroring KPP's
    identical 1DMIX-011 fix), which assumed the wet region always starts at
    index 0 and returned only its length -- correct for every previously-
    tested experiment, where a column shallower than the grid's deepest
    level is zero-padded by MITgcm below its real seafloor only (bathymetry
    masking is monotonic from the surface: wet from level 0 down to the
    seafloor, dry below). isomip (1DMIX-025, ALLOW_SHELFICE) breaks that
    assumption: a column under a floating ice shelf is masked (dry, exact
    0.0) from the surface down to kTopC-1, then wet from kTopC to the real
    seafloor -- confirmed directly on isomip's own capture, where 2401 of
    3000 non-land columns have this dry-top-then-wet-below shape (start>0),
    0 have the old dry-bottom-only shape at reduced depth (isomip's own
    bathymetry is flat except its two land walls), and the old
    `_wet_level_count` returned 0 for every one of the 2401 (since
    theta[0]==0.0 there), silently skipping them via run()'s
    `if nz_wet == 0: continue` rather than comparing them.

    Returns (0, len(theta)) for a fully wet column (every previously-tested
    experiment's common case) -- an exact behavioral no-op there, confirmed
    by rebuilding+rerunning vermix's existing GGL90 capture with the
    corresponding Fortran-side fix (see ggl90_mods/ggl90_calc.F's
    landColumn check) and diffing byte-for-byte against the pre-fix rerun.

    Raises
    ------
    ValueError
        If the wet region is not contiguous (a dry level sandwiched between
        two wet levels). Not observed in any capture to date -- isomip's
        real ice-shelf-covered columns are wet in exactly one contiguous
        run, from kTopC to the seafloor -- and not a shape this harness's
        column-local driver call (which needs one contiguous slice) knows
        how to feed correctly; fail loudly rather than silently mis-slicing.
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

    # Land columns start (and stay) zero, matching MITgcm's own convention.
    # Levels outside a partially-wet column's real wet range start (and
    # stay) NaN -- below a real seafloor, or (1DMIX-025) above a real
    # ice-shelf draft for an ALLOW_SHELFICE experiment -- see the truncation
    # note below for why this script does not attempt to reproduce MITgcm's
    # own non-trivial fill in either such region.
    kappa_m = np.zeros((ntime, nx, ny, nz))
    kappa_h = np.zeros((ntime, nx, ny, nz))
    mixing_length = np.zeros((ntime, nx, ny, nz))
    tke_new = np.zeros((ntime, nx, ny, nz))

    # 1DMIX-015: the captured `time` coordinate is the raw MITgcm iteration
    # index (0, 1, 2, ...), not seconds -- differencing it silently gave dt=1.0
    # instead of the real per-level tracer timestep. Newer captures carry the
    # real value (dTtracerLev(1), see ggl90_calc.F's PARAMETERS dump) as the
    # `deltaT` global attribute; require it rather than guess from the index.
    if 'deltaT' not in inputs_ds.attrs:
        raise ValueError(
            "Input NetCDF is missing the 'deltaT' global attribute (real MITgcm "
            "tracer timestep). This capture predates the 1DMIX-015 fix to "
            "ggl90_calc.F's PARAMETERS dump; regenerate it, or the diffed "
            "iteration-index time coordinate will silently understate dt."
        )
    dt = float(inputs_ds.attrs['deltaT'])

    for t in range(ntime):
        for i in range(nx):
            for j in range(ny):
                tke = inputs_ds['tke_before'].values[t, i, j, :]
                theta = inputs_ds['temperature'].values[t, i, j, :]
                salt = inputs_ds['salinity'].values[t, i, j, :]
                u = inputs_ds['u_velocity'].values[t, i, j, :]
                v = inputs_ds['v_velocity'].values[t, i, j, :]
                u_star_sq = float(inputs_ds['u_star_sq'].values[t, i, j])

                # Skip land points (see _is_land_column -- 1DMIX-028): leave
                # this column's already-zero-initialized output as-is,
                # matching MITgcm's own zero-fill convention for land.
                if _is_land_column(theta, salt):
                    continue

                # Truncate to this column's real wet (start, count) range --
                # see _wet_level_range (1DMIX-025, superseding the former
                # dry-bottom-only _wet_level_count; 1DMIX-028/1DMIX-011).
                # Outside that range (whether above a real ice-shelf draft
                # or below the real seafloor), MITgcm's own GGL90_CALC
                # output is NOT simply zero (confirmed directly: diff_kz
                # there equals the unconditional background diffKrNrS(k)
                # via ggl90_calc.F's `MAX(tmpVisc,diffKrNrS(k))` -- the same
                # unconditional-background-floor idiom already characterized
                # for KPP's viscArNr this session -- and mixing_length
                # floors at GGL90mixingLengthMin), neither of which this
                # port's compute_mixing call is asked to reproduce for a
                # region it was never given data for. NaN marks both such
                # regions as genuinely not compared, rather than asserting a
                # guessed fill value; compare_ggl90.py excludes NaN cells
                # from its statistics.
                wet_start, nz_wet = _wet_level_range(theta)
                if nz_wet == 0:
                    continue
                nz_full = len(theta)
                wet_end = wet_start + nz_wet

                # is_true_surface=False whenever this column's real wet
                # region starts below array index 0 (an ALLOW_SHELFICE
                # column, kSrf=wet_start>0) -- see 1DMIX-038: local index 0
                # of this slice is then MITgcm's real, interior kSrf, not
                # its true k=1 array boundary, and GGL90Driver.compute_mixing
                # needs to know that to reproduce MITgcm's real kappa_h[0]/
                # tke_new[0] there instead of the ordinary zero-flux/
                # Dirichlet-survives convention.
                out = driver.compute_mixing(
                    tke=tke[wet_start:wet_end], u=u[wet_start:wet_end],
                    v=v[wet_start:wet_end],
                    theta=theta[wet_start:wet_end], salt=salt[wet_start:wet_end],
                    depth=depth[wet_start:wet_end], z=depth[wet_start:wet_end],
                    dz=cell_thickness[wet_start:wet_end], dt=dt,
                    mask=np.ones(nz_wet), u_star_sq=u_star_sq,
                    gravity=gravity, rho_const=rho_const,
                    background_visc=background_visc,
                    background_diff=background_diff,
                    is_true_surface=(wet_start == 0),
                )

                def _pad(arr):
                    if nz_wet == nz_full:
                        return arr
                    return np.concatenate([
                        np.full(wet_start, np.nan),
                        arr,
                        np.full(nz_full - wet_end, np.nan),
                    ])

                kappa_m[t, i, j, :] = _pad(out.kappa_m)
                kappa_h[t, i, j, :] = _pad(out.kappa_h)
                mixing_length[t, i, j, :] = _pad(out.mixing_length)
                tke_new[t, i, j, :] = _pad(out.tke_new)

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
