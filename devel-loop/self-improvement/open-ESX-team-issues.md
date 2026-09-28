# Open ESX-team Issues

This ledger tracks unresolved ESX-team effectiveness and process issues. These entries
are separate from ESX transformation issues and are not selected by `loop_gate.py --next`.

## Template for New Entries

```markdown
## 🔴 PROPOSED: [Brief title]

**Date Identified**: YYYY-MM-DD  HH:MM
**Status**: Proposed | Investigating | Implementing | Implemented — awaiting publication/effectiveness evidence | Blocked
**UUID**: TEAM-AREA-SHORT-NAME-001
**Category**: stable_lowercase_category
**Severity**: Critical | High | Medium | Low
**Assessment**: devel-loop/self-improvement/assessments/YYYY-MM-DD-name/assessment.md
**Anchors**: path[:symbol|:line]; ...
**Implementation-Reference**: path or WORKTREE (required after implementation)
**Blocked-By**: UUID | EXTERNAL | OWNER-DECISION (required only when blocked)

### Issue
[Measured inefficiency or procedural defect.]

### Evidence
[Retained observations, commands, records, timings, or costs.]

### Potential Impact
[Consequence for correctness, cost, time, or evidence integrity.]

### Proposed Fix
[Specific structural or procedural correction.]

### Acceptance Criteria
[Executable checks and required output.]

### Expected Effect
[Metric and expected direction, or a precise qualitative invariant.]
```

---

## 🔴 PROPOSED: A wall-clock dispatch timeout discards a turn whose durable work is already complete

**Date Identified**: 2026-09-27  20:10
**Status**: Proposed
**UUID**: TEAM-DISPATCH-TIMEOUT-001
**Category**: dispatch_timeout_truncation
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-27-dispatch-timeout-truncation/assessment.md
**Anchors**: tools/esx/agent_runtime.py::run_turn; tools/esx/bounded_command.py::run

### Issue
`agent_runtime.run_turn` bounds a retained dispatch by wall clock only. When the bound fires it terminates the process group (SIGTERM, `returncode` 143), records `status: failed, error: timeout`, and leaves the sealed report empty. Because the report is written last, the truncation point is uncorrelated with progress: the agent's source edits, rebuilt captures, new tests and measured timings are already durable on disk, and only the terminal narration is lost. Recovery requires a whole extra `followup` dispatch that redoes no measurement.

### Evidence
`devel-loop/loop_state/dispatch_log.jsonl`, 195 events: 12 events with `error == 'timeout'` out of 115 `bob`/`richard` role dispatches (10.4%), spanning 10 distinct issues (1DMIX-026, 032, 034, 039, 041, 042, 043, 048, 049, 050; bob 10, richard 2). Representative event `a173627c4cb841f488d3ea177051a7aa` (1DMIX-049, bob): `duration_seconds` 2400.04, `returncode` 143, report sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` — the digest of zero bytes. `closed_issues.md:1407` records the same event from the coordinator's side and confirms no rebuild or measurement was redone on recovery.

### Potential Impact
Wall clock and provider spend on re-narrating completed work: ~10 minutes per event conservatively, ~120 minutes across the 12 observed events. Raising `--timeout` is not the fix — it moves the boundary and raises the ceiling on a genuinely runaway turn, which is the cost the bound exists to cap. The integrity risk is separate and worse: a coordinator who does not check the filesystem may read `status: failed` as "nothing happened" and re-dispatch from scratch, redoing an expensive Docker rerun that already succeeded.

### Proposed Fix
Distinguish a turn that produced durable artifacts from one that produced nothing, and expose that distinction in the recorded event rather than leaving it to coordinator judgement. Candidate mechanism: on timeout, record the source signature delta observed during the turn (`source_signature_at_dispatch` is already captured at start) so the event states whether the tree changed, and have the recovery path in `devel-loop/recovery.md` key off that field instead of prose. This is a diagnosis-first issue: measure whether a progress-aware bound is achievable before changing the bound itself.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. A timeout event recorded after the fix states, in the event itself, whether the working tree changed during the turn — demonstrated by a test that drives a turn to timeout after a file write and asserts the field. `devel-loop/recovery.md` cites that field as the recovery decision input. No change to the wall-clock bound's default and no new authority to exceed it.

### Expected Effect
Metric: recovery dispatches per timeout event, measured from `dispatch_log.jsonl`. Direction: lower — a truncated-but-complete turn should need at most a report reseal, not a re-read-and-re-narrate turn. Qualitative invariant that must hold regardless: a timed-out turn never becomes acceptable to a downstream gate without a successful terminal report.

---

## 🔴 PROPOSED: An unverified quantitative figure entered an issue's own scoping text and nearly caused a wrong deferral

**Date Identified**: 2026-09-27  20:10
**Status**: Proposed
**UUID**: TEAM-ESTIMATE-EVIDENCE-001
**Category**: unverified_cost_estimate
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-27-unverified-cost-estimate/assessment.md
**Anchors**: closed_issues.md:1391; devel-loop/issue_priority.md

### Issue
1DMIX-049's filed text asserted that regenerating the `global_oce_latlon` KPP capture meant "8760 timesteps" and hours of wall clock. That figure belongs to a different experiment (`lab_sea`/1DMIX-026, hourly steps); `global_oce_latlon` uses 12-hour steps and `nTimeSteps=720`, directly confirmable from the experiment's own `data` file. The figure was obtained by grepping for a timestep count and taking a match without confirming which experiment's record it belonged to. Nothing in the issue-filing path requires a quantitative claim in an issue's scoping text to name where it was measured.

### Evidence
`closed_issues.md:1391` records the correction and the measured truth: 720 timesteps x 43,200 s = 360 days = one full `externForcingCycle`, and "the actual MITgcm run+parse for 720 timesteps is only ~15 minutes total, not the 'hours' this issue's own text anticipated". Measured directly: 6m52s for the full Docker run, 6m57s to reparse the 13.82 GB `output.txt`. Richard independently reconfirmed the reconciliation by reading both closed issues and grepping the live `data` file rather than accepting the narrative (`closed_issues.md:1401`).

### Potential Impact
The issue had been scoped around the wrong number — its bounded first step existed specifically to avoid committing to a supposedly multi-hour run, and that hedge cost more than the run it hedged against. A ~15-minute task was one step from being deferred as expensive, which would have left this project's only genuinely multi-tile, realistic-forcing KPP validation case lost for at least another iteration. Generally: a wrong number in an issue's own text is inherited by every later prioritization and deferral decision about that issue and is not re-derived unless deliberately challenged.

### Proposed Fix
Require any cost or scale figure that a filed issue's scoping depends on to name its source — the file and line, command, or receipt it was read from — so that a reader can check it without reconstructing the search that produced it. State in `devel-loop/issue_priority.md` that a deferral justified by cost needs a measured cheap prefix of the real command, not an estimate transferred from a neighbouring experiment's record. This is the mechanism that actually caught the error here, so the rule reflects observed practice rather than aspiration.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. `devel-loop/issue_priority.md` states the sourcing requirement for cost/scale figures and the measured-prefix requirement for cost-based deferral. A survey of the current root `open_issues.md` entries reports, per entry, whether each quantitative scoping figure names a checkable source — with the unsourced ones either sourced or removed.

### Expected Effect
Metric: number of quantitative scoping figures in filed issues lacking a named source, counted by that survey. Direction: lower, to zero for newly filed issues. Qualitative invariant: no issue is deferred on cost grounds without a measurement of the real command at reduced scale.
