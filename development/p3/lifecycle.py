"""SYS-30 explicit local attestation ledger, never executes production actions."""
from copy import deepcopy
from datetime import datetime
import re

STAGES=('DRAFT','DEV_READY','CLAUDE_REVIEWED','GO_APPROVED','APPLIED','READBACK_VERIFIED','NATURAL_RUN_VERIFIED','CLOSE')
REQUIRED={
    'DEV_READY':(('TEST_REPORT','DEVELOPER'),),
    'CLAUDE_REVIEWED':(('INDEPENDENT_REVIEW_PASS','CLAUDE'),),
    'GO_APPROVED':(('ANDY_INDIVIDUAL_GO','ANDY'),),
    'APPLIED':(('APPLICATION_RECEIPT','OPERATOR'),),
    'READBACK_VERIFIED':(('READBACK_REPORT','VERIFIER'),),
    'NATURAL_RUN_VERIFIED':(('NATURAL_RUN_REPORT','VERIFIER'),),
    'CLOSE':(('CLOSE_INDEPENDENT_REVIEW','CLAUDE'),('CLOSE_DECISION','ANDY')),
}


def _time(value):
    if not isinstance(value,str):raise ValueError('TIMESTAMP_REQUIRED')
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})',value):raise ValueError('TIMESTAMP_PROFILE_INVALID')
    if value.endswith('-00:00'):raise ValueError('UNKNOWN_TIME_OFFSET')
    try:t=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('TIMESTAMP_INVALID') from None
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError('TIMEZONE_REQUIRED')
    return t


def new_ledger(case_id,commit,author):
    if not isinstance(case_id,str) or not case_id or not isinstance(commit,str) or not re.fullmatch('[0-9a-f]{40}',commit) or not isinstance(author,str) or not author:
        raise ValueError('LEDGER_IDENTITY_INVALID')
    return {'case_id':case_id,'subject_commit':commit,'subject_author':author,'stage':'DRAFT','history':[],'real_world_status_authenticity':'UNVERIFIED_BY_LOCAL_CODE','production_actions_performed':False}


def _event(ledger,event,registry,previous_at=None):
    target=event.get('to')
    if target not in REQUIRED:raise ValueError('TARGET_INVALID')
    if event.get('manual_action')!='RECORD_ATTESTATION' or not isinstance(event.get('actor'),str) or not event['actor']:
        raise ValueError('EXPLICIT_MANUAL_ACTION_REQUIRED')
    now=_time(event.get('recorded_at'))
    if previous_at is not None and now<previous_at:raise ValueError('HISTORY_TIME_REVERSED')
    records=event.get('evidence')
    if not isinstance(records,list):raise ValueError('EVIDENCE_LIST_REQUIRED')
    if len(records)!=len(REQUIRED[target]):raise ValueError('EXACT_STAGE_EVIDENCE_SET_REQUIRED')
    for kind,role in REQUIRED[target]:
        selected=[r for r in records if isinstance(r,dict) and r.get('kind')==kind]
        if len(selected)!=1:raise ValueError('REQUIRED_EVIDENCE_MISSING_OR_DUPLICATE')
        r=selected[0]
        if not isinstance(r.get('evidence_id'),str) or not r['evidence_id']:raise ValueError('EVIDENCE_ID_REQUIRED')
        if r.get('external_verification_status')!='EXTERNALLY_VERIFIED' or r.get('outcome')!='PASS':
            raise ValueError('SELFCLAIM_OR_FAILED_EVIDENCE')
        if r.get('case_id')!=ledger['case_id'] or r.get('subject_commit')!=ledger['subject_commit']:
            raise ValueError('EVIDENCE_IDENTITY_MISMATCH')
        issuer=r.get('issuer')
        if not isinstance(issuer,str) or issuer not in registry.get(role,[]):raise ValueError('ISSUER_NOT_IN_SUPPLIED_TRUST_REGISTRY')
        if role in ('CLAUDE','ANDY') and issuer==ledger['subject_author']:raise ValueError('INDEPENDENCE_VIOLATION')
        if not isinstance(r.get('source_reference'),str) or not r['source_reference'] or not isinstance(r.get('independent_verification_reference'),str) or not r['independent_verification_reference']:
            raise ValueError('EXTERNAL_SOURCE_BINDING_REQUIRED')
        if r['source_reference']==r['independent_verification_reference']:raise ValueError('SELF_REFERENCE_NOT_INDEPENDENT')
        digest=r.get('sha256')
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('EVIDENCE_SHA_REQUIRED')
        if _time(r.get('observed_at'))>now:raise ValueError('FUTURE_EVIDENCE')
        if kind=='ANDY_INDIVIDUAL_GO' and r.get('authorized_action')!='APPLY_EXACT_SUBJECT_COMMIT':
            raise ValueError('GO_ACTION_MISMATCH')
    return now


