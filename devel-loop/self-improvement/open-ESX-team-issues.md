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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DISPATCH-TIMEOUT-001
**Category**: dispatch_timeout_truncation
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-27-dispatch-timeout-truncation/assessment.md
**Anchors**: tools/esx/agent_runtime.py::run_turn; tools/esx/bounded_command.py::run
**Implementation-Reference**: ESX-Team 1d35c94 (1.2.0), deployed; tools/esx/agent_runtime.py:660 records `source_changed_during_turn`

### Implementation Status
Implemented upstream in ESX 1.2.0 and deployed here (`tools/esx` byte-identical to ESX-Team 1.4.0 template, checked 2026-09-29). Remaining against acceptance: the upstream test (`tests/test_parity_integration.py:138`) covers only the no-write timeout, not a write-then-timeout asserting `true`; `devel-loop/recovery.md` does not yet cite the field (only `team_operations.md:59` does); no post-upgrade timeout event observed yet.

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
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-ESTIMATE-EVIDENCE-001
**Category**: unverified_cost_estimate
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-27-unverified-cost-estimate/assessment.md
**Anchors**: closed_issues.md:1391; devel-loop/issue_priority.md
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

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

---

## 🔴 PROPOSED: Issue allocations are chosen by workflow kind rather than by measured work size, and `--timeout` is assumed to extend a turn past its scope deadline

**Date Identified**: 2026-09-28  03:50
**Status**: Implementing
**UUID**: TEAM-BUDGET-SIZING-001
**Category**: budget_allocation_sizing
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-budget-allocation-sizing/assessment.md
**Anchors**: tools/esx/team_budget.py::reserve; tools/esx/team_budget.py::limits; tools/esx/loop_gate.py::Gate.prepare
**Implementation-Reference**: ESX-Team 1d35c94 (1.2.0), 1907d03 (1.2.1), 67f6191 (1.2.2), deployed; tools/esx/team_budget.py::reserve

### Implementation Status
Partially implemented upstream. Done: `reserve` no longer refuses on exhausted wall time (overruns are recorded, not enforced), so an undersized allocation can no longer make an issue owner-blocked; effort is measured as summed dispatch duration rather than calendar span. Not done: sizing allocations from measured work size, naming that measurement in the `--prepare` reason, surfacing remaining scope time in `--next` or the brief. `--timeout` is still clamped by a still-future scope deadline (`min(deadlines)`), so the original misunderstanding remains possible though no longer blocking.

### Issue
Two compounding pre-dispatch modelling errors. First, Arch let `--budget-kind` default to the workflow `kind`, so a roughly 1,040-line prose rewrite across two files was allocated the `documentation` class's 30 minutes — tied with `scientific_small` for the smallest time allocation of any class. The class name matched the nature of the work but not its size, and `--budget-kind` exists precisely to decouple those. Second, Arch dispatched with `--timeout 2700` believing a 45-minute wall bound against a 30-minute budget would reserve partial-handoff headroom; `team_budget.reserve` takes `min(deadlines)` across the issue scope and the requested turn, so a `--timeout` larger than the scope's remaining wall time buys nothing and the believed margin did not exist.

### Evidence
Scope `issue:1DMIX-052` after one turn: `limits` minutes 30, usd 15, calls 120; started 20:11:33, deadline 20:41:33 local; wall 30/30 EXHAUSTED while calls stood at 13/120 and spend at $5/$15 — wall clock was the only exhausted dimension. Dispatch event `1eeea99a2d7c415fa1fcd78def37b01f`: `duration_seconds` 1800.044, `returncode` 143, `error` timeout — it died at the scope's 1800 s deadline, not the requested 2700 s, and its receipt's `deadline`/`soft_deadline` are 360 s apart, which are the scope's values rather than the requested turn's.

### Potential Impact
An undersized allocation on an atomically-shaped assignment is a total loss: this iteration spent 30 minutes and $5 of reservation for zero artifacts. The consequence then escalates, because the exhausted scope makes `reserve` refuse any further dispatch on that issue, and `team_budget.extend` requires an explicit Owner authorization that a role may not invent. One sizing mistake therefore converts routine autonomous work into work blocked pending owner action. The `--timeout` misunderstanding compounds it by making Arch believe a partial-handoff margin is reserved when none is.

### Proposed Fix
Choose an allocation from a measured property of the work — lines of prose to rewrite, files to touch, commands to run, expected command wall time — rather than from the workflow kind, and state that measurement in the `--priority` selection reason so the choice is auditable. Before dispatch, compute the effective turn deadline as `min(scope_remaining, requested_timeout)` and confirm it leaves room for the partial handoff the generated brief asks for. Consider surfacing the remaining scope wall time in `--next` or in the generated brief so the number is present at the moment the decision is made rather than requiring a separate `team_budget.py inspect` call.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. Every subsequent `--prepare` selection reason in `loop_history.jsonl` names the measured work size that justified its allocation class. No dispatch is issued with a `--timeout` exceeding the remaining scope wall time; demonstrated by a recorded pre-dispatch check of `team_budget.py inspect --issue ID` against the chosen timeout. A closing record must show at least one iteration whose allocation was sized this way and completed without exhausting its wall budget.

### Expected Effect
Metric: fraction of iterations whose wall budget is exhausted with zero durable artifacts, measured from `loop_history.jsonl` outcomes against `budget_ledger.json` scopes. Direction: lower, target zero. Qualitative invariant: no iteration becomes owner-blocked because of an allocation Arch could have sized correctly from information available before dispatch.

---

## 🔴 PROPOSED: An implementer who edits the targets he was oriented on always invalidates his own receipt, costing a whole correction round

**Date Identified**: 2026-09-28  04:55
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-ORIENTATION-RESEAL-001
**Category**: stale_orientation_after_self_edit
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-orientation-reseal/assessment.md
**Anchors**: tools/esx/doc_contract.py::validate_orientation; tools/esx/brief.py::build
**Implementation-Reference**: ESX-Team 1d35c94 (1.2.0), deployed; tools/esx/brief.py:31 emits "Reseal before reporting"

### Implementation Status
Implemented upstream in ESX 1.2.0 (the stronger automatic variant: every implementer brief carries the reseal instruction listing the oriented targets) and deployed here. Remaining against acceptance: one implementation iteration that modifies an oriented target and completes without a reseal-only correction round.

### Issue
Bob's 1DMIX-053 round-1 turn completed every remaining step of its assignment with passing acceptance tests, yet was recorded `status: incomplete`, `error: stale bob orientation`, because three of the targets its receipt was taken against had changed: `docs/code_map.md#verification-routes`, `compare_scenario_standalone.py::compare` and the verification `README.md`. Two of those three were targets Arch itself chose for the orientation, and the assignment required editing them. The outcome was therefore determined at dispatch time: any implementer doing the assigned work correctly would invalidate his own receipt, and no care on his part could avoid it. Nothing in the dispatch path warns Arch about this intersection or tells the implementer to reseal before reporting.

### Evidence
Dispatch event `ad8bbaf32cb9407f8e9ed01fb5d3c3ec` (1DMIX-053, bob, round 1): `status` incomplete, `error` beginning `stale bob orientation`, naming the three changed targets with their before/after component hashes. The follow-on reseal round, event `54231c2814c94c52be5b3cc9a0977296`, ran 115 s at roughly $1.81 and did no implementation, no measurement and no test — its own summary records "Round 2: no new implementation." Iteration accounting: 4 dispatches (bob 3, richard 1), 65-minute span, $14.70 total.

### Potential Impact
The money is small but the scarce resource is correction rounds: the reseal consumed one of a `corrections: 2` allocation, so a third genuinely-needed correction would have been refused by `team_budget.reserve`. The failure mode also misreports a successful turn as `incomplete`, which invites a coordinator who does not read the error text to assume the work failed and re-dispatch it. Because implementation work normally modifies the symbols it was oriented on, this is the common case rather than an edge case.

### Proposed Fix
When the assignment will modify a target chosen for orientation, instruct the implementer in the brief to re-run `doc_contract.py navigate` and recompute `project.py signature` as the final step before writing its report, converting an extra round into two tool calls inside the turn already running. A stronger variant worth measuring: have `brief.py::build` emit that instruction automatically whenever the orientation target set intersects the declared work targets, so correctness does not depend on Arch remembering. That variant needs the brief generator to know which targets the work will touch, which it currently does not, so scope it as a measurement first.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. A survey of `dispatch_log.jsonl` reports the historical rate of `stale .* orientation` errors, establishing whether this is frequent enough to warrant the automatic variant. Every subsequent implementation brief that touches an orientation target carries the reseal-before-report instruction. A closing record must show at least one implementation iteration that modified an oriented target and completed without spending a correction round on a reseal.

