"""Offline acquisition/storage integration; no real 12-race capture is claimed."""
from dataclasses import asdict
import datetime as dt
import gzip
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from test_v11_beforeinfo import fixture
from v11_candidate.evidence_capture import (
    CaptureError, CaptureLimits, CaptureSpec, EvidenceArchive, digest,
    full_day_phase, run_capture_phase, review_saved_beforeinfo)

DAY='2026-09-18'
LIMITS=CaptureLimits(100_000,1.0)


def create(tmp_path):
    return EvidenceArchive(tmp_path/'review.sqlite',full_day_phase(DAY,'OFFLINE_TEST'))


def response(body=b'<html>test only</html>', status=200, headers=None):
    return httpx.Response(status,headers={'content-type':'text/html; charset=utf-8',**(headers or {})},stream=httpx.ByteStream(body))


def run(a, handler=None, limits=LIMITS, **kwargs):
    return run_capture_phase(a,limits,transport=httpx.MockTransport(handler or (lambda r:response())),**kwargs)


def common(a,index,stage):
    return dict(key=a.keys[index],run_id=a.run_id,spec=asdict(a.specs[index]),stage=stage)


def test_phase_has_exact_24_unique_fixed_official_targets():
    p=full_day_phase(DAY,'TEST')
    assert len(p)==len({s.url for s in p})==24
    assert {s.race_no for s in p}==set(range(1,13))
    assert all(s.url.startswith('https://www.boatrace.jp/owpc/pc/race/') for s in p)


@pytest.mark.parametrize('day',['2026-02-30','20260918','26-09-18','2026-13-01','2026-09-18/../../',None])
def test_invalid_date_fails_before_io(day):
    with pytest.raises(CaptureError):full_day_phase(day,'TEST')


@pytest.mark.parametrize('r',[0,13,True,'1',None])
def test_invalid_race_fails(r):
    with pytest.raises(CaptureError):CaptureSpec(DAY,r,'beforeinfo','TEST')


@pytest.mark.parametrize('endpoint',['result','https://evil.example','beforeinfo?x=1','../racelist'])
def test_unapproved_endpoint_fails(endpoint):
    with pytest.raises(CaptureError):CaptureSpec(DAY,1,endpoint,'TEST')


@pytest.mark.parametrize('phase',['','../x','x','TEST SPACE','A'*49])
def test_invalid_phase_fails(phase):
    with pytest.raises(CaptureError):full_day_phase(DAY,phase)


@pytest.mark.parametrize('n',[0,-1,2_000_001,True,1.5])
def test_bad_body_limit(n):
    with pytest.raises(CaptureError):CaptureLimits(n,1)


@pytest.mark.parametrize('t',[0,-1,61,True,float('nan'),float('inf'),'1'])
def test_bad_timeout(t):
    with pytest.raises(CaptureError):CaptureLimits(100,t)


def test_existing_file_is_never_opened_for_write(tmp_path):
    p=tmp_path/'review.sqlite';p.write_bytes(b'production placeholder')
    with pytest.raises(FileExistsError):create(tmp_path)
    assert p.read_bytes()==b'production placeholder'


def test_symlink_is_never_followed_for_creation(tmp_path):
    target=tmp_path/'production';target.write_bytes(b'leave alone')
    (tmp_path/'review.sqlite').symlink_to(target)
    with pytest.raises(FileExistsError):create(tmp_path)
    assert target.read_bytes()==b'leave alone'


def test_unapproved_network_never_opens_client(tmp_path):
    a=create(tmp_path)
    with pytest.raises(CaptureError,match='NETWORK_NOT_AUTHORIZED'):
        run_capture_phase(a,LIMITS)
    assert all(a.read(k,'START') is None for k in a.keys)


