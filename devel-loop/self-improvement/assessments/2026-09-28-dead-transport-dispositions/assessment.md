# Assessment: a known-dead provider still requires one disposition per queued event

**Date**: 2026-09-28
**Owner issue**: TEAM-DEAD-TRANSPORT-001
**Scope**: `tools/esx/notifications.py record`, `devel-loop/communication.md`, measured over
the 2026-09-28 session.

## What happened

The communication contract is right that leaving events `pending` cannot satisfy the delivery
duty, and right that each event needs a real receipt or a concrete failure. But when the
provider is established dead for the whole session, that contract costs one tool call and one
hand-written justification per event, each carrying the same reason.

## Measurement

Slack was unauthenticated for the entire session: only
`mcp__plugin_slack_slack__authenticate` and `__complete_authentication` were ever exposed, and
`slack_send_message` — which delivered events as recently as 2026-09-20 — was absent
throughout. `authenticate` was called once, returned an OAuth authorize URL requiring an owner
browser step, and that step was never completed, so no send tool appeared and no retry was
ever possible.

**76 events** were dispositioned `unavailable` across the session. `notifications.py record`
takes exactly one event positional and has no batch mode, so each needed its own invocation,
each supplying a `--detail` string of 300 to 500 characters restating the same discovery. Some
invocations were wrapped in shell loops; the number of separate tool calls is not logged and is
not claimed here. Breakdown: 19 `issue_start`, 19 `issue_closeout`,
19 `progress`, 9 `issue_opened`, 4 `loop_start`, 4 `loop_end`, 2 `lesson`. Final ledger state:
0 pending, 0 undispositioned.

The gate enforces this per event: `--next` refuses to advance to issue selection while any
event is pending, so each closeout's announcement had to be dispositioned individually before
work could continue, five times over.

## Why the current shape is worth changing

Nothing here is a correctness problem — the ledger is accurate and the Owner-facing report was
able to state exactly what was undelivered and why. The cost is twofold. First, repetition
invites degradation: a justification retyped fifteen times becomes boilerplate, and boilerplate
is where a genuinely different failure would get mislabelled as the familiar one. Second, the
per-event detail strings now contain fifteen near-copies of one discovery, so a future reader
auditing the ledger cannot tell from the records whether the transport was probed fifteen times
or once.

The distinction the ledger cannot currently express is exactly the one that matters: a
*per-event* failure, where this send was attempted and failed, versus a *session-scoped*
transport outage, where no send was possible at all.

## Proposed fix

Allow one session-scoped provider disposition that applies to every currently queued event and
to events queued later in the same session, recording the discovery once with its probe
evidence, and marking each event as covered by that outage rather than individually
adjudicated. Require a **forced** re-probe rather than a discretionary one — one attempt per
loop iteration or per N covered events, whichever comes sooner, plus an iteration-count bound
after which the outage must be renewed with fresh probe evidence. A discretionary re-probe has
no forcing function, so an outage declared once could cover an arbitrarily long session after
the transport recovered, whereas today's 76 per-event dispositions at least create 76 moments
where recovery could be noticed. Keep
per-event dispositions for `failed` — an executed send that failed is genuinely per-event
information and should stay that way. Have `--next` treat events covered by an active outage as
dispositioned, so the gate stops blocking issue selection on a transport known to be down.

## Not measured

- Whether a send tool would have appeared had `authenticate` been re-invoked later. It was
  deliberately not re-called, because a second call invalidates the outstanding URL the Owner
  had been given, so this is untested rather than ruled out.
- Whether any of the 76 events would have failed for a per-event reason had the transport been
  up. Unknowable from here.
