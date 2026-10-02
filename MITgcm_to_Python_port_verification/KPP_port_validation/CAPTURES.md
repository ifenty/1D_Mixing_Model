# Capture manifest — KPP_port_validation

Written under 1DMIX-046 to resolve "which versioned file is current" for every
experiment that has more than one capture on disk, and to document the two
oddly-located `_python.nc`-suffixed files (1DMIX-046 task 5). Experiments with
exactly one input/output/python-output set (`lab_sea_1000_0820T0946` — now single
after this issue removed its stray duplicate, see below —, `lab_sea_6mo`,
`seaice_obcs_1dmix034`, `global_oce_latlon_720`) need no entry beyond noting
that single-version status; `global_oce_latlon_720` gets one anyway below since
it is a brand-new capture (1DMIX-049) worth documenting at introduction.

## Regenerated on WSL, 1DMIX-065 (2026-09-30)

The repo moved to a fresh WSL checkout on 2026-09-29 and every gitignored `*.nc`
capture was absent. 1DMIX-065 regenerated the KPP files below from scratch on
that host, using this repo's instrumented `mitgcm_verification_mods/*/code_validation`
trees and the Docker workflow (`~/Projects/MITgcm_verification_docker`,
image `mitgcm:latest`, `x86_64`, optfile `linux_amd64_gfortran`). Recorded per
file: the recipe that produced it, the MITgcm commit, the date and the sha256.
No Python-port output was used as an MITgcm reference and no MITgcm file was
produced by the Python port: the `*_from_mitgcm/` files come only from an
MITgcm run (parsed by `parse_mitgcm_split.py`); the `outputs_from_python/`
files (and the historically-mislocated `mitgcm_kpp_inputs_11k_1D_python.nc`)
come only from replaying the port on the paired input capture.

- **MITgcm commit**: `d861cd501f21303825de860eb3caa0a8a7ae22f8` (2026-09-06,
  `~/Projects/MITgcm`, tracked tree unmodified; build/run directories are
  untracked dirs under `verification/`).
- **Date**: runs and replays on 2026-09-30 (UTC; the host clock read 2026-09-29
  PDT). **Docker image**: `mitgcm:latest` (id `6cc66b8957d8`).
- **Parser**: all `mitgcm_kpp_*` files were parsed with the streaming
  `scripts/parse_mitgcm_split.py` (see below), so they carry fresh run UUIDs
  and use an unlimited `time` dimension (one HDF5 chunk per timestep, so the
  small captures are several times larger on disk than the old files; values
  and attributes are identical in content).

### Recipes (cwd `~/Projects/MITgcm/verification` unless stated; `<mods>` = `<repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods`)

| Id | Steps |
|---|---|
| **R1** `1D_10_kppmix_extend_rawflux_fix` (10 steps) | `./experiment_compile.sh 1D_ocean_ice_column -mods <mods>/1D_ocean_ice_column/code_validation -build build_docker_kppmix_extend -j 8`; `./experiment_run_no_compile.sh 1D_ocean_ice_column -build build_docker_kppmix_extend -output output_validation_1D10_rawflux_fix` (stock `input/`, `nTimeSteps=10`); parse (repo root): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py <run>/output.txt 1D_ocean_ice_column`, then copy the resulting `mitgcm_kpp_inputs.nc`/`mitgcm_kpp_outputs.nc` to the documented names. |
| **R2** `11k_1D` (11,000 steps) | same build as R1; run input dir `input_validation_11k` = `cp -r input input_validation_11k` with the single edit in `data` swapping `nTimeSteps= 10` / `# nTimeSteps= 11000` (as `1D_ocean_ice_column/README_11K_TIME_STEP_SIMULATION.TXT` describes): `./experiment_run_no_compile.sh 1D_ocean_ice_column input_validation_11k -build build_docker_kppmix_extend -output output_validation_11k`; parse as R1. |
| **R3** `lab_sea_1000_0820T0946` (999 steps) | `./experiment_compile.sh lab_sea -mods <mods>/lab_sea/code_validation -build build_docker_kpp_validation -j 8`; run input dir `input_validation_1000` = `cp -r input input_validation_1000` with the single edit in `data` `endTime=36000.` -> `endTime=3600000.` (`startTime=3600`, `deltaT=3600` => 999 steps): `./experiment_run_no_compile.sh lab_sea input_validation_1000 -build build_docker_kpp_validation -output output_validation_1000`; parse as R1 with experiment name `lab_sea`. |
| **R4** `global_oce_latlon_720` (720 steps x 4 tiles) | `./experiment_compile.sh global_oce_latlon -mods <mods>/global_oce_latlon/code_validation -build build_docker_kpp_fwd -j 8`; run directory `global_oce_latlon/input_docker_kpp_fwd` assembled exactly as `<mods>/global_oce_latlon/input_validation/README.md` "Reproducing the run directory" describes; `./experiment_run_no_compile.sh global_oce_latlon input_docker_kpp_fwd -build build_docker_kpp_fwd -output output_validation_720` (9 min, `output.txt` 13,823,541,777 bytes); parse as R1 with experiment name `global_oce_latlon` (7.5 min wall, peak RSS 0.155 GB under a `ulimit -v` 8 GB bound). |
| **P1** / **P2** / **P3** | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_<tag>.nc -o KPP_port_validation/outputs_from_python/python_kpp_outputs_<tag>.nc -j N` for `<tag>` = `1D_10_kppmix_extend_rawflux_fix` (P1), `11k_1D` (P2), `lab_sea_1000_0820T0946` (P3). |
| **P2b** | the same command as P2 with `-o KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` (the historically-mislocated name `compute_validation_statistics.py` opens; see the `11k_1D` section below). |

The two `data` edits (R2, R3) were not recorded anywhere in the repo before
1DMIX-065; they are inferred from the capture names, the captured time
dimensions (10 / 11,000 / 999) and the experiment README, so they reproduce
those runs' step counts but were not checked against the original Mac-era run
directories, which are not available. The regenerated `lab_sea` 999-step
capture is clean of the `OUTPUT_MIXING` truncation defect (0 of 149,850 ocean
column-timesteps; exactly 1710 active `visc_az` cells per timestep), whereas
the Mac-era file's documented active-cell count (1,637,981, i.e. 1639.6 per
timestep) implies it was not; that is why its relative-error statistics differ
slightly from `KPP_VALIDATION_RESULTS.md` while every other capture reproduces
the documented statistics to all printed digits.

### File provenance (sha256 of the bytes on the WSL checkout)

*Superseded by 1DMIX-070 ("Recaptured at 17 digits, 1DMIX-070" below): the bytes and hashes in this table (and in the 1DMIX-066 table further down) are the 16-digit captures; the current files replaced them in place.*

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | R2 | 23352759 | `ccdc7c99d2f3c55c2ff876d4ba0ca96ac1820b99ff22484b445da21eac7c17e4` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | P2b | 1614204 | `f59ee889989c7fd5ad0de690a36b78245475d0e450a404d8eddeddd09b04e789` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 129296 | `bf77754a8d59935ed81b11e4727552bd981172622695378cf90867a8559f3aef` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_oce_latlon_720.nc` | R4 | 704325331 | `89b324673fce191fe5e8995d7cbd86337e96cd4a5973e1cf731a8677bcc9d124` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc` | R3 | 73433208 | `6b8f7946eceee3d326c6bbb3701208f649b0c3187d8e472e04e0cb4be5183d75` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | R2 | 21556047 | `3730eb4bbd19da9f7260350b850b41dd9bde39487a8792b75557f7b85eb8012c` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 104890 | `8fad79bc2fd464274e2096c7d490fde738986cc74c3fe7b844cede7db93cd15a` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_oce_latlon_720.nc` | R4 | 1090886385 | `ada88d19bd2272fc58659c2518e64bb069ef5cf9569846267ff27bcac5cfe9e6` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_1000_0820T0946.nc` | R3 | 124875004 | `bed79b942d995f186f4fc05a5409da032dc5b99f7852213a2278ecb3304efca8` |
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | P2 | 1614204 | `ffb39a04e336d0c35d8594b97c01108c541cbaa97c74a7a5fbfdfb1148f58b49` |
| `outputs_from_python/python_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | P1 | 66309 | `ae691c9ad1a7e086680528cb3b982f14261758dca793a306a47d78285f68c97c` |
| `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc` | P3 | 27497628 | `d59fafbc942b55eaa8bf526ab610d2188ee8f8fc8bd550153f029f8fbe2eaf4f` |

