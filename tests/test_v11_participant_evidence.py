"""Synthetic participant-validation doubles, NOT captured official roster HTML.

A production semantic validator is deliberately absent. These tests establish
binding and fail-closed behavior, not official truth or live freshness.
"""
from dataclasses import asdict, replace, FrozenInstanceError
import datetime as dt
import hashlib
import inspect
import json
import pytest

from v11_candidate.participant_evidence import (
    ParticipantContractError, RaceIdentity, RosterSnapshot, RosterExtraction,
    SemanticValidator, inspect_participant_evidence, assess_snapshot_bound_readiness)
from v11_candidate.readiness import CheckState, EvidenceCheck
from v11_candidate.observation import parse_beforeinfo_observation
from test_v11_beforeinfo import fixture

TARGET = RaceIdentity('2026-09-18', '07', 12)
NOW = dt.datetime.fromisoformat('2026-09-18T20:30:00+09:00')
URL = 'https://www.boatrace.jp/owpc/pc/race/racelist?hd=20260918&jcd=07&rno=12'


def raw(**changes):
    payload = {'synthetic': True, 'identity': asdict(TARGET),
               'slots': [[b, 'ACTIVE'] for b in range(1,7)], 'locator': 'SYNTHETIC_ROSTER'} | changes
    return ('<synthetic>' + json.dumps(payload) + '</synthetic>').encode()


def snapshot(body=None, **changes):
    body = raw() if body is None else body
    args = dict(snapshot_id='SYNTHETIC-SNAPSHOT-12', requested_url=URL, response_url=URL,
                acquired_at='2026-09-18T20:29:00+09:00', http_status=200,
                content_type='text/html;charset=UTF-8', body=body,
                body_sha256=hashlib.sha256(body).hexdigest())
    return RosterSnapshot(**(args | changes))


def fake_extract(body):
    # Strict test-only envelope; do not reuse this as an official HTML parser.
    text = body.decode()
    if not text.startswith('<synthetic>') or not text.endswith('</synthetic>'):
        return None
    d=json.loads(text[len('<synthetic>'):-len('</synthetic>')])
    assert d['synthetic'] is True
    return RosterExtraction(RaceIdentity(**d['identity']), tuple(tuple(s) for s in d['slots']), d['locator'])


FAKE = SemanticValidator('SYNTHETIC_ROSTER_VALIDATOR_V1', fake_extract)


def inspect_snapshot(s=None, **changes):
    args = dict(now=NOW, validator=FAKE, allow_test_validator=True) | changes
    return inspect_participant_evidence(snapshot() if s is None else s, TARGET, **args)


def other_checks():
    return {k: EvidenceCheck(CheckState.PASS, ('SYNTHETIC_'+k,))
            for k in ('PAGE_IDENTITY', 'EXHIBITION_FRESHNESS', 'START_FRESHNESS')}


def bound(s=None, **changes):
    args = dict(now=NOW, validator=FAKE, allow_test_validator=True, checks=other_checks()) | changes
    return assess_snapshot_bound_readiness(parse_beforeinfo_observation(fixture()), TARGET,
                                          snapshot() if s is None else s, **args)


def test_values_and_proof_derived_from_same_body():
    seen=[]
    def extract(body):
        seen.append(body)
        return fake_extract(body)
    snap=snapshot(); p=inspect_snapshot(snap,validator=SemanticValidator('SYNTHETIC_V2',extract))
    assert seen==[snap.body]
    assert p.expected_boats==(1,2,3,4,5,6) and p.state==CheckState.PASS
    assert p.body_sha256==hashlib.sha256(snap.body).hexdigest()
    assert p.verify_binding() and p.test_only
    assert json.loads(json.dumps(asdict(p)))['expected_boats']==[1,2,3,4,5,6]


def test_no_installed_validator_never_passes_from_url_hash_alone():
    p=inspect_participant_evidence(snapshot(),TARGET,now=NOW)
    assert p.state==CheckState.UNVERIFIED and p.expected_boats is None
    assert p.reasons==('SEMANTIC_VALIDATOR_NOT_INSTALLED',)


def test_test_validator_not_allowed_by_default():
    p=inspect_snapshot(allow_test_validator=False)
    assert p.state==CheckState.UNVERIFIED and p.expected_boats is None


def test_missing_snapshot_unverified():
    p=inspect_participant_evidence(None,TARGET,now=NOW)
    assert p.state==CheckState.UNVERIFIED and p.verify_binding()


@pytest.mark.parametrize('body', [b'corrupt', b''])
def test_raw_bytes_changed_without_hash_is_fail(body):
    p=inspect_snapshot(replace(snapshot(),body=body))
    assert p.state==CheckState.FAIL and 'BODY_HASH_MISMATCH' in p.reasons


