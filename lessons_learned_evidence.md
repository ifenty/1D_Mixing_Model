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

## LESSON: The issue budget scope bounds the whole iteration, not one turn [LL-005]

**Date Identified**: 2026-09-28T04:55:00Z
**Confidence**: strongly supported

### Lesson and applicability
An issue's `team_budget` scope wall clock starts at its first dispatch and covers
every later dispatch, review round, final verification and Arch turn that
reserves. `--timeout` cannot extend past it. Applies to every `--prepare`.

### Observation
1DMIX-052 was prepared as `kind: documentation` with `--budget-kind` left to
default, allocating 30 minutes for a rewrite of roughly 1,040 lines of prose
across two files. A single Bob turn consumed the whole allocation and produced no
file change at all. Arch had dispatched with `--timeout 2700` believing a
45-minute turn bound against a 30-minute budget would reserve partial-handoff
headroom; the turn died at 1800.04 s.

### Mechanism
`team_budget.reserve` builds the turn deadline as `min(deadlines)` over the issue
scope's own deadline and the requested `turn_seconds`. A `--timeout` larger than
the scope's remaining wall time buys nothing. The scope's clock starts at the
first `reserve()` call and is absolute, so it covers every subsequent dispatch,
every review round, the final scientific suite and any Arch turn that reserves.

`team_budget.DEFAULTS` measured:

```
scientific_small    30 min   $15   120 calls   1 correction
documentation       30 min   $15   120 calls   1 correction
harness_change      45 min   $20   180 calls   1 correction
investigation       45 min   $20   180 calls   2 corrections
scientific_change  120 min   $60   500 calls   2 corrections
```

### Consequence observed
After exhaustion, scope `issue:1DMIX-052` showed wall 30/30 while calls stood at
13/120 and spend at $5/$15 — time was the only exhausted dimension. `reserve`
then refuses any further dispatch on that issue with `wall budget exhausted`, and
`team_budget.extend` requires an authorization file with `authorized_by: "Owner"`
that the code states a role may not invent. One sizing mistake converted routine
autonomous work into work blocked pending owner action.

### Contrast case
1DMIX-053 was prepared immediately afterwards with `--budget-kind
scientific_change` justified in the selection reason by measured work size. It
consumed 65 of 120 minutes, 139 of 500 calls and $14.70 of $60 across four
dispatches including an independent review and the final scientific suite, and
completed. The allocation class, not the workflow kind, was what differed.

### Limits and counterexamples
Choosing a larger allocation class does not weaken acceptance: `--budget-kind`
and `kind` are independent, and `loop_gate.py --help` documents
`scientific_small` as retaining full scientific review. No case was observed
where a larger allocation changed which gates applied.

### Recommended action
State the measured work size in the `--priority` selection reason and pick the
allocation class from it. Before each dispatch, read remaining scope wall time
with `team_budget.py inspect --issue ID` and set `--timeout` below it, leaving
room for the reviews and final verification that must fit inside the same scope.

---

## LESSON: Status fields fail optimistically; re-derive from the artifact they summarize [LL-006]

**Date Identified**: 2026-09-28T20:30:00Z
**Confidence**: strongly supported

### Lesson and applicability
A summary field — a receipt `status`, a ledger `Date Resolved`, a docstring's stated
mechanism, a report's quoted excerpt — is weaker evidence than the log, bytes or
source it summarizes, and when it drifts it drifts in the flattering direction.
Applies before acting on any such marker, and especially before spending anything
expensive (a re-run, a re-dispatch, re-opening an issue) on the strength of one.

### Evidence
Three independent instances, same window, all with structural checks passing.

