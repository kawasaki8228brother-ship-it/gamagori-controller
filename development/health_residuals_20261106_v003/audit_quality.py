"""C4/C5/C7 pure supplied-input QA; C8 read-only audit design, not execution.

No application, HTTP, DB, production connector, scheduler or runtime port is used.
Only C7 explicitly reads/executes one hash-pinned local stdlib-only QA source.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import re
from types import ModuleType


PORT_SCOPE = "OFFLINE_ONLY_RUNTIME_INTEGRATION_OPEN"
OBS_SOURCE = "development/health_residuals_20261105_v001/obs_qa.py"
OBS_COMMIT = "48333a2315628ae17e1fa3ce4f8ef12c70e2662f"
OBS_SHA256 = "dc6bdc6b77a3c4ce4f5b718cfd43be7fe1cc0d08d4e0e54057949ce7032e5634"
_STATUSES = frozenset({"PENDING", "DATA_WAIT", "CLOSING_WINDOW", "FREEZE_ZONE", "SAFE_STOP",
                       "C_EVENT_DONE", "REOPENED", "TERMINAL"})
_HTTP_FIELDS = frozenset({"status_code", "fetch_state", "parse_state", "content_length",
                         "content_length_unit", "wire_body_bytes", "wire_count_unit",
                         "decoded_body_bytes", "decoded_count_unit", "content_encoding",
                         "text_encoding", "stream_completed", "document_end_observed",
                         "parsed_rows", "table_tag_observed"})


def _base():
    return {"port_scope": PORT_SCOPE, "runtime_integrated": False,
            "official_success": "NOT_ASSESSED", "source_authenticity": "UNVERIFIED",
            "production_go": False}


def _count(value):
    return type(value) is int and value >= 0


def diagnose_http_observation(observation):
    """Keep HTTP, fetch, parse, stream, lengths and document observations separate.

    wire_body_bytes means encoded entity bytes only if explicitly declared so;
    TLS/header/chunk-frame totals and re-encoded text are not Content-Length.
    No submitted header/body/URL/error text is returned.
    """
    result = _base()
    result.update(status="UNVERIFIED", reasons=[], http_status=None, fetch_state="UNKNOWN",
                  parse_state="UNKNOWN", content_length=None, wire_body_bytes=None,
                  decoded_body_bytes=None, length_comparison="UNVERIFIED",
                  stream_completed=None, document_end_observed=None,
                  parsed_rows=None, table_tag_observed=None, text_encoding="UNKNOWN")
    if not isinstance(observation, dict):
        result["reasons"] = ["HTTP_OBSERVATION_NOT_OBJECT"]
        return result
    reasons = result["reasons"]
    inconsistent = False
    if set(observation) - _HTTP_FIELDS:
        reasons.append("HTTP_UNKNOWN_FIELDS")
    status = observation.get("status_code")
    if status is None:
        reasons.append("HTTP_STATUS_UNOBSERVED")
    elif type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
        if not 200 <= status <= 299:
            reasons.append("HTTP_NON_SUCCESS_STATUS_OBSERVED")
    else:
        reasons.append("HTTP_STATUS_INVALID")
    for field, permitted in (("fetch_state", {"RETURNED", "FAILED", "UNKNOWN"}),
                             ("parse_state", {"PARSED", "REJECTED", "NOT_ATTEMPTED", "UNKNOWN"})):
        value = observation.get(field)
        if isinstance(value, str) and value in permitted:
            result[field] = value
            if value == "UNKNOWN":
                reasons.append(field.upper() + "_UNOBSERVED")
            elif value == "FAILED":
                reasons.append("FETCH_FAILED_DECLARED")
            elif value == "REJECTED":
                reasons.append("PARSE_REJECTED_DECLARED")
        else:
            reasons.append(field.upper() + "_UNOBSERVED_OR_INVALID")
    for field in ("content_length", "wire_body_bytes", "decoded_body_bytes", "parsed_rows"):
        value = observation.get(field)
        if _count(value):
            result[field] = value
        elif value is not None:
            reasons.append(field.upper() + "_INVALID")
    for field in ("stream_completed", "document_end_observed", "table_tag_observed"):
        value = observation.get(field)
        if type(value) is bool:
            result[field] = value
        else:
            reasons.append(field.upper() + "_UNOBSERVED_OR_INVALID")
    encoding = observation.get("content_encoding")
    encoding = encoding if encoding in ("identity", "gzip", "br") else "UNKNOWN"
    result["content_encoding"] = encoding
    if encoding == "UNKNOWN":
        reasons.append("CONTENT_ENCODING_UNVERIFIED")
    charset = observation.get("text_encoding")
    if isinstance(charset, str) and charset in {"utf-8", "shift_jis", "euc-jp", "ascii"}:
        result["text_encoding"] = charset
    else:
        reasons.append("TEXT_ENCODING_UNVERIFIED")
    length_unit = observation.get("content_length_unit")
    wire_unit = observation.get("wire_count_unit")
    decoded_unit = observation.get("decoded_count_unit")
    result["content_length_unit"] = "OCTETS" if length_unit == "OCTETS" else "UNKNOWN"
    result["wire_count_unit"] = "ENCODED_ENTITY_OCTETS" if wire_unit == "ENCODED_ENTITY_OCTETS" else "UNKNOWN"
    result["decoded_count_unit"] = "DECODED_ENTITY_OCTETS" if decoded_unit == "DECODED_ENTITY_OCTETS" else "UNKNOWN"
    if length_unit != "OCTETS" or wire_unit != "ENCODED_ENTITY_OCTETS":
        reasons.append("LENGTH_UNITS_OR_LAYER_UNVERIFIED")
    if result["decoded_body_bytes"] is not None and decoded_unit != "DECODED_ENTITY_OCTETS":
        reasons.append("DECODED_LENGTH_LAYER_UNVERIFIED")
    if (result["content_length"] is not None and result["wire_body_bytes"] is not None
            and length_unit == "OCTETS" and wire_unit == "ENCODED_ENTITY_OCTETS"):
        matches = result["content_length"] == result["wire_body_bytes"]
        result["length_comparison"] = "ENCODED_ENTITY_MATCH" if matches else "ENCODED_ENTITY_MISMATCH"
        if not matches:
            reasons.append("ENCODED_ENTITY_LENGTH_MISMATCH")
            inconsistent = True
    else:
        reasons.append("CONTENT_LENGTH_COMPARISON_UNVERIFIED")
    if encoding in ("gzip", "br") and result["wire_body_bytes"] is None:
        reasons.append("COMPRESSED_DECODED_LENGTH_NOT_COMPARABLE")
    if (encoding == "identity" and result["wire_body_bytes"] is not None
            and result["decoded_body_bytes"] is not None and wire_unit == "ENCODED_ENTITY_OCTETS"
            and decoded_unit == "DECODED_ENTITY_OCTETS" and result["wire_body_bytes"] != result["decoded_body_bytes"]):
        reasons.append("IDENTITY_BODY_LENGTHS_CONTRADICT")
        inconsistent = True
    if result["stream_completed"] is False:
        reasons.append("STREAM_INCOMPLETE_DECLARED")
    if result["document_end_observed"] is False:
        reasons.append("DOCUMENT_END_NOT_OBSERVED")
    # HTTP response/parse/row claims never establish official correctness.
    result["status"] = "INCONSISTENCY" if inconsistent else "UNVERIFIED" if reasons else "CONSISTENT_SUPPLIED_DECLARATIONS_ONLY"
    result["reasons"] = list(dict.fromkeys(reasons))
    return result


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def summarize_prior_unfinished(states, target_date):
    """Aggregate only supplied unique normalized {race_id,status} state views.

    Nonterminal is a state observation, not missed LOCK/event eligibility.
    Any malformed/unknown row leaves the complete-cohort count UNVERIFIED.
    """
    result = _base()
    result.update(status="UNVERIFIED", reasons=[], provided_rows=None,
                  previous_day_nonterminal_count=None, observed_valid_previous_nonterminal_count=0,
                  older_nonterminal_count=0, duplicate_identity_rows=0, invalid_date_rows=0,
                  unknown_field_rows=0, missing_field_rows=0, unknown_status_rows=0,
                  query_completeness="UNVERIFIED_NO_DB_READ", rows=[])
    result["state_contract_reference"] = {"path": "models.py", "enum": "RaceStatus", "commit": OBS_COMMIT}
    target = _day(target_date)
    if target is None or not isinstance(states, list):
        result["reasons"] = ["STATE_TARGET_OR_COLLECTION_UNVERIFIED"]
        return result
    result["provided_rows"] = len(states)
    identities = Counter(row["race_id"] for row in states if isinstance(row, dict) and isinstance(row.get("race_id"), str))
    try:
        previous = target - timedelta(days=1)
    except OverflowError:
        result["reasons"] = ["PREVIOUS_CALENDAR_DAY_UNREPRESENTABLE"]
        return result
    bad = False
    for index, row in enumerate(states):
        codes = []
        if not isinstance(row, dict):
            codes.append("STATE_ROW_NOT_OBJECT")
        else:
            if set(row) - {"race_id", "status"}:
                codes.append("STATE_UNKNOWN_FIELDS")
                result["unknown_field_rows"] += 1
            if not {"race_id", "status"} <= set(row):
                codes.append("STATE_REQUIRED_FIELD_MISSING")
                result["missing_field_rows"] += 1
            identity = row.get("race_id")
            matched = re.fullmatch(r"([0-9]{8})_GAM_(?:0[1-9]|1[0-2])R", identity) if isinstance(identity, str) else None
            day = _day(matched[1]) if matched else None
            if day is None:
                codes.append("STATE_RACE_DATE_OR_ID_INVALID")
                result["invalid_date_rows"] += 1
            if isinstance(identity, str) and identities[identity] != 1:
                codes.append("STATE_DUPLICATE_IDENTITY_UNVERIFIED")
                result["duplicate_identity_rows"] += 1
            status = row.get("status")
            if not isinstance(status, str) or status not in _STATUSES:
                codes.append("STATE_STATUS_UNOBSERVED_OR_UNKNOWN")
                result["unknown_status_rows"] += 1
            if not codes and status != "TERMINAL":
                if day == previous:
                    result["observed_valid_previous_nonterminal_count"] += 1
                elif day < previous:
                    result["older_nonterminal_count"] += 1
        if codes:
            bad = True
        result["rows"].append({"row_index": index, "reasons": codes})
    if bad:
        result["reasons"].append("STATE_COLLECTION_HAS_UNVERIFIED_ROWS")
    else:
        result["status"] = "OBSERVED_PROVIDED_COLLECTION_ONLY"
        result["previous_day_nonterminal_count"] = result["observed_valid_previous_nonterminal_count"]
    result["count_scope"] = "PROVIDED_UNIQUE_VALID_ROWS_NOT_SOURCE_COMPLETENESS"
    return result


def _pinned_obs():
    path = Path(__file__).resolve().parents[1] / "health_residuals_20261105_v001" / "obs_qa.py"
    raw = path.read_bytes()
    if len(raw) != 16027 or hashlib.sha256(raw).hexdigest() != OBS_SHA256:
        raise ValueError("PINNED_OBS_SOURCE_MISMATCH")
    module = ModuleType("_health_v003_pinned_obs_qa")
    # Compile reviewed bytes directly: no module cache or app import is created.
    exec(compile(raw, OBS_SOURCE, "exec"), module.__dict__)
    return module


def make_synthetic_operational_fixture():
    return _pinned_obs().make_synthetic_obs_fixture()


def audit_operational_rows(rows):
    """Reuse the frozen A-only checker; never apply its formula to B or LOCK."""
    try:
        report = _pinned_obs().audit_obs_rows(rows)
    except (ValueError, TypeError, OSError):
        return dict(_base(), status="UNVERIFIED", reasons=["PINNED_OBS_OR_INPUT_UNAVAILABLE"])
    return {**_base(), "status": "OFFLINE_PINNED_OBS_QA_ONLY", "report": report,
            "implementation_reference": {"path": OBS_SOURCE, "commit": OBS_COMMIT,
                                         "bytes": 16027, "sha256": OBS_SHA256},
            "B_formula": "UNVERIFIED_NOT_PROVIDED_A_FORMULA_NOT_APPLIED",
            "related_reference_notice": "V001_REPORT_RETAINS_HISTORICAL_40_HEX_REFERENCE_SEE_V002_CORRECTION_NOT_OBS_AUTHORITY",
            "correction_reference": "development/health_residuals_20261106_v002/OBS_SHA_CORRECTION.json"}


def sqlite_offhours_audit_plan(request):
    """Pure design gate. Even complete declarations never authorize a DB read."""
    result = _base()
    result.update(status="UNVERIFIED", reasons=[], planned_query="PRAGMA journal_mode",
                  query_semantics="READ_VALUE_ONLY_NO_ASSIGNMENT", db_open_mode="mode=ro",
                  live_immutable_permitted=False, normal_shm_read_marks_possible=True,
                  db_connection_performed=False, live_execution_authorized=False,
                  offhours_reservation_created=False)
    required = {"window", "window_confirmed", "service_identity_confirmed", "individual_go_reference_sha256",
                "active_processing_absent_confirmed", "db_open_mode", "immutable"}
    if not isinstance(request, dict) or set(request) != required:
        result["reasons"] = ["OFFHOURS_AUDIT_CONTEXT_FIELDS_UNVERIFIED"]
        return result
    if request["window"] != "OFFHOURS" or request["window_confirmed"] is not True:
        result["reasons"].append("OFFHOURS_WINDOW_UNVERIFIED")
    if request["service_identity_confirmed"] is not True:
        result["reasons"].append("DB_SERVICE_IDENTITY_UNVERIFIED")
    if request["active_processing_absent_confirmed"] is not True:
        result["reasons"].append("ACTIVE_PROCESSING_UNVERIFIED")
    reference = request["individual_go_reference_sha256"]
    if not isinstance(reference, str) or not re.fullmatch(r"[0-9a-f]{64}", reference):
        result["reasons"].append("INDIVIDUAL_GO_REFERENCE_UNAVAILABLE")
    if request["db_open_mode"] != "mode=ro" or request["immutable"] is not False:
        result["reasons"].append("LIVE_SQLITE_READ_MODE_INVALID")
    if not result["reasons"]:
        result["status"] = "DESIGN_DECLARATIONS_ONLY_NOT_EXECUTION_GO"
    result["approval_authenticity"] = "UNVERIFIED_REFERENCE_IS_NOT_APPROVAL"
    return result
