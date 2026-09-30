#!/usr/bin/env bash
# 1DMIX-054: assemble the untracked run-input directory for the CONSTRUCTED lab_sea + GGL90 captures.
# Usage: MITGCM_ROOT=~/Projects/MITgcm ./assemble_run_dir.sh <999|6mo>
# Creates $MITGCM_ROOT/verification/lab_sea/input.ggl90_<tag>. The name starts with "input." on purpose:
# experiment_run_no_compile.sh layers it on the experiment's input/ (forcing, seaice, pickups, data.exf,
# data.cal, data.seaice, ... exactly the files the existing KPP captures use), so only the files that
# differ are here: data (the endTime edit of the existing KPP recipes R3/R5), data.pkg, data.ggl90,
# data.diagnostics, and pickup_ggl90.0000000001.{data,meta} (see make_pickup_ggl90.py).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MITGCM_ROOT="${MITGCM_ROOT:?set MITGCM_ROOT to the MITgcm checkout}"
TAG="${1:?usage: assemble_run_dir.sh <999|6mo>}"
case "$TAG" in
  999) END=3600000. ;;    # startTime=3600, deltaT=3600 => 999 steps (existing KPP recipe R3)
  6mo) END=15728400. ;;   # (15728400-3600)/3600 = 4368 steps (existing KPP recipe R5)
  *) echo "tag must be 999 or 6mo"; exit 2 ;;
esac
EXP="$MITGCM_ROOT/verification/lab_sea"
NEWDIR="$EXP/input.ggl90_$TAG"
rm -rf "$NEWDIR"
mkdir -p "$NEWDIR"
sed "s/^ endTime=36000\.,/ endTime=$END,/" "$EXP/input/data" > "$NEWDIR/data"
grep -q " endTime=$END," "$NEWDIR/data" || { echo "endTime edit failed"; exit 1; }
cp "$HERE/data.pkg" "$HERE/data.ggl90" "$HERE/data.diagnostics" "$NEWDIR/"
python3 "$HERE/make_pickup_ggl90.py" "$NEWDIR"
echo "assembled $NEWDIR (endTime=$END)"
