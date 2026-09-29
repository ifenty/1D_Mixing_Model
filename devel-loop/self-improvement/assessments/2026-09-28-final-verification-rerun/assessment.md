# Assessment: the final-verification receipt lifecycle does not survive an interrupted run

**Date**: 2026-09-28
**Owner issue**: TEAM-VERIFY-RERUN-001
**Scope**: `tools/esx/final_verification.py`, `tools/esx/loop_gate.py --check-done`, and
`tools/esx/loop_lifecycle.py::prepare_done`, measured against the three
final-verification receipts 1DMIX-057 iteration 3 actually produced.

## What happened

Three receipts exist for one candidate (`ce0546991f19eb92a42387f6acc67a0aaa153888943fbbcb9ec33a51713c72c4`),
one owner (`arch`) and one iteration timestamp (`2026-09-28T16:40:40.419142+00:00`):

```
9aab3c9e…  PASS     17:29:06Z   review_signature f43fdb82…   scientific bc0b4299…
c776b4b8…  FAILED   17:35:55Z   review_signature fb6d1180…   error "verification failed or source changed"
9d4a346a…  PASS     20:15:41Z   review_signature fb6d1180…   scientific acb6caf4…
```

The first PASS was real but became void: the closeout record was edited after it,
moving `review_signature` from `f43fdb82…` to `fb6d1180…`. That was handled correctly
at the time — a re-run was launched. The re-run is the one that did not survive. It
was cut off at 70% of 123 collected tests and recorded `FAILED`, which left
`final-verification/current.json` absent and the closeout blocked for about three hours
until a later session re-ran the suite to completion (`9d4a346a…`, 120 passed, 3 skipped,
655.58s).

## Measurement

Three separate defects compounded, each cheap to fix on its own.

**1. An interrupted run is labelled `FAILED`.** `run-9958b8af12e54753899315786d2b1b75.log`
contains **zero** lines matching `FAILED|ERROR`. It stops mid-line at
`test_global_ocean_cs32x15_pressure_coordinate_gap[visc_az-90.0-1000.0]` at `[ 70%]`,
with no pytest summary line. The same suite completed `120 passed, 3 skipped` in
486.59s immediately before it (`run-c1742ac0…`) and in 655.58s after it. So nothing
failed and the source did not move; the process simply stopped. The receipt's own error
text — `"verification failed or source changed"` — conflates three causes (a test
failed, the source moved under the run, the run never finished) and the only way to
tell them apart is to grep the log. A reader of the receipt alone would conclude a
scientific regression.

**2. `--check-done` names a missing file rather than the situation.** Its entire output
was `ESX gate: BLOCKED: [Errno 2] No such file or directory: …/final-verification/current.json`.
The gate has everything needed to say more: the iteration's last attempt, its status,
its log and whether that log holds real failures. Establishing "the science did not
fail, just re-run the suite" instead took reading three receipts, two logs and
`final_verification.py::review_signature` before any suite could be started — about
14 minutes, all of it before the 11-minute run that was the actual remedy.

**3. The closeout record keeps citing the void receipt.** `prepare_done` writes
`verification.receipt` and `verification.scientific` once, at prepare time. After the
successful re-run the record still cited `9aab3c9e…`, whose `review_signature` no
longer matched the record it was stored in. There is no supported operation to
re-point a prepared closeout at the current receipt, so the only route forward was to
hand-edit an active closeout record — the same record `--check-done` then validates.

## Why the consequence is disproportionate

The scientific suite is the most expensive single step in the loop: 486–656s measured,
versus seconds for every gate check around it. Its receipt is therefore the artifact
whose truthfulness matters most, and it is the one that cannot currently distinguish
"this candidate is wrong" from "this process was killed". Worse, the expensive remedy
(re-run) and the cheap remedy (re-point at an existing PASS) are indistinguishable
from the gate's message, so the safe default is always to pay full price.

## Proposed fix

Separate incompleteness from failure in the receipt: record `INTERRUPTED` when the
child process exited on a signal or its log carries no pytest summary line, and keep
`FAILED` for a real non-zero test outcome. Have `--check-done` read the iteration's
latest attempt and say which of the three cases it is, naming the log. Add a supported
way to bind a prepared closeout to `current.json` so refreshing a receipt after a
re-run is a tool operation rather than a hand edit.

## Not measured

- Why the 17:35Z run was killed. Its `finished_at` is 6m49s after the prior run's
  completion and the log stops cleanly mid-write; no OS-level cause was retained,
  and the loop's own iteration budget was reached later, at 19:40Z.
- Whether `verify.py` already distinguishes signal exit from non-zero exit internally
  and only the receipt flattens it. Inferred from the receipt's error string, not read.