### Expected Effect
Metric: correction rounds spent solely on orientation reseal, counted from `dispatch_log.jsonl` against rounds that changed no file. Direction: lower, target zero. Qualitative invariant: a turn that completes its assignment is never recorded `incomplete` for a reason that was determined before it started.

---

## 🔴 PROPOSED: Changing a named default invalidates statements across documents nobody enumerated, and each one a reviewer finds costs a correction round

**Date Identified**: 2026-09-28  07:45
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DOC-SWEEP-001
**Category**: documentation_staleness_sweep
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-doc-staleness-sweep/assessment.md
**Anchors**: tools/esx/brief.py::build; tools/esx/doc_contract.py::validate_report
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
1DMIX-057 flipped the `keep_mitgcm_bugs` default. That invalidated statements in five separate documents, but Arch scoped the brief around only the three it had thought of, and the other two -- plus three further unannotated spots inside one of them -- surfaced one reviewer round at a time. The documentation contract's own disposition machinery does not help here: it enumerates targets in the *changed candidate*, and these stale documents were not changed by the work, which is precisely why they were missed. Nothing in the dispatch path asks the obvious question, which is which documents currently mention the symbol whose meaning is about to change.

### Evidence
Round 0 updated `kpp_parameters.py`, `kpp_routines.py` and `docs/model_contract.md`. Richard's round-0 must_fix added `KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md` and `.../critical_lessons_fortran_to_python_porting.md`, both stating `keep_mitgcm_bugs=False` as the current default and recommending it. His round-1 must_fix added three further unannotated spots inside the first of those: the line-240 "fixes this bug by default" sentence, a `kpp_parameters.py` code excerpt showing the old default, and a Validation Impact bullet appearing above the superseded block so a top-to-bottom reader meets it as current fact. Bob hit the scope's `corrections: 2` limit and the soft deadline passed; Arch made the final three annotations directly and the iteration closed `partial` with the reviewer confirmation outstanding. A single `grep -rn keep_mitgcm_bugs` at brief time would have found all five files.

### Potential Impact
Each reviewer-discovered document costs a full correction round against an allowance of two, so a change touching three or more stale documents cannot complete within one iteration's allowance no matter how well the work itself is done -- which is exactly what happened here. The integrity cost is worse than the time cost: between the flip landing and the last annotation, the repository simultaneously shipped a default and documented its opposite, which is the specific condition 1DMIX-057 existed to eliminate.

### Proposed Fix
Before briefing any change to a named default, symbol or documented contract, run a repository-wide search for that name and enumerate every document that mentions it, then list them in the brief as explicit targets with their line numbers. Prefer `grep -rn` over recollection. Consider having `brief.py::build` accept a symbol name and emit that enumeration automatically, so the step does not depend on Arch remembering; measure first whether the search is precise enough to be useful without drowning the brief in matches.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. Every subsequent brief that changes a named default or documented contract lists the enumerated mentioning documents as explicit targets, demonstrated by the brief files retained in loop state. A closing record must show at least one such iteration completing with zero reviewer-discovered stale documents.

### Expected Effect
Metric: correction rounds whose sole content is documentation staleness a reviewer discovered, counted from `dispatch_log.jsonl` against the retained briefs. Direction: lower, target zero. Qualitative invariant: the repository never simultaneously ships a behaviour and documents its opposite across a completed iteration boundary.

---

## 🔴 PROPOSED: The `scientific_change` per-turn spend cap sits below the measured cost of a long implementation turn, and a cents-scale overshoot hard-blocks the whole issue

**Date Identified**: 2026-09-28  11:30
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-TURN-CAP-001
**Category**: turn_cap_breach
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-turn-cap-breach/assessment.md
**Anchors**: tools/esx/team_budget.py::settle; tools/esx/team_budget.py::reserve; tools/esx/team_budget.py::extend
**Implementation-Reference**: ESX-Team 1d35c94 (1.2.0), deployed; tools/esx/team_budget.py::reserve

### Implementation Status
Implemented upstream in ESX 1.2.0 by removing enforcement rather than retuning the threshold: `team_budget` refuses nothing, exceeded dimensions are recorded as overruns, and `--max-budget-usd` is no longer passed to the provider. `turn_usd` survives only as the default reservation amount. Remaining against acceptance: one `scientific_change` iteration with a long implementation turn completing without a blocked scope.

### Issue
`team_budget.DEFAULTS['scientific_change']` sets `turn_usd` to 12, but long Bob implementation turns in this project measure $11 to $19. 1DMIX-054's single turn reserved $12.00 and the provider reported $12.735075, so `settle` recorded `provider_overshoot` and set `breached: True` on the scope. That refuses every further launch, and `extend` refuses a breached scope outright on the stated grounds that a breach requires reconciliation rather than a budget extension. A $0.74 overshoot therefore hard-blocked an issue that still had roughly half its wall clock, 400 of 500 calls and $48 of $60 unspent — a strictly harsher and less recoverable outcome than ordinary wall exhaustion, attached to the one quantity nobody controls.

### Evidence
Scope `issue:1DMIX-054`: `limits` minutes 120, usd 60, calls 500, turn_usd 12; `breached: true`; single reservation `01e3fa34e787` with `reserved_usd` 12.00, `reported_usd` 12.735075499999999, `provider_overshoot` true, status settled. Measured long Bob turn costs this session: 1DMIX-056 r0 $11.17, 1DMIX-060 r0 $16.95, 1DMIX-058 r0 $17.12, 1DMIX-057 r0 $18.91, 1DMIX-054 r0 $12.74. Four of five exceeded the $12 cap. Reading `reserve`, `amount = min(amount, available)` clamps a reservation to remaining scope spend, which plausibly explains why the larger turns did not trip the same comparison — that interaction is inferred from the source, not tested.

### Potential Impact
An issue can be rendered permanently undispatchable by a provider pricing decision of less than a dollar, with no recovery path short of reconciliation, while most of its allocation is unused. Because the cap sits below the central tendency of the turns the class funds, this is a latent hard stop on roughly any long implementation turn rather than a rare event. It also inverts the intended severity ordering: the recoverable failure is the one Arch controls (wall sizing) and the unrecoverable one is the one Arch does not.

### Proposed Fix
First establish whether the cap is being compared against the right quantity, given that `reserve` clamps reservations to remaining scope spend — if the effective comparison differs from the nominal cap, the fix is to that logic rather than to the number. Then either raise `turn_usd` for `scientific_change` above the measured distribution of long implementation turns with deliberate headroom, or make breach require exceeding the reservation by a material margin rather than by any amount, so that a cents-scale provider variance cannot consume a scope. Keep the breach concept for genuine runaway spend; the objection is to its trigger threshold, not its existence.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. A recorded measurement of long-turn cost distribution per role, and a stated `turn_usd` chosen from it with its headroom justified. A test that drives a turn to a small overshoot and asserts the scope is not breached, alongside the existing behaviour for a large overshoot. A closing record must show at least one `scientific_change` iteration whose long implementation turn completed without breaching.

### Expected Effect
Metric: scopes rendered undispatchable by `breached` while more than half their spend allocation remains, counted from `budget_ledger.json`. Direction: lower, target zero. Qualitative invariant: no issue becomes unrecoverable because of a sub-dollar provider variance, and genuine runaway spend still halts immediately.

---

## 🔴 PROPOSED: A write-once baseline makes late closure of a long-open issue disproportionate and forces misattribution

**Date Identified**: 2026-09-28  13:50
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-BASELINE-PIN-001
**Category**: pinned_baseline_makes_late_closure_disproportionate
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-baseline-pin/assessment.md
**Anchors**: tools/esx/doc_contract.py::baseline; tools/esx/doc_contract.py::original_baseline; tools/esx/doc_contract.py::draft
**Implementation-Reference**: ESX-Team 9b7d34a (1.4.0), deployed; tools/esx/doc_contract.py `carried_forward` disposition