### Streaming parser (why the capture step changed)

The previous `parse_mitgcm_split.py` kept every value of every timestep in
Python dicts and built the arrays at the end. On this 27 GB host the 13.8 GB
`global_oce_latlon_720` capture held >24 GB for more than 25 minutes without
finishing. The parser now streams (engine `scripts/capture_stream.py`): each
completed timestep is appended to the NetCDF files and dropped. Measured on the
same file under a `ulimit -v` 8 GB bound: 449.6 s wall, **peak RSS 0.155 GB**.
Output content was verified identical to the old parser's on the 10-step,
11,000-step and 999-step `lab_sea` captures and a 4-timestep, 4-tile slice of
`global_oce_latlon`, variable by variable and byte for byte (only `uuid`,
`creation_date`, `output_file_path` and `input_uuid` excluded); see
`scripts/README.md` and `devel-loop/loop_state/bob-1DMIX-065-evidence.md`.

## Regenerated on WSL, 1DMIX-066 (2026-09-30)

The two remaining KPP captures the tests load, `lab_sea_6mo` and
`seaice_obcs_1dmix034`, were regenerated on the same host, image and MITgcm
commit as the 1DMIX-065 set above (`d861cd501f21303825de860eb3caa0a8a7ae22f8`,
`mitgcm:latest` id `6cc66b8957d8`, runs and replays 2026-09-30; cwd
`~/Projects/MITgcm/verification` unless stated; `<mods>` as above), with the
same provenance rules: MITgcm files only from a Docker MITgcm run parsed by
the streaming `scripts/parse_mitgcm_split.py`, Python files only from
replaying the port on the regenerated input. The GGL90 captures regenerated
under the same issue are in `../GGL90_port_validation/CAPTURES.md`.

