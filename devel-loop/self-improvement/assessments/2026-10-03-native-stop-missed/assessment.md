# Native reviewer stop not recorded (1DMIX-080, 2026-10-03)

Richard (native Agent-tool subagent, id a325d9f09d6c933c3) finished the 1DMIX-080 review at about
05:06Z. The host delivered his report and a completion notification. No SubagentStop record for him
reached `devel-loop/loop_state/dispatch_log.jsonl`, his `native_inflight/a325d9f09d6c933c3.json`
marker remained, and `loop_control.py status` still read "richard running".

Recovery: the stop event was rebuilt from his transcript
(`~/.claude/projects/<project>/<session>/subagents/agent-a325d9f09d6c933c3.jsonl`; final assistant
text, agent_type richard, agent_id, session_id, agent_transcript_path) and piped to
`python3 tools/esx/hooks.py subagent-stop`. It recorded `completed`, verdict REJECT, and cleared the
marker. That took 3.27 s real.

Timing: `time_reference_check.py` (this directory) runs only `footer_contract.reference_errors` on
Richard's real footer. Cold, it took 9.6 s real (user 3.6 s, sys 7.3 s). The hook limit in
`.claude/settings.json` is 15 s. A hook killed at its timeout would leave exactly this state. The
cause is not established; Bob's stop in the same iteration was recorded.
