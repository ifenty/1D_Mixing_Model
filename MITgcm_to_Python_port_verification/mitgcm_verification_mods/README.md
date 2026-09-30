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
`../KPP_port_validation/CAPTURES.md` and the two `CONVENTIONS_STANDALONE_DATA.md`.

## Current Experiments

### lab_sea/code_validation

**Purpose**: KPP validation instrumentation for Python port comparison

**Modified Files**:
- `SIZE.h` - Single-processor configuration (nPx=1, nPy=1)
- `kpp_calc.F` - Instrumented to call validation output routine
- `kpp_output_validation.F` - NEW: Outputs KPP I/O data in CSV format (E25.16 precision)
- `packages.conf` - Minimal package set for validation
- `FFIELDS.h` included for surface forcing variables

**Documentation**: See `lab_sea/code_validation/README`

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
