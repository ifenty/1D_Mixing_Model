# Capture manifest — GGL90_port_validation

Written under 1DMIX-046 to resolve "which versioned file is current" for every
experiment that has more than one capture on disk. Only `vermix` has multiple
versions here; every other experiment (`1D_ocean_ice_column`,
`global_ocean_90x40x15_idemix_10`, `global_ocean_cs32x15_idemix_10`, `isomip_12`)
has exactly one input/output/python-output triple and needs no entry.

## Regenerated on WSL, 1DMIX-066 (2026-09-30)

The repo moved to a fresh WSL checkout on 2026-09-29 and every gitignored `*.nc`
capture was absent, so `tests/test_ggl90_mitgcm_validation.py` skipped in full.
1DMIX-066 regenerated the five GGL90 captures it loads from scratch with this
repo's instrumented `mitgcm_verification_mods/*/code_validation` (and, for
`1D_ocean_ice_column`, `ggl90_code_validation`) trees, using the same Docker
workflow, image (`mitgcm:latest`, id `6cc66b8957d8`) and MITgcm commit
(`d861cd501f21303825de860eb3caa0a8a7ae22f8`, `~/Projects/MITgcm`, tracked tree
unmodified) as the KPP set (`../KPP_port_validation/CAPTURES.md`, "Regenerated
on WSL, 1DMIX-065"). Runs and replays: 2026-09-30. Provenance rules: every
`mitgcm_ggl90_*` file comes only from an MITgcm run parsed by the streaming
`scripts/parse_mitgcm_ggl90_split.py::parse_mitgcm_ggl90_split_to_files`; every
`python_ggl90_*` file comes only from replaying the port
(`scripts/run_ggl90_from_netcdf_input.py`) on the paired regenerated input; no
reference was produced by the component it tests. The files carry fresh run
UUIDs and an unlimited `time` dimension. Recipe status is stated per row:
**documented** = recorded in this repo before 1DMIX-066; **INFERRED** =
reconstructed here from repo evidence only.

### Recipes (cwd `~/Projects/MITgcm/verification`; `<mods>` = `<repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods`)

| Id | Status | Steps |
|---|---|---|
| **G1** `vermix_20_1dmix024` (20 steps, 1x26) | documented (`NETCDF_DATA_FORMAT.md`) | `./experiment_compile.sh vermix -mods <mods>/vermix/code_validation -build build_docker_ggl90_1dmix024 -j 8`; `mkdir vermix/input_ggl90_merged; cp vermix/input/* ...; cp vermix/input.ggl90/* ...` (`data`: `nTimeSteps=20`, `deltaT=1200`); `./experiment_run_no_compile.sh vermix input_ggl90_merged -build build_docker_ggl90_1dmix024 -output output_ggl90_1dmix066`; parse (repo root, `ulimit -v 8000000`): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py <run>/output.txt vermix`, then copy the resulting `mitgcm_ggl90_inputs.nc`/`mitgcm_ggl90_outputs.nc` to the documented names (peak RSS 0.109 GB). |
| **G2** `isomip_12` (12 steps, 8 tiles, 50x100x30, `ALLOW_SHELFICE`) | documented (closed 1DMIX-025) | `./experiment_compile.sh isomip -mods <mods>/isomip/code_validation -build build_docker_ggl90_isomip -clean -j 8`; `./experiment_run_no_compile.sh isomip input.obcs -build build_docker_ggl90_isomip -output output_ggl90_isomip_1dmix066` (26 s, `output.txt` 950,888,231 bytes); parse as G1 with experiment name `isomip` (20 s, peak RSS 0.162 GB). The Mac-era note that `bathy.box` had to be copied into the run directory is obsolete: the current run script layers `input.<X>` on `input/`. |
| **G3** `global_ocean_90x40x15_idemix_10` (10 steps, 36 tiles, 90x40x15, IDEMIX) | documented (`mitgcm_verification_mods/global_ocean_90x40x15/README.md`, with one correction: its symlink list omits `data.diagnostics`, without which the run stops at `DIAGNOSTICS_READPARMS`) | `./experiment_compile.sh global_ocean.90x40x15 -mods <mods>/global_ocean_90x40x15/code_validation -build build_docker_ggl90_idemix90 -clean -j 8`; run directory `global_ocean.90x40x15/input_docker_idemix90` built as that README describes (symlinks of `input.idemix`'s files including `data.diagnostics`, the 8 forcing binaries from `tutorial_global_oce_latlon/input`, and a real copy of `input.idemix/data` with `useSingleCpuIO=.TRUE.,` added inside `&PARM01`); `./experiment_run_no_compile.sh global_ocean.90x40x15 input_docker_idemix90 -build build_docker_ggl90_idemix90 -output output_ggl90_idemix90_1dmix066` (7 s, `output.txt` 190,466,515 bytes, 347,250 `OUTPUT_IDEMIX` lines); parse as G1 with experiment name `global_ocean.90x40x15` (5 s, peak RSS 0.128 GB). |
| **G4** `global_ocean_cs32x15_idemix_10` (10 steps, 12 tiles, `x=384,y=16,z=15` as captured, pressure coordinates) | documented (`mitgcm_verification_mods/global_ocean_cs32x15/README.md`; its manual `prepare_run`/symlink steps are no longer needed) | `./experiment_compile.sh global_ocean.cs32x15 -mods <mods>/global_ocean_cs32x15/code_validation -build build_docker_ggl90_idemixcs32 -clean -j 8`; `./experiment_run_no_compile.sh global_ocean.cs32x15 input.in_p -build build_docker_ggl90_idemixcs32 -output output_ggl90_idemixcs32_1dmix066` (12 s, `output.txt` 363,441,346 bytes, 663,000 `OUTPUT_IDEMIX` lines, 120 blocks); the current run script layers `input.in_p` on `input/` (which supplies `eedata`, `regMask_lat24.bin`, the `lev_surf*` and `trenberth_tau*` files) and runs `input.in_p/prepare_run` in the run directory, so no file inside the MITgcm checkout is created or edited; parse as G1 with experiment name `global_ocean.cs32x15` (9.5 s, peak RSS 0.142 GB). |
| **G5** `1D_ocean_ice_column_11000` (11,000 steps, 1x23) | mods tree documented; **run-time namelists INFERRED** | `./experiment_compile.sh 1D_ocean_ice_column -mods <mods>/1D_ocean_ice_column/ggl90_code_validation -build build_docker_ggl90_1d -clean -j 8`; input dir `input_validation_ggl90_11k_vx` = `cp -r input ...` with (a) `data`: the `nTimeSteps= 10` / `# nTimeSteps= 11000` swap (same single edit as KPP recipe R2), (b) `data.pkg`: `useKPP=.FALSE.,` and `useGGL90=.TRUE.,` (KPP is compiled in but disabled at run time, per that mods tree's `packages.conf`), (c) a new `data.ggl90` that is a verbatim copy of MITgcm's `verification/vermix/input.ggl90/data.ggl90` (`GGL90writeState=.TRUE.`, `GGL90TKEmin=1.E-7`, `mxlMaxFlag=3`, `GGL90mixingLengthMin=3.`); `./experiment_run_no_compile.sh 1D_ocean_ice_column input_validation_ggl90_11k_vx -build build_docker_ggl90_1d -output output_ggl90_11k_vx_1dmix066` (20 s, `output.txt` 315,048,431 bytes, 11,000 blocks, 253,000 wet column-timesteps); parse as G1 with experiment name `1D_ocean_ice_column` (36.8 s, peak RSS 0.140 GB). |
| **P** replays | — | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_ggl90_from_netcdf_input.py GGL90_port_validation/inputs_from_mitgcm/mitgcm_ggl90_inputs_<tag>.nc -o GGL90_port_validation/outputs_from_python/python_ggl90_outputs_<tag>.nc` (`ulimit -v 8000000`; peak RSS at most 0.31 GB) for each of the five tags **except `global_ocean_cs32x15_idemix_10`: since 1DMIX-073 `GGL90Driver.compute_mixing` rejects that pressure-coordinate geometry with a `ValueError`, so this replay now fails by design** (its last port-side numbers are historical, see below). |

**Why G5's namelist is inferred and how it was chosen.** No file in the repo
records how the Mac-era `1D_ocean_ice_column_11000` GGL90 run enabled GGL90 in an
experiment whose stock `input/` is KPP-only. The tests and the results document
state `mxlMaxFlag=3` for it, which is not MITgcm's default (0). `vermix`'s `data.ggl90` is the
only plausible candidate for a 1-D column that sets it: the one other namelist in the MITgcm
verification tree that does, `global_oce_latlon/input_ad.ggl90/data.ggl90`, also sets
`GGL90alpha=30.`, `GGL90TKEbottom`, `mxlSurfFlag` and `useLANGMUIR`, which is implausible for a 1-D column.
A first attempt (A) used a minimal `data.ggl90` containing only `mxlMaxFlag=3`
(everything else at the MITgcm defaults: `GGL90TKEmin=1e-11`,
`GGL90mixingLengthMin=1e-8`). Its capture regenerated cleanly but the comparison
failed 2 of the 4 `1D_ocean_ice_column` tests (19 `diff_kz` cells above 1% relative
error; `mixing_length` max abs 0.194 m against the 1e-3 bound). Diagnosis: with
TKE pinned at the 1e-11 floor and shear about 1e-100, the Prandtl number is set by
`Ri = N^2/(shear^2 + GGL90eps)` with `GGL90eps = 2.23e-16`; at the bottom
face `N^2` is about 1e-17 s^-2 (near-neutral), and the port's and MITgcm's `N^2`
there differ by 3.2e-17 s^-2, about one ulp of the ~1028 kg/m3 density, enough to
move `Ri` across the 0.2 threshold and the mixing length by 0.3%. That is the
documented EOS-precision amplification near neutral stratification (see
`GGL90_VALIDATION_RESULTS.md`), not a formula or harness defect; nothing in the
port, the tests or any tolerance was changed. Attempt B (the vermix namelist,
G5 above) passes all 4 tests and reproduces the documented figures (`visc_az`
max abs 1.76e-9, `diff_kz` 1.76e-10, `mixing_length` 5.57e-5, `tke_after`
6.6e-15; 0 cells above 1%). Recipe B was chosen after A failed, on the repo
evidence above, so the row stays **INFERRED**; the reproduction of four
independent Mac-era maxima is the strongest available check, not proof of the
original namelist. Further evidence for the choice (1DMIX-066 review, Richard's own
recomputation of every statistic on the tracked Mac-era report
`reports/ggl90_validation_1D_ocean_ice_column_11000.pdf`'s statistics pages): recipe B reproduces that
report to the last printed digit, including roundoff-level P95/median values such as `visc_az` P95 6.9389e-18;
attempt A does not (`visc_az` max 6.13e-8 against 1.76e-9). The `vermix`, `isomip`, `global_ocean.90x40x15` and
`global_ocean.cs32x15` captures likewise match their tracked report PDFs. The namelist itself is still not
recorded anywhere. Both attempts and the probes are in
`devel-loop/loop_state/bob-1DMIX-066-evidence.md`.

### File provenance (sha256 of the bytes on the WSL checkout)

*Superseded by 1DMIX-070 ("Recaptured at 17 digits, 1DMIX-070" below): the bytes and hashes in this
table are the 16-digit captures of 1DMIX-066; the current files replaced them in place.*

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix024.nc` | G1 | 79949 | `579526a73faddf26672650a49a5ba31b1ac28d5ebb4bb035694c2d82be04c5c0` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20_1dmix024.nc` | G1 | 69166 | `82f591af65d3862848e53d5f5c481c8992b02d5388a6e848b40fc51ef67a90ff` |
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix024.nc` | G1+P | 32057 | `82f1b08a62e3c24315124dfc72b4bf02fff084997c7b82b7e47deff15d9781f9` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_isomip_12.nc` | G2 | 21919890 | `911087203da6e393f5d688aa83e8b9017dd8a89da813987dc1b702ba907d09f0` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_isomip_12.nc` | G2 | 20118649 | `f9f1ef41742cb3c2a442a091ea520b8b820860b7d358da4fa185f365a0784c58` |
| `outputs_from_python/python_ggl90_outputs_isomip_12.nc` | G2+P | 57616601 | `1b0c6aa5be8c2cf9bb4b9efbfb5fb6f927da48fcf08048117a6bc083e70240f7` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_global_ocean_90x40x15_idemix_10.nc` | G3 | 12758697 | `09de8661e5d01b59ad3f92cdb995087d0da4e627ebd97b75c4824c5404573171` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_global_ocean_90x40x15_idemix_10.nc` | G3 | 16555774 | `eac0a82f38af07e7a7534fa9d105cf751a980d68659a2f14b32915d911a161e0` |
| `outputs_from_python/python_ggl90_outputs_global_ocean_90x40x15_idemix_10.nc` | G3+P | 17296185 | `58ace7f21a886cf6e545cdfe8ec7b57b4c8d5c0c8abd3047ed78fa164635290d` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_global_ocean_cs32x15_idemix_10.nc` | G4 | 23864246 | `221851597e6cd1c6d29263cc5cb8d75af31545a5306518bf9f02393516dc1f8f` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` | G4 | 30403765 | `2ddd3073f884a416f2c40014036f005601a895e5df85242b9668f3d41ec5df12` |
| `outputs_from_python/python_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` | G4+P (**HISTORICAL**: pre-1DMIX-073 port replay; `run` now raises on this capture, so the file cannot be regenerated) | 29509545 | `fdfabba900879e64015db95624553ea0898754309ead11473fdd0aa1b91610cd` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 17967456 | `04deb3715d8e2e253d89d77a5375b75c98991a7042fe8241a5d9a6dd1b8666f8` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 15698049 | `374e0ff7debba7554913cffff04fe5a41e41f7ba6d9f87588e33b5e19865d880` |
| `outputs_from_python/python_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5+P | 8199209 | `a195f70524fd46e741e1c637f0bc658306f68b8544f437ee2867a44d7130acc3` |

Every statistic in `GGL90_VALIDATION_RESULTS.md` for these five captures
reproduces to the printed digits from the regenerated files (`vermix` N=520
table; `isomip` N=1,437,204; `global_ocean.90x40x15` N=485,840;
`global_ocean.cs32x15` N=813,820 non-NaN cells, of which 555,220 ocean cells (port side now historical, 1DMIX-073); `1D_ocean_ice_column` N=253,000 absolute
maxima) — see `devel-loop/loop_state/bob-1DMIX-066-compare-stats.out`. One
pre-existing unit slip surfaced and was corrected in `GGL90_VALIDATION_RESULTS.md`: the
`1D_ocean_ice_column` table's relative maxima had been labelled `7.9e-7%` and `5.1e-9%` but are fractions
(7.936e-07, 5.139e-09), i.e. 7.9e-5% and 5.1e-7%.

**Streaming parser on real multi-tile GGL90 inputs.** These are the first real
multi-tile GGL90 captures the streaming parser has processed (1DMIX-065 proved
GGL90 identity only on single-tile `vermix`). Old parser = the pre-1DMIX-065
`parse_mitgcm_ggl90_split.py` (git `6bc1da5^`); each parser ran in its own
process under `RLIMIT_AS` 8 GB and every variable, dimension, attribute, dtype
and value was compared byte for byte (only `uuid`, `creation_date`,
`output_file_path`, `input_uuid` excluded; `time` is unlimited only in the new
files). `global_ocean.90x40x15` (36 tiles, full capture): old peak RSS 1.05 GB,
new 0.13 GB, **identical**. `global_ocean.cs32x15` (12 tiles, full capture): old
2.00 GB, new 0.14 GB, **identical**. `isomip` (8 tiles): the old parser
failed under the 8 GB bound on the full 951 MB `output.txt` (`MemoryError` at
4.4 GB RSS), so the proof used its first 2 timesteps x 8 tiles (preamble plus 16
blocks, 159 MB): old 0.89 GB, new 0.14 GB, **identical**; the new parser handles
the full file at 0.16 GB.

## Print precision and instrumentation fidelity, 1DMIX-069 (2026-09-30)

**Which captures are 16-digit and which are 17-digit.** *(As of 1DMIX-069; all
declared captures were recaptured at 17 digits by 1DMIX-070, see the next section.)*
Every capture declared
above (all five GGL90 sets, and every KPP capture in
`../KPP_port_validation/CAPTURES.md`) was produced with the instrumented
`FORMAT E25.16` (16 significant digits) and remains valid under that limit; none
was replaced by 1DMIX-069. The instrumented files now print `ES25.16` (17
significant digits, exact for a double); any capture regenerated from these mods
from 1DMIX-069 on carries bit-exact MITgcm T, S, sigma_r etc. The 17-digit
verification runs of 1DMIX-069 (vermix 20 steps, KPP `1D_10`, the 1DMIX-066
attempt-A `1D_ocean_ice_column` 11,000 steps, `isomip_12`) were kept only under
`devel-loop/loop_state/scratch/bob-1DMIX-069/`, not declared. The streaming parsers
needed no change: `capture_stream.ffloat` already reads the E-less 3-digit exponent
(`5.64e-106` prints as `5.6403554411026415-106`), which occurs in the 11,000-step
capture (273 lines).

**What the 17-digit format shows.** Re-running the 1DMIX-066 attempt-A
configuration (`1D_ocean_ice_column`, minimal `data.ggl90` with only
`mxlMaxFlag=3`, 11,000 steps, 253,000 wet cells) with the widened format and the
1DMIX-068 MITgcm-order N² in the port, and no tolerance changed, passes all four
`test_1d_ocean_ice_column_clean` bounds: `visc_az` max abs 2.1e-17, `diff_kz`
1.2e-17 (0 cells above 1% relative; 19 at 16 digits), `mixing_length` 2.2e-13
(1.9e-1 at 16 digits), `tke_after` 5.4e-20. So the attempt-A residual was print
quantisation, not a port, EOS or harness defect. (The declared
`1D_ocean_ice_column_11000` capture stays the vermix-namelist attempt B of
1DMIX-066, unchanged.) For `isomip_12` the widened capture gives identical physics
fields (all variables within 5.9e-16 relative of the declared capture, i.e. print
quantisation only), confirming the SHELFICE loop-bound fix is a no-op on square
tiles. Its port replay changes only the ulp-scale rows: `mixing_length` max abs
3.25e-4 -> 1.07e-13 and `visc_az` 1.1e-10 -> 9.5e-18 (the 1DMIX-038 kSrf `diff_kz`
(1075 vs 1102 cells above 1%) and `tke_after` (17934 cells, 9.08e-6) gaps are
unchanged, so they are not print artifacts). Consequently
`test_isomip_mixing_length_ksrf_plus_1`, which asserts `1e-4 < max_abs < 0.01`,
would fail on a 17-digit isomip capture; it passes on the declared capture, and its
bound was left untouched (follow-up when the declared isomip capture is recaptured).

**Fidelity audit against stock MITgcm (d861cd501).** Only three distinct
instrumented Fortran files exist: `mitgcm_verification_mods/ggl90_mods/ggl90_calc.F`,
`kpp_mods/kpp_calc.F` and `kpp_mods/kpp_routines.F` (all per-experiment
`code_validation/*.F` entries are symlinks to them, except
`1D_ocean_ice_column/code_validation/kpp_routines.F`, a byte-identical copy).
Every hunk versus stock is output-only (capture buffers, the
`*_OUTPUT_VALIDATION` subroutines and their calls, KPPMIX's `Rib, bfsfc` exposed
as output arguments) except one: the `ggl90_calc.F` SHELFICE u* block looped
`DO i=jMin,jMax` where stock has `DO i=iMin,iMax` (a transcription defect;
**fixed**, it affected only SHELFICE runs with non-square tiles or halos,
sNx != sNy or OLx != OLy; all current captures use 25x25 tiles or have no
SHELFICE). Until 1DMIX-069 the file also had the Langmuir u*/v* arrays as per-point
scalars (arithmetically identical); they are now restored to stock's 2-D arrays so
that the file now differs from stock only by output instrumentation. No declared
capture ran with `useLANGMUIR` on (`data.ggl90` of every declared run has no
`useLANGMUIR`; stock default `.FALSE.`). The headers copied into the mods
directories have no `#define/#undef` differences from the stock experiment's own
`code/` copies wherever one exists. Full hunk table:
`devel-loop/loop_state/bob-1DMIX-069-evidence.md`.

## Recaptured at 17 digits, 1DMIX-070 (2026-09-30)

Every capture declared in this manifest and in `esx/project.json:external_inputs` was
recaptured with the current instrumented mods (which print every captured field **and every
`PARAM_*` scalar** as `ES25.16`, 17 significant digits, exact for a double) and replaced in
place under the same names; the previous 16-digit files were kept only under
`devel-loop/loop_state/scratch/bob-1DMIX-070/old16/` for the comparison. Same recipes G1-G5
(the 1DMIX-066 recipes above, unchanged, **G5 still INFERRED**), same MITgcm commit
`d861cd501f21303825de860eb3caa0a8a7ae22f8` (tree unmodified), same image (`mitgcm:latest`, id
`6cc66b8957d8`), Docker, fresh build directories `build_docker_ggl90_*_070`, run directories
`output_ggl90_*_070`; each `output.txt` was parsed by the streaming
`parse_mitgcm_ggl90_split.py` in its own process under `RLIMIT_AS` 8 GB (peak RSS 0.108-0.163 GB;
isomip 21.5 s, 90x40x15 5.0 s, cs32x15 9.5 s, 1D 11,000-step 33.4 s, vermix 0.1 s). The parsers
needed no change (they read `ES25.16` and the E-less 3-digit-exponent form unchanged). Provenance
rules as before: MITgcm files come only from an MITgcm run, the `python_ggl90_*` files only from
replaying the current port on the paired new input (`scripts/run_ggl90_from_netcdf_input.py`,
`ulimit -v 8000000`); no reference was produced by the component it tests. All files are
17-digit; none is 16-digit any more. The 1DMIX-066 "File provenance" table above records the
superseded 16-digit bytes.

**16-digit versus 17-digit, per capture (`scratch/bob-1DMIX-070/cmp_ggl90_*.out`, streaming
comparison of every variable and attribute).** For all five captures every input and output
variable has identical shape, dtype and NaN pattern, and agrees with its 16-digit predecessor to
<= 5.9e-16 relative (isomip 5.90e-16 `vertical_shear`; 90x40x15 5.80e-16; cs32x15 5.71e-16; 1D
5.87e-16; vermix 5.33e-16), i.e. print quantization of E25.16 only (0 elements above 6e-16, no
finding). The 15 GGL90 parameter attributes are identical (they were exactly representable in
8 digits). MITgcm physics is therefore unchanged. Effect on the port comparison
(`stats_ggl90_16v17.out`: the same current port replayed on both captures, same replay entry
point and the same statistics the tests assert):

| Capture / field | 16-digit max_abs (n>1%) | 17-digit max_abs (n>1%) | Reading |
|---|---|---|---|
| `vermix` all four fields | 1.32e-5 / 1.32e-5 / 7.76e-3 / 7.84e-7 (0) | identical | real 1e-3-relative residual, not print |
| `1D_ocean_ice_column` `visc_az`/`diff_kz`/`mixing_length`/`tke_after` | 8.3e-10 / 8.3e-11 / 2.6e-5 / 2.9e-15 (0) | 3.3e-17 / 1.2e-17 / 2.6e-13 / 5.4e-20 (0) | print quantization -> roundoff |
| `isomip` `visc_az` | 1.13e-10 (0) | 9.5e-18 (0) | print quantization -> roundoff |
| `isomip` `mixing_length` | 3.25e-4 (0) | 1.07e-13 (0) | print quantization -> roundoff; the 1DMIX-038 "kSrf+1" residual |
| `isomip` `diff_kz` | 2.905e-3 (1102) | 2.905e-3 (1075) | real kSrf gap; 27 cells (rel 1.7%-51% at 16 digits, <= 0.26% at 17) were artifacts |
| `isomip` `tke_after` | 9.081e-6 (17934) | 9.081e-6 (17934) | real, identical |
| `global_ocean_90x40x15` (`visc_az`, `diff_kz`, `mixing_length`, `tke_after`) | 5.59 (183) / 2.75 (247456) / 15.5 (206) / 446 (264515) | identical | real (IDEMIX and a small tail) |
| `global_ocean_cs32x15` (same order) | 100 (508739) / 2.01e9 (510536) / 1.45e7 (510393) / 4.20e5 (527111) | identical | **HISTORICAL port-side numbers** (pressure coordinates: since 1DMIX-073 the port raises `ValueError` on this capture, so these cannot be reproduced; re-measured on the pre-change code 2026-10-02 they are unchanged: 100 / 2.0149e9 / 1.4492e7 / 4.1995e5 max abs, 62.5-64.8% of 813,820 cells >1%) |

Consequently only one test assertion was print-quantization-derived
(`test_isomip_mixing_length_ksrf_plus_1`, lower bound `1e-4 < max_abs` with an upper bound of 0.01);
it now asserts `max_abs < 1e-11` (roundoff level; 1.07e-13 measured), and its docstring, the
other isomip/1D docstring figures and `GGL90_VALIDATION_RESULTS.md` were updated to say so (upper
bounds elsewhere are unchanged; none was widened). At 17 digits `isomip`'s `tke_after` residuals sit
at first-wet level +1 (9542 cells above 1%), +2 (6581) and deeper (1811, the y=50 row) while
`mixing_length` agrees to 1e-13 at those levels, so they are not a `mixing_length` effect; their
mechanism beyond the 1DMIX-038/048 record was not re-traced (`scratch/.../isomip_levels.out`).

The 1DMIX-069 paragraph above that says the declared isomip bound "was left untouched (follow-up
when the declared isomip capture is recaptured)" is resolved by this section.