1. **A receipt said `FAILED` where nothing failed.** `final-verification/c776b4b8….json`
   recorded `status: FAILED` at 2026-09-28T17:35:55Z with the error string
   `verification failed or source changed`. Its log
   `verification/run-9958b8af12e54753899315786d2b1b75.log` contains **zero** lines
   matching `FAILED|ERROR`, carries no pytest summary line, and stops mid-line at
   `test_global_ocean_cs32x15_pressure_coordinate_gap[visc_az-90.0-1000.0]` at `[ 70%]`
   of 123 collected tests — an interrupted process, not a failure. The identical suite
   completed `120 passed, 3 skipped` in 486.59s immediately before it and 655.58s after.
   Acting on the status alone would have meant re-opening a validated scientific
   candidate; the log settled it in one grep.

2. **The permanent ledger claimed a resolution nothing had qualified.** 1DMIX-057's
   `closed_issues.md` entry carried `Date Resolved: 2026-09-28T17:10:00Z` while the
   accepted closeout recorded `closed_at: 2026-09-28T20:20:28Z` — 3h10m apart. This is
   structural, not sloppiness: `loop_gate.py:158` requires the entry to be in
   `closed_issues.md` *before* `--check-done` will accept the closeout, so the record is
   always published ahead of its validation. Inside that window, a status question from
   the owner was answered from the ledger and reported 1DMIX-057 as closed.

3. **Tests asserted an unmeasured mechanism.** Recorded under 1DMIX-059: three `ghat`
   tests attributed their residual MITgcm disagreement to "the same hbl-misdiagnosis
   tail". None of the three attributions had ever been measured — each was inherited
   from a neighbouring test — and the claim had already been checked and disproved three
   times (1DMIX-056, 1DMIX-057, 1DMIX-058). A wrong mechanism recorded as fact in a test
   docstring had by then cost three separate iterations a correction round.

A fourth, same family, is filed as 1DMIX-062: a bug report's quoted port excerpt no
longer matches the source it cites, and the divergence suggests the documented bug was
silently fixed.

### Mechanism
The summary and the thing summarized are written at different times by different steps,
and only the summary is cheap to read. Nothing recomputes it. Worse, the integrity
machinery checks *structure* — that a field exists, that a count matches, that a
reference resolves — which is exactly the class of check that a stale-but-well-formed
summary passes. So drift accumulates silently and is only ever found by someone who
re-derives rather than reads.

### Limits and counterexamples
Not every status is suspect: a receipt whose `review_signature` matches the record it
is stored in, and whose log carries a pytest summary line, is sound evidence — that
combination is what established the 20:15:41Z PASS. The lesson is about the cost
asymmetry, not about distrust: re-deriving is seconds, and the wrong conclusion is a
re-run, a re-dispatch, or a false report to the owner.

### Recommended action
Before acting on a status marker, spend the one cheap check that re-derives it:
`grep -c 'FAILED\|ERROR'` on a verification log plus a check for its summary line;
`final_verification.py check --review … --owner …` and compare its printed
`review_signature` against the receipt's before trusting a prior PASS; for a
resolved-looking ledger entry, confirm an accepted `closed_at` exists in `loop_state`;
for a cited excerpt or stated mechanism, read the line it names.

## [LL-007] References re-derived instead of measured put wrong figures in the record

1DMIX-054 (2026-09-30): `test_global_ocean_90x40x15_dvsq_is_four_point_average` built its
column-local reference as `0.5*(du**2+dv**2)`, while the port computes `du**2+dv**2`
(`kpp_core_driver.py` line 669). The test's only assertion on that quantity was
`median > 0.1`, which held either way. The reviewer's own recomputation on the same
207,369 cells gave median 27% and 97.6% of cells above 1%, and the same slip was then
found in the `shear_sq` figure (51% and 98.8%, previously stated as 96.4%). Cost: one
correction round.

1DMIX-069/070 (2026-09-30): `test_isomip_mixing_length_ksrf_plus_1` asserted a lower
bound of 1e-4 on a "known gap" that was print quantization: 3.25e-4 at 16 significant
digits, 1.07e-13 at 17. The reviewer's re-quantization of the 17-digit capture to 16
digits reproduced the old residual exactly.

Both were caught only by an independent recomputation from primary data, and in both
the loose assertion had passed for the wrong reason.
