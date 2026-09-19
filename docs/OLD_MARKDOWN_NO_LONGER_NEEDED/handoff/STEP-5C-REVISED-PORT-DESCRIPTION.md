# Step 5c-REVISED: Rewrite Port Description Files

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Rewrite both port_description files to be **reference documents** that show where different capabilities of the original Fortran are now present in the Python ports. Organize by code flow, provide file + line number mappings for each major step.

## User Requirements (2026-08-11)

> "What I want are reference documents that show where different capabilities of the original fortran are now present in the python ports. I don't want to include information about the development of the ports (no need to go through the history of how the ports were developed or which bugs were found along the way). Organize the files by considering the flow of each package. For each major step in the ported mixing routine, tell the user where that step is handled in the ported code and where in the original fortran that step is handled. When describing the python ported codes and the fortran codes, use filenames and line numbers."

## What to EXCLUDE

- ❌ Development history
- ❌ Bug fix chronology
- ❌ Testing/validation details
- ❌ Usage examples
- ❌ Workflow recipes
- ❌ Parameter tuning guidance

## What to INCLUDE

- ✅ Code flow through the mixing routine
- ✅ Major computational steps
- ✅ Python file + line numbers for each step
- ✅ Fortran file + line numbers for each step
- ✅ Clear mapping: "This Python code at X:line_Y implements Fortran at Z:line_W"
- ✅ Enough detail for user to trace original Fortran → Python

## New Structure (Code-Flow Based)

### Common Structure for Both Files

```
1. Introduction
   - Purpose of this document (reference mapping)
   - Scope of the port (1D column model)
   - How to use this document

2. Overview of Code Flow
   - High-level algorithm flowchart
   - Main entry point
   - Calling sequence

3. Step-by-Step Code Mapping
   [For each major step in the mixing calculation:]
   
   3.X Step Name
       - What this step computes
       - Python implementation:
         - File: path/to/file.py
         - Lines: XXX-YYY
         - Key functions/classes
       - Fortran source:
         - File: pkg/[scheme]/file.F
         - Lines: XXX-YYY
         - Subroutine name
       - [Optional code snippet showing the mapping]

4. Supporting Infrastructure
   - Parameter handling (Python vs Fortran)
   - Grid/coordinate system
   - Physical constants
   - Boundary conditions

5. File-to-File Correspondence Table
   - Complete mapping of Python modules ↔ Fortran files

6. Quick Reference: Key Variables
   - Variable name mappings
   - Unit conversions (if any)
   - Sign convention differences (if any)
```

## GGL90 Port Description Structure

**Section 3 major steps** (organized by GGL90 algorithm flow):

1. **Parameter Initialization**
   - Python: `GGL90_ML/GGL90_PY/ggl90_parameters.py`
   - Fortran: `pkg/ggl90/ggl90_readparms.F`, `pkg/ggl90/ggl90_init_fixed.F`

2. **Stratification and Shear Calculation**
   - Python: `GGL90_ML/GGL90_PY/ggl90_core.py::compute_buoyancy_frequency_squared()`, `compute_shear_squared()`
   - Fortran: `pkg/ggl90/ggl90_calc.F` (lines computing N², S²)

3. **Mixing Length Calculation**
   - Python: `GGL90_ML/GGL90_PY/ggl90_core.py::compute_mixing_length()`
   - Fortran: `pkg/ggl90/ggl90_calc.F::GGL90_MIXINGLENGTH()`

4. **TKE Evolution (Prognostic Step)**
   - Python: `GGL90_ML/GGL90_PY/ggl90_core.py::solve_tke_implicit()`
   - Fortran: `pkg/ggl90/ggl90_calc.F` (TKE time-stepping, implicit solve)

5. **Eddy Diffusivity Calculation**
   - Python: `GGL90_ML/GGL90_PY/ggl90_core.py::compute_eddy_coefficients()`
   - Fortran: `pkg/ggl90/ggl90_calc.F` (κₑ = √TKE × ℓ)

6. **Boundary Conditions**
   - Surface TKE forcing
   - Bottom boundary handling
   - Python: boundary condition logic in `ggl90_core.py`
   - Fortran: boundary condition sections in `ggl90_calc.F`

7. **Static Instability Handling**
   - Python: `main/convective_adjustment.py` (ivdc_kappa)
   - Fortran: `pkg/ggl90/ggl90_calc.F` (convective adjustment integration)

## KPP Port Description Structure

**Section 3 major steps** (organized by KPP algorithm flow):

1. **Parameter Initialization**
   - Python: `KPP_ML/KPP_PY/kpp_parameters.py`
   - Fortran: `pkg/kpp/kpp_readparms.F`, `pkg/kpp/kpp_init_fixed.F`

