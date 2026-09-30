#!/usr/bin/env python3
"""
Parse MITgcm GGL90 validation output (mitgcm_verification_mods/ggl90_mods/
ggl90_calc.F's GGL90_OUTPUT_VALIDATION dump) to separate input and output
NetCDF files, mirroring parse_mitgcm_split.py's KPP format/structure.

Creates two files:
  - mitgcm_ggl90_inputs.nc:  state, TKE(t), forcing, grid, parameters (UUID-tagged)
  - mitgcm_ggl90_outputs.nc: mixing coefficients, TKE(t+1) (UUID-linked)

GGL90 is prognostic (unlike KPP): TKE(t) is captured as an explicit input
(before this timestep's call mutates it), and TKE(t+1) as the output, so a
single-step-replay comparison (feed the Python port MITgcm's own TKE(t), not
its own evolving state) is possible without accumulating drift.

Streaming (1DMIX-065): like parse_mitgcm_split.py, ``output.txt`` is read line
by line and each completed timestep (all tiles) is appended to the NetCDF files
and then dropped, so peak memory is one timestep of arrays plus the fixed
metadata, independent of file length (the previous implementation kept every
value of every timestep in Python dicts until the end; a 13.8 GB KPP capture
exhausted 27 GB of RAM). The shared engine is ``capture_stream.py``; this file
supplies the GGL90 line grammar, variable tables, parameter/grid blocks and
global attributes. ``parse_mitgcm_ggl90_split`` keeps the original
in-memory ``(inputs_ds, outputs_ds)`` API for small captures (it streams to a
temporary directory and then loads the result); large captures should use
``parse_mitgcm_ggl90_split_to_files`` or the command line.
"""

import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import xarray as xr

from capture_stream import (ParserSpec, VarDef, ffloat, now_iso,
                            stream_convert)


def parse_mitgcm_ggl90_split_to_files(output_file: Path, inputs_path: Path,
                                      outputs_path: Path,
                                      experiment_name: str = None) -> str:
    """Stream ``output_file`` into ``inputs_path`` / ``outputs_path``.

    Memory is bounded by one timestep (see module docstring). Returns the run
    UUID recorded as ``uuid`` in the inputs file and ``input_uuid`` in the
    outputs file.
    """
    output_file = Path(output_file)
    print(f"Parsing MITgcm GGL90 validation output: {output_file}")
    if experiment_name is None:
        experiment_name = "unknown_experiment"
    return stream_convert(output_file, experiment_name, SPEC,
                          inputs_path, outputs_path)


def parse_mitgcm_ggl90_split(output_file: Path,
                             experiment_name: str = None
                             ) -> Tuple[xr.Dataset, xr.Dataset]:
    """In-memory convenience wrapper for SMALL captures.

    Streams into a temporary directory and returns the two Datasets fully
    loaded. Do not use it on a capture whose NetCDF files do not comfortably
    fit in memory; use ``parse_mitgcm_ggl90_split_to_files`` instead.
    """
    with tempfile.TemporaryDirectory() as tmp:
        inputs_path = Path(tmp) / 'mitgcm_ggl90_inputs.nc'
        outputs_path = Path(tmp) / 'mitgcm_ggl90_outputs.nc'
        parse_mitgcm_ggl90_split_to_files(output_file, inputs_path,
                                          outputs_path, experiment_name)
        with xr.open_dataset(inputs_path) as ds:
            inputs_ds = ds.load()
        with xr.open_dataset(outputs_path) as ds:
            outputs_ds = ds.load()
    return inputs_ds, outputs_ds


