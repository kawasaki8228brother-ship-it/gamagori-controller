"""Read-only operational OBS QA on a PROPOSED normalized local input.

No Airtable/Automation access, repair, event writer, eligibility or LOCK verdict.
Missing independently verified OBS contract fields stay UNVERIFIED.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json


RELATED_A_REFERENCE = {
    "main_version": "v3", "model": "Model 1.0 FROZEN", "execution_patch": "2026-09-18.1",
    "received_hash_label": "SHA256", "received_hash_verbatim": "d462767f4448e28fc735df7363fb1a75137c5e7f",
    "observed_hex_characters": 40, "sha256_length_matches": False,
    "algorithm": "UNVERIFIED", "is_independently_matched_OBS_contract": False,
}
UNVERIFIED_QUESTIONS = {
    "payload_uuid_mandatory": "UNVERIFIED", "column_uuid_only_eligibility": "UNVERIFIED",
    "run_start_empty_source_evidence_allowed": "UNVERIFIED",
    "missing_source_evidence_formal_violation": "UNVERIFIED",
}
CANONICAL_PROFILE = "LOCAL_PROPOSED_SORTED_COMPACT_ASCII_JSON_V001_NOT_CONFIRMED_A_PROFILE"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def confirmed_a_idempotency(producer_run_id, event_kind):
    """Confirmed formula only. Return no producer/raw values in QA reports."""
    if not isinstance(producer_run_id, str) or not producer_run_id or event_kind not in ("RUN_START", "RUN_END"):
        raise ValueError("CONFIRMED_A_FORMULA_INPUT_UNAVAILABLE")
    return _sha(("1|A|" + producer_run_id + "|" + event_kind).encode("utf-8"))


def _parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_KEY")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("NONFINITE_JSON")
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError("PAYLOAD_NOT_OBJECT")
    return value


def _compare(columns, payload, field):
    if field not in columns and field not in payload:
        return "BOTH_MISSING"
    if field not in columns:
        return "MISSING_COLUMNS"
    if field not in payload:
        return "MISSING_PAYLOAD"
    if columns[field] is None and payload[field] is None:
        return "BOTH_NULL"
    if columns[field] is None:
        return "NULL_COLUMNS"
    if payload[field] is None:
        return "NULL_PAYLOAD"
    return "MATCH" if type(columns[field]) is type(payload[field]) and columns[field] == payload[field] else "MISMATCH"


def _evidence(payload):
    if "source_evidence" not in payload:
        return "MISSING_FIELD"
    value = payload["source_evidence"]
    if value is None:
        return "NULL"
    if not isinstance(value, list):
        return "MALFORMED"
    if not value:
        return "EMPTY_ARRAY"
    # These are normalized proposal labels, not guessed official payload fields.
    known = {"DECLARED_NORMAL", "MISSING", "EXPLICIT_MISSING", "FETCH_FAILED"}
    statuses = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("status"), str) or item["status"] not in known:
            return "MALFORMED"
        statuses.append("EXPLICIT_MISSING" if item["status"] == "MISSING" else item["status"])
    return statuses[0] if len(set(statuses)) == 1 else "MIXED"


def _provided_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _audit_one(row, index):
    result = {"row_index": index, "status": "CONTRACT_UNVERIFIED", "scope": "UNVERIFIED",
              "reasons": [], "field_comparisons": {}, "source_evidence": "UNREADABLE_OR_UNVERIFIED_PAYLOAD",
              "hashes": {"raw_match": None, "pre_post_equal": None, "local_canonical_match": None},
              "a_idempotency": {"evaluated": False, "all_provided_keys_match": None,
                                "column_match": None, "payload_match": None},
              "source_claim_authenticity": "UNVERIFIED"}
    if not isinstance(row, dict) or not isinstance(row.get("columns"), dict):
        result["reasons"].append("NORMALIZED_COLUMNS_UNAVAILABLE")
        return result, None
    columns = row["columns"]
    # Explicit LOCK or B metadata is outside this A operational checker.
    if columns.get("event_kind") == "LOCK" or columns.get("source") == "B":
        result.update(status="OUT_OF_SCOPE", scope="LOCK_OUT_OF_SCOPE" if columns.get("event_kind") == "LOCK" else "B_OUT_OF_SCOPE")
        result["reasons"].append("NO_A_OPERATIONAL_OR_LOCK_JUDGMENT_APPLIED")
        return result, None
    text = row.get("payload_raw")
    if not isinstance(text, str):
        result["reasons"].append("PAYLOAD_RAW_STRING_UNAVAILABLE")
        return result, None
    try:
        raw = text.encode("utf-8")
        if len(raw) > 1_000_000:
            raise ValueError("LOCAL_RESOURCE_LIMIT")
        payload = _parse(text)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        result.update(status="INCONSISTENCY", scope="PAYLOAD_UNREADABLE")
        result["reasons"].append("PAYLOAD_JSON_OR_UTF8_UNREADABLE")
        return result, None
    compared = {field: _compare(columns, payload, field)
                for field in ("event_uuid", "source", "producer_run_id", "event_kind", "idempotency_key")}
    result["field_comparisons"] = compared
    mismatches = [field for field, state in compared.items() if state == "MISMATCH"]
    result["reasons"].extend(field.upper() + "_PROVIDED_VALUES_DIFFER" for field in mismatches)
    observed_sources = {value for value in (columns.get("source"), payload.get("source")) if isinstance(value, str)}
    kinds = {value for value in (columns.get("event_kind"), payload.get("event_kind")) if isinstance(value, str)}
    if observed_sources == {"B"} or kinds == {"LOCK"}:
        result.update(status="OUT_OF_SCOPE", scope="B_OUT_OF_SCOPE" if observed_sources == {"B"} else "LOCK_OUT_OF_SCOPE")
        return result, None
    if (compared["source"] == "MISMATCH" or compared["event_kind"] == "MISMATCH"
            or observed_sources != {"A"} or len(kinds) != 1 or not kinds.issubset({"RUN_START", "RUN_END"})):
        result.update(status="INCONSISTENCY" if mismatches else "CONTRACT_UNVERIFIED", scope="SOURCE_OR_OPERATION_UNRESOLVED")
        result["reasons"].append("NO_CONFIRMED_A_START_END_FORMULA_APPLIED")
        return result, None
    kind = next(iter(kinds))
    result.update(scope="A_OPERATIONAL_OBS", event_kind=kind)
    result["source_evidence"] = _evidence(payload)
    result["operational_presence"] = {field: "MISSING" if field not in payload else "NULL" if payload[field] is None else "PROVIDED"
                                      for field in ("started_at", "ended_at", "stages", "errors")}
    result["stage_count"] = len(payload["stages"]) if isinstance(payload.get("stages"), list) else None
    result["error_count"] = len(payload["errors"]) if isinstance(payload.get("errors"), list) else None
    unknown = any(state in ("BOTH_MISSING", "MISSING_COLUMNS", "MISSING_PAYLOAD", "BOTH_NULL", "NULL_COLUMNS", "NULL_PAYLOAD")
                  for state in compared.values())
    if compared["event_uuid"] in ("MISSING_PAYLOAD", "BOTH_MISSING", "NULL_PAYLOAD", "BOTH_NULL"):
        result["reasons"].append("PAYLOAD_UUID_REQUIREMENT_UNVERIFIED")
    if result["source_evidence"] in ("MISSING_FIELD", "NULL", "EMPTY_ARRAY", "MALFORMED"):
        unknown = True
        result["reasons"].append("SOURCE_EVIDENCE_REQUIREMENT_OR_FORMAT_UNVERIFIED")
    hashes = row.get("hashes", {})
    if not isinstance(hashes, dict):
        hashes = {}
        unknown = True
        result["reasons"].append("HASH_DECLARATIONS_UNAVAILABLE")
    canonical = _canonical(payload)
    raw_digest, canonical_digest = _sha(raw), _sha(canonical)
    raw_claim = hashes.get("raw_sha256")
    if raw_claim is not None:
        result["hashes"]["raw_match"] = _provided_sha(raw_claim) and raw_claim == raw_digest
        if not result["hashes"]["raw_match"]:
            result["reasons"].append("DECLARED_RAW_SHA256_DOES_NOT_MATCH_BYTES")
            mismatches.append("raw_sha256")
    else:
        unknown = True
    before, after = hashes.get("canonical_before_sha256"), hashes.get("canonical_after_sha256")
    if before is not None and after is not None:
        if not _provided_sha(before) or not _provided_sha(after):
            mismatches.append("canonical_hash_format")
            result["reasons"].append("DECLARED_CANONICAL_SHA256_FORMAT_INCONSISTENT")
        else:
            result["hashes"]["pre_post_equal"] = before == after
            result["hashes"]["local_canonical_match"] = before == after == canonical_digest
            if before != after:
                mismatches.append("canonical_pre_post")
                result["reasons"].append("PROVIDED_CANONICAL_PRE_POST_HASHES_DIFFER")
            elif before != canonical_digest:
                unknown = True
                result["reasons"].append("CANONICALIZATION_PROFILE_DIFFERS_A_PROFILE_UNVERIFIED")
    else:
        unknown = True
        result["reasons"].append("CANONICAL_PRE_POST_DECLARATIONS_UNAVAILABLE")
    producer_values = [value for value in (columns.get("producer_run_id"), payload.get("producer_run_id"))
                       if isinstance(value, str) and value]
    if producer_values and len(set(producer_values)) == 1 and compared["producer_run_id"] != "MISMATCH":
        expected = confirmed_a_idempotency(producer_values[0], kind)
        checks = []
        result["a_idempotency"]["evaluated"] = True
        for side, value in (("column", columns), ("payload", payload)):
            if "idempotency_key" in value and value["idempotency_key"] is not None:
                matched = value["idempotency_key"] == expected
                checks.append(matched)
                result["a_idempotency"][side + "_match"] = matched
                if not matched:
                    mismatches.append("confirmed_key")
                    result["reasons"].append("CONFIRMED_A_IDEMPOTENCY_FORMULA_MISMATCH")
        result["a_idempotency"]["all_provided_keys_match"] = all(checks) if checks else None
        if not checks:
            unknown = True
    else:
        unknown = True
        result["reasons"].append("PRODUCER_IDENTITY_UNAVAILABLE_OR_CONFLICTING")
    result["status"] = "INCONSISTENCY" if mismatches else "CONTRACT_UNVERIFIED" if unknown else "OBSERVED"
    supplied_keys = {value for value in (columns.get("idempotency_key"), payload.get("idempotency_key")) if _provided_sha(value)}
    # Internal duplicate analysis returns no actual key, UUID, run ID or errors.
    internal = {"keys": supplied_keys, "raw_digest": raw_digest, "uuid_missing": "event_uuid" not in payload}
    return result, internal


def audit_obs_rows(rows):
    """Return fixed-code observations, never formal OBS/LOCK eligibility."""
    if not isinstance(rows, list):
        raise ValueError("NORMALIZED_OBS_ROWS_LIST_REQUIRED")
    reports, internals = [], []
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        try:
            report, internal = _audit_one(row, index)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            report, internal = ({"row_index": index, "status": "INCONSISTENCY", "scope": "NORMALIZED_INPUT_UNREADABLE",
                                 "reasons": ["NORMALIZED_ROW_UNREADABLE"], "source_evidence": "UNREADABLE_OR_UNVERIFIED_PAYLOAD"}, None)
        reports.append(report)
        internals.append(internal)
        if internal:
            for key in internal["keys"]:
                groups[key].append(index)
    duplicate_groups = 0
    for indices in groups.values():
        if len(indices) > 1:
            duplicate_groups += 1
            different = len({internals[index]["raw_digest"] for index in indices}) > 1
            for index in indices:
                reports[index]["reasons"].append("DUPLICATE_KEY_DIFFERENT_RAW_PAYLOAD" if different else "REPEATED_IDENTICAL_KEY_OBSERVATION")
                if different:
                    reports[index]["status"] = "INCONSISTENCY"
    operational = [r for r in reports if r["scope"] == "A_OPERATIONAL_OBS"]
    return {"status": "READ_ONLY_OBSERVATIONAL_QA_NOT_ELIGIBILITY", "input_rows": len(rows),
            "query_completeness": "UNVERIFIED_NO_SOURCE_QUERY_PERFORMED",
            "A_operational_rows": len(operational), "status_counts": dict(Counter(r["status"] for r in reports)),
            "payload_uuid_missing_rows": sum(bool(item and item["uuid_missing"]) for item in internals),
            "uuid_comparison_counts": dict(Counter(r.get("field_comparisons", {}).get("event_uuid", "UNASSESSED") for r in reports)),
            "source_evidence_counts": dict(Counter(r["source_evidence"] for r in operational)),
            "hash_counts": {"raw_matches": sum(r["hashes"]["raw_match"] is True for r in operational),
                            "pre_post_equal": sum(r["hashes"]["pre_post_equal"] is True for r in operational),
                            "local_canonical_matches": sum(r["hashes"]["local_canonical_match"] is True for r in operational)},
            "idempotency_counts": {"evaluated_A_rows": sum(r["a_idempotency"]["evaluated"] for r in operational),
                                   "matching_A_rows": sum(r["a_idempotency"]["all_provided_keys_match"] is True for r in operational),
                                   "unique_A_provided_keys": len(groups), "duplicate_key_groups": duplicate_groups},
            "rows": reports, "normalized_input_contract": "PROPOSED_NOT_ACTUAL_A_FIELD_MAPPING",
            "actual_OBS_contract": "UNVERIFIED_NOT_INDEPENDENTLY_MATCHED", "unverified_questions": dict(UNVERIFIED_QUESTIONS),
            "local_canonical_profile": CANONICAL_PROFILE, "actual_A_canonicalization": "UNVERIFIED",
            "related_A_reference": dict(RELATED_A_REFERENCE), "source_claim_authenticity": "UNVERIFIED",
            "lock_eligibility": "NOT_ASSESSED_UNCHANGED", "production_go": False}


def make_synthetic_obs_fixture():
    """20 invented rows matching only requested counts, never 11/5 reconstruction."""
    rows = []
    for index in range(20):
        kind = "RUN_START" if index % 2 == 0 else "RUN_END"
        run_id = "SYNTHETIC_A_RUN_%02d" % (index // 2 + 1)
        key = confirmed_a_idempotency(run_id, kind)
        columns = {"event_uuid": "SYNTHETIC_OBS_COLUMN_%02d" % (index + 1), "source": "A",
                   "producer_run_id": run_id, "event_kind": kind, "idempotency_key": key}
        payload = {"classification": "SYNTHETIC_ONLY", "source": "A", "producer_run_id": run_id,
                   "event_kind": kind, "idempotency_key": key,
                   "started_at": "2099-01-01T09:%02d:00+09:00" % (index // 2),
                   "stages": [{"name": "SYNTHETIC_STAGE", "state": "RECORDED"}], "errors": []}
        if kind == "RUN_END":
            payload["ended_at"] = "2099-01-01T09:%02d:01+09:00" % (index // 2)
        if index >= 12:
            payload["event_uuid"] = columns["event_uuid"]
        if index != 0:
            payload["source_evidence"] = [] if index in (2, 4, 6) else [{"status": "DECLARED_NORMAL"}]
        raw = _canonical(payload)
        digest = _sha(raw)
        rows.append({"columns": columns, "payload_raw": raw.decode("ascii"),
                     "hashes": {"raw_sha256": digest, "canonical_before_sha256": digest, "canonical_after_sha256": digest}})
    return {"classification": "SYNTHETIC_ONLY", "purpose": "NOT_2026_11_05_OBS_RECONSTRUCTION",
            "rows": rows, "expected": {"input_rows": 20, "payload_uuid_missing_rows": 12,
            "source_evidence_missing_field_rows": 1, "source_evidence_empty_array_rows": 3,
            "local_canonical_matches": 20, "matching_A_idempotency_rows": 20, "unique_A_keys": 20}}
