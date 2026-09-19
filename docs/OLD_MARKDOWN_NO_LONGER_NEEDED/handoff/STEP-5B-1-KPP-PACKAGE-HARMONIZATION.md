# Step 5b-1: KPP package_description Harmonization

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Restructure `docs/KPP/KPP_package_description.tex` to match the approved shared skeleton (19 sections + 3 appendices), fold unique content from `docs/KPP/KPP_Report.tex`, and write new content where KPP currently has gaps. End state: KPP documentation uses identical organizational structure to GGL90, enabling side-by-side comparison.

## Context

- **Step 4 (Reorganization)**: COMPLETE. Repository now has clean docs/{GGL90,KPP,dev_notes} structure.
- **Step 5a (α-minimum verification)**: COMPLETE. GGL90_package_description.tex §3.8.6 now has verified metrics.
- **Shared skeleton**: Approved by PO (`handoff/DOC-SKELETON.md`). 19 main sections + 3 appendices.
- **User directive**: "the kpp and ggl subdirectories should be essentially mirror images of each other in terms of structure"
- **Critical clarification**: ECCOv4 uses GGL90, NOT KPP → **SKIP Appendix B (ECCOv4 Config) for KPP**

## Approved Skeleton Structure

### Main Sections (1-19)
1. Introduction and Scientific Background
2. Governing Equations (overview)
3. Package Architecture and Call Flow
4. Parameter Initialization
5. Main Driver Routine
6. Stratification and Buoyancy
7. Surface Forcing
8. Interior Mixing
9. Boundary / Surface Layer Mixing
10. Core Diffusivity/Prognostic Update
11. Additional Mixing Processes
12. Eddy Coefficients and Model Interface
13. Initialization and Restart
14. Compile-Time Options
15. Output and Diagnostics
16. Package Validation
17. Numerical Considerations & Frequently Encountered Issues
18. Conclusions
19. Glossary of Symbols

### Appendices
- **Appendix A**: Complete Input/Output Mapping
- **Appendix B**: ECCOv4 Configuration ← **SKIP FOR KPP** (ECCOv4 uses GGL90)
- **Appendix C**: Adjoint Model Considerations ← **NEW CONTENT REQUIRED**

## File Operations

### Input Files
```
docs/KPP/KPP_package_description.tex  (2,215 lines) - restructure to skeleton
docs/KPP/KPP_Report.tex              (896 lines)  - fold content in, then DELETE
docs/KPP/1D_ML_draft.tex             (898 lines)  - move to docs/ML/
```

### Output Files
```
docs/KPP/KPP_package_description.tex  (restructured, ~2,800-3,200 lines estimated)
docs/ML/1D_ML_draft.tex               (moved, unchanged)
```

### Deletions
```
docs/KPP/KPP_Report.tex  (DELETE after content folded)
```

## Detailed Instructions

### Phase 1: Read and Map Existing Content

1. **Read all three input files** to understand what content exists:
   - `docs/KPP/KPP_package_description.tex` (current main doc)
   - `docs/KPP/KPP_Report.tex` (may contain unique analysis/validation)
   - `docs/KPP/1D_ML_draft.tex` (ML-specific, will be moved out)

2. **Create content mapping table** showing:
   - Which skeleton section each existing paragraph/subsection belongs in
   - Which content from KPP_Report.tex needs to be folded in
   - Which sections need NEW content written

### Phase 2: Restructure KPP_package_description.tex

3. **Rewrite KPP_package_description.tex with the approved skeleton**:
   - Use the exact 19-section + 3-appendix structure from DOC-SKELETON.md
   - Redistribute existing content from old sections into new skeleton sections
   - Preserve ALL existing physics content, equations, code listings, tables, figures
   - Add `\section` and `\subsection` commands to match skeleton hierarchy
   - Maintain LaTeX quality: proper math mode, citations, code listings, cross-references

4. **Fold content from KPP_Report.tex**:
   - Identify any validation results, analysis, or insights unique to KPP_Report.tex
   - Integrate this content into appropriate skeleton sections (likely §6-10, §15, §17)
   - Do NOT duplicate content already in package_description.tex
   - Preserve figure/table references if folding figures/tables

### Phase 3: Write New Content for KPP Gaps

5. **§13 Initialization and Restart** (USER-SPECIFIED CONTENT):
   Write that KPP is **diagnostic, not prognostic**. Must explain:
   - **What "diagnostic" means**: All mixing coefficients (diffusivities, viscosities) are recomputed from the instantaneous ocean state each time step
   - **No state persistence**: There is NO previous KPP state that carries from one time step to the next
   - **No pickup files**: Unlike GGL90 (which carries prognostic TKE in pickup files), KPP has no pickup/restart field
   - **Initialization**: KPP initialization only sets runtime parameters; ocean state (T, S, U, V) comes from model initialization
   - Keep concise (1-2 paragraphs), contrast with prognostic schemes (like GGL90) briefly

