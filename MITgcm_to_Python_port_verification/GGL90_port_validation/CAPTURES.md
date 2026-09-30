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
| **P** replays | — | cwd `MITgcm_to_Python_port_verification`: `python3 scripts/run_ggl90_from_netcdf_input.py GGL90_port_validation/inputs_from_mitgcm/mitgcm_ggl90_inputs_<tag>.nc -o GGL90_port_validation/outputs_from_python/python_ggl90_outputs_<tag>.nc` (`ulimit -v 8000000`; peak RSS at most 0.31 GB) for each of the five tags. |

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
| `outputs_from_python/python_ggl90_outputs_global_ocean_cs32x15_idemix_10.nc` | G4+P | 29509545 | `fdfabba900879e64015db95624553ea0898754309ead11473fdd0aa1b91610cd` |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 17967456 | `04deb3715d8e2e253d89d77a5375b75c98991a7042fe8241a5d9a6dd1b8666f8` |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5 (INFERRED) | 15698049 | `374e0ff7debba7554913cffff04fe5a41e41f7ba6d9f87588e33b5e19865d880` |
| `outputs_from_python/python_ggl90_outputs_1D_ocean_ice_column_11000.nc` | G5+P | 8199209 | `a195f70524fd46e741e1c637f0bc658306f68b8544f437ee2867a44d7130acc3` |

Every statistic in `GGL90_VALIDATION_RESULTS.md` for these five captures
reproduces to the printed digits from the regenerated files (`vermix` N=520
table; `isomip` N=1,437,204; `global_ocean.90x40x15` N=485,840;
`global_ocean.cs32x15` N=813,820; `1D_ocean_ice_column` N=253,000 absolute
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
