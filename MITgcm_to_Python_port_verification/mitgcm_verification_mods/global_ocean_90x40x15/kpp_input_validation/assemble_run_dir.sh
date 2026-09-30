#!/usr/bin/env bash
# 1DMIX-054: assemble the untracked run-input directory for the CONSTRUCTED
# global_ocean.90x40x15 + KPP capture. Usage: MITGCM_ROOT=~/Projects/MITgcm ./assemble_run_dir.sh
# Creates $MITGCM_ROOT/verification/global_ocean.90x40x15/input_docker_kpp90 (an untracked
# directory of the same category as this project's build_docker_* / input_docker_idemix90
# artifact directories; never part of the tracked MITgcm checkout). Relative symlinks so the
# directory resolves inside the Docker container (/mitgcm mount).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MITGCM_ROOT="${MITGCM_ROOT:?set MITGCM_ROOT to the MITgcm checkout}"
EXP="$MITGCM_ROOT/verification/global_ocean.90x40x15"
NEWDIR="$EXP/input_docker_kpp90"
rm -rf "$NEWDIR"
mkdir -p "$NEWDIR"
# constructed files (real copies): data, data.pkg, data.kpp
cp "$HERE/data" "$HERE/data.pkg" "$HERE/data.kpp" "$NEWDIR/"
# identical-to-the-GGL90-capture files from input.idemix (same GM, exch2, eedata, ptracers file)
for f in data.exch2.mpi data.gmredi data.ptracers eedata eedata.mth; do
  ln -sf "../input.idemix/$f" "$NEWDIR/$f"
done
# the experiment's own standard diagnostics list (input.idemix's lists GGL90/IDEMIX-only
# diagnostics that do not exist when useGGL90 is off)
ln -sf "../input/data.diagnostics" "$NEWDIR/data.diagnostics"
# the 8 shared forcing binaries (as input/prepare_run and the GGL90 capture recipe)
for f in bathymetry.bin lev_t.bin lev_s.bin trenberth_taux.bin trenberth_tauy.bin \
         lev_sst.bin lev_sss.bin ncep_qnet.bin; do
  ln -sf "../../tutorial_global_oce_latlon/input/$f" "$NEWDIR/$f"
done
echo "assembled $NEWDIR"