def test_all_24_attempts_archived_deduped_and_readback(tmp_path):
    a=create(tmp_path);calls=[]
    def get(r):
        calls.append(str(r.url));return response()
    out=run(a,get)
    assert len(calls)==24 and len(set(calls))==24
    assert out['counts']==dict(planned=24,attempted_this_run=24,received_headers=24,http_200=24,
         body_complete=24,body_persisted=24,end_persisted=24,readback_verified=24)
    with sqlite3.connect(a.path) as c:
        assert c.execute('SELECT count(*) FROM blobs').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM receipts').fetchone()[0]==48
    assert out['production_recovery_proven'] is False
    assert out['semantic_validation']=='NOT_RUN'
    for k in a.keys:
        p,b=a.read(k,'END');assert p['body_sha256']==digest(b)
        assert dt.datetime.fromisoformat(p['started_at'])<=dt.datetime.fromisoformat(p['received_at'])<=dt.datetime.fromisoformat(p['finished_at'])


def test_paired_failure_never_discards_successful_other_side(tmp_path):
    a=create(tmp_path)
    def get(r):
        if '/racelist?' in str(r.url):raise httpx.ConnectError('private credential must not be logged')
        return response()
    out=run(a,get)
    assert out['counts']['attempted_this_run']==24
    assert out['counts']['body_persisted']==12 and out['counts']['readback_verified']==24
    p,b=a.read(a.keys[0],'END');assert b is None and p['error']=='ConnectError'
    assert 'credential' not in json.dumps(p)
    assert a.read(a.keys[1],'END')[1] is not None


def test_non_200_response_body_is_preserved(tmp_path):
    a=create(tmp_path);out=run(a,lambda r:response(b'upstream error',503))
    assert out['counts']['http_200']==0 and out['counts']['body_persisted']==24
    assert a.read(a.keys[1],'END')[1]==b'upstream error'
    with pytest.raises(CaptureError):review_saved_beforeinfo(a,a.keys[1])


def test_redirect_is_recorded_without_following(tmp_path):
    a=create(tmp_path);seen=[]
    def get(r):
        seen.append(r.url.host);return response(b'moved',302,{'location':'https://evil.example'})
    out=run(a,get)
    assert seen==['www.boatrace.jp']*24
    assert out['counts']['http_200']==0 and out['counts']['body_persisted']==24


def test_sensitive_headers_never_saved_or_reused(tmp_path):
    a=create(tmp_path)
    def get(r):
        assert 'cookie' not in r.headers and 'authorization' not in r.headers
        return response(headers={'set-cookie':'SECRET=yes','www-authenticate':'SECRET','etag':'abc','date':'Fri, 18 Sep 2026 00:00:00 GMT'})
    run(a,get)
    for k in a.keys:
        p,_=a.read(k,'END')
        assert 'set-cookie' not in p['headers'] and 'www-authenticate' not in p['headers']
        assert p['headers']['etag']=='abc' and p['source_effective_at'] is None


@pytest.mark.parametrize('size',[9,10,11])
def test_body_boundary_and_prefix_not_complete(tmp_path,size):
    a=create(tmp_path);out=run(a,lambda r:response(b'x'*size),CaptureLimits(10,1))
    p,b=a.read(a.keys[1],'END')
    assert len(b)==min(size,10)
    assert p['body_complete'] is (size<=10)
    assert p['error']==('BODY_LIMIT_EXCEEDED' if size>10 else None)
    if size>10:
        assert out['counts']['body_complete']==0
        with pytest.raises(CaptureError):review_saved_beforeinfo(a,a.keys[1])


class BrokenBody(httpx.SyncByteStream):
    def __iter__(self):
        yield b'partial'
        raise httpx.ReadError('stream broke')


def test_stream_failure_preserves_partial_prefix_not_usable(tmp_path):
    a=create(tmp_path)
    run(a,lambda r:httpx.Response(200,headers={'content-type':'text/html'},stream=BrokenBody()))
    p,b=a.read(a.keys[1],'END')
    assert b==b'partial' and p['body_complete'] is False and p['error']=='ReadError'
    with pytest.raises(CaptureError):review_saved_beforeinfo(a,a.keys[1])


