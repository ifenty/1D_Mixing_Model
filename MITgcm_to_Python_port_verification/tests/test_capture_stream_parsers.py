"""
Regression tests for the streaming MITgcm capture parsers
(`scripts/capture_stream.py`, `scripts/parse_mitgcm_split.py`,
`scripts/parse_mitgcm_ggl90_split.py`), 1DMIX-065.

These tests are self-contained (tiny synthetic ``output.txt`` files written into
``tmp_path``), so unlike the MITgcm-comparison tests they never skip for a
missing capture. They pin the behaviours the streaming rewrite had to preserve
from the old whole-file parsers: tile-local -> global (x, y) remapping across
several tiles, zero fill for cells no line supplied, optional variables that
appear only in later timesteps (present, zero before), Fortran's E-less
bare-exponent floats, dropping a malformed line, KPP/GGL90 UUID linkage, and the
new streaming-specific guarantees (many appended timesteps, refusal of
non-contiguous/descending timesteps). Byte-for-byte identity against the old
implementation on real captures was checked separately (see the 1DMIX-065
evidence log); these tests guard the mechanics on every run.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

_VERIFICATION_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_VERIFICATION_ROOT / 'scripts'))

from parse_mitgcm_split import parse_mitgcm_split  # noqa: E402
from parse_mitgcm_ggl90_split import (  # noqa: E402
    parse_mitgcm_ggl90_split, parse_mitgcm_ggl90_split_to_files)

# Grid: 2 tiles in x (BI=1,2), each sNx=2 x sNy=1, nz=2 -> global nx=4, ny=1.
SNX, NZ = 2, 2
BARE_EXP = '0.105188567206-104'      # Fortran drops the "E" for 3-digit exponents
BARE_EXP_VALUE = 0.105188567206e-104


def _header_lines(prefix, params):
    lines = [f'===== {prefix}_MODEL_PARAMETERS =====']
    lines += [f'PARAM_{k}={v}' for k, v in params]
    lines += [f'===== {prefix}_MODEL_PARAMETERS_END =====',
              f'===== {prefix}_GRID_GEOMETRY =====',
              'GRID_GEOM,1,10.0,-10.0,-5.0',
              'GRID_GEOM,2,10.0,-20.0,-15.0',
              f'===== {prefix}_GRID_GEOMETRY_END =====',
              f'===== {prefix}_DATA_HEADERS =====',
              'ignored header line',
              f'===== {prefix}_DATA_HEADERS_END =====']
    return lines


def _val(ts, bi, i, k):
    """Distinct, checkable value for (timestep, tile, local i, level k)."""
    return ts * 1000.0 + bi * 100.0 + i * 10.0 + k


def _kpp_block(ts, bi, optional, special):
    lines = ['===== KPP_VALIDATION_START =====',
             f'TIMESTEP={ts:10d},BI={bi:3d},BJ=  1']
    for i in range(1, SNX + 1):
        for k in range(1, NZ + 1):
            v = _val(ts, bi, i, k)
            salt = 'BAD' if (special and (ts, bi, i, k) == (5, 1, 1, 1)) else v + 0.1
            lines.append(f'INPUT_STATE,{i:3d},  1,{k:3d},{v},{salt},{v + 0.2},{v + 0.3}')
            lines.append(f'OUTPUT_MIXING,{i:3d},  1,{k:3d},{v + 0.4},{v + 0.5},{v + 0.6},{v + 0.7}')
            if optional:
                lines.append(f'OUTPUT_DIAGNOSTICS,{i:3d},  1,{k:3d},{v},{v + 1},{v + 2},{v + 3},{v + 4}')
        lines.append(f'INPUT_FORCING,{i:3d},  1,{_val(ts, bi, i, 0)},2.0,3.0,4.0,5.0')
        lines.append(f'INPUT_CORIOLIS,{i:3d},  1,{1e-4 * i}')
        hbl = BARE_EXP if (special and (ts, bi, i) == (5, 1, 1)) else _val(ts, bi, i, 9)
        lines.append(f'OUTPUT_HBL,{i:3d},  1,{hbl}')
    lines.append('===== KPP_VALIDATION_END =====')
    return lines


def _write_kpp(path, timesteps, tiles=(1, 2), extra_tail=(), optional_from=None,
               special=False):
    lines = ['some MITgcm preamble', 'PROGRAM MAIN: starting'] + _header_lines(
        'KPP', [('viscAz', '0.1930000E-04'), ('use_ghat', 1)])
    for ts in timesteps:
        for bi in tiles:
            lines += _kpp_block(ts, bi, optional=(optional_from is not None and ts >= optional_from),
                                special=special)
            lines.append('DEBUG: text between blocks is ignored')
    lines += list(extra_tail)
    Path(path).write_text('\n'.join(lines) + '\n')


def test_kpp_multi_tile_values_optional_variables_and_links(tmp_path):
    out = tmp_path / 'output.txt'
    # The first tile's ts=5 (i=1,k=1) state line is malformed (dropped whole); a
    # bare-exponent HBL value must still parse. Diagnostics (with dVsq/Ritop) appear only from ts=6.
    _write_kpp(out, [5, 6], optional_from=6, special=True)

    ip, op = tmp_path / 'i.nc', tmp_path / 'o.nc'
    uid = parse_mitgcm_split(out, ip, op, 'synthetic')
    ins, outs = xr.open_dataset(ip), xr.open_dataset(op)

    assert dict(ins.sizes)['time'] == 2 and dict(ins.sizes)['x'] == 2 * SNX and dict(ins.sizes)['y'] == 1
    assert list(ins['time'].values) == [5, 6]
    assert ins.attrs['uuid'] == uid == outs.attrs['input_uuid']
    assert ins.attrs['experiment'] == 'synthetic'
    assert ins.attrs['viscAz'] == pytest.approx(1.93e-5) and ins.attrs['use_ghat'] == 1
    assert ins.attrs['forcing_validation_data'] == 'absent'   # 8-part forcing lines: no raw fluxes
    assert np.allclose(ins['depth'].values, [-5.0, -15.0]) and np.allclose(ins['cell_thickness'].values, [10.0, 10.0])

    # tile-local (bi, i) -> global x = (bi-1)*sNx + (i-1); values per (ts, bi, i, k)
    for t_idx, ts in enumerate([5, 6]):
        for bi in (1, 2):
            for i in (1, 2):
                x = (bi - 1) * SNX + (i - 1)
                for k in (1, 2):
                    if (ts, bi, i, k) == (5, 1, 1, 1):
                        # malformed state line was dropped entirely -> stays at the zero fill
                        assert ins['temperature'].values[t_idx, x, 0, k - 1] == 0.0
                        assert ins['u_velocity'].values[t_idx, x, 0, k - 1] == 0.0
                    else:
                        v = _val(ts, bi, i, k)
                        assert ins['temperature'].values[t_idx, x, 0, k - 1] == v
                        assert ins['v_velocity'].values[t_idx, x, 0, k - 1] == pytest.approx(v + 0.3)
                    v = _val(ts, bi, i, k)
                    assert outs['visc_az'].values[t_idx, x, 0, k - 1] == pytest.approx(v + 0.4)
                    assert outs['ghat'].values[t_idx, x, 0, k - 1] == pytest.approx(v + 0.7)
                if (ts, bi, i) == (5, 1, 1):
                    assert outs['hbl'].values[t_idx, x, 0] == BARE_EXP_VALUE   # E-less exponent parsed
                else:
                    assert outs['hbl'].values[t_idx, x, 0] == _val(ts, bi, i, 9)

    # Optional variables (dVsq/Ritop) exist because ts=6 supplied them; zero in ts=5.
    assert outs.attrs['kppmix_direct_inputs'] == 'present'
    assert np.all(outs['dVsq'].values[0] == 0.0) and np.all(outs['Ritop'].values[0] == 0.0)
    assert outs['dVsq'].values[1, 0, 0, 0] == pytest.approx(_val(6, 1, 1, 1) + 3)
    assert outs['Ritop'].values[1, 3, 0, 1] == pytest.approx(_val(6, 2, 2, 2) + 4)
    # Never-supplied optional variables are absent, as in the old parser.
    for name in ('swatt', 'boplume', 'bulk_ri', 'q_net', 'qnet_raw'):
        assert name not in ins and name not in outs


def test_kpp_many_appended_timesteps_and_unlimited_time(tmp_path):
    n = 40
    out = tmp_path / 'output.txt'
    _write_kpp(out, list(range(100, 100 + n)))
    ip, op = tmp_path / 'i.nc', tmp_path / 'o.nc'
    parse_mitgcm_split(out, ip, op, 'synthetic')
    ins, outs = xr.open_dataset(ip), xr.open_dataset(op)
    assert list(ins['time'].values) == list(range(100, 100 + n))
    # every appended timestep landed at its own index (value encodes the timestep)
    for t_idx, ts in enumerate(range(100, 100 + n)):
        assert ins['temperature'].values[t_idx, 3, 0, 1] == _val(ts, 2, 2, 2)
        assert outs['hbl'].values[t_idx, 0, 0] == _val(ts, 1, 1, 9)
    import netCDF4
    with netCDF4.Dataset(ip) as nc:
        assert nc.dimensions['time'].isunlimited() and len(nc.dimensions['time']) == n


@pytest.mark.parametrize('order,fragment', [
    ([5, 6, 5], 're-appears'),       # timestep 5 returns after 6
    ([6, 5], 'ascending'),           # descending
])
def test_kpp_rejects_non_contiguous_or_descending_timesteps(tmp_path, order, fragment):
    out = tmp_path / 'output.txt'
    _write_kpp(out, order)
    with pytest.raises(ValueError, match=fragment):
        parse_mitgcm_split(out, tmp_path / 'i.nc', tmp_path / 'o.nc', 'synthetic')


def _ggl_block(ts, bi, with_pr):
    lines = ['===== GGL90_VALIDATION_START =====',
             f'TIMESTEP={ts:10d},BI={bi:3d},BJ=  1']
    for i in range(1, SNX + 1):
        for k in range(1, NZ + 1):
            v = _val(ts, bi, i, k)
            lines.append(f'INPUT_STATE,{i:3d},  1,{k:3d},{v},{v + 0.1},{v + 0.2},{v + 0.3}')
            lines.append(f'INPUT_TKE,{i:3d},  1,{k:3d},{v + 0.4}')
            lines.append(f'OUTPUT_MIXING,{i:3d},  1,{k:3d},{v + 0.5},{v + 0.6},{v + 0.7}')
            lines.append(f'OUTPUT_TKE,{i:3d},  1,{k:3d},{v + 0.8}')
            if with_pr:
                lines.append(f'OUTPUT_RI_SHEAR_PR,{i:3d},  1,{k:3d},{v + 1},{v + 2},{v + 3}')
        lines.append(f'INPUT_FORCING,{i:3d},  1,1.0,2.0,{_val(ts, bi, i, 0)}')
    lines.append('===== GGL90_VALIDATION_END =====')
    return lines


def _write_ggl(path, timesteps, pr_from):
    lines = ['preamble'] + _header_lines('GGL90', [('GGL90ck', '0.1E+00'), ('mxlMaxFlag', 3),
                                                   ('GGL90_dirichlet', 0)])
    for ts in timesteps:
        for bi in (1, 2):
            lines += _ggl_block(ts, bi, with_pr=ts >= pr_from)
    Path(path).write_text('\n'.join(lines) + '\n')


def test_ggl90_multi_tile_defaults_and_in_memory_wrapper(tmp_path):
    out = tmp_path / 'output.txt'
    _write_ggl(out, [3, 4], pr_from=4)
    ip, op = tmp_path / 'i.nc', tmp_path / 'o.nc'
    uid = parse_mitgcm_ggl90_split_to_files(out, ip, op, 'synthetic')
    ins, outs = xr.open_dataset(ip), xr.open_dataset(op)

    assert ins.attrs['uuid'] == uid == outs.attrs['input_uuid']
    assert ins.attrs['sigma_r_data'] == 'absent'          # no INPUT_SIGMAR lines
    assert outs.attrs['ri_shear_pr_data'] == 'present' and outs.attrs['idemix_gtke_data'] == 'absent'
    assert ins.attrs['GGL90ck'] == pytest.approx(0.1) and ins.attrs['mxlMaxFlag'] == 3
    assert dict(outs.sizes)['x'] == 4 and list(outs['time'].values) == [3, 4]
    assert outs['tke_after'].values[0, 3, 0, 1] == pytest.approx(_val(3, 2, 2, 2) + 0.8)
    assert ins['u_star_sq'].values[1, 2, 0] == _val(4, 2, 1, 0)
    # ri_shear_pr: zero fill before it appears; TKEPrandtlNumber defaults to 1 (Fortran init value)
    assert np.all(outs['ri_number'].values[0] == 0.0) and np.all(outs['tke_prandtl_number'].values[0] == 1.0)
    assert outs['ri_number'].values[1, 0, 0, 0] == pytest.approx(_val(4, 1, 1, 1) + 1)
    assert outs['tke_prandtl_number'].values[1, 0, 0, 0] == pytest.approx(_val(4, 1, 1, 1) + 3)

    # The in-memory wrapper (used by compare_scenario_ggl90_standalone.py) returns
    # loaded Datasets with the same content.
    ins_m, outs_m = parse_mitgcm_ggl90_split(out, 'synthetic')
    for name in outs.data_vars:
        assert np.array_equal(outs_m[name].values, outs[name].values)
    for name in ins.data_vars:
        assert np.array_equal(ins_m[name].values, ins[name].values)
    assert set(outs_m.data_vars) == set(outs.data_vars)
