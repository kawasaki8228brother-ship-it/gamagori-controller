"""Synthetic observation/negative tests, not validation of actual project data."""
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

import evidence_checks as sut

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE/'fixtures.json').read_text())['cases']


def subset(test, actual, expected):
    for key, value in expected.items():
        test.assertIn(key, actual)
        if isinstance(value, dict):
            subset(test, actual[key], value)
        else:
            test.assertEqual(actual[key], value, key)


class FixtureTests(unittest.TestCase):
    pass


def case_test(case):
    def test(self):
        request = deepcopy(case['request'])
        before = json.dumps(request, sort_keys=True)
        actual = sut.FUNCTIONS[case['mode']](request)
        subset(self, actual, case['expected_subset'])
        self.assertFalse(actual['production_GO'])
        self.assertEqual(json.dumps(request, sort_keys=True), before)
    return test


for case in CASES:
    setattr(FixtureTests, 'test_'+case['id'], case_test(case))


class InvariantTests(unittest.TestCase):
    def test_SYS04_open_only_and_toy_slice_not_old_source(self):
        status=json.loads((HERE/'SYS04_STATUS.json').read_text())
        self.assertFalse(status['old_v004_exact_bytes_received'])
        self.assertFalse(status['D1_D2_D3_definitions_received'])
        self.assertFalse(status['implementation_changed'])
        self.assertEqual(status['state'],'OPEN')
        toy=status['toy_fixture']
        before,after=(base64.b64decode(toy[k],validate=True) for k in ['old_b64','candidate_b64'])
        self.assertEqual(before[:toy['prefix_bytes']],after[:toy['prefix_bytes']])
        self.assertEqual(before[-toy['suffix_bytes']:],after[-toy['suffix_bytes']:])
        self.assertNotEqual(before,after)

    def test_empty_raw_is_not_absent(self):
        empty=hashlib.sha256(b'').hexdigest()
        r=sut.archive_check({'raw_b64':'','expected_raw_sha256':empty,'readback_b64':'','save_receipt':{'acknowledged':True,'raw_sha256':empty}})
        self.assertEqual(r['raw_expected'],'MATCH')
        self.assertEqual(r['readback_bytes'],'MATCH')
        self.assertEqual(r['receipt_and_retrieval_authenticity'],'UNVERIFIED')

    def test_missing_raw_never_verified_from_claims(self):
        h=hashlib.sha256(b'claim').hexdigest()
        r=sut.archive_check({'expected_raw_sha256':h,'save_receipt':{'acknowledged':True,'raw_sha256':h}})
        self.assertEqual(r['local_state'],'UNVERIFIED')
        self.assertEqual(r['raw_expected'],'UNVERIFIED')

    def test_unreferenced_duplicate_history_also_flagged(self):
        r=deepcopy(next(c['request'] for c in CASES if c['id']=='pointer_consistent_claims'))
        row=dict(r['decisions'][0],id='SYN_OTHER')
        r['decisions'] += [deepcopy(row),deepcopy(row)]
        result=sut.pointer_check(r)
        self.assertEqual(result['local_state'],'INCONSISTENT')
        self.assertIn('DECISION_HISTORY_DUPLICATE_ID',result['history_issues'])

    def test_missing_history_ID_flagged(self):
        r=deepcopy(next(c['request'] for c in CASES if c['id']=='pointer_consistent_claims'))
        r['decisions'].append({})
        self.assertEqual(sut.pointer_check(r)['local_state'],'INCONSISTENT')

    def test_neutral_health_may_read_both_but_cannot_relay_B_to_A(self):
        r=deepcopy(next(c['request'] for c in CASES if c['id']=='cross_via_neutral_auditor'))
        result=sut.boundary_check(r)
        witness=[v['declared_path'] for v in result['violations'] if v['from_owner']=='B' and v['to_owner']=='A']
        self.assertIn(['B_data','Health','A_pred'],witness)
        self.assertIn('UNVERIFIED',result['live_A_B_independence'])

    def test_false_external_verified_flag_cannot_establish_authenticity(self):
        c=next(c for c in CASES if c['id']=='all_claims_rewritten_not_independent')
        result=sut.immutable_evidence(c['request'])
        self.assertEqual(result['self_hash'],'MATCH')
        self.assertEqual(result['external_hash_claim'],'MATCH')
        self.assertTrue(result['claimed_verified_flag_not_trusted'])
        self.assertEqual(result['independent_attestation'],'UNVERIFIED_NO_EXTERNAL_VERIFIER_OR_TRUST_ANCHOR')

    def test_SYS17_never_automatically_leaves_lane2(self):
        for c in CASES:
            if c['mode']=='sys16_17':
                r=sut.parser_observations(c['request'])
                self.assertEqual(r['input_change_lane'],'LANE2_HOLD')
                self.assertEqual(r['LOCK_validity'],'NOT_EVALUATED')
                self.assertEqual(r['official_fetch_success'],'NOT_ASSIGNED')

    def test_invalid_requests_do_not_silently_pass(self):
        bad=[
            ('sys14',{'raw_b64':'%%%'}),('sys14',{'save_receipt':9}),('sys14',{'save_receipt':{'acknowledged':1}}),
            ('sys15',{}),('sys15',{'canonical':{},'pointer':{},'decisions':[None]}),
            ('sys16_17',{'http_status':True}),('sys16_17',{'scratch_count':False}),
            ('sys16_17',{'expected_date':'20990101'}),('sys16_17',{'network_error':'invented'}),
            ('sys16_17',{'official_calendar':'MAYBE'}),('sys16_17',{'input_format':'invented'}),
            ('sys16_17',{'parser_error':'invented'}),('sys16_17',{'tracking_fallback':'invented'}),
            ('sys23',{'nodes':[],'edges':[{'from':'missing','to':'missing'}]}),
            ('sys23',{'nodes':[{'id':'X','owner':'A'},{'id':'X','owner':'B'}],'edges':[]}),
            ('sys23',{'nodes':[{'id':'X','owner':[]}],'edges':[]}),
            ('sys23',{'nodes':[],'edges':[{'from':[],'to':[]}]}),
            ('sys23',{'nodes':[{'id':str(i),'owner':'PUBLIC'} for i in range(257)],'edges':[]}),
            ('sys24',{'external_record':False}),
        ]
        for mode,request in bad:
            with self.subTest(mode=mode,request=request):
                with self.assertRaises(ValueError):sut.FUNCTIONS[mode](request)

    def test_cli_returns_ascii_metadata_without_external_calls(self):
        c=next(c for c in CASES if c['id']=='archive_all_local_matches')
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            f=Path(d)/'synthetic.json';f.write_text(json.dumps(c['request']))
            p=subprocess.run([sys.executable,'-B',str(HERE/'evidence_checks.py'),'sys14',str(f)],capture_output=True,check=True)
        r=json.loads(p.stdout)
        self.assertEqual(r['local_state'],'LOCALLY_CONSISTENT')
        self.assertFalse(r['production_GO'])

    def test_cli_rejects_duplicate_nonfinite_and_invalid_UTF8(self):
        for raw in [b'{"raw_b64":"","raw_b64":""}',b'{"x":NaN}',b'\xff',b'[]']:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory(dir=HERE) as d:
                f=Path(d)/'bad.json';f.write_bytes(raw)
                p=subprocess.run([sys.executable,'-B',str(HERE/'evidence_checks.py'),'sys14',str(f)],capture_output=True)
                self.assertEqual(p.returncode,2)
                self.assertEqual(json.loads(p.stdout)['state'],'INPUT_ERROR')
                self.assertEqual(p.stderr,b'')


if __name__=='__main__':unittest.main(verbosity=2)
