# Step 5b-2: GGL90 package_description Harmonization

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Restructure `docs/GGL90/GGL90_package_description.tex` to match the approved shared skeleton (19 sections + 3 appendices), fold unique content from `docs/GGL90/GGL90_Report.tex`, and ensure all existing verified content (especially α-minimum section) is preserved. End state: GGL90 documentation uses identical organizational structure to KPP, enabling side-by-side comparison.

## Context

- **Step 5b-1 (KPP harmonization)**: COMPLETE (commit 31876e6). KPP now uses the shared skeleton.
- **Shared skeleton**: Approved by PO (`handoff/DOC-SKELETON.md`). 19 main sections + 3 appendices.
- **Critical content**: GGL90_package_description.tex §3.8.6 contains VERIFIED α-minimum analysis (Step 5a, commit b30b318) — MUST preserve exactly
- **User directive**: "the kpp and ggl subdirectories should be essentially mirror images of each other in terms of structure"
- **GGL90 gets Appendix B**: Unlike KPP, GGL90 document INCLUDES Appendix B (ECCOv4 Configuration) because ECCOv4 uses GGL90

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
- **Appendix B**: ECCOv4 Configuration ← **INCLUDE FOR GGL90** (ECCOv4 uses GGL90)
- **Appendix C**: Adjoint Model Considerations

## File Operations

### Input Files
```
docs/GGL90/GGL90_package_description.tex  (4,520 lines) - restructure to skeleton
docs/GGL90/GGL90_Report.tex              (1,320 lines) - fold content in, then DELETE
```

### Output Files
```
docs/GGL90/GGL90_package_description.tex  (restructured, ~4,800-5,200 lines estimated)
```

### Deletions
```
docs/GGL90/GGL90_Report.tex  (DELETE after content folded)
```

## Detailed Instructions

### Phase 1: Read and Map Existing Content

1. **Read both GGL90 files** to understand what content exists:
   - `docs/GGL90/GGL90_package_description.tex` (current main doc, 4,520 lines)
   - `docs/GGL90/GGL90_Report.tex` (may contain unique analysis/validation)

2. **Create content mapping table** showing:
   - Which skeleton section each existing paragraph/subsection belongs in
   - Which content from GGL90_Report.tex needs to be folded in
   - Which sections need NEW content written (if any)
   - **CRITICAL**: Map verified α-minimum section (currently §3.8.6) to skeleton §17 (Numerical Considerations)

### Phase 2: Restructure GGL90_package_description.tex

3. **Rewrite GGL90_package_description.tex with the approved skeleton**:
   - Use the exact 19-section + 3-appendix structure from DOC-SKELETON.md
   - Redistribute existing content from old sections into new skeleton sections
   - **PRESERVE EXACTLY**: Verified α-minimum analysis (Step 5a) with all metrics (roughness, oscillation count, under-resolved fraction table)
   - Preserve ALL existing physics content, equations, code listings, tables, figures
   - Add `\section` and `\subsection` commands to match skeleton hierarchy
   - Maintain LaTeX quality: proper math mode, citations, code listings, cross-references

4. **Fold content from GGL90_Report.tex**:
   - Identify any validation results, analysis, or insights unique to GGL90_Report.tex
   - Integrate this content into appropriate skeleton sections
   - Do NOT duplicate content already in package_description.tex
   - Preserve figure/table references if folding figures/tables

### Phase 3: Write/Verify New Content

5. **§13 Initialization and Restart**:
   - Explain GGL90 is **prognostic** (carries TKE state)
   - Document TKE pickup files: `pickup.ggl90` format, variables stored
   - Contrast with diagnostic schemes (like KPP) briefly
   - Document initial TKE value (`GGL90TKEmin` default)
   - Check if existing content covers this; if so, preserve and enhance

6. **Appendix B: ECCOv4 Configuration** (INCLUDE FOR GGL90):
   - **Primary source**: ECCOv4 configuration files (user opened in IDE earlier)
   - Document GGL90 parameter settings used in ECCOv4 Release 4
   - Key parameters to cover:
     - `GGL90diffTKEh`, `GGL90diffKrS`, `GGL90diffKrT`
     - `GGL90m2`, `GGL90alpha` (α value used)
     - `GGL90TKEmin`, `GGL90TKEsurfMin`
     - Mixing length flags (`mxlSurfFlag`, `GGL90mixingMaps`, etc.)
   - Check existing package_description content for ECCOv4 references; consolidate into this appendix
   - **Length target**: 2-4 pages

