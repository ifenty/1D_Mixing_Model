# Assessment: closing an issue's second iteration requires four undocumented steps, each discovered only by hitting its rejection

**Date**: 2026-09-28
**Observed on**: 1DMIX-058 iteration 2 (1D Mixing Model)
**Category**: reiteration_closeout_route_undiscoverable

## What happened

1DMIX-058 closed partial in iteration 1, leaving two failed turns behind: the
implementer's third correction round was refused for a stale orientation receipt, and
the reviewer's turn was refused because an approval needs a successful executed check
and no `must_fix` findings. Iteration 2 dispatched a fresh implementer and a fresh
reviewer, both completed, reviewer verdict `APPROVE`.

Assembling the closeout then failed four times in sequence. Each rejection named the
symptom accurately and none named the route:

| Attempt | Rejection | Actual requirement |
|---|---|---|
| 1 | `scope_decisions[0] needs a valid classification` | `separate_new` is not in the valid set; must file the issue first, then classify `separate_existing` |
| 2 | `bc2a550d…: current issue review completion is missing from subagents.richard` | Iteration 1's failed reviewer must be *referenced*, not omitted — and `waived` does not satisfy it, because waived entries are filtered out of `referenced` |
| 3 | `e9e7cebf…: attempt predates this iteration; retain it through --prior` | `prepare-done --prior <previous closeout>`; the prior closeout path is not recorded anywhere the closer reads |
| 4 | `bob: failed or incomplete turn remains unresolved` | `agent_continuity.replacements` needs an explicit `{role, old_id, new_id, reason, evidence_refs}` disposition per failed identity |
| 5 | `verification reference is required` | Completed outcome needs `verification.{structural,scientific,receipt}`, three separate evidence references |

Roughly ten minutes and five tool round-trips, all on bookkeeping, on an iteration
whose substantive work was already done and approved.

## Why this is worth fixing rather than remembering

None of the five requirements is wrong. Each is a real integrity property:

- A failed turn must not silently vanish from the record.
- A replacement reviewer must be dispositioned, not assumed.
- A completed scientific change must cite structural, scientific and final evidence.

The defect is discoverability, and it bites hardest exactly where it is least
affordable. A second iteration exists *because* the first one went badly — so the
closer is guaranteed to be carrying failed turns, and is therefore guaranteed to hit
this sequence. The cost is not paid by well-run issues; it is paid by the ones already
behind. And the pressure it creates is toward the wrong resolution: the fastest way
past attempt 2 looks like marking the failed reviewer `waived`, which would erase the
record of a review that did not happen. That path is closed only by accident of how
`referenced` filters waived entries, not by an error message explaining why it is
wrong.

There is also a genuine expressiveness gap behind attempt 1. A new issue discovered
*by the review* has no classification of its own. The valid set is `dependency`,
`introduced_regression`, `separate_existing`, `unknown`. To record "the reviewer found
a real coverage gap and I filed it as a new issue" you must file the issue, then call
it `separate_existing` — which reads, in the closed record, as though the issue already
existed and was merely referenced. That is a small but real loss of provenance: it
makes review-discovered work indistinguishable from pre-existing work.

## Proposed fix

Two parts, both cheap and both in `tools/esx`.

1. **Make `prepare-done` compute the route instead of rejecting on it.** It already
   reads the dispatch log and already knows the issue id. It can therefore find the
   issue's prior closeout in `loop_state/closed/`, detect unresolved failed turns for
   the current issue, and emit them in the draft as a `replacements` skeleton with
   `reason` and `evidence_refs` left empty for the closer to fill. Empty-reason entries
   still fail validation, so nothing is weakened — the judgment stays with the closer,
   only the archaeology is automated. Same for `--prior`: if a prior closeout for this
   id exists, use it and say so, rather than failing and asking for it.

2. **Add `separate_new` to the valid classification set**, with the same `issue_id`
   requirement as `separate_existing`. It carries strictly more information: that the
   issue was opened by this closeout rather than referenced by it. Validation is
   otherwise identical.

Optionally, name the required `verification` keys in that rejection message. The
current text explains what *not* to cite (a bare pytest run) without listing what a
completed scientific change must cite.

## Evidence

- `devel-loop/loop_state/dispatch_log.jsonl` — the two iteration-1 failures, with the
  `stale bob orientation` and `approval needs a successful executed check` errors.
- `devel-loop/loop_state/closed/issue-done-f15212f2483b2f8e8cf78f67892a5babed77dbf2abfd1d6dbc7da042995adbdb.json`
  — the prior closeout that `--prior` required.
- `tools/esx/workflow_policy.py::validate_scope_decisions` — the classification set.
- `tools/esx/workflow_policy.py::validate_reviews` and `::resolved_dispatch` — the
  `referenced` / `waived` interaction and the `replacements` requirement.
- `devel-loop/loop_state/fill_done_058_r2.py` — the final working assembly, showing
  every piece that had to be added by hand.