@pytest.mark.parametrize('change',[
    {'expected_boats':(1,2,3,4,5)}, {'snapshot_id':'OTHER'},
    {'target':RaceIdentity('2026-09-18','07',3)}, {'body_sha256':'0'*64},
    {'validator_id':'OTHER'}, {'acquired_at':'2026-09-18T01:00:00Z'},
    {'state':CheckState.UNVERIFIED}, {'test_only':False}])
def test_changed_bound_value_invalidates_integrity(change):
    assert not replace(inspect_snapshot(),**change).verify_binding()


def test_bound_result_is_frozen():
    p=inspect_snapshot()
    with pytest.raises(FrozenInstanceError): p.expected_boats=(1,2,3,4,5)


@pytest.mark.parametrize('url',[
    URL.replace('https:','http:'), URL.replace('www.boatrace.jp','evil.example'),
    URL.replace('/racelist?','/beforeinfo?'), URL.replace('20260918','20260917'),
    URL.replace('rno=12','rno=3'), URL.replace('jcd=07','jcd=08'),
    URL+'&rno=12', URL+'#other', URL.replace('https://','https://name@'),
    URL.replace('www.boatrace.jp','www.boatrace.jp:444'), URL+' ',
    URL.replace('www.boatrace.jp','www.boatrace.jp.evil.example')])
def test_wrong_requested_url_never_reaches_semantics(url):
    seen=[]
    def extract(body): seen.append(body); return fake_extract(body)
    p=inspect_snapshot(snapshot(requested_url=url),validator=SemanticValidator('SYNTHETIC_V',extract))
    assert p.state==CheckState.FAIL and seen==[]


def test_redirected_body_url_also_checked():
    p=inspect_snapshot(snapshot(response_url=URL.replace('rno=12','rno=11')))
    assert p.state==CheckState.FAIL


@pytest.mark.parametrize('url',[URL.replace('www.boatrace.jp','boatrace.jp'),URL.replace('www.boatrace.jp','www.boatrace.jp:443')])
def test_both_official_host_spellings_and_https_port(url):
    assert inspect_snapshot(snapshot(requested_url=url,response_url=url)).state==CheckState.PASS


@pytest.mark.parametrize('identity',[{'target_date':'2026-09-17','venue_code':'07','race_no':12},
                                     {'target_date':'2026-09-18','venue_code':'07','race_no':3}])
def test_correct_url_does_not_override_mismatching_body(identity):
    p=inspect_snapshot(snapshot(raw(identity=identity)))
    assert p.state==CheckState.FAIL and p.expected_boats is None
    assert p.reasons==('ROSTER_BODY_IDENTITY_MISMATCH',)


@pytest.mark.parametrize('slots',[
    [[b,'ACTIVE'] for b in range(1,6)],
    [[b, 'UNKNOWN' if b==6 else 'ACTIVE'] for b in range(1,7)], []])
def test_missing_and_unknown_roster_slots_do_not_shrink_field(slots):
    p=inspect_snapshot(snapshot(raw(slots=slots)))
    assert p.state==CheckState.UNVERIFIED and p.expected_boats is None


def test_explicit_withdrawal_values_are_carried_but_reduced_policy_stays_unverified():
    slots=[[b,'WITHDRAWN' if b==6 else 'ACTIVE'] for b in range(1,7)]
    r=bound(snapshot(raw(slots=slots)))
    assert r.participants.expected_boats==(1,2,3,4,5)
    assert r.participants.state==CheckState.PASS
    assert r.readiness.state==CheckState.UNVERIFIED and not r.readiness.input_eligible
    assert 'REDUCED_FIELD_POLICY_NOT_IMPLEMENTED' in r.readiness.reasons


@pytest.mark.parametrize('slots',[
    [[1,'ACTIVE'],[1,'ACTIVE']], [[True,'ACTIVE']], [['1','ACTIVE']],
    [[7,'ACTIVE']], [[1,'F']], [[1,'ACTIVE','unexpected']]])
def test_invalid_roster_fails_without_inference(slots):
    p=inspect_snapshot(snapshot(raw(slots=slots)))
    assert p.state==CheckState.FAIL and p.expected_boats is None


def test_slot_order_is_normalized_not_interpreted_as_course():
    assert inspect_snapshot(snapshot(raw(slots=[[b,'ACTIVE'] for b in range(6,0,-1)]))).expected_boats==(1,2,3,4,5,6)