| Id | Steps |
|---|---|
| **R5** `lab_sea_6mo` (4368 steps, **INFERRED**) | `./experiment_compile.sh lab_sea -mods <mods>/lab_sea/code_validation -build build_docker_kpp_validation -clean -j 8`; run input dir `input_validation_6mo` = `cp -r input input_validation_6mo` with the single edit in `data` `endTime=36000.` -> `endTime=15728400.` (`startTime=3600`, `deltaT=3600` => (15728400-3600)/3600 = 4368 steps, the rule that gives R3's 999 steps for `endTime=3600000.`): `./experiment_run_no_compile.sh lab_sea input_validation_6mo -build build_docker_kpp_validation -output output_kpp_6mo_1dmix066` (5 min 16 s, `output.txt` 8,230,063,413 bytes, 4368 validation blocks); parse (repo root, `ulimit -v 8000000`): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py <run>/output.txt lab_sea` (3 min 49 s, **peak RSS 0.174 GB**). The `endTime` edit is recorded nowhere in the repo; it is inferred from the capture name, the step count (4368) and the documented 655,200 wet column-timesteps (4368 x 150), all of which the regenerated file matches. Supporting evidence (1DMIX-066 review, Richard's own recomputation of the tracked Mac-era report `reports/kpp_validation_lab_sea_6mo.pdf`): the regenerated capture's `hbl` statistics match that report; `seaice_obcs` likewise matches `reports/kpp_validation_seaice_obcs_1dmix034.pdf`. The `endTime` edit itself remains unrecorded, so the row stays INFERRED. |
| **R6** `seaice_obcs_1dmix034` (5 steps, 2 tiles) | `./experiment_compile.sh seaice_obcs -mods <mods>/seaice_obcs/code_validation -build build_docker_kpp_validation -clean -j 8`; `./experiment_run_no_compile.sh seaice_obcs input -build build_docker_kpp_validation -output output_kpp_seaice_obcs_1dmix066` (stock `input/`, `startTime=3600`/`endTime=21600.`/`deltaT=3600`; `input/prepare_run` links the `lab_sea` 1979 forcing and is run by the run script); parse as R5 with experiment name `seaice_obcs` (0.8 s, peak RSS 0.112 GB). Documented (1DMIX-025/-034), not inferred. |
| **P4** | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_seaice_obcs_1dmix034.nc -o KPP_port_validation/outputs_from_python/python_kpp_outputs_seaice_obcs_1dmix034.nc -j 4` (the file `docs/model_contract.md` cites for the salt-plume evidence). |
| **P5** | same as P4 for `lab_sea_6mo` with `--last 99 -j 8` and `-o KPP_port_validation/outputs_from_python/python_kpp_outputs_lab_sea_6mo.nc`: the leading 100 of 4368 timesteps only, matching `_LABSEA_6MO_N` in `tests/test_kpp_mitgcm_validation_extended.py`; no full 4368-step replay exists. |

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_6mo.nc` | R5 | 320939794 | `f42c8cc01ff11d79a1854c5c2ffe8a598b880e47d2d5b38adf715003aa6fa96f` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_6mo.nc` | R5 | 520574716 | `0fe45446097668f5315881608bf662b8b142ae0cfe7e007957324406dfe70c93` |
| `outputs_from_python/python_kpp_outputs_lab_sea_6mo.nc` (first 100 steps) | P5 | 2910396 | `4c87cdab223c9b09761105fc7897092a27605dad98783f681aad4c573d91d154` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_seaice_obcs_1dmix034.nc` | R6 | 261801 | `9fdc8b40ecf63ed05fc92d0970c7ffd572b7d603754749a2bfcf1d6b5a17ea72` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_seaice_obcs_1dmix034.nc` | R6 | 325251 | `0b9bcceead643974959093c2d3efc3927ee0a882c87f2b75e35cf00876942223` |
| `outputs_from_python/python_kpp_outputs_seaice_obcs_1dmix034.nc` | P4 | 109056 | `ffe9d5c8453a5e2dae0cd1d52803420f82a04a36116c44625f2d80a6b8b2311b` |

The regenerated `lab_sea_6mo` files are 321 MB + 521 MB (time chunk 1, i.e.
`(1, 20, 16, 23)`), not the Mac-era single 222 MB file with time chunks of 2184
that the extended test module's comment now records as the original chunking; content and attributes are
otherwise as documented, and the test's `.load()` preload is unchanged. The
`lab_sea_6mo` test group passes (6 tests, 33 s) and every statistic in
`KPP_VALIDATION_RESULTS.md` for `lab_sea_6mo` (first 100 timesteps) and
`seaice_obcs` reproduces to the printed digits (`hbl` N=15,000: median 2.89e-3
m, max 40.72 m, 0.68%/0.47% above 1 m/5 m; mixing and `ghat` rows likewise; and
`seaice_obcs` `hbl` N=295: median 3.46e-2 m, 9.15%/2.71%): evidence in
`devel-loop/loop_state/bob-1DMIX-066-evidence.md` and
`devel-loop/loop_state/bob-1DMIX-066-compare-stats.out`.

### Legacy `mitgcm_kpp_inputs_1D_10.nc`: removed from `esx/project.json:external_inputs`

The original 2026-08-19 capture cannot be faithfully re-made: it predates
the `_kppmix_extend` and `_kppmix_extend_rawflux_fix` re-captures and the
instrumentation fixes that produced them, its would-be paired output was never
kept, and nothing loads it (grep-confirmed 2026-09-30 over `*.py`, `*.sh`,
`*.yaml`, `*.json` and the docs: the only references were its own
`external_inputs` entry and the manifest row below). Rather than fabricate a
file under that name, the entry was removed from `esx/project.json`; the
declared external inputs were then 30 files, all present. 1DMIX-066 added 17 (the 14 MITgcm-side
files of its seven captures plus the three `outputs_from_mitgcm` files of `11k_1D`, `lab_sea_1000_0820T0946` and
`1D_10_kppmix_extend_rawflux_fix` that the tests load but the list omitted): 47 in total, all present, no Python
replay files.

## Print precision and instrumentation fidelity, 1DMIX-069 (2026-09-30)

*(As of 1DMIX-069; all declared KPP captures were recaptured at 17 digits by 1DMIX-070, see "Recaptured at 17 digits, 1DMIX-070" below.)*
Every KPP capture declared in this manifest (and in `esx/project.json:external_inputs`)
was produced with `kpp_calc.F`'s `FORMAT E25.16` (16 significant digits) and stays
valid under that limit; none was replaced by 1DMIX-069. `kpp_mods/kpp_calc.F` now
prints `ES25.16` (17 significant digits); captures regenerated from these mods from
1DMIX-069 on are bit-exact in T, S, u, v and every diagnostic. Check run (kept under
`devel-loop/loop_state/scratch/bob-1DMIX-069/`, not declared): recipe R1 (`1D_10`, 10
steps) rebuilt with the new mods parses cleanly with the unchanged streaming parser
(`parse_mitgcm_split.py`; peak RSS 0.11 GB) and every input (17) and output (12)
variable agrees with the declared `1D_10_kppmix_extend_rawflux_fix` capture to
<= 5.0e-16 relative (the E25.16 print quantisation), i.e. physics unchanged;
`tests/test_kpp_mitgcm_validation.py -k 1d` (2 tests) passes when pointed at the new
files.

Fidelity audit versus stock MITgcm (d861cd501): `kpp_mods/kpp_routines.F` differs
from `pkg/kpp/kpp_routines.F` only by KPPMIX exposing its existing `Rib, bfsfc`
locals as output arguments (plus comments); `kpp_mods/kpp_calc.F` differs from
`pkg/kpp/kpp_calc.F` only by the `kppRib`/`kppBfsfc` declarations, the extra KPPMIX
arguments, the call to `KPP_OUTPUT_VALIDATION` and that write-only subroutine. No
hunk can change computed physics; no KPP source correction was needed. Details:
`devel-loop/loop_state/bob-1DMIX-069-evidence.md` and the GGL90 manifest
(`../GGL90_port_validation/CAPTURES.md`, same-titled section) for the GGL90 file.

## Recaptured at 17 digits, 1DMIX-070 (2026-09-30)

Every KPP capture declared in this manifest and in `esx/project.json:external_inputs` was
recaptured with the current instrumented mods (`kpp_calc.F` prints every captured field and every
`PARAM_*` scalar as `ES25.16`, 17 significant digits, exact for a double) and replaced in place under
the same names; the 16-digit predecessors were kept only under
`devel-loop/loop_state/scratch/bob-1DMIX-070/old16/` for the comparison. Recipes R1-R6 are the
1DMIX-065/066 recipes above, unchanged (**R5 still INFERRED**); MITgcm commit
`d861cd501f21303825de860eb3caa0a8a7ae22f8` (tree unmodified), image `mitgcm:latest` (`6cc66b8957d8`),
Docker, fresh build directories `build_docker_kpp_*_070`, run directories `output_kpp_*_070`. Each
`output.txt` was parsed by the streaming `parse_mitgcm_split.py` in its own process under `RLIMIT_AS`
8 GB: `1D_10` 0.1 s, `11k_1D` 50.5 s (peak RSS 0.144 GB), `lab_sea_1000` 45.6 s (0.152 GB),
`lab_sea_6mo` 201 s (0.168 GB), `seaice_obcs` 0.1 s, `global_oce_latlon_720` 486.8 s (0.151 GB; raw
`output.txt` 13.8 GB, never loaded whole). Parsers unchanged. Python files come only from replaying
the current port (recipes P1-P5, P2b) on the new inputs; no reference was produced by the component it
tests.

**16-digit versus 17-digit (`scratch/bob-1DMIX-070/cmp_kpp_*.out`, every variable and attribute,
streamed).** For all six captures every input and output variable has identical shape, dtype and NaN
pattern and agrees with its 16-digit predecessor to <= 5.9e-16 relative (`11k_1D` 5.89e-16 `dVsq`,
`1D_10` 5.01e-16, `lab_sea_1000` 5.68e-16, `lab_sea_6mo` 5.68e-16, `seaice_obcs` 5.36e-16,
`global_oce_latlon_720` 5.68e-16; 0 elements above 6e-16): print quantization only, MITgcm physics
unchanged. The only attribute differences are the two lookup-table spacings `deltaz`
(4.4893378e-10 -> 4.489337822671156e-10, 5.05e-9 relative) and `deltau` (8.3160083e-05 ->
8.316008316008316e-05, 1.9e-9), which the old `E16.8` PARAM prints truncated to 8 digits; every other
parameter was exactly representable and is identical. Effect on the port comparison
(`stats_kpp_16v17_*.out`: the same current port replayed on both captures, with the exact subsets and
statistics the KPP tests use): **every KPP statistic is identical at both precisions** except two
shifts in `11k_1D` (`visc_az` cells above 1% 0.056% -> 0.055%; `diff_kz_s/t` 0.806% -> 0.796%,
median 2.305e-7 -> 2.303e-7), so the KPP known gaps (Rib/Ricr threshold tail, `wscale` clamp, `ghat`
zero-signature cells) are real and none was a print artifact: `1D_10` `hbl` max 1.289e-2 m,
`11k_1D` `hbl` median 2.85e-5 m / max 20.28 m, `lab_sea_1000` (first 20 steps) `hbl` max 26.4 m,
`lab_sea_6mo` (first 100 steps) `hbl` max 40.72 m and `visc_az` 13.35% above 1%, `seaice_obcs` `hbl`
max 20.4 m, `global_oce_latlon_720` (first 5 steps) `hbl` max 3.09 m. No KPP test assertion needed
changing (all KPP upper bounds unchanged and passing).

Note on documented numbers: the `11k_1D` fractions above (0.055% and 0.796%) are what the current
port measures at both precisions; `KPP_VALIDATION_RESULTS.md` and the `11k` test docstring still quote
0.087% and 1.19%, the 1DMIX-065 measurement taken before 1DMIX-068 changed the shared `jmd95_eos`
operation order. That drift predates and is independent of this recapture (identical at 16 and 17
digits) and was left for a separate documentation update.

Recorded per file (sha256 of the bytes on the WSL checkout after 1DMIX-070; `Digits` = significant
digits of every captured field; raw `output.txt` kept under
`~/Projects/MITgcm/verification/<exp>/output_kpp_*_070/`). The 1DMIX-065/066 "File provenance" tables
above record the superseded 16-digit bytes.

| File | Recipe | Bytes | sha256 | Digits | raw `output.txt` bytes | raw `output.txt` sha256 |
|---|---|---|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | R2 | 23352755 | `334a12ef60124fd9c7feb382733b6eca071429e0a2d82b3e891e9b0a6f569a82` | 17 (ES25.16) | 314645448 | `37beef2b1545aa476b854b9998cb6d919a22201dfe5ea6f1afb81dc9df66cf47` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | R2 | 21557575 | `dd8862754bf1c068421154358a7fdf8d2c7fd8798ca131d7db750ed463ae567f` | 17 (ES25.16) | 314645448 | `37beef2b1545aa476b854b9998cb6d919a22201dfe5ea6f1afb81dc9df66cf47` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 129291 | `92fb04877db2345132a0686fcebffdad62e64f67affdb6ca2dcf5ecf7ac00ef3` | 17 (ES25.16) | 443412 | `a41ff4a87c8a96160177e489a73e5e71987eaf166c560a6cfccc983369ce1050` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | R1 | 104890 | `4cf0f61f7768ea6cb4ffcb93aa6ed375f789253a8a88e159d84910763d53a057` | 17 (ES25.16) | 443412 | `a41ff4a87c8a96160177e489a73e5e71987eaf166c560a6cfccc983369ce1050` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc` | R3 | 73391898 | `6fbee2fd06b7ee82890eed444e3fd15ea5bd4cc788e5d557ac77016eb9a8b72e` | 17 (ES25.16) | 1882448839 | `b79f91b12432ace3c4704b9a9d16abc68a75d525db34d1435c89fd41bf549064` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_1000_0820T0946.nc` | R3 | 124863579 | `c11406138f0709e8188e98f4d81d9ca1e9a26d791841f354132f323315e53111` | 17 (ES25.16) | 1882448839 | `b79f91b12432ace3c4704b9a9d16abc68a75d525db34d1435c89fd41bf549064` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_6mo.nc` | R5 | 320746270 | `becb43a7bcbe8ece06f60a32173a0d9ae99a8eefee331037e86c8a001565ffd7` | 17 (ES25.16) | 8230063810 | `fa874b154a49534c505814d8c946d9276ccce1b27af7bbfcbec4c4f841957d5c` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_6mo.nc` | R5 | 520521369 | `07e93b906d548fb275dafbbb8f5f244cc814b75daa4e7c9aae786cedf7c59463` | 17 (ES25.16) | 8230063810 | `fa874b154a49534c505814d8c946d9276ccce1b27af7bbfcbec4c4f841957d5c` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_seaice_obcs_1dmix034.nc` | R6 | 258244 | `aa08ad9ec3ca76ae57668f70d2b884560670b6e359839b693294870c89a41cd7` | 17 (ES25.16) | 3983594 | `f34c443bb64e46c8f4e3606c68df16195ba9dc8e248654b0c6106656d9d338f0` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_seaice_obcs_1dmix034.nc` | R6 | 325196 | `5798865000291bba567b0095acb83172532d287388ac57304c3b1c09751c06c1` | 17 (ES25.16) | 3983594 | `f34c443bb64e46c8f4e3606c68df16195ba9dc8e248654b0c6106656d9d338f0` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_oce_latlon_720.nc` | R4 | 703126967 | `ceb0cdab68222d75e323c97ee4f05808fa5203d9fba5d3f17721952cbed69a8c` | 17 (ES25.16) | 13823542144 | `d7f7532feaaf8cd8fb52c7265e51fcd45846e677062d5ed559ca10bcffb06a3e` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_oce_latlon_720.nc` | R4 | 1090745317 | `38aee57b1767ef71b8b252b71514d4e6ae1a4bbe9593fe99f9f1dca3cd11c314` | 17 (ES25.16) | 13823542144 | `d7f7532feaaf8cd8fb52c7265e51fcd45846e677062d5ed559ca10bcffb06a3e` |

Replays regenerated on the 17-digit inputs (recipes P1-P5, P2b; `ulimit -v 8000000`):

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | P2 | 1613834 | `3424c32d19bc581836bb5a3e673c8a6ccc61a07107d2f07e756d6e1c92dcd36f` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | P2b | 1613834 | `d82db884b829cfef6a0c936fb37213819b0a578eff9a5fb80052d79be8a309cb` |
| `outputs_from_python/python_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | P1 | 66291 | `b4708d44003f5df9fcc74899db021f6f17346f33d264ffc533d19b62df2b7e65` |
| `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc` | P3 | 27497350 | `db10a5438ad2a53d5c68c07ebd97f64bae2949ee1cd5511e298bde2556cf8561` |
| `outputs_from_python/python_kpp_outputs_lab_sea_6mo.nc` | P5 | 2910360 | `440cc6d6e58f0288899ce30e73ef04f269680fd7decaf053434510fe67d279a1` |
| `outputs_from_python/python_kpp_outputs_seaice_obcs_1dmix034.nc` | P4 | 108951 | `a85c9080222a97032d2b76175e1cc13a6197164cde679d3e8e81d3315c947613` |