### Implementation Status
Implemented upstream in ESX 1.4.0 via a `carried_forward` disposition prefilled by `draft()`. The proof is exact target byte state judged under another issue's completed closeout, not baseline ancestry; `validate_report` re-derives it. Upstream tests in `tests/test_workflow_ergonomics.py` cover both directions. Remaining: a closure in this project demonstrating the reduced disposition count.

### Issue
`doc_contract.baseline` pins an issue's baseline write-once, deliberately, so that a fresh working-tree capture cannot hide cumulative edits. The consequence is that an issue left open across other closures accumulates their changes into its own candidate diff. Closing 1DMIX-057 — whose only outstanding item was a reviewer confirmation of three documentation annotations — required dispositioning 72 targets, roughly four in five belonging to four other issues and to a framework upgrade. Producing that report would assert under 1DMIX-057 that documentation is accurate for work those issues already dispositioned under their own baselines, which adds no integrity and actively misattributes. `draft(previous_ref=...)` cannot bridge the gap because it reuses judgments only from a sealed report sharing the same baseline.

### Evidence
`doc_contract.draft` against 1DMIX-057's original baseline returns 72 dispositions. Attribution: 1DMIX-058 contributed `kpp_scheme_specific.py`, `mixing_adapter.py`, `unified_driver.py` and `test_kpp_ghat_gate.py`; 1DMIX-059 contributed `kpp_parameters.py::__post_init__`, `test_kpp_doublediff_guard.py` and `kpp_default_parameters.yaml`; 1DMIX-060 contributed four test docstrings; 1DMIX-054 contributed 18 new files across two `*_code_validation/` directories; the ESX 1.2.0/1.2.1 upgrade contributed four `tools/esx` modules and `devel-loop/team_operations.md`. Only four targets belong to 1DMIX-057 itself. `baseline()`'s own docstring states the pin's purpose.

### Potential Impact
The cost lands on the wrong event: a one-step remainder becomes a large mechanical task, and the only cheap ways out are both bad — misattribute other issues' work, or leave the issue open indefinitely so the diff grows further. It also creates pressure to fabricate a rebaseline, which the pin exists to prevent. In this project it blocked the clean closure of a validated scientific change whose own contribution was four targets.

### Proposed Fix
Preserve the integrity property and remove the misattribution. The candidate direction is a carried-forward disposition class that a target may take only when it can be proven dispositioned under some already-sealed report whose baseline is an ancestor of this issue's — so nothing is laundered, but nothing is re-judged either. Establish first whether that ancestry is cheaply provable from existing records. If it is not, the alternative is an explicit supersede-and-refile route: retire the long-open issue with its evidence intact and open a successor whose baseline is current, which is what Arch recommended to the Owner here.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. A long-open issue can be closed without dispositioning targets belonging to other issues, demonstrated by a test that opens an issue, closes two others that change unrelated files, and then closes the first with a disposition count proportional to its own changes. The integrity property is preserved, demonstrated by a test showing a target changed since the baseline and dispositioned nowhere still blocks closure.

### Expected Effect
Metric: disposition targets required to close an issue, divided by targets that issue actually changed. Direction: lower, toward one. Qualitative invariant: no issue's documentation report ever asserts accuracy for another issue's changes, and no change reaches closure undispositioned anywhere.

---

## 🔴 PROPOSED: An ESX upgrade lands in every open project issue's candidate diff, and can make an issue impossible to close honestly

**Date Identified**: 2026-09-28  14:30
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-UPGRADE-DIFF-001
**Category**: upgrade_pollutes_issue_diffs
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-upgrade-pollutes-issue-diffs/assessment.md
**Anchors**: tools/esx/project.py::selected; tools/esx/project.py::inventory_paths; tools/esx/doc_inventory.py::changes; tools/esx/doc_contract.py::draft
**Implementation-Reference**: ESX-Team 6a4db29 (1.3.0), deployed; tools/esx/doc_contract.py `upgrade_supplied` disposition

### Implementation Status
Implemented upstream in ESX 1.3.0 via an `upgrade_supplied` disposition prefilled by `draft()` when both byte endpoints of a framework file match states a recorded applied upgrade produced; `validate_report` re-derives attribution, so a local framework patch still needs explicit judgment. Remaining against acceptance: the affected open issues closing without dispositioning `tools/esx` symbols they did not change.

### Issue
`FRAMEWORK_PATHS` includes `tools/esx` and participates in the non-scientific inventory that a candidate diff is computed over, so upgrading ESX puts every changed framework symbol into the candidate diff of every open project issue whose baseline predates the upgrade. Measured immediately after a 1.1.1 to 1.2.2 upgrade with six issues open: each gained 18 to 20 framework-owned disposition targets. For one issue that is **100% of its diff** — all 18 targets are framework symbols, because its own deliverables sit outside configured scanned roots. Closing it would require a documentation report under a report-splitting issue asserting documentation accuracy for `tools/esx/team_budget.py::observe`, which is not a statement that issue is in any position to make.

### Evidence
Disposition counts per open issue, total versus framework-owned: 1DMIX-055 18/18, 1DMIX-054 36/18, 1DMIX-059 56/19, 1DMIX-058 71/19, 1DMIX-057 75/19, 1DMIX-052 102/20. `FRAMEWORK_PATHS` is `['tools/esx', '.claude', 'devel-loop', 'docs', 'esx', 'CLAUDE.md', '.gitignore']`. The 1.2.x upgrade changed `team_budget.py`, `brief.py`, `agent_runtime.py`, `team_driver.py`, `ralph_stop.py` and `devel-loop/team_operations.md`. Before the upgrade 1DMIX-055's diff would have been a single target, `docs/code_map.md`.

### Potential Impact
An upgrade is meant to be routine, and this makes it a tax on every open issue proportional to how many are open. It creates direct pressure to either misattribute framework work to a scientific issue or avoid upgrading while issues are open — and avoiding upgrades is how a receiving project ends up patching framework code locally, which is the divergence upgrades exist to prevent. In the observed case it made one issue impossible to close honestly at all.

### Proposed Fix
The distinguishing information already exists: `esx_upgrade.py` records each transaction in `ESX-team-local/` with per-file `before_sha256`, `result_sha256` and `master_sha256`. A target whose current bytes match the `master_sha256` of a recorded upgrade is provably framework-supplied rather than project-authored, so disposition it automatically as upgrade-supplied, citing the deployment record. That preserves scope for a genuine local framework patch, whose bytes would match neither side, rather than excluding framework paths outright and letting an unreviewed local edit through. Establish first whether three-way-merge results are reliably attributable, since their bytes match neither master nor baseline.

### Acceptance Criteria
`python3 tools/esx/self_improvement.py check` passes with this record closed. A test that opens an issue, applies an upgrade changing framework files, and then closes the issue with a disposition count equal to its own changed targets. A second test showing a deliberate local edit to a framework file still requires an explicit disposition, so the integrity property is preserved. The observed six issues close without any of them dispositioning a `tools/esx` symbol they did not change.

### Expected Effect
Metric: framework-owned disposition targets required to close a project issue that changed no framework file. Direction: lower, to zero. Qualitative invariant: applying an upgrade never increases the work required to close an unrelated open issue, and never decreases the review a genuine local framework patch receives.

## 🔴 PROPOSED: Closing an issue's second iteration requires four undocumented steps, each discovered only by hitting its rejection

**Date Identified**: 2026-09-28  16:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-REITERATION-CLOSEOUT-001
**Category**: reiteration_closeout_route_undiscoverable
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-reiteration-closeout/assessment.md
**Anchors**: tools/esx/workflow_records.py::prepare_done; tools/esx/workflow_policy.py::validate_reviews; tools/esx/workflow_policy.py::resolved_dispatch; tools/esx/workflow_policy.py::validate_scope_decisions
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
An issue that closed partial leaves failed turns in the dispatch log. Its next iteration must then satisfy five separate requirements that nothing announces in advance: `prepare-done --prior <previous closeout>` to retain pre-iteration attempts; an explicit `agent_continuity.replacements` disposition per failed identity, carrying `role`, `old_id`, `new_id`, `reason` and `evidence_refs`; a `verification` block naming `structural`, `scientific` and `receipt` separately; and a `scope_decisions` classification drawn from a set that has no member for "the review found this and I filed it". Each requirement announced itself only as a rejection, after the fact. The cost lands exactly where it is least affordable: a second iteration exists *because* the first went badly, so the closer is guaranteed to be carrying failed turns and guaranteed to hit the whole sequence.

