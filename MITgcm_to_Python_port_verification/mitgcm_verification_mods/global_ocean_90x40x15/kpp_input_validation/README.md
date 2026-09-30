# `global_ocean.90x40x15` + KPP: CONSTRUCTED run-input files (1DMIX-054)

**These namelists are constructed by this project. They are NOT a stock MITgcm experiment**:
no `data.kpp` and no KPP-enabled `data.pkg` exists for `global_ocean.90x40x15` anywhere in the
MITgcm tree (its `code/packages.conf` has an explicit `-kpp`). Nothing here should be read as
"the MITgcm KPP verification of this grid". The MITgcm reference values still come only from a real
MITgcm run (recipe R7 in `KPP_port_validation/CAPTURES.md`).

Companion: `../kpp_code_validation/` (compile side: the stock `code/` headers unmodified, `-kpp`
removed from `packages.conf`, `kpp_calc.F`/`kpp_routines.F` symlinked to `../../kpp_mods/`, MITgcm's
default `KPP_OPTIONS.h`). `../code_validation/` + `input.idemix` is the existing GGL90/IDEMIX capture
of the same grid; this run shares its domain (36 tiles, 90x40x15), forcing binaries, JMD95P
equation of state, static z-coordinate geometry, GMRedi and exch2 files, cold start (`nIter0=0`),
`deltaTtracer=86400 s` and 10 time steps, so the two captures are a geometry-matched cross-scheme pair.

Files (every other run-directory file is a symlink, see `assemble_run_dir.sh`):

| file | source | differences |
|---|---|---|
| `data` | `verification/global_ocean.90x40x15/input.idemix/data` | see the table below |
| `data.pkg` | `input.idemix/data.pkg` | `useKPP=.TRUE.` replaces `useGGL90=.TRUE.` (GGL90 and KPP cannot both be on: `pkg/ggl90/ggl90_check.F`) |
| `data.kpp` | `global_oce_latlon/input_validation/data.kpp` | identical content: `&KPP_PARM01 &`, every parameter at the MITgcm default |

`data` differences from `input.idemix/data` (comments in the file mark each one):

| parameter | value here | why (target-grid evidence) |
|---|---|---|
| `viscAr` | `1.E-3` (commented out in `input.idemix`) | KPP has no IDEMIX background; its interior mixing is built on `viscArNr(1)`/`diffKrNr` (`kpp_routines.F`: `diffus = MAX(blmc, viscArNr(1))`, `Ri_iwmix`). The grid's own standard value (`input/data`) is restored. |
| `diffKrT`, `diffKrS` | `3.E-5` (commented out) | same reason and source |
| `ivdc_kappa` | `0.` (`input.idemix`: `1.`) | **required**: `pkg/kpp/kpp_check.F:128-133` stops the run unless `cAdjFreq=0` and `ivdc_kappa=0`. The first run with `ivdc_kappa=1.` did stop there; the stock `input/data` value (10.) is illegal too. |
| `useSingleCpuIO` | `.TRUE.` (added) | the same single edit the GGL90 capture's recipe made (flat `.bin` fields on a 36-tile domain) |
| `the_run_name` | `'kpp_90x40x15'` | label only |

Deliberately NOT carried over: the tuned values of other KPP namelists in this project
(`KPPwriteState`, `KPP_ghatUseTotalDiffus`, `KPPuseSWfrac3D` from lab_sea / the 1-D column,
`minKPPhbl`, `Ricr` from vermix): they are I/O or configuration choices of those experiments with
no basis in this grid's forcing or geometry. `data.diagnostics` is the experiment's own stock
`input/data.diagnostics` (`input.idemix`'s lists GGL90/IDEMIX-only diagnostics that do not exist with
GGL90 off).

## Reproduce

```bash
export MITGCM_ROOT=~/Projects/MITgcm            # d861cd501, tracked tree unmodified
./assemble_run_dir.sh                            # creates verification/global_ocean.90x40x15/input_docker_kpp90
cd $MITGCM_ROOT/verification
./experiment_compile.sh global_ocean.90x40x15 -mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_ocean_90x40x15/kpp_code_validation -build build_docker_kpp_054 -clean -j 8
./experiment_run_no_compile.sh global_ocean.90x40x15 input_docker_kpp90 -build build_docker_kpp_054 -output output_kpp_90x40_054
cd <repo> && python3 MITgcm_to_Python_port_verification/scripts/parse_mitgcm_split.py $MITGCM_ROOT/verification/global_ocean.90x40x15/output_kpp_90x40_054/output.txt global_ocean.90x40x15
```

Measured (Docker, 7 s run, 192 MB `output.txt`, 360 validation blocks = 10 steps x 36 tiles, 2,315 wet
columns per step). The comparison with the port is in `KPP_port_validation/KPP_VALIDATION_RESULTS.md`.
