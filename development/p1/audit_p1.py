"""Independent, offline P1 observations. No writer, network or LOCK decisions."""
from __future__ import annotations

import argparse
import base64
import binascii
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

MISSING = object()
HASH = re.compile(r"^[0-9a-fA-F]{64}$")


def field_kind(record: dict, key: str) -> str:
    """SYS-08: JSON field states, including bool vs numeric zero."""
    value = record.get(key, MISSING)
    if value is MISSING:
        return "MISSING"
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "TRUE_BOOLEAN" if value else "FALSE_BOOLEAN"
    if type(value) in (int, float):
        if isinstance(value, float) and not math.isfinite(value):
            return "NON_FINITE_NUMBER"
        return "ZERO_NUMBER" if value == 0 else "OTHER_NUMBER"
    if isinstance(value, str):
        return "EMPTY_STRING" if value == "" else "NONEMPTY_STRING"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "OBJECT"
    return "UNSUPPORTED_TYPE"


def event_scope(rows: list[dict], read_status: str) -> dict:
    """SYS-05: physical row scope, not unique races or eligible evaluation N."""
    if read_status not in {"READ_OK_COMPLETE", "READ_FAILED", "INCOMPLETE"}:
        raise ValueError("READ_STATUS_INVALID")
    counts = {"production_observed": 0, "test_observed": 0,
              "production_unknown": 0, "race_linked_observed": 0,
              "unlinked_observed": 0, "link_unknown": 0, "OBS_subset": 0}
    for row in rows:
        is_test = row.get("is_test", MISSING)
        record_id = row.get("id")
        if is_test is True or isinstance(record_id, str) and record_id.startswith("TEST_"):
            counts["test_observed"] += 1
        elif is_test is not False:
            counts["production_unknown"] += 1
        else:
            counts["production_observed"] += 1
            race = row.get("race_id", MISSING)
            if race is MISSING or race is None or race == "":
                counts["unlinked_observed"] += 1
            elif isinstance(race, str) and race.strip():
                counts["race_linked_observed"] += 1
            else:
                counts["link_unknown"] += 1
            if row.get("kind") == "OBS":
                counts["OBS_subset"] += 1
    complete = read_status == "READ_OK_COMPLETE"
    total_known = complete and counts["production_unknown"] == 0
    return {"case": "SYS-05", "read_status": read_status,
            "status": "OBSERVED_COMPLETE" if total_known and counts["link_unknown"] == 0 else "UNVERIFIED",
            "production_total": counts["production_observed"] if total_known else None,
            "observed_counts": counts,
            "OBS_is_subset_not_additional_rows": True,
            "count_unit": "PHYSICAL_RECORDS_NOT_UNIQUE_RACES", "production_GO": False}


def _raw(record: dict) -> bytes | None:
    value = record.get("payload_raw_b64")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("RAW_ENCODING_INVALID")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("RAW_ENCODING_INVALID") from None


def _hash_equal(claim, actual: str | None) -> bool | None:
    if not isinstance(claim, str) or not HASH.fullmatch(claim) or actual is None:
        return None
    return claim.lower() == actual