### Evidence
Measured on 1DMIX-058 iteration 2, whose substantive work was already complete and whose reviewer verdict was `APPROVE`. Five sequential rejections, roughly ten minutes and five tool round-trips, entirely on bookkeeping: `scope_decisions[0] needs a valid classification`; `bc2a550d…: current issue review completion is missing from subagents.richard`; `e9e7cebf…: attempt predates this iteration; retain it through --prior`; `bob: failed or incomplete turn remains unresolved`; `verification reference is required`. The two iteration-1 failures being accounted for were a stale orientation receipt on the implementer's third correction round and a reviewer approval lacking a successful executed check.

### Potential Impact
The integrity properties behind each requirement are correct and should not be relaxed — a failed turn must not vanish, a replacement reviewer must be dispositioned, a completed scientific change must cite its evidence. The problem is that the fastest-looking way past the second rejection is to mark the failed reviewer `waived`, which would erase the record of a review that did not happen. That path is closed only by an implementation detail — `waived` entries are filtered out of `referenced`, so the same error simply recurs — and not by any message explaining why it is the wrong move. A validation regime whose correct route is undiscoverable and whose incorrect route is the obvious one is inviting the failure it exists to prevent.

Separately, the classification set loses real provenance. To record that a reviewer discovered a genuine coverage gap which was then filed as a new issue, the closer must file it and then classify it `separate_existing` — which reads, in the closed record, as though the issue predated the closeout and was merely referenced. Review-discovered work becomes indistinguishable from pre-existing work.

### Proposed Fix
`prepare-done` already reads the dispatch log and already knows the issue id, so it can compute what it currently rejects on. Have it locate the issue's prior closeout in `loop_state/closed/` and use it, rather than failing and asking for `--prior`; and have it detect unresolved failed turns for the current issue and emit them into the draft as a `replacements` skeleton with `reason` and `evidence_refs` left empty. Empty-reason entries still fail validation, so no integrity property is weakened — the judgment stays with the closer and only the archaeology is automated. Add `separate_new` to the valid classification set with the same `issue_id` requirement as `separate_existing`, since it carries strictly more information. Name the three required `verification` keys in that rejection message, which currently explains what not to cite without listing what is needed. Acceptance: a partial-then-completed issue pair closes without a rejection that names a requirement the closer could not have known, and the closed record distinguishes an issue opened by a closeout from one merely referenced by it.

### Expected Effect
A partial-then-completed issue pair closes on the first assembly attempt, with the draft carrying the prior-closeout reference and a pre-populated `replacements` skeleton whose `reason` and `evidence_refs` fields are the only things the closer must supply. Judgment stays with the closer; the archaeology does not. The obvious route and the correct route become the same route, removing the standing invitation to `waive` a failed review rather than disposition it. Closed records gain the ability to say that an issue was opened by a closeout rather than merely referenced by it, so review-discovered work is traceable to the review that found it.

### Acceptance Criteria
A second iteration of an issue whose first closed partial is assembled into a completed closeout without any rejection naming a requirement the closer could not have known in advance — specifically, without the `--prior`, `missing from subagents`, `remains unresolved` or `verification reference is required` rejections firing. `prepare-done` emits a `replacements` entry per unresolved failed identity with empty `reason` and `evidence_refs`, and validation still refuses the draft until both are filled, demonstrated by a test that leaves them empty and expects refusal. `separate_new` is accepted with an `issue_id` and rejected without one, demonstrated by tests in both directions. The three required `verification` keys are named in that rejection's own message. No existing integrity check is relaxed: the current test suite passes unchanged alongside the new tests.

---

## 🔴 PROPOSED: An interrupted verification suite is recorded as `FAILED`, and the closeout keeps citing the receipt the re-run replaced

**Date Identified**: 2026-09-28  20:25
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-VERIFY-RERUN-001
**Category**: final_verification_rerun_lifecycle
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-final-verification-rerun/assessment.md
**Anchors**: tools/esx/final_verification.py::ready; tools/esx/final_verification.py::check_receipt; tools/esx/loop_gate.py:158; tools/esx/loop_lifecycle.py::prepare_done
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
The scientific suite is the most expensive step in the loop and its receipt is the artifact whose truthfulness matters most, but that receipt cannot currently distinguish "this candidate is wrong" from "this process was killed". Three defects compound. An interrupted run is recorded `status: FAILED` with the error text `verification failed or source changed`, which conflates a real test failure, a source change under the run, and a run that never finished. `--check-done` then reports only the resulting missing artifact — `[Errno 2] No such file or directory: …/final-verification/current.json` — naming neither the last attempt nor its status nor its log. And because `prepare_done` writes `verification.receipt` once at prepare time, a successful re-run leaves the closeout record still citing the superseded receipt, with no supported operation to re-point it at `current.json`.

### Evidence
Measured on 1DMIX-057 iteration 3, which produced three receipts for one candidate (`ce0546991f…`), one owner (`arch`) and one iteration timestamp: `9aab3c9e…` PASS at 17:29:06Z under `review_signature f43fdb82…`; `c776b4b8…` FAILED at 17:35:55Z under `fb6d1180…`; `9d4a346a…` PASS at 20:15:41Z under `fb6d1180…`. The first PASS was correctly recognized as void once the closeout record was edited and its signature moved to `fb6d1180…`, and a re-run was launched. That re-run is the one that did not survive. Its log `run-9958b8af12e54753899315786d2b1b75.log` contains **zero** lines matching `FAILED|ERROR`, carries no pytest summary line, and stops mid-line at `test_global_ocean_cs32x15_pressure_coordinate_gap[visc_az-90.0-1000.0]` at `[ 70%]` of 123 collected tests. The identical suite completed `120 passed, 3 skipped` in 486.59s immediately before it (`run-c1742ac0…`) and in 655.58s after it. Establishing from the receipts that nothing scientific had failed, and that the remedy was simply to re-run, took about 14 minutes of reading three receipts, two logs and `final_verification.py::review_signature` — before the 11-minute run that was the actual fix. Re-pointing the record afterwards required hand-editing `issue-done.json`, the same active record `--check-done` then validates.

### Potential Impact
A receipt that says `FAILED` when its log proves no test failed invites exactly the wrong conclusion: that a validated scientific candidate regressed. The available responses to a suspected regression — re-open the issue, re-dispatch a reviewer, re-litigate the physics — are all far more expensive than the actual remedy, and all are reachable from the receipt alone without ever opening the log. The missing-file error compounds this by giving the gate's reader no cheap path to the truth, so the safe default becomes paying full price for another suite run on every ambiguity. The hand-edit requirement is separately corrosive: refreshing a receipt is a legitimate, frequent operation that currently has no tool, so it is performed by editing a validated record by hand.

### Proposed Fix
Separate incompleteness from failure at the point the receipt is written: record `INTERRUPTED` when the child exited on a signal or its log carries no pytest summary line, reserving `FAILED` for a genuine non-zero test outcome, and stop merging "source changed" into the same string. Have `--check-done` read the iteration's latest attempt and report which of the three cases holds, naming the log path, rather than reporting the absence of `current.json`. Add a supported operation that binds a prepared closeout to the current receipt, so a post-re-run refresh is a tool call whose result the gate validates rather than a hand edit the gate merely tolerates.

### Acceptance Criteria
A suite run killed by a signal produces a receipt whose status is `INTERRUPTED`, not `FAILED`, demonstrated by a test that terminates the child and asserts the recorded status and that the log holds no failure lines. A genuine test failure still produces `FAILED`, demonstrated in the same test file. `--check-done`, run with an interrupted attempt as the latest, emits a message naming the attempt's status and log path and stating that no test failed, instead of an `Errno 2` on `current.json`. A documented command re-points a prepared closeout at `current.json` and refuses when the current receipt's `review_signature` does not match the record, demonstrated in both directions. No existing integrity check is relaxed: a void receipt must still fail `check_receipt`, and the existing suite passes unchanged.

### Expected Effect
The distinction that costs the most to get wrong — candidate is wrong versus process was killed — becomes readable from the receipt without opening a log, and readable from `--check-done` without reading receipts. The measured 14 minutes of receipt archaeology before a re-run drops to one gate message. Refreshing a receipt after a re-run stops requiring a hand edit of a validated record.

---

## 🔴 PROPOSED: The gate requires a resolution published to `closed_issues.md` before it will validate that resolution