7. **Appendix C: Adjoint Model Considerations**:
   - **Primary source**: MITgcm GGL90 adjoint source files in `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
   - Look for files matching pattern `*_ad.F`, `*_ad.flow`, `ggl90_ad_*`, or adjoint-specific comments
   - **Content to cover**:
     - Whether GGL90 has full adjoint support in MITgcm (TAF-generated or hand-coded)
     - Key adjoint considerations for GGL90 (TKE prognostic state, implicit solver adjoint, checkpointing)
     - Any GGL90-specific adjoint limitations or requirements
     - Active/passive variable handling
     - Comparison to KPP adjoint complexity (KPP's Appendix C for reference)
   - **Length target**: 2-4 pages (similar depth to KPP's appendix)

### Phase 4: File Cleanup

8. **Delete GGL90_Report.tex** after verifying all unique content has been folded:
   ```bash
   git rm docs/GGL90/GGL90_Report.tex
   ```

### Phase 5: Technical Verification

9. **Verify against MITgcm GGL90 source**:
   - Source location: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
   - Key files to reference:
     - `ggl90_calc.F` (main driver)
     - `ggl90_routines.F` (TKE evolution, mixing length)
     - `ggl90_init_varia.F`, `ggl90_readparms.F` (initialization)
     - `ggl90_output.F`, `ggl90_diagnostics_init.F` (diagnostics)
     - `GGL90_OPTIONS.h` (compile-time flags)
     - `GGL90.h` (parameters, common blocks)
   - Ensure all code snippets, parameter names, equation references are accurate
   - **CRITICAL**: Do NOT modify verified α-minimum section from Step 5a

10. **Preserve existing content depth**:
    - Do NOT pad sections with filler text
    - Do NOT invent physics details not in MITgcm source
    - GGL90 likely has MORE detail than KPP in some sections (prognostic TKE, mixing length) — preserve this depth
    - **α-minimum section**: Already verified and publication-ready — preserve verbatim in §17

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

- [ ] All 19 main sections present in GGL90_package_description.tex
- [ ] Appendix A (I/O Mapping) present
- [ ] Appendix B (ECCOv4 Configuration) present with substantive content
- [ ] Appendix C (Adjoint) present with substantive content
- [ ] §13 (Init/Restart) explains prognostic TKE and pickup files
- [ ] §17 (Numerical Considerations) contains VERIFIED α-minimum analysis from Step 5a (table with under-resolved fraction, 3 metrics)
- [ ] All existing GGL90 physics content preserved (no loss of equations, tables, figures)
- [ ] Unique content from GGL90_Report.tex successfully folded in
- [ ] GGL90_Report.tex deleted (git rm)
- [ ] Code snippets verified against MITgcm source in `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
- [ ] LaTeX compiles without errors (if testable)
- [ ] No TODO, FIXME, or placeholder comments left in final tex
- [ ] Cross-references, citations, labels all functional
- [ ] α-minimum section unchanged from commit b30b318

## Git Commands

```bash
# After Richard approval
git rm docs/GGL90/GGL90_Report.tex
git add docs/GGL90/GGL90_package_description.tex
git commit -m "Step 5b-2: Harmonize GGL90 package_description to shared skeleton

- Restructure to 19 sections + 3 appendices (A, B, C)
- Preserve verified α-minimum analysis in §17 (Step 5a)
- Write §13 Init/Restart (prognostic TKE, pickup files)
- Write Appendix B (ECCOv4 Configuration)
- Write Appendix C (Adjoint Model Considerations)
- Fold unique content from GGL90_Report.tex (now deleted)
- Verified against MITgcm pkg/ggl90/ source"

# DO NOT PUSH (await PO gate)
```

## Success Criteria

- GGL90_package_description.tex uses identical section structure to KPP_package_description.tex
- User can open KPP and GGL90 package_description files side-by-side and see matching §1-19 + appendices A, B (GGL90 only), C
- All existing GGL90 physics content preserved at current depth
- **Verified α-minimum section preserved exactly** in §17
- New Appendix B (ECCOv4) and Appendix C (Adjoint) written with accurate technical content
- GGL90_Report.tex content folded in and file deleted
- Zero regressions in documentation accuracy (Richard verification)

## References

- Shared skeleton: `handoff/DOC-SKELETON.md`
- MITgcm GGL90 source: `/Users/ifenty/git_repo_others/MITgcm/pkg/ggl90/`
- Current GGL90 docs: `docs/GGL90/` (2 tex files)
- Verified α-minimum section: commit b30b318, §3.8.6 in current file
- KPP harmonization (for structure reference): commit 31876e6
- User directive: "kpp and ggl subdirectories should be essentially mirror images"

---

**Builder (Bob)**: Execute Phases 1-4, deliver restructured tex + git operations to Richard.  
**Reviewer (Richard)**: Validate checklist, verify MITgcm source accuracy, verify α-minimum preservation, approve for commit.  
**Architect (Arch)**: Launch Bob, monitor progress, coordinate Richard review, obtain PO deploy gate.
