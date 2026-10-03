"""TEAM-LOOP-USAGE-LIMIT-PAUSE-001: the deployed Stop hook recognises a real usage-limit turn and its recovery.

Fixtures are this coordinator session's own transcript records (text omitted,
structural fields kept): the provider's synthetic rate_limit record, and the
same turn followed by the "usage limit has reset" message and real output.
"""
import json
from pathlib import Path
import sys
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parents[3] / 'tools/esx'))
import ralph_stop
limited = here / 'limited_turn.jsonl'
resumed = here / 'resumed_turn.jsonl'
records = [json.loads(l) for l in limited.read_text().splitlines()]
results = {
    'synthetic_record_detected': ralph_stop.synthetic_limit(records[-1]),
    'real_output_not_detected': not ralph_stop.synthetic_limit(records[1]),
    'limited_turn': ralph_stop.provider_turn(str(limited)),
    'resumed_turn': ralph_stop.provider_turn(str(resumed)),
}
ok = (results['synthetic_record_detected'] and results['real_output_not_detected']
      and results['limited_turn'] == 'limited' and results['resumed_turn'] == 'working')
print(json.dumps(dict(results, deployed_ralph_stop=str(Path(ralph_stop.__file__).relative_to(here.parents[3])), status='PASS' if ok else 'FAIL'), indent=2))
sys.exit(0 if ok else 1)
