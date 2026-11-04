"""P2 offline research checks. No services, keys, writer or prediction changes."""
from __future__ import annotations

import argparse
import base64
from collections import deque
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


def _sha(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) else None


def _bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("BASE64_STRING_REQUIRED")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError("BASE64_INVALID") from None


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _comparison(left: Any, right: Any) -> str:
    return "UNVERIFIED" if left is None or right is None else "MATCH" if left == right else "MISMATCH"


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _aware(value: Any) -> str:
    if value is None:
        return "UNVERIFIED"
    if not isinstance(value, str):
        return "INVALID"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "INVALID"
    return "WELL_FORMED_CLAIM_ONLY" if dt.tzinfo is not None and dt.utcoffset() is not None else "INVALID"


def archive_check(request: dict[str, Any]) -> dict[str, Any]:
    """SYS-14: original hash, receipt acknowledgment and readback are separate."""
    raw = _bytes(request.get("raw_b64"))
    actual = None if raw is None else _digest(raw)
    expected = _sha(request.get("expected_raw_sha256"))
    receipt = request.get("save_receipt")
    if receipt is not None and not isinstance(receipt, dict):
        raise ValueError("RECEIPT_OBJECT_REQUIRED")
    receipt = receipt or {}
    ack = receipt.get("acknowledged")
    if ack is not None and type(ack) is not bool:
        raise ValueError("ACK_BOOL_OR_NULL_REQUIRED")
    readback = _bytes(request.get("readback_b64"))
    raw_match = _comparison(actual, expected)
    receipt_match = _comparison(actual, _sha(receipt.get("raw_sha256")))
    readback_match = _comparison(raw, readback)
    axes = [raw_match, receipt_match, readback_match]
    local_state = "MISMATCH" if "MISMATCH" in axes or ack is False else "LOCALLY_CONSISTENT" if all(x == "MATCH" for x in axes) and ack is True else "UNVERIFIED"
    return {"task": "SYS-14", "raw_sha256": actual, "raw_expected": raw_match,
            "receipt_acknowledged_claim": ack, "receipt_hash_claim": receipt_match,
            "readback_bytes": readback_match, "local_state": local_state,
            "receipt_and_retrieval_authenticity": "UNVERIFIED",
            "timestamp_DB_source_authenticity": "NOT_PROVEN", "production_GO": False}


def pointer_check(request: dict[str, Any]) -> dict[str, Any]:
    """SYS-15: checks a proposed manifest schema, never edits actual POINTER."""
    canonical, pointer = request.get("canonical"), request.get("pointer")
    history = request.get("decisions")
    if not isinstance(canonical, dict) or not isinstance(pointer, dict) or not isinstance(history, list) or any(not isinstance(r, dict) for r in history):
        raise ValueError("MANIFEST_OBJECTS_AND_HISTORY_REQUIRED")
    history_ids = [_text(row.get("id")) for row in history]
    history_issues = []
    if None in history_ids:
        history_issues.append("DECISION_HISTORY_ID_MISSING")
    if len([x for x in history_ids if x is not None]) != len({x for x in history_ids if x is not None}):
        history_issues.append("DECISION_HISTORY_DUPLICATE_ID")
    raw = _bytes(request.get("canonical_raw_b64"))
    actual = None if raw is None else _digest(raw)
    fields = {
        "canonical_id": _comparison(_text(canonical.get("id")), _text(pointer.get("canonical_id"))),
        "canonical_version": _comparison(_text(canonical.get("version")), _text(pointer.get("canonical_version"))),
        "canonical_hash_claim": _comparison(_sha(canonical.get("sha256")), _sha(pointer.get("canonical_sha256"))),
        "canonical_raw_hash": _comparison(actual, _sha(canonical.get("sha256"))),
    }
    decision_id = _text(pointer.get("decision_id"))
    candidates = [r for r in history if isinstance(r, dict) and decision_id is not None and r.get("id") == decision_id]
    if len(candidates) > 1:
        decision_state = "AMBIGUOUS_DUPLICATE_ID"
    elif len(candidates) == 0:
        decision_state = "UNVERIFIED_REFERENCE_NOT_FOUND"
    else:
        row = candidates[0]
        claims = [_comparison(_text(row.get("canonical_id")), _text(canonical.get("id"))),
                  _comparison(_text(row.get("version")), _text(canonical.get("version"))),
                  _comparison(_sha(row.get("sha256")), _sha(canonical.get("sha256")))]
        decision_state = "MISMATCH" if "MISMATCH" in claims else "MATCHING_CLAIMS_ONLY" if all(x == "MATCH" for x in claims) else "UNVERIFIED_INCOMPLETE"
    if "MISMATCH" in fields.values() or decision_state in {"MISMATCH", "AMBIGUOUS_DUPLICATE_ID"} or history_issues:
        state = "INCONSISTENT"
    elif all(x == "MATCH" for x in fields.values()) and decision_state == "MATCHING_CLAIMS_ONLY":
        state = "LOCALLY_CONSISTENT"
    else:
        state = "UNVERIFIED"
    return {"task": "SYS-15", "fields": fields, "decision_reference": decision_state, "history_issues": history_issues,
            "local_state": state, "decision_approval_authenticity": "UNVERIFIED",
            "canonical_POINTER_modified": False, "production_GO": False}


