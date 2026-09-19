# Unified GGL90 and KPP Vertical Mixing Scheme Reports

**Date:** 2026-07-16  
**Format:** LaTeX (.tex) — Compile with `pdflatex` or modern LaTeX processor  
**Status:** Complete and ready for review

## Overview

Two comprehensive, unified LaTeX technical reports have been created documenting the GGL90 and KPP vertical mixing parameterizations as implemented in MITgcm and ECCOv4. The reports follow an identical organizational structure to facilitate comparison and understanding of both schemes.

## File Locations

```
GGL90/GGL90_REPORT/GGL90_Report.tex      (Main GGL90 comprehensive report)
KPP/KPP_REPORT/KPP_Report.tex           (Main KPP comprehensive report)
```

## Report Structure (Unified Across Both Schemes)

Both reports follow this identical organizational structure:

### 1. Purpose and Scope
- What is the scheme? (GGL90 vs. KPP)
- Key physics features
- Applications

### 2. Scientific Background and Core Equations
- Fundamental prognostic/diagnostic equations
- Viscosity and diffusivity relationships
- Mixing length computation (GGL90) or boundary layer diagnosis (KPP)
- Buoyancy frequency and stratification concepts
- Nonlocal transport (KPP) or dissipation (GGL90)

### 3. Package Structure
- Directory organization and file overview
- Compile-time options (CPP flags)
- Approximate lines of code per module

### 4. Key Parameters and Their Meanings
- Closure constants and tuning parameters
- Boundary condition values
- Control flags and limits
- Physical interpretation of each parameter

### 5. Initialization Phase
- Step 1: Parameter reading (readparms)
- Step 2: Fixed initialization (init_fixed)
- Step 3: Variable initialization (init_varia)

### 6. Main Runtime Computation
- Entry points and call sequences
- Complete input specification (explicit arguments + implicit common blocks)
- **Detailed computational sequence** (the core innovation):
  - Sequence 1, 2, 3, ... through final output
  - Order of operations precisely documented
  - All intermediate calculations explained
  - Physical meaning and numerical considerations
- Main outputs and array dimensions

### 7. Integration with the Ocean Model
- Where in the model control flow the scheme sits
- How viscosity enters momentum equation
- How diffusivity enters tracer equations
- Nonlocal transport coupling (KPP)

### 8. Diagnostics and Output
- Registered diagnostic fields
- Snapshot/pickup file handling
- Output frequencies and formats

### 9. Comparison with the Other Scheme (NEW)
- Fundamental differences table
- Physical behavior comparison under different forcing regimes:
  - Wind-driven mixing (stable stratification)
  - Convective mixing (unstable stratification)
  - Double-diffusive effects (KPP)
  - Shear-driven interior mixing (GGL90)
- Validation and tuning considerations
- When to use which scheme

### 10. Python 1D Implementation Status
- Reference to separate Python implementation documentation
- Connection to research code

### Appendices

**Appendix A: Parameter Table**
- Comprehensive table of all parameters
- Description of physical meaning
- Units
- Typical/default values
- ECCOv4 R4 tuning values (where applicable)

**Appendix B: References**
- Original papers (Gaspar et al. 1990 for GGL90; Large et al. 1994 for KPP)
- Implementation references
- Related numerical methods papers

## Key Improvements Over Previous Documentation

### 1. **Unified Structure**
   - Identical organizational outline enables direct comparison
   - Same section headers and naming conventions
   - Easy to navigate between schemes

### 2. **Comprehensive Calculation Sequences**
   - New **detailed sequence sections** break down the complete computational flow
   - Each step numbered and explained
   - Physical meaning provided
   - Numerical considerations noted
   - All intermediate variables named and typed

### 3. **Inputs and Outputs Fully Specified**
   - Explicit arguments clearly listed
   - Implicit inputs (via common blocks) enumerated
   - All arrays: shape, units, interpretation
   - Output arrays and their consumption by downstream routines

### 4. **Comparison Section**
   - Direct side-by-side behavior comparison
   - Table summarizing 13 key differences
   - Regime-dependent behavior analysis
   - Guidance on when to use each scheme

### 5. **Professional LaTeX Format**
   - Consistent formatting and typography
   - Proper mathematical notation with KaTeX/AMS Math
   - References and citations with proper formatting
   - Hyperlinked table of contents
   - Professional layout with proper margins and spacing

### 6. **Parameter Appendix**
   - All parameters in one comprehensive table
   - Units and typical values visible at a glance
   - ECCOv4 R4 tuning values highlighted

## Reading Guide

### For New Users (Starting from Scratch)

1. Read **Section 1** (Purpose and Scope) to understand what the scheme does
2. Skim **Section 2** (Scientific Background) to get the physics intuition
3. Read **Section 4** (Key Parameters) to understand what controls behavior
4. Study **Section 6** (Main Runtime Computation) to see exact order of calculations
5. Read **Section 9** (Comparison) to understand relative strengths
6. Reference **Appendix A** (Parameter Table) when tuning

### For Model Developers