**Date Identified**: 2026-09-28  20:25
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-LEDGER-AHEAD-001
**Category**: ledger_precedes_validation
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-ledger-precedes-validation/assessment.md
**Anchors**: tools/esx/loop_gate.py:158; tools/esx/loop_lifecycle.py::prepare_done; closed_issues.md; open_issues.md
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
`loop_gate.py:158` requires `done['id'] in closed and done['id'] not in opened` for a completed outcome, so an issue's entry must already have been moved into `closed_issues.md` before `--check-done` will accept its closeout. The permanent record is written first and validated second. When validation then fails for any reason, the ledger is left asserting a resolution that nothing has qualified, and the width of that window equals however long validation takes to succeed. Nothing is done out of order to produce this: `prepare_done` sets `open_issues_md_updated=True` unconditionally, and an Arch who moved the entry only after a passing gate could never pass the gate at all.

### Evidence
Measured on 1DMIX-057. Its `closed_issues.md` entry carries `**Date Resolved**: 2026-09-28T17:10:00Z`; the accepted closeout records `closed_at: 2026-09-28T20:20:28.881815+00:00`. For **3 hours 10 minutes** the permanent record stated Resolved while the gate had the iteration open, no passing receipt was bound to the record, and the receipt the record did cite (`9aab3c9e…`) was void — its `review_signature f43fdb82…` no longer matching the record's own `fb6d1180…`. The consequence was realized rather than hypothetical: asked for project status at approximately 19:40Z, inside the window, the readable sources were `open_issues.md`, `closed_issues.md` and the notification ledger, all three consistent with a closed 1DMIX-057, and the status reported to the owner treated it as closed. The gate's contrary view was reachable only by running `loop_gate.py --next`, which is not where issue state is read.

### Potential Impact
The ledger is this project's durable, human-facing record of what has been established, and it is explicitly the artifact that outlives the loop state. A window in which it claims an unqualified resolution is a window in which every reader — the owner, a future session, any report generated from it — can attribute validated status to work whose acceptance suite has not passed. The failure is silent and its direction is always optimistic. It is also self-concealing: the more validation struggles, the wider the window during which the record looks finished.

### Proposed Fix
Make the permanent record a consequence of validation rather than a precondition for it. Preferred: have `--check-done` perform the move itself as its final step on acceptance, since it already parses both files and already knows the outcome. Alternative, if the move must stay with Arch: require the entry to carry an explicit pending-validation marker for as long as `issue-done.json` exists without an accepted `closed_at`, with the gate clearing the marker on acceptance and refusing a `completed` closeout whose entry lacks it. Either way the invariant to establish is that no entry in `closed_issues.md` ever states a resolution that the gate has not accepted.

### Acceptance Criteria
A closeout whose validation fails leaves no unqualified resolution in `closed_issues.md`, demonstrated by a test that submits a `completed` closeout with a void verification receipt and asserts both that the gate refuses it and that the resolution is not readable as accepted in the ledger afterwards. A successful `--check-done` leaves the entry in `closed_issues.md` and absent from `open_issues.md`, exactly as today, demonstrated by the existing passing path. The existing integrity property — that an accepted `completed` closeout never coexists with an `open_issues.md` entry — is preserved, not relaxed, and the current suite passes unchanged.

### Expected Effect
The measured 3h10m window in which the permanent ledger asserted an unvalidated resolution goes to zero by construction, since the entry's resolved state and the gate's acceptance become the same event. A reader of `closed_issues.md`, including the owner asking for status, can treat the presence of a resolution as evidence that its acceptance suite passed.

---

## 🔴 PROPOSED: The coordinator's cost is structurally unmeasurable, so retrospectives under-measure the workflow they evaluate

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-COORDINATOR-COST-001
**Category**: coordinator_cost_unmeasured
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-coordinator-cost-unmeasured/assessment.md
**Anchors**: tools/esx/team_accounting.py:227; tools/esx/team_accounting.py::summary
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
`team_accounting.py:227` computes `'coordinator_coverage': 'recorded' if 'arch' in roles else 'missing'`, so the framework anticipates Arch costs and has a field for them. It has never received any, and cannot: Arch is the interactive main session rather than a dispatched agent, so no `dispatch_log.jsonl` entry meters it. Every `cost_usd` and `span_minutes` figure the self-improvement program reasons about therefore describes dispatched agents only, while presenting as the cost of the iteration.

### Evidence
`coordinator_coverage` reads `missing` in all **20** accepted retrospectives across the project's history (13 distinct issues); `by_role` composition varies across iterations (bob-only, bob+richard, or in two cases neither), so the coordinator gap is not an artifact of which issues were sampled. Independently re-derived by the reviewer over the full `retrospective_history.jsonl` population rather than the eight-issue subset this entry was first written from. The omitted share is not marginal: in the five-issue loop of 2026-09-28 Arch performed all packet assembly, all ledger writing, every independent re-verification of an implementer's headline claim, and all five `final_verification.py` runs, whose scientific suite alone consumed 496 to 656 seconds five times over — roughly 50 minutes of measured wall clock, none of it attributed. 1DMIX-063's retrospective reports that iteration as "40 minutes, bob $2.30 and richard $2.02".

### Potential Impact
The distortion lands precisely on the judgments retrospectives exist to make. Deciding whether a reviewer round earned its price compares a metered reviewer against unmetered coordination, which systematically favours the conclusion that review is expensive relative to the work around it. Any future decision to reduce review in favour of coordinator effort would be made on figures that cannot see the coordinator.

### Proposed Fix
Choose deliberately, as an Owner decision rather than an Arch one. Either make it measurable — have the main session write an accounting record per iteration phase, a shape `team_accounting.summary` already supports, so `coordinator_coverage` can read `recorded`; or accept it as a permanent limit and label every consumed figure as dispatched-agent-only at the point of consumption, so no reader infers a total. The present state is the worse of the two: a field that names the gap, reports it eight times out of eight, and is never acted on.

### Acceptance Criteria
Either `coordinator_coverage` reads `recorded` for a completed iteration, with an accounting record attributable to the main session and a test demonstrating that an iteration without one still reports `missing`; or `esx/project_profile.md` and the retrospective template both state that `cost_usd` and `span_minutes` exclude the coordinator, and `--draft-retro` emits that caveat inline so it appears in every retrospective rather than only in documentation. In either case no existing figure is silently redefined.

### Expected Effect
A reader of any retrospective can tell whether its cost figures are total or partial without reading the accounting implementation. If the measuring option is taken, cost-of-review judgments become comparisons between two measured quantities rather than between a measured and an invisible one.

---

## 🔴 PROPOSED: Closeout requirements are discovered one rejection at a time, including on first iterations

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-CLOSEOUT-DOCTOR-001
**Category**: closeout_requirements_serial_discovery
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-closeout-serial-discovery/assessment.md
**Anchors**: tools/esx/loop_gate.py::check_done; tools/esx/final_verification.py::ready; tools/esx/workflow_handoff.py::readiness
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
Assembling a closeout means satisfying a requirement set that is never stated in advance: each tool reports the first unmet condition, the closer fixes it, reruns, and learns the next. `TEAM-REITERATION-CLOSEOUT-001` covers this but is scoped explicitly to an issue's second iteration after a partial close; the measurements here show the pattern is not confined to that case.

### Evidence
1DMIX-052, iteration 2 — eight sequential rejections: `map_delta needs updated or MAP-OK status`; `candidate reference is required`; `review packet still has pending preparation fields`; `bob: failed or incomplete turn remains unresolved`; `stale arch orientation`; `documentation_review.report must be the exact sealed report reference`; `record stable bob runtime identities`; `final verification receipt is stale`. 1DMIX-062, **iteration 1** — four rejections, so not a second-iteration effect. 1DMIX-063, iteration 1 — prerequisites passed on the first attempt, because by then the order had been learned. That contrast is the evidence that the cost is discovery rather than complexity: same closer, same tooling, same class of issue, and the difference between eight rejections and zero is prior exposure. Roughly 25 minutes on 1DMIX-052 and 10 on 1DMIX-062, entirely on bookkeeping, on issues whose reviewers had already approved.

### Potential Impact
Two of the eight are traps rather than instructions. `record stable bob runtime identities` does not say the wanted value is the list of `dispatch_id`s already present in `subagents`. And `final verification receipt is stale` fires *after* a passing suite, because the fields feeding `review_signature` were still being discovered when the receipt was taken — so the natural order of work guarantees the failure, and a closer meeting it for the first time will reasonably conclude the suite must be rerun. On this project that is an 11-minute penalty for a bookkeeping edit. Every individual check is correct and none should be relaxed; the defect is that a knowable set is not offered.

