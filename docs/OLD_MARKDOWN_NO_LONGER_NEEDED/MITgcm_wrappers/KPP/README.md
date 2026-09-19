# MITgcm KPP Standalone Wrapper

**Status**: 🚧 In Development — Step 1 (Design)

## Purpose

Run MITgcm's Fortran KPP mixing package standalone (without full MITgcm) using the same 1D column inputs as the Python KPP port in `1D_Mixing_Model/KPP/`.

## Goals

1. **Bit-level validation**: Compare MITgcm Fortran KPP against Python port with identical inputs
2. **Fast iteration**: No 5-minute MITgcm compile/run overhead
3. **High precision**: E25.16 output format enabling rtol=1e-12 testing
4. **Input compatibility**: Read same YAML configs as Python implementation

## Architecture

[Pending Step 1 design decision]

## Dependencies

- MITgcm source: `/Users/ifenty/git_repo_others/MITgcm`
- Validation code: `../../mitgcm_verification_mods/lab_sea/code_validation/`
- Python configs: `../../1D_Mixing_Model/configuration_yamls/`

## Usage

[To be determined after implementation]

## Project Structure

```
MITgcm_wrappers/KPP/
├── README.md                  ← This file
├── handoff/                   ← Three Man Team coordination
│   ├── ARCHITECT-BRIEF.md     ← Current step instructions
│   ├── DESIGN-DECISION.md     ← Step 1 deliverable (pending)
│   └── BUILD-LOG.md           ← Step history (pending)
├── src/                       ← Fortran wrapper source (pending)
├── inputs/                    ← Test input files (pending)
└── outputs/                   ← Validation output (pending)
```

## Related Projects

- **1D_Mixing_Model**: Python ports of GGL90 and KPP (`../../1D_Mixing_Model/`)
- **MITgcm_verification_docker**: Docker tools for running full MITgcm experiments (`/Users/ifenty/git_repo_others/MITgcm_verification_docker`)
- **Validation mods**: Instrumented KPP code for output generation (`../../mitgcm_verification_mods/lab_sea/code_validation/`)
