# Capture manifest — GGL90_port_validation

Written under 1DMIX-046 to resolve "which versioned file is current" for every
experiment that has more than one capture on disk. Only `vermix` has multiple
versions here; every other experiment (`1D_ocean_ice_column`,
`global_ocean_90x40x15_idemix_10`, `global_ocean_cs32x15_idemix_10`, `isomip_12`)
has exactly one input/output/python-output triple and needs no entry.

## `vermix` (20 timesteps, single column)

`GGL90` was iterated on this experiment across several closed issues (1DMIX-015,
-016, -024, -041, -048), each producing its own re-capture. UUIDs cross-checked
directly (`input_uuid` in each `outputs_from_python/` file matches the `uuid` of
its own `inputs_from_mitgcm/` counterpart — verified 2026-09-27) confirm the
pairings below; creation timestamps are monotonically increasing in the order
listed.

| File | Status | Why |
|---|---|---|
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix024.nc` | **current** | The capture `tests/test_ggl90_mitgcm_validation.py` (`DATA_VERMIX`) actually loads; newest (2026-09-19), matches `VALIDATION_RESULTS.md`'s own `vermix` row. |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20_1dmix024.nc` | **current** | Paired MITgcm output for the above (`OUTPUTS_VERMIX` in the same test). |
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix024.nc` | **current** | Regenerated freshest (2026-09-27, post-1DMIX-048 fix) against the current port; this is the file the freshness-checked PDF report (`reports/ggl90_validation_vermix_20.pdf`) was built from. |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20.nc` | superseded, retained | Original 2026-09-16 capture, predates the 1DMIX-015 `dt`-bug fix. No active script/test references it by name (confirmed by grep). |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix016_fix.nc` | superseded, retained | 2026-09-17 re-capture for 1DMIX-016. No active reference. |
| `inputs_from_mitgcm/mitgcm_ggl90_inputs_vermix_20_1dmix015_fix.nc` | superseded, retained | 2026-09-18 re-capture for 1DMIX-015 (despite the "015" name, dated *after* "016" — the fix issue numbers were not assigned in strict chronological-capture order). No active reference. |
| `outputs_from_mitgcm/mitgcm_ggl90_outputs_vermix_20*.nc` (the 3 non-current versions) | superseded, retained | Paired MITgcm outputs for the 3 superseded inputs above. No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20.nc` | superseded, retained | Paired with the original 2026-09-16 input; predates 1DMIX-015/-016/-041/-048. No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20_fixed.nc` | superseded, retained | Same 2026-09-16 input UUID as the plain `vermix_20.nc` output above — an intermediate re-run the same day (`_fixed` suffix, no corresponding "unfixed" input version — likely an early dt-bug-fix attempt before the 1DMIX-015 re-capture existed). No active reference. |
| `outputs_from_python/python_ggl90_outputs_vermix_20_1dmix016_fix.nc` | superseded, retained | Paired with the 2026-09-17 `_1dmix016_fix` input. No active reference. |

None of the "superseded, retained" files above are referenced by any script or
test under `MITgcm_to_Python_port_verification/{scripts,tests}` (grep-confirmed,
1DMIX-046) or by `VALIDATION_RESULTS.md`. They are kept only because deleting a
capture that later turns out to matter is harder to undo cleanly than keeping a
small `.nc` file; delete them in a future issue if disk space becomes a real
constraint (git-ignored, so removal does not touch history either way).
