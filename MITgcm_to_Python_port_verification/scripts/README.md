# KPP/GGL90 Validation Scripts

This directory contains the core validation pipeline for both the Python KPP
port and the Python GGL90 port.

## Active Validation Scripts

**Complete validation workflow** (use these scripts):

1. **`parse_mitgcm_split.py`** (KPP) / **`parse_mitgcm_ggl90_split.py`** (GGL90)
   - Parse MITgcm STDOUT to NetCDF files
   - Input: MITgcm `output.txt` with validation data
   - Output: `mitgcm_kpp_inputs.nc`/`mitgcm_ggl90_inputs.nc` and the matching
     `..._outputs.nc`
   - **Streaming (1DMIX-065)**: both parsers share the engine in
     `capture_stream.py`. `output.txt` is read line by line (two passes: a
     counters-only scan for the grid extent, timesteps and which optional
     variables occur, then a write pass) and each completed timestep, all tiles,
     is appended to the NetCDF files and dropped. Peak memory is one timestep of
     arrays plus fixed metadata, independent of file length. This replaced a
     parser that kept every value of every timestep in Python dicts until the
     end: the 13.8 GB `global_oce_latlon_720` capture exhausted 27 GB of RAM
     and never finished, while the streaming parser handles it in a fraction of
     a GB (measured peak RSS is recorded in
     `KPP_port_validation/CAPTURES.md`). Output files are identical in
     variables, dimensions, attributes, dtypes and values to the old parser's
     (checked variable by variable); the one on-disk difference is that
     `time` is an unlimited dimension. The parsers require each timestep's
     blocks to be contiguous and timesteps ascending (as MITgcm writes them) and
     raise `ValueError` otherwise. `parse_mitgcm_ggl90_split.parse_mitgcm_ggl90_split`
     still returns in-memory Datasets for small captures (used by
     `compare_scenario_ggl90_standalone.py`); large ones should use
     `parse_mitgcm_ggl90_split_to_files` or the command line.

