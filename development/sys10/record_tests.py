"""Record synthetic local test results; no external connections or writers."""
from pathlib import Path
import io
import json
import platform
import sys
import unittest

from ac1 import measure
import test_ac1

HERE=Path(__file__).resolve().parent
stream=io.StringIO()
suite=unittest.defaultTestLoader.loadTestsFromModule(test_ac1)
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
environment={'python':sys.version.split()[0],'os':platform.platform(),'scope':'OFFLINE_SYNTHETIC_ONLY_NOT_REAL_MEASUREMENT'}
log='ENV '+json.dumps(environment,sort_keys=True)+'\n'+stream.getvalue()
(HERE/'tests.raw.log').write_text(log)
rows=[]
table=['classification\tcase\tphase\tdenominator\tauto_confirmed\tunknown\tlower_bound\tupper_bound\texact_rate\tcomparison95_descriptive\tformal_judgment']
for c in test_ac1.CASES:
 r=measure(c['input'])
 rows.append({'id':c['id'],'classification':'SYNTHETIC_ONLY','result':r})
 table.append('\t'.join(map(str,['SYNTHETIC_ONLY',c['id'],r['phase'],r['denominator'],r['counts']['AUTO_CONFIRMED'],r['counts']['UNVERIFIED'],r['auto_save_rate']['lower_bound'],r['auto_save_rate']['upper_bound'],r['auto_save_rate']['exact'],r['comparison_95_percent']['descriptive_only'],r['comparison_95_percent']['formal_judgment']])))
(HERE/'MEASUREMENT-EXAMPLES.tsv').write_text('\n'.join(table)+'\n')
report={'module':'SYS-10','development_state':'DEV_READY' if result.wasSuccessful() else 'OPEN','environment':environment,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'synthetic_fixture_cases':len(test_ac1.CASES),'real_data_received':False,'real_measurement':'NOT_PERFORMED_HQ14_PRIVATE_INPUT_REQUIRED','Claude_review':'PENDING_AFTER_CERTIFI','production_application':'NOT_AUTHORIZED','production_GO':False,'cases':rows}
(HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
raise SystemExit(0 if result.wasSuccessful() else 1)
