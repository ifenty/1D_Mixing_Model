# Assessment: an ESX upgrade lands in every open project issue's candidate diff

**Date**: 2026-09-28
**Owner issue**: TEAM-UPGRADE-DIFF-001
**Scope**: `project.FRAMEWORK_PATHS` participation in the documentation inventory,
observed after upgrading a receiving project from ESX 1.1.1 to 1.2.2 with six
issues open.

## Measurement

Disposition targets per open issue, and how many are framework-owned rather than
the issue's own work:

| issue | total | framework-owned | its own |
|---|---|---|---|
| 1DMIX-055 | 18 | **18** | **0** |
| 1DMIX-054 | 36 | 18 | 18 |
| 1DMIX-059 | 56 | 19 | 37 |
| 1DMIX-058 | 71 | 19 | 52 |
| 1DMIX-057 | 75 | 19 | 56 |
| 1DMIX-052 | 102 | 20 | 82 |

`FRAMEWORK_PATHS` is `['tools/esx', '.claude', 'devel-loop', 'docs', 'esx',
'CLAUDE.md', '.gitignore']` and participates in the non-scientific inventory that
a candidate diff is computed over. The upgrade changed `team_budget.py`,
`brief.py`, `agent_runtime.py`, `team_driver.py`, `ralph_stop.py` and
`devel-loop/team_operations.md`, so those symbols now appear in the diff of every
issue whose baseline predates the upgrade.

1DMIX-055 is the clearest case: **100% of its 18 targets are framework symbols.**
Its own deliverables -- two per-scheme validation reports, a pointer file and a
trimmed README -- all sit outside configured scanned roots and so contribute no
targets at all. Closing it would require a documentation report under a
report-splitting issue asserting that documentation is accurate for
`tools/esx/team_budget.py::observe`.

## Why the inclusion is defensible in general

A receiving project may legitimately patch framework code, and such a patch should
be documented and reviewed like any other change. This project did exactly that
before upstreaming two patches into 1.1.1. Excluding framework paths outright would
let a local framework edit through unreviewed.

## Why the consequence is nevertheless wrong

When the change arrives from an *upgrade* rather than from the issue, it is pure
noise in that issue's record, and it scales with how many issues are open. An
upgrade is meant to be routine; here it made all six open issues materially harder
to close, and made one of them impossible to close honestly.

The distinguishing information already exists: `esx_upgrade.py` records the exact
transaction in `ESX-team-local/`, including per-file `before_sha256`,
`result_sha256` and `master_sha256`. A target whose current bytes match the
`master_sha256` of a recorded upgrade is provably framework-supplied rather than
project-authored.

## Candidate fix

Disposition such targets automatically as upgrade-supplied, citing the deployment
record that supplies them, rather than either excluding them silently or asking a
reviewer to judge them. That keeps a genuine local framework patch in scope --
its bytes would not match `master_sha256` -- while removing upgrade noise.

## Not measured

- Whether every upgrade path records enough to make the match reliable, including
  three-way merges where the result matches neither side.
- Whether `docs/` and `devel-loop/` project-owned files inside `FRAMEWORK_PATHS`
  need different treatment from `tools/esx/`.
