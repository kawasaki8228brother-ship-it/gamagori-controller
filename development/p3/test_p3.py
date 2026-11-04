from copy import deepcopy
from itertools import permutations
from pathlib import Path
import json
import math
import unittest

from evaluator import evaluate_pairs,cluster_interval
from box_arithmetic import check_box
from lifecycle import new_ledger,record_transition,validate_ledger,REQUIRED,STAGES

F=json.loads((Path(__file__).resolve().parent/'fixtures.json').read_text())

class ResearchTests(unittest.TestCase):
 def test_hits_refunds_ROI_and_scores(self):
  before=deepcopy(F['pairs']);r=evaluate_pairs(before,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE',calibration_edges=[0,.5,1],ci_config=F['cluster_plan'])
  self.assertEqual(before,F['pairs']);self.assertEqual(r['complete_pair_N'],2)
  self.assertEqual(r['old_hit_rate'],0);self.assertEqual(r['candidate_hit_rate'],1);self.assertEqual(r['paired_improvement'],1)
  self.assertAlmostEqual(r['proper_scores']['old']['log_loss'],math.log(6))
  self.assertAlmostEqual(r['proper_scores']['candidate']['brier_multiclass_sum'],5/6)
  self.assertEqual(r['money']['candidate']['gross_return_rate'],'2.2');self.assertEqual(r['money']['candidate']['net_ROI'],'1.2')
  self.assertEqual(r['paired_market_comparison']['N'],2)
  self.assertAlmostEqual(r['paired_market_comparison']['candidate_log_loss_minus_market'],0)
  self.assertEqual(r['cluster_CI']['status'],'UNVERIFIED_SMALL_CLUSTER_COUNT')
 def test_same_race_and_source_required(self):
  for field,value in [('race_id','DIFFERENT'),('lane','A')]:
   rows=deepcopy(F['pairs']);rows[0]['candidate'][field]=value
   self.assertEqual(evaluate_pairs(rows,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['complete_pair_N'],1)
  rows=deepcopy(F['pairs']);rows[0]['comparator_source']='B'
  self.assertEqual(evaluate_pairs(rows,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['complete_pair_N'],1)
 def test_bound_source_candidate_and_day_required(self):
  for prediction,field,value in [('old','source','B'),('candidate','comparator_source','B'),('candidate','candidate_id','OTHER_CANDIDATE'),('old','target_date','2099-01-02'),('candidate','target_date',None)]:
   rows=deepcopy(F['pairs']);rows[0][prediction][field]=value
   r=evaluate_pairs(rows,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')
   self.assertEqual(r['complete_pair_N'],1);self.assertEqual(r['excluded_pair_count'],1)
  for field,value in [('race_id_profile',None),('day','2099-01-03')]:
   rows=deepcopy(F['pairs']);rows[0][field]=value
   self.assertEqual(evaluate_pairs(rows,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['complete_pair_N'],1)
 def test_duplicate_pairs_all_excluded(self):
  rows=[deepcopy(F['pairs'][0]),deepcopy(F['pairs'][0])]
  r=evaluate_pairs(rows,comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE');self.assertEqual(r['complete_pair_N'],0);self.assertIsNone(r['candidate_hit_rate'])
 def test_invalid_and_late_not_repaired(self):
  for change in ['late','duplicate_ticket','missing_result','bad_date']:
   row=deepcopy(F['pairs'][0])
   if change=='late':row['candidate']['existing_predeadline_verdict']='UNVERIFIED'
   if change=='duplicate_ticket':row['candidate']['tickets'][1]=row['candidate']['tickets'][0]
   if change=='missing_result':row['result']=None
   if change=='bad_date':row['day']='not-a-date'
   self.assertEqual(evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['complete_pair_N'],0)
 def test_missing_money_never_zero(self):
  row=deepcopy(F['pairs'][0]);row['candidate']['money']['refund_yen']=None
  r=evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE');self.assertEqual(r['complete_pair_N'],1);self.assertEqual(r['money_complete_pair_N'],0)
  self.assertIsNone(r['money']['old']['stake_yen'])
 def test_full_120_probability_domain(self):
  row=deepcopy(F['pairs'][0]);domain=['-'.join(map(str,p)) for p in permutations(range(1,7),3)]
  row['active_boats']=list(range(1,7));row['old']['probabilities']={k:1/120 for k in domain};row['candidate']['probabilities']={k:1/120 for k in domain};row['market_odds']={k:120 for k in domain}
  r=evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE');self.assertEqual(r['proper_score_pair_N'],1);self.assertEqual(r['market_N'],1)
  row['candidate']['probabilities'].pop(domain[-1]);r=evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')
  self.assertEqual(r['proper_score_pair_N'],0);self.assertEqual(r['complete_pair_N'],1);self.assertEqual(r['paired_market_comparison']['N'],0)
 def test_zero_nan_and_non_normalized_probabilities(self):
  for value in [0,float('nan'),float('inf'),-1,True,.9]:
   row=deepcopy(F['pairs'][0]);row['candidate']['probabilities']['1-2-3']=value
   self.assertEqual(evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['proper_score_pair_N'],0)
 def test_market_five_odds_not_full_market(self):
  row=deepcopy(F['pairs'][0]);row['market_odds'].pop('3-2-1')
  self.assertEqual(evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['market_N'],0)
  row=deepcopy(F['pairs'][0]);row['market_snapshot_verdict']='UNVERIFIED'
  self.assertEqual(evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['market_N'],0)
 def test_cluster_configuration_and_reproducibility(self):
  self.assertIsNone(cluster_interval({'a':[1]},None)['interval'])
  config=deepcopy(F['cluster_plan']);config['min_cluster_days']=3
  data={'a':[1,0],'b':[-1],'c':[0]}
  a=cluster_interval(data,config);b=cluster_interval(data,config)
  self.assertEqual(a,b);self.assertIn('EXPLORATORY',a['status']);self.assertEqual(a['formal_superiority'],'NOT_EVALUATED')
  config['exchangeable_days_assumption']=False;self.assertIsNone(cluster_interval(data,config)['interval'])
 def test_missing_calibration_edges_and_invalid_config(self):
  self.assertEqual(evaluate_pairs(F['pairs'],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['calibration']['candidate']['status'],'UNVERIFIED_BINS_NOT_PREREGISTERED')
  with self.assertRaises(ValueError):evaluate_pairs(F['pairs'],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE',calibration_edges=[0,.5,.5,1])
 def test_extreme_numeric_and_empty_cluster_rejected(self):
  row=deepcopy(F['pairs'][0]);row['candidate']['probabilities']['1-2-3']=10**1000
  self.assertEqual(evaluate_pairs([row],comparator_source='A',candidate_id='SYNTHETIC_CANDIDATE')['proper_score_pair_N'],0)
  config=deepcopy(F['cluster_plan']);config['min_cluster_days']=2
  with self.assertRaises(ValueError):cluster_interval({'a':[],'b':[]},config)

class BoxTests(unittest.TestCase):
 def test_scope_and_snapshot_arithmetic(self):
  source=deepcopy(F['box']);r=check_box(source,coverage=F['box_coverage']);self.assertEqual(source,F['box'])
  self.assertEqual(len(r['groups']),3);final=next(g for g in r['groups'] if g['phase']=='FINAL')
  self.assertTrue(final['claimed_cumulative_matches_flows']);self.assertEqual(final['net_ROI'],'1.2')
  self.assertFalse(r['existing_cumulative_rewritten'])
 def test_unknown_coverage_and_money_do_not_zero_fill(self):
  r=check_box(F['box']);self.assertTrue(all(g['complete_totals'] is None for g in r['groups']))
  entries=deepcopy(F['box']);entries[2]['refund_yen']=None
  g=next(g for g in check_box(entries,coverage=F['box_coverage'])['groups'] if g['phase']=='FINAL')
  self.assertIsNone(g['complete_totals']);self.assertIsNone(g['claimed_cumulative_matches_flows'])
 def test_mismatched_snapshot_not_rewritten(self):
  entries=deepcopy(F['box']);entries[3]['payout_yen']=99
  g=next(g for g in check_box(entries,coverage=F['box_coverage'])['groups'] if g['phase']=='FINAL')
  self.assertFalse(g['claimed_cumulative_matches_flows']);self.assertEqual(entries[3]['payout_yen'],99)
 def test_unconfirmed_final_and_duplicate_ids(self):
  entries=deepcopy(F['box']);entries[2]['confirmed']=False
  self.assertIsNone(next(g for g in check_box(entries,coverage=F['box_coverage'])['groups'] if g['phase']=='FINAL')['complete_totals'])
  entries=[deepcopy(F['box'][0]),deepcopy(F['box'][0])]
  self.assertEqual(check_box(entries,coverage=F['box_coverage'])['groups'][0]['status'],'UNVERIFIED')

REGISTRY={'DEVELOPER':['DEV'],'CLAUDE':['INDEPENDENT_CLAUDE'],'ANDY':['ANDY'],'OPERATOR':['OP'],'VERIFIER':['VERIFIER']}
def evidences(ledger,target):
 return [{'evidence_id':'SYNTHETIC_'+target+'_'+kind,'kind':kind,'issuer':REGISTRY[role][0],'case_id':ledger['case_id'],'subject_commit':ledger['subject_commit'],'sha256':'b'*64,'source_reference':'SYNTHETIC_SOURCE','independent_verification_reference':'SYNTHETIC_EXTERNAL_ATTESTATION','external_verification_status':'EXTERNALLY_VERIFIED','outcome':'PASS','observed_at':'2099-01-01T00:00:00+09:00',**({'authorized_action':'APPLY_EXACT_SUBJECT_COMMIT'} if kind=='ANDY_INDIVIDUAL_GO' else {})} for kind,role in REQUIRED[target]]
def advance(ledger,target,records=None,**kwargs):
 return record_transition(ledger,target,actor='SYNTHETIC_CLERK',recorded_at='2099-01-01T01:00:00+09:00',evidence=evidences(ledger,target) if records is None else records,trust_registry=REGISTRY,manual_action=kwargs.get('manual_action','RECORD_ATTESTATION'))

class LifecycleTests(unittest.TestCase):
 def test_explicit_separate_stages(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV');original=deepcopy(ledger)
  for stage in STAGES[1:]:
   new=advance(ledger,stage);self.assertEqual(new['stage'],stage);self.assertEqual(len(new['history']),len(ledger['history'])+1);ledger=new
  self.assertEqual(original['history'],[]);self.assertFalse(ledger['production_actions_performed'])
  self.assertIn('UNVERIFIED',ledger['real_world_status_authenticity'])
 def test_no_skip_or_automatic_transition(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV')
  with self.assertRaises(ValueError):advance(ledger,'GO_APPROVED')
  with self.assertRaises(ValueError):advance(ledger,'DEV_READY',manual_action='AUTO_PROMOTE')
 def test_missing_false_selfclaim_or_identity_evidence(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV')
  with self.assertRaises(ValueError):advance(ledger,'DEV_READY',[])
  for field,value in [('external_verification_status',True),('outcome','FAIL'),('case_id','OTHER'),('subject_commit','c'*40),('source_reference',''),('independent_verification_reference',''),('issuer','UNTRUSTED'),('observed_at','2099-01-02T00:00:00+09:00')]:
   r=evidences(ledger,'DEV_READY');r[0][field]=value
   with self.assertRaises(ValueError):advance(ledger,'DEV_READY',r)
 def test_review_independence_and_GO_scope(self):
  ledger=advance(new_ledger('SYNTHETIC_CASE','a'*40,'DEV'),'DEV_READY')
  r=evidences(ledger,'CLAUDE_REVIEWED');r[0]['issuer']='DEV'
  with self.assertRaises(ValueError):advance(ledger,'CLAUDE_REVIEWED',r)
  ledger=advance(ledger,'CLAUDE_REVIEWED');r=evidences(ledger,'GO_APPROVED');r[0]['authorized_action']='ANYTHING'
  with self.assertRaises(ValueError):advance(ledger,'GO_APPROVED',r)
 def test_history_forgery_or_stage_without_history(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV');ledger['stage']='APPLIED'
  with self.assertRaises(ValueError):validate_ledger(ledger,REGISTRY)
  ledger=advance(new_ledger('SYNTHETIC_CASE','a'*40,'DEV'),'DEV_READY');ledger['history'][0]['previous_event_id']='FORGED'
  with self.assertRaises(ValueError):validate_ledger(ledger,REGISTRY)
  with self.assertRaises(ValueError):validate_ledger(new_ledger('SYNTHETIC_CASE','a'*40,'DEV'),{})
 def test_registry_self_reference_reuse_and_stage_time(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV')
  with self.assertRaises(ValueError):validate_ledger(ledger,{'DEVELOPER':'DEV'})
  r=evidences(ledger,'DEV_READY');r[0]['independent_verification_reference']=r[0]['source_reference']
  with self.assertRaises(ValueError):advance(ledger,'DEV_READY',r)
  ledger=advance(ledger,'DEV_READY');r=evidences(ledger,'CLAUDE_REVIEWED');r[0]['evidence_id']=ledger['history'][0]['evidence'][0]['evidence_id']
  with self.assertRaises(ValueError):advance(ledger,'CLAUDE_REVIEWED',r)
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV');r=evidences(ledger,'DEV_READY');r[0]['observed_at']='2099-01-01T01:00:00+09:00';ledger=advance(ledger,'DEV_READY',r)
  with self.assertRaises(ValueError):advance(ledger,'CLAUDE_REVIEWED')
 def test_unknown_offset_precision_and_approval_observation_order(self):
  ledger=new_ledger('SYNTHETIC_CASE','a'*40,'DEV')
  for stamp in ['2099-01-01T00:00:00-00:00','2099-01-01T00:00:00.1234567+09:00','2099-01-01 00:00:00+09:00','2099-01-01T00:00:00']:
   r=evidences(ledger,'DEV_READY');r[0]['observed_at']=stamp
   with self.assertRaises(ValueError):advance(ledger,'DEV_READY',r)
  ledger=advance(ledger,'DEV_READY');r=evidences(ledger,'CLAUDE_REVIEWED');r[0]['observed_at']='2099-01-01T00:01:00+09:00';ledger=advance(ledger,'CLAUDE_REVIEWED',r)
  r=evidences(ledger,'GO_APPROVED');r[0]['observed_at']='2099-01-01T00:02:00+09:00';ledger=advance(ledger,'GO_APPROVED',r)
  r=evidences(ledger,'APPLIED');r[0]['observed_at']='2099-01-01T00:01:30+09:00'
  with self.assertRaises(ValueError):advance(ledger,'APPLIED',r)
  r[0]['observed_at']='2099-01-01T00:03:00+09:00';result=advance(ledger,'APPLIED',r)
  self.assertEqual(result['stage'],'APPLIED');self.assertFalse(result['production_actions_performed'])

if __name__=='__main__':unittest.main(verbosity=2)
