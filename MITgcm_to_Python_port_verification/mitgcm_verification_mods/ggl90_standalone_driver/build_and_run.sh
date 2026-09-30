#!/bin/bash
#
# Compile and run the standalone GGL90_CALC driver: compiles the real
# vermix instrumentation copy of MITgcm/pkg/ggl90/ggl90_calc.F (same
# physics as pristine, only additive validation-dump instrumentation --
# see 1DMIX-016/1DMIX-024) plus pristine MITgcm/pkg/ggl90/ggl90_mixinglength.F
# and MITgcm/model/src/solve_tridiagonal.F, plus this directory's
# ggl90_standalone_main.F -- no genmake2, no full model build. Mirrors
# ../kpp_standalone_driver/build_and_run.sh's two-stage compilation
# (cpp -traditional -P followed by tools/set64bitConst.sh).
#
# Usage: ./build_and_run.sh <input.txt> <output.txt>

set -e

DRIVER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Override with the MITGCM_ROOT environment variable on any host whose MITgcm
# checkout is not at the original macOS path (1DMIX-065: WSL uses
# ~/Projects/MITgcm). The default is unchanged.
MITGCM_ROOT="${MITGCM_ROOT:-/Users/ifenty/git_repo_others/MITgcm}"
VERMIX_DIR="$MITGCM_ROOT/verification/vermix"
# PACKAGES_CONFIG.h / CPP_OPTIONS.h: reuse the real, genmake2-generated
# build directory created for 1DMIX-024's sigmaR-capture rebuild (see
# open_issues.md) -- same reasoning as kpp_standalone_main.F's own
# build_and_run.sh reusing 1D_ocean_ice_column/build_docker_kppmix_extend
# for the identical purpose (real, correctly-generated package defines,
# not hand-written guesswork).
PKGCONFIG_DIR="$VERMIX_DIR/build_docker_ggl90_1dmix024"
# CPP_EEOPTIONS.h / GGL90_OPTIONS.h: vermix's real code_validation dir
# (same one -mods points the full-model build at).
CPPOPTS_DIR="$VERMIX_DIR/code_validation"

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.txt> <output.txt>"
    exit 1
fi
if [ ! -d "$PKGCONFIG_DIR" ]; then
    echo "Error: $PKGCONFIG_DIR not found -- build vermix's"
    echo "  build_docker_ggl90_1dmix024 first (experiment_compile.sh vermix"
    echo "  -mods $CPPOPTS_DIR -build build_docker_ggl90_1dmix024)."
    exit 1
fi
INPUT_TXT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
OUTPUT_TXT_DIR="$(cd "$(dirname "$2")" && pwd)"
OUTPUT_TXT_NAME="$(basename "$2")"

# SIZE.h: auto-regenerated per-run (1DMIX-024 scenario-extension
# follow-up), mirroring ../kpp_standalone_driver/build_and_run.sh's
# Nr-detection -- but UNLIKE that driver, OLx/OLy stay 2 (not 0), since
# GGL90_CALC's loop bounds and every array's declared halo are
# parameterized directly from SIZE.h's real OLx=OLy=2 (see this
# directory's ggl90_standalone_main.F header comment). Only Nr varies
# (vermix's own captures always have Nr=26, so this is backward
# compatible; the 6 idealized scenarios have Nr=23..50).
NR_DETECTED="$(head -1 "$INPUT_TXT" | awk '{print $2}')"
if [ -z "$NR_DETECTED" ]; then
    echo "Error: could not read Nr from first line of $INPUT_TXT"
    exit 1
fi
cat > "$DRIVER_DIR/SIZE.h" <<EOF
CBOP
C    !ROUTINE: SIZE.h
C    !INTERFACE:
C    include SIZE.h
C    !DESCRIPTION: \bv
C     Standalone GGL90_CALC driver's SIZE.h. sNx=sNy=1, OLx=OLy=2
C     preserved from vermix's real code_validation/SIZE.h (real halo
C     width, needed by GGL90_CALC's own loop bounds/array declarations).
C     Nr is auto-regenerated on every run from the input file's own
C     ntimeIn/nrIn header -- do not hand-edit.
      INTEGER sNx
      INTEGER sNy
      INTEGER OLx
      INTEGER OLy
      INTEGER nSx
      INTEGER nSy
      INTEGER nPx
      INTEGER nPy
      INTEGER Nx
      INTEGER Ny
      INTEGER Nr
      PARAMETER (
     &           sNx =   1,
     &           sNy =   1,
     &           OLx =   2,
     &           OLy =   2,
     &           nSx =   1,
     &           nSy =   1,
     &           nPx =   1,
     &           nPy =   1,
     &           Nx  = sNx*nSx*nPx,
     &           Ny  = sNy*nSy*nPy,
     &           Nr  =  ${NR_DETECTED})

      INTEGER MAX_OLX
      INTEGER MAX_OLY
      PARAMETER ( MAX_OLX = OLx,
     &            MAX_OLY = OLy )
EOF
echo "SIZE.h: Nr=$NR_DETECTED (auto-detected from $INPUT_TXT), OLx=OLy=2 preserved"

echo "Compiling standalone GGL90_CALC driver..."
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
    INCS='-I/driver -I/pkgconfig -I/cppopts -I/mitgcm/pkg/ggl90
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
    # source only by case (macOS's default case-insensitive filesystem
    # would treat foo.F and foo.f as the SAME file) -- same caution as
    # ../kpp_standalone_driver/build_and_run.sh.
    preprocess /cppopts/ggl90_calc.F ggl90_calc_pp.f
    preprocess /mitgcm/pkg/ggl90/ggl90_mixinglength.F ggl90_mixinglength_pp.f
    preprocess /mitgcm/model/src/solve_tridiagonal.F solve_tridiagonal_pp.f
    preprocess ggl90_standalone_main.F ggl90_standalone_main_pp.f

    gfortran \$FFLAGS -c ggl90_calc_pp.f -o ggl90_calc.o
    gfortran \$FFLAGS -c ggl90_mixinglength_pp.f -o ggl90_mixinglength.o
    gfortran \$FFLAGS -c solve_tridiagonal_pp.f -o solve_tridiagonal.o
    gfortran \$FFLAGS -c ggl90_standalone_main_pp.f -o ggl90_standalone_main.o
    gfortran ggl90_calc.o ggl90_mixinglength.o solve_tridiagonal.o \
        ggl90_standalone_main.o -o ggl90_standalone_main

    echo 'Build OK. Running...'
    ./ggl90_standalone_main /data/input.txt /data/out/$OUTPUT_TXT_NAME
    echo 'Run complete.'
"
