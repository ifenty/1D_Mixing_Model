# Documentation Index

**Last Updated**: 2026-07-20  
**Phase**: 4+ (Full Scenario Validation)

## Start Here

- **[README.md](README.md)** — ⭐ **START HERE** — Comprehensive project overview, quick start, architecture, and next steps for new agents

## Team & Coordination

- **[ARCHITECT.md](ARCHITECT.md)** — Role definition for project architect
- **[BUILDER.md](BUILDER.md)** — Role definition for project builder
- **[REVIEWER.md](REVIEWER.md)** — Role definition for project reviewer
- **[handoff/](handoff/)** — Coordination files (briefs, build logs, reviews, checkpoints)

## Core Physics & Implementation

### GGL90 (Prognostic TKE Scheme)
- **[1D_Mixing_Model/GGL90_ML/GGL90_PY/IMPLEMENTATION_NOTES.md](1D_Mixing_Model/GGL90_ML/GGL90_PY/IMPLEMENTATION_NOTES.md)** — Implementation architecture (Phase 2+ refactored)
- **[1D_Mixing_Model/GGL90_ML/GGL90_REPORT/](1D_Mixing_Model/GGL90_ML/GGL90_REPORT/)** — Comprehensive technical reports (LaTeX + markdown)

### KPP (Diagnostic Boundary Layer Scheme)
- **[1D_Mixing_Model/KPP_ML/KPP_PHYSICS_EXPLANATION.md](1D_Mixing_Model/KPP_ML/KPP_PHYSICS_EXPLANATION.md)** — Physics background and common Q&A
- **[1D_Mixing_Model/KPP_ML/IMPORT_FIX_SUMMARY.md](1D_Mixing_Model/KPP_ML/IMPORT_FIX_SUMMARY.md)** — Technical notes on import fixes
- **[1D_Mixing_Model/KPP_ML/KPP_REPORT/](1D_Mixing_Model/KPP_ML/KPP_REPORT/)** — Comprehensive technical reports (LaTeX + markdown)

## Validation & Testing

- **[1D_Mixing_Model/PHASE4_FULL_SCENARIO_VALIDATION_REPORT.md](1D_Mixing_Model/PHASE4_FULL_SCENARIO_VALIDATION_REPORT.md)** — Current validation results (auto-generated from test suite)

## Technical References

- **[1D_Mixing_Model/MIXING_SCHEMES_REPORT_README.md](1D_Mixing_Model/MIXING_SCHEMES_REPORT_README.md)** — Guide to comprehensive technical reports
- **[1D_Mixing_Model/MITGCM_STAGGERING.md](1D_Mixing_Model/MITGCM_STAGGERING.md)** — Vertical grid staggering convention (Python ↔ MITgcm mapping)

## Recent Documentation Changes (This Session)

### ✅ Created
- **README.md** — Comprehensive top-level guide for future agents

### ✅ Deleted (Obsolete)
- `new-setup.md` — First-time setup guide (archived)
- `PHASE4_CROSS_SCHEME_VALIDATION_REPORT.md` — Superseded by PHASE4_FULL_SCENARIO_VALIDATION_REPORT
- `1D_Mixing_Model/KPP_ML/PHASE3_COMPLETION_REPORT.md` — Old completion report
- `1D_Mixing_Model/GGL90_ML/GGL90_PY/PHASE2_COMPLETION_REPORT.md` — Old completion report

### ✅ Updated
- `1D_Mixing_Model/GGL90_ML/GGL90_PY/IMPLEMENTATION_NOTES.md` — Now reflects Phase 2+ refactored architecture

## Running Tests & Viewing Results

**For a complete walkthrough**, see [README.md](README.md#running-tests--generating-visualizations).

**Quick commands:**
```bash
cd 1D_Mixing_Model

# Full validation suite (generates all plots)
python main/test_full_scenario_validation.py

# Run specific scenario
python main/run_scenarios.py --scenario arctic_convection

# View results
open visualizations/  # PNG plots
open PHASE4_FULL_SCENARIO_VALIDATION_REPORT.md  # Metrics report
```

## Repository Memory

Extended technical notes stored in `/memories/repo/1D_mixing_experiments.md`:
- Environment setup details
- Bug fixes (with physics explanations)
- Phase-by-phase completion summaries
- ECCOv4 Release 4 configuration notes

---

**All documentation is current and actionable.** Future agents should start with [README.md](README.md).