Standalone-driver outputs (`outputs_from_python_standalone/<scenario>/kpp_standalone_output.txt`) were
regenerated with the widened `kpp_standalone_main.F` FORMATs from the unchanged
`kpp_standalone_input.txt`; see `CONVENTIONS_STANDALONE_DATA.md` ("Regenerated at 17 digits, 1DMIX-070").

## Cross-scheme captures, 1DMIX-054 (2026-09-30): KPP on the two `global_ocean` grids

Two KPP captures on grids that had only ever been captured with GGL90. **Both use CONSTRUCTED
namelists**: no stock MITgcm experiment has a `data.kpp` (nor a KPP-enabled `data.pkg`) for
`global_ocean.90x40x15` or `global_ocean.cs32x15`; the constructed files, and the justification of
every value that differs from the donor GGL90 input directory, are in
`mitgcm_verification_mods/global_ocean_{90x40x15,cs32x15}/kpp_input_validation/` (READMEs, `data*` files,
run-directory assembly scripts). They are **not** stock MITgcm experiments and must not be described as such;
the MITgcm reference values still come only from a real MITgcm run parsed by the streaming
`parse_mitgcm_split.py`, and the Python files only from replaying the port. Same MITgcm commit
(`d861cd501f21303825de860eb3caa0a8a7ae22f8`, tracked tree unmodified), image (`mitgcm:latest`, `6cc66b8957d8`),
host and date as the 1DMIX-070 set; ES25.16 (17-digit) instrumentation. Compile trees: `global_ocean_90x40x15/
kpp_code_validation/`, `global_ocean_cs32x15/kpp_code_validation/` (differences from the stock `code/`: see
`mitgcm_verification_mods/README.md`, "Cross-scheme trees").

