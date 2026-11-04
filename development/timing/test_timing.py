from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import timing_audit as sut

HERE=Path(__file__).resolve().parent
CASES=json.loads((HERE/'fixtures.json').read_text())['cases']


def lookup(value,path):
    for part in path.split('.'):
        value=value[part]
    return value


class FixtureTests(unittest.TestCase):
    pass


def fixture_test(case):
    def test(self):
        original=deepcopy(case['input'])
        result=sut.audit(case['input'])
        for path,expected in case['expected'].items():
            self.assertEqual(lookup(result,path),expected,path)
        self.assertEqual(case['input'],original)
        self.assertEqual(result['LOCK_validity'],'NOT_EVALUATED')
        self.assertFalse(result['production_GO'])
        self.assertFalse(result['scheduler']['origin_proven'])
    return test


for case in CASES:
    setattr(FixtureTests,'test_'+case['id'],fixture_test(case))


class ContractTests(unittest.TestCase):
    def test_all_time_classifications_covered(self):
        labels=set()
        for case in CASES:
            labels.update(f['status'] for f in sut.audit(case['input'])['times'].values())
        self.assertEqual(labels,set(sut.TIME_STATUSES))

    def test_each_of_six_fields_stays_independent(self):
        base=deepcopy(CASES[0]['input'])
        baseline=sut.audit(base)
        for field in sut.FIELDS:
            changed=deepcopy(base);changed.pop(field)
            result=sut.audit(changed)
            self.assertEqual(result['times'][field]['status'],'MISSING')
            self.assertIsNone(result['times'][field]['jst'])
            for other in sut.FIELDS:
                if other!=field:self.assertEqual(result['times'][other],baseline['times'][other])

    def test_no_clock_source_failure_substitution(self):
        record=deepcopy(CASES[0]['input'])
        record['clock_failures']=['observed_at']
        report=sut.audit(record)
        self.assertEqual(report['times']['observed_at']['status'],'CONFLICT_CLOCK_FAILURE_WITH_VALUE')
        self.assertEqual(report['intervals']['started_to_observed']['status'],'UNVERIFIED')
        self.assertEqual(report['times']['saved_at']['status'],'VALID')

    def test_clock_failure_configuration_rejects_invalid_data(self):
        for bad in ['started_at',None,[9],['unknown_field']]:
            with self.assertRaisesRegex(ValueError,'^CLOCK_FAILURE_FIELDS_INVALID$'):
                sut.audit({'clock_failures':bad})
        for bad in [[],None,'text',1]:
            with self.assertRaises(TypeError):sut.audit(bad)

    def test_time_type_and_syntax_boundaries(self):
        for raw in [0,False,{},[],1.0]:
            self.assertEqual(sut.parse_time(raw)[0]['status'],'INVALID_TYPE')
        for raw in ['2026-02-30T13:00:00','2026-02-30T13:00:00Z','2026-11-09 13:00:00+09:00','2026-11-09T13:00:00+24:00','2026-11-09T13:00:60Z','2026-11-09T13:00:00z','9999-12-31T23:59:59-23:59','0001-01-01T00:00:00+23:59']:
            self.assertEqual(sut.parse_time(raw)[0]['status'],'MALFORMED',raw)

    def test_exact_intervals_do_not_use_float_arithmetic(self):
        a=datetime(1,1,1,tzinfo=timezone.utc);b=datetime(9999,12,31,23,59,59,999999,tzinfo=timezone.utc)
        r=sut.interval(a,b)
        self.assertEqual(r['microseconds'],315537897599999999)
        self.assertEqual(r['seconds'],'315537897599.999999')
        self.assertEqual(sut.interval(b,a)['seconds'],'-315537897599.999999')
        self.assertEqual(sut.interval(None,a)['status'],'UNVERIFIED')

    def test_policy_invalid_numbers_no_automatic_default(self):
        for n in [True,-1,float('nan'),float('inf'),'10',None]:
            record=deepcopy(CASES[0]['input']);record['tolerance_policy']={'status':'PROPOSED','early_seconds':n,'late_seconds':1}
            report=sut.audit(record)
            self.assertEqual(report['tolerance_policy']['status'],'INVALID_OR_UNADOPTED_POLICY')
            self.assertIsNone(report['start_comparison']['outside_proposed_tolerance'])
        record=deepcopy(CASES[0]['input']);record['tolerance_policy']={'status':'PROPOSED','early_seconds':10**400,'late_seconds':10**400}
        self.assertFalse(sut.audit(record)['start_comparison']['outside_proposed_tolerance'])
        record['tolerance_policy']['early_seconds']=10**10000
        self.assertEqual(sut.audit(record)['tolerance_policy']['status'],'INVALID_OR_UNADOPTED_POLICY')

    def test_run_identity_selfclaim_never_authenticity(self):
        record=deepcopy(CASES[0]['input']);record['run_id']='SYNTHETIC_ID_NOT_ECHOED';record['execution_origin_claim']={'unexpected':'secret'}
        report=sut.audit(record)
        self.assertEqual(report['scheduler']['origin_claim'],'UNRECOGNIZED_CLAIM')
        self.assertNotIn('SYNTHETIC_ID_NOT_ECHOED',json.dumps(report))
        self.assertEqual(report['scheduler']['evidence_authenticity'],'NOT_PROVEN_OFFLINE')

    def test_CLI_valid_and_rejected_inputs_no_secret_echo(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            p=Path(directory)/'input.json'
            p.write_text(json.dumps(CASES[0]['input']))
            r=subprocess.run([sys.executable,'-B',str(HERE/'timing_audit.py'),str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['start_comparison']['classification'],'AT_SCHEDULE')
            for data in [b'{"started_at":1,"started_at":2}',b'{"x":NaN}',b'not-json',b'\xff',b'x'*1_048_577]:
                p.write_bytes(data)
                r=subprocess.run([sys.executable,'-B',str(HERE/'timing_audit.py'),str(p)],capture_output=True,text=True)
                self.assertEqual(r.returncode,2)
                self.assertEqual(json.loads(r.stdout)['status'],'INPUT_UNVERIFIED')
            r=subprocess.run([sys.executable,'-B',str(HERE/'timing_audit.py'),'-'],input=json.dumps([CASES[0]['input']]),capture_output=True,text=True)
            self.assertEqual(r.returncode,0)
            self.assertIsInstance(json.loads(r.stdout),list)


if __name__=='__main__':unittest.main(verbosity=2)
