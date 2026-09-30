#!/usr/bin/env python3
"""
Streaming reader / incremental NetCDF writer shared by the two MITgcm capture
parsers, ``parse_mitgcm_split.py`` (KPP) and ``parse_mitgcm_ggl90_split.py``
(GGL90).

Why this exists (1DMIX-065): the previous parsers iterated the captured
``output.txt`` line by line but stored *every* value of *every* timestep in
nested Python dicts, and only built the NumPy arrays / NetCDF files at the
very end. Memory therefore grew with file length: the 13.8 GB
``global_oce_latlon_720`` capture held >24 GB of a 27 GB machine for more than
25 minutes without finishing. This module keeps memory bounded by **one
timestep** (all tiles) of arrays, independent of file length.

How it works (two sequential passes over the text file, nothing kept but
counters and one timestep of arrays):

1. **Scan pass.** Read the file with the same line grammar the old parsers
   used and keep only: the parameter block, the grid block, the distinct
   timestep numbers (in encounter order), the tile-local index maxima and tile
   counts (which fix ``nx``, ``ny``), and which optional variables ever
   received a value (which decides whether they exist in the NetCDF file, exactly
   as the old ``has_*`` flags did). The scan raises ``ValueError`` if a
   timestep number re-appears after a different one or the numbers are not
   ascending -- the old parser sorted timesteps and silently merged
   non-contiguous blocks; a streaming writer cannot, so it refuses rather than
   risk a different result. MITgcm writes timesteps in ascending order, tiles
   contiguous within a timestep.
2. **Write pass.** Read the file again, fill per-timestep arrays (all tiles of
   one timestep), and when the timestep changes flush the arrays to the NetCDF
   files and reuse them. The first timestep is written through
   ``xarray.Dataset.to_netcdf`` (so variable/coordinate attributes, ``_FillValue``,
   ``coordinates`` attributes, compression and dtypes are produced by the same
   encoder as before), with ``time`` as an unlimited dimension; every later
   timestep is appended with ``netCDF4``.

The content of the resulting files (variables, dimensions, coordinates,
attributes, dtypes, values) is identical to what the old whole-file parsers
wrote; the only on-disk differences are that ``time`` is an unlimited
dimension (HDF5 chunking differs accordingly) and, as before, the per-run
``uuid``/``creation_date``. The identity was checked variable by variable
against the old implementations, see the 1DMIX-065 evidence log.

The per-scheme knowledge (marker names, tags, variable tables, attributes)
lives in a ``ParserSpec`` supplied by each parser script.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

import netCDF4
import numpy as np
import xarray as xr

# Fortran's fixed-width E-format drops the "E" when the exponent needs 3
# digits to fit the field width, e.g. '0.105188567206-104' instead of
# '0.105188567206E-104'. Python's float() raises ValueError on the "E"-less
# form (closed issue 1DMIX-012).
_FORTRAN_BARE_EXPONENT = re.compile(r'^([+-]?\d*\.\d+)([+-]\d+)$')

# The TIMESTEP header (format '(A,I10,A,I3,A,I3)') always carries the tile
# indices BI=/BJ=, even for single-tile (nSx=nSy=1) experiments (where they
# are always 1,1). Every index parsed from a data line is tile-local (i,j); a
# real multi-tile domain (e.g. global_oce_latlon's nSx=nSy=2) reuses the same
# local index range in every tile, so BI/BJ and the tile size (inferred from
# the data) are needed to map (i,j) to global (x,y) (1DMIX-021).
TIMESTEP_HEADER = re.compile(r'^TIMESTEP=\s*(-?\d+),BI=\s*(\d+),BJ=\s*(\d+)$')


def ffloat(s: str) -> float:
    """float() that also accepts Fortran's E-less bare-exponent form."""
    try:
        return float(s)
    except ValueError:
        m = _FORTRAN_BARE_EXPONENT.match(s.strip())
        if m:
            return float(m.group(1) + 'E' + m.group(2))
        raise


def skip_until(f, marker: str) -> None:
    """Advance the file iterator past the line equal to ``marker``."""
    for line in f:
        if line.strip() == marker:
            break


