# Shared package_description.tex Skeleton (Step 5b)

Goal: GGL90 and KPP `*_package_description.tex` use an IDENTICAL top-level section list
(PO decision: "Fully identical section list"). Where a scheme has little to say in a
section, it carries a short honest note rather than being omitted — so the two docs open
side-by-side as mirror images.

Legend: each section shows how the CURRENT content of each scheme maps in.

| # | Shared Section Title | GGL90 source content | KPP source content |
|---|----------------------|----------------------|--------------------|
| 1 | Introduction and Scientific Background | Intro/Sci Background | Intro/Sci Background |
| 2 | Governing Equations (overview) | TKE eq, κm/κh, mixing length summary | Ri interior, bldepth, wscale summary |
| 3 | Package Architecture and Call Flow | Package Architecture & Call Flow | Package Architecture & Call Flow |
| 4 | Parameter Initialization | Parameter Initialization | Parameter Initialization |
| 5 | Main Driver Routine | GGL90\_CALC | KPP\_CALC |
| 6 | Stratification and Buoyancy | Stratification & Shear (N², S²) | STATEKPP (density/buoyancy, N²) |
| 7 | Surface Forcing | surface TKE from u\* (in Boundary Conditions) | KPP\_FORCING\_SURF |
| 8 | Interior Mixing | shear production; background/interior κ | Ri\_iwmix (interior + internal wave) |
| 9 | Boundary / Surface Layer Mixing | mixing length (GGL90\_MIXINGLENGTH), mxlSurfFlag | bldepth, wscale, blmix, enhance |
| 10 | Core Diffusivity/Prognostic Update | TKE Evolution & Budget → eddy coeffs | KPPMIX (assemble diffusivities) |
| 11 | Additional Mixing Processes | IDEMIX, Langmuir (optional) | Double diffusion, salt plume, shortwave |
| 12 | Eddy Coefficients and Model Interface | Eddy Coefficient Calc + Interface Routines | Model Interface Routines |
| 13 | Initialization and Restart | Init & Restart (TKE pickup) | diagnostic note (see below) |
| 14 | Compile-Time Options | Compile-Time Options | Compile-Time Options |
| 15 | Output and Diagnostics | Output & Diagnostics | Output & Diagnostics |
| 16 | Package Validation | GGL90\_CHECK | KPP\_CHECK |
| 17 | Numerical Considerations & Frequently Encountered Issues | α-minimum / oscillations; tuning | analogous tuning/issues |
| 18 | Conclusions | Conclusions | Conclusions |
| 19 | Glossary of Symbols | Glossary | Glossary |
| A | Appendix A: Complete Input/Output Mapping | I/O Mapping | Complete I/O Summary |
| B | Appendix B: ECCOv4 Configuration | ECCOv4 Configuration | NEW (mirror; from ECCOv4 data.kpp) |
| C | Appendix C: Adjoint Model Considerations | Adjoint Model Considerations | NEW (mirror; KPP adjoint notes) |

## Notes / asymmetries to handle honestly (PO-approved 2026-08-11)
- ECCOv4 Configuration and Adjoint Model Considerations are APPENDICES (B, C), not main-body sections.
- §13 (Init/Restart) — KPP text (PO-specified content): state that KPP is DIAGNOSTIC, not prognostic; explain what that means (all mixing coefficients are recomputed from the instantaneous ocean state each time step); and that there is NO previous KPP state carried from one time step to the next (no KPP pickup/restart field). GGL90 by contrast carries prognostic TKE in a pickup.
- §11 (Additional Processes): different sub-content per scheme (IDEMIX/Langmuir vs double-diffusion/salt-plume) — same section, scheme-specific subsections.
- Appendices B, C: KPP currently lacks these → must be WRITTEN for KPP to mirror GGL90 (verify against MITgcm KPP source + ECCOv4 data.kpp).
- Content DEPTH may differ (PO: depth allowed to differ); only the section/appendix LIST is forced identical.
- The `Report.tex` pair (GGL90_Report.tex/KPP_Report.tex) is deleted after folding any unique content into the sections above.

## Same skeleton principle applies to port_description.tex (Step 5c) — separate skeleton TBD.
