# Step 5c: Write Port Description Files

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Write two LaTeX documents describing how the Python ports implement the MITgcm Fortran code. Both files must use identical 10-section structure to enable side-by-side comparison.

## Context

- **Step 5b (Package harmonization)**: COMPLETE. Both package_description files now use shared skeleton.
- **Current docs state**: Still contain markdown files that will be removed in Step 5d
- **User directive**: "the other file should be 'port description' which details how the python port implements the mitgcm fortran code"
- **Structural requirement**: Both port_description files must use identical section structure

## Skeleton Structure

See: `handoff/STEP-5C-PORT-DESCRIPTION-SKELETON.md`

**10 sections**:
1. Introduction and Scope
2. Development History and Bug Fixes
3. File Organization and Module Structure
4. Coordinate System and Sign Conventions
5. Core Algorithm Implementation
6. Numerical Methods and Time-Stepping
7. Parameter Handling and Configuration
8. Integration with Model Driver
9. Testing and Validation
10. Usage Examples and Workflows

## File Operations

### Output Files
```
docs/GGL90/GGL90_port_description.tex  (NEW, ~600-1,000 lines)
docs/KPP/KPP_port_description.tex      (NEW, ~600-1,000 lines)
```

### Source Material
```
GGL90:
- docs/GGL90/05_PYTHON_IMPLEMENTATION_NOTES.md (411 lines)
- GGL90_ML/GGL90_PY/*.py (code reading)
- /Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/ (comparison)

KPP:
- KPP_ML/KPP_PY/*.py (code reading - no existing markdown notes)
- /Users/ifenty/git_repo_others/MITgcm/pkg/kpp/ (comparison)
```

### No Deletions (Step 5d handles markdown cleanup)

## Detailed Instructions

### Phase 1: GGL90_port_description.tex

1. **Read source materials**:
   - Complete `docs/GGL90/05_PYTHON_IMPLEMENTATION_NOTES.md`
   - Browse `GGL90_ML/GGL90_PY/` directory structure
   - Skim key MITgcm files for comparison context

2. **Write GGL90_port_description.tex** following 10-section skeleton:
   - **§1 Introduction**: Explain Python port purpose, 1D column model scope, target users
   - **§2 History/Bugs**: Extract from implementation notes:
     - N² sign convention fix (Fix 1)
     - Z-coordinate double-negation fix (Fix 2)
     - Pressure coordinate fix (Fix 3)
     - Static instability mask implementation
     - Include before/after code snippets
   - **§3 File Organization**: Map Python modules to MITgcm Fortran files
   - **§4 Coordinates/Conventions**: Depth vs z, sign conventions, MITgcm comparison
   - **§5 Core Algorithm**: How `ggl90_core.py` implements `ggl90_calc.F`
   - **§6 Numerical Methods**: Implicit TKE solver, stability, comparison to MITgcm
   - **§7 Parameters**: YAML system, default vs ECCOv4 parameter sets
   - **§8 Integration**: Mixing adapter, unified driver architecture
   - **§9 Testing**: Unit tests, scenario validation, MITgcm comparison status
   - **§10 Usage**: Command-line examples, workflow recipes

3. **Include code snippets** showing key MITgcm → Python translations

### Phase 2: KPP_port_description.tex

