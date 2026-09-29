# Assessment: an implementer who edits the targets he was oriented on always invalidates his own receipt, costing a round

**Date**: 2026-09-28
**Owner issue**: TEAM-ORIENTATION-RESEAL-001
**Scope**: Arch's dispatch sequencing against `doc_contract.validate_orientation`'s
freshness requirement, as exercised by the 1DMIX-053 iteration.

## What happened

Bob's 1DMIX-053 round-1 turn completed every remaining step of the assignment and
its acceptance tests passed. It was nevertheless recorded
`status: incomplete`, `error: stale bob orientation`, listing three targets whose
bytes had changed since his receipt was taken:

```
docs/code_map.md#verification-routes                                  documentation
MITgcm_to_Python_port_verification/scripts/compare_scenario_standalone.py::compare
                                                                      source, module_context
MITgcm_to_Python_port_verification/README.md                          documentation
```

A whole extra round (event `54231c2814c94c52be5b3cc9a0977296`, 115 s, roughly
$1.81) was spent doing nothing but re-navigating and returning a fresh footer. No
implementation, no measurement, no test was redone.

## Why this is structural rather than a mistake by the implementer

The orientation contract requires the receipt to bind to the bytes a reviewer will
see. The assignment required editing `docs/code_map.md#verification-routes` and
`compare_scenario_standalone.py::compare` — two of the three targets Arch itself
chose for the orientation. The outcome was therefore determined at dispatch time:
any implementer who did the assigned work correctly would invalidate his own
receipt, and no amount of care on his part could avoid it.

This is not the framework being wrong. Freshness is exactly what makes the receipt
worth anything to a reviewer. The defect is that Arch selected orientation targets
that the work was certain to modify, and then did not tell the implementer to
re-navigate as the final act of the turn.

## Measurement

1DMIX-053 accounting: 4 dispatches (bob 3, richard 1), 65-minute span, $14.70
total ($10.93 bob, $3.77 richard). One of bob's three rounds existed solely for
the reseal. The wasted fraction is small in money but it consumed a correction
round against a `corrections: 2` limit, which is the scarcer resource — a third
genuine correction would have been refused.

## Proposed fix

When the assignment will modify a target chosen for orientation — which is the
normal case for implementation work, not an edge case — instruct the implementer
in the brief to re-run `doc_contract.py navigate` and recompute
`project.py signature` as the final step before writing the report. That turns a
whole extra round into two tool calls inside the turn that was already running.

A stronger variant worth measuring: have the generated brief derive this
instruction automatically whenever the orientation target set intersects the
declared work targets, so it does not depend on Arch remembering.

## Not measured

- How often this has occurred historically. Only this instance was examined;
  `dispatch_log.jsonl` would need a survey of `stale .* orientation` errors to
  establish a rate, and that survey was not run.
- Whether the automatic-brief variant is feasible without the brief generator
  knowing which targets the work will touch, which it currently does not.
