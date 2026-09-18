"""Pure guards for prospective integration, not a database permission system."""
from __future__ import annotations
import datetime as dt
import copy
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any
from urllib.parse import urlparse, parse_qs


class ContractError(ValueError):
    pass


class SourceStatus(str, Enum):
    SOURCE_ACQUIRED_NO_CHANGE = 'SOURCE_ACQUIRED_NO_CHANGE'
    SOURCE_ACQUIRED_REVISION_TRIGGER = 'SOURCE_ACQUIRED_REVISION_TRIGGER'
    SOURCE_NOT_PUBLISHED = 'SOURCE_NOT_PUBLISHED'
    SOURCE_FETCH_FAILED = 'SOURCE_FETCH_FAILED'
    SOURCE_PARSE_FAILED = 'SOURCE_PARSE_FAILED'


def canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(payload: dict) -> str:
    return hashlib.sha256(canonical(payload).encode('utf-8')).hexdigest()


def aware(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ContractError('INVALID_TIMESTAMP') from exc
    if parsed.tzinfo is None:
        raise ContractError('NAIVE_TIMESTAMP')
    return parsed


def verify_prediction_times(observed: str, ingested: str, deadline: str) -> None:
    o, i, d = map(aware, [observed, ingested, deadline])
    if not o <= i < d:
        raise ContractError('INVALID_PREDICTION_TIME_ORDER')


@dataclass(frozen=True)
class DeadlineSnapshot:
    target_date: str
    scheduled_deadline: str
    official_deadline_observed: str | None
    acquired_at: str
    source_url: str
    live_state_consistent: bool

    def allow_revision(self, now: str, reserve_seconds: float) -> bool:
        if type(self.live_state_consistent) is not bool:
            raise ContractError('INVALID_LIVE_STATE_TYPE')
        if type(reserve_seconds) not in (int, float) or not math.isfinite(reserve_seconds) or reserve_seconds < 0:
            raise ContractError('INVALID_RESERVE')
        if not self.live_state_consistent or self.official_deadline_observed is None:
            return False
        stamp, acquired = aware(now), aware(self.acquired_at)
        deadline = aware(self.official_deadline_observed)
        scheduled = aware(self.scheduled_deadline)
        day = dt.date.fromisoformat(self.target_date)
        jst = dt.timezone(dt.timedelta(hours=9))
        if deadline.astimezone(jst).date() != day or scheduled.astimezone(jst).date() != day:
            raise ContractError('DEADLINE_TARGET_DATE_MISMATCH')
        if acquired > stamp:
            raise ContractError('FUTURE_ACQUISITION')
        # Reserve is an explicit policy input, not a learned/guaranteed P99.
        return (deadline - stamp).total_seconds() > reserve_seconds


class SourceScopedReader:
    """Validate before query AND before data is returned to prediction context.

    A caller bypassing this wrapper is not protected. Separate credentials and
    separate model contexts remain required for strong A/B isolation.
    """
    def __init__(self, source: str, source_field: str, choice_id: str, race_field: str):
        if source not in {'A', 'B'} or not re.fullmatch(r'sel[A-Za-z0-9]{14}', choice_id):
            raise ContractError('INVALID_SOURCE')
        if not all(re.fullmatch(r'fld[A-Za-z0-9]{14}', f) for f in [source_field, race_field]):
            raise ContractError('INVALID_FIELD_ID')
        self.source, self.source_field, self.choice_id, self.race_field = source, source_field, choice_id, race_field

    def read(self, query: Callable[[dict], list[dict]], race_id: str) -> list[dict]:
        if not isinstance(race_id, str) or not re.fullmatch(r'\d{8}_GAMAGORI_(?:[1-9]|1[0-2])R', race_id):
            raise ContractError('INVALID_RACE_ID')
        try:
            dt.datetime.strptime(race_id[:8], '%Y%m%d')
        except ValueError as exc:
            raise ContractError('INVALID_RACE_DATE') from exc
        filters = {'operator':'and','operands':[
            {'operator':'=','operands':[self.source_field,self.choice_id]},
            {'operator':'contains','operands':[self.race_field,race_id]}]}
        result = query(filters)
        if type(result) is not list or not all(type(row) is dict for row in result):
            raise ContractError('INVALID_QUERY_RESPONSE_TYPE')
        # Detach the validated response from adapter-owned mutable objects.
        rows = copy.deepcopy(result)
        # Consume the entire response before allowing even one row through.
        for row in rows:
            if row.get('source') != self.source or row.get('race_id') != race_id:
                raise ContractError('SOURCE_OR_RACE_SCOPE_BREACH')
            payload = row.get('payload')
            if not isinstance(payload, dict) or payload.get('source') != self.source or payload.get('race_id') != race_id:
                raise ContractError('PAYLOAD_SCOPE_BREACH')
        return rows


class StageTelemetry:
    def __init__(self, clock: Callable[[], float] = time.monotonic, wall: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc)):
        self.clock, self.wall, self.marks = clock, wall, []

    def mark(self, stage: str) -> None:
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', stage) or any(x['stage']==stage for x in self.marks):
            raise ContractError('INVALID_OR_DUPLICATE_STAGE')
        value = self.clock()
        if not math.isfinite(value) or (self.marks and value < self.marks[-1]['monotonic']):
            raise ContractError('MONOTONIC_REGRESSION')
        stamp=self.wall()
        if stamp.tzinfo is None:
            raise ContractError('NAIVE_WALL_CLOCK')
        self.marks.append({'stage':stage,'at':stamp.isoformat(),'monotonic':value})

    def intervals(self) -> list[dict]:
        return [{'from':a['stage'],'to':b['stage'],'seconds':b['monotonic']-a['monotonic']} for a,b in zip(self.marks,self.marks[1:])]


def qualitative_delta(direction: str, reason_code: str, evidence_ids: list[str]) -> dict:
    if direction not in {'UP','DOWN','UNCHANGED'} or not re.fullmatch(r'[A-Z][A-Z0-9_]*', reason_code):
        raise ContractError('INVALID_DELTA')
    if not evidence_ids or not all(isinstance(x,str) and x for x in evidence_ids):
        raise ContractError('DELTA_EVIDENCE_REQUIRED')
    return {'mode':'QUALITATIVE','direction':direction,'reason_code':reason_code,'evidence_ids':list(evidence_ids),'score_delta':None}


def response_metadata(body: bytes, url: str, acquired_at: str, status: int, content_type: str, target_date: str, race_no: int) -> dict:
    """Record hashes only; never claim bytes were persisted or page is valid."""
    parsed = urlparse(url); q = parse_qs(parsed.query)
    aware(acquired_at)
    day=dt.date.fromisoformat(target_date).strftime('%Y%m%d')
    identity=(parsed.scheme=='https' and parsed.hostname in {'www.boatrace.jp','boatrace.jp'} and q.get('hd')==[day] and q.get('jcd')==['07'] and q.get('rno')==[str(race_no)])
    if not isinstance(body,bytes) or not 1<=race_no<=12:
        raise ContractError('INVALID_RESPONSE_INPUT')
    return {'url':url,'acquired_at':acquired_at,'http_status':status,'content_type':content_type,'body_size_bytes':len(body),'body_sha256':hashlib.sha256(body).hexdigest(),'url_identity_matches':identity,'snapshot_reference':None,'snapshot_persisted':False,'content_validated':False}
