# Assessment: the scientific_change per-turn cap is below the measured cost of a long implementation turn

**Date**: 2026-09-28
**Owner issue**: TEAM-TURN-CAP-001
**Scope**: `team_budget.DEFAULTS['scientific_change']['turn_usd']` against this
session's measured Bob turn costs.

## What happened

1DMIX-054's single implementation turn reserved its per-turn cap of $12.00. The
provider reported $12.735075. `team_budget.settle` recorded
`provider_overshoot: True` and set `breached: True` on the scope, which makes
`reserve` refuse every further launch, and `extend` refuse the scope entirely on
the grounds that a breach "requires reconciliation, not a budget extension".

A $0.74 overshoot therefore hard-blocked an issue whose scope still had roughly
half its wall clock, 400 of 500 calls and $48 of $60 unspent.

## Measurement

`scientific_change` sets `turn_usd: 12`. Long Bob turns measured this session:

```
1DMIX-056 round 0   $11.17
1DMIX-058 round 0   $17.12  (under a scope whose turn cap was also 12)
1DMIX-060 round 0   $16.95
1DMIX-057 round 0   $18.91
1DMIX-054 round 0   $12.74  -> breach
```

Four of five exceeded $12. The cap is below the central tendency of the very turns
the class exists to fund, so a breach is close to inevitable on any long turn
rather than exceptional. That the earlier ones did not breach appears to be because
`reserve` clamps the reservation to the remaining scope spend
(`amount = min(amount, available)`), so a turn reserving less than the cap can
report more than its reservation without tripping the comparison in the same way.
That mechanism was not investigated further and is the first thing a fix should
establish.

## Why the consequence is disproportionate

Wall-budget exhaustion is recoverable: an Owner extension exists for it, and four
issues in this session are waiting on exactly that. A provider breach is not
recoverable that way by design — `extend` refuses it outright. So the harsher
outcome attaches to the smaller and less controllable error: Arch chooses the wall
budget, but nobody chooses how much a provider decides a turn cost.

## Proposed fix

Establish whether `turn_usd` for `scientific_change` should simply be raised to
sit above the measured distribution of long implementation turns, or whether the
reservation-clamping interaction means the cap is being compared against the wrong
quantity. Then decide whether a small overshoot should breach at all, or whether
breach should require exceeding the reservation by a material margin rather than
by any amount.

## Not measured

- Whether the four non-breaching turns above avoided breach through the clamping
  mechanism or for another reason. Inferred from reading `reserve`, not tested.
- Provider cost variance for identical work, which would set how much headroom a
  cap needs.