Recorded per file (sha256 of the bytes on the WSL checkout after 1DMIX-070; `Digits` = significant
digits of every captured field; raw `output.txt` = the run's STDOUT it was parsed from, kept under
`~/Projects/MITgcm/verification/<exp>/output_*_070/`):

| File | Recipe | Bytes | sha256 | Digits | raw `output.txt` bytes | raw `output.txt` sha256 |
|---|---|---|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix024.nc` | G1 | 78881 | `10bb1ba55ced3e2890d940094b2352eddbf75e4623fce28a086258744b4e1745` | 17 (ES25.16) | 555367 | `9b440f06d96d4c115cd56b29a29bf4c005713c7234ce2967f8f6ba4f582c5a55` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20_1dmix024.nc` | G1 | 69164 | `244912ce5d10f264de4c5b36c053ff4bfa76ecc1dff05ba3b20eb4572a56d885` | 17 (ES25.16) | 555367 | `9b440f06d96d4c115cd56b29a29bf4c005713c7234ce2967f8f6ba4f582c5a55` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_isomip_12.nc` | G2 | 21731913 | `c0c136a472f06c4998da301d9a4ff20d1d3ab1b38828be3be5acd57a7698e665` | 17 (ES25.16) | 950888376 | `d1b18ea6ed1cf3ff3060f34ebf309e7c8def0d039e673ba24b685a5e3c7355b1` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_isomip_12.nc` | G2 | 20118698 | `203b4ecac51da52731f0e110b9db445a31af65ed73ea8bca36594d28ba5b5ebd` | 17 (ES25.16) | 950888376 | `d1b18ea6ed1cf3ff3060f34ebf309e7c8def0d039e673ba24b685a5e3c7355b1` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_global_ocean_90x40x15_idemix_10.nc` | G3 | 12694959 | `d996958b6cf7d99a2debde4648eef585c36bf7d5ec9045c76dedd41cd4fd90e7` | 17 (ES25.16) | 190466650 | `6bee8ddf1925c2198541a81fd9f400a7933022553abcece838d968d5267cf273` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_global_ocean_90x40x15_idemix_10.nc` | G3 | 16555011 | `b7891b9ce640ff62ff67c53a26bf752e24d2493064a785015462f1bc96104072` | 17 (ES25.16) | 190466650 | `6bee8ddf1925c2198541a81fd9f400a7933022553abcece838d968d5267cf273` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_global_ocean_cs32x15_idemix_10.nc` | G4 | 23813780 | `47c124a8e60da8c2d5abe18cff16bd6271fb260b38e8a51bc7df30efe7d4e102` | 17 (ES25.16) | 363441486 | `be6d863802625ddc2cdc5b9d6a020ed0df6b7a5dc6096e728e7bb03551cfda69` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` | G4 | 30403458 | `3207434355812e853dc0cd633281ebdb1e3ec5e818fc3175ca83b77458444294` | 17 (ES25.16) | 363441486 | `be6d863802625ddc2cdc5b9d6a020ed0df6b7a5dc6096e728e7bb03551cfda69` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 17966603 | `caeb1bd3e51cb220085ac28f3d7bcf617f0c2899f1ffce03df67e6a7e01141e9` | 17 (ES25.16) | 315048571 | `5ff0828cc9ff44cc774d6de87ab1c2e713236a91b2c7ec325792de0180b2945c` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 15698062 | `26b6a0c4dd0487589658a76053d49de293860f02fef8d1423f968d794ba3faa6` | 17 (ES25.16) | 315048571 | `5ff0828cc9ff44cc774d6de87ab1c2e713236a91b2c7ec325792de0180b2945c` |