2. **`run_kpp_from_netcdf_input.py`** (KPP) / **`run_ggl90_from_netcdf_input.py`** (GGL90)
   - Run the Python port from NetCDF inputs
   - Input: NetCDF input file (from step 1 or custom)
   - Output: Python port outputs with UUID provenance tracking (`input_uuid`
     matches the input file's own `uuid` attribute)
   - `run_kpp_from_netcdf_input.py`'s CLI additionally does a quick console
     comparison with MITgcm outputs if a matching file is found automatically
   - `run_ggl90_from_netcdf_input.py` (1DMIX-054): `run(inputs_nc, output_nc, first_timestep=None,
     last_timestep=None)` and CLI `--first N --last N` (0-indexed, inclusive) replay a contiguous
     subset of a long capture, like the KPP script's arguments of the same name; the selected inputs
     are `.load()`ed once (a multi-column capture is otherwise re-read per column, thousands of times
     slower; results are numerically identical).
   - **Tracer-point inputs (1DMIX-071)**: MITgcm's shear at a tracer point uses the (i,i+1),(j,j+1)
     velocities and KPP's smoothed quantities use the 3x3 neighbourhood. By default both replays rebuild
     them from the neighbouring captured columns with `tracer_point_inputs.py` (periodic wrap = MITgcm's
     default exchange): GGL90 (`run(..., tracer_point_velocities=True)`) feeds ubar/vbar to the port; KPP
     (`run_python_kpp_on_dataset(..., tracer_point_inputs=True)`) passes `shsq`, `dVsq` and the smoothed
     `dbloc` through `KPPDriver.compute_mixing`'s keyword-only `shsq_forcing`/`dvsq_forcing`/
     `dbloc_smooth_forcing`. `--column-local` (CLI) / `False` restores the former column-local replay.
     The GGL90 replay raises `ValueError` for a capture with calcMeanVertShear=1, the KPP replay
     `NotImplementedError` for captures built with KPP_ESTIMATE_UREF/SMOOTH_DVSQ/SMOOTH_DENS/SMOOTH_VISC/
     SMOOTH_DIFF. Where the periodic-wrap rule is actually verified (wrap and zero-fill give different reconstructions and wrap matches the capture; counts from this issue and from Richard's review): x on `global_ocean.90x40x15` (GGL90 2,790 of 3,830 domain-edge interfaces; KPP 6,039 of 10,220), `global_oce_latlon` (1,610 cells, review) and `seaice_obcs` (245); y only on `seaice_obcs` and the 1x1 single-column captures. NOT verified: y on the global grids and on every GGL90 capture, and both axes on `lab_sea` and `isomip`, because wrap and zero-fill give identical reconstructions there (closed basins whose edge columns are land). See the two `*_VALIDATION_RESULTS.md` documents and `tests/test_tracer_point_inputs.py`.

3. **`generate_kpp_validation_report.py`** (KPP) / **`generate_ggl90_validation_report.py`** (GGL90, 1DMIX-044)
   - Generate a comprehensive multi-page PDF validation report
   - Inputs: MITgcm output NetCDF + Python output NetCDF + optional output path
   - Output: PDF with provenance page, statistics tables (median/p95/max abs
     and relative error), scatter/histogram and (for single-column captures)
     vertical-profile comparison pages, and a pass/fail assessment page.
     KPP's report covers `hbl`/`visc_az`/`diff_kz_s`/`diff_kz_t`/`ghat`;
     GGL90's covers `visc_az`/`diff_kz`/`mixing_length`/`tke_after` (GGL90's
     own field set, per `compare_ggl90.py`'s established naming/wet-mask
     convention — reused, not reinvented).
   - If the Python output's time axis is a strict prefix of MITgcm's (e.g. a
     `--last`-truncated replay of a very large capture), the KPP generator
     automatically restricts MITgcm to the same leading subsample before
     computing statistics (1DMIX-044 fix) rather than crashing on a shape
     mismatch.

## Documentation

- **`../KPP_port_validation/NETCDF_DATA_FORMAT.md`**, **`../GGL90_port_validation/NETCDF_DATA_FORMAT.md`** - NetCDF format specifications
- **`../KPP_port_validation/SIMPLIFIED_API_SUMMARY.md`** - Forcing API reference

## Example Usage

```bash
# Step 1: Parse MITgcm output
cd /path/to/mitgcm/run
python /path/to/scripts/parse_mitgcm_split.py output.txt lab_sea

# Step 2: Run Python KPP
cd /path/to/1D_Mixing_Experiments
python scripts/run_kpp_from_netcdf_input.py \
  KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs.nc

# Step 3: Generate validation report
python scripts/generate_kpp_validation_report.py \
  KPP_port_validation/outputs_from_mitgcm/mitgcm_kpp_outputs.nc \
  KPP_port_validation/outputs_from_python/mitgcm_kpp_inputs_python.nc \
  KPP_port_validation/reports/validation_report.pdf
```

## Current Validation Status

See `../README.md`'s status table and the repo root's `open_issues.md` /
`closed_issues.md` for current, accurate results — this is the source of
truth, not the numbers below.

`../KPP_port_validation/archive_2026-08-investigation/INVESTIGATION_CONCLUSION.md`
and `VALIDATION_SUMMARY.md` document an early (2026-08-20) investigation phase
that concluded "all formulas verified correct" against a single dataset
(11,000 timesteps, `1D_ocean_ice_column`, mean relative error 0.18%). That
conclusion is now known to be **incomplete**: real bugs were found and fixed
afterward (forcing-validation and EOS derivative bugs — 1DMIX-013, 1DMIX-017;
harness bugs found while extending to `lab_sea` — 1DMIX-018). Treat those
archived documents as historical record only.

## Reports Directory

Generated PDF validation reports and two still-relevant lessons-learned docs
are stored in `../KPP_port_validation/reports/`. `../GGL90_port_validation/reports/`
holds the GGL90 equivalent (1DMIX-044) — both directories are now structurally
symmetric.

## See Also

- NetCDF format spec: `../KPP_port_validation/NETCDF_DATA_FORMAT.md`
- Top-level overview and current status: `../README.md`
