#!/usr/bin/env bash
# 1DMIX-054: assemble the untracked run-input directory for the CONSTRUCTED
# global_ocean.cs32x15 + KPP capture (pressure coordinates!).
# Usage: MITGCM_ROOT=~/Projects/MITgcm ./assemble_run_dir.sh
# Creates $MITGCM_ROOT/verification/global_ocean.cs32x15/input.in_p_kpp. The name starts with
# "input." on purpose: experiment_run_no_compile.sh then layers it on the experiment's input/
# (eedata, regMask_lat24.bin, lev_surf*, trenberth_tau*, bathy files) exactly as it does for the
# stock input.in_p used by the existing GGL90 capture, and runs input.in_p_kpp/prepare_run
# (== input.in_p/prepare_run: links the grid_cs32 faces and the icedyn/seaice data files).
# Relative symlinks so the directory resolves inside the Docker container (/mitgcm mount).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MITGCM_ROOT="${MITGCM_ROOT:?set MITGCM_ROOT to the MITgcm checkout}"
EXP="$MITGCM_ROOT/verification/global_ocean.cs32x15"
NEWDIR="$EXP/input.in_p_kpp"
rm -rf "$NEWDIR"
mkdir -p "$NEWDIR"
# constructed files (real copies): data, data.pkg, data.kpp, data.diagnostics
cp "$HERE/data" "$HERE/data.pkg" "$HERE/data.kpp" "$HERE/data.diagnostics" "$NEWDIR/"
# everything else the GGL90 capture's input.in_p supplies, unmodified (data.ggl90 and the
# IDEMIX forcing files are not needed with KPP)
for f in bathy_in_P.bin geopotanom.bin lev_S_cs_flip15.bin lev_T_cs_flip15.bin prepare_run \
         tr_checklist eedata.mth; do
  ln -sf "../input.in_p/$f" "$NEWDIR/$f"
done
echo "assembled $NEWDIR"
