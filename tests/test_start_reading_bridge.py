"""Stage18a focused model/adapter tests; not deployed fetcher integration."""
from dataclasses import asdict
import pytest
from pydantic import ValidationError
from models import LiveDataCompleteness
from start_reading import ExhibitionStartReading
from beforeinfo_bridge import prepare_beforeinfo
from test_v11_beforeinfo import fixture
from v11_candidate.beforeinfo import parse_start

URL='https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20260918&jcd=07&rno=12'
AT='2026-09-19T05:00:00+09:00'

@pytest.mark.parametrize('raw',['.00','.02','0.12','F.00','F.01','F.02','L.99','F','L','Ｆ．０２'])
def test_lossless_roundtrip_matches_existing_parser(raw):
    reading=parse_start(raw)
    model=ExhibitionStartReading(**asdict(reading))
    assert model.model_dump()==asdict(reading)
    assert ExhibitionStartReading.model_validate_json(model.model_dump_json())==model

@pytest.mark.parametrize('payload',[
 {'raw':'F.01','marker':None,'seconds_magnitude':.01},
 {'raw':'.01','marker':'F','seconds_magnitude':.01},
 {'raw':'F','marker':'F','seconds_magnitude':0},
 {'raw':'L','marker':'L','seconds_magnitude':.99},
 {'raw':'.01','seconds_magnitude':'0.01'},
 {'raw':'.00','seconds_magnitude':False},
 {'raw':'.01','seconds_magnitude':float('nan')},
 {'raw':'.01','seconds_magnitude':float('inf')},
 {'raw':None}, {'raw':'欠場'}, {'raw':''}, {'raw':'-'},
 {'raw':'F-.01'}, {'raw':'F .01'}, {'raw':'.001'},
])
def test_contradictory_or_unknown_reading_rejected(payload):
    with pytest.raises(ValidationError):ExhibitionStartReading(**payload)

def test_empty_model_backward_compatible():
    data=LiveDataCompleteness(start_exhibition_st={1:.02})
    assert data.start_exhibition_readings=={} and data.start_exhibition_st=={1:.02}

def test_adapter_keeps_markers_out_of_unsigned_legacy_values():
    result=prepare_beforeinfo(fixture(),URL,AT)
    data=result.live_data
    assert len(data.start_exhibition_readings)==6
    assert 2 not in data.start_exhibition_st and 3 not in data.start_exhibition_st
    assert data.start_exhibition_readings[2].marker=='F'
    assert data.start_exhibition_readings[2].seconds_magnitude==.01
    assert data.start_exhibition_st=={1:.02,4:.11,5:.01,6:.14}
    assert not data.is_complete and not result.runtime_connected
    assert LiveDataCompleteness.model_validate_json(data.model_dump_json())==data

@pytest.mark.parametrize('raw',['F','L'])
def test_marker_only_not_numeric_or_missing(raw):
    result=prepare_beforeinfo(fixture().replace('F.01',raw),URL,AT)
    r=result.live_data.start_exhibition_readings[2]
    assert r.raw==raw and r.marker==raw and r.seconds_magnitude is None
    assert 2 not in result.live_data.start_exhibition_st

@pytest.mark.parametrize('raw',['','-'])
def test_blank_is_not_zero(raw):
    data=prepare_beforeinfo(fixture().replace('F.01',raw),URL,AT).live_data
    assert 2 not in data.start_exhibition_st and 2 not in data.start_exhibition_readings

def test_bad_optional_weather_retains_reads_without_readiness_promotion():
    result=prepare_beforeinfo(fixture().replace('1m','broken',1),URL,AT)
    assert len(result.live_data.start_exhibition_readings)==6
    assert result.section_reports['weather']['state']=='PARSE_FAILED'
    assert not result.live_data.is_complete

@pytest.mark.parametrize('raw',['F.01','L'])
def test_event_payload_keeps_marked_reading(raw):
    import json
    from closing import ClosingEvaluator
    data=prepare_beforeinfo(fixture().replace('F.01',raw),URL,AT).live_data
    a,b,payload=ClosingEvaluator.evaluate_closing_signals(
        '20260918_GAM_12R',1,AT,None,None,data,AT)
    saved=json.loads(json.dumps(payload,ensure_ascii=False,allow_nan=False))
    assert saved['live_data']['start_exhibition_readings']['2']['raw']==raw
    assert saved['live_data']['start_exhibition_readings']['2']['marker']==raw[0]
    assert '2' not in saved['live_data']['start_exhibition_st']
    assert len(a)==5 and len(b)==5  # existing dummy predictions unchanged
