#!/usr/bin/env python3
"""
Build the reduced single-column witnesses of 1DMIX-075 (`Vertical_Mixing_Models/tests/data/kpp_075_witnesses.npz`).

Each witness holds the EXACT keyword inputs of `KPPDriver.compute_mixing` (as the capture replay
`run_kpp_from_netcdf_input.py` passes them, including the tracer-point `shsq_forcing`/`dvsq_forcing`/
`dbloc_smooth_forcing` and, for a truncated column, the dry model levels below it) and the MITgcm (or
standalone-Fortran) output for that column, so that
`Vertical_Mixing_Models/tests/test_kpp_levels_below.py` can assert the driver against MITgcm without any
capture being present:

  g90_t5_i72_j35      global_ocean_90x40x15_10 capture, t=5, i=72, j=35: two wet levels, hbl 29.006 m (case A)
  g90_t0_i0_j34       same capture, t=0, i=0, j=34: two wet levels, hbl = 85 m (bottomed out), unstable forcing
  g90_t3_i30_j18      same capture, t=3, i=30, j=18: two wet levels, hbl = minKPPhbl = 25 m
  g90_t0_i86_j36_three_wet  same capture, t=0, i=86, j=36: three wet levels in the kbl = kmtj+1 regime, unstable forcing
  k11_t70             11k_1D capture (1D_ocean_ice_column, full depth, no dry level), t=70: boundary layer in
                      the surface cell (Fortran kn = 1): MITgcm reads diffus(i,0,*) = 0

Usage: python make_kpp_075_witnesses.py [output.npz]   (needs the gitignored captures; regenerates the fixture)
"""
import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT / 'Vertical_Mixing_Models'))

import run_kpp_from_netcdf_input as r  # noqa: E402
from KPP.kpp_core_driver import KPPDriver  # noqa: E402
from KPP.kpp_parameters import KPPParameters  # noqa: E402

KPP_DIR = _ROOT / 'MITgcm_to_Python_port_verification' / 'KPP_port_validation'
OUT = _ROOT / 'Vertical_Mixing_Models' / 'tests' / 'data' / 'kpp_075_witnesses.npz'


def capture_witness(stem, t, i, j):
    ii = xr.open_dataset(KPP_DIR / 'inputs_from_mitgcm' / f'mitgcm_kpp_inputs_{stem}.nc').isel(time=slice(t, t + 1)).load()
    oo = xr.open_dataset(KPP_DIR / 'outputs_from_mitgcm' / f'mitgcm_kpp_outputs_{stem}.nc').isel(time=slice(t, t + 1)).load()
    kp, bg, _, _ = r.extract_parameters_from_inputs(ii, verbose=False)
    params = KPPParameters(**kp)
    tp = r.build_tracer_point_arrays(ii, params, 0, 0)
    theta = ii.temperature.values[0, i, j]
    ws, n = r._wet_level_range(theta)
    we = ws + n
    depth, thk = ii.depth.values, ii.cell_thickness.values

    def col(name):
        return ii[name].values[0, i, j]
    kw = dict(theta=theta[ws:we], salt=col('salinity')[ws:we], u_vel=col('u_velocity')[ws:we],
              v_vel=col('v_velocity')[ws:we], depth=depth[ws:we], cell_thickness=thk[ws:we],
              coriol=float(ii.f_coriolis.values[0, i, j]),
              background_visc=bg['background_visc'], background_diff_s=bg['background_diff_s'],
              background_diff_t=bg['background_diff_t'],
              ustar_forcing=float(ii.ustar.values[0, i, j]), bo_forcing=float(ii.bo.values[0, i, j]),
              bosol_forcing=float(ii.bosol.values[0, i, j]))
    kw.update(r._tracer_point_kwargs(tp, 0, i, j, ws, we))
    kw.update(r._levels_below_kwargs(depth, thk, we))
    exp = dict(visc_az=oo.visc_az.values[0, i, j, :n], diff_kz_s=oo.diff_kz_s.values[0, i, j, :n],
               diff_kz_t=oo.diff_kz_t.values[0, i, j, :n], ghat=oo.ghat.values[0, i, j, :n],
               hbl=float(oo.hbl.values[0, i, j]))
    return kp, kw, exp, dict(capture=stem, t=t, i=i, j=j, nz_wet=n)


def main(out=OUT):
    wit = {}
    wit['g90_t5_i72_j35'] = capture_witness('global_ocean_90x40x15_10', 5, 72, 35)
    wit['g90_t0_i0_j34'] = capture_witness('global_ocean_90x40x15_10', 0, 0, 34)
    wit['g90_t3_i30_j18'] = capture_witness('global_ocean_90x40x15_10', 3, 30, 18)
    wit['g90_t0_i86_j36_three_wet'] = capture_witness('global_ocean_90x40x15_10', 0, 86, 36)
    wit['k11_t70'] = capture_witness('11k_1D', 70, 0, 0)
    arrays, meta = {}, {}
    for name, (kp, kw, exp, info) in wit.items():
        drv = KPPDriver(KPPParameters(**kp))
        res = drv.compute_mixing(**kw)
        n = len(kw['depth'])
        diffs = {f: float(np.max(np.abs(getattr(res, f) - exp[f][:n]))) for f in ('visc_az', 'diff_kz_s', 'diff_kz_t', 'ghat')}
        diffs['hbl'] = abs(res.hbl - exp['hbl'])
        print(name, info, {k: f'{v:.3g}' for k, v in diffs.items()})
        for k, v in kw.items():
            arrays[f'{name}/in/{k}'] = np.asarray(v, dtype=np.float64)
        for k, v in exp.items():
            arrays[f'{name}/mit/{k}'] = np.asarray(v, dtype=np.float64)
        meta[name] = dict(info=info, params=kp)
    arrays['meta_json'] = np.array(json.dumps(meta, default=str))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **arrays)
    print('wrote', out)


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
