# `global_ocean.90x40x15` IDEMIX capture setup (1DMIX-025)

`code_validation/` mirrors this project's usual per-experiment pattern:
`ggl90_calc.F` symlinked to `../../ggl90_mods/ggl90_calc.F` (the canonical,
additively-instrumented source), every other header (`CPP_OPTIONS.h`,
`DIAGNOSTICS_SIZE.h`, `GAD_OPTIONS.h`, `GGL90_OPTIONS.h`, `packages.conf`,
`SIZE.h`, `SIZE.h_mpi`) copied **unmodified** directly from the experiment's
own real `code/` directory. Unlike every prior GGL90 experiment, `GGL90_
OPTIONS.h` here is the experiment's own real header (not this project's own
template) — it already `#define`s `ALLOW_GGL90_IDEMIX` correctly, so no
hand-edit was needed.

## Why a new input directory was needed

`verification/global_ocean.90x40x15/input.idemix/` has no `prepare_run`
script and is missing the 8 shared forcing binaries
(`bathymetry.bin`/`lev_t.bin`/`lev_s.bin`/`trenberth_taux.bin`/
`trenberth_tauy.bin`/`lev_sst.bin`/`lev_sss.bin`/`ncep_qnet.bin`) that its own
`data` namelist references — these are stock MITgcm reference data already
present at `verification/tutorial_global_oce_latlon/input/`, exactly as the
base (non-IDEMIX) `global_ocean.90x40x15/input/prepare_run` script documents
for the plain variant.

The first run attempt (input dir = `input.idemix` directly, forcing
binaries symlinked into the run's own writable output directory) hit
`STOP ABNORMAL END: S/R MDS_READ_FIELD: bathymetry.bin.001.001.data ...
Files DO not exist` — this experiment's real 36-tile `SIZE.h`
(`sNx=10,sNy=10,nSx=9,nSy=4`, `nPx=nPy=1`) makes MITgcm's default MDS reader
expect each 2D field pre-split per-tile, which the plain flat shared `.bin`
files are not (the same root cause `global_oce_latlon/input_validation/
README.md` already documents for its own, differently-tiled domain). The
fix is `useSingleCpuIO=.TRUE.` — but `input.idemix/data` is read-only
checkout source, and the run harness's own `ln -sf .../input.idemix/* .`
step would silently clobber any same-named override placed in the output
directory before running.

`input_docker_idemix90/` is a new, project-added, **untracked** directory
(same category as this project's own `build_docker_*`/`output_docker_*`
artifact directories — never part of the tracked MITgcm checkout) that
symlinks every one of `input.idemix`'s own real files plus the 8 shared
forcing binaries (relative symlinks, resolvable inside the Docker container
since this directory lives inside the same `/mitgcm`-mounted tree, unlike a
symlink placed in the separately-mounted `/output`). Only `data` itself is a
real (non-symlink) copy, carrying exactly one added line
(`useSingleCpuIO=.TRUE.`, with a comment citing this file).

## Reproducing the run directory

```bash
EXP=$MITGCM_ROOT/verification/global_ocean.90x40x15
NEWDIR="$EXP/input_docker_idemix90"
mkdir -p "$NEWDIR"
for f in data.ggl90 data.pkg data.exch2.mpi data.gmredi data.ptracers \
         data.diagnostics eedata eedata.mth tidal_energy.bin wind_energy.bin; do
  ln -sf "../input.idemix/$f" "$NEWDIR/$f"
done
for f in bathymetry.bin lev_t.bin lev_s.bin trenberth_taux.bin \
         trenberth_tauy.bin lev_sst.bin lev_sss.bin ncep_qnet.bin; do
  ln -sf "../../tutorial_global_oce_latlon/input/$f" "$NEWDIR/$f"
done
cp "$EXP/input.idemix/data" "$NEWDIR/data"
# then append useSingleCpuIO=.TRUE., to $NEWDIR/data's &PARM01 block
# (1DMIX-066: `data.diagnostics` was missing from this list until the WSL regeneration;
# without it the run stops at DIAGNOSTICS_READPARMS. Insert the line before the closing
# `&` of &PARM01.)
```

Then compile with `-mods <repo>/MITgcm_to_Python_port_verification/
mitgcm_verification_mods/global_ocean_90x40x15/code_validation` and run with
`input_docker_idemix90` as the input dir — see `mitgcm_verification_mods/
README.md` for the general Docker compile/run commands. See `open_issues.md`
1DMIX-025 for the full capture/comparison evidence.
