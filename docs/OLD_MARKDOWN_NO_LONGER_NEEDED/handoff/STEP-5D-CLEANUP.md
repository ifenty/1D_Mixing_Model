# Step 5d: Consolidate and Remove Markdown

**Date**: 2026-08-11  
**Architect**: Arch  
**Builder**: Bob  
**Reviewer**: Richard  

## Mission

Verify all markdown content is now incorporated into the .tex files, then remove all markdown and temporary files. End state: each scheme directory contains exactly 2 .tex files.

## Context

- **Step 5b (Harmonization)**: Both package_description files restructured to shared skeleton
- **Step 5c (Port description)**: Both port_description files written with shared structure
- **Current state**: Markdown files remain from pre-Step-5 documentation

## Current Files

### docs/GGL90/
**Keep (2 .tex files)**:
- `GGL90_package_description.tex` ✓
- `GGL90_port_description.tex` ✓

**Remove (5 markdown + temporary)**:
- `00_GGL90_COMPREHENSIVE_REPORT.md` - content folded into package_description
- `01_SOURCE_CODE_SUMMARY.md` - content folded into package_description
- `02_ECCOV4_R4_CONFIGURATION.md` - content folded into package_description Appendix B
- `03_QUICK_REFERENCE.md` - content folded into port_description
- `05_PYTHON_IMPLEMENTATION_NOTES.md` - content folded into port_description

### docs/KPP/
**Keep (2 .tex files)**:
- `KPP_package_description.tex` ✓
- `KPP_port_description.tex` ✓

**Remove (7 markdown + temporary)**:
- `BOB_COMPLETION_REPORT.md` - temporary build artifact from Step 5b-1
- `MITgcm_KPP_Report.md` - content folded into package_description
- `RESTRUCTURING_HANDOFF_TO_RICHARD.md` - temporary handoff from Step 5b-1
- `RESTRUCTURING_NOTE.md` - temporary note from Step 5b-1
- `RICHARD_REVIEW_REPORT.md` - temporary review from Step 5b-1
- `NEW_APPENDIX_C_ADJOINT.tex` - source material, already incorporated into package_description
- `NEW_SECTION_13_INIT_RESTART.tex` - source material, already incorporated into package_description
- `KPP_package_description_ORIGINAL_BACKUP.tex` - backup from restructuring, no longer needed

## Phase 1: Verify Content Migration

Bob must verify that all useful markdown content has been incorporated:

1. **GGL90 markdown → tex mapping**:
   - `00_COMPREHENSIVE_REPORT.md` → `GGL90_package_description.tex` (physics)
   - `01_SOURCE_CODE_SUMMARY.md` → `GGL90_package_description.tex` (source overview)
   - `02_ECCOV4_R4_CONFIGURATION.md` → `GGL90_package_description.tex` Appendix B
   - `03_QUICK_REFERENCE.md` → `GGL90_port_description.tex` §10 (Usage)
   - `05_PYTHON_IMPLEMENTATION_NOTES.md` → `GGL90_port_description.tex` §2 (Bug fixes)

2. **KPP markdown → tex mapping**:
   - `MITgcm_KPP_Report.md` → `KPP_package_description.tex` (physics)
   - Temporary .md files are build artifacts, not content sources

3. **Check for unique content**: 
   - Grep each markdown file for unique information not in the .tex files
   - If found, add to appropriate .tex file before deletion
   - Most likely all content already migrated (Steps 5b/5c specifically folded content)

## Phase 2: Remove Files

After verification, remove all markdown and temporary files:

```bash
# GGL90 cleanup
git rm docs/GGL90/00_GGL90_COMPREHENSIVE_REPORT.md
git rm docs/GGL90/01_SOURCE_CODE_SUMMARY.md
git rm docs/GGL90/02_ECCOV4_R4_CONFIGURATION.md
git rm docs/GGL90/03_QUICK_REFERENCE.md
git rm docs/GGL90/05_PYTHON_IMPLEMENTATION_NOTES.md

# KPP cleanup
git rm docs/KPP/BOB_COMPLETION_REPORT.md
git rm docs/KPP/MITgcm_KPP_Report.md
git rm docs/KPP/RESTRUCTURING_HANDOFF_TO_RICHARD.md
git rm docs/KPP/RESTRUCTURING_NOTE.md
git rm docs/KPP/RICHARD_REVIEW_REPORT.md
git rm docs/KPP/NEW_APPENDIX_C_ADJOINT.tex
git rm docs/KPP/NEW_SECTION_13_INIT_RESTART.tex
git rm docs/KPP/KPP_package_description_ORIGINAL_BACKUP.tex
```

## Phase 3: Verify End State

```bash
# Should show only 2 .tex files each
ls docs/GGL90/*.tex
ls docs/KPP/*.tex

# Should show no markdown files
ls docs/GGL90/*.md 2>/dev/null || echo "No markdown files (correct)"
ls docs/KPP/*.md 2>/dev/null || echo "No markdown files (correct)"
```

## Validation Checklist for Richard

- [ ] All GGL90 markdown content verified in .tex files (no unique content lost)
- [ ] All KPP markdown content verified in .tex files (no unique content lost)
- [ ] `docs/GGL90/` contains exactly 2 files: `GGL90_package_description.tex`, `GGL90_port_description.tex`
- [ ] `docs/KPP/` contains exactly 2 files: `KPP_package_description.tex`, `KPP_port_description.tex`
- [ ] No .md files remain in docs/GGL90/ or docs/KPP/
- [ ] No temporary .tex files remain (NEW_*, *_BACKUP.tex, etc.)
- [ ] Git status shows clean deletions

## Git Commit

```bash
git commit -m "Step 5d: Remove markdown files after consolidation into LaTeX

- Remove 5 GGL90 markdown files (content folded into .tex files)
- Remove 8 KPP markdown/temporary files (content folded into .tex files)
- End state: each scheme dir has exactly 2 .tex files
- GGL90: package_description.tex + port_description.tex
- KPP: package_description.tex + port_description.tex

All markdown content verified migrated in Steps 5b/5c

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# DO NOT PUSH (await PO gate)
```

## Success Criteria

- Each scheme directory (`docs/GGL90/`, `docs/KPP/`) contains exactly 2 .tex files
- Zero markdown files remain
- Zero temporary files remain
- No unique content lost from markdown files
- User can now see clean mirror-image structure:
  ```
  docs/GGL90/
    GGL90_package_description.tex  (physics of mixing scheme)
    GGL90_port_description.tex     (Python port implementation)
  
  docs/KPP/
    KPP_package_description.tex    (physics of mixing scheme)
    KPP_port_description.tex       (Python port implementation)
  ```

## References

- User directive: "consolidate into latex, remove the markdown"
- Step 5b commits: 31876e6 (KPP harmonization), f66d615 (GGL90 harmonization)
- Step 5c commit: 3334bf1 (port_description files)

---

**Builder (Bob)**: Execute Phases 1-3, deliver clean directories to Richard.  
**Reviewer (Richard)**: Validate checklist, verify no content loss, approve for commit.  
**Architect (Arch)**: Launch Bob, coordinate Richard review, obtain PO deploy gate.
