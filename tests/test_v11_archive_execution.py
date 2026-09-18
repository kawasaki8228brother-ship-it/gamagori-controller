"""Local ledger/state tests. Synthetic source data, no scheduler or real GETs."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import datetime as dt
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from test_v11_postrace_completion import snap
from v11_candidate.archive_execution import ArchiveExecutionLedger, LedgerError, sha
from v11_candidate.contracts import canonical
from v11_candidate.evidence_capture import EvidenceArchive, full_day_phase, run_capture_phase, CaptureLimits

DAY='2026-09-18'
NOW=dt.datetime(2026,9,19,10,tzinfo=dt.timezone.utc)
LATER=NOW+dt.timedelta(seconds=20)


@pytest.fixture(scope='module')
def sources():return tuple(snap(i) for i in range(1,13))


def ledger(tmp_path):return ArchiveExecutionLedger(tmp_path/'ledger.sqlite',create=True)


def claim(led,sources):
    d=led.register_decision(DAY,sources,now=NOW)
    return led.claim(d,now=NOW)


def captured(tmp_path,handler=None,clock=None):
    archive=EvidenceArchive(tmp_path/'capture.sqlite',full_day_phase(DAY,'POSTDAY_TEST'))
    def default(r):
        return httpx.Response(200,headers={'content-type':'text/html'},stream=httpx.ByteStream(b'test raw body only'))
    run_capture_phase(archive,CaptureLimits(10_000,1),transport=httpx.MockTransport(handler or default),
                      clock=clock or (lambda:NOW+dt.timedelta(seconds=10)))
    return archive


def modify(path,sql,params=()):
    with sqlite3.connect(path) as c:c.execute(sql,params)


def test_complete_decision_keeps_full_proofs_and_reloads_after_restart(tmp_path,sources):
    l=ledger(tmp_path);d=l.register_decision(DAY,sources,now=NOW)
    before=l.read_decision(d)
    again=ArchiveExecutionLedger(l.path).read_decision(d)
    assert before==again and len(again['assessment']['result_publications'])==12
    assert again['assessment']['result_publications'][0]['body_sha256']==sources[0].body_sha256
    assert again['assessment']['binding_sha256']!=d
    assert again['assessment']['scheduler_started'] is False


@pytest.mark.parametrize('count',[0,1,11])
def test_incomplete_evidence_stored_without_creating_claim(tmp_path,sources,count):
    l=ledger(tmp_path);d=l.register_decision(DAY,sources[:count],now=NOW)
    assert l.read_decision(d)['assessment']['state']=='UNVERIFIED'
    assert l.claim(d,now=NOW).state=='NOT_ELIGIBLE'
    with sqlite3.connect(l.path) as c:
        assert c.execute('SELECT count(*) FROM blobs').fetchone()[0]==count
        assert c.execute('SELECT count(*) FROM jobs').fetchone()[0]==0


@pytest.mark.parametrize('kw',[
    {'body_sha256':'0'*64},{'body':b'unknown source layout'},
    {'response_url':'https://evil.example'},{'body_complete':False},{'http_status':503}])
def test_bad_or_unknown_result_preserved_but_not_claimed(tmp_path,sources,kw):
    l=ledger(tmp_path);s=(replace(sources[0],**kw),)+sources[1:]
    d=l.register_decision(DAY,s,now=NOW)
    assert l.claim(d,now=NOW).created is False
    with sqlite3.connect(l.path) as c:
        assert c.execute('SELECT body FROM blobs WHERE h=?',(sha(s[0].body),)).fetchone()[0]==s[0].body


def test_duplicate_result_slots_keep_raw_evidence_and_explicit_error(tmp_path,sources):
    l=ledger(tmp_path);d=l.register_decision(DAY,(sources[0],sources[0]),now=NOW)
    r=l.read_decision(d)['assessment']
    assert r['state']=='FAIL' and 'DUPLICATE' in r['assessment_error']
    assert not l.claim(d,now=NOW).created


def test_new_assessment_time_does_not_create_second_job(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources)
    new=l.register_decision(DAY,sources,now=LATER)
    b=l.claim(new,now=LATER)
    assert a.created and not b.created and b.owner_token is None
    assert b.work_key==a.work_key and b.decision_hash==a.decision_hash
    assert new!=a.decision_hash


def test_no_automatic_expiry_or_restart_of_running_claim(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources)
    reopened=ArchiveExecutionLedger(l.path)
    b=reopened.claim(a.decision_hash,now=NOW+dt.timedelta(days=100))
    assert b.state=='RUNNING' and not b.created


def test_three_concurrent_connections_only_one_claim_owner(tmp_path,sources):
    l=ledger(tmp_path);d=l.register_decision(DAY,sources,now=NOW)
    def attempt(_):return ArchiveExecutionLedger(l.path).claim(d,now=NOW)
    with ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(attempt,range(3)))
    assert sum(x.created for x in r)==1
    assert len({x.work_key for x in r})==1
    assert sum(x.owner_token is not None for x in r)==1


@pytest.mark.parametrize('token',[None,'','0'*32,'abc',123])
def test_wrong_owner_never_terminates_running_claim(tmp_path,sources,token):
    l=ledger(tmp_path);a=claim(l,sources)
    with pytest.raises(LedgerError,match='OWNER'):
        l.fail(a.work_key,token,'MANUAL_TEST_ABORT',now=LATER)
    assert l.inspect(a.work_key)['event']['state']=='RUNNING'


def test_owner_abort_keeps_original_claim_and_never_implicitly_retries(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources)
    done=l.fail(a.work_key,a.owner_token,'TEST_ABORT',now=LATER)
    assert done['event']['state']=='FAILED' and done['event']['sequence']==2
    assert done['event']['previous'] is not None
    assert not l.claim(a.decision_hash,now=LATER).created
    with pytest.raises(LedgerError,match='TERMINAL'):
        l.fail(a.work_key,a.owner_token,'AGAIN',now=LATER)


@pytest.mark.parametrize('when',[NOW-dt.timedelta(seconds=1),dt.datetime(2026,9,19)])
def test_claim_rejects_earlier_or_naive_clock(tmp_path,sources,when):
    l=ledger(tmp_path);d=l.register_decision(DAY,sources,now=NOW)
    with pytest.raises(LedgerError):l.claim(d,now=when)


def test_new_store_does_not_overwrite_old_file(tmp_path):
    p=tmp_path/'existing';p.write_bytes(b'do not modify')
    with pytest.raises(FileExistsError):ArchiveExecutionLedger(p,create=True)
    assert p.read_bytes()==b'do not modify'


def test_wrong_existing_database_rejected(tmp_path):
    p=tmp_path/'old'
    with sqlite3.connect(p) as c:c.execute('CREATE TABLE meta(name,value)');c.execute("INSERT INTO meta VALUES('type','PRODUCTION')")
    with pytest.raises(LedgerError):ArchiveExecutionLedger(p)


def test_symlink_store_rejected(tmp_path):
    p=tmp_path/'old';p.write_bytes(b'no')
    s=tmp_path/'link';s.symlink_to(p)
    with pytest.raises(LedgerError):ArchiveExecutionLedger(s,create=True)


@pytest.mark.parametrize('which',['object','body','missing_body'])
def test_stored_result_graph_corruption_detected(tmp_path,sources,which):
    l=ledger(tmp_path);d=l.register_decision(DAY,sources,now=NOW)
    if which=='object':modify(l.path,'UPDATE objects SET json=? WHERE h=?',('{}',d))
    elif which=='body':modify(l.path,'UPDATE blobs SET body=?',(b'corrupt',))
    else:modify(l.path,'DELETE FROM blobs')
    with pytest.raises(LedgerError):l.read_decision(d)
    with pytest.raises(LedgerError):l.claim(d,now=NOW)


def test_complete_capture_retains_12_basis_and_24_output_targets(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path)
    original=sha(c.path.read_bytes())
    done=l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert sha(c.path.read_bytes())==original
    assert done['event']['state']=='COMPLETE'
    assert done['capture']['counts']==dict(planned=24,starts=24,ends=24,bodies=24,complete_http200=24,injected_ends=24)
    assert done['capture']['decision_basis']==a.decision_hash
    assert len(done['decision']['assessment']['result_publications'])==12
    assert done['decision']['assessment']['scheduler_started'] is False
    assert len(done['capture']['targets'])==24
    assert done['capture']['role']=='POST_DECISION_CAPTURE_OUTPUT_NOT_DECISION_BASIS'
    # New connection/reopened process boundary can still trace the graph.
    assert ArchiveExecutionLedger(l.path).inspect(a.work_key)==done


def test_one_failed_half_pair_preserves_other_23_and_records_partial(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources)
    def handler(r):
        fail=r.url.params['rno']=='1' and r.url.path.endswith('racelist')
        return httpx.Response(503 if fail else 200,stream=httpx.ByteStream(b'raw error' if fail else b'ok'))
    c=captured(tmp_path,handler)
    done=l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert done['event']['state']=='PARTIAL'
    assert done['capture']['counts']['complete_http200']==23
    assert done['capture']['counts']['ends']==24
    assert not l.claim(a.decision_hash,now=LATER).created


def test_planned_but_unstarted_archive_never_counts_as_complete(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources)
    c=EvidenceArchive(tmp_path/'empty',full_day_phase(DAY,'TEST'))
    done=l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert done['event']['state']=='FAILED'
    assert done['capture']['counts']['planned']==24 and done['capture']['counts']['ends']==0


def test_interrupted_archive_leaves_unmatched_start_visible(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path)
    modify(c.path,'DELETE FROM receipts WHERE k=? AND stage="END"',(c.keys[0],))
    done=l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert done['event']['state']=='PARTIAL'
    assert done['capture']['counts']['starts']==24 and done['capture']['counts']['ends']==23


@pytest.mark.parametrize('which',['body','receipt_hash','missing_start','plan_date','wrong_meta'])
def test_corrupt_capture_rejected_atomically_and_claim_stays_running(tmp_path,sources,which):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path)
    if which=='body':modify(c.path,'UPDATE blobs SET body=?',(b'wrong',))
    elif which=='receipt_hash':modify(c.path,'UPDATE receipts SET payload_hash=?',('0'*64,))
    elif which=='missing_start':modify(c.path,'DELETE FROM receipts WHERE k=? AND stage="START"',(c.keys[0],))
    elif which=='plan_date':modify(c.path,'UPDATE planned SET spec_json=replace(spec_json,?,?)',('2026-09-18','2026-09-17'))
    else:modify(c.path,'UPDATE meta SET review_only=0')
    with sqlite3.connect(l.path) as db:n=db.execute('SELECT count(*) FROM objects').fetchone()[0]
    with pytest.raises(LedgerError):l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert l.inspect(a.work_key)['event']['state']=='RUNNING'
    with sqlite3.connect(l.path) as db:assert db.execute('SELECT count(*) FROM objects').fetchone()[0]==n


@pytest.mark.parametrize('capture_time',[NOW-dt.timedelta(seconds=1),LATER+dt.timedelta(seconds=1)])
def test_old_or_future_capture_cannot_be_passed_as_this_execution(tmp_path,sources,capture_time):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path,clock=lambda:capture_time)
    with pytest.raises(LedgerError):l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    assert l.inspect(a.work_key)['event']['state']=='RUNNING'


def test_output_corruption_detected_on_later_readback(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path)
    done=l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    modify(l.path,'UPDATE objects SET json=? WHERE h=?',('{}',done['event']['capture_manifest']))
    with pytest.raises(LedgerError):l.inspect(a.work_key)


def test_complete_claim_cannot_be_finished_twice(tmp_path,sources):
    l=ledger(tmp_path);a=claim(l,sources);c=captured(tmp_path)
    l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)
    with pytest.raises(LedgerError,match='TERMINAL'):
        l.finish_from_archive(a.work_key,a.owner_token,c.path,now=LATER)


def test_exception_in_assessor_does_not_erase_committed_raw_inputs(tmp_path,sources,monkeypatch):
    l=ledger(tmp_path)
    import v11_candidate.archive_execution as module
    def broken(*a,**k):raise RuntimeError('simulated code bug')
    monkeypatch.setattr(module.completion,'assess_postrace_day',broken)
    with pytest.raises(RuntimeError):l.register_decision(DAY,sources,now=NOW)
    with sqlite3.connect(l.path) as c:
        assert c.execute('SELECT count(*) FROM blobs').fetchone()[0]==12
        assert c.execute('SELECT count(*) FROM jobs').fetchone()[0]==0
