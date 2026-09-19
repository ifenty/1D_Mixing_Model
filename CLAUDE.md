# 1D Ocean Mixing Model - AI Project Context

## Project Overview

This is a **1D column model for ocean vertical mixing** that validates two parameterization schemes:
- **GGL90** (prognostic, TKE-based turbulence closure)
- **KPP** (diagnostic, Richardson-number based boundary layer scheme)

Both schemes are Python ports of MITgcm implementations, designed for bit-level accuracy with the Fortran source.

**Primary Goal**: Validate Python ports against MITgcm reference implementations across physically distinct ocean scenarios (arctic convection, hurricanes, tropical heating, freshwater events, etc.)

**Key Constraint**: These ports must exactly replicate MITgcm physics - any deviation is a bug that needs investigation and fixing.

## Project Structure

```
1D_Mixing_Model/                            # This repo (github.com/ifenty/1D_Mixing_Model)
├── Vertical_Mixing_Models/                   # The Python ports themselves
│   ├── main/                                   # Shared physics, EOS, grid, solvers
│   ├── GGL90/                                  # GGL90 scheme implementation
│   ├── KPP/                                    # KPP scheme implementation
│   ├── configuration_yamls/                    # Physical parameters
│   ├── simulations/scenarios/                  # Per-scenario forcing/IC/time-integration YAMLs
│   ├── tests/                                  # pytest suite
│   └── docs/{GGL90,KPP,dev_notes}/             # Scheme documentation
├── MITgcm_to_Python_port_verification/       # MITgcm-vs-Python validation data/scripts/mods
│   ├── KPP_port_validation/, GGL90_port_validation/  # NetCDF captures + reports (gitignored *.nc)
│   ├── mitgcm_verification_mods/               # Instrumented MITgcm Fortran source
│   └── scripts/, tests/                        # Comparison scripts and root-level MITgcm tests
├── esx/                                       # ESX project configuration and scientific profile
├── docs/                                      # ESX-owned code map, model contract, doc archive
├── open_issues.md / closed_issues.md          # Issue tracking (see below)
└── README.md                                  # User documentation
```

## Agentic workflow

This project uses the **ESX-Team** workflow. Read
[esx/project_instructions.md](esx/project_instructions.md) for the team roles
(Arch coordinates; Bob implements; Richard reviews independently; Scout, Prober,
Bisector, Auditor are bounded specialists) and
[esx/project_profile.md](esx/project_profile.md) for the full scientific,
numerical, evidence and runtime contract for this project. Executable
configuration (source/test paths, verification commands, communication and
commit policy) lives in `esx/project.json`. Do not duplicate that contract
here — this file only orients a fresh session to the project's identity and
where to look next.

Bug/inconsistency tracking with MITgcm now lives in `open_issues.md` /
`closed_issues.md` (ESX issue format), not in a standalone markdown file — see
`devel-loop/issue_priority.md` for how issues are prioritized and
`devel-loop/documentation_contract.md` for the documentation-maintenance rule
that replaces the old "update CLAUDE.md/bug file immediately" instruction.

## Critical files

- [`docs/code_map.md`](docs/code_map.md) — pipeline stages, ownership, nearest tests
- [`docs/model_contract.md`](docs/model_contract.md) — GGL90/KPP equations, EOS, grid/sign conventions, MITgcm correspondence requirement
- `Vertical_Mixing_Models/main/eos.py` — equation of state (JMD95, buoyancy gradients)
- `Vertical_Mixing_Models/main/physics_basis.py` — shared physics functions (N², S², Richardson number)
- `Vertical_Mixing_Models/GGL90/ggl90_core_driver.py` — GGL90 orchestration
- `Vertical_Mixing_Models/KPP/kpp_core_driver.py` — KPP orchestration

## Environment

- **Python**: conda env `ecco` (see `esx/project_profile.md` Runtime section for the exact toolchain probe)
- **MITgcm Source** (for reference): `/Users/ifenty/git_repo_others/MITgcm`
- **Run commands**: see `esx/project.json` (`toolchain_commands`, `verification.*`) — that file is the executable source of truth, not this section

Packet assembly and recovery: `devel-loop/recovery.md` defines exact review
handoffs, read-only readiness, assessed same-session continuation and evidence reuse.
