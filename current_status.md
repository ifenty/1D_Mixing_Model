# Project milestones

Append dated, evidence-linked milestones when warranted. Keep any resume block limited to stable navigation links.

## 2026-09-21: Multi-day three-way verification push — GGL90 coverage extended, lab_sea full-year KPP comparison, 8 real port/harness bugs fixed

**Status**: Complete, independently reviewed (Bob + Richard on every `scientific_change`), 15+ issues closed. Full pytest suite green throughout (56 passed, 3 skipped). Not committed (per `commit_policy=owner_authorization`) — changes remain in the working tree pending owner authorization.

**Scope**: owner-directed extension of the KPP/GGL90-vs-MITgcm three-way verification mission across new experiments, longer runs, and systematic scheme×experiment cross-testing.

**Coverage extended**:
- GGL90 run for the first time on a real multi-column, real-bathymetry grid (`global_oce_latlon`), and on `1D_ocean_ice_column`'s reprocessed 11k-timestep capture (1DMIX-028, 1DMIX-029).
- `global_oce_latlon` KPP extended from a 4-timestep smoke test to a full periodic-forcing cycle (720 timesteps, 1DMIX-027).
- `lab_sea` KPP extended from a 6-month sample to a full year (8760 timesteps), with corrected capture instrumentation for the first time (1DMIX-026).
- KPP idealized-scenario-to-standalone-driver export pipeline built and validated (5/6 scenarios machine-precision exact, 1DMIX-023); GGL90 standalone driver built and run across all 6 scenarios (1DMIX-024).

**Real bugs found and fixed** (each independently reviewed):
- `parse_mitgcm_split.py` silently corrupted multi-tile domains (no `BI=`/`BJ=` awareness) — 1DMIX-021.
- KPP forcing-validation gate false-failed on realistic multi-column forcing (T-grid tau averaging) — 1DMIX-022.
- `OUTPUT_DIAGNOSTICS`/`OUTPUT_MIXING` capture truncation silently zero-filled real, nonzero mixing data (up to 83.5% of wet columns in one case) — 1DMIX-033, 1DMIX-035.
- Missing `KPP_ESTIMATE_UREF` reference-velocity estimate caused a real ~9 m mean `hbl` divergence on `vermix` — 1DMIX-032.
- GGL90 mixing-length depth limiter used cell-center span instead of MITgcm's interface-to-interface span — 1DMIX-030.
- `lab_sea`'s own capture instrumentation was stale (missing 4 prior fixes, entirely missing `kpp_routines.F`); fixing it surfaced a broken `sys.path` from the repo reorganization and an overly-strict salt-plume safety guard — 1DMIX-026.
- Two tooling bugs blocking formal closure itself: `verify.py`'s PATH-sensitive evidence fingerprint, and `final_verification.py`'s dual-module-identity lease bug — 1DMIX-036, 1DMIX-037.

**Root-caused, not fixed (structural/inert, evidenced)**:
- KPP `hbl` Rib/Ricr threshold-crossing sensitivity — inherent floating-point sensitivity of a hard-thresholded diagnostic, not a port defect (1DMIX-019).
- GGL90 `diff_kz`/`tke_after` residual on `global_oce_latlon` — real horizontal smoothing (`ALLOW_GGL90_SMOOTH`) outside single-column replay scope, confirmed to 1.7e-16 median relative error once compared correctly (1DMIX-028).
- GGL90 TKE-near-floor mismatches — inert floating-point noise, matching the KPP Rib/Ricr precedent (1DMIX-031).

**Scoped but not yet implemented**: KPP salt-plume physics port (real formula, exact 3 Python call sites, exact 2 new Fortran capture fields identified — 1DMIX-034); IDEMIX/ShelfIce GGL90 instrumentation for remaining MITgcm experiments (1DMIX-025).

**Evidence**: see `closed_issues.md` for full per-issue resolution narratives, root-cause evidence, and reviewer traceability (Bob/Richard agent IDs, verification receipts).
