"""Postday gating and offline entry tests. Not evidence of real HTTP success."""
import datetime as dt
import json
import sqlite3
import httpx
import pytest
from tools.capture_postday_review import ensure_postday, execute_review, TARGET_DATE
from v11_candidate.evidence_capture import CaptureError
UTC=dt.timezone.utc

@pytest.mark.parametrize('value',[None,'2026-09-19',dt.datetime(2026,9,19)])
def test_reject_unknown_clock(value):
    with pytest.raises(CaptureError):ensure_postday(value,TARGET_DATE)

@pytest.mark.parametrize('value',[
    dt.datetime(2026,9,18,14,59,59,999999,tzinfo=UTC),
    dt.datetime(2026,9,18,0,tzinfo=UTC),
    dt.datetime(2026,9,17,15,tzinfo=UTC)])
def test_no_same_or_future_day(value):
    with pytest.raises(CaptureError,match='TARGET_DAY_NOT_ELAPSED'):ensure_postday(value,TARGET_DATE)

@pytest.mark.parametrize('value',[
    dt.datetime(2026,9,18,15,tzinfo=UTC),
    dt.datetime(2026,9,19,0,tzinfo=dt.timezone(dt.timedelta(hours=9))),
    dt.datetime(2026,9,19,7,tzinfo=UTC)])
def test_jst_postday_boundary(value):ensure_postday(value,TARGET_DATE)

@pytest.mark.parametrize('target',['2026-09-17','2026-09-19','bad',None])
def test_fixed_oneoff_target(target):
    with pytest.raises(CaptureError):ensure_postday(dt.datetime(2026,9,20,tzinfo=UTC),target)


def test_no_network_by_default_or_output_side_effect(tmp_path):
    out=tmp_path/'none'
    with pytest.raises(CaptureError,match='NETWORK_NOT_AUTHORIZED'):execute_review(out)
    assert not out.exists()


def test_before_target_day_does_not_create_output_or_issue_requests(tmp_path):
    calls=[]
    def handler(request):
        calls.append(request);return httpx.Response(200)
    with pytest.raises(CaptureError,match='TARGET_DAY_NOT_ELAPSED'):
        execute_review(tmp_path/'no',transport=httpx.MockTransport(handler),
                       clock=lambda:dt.datetime(2026,9,18,tzinfo=UTC))
    assert calls==[] and not (tmp_path/'no').exists()


def test_offline_24_503s_persist_without_becoming_success(tmp_path):
    calls=[]
    def handler(request):
        calls.append(str(request.url));return httpx.Response(503,headers={'content-type':'text/html'},stream=httpx.ByteStream(b'unavailable'))
    out=tmp_path/'review'
    result=execute_review(out,transport=httpx.MockTransport(handler),clock=lambda:dt.datetime(2026,9,19,tzinfo=UTC))
    assert len(calls)==24 and len(set(calls))==24
    assert result['counts']['http_200']==0 and result['counts']['readback_verified']==24
    assert result['transport_injected'] and not result['production_recovery_proven']
    parsed=json.loads((out/'parsed_review.json').read_text())
    assert len(parsed)==24 and all('parsed' not in p and not p['input_eligible'] for p in parsed)
    manifest=json.loads((out/'manifest.json').read_text())
    assert not manifest['predeadline_state_proven'] and not manifest['automatic_recurrence']
    with sqlite3.connect(f'file:{out / "evidence.sqlite"}?mode=ro',uri=True) as conn:
        assert conn.execute('select count(*) from receipts').fetchone()[0]==48


def test_refuses_existing_output_directory(tmp_path):
    with pytest.raises(FileExistsError):
        execute_review(tmp_path,transport=httpx.MockTransport(lambda r:httpx.Response(200)),clock=lambda:dt.datetime(2026,9,19,tzinfo=UTC))
