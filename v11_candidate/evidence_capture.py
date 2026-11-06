"""One bounded capture phase, isolated SQLite evidence, no prediction/runtime writes.

No scheduler or retention policy is installed. Production store selection is
OPEN. All archives made here are review-only. HTTP entity bytes are preserved
before any semantic parser runs. A stored 200 response is not verified content.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

import httpx
from .contracts import canonical


class CaptureError(ValueError):
    pass


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def stamp(clock) -> str:
    value = clock()
    if type(value) is not dt.datetime or value.tzinfo is None or value.utcoffset() is None:
        raise CaptureError('AWARE_CLOCK_REQUIRED')
    return value.astimezone(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class CaptureSpec:
    target_date: str
    race_no: int
    endpoint: str
    phase: str

    def __post_init__(self):
        if type(self.target_date) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', self.target_date):
            raise CaptureError('INVALID_DATE')
        try:
            dt.date.fromisoformat(self.target_date)
        except ValueError as exc:
            raise CaptureError('INVALID_DATE') from exc
        if type(self.race_no) is not int or not 1 <= self.race_no <= 12:
            raise CaptureError('INVALID_RACE')
        if type(self.endpoint) is not str or self.endpoint not in ('racelist', 'beforeinfo'):
            raise CaptureError('INVALID_ENDPOINT')
        if type(self.phase) is not str or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,47}', self.phase):
            raise CaptureError('INVALID_PHASE')

    @property
    def url(self):
        return ('https://www.boatrace.jp/owpc/pc/race/' + self.endpoint +
                '?hd=' + self.target_date.replace('-', '') + '&jcd=07&rno=' + str(self.race_no))


def full_day_phase(target_date: str, phase: str) -> tuple[CaptureSpec, ...]:
    """24 planned requests, not a claim that 12 races are being held or captured."""
    return tuple(CaptureSpec(target_date, r, endpoint, phase)
                 for r in range(1, 13) for endpoint in ('racelist', 'beforeinfo'))


@dataclass(frozen=True)
class CaptureLimits:
    max_body_bytes: int
    timeout_seconds: float

    def __post_init__(self):
        if type(self.max_body_bytes) is not int or not 1 <= self.max_body_bytes <= 2_000_000:
            raise CaptureError('INVALID_BODY_LIMIT')
        if type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60:
            raise CaptureError('INVALID_TIMEOUT')


class EvidenceArchive:
    """Exclusive new review DB. Never opens an existing production DB for writes.

    Blob/END insertion is one transaction. Existing bytes/receipts are checked,
    never replaced. Local fsync/SQLite are not a cloud durability guarantee.
    The DB is not signed; an actor able to rewrite it can recompute hashes.
    """
    def __init__(self, path: Path, specs: tuple[CaptureSpec, ...]):
        if (type(specs) is not tuple or len(specs) != 24 or
                any(type(s) is not CaptureSpec for s in specs) or
                specs != full_day_phase(specs[0].target_date, specs[0].phase)):
            raise CaptureError('EXPLICIT_FULL_DAY_PHASE_REQUIRED')
        self.path = Path(path).absolute()
        self.run_id = str(uuid.uuid4())
        self.specs = specs
        self.keys = tuple(digest(canonical({'run_id': self.run_id, **asdict(s)}).encode()) for s in specs)
        # No overwrite, symlink-follow or implicit parent directory creation.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        with closing(self._connect()) as conn, conn:
            conn.executescript('''
                CREATE TABLE meta(run_id TEXT PRIMARY KEY, schema_version INTEGER, review_only INTEGER);
                CREATE TABLE planned(k TEXT PRIMARY KEY, spec_json TEXT NOT NULL);
                CREATE TABLE blobs(h TEXT PRIMARY KEY, body BLOB NOT NULL);
                CREATE TABLE receipts(k TEXT NOT NULL, stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
                    PRIMARY KEY(k,stage), FOREIGN KEY(k) REFERENCES planned(k));
            ''')
            conn.execute('INSERT INTO meta VALUES(?,1,1)', (self.run_id,))
            conn.executemany('INSERT INTO planned VALUES(?,?)',
                             [(k, canonical(asdict(s))) for k, s in zip(self.keys, specs)])
        self._verify_plan()

    def _connect(self, readonly=False):
        conn = sqlite3.connect(self.path.as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True, timeout=5)
        conn.execute('PRAGMA foreign_keys=ON')
        if not readonly:
            conn.execute('PRAGMA synchronous=FULL')
        return conn

    def _verify_plan(self):
        with closing(self._connect(True)) as conn:
            meta = conn.execute('SELECT run_id,schema_version,review_only FROM meta').fetchall()
            plans = dict(conn.execute('SELECT k,spec_json FROM planned'))
        expected = {k: canonical(asdict(s)) for k, s in zip(self.keys, self.specs)}
        if meta != [(self.run_id, 1, 1)] or plans != expected:
            raise CaptureError('PLAN_READBACK_MISMATCH')

    def append(self, key: str, stage: str, payload: dict, body: bytes | None = None):
        if key not in self.keys or stage not in ('START', 'END') or type(payload) is not dict:
            raise CaptureError('INVALID_RECEIPT')
        spec = self.specs[self.keys.index(key)]
        if payload.get('run_id') != self.run_id or payload.get('key') != key or payload.get('stage') != stage or payload.get('spec') != asdict(spec):
            raise CaptureError('RECEIPT_CONTEXT_MISMATCH')
        if stage == 'START' and body is not None:
            raise CaptureError('START_HAS_BODY')
        if stage == 'END' and payload.get('body_sha256') != (digest(body) if body is not None else None):
            raise CaptureError('RECEIPT_BODY_MISMATCH')
        text = canonical(payload)
        h = digest(text.encode('utf-8'))
        with closing(self._connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            if stage == 'END' and conn.execute('SELECT 1 FROM receipts WHERE k=? AND stage="START"', (key,)).fetchone() is None:
                raise CaptureError('END_WITHOUT_START')
            prior = conn.execute('SELECT payload_json,payload_hash FROM receipts WHERE k=? AND stage=?', (key, stage)).fetchone()
            if prior is not None:
                if prior != (text, h):
                    raise CaptureError('RECEIPT_COLLISION')
                return
            if body is not None:
                old = conn.execute('SELECT body FROM blobs WHERE h=?', (digest(body),)).fetchone()
                if old is not None and old[0] != body:
                    raise CaptureError('BLOB_HASH_MISMATCH')
                if old is None:
                    conn.execute('INSERT INTO blobs VALUES(?,?)', (digest(body), body))
            conn.execute('INSERT INTO receipts VALUES(?,?,?,?)', (key, stage, text, h))

    def read(self, key: str, stage: str) -> tuple[dict, bytes | None] | None:
        self._verify_plan()
        with closing(self._connect(True)) as conn:
            row = conn.execute('SELECT payload_json,payload_hash FROM receipts WHERE k=? AND stage=?', (key, stage)).fetchone()
            if row is None:
                return None
            text, stored = row
            payload = json.loads(text)
            if canonical(payload) != text or digest(text.encode('utf-8')) != stored:
                raise CaptureError('RECEIPT_HASH_MISMATCH')
            if key not in self.keys or payload.get('key') != key or payload.get('stage') != stage or payload.get('run_id') != self.run_id or payload.get('spec') != asdict(self.specs[self.keys.index(key)]):
                raise CaptureError('RECEIPT_CONTEXT_MISMATCH')
            h = payload.get('body_sha256')
            blob = conn.execute('SELECT body FROM blobs WHERE h=?', (h,)).fetchone() if h else None
            if h and (blob is None or digest(blob[0]) != h):
                raise CaptureError('BLOB_READBACK_MISMATCH')
            return payload, blob[0] if blob is not None else None


HEADERS = ('content-type', 'content-length', 'content-encoding', 'date', 'last-modified', 'etag', 'cache-control')


def run_capture_phase(archive: EvidenceArchive, limits: CaptureLimits, *,
                      transport=None, network_enabled=False,
                      clock=lambda: dt.datetime.now(dt.timezone.utc), monotonic=time.monotonic) -> dict:
    """Sequential, one attempt per target. No automatic retries, no schedule.

    START precedes the network call; an unmatched START is not proof of receipt.
    Existing STARTs are not retried silently. Partial/error bodies remain evidence,
    never parser-eligible. HTTPX timeout is per operation, not total wall deadline.
    A trusted application supplies a transport for offline tests. No model input.
    """
    if type(network_enabled) is not bool or (transport is None and not network_enabled):
        raise CaptureError('NETWORK_NOT_AUTHORIZED')
    if type(limits) is not CaptureLimits:
        raise CaptureError('INVALID_LIMITS')
    counts = dict(planned=24, attempted_this_run=0, received_headers=0, http_200=0,
                  body_complete=0, body_persisted=0, end_persisted=0, readback_verified=0)
    failures, saved = [], []
    with httpx.Client(transport=transport, timeout=limits.timeout_seconds, trust_env=False,
                      follow_redirects=False, headers={'User-Agent': 'GamagoriEvidenceReview/1.1',
                      'Accept-Encoding': 'identity', 'Accept': 'text/html'}) as client:
        for key, spec in zip(archive.keys, archive.specs):
            common = {'run_id': archive.run_id, 'key': key, 'spec': asdict(spec),
                      'review_only': True, 'input_eligible': False, 'source_effective_at': None,
                      'transport_injected': transport is not None, 'limits': asdict(limits)}
            try:
                if archive.read(key, 'START') is not None:
                    failures.append({'key': key, 'stage': 'START', 'error': 'EXISTING_ATTEMPT_NOT_RETRIED'})
                    continue
                started = stamp(clock)
                archive.append(key, 'START', common | {'stage': 'START', 'started_at': started})
                archive.read(key, 'START')
            except Exception as exc:
                failures.append({'key': key, 'stage': 'START', 'error': type(exc).__name__})
                continue
            result = common | {'stage': 'END', 'started_at': started, 'requested_url': spec.url,
                      'http_status': None, 'response_url': None, 'headers': {}, 'received_at': None,
                      'body_complete': False, 'error': None, 'attempted': False,
                      'request_started_at': None,
                      'body_representation': 'HTTP_ENTITY_BYTES_CONTENT_ENCODING_RETAINED'}
            body, chunks, received = None, bytearray(), False
            begin = None
            try:
                begin = monotonic()
                result['request_started_at'] = stamp(clock)
                if dt.datetime.fromisoformat(result['request_started_at']) < dt.datetime.fromisoformat(started):
                    raise CaptureError('CLOCK_REGRESSION_BEFORE_REQUEST')
                client.cookies.clear()  # do not reuse Set-Cookie between public requests
                counts['attempted_this_run'] += 1
                result['attempted'] = True
                with client.stream('GET', spec.url) as response:
                    received = True
                    counts['received_headers'] += 1
                    counts['http_200'] += int(response.status_code == 200)
                    result.update(http_status=response.status_code, response_url=str(response.url),
                                  received_at=stamp(clock), headers={h: response.headers[h][:1024] for h in HEADERS if h in response.headers})
                    for chunk in response.iter_raw():
                        room = limits.max_body_bytes - len(chunks)
                        chunks.extend(chunk[:room])
                        if len(chunk) > room:
                            result['error'] = 'BODY_LIMIT_EXCEEDED'
                            break
                    else:
                        result['body_complete'] = True
            except Exception as exc:
                result['error'] = type(exc).__name__  # no cookies, credentials or raw exception strings
            if received:
                body = bytes(chunks)
            result['body_sha256'] = digest(body) if body is not None else None
            result['stored_body_bytes'] = len(body) if body is not None else 0
            try:
                finished = stamp(clock)
                duration = monotonic() - begin if begin is not None else None
                sequence = [result[k] for k in ('started_at', 'request_started_at', 'received_at') if result[k] is not None] + [finished]
                times = [dt.datetime.fromisoformat(v) for v in sequence]
                if times != sorted(times) or duration is None or not math.isfinite(duration) or duration < 0:
                    raise CaptureError('CLOCK_REGRESSION')
                result.update(finished_at=finished, elapsed_seconds=duration, clock_status='OK')
            except Exception as exc:
                result.update(finished_at=None, elapsed_seconds=None, clock_status=type(exc).__name__)
            counts['body_complete'] += int(result['body_complete'])
            try:
                archive.append(key, 'END', result, body)
                counts['end_persisted'] += 1
                counts['body_persisted'] += int(body is not None)
                loaded, read_body = archive.read(key, 'END')
                if loaded != result or read_body != body:
                    raise CaptureError('END_READBACK_DIFFERENCE')
                counts['readback_verified'] += 1
                saved.append(key)
            except Exception as exc:
                failures.append({'key': key, 'stage': 'END', 'error': type(exc).__name__})
    return {'run_id': archive.run_id, 'counts': counts, 'storage_failures': failures,
            'verified_keys': saved, 'review_only': True, 'semantic_validation': 'NOT_RUN',
            'production_recovery_proven': False, 'transport_injected': transport is not None,
            'limits': asdict(limits)}


def review_saved_beforeinfo(archive: EvidenceArchive, key: str) -> dict:
    """Both parsers consume one independently read-back body; no readiness claim."""
    from .observation import parse_beforeinfo_observation
    from .withdrawal_observation import scan_withdrawal_text
    loaded = archive.read(key, 'END')
    if loaded is None:
        raise CaptureError('SAVED_RESPONSE_MISSING')
    receipt, body = loaded
    headers = receipt['headers']
    if (receipt['spec']['endpoint'] != 'beforeinfo' or not receipt['body_complete'] or
            receipt['error'] is not None or receipt['http_status'] != 200 or body is None or
            headers.get('content-type', '').split(';')[0].strip().lower() != 'text/html' or
            headers.get('content-encoding', 'identity').lower() != 'identity'):
        raise CaptureError('BODY_NOT_ELIGIBLE_FOR_REVIEW_PARSE')
    output = {'body_sha256': digest(body), 'key': key, 'input_eligible': False}
    for name, operation in (
            ('observation', lambda: parse_beforeinfo_observation(body.decode('utf-8', errors='strict'))),
            ('withdrawal', lambda: scan_withdrawal_text(body))):
        try:
            output[name] = asdict(operation())
        except Exception as exc:
            output[name] = {'error': type(exc).__name__}
    return output