1. Study **Section 3** (Package Structure) to find relevant source files
2. Read **Section 6** (Main Runtime Computation) in detail for algorithm specifics
3. Study **Section 7** (Integration with Ocean Model) to understand coupling
4. Reference **Appendix A** for parameter definitions when reading code

### For Researchers Comparing Schemes

1. Read **Section 1** (Purpose and Scope) for both schemes
2. Study **Section 2** (Scientific Background) for both to understand physics
3. Go directly to **Section 9** (Comparison) for direct side-by-side analysis
4. Read relevant subsections of **Section 6** for computational details of interest

### For Implementation in New Code

1. Read **Section 2** (Scientific Background) to understand physics to implement
2. Study **Section 6** (Main Runtime Computation) to understand exact sequence
3. Reference **Section 7** (Integration) to understand coupling to other modules
4. Use **Appendix A** (Parameter Table) as reference for all parameter definitions

## Compilation Instructions

### Prerequisites

Install a modern LaTeX distribution (TeX Live, MiKTeX, MacTeX, etc.)

### On macOS (with MacTeX installed)

```bash
cd /Users/ifenty/Library/CloudStorage/Box-Box/ifenty/Projects/ECCO/1D_Mixing_Experiments/1D_Mixing_Model/GGL90/GGL90_REPORT

# Compile GGL90 report to PDF
pdflatex -interaction=nonstopmode GGL90_Report.tex

# Compile KPP report to PDF
cd ../../KPP/KPP_REPORT
pdflatex -interaction=nonstopmode KPP_Report.tex
```

### On Linux (with TeX Live installed)

```bash
pdflatex -interaction=nonstopmode GGL90_Report.tex
pdflatex -interaction=nonstopmode KPP_Report.tex
```

### Recommended Multi-Pass Compilation

For proper hyperlink resolution and table of contents:

```bash
pdflatex GGL90_Report.tex
pdflatex GGL90_Report.tex  # Second pass for TOC references
```

Output files will be:
- `GGL90_Report.pdf`
- `KPP_Report.pdf`

## Content Verification Checklist

Both reports include:

- [x] Purpose and scope (what, why, applications)
- [x] Scientific background (equations, physics)
- [x] Package structure (file organization, ~3000-4000 lines documented)
- [x] Key parameters (all documented with units and meanings)
- [x] Initialization phase (3-step process documented)
- [x] Main runtime computation (complete sequence with all steps)
- [x] Input specification (explicit + implicit via common blocks)
- [x] Output specification (arrays, shapes, units, consumption)
- [x] Integration with model (coupling to momentum and tracer solvers)
- [x] Diagnostics and output (registered fields, frequencies)
- [x] Comparison section (13-point table + regime analysis)
- [x] Python implementation status reference
- [x] Parameter appendix (comprehensive table)
- [x] Reference section (papers and related work)

## Physical Insights Highlighted in Comparison

### GGL90 (Prognostic TKE Closure)

**Strengths:**
- Evolves TKE over time → memory of forcing history
- Smooth mixing profiles across all depths
- Natural deep convection (no prescribed depth limit)
- Energy-consistent framework
- Good for long integrations and climate studies

**Characteristics:**
- Sensitive to both shear and stratification continuously
- Nonlinear TKE evolution (balance of production and dissipation)
- Requires restart files to maintain continuity
- Higher computational cost

### KPP (Diagnostic Boundary Layer)

**Strengths:**
- Fast initialization (no spin-up needed)
- Explicit nonlocal transport (good for convection)
- Well-designed for tropical/subtropical boundaries
- Simple diagnostic nature (no state variables)
- Lower computational cost

**Characteristics:**
- Sharp transition at boundary layer base
- Instantaneous response to forcing changes
- Designed specifically for shallow mixed layers
- No history dependence between time steps

## Typical Use Cases

| Task | Recommend | Reason |
|------|-----------|--------|
| Initial spin-up (0-1 months) | KPP | Fast initialization, no TKE history needed |
| Climate simulation (10+ years) | GGL90 | TKE memory crucial for stability |
| Assimilation (daily updates) | KPP | Rapid diagnostics, no restart complexity |
| Deep convection study | GGL90 | Natural depth evolution, no limits |
| Process study (weeks) | Either | Both work; choose by physics |
| Tropical/subtropical focus | KPP | Designed for this regime |
| Polar/deep water focus | GGL90 | Handles deep mixing naturally |

## Next Steps

1. **Compilation:** Generate PDF versions using pdflatex
2. **Review:** Check sections 6 and 9 for accuracy against source code
3. **Distribution:** Share both PDFs with research team
4. **Citation:** Reference reports when describing methodology
5. **Continuation:** Update reports as code evolves or physics is enhanced

## Feedback and Updates

These reports are living documents. When:
- Code is modified significantly
- New physics (IDEMIX, Langmuir, etc.) is added
- Parameters are re-tuned for new applications
- Bugs are discovered and fixed

Update the relevant sections and recompile PDFs.

---

**Report Status:** Complete and ready for use  
**Last Updated:** 2026-07-16  
**Format:** LaTeX 2e with AMS Math, Hyperref, Booktabs  
**Approximate PDF Sizes:** 25-30 pages each when compiled