2. **Density and Buoyancy Calculation**
   - Python: `KPP_ML/KPP_PY/kpp_core.py` (density/buoyancy)
   - Fortran: `pkg/kpp/kpp_calc.F::STATEKPP()`

3. **Boundary Layer Depth Diagnosis**
   - Bulk Richardson criterion
   - Python: `KPP_ML/KPP_PY/kpp_core.py::compute_boundary_layer_depth()`
   - Fortran: `pkg/kpp/kpp_calc.F` (hbl calculation), `pkg/kpp/kpp_depth_smooth.F`

4. **Surface Forcing Calculation**
   - Surface buoyancy flux, friction velocity
   - Python: `KPP_ML/KPP_PY/kpp_core.py::compute_surface_forcing()`
   - Fortran: `pkg/kpp/kpp_calc.F::KPP_FORCING_SURF()`

5. **Interior Richardson Mixing**
   - Ri-based diffusivity
   - Python: `KPP_ML/KPP_PY/kpp_core.py::compute_interior_mixing()`
   - Fortran: `pkg/kpp/kpp_calc.F::RI_IWMIX()`

6. **Boundary Layer Mixing (Shape Functions)**
   - Cubic polynomial profiles
   - Python: `KPP_ML/KPP_PY/kpp_core.py::compute_boundary_layer_mixing()`
   - Fortran: `pkg/kpp/kpp_calc.F::BLMIX()`, `pkg/kpp/kpp_mix.F`

7. **Nonlocal Transport**
   - Counter-gradient term
   - Python: `KPP_ML/KPP_PY/kpp_core.py::compute_nonlocal_transport()`
   - Fortran: `pkg/kpp/kpp_calc.F` (nonlocal term)

8. **Diffusivity Assembly**
   - Combining interior + boundary layer
   - Python: `KPP_ML/KPP_PY/kpp_core.py::assemble_diffusivities()`
   - Fortran: `pkg/kpp/kpp_mix.F::KPPMIX()`

9. **Double Diffusion (if enabled)**
   - Python: `KPP_ML/KPP_PY/kpp_core.py` (double diffusion logic)
   - Fortran: `pkg/kpp/kpp_calc.F` (double diffusion)

## File Operations

### Overwrite Existing Files
```
docs/GGL90/GGL90_port_description.tex  (REWRITE, target ~800-1200 lines)
docs/KPP/KPP_port_description.tex      (REWRITE, target ~900-1300 lines)
```

## Detailed Instructions

### Phase 1: GGL90_port_description.tex

1. **Read source code** to trace algorithm flow:
   - Python: Browse `GGL90_ML/GGL90_PY/ggl90_core.py`, `ggl90_parameters.py`
   - Fortran: Read `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ggl90_calc.F`
   - Identify line numbers for each major step

2. **Write new GGL90_port_description.tex**:
   - §1 Introduction: Purpose (reference mapping), how to use this document
   - §2 Overview: Algorithm flowchart, main entry point (`ggl90_core_driver()` in Python, `GGL90_CALC()` in Fortran)
   - §3 Step-by-Step Mapping: 7 subsections following GGL90 flow above
   - §4 Supporting Infrastructure: Parameters, grid, constants, boundary conditions
   - §5 File-to-File Table: Complete Python ↔ Fortran mapping
   - §6 Quick Reference: Variable names, units, sign conventions

3. **For each step in §3**, provide:
   - Brief description of what's computed
   - Python location: `file.py::function_name()` with line numbers
   - Fortran location: `file.F::SUBROUTINE_NAME()` with line numbers
   - Optional: minimal code snippet showing key equations

### Phase 2: KPP_port_description.tex

4. **Read source code** to trace algorithm flow:
   - Python: Browse `KPP_ML/KPP_PY/kpp_core.py`, `kpp_parameters.py`
   - Fortran: Read `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/kpp_calc.F`, `kpp_routines.F`, `kpp_mix.F`
   - Identify line numbers for each major step

5. **Write new KPP_port_description.tex**:
   - §1 Introduction: Purpose (reference mapping), how to use this document
   - §2 Overview: Algorithm flowchart, main entry point (`kpp_core_driver()` in Python, `KPP_CALC()` in Fortran)
   - §3 Step-by-Step Mapping: 9 subsections following KPP flow above
   - §4 Supporting Infrastructure: Parameters, grid, constants, boundary conditions
   - §5 File-to-File Table: Complete Python ↔ Fortran mapping
   - §6 Quick Reference: Variable names, units, sign conventions

6. **For each step in §3**, provide:
   - Brief description of what's computed
   - Python location: `file.py::function_name()` with line numbers
   - Fortran location: `file.F::SUBROUTINE_NAME()` with line numbers
   - Optional: minimal code snippet showing key equations

### Phase 3: Line Number Accuracy