6. **Appendix C: Adjoint Model Considerations** (NEW CONTENT REQUIRED):
   Research and document:
   - **Primary source**: MITgcm KPP adjoint source files in `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
   - Look for files matching pattern `*_ad.F`, `*_ad.flow`, `kpp_ad_*`, or adjoint-specific comments
   - **Content to cover**:
     - Whether KPP has full adjoint support in MITgcm (TAF-generated or hand-coded)
     - Key adjoint considerations for KPP (e.g., non-smoothness at boundary layer depth, implicit solver adjoint)
     - Any KPP-specific adjoint limitations or requirements
     - Active/passive variable handling
   - If adjoint files are minimal/absent, state that honestly and explain what exists
   - **Length target**: 1-2 pages (similar depth to GGL90's appendix if it exists)

7. **Appendix B: ECCOv4 Configuration** ← **DO NOT WRITE**:
   - PO confirmed: "eccov4 doesn't use kpp, so no appendix for kpp ecco v4 in the kpp document"
   - The skeleton shows this appendix, but KPP skips it
   - Appendix numbering: A (I/O Mapping), ~~B (ECCOv4)~~, C (Adjoint) → becomes A, C only for KPP

### Phase 4: File Cleanup

8. **Move 1D_ML_draft.tex**:
   ```bash
   mkdir -p docs/ML
   git mv docs/KPP/1D_ML_draft.tex docs/ML/1D_ML_draft.tex
   ```

9. **Delete KPP_Report.tex** after verifying all unique content has been folded:
   ```bash
   git rm docs/KPP/KPP_Report.tex
   ```

### Phase 5: Technical Verification

10. **Verify against MITgcm KPP source**:
    - Source location: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
    - Key files to reference:
      - `kpp_calc.F` (main driver)
      - `kpp_routines.F` (mixing computations)
      - `kpp_forcing_surf.F` (surface forcing)
      - `kpp_mix.F` (diffusivity assembly)
      - `kpp_transport_*.F` (transport/interface)
      - `KPP_OPTIONS.h` (compile-time flags)
      - `KPP_PARAMS.h` (parameters)
    - Ensure all code snippets, parameter names, equation references are accurate
    - Flag any discrepancies between doc and source for Richard to review

11. **Preserve existing content depth**:
    - Do NOT pad sections with filler text
    - Do NOT invent physics details not in MITgcm source
    - If KPP has less to say in a section than GGL90, that's fine (per PO: "content depth may differ")
    - Short sections (1-2 paragraphs) are acceptable where appropriate

## LaTeX Style Guide

- Use `\section{}`, `\subsection{}`, `\subsubsection{}` for hierarchy
- Math in `\[ ... \]` (display) or `$...$` (inline)
- Code listings: `\begin{lstlisting}[language=Fortran, caption={...}] ... \end{lstlisting}`
- Citations: `\citep{author_year}` or `\citet{author_year}`
- Cross-references: `\label{sec:foo}` and `\ref{sec:foo}`
- Tables: `\begin{table}...\begin{tabular}...\end{tabular}\end{table}` with `\toprule`, `\midrule`, `\bottomrule`
- Figures: `\begin{figure}...\includegraphics{...}...\end{figure}`
- Glossary: `\textbf{Symbol}` & Description format
- Appendices: `\appendix` then `\section{Appendix Title}`

## Validation Checklist for Richard

- [ ] All 19 main sections present in KPP_package_description.tex
- [ ] Appendix A (I/O Mapping) present
- [ ] Appendix C (Adjoint) present with substantive content (not placeholder)
- [ ] Appendix B (ECCOv4) correctly OMITTED
- [ ] §13 (Init/Restart) explains diagnostic nature per user specification
- [ ] All existing KPP physics content preserved (no loss of equations, tables, figures)
- [ ] Unique content from KPP_Report.tex successfully folded in
- [ ] 1D_ML_draft.tex moved to docs/ML/ (git mv with history preserved)
- [ ] KPP_Report.tex deleted (git rm)
- [ ] Code snippets verified against MITgcm source in `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
- [ ] LaTeX compiles without errors (if testable)
- [ ] No TODO, FIXME, or placeholder comments left in final tex
- [ ] Cross-references, citations, labels all functional

## Git Commands

```bash
# Phase 4 file operations
mkdir -p docs/ML
git mv docs/KPP/1D_ML_draft.tex docs/ML/1D_ML_draft.tex
git rm docs/KPP/KPP_Report.tex

# After Richard approval
git add docs/KPP/KPP_package_description.tex docs/ML/
git commit -m "Step 5b-1: Harmonize KPP package_description to shared skeleton

- Restructure to 19 sections + 3 appendices (skip B per PO)
- Fold unique content from KPP_Report.tex (now deleted)
- Write §13 Init/Restart (diagnostic vs prognostic explanation)
- Write Appendix C (Adjoint Model Considerations)
- Move 1D_ML_draft.tex to docs/ML/
- Verified against MITgcm pkg/kpp/ source"

# DO NOT PUSH (await PO gate)
```

## Success Criteria

- KPP_package_description.tex uses identical section structure to skeleton
- User can open KPP and GGL90 package_description files side-by-side and see matching §1-19 + appendices
- All existing KPP physics content preserved at current depth
- New §13 (Init/Restart) and Appendix C (Adjoint) written with accurate technical content
- KPP_Report.tex content folded in and file deleted
- 1D_ML_draft.tex cleanly moved to docs/ML/
- Zero regressions in documentation accuracy (Richard verification)

## References

- Shared skeleton: `handoff/DOC-SKELETON.md`
- MITgcm KPP source: `/Users/ifenty/git_repo_others/MITgcm/pkg/kpp/`
- Current KPP docs: `docs/KPP/` (3 files)
- User directive: "kpp and ggl subdirectories should be essentially mirror images"
- PO clarification: "eccov4 doesn't use kpp, so no appendix for kpp ecco v4 in the kpp document"

---

**Builder (Bob)**: Execute Phases 1-4, deliver restructured tex + git operations to Richard.  
**Reviewer (Richard)**: Validate checklist, verify MITgcm source accuracy, approve for commit.  
**Architect (Arch)**: Launch Bob, monitor progress, coordinate Richard review, obtain PO deploy gate.
