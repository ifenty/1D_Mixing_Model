# Assessment: a default flip invalidated five documents; the brief enumerated three

**Date**: 2026-09-28
**Owner issue**: TEAM-DOC-SWEEP-001
**Scope**: Arch's brief scoping for 1DMIX-057.

## Measurement

Documents invalidated by flipping `keep_mitgcm_bugs` from `False` to `True`:

| document | in round-0 brief | found by |
|---|---|---|
| `Vertical_Mixing_Models/KPP/kpp_parameters.py` | yes | brief |
| `Vertical_Mixing_Models/KPP/kpp_routines.py` | yes | brief |
| `docs/model_contract.md` | yes | brief |
| `docs/code_map.md` | yes | brief |
| `KPP_port_validation/reports/possible_kpp_bugs_in_mitgcm.md` | no | Richard round 0 |
| `KPP_port_validation/reports/critical_lessons_fortran_to_python_porting.md` | no | Richard round 0 |
| three further spots inside `possible_kpp_bugs_in_mitgcm.md` | no | Richard round 1 |

Iteration accounting: 90-minute span, 5 dispatches (bob 3, richard 2), $27.91
total. Two of Bob's three rounds were documentation staleness only.

## Why the existing machinery did not catch it

`doc_contract.validate_report` enumerates dispositions from the *changed*
candidate. These documents were not changed by the work — that is exactly why they
were stale. The disposition machinery is therefore structurally blind to this
class: it asks "did you document what you changed", not "did what you changed
falsify something you did not touch."

## The cheap check that would have worked

`grep -rn keep_mitgcm_bugs` over the repository returns all five files in under a
second. It was run — after the fact, during this retrospective — and is how the
completeness of the final state was confirmed.

## Consequence

Bob reached the scope's `corrections: 2` limit with one annotation still
unconfirmed, so the iteration closed `partial` despite the science being complete
and independently validated. Arch made the last three annotations directly, which
was defensible only because that file lies outside every configured scanned root
(`project.py signature` was unchanged across the edits, at
`6444f7eab449dd18c1e54463c9597c11e360bac2aaaa4f3c9add7fecc434bed4`) — had the
stale document been inside the candidate, there would have been no way to finish.

## Not measured

- Whether an automatic enumeration in `brief.py` would be precise enough to be
  useful, or would flood a brief with incidental matches. Untested.
- The historical rate of this class across earlier iterations.