@dataclass(frozen=True)
class VarDef:
    """One NetCDF data variable.

    ``dims`` are the dimensions after ``time`` (e.g. ``('x', 'y', 'z')``).
    ``optional`` variables exist in the output only if at least one data line
    supplied a value for them anywhere in the file (the old ``has_*`` flags);
    all other variables are always written. ``fill`` is the value cells that
    receive no data line hold (the old ``np.zeros``/``np.ones`` allocation).
    """
    name: str
    dims: Tuple[str, ...]
    attrs: Dict[str, str]
    fill: float = 0.0
    optional: bool = False


# A parsed data line becomes a list of (variable name, i, j, k, value) with
# tile-local zero-based i, j and k=None for horizontal (x, y) variables.
Update = Tuple[str, int, int, Optional[int], float]


@dataclass
class ParserSpec:
    """Everything scheme-specific the streaming engine needs.

    ``prefix`` is 'KPP' or 'GGL90': the text markers are
    ``===== <prefix>_MODEL_PARAMETERS =====`` (+ ``_END``),
    ``<prefix>_GRID_GEOMETRY``, ``<prefix>_DATA_HEADERS`` and
    ``<prefix>_VALIDATION_START``/``_END``.
    """
    prefix: str
    extent_tags: FrozenSet[str]
    parse_parameters: Callable
    parse_grid: Callable
    parse_line: Callable[[str, List[str]], Optional[List[Update]]]
    inputs_vars: Sequence[VarDef]
    outputs_vars: Sequence[VarDef]
    # (grid_info) -> {coord_name: (dims, values, attrs)} for the vertical
    # coordinates that follow time/x/y.
    inputs_coords: Callable[[dict], dict]
    outputs_coords: Callable[[dict], dict]
    # (nx, ny, nz) -> {dimension name: size} for every non-time dimension.
    dim_sizes: Callable[[int, int, int], Dict[str, int]]
    # (experiment, output_file, run_uuid, params, seen_variable_names)
    # -> ordered global attributes.
    inputs_attrs: Callable[..., dict]
    outputs_attrs: Callable[..., dict]


class _State:
    """Mutable bookkeeping updated while a file is read."""

    def __init__(self):
        self.params: dict = {}
        self.grid_info: dict = {}
        self.nz_max: int = 0
        self.local_i_max: int = 0
        self.local_j_max: int = 0
        self.bi_max: int = 1
        self.bj_max: int = 1


def _iter_events(output_file: Path, spec: ParserSpec, st: _State):
    """Yield ('block', ts, bi, bj) per TIMESTEP header and
    ('data', bi, bj, updates) per successfully parsed data line.

    The line grammar, marker precedence and the "drop the whole line on
    ValueError/IndexError" behaviour are those of the old whole-file parsers.
    """
    p = spec.prefix
    m_params = f'===== {p}_MODEL_PARAMETERS ====='
    m_grid = f'===== {p}_GRID_GEOMETRY ====='
    m_headers = f'===== {p}_DATA_HEADERS ====='
    m_headers_end = f'===== {p}_DATA_HEADERS_END ====='
    m_start = f'===== {p}_VALIDATION_START ====='
    m_end = f'===== {p}_VALIDATION_END ====='
    extent_tags = spec.extent_tags
    parse_line = spec.parse_line

    with open(output_file, 'r') as f:
        in_block = False
        cur_ts = None
        cur_bi, cur_bj = 1, 1

        for line in f:
            line = line.strip()

            if line == m_params:
                st.params = spec.parse_parameters(f)
                continue
            if line == m_grid:
                st.grid_info = spec.parse_grid(f)
                st.nz_max = st.grid_info['nr']
                continue
            if line == m_headers:
                skip_until(f, m_headers_end)
                continue
            if line == m_start:
                in_block = True
                continue

            if in_block and line.startswith('TIMESTEP='):
                m = TIMESTEP_HEADER.match(line)
                if m:
                    cur_ts = int(m.group(1))
                    cur_bi, cur_bj = int(m.group(2)), int(m.group(3))
                else:
                    # Older/malformed header without BI=/BJ= -- treat as the
                    # single-tile case (current captures always emit BI/BJ).
                    cur_ts = int(line.split(',')[0].split('=')[1].strip())
                    cur_bi, cur_bj = 1, 1
                st.bi_max = max(st.bi_max, cur_bi)
                st.bj_max = max(st.bj_max, cur_bj)
                yield ('block', cur_ts, cur_bi, cur_bj)
                continue

            if line == m_end:
                in_block = False
                cur_ts = None
                continue

            if not in_block or not line or cur_ts is None:
                continue

            parts = line.split(',')
            if len(parts) < 2:
                continue
            tag = parts[0]

            try:
                # The tile-local index maxima are updated before the values
                # are parsed, so a line whose floats fail to parse still
                # counts toward the extent (as in the old parsers).
                if tag in extent_tags:
                    i, j = int(parts[1]) - 1, int(parts[2]) - 1
                    if i > st.local_i_max:
                        st.local_i_max = i
                    if j > st.local_j_max:
                        st.local_j_max = j
                updates = parse_line(tag, parts)
            except (ValueError, IndexError):
                continue
            if updates:
                yield ('data', cur_bi, cur_bj, updates)


