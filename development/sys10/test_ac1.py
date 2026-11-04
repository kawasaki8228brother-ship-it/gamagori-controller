from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from ac1 import measure, jst_time

HERE=Path(__file__).resolve().parent
CASES=json.loads((HERE/'fixtures.json').read_text())['cases']


class Fixtures(unittest.TestCase):
    pass


def make_test(case):
    def test(self):
        before=json.dumps(case['input'],sort_keys=True)
        r=measure(case['input'],include_details=True);e=case['expected']
        self.assertEqual(r['denominator'],e['denominator'])
        self.assertEqual(r['counts']['AUTO_CONFIRMED'],e['auto'])
        self.assertEqual(r['counts']['UNVERIFIED'],e['unknown'])
        self.assertEqual(r['comparison_95_percent']['formal_judgment'],e['formal'])
        self.assertFalse(r['production_GO'])
        self.assertEqual(before,json.dumps(case['input'],sort_keys=True))
    return test


for c in CASES:setattr(Fixtures,'test_'+c['id'],make_test(c))


class Contract(unittest.TestCase):
    def base(self,name='baseline_complete_100'):
        return deepcopy(next(c['input'] for c in CASES if c['id']==name))

    def test_empty_log_bounds_not_automatic_success(self):
        d=self.base('empty_logs_not_proof');r=measure(d)
        self.assertIsNone(r['auto_save_rate']['exact'])
        self.assertEqual(r['auto_save_rate']['lower_bound'],0)
        self.assertEqual(r['auto_save_rate']['upper_bound'],1)
        self.assertEqual(r['measurement_status'],'UNVERIFIED')

    def test_aggregate_output_omits_pair_identity(self):
        d=self.base();r=measure(d)
        self.assertNotIn('pair_details',r)
        self.assertNotIn('SYNTHETIC_R1',json.dumps(r))
        self.assertIn('pair_details',measure(d,include_details=True))

    def test_scope_must_bind_coverage_to_whole_denominator(self):
        d=self.base();d['lock_record_coverage']['race_ids']=[]
        r=measure(d);self.assertEqual(r['counts']['UNVERIFIED'],2)
        self.assertEqual(r['measurement_status'],'UNVERIFIED')

    def test_nonrace_zero_denominator_is_not_100_percent(self):
        d=self.base();d['official_schedule']['races']=[]
        for key in ['lock_record_coverage','intervention_coverage']:d[key]['race_ids']=[]
        r=measure(d);self.assertEqual(r['denominator'],0)
        self.assertIsNone(r['auto_save_rate']['exact'])
        self.assertEqual(r['measurement_status'],'UNVERIFIED')

    def test_missing_phase_cannot_formal_pass(self):
        d=self.base('formal_complete_pass');d.pop('phase')
        self.assertEqual(measure(d)['comparison_95_percent']['formal_judgment'],'UNVERIFIED')

    def test_same_day_adoption_order_cannot_be_inferred(self):
        d=self.base('formal_complete_pass')
        d['formal_cohort']['adoptions']['SYS-01']['adopted_at']='2026-11-16T00:00:00+09:00'
        r=measure(d);self.assertEqual(r['comparison_95_percent']['formal_judgment'],'UNVERIFIED')

    def test_all_95_boundary_arithmetic(self):
        d=self.base('formal_complete_pass');prototype=deepcopy(d)
        races=[];records=[];att=[]
        for i in range(10):
            original=prototype['official_schedule']['races'][i%2]
            rid='SYNTHETIC_BOUNDARY_'+str(i)
            races.append(dict(original,race_id=rid))
            for source in ['A','B']:
                records.append(dict(deepcopy(prototype['lock_records'][0]),race_id=rid,source=source))
                att.append(dict(deepcopy(prototype['pair_attestations'][0]),race_id=rid,source=source))
        d['official_schedule']['races']=races;d['lock_records']=records;d['pair_attestations']=att
        d['formal_cohort']['threshold_rule']['scope']='COMBINED'
        for key in ['lock_record_coverage','intervention_coverage']:d[key]['race_ids']=[r['race_id'] for r in races]
        d['lock_records'].pop()
        r=measure(d);self.assertEqual(r['denominator'],20);self.assertEqual(r['auto_save_rate']['exact'],.95)
        self.assertEqual(r['comparison_95_percent']['formal_judgment'],'PASS')
        d['formal_cohort']['threshold_rule']['scope']='EACH_SOURCE'
        r=measure(d);self.assertEqual(r['by_source']['A']['auto_save_rate']['exact'],1.0)
        self.assertEqual(r['by_source']['B']['auto_save_rate']['exact'],.9)
        self.assertEqual(r['comparison_95_percent']['formal_judgment'],'FAIL')
        d['formal_cohort']['threshold_rule']['scope']='COMBINED'
        d['lock_records'].pop();self.assertEqual(measure(d)['comparison_95_percent']['formal_judgment'],'FAIL')

    def test_attestation_contradiction_remains_open(self):
        r=measure(self.base('attestation_conflicts_with_replay'))
        self.assertEqual(r['counts']['INTERVENED'],1)
        self.assertEqual(r['intervention_evidence_conflicts'],1)
        self.assertEqual(r['measurement_status'],'UNVERIFIED')

    def test_naive_unknown_and_JST_conversion(self):
        self.assertIsNone(jst_time(None));self.assertIsNone(jst_time('bad'))
        self.assertIsNone(jst_time('2026-11-09T13:00:00'))
        self.assertIsNone(jst_time('2026-11-09T04:00:00-00:00'))
        self.assertIsNone(jst_time('2026-11-09T04:00:00+09:99'))
        self.assertIsNone(jst_time('2026-11-09T04:00:00.1234567Z'))
        self.assertEqual(jst_time('2026-11-09T04:00:00Z').hour,13)

    def test_cohort_attestations_cannot_be_reused_for_other_meets(self):
        for field in ['first_two_after_adoption_attestation','both_meets_complete']:
            d=self.base('formal_complete_pass')
            d['formal_cohort'][field]['cohort_meet_ids']=['SYNTHETIC_WRONG1','SYNTHETIC_WRONG2']
            self.assertEqual(measure(d)['comparison_95_percent']['formal_judgment'],'UNVERIFIED')
        d=self.base('formal_complete_pass')
        d['formal_cohort']['adoptions']['SYS-01']['evidence_ref']='SYNTHETIC_DIFFERENT_ADOPTION'
        self.assertEqual(measure(d)['comparison_95_percent']['formal_judgment'],'UNVERIFIED')

    def test_non_initial_intervention_does_not_disqualify_initial(self):
        r=measure(self.base('later_non_initial_action'))
        self.assertEqual(r['counts']['AUTO_CONFIRMED'],2)

    def test_source_C_does_not_enter_A_B_denominator(self):
        d=self.base();d['lock_records'].append(dict(deepcopy(d['lock_records'][0]),source='C'))
        r=measure(d);self.assertEqual(r['denominator'],2);self.assertEqual(r['counts']['AUTO_CONFIRMED'],2)
        self.assertEqual(r['outside_scope_evidence_rows'],1)

    def test_input_contract_rejects_invalid_shape(self):
        for d in [[],{'official_schedule':[]},{'official_schedule':{'races':None}},{'lock_records':[None]},{'lock_records':[{'race_id':[]}]},{'lock_records':[{}]}]:
            with self.assertRaises(ValueError):measure(d)

    def test_bool_null_zero_are_not_silently_interchangeable(self):
        for field,value in [('saved',None),('saved',0),('predeadline',None),('predeadline',0)]:
            d=self.base()
            if field=='saved':d['lock_records'][0][field]=value
            else:d['lock_records'][0]['existing_validity'][field]=value
            r=measure(d);self.assertEqual(r['counts']['UNVERIFIED'],1)
        d=self.base();d['lock_records'][0]['saved']=False
        self.assertEqual(measure(d)['counts']['NO_VALID_INITIAL_SAVE'],1)

    def test_CLI_private_local_input_and_bad_input_no_path_echo(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.json';p.write_text(json.dumps(self.base()))
            v=subprocess.run([sys.executable,'-B',str(HERE/'ac1.py'),str(p)],capture_output=True,text=True)
            self.assertEqual(v.returncode,0);self.assertEqual(json.loads(v.stdout)['denominator'],2)
            p.write_text('not json')
            v=subprocess.run([sys.executable,'-B',str(HERE/'ac1.py'),str(p)],capture_output=True,text=True)
            self.assertEqual(v.returncode,2);self.assertNotIn(temp,v.stdout+v.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