Replays regenerated on the 17-digit inputs (recipe P, `ulimit -v 8000000`):

| File | Recipe | Bytes | sha256 |
|---|---|---|---|
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix024.nc` | G1+P | 32057 | `67ca61bd7e295e683466865b636606b8239822460c1eef166ef1ca4635f550cf` |
| `outputs_from_python/python_ggl90_outputs_isomip_12.nc` | G2+P | 57616601 | `c812dfc6e87d0ee20ab9ee721e46bd88620019709b511a19b28a39098ee37b01` |
| `outputs_from_python/python_ggl90_outputs_global_ocean_90x40x15_idemix_10.nc` | G3+P | 17296185 | `39a3ba8bcbb8040b5edfe16f5b435573bdf6c49ea1a08d86ee8d3da063d4502a` |
| `outputs_from_python/python_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` | G4+P (**HISTORICAL**, as above) | 29509545 | `899c7e745b403f38320946c794130264e1d3a6e7f4ea5e5f4525293909c14af5` |
| `outputs_from_python/python_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5+P | 8199209 | `1a56afbdefd00adfe29128bb7cfb4e4708d15bbef2aa39403f0c5ea2bf1f0e10` |

Standalone-driver Fortran outputs (`outputs_from_python_standalone/<scenario>/ggl90_standalone_output.txt`)
were regenerated with the widened `ggl90_calc.F` prints from the unchanged
`ggl90_standalone_input.txt`; see `CONVENTIONS_STANDALONE_DATA.md` ("Regenerated at 17 digits, 1DMIX-070").

