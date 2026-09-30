# `global_ocean.cs32x15` IDEMIX capture setup (1DMIX-025/1DMIX-040)

`code_validation/` mirrors this project's usual per-experiment pattern:
`ggl90_calc.F` symlinked to `../../ggl90_mods/ggl90_calc.F`, every other
header (`CPP_OPTIONS.h`, `DIAG_OPTIONS.h`, `DIAGNOSTICS_SIZE.h`,
`EXF_OPTIONS.h`, `GGL90_OPTIONS.h`, `packages.conf`, `SEAICE_OPTIONS.h`,
`SIZE.h`, `SIZE.h_mpi`) copied **unmodified** from the experiment's own real
`code/`. As with `global_ocean_90x40x15`, `GGL90_OPTIONS.h` is the
experiment's own real header (already `#define ALLOW_GGL90_IDEMIX` **and**
`#define GGL90_IDEMIX_CVMIX_VERSION` — a real, confirmed difference from
`global_ocean.90x40x15`'s own header, which leaves the CVMIX variant
`#undef`'d).

## Setup steps performed directly inside `input.in_p/` (documented, not a bug)

**1DMIX-066 update (2026-09-30):** the current `experiment_run_no_compile.sh` layers
`input.<X>` on top of `input/` and runs `input.in_p/prepare_run` inside the run
directory, so `./experiment_run_no_compile.sh global_ocean.cs32x15 input.in_p -build <build> -output <run>`
ran to completion on the WSL checkout with none of the manual steps below (no
file inside the MITgcm checkout is created). They are kept as the record of
what the original Mac-era run needed.

`input.in_p` has its own real `prepare_run` script — ran it directly (same
established precedent as `seaice_obcs`'s own `prepare_run`): it symlinks
`grid_cs32.face00?.bin` (from `../../tutorial_held_suarez_cs/input`),
`core_dwnLw_cs32.bin`/`core_dwnSw_cs32.bin`/`core_prec_1_cs32.bin`/
`core_q_air_cs32.bin`/`core_rnof_1_cs32.bin`/`core_snwP_1_cs32.bin`/
`core_t_Air_cs32.bin`/`core_wndSpd_cs32.bin` (from `../input.icedyn`), and
`data.exf`/`data.seaice`/`runoff_temperature.bin` (from `../input.seaice`)
directly into `input.in_p/`.

`prepare_run` does **not** cover every file `input.in_p`'s own (symlinked)
namelists reference. Four further `STOP ABNORMAL END: S/R MDS_READ_FIELD`
failures were found and fixed the same way — symlinking from the sibling
`input/` directory, which already has the real file:

```bash
cd $MITGCM_ROOT/verification/global_ocean.cs32x15/input.in_p
./prepare_run
ln -sf ../input/eedata eedata                        # missing entirely
ln -sf ../input/regMask_lat24.bin regMask_lat24.bin   # data.diagnostics's diagSt_regMaskFile
ln -sf ../input/lev_surfT_cs_12m.bin lev_surfT_cs_12m.bin   # data.exf's climsstfile
ln -sf ../input/lev_surfS_cs_12m.bin lev_surfS_cs_12m.bin   # data.exf's climsssfile
ln -sf ../input/trenberth_taux.bin trenberth_taux.bin       # data.exf's ustressfile
ln -sf ../input/trenberth_tauy.bin trenberth_tauy.bin       # data.exf's vstressfile
```

(`data.exf`'s commented-out `#uwindfile`/`#vwindfile` =
`core_u_wind_cs32.bin`/`core_v_wind_cs32.bin` are genuinely inactive —
confirmed by reading the real namelist, not needed.)

Unlike `global_ocean_90x40x15`, no `useSingleCpuIO` fix was needed here —
`input.in_p/data` already sets it, and no new/modified `data` copy was
required; every fix above is a plain symlink of an already-real, unmodified
sibling file, added directly inside `input.in_p/` (untracked additions, not
an edit of any existing tracked file's content).

## Known confound — do not trust this capture's raw comparison as an IDEMIX signal

This experiment sets `buoyancyRelation='OCEANICP'` → MITgcm's own
`usingPCoords=.TRUE.` (pressure coordinates). This project's GGL90 (and
KPP) Python port has no pressure-coordinate support at all — see
`open_issues.md` 1DMIX-040 for the full evidence. The captured grid
geometry (`rC`/`rF`/`drF`) is genuinely in Pa here, not metres; any
Python-port comparison against this capture's `mixing_length`/`diff_kz`/
`tke_after` is dominated by that confound, not by the IDEMIX gap this
capture was originally built to test. Use `global_ocean.90x40x15`'s own
capture (a real z-coordinate experiment) for a clean IDEMIX-gap
quantification instead.

See `open_issues.md` 1DMIX-025 (capture evidence) and 1DMIX-040
(pressure-coordinate gap) for full detail.