7. **Verify all line numbers** by reading the actual source files:
   - Use `grep -n` to find exact line numbers
   - Python: Check current code in repo
   - Fortran: Check MITgcm source at `/Users/ifenty/git_repo_others/MITgcm/pkg/`
   - If code spans many lines, provide range (e.g., "lines 245-289")

8. **Create file-to-file correspondence tables** (§5 in both files):
   ```latex
   \begin{table}[h]
   \centering
   \begin{tabular}{ll}
   \toprule
   \textbf{Python Module} & \textbf{MITgcm Fortran File} \\
   \midrule
   ggl90_core.py & pkg/ggl90/ggl90_calc.F \\
   ggl90_parameters.py & pkg/ggl90/ggl90_readparms.F, GGL90.h \\
   ... & ... \\
   \bottomrule
   \end{tabular}
   \end{table}
   ```

## LaTeX Style

- Document class: `\documentclass[11pt]{article}`
- Title: `[SCHEME] Python Port Reference: Code Flow and Fortran-to-Python Mapping`
- Code references: `\verb|file.py::function()| (lines 123-145)`
- File paths: `\texttt{path/to/file}`
- Minimal code snippets only when clarifying the mapping
- Focus on **references** (file:line), not extensive code reproduction

## Example Section Structure

```latex
\subsection{Mixing Length Calculation}

\textbf{Purpose}: Compute the turbulent mixing length scale $\ell$ based on TKE, stratification, and distance from boundaries.

\textbf{Python Implementation}:
\begin{itemize}
\item File: \verb|GGL90_ML/GGL90_PY/ggl90_core.py|
\item Function: \verb|compute_mixing_length()| (lines 345-412)
\item Called from: \verb|ggl90_core_driver()| (line 156)
\end{itemize}

\textbf{Fortran Source}:
\begin{itemize}
\item File: \verb|pkg/ggl90/ggl90_calc.F|
\item Subroutine: \verb|GGL90_MIXINGLENGTH()| (lines 687-894)
\item Called from: \verb|GGL90_CALC()| (line 234)
\end{itemize}

\textbf{Key Computation}:
The mixing length is computed using Eq.~(2.3) in \cite{Gaspar1990} with limiting by distance to surface/bottom. Python implements the same formula with identical logic for Method 1 vs Method 2 (controlled by \verb|mxlSurfFlag|).

\textbf{Implementation Notes}:
\begin{itemize}
\item Both implementations use the same $\alpha$ (turbulent Prandtl number) parameter
\item Minimum length scale \verb|GGL90mixingLengthMin| applied identically
\item Surface mixed layer depth handling matches MITgcm's Method 1/2 switch
\end{itemize}
```

## Validation Checklist for Richard

- [ ] Both files rewritten with code-flow organization
- [ ] NO development history, bug fixes, or testing sections
- [ ] All major algorithm steps covered for each scheme
- [ ] Every step has Python file + line numbers
- [ ] Every step has Fortran file + line numbers
- [ ] File-to-file correspondence tables complete
- [ ] Variable name mapping tables present
- [ ] Line numbers verified accurate against current code
- [ ] Documents serve as reference for tracing Fortran → Python
- [ ] LaTeX compiles without errors

## Git Commands

```bash
# After Richard approval
git add docs/GGL90/GGL90_port_description.tex docs/KPP/KPP_port_description.tex
git commit -m "Rewrite port_description files as Fortran→Python reference maps

- Reorganize by code flow (major computational steps)
- Remove development history, bug fixes, testing details
- Add file + line number references for each step
- GGL90: 7-step flow (stratification → TKE evolution → eddy coeffs)
- KPP: 9-step flow (BL depth → interior mixing → assembly)
- Include file-to-file correspondence tables
- Include variable name mapping tables
- Documents now serve as reference for tracing original Fortran

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# DO NOT PUSH (await PO gate)
```

## Success Criteria

- Both files organized by code flow, not development history
- User can look up any major mixing step and find:
  - Where it lives in Python (file:lines)
  - Where it came from in Fortran (file:lines)
- Clear reference documents for understanding the port
- Enough detail to trace Fortran → Python without excessive line-by-line commentary
- File-to-file and variable-to-variable mapping tables complete

## References

- GGL90 Python code: `GGL90_ML/GGL90_PY/`
- KPP Python code: `KPP_ML/KPP_PY/`
- MITgcm GGL90 source: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
- MITgcm KPP source: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
- User directive (2026-08-11): "reference documents that show where different capabilities of the original fortran are now present in the python ports"

---

**Builder (Bob)**: Execute Phases 1-3, rewrite both files, deliver to Richard.  
**Reviewer (Richard)**: Verify line numbers accurate, check mapping completeness, approve for commit.  
**Architect (Arch)**: Launch Bob, coordinate Richard review, obtain PO deploy gate.