@pytest.mark.parametrize('stamp',['not-a-time','2026-09-18T20:29:00','2026-09-18T20:31:00+09:00'])
def test_bad_or_future_acquisition_is_fail(stamp):
    assert inspect_snapshot(snapshot(acquired_at=stamp)).state==CheckState.FAIL


def test_old_acquisition_is_not_freshness_certification():
    p=inspect_snapshot(snapshot(acquired_at='2026-09-17T20:29:00+09:00'))
    assert p.state==CheckState.PASS  # claim binding only, NOT freshness
    r=bound(snapshot(acquired_at='2026-09-17T20:29:00+09:00'),checks={})
    assert not r.readiness.input_eligible and r.readiness.state==CheckState.UNVERIFIED


@pytest.mark.parametrize('changes',[{'http_status':503},{'http_status':302},{'content_type':'application/json'}])
def test_unavailable_response_is_unknown(changes):
    assert inspect_snapshot(snapshot(**changes)).state==CheckState.UNVERIFIED


@pytest.mark.parametrize('changes',[{'http_status':True},{'body_sha256':'abc'},{'body':bytearray(b'a')},
                                   {'snapshot_id':''},{'acquired_at':None},{'body':b'x'*2_000_001}])
def test_invalid_metadata_is_fail(changes):
    assert inspect_snapshot(replace(snapshot(),**changes)).state==CheckState.FAIL


def test_unrecognized_body_not_inferred_from_observation():
    r=bound(snapshot(b'<html>No roster</html>'))
    assert r.participants.expected_boats is None and not r.readiness.input_eligible


def test_validator_exception_does_not_leak_body_or_claim_validity():
    def failing(body): raise RuntimeError('private full response')
    p=inspect_snapshot(validator=SemanticValidator('SYNTHETIC_FAIL',failing))
    assert p.state==CheckState.UNVERIFIED and 'private' not in str(p)


@pytest.mark.parametrize('out',[{},RosterExtraction(TARGET,tuple((b,'ACTIVE') for b in range(1,7)), '')])
def test_invalid_validator_output_is_fail(out):
    assert inspect_snapshot(validator=SemanticValidator('SYNTHETIC_BAD',lambda body:out)).state==CheckState.FAIL


def test_no_two_channel_override_in_entry_signature():
    sig=inspect.signature(assess_snapshot_bound_readiness)
    assert 'expected_boats' not in sig.parameters
    with pytest.raises(TypeError):
        bound(expected_boats=(1,2,3,4,5,6))


@pytest.mark.parametrize('key',['OFFICIAL_PARTICIPANTS','expected_boats','UNRECOGNIZED'])
def test_other_checks_cannot_override_participant_evidence(key):
    with pytest.raises(ParticipantContractError):bound(checks={key:EvidenceCheck(CheckState.PASS,('SYNTHETIC',))})


def test_binding_does_not_create_other_evidence():
    r=bound(checks={})
    assert r.participants.state==CheckState.PASS
    assert r.readiness.state==CheckState.UNVERIFIED and not r.readiness.input_eligible


def test_other_checks_not_mutated_and_full_synthetic_case_can_pass():
    checks=other_checks(); before=dict(checks)
    r=bound(checks=checks)
    assert checks==before and 'OFFICIAL_PARTICIPANTS' not in checks
    assert r.readiness.input_eligible and r.participants.test_only


def test_broken_evidence_is_fail_even_when_other_checks_unknown():
    r=bound(replace(snapshot(),body=b'wrong'),checks={})
    assert r.readiness.state==CheckState.FAIL
    assert 'PAGE_IDENTITY:UNVERIFIED' in r.readiness.reasons


def test_ordinary_gateway_with_no_real_verifier_cannot_enable_evaluation():
    r=bound(validator=None,allow_test_validator=False)
    assert r.readiness.state==CheckState.UNVERIFIED and not r.readiness.input_eligible


@pytest.mark.parametrize('day',['2026-02-30','20260918','2026-9-18',None])
def test_invalid_race_date(day):
    with pytest.raises(ParticipantContractError):RaceIdentity(day,'07',12)


@pytest.mark.parametrize('venue,race',[('08',12),('07',True),('07',0),('07',13),('07','12')])
def test_invalid_race_identity(venue,race):
    with pytest.raises(ParticipantContractError):RaceIdentity('2026-09-18',venue,race)


def test_naive_inspection_clock_rejected():
    with pytest.raises(ParticipantContractError):inspect_snapshot(now=NOW.replace(tzinfo=None))


def test_input_snapshot_is_unchanged():
    s=snapshot(); before=asdict(s)
    inspect_snapshot(s)
    assert asdict(s)==before
