import copy
import hashlib
import json
import pytest
from closing import ClosingEvaluator
from beforeinfo_bridge import prepare_beforeinfo
from test_v11_beforeinfo import fixture
from c_payload_schema import read_c_payload, PayloadSchemaError


def pack(p):
    text = json.dumps(p, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return text, hashlib.sha256(text.encode()).hexdigest()


def current():
    d = prepare_beforeinfo(fixture(), 'test', 'test').live_data
    return ClosingEvaluator.evaluate_closing_signals('20260918_GAM_12R', 1, 'test', None, None, d, 'test')[2]


def test_new_payload_uses_v2_and_preserves_markers():
    p = current(); text, h = pack(p); r = read_c_payload(text, h)
    assert p['schema_version'] == 2
    assert r['start_readings']['2']['raw'] == 'F.01'
    assert r['start_readings']['2']['marker'] == 'F'
    assert '2' not in r['original_payload']['live_data']['start_exhibition_st']
    assert not r['prediction_validated'] and not r['readiness_validated']


@pytest.mark.parametrize('explicit', [False, True])
def test_legacy_preserves_hash_without_filling_in_missing_markers(explicit):
    p = {'source':'Observer_C', 'live_data':{'start_exhibition_st':{'1':0.01}}}
    if explicit: p['schema_version'] = 1
    text,h = pack(p); original = copy.deepcopy(p); r = read_c_payload(text,h)
    assert r['effective_schema_version'] == 1 and r['start_readings'] is None
    assert r['marker_semantics'] == 'LEGACY_UNKNOWN'
    assert r['original_payload'] == original and pack(r['original_payload'])[1] == h
    assert ('schema_version' in r['original_payload']) == explicit


@pytest.mark.parametrize('value', [None, True, False, '2', 2.0, 0, -1, 3, {}, []])
def test_invalid_or_future_version_never_coerced(value):
    p = current(); p['schema_version'] = value
    with pytest.raises(PayloadSchemaError, match='UNSUPPORTED'):read_c_payload(*pack(p))


@pytest.mark.parametrize('field',['start_exhibition_readings','start_exhibition_st'])
def test_v2_missing_field_not_silently_defaulted(field):
    p=current(); del p['live_data'][field]
    with pytest.raises(PayloadSchemaError,match='REQUIRED'):read_c_payload(*pack(p))


def test_marked_value_cannot_silently_enter_numeric_projection():
    p=current(); p['live_data']['start_exhibition_st'][2]=0.01
    with pytest.raises(PayloadSchemaError,match='PROJECTION'):read_c_payload(*pack(p))


def test_changed_raw_is_rejected_even_with_recomputed_payload_hash():
    p=current(); p['live_data']['start_exhibition_readings'][2]['marker']=None
    with pytest.raises(PayloadSchemaError,match='READING'):read_c_payload(*pack(p))


def test_legacy_extension_is_preserved_not_silently_upgraded():
    p=current(); p['schema_version']=1; r=read_c_payload(*pack(p))
    assert r['v1_has_uninterpreted_extension'] and r['start_readings'] is None
    assert r['original_payload']['live_data']['start_exhibition_readings']


@pytest.mark.parametrize('source',['A','B','SYSTEM',None])
def test_reader_does_not_apply_C_schema_to_other_records(source):
    p=current(); p['source']=source
    with pytest.raises(PayloadSchemaError,match='NOT_C'):read_c_payload(*pack(p))


def test_hash_checked_before_version_default():
    p=current(); text,h=pack(p)
    with pytest.raises(PayloadSchemaError,match='HASH'):read_c_payload(text,'0'*64)


def test_duplicate_keys_rejected():
    with pytest.raises(PayloadSchemaError,match='DUPLICATE'):
        read_c_payload('{"schema_version":1,"schema_version":2}', '0'*64)


@pytest.mark.parametrize('token',['NaN','Infinity','-Infinity'])
def test_nonfinite_rejected(token):
    with pytest.raises(PayloadSchemaError,match='NONFINITE'):
        read_c_payload('{"x":'+token+'}', '0'*64)


@pytest.mark.parametrize('boat',['0','7','01','a'])
def test_invalid_boat_ids_rejected(boat):
    p=json.loads(json.dumps(current())); p['live_data']['start_exhibition_readings'][boat]={'raw':'.01','marker':None,'seconds_magnitude':.01}
    with pytest.raises(PayloadSchemaError,match='BOAT_MAP'):read_c_payload(*pack(p))
