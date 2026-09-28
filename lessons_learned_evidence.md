# Lesson evidence

One detailed entry per stable ID. Include counterexamples and the cost of being wrong.

## LESSON: Footer fields have exact required values, not free text [LL-001]

**Date Identified**: 2026-09-23T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
`candidate_signature` must be `project.py::source_signature(root)`'s value —
not `issue_candidates.py`'s own content-addressed signature (a different hash
scheme over differently-scoped data). `documentation_review.status` must be
the literal string `confirmed` (the reviewer's own act of confirming the
report), not `sealed` (the report's own state) or any other synonym.

### Evidence
Closing 1DMIX-026 required 4 separate correction rounds purely for footer
format after the substantive review was already correct: both Bob and
Richard independently reported the wrong signature scheme; Richard reported
`documentation_review.status='sealed'`; `independent_check.evidence` was left
as an empty `{"path":"","sha256":""}` reference from a plain pytest command.
Confirmed directly against `tools/esx/workflow_policy.py::current_review`/
`doc_contract.py`'s literal `require()` checks. This same `sealed` vs.
`confirmed` confusion recurred independently in an earlier issue too
(`confirmed_current` was used instead of the literal `confirmed`).

### Limits and counterexamples
None found — every occurrence of this confusion in this project's history
was a genuine formatting mismatch, never a case where the gate's own
requirement was actually wrong.

### Recommended action
Read `esx/templates/agent_report_guide.md` before writing a report. Compute
`candidate_signature` via `python3 tools/esx/project.py signature`, never by
hand or by reusing `issue_candidates.py check`'s own signature field.

## LESSON: A completed-but-unreferenced review is discarded, not correctable [LL-002]

**Date Identified**: 2026-09-23T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
`workflow_policy.py::known_completion_iteration()` only reuses a prior
dispatch across a re-`--prepare` if it is referenced in a prior
`loop_history.jsonl` row's `subagents` field. A real, substantively-correct
review that was never threaded into that field cannot be "fixed" later — it
must be redone from scratch under a fresh agent identity.

### Evidence
Across 9 issues / 49 dispatches in one 27-hour window, 11 dispatches (22%,
$24.40, 50.1 minutes) were full redos of a role under a different identity at
`correction_round=0` — not corrections, full discards. 1DMIX-030 had 5
distinct Richard identities and 2 distinct Bob identities all at round 0;
1DMIX-032 had 4 distinct Richard identities and 2 distinct Bob identities.
Root cause: `workflow_records.py selections --start issue-start.json`, which
lists every real dispatch for the active issue, was never used even once in
that entire window — its existence was not discoverable from any doc actually
read at the time.

### Limits and counterexamples
This does not mean every re-dispatch is a mistake — a genuinely stale or
superseded review should be redone. The lesson is specifically about
discarding a *still-valid* review due to a bookkeeping gap, not about when a
fresh review is scientifically warranted.

### Recommended action
Run `workflow_records.py selections` before building any `--select` file or
before deciding to redispatch a role "to be safe." `devel-loop/execution.md`
and `recovery.md` now open their packet-building recipes with this step.

## LESSON: Signature drift forces reclassification even with zero new code [LL-003]

**Date Identified**: 2026-09-23T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
`loop_gate.py::check_done()` requires `workflow.kind=='scientific_change'`
whenever the live scientific-path signature has drifted from an issue's own
frozen `numerical_signature_at_start` (set once, at first `--prepare`, never
refreshed). Any *other* `scientific_change` closure in the meantime causes
this drift for every other open issue, regardless of whether that issue's
own work touched anything scientific.

### Evidence
Hit at least 3 of 9 issues in one session window (1DMIX-027, 1DMIX-028,
1DMIX-031). One case (1DMIX-027) required discarding an entire completed
closeout attempt (a sealed 85-target documentation report, a structural
verification run) and redoing it via a confirmation-only Bob+Richard
redispatch — recorded in `loop_history.jsonl` as an iteration with
`iteration: null, start_timestamp: null`, itself a symptom of the discard.
By 1DMIX-031, the team had learned to pre-emptively classify as
`scientific_change` from the start, avoiding the discard.

### Limits and counterexamples
This is not a bug to route around — the gate exists to catch real drift a
reviewer hasn't seen, and a code fix to exempt "provably unrelated" drift was
deliberately not attempted (see `self-improvement/improvements_2026-09-23_from_1D_Mixing_Experiment.md`
in the ESX-Team framework repo for the full reasoning on why that tradeoff
was left as-is rather than weakened).

### Recommended action
When starting an issue expected to stay open across other issues' closures
(e.g. waiting on a long capture/build), default to `kind=scientific_change`
from the first `--prepare` rather than `investigation`/`harness_change`, even
if no source change is anticipated yet.

## LESSON: A workflow amendment must be re-applied to issue-done.json and closed_issues.md, not just the review packet [LL-004]

**Date Identified**: 2026-09-27T00:00:00Z
**Confidence**: strongly supported

### Lesson and applicability
Discovering mid-closeout that a `harness_change` issue must amend to
`scientific_change` (e.g. because a new test file triggers the tests-changed
drift check) requires fixing the amendment in *three* independent places:
(1) the review packet dispatched to Richard, (2) `issue-done.json`'s own
`workflow`/`workflow_amendment`/`maintenance.documentation` fields, and (3)
any `closed_issues.md` entry already written under the old, pre-amendment
assumption. Fixing only (1) — the packet actually reviewed — leaves (2) and
(3) silently stale, and an independent reviewer will catch the mismatch
against the *structured* record (`issue-start.json`, `workflow_records.py
selections`) even when the *reviewed content* is entirely correct.

### Evidence
1DMIX-042: discovered a documentation report had gone stale (9 untracked
Fortran build byproducts removed without a disposition), fixed it by
resealing at the review-packet level (`728ba10a...`), and dispatched Richard
against the corrected packet. Richard's round-0 review (`APPROVE_WITH_FIXES`)
still caught two bookkeeping gaps that the packet-level fix never touched:
`issue-done.json`'s `maintenance.documentation` still pointed at the original
stale seal (`1144b6d9...`), and `closed_issues.md`'s already-written
1DMIX-042 entry still said `Status: Resolved`, `kind: harness_change, 0
required reviewers` — both written before the amendment need was discovered,
neither updated once it was. Both were purely Arch's own closeout process
errors; Richard's own independent re-verification confirmed the actual test
content, tolerances, and permanentized captures were correct throughout.
Cost: a full extra round-1 dispatch (10 minutes, ~$5) purely to confirm two
bookkeeping edits that could have been made correctly the first time.

### Limits and counterexamples
None found — every case where this gap was checked, the structured record
(`issue-start.json`'s frozen original workflow, `workflow_records.py
selections`'s dispatch list) was the authoritative source Richard cross-
referenced against, and the packet-level fix alone was never sufficient.

### Recommended action
When amending a workflow mid-closeout, make all three edits in the same
pass: reseal/patch the review packet, update `issue-done.json`'s
`workflow`/`workflow_amendment`/`maintenance.documentation`, and rewrite the
`closed_issues.md` entry (if already written) — before dispatching the
reviewer, not after receiving a must_fix for the gap.
