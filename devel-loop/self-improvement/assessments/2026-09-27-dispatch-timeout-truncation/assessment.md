# Assessment: retained-dispatch wall-clock timeout truncates a turn whose work is already complete

**Date**: 2026-09-27
**Owner issue**: TEAM-DISPATCH-TIMEOUT-001
**Scope**: `tools/esx/agent_runtime.py` turn bounding, as exercised by this project's
1DMIX-021 through 1DMIX-051 iterations.

## Measurement

Source: `devel-loop/loop_state/dispatch_log.jsonl` (195 events at time of measurement).

```
timeout events (error == 'timeout'):        12
bob/richard dispatch events:               115
timeout share of role dispatches:         10.4 %
roles affected:                  bob 10, richard 2
distinct issues affected:                   10
  1DMIX-026, 1DMIX-032, 1DMIX-034, 1DMIX-039, 1DMIX-041,
  1DMIX-042, 1DMIX-043, 1DMIX-048, 1DMIX-049, 1DMIX-050
```

A representative record (the 1DMIX-049 implementation turn):

```json
{"event_id": "a173627c4cb841f488d3ea177051a7aa", "agent_type": "bob",
 "agent_id": "f627bae1-9fea-44c0-b0bd-357ba769c03a", "issue_id": "1DMIX-049",
 "status": "failed", "error": "timeout", "execution_phase": "executed_failed",
 "duration_seconds": 2400.0355571249966, "returncode": 143,
 "report": {"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}}
```

`returncode` 143 is SIGTERM from the wrapper's own process-group termination.
The report digest `e3b0c442...` is the SHA-256 of zero bytes: the sealed report
file is created and left empty.

## Mechanism

`agent_runtime.run_turn` bounds a provider turn by wall clock and, on expiry,
terminates the process group through `bounded_command.run`. That bound is
honest and necessary — an unbounded turn would spend indefinitely. The defect is
that the bound is *only* wall clock, and the truncation point is uncorrelated
with progress:

1. The agent's filesystem work is already durable when the bound fires
   (source edits, rebuilt captures, new tests, measured timings).
2. Only the terminal act — writing the structured report and its footer — is
   lost, because that happens last.
3. The event is recorded `status: failed`, so no downstream gate will accept it.

Recovery is `agent_runtime.py followup` against the same retained session, which
costs a fresh dispatch: the agent re-reads its own context and rewrites the
report. In 1DMIX-049 this is recorded directly in the closed issue's own
Traceability section ("killed once by the harness's own 40-minute timeout after
the substantive rebuild/rerun/test-writing work was already fully complete, and
resumed via `followup` to finish the documentation seal and report; no rebuild or
measurement was redone").

## Why raising the timeout is not the fix

Raising `--timeout` from 2400 s moves the boundary without removing it, and it
raises the ceiling on a genuinely runaway turn — the exact cost the bound exists
to cap. The asymmetry worth fixing is that a turn which has *produced durable
artifacts* is treated identically to a turn that has produced nothing.

## Quantified cost

Each of the 12 events required one recovery dispatch. Observed recovery turns in
this project ran roughly 5–15 minutes of wall clock each (they re-read context
and write a report; they redo no measurement). Attributing a conservative
10 minutes per event gives ~120 minutes of coordinator and provider time spent
re-narrating work that was already on disk.

## Not measured

- Provider cost per recovery dispatch. This project's accounting instrumentation
  (ESX 1.1.x) postdates most of these events; `measured.cost_usd` is empty for
  the 1DMIX-049 closeout and no invoice reconciliation exists. The minute figures
  above are wall clock only and are explicitly not a billing claim.
- Whether any of the 12 turns would have exceeded a larger bound anyway.