class _IncrementalNetCDF:
    """Create a NetCDF file from its first timestep, then append the rest."""

    def __init__(self, path: Path, vars_present: Sequence[VarDef], nx: int,
                 ny: int, coords: dict, attrs: dict):
        self.path = Path(path)
        self.vars = list(vars_present)
        self.nx, self.ny = nx, ny
        self.coords = coords
        self.attrs = attrs
        self._nc = None
        self.n_written = 0

    def _dataset(self, timesteps: Sequence[int],
                 arrays: Dict[str, np.ndarray]) -> xr.Dataset:
        data_vars = {
            v.name: (['time', *v.dims], arrays[v.name], dict(v.attrs))
            for v in self.vars
        }
        coords = {'time': list(timesteps), 'x': np.arange(self.nx),
                  'y': np.arange(self.ny)}
        for name, (dims, values, cattrs) in self.coords.items():
            coords[name] = (dims, values, cattrs)
        ds = xr.Dataset(data_vars=data_vars, coords=coords)
        ds.attrs.update(self.attrs)
        return ds

    def _write_first(self, ds: xr.Dataset) -> None:
        encoding = {v.name: {'zlib': True, 'complevel': 4} for v in self.vars}
        ds.to_netcdf(self.path, encoding=encoding, unlimited_dims=['time'])

    def append(self, ts: int, arrays: Dict[str, np.ndarray]) -> None:
        if self._nc is None:
            first = {name: arr[np.newaxis, ...] for name, arr in arrays.items()}
            self._write_first(self._dataset([ts], first))
            self._nc = netCDF4.Dataset(self.path, 'a')
            # Bound the HDF5 chunk cache per variable. With this project's
            # netCDF4 4.10.1 / HDF5 2.2.0 build the default cache of a
            # compressed variable appended along an unlimited dimension never
            # evicts: every appended timestep stayed resident (RSS grew by the
            # full size of the data, measured 1.4 GB for 24 variables x 999
            # small timesteps). One appended timestep is exactly one chunk
            # (time chunk length 1), so a cache of a few chunks is enough.
            for v in self.vars:
                var = self._nc.variables[v.name]
                chunk = var.chunking()
                chunk_bytes = (int(np.prod(chunk)) * var.dtype.itemsize
                               if chunk != 'contiguous' else 0)
                var.set_var_chunk_cache(size=max(2**20, 2 * chunk_bytes),
                                        nelems=521, preemption=0.75)
        else:
            n = self.n_written
            self._nc.variables['time'][n] = ts
            for v in self.vars:
                self._nc.variables[v.name][n, ...] = arrays[v.name]
        self.n_written += 1

    def close(self, empty_shapes: Optional[Dict[str, tuple]] = None) -> None:
        if self._nc is None:
            # No validation block at all: write the same empty-time file the
            # old parsers produced.
            arrays = {name: np.zeros(shape) for name, shape in empty_shapes.items()}
            self._write_first(self._dataset([], arrays))
        else:
            self._nc.close()
            self._nc = None


