import json, sys, time
sys.path.insert(0, 'tools/esx')
import footer_contract
start = json.load(open('devel-loop/loop_state/issue-start.json'))
footer = {"agent": "richard", "issue_id": "1DMIX-080",
  "orientation": {"path": "devel-loop/loop_state/maintenance/76fa2af0d3a493bdfd76a7b964b2e3b77293395dcbe0c3e62a5e6cb133d72da4.json", "sha256": "76fa2af0d3a493bdfd76a7b964b2e3b77293395dcbe0c3e62a5e6cb133d72da4"},
  "independent_check": {"evidence": {"path": "devel-loop/loop_state/verification/476739e5552b0adb5386d85cbd678d76ae009b72b41a921d7c102fd7fa72aca1.json", "sha256": "476739e5552b0adb5386d85cbd678d76ae009b72b41a921d7c102fd7fa72aca1"}},
  "documentation_review": {"report": {"path": "devel-loop/loop_state/maintenance/8e35884ce8ed14edbfb3d8147f28c2dea723c26ab93898ecf775bf59f6c926cd.json", "sha256": "8e35884ce8ed14edbfb3d8147f28c2dea723c26ab93898ecf775bf59f6c926cd"}}}
t = time.time()
print(footer_contract.reference_errors('.', 'richard', footer, start, 'a325d9f09d6c933c3'))
print('seconds', round(time.time() - t, 1))