| Id | Steps |
|---|---|
| **R7** `global_ocean_90x40x15_10` (10 steps, 36 tiles, 2,315 wet columns) | `MITGCM_ROOT=~/Projects/MITgcm <mods>/global_ocean_90x40x15/kpp_input_validation/assemble_run_dir.sh` (creates the untracked `verification/global_ocean.90x40x15/input_docker_kpp90`); cwd `~/Projects/MITgcm/verification`: `./experiment_compile.sh global_ocean.90x40x15 -mods <mods>/global_ocean_90x40x15/kpp_code_validation -build build_docker_kpp_054 -clean -j 8` (21 s); `./experiment_run_no_compile.sh global_ocean.90x40x15 input_docker_kpp90 -build build_docker_kpp_054 -output output_kpp_90x40_054` (7.4 s, `output.txt` 192,305,496 bytes, 360 validation blocks = 10 steps x 36 tiles); parse (repo root, `ulimit -v 8000000`): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py <run>/output.txt global_ocean.90x40x15` (5.6 s), then copy `mitgcm_kpp_inputs.nc`/`mitgcm_kpp_outputs.nc` to the names below. **CONSTRUCTED namelist**; header = MITgcm default `KPP_OPTIONS.h` (`smooth_shsq=smooth_dbloc=use_ghat=1`). The first attempt (`ivdc_kappa=1.` as in the GGL90 donor) stopped at `KPP_CHECK` and led to `ivdc_kappa=0.`. Duration 10 steps = the existing GGL90 capture of the same grid. |
| **R8** `global_ocean_cs32x15_pcoords_1` (**1 step**, 12 tiles, 1,621 wet columns, **pressure coordinates**) | `MITGCM_ROOT=~/Projects/MITgcm <mods>/global_ocean_cs32x15/kpp_input_validation/assemble_run_dir.sh` (creates `verification/global_ocean.cs32x15/input.in_p_kpp`, layered on `input/` by the run script); `./experiment_compile.sh global_ocean.cs32x15 -mods <mods>/global_ocean_cs32x15/kpp_code_validation -build build_docker_kpp_054 -clean -j 8`; `./experiment_run_no_compile.sh global_ocean.cs32x15 input.in_p_kpp -build build_docker_kpp_054 -output output_kpp_cs32_054` (1.6 s; **exits 1: MITgcm stops itself** -- `MON_SOLUTION: STOPPING CALCULATION at Iter=1`, `tMin,tMax = -1.117E+13 -8.892E+12`, `STOP ABNORMAL END: S/R MON_SOLUTION`; `output.txt` 13,659,218 bytes, 12 validation blocks = 1 step x 12 tiles); parse as R7 with experiment name `global_ocean.cs32x15`. **CONSTRUCTED namelist.** The 1-step duration is not a choice: MITgcm's own KPP, applied in pressure coordinates with `KPP_GHAT` on (MITgcm default), blows the tracers up at iteration 1 (see below). |
| **P6** / **P7** | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_kpp_from_netcdf_input.py KPP_port_validation/inputs_from_mitgcm/mitgcm_kpp_inputs_<tag>.nc -o KPP_port_validation/outputs_from_python/python_kpp_outputs_<tag>.nc -j 4` for `<tag>` = `global_ocean_90x40x15_10` (P6), `global_ocean_cs32x15_pcoords_1` (P7). Not read by any test (the tests replay in-process). |

