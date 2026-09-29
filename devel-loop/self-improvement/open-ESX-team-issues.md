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

---

## 🔴 PROPOSED: Issue allocations are chosen by workflow kind rather than by measured work size, and `--timeout` is assumed to extend a turn past its scope deadline

**Date Identified**: 2026-09-28  03:50
**Status**: Proposed
**UUID**: TEAM-BUDGET-SIZING-001
**Category**: budget_allocation_sizing
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-budget-allocation-sizing/assessment.md
**Anchors**: tools/esx/team_budget.py::reserve; tools/esx/team_budget.py::limits; tools/esx/loop_gate.py::Gate.prepare

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
**Status**: Proposed
**UUID**: TEAM-ORIENTATION-RESEAL-001
**Category**: stale_orientation_after_self_edit
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-orientation-reseal/assessment.md
**Anchors**: tools/esx/doc_contract.py::validate_orientation; tools/esx/brief.py::build

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
**Status**: Proposed
**UUID**: TEAM-DOC-SWEEP-001
**Category**: documentation_staleness_sweep
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-doc-staleness-sweep/assessment.md
**Anchors**: tools/esx/brief.py::build; tools/esx/doc_contract.py::validate_report

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
**Status**: Proposed
**UUID**: TEAM-TURN-CAP-001
**Category**: turn_cap_breach
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-turn-cap-breach/assessment.md
**Anchors**: tools/esx/team_budget.py::settle; tools/esx/team_budget.py::reserve; tools/esx/team_budget.py::extend

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
**Status**: Proposed
**UUID**: TEAM-BASELINE-PIN-001
**Category**: pinned_baseline_makes_late_closure_disproportionate
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-baseline-pin/assessment.md
**Anchors**: tools/esx/doc_contract.py::baseline; tools/esx/doc_contract.py::original_baseline; tools/esx/doc_contract.py::draft

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
**Status**: Proposed
**UUID**: TEAM-UPGRADE-DIFF-001
**Category**: upgrade_pollutes_issue_diffs
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-upgrade-pollutes-issue-diffs/assessment.md
**Anchors**: tools/esx/project.py::selected; tools/esx/project.py::inventory_paths; tools/esx/doc_inventory.py::changes; tools/esx/doc_contract.py::draft

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
**Status**: Proposed
**UUID**: TEAM-REITERATION-CLOSEOUT-001
**Category**: reiteration_closeout_route_undiscoverable
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-reiteration-closeout/assessment.md
**Anchors**: tools/esx/workflow_records.py::prepare_done; tools/esx/workflow_policy.py::validate_reviews; tools/esx/workflow_policy.py::resolved_dispatch; tools/esx/workflow_policy.py::validate_scope_decisions

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
**Status**: Proposed
**UUID**: TEAM-VERIFY-RERUN-001
**Category**: final_verification_rerun_lifecycle
**Severity**: High
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-final-verification-rerun/assessment.md
**Anchors**: tools/esx/final_verification.py::ready; tools/esx/final_verification.py::check_receipt; tools/esx/loop_gate.py:158; tools/esx/loop_lifecycle.py::prepare_done

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
**Status**: Proposed
**UUID**: TEAM-LEDGER-AHEAD-001
**Category**: ledger_precedes_validation
**Severity**: Medium
**Assessment**: devel-loop/self-improvement/assessments/2026-09-28-ledger-precedes-validation/assessment.md
**Anchors**: tools/esx/loop_gate.py:158; tools/esx/loop_lifecycle.py::prepare_done; closed_issues.md; open_issues.md

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
