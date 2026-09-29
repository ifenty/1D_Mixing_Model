# Assessment: a write-once baseline makes late closure of a long-open issue disproportionate

**Date**: 2026-09-28
**Owner issue**: TEAM-BASELINE-PIN-001
**Scope**: `doc_contract.baseline` / `original_baseline` pinning, as met when closing
1DMIX-057 two days and four closures after its first iteration.

## Measurement

`doc_contract.draft` against 1DMIX-057's original baseline returns **72**
disposition targets. Attribution of those targets:

| origin | targets |
|---|---|
| 1DMIX-058 (`ghat` compute-vs-apply) | `kpp_scheme_specific.py`, `mixing_adapter.py`, `unified_driver.py`, `test_kpp_ghat_gate.py` |
| 1DMIX-059 (`use_doublediff` guard) | `kpp_parameters.py::__post_init__`, `test_kpp_doublediff_guard.py`, `kpp_default_parameters.yaml` |
| 1DMIX-060 (per-capture `ghat` attributions) | four `test_kpp_mitgcm_validation_extended.py` docstrings |
| 1DMIX-054 (bounded first step) | 18 new files under two `*_code_validation/` directories |
| ESX 1.2.0/1.2.1 upgrade | `tools/esx/{team_budget,brief,agent_runtime,team_driver}.py`, `devel-loop/team_operations.md` |
| **1DMIX-057 itself** | `kpp_parameters.py::KPPParameters`, `kpp_routines.py::wscale`, two `global_oce_latlon` tests |

So roughly four of every five targets belong to something else.

## Why the pin exists and why it is right

`baseline()` documents it plainly: *"A write-once pin prevents a fresh
working-tree capture from hiding cumulative edits."* Without it, an issue left open
while the tree moved could take a fresh snapshot and silently launder every
intervening change through its own approval. That is a real integrity property and
should not be removed.

## Why the consequence is nevertheless wrong

The pin's cost falls on the wrong event. An issue whose remaining work is one
reviewer confirmation becomes a 72-target documentation exercise, and producing
that report would state under 1DMIX-057 that documentation is accurate for four
other issues' work plus a framework upgrade. Each of those already documented its
own changes under its own baseline; re-dispositioning them here adds no integrity
and actively misattributes.

`draft(previous_ref=...)` cannot bridge this: it reuses judgments only from a
sealed report sharing the same baseline, and the other reports each used their own.

## Not measured

- Whether a "carried-forward, already-dispositioned elsewhere" disposition class
  could preserve the integrity property while avoiding misattribution. Untested;
  it would need to prove the target was dispositioned under some sealed report
  whose baseline is an ancestor.
- How often this arises. One instance examined; the pattern requires an issue to
  stay open across other closures, which this project did five times at once.