Evidence-only reruns (kept under `devel-loop/loop_state/scratch/bob-1DMIX-054/`, **not declared, not tested**): (a)
`global_ocean.90x40x15` with `KPP_SMOOTH_SHSQ`/`KPP_SMOOTH_DBLOC` `#undef`'d (`KPP_OPTIONS.h` = the pkg default with those two
lines flipped; otherwise R7), to isolate the horizontal-smoothing effect on the comparison; (b) `global_ocean.cs32x15` with
`KPP_GHAT` `#undef`'d, which completes 10 steps (120 blocks) and shows the same unit-confused KPP output as R8, proving that
the abort is the application of `ghat` (6.3e10) to the tracers.

**cs32x15 must not be read as validation.** MITgcm's `pkg/kpp` has no pressure-coordinate handling (`coordFac`,
`usingPCoords`: zero occurrences, unlike `pkg/ggl90/ggl90_calc.F`). Measured on R8: MITgcm's own `hbl` is negative in
all 1,621 columns (99.26% exactly the surface layer's Pa value), its interior mixing is the constant Pa-unit background
(`viscAr = 1.0309e5`), `ghat` reaches 6.3e10 and the run aborts. Before 1DMIX-072 the port's interior mixing coefficients were NaN in 91%
of cells and its `hbl` differed by a median 1.2e6, and the only close field, `ghat`, agreed because both sides evaluated the same
formula on the same Pa-as-metres geometry (maximum identical to the last digit, `6.3275154945147095e10`) -- a shared
unit error, not fidelity. Since 1DMIX-072 `KPPDriver.compute_mixing` raises `ValueError` on this geometry
(`main/column_grid.py::validate_zcoordinate_geometry`, shared with GGL90 since 1DMIX-073 and re-exported by `kpp_core_driver.py`; depth is positive Pa, max 4.9e7), so the capture serves as MITgcm-side
evidence only and has no port replay. Details and the tests that encode each fact:
`KPP_VALIDATION_RESULTS.md` ("`global_ocean_cs32x15` + KPP"),
`tests/test_kpp_mitgcm_validation_extended.py::test_global_ocean_cs32x15_*`.

| File | Recipe | Bytes | sha256 | Digits | raw `output.txt` bytes | raw `output.txt` sha256 |
|---|---|---|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_ocean_90x40x15_10.nc` | R7 | 8861852 | `3b806b2d73c22a848afc159498628aa69ccfebf20b23e4db08d2ff8fe37daa07` | 17 (ES25.16) | 192305496 | `29c42fdaa5d2d074b18b2d89d2fdc01e52a335f6039f0215ab5d5360531f50a8` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_ocean_90x40x15_10.nc` | R7 | 14431492 | `0ce4daa6f5e1fc1aeb44b4df7c7102a64174ecd0b35aaac4018848ed2e2f8f0f` | 17 (ES25.16) | 192305496 | `29c42fdaa5d2d074b18b2d89d2fdc01e52a335f6039f0215ab5d5360531f50a8` |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_ocean_cs32x15_pcoords_1.nc` | R8 | 600081 | `188ecac26830b0c6cc4e7f8a4f30367785300975c4f87fc675b0ba6b2ffab51c` | 17 (ES25.16) | 13659218 | `2051902e6a7e4ac3ebf93f25be1876aa1d1b657443a53e57c0e990306a47105a` |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_ocean_cs32x15_pcoords_1.nc` | R8 | 647338 | `c53e174c95c31642bc5194ca44326b77eb18035d956d8c22f416f3b8b0355c7e` | 17 (ES25.16) | 13659218 | `2051902e6a7e4ac3ebf93f25be1876aa1d1b657443a53e57c0e990306a47105a` |
| `outputs_from_python/python_kpp_outputs_global_ocean_90x40x15_10.nc` | P6 | 2175285 | `90ef5ada85f1578befae6cb8ac8e6717b86cd48817e015f65d240e40ca113927` | - | - | - |
| `outputs_from_python/python_kpp_outputs_global_ocean_cs32x15_pcoords_1.nc` | P7 | 211909 | `8dc7fd6a6d4f10feb6108e043f9a21952c54a695966c9aabca6613e51fa4cf61` | - | - | - |

Raw `output.txt` files are kept under `~/Projects/MITgcm/verification/<exp>/output_kpp_*_054/` (untracked, outside the repo).
`esx/project.json:external_inputs` now declares these four MITgcm-side pairs' 4 files (55 entries in total with the GGL90 captures of
1DMIX-054).

