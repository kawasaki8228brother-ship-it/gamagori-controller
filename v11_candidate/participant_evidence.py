"""Snapshot-bound participant evidence candidate; no live validator is installed.

The application must supply reviewed semantic-validation CODE, not an LLM PASS
flag. A URL, a digest, or an evidence ID cannot establish official body content.
The only supplied validator in this stage is synthetic and lives in tests.
This is a data-flow contract, NOT a signature, permission boundary or freshness
policy. Existing readiness/runtime modules are deliberately not changed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import re
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from .contracts import canonical
from .observation import BeforeObservation
from .readiness import (CheckState, EvidenceCheck, ReadinessContext,
                        ReadinessReport, assess_exhibition_readiness)


class ParticipantContractError(ValueError):
    pass


@dataclass(frozen=True)
class RaceIdentity:
    target_date: str
    venue_code: str
    race_no: int

    def __post_init__(self) -> None:
        if type(self.target_date) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', self.target_date):
            raise ParticipantContractError('INVALID_TARGET_DATE')
        try:
            dt.date.fromisoformat(self.target_date)
        except ValueError as exc:
            raise ParticipantContractError('INVALID_TARGET_DATE') from exc
        if self.venue_code != '07' or type(self.race_no) is not int or not 1 <= self.race_no <= 12:
            raise ParticipantContractError('INVALID_RACE_IDENTITY')


@dataclass(frozen=True)
class RosterSnapshot:
    snapshot_id: str
    requested_url: str
    response_url: str
    acquired_at: str
    http_status: int
    content_type: str
    body: bytes
    body_sha256: str


@dataclass(frozen=True)
class RosterExtraction:
    """Reviewed validator output; six explicit slot states, never missing-row inference."""
    body_identity: RaceIdentity
    slot_states: tuple[tuple[int, str], ...]  # ACTIVE / WITHDRAWN / UNKNOWN
    evidence_locator: str


@dataclass(frozen=True)
class SemanticValidator:
    validator_id: str
    extract: Callable[[bytes], RosterExtraction | None]
    test_only: bool = True

    def __post_init__(self) -> None:
        if type(self.validator_id) is not str or not self.validator_id.strip() or not callable(self.extract) or type(self.test_only) is not bool:
            raise ParticipantContractError('INVALID_VALIDATOR')


@dataclass(frozen=True)
class ParticipantEvidence:
    target: RaceIdentity
    state: CheckState
    expected_boats: tuple[int, ...] | None
    snapshot_id: str | None
    body_sha256: str | None
    requested_url: str | None
    response_url: str | None
    acquired_at: str | None
    validator_id: str | None
    evidence_locator: str | None
    reasons: tuple[str, ...]
    test_only: bool
    binding_sha256: str

    def verify_binding(self) -> bool:
        """Integrity only. Anyone able to rewrite everything can recompute this hash."""
        payload = asdict(self)
        stored = payload.pop('binding_sha256')
        try:
            return stored == hashlib.sha256(canonical(payload).encode('utf-8')).hexdigest()
        except (TypeError, ValueError):
            return False


def _timestamp(value: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError, TypeError) as exc:
        raise ParticipantContractError('INVALID_ACQUIRED_AT') from exc
    if parsed.tzinfo is None:
        raise ParticipantContractError('NAIVE_ACQUIRED_AT')
    return parsed


def _url_matches(url: str, target: RaceIdentity) -> bool:
    try:
        if type(url) is not str or any(c.isspace() for c in url):
            return False
        p = urlsplit(url)
        q = parse_qs(p.query, keep_blank_values=True)
        return (p.scheme == 'https' and p.hostname in {'boatrace.jp', 'www.boatrace.jp'}
                and p.port in (None, 443) and p.username is None and p.password is None
                and not p.fragment and p.path == '/owpc/pc/race/racelist'
                and q.get('hd') == [target.target_date.replace('-', '')]
                and q.get('jcd') == [target.venue_code] and q.get('rno') == [str(target.race_no)])
    except (TypeError, ValueError):
        return False


def inspect_participant_evidence(snapshot: RosterSnapshot | None, target: RaceIdentity,
                                 *, now: dt.datetime, validator: SemanticValidator | None = None,
                                 allow_test_validator: bool = False) -> ParticipantEvidence:
    """Derive values AND status from the same bytes; never accepts expected_boats.

    Transport metadata is supplied by the acquisition boundary. It is not
    authenticated here. No TTL, 'latest official status', or runtime acceptance
    is inferred. A missing semantic validator always yields UNVERIFIED.
    """
    if type(target) is not RaceIdentity or type(now) is not dt.datetime or now.tzinfo is None or type(allow_test_validator) is not bool:
        raise ParticipantContractError('INVALID_INSPECTION_CONTEXT')
    if validator is not None and type(validator) is not SemanticValidator:
        raise ParticipantContractError('INVALID_VALIDATOR')
    fields = dict(target=target, expected_boats=None, snapshot_id=None, body_sha256=None,
                  requested_url=None, response_url=None, acquired_at=None,
                  validator_id=validator.validator_id if validator else None,
                  evidence_locator=None, test_only=bool(validator and validator.test_only))

    def done(state: CheckState, reason: str | None = None) -> ParticipantEvidence:
        data = fields | dict(state=state, reasons=(reason,) if reason else ())
        # Use dataclass-like representation so the target has canonical fields.
        payload = data | {'target': asdict(target)}
        binding = hashlib.sha256(canonical(payload).encode('utf-8')).hexdigest()
        return ParticipantEvidence(**data, binding_sha256=binding)

    if snapshot is None:
        return done(CheckState.UNVERIFIED, 'ROSTER_SNAPSHOT_MISSING')
    if type(snapshot) is not RosterSnapshot:
        return done(CheckState.FAIL, 'INVALID_SNAPSHOT_TYPE')
    if (any(type(v) is not str or not v.strip() for v in
            (snapshot.snapshot_id, snapshot.requested_url, snapshot.response_url, snapshot.acquired_at, snapshot.content_type))
            or type(snapshot.http_status) is not int or not 100 <= snapshot.http_status <= 599
            or type(snapshot.body) is not bytes or len(snapshot.body) > 2_000_000
            or type(snapshot.body_sha256) is not str or not re.fullmatch(r'[0-9a-f]{64}', snapshot.body_sha256)):
        return done(CheckState.FAIL, 'INVALID_SNAPSHOT_METADATA')
    fields.update(snapshot_id=snapshot.snapshot_id, body_sha256=snapshot.body_sha256,
                  requested_url=snapshot.requested_url, response_url=snapshot.response_url,
                  acquired_at=snapshot.acquired_at)
    if hashlib.sha256(snapshot.body).hexdigest() != snapshot.body_sha256:
        return done(CheckState.FAIL, 'BODY_HASH_MISMATCH')
    if not all(_url_matches(u, target) for u in (snapshot.requested_url, snapshot.response_url)):
        return done(CheckState.FAIL, 'ROSTER_URL_IDENTITY_MISMATCH')
    try:
        acquired = _timestamp(snapshot.acquired_at)
    except ParticipantContractError as exc:
        return done(CheckState.FAIL, str(exc))
    if acquired > now:
        return done(CheckState.FAIL, 'FUTURE_ACQUISITION')
    if snapshot.http_status != 200 or snapshot.content_type.split(';', 1)[0].strip().lower() != 'text/html':
        return done(CheckState.UNVERIFIED, 'ROSTER_RESPONSE_UNAVAILABLE')
    if validator is None:
        return done(CheckState.UNVERIFIED, 'SEMANTIC_VALIDATOR_NOT_INSTALLED')
    if validator.test_only and not allow_test_validator:
        return done(CheckState.UNVERIFIED, 'TEST_VALIDATOR_NOT_ALLOWED')
    try:
        parsed = validator.extract(snapshot.body)
    except Exception as exc:
        return done(CheckState.UNVERIFIED, 'SEMANTIC_VALIDATOR_ERROR:' + type(exc).__name__)
    if parsed is None:
        return done(CheckState.UNVERIFIED, 'ROSTER_LAYOUT_NOT_RECOGNIZED')
    if type(parsed) is not RosterExtraction or type(parsed.body_identity) is not RaceIdentity:
        return done(CheckState.FAIL, 'INVALID_SEMANTIC_RESULT')
    if parsed.body_identity != target:
        return done(CheckState.FAIL, 'ROSTER_BODY_IDENTITY_MISMATCH')
    if type(parsed.evidence_locator) is not str or not parsed.evidence_locator.strip():
        return done(CheckState.FAIL, 'ROSTER_EVIDENCE_LOCATOR_MISSING')
    fields['evidence_locator'] = parsed.evidence_locator
    slots = parsed.slot_states
    if (type(slots) is not tuple or any(type(s) is not tuple or len(s) != 2
            or type(s[0]) is not int or not 1 <= s[0] <= 6
            or s[1] not in ('ACTIVE', 'WITHDRAWN', 'UNKNOWN') for s in slots)):
        return done(CheckState.FAIL, 'INVALID_ROSTER_SLOTS')
    if len({b for b, _ in slots}) != len(slots):
        return done(CheckState.FAIL, 'DUPLICATE_ROSTER_SLOT')
    if {b for b, _ in slots} != set(range(1, 7)):
        return done(CheckState.UNVERIFIED, 'ROSTER_SLOT_COVERAGE_UNKNOWN')
    if any(state == 'UNKNOWN' for _, state in slots):
        return done(CheckState.UNVERIFIED, 'ROSTER_SLOT_STATUS_UNKNOWN')
    fields['expected_boats'] = tuple(sorted(b for b, state in slots if state == 'ACTIVE'))
    return done(CheckState.PASS)


@dataclass(frozen=True)
class BoundReadiness:
    participants: ParticipantEvidence
    readiness: ReadinessReport


def assess_snapshot_bound_readiness(observation: BeforeObservation, target: RaceIdentity,
                                    snapshot: RosterSnapshot | None, *, now: dt.datetime,
                                    validator: SemanticValidator | None = None,
                                    checks: dict[str, EvidenceCheck] | None = None,
                                    allow_test_validator: bool = False) -> BoundReadiness:
    """One entry, one participant source. Other evidence checks are still assertions.

    Neither expected_boats nor OFFICIAL_PARTICIPANTS is accepted as an override.
    The legacy API remains unchanged and must not be used to bypass this future
    entry. No network, storage, scoring, cutoff decision or live integration.
    """
    checks = {} if checks is None else checks
    if type(checks) is not dict or any(k not in {'PAGE_IDENTITY', 'EXHIBITION_FRESHNESS', 'START_FRESHNESS'} for k in checks):
        raise ParticipantContractError('PARTICIPANT_OVERRIDE_OR_UNKNOWN_CHECK')
    p = inspect_participant_evidence(snapshot, target, now=now, validator=validator,
                                     allow_test_validator=allow_test_validator)
    if not p.verify_binding():
        raise ParticipantContractError('INTERNAL_BINDING_MISMATCH')
    derived = dict(checks)
    derived['OFFICIAL_PARTICIPANTS'] = EvidenceCheck(p.state, (p.binding_sha256,))
    report = assess_exhibition_readiness(observation, ReadinessContext(p.expected_boats, derived))
    return BoundReadiness(p, report)