def key_duplicates(records: list[dict]) -> dict:
    """SYS-06: compare calculated raw hashes, separately from hash claims."""
    grouped = defaultdict(list)
    invalid_keys = 0
    for record in records:
        key = record.get("key")
        try:
            valid = isinstance(key, str) and bool(key) and bool(key.encode("utf-8"))
        except UnicodeEncodeError:
            valid = False
        if not valid:
            invalid_keys += 1
            continue
        try:
            raw = _raw(record)
            actual = None if raw is None else hashlib.sha256(raw).hexdigest()
            encoding = "AVAILABLE" if raw is not None else "RAW_UNAVAILABLE"
        except ValueError:
            actual, encoding = None, "INVALID_RAW_ENCODING"
        grouped[key].append({"calculated_raw_sha256": actual,
                             "raw_status": encoding,
                             "claim_field_kind": field_kind(record, "claimed_hash"),
                             "claim_matches_calculated_raw": _hash_equal(record.get("claimed_hash"), actual)})
    groups = []
    for key, rows in sorted(grouped.items()):
        available = [row["calculated_raw_sha256"] for row in rows]
        if len(rows) == 1:
            kind = "SINGLE"
        elif None in available:
            kind = "DUPLICATE_RAW_UNVERIFIED"
        elif len(set(available)) == 1:
            kind = "DUPLICATE_IDENTICAL_RAW"
        else:
            kind = "CONFLICT_DIFFERENT_RAW"
        groups.append({"key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                       "count": len(rows), "classification": kind, "rows": rows})
    return {"case": "SYS-06", "groups": groups, "invalid_key_rows": invalid_keys,
            "claim_equality_is_not_raw_equality": True,
            "LOCK_validity": "NOT_EVALUATED", "production_GO": False}


def hash_spec_research(record: dict, profile: dict | None) -> dict:
    """SYS-07 supports only one explicit synthetic research profile."""
    base = {"case": "SYS-07", "mode": "SPECIFICATION_RESEARCH_ONLY",
            "LOCK_validity": "NOT_EVALUATED", "production_GO": False,
            "existing_B_contract": "UNVERIFIED"}
    if not isinstance(profile, dict):
        return dict(base, status="UNVERIFIED", reason="PROFILE_REQUIRED")
    if profile.get("column_hash_kind") != "RAW_BYTES" or profile.get("embedded_hash_kind") != "FIXED_SPEC_REFERENCE":
        return dict(base, status="UNVERIFIED", reason="UNSUPPORTED_PROFILE")
    spec = profile.get("expected_spec_hash")
    embedded_field = profile.get("embedded_hash_field")
    if not isinstance(spec, str) or not HASH.fullmatch(spec) or not isinstance(embedded_field, str) or not embedded_field:
        return dict(base, status="UNVERIFIED", reason="PROFILE_INCOMPLETE")
    try:
        raw = _raw(record)
    except ValueError:
        return dict(base, status="UNVERIFIED", reason="INVALID_RAW_ENCODING")
    calculated = None if raw is None else hashlib.sha256(raw).hexdigest()
    column = _hash_equal(record.get("column_hash"), calculated)
    if raw is None:
        return dict(base, status="UNVERIFIED", reason="RAW_PAYLOAD_UNAVAILABLE", column_vs_raw=column, embedded_vs_fixed_spec=None)
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (ValueError, UnicodeDecodeError):
        return dict(base, status="UNVERIFIED", reason="RAW_JSON_INVALID_OR_AMBIGUOUS", column_vs_raw=column, embedded_vs_fixed_spec=None)
    if not isinstance(payload, dict):
        return dict(base, status="UNVERIFIED", reason="PAYLOAD_NOT_OBJECT", column_vs_raw=column, embedded_vs_fixed_spec=None)
    embedded = _hash_equal(payload.get(embedded_field), spec.lower())
    return dict(base, status="SYNTHETIC_PROFILE_OBSERVED" if column is not None and embedded is not None else "UNVERIFIED",
                column_vs_raw=column, embedded_vs_fixed_spec=embedded,
                column_and_embedded_equality_required=False,
                mismatches=[label for label, value in [("COLUMN_RAW", column), ("EMBEDDED_SPEC", embedded)] if value is False])


def receipt_stages(receipts: list[dict], start_save_failure_evidence: bool = False) -> dict:
    """SYS-11: stage presence and claims; does not create or repair receipts."""
    starts = [r for r in receipts if r.get("phase") == "START"]
    ends = [r for r in receipts if r.get("phase") == "END"]
    warnings = []
    if any(r.get("phase") not in {"START", "END"} for r in receipts):
        warnings.append("UNKNOWN_PHASE")
    valid_scope = lambda r: all(isinstance(r.get(k), str) and bool(r[k].strip()) for k in ("run_id", "task_id"))
    scopes = {(r.get("run_id"), r.get("task_id")) for r in receipts if valid_scope(r)}
    if len(scopes) > 1:
        warnings.append("MIXED_RUN_OR_TASK_SCOPE")
    if any(not valid_scope(r) for r in receipts):
        warnings.append("RUN_OR_TASK_SCOPE_MISSING")
    if len(starts) > 1 or len(ends) > 1:
        state = "DUPLICATE_PHASE_UNVERIFIED"
    elif starts and ends:
        state = "PAIR_PRESENT"
    elif starts:
        state = "START_ONLY_IN_PROGRESS_OR_END_MISSING"
    elif ends:
        state = "END_WITH_START_SAVE_FAILURE_EVIDENCE" if start_save_failure_evidence is True else "END_WITHOUT_START_UNVERIFIED"
    else:
        state = "NO_RECEIPTS_UNVERIFIED"
    if any(r.get("run_status") != "RUNNING" for r in starts):
        warnings.append("START_STATUS_NOT_RUNNING")
    if any(r.get("run_status") not in {"PASS", "PARTIAL", "FAIL", "UNVERIFIED", "NO_RACE"} for r in ends):
        warnings.append("END_STATUS_NOT_TERMINAL_OR_UNKNOWN")
    return {"case": "SYS-11", "presence": state, "START_count": len(starts), "END_count": len(ends),
            "warnings": warnings, "receipt_presence_does_not_prove_delivery": True,
            "start_failure_evidence_is_caller_claim": True, "production_GO": False}


def nonrace_research(official_status: str, summary_kind: str, result_kind: str) -> dict:
    """SYS-12: study classification only, no Daily writer/settlement decision."""
    summary = summary_kind if summary_kind in {"NON_RACE_SUMMARY", "RACE_SUMMARY", "MISSING"} else "UNVERIFIED"
    result = result_kind if result_kind in {"OFFICIAL_RESULT", "SHADOW_DRY_RUN", "MISSING"} else "UNVERIFIED"
    if official_status not in {"NO_RACE_VERIFIED", "RACE_VERIFIED"} or "UNVERIFIED" in {summary, result}:
        consistency = "UNVERIFIED"
    elif official_status == "NO_RACE_VERIFIED":
        consistency = "CONFLICT_REVIEW" if result == "OFFICIAL_RESULT" or summary == "RACE_SUMMARY" else "NONRACE_OBSERVATION_ONLY"
    elif summary == "NON_RACE_SUMMARY":
        consistency = "CONFLICT_REVIEW"
    elif result != "OFFICIAL_RESULT":
        consistency = "UNVERIFIED_MISSING_OFFICIAL_RESULT"
    else:
        consistency = "RACE_RESULT_OBSERVATION_ONLY"
    return {"case": "SYS-12", "mode": "CLASSIFICATION_RESEARCH_ONLY",
            "summary_semantic_class": summary, "result_semantic_class": result,
            "consistency": consistency, "NON_RACE_SUMMARY_is_official_RESULT": False,
            "settlement_or_LOCK_validity": "NOT_EVALUATED", "production_GO": False}


def _typed_equal(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def daily_display_fixture(expected: dict, observed: dict) -> dict:
    """SYS-13 checks synthetic display evidence retention; no formatter change."""
    required = ["audit_status", "scope", "counts", "receipts", "unverified"]
    missing = [key for key in required if key not in expected or key not in observed]
    changed = [key for key in required if key not in missing and not _typed_equal(expected[key], observed[key])]
    extra = sorted(set(observed) - set(expected))
    return {"case": "SYS-13", "mode": "SYNTHETIC_DISPLAY_COMPARISON_ONLY",
            "required_fields_missing": missing, "required_fields_changed": changed,
            "extra_fields_for_review": extra,
            "contract_match": not missing and not changed and not extra,
            "actual_Daily_prompt_execution": "UNVERIFIED_NOT_EXECUTED", "production_GO": False}


def notification_axes(send: dict, arrival: dict, receipt: dict) -> dict:
    """SYS-29 never sends. Supplied evidence claims remain independent."""
    def observation(value):
        known = (isinstance(value, dict) and value.get("status") in {"CONFIRMED", "FAILED"}
                 and value.get("verified") is True and isinstance(value.get("evidence_ref"), str)
                 and bool(value["evidence_ref"]))
        return {"status": value["status"] if known else "UNVERIFIED",
                "evidence_class": "SUPPLIED_CLAIM_NOT_AUTHENTICATED_HERE"}
    return {"case": "SYS-29", "send": observation(send), "arrival": observation(arrival),
            "receipt": observation(receipt), "derived_E2E_success": "NOT_ASSIGNED",
            "status_scope": "SUPPLIED_EVIDENCE_CLASSIFICATION_NOT_EXTERNAL_VERIFICATION",
            "external_evidence_authentication": "UNVERIFIED",
            "notification_sends_executed": 0, "production_GO": False}


def dispatch(operation: str, data: dict) -> dict:
    if operation == "SYS-05": return event_scope(data["rows"], data["read_status"])
    if operation == "SYS-06": return key_duplicates(data["records"])
    if operation == "SYS-07": return hash_spec_research(data["record"], data.get("profile"))
    if operation == "SYS-08": return {"case": "SYS-08", "field_kind": field_kind(data["record"], data["key"]), "production_GO": False}
    if operation == "SYS-11": return receipt_stages(data["receipts"], data.get("start_save_failure_evidence", False))
    if operation == "SYS-12": return nonrace_research(data["official_status"], data["summary_kind"], data["result_kind"])
    if operation == "SYS-13": return daily_display_fixture(data["expected"], data["observed"])
    if operation == "SYS-29": return notification_axes(data.get("send"), data.get("arrival"), data.get("receipt"))
    raise ValueError("OPERATION_UNKNOWN")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("AMBIGUOUS_JSON")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("NONFINITE_JSON")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["SYS-05", "SYS-06", "SYS-07", "SYS-08", "SYS-11", "SYS-12", "SYS-13", "SYS-29"])
    parser.add_argument("input_file", type=Path)
    args = parser.parse_args()
    try:
        with args.input_file.open("rb") as stream:
            raw = stream.read(2_097_153)
        if len(raw) > 2_097_152: raise ValueError("INPUT_TOO_LARGE")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_nonfinite)
        report = dispatch(args.operation, data)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError, AttributeError):
        print(json.dumps({"status": "INPUT_ERROR", "production_GO": False}))
        raise SystemExit(2)