## `global_oce_latlon_720` (720 timesteps, 4-tile 2×2 90×40×15, `global_oce_latlon` verification experiment)

Single version — regenerated fresh 2026-09-27 (1DMIX-049) after the original
1DMIX-027 capture was lost in a disk-space rescue; no superseded alternative
exists. Regenerated again on the WSL checkout 2026-09-30 (1DMIX-065, recipe R4
above; same 2,315 wet columns at all 720 timesteps, statistics reproduce the
documented ones to every printed digit).

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_global_oce_latlon_720.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation_extended.py` (`DATA_GLOBAL_OCE_LATLON`), first 5 (of 720) timesteps replayed at full spatial resolution. |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_global_oce_latlon_720.nc` | **current** | Paired MITgcm output, same test. |

No `outputs_from_python/` file exists for this capture (only a bounded
5-timestep subsample was ever replayed through the Python port; a full
720-timestep replay, estimated ~1.5 h, remains a separate, not-yet-scoped
follow-up — see
`MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`'s
`global_oce_latlon` section).

## `1D_10` (10 timesteps, single column, `1D_ocean_ice_column` verification experiment)

UUIDs cross-checked directly (`input_uuid` in each output matches its own input's
`uuid`, 2026-09-27).

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | The capture `tests/test_kpp_mitgcm_validation.py` actually loads (`DATA_1D`). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | Paired MITgcm output for the above, same test. |
| `outputs_from_python/python_kpp_outputs_1D_10_kppmix_extend_rawflux_fix.nc` | **current** | Regenerated 2026-09-27; the file `reports/kpp_validation_1D_ocean_ice_column_10.pdf` was built from (see `MITgcm_to_Python_port_verification/KPP_port_validation/KPP_VALIDATION_RESULTS.md`'s Reproducibility section). |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10_kppmix_extend.nc` | superseded, retained | **Documented-buggy legacy capture** — `scripts/run_kpp_from_netcdf_input.py::derive_raw_flux_forcing`'s own docstring (1DMIX-013) states this capture's `q_net`/`fw_flux` columns are *not* real raw fluxes despite the name (they hold MITgcm's own already-converted `surfaceForcingT`/`surfaceForcingS`, a pre-fix `KPP_OUTPUT_VALIDATION` bug) — feeding them through the raw-flux formula double-applies the conversion. This is why `_rawflux_fix` was captured. No active test/script loads this file's data (the one reference is that explanatory comment, not a load path). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10_kppmix_extend.nc` | superseded, retained | Paired MITgcm output for the legacy capture above. No active reference. |
| `outputs_from_mitgcm_standalone/mitgcm_kpp_outputs_standalone_1D_10.nc` | superseded, retained | Standalone-Fortran-driver output (three-way method step 2) paired (by `input_uuid`) to the *legacy* `_kppmix_extend.nc` capture, not the current `_rawflux_fix` one — from the KPP standalone driver's original bring-up test (README's own status table, "`1D_ocean_ice_column` \| KPP standalone (step 2)" row, 1DMIX-012, resolved: exact match to floating-point roundoff). Not re-run against the corrected capture since 1DMIX-012 closed; no active script/test references this file by name. The raw-flux bug above affects `q_net`/`fw_flux` specifically, which the standalone driver never consumes (it calls `KPPMIX` directly with `ustar`/`bo`/`bosol`), so this historical result is not itself invalidated by that bug — it simply predates the fix and has not been re-verified against it. |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_1D_10.nc` | **removed** (1DMIX-065, 2026-09-30) | Original 2026-08-19 capture, predates both later re-captures. No active reference; no paired output file exists for it (its would-be `outputs_from_mitgcm/mitgcm_kpp_outputs_1D_10.nc` was never kept). Not present on the WSL checkout and cannot be faithfully re-made; its entry was removed from `esx/project.json:external_inputs` instead of fabricating a file under this name (rationale in "Regenerated on WSL, 1DMIX-065" above). |
| `outputs_from_python/python_kpp_outputs_1D_10_precomputed_forcing.nc` | superseded, retained (orphaned) | A 2026-09-16 Python-port output for a *different*, one-off experiment (`input_file_name` attribute reads `mitgcm_kpp_inputs_precomputed_forcing_only.nc`, not any file above) whose own input capture is no longer present in this repo. Not part of the `1D_10` version family despite the shared filename prefix; not referenced by any active script/test. Kept rather than deleted only because its originating input can no longer be inspected to confirm it is safe to discard. |

## `11k_1D` (11,000 timesteps, single sea-ice-coupled column, `1D_ocean_ice_column`)

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation_extended.py` (`DATA_11K`) and by `KPP_port_validation/scripts/compute_validation_statistics.py` (as `mitgcm_file`'s sibling). Single version — no superseded alternative exists. |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_11k_1D.nc` | **current** | Paired MITgcm output, same test; also loaded directly by `compute_validation_statistics.py`. |
| `outputs_from_python/python_kpp_outputs_11k_1D.nc` | **current** | The standard-convention Python output the active test suite actually asserts against; source of `reports/kpp_validation_1D_ocean_ice_column_11000.pdf`. |
| `inputs_from_mitgcm/mitgcm_kpp_inputs_11k_1D_python.nc` | **anomalous — retained, not "current"** (1DMIX-046 task 5) | **Investigated.** Despite its name and location (inside `inputs_from_mitgcm/`, not `outputs_from_python/`), this file's own embedded NetCDF metadata is unambiguous: `title="Python KPP Port Outputs"`, `source="Python KPP port"`, `description="KPP outputs from Python port using MITgcm inputs"` — it **is** a Python-port output, not an MITgcm input, mislocated by an earlier (2026-08-20) version of the pipeline that saved a `<input_basename>_python.nc` file alongside its input by default, before the current `outputs_from_python/python_kpp_outputs_<tag>.nc` convention existed (see `NETCDF_DATA_FORMAT.md`'s own now-corrected step-4 walkthrough, which still documents this exact historical behavior). It shares the real capture's `uuid` (provenance-verified). **Not deleted**: `KPP_port_validation/scripts/compute_validation_statistics.py` still opens this exact file by name as its `python_file`. It is listed in `esx/project.json:external_inputs` (mislabeled there as an "MITgcm-derived" input, which it is not — left as-is rather than edited further, since removing the file itself would require a coupled `project.json` edit, and this file, unlike the `lab_sea` one below, is not safe to delete). **Regenerated 1DMIX-065 (2026-09-30)**: produced by replaying the port on the regenerated 11k capture (recipe P2b above, sha256 in the provenance table), with the current `run_kpp_from_netcdf_input.py` CLI; it therefore shares the regenerated capture's `uuid` and is content-equivalent to `outputs_from_python/python_kpp_outputs_11k_1D.nc`. |

