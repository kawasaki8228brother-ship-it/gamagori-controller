"""SYS-02 offline prototype. No I/O, network, writer, LOCK or timing decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from typing import Any

PROFILE = "SYS02_DECIMAL_EXACT_V1_PROTOTYPE"
MAX_NUMBER_TOKEN_CHARS = 256
INPUT_STATUSES = frozenset({"VALID", "INVALID_UTF8", "INVALID_JSON", "DUPLICATE_KEY", "NON_FINITE_LITERAL", "INVALID_UNICODE_SCALAR", "RESOURCE_LIMIT"})
CANONICAL_STATUSES = frozenset({"AVAILABLE", "UNAVAILABLE_INPUT", "UNAVAILABLE_FLOAT_RANGE"})
AXIS_STATES = frozenset({"MATCH", "DIFFERENT", "UNVERIFIED"})


class _DuplicateKey(ValueError):
    pass


class _NonFinite(ValueError):
    pass


class _Limit(ValueError):
    pass


class _UnicodeScalar(ValueError):
    pass


@dataclass
class _Analysis:
    report: dict[str, Any]
    value: Any = field(default=None, repr=False)


def sha256_bytes(raw: bytes) -> str:
    if not isinstance(raw, bytes):
        raise TypeError("BYTES_REQUIRED")
    return hashlib.sha256(raw).hexdigest()


def _expected(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", value):
        raise ValueError("EXPECTED_SHA256_INVALID")
    return value.lower()


def _settings(max_bytes: int, max_depth: int) -> None:
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("MAX_BYTES_INVALID")
    if type(max_depth) is not int or not 0 <= max_depth <= 128:
        raise ValueError("MAX_DEPTH_INVALID")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _number(token: str) -> Decimal:
    if len(token) > MAX_NUMBER_TOKEN_CHARS:
        raise _Limit
    try:
        return Decimal(token)
    except InvalidOperation:
        raise _Limit from None


def _constant(_token: str) -> None:
    raise _NonFinite


def _guard(value: Any, max_depth: int, depth: int = 0) -> None:
    if depth > max_depth:
        raise _Limit
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise _UnicodeScalar
    elif isinstance(value, dict):
        for key, child in value.items():
            _guard(key, max_depth, depth + 1)
            _guard(child, max_depth, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _guard(child, max_depth, depth + 1)


def _analyze(raw: bytes, expected_raw: str | None, expected_canonical: str | None,
             max_bytes: int, max_depth: int) -> _Analysis:
    # Hash the COMPLETE supplied bytes, even if later JSON validation is refused.
    raw_hash = sha256_bytes(raw)
    report: dict[str, Any] = {
        "profile": PROFILE, "bytes": len(raw), "input_status": "VALID",
        "raw": {"sha256": raw_hash, "expected_sha256": expected_raw,
                "expected_match": None if expected_raw is None else raw_hash == expected_raw},
        "canonical": {"status": "UNAVAILABLE_INPUT", "sha256": None,
                      "expected_sha256": expected_canonical, "expected_match": None},
        "warnings": [],
        "provenance_not_proven": ["TIMESTAMP_AUTHENTICITY", "DB_IDENTITY", "SOURCE_AUTHENTICITY"],
        "LOCK_validity": "NOT_EVALUATED",
    }
    try:
        if len(raw) > max_bytes:
            raise _Limit
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, parse_int=_number, parse_float=_number,
                           parse_constant=_constant, object_pairs_hook=_pairs)
        _guard(value, max_depth)
    except UnicodeDecodeError:
        report["input_status"] = "INVALID_UTF8"
    except _DuplicateKey:
        report["input_status"] = "DUPLICATE_KEY"
    except _NonFinite:
        report["input_status"] = "NON_FINITE_LITERAL"
    except _UnicodeScalar:
        report["input_status"] = "INVALID_UNICODE_SCALAR"
    except (_Limit, RecursionError):
        report["input_status"] = "RESOURCE_LIMIT"
    except json.JSONDecodeError:
        report["input_status"] = "INVALID_JSON"
    else:
        rounded = False

        def python_float(token: str) -> float:
            nonlocal rounded
            f = float(token)
            if math.isfinite(f) and Decimal(repr(f)) != Decimal(token):
                rounded = True
            return f

        # Canonical axis intentionally uses normal Python int/float behavior.
        # Exact Decimal values above are reserved for the SEMANTIC axis.
        obj = json.loads(text, parse_float=python_float, parse_constant=_constant,
                         object_pairs_hook=_pairs)
        try:
            canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False).encode("utf-8")
        except ValueError:
            report["canonical"]["status"] = "UNAVAILABLE_FLOAT_RANGE"
        else:
            digest = sha256_bytes(canonical)
            report["canonical"].update(status="AVAILABLE", sha256=digest,
                                       expected_match=None if expected_canonical is None else digest == expected_canonical)
        if rounded:
            report["warnings"].append("CANONICAL_DECIMAL_ROUNDING")
        return _Analysis(report, value)
    return _Analysis(report)


def inspect_bytes(raw: bytes, *, expected_raw_sha256: str | None = None,
                  expected_canonical_sha256: str | None = None,
                  max_bytes: int = 1_048_576, max_depth: int = 64) -> dict[str, Any]:
    """Inspect one complete byte string. Hash expectation kinds are explicit."""
    _settings(max_bytes, max_depth)
    expected_raw = _expected(expected_raw_sha256)
    expected_canonical = _expected(expected_canonical_sha256)
    return _analyze(raw, expected_raw, expected_canonical, max_bytes, max_depth).report


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, Decimal) and isinstance(right, Decimal):
        return left == right
    # In particular, JSON true is not JSON number 1.
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_value(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))
    return left == right


def _axis(match: bool | None) -> dict[str, Any]:
    return {"match": match, "state": "UNVERIFIED" if match is None else "MATCH" if match else "DIFFERENT"}


def compare_bytes(left: bytes, right: bytes, *, max_bytes: int = 1_048_576,
                  max_depth: int = 64) -> dict[str, Any]:
    """Independent raw, Python-canonical and exact-Decimal semantic axes."""
    _settings(max_bytes, max_depth)
    a = _analyze(left, None, None, max_bytes, max_depth)
    b = _analyze(right, None, None, max_bytes, max_depth)
    ca, cb = a.report["canonical"], b.report["canonical"]
    canonical_match = ca["sha256"] == cb["sha256"] if ca["status"] == cb["status"] == "AVAILABLE" else None
    semantic_match = _same_value(a.value, b.value) if a.report["input_status"] == b.report["input_status"] == "VALID" else None
    return {
        "profile": PROFILE, "left": a.report, "right": b.report,
        "axes": {
            "raw_bytes": _axis(left == right),
            "canonical": _axis(canonical_match),
            "semantic": dict(_axis(semantic_match), policy="EXACT_DECIMAL_NUMBERS_BOOL_DISTINCT_NO_UNICODE_NORMALIZATION"),
        },
        "aggregate_integrity_verdict": "NOT_ASSIGNED_AXES_MUST_NOT_BE_COLLAPSED",
        "real_56_records": "NOT_RECEIVED_NOT_TESTED_HQ14_PRIVATE_TASK",
        "production_GO": False,
    }
