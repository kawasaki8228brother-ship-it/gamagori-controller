"""Synthetic fixture oracles; not live data verification."""
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest

import audit_p1 as sut

HERE = Path(__file__).resolve().parent
FIXTURES = json.loads((HERE / 'fixtures.json').read_text())['cases']


def lookup(report, path):
    for part in path.split('.'):
        report = report[int(part)] if isinstance(report, list) else report[part]
    return report


class FixtureTests(unittest.TestCase):
    pass


def fixture_test(case):
    def test(self):
        before = deepcopy(case['input'])
        out = sut.dispatch(case['operation'], case['input'])
        for path, expected in case['expect'].items():
            self.assertEqual(lookup(out,path), expected)
            self.assertIs(type(lookup(out,path)), type(expected))
        self.assertEqual(case['input'], before)
        self.assertFalse(out['production_GO'])
    return test


for case in FIXTURES:
    setattr(FixtureTests,'test_'+case['id'],fixture_test(case))


class BoundaryTests(unittest.TestCase):
    def test_SYS08_all_json_and_nonfinite_states(self):
        values = [({},'MISSING'),({'x':None},'NULL'),({'x':''},'EMPTY_STRING'),({'x':0},'ZERO_NUMBER'),
                  ({'x':-0.0},'ZERO_NUMBER'),({'x':False},'FALSE_BOOLEAN'),({'x':True},'TRUE_BOOLEAN'),
                  ({'x':'0'},'NONEMPTY_STRING'),({'x':9},'OTHER_NUMBER'),({'x':[]},'ARRAY'),({'x':{}},'OBJECT'),
                  ({'x':float('nan')},'NON_FINITE_NUMBER'),({'x':float('inf')},'NON_FINITE_NUMBER'),({'x':object()},'UNSUPPORTED_TYPE')]
        for record, expected in values:
            with self.subTest(expected=expected):self.assertEqual(sut.field_kind(record,'x'), expected)

    def test_failed_read_not_zero_even_empty(self):
        self.assertIsNone(sut.event_scope([],'READ_FAILED')['production_total'])
        self.assertEqual(sut.event_scope([],'READ_OK_COMPLETE')['production_total'],0)

    def test_scope_does_not_coerce_is_test_zero(self):
        r=sut.event_scope([{'is_test':0,'race_id':'SYNTH_R1'}],'READ_OK_COMPLETE')
        self.assertEqual(r['observed_counts']['production_unknown'],1)
        self.assertIsNone(r['production_total'])

    def test_empty_link_whitespace_and_partial_counts(self):
        rows=[{'is_test':False},{'is_test':False,'race_id':''},{'is_test':False,'race_id':' '}]
        r=sut.event_scope(rows,'READ_OK_COMPLETE')
        self.assertEqual(r['production_total'],3)
        self.assertEqual(r['observed_counts']['unlinked_observed'],2)
        self.assertEqual(r['observed_counts']['link_unknown'],1)
        self.assertEqual(r['status'],'UNVERIFIED')

    def test_bad_read_status_not_guessed(self):
        with self.assertRaises(ValueError):sut.event_scope([],'UNKNOWN')

    def test_key_raw_missing_and_invalid_claim_do_not_pass(self):
        r=sut.key_duplicates([{'key':'SYNTH_K','claimed_hash':'not-hash'}])
        row=r['groups'][0]['rows'][0]
        self.assertEqual(row['raw_status'],'RAW_UNAVAILABLE')
        self.assertIsNone(row['claim_matches_calculated_raw'])

    def test_same_hash_claim_does_not_mask_raw_conflict(self):
        records=[{'key':'SYNTH_K','claimed_hash':'0'*64,'payload_raw_b64':base64.b64encode(b).decode()} for b in [b'A',b'B']]
        r=sut.key_duplicates(records)
        self.assertEqual(r['groups'][0]['classification'],'CONFLICT_DIFFERENT_RAW')
        self.assertTrue(all(x['claim_matches_calculated_raw'] is False for x in r['groups'][0]['rows']))

    def test_invalid_base64_type_and_key_unicode(self):
        r=sut.key_duplicates([{'key':'SYNTH_K','payload_raw_b64':123},{'key':'\ud800'}])
        self.assertEqual(r['groups'][0]['rows'][0]['raw_status'],'INVALID_RAW_ENCODING')
        self.assertEqual(r['invalid_key_rows'],1)

    def test_uppercase_hash_and_empty_raw(self):
        h=hashlib.sha256(b'').hexdigest()
        r=sut.key_duplicates([{'key':'SYNTH_K','payload_raw_b64':'','claimed_hash':h.upper()}])
        self.assertIs(r['groups'][0]['rows'][0]['claim_matches_calculated_raw'],True)

    def test_SYS07_reads_embedded_value_from_exact_payload(self):
        expected=hashlib.sha256(b'SYNTHETIC_SPEC').hexdigest()
        raw=json.dumps({'synthetic_spec_hash':'0'*64}).encode()
        record={'payload_raw_b64':base64.b64encode(raw).decode(),'column_hash':hashlib.sha256(raw).hexdigest(),'embedded_hash':expected}
        profile={'column_hash_kind':'RAW_BYTES','embedded_hash_kind':'FIXED_SPEC_REFERENCE','expected_spec_hash':expected,'embedded_hash_field':'synthetic_spec_hash'}
        out=sut.hash_spec_research(record,profile)
        self.assertIs(out['column_vs_raw'],True)
        self.assertIs(out['embedded_vs_fixed_spec'],False)
        self.assertEqual(out['LOCK_validity'],'NOT_EVALUATED')

    def test_SYS07_duplicate_or_nonobject_payload_is_unverified(self):
        expected='1'*64
        profile={'column_hash_kind':'RAW_BYTES','embedded_hash_kind':'FIXED_SPEC_REFERENCE','expected_spec_hash':expected,'embedded_hash_field':'x'}
        for raw,reason in [(b'{"x":1,"x":2}','RAW_JSON_INVALID_OR_AMBIGUOUS'),(b'[]','PAYLOAD_NOT_OBJECT'),(b'\xff','RAW_JSON_INVALID_OR_AMBIGUOUS')]:
            out=sut.hash_spec_research({'payload_raw_b64':base64.b64encode(raw).decode(),'column_hash':hashlib.sha256(raw).hexdigest()},profile)
            self.assertEqual(out['status'],'UNVERIFIED')
            self.assertEqual(out['reason'],reason)
            self.assertIs(out['column_vs_raw'],True)

    def test_receipt_failure_evidence_requires_literal_true(self):
        end={'run_id':'SYNTH_RUN','task_id':'SYNTH_TASK','phase':'END','run_status':'PARTIAL'}
        self.assertEqual(sut.receipt_stages([end],True)['presence'],'END_WITH_START_SAVE_FAILURE_EVIDENCE')
        self.assertEqual(sut.receipt_stages([end],'true')['presence'],'END_WITHOUT_START_UNVERIFIED')

    def test_missing_empty_scope_does_not_form_verified_pair(self):
        rows=[{'run_id':'','task_id':'SYNTH_TASK','phase':'START','run_status':'RUNNING'}, {'run_id':'','task_id':'SYNTH_TASK','phase':'END','run_status':'PASS'}]
        self.assertIn('RUN_OR_TASK_SCOPE_MISSING',sut.receipt_stages(rows)['warnings'])

    def test_daily_display_list_order_and_type_preservation(self):
        expected={'audit_status':'PARTIAL','scope':'SYNTHETIC','counts':{'sources':['A','B']},'receipts':{'START':'SYNTH_S'},'unverified':['SYNTHETIC_WARNING']}
        observed=deepcopy(expected);observed['counts']['sources'].reverse()
        self.assertEqual(sut.daily_display_fixture(expected,observed)['required_fields_changed'],['counts'])
        self.assertEqual(expected['counts']['sources'],['A','B'])

    def test_notification_claim_needs_its_own_evidence(self):
        r=sut.notification_axes({'status':'CONFIRMED','verified':True,'evidence_ref':''},None,{'status':'CONFIRMED','verified':True,'evidence_ref':'SYNTH_RECEIPT'})
        self.assertEqual(r['send']['status'],'UNVERIFIED')
        self.assertEqual(r['arrival']['status'],'UNVERIFIED')
        self.assertEqual(r['receipt']['status'],'CONFIRMED')
        self.assertEqual(r['notification_sends_executed'],0)

    def test_unknown_operation_rejected(self):
        with self.assertRaises(ValueError):sut.dispatch('OTHER',{})

    def test_CLI_local_only_valid_input(self):
        with tempfile.TemporaryDirectory(prefix='p1-synth-') as tmp:
            p=Path(tmp)/'synthetic.json';p.write_text('{"rows":[],"read_status":"READ_FAILED"}')
            r=subprocess.run([sys.executable,'-B',str(HERE/'audit_p1.py'),'SYS-05',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIsNone(json.loads(r.stdout)['production_total'])

    def test_CLI_ambiguous_or_nonfinite_JSON_rejected(self):
        for raw in ['{"rows":[],"rows":[]}', '{"x":NaN}', 'not-json']:
            with tempfile.TemporaryDirectory(prefix='p1-synth-') as tmp:
                p=Path(tmp)/'synthetic.json';p.write_text(raw)
                r=subprocess.run([sys.executable,'-B',str(HERE/'audit_p1.py'),'SYS-05',str(p)],capture_output=True,text=True)
                self.assertEqual(r.returncode,2)
                self.assertEqual(json.loads(r.stdout)['status'],'INPUT_ERROR')
                self.assertNotIn(raw,r.stdout)

    def test_CLI_oversized_input_refused_without_prefix_result(self):
        with tempfile.TemporaryDirectory(prefix='p1-synth-') as tmp:
            p=Path(tmp)/'synthetic.json';p.write_bytes(b' ' * 2_097_153)
            r=subprocess.run([sys.executable,'-B',str(HERE/'audit_p1.py'),'SYS-05',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2)
            self.assertEqual(json.loads(r.stdout)['status'],'INPUT_ERROR')


if __name__=='__main__':unittest.main(verbosity=2)