4. **Read source materials**:
   - Browse `KPP_ML/KPP_PY/` directory structure
   - Map to MITgcm files in `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
   - Identify key algorithm translations

5. **Write KPP_port_description.tex** following **same 10-section skeleton**:
   - **§1 Introduction**: KPP port purpose, diagnostic nature, scope
   - **§2 History/Bugs**: Development timeline, any bug fixes (if known), validation milestones
   - **§3 File Organization**: Map Python modules to MITgcm Fortran files:
     - `kpp_core.py` → `kpp_calc.F`
     - `kpp_routines.py` → `kpp_routines.F`, `kpp_mix.F`
     - Parameter files, forcing modules
   - **§4 Coordinates/Conventions**: Same coordinate system as GGL90 port, any KPP-specific conventions
   - **§5 Core Algorithm**: How Python implements:
     - Boundary layer depth calculation (`kpp_calc.F`, `kpp_depth_smooth.F`)
     - Interior Ri mixing
     - Surface layer scaling (w*, u*)
     - Shape functions (cubic profiles)
   - **§6 Numerical Methods**: Diagnostic recomputation each timestep, no state persistence
   - **§7 Parameters**: YAML system, default parameter sets, tuning options
   - **§8 Integration**: Same mixing adapter interface as GGL90
   - **§9 Testing**: Unit tests, scenario validation, comparison to MITgcm/GGL90
   - **§10 Usage**: Same workflow as GGL90 (scheme flag difference)

6. **Include code snippets** showing key KPP algorithm translations

### Phase 3: LaTeX Quality Check

7. **Verify both files**:
   - Identical section numbering (§1-§10)
   - Identical section titles
   - Consistent LaTeX style (equations, code listings, cross-references)
   - No TODO/FIXME placeholders
   - All code snippets properly formatted

8. **Compile test** (if LaTeX available):
   - Check both PDFs render correctly
   - Verify table of contents
   - Check code listing syntax highlighting

## LaTeX Style Guide

- Document class: `\documentclass[11pt]{article}`
- Packages: `amsmath`, `listings`, `hyperref`, `graphicx`, `booktabs`
- Code listings:
  ```latex
  \begin{lstlisting}[language=Python, caption={Description}]
  # Python code here
  \end{lstlisting}
  
  \begin{lstlisting}[language=Fortran, caption={MITgcm comparison}]
  C Fortran code here
  \end{lstlisting}
  ```
- File paths: `\verb|path/to/file.py|` or `\texttt{path/to/file.py}`
- Cross-references: `\label{sec:foo}`, `\ref{sec:foo}`
- Emphasis: `\textbf{bold}`, `\textit{italic}`, `\texttt{code}`

## Key Content Requirements

### GGL90 (from implementation notes)

**Critical bugs to document**:
1. **N² sign fix** (lines 69-91 of implementation notes):
   ```python
   # BEFORE (WRONG):
   N_squared = (g / rho0) * drho_dz
   
   # AFTER (CORRECT):
   N_squared = -(g / rho0) * drho_dz
   ```

2. **Z-coordinate fix** (lines 93-122):
   - `z_positive_up` property double-negation
   - Already-correct depth values getting inverted

3. **Pressure coordinate fix** (lines 124-163):
   - Absolute vs gauge pressure
   - Reference pressure subtraction

4. **Static instability mask** (lines 165-205):
   - Implementation details
   - Comparison to MITgcm approach

### KPP (from code + MITgcm)

**Key algorithms to document**:
1. **Boundary layer depth** (`kpp_calc.F`):
   - Bulk Richardson number criterion
   - Smoothing algorithm
   - Depth limiting

2. **Interior mixing** (`ri_iwmix.F`):
   - Richardson number-based diffusivity
   - Internal wave background mixing

3. **Surface forcing** (`kpp_forcing_surf.F`):
   - Surface buoyancy flux
   - Friction velocity (u*)
   - Convective velocity (w*)

4. **Diffusivity assembly** (`kpp_mix.F`, `kpp_transport_*.F`):
   - Shape functions (cubic polynomials)
   - Enhanced diffusivity in surface layer
   - Tracer vs momentum differences

## Validation Checklist for Richard

- [ ] Both files use identical 10-section structure
- [ ] Section titles match exactly between files
- [ ] GGL90 documents all 4 bug fixes from implementation notes
- [ ] KPP documents diagnostic nature and no state persistence
- [ ] Code snippets properly formatted (Python + Fortran)
- [ ] File paths accurate and resolvable
- [ ] MITgcm comparisons technically correct
- [ ] No TODO/FIXME placeholders
- [ ] LaTeX compiles without errors (if testable)
- [ ] Both files 15-25 pages (600-1,000 lines LaTeX estimated)

## Git Commands

```bash
# After Richard approval
git add docs/GGL90/GGL90_port_description.tex docs/KPP/KPP_port_description.tex
git commit -m "Step 5c: Write port_description files for GGL90 and KPP

- Both files use identical 10-section structure
- GGL90: Document N² sign fix, z-coordinate fix, pressure fix, static instability
- KPP: Document diagnostic nature, boundary layer depth, Ri mixing, shape functions
- Include code snippets showing MITgcm → Python translations
- Source: GGL90 implementation notes + code reading for both schemes
- Verified against MITgcm pkg/ggl90/ and pkg/kpp/ source

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# DO NOT PUSH (await PO gate)
```

## Success Criteria

- Two new .tex files created with identical section structure
- GGL90 file comprehensively documents Python port implementation and bug fixes
- KPP file comprehensively documents Python port implementation from code reading
- User can open both files side-by-side and see matching §1-§10
- Technical depth sufficient for someone porting to another framework
- Code snippets show clear MITgcm → Python translations
- Zero LaTeX compilation errors (Richard verification)

## References

- Skeleton definition: `handoff/STEP-5C-PORT-DESCRIPTION-SKELETON.md`
- GGL90 implementation notes: `docs/GGL90/05_PYTHON_IMPLEMENTATION_NOTES.md`
- GGL90 Python code: `GGL90_ML/GGL90_PY/`
- KPP Python code: `KPP_ML/KPP_PY/`
- MITgcm GGL90 source: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
- MITgcm KPP source: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`

---

**Builder (Bob)**: Execute Phases 1-3, deliver both tex files to Richard.  
**Reviewer (Richard)**: Validate checklist, verify structure consistency, verify technical accuracy, approve for commit.  
**Architect (Arch)**: Launch Bob, monitor progress, coordinate Richard review, obtain PO deploy gate.
