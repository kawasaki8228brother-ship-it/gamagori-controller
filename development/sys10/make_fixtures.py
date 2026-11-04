from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent


def baseline():
    races = [{"race_id":"SYNTHETIC_R1", "meet_id":"SYNTHETIC_BASELINE_MEET", "target_date":"2026-11-09"}]
    proof = {"status":"VERIFIED", "evidence_ref":"SYNTHETIC_EXTERNAL_PROOF", "complete":True, "race_ids":["SYNTHETIC_R1"], "sources":["A","B"]}
    return {"classification":"SYNTHETIC_ONLY", "phase":"BASELINE", "official_schedule":{"status":"VERIFIED","evidence_ref":"SYNTHETIC_OFFICIAL_SCHEDULE","complete":True,"races":races},
            "lock_record_coverage":deepcopy(proof), "intervention_coverage":deepcopy(proof),
            "lock_records":[{"race_id":"SYNTHETIC_R1","source":s,"record_id":"SYNTHETIC_INITIAL_"+s,"kind":"INITIAL_LOCK","saved":True,"existing_validity":{"status":"VERIFIED","evidence_ref":"SYNTHETIC_UPSTREAM_VERDICT","verdict":"VALID","predeadline":True}} for s in ["A","B"]],
            "interventions":[], "pair_attestations":[{"race_id":"SYNTHETIC_R1","source":s,"status":"VERIFIED","evidence_ref":"SYNTHETIC_INDEPENDENT_NO_INTERVENTION","coverage_complete":True,"conclusion":"NO_INTERVENTION"} for s in ["A","B"]]}


def formal():
    data=baseline();data['phase']='FORMAL_FIRST_TWO_MEETS'
    data['official_schedule']['races'][0].update(target_date='2026-11-16',meet_id='SYNTHETIC_MEET1')
    second=deepcopy(data['official_schedule']['races'][0]);second.update(race_id='SYNTHETIC_R2',meet_id='SYNTHETIC_MEET2',target_date='2026-11-23');data['official_schedule']['races'].append(second)
    for name in ['lock_record_coverage','intervention_coverage']:data[name]['race_ids'].append('SYNTHETIC_R2')
    for name in ['lock_records','pair_attestations']:
        data[name].extend([dict(deepcopy(row),race_id='SYNTHETIC_R2') for row in data[name]])
    proof={'status':'VERIFIED','evidence_ref':'SYNTHETIC_FORMAL_WINDOW_PROOF'}
    adoptions={task:dict(proof,evidence_ref='SYNTHETIC_ADOPTION_'+task,adopted_at='2026-11-15T10:00:00+09:00') for task in ['SYS-01','SYS-02']}
    boundproof=dict(proof,cohort_meet_ids=['SYNTHETIC_MEET1','SYNTHETIC_MEET2'],adoption_evidence_refs={task:p['evidence_ref'] for task,p in adoptions.items()})
    data['formal_cohort']={'adoptions':adoptions,'first_two_meet_ids':['SYNTHETIC_MEET1','SYNTHETIC_MEET2'],'first_two_after_adoption_attestation':deepcopy(boundproof),'both_meets_complete':deepcopy(boundproof),'threshold_rule':dict(proof,scope='EACH_SOURCE')}
    return data


cases=[]
def add(name,data,expected):cases.append({'id':name,'input':data,'expected':expected,'classification':'SYNTHETIC_ONLY_NOT_REAL_APPROVAL'})

