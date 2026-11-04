"""Record new offline development checks without overwriting earlier runs."""
from pathlib import Path
import argparse
import io
import json
import platform
import sys
import unittest
import test_p2

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--run',default='r001');args=p.parse_args()
if not args.run.isalnum():raise SystemExit('INVALID_RUN_ID')
out=HERE/'results';out.mkdir(exist_ok=True)
logpath,reportpath=out/(args.run+'.log'),out/(args.run+'.json')
if logpath.exists() or reportpath.exists():raise SystemExit('EXISTING_RUN_STOP')
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_p2))
env={'python':sys.version.split()[0],'os':platform.platform(),'scope':'OFFLINE_SYNTHETIC_ONLY'}
with logpath.open('x') as f:f.write('ENV '+json.dumps(env,sort_keys=True)+'\n'+stream.getvalue())
report={'status':'PASS_DEVELOPMENT_ONLY' if result.wasSuccessful() else 'FAIL','environment':env,'tests':result.testsRun,'synthetic_cases':len(test_p2.CASES),'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'real_source_bytes_or_records_received':0,'SYS04':'OPEN_MISSING_OLD_V004_BYTES_AND_D1_D3_DEFINITIONS','SYS17':'LANE2_HOLD','SYS23_live_independence':'UNVERIFIED','SYS24_independent_attestation':'UNVERIFIED','review':'PENDING_AFTER_CERTIFI','production_GO':False}
with reportpath.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report,sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() else 1)