## `global_ocean_cs32x15_idemix_10` is MITgcm-side evidence only (1DMIX-073)

Recipe G4 is a **pressure-coordinate** run (`input.in_p`, `buoyancyRelation='OCEANICP'`): the captured `depth` is
positive Pa (4.9467e7 ... 2.5133e5, decreasing with level index) and `cell_thickness` 5.03e5 ... 7.11e6, the same Pa grid
as the KPP cs32x15 capture. The port has no `coordFac` conversion (permanently out of scope, 1DMIX-040), and until
1DMIX-073 `GGL90Driver.compute_mixing` accepted that geometry and returned **finite wrong values**. Since 1DMIX-073 it
calls `main/column_grid.py::validate_zcoordinate_geometry` first and raises `ValueError`
(`tests/test_ggl90_mitgcm_validation.py::test_global_ocean_cs32x15_port_rejects_pressure_coordinate_input`; no output is
written by `run_ggl90_from_netcdf_input.py::run`). The capture stays declared (`esx/project.json:external_inputs`) because the MITgcm-side
facts are still asserted (`::test_global_ocean_cs32x15_capture_geometry_is_pressure_coordinate`,
`::test_global_ocean_cs32x15_mitgcm_ggl90_diffkz_is_in_coordfac_squared_units`).