def parser_observations(request: dict[str, Any]) -> dict[str, Any]:
    """SYS-16/17: observation classification, not the existing parser or C path."""
    flags: list[str] = []
    http = request.get("http_status")
    if http is not None and (type(http) is not int or not 100 <= http <= 599):
        raise ValueError("HTTP_STATUS_INVALID")
    network = request.get("network_error", "NONE")
    if network not in {"NONE", "SSL", "DNS", "TIMEOUT", "PROXY", "CONNECTION", "UNKNOWN"}:
        raise ValueError("NETWORK_CLASS_INVALID")
    if network != "NONE":
        flags.append("NETWORK_FAILURE_" + network)
    if http is None:
        flags.append("HTTP_RESPONSE_UNVERIFIED")
    elif http == 200:
        flags.append("HTTP200_NOT_CONTENT_PROOF")
    else:
        flags.append("HTTP_STATUS_NOT_200")
    date_state = _comparison(_text(request.get("expected_date")), _text(request.get("observed_date")))
    for field in ("expected_date", "observed_date"):
        value = request.get(field)
        if value is not None:
            try:
                if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError
                date.fromisoformat(value)
            except (ValueError, TypeError):
                raise ValueError("DATE_FORMAT_INVALID") from None
    venue_state = _comparison(_text(request.get("expected_venue")), _text(request.get("observed_venue")))
    if date_state != "MATCH":
        flags.append("DATE_" + date_state)
    if venue_state != "MATCH":
        flags.append("VENUE_" + venue_state)
    parser = request.get("parser_error", "NONE")
    if parser not in {"NONE", "NO_RACE_ROWS", "OTHER", "UNKNOWN"}:
        raise ValueError("PARSER_CLASS_INVALID")
    if request.get("official_calendar", "UNKNOWN") not in {"NO_RACE_VERIFIED", "RACE_VERIFIED", "UNKNOWN"}:
        raise ValueError("CALENDAR_CLASS_INVALID")
    fmt = request.get("input_format", "UNKNOWN")
    if fmt not in {"EXPECTED", "CHANGED", "UNKNOWN"}:
        raise ValueError("FORMAT_CLASS_INVALID")
    if fmt == "CHANGED":
        flags.append("INPUT_FORMAT_CHANGE_LANE2")
    elif fmt == "UNKNOWN":
        flags.append("INPUT_FORMAT_UNVERIFIED")
    fallback = request.get("tracking_fallback", "UNKNOWN")
    if fallback not in {"PRESENT", "MISSING", "UNKNOWN"}:
        raise ValueError("FALLBACK_CLASS_INVALID")
    if fallback != "PRESENT":
        flags.append("TRACKING_FALLBACK_" + fallback)
    scratch = request.get("scratch_count")
    if scratch is not None and (type(scratch) is not int or scratch < 0):
        raise ValueError("SCRATCH_COUNT_INVALID")
    if scratch is None:
        flags.append("SCRATCH_COUNT_UNVERIFIED")
    elif scratch > 0:
        flags.append("SCRATCH_PRESENT_INPUT_CANDIDATE_LANE2")
    if parser == "NO_RACE_ROWS":
        compatible = (request.get("official_calendar") == "NO_RACE_VERIFIED" and date_state == venue_state == "MATCH" and fmt == "EXPECTED" and http == 200 and network == "NONE")
        flags.append("NONRACE_PATTERN_COMPATIBLE_NOT_SUCCESS_PROOF" if compatible else "NONRACE_PARSER_UNVERIFIED")
    elif parser != "NONE":
        flags.append("PARSER_ERROR_" + parser)
    return {"tasks": ["SYS-16", "SYS-17"], "flags": flags,
            "input_change_lane": "LANE2_HOLD", "actual_C_parser_validation": "UNVERIFIED_SYNTHETIC_CLASSIFIER_ONLY",
            "official_fetch_success": "NOT_ASSIGNED", "LOCK_validity": "NOT_EVALUATED", "production_GO": False}