def test_compressed_entity_not_silently_decoded(tmp_path):
    a=create(tmp_path);wire=gzip.compress(b'<html>hello</html>')
    run(a,lambda r:response(wire,headers={'content-encoding':'gzip'}))
    assert a.read(a.keys[1],'END')[1]==wire
    with pytest.raises(CaptureError):review_saved_beforeinfo(a,a.keys[1])


def test_same_phase_not_retried_implicitly(tmp_path):
    a=create(tmp_path);run(a)
    out=run(a,lambda r:pytest.fail('must not fetch twice'))
    assert out['counts']['attempted_this_run']==0 and len(out['storage_failures'])==24


def test_interruption_leaves_start_and_planned_holes(tmp_path):
    a=create(tmp_path)
    def get(r):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):run(a,get)
    assert a.read(a.keys[0],'START') is not None and a.read(a.keys[0],'END') is None
    assert a.read(a.keys[1],'START') is None


def test_start_storage_failure_does_not_fetch_and_other_side_continues(tmp_path,monkeypatch):
    a=create(tmp_path);real=a.append;calls=[]
    def append(k,s,p,b=None):
        if k==a.keys[0] and s=='START':raise OSError('disk fail')
        return real(k,s,p,b)
    monkeypatch.setattr(a,'append',append)
    out=run(a,lambda r:(calls.append(str(r.url)) or response()))
    assert out['counts']['attempted_this_run']==23 and a.specs[0].url not in calls
    assert a.read(a.keys[1],'END') is not None


def test_end_storage_failure_keeps_start_and_other_captures(tmp_path,monkeypatch):
    a=create(tmp_path);real=a.append
    def append(k,s,p,b=None):
        if k==a.keys[0] and s=='END':raise OSError('disk fail')
        return real(k,s,p,b)
    monkeypatch.setattr(a,'append',append);out=run(a)
    assert out['counts']['end_persisted']==23 and out['counts']['readback_verified']==23
    assert a.read(a.keys[0],'START') is not None and a.read(a.keys[0],'END') is None


def test_corrupt_blob_or_receipt_cannot_be_readback_verified(tmp_path):
    a=create(tmp_path);run(a)
    with sqlite3.connect(a.path) as c:c.execute("UPDATE blobs SET body=?",(b'tampered',))
    with pytest.raises(CaptureError,match='BLOB_READBACK'):a.read(a.keys[1],'END')


def test_receipt_tamper_rejected(tmp_path):
    a=create(tmp_path);run(a)
    with sqlite3.connect(a.path) as c:c.execute("UPDATE receipts SET payload_json='{}' WHERE stage='END'")
    with pytest.raises(CaptureError,match='HASH'):a.read(a.keys[0],'END')


def test_plan_tamper_rejected(tmp_path):
    a=create(tmp_path)
    with sqlite3.connect(a.path) as c:c.execute("UPDATE planned SET spec_json='{}'")
    with pytest.raises(CaptureError,match='PLAN'):a.read(a.keys[0],'START')


def test_retry_same_receipt_is_dedup_not_overwrite(tmp_path):
    a=create(tmp_path);p=common(a,0,'START')
    a.append(a.keys[0],'START',p);a.append(a.keys[0],'START',p)
    with pytest.raises(CaptureError,match='COLLISION'):a.append(a.keys[0],'START',p|{'other':1})
    assert a.read(a.keys[0],'START')[0]==p


def test_no_end_without_start_or_body_binding(tmp_path):
    a=create(tmp_path);p=common(a,0,'END')|{'body_sha256':None}
    with pytest.raises(CaptureError,match='END_WITHOUT'):a.append(a.keys[0],'END',p)
    a.append(a.keys[0],'START',common(a,0,'START'))
    with pytest.raises(CaptureError,match='BODY_MISMATCH'):a.append(a.keys[0],'END',p,b'abc')


