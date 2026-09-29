# Assessment: the reviewer is never told which sealed report to cite, and cites a stale one

**Date**: 2026-09-28
**Owner issue**: TEAM-SEAL-CITATION-001
**Scope**: `tools/esx/brief.py::build`, `tools/esx/final_verification.py::ready`, measured on
two closeouts on 2026-09-28.

## What happened

A reviewer's footer must carry `documentation_review.report` equal to the *current* sealed
documentation plan. Each implementer correction forces a re-seal, because sealing binds the
plan to the exact current candidate bytes. So by a confirming round, the seal the reviewer
first read is one or two generations stale — and nothing in the brief or the packet makes the
current hash salient against the one already in his context.

## Measurement

Twice, on two different issues, with the same outcome.

**1DMIX-052.** Round-2 footer cited `093e1c22f81bf5204aabf551b9462d9eec0a92f4a61194a8ff4b48421b3e9ca1`,
the round-1 seal, with the reviewer's own note reading "Same sealed plan cited in round 1".
Current was `9029b239873eba074cedc52a59a429fa0d3ee7d622acd5e9727f9ce8a91058a8`.

**1DMIX-062.** Round-2 footer cited `4cac34ee352a1fd1c318f749f882623f6b803c0aa5dd727157a6150b46d5b0ac`,
the round-0 seal, after two re-seals. Current was
`e56f80cabd068a6d6e0adfdbeb4d08eb633283e5ddb3a9698e2c40835653f8a6`.

Both surfaced only at `final_verification.py check`, as `documentation_review.report must be
the exact sealed report reference, not a copy or a different report`. Both were resolved by a
footer-only correction round that named the current hash explicitly and told the reviewer to
read it rather than assume equivalence: 142 seconds and one further round respectively, with
the `APPROVE` verdict unchanged in both cases.

The same sequence is recorded once before this session, in 1DMIX-057's closeout: "Richard's
rounds 0 and 1 are recorded incomplete, round 1 solely because its footer cited a navigate
receipt instead of the sealed documentation report, which round 2 corrected with no change to
the verdict." Three occurrences, three wasted rounds, one cause.

## Why this is cheap to fix

Corrected on review. The current sealed reference is **already** put in front of the reviewer:
`brief.py::build` emits `'Richard confirms the exact sealed documentation reference in this
packet: ' + json.dumps(packet)`, and `packet['maintenance']['documentation']` carries it. That
has been true since commit `1482fe5`, before this session. So the defect is not missing
information but missing salience — the hash sits undifferentiated inside a large JSON blob,
indistinguishable from every other field, with nothing marking it as the thing to re-check
against a stale value already in context. Nothing about the integrity property needs to change:
the reviewer must still read the plan and must still be free to reject it.

## Proposed fix

Give the current sealed documentation reference a labeled, standalone line in the brief rather
than leaving it inside the packet dump, with an instruction to read that exact file rather than
assume it matches one already seen. Optionally also validate the citation at packet-build or
report-capture time rather than at final verification, so a stale citation is caught before a
reviewer's round is spent. Both halves are additive.

## Not measured

- Whether reviewers cite the stale seal because they are reusing context or because the brief
  does not name one. Only the outcome was observed; the cause is inferred from the fact that
  each correction naming the hash explicitly resolved it immediately.
- Whether the same staleness affects other footer references, for example `orientation`. Not
  checked.