add('baseline_complete_100',baseline(),{'denominator':2,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['pair_attestations']=[];add('empty_logs_not_proof',d,{'denominator':2,'auto':0,'unknown':2,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['intervention_coverage']['complete']=False;add('coverage_unknown',d,{'denominator':2,'auto':0,'unknown':2,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_record_coverage']['complete']=False;add('events_scope_unknown',d,{'denominator':2,'auto':0,'unknown':2,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records']=[];add('complete_scope_no_initial_lock',d,{'denominator':2,'auto':0,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records'][0]['existing_validity']['predeadline']=False;add('upstream_postdeadline',d,{'denominator':2,'auto':1,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records'][0]['existing_validity']['status']='UNVERIFIED';add('validity_unknown',d,{'denominator':2,'auto':1,'unknown':1,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records'].append(deepcopy(d['lock_records'][0]));add('duplicate_initial_lock',d,{'denominator':2,'auto':1,'unknown':1,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records'].append(dict(deepcopy(d['lock_records'][0]),kind='REVISION'));add('revision_not_initial',d,{'denominator':2,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['lock_records'].append(dict(deepcopy(d['lock_records'][0]),kind='UNVERIFIED'));add('unknown_role_not_noninitial',d,{'denominator':2,'auto':1,'unknown':1,'formal':'NOT_APPLICABLE_BASELINE'})
intervention={'race_id':'SYNTHETIC_R1','source':'A','at':'2026-11-09T04:00:00Z','action':'REPLAY','initial_lock_effect':'AFFECTS_INITIAL','evidence_ref':'SYNTHETIC_MANUAL_REPLAY_RECEIPT'}
d=baseline();d['interventions']=[intervention];d['pair_attestations'][0]['conclusion']='INTERVENTION';add('manual_replay',d,{'denominator':2,'auto':1,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['interventions']=[dict(intervention,initial_lock_effect='DOES_NOT_AFFECT_INITIAL')];add('later_non_initial_action',d,{'denominator':2,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['interventions']=[dict(intervention,at=None)];add('intervention_time_unknown',d,{'denominator':2,'auto':1,'unknown':1,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['interventions']=[dict(intervention,initial_lock_effect='UNVERIFIED')];add('intervention_effect_unknown',d,{'denominator':2,'auto':1,'unknown':1,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['official_schedule']['complete']=False;add('schedule_incomplete',d,{'denominator':None,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['official_schedule']['races'].append(deepcopy(d['official_schedule']['races'][0]));add('duplicate_schedule_identity',d,{'denominator':None,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
d=baseline();d['phase']='FORMAL_FIRST_TWO_MEETS';add('baseline_cannot_formal_pass',d,{'denominator':2,'auto':2,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})
add('formal_complete_pass',formal(),{'denominator':4,'auto':4,'unknown':0,'formal':'PASS'})
d=formal();d['lock_records'].pop();add('formal_complete_fail',d,{'denominator':4,'auto':3,'unknown':0,'formal':'FAIL'})
d=formal();d['formal_cohort']['adoptions'].pop('SYS-02');add('formal_missing_adoption',d,{'denominator':4,'auto':4,'unknown':0,'formal':'UNVERIFIED'})
d=formal();d['formal_cohort']['first_two_after_adoption_attestation']['status']='UNVERIFIED';add('first_two_meets_unproven',d,{'denominator':4,'auto':4,'unknown':0,'formal':'UNVERIFIED'})
d=formal();d['formal_cohort']['both_meets_complete']['status']='UNVERIFIED';add('formal_meets_not_complete',d,{'denominator':4,'auto':4,'unknown':0,'formal':'UNVERIFIED'})
d=formal();d['intervention_coverage']['complete']=False;add('formal_intervention_completeness_unknown',d,{'denominator':4,'auto':0,'unknown':4,'formal':'UNVERIFIED'})
d=formal();d['formal_cohort'].pop('threshold_rule');add('formal_threshold_scope_unadopted',d,{'denominator':4,'auto':4,'unknown':0,'formal':'UNVERIFIED'})
d=baseline();d['interventions']=[intervention];add('attestation_conflicts_with_replay',d,{'denominator':2,'auto':1,'unknown':0,'formal':'NOT_APPLICABLE_BASELINE'})

(HERE/'fixtures.json').write_text(json.dumps({'classification':'SYNTHETIC_ONLY','cases':cases},indent=2)+'\n')
(HERE/'input-template.json').write_text(json.dumps(baseline(),indent=2)+'\n')
(HERE/'intervention-template.json').write_text(json.dumps({'classification':'SYNTHETIC_INPUT_SHAPE_ONLY','race_id':'SYNTHETIC_R1','source':'A','at':'2026-11-09T13:00:00+09:00','action':'REPLAY','initial_lock_effect':'UNVERIFIED','actor_reference':'SYNTHETIC_PRIVATE_ACTOR_REFERENCE','description':'SYNTHETIC intervention description; do not infer effect from missing log','evidence_ref':'SYNTHETIC_INTERVENTION_RECORD'},indent=2)+'\n')
print(json.dumps({'synthetic_cases':len(cases)}))
