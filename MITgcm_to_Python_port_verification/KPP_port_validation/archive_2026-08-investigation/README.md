# Archived: 2026-08-20 outlier investigation (superseded, disclaimed)

**Status: superseded/disclaimed — not part of the active validation pipeline.**
Read `closed_issues.md` (1DMIX-013, -017, -018, -019) for the current, accurate
history. This directory is retained (not deleted) purely as a historical record
of the earlier investigation and its debugging tooling — nothing here should be
run as part of the active pipeline or cited as a current result.

## What this is

An early (2026-08-20), single-experiment (`1D_ocean_ice_column`, the original
11,000-timestep KPP capture) investigation into a cluster of large-relative-error
outliers around timestep 2312. Its three documents (`INVESTIGATION_CONCLUSION.md`,
`VALIDATION_SUMMARY.md`, `MITGCM_MODIFICATION_COMPLETE.md`) concluded the outliers
were purely a floating-point-precision/near-critical-threshold artifact with
"all formulas verified correct" and the port "production-ready" — before two
real port bugs affecting this same capture were subsequently found and fixed
(1DMIX-013, -017, -018) and the Rib/Ricr threshold-crossing sensitivity mechanism
itself was independently, more rigorously characterized at much larger scale on
`lab_sea` (1DMIX-019). The bottom-line "all formulas verified correct" claim is
therefore **known incomplete**, not merely stale phrasing.

`scripts/debug_timestep_2312.py` and `scripts/analyze_outlier_cluster.py`
(relocated here under 1DMIX-046, no code changes) are this investigation's own
debugging tools, hardcoded to the specific `mitgcm_kpp_inputs_11k_1D.nc` capture
and its now-historical `outputs_from_python/python_kpp_outputs_11k_1D.nc`
snapshot; `outlier_diagnostics/` (relocated the same way) holds the 10 per-timestep
diagnostic PNGs those scripts produced. None of the three are imported by, or
referenced from, any file under the active `scripts/`/`tests/` trees. Both
scripts' relative `inputs_from_mitgcm/...`/`outputs_from_python/...` paths were
originally written assuming a `KPP_port_validation/` working directory (one
level up from here) — unchanged on relocation, since these are frozen debugging
artifacts, not active tooling; run them (if ever needed again) from
`KPP_port_validation/` with `python archive_2026-08-investigation/scripts/<name>.py`,
or adjust `cwd` accordingly.

## Why relocated instead of deleted

Everything here is git-tracked (recoverable via history either way), but the
debug trace and plots have genuine, if narrow, historical value for anyone
re-investigating Rib/Ricr threshold sensitivity in the future — deleting them
outright would lose a worked example for no real benefit. Relocating into one
clearly-labeled directory (rather than leaving the two scripts and the PNG
directory scattered across the otherwise-active `scripts/`/`outputs_from_python/`
trees) resolves the ambiguity this issue (1DMIX-046) was opened to fix, at lower
risk than deletion. `MITgcm_wrappers/` (a separate, unrelated artifact, same
issue) was deleted outright instead, per an explicit owner decision recorded in
1DMIX-046 — that is a different, stronger case (owner-confirmed abandonment, not
merely superseded-with-residual-value) and does not set a precedent for this
material.
