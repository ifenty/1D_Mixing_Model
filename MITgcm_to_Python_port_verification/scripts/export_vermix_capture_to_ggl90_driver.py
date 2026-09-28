#!/usr/bin/env python3
"""
Export a captured MITgcm GGL90 inputs NetCDF (vermix, single column) to a
flat text file the standalone GGL90_CALC driver
(mitgcm_verification_mods/ggl90_standalone_driver) can read with plain
Fortran READ statements. Mirrors export_kpp_input_for_fortran.py's role for
the KPP standalone driver.

Deliberately avoids NetCDF-Fortran: the standalone driver only needs to
call GGL90_CALC directly, so its I/O can stay a trivial flat format.

Only single-column (nx=1, ny=1) captures are supported. Requires the
capture to include sigma_r (1DMIX-024's INPUT_SIGMAR addition to
mitgcm_verification_mods/{ggl90_mods,vermix/code_validation}/ggl90_calc.F)
-- an older capture missing it (attrs['sigma_r_data'] != 'present') cannot
drive GGL90_CALC, since sigmaR is its one explicit array argument and must
not be silently guessed or zero-filled.
"""

import sys
import numpy as np
import xarray as xr
from pathlib import Path


# GGL90.h/PARAMS.h scalar parameters, in the exact order
# ggl90_standalone_main.F's READ statements expect them (matching the
# PARAM_<name> tags ggl90_calc.F's GGL90_OUTPUT_VALIDATION dumps).
FLOAT_PARAMS = [
    'GGL90ck', 'GGL90ceps', 'GGL90alpha', 'GGL90m2',
    'GGL90TKEmin', 'GGL90TKEsurfMin', 'GGL90TKEbottom',
    'GGL90mixingLengthMin', 'GGL90viscMax', 'GGL90diffMax',
    'gravity', 'rhoConst', 'viscAz', 'diffKzS', 'deltaT',
]
INT_PARAMS = ['mxlMaxFlag']
BOOL_PARAMS = ['GGL90_dirichlet', 'calcMeanVertShear']


def export(inputs_nc: Path, out_txt: Path) -> None:
    ds = xr.open_dataset(inputs_nc)

    if ds.attrs.get('sigma_r_data') != 'present':
        raise ValueError(
            f"{inputs_nc} lacks sigma_r (GGL90_CALC's one explicit array "
            "argument). Re-run the instrumented MITgcm build with the "
            "1DMIX-024 sigmaR-capture ggl90_calc.F and reparse with the "
            "extended scripts/parse_mitgcm_ggl90_split.py before exporting "
            "for the standalone driver."
        )
    for name in FLOAT_PARAMS + INT_PARAMS + BOOL_PARAMS:
        if name not in ds.attrs:
            raise ValueError(f"{inputs_nc} is missing required attr '{name}'")

    nx = ds.sizes['x']
    ny = ds.sizes['y']
    if nx != 1 or ny != 1:
        raise ValueError(
            f"Only single-column captures are supported (got nx={nx}, ny={ny})"
        )

    nr = ds.sizes['z']
    ntime = ds.sizes['time']

    lines = []
    lines.append(f"{ntime} {nr}")

    # Static grid (drF, rF, rC), per level -- matches
    # GGL90_GRID_GEOMETRY's own dump order.
    drF = ds['cell_thickness'].values
    rF = ds['depth_iface'].values
    rC = ds['depth'].values
    for k in range(nr):
        lines.append(f"{float(drF[k])!r} {float(rF[k])!r} {float(rC[k])!r}")

    for name in FLOAT_PARAMS:
        lines.append(repr(float(ds.attrs[name])))
    for name in INT_PARAMS:
        lines.append(str(int(ds.attrs[name])))
    for name in BOOL_PARAMS:
        lines.append(str(int(ds.attrs[name])))

    theta = ds['temperature'].values
    salt = ds['salinity'].values
    u = ds['u_velocity'].values
    v = ds['v_velocity'].values
    tke_before = ds['tke_before'].values
    sigma_r = ds['sigma_r'].values
    tau_x = ds['tau_x'].values
    tau_y = ds['tau_y'].values
    u_star_sq = ds['u_star_sq'].values

    timesteps = ds['time'].values
    for t in range(ntime):
        lines.append(f"{int(timesteps[t])}")
        lines.append(
            f"{float(tau_x[t,0,0])!r} {float(tau_y[t,0,0])!r} "
            f"{float(u_star_sq[t,0,0])!r}"
        )
        for k in range(nr):
            lines.append(
                f"{float(theta[t,0,0,k])!r} {float(salt[t,0,0,k])!r} "
                f"{float(u[t,0,0,k])!r} {float(v[t,0,0,k])!r}"
            )
        for k in range(nr):
            lines.append(f"{float(tke_before[t,0,0,k])!r}")
        for k in range(nr):
            lines.append(f"{float(sigma_r[t,0,0,k])!r}")

    out_txt.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_txt} ({ntime} timesteps, {nr} levels)")


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: python export_vermix_capture_to_ggl90_driver.py "
            "<inputs.nc> <out.txt>"
        )
        sys.exit(1)
    export(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == '__main__':
    main()
