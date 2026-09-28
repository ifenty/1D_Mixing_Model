#!/usr/bin/env python3
"""
Export a captured MITgcm KPP inputs/outputs NetCDF pair to a flat text file
that the standalone KPPMIX driver (mitgcm_verification_mods/kpp_standalone_driver)
can read with plain Fortran READ statements.

Deliberately avoids NetCDF-Fortran: the standalone driver only needs to call
KPPMIX directly (an argument-only subroutine, see kpp_routines.F), so its I/O
can stay a trivial flat format. This script is the only place that translates
between the two.

Only single-column (nx=1, ny=1) captures are supported: KPPMIX's direct
arguments (shsq, dVsq, dbloc/buoy_freq_sq, Ritop, ustar, bo, bosol) must be
present in the outputs file (added alongside shear_sq/buoy_freq_sq; see
parse_mitgcm_split.py's `kppmix_direct_inputs` attribute).
"""

import sys
import numpy as np
import xarray as xr
from pathlib import Path


# KPP_PARAMS.h scalar/common-block parameters that must be reproduced exactly
# for a bit-level match with the full-model run. Names match the PARAM_<name>
# tags kpp_calc.F's KPP_OUTPUT_VALIDATION dumps (see kpp_readparms.F defaults).
SCALAR_PARAMS = [
    'Ricr', 'cekman', 'cmonob', 'concv', 'hbf',
    'epsilon', 'vonk', 'dB_dz',
    'Riinfty', 'BVSQcon', 'difm0', 'difs0', 'dift0',
    'difmcon', 'difscon', 'diftcon',
    'conc1', 'conam', 'concm', 'conc2', 'zetam',
    'conas', 'concs', 'conc3', 'zetas',
    'Rrho0', 'dsfmax',
    'epsln', 'phepsi', 'cstar', 'minKPPhbl',
    'zmin', 'zmax', 'umin', 'umax',
    'viscAz', 'diffKzS', 'diffKzT',
]
INT_PARAMS = ['num_v_smooth_Ri', 'selectPenetratingSW']
# LimitHblStable, KPPuseSWfrac3D are referenced directly inside
# KPPMIX/bldepth. KPPuseDoubleDiff is only used by kpp_calc.F's separate
# KPP_DOUBLEDIFF call (not invoked by the standalone driver) but is kept
# here for documentation/consistency.
BOOL_PARAMS = ['KPPuseDoubleDiff', 'LimitHblStable', 'KPPuseSWfrac3D']


def export(inputs_nc: Path, outputs_nc: Path, out_txt: Path) -> None:
    inputs_ds = xr.open_dataset(inputs_nc)
    outputs_ds = xr.open_dataset(outputs_nc)

    if outputs_ds.attrs.get('kppmix_direct_inputs') != 'present':
        raise ValueError(
            f"{outputs_nc} lacks dVsq/Ritop (KPPMIX's direct 'I'-only "
            "arguments). Re-run the instrumented MITgcm build with the "
            "extended kpp_calc.F (mitgcm_verification_mods/kpp_mods/kpp_calc.F) "
            "before exporting for the standalone driver."
        )
    if int(inputs_ds.attrs.get('shortwave_heating', 0)) == 1 and (
        inputs_ds.attrs.get('swatt_data') != 'present'
    ):
        raise ValueError(
            f"{inputs_nc} was captured with SHORTWAVE_HEATING active but has "
            "no swatt profile. Re-run with the extended kpp_calc.F."
        )

    nx = inputs_ds.sizes['x']
    ny = inputs_ds.sizes['y']
    if nx != 1 or ny != 1:
        raise ValueError(
            f"Only single-column captures are supported (got nx={nx}, ny={ny})"
        )

    nr = inputs_ds.sizes['z']
    ntime = inputs_ds.sizes['time']

    lines = []
    lines.append(f"{ntime} {nr}")

    # Static grid (drF, rC) -- used to rebuild zgrid/hwide per kpp_init_fixed.F
    drF = inputs_ds['cell_thickness'].values
    rC = inputs_ds['depth'].values
    for k in range(nr):
        lines.append(f"{float(drF[k])!r} {float(rC[k])!r}")

    # Scalar KPP_PARAMS.h parameters, in a fixed order the Fortran driver expects
    for name in SCALAR_PARAMS:
        lines.append(repr(float(inputs_ds.attrs[name])))
    for name in INT_PARAMS:
        lines.append(str(int(inputs_ds.attrs[name])))
    for name in BOOL_PARAMS:
        lines.append(str(int(inputs_ds.attrs[name])))

    # Per-timestep, per-column data (nx=ny=1, so one column per timestep)
    ustar = inputs_ds['ustar'].values
    bo = inputs_ds['bo'].values
    bosol = inputs_ds['bosol'].values
    coriol = inputs_ds['f_coriolis'].values
    shsq = outputs_ds['shear_sq'].values
    dbloc = outputs_ds['buoy_freq_sq'].values
    dvsq = outputs_ds['dVsq'].values
    ritop = outputs_ds['Ritop'].values
    swatt = inputs_ds['swatt'].values if 'swatt' in inputs_ds else None

    timesteps = inputs_ds['time'].values
    for t in range(ntime):
        lines.append(f"{int(timesteps[t])}")
        lines.append(
            f"{float(ustar[t,0,0])!r} {float(bo[t,0,0])!r} "
            f"{float(bosol[t,0,0])!r} {float(coriol[t,0,0])!r}"
        )
        for k in range(nr):
            lines.append(
                f"{float(shsq[t,0,0,k])!r} {float(dvsq[t,0,0,k])!r} "
                f"{float(dbloc[t,0,0,k])!r} {float(ritop[t,0,0,k])!r}"
            )
        # swatt: Nr+1 levels (one more than the KPPMIX-level arrays above)
        for k in range(nr + 1):
            val = float(swatt[t, 0, 0, k]) if swatt is not None else 0.0
            lines.append(f"{val!r}")

    out_txt.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_txt} ({ntime} timesteps, {nr} levels)")


def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python export_kpp_input_for_fortran.py "
            "<inputs.nc> <outputs.nc> <out.txt>"
        )
        sys.exit(1)
    export(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == '__main__':
    main()