def _parse_line(tag: str, parts: List[str]) -> Optional[List[tuple]]:
    """One GGL90 data line -> [(variable, i, j, k, value), ...] (tile-local,
    zero-based i/j/k; k=None for horizontal variables), or None for an
    unrecognised tag. A malformed field raises ValueError/IndexError and the
    caller drops the whole line, as the old parser did."""
    if tag == 'INPUT_STATE':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('temperature', i, j, k, ffloat(parts[4])),
                ('salinity', i, j, k, ffloat(parts[5])),
                ('u_velocity', i, j, k, ffloat(parts[6])),
                ('v_velocity', i, j, k, ffloat(parts[7]))]

    if tag == 'INPUT_TKE':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('tke_before', i, j, k, ffloat(parts[4]))]

    if tag == 'INPUT_SIGMAR':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('sigma_r', i, j, k, ffloat(parts[4]))]

    if tag == 'INPUT_FORCING':
        i, j = int(parts[1])-1, int(parts[2])-1
        return [('tau_x', i, j, None, ffloat(parts[3])),
                ('tau_y', i, j, None, ffloat(parts[4])),
                ('u_star_sq', i, j, None, ffloat(parts[5]))]

    if tag == 'OUTPUT_MIXING':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('visc_az', i, j, k, ffloat(parts[4])),
                ('diff_kz', i, j, k, ffloat(parts[5])),
                ('mixing_length', i, j, k, ffloat(parts[6]))]

    if tag == 'OUTPUT_TKE':
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('tke_after', i, j, k, ffloat(parts[4]))]

    if tag == 'OUTPUT_RI_SHEAR_PR':
        # 1DMIX-028: RiNumber, verticalShear(i,j) and TKEPrandtlNumber(i,j,k),
        # ground-truthing the diff_kz-level residual found on
        # global_oce_latlon.
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('ri_number', i, j, k, ffloat(parts[4])),
                ('vertical_shear', i, j, k, ffloat(parts[5])),
                ('tke_prandtl_number', i, j, k, ffloat(parts[6]))]

    if tag == 'OUTPUT_IDEMIX':
        # 1DMIX-025: IDEMIX_gTKE(i,j,k), the real additional TKE source term
        # (dissipation of internal-wave energy) ALLOW_GGL90_IDEMIX adds -- the
        # Python GGL90 port has no IDEMIX physics, so this quantifies the
        # real, expected physics gap rather than feeding a Python-side
        # implementation. Always present in a capture from the fixed
        # ggl90_calc.F (this project's own instrumentation,
        # always-declared/zeroed there), and is genuinely 0 for any
        # non-IDEMIX experiment.
        i, j, k = int(parts[1])-1, int(parts[2])-1, int(parts[3])-1
        return [('idemix_gtke', i, j, k, ffloat(parts[4]))]

    return None


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
            drF.append(ffloat(parts[2]))
            rF.append(ffloat(parts[3]))
            rC.append(ffloat(parts[4]))
    return {'nr': len(drF), 'drF': np.array(drF), 'rF': np.array(rF), 'rC': np.array(rC)}


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
    return {'x': nx, 'y': ny, 'z': nz, 'z_iface': nz}