**Last measured port-side numbers (HISTORICAL; the port can no longer produce them).** Measured 2026-10-02 on the
pre-change code (a `git archive` extraction of HEAD 65939cf, so the HEAD driver and replay script), full capture, all 10
timesteps, N = 813,820 non-NaN cells, every one finite (0 NaN, 0 inf; N is 555,220 computed ocean cells with non-zero input temperature plus 258,600 zero-filled land-column cells that are zero on both sides and dilute the fractions; ocean-only fractions 0.9163 / 0.9195 / 0.9193 / 0.9494 with the same cell counts above 1%), statistics by the test module's own `_diff_and_rel`
(`devel-loop/loop_state/scratch/ab2c15d32621abb42/measure_cs32x15_prechange.py`, `bob-1DMIX-073-evidence.md` unit 0):

| field | fraction >1% rel | max abs diff | max port value |
|---|---|---|---|
| `visc_az` | 0.6251 | 99.99992 | 100 (`GGL90viscMax` cap) |
| `diff_kz` | 0.6273 | 2.0149e9 | 100 (cap) |
| `mixing_length` | 0.6272 | 1.4492e7 | 1.4493349e7 m |
| `tke_after` | 0.6477 | 4.1995e5 | 4.1995e5 |

Reading note found while measuring: the `diff_kz` "max abs diff" of 2.0149e9 is MITgcm's own captured `diff_kz`
(maximum 2.0149e9; the port's value there is capped at 100). The instrumented source
`mitgcm_verification_mods/ggl90_mods/ggl90_calc.F` explains it: `coordFac = gravity * rhoConst` for `usingPCoords` (line 257),
the captured `visc_az` is `KappaM` (stored in `GGL90viscOutput`, lines 518-519) before any `coordFac` scaling, and lines 1088-1090 set
`GGL90diffKr = MAX( MIN(visctmp/TKEPrandtlNumber, GGL90diffMax)*coordFac*coordFac, diffKrNrS )`. So the captured `diff_kz` carries
`coordFac^2` (Pa^2/s scale) and is not a metres-scale diffusivity; that law (with `TKEPrandtlNumber` from the capture and
`GGL90diffMax`, `diffKzS`, `gravity`, `rhoConst` from its attributes) reproduces `diff_kz` with maximum relative deviation 0.0 over all
510,536 cells with `visc_az > 0` (`scratch/ab2c15d32621abb42/law_check.py`; the other 411,064 cells have `visc_az == 0` and `diff_kz == 0`). So the 2.0e9 listed as the `diff_kz` port-versus-MITgcm difference here
and in `GGL90_VALIDATION_RESULTS.md` is MITgcm's own value in those units, not a port-side error of that size.

## Cross-scheme captures, 1DMIX-054 (2026-09-30): GGL90 on `lab_sea`

The first GGL90 captures of `lab_sea` (all its existing captures are KPP), at the two durations of the existing KPP
captures. **The namelist is CONSTRUCTED**: no stock MITgcm experiment has a `data.ggl90` for `lab_sea`. `data.ggl90` is
`&GGL90_PARM01 &` (every parameter at the MITgcm default: none of this project's other GGL90 namelists can be derived from
this grid's own geometry/forcing, see the README), `data.pkg` switches `useKPP` off and `useGGL90` on, and a constructed
`pickup_ggl90.0000000001` holds the cold-start TKE (`GGL90TKEmin=1e-11`; `nIter0=1` makes GGL90 require its own pickup, which
the stock KPP-only input never had). All in `mitgcm_verification_mods/lab_sea/ggl90_input_validation/` (README, files,
`assemble_run_dir.sh`, `make_pickup_ggl90.py`); compile tree `lab_sea/ggl90_code_validation/` (stock headers, the single-tile
20x16 `SIZE.h` shared with `lab_sea/code_validation/`, `ggl90` added, default `GGL90_OPTIONS.h`; differences in
`mitgcm_verification_mods/README.md`). Provenance rules, MITgcm commit, image and instrumentation as the 1DMIX-070 set
(`d861cd501`, `mitgcm:latest` `6cc66b8957d8`, ES25.16); MITgcm files only from an MITgcm run parsed by the streaming
`parse_mitgcm_ggl90_split.py`, Python files only from replaying the port.

| Id | Steps |
|---|---|
| **G6** `lab_sea_999` (999 steps, 1 tile 20x16x23, 5,764,230 wet cells) | `MITGCM_ROOT=~/Projects/MITgcm <mods>/lab_sea/ggl90_input_validation/assemble_run_dir.sh 999` (creates `verification/lab_sea/input.ggl90_999`: `data` = stock `input/data` with the single `endTime=36000.` -> `3600000.` edit of KPP recipe R3, plus `data.pkg`, `data.ggl90`, `data.diagnostics`, `pickup_ggl90.0000000001.{data,meta}`; the run script layers it on the stock `input/`); cwd `~/Projects/MITgcm/verification`: `./experiment_compile.sh lab_sea -mods <mods>/lab_sea/ggl90_code_validation -build build_docker_ggl90_054 -clean -j 8`; `./experiment_run_no_compile.sh lab_sea input.ggl90_999 -build build_docker_ggl90_054 -output output_ggl90_999_054` (64.6 s, `output.txt` 1,898,240,036 bytes, 999 validation blocks); parse (repo root, `ulimit -v 8000000`): `python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_ggl90_split.py <run>/output.txt lab_sea` (46 s). **CONSTRUCTED namelist.** Files named `lab_sea_999` (the true step count; the KPP counterpart is `lab_sea_1000_0820T0946`, also 999 steps). |
| **G7** `lab_sea_6mo` (4368 steps, **INFERRED** end time as R5) | same as G6 with `assemble_run_dir.sh 6mo` (`endTime=15728400.`, the edit of KPP recipe R5, itself INFERRED) and `-output output_ggl90_6mo_054` (about 5 min run, `output.txt` 8,299,126,949 bytes, 4368 validation blocks, `Execution ended Normally`); parse as G6 (about 4 min, output files written by the streaming parser, peak memory not separately recorded). **CONSTRUCTED namelist.** Its first 999 steps are bitwise identical to G6 (every input and output variable; asserted for the first 20 steps in `test_lab_sea_6mo_first_999_steps_identical_to_999_capture`). |
| **P8** | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_ggl90_from_netcdf_input.py GGL90_port_validation/inputs_from_mitgcm/mitgcm_ggl90_inputs_lab_sea_999.nc -o GGL90_port_validation/outputs_from_python/python_ggl90_outputs_lab_sea_999.nc` (`ulimit -v 8000000`, 55 s; `run_ggl90_from_netcdf_input.py` gained optional `--first`/`--last` and loads the selected inputs once, 1DMIX-054; without that the 999-step capture cannot be replayed in practice). No Python file exists for `lab_sea_6mo` (tests replay steps 2000-2099 in-process). |

| File | Recipe | Bytes | sha256 | Digits | raw `output.txt` bytes | raw `output.txt` sha256 |
|---|---|---|---|---|---|---|
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_lab_sea_999.nc` | G6 | 85252860 | `b38746a9fb0be5266f2b953f1bf2ef909590582dc489c1952dd714cd85d5e2cc` | 17 (ES25.16) | 1898240036 | `7f17047e2c729f76b27f111cb03299959ceec6c1ce9f73dedf7a68eee705467b` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_lab_sea_999.nc` | G6 | 67675896 | `be3d190bb402da6c1cec039ee826a0012a78768fee15d9c0eb952fca4f7b8361` | 17 (ES25.16) | 1898240036 | `7f17047e2c729f76b27f111cb03299959ceec6c1ce9f73dedf7a68eee705467b` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_lab_sea_6mo.nc` | G7 (INFERRED end time) | 366268537 | `90400b03aa1d23515a6e9d16988b4a45e4c6fb8423b9aaa0243778f372c9c19d` | 17 (ES25.16) | 8299126949 | `fa3f94de2e521b57c1f2feaa514334ece04717780b4201344138b85b2ae34a4b` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_lab_sea_6mo.nc` | G7 (INFERRED end time) | 283434338 | `eb1e34b921bf6929ff6cfda03218b3d3a5cae70f206bfac6b3bd768d6fb0be9c` | 17 (ES25.16) | 8299126949 | `fa3f94de2e521b57c1f2feaa514334ece04717780b4201344138b85b2ae34a4b` |
| `outputs_from_python/python_ggl90_outputs_lab_sea_999.nc` | P8 | 235307953 | `d6fc4b2cb64801743a8e300d29c3d05da676bcd4dcfc77387e051dfa94cd15b8` | - | - | - |

Raw `output.txt` files are kept under `~/Projects/MITgcm/verification/lab_sea/output_ggl90_*_054/` (untracked, outside the repo).
Results: `GGL90_VALIDATION_RESULTS.md` ("`lab_sea` (999 timesteps and 6-month)"). In short: `visc_az`/`mixing_length` are clean to
roundoff; `diff_kz`/`tke_after` are known gaps traced (by a measured identity) to the replay feeding the port column-local
velocities where MITgcm averages (i,i+1),(j,j+1) (replay-input effect 1DMIX-071, not a port gap).

## `vermix` (20 timesteps, single column)

`GGL90` was iterated on this experiment across several closed issues (1DMIX-015,
-016, -024, -041, -048), each producing its own re-capture. UUIDs cross-checked
directly (`input_uuid` in each `outputs_from_python/` file matches the `uuid` of
its own `inputs_from_mitgcm/` counterpart — verified 2026-09-27) confirm the
pairings below; creation timestamps are monotonically increasing in the order
listed.

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix024.nc` | **current** | The capture `tests/test_ggl90_mitgcm_validation.py` (`DATA_VERMIX`) actually loads; newest (2026-09-19), matches `MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`'s own `vermix` section. |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20_1dmix024.nc` | **current** | Paired MITgcm output for the above (`OUTPUTS_VERMIX` in the same test). |
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix024.nc` | **current** | Regenerated freshest (2026-09-27, post-1DMIX-048 fix) against the current port; this is the file the freshness-checked PDF report (`reports/ggl90_validation_vermix_20.pdf`) was built from. |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20.nc` | superseded, retained | Original 2026-09-16 capture, predates the 1DMIX-015 `dt`-bug fix. No active script/test references it by name (confirmed by grep). |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix016_fix.nc` | superseded, retained | 2026-09-17 re-capture for 1DMIX-016. No active reference. |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix015_fix.nc` | superseded, retained | 2026-09-18 re-capture for 1DMIX-015 (despite the "015" name, dated *after* "016" — the fix issue numbers were not assigned in strict chronological-capture order). No active reference. |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20*.nc` (the 3 non-current versions) | superseded, retained | Paired MITgcm outputs for the 3 superseded inputs above. No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20.nc` | superseded, retained | Paired with the original 2026-09-16 input; predates 1DMIX-015/-016/-041/-048. No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20_fixed.nc` | superseded, retained | Same 2026-09-16 input UUID as the plain `vermix_20.nc` output above — an intermediate re-run the same day (`_fixed` suffix, no corresponding "unfixed" input version — likely an early dt-bug-fix attempt before the 1DMIX-015 re-capture existed). No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix016_fix.nc` | superseded, retained | Paired with the 2026-09-17 `_1dmix016_fix` input. No active reference. |

None of the "superseded, retained" files above are referenced by any script or
test under `MITgcm_to_Python_port_verification/{scripts,tests}` (grep-confirmed,
1DMIX-046) or by
`MITgcm_to_Python_port_verification/GGL90_port_validation/GGL90_VALIDATION_RESULTS.md`.
They are kept only because deleting a
capture that later turns out to matter is harder to undo cleanly than keeping a
small `.nc` file; delete them in a future issue if disk space becomes a real
constraint (git-ignored, so removal does not touch history either way).
