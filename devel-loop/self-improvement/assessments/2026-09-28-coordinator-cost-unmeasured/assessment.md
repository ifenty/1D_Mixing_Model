# Assessment: the coordinator's cost is structurally unmeasurable, so the self-improvement program under-measures the thing it evaluates

**Date**: 2026-09-28
**Owner issue**: TEAM-COORDINATOR-COST-001
**Scope**: `tools/esx/team_accounting.py::summary` against all eight accepted retrospectives
in `devel-loop/loop_state/retrospective_history.jsonl`.

## What happened

`team_accounting.py:227` computes `'coordinator_coverage': 'recorded' if 'arch' in roles
else 'missing'`. So the framework anticipates Arch costs and has a field to report them.
It has never received any.

## Measurement

Every accepted retrospective in this project's history reports `coordinator_coverage: missing` — **20 of 20 records across 13 distinct issues**, re-derived by the reviewer over the full `retrospective_history.jsonl` population. `by_role` composition varies by iteration (bob-only, bob+richard, and two rows with neither), so the gap is not a sampling artifact. The eight final-iteration records this assessment was first written from:

```
1DMIX-055  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-059  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-058  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-057  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-052  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-061  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-062  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
1DMIX-063  cost_usd keys: ['bob', 'richard']  coordinator_coverage: missing
```

Twenty for twenty. The cause is structural rather than an omission: Arch is the interactive
main session, not a dispatched agent, so no entry in `dispatch_log.jsonl` meters it and no
`accounting` record can attribute usage to it.

## Why this matters more than a missing number

The omitted share is not marginal. In the five-issue loop of 2026-09-28, Arch performed all
packet assembly, all ledger writing, every independent verification of an implementer's
headline claim, and all five `final_verification.py` runs — the scientific suite alone ran
five times at 496 to 656 seconds each, roughly 50 minutes of measured wall clock, all of it
Arch's. Meanwhile 1DMIX-063's retrospective reports the iteration as "40 minutes, one round
each, bob $2.30 and richard $2.02". Both statements are true; together they imply a total
cost that is wrong by a large factor.

The consequence lands specifically on this program. Retrospectives exist to let workflow cost
"be evaluated empirically" and to decide questions like whether a reviewer round was worth
its price. Those judgments are being made against figures that exclude the coordinator —
which systematically favours conclusions like "the review was expensive relative to the
work", because the reviewer's cost is metered and the coordination around it is free by
construction.

## Proposed fix

Two honest options, and the choice is the Owner's rather than Arch's.

Either make it measurable — have the main session write its own accounting record per
iteration phase, which `team_accounting.summary` already has a shape for, so
`coordinator_coverage` can read `recorded`; or accept it as a permanent limit and say so
where the numbers are consumed, so that `span_minutes` and `cost_usd` are explicitly labelled
as dispatched-agent-only and no reader infers a total. The present state is the worst of the
two: a field that names the gap, reports it every time, and is never acted on.

## Not measured

- Arch's actual token or dollar usage for any iteration. That is precisely what is
  unavailable; the 50 minutes of suite wall clock above is measured, the coordination
  turns around it are not.
- Whether any prior retrospective's conclusion would change under full accounting. Plausible
  for the cost-of-review judgments, but not established.