def test_review_both_parsers_bound_to_same_saved_bytes(tmp_path):
    a=create(tmp_path);body=fixture().replace('F.01','欠場',1).encode('utf-8')
    run(a,lambda r:response(body))
    out=review_saved_beforeinfo(a,a.keys[1])
    assert out['body_sha256']==out['withdrawal']['body_sha256']==digest(body)
    assert out['withdrawal']['signals'][0]['boat']==2
    assert 2 not in out['observation']['data']['starts']
    assert out['input_eligible'] is False
    assert out['withdrawal']['official_status_verified'] is False


def test_parser_error_cannot_delete_saved_raw_response(tmp_path):
    a=create(tmp_path);body=b'\xff invalid UTF8'
    run(a,lambda r:response(body))
    out=review_saved_beforeinfo(a,a.keys[1])
    assert 'error' in out['observation'] and 'error' in out['withdrawal']
    assert a.read(a.keys[1],'END')[1]==body


def test_no_new_phase_or_retention_schedule_is_implied(tmp_path):
    a=create(tmp_path);out=run(a)
    assert all(s.phase=='OFFLINE_TEST' for s in a.specs)
    assert out['review_only'] and not out['production_recovery_proven']
    assert not hasattr(a,'delete') and not hasattr(a,'schedule')


def test_unsupported_plan_rejected_before_creating_db(tmp_path):
    with pytest.raises(CaptureError):EvidenceArchive(tmp_path/'never.sqlite',full_day_phase(DAY,'TEST')[:-1])
    assert not (tmp_path/'never.sqlite').exists()


def test_injected_transport_classification_is_in_every_receipt(tmp_path):
    a=create(tmp_path);run(a)
    for key in a.keys:
        for stage in ('START','END'):
            p,_=a.read(key,stage)
            assert p['transport_injected'] is True and p['review_only'] is True
            assert p['limits']==asdict(LIMITS)


def test_bad_clock_before_request_prevents_network(tmp_path):
    a=create(tmp_path)
    out=run(a,lambda r:pytest.fail('clock invalid'),clock=lambda:dt.datetime(2026,9,18))
    assert out['counts']['attempted_this_run']==0 and len(out['storage_failures'])==24


def test_end_clock_regression_does_not_discard_response_bytes(tmp_path):
    a=create(tmp_path);n=[0]
    def clock():
        n[0]+=1
        # Per target: START, request-start, headers, END; END moves backwards.
        sec=([0,1,2,-1][(n[0]-1)%4])
        return dt.datetime(2026,9,18,tzinfo=dt.timezone.utc)+dt.timedelta(seconds=sec)
    run(a,clock=clock)
    p,b=a.read(a.keys[0],'END')
    assert b is not None and p['clock_status']!='OK' and p['finished_at'] is None


def test_end_insert_failure_rolls_back_new_blob_in_same_transaction(tmp_path):
    a=create(tmp_path)
    a.append(a.keys[0],'START',common(a,0,'START'))
    with sqlite3.connect(a.path) as c:
        c.execute("CREATE TRIGGER reject_end BEFORE INSERT ON receipts WHEN NEW.stage='END' BEGIN SELECT RAISE(ABORT,'test'); END")
    p=common(a,0,'END')|{'body_sha256':digest(b'abc')}
    with pytest.raises(sqlite3.IntegrityError):a.append(a.keys[0],'END',p,b'abc')
    with sqlite3.connect(a.path) as c:assert c.execute('SELECT count(*) FROM blobs').fetchone()[0]==0
    assert a.read(a.keys[0],'START') and a.read(a.keys[0],'END') is None


def test_failed_readback_is_not_counted_as_verified(tmp_path,monkeypatch):
    a=create(tmp_path);read=a.read
    def read_fail(key,stage):
        if stage=='END' and key==a.keys[0]:raise CaptureError('INJECTED_READBACK_FAIL')
        return read(key,stage)
    monkeypatch.setattr(a,'read',read_fail)
    out=run(a)
    assert out['counts']['end_persisted']==24 and out['counts']['readback_verified']==23
    assert out['storage_failures'][0]['stage']=='END'