def boundary_check(request: dict[str, Any]) -> dict[str, Any]:
    """SYS-23: transitive checks on a DECLARED synthetic dependency graph."""
    nodes, edges = request.get("nodes"), request.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("GRAPH_LISTS_REQUIRED")
    if len(nodes) > 256 or len(edges) > 2048:
        raise ValueError("GRAPH_PROTOTYPE_LIMIT")
    owners: dict[str, str] = {}
    for row in nodes:
        if not isinstance(row, dict) or _text(row.get("id")) is None or not isinstance(row.get("owner"), str) or row.get("owner") not in {"A", "B", "NEUTRAL", "PUBLIC", "UNKNOWN"}:
            raise ValueError("NODE_INVALID")
        if row["id"] in owners:
            raise ValueError("NODE_ID_DUPLICATE")
        owners[row["id"]] = row["owner"]
    adjacency: dict[str, list[str]] = {node: [] for node in owners}
    for row in edges:
        if not isinstance(row, dict) or _text(row.get("from")) is None or _text(row.get("to")) is None or row.get("from") not in owners or row.get("to") not in owners:
            raise ValueError("EDGE_NODE_UNKNOWN")
        adjacency[row["from"]].append(row["to"])
    violations = []
    for start, owner in owners.items():
        if owner not in {"A", "B"}:
            continue
        other = "B" if owner == "A" else "A"
        queue, visited = deque([(start, [start])]), {start}
        while queue:
            node, path = queue.popleft()
            if owners[node] == other:
                violations.append({"from_owner": owner, "to_owner": other, "declared_path": path})
            for nxt in adjacency[node]:
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))
    unknown = "UNKNOWN" in owners.values()
    return {"task": "SYS-23", "declared_graph_state": "CROSS_SOURCE_PATH_FOUND" if violations else "UNVERIFIED_UNKNOWN_OWNER" if unknown else "NO_CROSS_SOURCE_PATH_FOUND_IN_DECLARATION",
            "violations": violations, "actual_reader_filter_unchanged": True,
            "live_A_B_independence": "UNVERIFIED_VERIFIED_LIVE_BYTES_AND_GRAPH_MAPPING_REQUIRED", "production_GO": False}


def immutable_evidence(request: dict[str, Any]) -> dict[str, Any]:
    """SYS-24: local consistency is not external independent attestation."""
    raw = _bytes(request.get("raw_b64"))
    actual = None if raw is None else _digest(raw)
    self_match = _comparison(actual, _sha(request.get("self_sha256")))
    external = request.get("external_record")
    if external is not None and not isinstance(external, dict):
        raise ValueError("EXTERNAL_RECORD_OBJECT_REQUIRED")
    external = external or {}
    external_match = _comparison(actual, _sha(external.get("raw_sha256")))
    timestamp = _aware(external.get("observed_at"))
    return {"task": "SYS-24", "raw_sha256": actual, "self_hash": self_match,
            "external_hash_claim": external_match, "external_timestamp_claim": timestamp,
            "claimed_verified_flag_not_trusted": "verified" in external,
            "independent_attestation": "UNVERIFIED_NO_EXTERNAL_VERIFIER_OR_TRUST_ANCHOR",
            "tamper_or_claim_inconsistency": self_match == "MISMATCH" or external_match == "MISMATCH",
            "new_signing_keys_or_storage": False, "production_GO": False}


FUNCTIONS = {"sys14": archive_check, "sys15": pointer_check, "sys16_17": parser_observations,
             "sys23": boundary_check, "sys24": immutable_evidence}


def _unique_pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in rows:
        if key in result:
            raise ValueError("INPUT_DUPLICATE_KEY")
        result[key] = value
    return result


def _bad_constant(_value: str) -> None:
    raise ValueError("INPUT_NONFINITE")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=FUNCTIONS)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        with args.input.open("rb") as stream:
            raw = stream.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("INPUT_LIMIT")
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
        if not isinstance(request, dict):
            raise ValueError("REQUEST_OBJECT_REQUIRED")
        result = FUNCTIONS[args.mode](request)
    except (OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({"state": "INPUT_ERROR", "details": "NOT_ECHOED", "production_GO": False}))
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
