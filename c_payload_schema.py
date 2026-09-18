"""Version-aware C payload reader. No writes, migration, scoring or A/B handling.

Verify the original payload before deriving defaults. Missing/v1 records do not
prove whether a numeric ST had an F/L marker. Hash validity is not authenticity.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from start_reading import ExhibitionStartReading

C_PAYLOAD_SCHEMA_VERSION = 2


class PayloadSchemaError(ValueError):
    pass


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise PayloadSchemaError('DUPLICATE_JSON_KEY')
        out[key] = value
    return out


def _constant(value):
    raise PayloadSchemaError('NONFINITE_JSON')


def _boats(value, name):
    if type(value) is not dict or any(not re.fullmatch('[1-6]', key) for key in value):
        raise PayloadSchemaError('INVALID_BOAT_MAP:' + name)
    return value


def read_c_payload(payload_json: str, payload_hash: str) -> dict:
    """A detached interpreted view; original content/hash remain unchanged.

    V1 extension fields are preserved but not promoted to verified V2 readings.
    V2 requires a lossless map and a consistent unmarked-only legacy projection.
    Empty maps do not imply complete input, readiness or a successful prediction.
    """
    if type(payload_json) is not str or type(payload_hash) is not str or not re.fullmatch('[0-9a-f]{64}', payload_hash):
        raise PayloadSchemaError('INVALID_INPUT')
    try:
        payload = json.loads(payload_json, object_pairs_hook=_object, parse_constant=_constant)
        if type(payload) is not dict:
            raise PayloadSchemaError('PAYLOAD_NOT_OBJECT')
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError) as exc:
        if isinstance(exc, PayloadSchemaError):
            raise
        raise PayloadSchemaError('INVALID_JSON') from exc
    if hashlib.sha256(canonical.encode('utf-8')).hexdigest() != payload_hash:
        raise PayloadSchemaError('PAYLOAD_HASH_MISMATCH')
    if payload.get('source') != 'Observer_C':
        raise PayloadSchemaError('NOT_C_PAYLOAD')
    version = payload.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise PayloadSchemaError('UNSUPPORTED_SCHEMA_VERSION')
    live = payload.get('live_data')
    if type(live) is not dict:
        raise PayloadSchemaError('LIVE_DATA_MISSING')
    numeric = _boats(live.get('start_exhibition_st', {}), 'legacy')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in numeric.values()):
        raise PayloadSchemaError('INVALID_LEGACY_NUMBER')
    readings = None
    if version == 2:
        if 'start_exhibition_st' not in live or 'start_exhibition_readings' not in live:
            raise PayloadSchemaError('V2_REQUIRED_FIELD_MISSING')
        raw_map = _boats(live['start_exhibition_readings'], 'lossless')
        try:
            readings = {key: ExhibitionStartReading.model_validate(value).model_dump() for key, value in raw_map.items()}
        except (ValueError, TypeError) as exc:
            raise PayloadSchemaError('INVALID_LOSSLESS_READING') from exc
        ordinary = {key: val['seconds_magnitude'] for key, val in readings.items()
                    if val['marker'] is None and val['seconds_magnitude'] is not None}
        if ordinary != numeric:
            raise PayloadSchemaError('LEGACY_PROJECTION_CONFLICT')
    return {'effective_schema_version': version,
            'version_was_explicit': 'schema_version' in payload,
            'original_payload': payload, 'original_payload_hash': payload_hash,
            'start_readings': readings,
            'marker_semantics': 'LOSSLESS_RECORDED' if version == 2 else 'LEGACY_UNKNOWN',
            'v1_has_uninterpreted_extension': version == 1 and 'start_exhibition_readings' in live,
            'prediction_validated': False, 'readiness_validated': False}
