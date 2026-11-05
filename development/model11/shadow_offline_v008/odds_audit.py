"""Pure diagnostic for full pre-deadline odds; no stale/final fallback policy."""
from __future__ import annotations

from hashlib import sha256
from itertools import permutations
import json
import math
import re

from model11.shadow_launch.sources import _stamp

TICKETS = frozenset('-'.join(map(str, triple)) for triple in permutations(range(1, 7), 3))
TIMES = ('acquired_at', 'available_at', 'revision_at')
FIELDS = {'unit', 'odds', 'evidence_sha256', *TIMES}
# Reuse the existing SourceAdapter capture byte bound; no freshness threshold.
MAX_RAW_BYTES = 4 * 1024 * 1024


def audit_odds_snapshot(snapshot, *, prediction_at, deadline, snapshot_role=None):
    result = {'status': 'HOLD', 'structural_pass': False, 'temporal_pass': False,
              'reasons': [], 'expected_tickets': 120, 'observed_tickets': None,
              'age_seconds': None, 'freshness_status': 'UNVERIFIED_NO_APPROVED_MAX_AGE',
              'freshness_max_age_seconds': None, 'raw_duplicate_scope': 'DICT_DOMAIN_ONLY_RAW_BYTES_REQUIRED',
              'external_authenticity': 'UNVERIFIED', 'application_status': 'HOLD',
              'market_execution_eligible': False, 'production_go': False}
    reasons = result['reasons']
    if snapshot_role != 'PRE_DEADLINE':
        reasons.append('FINAL_OR_UNKNOWN_SNAPSHOT_ROLE_NO_FALLBACK')
    predicted, closes = _stamp(prediction_at), _stamp(deadline)
    if predicted is None or closes is None or predicted >= closes:
        reasons.append('PREDICTION_NOT_KNOWN_PRE_DEADLINE')
    if not isinstance(snapshot, dict) or set(snapshot) != FIELDS:
        reasons.append('ODDS_FIELDS_MISSING_OR_UNKNOWN')
        return result
    if snapshot['unit'] != 'gross_payout_multiple':
        reasons.append('GROSS_PAYOUT_UNIT_REQUIRED_NO_INFERENCE')
    digest = snapshot['evidence_sha256']
    if not isinstance(digest, str) or re.fullmatch('[0-9a-f]{64}', digest) is None:
        reasons.append('EVIDENCE_SHA_FORMAT_UNKNOWN_NOT_AUTHENTICATION')
    values = snapshot['odds']
    if isinstance(values, dict):
        result['observed_tickets'] = len(values)
    if not isinstance(values, dict) or set(values) != TICKETS:
        reasons.append('EXACT_DISTINCT_FULL_120_DOMAIN_REQUIRED')
    if isinstance(values, dict):
        for value in values.values():
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                reasons.append('POSITIVE_FINITE_NONBOOLEAN_ODDS_REQUIRED')
                break
    stamps = {key: _stamp(snapshot[key]) for key in TIMES}
    if any(value is None for value in stamps.values()):
        reasons.append('ODDS_TIME_UNKNOWN_OR_INVALID')
    else:
        acquired, available, revised = (stamps[key] for key in TIMES)
        if acquired > available or acquired > revised:
            reasons.append('ODDS_TIME_ORDER_INVALID')
        if predicted and any(value > predicted for value in stamps.values()):
            reasons.append('FUTURE_OR_POST_LOCK_ODDS_FORBIDDEN')
        if predicted:
            result['age_seconds'] = {key: (predicted - stamp).total_seconds() for key, stamp in stamps.items()}
    structural_codes = {'ODDS_FIELDS_MISSING_OR_UNKNOWN', 'GROSS_PAYOUT_UNIT_REQUIRED_NO_INFERENCE',
                        'EVIDENCE_SHA_FORMAT_UNKNOWN_NOT_AUTHENTICATION', 'EXACT_DISTINCT_FULL_120_DOMAIN_REQUIRED',
                        'POSITIVE_FINITE_NONBOOLEAN_ODDS_REQUIRED'}
    result['structural_pass'] = not any(code in structural_codes for code in reasons)
    result['temporal_pass'] = not any(code not in structural_codes for code in reasons)
    if not reasons:
        result['status'] = 'CONTRACT_CLAIMS_CONSISTENT_FRESHNESS_OPEN'
    return result


def audit_odds_raw(raw, *, expected_sha256, prediction_at, deadline, snapshot_role=None):
    failure = {'status': 'HOLD', 'reasons': [], 'raw_sha256': None, 'raw_bytes': None,
               'external_authenticity': 'UNVERIFIED', 'application_status': 'HOLD', 'production_go': False}
    if type(raw) is not bytes:
        failure['reasons'] = ['ORIGINAL_BYTES_REQUIRED']
        return failure
    failure['raw_bytes'] = len(raw)
    if not 0 < len(raw) <= MAX_RAW_BYTES:
        failure['reasons'] = ['ORIGINAL_BYTES_EMPTY_OR_CAPTURE_LIMIT_EXCEEDED']
        return failure
    failure['raw_sha256'] = sha256(raw).hexdigest()
    if (type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None
            or failure['raw_sha256'] != expected_sha256):
        failure['reasons'] = ['ORIGINAL_BYTE_SHA_MISMATCH_OR_UNKNOWN']
        return failure
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('DUPLICATE_JSON_KEY')
            obj[key] = value
        return obj
    def constant(value):
        raise ValueError('NONFINITE_JSON')
    try:
        snapshot = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=unique, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        failure['reasons'] = ['STRICT_ODDS_JSON_REQUIRED_DUPLICATES_NONFINITE_FORBIDDEN']
        return failure
    result = audit_odds_snapshot(snapshot, prediction_at=prediction_at, deadline=deadline, snapshot_role=snapshot_role)
    result.update(raw_sha256=failure['raw_sha256'], raw_bytes=len(raw), raw_duplicate_scope='STRICT_RAW_JSON_DUPLICATE_KEYS_REJECTED')
    return result
