# Assessment: Arch's orientation is invalidated by exactly the edits Arch commissioned

**Date**: 2026-09-28
**Owner issue**: TEAM-ARCH-REORIENT-001
**Scope**: `tools/esx/doc_contract.py::check_start` / `validate_orientation` and
`workflow_handoff.assemble`'s `ARCH_ORIENTATION_INVALID` finding, measured across four
issues on 2026-09-28.

## What happened

Arch records an orientation at `--prepare`, naming a map heading, source targets and
documentation sections. The implementer then edits those documents — because that is the
assignment — and the packet build refuses with `ARCH_ORIENTATION_INVALID`, listing the changed
target and its before/after hashes. The remedy is to rerun `doc_contract.py navigate` with the
same map, the same targets and the same documents, changing only the free-text `--use`.

This is distinct from `TEAM-ORIENTATION-RESEAL-001`, which covers an *implementer* invalidating
his own receipt by editing his own oriented targets. Here the invalidation is of the
*coordinator's* orientation, by an agent, doing what the coordinator asked.

## Measurement

Five re-navigations across four issues, every one triggered by a commissioned edit:

- **1DMIX-052**, after the implementer's correction: `changes=[{"target":
  "MITgcm_to_Python_port_verification/README.md#current-validation-status", "changed":
  ["documentation"], "before": "f252270f…", "after": "ddd389e5…"}]` — the edit Arch had
  directed, to the line Arch had oriented on.
- **1DMIX-061**, after the witness and contract statements landed.
- **1DMIX-062**, twice — once after the initial repair, once after the sweep correction.
- **1DMIX-063**, after the guard and coverage statements landed.

In all five the arguments to `navigate` were unchanged apart from `--use`. No case surfaced a
change Arch had not already directed or already read, and no re-navigation changed any
subsequent judgment.

## Why this is not simply a correct check

The integrity property is sound: a coordinator must not carry a stale picture of the code into
a review packet. What is wrong is the cost/benefit at this particular boundary. The check
cannot distinguish "the dependency slice moved under you" from "the agent did the thing you
asked in the file you asked about", and only the first is a real staleness risk. Because the
remedy is a re-issued command with identical arguments, the check has the property that makes
controls decay: it is satisfied by ceremony rather than by attention, and an Arch who has done
it five times will do the sixth without reading the diff — which is exactly the failure the
check exists to prevent.

`ARCH_ORIENTATION_INVALID` already prints every changed target with old and new hashes, so the
information needed for a genuine acknowledgement is on screen at the moment of refusal.

## Proposed fix

**A diff-acknowledgement was proposed here and rejected on review; the rejection matters more
than the original proposal.** Letting Arch clear staleness by citing the changed targets'
expected new hashes does *not* preserve the property: `validate_orientation` already embeds
each `after` hash in its own refusal text, so such an acknowledgement is satisfiable by copying
the refusal, with zero exposure to file content — strictly weaker than re-running `navigate`,
which at least reprints the current 65-line excerpt through `_navigate`. It would have been a
regression dressed as a preservation.

Remove the retyping without removing the exposure instead: a `navigate --reuse-args
<prior-orientation-ref>` shortcut that reloads the recorded map, targets and documents so they
need not be re-supplied by hand, still executes the excerpt-printing path, and still demands a
freshly written `--use`. Refuse the shortcut when a changed target was *not* in the original
orientation's own target or document list, since that is the case the check is actually for —
the slice moving somewhere Arch never looked.

## Not measured

- Whether an Arch orientation has ever gone stale for a reason *other* than a commissioned
  edit. That is the case the check protects and no instance of it was observed this session,
  so its frequency is unknown and the fix must not blind the check to it.
- Whether the same ceremony affects reviewer orientations at the same rate.
