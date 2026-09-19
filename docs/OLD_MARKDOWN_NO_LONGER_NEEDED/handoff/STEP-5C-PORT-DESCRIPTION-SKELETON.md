# Step 5c: Port Description Skeleton

**Date**: 2026-08-11  
**Purpose**: Define shared section structure for `*_port_description.tex` files

## Mission

Both `GGL90_port_description.tex` and `KPP_port_description.tex` must share **identical section structure** to enable side-by-side comparison of how the Python ports implement the MITgcm Fortran code.

## Shared Section Structure (10 sections)

1. **Introduction and Scope**
   - Purpose of the Python port
   - Relationship to MITgcm Fortran implementation
   - Target use cases (research, validation, training data generation)
   - Directory structure overview

2. **Development History and Bug Fixes**
   - Timeline of development
   - Critical bug fixes with before/after code
   - Validation milestones
   - Current status

3. **File Organization and Module Structure**
   - Core physics modules
   - Parameter handling
   - Configuration files (YAML)
   - Integration with main driver

4. **Coordinate System and Sign Conventions**
   - Vertical coordinate system (depth vs z)
   - Sign conventions for gradients, fluxes
   - Comparison to MITgcm conventions
   - Translation layer if different

5. **Core Algorithm Implementation**
   - Main driver function (equivalent to *_calc.F)
   - Physics computations
   - Comparison to MITgcm Fortran line-by-line
   - Key algorithmic differences (if any)

6. **Numerical Methods and Time-Stepping**
   - Time-stepping scheme (implicit/explicit)
   - Solver implementation
   - Stability considerations
   - Comparison to MITgcm approach

7. **Parameter Handling and Configuration**
   - YAML configuration system
   - Default parameter sets
   - ECCOv4 configuration (GGL90 only)
   - Parameter validation

8. **Integration with Model Driver**
   - Unified driver architecture
   - Mixing adapter interface
   - Diagnostics integration
   - Scenario runner

9. **Testing and Validation**
   - Unit test suite
   - Scenario-based validation
   - Comparison to MITgcm output
   - Known limitations

10. **Usage Examples and Workflows**
    - Running single experiments
    - Batch scenario execution
    - Custom configuration
    - Common workflows

## Content Guidance

### For GGL90_port_description.tex
**Primary sources**:
- `docs/GGL90/05_PYTHON_IMPLEMENTATION_NOTES.md` (411 lines) - comprehensive port notes
- Code reading: `GGL90_ML/GGL90_PY/` directory
- MITgcm comparison: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`

**Key content to include**:
- N² sign convention bug fix (Fix 1 in notes)
- Z-coordinate double-negation fix (Fix 2)
- Pressure coordinate handling (Fix 3)
- Static instability mask implementation
- Implicit TKE diffusion solver
- ECCOv4 parameter set

### For KPP_port_description.tex
**Primary sources**:
- Code reading: `KPP_ML/KPP_PY/` directory (no existing markdown port notes)
- MITgcm comparison: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`

**Key content to include**:
- Diagnostic (non-prognostic) implementation
- Boundary layer depth calculation
- Interior/internal wave mixing
- Double diffusion implementation
- Ri-based mixing
- Shape functions (cubic polynomial profiles)

## Length Target

- **Each file**: 15-25 pages (roughly 600-1,000 lines LaTeX)
- **Depth**: Technical but accessible; include code snippets showing key translations
- **Balance**: Enough detail for someone porting to another framework, not line-by-line commentary

## LaTeX Structure Template

```latex
\documentclass[11pt]{article}
\usepackage{amsmath, listings, hyperref, graphicx}

\title{[SCHEME] Python Port Description:\\
       Implementation of MITgcm [Package] in 1D Column Model}
\author{Python Port Development Team}
\date{\today}

\begin{document}
\maketitle
\tableofcontents
\newpage

\section{Introduction and Scope}
...

\section{Development History and Bug Fixes}
...

[... sections 3-10 ...]

\end{document}
```

## Notes

- Both files written in **single Step 5c task** to ensure structural consistency
- After Step 5c, only 2 .tex files remain per scheme directory
- Step 5d then removes all markdown files
- End state: `docs/GGL90/{GGL90_package_description.tex, GGL90_port_description.tex}`
- End state: `docs/KPP/{KPP_package_description.tex, KPP_port_description.tex}`

## Success Criteria

- Both files use identical 10-section structure
- User can open side-by-side and see matching sections
- GGL90 leverages existing implementation notes
- KPP written from code reading + MITgcm comparison
- Technical depth sufficient for port developers
- Code snippets show MITgcm → Python translations
