# Assessment: closeout requirements are discovered one rejection at a time, on first iterations too

**Date**: 2026-09-28
**Owner issue**: TEAM-CLOSEOUT-DOCTOR-001
**Scope**: `tools/esx/loop_gate.py --check-done`, `tools/esx/final_verification.py ready`,
`tools/esx/workflow_records.py review-packet`, measured across four closeouts on 2026-09-28.

## What happened

Assembling a closeout means satisfying a set of requirements that is never stated in advance.
Each tool reports the first unmet one, the closer fixes it, reruns, and learns the next.

`TEAM-REITERATION-CLOSEOUT-001` already covers this, but it is scoped explicitly to "an
issue's second iteration" whose first closed partial. The measurements below show the pattern
is not confined to that case.

## Measurement

**1DMIX-052, iteration 2** — eight sequential rejections, in this order:

```
map_delta needs updated or MAP-OK status
candidate reference is required
review packet still has pending preparation fields
bob: failed or incomplete turn remains unresolved
stale arch orientation: receipt=...; changes=[README.md#current-validation-status]
documentation_review.report must be the exact sealed report reference
record stable bob runtime identities
final verification receipt is stale
```

**1DMIX-062, iteration 1** — four rejections, so not a second-iteration effect:
`ARCH_ORIENTATION_INVALID`, `STRUCTURAL_STALE_OR_FAILING`, `documentation_review.report must
be the exact sealed report reference`, and `final review must reference the latest completion
event; current candidate has 0 independent approvals`.

**1DMIX-063, iteration 1** — prerequisites passed on the first attempt, because by then the
order had been learned. That contrast is the evidence that the cost is discovery, not
complexity: the same closer, the same tooling, the same class of issue, and the difference
between eight rejections and zero is prior exposure.

Measured cost of discovery: roughly 25 minutes on 1DMIX-052 and 10 on 1DMIX-062, entirely on
bookkeeping, on issues whose substantive work was complete and whose reviewers had approved.

## Why the consequence is worse than the time

Two of the eight rejections are traps rather than instructions. `record stable bob runtime
identities` does not say that the value wanted is the list of `dispatch_id`s already present
in `subagents`. And `final verification receipt is stale` fires *after* a passing suite,
because the fields feeding `review_signature` were still being discovered when the receipt was
taken — so the natural order of work guarantees the failure. A closer who has not met that
before will reasonably conclude the suite must be rerun.

Every individual check is correct and none should be relaxed. The defect is that the set is
knowable up front and is not offered.

## Proposed fix

Add a dry-run that reports *all* unmet closeout requirements at once rather than the first.
The information exists: `final_verification.ready` and `loop_gate.check_done` already compute
these conditions, and `workflow_handoff.readiness` already demonstrates the pattern of
returning a `findings` list instead of raising on the first problem. Extend that shape to
`--check-done` behind a flag, or add `loop_gate.py --closeout-doctor`. Make the
`review_signature` dependency explicit in the output, so the ordering constraint — finalize
every signed field before taking the receipt — is stated rather than learned by rejection.

## Not measured

- Whether the full requirement set can always be computed before the first fix, or whether
  some checks genuinely depend on earlier ones being satisfied. `readiness` suggests most can
  be collected independently; this was not verified for every check.
- Time cost for a closer who has never done one, as distinct from one who has done three.