def stream_convert(output_file, experiment_name: str, spec: ParserSpec,
                   inputs_path, outputs_path, progress_every: int = 100) -> str:
    """Convert one MITgcm ``output.txt`` capture into the split
    inputs/outputs NetCDF pair without holding more than one timestep in
    memory. Returns the run UUID stored in both files (``uuid`` in the inputs,
    ``input_uuid`` in the outputs)."""
    output_file = Path(output_file)
    run_uuid = str(uuid.uuid4())
    print(f"  Experiment: {experiment_name}")
    print(f"  UUID: {run_uuid}")

    # ---- pass 1: scan (counters only) -----------------------------------
    st = _State()
    timesteps: List[int] = []
    seen_ts = set()
    seen_vars = set()
    tracked = {v.name for v in (*spec.inputs_vars, *spec.outputs_vars)}
    for ev in _iter_events(output_file, spec, st):
        if ev[0] == 'block':
            ts = ev[1]
            if not timesteps or timesteps[-1] != ts:
                if ts in seen_ts:
                    raise ValueError(
                        f"timestep {ts} re-appears after a different timestep in "
                        f"{output_file}; the streaming parser requires each "
                        "timestep's blocks to be contiguous")
                if timesteps and ts < timesteps[-1]:
                    raise ValueError(
                        f"timestep {ts} follows {timesteps[-1]} in {output_file}; "
                        "the streaming parser requires ascending timesteps")
                timesteps.append(ts)
                seen_ts.add(ts)
        else:
            for u in ev[3]:
                if u[0] not in seen_vars and u[0] in tracked:
                    seen_vars.add(u[0])

    # sNx/sNy (uniform per-tile size) inferred from the tile-local index range
    # actually observed -- MITgcm's decomposition is exact (every tile is
    # exactly sNx x sNy), so the maximum local index seen over ALL tiles
    # equals sNx-1/sNy-1.
    sNx, sNy = st.local_i_max + 1, st.local_j_max + 1
    nx, ny, nz = st.bi_max * sNx, st.bj_max * sNy, st.nz_max
    n_time = len(timesteps)
    print(f"  Parsed: {n_time} timesteps, grid {nx}x{ny}x{nz}"
          f" ({st.bi_max}x{st.bj_max} tiles of {sNx}x{sNy})")

    sizes = spec.dim_sizes(nx, ny, nz)
    in_vars = [v for v in spec.inputs_vars if not v.optional or v.name in seen_vars]
    out_vars = [v for v in spec.outputs_vars if not v.optional or v.name in seen_vars]
    grid_info, params = st.grid_info, st.params

    def shape(v: VarDef) -> tuple:
        return tuple(sizes[d] for d in v.dims)

    in_writer = _IncrementalNetCDF(
        inputs_path, in_vars, nx, ny, spec.inputs_coords(grid_info),
        spec.inputs_attrs(experiment_name, output_file, run_uuid, params, seen_vars))
    out_writer = _IncrementalNetCDF(
        outputs_path, out_vars, nx, ny, spec.outputs_coords(grid_info),
        spec.outputs_attrs(experiment_name, run_uuid, seen_vars))

    # ---- pass 2: fill one timestep of arrays, flush on timestep change ----
    cur = {v.name: np.full(shape(v), v.fill) for v in (*in_vars, *out_vars)}
    fills = {v.name: v.fill for v in (*in_vars, *out_vars)}

    def flush(ts: int) -> None:
        in_writer.append(ts, {v.name: cur[v.name] for v in in_vars})
        out_writer.append(ts, {v.name: cur[v.name] for v in out_vars})
        done = in_writer.n_written
        if progress_every and (done % progress_every == 0 or done == n_time):
            print(f"  wrote timestep {done}/{n_time}", flush=True)

    cur_ts = None
    for ev in _iter_events(output_file, spec, _State()):
        if ev[0] == 'block':
            if ev[1] != cur_ts:
                if cur_ts is not None:
                    flush(cur_ts)
                    for name, arr in cur.items():
                        arr.fill(fills[name])
                cur_ts = ev[1]
        else:
            x0, y0 = (ev[1] - 1) * sNx, (ev[2] - 1) * sNy
            for name, i, j, k, val in ev[3]:
                if k is None:
                    cur[name][x0 + i, y0 + j] = val
                else:
                    cur[name][x0 + i, y0 + j, k] = val
    if cur_ts is not None:
        flush(cur_ts)

    empty_in = {v.name: (0, *shape(v)) for v in in_vars}
    empty_out = {v.name: (0, *shape(v)) for v in out_vars}
    in_writer.close(empty_in)
    out_writer.close(empty_out)
    return run_uuid


def now_iso() -> str:
    """Timestamp string used for the ``creation_date`` attribute."""
    return datetime.now().isoformat()
