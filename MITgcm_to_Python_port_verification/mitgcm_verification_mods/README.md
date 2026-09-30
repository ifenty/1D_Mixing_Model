# MITgcm Verification Modifications

This directory contains custom MITgcm source code modifications for validation experiments.

## Purpose

Contains modified or additional MITgcm source files that override the default verification experiment code. These modifications are kept separate from the MITgcm source repository to:

1. **Version Control** - Track custom code alongside validation test code
2. **Portability** - Share validation setup without modifying MITgcm installation
3. **Reproducibility** - Ensure exact code used for validation is documented
4. **Clean Separation** - Keep instrumentation separate from standard MITgcm code

## Directory Structure

```
mitgcm_verification_mods/
└── <experiment_name>/
    └── code_<purpose>/
        ├── *.F           # Modified Fortran source files
        ├── *.h           # Modified header files
        ├── packages.conf # Custom package configuration
        └── README        # Documentation of modifications
```

## Usage with Docker Compilation

When compiling with the MITgcm Docker tools, use the `-mods` flag to specify the custom code directory:

```bash
cd /path/to/MITgcm/verification

# Compile with custom code from this project
./experiment_compile.sh lab_sea \
    -mods /Users/ifenty/ProjectsNotBox/1D_Mixing_Experiments/mitgcm_verification_mods/lab_sea/code_validation \
    -j 8
```

The `-mods` path should be:
- **Absolute path** from host machine
- Will be mounted into Docker container automatically
- Files in this directory override matching files from MITgcm source

Note (1DMIX-013): if the invoking shell reports `uname -m` as `x86_64` on an
Apple Silicon Mac (e.g. running under Rosetta translation -- check with
`sysctl -n sysctl.proc_translated`), `experiment_compile.sh`'s architecture
auto-detection picks the wrong optfile (`linux_amd64_gfortran` instead of
`linux_arm64_gfortran`) even though Docker Desktop provisions a native
arm64 container, causing a `gcc: error: unrecognized argument in option
'-mcmodel=medium'` build failure. Work around by forcing native execution
for the compile/run commands: `arch -arm64 ./experiment_compile.sh ...`
and `arch -arm64 ./experiment_run_no_compile.sh ...`.

Note (1DMIX-065, Linux/WSL): the `-mods` example paths above are the original
macOS ones; use the absolute path of this directory on your host. The
standalone Fortran drivers (`kpp_standalone_driver/build_and_run.sh`,
`ggl90_standalone_driver/build_and_run.sh`) default to the macOS MITgcm
checkout path but honour the `MITGCM_ROOT` environment variable (e.g.
`MITGCM_ROOT=~/Projects/MITgcm`); they also need the genmake2-generated build
directories `1D_ocean_ice_column/build_docker_kppmix_extend` (KPP) and
`vermix/build_docker_ggl90_1dmix024` (GGL90) under `$MITGCM_ROOT/verification/`,
created with `experiment_compile.sh ... -mods ... -build <name>`. The exact
recipes that regenerated every capture on the WSL checkout are recorded in
`../KPP_port_validation/CAPTURES.md`, `../GGL90_port_validation/CAPTURES.md` (1DMIX-066) and the two
`CONVENTIONS_STANDALONE_DATA.md`.

## Current Experiments

### lab_sea/code_validation

**Purpose**: KPP validation instrumentation for Python port comparison

**Modified Files**:
- `SIZE.h` - Single-processor configuration (nPx=1, nPy=1)
- `kpp_calc.F` - Instrumented to call validation output routine
- `kpp_output_validation.F` - NEW: Outputs KPP I/O data in CSV format (E25.16 precision when this was written; the current `kpp_mods/kpp_calc.F` prints ES25.16, 17 significant digits, see "Instrumented-file fidelity" below)
- `packages.conf` - Minimal package set for validation
- `FFIELDS.h` included for surface forcing variables

**Documentation**: See `lab_sea/code_validation/README`

### Cross-scheme trees (1DMIX-054): the second scheme on a grid that had only one

Every grid below previously had captures of exactly one mixing scheme. Each new `<scheme>_code_validation/` tree
is the grid's own stock `code/` directory with only the differences listed here (`diff -r <stock code> <tree>` is
the check); `kpp_calc.F`/`kpp_routines.F` (or `ggl90_calc.F`) are symlinks to `kpp_mods/` (`ggl90_mods/`). The
run-input namelists are CONSTRUCTED (no stock MITgcm experiment has them) and live next to each tree in
`<scheme>_input_validation/` with their own README, a run-directory assembly script and the justification of every
non-stock value; the recipes are R7/R8 (`KPP_port_validation/CAPTURES.md`) and G6/G7 (`GGL90_port_validation/CAPTURES.md`).

