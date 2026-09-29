# Assessment: Arch sized an issue allocation by workflow kind rather than by the work, and mis-modelled the effective turn deadline

**Date**: 2026-09-28
**Owner issue**: TEAM-BUDGET-SIZING-001
**Scope**: Arch's `loop_gate.py --prepare` allocation choice and `agent_runtime.py
start --timeout` choice, as exercised by the 1DMIX-052 iteration.

## What happened

1DMIX-052 asks for a rewrite of `VALIDATION_RESULTS.md` (781 lines) and a trim of
`README.md` (260 lines) — roughly 1,040 lines of prose across two files. Arch
prepared it as `kind: documentation` and let `--budget-kind` default to the same
value, which allocates 30 minutes. One Bob turn consumed the entire 30 minutes
and produced no file change at all.

## Measurement

Budget scope `issue:1DMIX-052` after the single turn:

```
limits:   {"minutes": 30, "usd": 15, "calls": 120, "corrections": 1, "turn_usd": 5}
started:  20:11:33   deadline: 20:41:33   (local)
wall:     30 / 30 minutes   EXHAUSTED
calls:    13 / 120
spend:    $5 / $15
```

Dispatch event `1eeea99a2d7c415fa1fcd78def37b01f`: `duration_seconds`
1800.044, `returncode` 143, `error` `timeout`.

Wall clock was the only exhausted dimension. Calls were at 11% and spend at 33%.

## Two distinct errors

### 1. Allocation sized by kind, not by work

`team_budget.DEFAULTS` gives `documentation` 30 minutes — tied with
`scientific_small` for the smallest time allocation of any class:

```
scientific_small   30 min    $15    120 calls
documentation      30 min    $15    120 calls
harness_change     45 min    $20    180 calls
investigation      45 min    $20    180 calls
scientific_change 120 min    $60    500 calls
```

The class name matched the *nature* of the work (documentation) but not its
*size*. `--budget-kind` exists precisely to decouple these — the flag's own help
text says it is an "allocation class" and notes that `scientific_small` "retains
full scientific review", i.e. the allocation and the acceptance contract are
independent. Arch did not use it, defaulting the allocation to the kind.

### 2. `--timeout` cannot exceed the issue scope deadline

Arch dispatched with `--timeout 2700` (45 minutes) on the stated reasoning that a
45-minute wall bound against a 30-minute budget would leave partial-handoff
headroom. That reasoning is wrong. `team_budget.reserve` computes:

```python
deadlines = [ledger['scopes'][k].get('deadline', ...) for k, c in scopes]
if turn_seconds is not None:
    deadlines.append(time.time() + turn_seconds)
receipt = {..., 'deadline': min(deadlines), ...}
```

The turn deadline is the **minimum** of the issue-scope deadline and the turn
timeout. A `--timeout` larger than the scope's remaining wall time buys nothing.
The turn died at 1800.04 s, not 2700 s, and the recorded receipt shows
`deadline` and `soft_deadline` 360 s apart — the scope's own values, not the
requested turn's.

## Potential impact

An undersized allocation on an atomically-shaped assignment produces a total
loss: the iteration spent 30 minutes and $5 for zero artifacts. Worse, the scope
is then exhausted and `reserve` refuses further dispatch on that issue, so the
issue cannot be retried without an explicit Owner budget extension
(`team_budget.extend`, which requires `authorized_by: "Owner"` and states a role
may not invent it). A single sizing mistake therefore converts routine work into
work that is blocked pending owner action.

The `--timeout` misunderstanding compounds this by making Arch believe a safety
margin exists when it does not, so no partial-handoff margin is actually
reserved.

## Proposed fix

Before dispatch, choose the allocation from a measured property of the work
(lines of prose to rewrite, files to touch, commands to run) rather than from the
workflow kind, and state that measurement in the selection reason. Compute the
effective turn deadline as `min(scope_remaining, requested_timeout)` and confirm
it leaves room for the partial handoff the brief asks for.

## Not measured

- Whether 120 minutes would in fact suffice for this particular rewrite. No
  completed run exists to measure against; the next attempt provides the first
  real datum.
- Provider cost. `cost_usd` for the turn is `null` and the event is listed in
  `unknown_cost_event_ids`; the $5 figure is the retained reservation, not a
  reconciled invoice amount.