# Variable tables. All variables are always written; whether the optional
# instrumentation groups were present in the capture is recorded in the
# sigma_r_data / ri_shear_pr_data / idemix_gtke_data global attributes.
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
        'long_name': 'Zonal velocity', 'units': 'm/s'
    }),
    VarDef('v_velocity', ('x', 'y', 'z'), {
        'long_name': 'Meridional velocity', 'units': 'm/s'
    }),
    VarDef('tke_before', ('x', 'y', 'z'), {
        'long_name': 'Turbulent kinetic energy at t (input)', 'units': 'm^2/s^2',
        'description': (
            'GGL90TKE captured before this call mutates it -- feed this '
            'directly to the Python port for single-step-replay '
            'comparison against tke_after (in outputs), not the port\'s '
            'own evolving TKE state.'
        )
    }),
    VarDef('sigma_r', ('x', 'y', 'z'), {
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
    VarDef('tau_x', ('x', 'y'), {
        'long_name': 'Zonal wind stress per unit density', 'units': 'm^2/s^2'
    }),
    VarDef('tau_y', ('x', 'y'), {
        'long_name': 'Meridional wind stress per unit density', 'units': 'm^2/s^2'
    }),
    VarDef('u_star_sq', ('x', 'y'), {
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
]

_OUTPUT_VARS = [
    VarDef('visc_az', ('x', 'y', 'z'), {
        'long_name': 'Vertical eddy viscosity (GGL90, cell-centered pre-stagger)',
        'units': 'm^2/s',
        'description': 'GGL90visctmp: cell-centered KappaM before U/V staggering'
    }),
    VarDef('diff_kz', ('x', 'y', 'z'), {
        'long_name': 'Vertical eddy diffusivity (GGL90)', 'units': 'm^2/s',
        'description': 'GGL90diffKr'
    }),
    VarDef('mixing_length', ('x', 'y', 'z'), {
        'long_name': 'GGL90 mixing length', 'units': 'm'
    }),
    VarDef('tke_after', ('x', 'y', 'z'), {
        'long_name': 'Turbulent kinetic energy at t+1 (output)', 'units': 'm^2/s^2',
        'description': 'GGL90TKE after this call\'s implicit tridiagonal solve'
    }),
    VarDef('ri_number', ('x', 'y', 'z'), {
        'long_name': 'GGL90 local Richardson number (RiNumber)', 'units': '1',
        'description': (
            '1DMIX-028: MAX(Nsquare,0)/(verticalShear+GGL90eps), the exact '
            'quantity ggl90_calc.F branches TKEPrandtlNumber on '
            '(RiNumber>=0.2). Absent from captures predating this fix '
            '(stays 0).'
        )
    }),
    VarDef('vertical_shear', ('x', 'y', 'z'), {
        'long_name': 'GGL90 (squared) vertical shear', 'units': '1/s^2',
        'description': '1DMIX-028: verticalShear(i,j) at this level, before it is overwritten by the next k iteration.'
    }),
    VarDef('tke_prandtl_number', ('x', 'y', 'z'), {
        'long_name': 'GGL90 turbulent Prandtl number (TKEPrandtlNumber)', 'units': '1',
        'description': '1DMIX-028: direct capture, not inferred from visc_az/diff_kz ratios. Absent from captures predating this fix (stays 1, the Fortran init value).'
    }, fill=1.0),
    VarDef('idemix_gtke', ('x', 'y', 'z'), {
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
]


def _inputs_attrs(experiment_name, output_file, run_uuid, params, seen) -> Dict:
    attrs = {
        'title': 'MITgcm GGL90 Inputs',
        'source': 'MITgcm with GGL90 instrumentation',
        'institution': 'MITgcm',
        'experiment': experiment_name,
        'output_file_path': str(Path(output_file).absolute()),
        'creation_date': now_iso(),
        'uuid': run_uuid,
        'description': 'GGL90 inputs (state, TKE(t), forcing, grid) from MITgcm for validation',
        'conventions': 'CF-1.8',
        'sigma_r_data': 'present' if 'sigma_r' in seen else 'absent',
    }
    for name, value in params.items():
        attrs[name] = value
    return attrs


def _outputs_attrs(experiment_name, run_uuid, seen) -> Dict:
    return {
        'title': 'MITgcm GGL90 Outputs',
        'source': 'MITgcm GGL90',
        'institution': 'MITgcm',
        'experiment': experiment_name,
        'ri_shear_pr_data': 'present' if 'ri_number' in seen else 'absent',
        'idemix_gtke_data': 'present' if 'idemix_gtke' in seen else 'absent',
        'creation_date': now_iso(),
        'input_uuid': run_uuid,
        'description': 'GGL90 outputs (mixing coefficients, TKE(t+1)) from MITgcm',
        'conventions': 'CF-1.8',
    }


SPEC = ParserSpec(
    prefix='GGL90',
    # Tags whose (i, j) fix the tile-local index extent (sNx/sNy).
    extent_tags=frozenset({'INPUT_STATE', 'OUTPUT_MIXING'}),
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
        print("Usage: python parse_mitgcm_ggl90_split.py <output.txt> [experiment_name]")
        sys.exit(1)

    output_file = Path(sys.argv[1])
    experiment_name = sys.argv[2] if len(sys.argv) >= 3 else None

    if not output_file.exists():
        print(f"Error: File not found: {output_file}")
        sys.exit(1)

    inputs_file = output_file.parent / 'mitgcm_ggl90_inputs.nc'
    outputs_file = output_file.parent / 'mitgcm_ggl90_outputs.nc'

    run_uuid = parse_mitgcm_ggl90_split_to_files(output_file, inputs_file,
                                                 outputs_file, experiment_name)
    print(f"  Inputs:  {inputs_file} ({inputs_file.stat().st_size/1024:.1f} KB)")
    print(f"  Outputs: {outputs_file} ({outputs_file.stat().st_size/1024:.1f} KB)")
    print(f"UUID: {run_uuid}")


if __name__ == '__main__':
    main()
