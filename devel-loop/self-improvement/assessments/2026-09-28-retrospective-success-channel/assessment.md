# Assessment: the retrospective schema has no success channel, so confirmations are recorded as problems

**Date**: 2026-09-28
**Owner issue**: TEAM-RETRO-SUCCESS-001
**Scope**: `tools/esx/team_retrospective.py` schema validation, against five retrospectives
accepted on 2026-09-28.

## What happened

A schema-version-2 retrospective carries `problems`, `solutions`, `carry_forward` and
`no_problem_reason`. There is no field for a confirmation — an approach that was tried
deliberately, worked, and should be repeated. `accept` requires every `problems` entry to
have `category`, `summary`, `evidence` and a non-negative integer `minutes_lost`, and requires
each problem to have a `solutions` disposition.

So recording a success means writing it into the failure array with `minutes_lost: 0`.

## Measurement

Six instances, across two sessions, all saying some version of the same thing in prose because
the schema cannot say it structurally. The reviewer's recount found ten `minutes_lost: 0`
entries in total: six carry this complaint, four are genuine zero-cost defects.

- 1DMIX-058: `distinct_reviewer_questions_found_new_ground`, `minutes_lost: 0`, whose summary
  opens *"Recorded because the schema has no success channel"*.
- 1DMIX-061: `restated_rules_prevented_rework`, `minutes_lost: 0`, opening *"Recorded because
  the schema has no success channel, and because this iteration is the controlled comparison
  for the immediately preceding one."*
- 1DMIX-063: `handbuilt_witness_guards_callee_not_pipeline`, `minutes_lost: 0`, opening
  *"Recorded because it is the third consecutive demonstration of one structural fact and the
  schema has no channel for a finding that is neither a process failure nor a success."*
- 1DMIX-054 and 1DMIX-059 both carry `bounded_first_step_paid_off` with the same complaint.
- One further entry in the same window carries `minutes_lost: 0` for the same reason.

Each of these also had to be given a `solutions` entry with `action: filed` against an open
process issue, because the validator demands a disposition per problem — so a confirmation is
additionally forced to nominate an owner as though it were a defect.

## Why it matters beyond tidiness

The project's own guidance says to record from success as well as failure, on the grounds that
recording only corrections avoids past mistakes but drifts away from approaches already
validated. The schema contradicts that guidance: the only cheap way to log a validated
approach is to file it as a problem. Two consequences follow. A reader scanning `problems`
arrays to count defects over-counts, because some entries are successes. And a reader looking
for what to keep doing has nowhere to look, since confirmations are scattered inside a failure
field and distinguishable only by `minutes_lost: 0` and a prose disclaimer.

The 1DMIX-061 entry is the sharpest case: it exists specifically as the controlled comparison
against 1DMIX-052, where the same rule was unstated and cost a 59-tool-call turn. That is the
most useful kind of process evidence the program can produce, and it is filed as a problem.

## Proposed fix

Add a `confirmations` array to schema version 3: entries carrying `category`, `summary`,
`evidence`, and no `minutes_lost` or `solutions` requirement, since a confirmation needs no
owner. Keep `problems` for defects. Have `--draft-retro` emit both arrays, and have `validate`
accept a retrospective whose `problems` is empty when `confirmations` is not, without demanding
a 60-character `no_problem_reason` — the confirmations *are* the measured evidence that reason
exists to supply — but keep an evidentiary floor, because without one the new path is a strictly
lower bar than today's. Confirmations must carry substantive `evidence` exactly as `problems`
entries must, and an empty `problems` array is exempted only from *duplicating* the explanation,
never from supplying one. Retain the existing recurring-category machinery for `problems` only.

## Not measured

- Whether any prior analysis of this project's `problems` history was distorted by the
  miscounting. Plausible but not established.
- How many `minutes_lost: 0` entries across all history are confirmations versus genuine
  zero-cost defects. Five were identified by reading; the full history was not audited.