### Proposed Fix
Add a dry run that reports all unmet closeout requirements at once instead of the first. The information already exists: `final_verification.ready` and `loop_gate.check_done` compute these conditions, and `workflow_records.readiness` already demonstrates returning a `findings` list rather than raising on the first problem. Extend that shape to `--check-done` behind a flag, or add `loop_gate.py --closeout-doctor`. State the `review_signature` ordering constraint explicitly in the output — finalize every signed field before taking the receipt — so it is read rather than learned by rejection.

### Acceptance Criteria
A closeout draft missing several requirements yields a single report listing all of them, demonstrated by a test that omits at least three and asserts all three appear in one invocation. The `review_signature` dependency is named in that output, with the fields it covers enumerated. The existing strict behaviour of `--check-done` is unchanged for callers that do not request the dry run, and the current suite passes unchanged.

### Expected Effect
A first-time closer sees the whole requirement set before the first fix instead of after the seventh. The measured 25 minutes of serial discovery collapses to one report, and the specific trap where a passing receipt is invalidated by a subsequently-discovered field stops being reachable by following the tools in their natural order.

---

## 🔴 PROPOSED: The reviewer is never told which sealed documentation report to cite, and cites a superseded one

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-SEAL-CITATION-001
**Category**: reviewer_uninformed_of_current_seal
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-reviewer-seal-citation/assessment.md
**Anchors**: tools/esx/brief.py::build; tools/esx/final_verification.py::ready; tools/esx/doc_contract.py::seal
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
A reviewer's footer must carry `documentation_review.report` equal to the current sealed documentation plan. Every implementer correction forces a re-seal, because sealing binds the plan to the exact current candidate bytes, so by a confirming round the seal the reviewer first read is one or two generations stale. Nothing in the brief makes the current hash salient against the one already in his context, and the mismatch surfaces only at final verification — after his round is spent.

### Evidence
Three occurrences, three wasted rounds, one cause. 1DMIX-052 round 2 cited `093e1c22…`, the round-1 seal, with the reviewer's own note reading "Same sealed plan cited in round 1"; current was `9029b239…`. 1DMIX-062 round 2 cited `4cac34ee…`, the round-0 seal, after two re-seals; current was `e56f80ca…`. 1DMIX-057 records the same failure before this session: "round 1 solely because its footer cited a navigate receipt instead of the sealed documentation report, which round 2 corrected with no change to the verdict." Each was resolved by a footer-only correction naming the current hash explicitly — 142 seconds in the 1DMIX-062 case — with the `APPROVE` verdict unchanged every time.

### Potential Impact
The wasted round is the smaller cost. The larger one is that a footer-only correction round is indistinguishable in the record from a substantive one, so an iteration's round count overstates the review effort actually spent on correctness. And a reviewer asked three times to re-cite without being told why may reasonably start treating the citation as bookkeeping rather than as the attestation it is — which is the property the field exists to capture.

### Proposed Fix
Have `brief.py` inject the current sealed documentation reference into every reviewer brief verbatim as a required footer input, with an instruction to read that exact file rather than assume it matches one already seen. The current sealed documentation reference is **already** dumped verbatim into every reviewer brief (`brief.py::build`, `json.dumps(packet)`, present since commit 1482fe5), but buried undifferentiated inside the full packet JSON with nothing marking it as the field to re-check against context. The fix is to give it a labeled, standalone line, not to add information that is currently absent. Additionally, validate the citation at packet-build or report-capture time rather than only at final verification, so a stale citation is caught before a round is spent. Both halves are additive and neither weakens the attestation.

### Acceptance Criteria
A generated reviewer brief contains the current sealed report path and sha256, demonstrated by a test comparing the brief text against the packet's documentation reference. A footer citing a superseded seal is rejected at report capture with a message naming both the cited and the expected hash, demonstrated in both directions. No existing integrity check is relaxed: a footer citing a non-existent or altered report still fails.

### Expected Effect
The three-for-three failure rate on confirming rounds goes to zero, and a reviewer who cites the wrong seal learns so from his own turn rather than from a later refusal. Round counts in retrospectives start reflecting correctness effort rather than citation bookkeeping.

---

## 🔴 PROPOSED: The retrospective schema has no success channel, so validated approaches are recorded as problems

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-RETRO-SUCCESS-001
**Category**: retrospective_lacks_success_channel
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-retrospective-success-channel/assessment.md
**Anchors**: tools/esx/team_retrospective.py::accept; tools/esx/team_retrospective.py:97; devel-loop/self-improvement/README.md
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
A schema-version-2 retrospective carries `problems`, `solutions`, `carry_forward` and `no_problem_reason`, and nothing else. There is no field for a confirmation — an approach tried deliberately, which worked, and should be repeated. `validate` requires every `problems` entry to carry `minutes_lost` and to receive a `solutions` disposition naming an open process owner. Recording a success therefore means writing it into the failure array with `minutes_lost: 0` and nominating an owner for it as though it were a defect.

### Evidence
Six instances across two sessions, each saying in prose what the schema cannot say structurally. 1DMIX-054's and 1DMIX-059's `bounded_first_step_paid_off` entries both carry the same complaint. 1DMIX-058's `distinct_reviewer_questions_found_new_ground` opens "Recorded because the schema has no success channel". 1DMIX-061's `restated_rules_prevented_rework` opens "Recorded because the schema has no success channel, and because this iteration is the controlled comparison for the immediately preceding one". 1DMIX-063's `handbuilt_witness_guards_callee_not_pipeline` opens "Recorded because it is the third consecutive demonstration of one structural fact and the schema has no channel for a finding that is neither a process failure nor a success". Two further entries in the same window carry `minutes_lost: 0` for the same reason.

### Potential Impact
The project's own guidance is to record from success as well as failure, on the stated grounds that recording only corrections avoids past mistakes while drifting away from approaches already validated. The schema contradicts that guidance. Two concrete consequences follow: anyone counting defects from `problems` arrays over-counts, because some entries are successes distinguishable only by `minutes_lost: 0` and a prose disclaimer; and anyone looking for what to keep doing has nowhere to look. The 1DMIX-061 entry is the sharpest case — it exists specifically as the controlled comparison against an iteration where the same rule was unstated and cost a 59-tool-call turn, which is the most useful process evidence this program can produce, and it is filed as a problem.

### Proposed Fix
Add a `confirmations` array in schema version 3: entries carrying `category`, `summary` and `evidence`, with no `minutes_lost` and no `solutions` requirement, since a confirmation needs no owner. Keep `problems` for defects. Have `--draft-retro` emit both arrays, and have `validate` accept a retrospective whose `problems` is empty when `confirmations` is not, without demanding a 60-character `no_problem_reason` — the confirmations are themselves the measured evidence that reason exists to supply. Leave the recurring-category machinery applying to `problems` only. Confirmations must still meet the evidentiary floor `accept()` already applies to `problems` (an `evidence` field of substantive length), and an empty `problems` array is exempted only from *duplicating* the explanation, never from supplying one: it requires either a `no_problem_reason` of 60 characters or at least one confirmation whose own evidence meets that bar. Without that floor the new path would be a strictly lower bar than today's.

### Acceptance Criteria
A schema-version-3 retrospective with a populated `confirmations` array and an empty `problems` array validates and is accepted, demonstrated by a test. A confirmation entry is rejected if it lacks substantive `evidence`, and is not required to carry `minutes_lost` or a disposition. A retrospective with an empty `problems` array, an empty `no_problem_reason` and only a content-free confirmation is refused, demonstrated by a test. Existing version-2 records remain readable and their recurring-category checks behave unchanged. `--draft-retro` emits both arrays.

### Expected Effect
Confirmations stop being filed as zero-cost defects, so `problems` counts mean what they say. The prose disclaimer "recorded because the schema has no success channel", now written five times, stops being necessary. A reader can answer "what has this project validated and should keep doing" from a field instead of by inference.

---