| tree | differences from the grid's stock `code/` |
|---|---|
| `global_ocean_90x40x15/kpp_code_validation/` | + `kpp_calc.F`, `kpp_routines.F` (symlinks); `packages.conf`: stock line `-kpp` removed (so the `oceanic` group brings kpp in), `ggl90` still compiled (as in stock, run-time off); headers byte-identical; **no** `KPP_OPTIONS.h`, so MITgcm's default applies (`KPP_SMOOTH_SHSQ`, `KPP_SMOOTH_DBLOC`, `KPP_GHAT` defined). (An earlier scaffold carried the ECCO-adjoint `KPP_OPTIONS.h` of `global_oce_latlon/code_validation` with all three undefined, and lacked `GGL90_OPTIONS.h`; both were corrected under 1DMIX-054.) |
| `global_ocean_cs32x15/kpp_code_validation/` | + `kpp_calc.F`, `kpp_routines.F` (symlinks); `packages.conf`: stock list + `kpp`; headers byte-identical; no `KPP_OPTIONS.h`. **Pressure-coordinate grid, KPP has no pressure-coordinate support: known-gap characterization only.** |
| `lab_sea/ggl90_code_validation/` | + `ggl90_calc.F` (symlink); `packages.conf`: + `ggl90` (kpp stays compiled through `oceanic`, run-time off); `SIZE.h`: the single-tile 20x16 edit shared with `lab_sea/code_validation/` (`sNx=20, sNy=16, nSx=nSy=1`; the `MAX_OLy` line also differs from stock by letter case and one blank line, no code effect); other headers byte-identical; **no** `GGL90_OPTIONS.h`, so MITgcm's default applies (no Langmuir, no `GGL90_MISSING_HFAC_BUG`). (An earlier scaffold carried the vermix-era header with `ALLOW_GGL90_LANGMUIR` and `GGL90_MISSING_HFAC_BUG` defined, which differs from the current stock default; it was removed under 1DMIX-054. `1D_ocean_ice_column/ggl90_code_validation/` and `vermix/code_validation/` still carry that older header.) |

## Instrumented-file fidelity to stock MITgcm and print precision (1DMIX-069)

Only three instrumented Fortran sources exist (`ggl90_mods/ggl90_calc.F`,
`kpp_mods/kpp_calc.F`, `kpp_mods/kpp_routines.F`); every per-experiment
`code_validation/`/`kpp_code_validation/`/`ggl90_code_validation/` copy of them is a
symlink, except `1D_ocean_ice_column/code_validation/kpp_routines.F` (a byte-identical
copy of the `kpp_mods` file). They are meant to differ from stock (`pkg/ggl90/`,
`pkg/kpp/` of the MITgcm checkout, audited at d861cd501) only by output
instrumentation: capture arrays, the `GGL90_OUTPUT_VALIDATION` /
`KPP_OUTPUT_VALIDATION` subroutines and their calls, and KPPMIX's existing
`Rib, bfsfc` locals exposed as output arguments. Audit result (1DMIX-069): the only hunk that touched computed values was
`ggl90_calc.F`'s SHELFICE u* block looping `DO i=jMin,jMax` instead of stock's
`DO i=iMin,iMax` -- a transcription error, fixed; the instrumented files now differ
from stock only by output instrumentation (the Langmuir u*/v* arrays are stock's
2-D arrays). To re-audit after any edit:
`diff ~/Projects/MITgcm/pkg/ggl90/ggl90_calc.F ggl90_mods/ggl90_calc.F` (and the two
KPP files) and classify each hunk as output-only or physics; every physics hunk must be
identical to stock or documented here. Headers (`*_OPTIONS.h`, `SIZE.h`, ...) are
build configuration copied from the stock experiment `code/` directories (no
`#define/#undef` differences wherever a stock copy exists).

Print format: every captured field is written with `ES25.16` (17 significant digits,
23 characters including sign and a 3-digit exponent, so it always fits the 25-column
field). Before 1DMIX-069 it was `E25.16` (16 digits), which is not bit-exact for a
double. 1DMIX-070 recaptured every declared capture under `../KPP_port_validation/` and
`../GGL90_port_validation/` with `ES25.16` (see the `CAPTURES.md` files); the earlier
16-digit captures were valid under their limit. The `PARAM_*` scalar lines (previously
`E16.8`, 8 digits) are `ES25.16` as well (1DMIX-070), so runtime constants such as
`GGL90ck=0.1` print as the exact double `1.0000000000000001E-01`. The streaming parsers
read both formats unchanged (a 3-digit exponent prints without the letter E, e.g.
`5.6403554411026415-106`; `scripts/capture_stream.py::ffloat` handles it; the
`float()` in the PARAM parsers needs no such form because no parameter is near 1e+-100).
`kpp_standalone_driver/kpp_standalone_main.F`'s result FORMATs 204/205 are `ES25.16` too
(1DMIX-070); `ggl90_standalone_driver/ggl90_standalone_main.F` has no result FORMAT of its
own: its output is the instrumented `ggl90_calc.F`'s `GGL90_OUTPUT_VALIDATION` write.

## MITgcm Convention

This follows MITgcm's convention of using `code_XXX/` directories for custom code:
- Original code in `verification/<experiment>/code/`
- Custom variants in `code_XXX/` directories
- Specified via `-mods` flag to genmake2/testreport

## Notes

- Custom code should document all changes from MITgcm source
- Include line numbers and file references to original MITgcm code
- Test that modifications don't break compilation or physics
- Keep modifications minimal and well-documented