## `lab_sea_1000_0820T0946` (999-timestep, 20×16-grid `lab_sea` run — the "41-day" capture)

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946.nc` | **current** | Loaded by `tests/test_kpp_mitgcm_validation.py`. Single version now (see below). |
| `outputs_from_mitgcm/mitgcm_kpp_outputs_lab_sea_1000_0820T0946.nc` | **current** | Paired MITgcm output, same test. |
| `outputs_from_python/python_kpp_outputs_lab_sea_1000_0820T0946.nc` | **current** | Standard-convention Python output the test asserts against; source of `reports/kpp_validation_lab_sea_999.pdf`. |
| ~~`inputs_from_mitgcm/mitgcm_kpp_inputs_lab_sea_1000_0820T0946_python.nc`~~ | **deleted, 1DMIX-046 task 5** | Investigated and confirmed safe to delete (not merely "retained-with-uncertainty"): same "Python-port-output-mislocated-as-input" pattern as the `11k_1D` anomaly above (identical `title`/`source`/`description` metadata), but **also confirmed incomplete** — only 1 of the real capture's 999 timesteps (`dims: time=1` vs. the real input's `time=999`), i.e. an abandoned partial snapshot, not even a full early replay. Zero references anywhere in `{scripts,tests}` (grep-confirmed). It **was** listed in `esx/project.json:external_inputs`; that entry was removed in the same patch so the environment probe's required-file hash check (`tools/esx/project.py::environment`) does not fail on the now-deleted file. Not git-tracked (gitignored `*.nc`), so no history is lost by deleting outright either way. |

## Standalone-driver outputs and `outputs_from_python` general note

`outputs_from_mitgcm_standalone/` and the `1D_10`-family standalone file above are
the only KPP standalone-Fortran-driver (three-way method step 2) captures kept
under real MITgcm data; the 6 idealized-scenario standalone-driver runs
(1DMIX-023/-041/-048) instead write to `Vertical_Mixing_Models/output/<scenario>/`
and are out of this manifest's scope (no real-MITgcm capture involved there).
Their durable copies (`{inputs,outputs}_from_python_standalone/`) were
regenerated on the WSL checkout under 1DMIX-065; the per-file recipe, MITgcm
commit and sha256 are in `CONVENTIONS_STANDALONE_DATA.md` ("Regenerated on
WSL, 1DMIX-065").
