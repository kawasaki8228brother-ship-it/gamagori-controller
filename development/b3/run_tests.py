"""Run local synthetic tests and record actual results. No external services."""
from pathlib import Path
import io,json,platform,sys,unittest
from b3_inventory import inventory
from make_fixture import make_fixture
import test_b3

HERE=Path(__file__).resolve().parent
out=HERE/'results';out.mkdir(exist_ok=True)
logpath=out/'tests.log';resultpath=out/'results.json'
if logpath.exists() or resultpath.exists():raise SystemExit('STOP_EXISTING_RESULT_NO_OVERWRITE')
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_b3))
env={'python':sys.version.split()[0],'os':platform.platform(),'scope':'OFFLINE_SYNTHETIC_ONLY'}
with logpath.open('x') as f:f.write('ENV '+json.dumps(env,sort_keys=True)+'\n'+stream.getvalue())
report={'status':'PASS_DEVELOPMENT_ONLY' if result.wasSuccessful() else 'FAIL','unittest_tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'environment':env,'real_records_received':0,'live_schema_compatibility':'UNVERIFIED','independent_review':'PENDING_AFTER_CERTIFI','production_GO':False,'example_synthetic_inventory':inventory(make_fixture())}
with resultpath.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in report.items() if k!='example_synthetic_inventory'}))
raise SystemExit(0 if result.wasSuccessful() else 1)
