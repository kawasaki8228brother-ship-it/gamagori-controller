"""Review-only provenance ledger and one-claim-per-day archive state.

No scheduler, network, lease expiry, implicit retry, retention or production
store. Result pages are DECISION BASIS; later racelist/beforeinfo responses are
CAPTURE OUTPUT, not retroactive basis for the earlier decision. Hashes bind
stored associations, not source truth, freshness, power-loss or authorization.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

from .contracts import canonical
from .evidence_capture import full_day_phase
from .participant_evidence import RaceIdentity
from . import postrace_completion as completion


class LedgerError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _time(now: dt.datetime) -> str:
    if type(now) is not dt.datetime or now.utcoffset() is None:
        raise LedgerError('AWARE_TIME_REQUIRED')
    return now.astimezone(dt.timezone.utc).isoformat()


def _parse_time(raw: str) -> dt.datetime:
    try:
        value = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
        _time(value)
        return value
    except (TypeError, AttributeError, ValueError) as exc:
        raise LedgerError('INVALID_TIME') from exc


def _assessment(day, snapshots, now):
    try:
        return completion.assess_postrace_day(day, snapshots, now=now)
    except completion.CompletionError as exc:
        out = dict(policy_id='ALL12_RESULT_PUBLICATIONS_V1_CANDIDATE',
                   target_date=day, decision_at=now.isoformat(), state='FAIL',
                   archive_input_eligible=False, result_publications=[],
                   assessment_error=str(exc), scheduler_started=False)
        out['binding_sha256'] = sha(canonical(out).encode('utf-8'))
        return out


def _version() -> str:
    return sha(Path(completion.__file__).read_bytes())


@dataclass(frozen=True)
class Claim:
    work_key: str
    state: str
    created: bool
    decision_hash: str
    owner_token: str | None = None


class ArchiveExecutionLedger:
    """A NEW review database or an explicitly recognized existing review store.

    Transactional claims coordinate callers of this API using the SAME SQLite
    database. They do not stop bypassing workers or other database copies. A
    RUNNING claim never expires automatically: an interrupted owner remains
    visible, and cannot silently be replaced by a second collector.
    """
    def __init__(self, path: Path, *, create: bool = False):
        if type(create) is not bool:
            raise LedgerError('INVALID_CREATE_FLAG')
        self.path = Path(path).absolute()
        if self.path.is_symlink():
            raise LedgerError('SYMLINK_STORE_REJECTED')
        if create:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            with closing(self._connect()) as conn, conn:
                conn.executescript('''
                    CREATE TABLE meta(name TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT INTO meta VALUES('type','GAMAGORI_REVIEW_EXECUTION_V1');
                    CREATE TABLE blobs(h TEXT PRIMARY KEY, body BLOB NOT NULL);
                    CREATE TABLE objects(h TEXT PRIMARY KEY, json TEXT NOT NULL);
                    CREATE TABLE jobs(k TEXT PRIMARY KEY, head TEXT NOT NULL,
                        FOREIGN KEY(head) REFERENCES objects(h));
                ''')
        with closing(self._connect(True)) as conn:
            if conn.execute('SELECT name,value FROM meta').fetchall() != [('type','GAMAGORI_REVIEW_EXECUTION_V1')]:
                raise LedgerError('UNRECOGNIZED_REVIEW_STORE')

    def _connect(self, readonly=False):
        conn = sqlite3.connect(self.path.as_uri() + ('?mode=ro' if readonly else '?mode=rw'),
                               uri=True, timeout=5)
        conn.execute('PRAGMA foreign_keys=ON')
        if not readonly:
            conn.execute('PRAGMA synchronous=FULL')
        return conn

    @staticmethod
    def _put(conn, value: dict) -> str:
        text = canonical(value)
        h = sha(text.encode('utf-8'))
        previous = conn.execute('SELECT json FROM objects WHERE h=?', (h,)).fetchone()
        if previous is not None and previous[0] != text:
            raise LedgerError('OBJECT_HASH_COLLISION')
        conn.execute('INSERT OR IGNORE INTO objects VALUES(?,?)', (h,text))
        return h

    @staticmethod
    def _get(conn, h: str, kind: str) -> dict:
        row = conn.execute('SELECT json FROM objects WHERE h=?', (h,)).fetchone()
        if row is None:
            raise LedgerError('OBJECT_MISSING')
        value = json.loads(row[0])
        if (type(value) is not dict or canonical(value) != row[0] or
                sha(row[0].encode('utf-8')) != h or value.get('kind') != kind):
            raise LedgerError('OBJECT_HASH_OR_KIND_MISMATCH')
        return value

    @staticmethod
    def _body(conn, body: bytes) -> str:
        if type(body) is not bytes or len(body) > 2_000_000:
            raise LedgerError('BODY_TYPE_OR_SIZE')
        h = sha(body)
        row = conn.execute('SELECT body FROM blobs WHERE h=?', (h,)).fetchone()
        if row is not None and row[0] != body:
            raise LedgerError('BLOB_HASH_COLLISION')
        conn.execute('INSERT OR IGNORE INTO blobs VALUES(?,?)', (h,body))
        return h

    @staticmethod
    def _read_body(conn, h: str) -> bytes:
        row = conn.execute('SELECT body FROM blobs WHERE h=?', (h,)).fetchone()
        if row is None or sha(row[0]) != h:
            raise LedgerError('BLOB_MISSING_OR_CORRUPT')
        return row[0]

    def register_decision(self, day: str, snapshots: tuple[completion.ResultSnapshot,...],
                          *, now: dt.datetime) -> str:
        """Commit input bytes first; store the complete derived assessment next."""
        RaceIdentity(day,'07',1)
        at = _time(now)
        if (type(snapshots) is not tuple or len(snapshots)>12 or
                any(type(s) is not completion.ResultSnapshot for s in snapshots)):
            raise LedgerError('INVALID_RESULT_INPUTS')
        refs=[]
        with closing(self._connect()) as conn, conn:
            for s in snapshots:
                meta=asdict(s); body=meta.pop('body')
                body_hash=self._body(conn,body)
                refs.append(self._put(conn,dict(kind='RESULT_SNAPSHOT',metadata=meta,
                         stored_body_sha256=body_hash,provenance='CALLER_SUPPLIED_METADATA')))
            batch_hash=self._put(conn,dict(kind='RESULT_INPUT_BATCH',target_date=day,
                                      recorded_at=at,snapshots=refs))
        # A parser failure cannot roll back the already committed raw input.
        result=_assessment(day,snapshots,dt.datetime.fromisoformat(at))
        record=dict(kind='COMPLETION_DECISION',schema_version=1,review_only=True,
                    input_batch=batch_hash,assessment=result,assessment_code_sha256=_version())
        with closing(self._connect()) as conn, conn:
            h=self._put(conn,record)
        self.read_decision(h)
        return h

    def _decision(self, conn, h):
        decision=self._get(conn,h,'COMPLETION_DECISION')
        if decision['assessment_code_sha256'] != _version():
            raise LedgerError('ASSESSMENT_CODE_VERSION_UNSUPPORTED')
        batch=self._get(conn,decision['input_batch'],'RESULT_INPUT_BATCH')
        snapshots=[]
        for ref in batch['snapshots']:
            record=self._get(conn,ref,'RESULT_SNAPSHOT')
            body=self._read_body(conn,record['stored_body_sha256'])
            snapshots.append(completion.ResultSnapshot(**record['metadata'],body=body))
        expected=_assessment(batch['target_date'],tuple(snapshots),_parse_time(batch['recorded_at']))
        if canonical(decision['assessment']) != canonical(expected):
            raise LedgerError('ASSESSMENT_RECONSTRUCTION_MISMATCH')
        return decision,batch

    def read_decision(self, h: str) -> dict:
        with closing(self._connect(True)) as conn:
            conn.execute('BEGIN')
            decision,_=self._decision(conn,h)
            return decision

    def _job(self, conn, key):
        row=conn.execute('SELECT head FROM jobs WHERE k=?',(key,)).fetchone()
        if row is None:
            return None
        head=self._get(conn,row[0],'EXECUTION_EVENT')
        if head['work_key']!=key:
            raise LedgerError('JOB_CONTEXT_MISMATCH')
        initial=head
        if head['state']!='RUNNING':
            initial=self._get(conn,head['previous'],'EXECUTION_EVENT')
            if (head['state'] not in ('COMPLETE','PARTIAL','FAILED') or
                    head['sequence']!=2 or initial['state']!='RUNNING' or
                    any(head[k]!=initial[k] for k in ('work_key','decision_hash','owner_hash')) or
                    _parse_time(head['at'])<_parse_time(initial['at'])):
                raise LedgerError('INVALID_EVENT_CHAIN')
        if initial['sequence']!=1 or initial['previous'] is not None or initial['state']!='RUNNING':
            raise LedgerError('INVALID_INITIAL_CLAIM')
        decision,_=self._decision(conn,head['decision_hash'])
        expected=sha(canonical(dict(day=decision['assessment']['target_date'],venue='07',
                     phase='POSTRACE_ARCHIVE',policy=decision['assessment']['policy_id'])).encode())
        if expected!=key or decision['assessment']['archive_input_eligible'] is not True:
            raise LedgerError('JOB_BASIS_MISMATCH')
        return row[0],head

    def claim(self, decision_hash: str, *, now: dt.datetime) -> Claim:
        at=_time(now)
        with closing(self._connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            decision,batch=self._decision(conn,decision_hash)
            if _parse_time(at)<_parse_time(batch['recorded_at']):
                raise LedgerError('CLAIM_BEFORE_DECISION')
            a=decision['assessment']
            key=sha(canonical(dict(day=a['target_date'],venue='07',phase='POSTRACE_ARCHIVE',policy=a['policy_id'])).encode())
            existing=self._job(conn,key)
            if existing:
                # A new decision/time/hash cannot silently authorize a new run.
                return Claim(key,existing[1]['state'],False,existing[1]['decision_hash'])
            if a['archive_input_eligible'] is not True:
                return Claim(key,'NOT_ELIGIBLE',False,decision_hash)
            token=uuid.uuid4().hex
            event=dict(kind='EXECUTION_EVENT',work_key=key,decision_hash=decision_hash,
                       owner_hash=sha(token.encode()),state='RUNNING',sequence=1,
                       previous=None,at=at,capture_manifest=None,reason=None)
            head=self._put(conn,event)
            conn.execute('INSERT INTO jobs VALUES(?,?)',(key,head))
        self.inspect(key)
        return Claim(key,'RUNNING',True,decision_hash,token)

    def inspect(self, key: str) -> dict | None:
        with closing(self._connect(True)) as conn:
            conn.execute('BEGIN')
            result=self._job(conn,key)
            if result is None:return None
            h,event=result
            decision,_=self._decision(conn,event['decision_hash'])
            capture=self._get(conn,event['capture_manifest'],'CAPTURE_MANIFEST') if event['capture_manifest'] else None
            if capture:
                self._verify_capture(conn,capture,event)
            return dict(work_key=key,event_hash=h,event=event,decision=decision,capture=capture)

    @staticmethod
    def _owner(event, token, at):
        if type(token) is not str or not re.fullmatch('[0-9a-f]{32}',token) or sha(token.encode())!=event['owner_hash']:
            raise LedgerError('CLAIM_OWNER_MISMATCH')
        if event['state']!='RUNNING':raise LedgerError('CLAIM_ALREADY_TERMINAL')
        if _parse_time(at)<_parse_time(event['at']):raise LedgerError('CLOCK_REGRESSION')

    def fail(self, key: str, token: str, reason: str, *, now: dt.datetime) -> dict:
        """Explicit owner abort, not automatic retry or silent claim expiry."""
        if type(reason) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,79}',reason):
            raise LedgerError('INVALID_FAILURE_REASON')
        at=_time(now)
        with closing(self._connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            result=self._job(conn,key)
            if result is None:raise LedgerError('CLAIM_MISSING')
            previous,event=result;self._owner(event,token,at)
            event=event|dict(state='FAILED',sequence=2,previous=previous,at=at,reason=reason)
            head=self._put(conn,event)
            conn.execute('UPDATE jobs SET head=? WHERE k=?',(head,key))
        return self.inspect(key)

    def finish_from_archive(self, key: str, token: str, path: Path, *, now: dt.datetime) -> dict:
        """Import one completed/partial Stage12 REVIEW archive, never modify it.

        No caller success flag is accepted. All24 planned targets and original
        START/END receipts remain linked. Corruption is rejected and leaves the
        claim RUNNING; a valid partial archive records a terminal PARTIAL state.
        """
        at=_time(now)
        path=Path(path).absolute()
        if path.is_symlink() or path==self.path or not path.is_file():
            raise LedgerError('INVALID_CAPTURE_ARCHIVE')
        with closing(self._connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            result=self._job(conn,key)
            if result is None:raise LedgerError('CLAIM_MISSING')
            previous,event=result;self._owner(event,token,at)
            decision,_=self._decision(conn,event['decision_hash'])
            day=decision['assessment']['target_date']
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)) as source:
                source.execute('BEGIN')
                if source.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or source.execute('PRAGMA foreign_key_check').fetchall():
                    raise LedgerError('SOURCE_DB_INTEGRITY')
                meta=source.execute('SELECT run_id,schema_version,review_only FROM meta').fetchall()
                if len(meta)!=1 or meta[0][1:]!=(1,1):raise LedgerError('SOURCE_META')
                run_id=meta[0][0]
                plans=dict(source.execute('SELECT k,spec_json FROM planned'))
                if len(plans)!=24:raise LedgerError('SOURCE_PLAN_COUNT')
                specs=[json.loads(v) for v in plans.values()]
                phase=specs[0]['phase']
                expected={sha(canonical(dict(run_id=run_id,**asdict(s))).encode()):canonical(asdict(s))
                          for s in full_day_phase(day,phase)}
                if plans!=expected:raise LedgerError('SOURCE_PLAN_CONTEXT')
                all_rows=source.execute('SELECT k,stage,payload_json,payload_hash FROM receipts').fetchall()
                if any(k not in plans or stage not in ('START','END') for k,stage,_,_ in all_rows):
                    raise LedgerError('SOURCE_RECEIPT_CONTEXT')
                rows={(k,stage):(text,h) for k,stage,text,h in all_rows}
                if len(rows)!=len(all_rows):raise LedgerError('SOURCE_DUPLICATE_RECEIPT')
                outputs=[]
                for k,text in sorted(plans.items()):
                    spec=json.loads(text); refs={}; body_hash=None
                    for stage in ('START','END'):
                        record=rows.get((k,stage))
                        if record is None:continue
                        raw,h=record;p=json.loads(raw)
                        if canonical(p)!=raw or sha(raw.encode())!=h:raise LedgerError('SOURCE_RECEIPT_HASH')
                        if any(p.get(n)!=v for n,v in (('key',k),('run_id',run_id),('stage',stage),('spec',spec))):
                            raise LedgerError('SOURCE_RECEIPT_CONTEXT')
                        if (p.get('review_only') is not True or p.get('input_eligible') is not False or
                                type(p.get('transport_injected')) is not bool):raise LedgerError('SOURCE_FLAGS')
                        if not _parse_time(event['at'])<=_parse_time(p['started_at'])<=_parse_time(at):
                            raise LedgerError('CAPTURE_OUTSIDE_CLAIM_TIME')
                        if stage=='END':
                            if 'START' not in refs:raise LedgerError('SOURCE_END_WITHOUT_START')
                            start=self._get(conn,refs['START'],'CAPTURE_RECEIPT')['original_payload']
                            if (p['started_at']!=start['started_at'] or p['transport_injected']!=start['transport_injected'] or
                                    p.get('requested_url')!=full_day_phase(day,phase)[2*(spec['race_no']-1)+(spec['endpoint']=='beforeinfo')].url):
                                raise LedgerError('SOURCE_START_END_CONFLICT')
                            if p.get('finished_at') is not None and not _parse_time(p['started_at'])<=_parse_time(p['finished_at'])<=_parse_time(at):
                                raise LedgerError('CAPTURE_FINISH_TIME')
                            body_hash=p.get('body_sha256')
                            if body_hash is not None:
                                blob=source.execute('SELECT body FROM blobs WHERE h=?',(body_hash,)).fetchone()
                                if blob is None or sha(blob[0])!=body_hash:raise LedgerError('SOURCE_BODY_HASH')
                                if p.get('stored_body_bytes') != len(blob[0]):raise LedgerError('SOURCE_BODY_LENGTH')
                                self._body(conn,blob[0])
                        refs[stage]=self._put(conn,dict(kind='CAPTURE_RECEIPT',original_payload=p,
                                         original_payload_sha256=h,body_sha256=body_hash if stage=='END' else None))
                    outputs.append(dict(source_key=k,spec=spec,receipt_refs=refs))
            manifest=dict(kind='CAPTURE_MANIFEST',schema_version=1,decision_basis=event['decision_hash'],
                   work_key=key,source_run_id=run_id,imported_at=at,targets=outputs,
                   role='POST_DECISION_CAPTURE_OUTPUT_NOT_DECISION_BASIS',review_only=True)
            counts=self._verify_capture(conn,manifest,event)
            manifest['counts']=counts
            m=self._put(conn,manifest)
            status='COMPLETE' if counts['complete_http200']==24 else 'PARTIAL' if counts['ends'] else 'FAILED'
            event=event|dict(state=status,sequence=2,previous=previous,at=at,capture_manifest=m,
                            reason=None if status=='COMPLETE' else 'CAPTURE_INCOMPLETE')
            head=self._put(conn,event)
            conn.execute('UPDATE jobs SET head=? WHERE k=?',(head,key))
        return self.inspect(key)

    def _verify_capture(self,conn,manifest,event):
        if manifest['decision_basis']!=event['decision_hash'] or manifest['work_key']!=event['work_key']:
            raise LedgerError('CAPTURE_BINDING_MISMATCH')
        decision,_=self._decision(conn,event['decision_hash'])
        day=decision['assessment']['target_date']
        targets=manifest['targets']
        if len(targets)!=24:raise LedgerError('CAPTURE_TARGET_COUNT')
        expected={canonical(asdict(s)) for s in full_day_phase(day,targets[0]['spec']['phase'])}
        if {canonical(t['spec']) for t in targets}!=expected:raise LedgerError('CAPTURE_TARGET_SCOPE')
        counts=dict(planned=len(targets),starts=0,ends=0,bodies=0,complete_http200=0,injected_ends=0)
        for target in manifest['targets']:
            for stage,h in target['receipt_refs'].items():
                record=self._get(conn,h,'CAPTURE_RECEIPT');p=record['original_payload']
                if (sha(canonical(p).encode())!=record['original_payload_sha256'] or p['spec']!=target['spec'] or
                        p['key']!=target['source_key'] or p['stage']!=stage or p['run_id']!=manifest['source_run_id']):
                    raise LedgerError('CAPTURE_RECEIPT_BINDING')
                counts['starts' if stage=='START' else 'ends']+=1
                if stage=='END':
                    bh=record['body_sha256']
                    if bh!=p.get('body_sha256'):raise LedgerError('CAPTURE_BODY_BINDING')
                    body=self._read_body(conn,bh) if bh else None
                    counts['bodies']+=int(body is not None)
                    counts['injected_ends']+=int(p['transport_injected'])
                    counts['complete_http200']+=int(body is not None and p.get('http_status')==200 and
                        p.get('body_complete') is True and p.get('error') is None and p.get('clock_status')=='OK' and
                        p.get('requested_url')==p.get('response_url'))
        if 'counts' in manifest and manifest['counts']!=counts:raise LedgerError('CAPTURE_COUNTS_MISMATCH')
        if event['state']!='RUNNING':
            expected_state='COMPLETE' if counts['complete_http200']==24 else 'PARTIAL' if counts['ends'] else 'FAILED'
            if event['state']!=expected_state:raise LedgerError('CAPTURE_STATE_COUNTS_MISMATCH')
        return counts
