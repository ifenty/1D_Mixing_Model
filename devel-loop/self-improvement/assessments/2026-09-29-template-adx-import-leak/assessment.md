# Assessment: the ESX template imports a module that exists only in the ADX project

**Date**: 2026-09-29
**Owner issue**: TEAM-TEMPLATE-ADX-IMPORT-001
**Scope**: `tools/esx/workflow_handoff.py` as shipped by the ESX-Team template and
deployed unchanged into this project.

## Observation

`tools/esx/workflow_handoff.py:141-144`:

```python
try:
    import adx_workflow as lifecycle
except ImportError:
    import workflow_policy as lifecycle
```

- No `adx_workflow` module exists anywhere in this repository. The only file of
  that name on this workstation is `~/Projects/ADX/tools/adx_workflow.py`, which
  belongs to the separate ADX project.
- The same lines are in the upstream template at
  `~/Projects/ESX-Team/template/tools/esx/workflow_handoff.py:142` (ESX-Team HEAD
  `c630fc3`, 1.5.0). `git log -S adx_workflow` in ESX-Team finds only `f8f6df1`
  (the first commit), so the line has been there since the framework was
  extracted from ADX. The deployed copy here is byte-identical to the template
  (`diff -q` reports no difference).
- Found on 2026-09-29 by a whole-repo scan for imports missing from the new
  `ecco` environment; the owner confirmed there is no `adx_workflow` in this
  project.

## Effect today

Nothing breaks at runtime: the `ImportError` path always runs and binds the
project-local `workflow_policy`, which is the intended lifecycle module.
`loop_gate.py --doctor` passes. The costs are:

1. **A misleading dependency**: import scans, and readers, see a dependency that
   cannot be satisfied and must work out that it doesn't matter. That happened
   in this session: it was first misdescribed as "an optional ESX tooling import".
2. **A silent-substitution hazard**: if any importable `adx_workflow` ever lands on
   `sys.path` (e.g. running from a shell where the ADX tools directory is on
   `PYTHONPATH`), the handoff check silently uses ADX's lifecycle rules instead of
   this project's `workflow_policy.resolved_dispatch`, and nothing records the switch.

## Recommended upstream fix

In `template/tools/esx/workflow_handoff.py`, replace the `try`/`except` with
`import workflow_policy as lifecycle`, grep the template for any other
`adx`-specific names, and redeploy. No project-local edit here in the meantime:
`tools/esx` stays byte-identical to the template.