## 🔴 PROPOSED: Arch's orientation is invalidated by exactly the edits Arch commissioned, and the remedy is retyping

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-ARCH-REORIENT-001
**Category**: arch_orientation_invalidated_by_commissioned_edits
**Severity**: Low
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-arch-reorientation-ceremony/assessment.md
**Anchors**: tools/esx/doc_contract.py::validate_orientation; tools/esx/doc_contract.py::navigate; tools/esx/workflow_handoff.py::assemble
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
Arch records an orientation at `--prepare`. The implementer then edits those documents, because that is the assignment, and the packet build refuses with `ARCH_ORIENTATION_INVALID`. The remedy is to rerun `doc_contract.py navigate` with the same map, the same targets and the same documents, changing only the free-text `--use`. This is distinct from `TEAM-ORIENTATION-RESEAL-001`, which covers an implementer invalidating his *own* receipt; here the coordinator's orientation is invalidated by an agent doing what the coordinator asked.

### Evidence
Five re-navigations across four issues on 2026-09-28, every one triggered by a commissioned edit. 1DMIX-052 reported `changes=[{"target": "MITgcm_to_Python_port_verification/README.md#current-validation-status", "changed": ["documentation"], "before": "f252270f…", "after": "ddd389e5…"}]` — the exact edit Arch had directed, to the line Arch had oriented on. 1DMIX-061 once, 1DMIX-062 twice (after the repair and again after the sweep correction), 1DMIX-063 once. In all five the `navigate` arguments were unchanged apart from `--use`; no case surfaced a change Arch had not already directed or already read, and no re-navigation altered any later judgment.

### Potential Impact
The integrity property is sound — a coordinator must not carry a stale picture into a review packet — but the check cannot distinguish "the dependency slice moved under you" from "the agent did what you asked in the file you asked about", and only the first is a staleness risk. Because the remedy is a re-issued command with identical arguments, the check has the property that makes controls decay: it is satisfied by ceremony rather than attention, and an Arch who has performed it five times will perform the sixth without reading the diff, which is exactly the failure the check exists to prevent.

### Proposed Fix
**A hash-citation acknowledgement was considered and rejected on review.** `validate_orientation` already embeds each changed target's `after` hash in its own refusal text, so an acknowledgement citing those hashes back can be satisfied by copying the refusal output, with zero exposure to file content — strictly less assurance than re-running `navigate`, which at least reprints the current 65-line excerpt via `_navigate`. That would have been a regression on the property it claimed to preserve.

Instead remove the retyping without removing the exposure: add a `navigate --reuse-args <original-orientation-ref>` shortcut that reloads the recorded map, targets and documents so they need not be re-supplied by hand, still executes the excerpt-printing path, and still requires a freshly written `--use`. That deletes the ceremony (re-typing identical arguments) while keeping the one element that actually forces attention (the freshly printed excerpt). Additionally refuse the shortcut when a changed target was **not** in the original orientation's own target or document list, since that is the case the check exists for — the slice moving somewhere Arch never looked.

### Acceptance Criteria
`navigate --reuse-args` reloads the recorded map, targets and documents from a named prior orientation, prints the current excerpt for every one of them, and refuses without a fresh `--use`, demonstrated by a test. It is refused when any changed target lies outside the original orientation's declared targets and documents. No path exists to clear a stale orientation using only values echoed by the refusal message itself. Re-issuing `navigate` in full remains available and unchanged.

### Expected Effect
The five ceremonial re-navigations measured in one session stop requiring identical arguments to be re-supplied by hand, while still putting the current excerpt in front of the coordinator every time. The check keeps its force at the boundary it was built for — an unexpected target moving — and no cheaper path exists that a coordinator could satisfy without reading anything.

---

## 🔴 PROPOSED: A provider known dead for the whole session still requires one disposition per queued event

**Date Identified**: 2026-09-28  19:40
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-DEAD-TRANSPORT-001
**Category**: per_event_disposition_for_dead_transport
**Severity**: Low
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-dead-transport-dispositions/assessment.md
**Anchors**: tools/esx/notifications.py (record); devel-loop/communication.md; .claude/skills/esx-announce/SKILL.md
**Implementation-Reference**: ESX-Team c630fc3 (1.5.0), deployed 2026-09-29

### Issue
The communication contract is correct that a pending event cannot satisfy the delivery duty and that each event needs a real receipt or a concrete failure. But when the provider is established dead for an entire session, that contract costs one tool call and one hand-written justification per event, each restating the same discovery, and the gate blocks issue selection until every one is individually adjudicated.

### Evidence
Slack was unauthenticated throughout 2026-09-28: only `authenticate` and `complete_authentication` were exposed, and `slack_send_message` — which delivered events on 2026-09-20 — was absent. `authenticate` was called once, returned an OAuth URL requiring an owner browser step, and that step was never completed, so no send tool appeared and retry was never possible. **76 events** were dispositioned `unavailable`, each needing its own `notifications.py record` invocation (the CLI takes exactly one event positional and has no batch mode) carrying a 300-to-500-character `--detail` restating that same finding. Some invocations were wrapped in shell loops, so the number of separate tool calls is not logged and is not claimed here. Breakdown: 19 `issue_start`, 19 `issue_closeout`, 19 `progress`, 9 `issue_opened`, 4 `loop_start`, 4 `loop_end`, 2 `lesson`. Final ledger state: 0 pending, 0 undispositioned. `--next` refused to advance to issue selection while any event was pending, so this recurred at every closeout, five times over.

### Potential Impact
No correctness problem — the ledger is accurate and the owner-facing report could state exactly what was undelivered and why. The costs are that a justification retyped fifteen times becomes boilerplate, and boilerplate is where a genuinely different failure gets mislabelled as the familiar one; and that the ledger now holds fifteen near-copies of one discovery, so a future auditor cannot tell whether the transport was probed fifteen times or once. The distinction the ledger cannot express is the one that matters: a per-event failure, where this send was attempted and failed, versus a session-scoped outage where no send was possible at all.

### Proposed Fix
Allow one session-scoped provider-outage disposition covering every queued event and events queued later in the same session, recording the discovery once with its probe evidence and marking each event as covered by that outage rather than individually adjudicated. Require an explicit re-probe to clear it, so recovery is never assumed. Keep per-event dispositions for `failed`, since an executed send that failed is genuinely per-event information. Have `--next` treat outage-covered events as dispositioned so the gate stops blocking issue selection on a transport known to be down.

### Acceptance Criteria
A single outage record dispositions all queued events for its provider and is applied automatically to events queued afterwards in the same session, demonstrated by a test. `notifications.py status` distinguishes outage-covered events from individually `failed` ones. Clearing the outage requires an explicit re-probe, and the re-probe is **forced rather than discretionary**: `--next` requires one probe attempt per loop iteration (or per N covered events, whichever comes sooner) while an outage is active, and the outage record carries an iteration-count bound after which it must be renewed with fresh probe evidence rather than silently continuing to apply. An event queued after clearing is again individually adjudicated. `--next` does not block on outage-covered events, and `pending` still blocks as it does today.

### Expected Effect
One recorded discovery with its probe evidence replaces fifteen near-duplicate justifications, and the ledger states plainly whether a transport was down or a send was attempted and failed. The loop stops requiring five separate adjudication rounds to advance past a provider that was dead before the first one.

---

## 🔴 PROPOSED: The ESX template imports `adx_workflow`, a module that exists only in the ADX project

**Date Identified**: 2026-09-29  12:00
**Status**: Proposed
**UUID**: TEAM-TEMPLATE-ADX-IMPORT-001
**Category**: template_foreign_project_import
**Severity**: Low
**Assessment**: devel-loop/self-improvement/assessments/2026-09-29-template-adx-import-leak/assessment.md
**Anchors**: tools/esx/workflow_handoff.py:142

### Issue
`tools/esx/workflow_handoff.py` tries `import adx_workflow as lifecycle` and falls back to `workflow_policy` on `ImportError`. `adx_workflow` doesn't exist in this project. It is left over from the ADX project the ESX framework was extracted from, and it ships in the upstream template (`ESX-Team/template/tools/esx/workflow_handoff.py:142`, present since ESX-Team's first commit `f8f6df1`).

### Evidence
A whole-repo import scan run on 2026-09-29 while building the `ecco` env flagged `adx_workflow` as unresolvable. The only file with that name on the workstation is `~/Projects/ADX/tools/adx_workflow.py`. `git log -S adx_workflow` in ESX-Team finds only `f8f6df1`, and the deployed copy is byte-identical to the 1.5.0 template (`c630fc3`). The project owner confirmed there is no `adx_workflow` in this project. `loop_gate.py --doctor` passes because the fallback always runs.

