"""Record one new, local synthetic test run. Does not contact any service."""
from pathlib import Path
import argparse
import base64
import io
import json
import platform
import sys
import unittest

import json_integrity as sut
import test_sys02

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--run', default='r001')
args = parser.parse_args()
if not args.run.isalnum():
    raise SystemExit('RUN_ID_INVALID')
out = HERE / 'results'
out.mkdir(exist_ok=True)
logpath, reportpath = out / (args.run+'.log'), out / (args.run+'.json')
if logpath.exists() or reportpath.exists():
    raise SystemExit('EXISTING_RUN_STOP_NO_OVERWRITE')
stream = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromModule(test_sys02)
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
env = {'python':sys.version.split()[0], 'os':platform.platform(), 'scope':'OFFLINE_SYNTHETIC_ONLY_NOT_PRODUCTION'}
log = 'ENV '+json.dumps(env,sort_keys=True)+'\n'+stream.getvalue()
with logpath.open('x') as f: f.write(log)
examples, input_labels, canonical_labels, axis_labels = [], set(), set(), set()
for case in test_sys02.CASES:
    report = sut.compare_bytes(base64.b64decode(case['left_b64']),base64.b64decode(case['right_b64']),**case['settings'])
    examples.append({'id':case['id'], 'axes':report['axes'], 'left':report['left'], 'right':report['right']})
    for side in ('left','right'):
        input_labels.add(report[side]['input_status']);canonical_labels.add(report[side]['canonical']['status'])
    axis_labels.update(x['state'] for x in report['axes'].values())
summary = {'status':'PASS_DEVELOPMENT_ONLY' if result.wasSuccessful() else 'FAIL', 'environment':env,
    'unittest_tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
    'synthetic_fixture_cases':len(test_sys02.CASES),'input_classifications_exercised':sorted(input_labels),
    'canonical_classifications_exercised':sorted(canonical_labels),'axis_states_exercised':sorted(axis_labels),
    'real_records_received':0,'HQ14_56_record_validation':'NOT_PERFORMED_HQ14_PRIVATE',
    'independent_review':'PENDING_AFTER_CERTIFI','production_application':'NOT_AUTHORIZED', 'production_GO':False,'examples':examples}
with reportpath.open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in summary.items() if k!='examples'},ensure_ascii=False))
raise SystemExit(0 if result.wasSuccessful() else 1)
