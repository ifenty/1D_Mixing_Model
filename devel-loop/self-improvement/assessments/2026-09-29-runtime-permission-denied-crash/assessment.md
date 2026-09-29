# Assessment: agent_runtime.py crashes on a `permission_denied` stream event

**Owner issue**: TEAM-RUNTIME-PERMDENIED-CRASH-001
**Observed**: 2026-09-29, 1DMIX-064 Bob dispatch (session c641620b-315d-44ad-9c0c-98d6aadf2b12, turn 404e048cf06a4a028cab33b9858d07fc)

## Reproduction
`agent_runtime.py start --role bob --issue 1DMIX-064 ...` with Claude CLI 2.1.285 on WSL, no permission allow rules in project or user settings. Bob's first Bash call was denied. CLI emitted (stdout.jsonl line 28, file sha256 prefix 2e9b2d1dc1c40482):

    {"type": "system", "subtype": "permission_denied", "tool_name": "Bash", ..., "message": "This command requires approval", ...}

`_read_tool_events` (tools/esx/agent_runtime.py:363) runs `event.get("message", {}).get("content", [])`; `message` is a str here, so it raises `AttributeError: 'str' object has no attribute 'get'` inside the watchdog, killing the adapter with a traceback and no footer or turn record.

## Consequence
The turn is left as work-of-unknown-completeness (no tree edits occurred in this instance). A headless role that hits any permission denial takes down the dispatcher instead of receiving the denial and continuing or reporting.

## Separate, project-local cause of the denial
This WSL workstation has no Bash allow rules for headless roles (`.claude/settings.json` has hooks only; `~/.claude/settings.json` has no `permissions`), so every non-read-only Bash call from a dispatched role is denied. That is an owner permission decision, not a kit defect.

## Recurrence after owner added allow rules (2026-09-29, Arch session 377c3c70)
Owner added `Bash(conda *)`, `Bash(~/miniforge3/bin/conda *)`, `Bash(pytest *)`, `cut`, `wc`, `sort`, `diff`, `sha256sum`, `echo`, `mktemp` allow rules to `.claude/settings.local.json` (which also sets `defaultMode: bypassPermissions`). A fresh `agent_runtime.py start --role bob --issue 1DMIX-064` (session 27bfb972-f560-44dc-b2d3-61c7df9f89b0, event 5b3819f255184327b5bc931efa984c56) crashed identically at `agent_runtime.py:363`. The child reported `"permissionMode":"default"` (the local `bypassPermissions` default does not reach the headless child), and its first Bash call — a compound `sed -n ...; grep ... | cut ...; python3 tools/esx/project.py signature; grep ... -A80 ... | head -150`, every segment of which matches an allow rule — was still denied with "This command requires approval" (stdout.jsonl line 15). So (a) the watchdog crash remains the kit defect, and (b) allow-rule matching for compound commands in headless children is not sufficient on this workstation.

A `--replaces-agent c641620b-...` start was refused with "replacement agent has no recorded dispatch": a crashed turn leaves no dispatch record, so the crashed identity cannot be formally replaced either — a second consequence of the same defect.

Workaround used: Arch dispatched Bob as a native `bob` subagent (inherits the Arch session's permission mode; recorded via the SubagentStop hook).