def validate_ledger(ledger,trust_registry):
    if not isinstance(trust_registry,dict) or not trust_registry:raise ValueError('EXTERNAL_TRUST_REGISTRY_REQUIRED')
    for issuers in trust_registry.values():
        if not isinstance(issuers,list) or not issuers or any(not isinstance(x,str) or not x for x in issuers) or len(set(issuers))!=len(issuers):raise ValueError('TRUST_REGISTRY_FORMAT_INVALID')
    if not isinstance(ledger,dict):raise ValueError('LEDGER_OBJECT_REQUIRED')
    new_ledger(ledger.get('case_id'),ledger.get('subject_commit'),ledger.get('subject_author'))
    history=ledger.get('history')
    if not isinstance(history,list):raise ValueError('HISTORY_REQUIRED')
    state='DRAFT';when=None;previous_event=None;seen_evidence=set();previous_evidence_at=None
    for event in history:
        if not isinstance(event,dict) or STAGES.index(state)+1>=len(STAGES) or event.get('from')!=state or event.get('to')!=STAGES[STAGES.index(state)+1]:
            raise ValueError('NONSEQUENTIAL_HISTORY')
        if event.get('event_id')!=ledger['case_id']+':'+event['to'] or event.get('previous_event_id')!=previous_event:raise ValueError('EVENT_LINK_MISMATCH')
        when=_event(ledger,event,trust_registry,when);state=event['to'];previous_event=event['event_id']
        times=[_time(r['observed_at']) for r in event['evidence']]
        if previous_evidence_at is not None and any(t<previous_evidence_at for t in times):raise ValueError('EVIDENCE_STAGE_TIME_REVERSED')
        previous_evidence_at=max(times)
        for record in event['evidence']:
            if not isinstance(record,dict) or record.get('evidence_id') in seen_evidence:raise ValueError('EVIDENCE_ID_REUSED')
            if record.get('evidence_id') is not None:seen_evidence.add(record['evidence_id'])
    if ledger.get('stage')!=state:raise ValueError('STAGE_HISTORY_MISMATCH')
    return state,when


def record_transition(ledger,target,*,actor,recorded_at,evidence,trust_registry,manual_action):
    """One explicit transition only. Metadata truth remains an external boundary."""
    state,previous=validate_ledger(ledger,trust_registry)
    if STAGES.index(state)+1>=len(STAGES) or target!=STAGES[STAGES.index(state)+1]:raise ValueError('NEXT_STAGE_ONLY')
    event={'from':state,'to':target,'actor':actor,'recorded_at':recorded_at,'manual_action':manual_action,'evidence':deepcopy(evidence),'event_id':ledger['case_id']+':'+target,'previous_event_id':ledger['history'][-1]['event_id'] if ledger['history'] else None}
    _event(ledger,event,trust_registry,previous)
    result=deepcopy(ledger);result['history'].append(event);result['stage']=target
    validate_ledger(result,trust_registry)
    result['real_world_status_authenticity']='UNVERIFIED_BY_LOCAL_CODE_EXTERNAL_TRUST_INPUT_REQUIRED'
    result['production_actions_performed']=False
    return result
