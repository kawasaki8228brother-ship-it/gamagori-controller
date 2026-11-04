from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from b3_inventory import InputError, inventory
from make_fixture import make_fixture

class InventoryTests(unittest.TestCase):
    def setUp(self):self.data=make_fixture()
    def analyze(self):return inventory(self.data)
    def row(self,r,s='A',i=0):return [x for x in r['rows'] if x['source']==s][i]

    def test_base_four_meet_N_and_money(self):
        r=self.analyze();a=r['sources']['A']['cumulative'];b=r['sources']['B']['cumulative']
        self.assertEqual((a['valid_N'],a['hits'],a['monetary_N']),(4,2,4));self.assertEqual((b['valid_N'],b['hits'],b['monetary_N']),(4,1,4))
        self.assertEqual((a['stake_yen'],a['payout_yen'],a['refund_yen']),(2000,5200,0));self.assertEqual((b['stake_yen'],b['payout_yen']),(2000,800))
        self.assertEqual((a['gross_return_rate'],a['net_ROI']),(2.6,1.6));self.assertEqual((b['gross_return_rate'],b['net_ROI']),(.4,-.6))
    def test_input_not_mutated(self):
        before=deepcopy(self.data);self.analyze();self.assertEqual(before,self.data)
    def test_meet_month_cumulative(self):
        a=self.analyze()['sources']['A'];self.assertEqual((len(a['meets']),len(a['months'])),(4,4));self.assertEqual(sum(m['valid_N'] for m in a['meets'].values()),a['cumulative']['valid_N'])
    def test_A_duplicate_does_not_affect_B(self):
        rec=deepcopy(self.data['locks'][0]);rec['record_id']='SYNTH_DUP';self.data['locks'].append(rec);r=self.analyze()
        self.assertEqual((r['sources']['A']['cumulative']['valid_N'],r['sources']['B']['cumulative']['valid_N']),(3,4));self.assertIn('LOCK_DUPLICATE',self.row(r)['issues'])
    def test_missing_B_summary(self):
        self.data['summaries'].pop(1);r=self.analyze();self.assertEqual((r['sources']['A']['cumulative']['valid_N'],r['sources']['B']['cumulative']['valid_N']),(4,3));self.assertIn('SUMMARY_MISSING',self.row(r,'B')['issues'])
    def test_missing_result_affects_both(self):
        self.data['results'].pop(0);r=self.analyze();self.assertEqual((r['sources']['A']['cumulative']['valid_N'],r['sources']['B']['cumulative']['valid_N']),(3,3))
    def test_duplicate_result_no_latest_selection(self):
        rec=deepcopy(self.data['results'][0]);rec['record_id']='SYNTH_OTHER_RESULT';self.data['results'].append(rec)
        self.assertIn('RESULT_DUPLICATE',self.row(self.analyze())['issues'])
    def test_cross_source_summary_reference(self):
        self.data['summaries'][0]['lock_record_id']=self.data['locks'][1]['record_id'];self.assertIn('SUMMARY_LINK_MISMATCH',self.row(self.analyze())['issues'])
    def test_summary_hit_mismatch(self):
        self.data['summaries'][0]['hit']=False;self.assertIn('SUMMARY_HIT_MISMATCH_OR_UNKNOWN',self.row(self.analyze())['issues'])
    def test_late_never_relabels_existing_validity(self):
        self.data['locks'][0]['saved_at']='2026-07-11T14:00:00+09:00';r=self.row(self.analyze())
        self.assertFalse(r['valid_N']);self.assertEqual(r['existing_LOCK_validity'],'VALID');self.assertEqual(r['timing_observation'],'AT_OR_AFTER_DEADLINE');self.assertIn('UPSTREAM_TIME_CONTRADICTION',r['issues'])
    def test_upstream_deadline_unknown(self):
        self.data['locks'][0]['existing_deadline_verdict']='UNVERIFIED';self.assertIn('UPSTREAM_PREDEADLINE_NOT_VERIFIED',self.row(self.analyze())['issues'])
    def test_time_missing_unknown(self):
        self.data['locks'][0]['saved_at']=None;r=self.row(self.analyze());self.assertEqual(r['timing_observation'],'UNVERIFIED');self.assertIn('LOCK_TIME_UNVERIFIED',r['issues'])
    def test_five_tickets_nonunique(self):
        self.data['locks'][0]['tickets'][4]=self.data['locks'][0]['tickets'][0];self.assertIn('FIVE_UNIQUE_ORDERED_TICKETS_INVALID',self.row(self.analyze())['issues'])
    def test_hash_verification_unknown(self):
        self.data['locks'][0]['payload_hash_verified']=None;self.assertIn('LOCK_HASH_UNVERIFIED',self.row(self.analyze())['issues'])
    def test_money_unknown_separate_N(self):
        self.data['results'][0]['payout_yen_per_100']=None;r=self.analyze();row=self.row(r)
        self.assertTrue(row['valid_N']);self.assertFalse(row['monetary_N']);self.assertIsNone(row['payout_yen'])
        a=r['sources']['A']['cumulative'];self.assertEqual((a['valid_N'],a['monetary_N'],a['money_unverified_N']),(4,3,1));self.assertEqual(a['payout_yen'],4000)
    def test_no_money_data_is_not_zero_totals(self):
        for r in self.data['results']:r['payout_yen_per_100']=None
        a=self.analyze()['sources']['A']['cumulative'];self.assertIsNone(a['stake_yen']);self.assertIsNone(a['payout_yen']);self.assertIsNone(a['gross_return_rate'])
    def test_refunds_by_combination_not_same_indices(self):
        self.data['results'][2]['refunded_combinations']=[[1,2,3]];self.data['summaries'][4]['refund_yen']=100;r=self.analyze()
        self.assertEqual(self.row(r,i=2)['refund_yen'],100);self.assertEqual(self.row(r,'B',2)['refund_yen'],0);self.assertEqual(self.row(r,i=2)['gross_return_rate'],.2)
    def test_winning_refund_conflict(self):
        self.data['results'][0]['refunded_combinations']=[[1,2,3]];self.assertIn('WINNING_TICKET_REFUND_CONFLICT',self.row(self.analyze())['issues'])
    def test_summary_money_not_repaired(self):
        self.data['summaries'][0]['payout_yen']=1201;r=self.row(self.analyze());self.assertTrue(r['valid_N']);self.assertFalse(r['monetary_N']);self.assertIsNone(r['payout_yen']);self.assertIn('SUMMARY_MONETARY_MISMATCH',r['issues'])
    def test_boolean_money_not_zero(self):
        self.data['results'][0]['payout_yen_per_100']=False;self.assertFalse(self.row(self.analyze())['monetary_N'])
    def test_cancelled_is_exclusion_not_false_miss(self):
        self.data['results'][0]['status']='CANCELLED';r=self.row(self.analyze());self.assertFalse(r['valid_N']);self.assertIsNone(r['hit']);self.assertIn('RESULT_NOT_VERIFIED_FINAL',r['issues'])
    def test_no_causal_stage_from_tickets_alone(self):
        r=self.row(self.analyze(),i=1);self.assertFalse(r['hit']);self.assertEqual(r['miss_label'],'UNSPECIFIED_INSUFFICIENT_EVIDENCE')
    def test_evidence_gated_stage_labels(self):
        a={'verification':'VERIFIED','predeadline_verified':True,'coverage_complete':True,'first_candidates':[1]};self.data['locks'][2]['selection_audit']=a
        self.assertEqual(self.row(self.analyze(),i=1)['miss_label'],'FIRST_CANDIDATE_COVERAGE_MISS')
        a.update(first_candidates=[2],second_candidates_by_first={'2':[3]});self.assertEqual(self.row(self.analyze(),i=1)['miss_label'],'SECOND_CANDIDATE_COVERAGE_MISS')
        a.update(second_candidates_by_first={'2':[1]},third_candidates_by_pair={'2-1':[4]});self.assertEqual(self.row(self.analyze(),i=1)['miss_label'],'THIRD_CANDIDATE_COVERAGE_MISS')
        a['third_candidates_by_pair']={'2-1':[3]};self.assertEqual(self.row(self.analyze(),i=1)['miss_label'],'FIVE_TICKET_SELECTION_MISS')
    def test_bad_stage_evidence_is_unspecified(self):
        self.data['locks'][2]['selection_audit']={'verification':'VERIFIED','predeadline_verified':True,'coverage_complete':True,'first_candidates':[[]]}
        self.assertEqual(self.row(self.analyze(),i=1)['miss_label'],'UNSPECIFIED_INSUFFICIENT_EVIDENCE')
    def test_schema_time_identity_scope_errors(self):
        changes=[lambda d:d['meets'].pop(),lambda d:d['races'][0].update(race_id='bad'),lambda d:d['races'][0].update(date='2026-07-12'),lambda d:d['races'][0].update(deadline='2026-07-11T14:00:00'),lambda d:d['locks'][0].update(source='C'),lambda d:d['locks'][0].update(race_id='20990101_GAMAGORI_1R')]
        for change in changes:
            d=make_fixture();change(d)
            with self.assertRaises(InputError):inventory(d)
    def test_UTC_times_convert_to_JST(self):
        self.data['locks'][0]['observed_at']='2026-07-11T04:01:00+00:00';self.assertTrue(self.row(self.analyze())['valid_N'])
    def test_CLI_and_duplicate_JSON_key(self):
        module=Path(__file__).with_name('b3_inventory.py')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.json';p.write_text(json.dumps(self.data))
            r=subprocess.run([sys.executable,'-B',str(module),str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['sources']['A']['cumulative']['valid_N'],4)
            p.write_text('{"schema":1,"schema":2}');r=subprocess.run([sys.executable,'-B',str(module),str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['reason'],'DUPLICATE_INPUT_JSON_KEY')
    def test_failed_read_is_not_zero_records(self):
        self.data['read_coverage']['locks']['A']='READ_FAILED';self.data['locks']=[x for x in self.data['locks'] if x['source']=='B']
        r=self.analyze();row=self.row(r)
        self.assertIn('LOCK_READ_UNVERIFIED',row['issues']);self.assertIn('LOCK_NOT_OBSERVED_UNVERIFIED',row['issues']);self.assertNotIn('LOCK_MISSING',row['issues'])
        self.assertEqual(r['sources']['B']['cumulative']['valid_N'],4)
    def test_missing_coverage_does_not_assert_representative_valid_N(self):
        self.data.pop('read_coverage');r=self.analyze();self.assertEqual(r['sources']['A']['cumulative']['valid_N'],0);self.assertIsNone(r['sources']['A']['cumulative']['hit_rate'])
        self.assertIn('SCHEDULE_COVERAGE_UNVERIFIED',self.row(r)['issues'])
    def test_malformed_identifier_types_fail_closed(self):
        for field in ['race_id','meet_id']:
            d=make_fixture();d['races'][0][field]=[]
            with self.assertRaises(InputError):inventory(d)
        d=make_fixture();d['locks'][0]['race_id']=[]
        with self.assertRaises(InputError):inventory(d)
    def test_unknown_offset_and_precision_are_not_normalized(self):
        for stamp in ['2026-07-11T13:01:00-00:00','2026-07-11T13:01:00.1234567+09:00','2026-07-11 13:01:00+09:00']:
            d=make_fixture();d['locks'][0]['observed_at']=stamp;r=inventory(d)
            self.assertIn('LOCK_TIME_UNVERIFIED',self.row(r)['issues'])
        self.data['races'][0]['deadline']='2026-07-11T14:00:00-00:00'
        with self.assertRaises(InputError):self.analyze()

if __name__=='__main__':unittest.main(verbosity=2)
