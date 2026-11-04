"""Record synthetic development tests only; never calls a model or service."""
from pathlib import Path
import argparse
import io
import json
import platform
import sys
import unittest
import test_p3
from evaluator import evaluate_pairs
from box_arithmetic import check_box

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--run',default='r001');args=p.parse_args()
if not args.run.isalnum():raise SystemExit('RUN_ID_INVALID')
out=HERE/'results';out.mkdir(exist_ok=True)
log=out/(args.run+'.log');report=out/(args.run+'.json')
if log.exists() or report.exists():raise SystemExit('RUN_EXISTS_NO_OVERWRITE')
stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromModule(test_p3)
r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
env={'python':sys.version.split()[0],'os':platform.platform(),'scope':'OFFLINE_SYNTHETIC_RESEARCH_ONLY'}
with log.open('x') as f:f.write('ENV '+json.dumps(env,sort_keys=True)+'\n'+stream.getvalue())
fixture=test_p3.F
obj={'status':'PASS_DEVELOPMENT_ONLY' if r.wasSuccessful() else 'FAIL','tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'environment':env,'real_data_received':0,'actual_model_training_or_prediction':0,'Production_actions':0,'independent_review':'PENDING_AFTER_CERTIFI','production_GO':False,'example_evaluation':evaluate_pairs(fixture['pairs'],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE',calibration_edges=[0,.5,1],ci_config=fixture['cluster_plan']),'example_box':check_box(fixture['box'],coverage=fixture['box_coverage'])}
with report.open('x') as f:json.dump(obj,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in obj.items() if not k.startswith('example')}))
raise SystemExit(0 if r.wasSuccessful() else 1)