### Potential Impact
No current runtime failure. It is a misleading dependency: in this session it was first misreported as an optional ESX import. It is also a silent-substitution hazard: if an importable `adx_workflow` is ever on `sys.path`, the handoff gate uses ADX's `resolved_dispatch` rules instead of this project's, and nothing records the switch.

### Proposed Fix
Upstream in ESX-Team, replace the `try`/`except` with `import workflow_policy as lifecycle`, grep the template for any other ADX-specific names, and redeploy. Don't make a project-local edit meanwhile, so `tools/esx` stays byte-identical to the template.

### Acceptance Criteria
`grep -rn adx_workflow tools/esx` returns nothing after redeploy. `python3 tools/esx/loop_gate.py --doctor` and `python3 tools/esx/self_improvement.py check` pass. The upstream template has no remaining references to modules that exist only in ADX.

### Expected Effect
The handoff gate always uses this project's own lifecycle module, and the import no longer needs explaining. Invariant: the template imports only modules it ships.

---

## 🔴 PROPOSED: `agent_runtime.py` crashes when the CLI streams a `permission_denied` event

**Date Identified**: 2026-09-29  21:45
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-RUNTIME-PERMDENIED-CRASH-001
**Category**: runtime_stream_parsing
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-29-runtime-permission-denied-crash/assessment.md
**Anchors**: tools/esx/agent_runtime.py:363
**Implementation-Reference**: ESX-Team 8c7ea7d (1.5.1), deployed 2026-09-29

### Issue
`_read_tool_events` assumes every stream event's `message` is a dict. Claude CLI 2.1.285 emits `{"type":"system","subtype":"permission_denied","message":"This command requires approval",...}` with a string `message`, so `event.get("message", {}).get(...)` raises `AttributeError` in the watchdog and the adapter dies without a footer or turn record.

### Evidence
1DMIX-064 Bob dispatch, session `c641620b-315d-44ad-9c0c-98d6aadf2b12`, turn `404e048cf06a4a028cab33b9858d07fc`: `stdout.jsonl` line 28 is the event above; the dispatcher traceback ends at `agent_runtime.py:363`. No working-tree edits were made before the crash.

### Potential Impact
Any permission denial in a headless role turns into a dispatcher crash and an unrecorded, unknown-completeness turn, rather than a denial the role can report.

### Proposed Fix
Upstream in ESX-Team: take `message = event.get("message")` and read `content` only when it is a dict; consider recording `permission_denied` events in the turn evidence so the coordinator sees them. Keep the deployed copy byte-identical until redeploy.

### Acceptance Criteria
A replayed stream containing a `permission_denied` event completes the turn with a footer/failed status and no traceback; the denial appears in turn evidence.

### Expected Effect
Permission problems surface as recorded role evidence instead of dispatcher crashes. Invariant: the stream parser tolerates any JSON event shape.

---

## 🔴 PROPOSED: Missing `external_inputs` on a fresh checkout are only discovered at review-packet time, after implementation

**Date Identified**: 2026-09-29  21:55
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-VERIFY-EXTERNAL-INPUTS-PREFLIGHT-001
**Category**: environment_preflight
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-29-runtime-permission-denied-crash/assessment.md
**Anchors**: tools/esx/verify.py; tools/esx/loop_gate.py; esx/project.json:external_inputs
**Implementation-Reference**: ESX-Team 8c7ea7d (1.5.1), deployed 2026-09-29

### Issue
`verify.py` fingerprints every `external_inputs` path before running any suite, so a checkout missing gitignored captures cannot produce even structural evidence. `loop_control.py run`, `--next`, `--prepare` and dispatch all succeed on such a checkout; the gap first surfaces when `workflow_records.py review-packet` demands structural evidence, after Bob's implementation is done.

### Evidence
1DMIX-064 on the new WSL checkout (2026-09-29): all 31 of 31 `external_inputs` absent; `verify.py --suite structural --owner arch` → `[Errno 2] No such file or directory: .../mitgcm_kpp_inputs_11k_1D.nc`; review packet refused with `STRUCTURAL_STALE_OR_FAILING`; issue parked as blocked after implementation.

### Potential Impact
Implementation and loop iterations are spent on work that cannot reach review on this machine; every scientific issue blocks the same way.

### Proposed Fix
Have `loop_control.py run` / `--next` (or `--doctor`) check `external_inputs` existence and report a single environment blocker before selecting work; optionally distinguish inputs required by the structural suite from those only needed by scientific suites.

### Acceptance Criteria
On a checkout with a missing `external_inputs` path, `loop_gate.py --next` prints an environment-blocker NEXT naming the missing paths before any issue preparation or dispatch.

### Expected Effect
Zero implementation dispatches on checkouts that cannot produce verification evidence.

---

## 🔴 PROPOSED: Stop hook consumes a loop iteration each time Arch ends a turn to await a background dispatch

**Date Identified**: 2026-09-29  21:55
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-LOOP-WAIT-BURNS-ITERATION-001
**Category**: loop_budget_accounting
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-29-runtime-permission-denied-crash/assessment.md
**Anchors**: tools/esx/ralph_stop.py; tools/esx/loop_control.py
**Implementation-Reference**: ESX-Team 8c7ea7d (1.5.1), deployed 2026-09-29

### Issue
When Arch dispatches a role in the background and ends its turn to wait, the Stop hook advances the loop iteration counter and re-injects the prompt, though no issue work completed. A 5-iteration budget lost 2 iterations (1→2→3) to waiting on one 1DMIX-064 dispatch, each also emitting a Slack progress post.

### Evidence
Session 377c3c70 (2026-09-29): iterations 2 and 3 began at 21:44:47 and 21:45:42 while the same Bob dispatch was in flight; notifications fea26d5f4178a2604bdb66a0 and 6d038b0c80cc8255f520d3aa.

### Potential Impact
Loop budgets are exhausted by waits rather than work; channel receives redundant progress posts.

### Proposed Fix
Do not advance the iteration while the active issue has an in-flight retained or native dispatch (or while `--next` returns the same "finish active iteration" instruction without new completion records); alternatively document that Arch must block in-turn on dispatch completion.

### Acceptance Criteria
A Stop during an in-flight dispatch of the active issue leaves `iteration` unchanged and queues no progress notification.

### Expected Effect
Iteration count equals issue iterations actually attempted.

---

## 🔴 PROPOSED: Stop hook misses a fulfilled completion promise in the final assistant message (transcript flush race)

**Date Identified**: 2026-09-29  22:00
**Status**: Implemented — awaiting publication/effectiveness evidence
**UUID**: TEAM-LOOP-PROMISE-FLUSH-RACE-001
**Category**: loop_termination
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-29-runtime-permission-denied-crash/assessment.md
**Anchors**: tools/esx/ralph_stop.py:current_text; tools/esx/ralph_stop.py:211
**Implementation-Reference**: ESX-Team 8c7ea7d (1.5.1), deployed 2026-09-29

### Issue
After `loop_gate.py --next` exited 3 and printed `ESX-LOOP-NO-ACTIONABLE-WORK`, Arch ended two consecutive turns with `<promise>ESX-LOOP-NO-ACTIONABLE-WORK</promise>` as the last text, yet the Stop hook logged `CONTINUE` both times (iterations 3→4, 4→5) with no `DEGRADED` entry.

### Evidence
Session transcript `377c3c70-d8ce-48e1-a428-09f6aadfdfb7.jsonl` record 669 (message `msg_011CfYUcWKUpdduPaeAoaGQo`, timestamp 21:56:01.018Z) ends with the exact promise; `.claude/esx-loop-exit.log` shows `21:56:01.063380 CONTINUE iteration=5`, 45 ms later. `current_text` logic handles this record correctly when run afterwards, implying the record was not yet on disk when the hook read the transcript.

### Potential Impact
Completed loops cannot terminate by promise; they run to the iteration budget, each extra turn posting a misleading progress notification.

### Proposed Fix
Before concluding no promise, have the hook fall back to `hook_input['last_assistant_message']` (if provided by the CLI) or briefly retry reading the transcript tail; alternatively let `loop_gate.py --next` exit 3 record a terminal marker the hook honours directly.

### Acceptance Criteria
With a final assistant message containing the promise and a transcript that is flushed only after hook start, the hook archives `END current completion promise fulfilled`.

### Expected Effect
Zero iterations consumed after a gate-confirmed no-actionable-work state.
