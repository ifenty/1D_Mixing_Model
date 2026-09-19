#!/bin/bash
#
# Compile and run the standalone KPPMIX driver: compiles ONLY
# MITgcm/pkg/kpp/kpp_routines.F (pristine, unmodified) plus this
# directory's kpp_standalone_main.F -- no genmake2, no full model build.
#
# Replicates MITgcm's real two-stage .F compilation (see the generated
# build's Makefile .F.o rule): `cpp -traditional -P` followed by
# tools/set64bitConst.sh, which turns MITgcm's `1. _d 0`-style literals
# into valid `1.D0` Fortran via sed -- plain `gfortran -cpp` alone does
# NOT do this substitution and would fail to compile kpp_routines.F.
#
# Usage: ./build_and_run.sh <input.txt> <output.txt>

set -e

DRIVER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MITGCM_ROOT="/Users/ifenty/git_repo_others/MITgcm"
PKGCONFIG_DIR="$MITGCM_ROOT/verification/1D_ocean_ice_column/build_docker_kppmix_extend"
CPPOPTS_DIR="/Users/ifenty/ProjectsNotBox/1D_Mixing_Experiments/mitgcm_verification_mods/1D_ocean_ice_column/code_validation"

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.txt> <output.txt>"
    exit 1
fi
INPUT_TXT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_TXT_DIR="$(cd "$(dirname "$2")" && pwd)"
OUTPUT_TXT_NAME="$(basename "$2")"

echo "Compiling standalone KPPMIX driver..."
docker run --rm \
    -v "$MITGCM_ROOT:/mitgcm" \
    -v "$DRIVER_DIR:/driver" \
    -v "$PKGCONFIG_DIR:/pkgconfig" \
    -v "$CPPOPTS_DIR:/cppopts" \
    -v "$INPUT_TXT:/data/input.txt" \
    -v "$OUTPUT_TXT_DIR:/data/out" \
    mitgcm:latest bash -c "
    set -euo pipefail
    cd /driver
    INCS='-I/driver -I/pkgconfig -I/cppopts -I/mitgcm/pkg/kpp
          -I/mitgcm/eesupp/inc -I/mitgcm/model/inc'
    DEFINES='-DWORDLENGTH=4 -DNML_TERMINATOR -DHAVE_SYSTEM
             -DHAVE_FDATE -DHAVE_ETIME_SBR -DHAVE_CLOC -DHAVE_SETRLSTK
             -DHAVE_SIGREG -DHAVE_STAT -DHAVE_NETCDF -DHAVE_FLUSH'
    FFLAGS='-ffixed-line-length-132'

    preprocess() {
        cat \"\$1\" | cpp -traditional -P \$DEFINES \$INCS \
            | /mitgcm/tools/set64bitConst.sh > \"\$2\"
    }

    # NOTE: destination names deliberately do NOT differ from their
    # source only by case (e.g. never foo.F -> foo.f in the same dir) --
    # macOS's default case-insensitive filesystem treats those as the
    # SAME file, so a naive foo.F->foo.f pipeline races cat's read
    # against the redirect's truncate and can silently wipe the source.
    preprocess /mitgcm/pkg/kpp/kpp_routines.F kpp_routines_pp.f
    preprocess kpp_standalone_main.F kpp_standalone_main_pp.f

    gfortran \$FFLAGS -c kpp_routines_pp.f -o kpp_routines.o
    gfortran \$FFLAGS -c kpp_standalone_main_pp.f -o kpp_standalone_main.o
    gfortran kpp_routines.o kpp_standalone_main.o \
        -o kpp_standalone_main

    echo 'Build OK. Running...'
    ./kpp_standalone_main /data/input.txt /data/out/$OUTPUT_TXT_NAME
    echo 'Run complete.'
"
