# Assessment: the permanent issue ledger must publish a resolution before the gate will validate it

**Date**: 2026-09-28
**Owner issue**: TEAM-LEDGER-AHEAD-001
**Scope**: `tools/esx/loop_gate.py:158` against the measured close of 1DMIX-057 iteration 3.

## What happened

`loop_gate.py:158` requires, for a completed outcome:

```python
require(done['id'] in closed and done['id'] not in opened, 'completed issue must be in closed_issues.md')
```

So the entry must already have been moved out of `open_issues.md` and into
`closed_issues.md` before `--check-done` will accept the closeout. The permanent record
is therefore written first and validated second. When validation then fails — for any
reason, including an interrupted verification suite — the ledger is left asserting a
resolution that nothing has qualified.

## Measurement

The 1DMIX-057 entry in `closed_issues.md` carries `**Date Resolved**: 2026-09-28T17:10:00Z`.
The accepted closeout records `closed_at: 2026-09-28T20:20:28.881815+00:00`. For
**3 hours 10 minutes** the authoritative, permanent record stated the issue was Resolved
while the gate still had the iteration open and no passing final-verification receipt was
bound to the record. During that window the only receipt the record cited (`9aab3c9e…`)
was void, its `review_signature` no longer matching the record it was stored in.

The consequence was realized, not hypothetical. Asked for project status at approximately
19:40Z — inside the window — the readable sources were `open_issues.md`, `closed_issues.md`
and the notification ledger. All three were consistent with a closed 1DMIX-057, and the
status reported to the owner treated it as closed. The gate's own view, that the iteration
was still active and its verification unqualified, was visible only by running
`loop_gate.py --next`, which is not where a reader looks for issue state.

## Why this is structural rather than an operator error

Nothing was done out of order. The contract mandates this sequence: `prepare_done` sets
`open_issues_md_updated=True` unconditionally, and the gate then requires that the move
has happened. An Arch who moved the entry *after* a passing `--check-done` would simply
be unable to pass the gate. So the divergence window is not avoidable by care; it is
entailed by the ordering, and its width equals however long validation takes to succeed —
here, three hours across two sessions and two suite runs.

The integrity property behind the check is sound: a closeout claiming `completed` should
not be accepted while its issue still sits in `open_issues.md`. The defect is that the
check is written against the *final* state rather than against a state that distinguishes
"being closed" from "closed".

## Proposed fix

Give the ledger a way to represent an in-flight closeout, so the permanent record never
asserts an unqualified resolution. Either move the entry only on acceptance — the gate
performing the move itself, as the last step of `--check-done`, since it already parses
both files — or require the entry to carry an explicit pending-validation marker while
`issue-done.json` exists and no accepted `closed_at` does, with the gate clearing that
marker on acceptance. The first is preferable: it makes the permanent record a
consequence of validation rather than a precondition for it.

## Not measured

- Whether any other reader (a test, a report generator, `doc_contract`) treats
  `closed_issues.md` as authoritative for resolution state and would therefore also have
  been misled during the window. Only the status answer given to the owner was observed.
- How often this window is non-trivial in practice. One instance is measured at 3h10m;
  the distribution across this project's prior closeouts was not surveyed.
