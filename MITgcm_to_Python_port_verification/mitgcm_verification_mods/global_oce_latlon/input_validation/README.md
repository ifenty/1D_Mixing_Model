# `global_oce_latlon` forward-only KPP input namelist (1DMIX-020/021/022)

`global_oce_latlon`'s only KPP-enabled build variant (`code_oad`) bundles KPP
with the OpenAD adjoint packages, which need the real OpenAD source-to-source
compiler (not available in this project's plain-gfortran Docker image) --
see `closed_issues.md` 1DMIX-020. This directory holds the namelist set for
a **forward-only KPP** build instead (paired with
`../code_validation/`'s trimmed `packages.conf`, which drops `openad`/
`adjoint` from `code_oad`'s package list).

No single stock MITgcm input directory has this combination, so this is a
merge of three sources, plus two required fixes -- reproduced here (not the
raw external MITgcm checkout) so this configuration survives even if that
checkout is ever reset:

- `data`, `data.kpp`: from `input_oad.kpp/` (KPP + GMRedi enabled, `useGrdchk`
  left as in that source -- see fix below).
- `eedata`, `data.gmredi`: from `input_oad/` (not present in `input_oad.kpp/`).
- `NCEP_4x4_sw_monav_48-03av`: from `input_oad.kpp/` (shortwave water-type
  data file referenced by `data`'s `surfQswFile`).
- `data.pkg`: `input_oad.kpp/data.pkg` with `useGrdchk` changed
  `.TRUE. -> .FALSE.` (the `grdchk` package isn't compiled into this
  forward-only build).
- `data` also has `useSingleCpuIO=.TRUE.` added to `&PARM01` -- without it,
  MITgcm's default multi-tile MDS I/O expects each `.bin` field pre-split
  into per-tile files (`bathymetry.bin.001.001.data`, etc.), which don't
  exist for this 4-tile (`sNx=45,sNy=20,nSx=2,nSy=2`) domain.
- `*.meta`: written here (no stock MITgcm source has these). `useSingleCpuIO`
  needs each field in MDS `<name>.data`/`<name>.meta` pair format, not a bare
  `.bin` -- these are plain-text MDS metadata (dimensions, precision, record
  count) for the plain flat `.bin` files reused from `tutorial_global_oce_latlon/input/`.

## What's NOT copied here

The actual binary field data (`bathymetry.bin`, `lev_t.bin`, `lev_s.bin`,
`lev_sst.bin`, `lev_sss.bin`, `ncep_qnet.bin`, `trenberth_taux.bin`,
`trenberth_tauy.bin`) is stock MITgcm reference data already present at
`$MITGCM_ROOT/verification/tutorial_global_oce_latlon/input/` -- not
authored by this project, and too large/redundant to duplicate here.

## Reproducing the run directory

```bash
RUNDIR=$MITGCM_ROOT/verification/global_oce_latlon/input_docker_kpp_fwd
mkdir -p "$RUNDIR"
cp <this_dir>/{data,data.pkg,data.kpp,data.gmredi,eedata,NCEP_4x4_sw_monav_48-03av,*.meta} "$RUNDIR/"
for f in bathymetry.bin lev_s.bin lev_sss.bin lev_sst.bin lev_t.bin \
         ncep_qnet.bin trenberth_taux.bin trenberth_tauy.bin; do
  # Two levels up: input_docker_kpp_fwd/ -> global_oce_latlon/ -> verification/
  ln -sf "../../tutorial_global_oce_latlon/input/$f" "$RUNDIR/${f}.data"
done
```

Then compile with `-mods <repo>/MITgcm_to_Python_port_verification/mitgcm_verification_mods/global_oce_latlon/code_validation`
and run with this `input_docker_kpp_fwd` directory -- see
`MITgcm_to_Python_port_verification/mitgcm_verification_mods/README.md` for
the general Docker compile/run commands.
