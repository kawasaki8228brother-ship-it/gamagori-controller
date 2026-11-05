"""Pure, read-only supplied-evidence coverage checks; no source/store calls.

Complete local byte agreement is never official-source authenticity or GO.
"""
from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re


_NS = "MODEL11_THIRD_RESEARCH"
_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_JST = timezone(timedelta(hours=9))
_LIMIT = 16_000_000  # Local input-resource guard only; not a study threshold.
LEDGER_FIELDS = ("race_key", "namespace", "race_id", "storage_id", "input_sha", "model_sha",
                 "deadline", "state", "receipt_sha", "committed_at", "finalized_at")
_BLOBS = ("input", "forecast", "receipt", "completion", "metadata")


class _Invalid(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise _Invalid(reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _time(value):
    _need(isinstance(value, str) and not value.endswith("-00:00"), "INVALID_AWARE_TIMESTAMP")
    matched = re.fullmatch(r"\d{4}-\d{2}-\d{2}T(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})(?:\.\d{1,6})?(?P<z>Z|[+-]\d{2}:\d{2})", value)
    _need(matched is not None, "INVALID_AWARE_TIMESTAMP")
    _need(int(matched["h"]) < 24 and int(matched["m"]) < 60 and int(matched["s"]) < 60,
          "INVALID_AWARE_TIMESTAMP")
    if matched["z"] != "Z":
        _need(int(matched["z"][1:3]) < 24 and int(matched["z"][4:6]) < 60, "INVALID_AWARE_TIMESTAMP")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _Invalid("INVALID_AWARE_TIMESTAMP") from None


def _date(value):
    try:
        _need(isinstance(value, str) and date.fromisoformat(value).isoformat() == value, "INVALID_TARGET_DATE")
    except (ValueError, TypeError):
        raise _Invalid("INVALID_TARGET_DATE") from None
    return value


def _decode(value):
    _need(isinstance(value, str) and len(value) <= 4 * ((_LIMIT + 2) // 3), "RAW_BLOB_MISSING_OR_OVERSIZE")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise _Invalid("RAW_BLOB_BASE64_INVALID") from None
    _need(len(raw) <= _LIMIT, "RAW_BLOB_MISSING_OR_OVERSIZE")
    return raw


def _object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        raise _Invalid("NONFINITE_JSON")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise _Invalid("RAW_JSON_INVALID") from None
    _need(isinstance(result, dict), "RAW_JSON_NOT_OBJECT")
    return result


def frame_prediction_evidence(ledger, *, input_raw, forecast_raw, receipt_raw,
                              completion_raw, metadata_raw, observation="READ_OK"):
    """Pure JSON-safe framing; does not read a store or authenticate its origin.

    Whitelists ledger fields so tokens/session/PID/paths are never exported.
    Required fields match the frozen v005 ledger, plus independently read
    OWNER/meta storage_id. The caller is responsible for read-only extraction.
    """
    _need(isinstance(ledger, dict), "LEDGER_OBJECT_REQUIRED")
    _need(isinstance(ledger.get("race_id"), str) and _ID.fullmatch(ledger["race_id"]), "RACE_ID_INVALID")
    raw = {"input": input_raw, "forecast": forecast_raw, "receipt": receipt_raw,
           "completion": completion_raw, "metadata": metadata_raw}
    _need(all(isinstance(value, bytes) and len(value) <= _LIMIT for value in raw.values()), "RAW_BYTES_REQUIRED")
    return {"evidence_schema": "SHADOW_READONLY_EVIDENCE_V001_PROPOSED", "race_id": ledger["race_id"],
            "observation": observation,
            "ledger": {field: deepcopy(ledger.get(field)) for field in LEDGER_FIELDS},
            "raw_blobs": {key + "_b64": base64.b64encode(value).decode("ascii") for key, value in raw.items()}}


def _schedule(schedule, target_date):
    _need(isinstance(schedule, dict), "SCHEDULE_MISSING")
    raw = _decode(schedule.get("raw_manifest_b64"))
    _need(type(schedule.get("manifest_bytes")) is int and schedule["manifest_bytes"] == len(raw), "SCHEDULE_BYTE_COUNT_MISMATCH")
    _need(isinstance(schedule.get("manifest_sha256"), str)
          and _HEX.fullmatch(schedule["manifest_sha256"])
          and _sha(raw) == schedule["manifest_sha256"], "SCHEDULE_HASH_MISMATCH")
    manifest = _object(raw)
    _need(set(manifest) == {"schema", "venue", "target_date", "source_id", "races"}, "SCHEDULE_FIELDS_INVALID")
    _need(manifest["schema"] == "OFFICIAL_DAY_SCHEDULE_V001_PROPOSED", "SCHEDULE_SCHEMA_UNREVIEWED")
    _need(manifest["venue"] == "GAMAGORI", "SCHEDULE_VENUE_MISMATCH")
    _need(manifest["target_date"] == target_date, "SCHEDULE_TARGET_DATE_MISMATCH")
    _need(isinstance(manifest["source_id"], str) and _ID.fullmatch(manifest["source_id"]), "SCHEDULE_SOURCE_ID_INVALID")
    approval = schedule.get("approval")
    _need(isinstance(approval, dict) and approval.get("approved") is True, "SCHEDULE_APPROVAL_UNVERIFIED")
    _need(approval.get("declared_external_verification") is True, "SCHEDULE_EXTERNAL_REVIEW_NOT_DECLARED")
    for key in ("venue", "target_date", "source_id"):
        _need(approval.get(key) == manifest[key], "SCHEDULE_APPROVAL_BINDING_MISMATCH")
    _need(approval.get("manifest_sha256") == _sha(raw), "SCHEDULE_APPROVAL_HASH_MISMATCH")
    for key in ("mapping_sha256", "evidence_sha256"):
        _need(isinstance(approval.get(key), str) and _HEX.fullmatch(approval[key]), "SCHEDULE_REVIEW_EVIDENCE_MISSING")
    _need(isinstance(manifest["races"], list), "SCHEDULE_ROWS_MISSING")
    return manifest, approval


def _prediction(entry, row, target_date, namespace, expected_storage_id):
    _need(isinstance(entry, dict), "OBSERVATION_OBJECT_REQUIRED")
    observation = entry.get("observation")
    explicit = {"ABSENT": "OBSERVED_ABSENT", "NOT_SAVED": "PREDICTION_NOT_SAVED",
                "READ_FAILED": "PREDICTION_READ_FAILED", "UNCERTAIN": "PREDICTION_SAVE_UNCERTAIN",
                "CORRUPT": "PREDICTION_DECLARED_CORRUPT"}
    if observation in explicit:
        raise _Invalid(explicit[observation])
    _need(observation == "READ_OK", "OBSERVATION_STATUS_UNVERIFIED")
    _need(entry.get("evidence_schema") == "SHADOW_READONLY_EVIDENCE_V001_PROPOSED", "OBSERVATION_SCHEMA_UNREVIEWED")
    ledger = entry.get("ledger")
    _need(isinstance(ledger, dict), "LEDGER_EVIDENCE_MISSING")
    state = ledger.get("state")
    if state in ("RESERVED", "STAGING", "COMPLETION_PENDING", "HOLD_UNCERTAIN"):
        raise _Invalid("PREDICTION_SAVE_UNCERTAIN")
    if state in ("NOT_SAVED", "CANCELLED_UNSAVED"):
        raise _Invalid("PREDICTION_NOT_SAVED")
    _need(state == "COMMITTED", "LEDGER_STATE_UNVERIFIED")
    expected_key = _sha((namespace + "\0" + row["race_id"]).encode("ascii"))
    _need(ledger.get("race_key") == expected_key and ledger.get("race_id") == row["race_id"]
          and entry.get("race_id") == row["race_id"] and ledger.get("namespace") == namespace, "LEDGER_KEY_OR_NAMESPACE_MISMATCH")
    _need(isinstance(ledger.get("storage_id"), str)
          and re.fullmatch(r"[0-9a-f]{32}", ledger["storage_id"]), "STORAGE_IDENTITY_UNVERIFIED")
    if expected_storage_id is not None:
        _need(ledger["storage_id"] == expected_storage_id, "STORAGE_IDENTITY_MISMATCH")
    blobs = entry.get("raw_blobs")
    _need(isinstance(blobs, dict), "READBACK_RAW_BLOBS_MISSING")
    raw = {key: _decode(blobs.get(key + "_b64")) for key in _BLOBS}
    receipt, completion, metadata, envelope = (_object(raw[key]) for key in ("receipt", "completion", "metadata", "forecast"))
    _need(_sha(raw["receipt"]) == ledger.get("receipt_sha"), "RECEIPT_HASH_MISMATCH")
    _need(receipt.get("kind") == "IMMUTABLE_FORECAST_RECEIPT_V005"
          and receipt.get("key") == expected_key and receipt.get("race_id") == row["race_id"]
          and receipt.get("namespace") == namespace and receipt.get("storage_id") == ledger["storage_id"], "RECEIPT_IDENTITY_MISMATCH")
    for name in ("input", "forecast"):
        _need(type(receipt.get(name + "_bytes")) is int and receipt[name + "_bytes"] == len(raw[name])
              and receipt.get(name + "_sha256") == _sha(raw[name]), "RAW_" + name.upper() + "_READBACK_MISMATCH")
    _need(ledger.get("input_sha") == _sha(raw["input"]), "LEDGER_INPUT_HASH_MISMATCH")
    _need(receipt.get("metadata_sha256") == _sha(raw["metadata"]), "COMMIT_METADATA_HASH_MISMATCH")
    _need(completion.get("receipt_sha256") == ledger["receipt_sha"], "COMPLETION_RECEIPT_BINDING_MISMATCH")
    _need(receipt.get("validity") == "REQUIRES_COMMITTED_LEDGER_AND_READBACK", "RECEIPT_VALIDITY_UNVERIFIED")
    _need(envelope.get("schema") == "MODEL11_INDEPENDENT_SHADOW_RECORD_V005"
          and envelope.get("namespace") == namespace and envelope.get("race_id") == row["race_id"], "FORECAST_ENVELOPE_IDENTITY_MISMATCH")
    _need(envelope.get("target_date") == target_date, "PREDICTION_TARGET_DATE_MISMATCH")
    _need(envelope.get("mode") in ("SIMULATION", "PRIVATE_SHADOW"), "FORECAST_MODE_UNVERIFIED")
    forecast = envelope.get("forecast")
    _need(isinstance(forecast, dict), "INNER_FORECAST_MISSING")
    expected_source = "MODEL11_RESEARCH_V003" if envelope["mode"] == "SIMULATION" else "MODEL11_THIRD_RESEARCH"
    _need(forecast.get("race_id") == row["race_id"] and forecast.get("source") == expected_source,
          "INNER_FORECAST_IDENTITY_MISMATCH")
    _need(forecast.get("target_date") == target_date, "PREDICTION_TARGET_DATE_MISMATCH")
    _need("actual" not in forecast and forecast.get("first_course") is None, "FORECAST_CONTAINS_EVALUATION_FIELDS")
    payload = dict(forecast)
    prediction_sha = payload.pop("prediction_sha256", None)
    _need(isinstance(prediction_sha, str) and _HEX.fullmatch(prediction_sha)
          and _sha(_canonical(payload)) == prediction_sha, "INNER_FORECAST_HASH_MISMATCH")
    model_sha = forecast.get("model_sha256")
    _need(isinstance(model_sha, str) and _HEX.fullmatch(model_sha)
          and ledger.get("model_sha") == model_sha == receipt.get("model_sha256"), "MODEL_HASH_BINDING_MISMATCH")
    _need(isinstance(forecast.get("model_spec"), dict)
          and _sha(_canonical(forecast["model_spec"])) == model_sha, "MODEL_SPEC_HASH_MISMATCH")
    evidence = envelope.get("source_evidence")
    _need(isinstance(evidence, dict) and evidence.get("payload_sha256") == _sha(raw["input"]), "SOURCE_INPUT_HASH_BINDING_MISMATCH")
    _need(metadata.get("source_payload_sha256") == _sha(raw["input"])
          and metadata.get("forecast_sha256") == _sha(raw["forecast"]), "COMMIT_METADATA_PAYLOAD_BINDING_MISMATCH")
    deadline = _time(row["deadline"])
    for value in (ledger.get("deadline"), receipt.get("deadline"), envelope.get("deadline"), forecast.get("deadline")):
        _need(_time(value) == deadline, "PREDICTION_DEADLINE_MISMATCH")
    generated = _time(envelope.get("generated_at"))
    _need(_time(receipt.get("generated_at")) == generated == _time(metadata.get("generated_at")), "GENERATION_TIME_BINDING_MISMATCH")
    chain = [_time(forecast.get("prediction_at")), generated, _time(receipt.get("persist_observed_at")),
             _time(ledger.get("committed_at")), _time(completion.get("finished_observed_at")), _time(ledger.get("finalized_at"))]
    _need(all(a <= b for a, b in zip(chain, chain[1:])), "PREDICTION_CLOCK_CHAIN_INVALID")
    _need(all(stamp < deadline for stamp in chain), "PREDICTION_SAVED_LATE")
    return "SAVED_PREDEADLINE_LOCAL"


def _category(reason):
    return {"NO_PREDICTION_OBSERVATION": "no_observation", "OBSERVED_ABSENT": "observed_absent",
            "PREDICTION_NOT_SAVED": "not_saved", "PREDICTION_READ_FAILED": "read_failed",
            "PREDICTION_SAVE_UNCERTAIN": "uncertain", "PREDICTION_SAVED_LATE": "late",
            "PREDICTION_TARGET_DATE_MISMATCH": "target_date_mismatch",
            "PREDICTION_DEADLINE_MISMATCH": "deadline_mismatch",
            "DUPLICATE_PREDICTION_OBSERVATION": "duplicate_observation"}.get(reason, "corrupt_or_unverified")


def audit_schedule_coverage(schedule, predictions, *, target_date, namespace=_NS, expected_storage_id=None):
    """Pure twelve-race coverage audit of caller-supplied read-only evidence.

    OBSERVATION_COMPLETE_LOCAL is structural/hash/time agreement only. It never
    changes, fills, writes, replays, authenticates sources, or grants GO.
    """
    report = {"status": "HOLD", "schedule_approval": "UNVERIFIED", "expected_races": 12,
              "scheduled_rows": None, "supplied_prediction_observations": len(predictions) if isinstance(predictions, list) else None,
              "locally_verified_saved_predictions": 0, "counts": {}, "rows": [], "issues": [],
              "external_schedule_authenticity": "UNVERIFIED", "external_prediction_authenticity": "UNVERIFIED",
              "runtime_final_readback_time": "UNVERIFIED_NOT_IN_STORED_RECEIPT",
              "predictor_semantics": "OUT_OF_SCOPE_PRIOR_GATES_REQUIRED", "production_go": False}
    try:
        _date(target_date)
        _need(namespace == _NS, "THIRD_RESEARCH_NAMESPACE_REQUIRED")
        if expected_storage_id is not None:
            _need(isinstance(expected_storage_id, str) and re.fullmatch(r"[0-9a-f]{32}", expected_storage_id), "EXPECTED_STORAGE_ID_INVALID")
        manifest, approval = _schedule(schedule, target_date)
        report["schedule_approval"] = "SELF_REPORTED_REQUIRED_METADATA_MATCHED"
        report["manifest_sha256"] = schedule["manifest_sha256"]
        report["mapping_sha256"] = approval["mapping_sha256"]
        raw_rows = manifest["races"]
        report["scheduled_rows"] = len(raw_rows)
        if len(raw_rows) != 12:
            report["issues"].append({"reason": "SCHEDULE_ROW_COUNT_NOT_12"})
        rows, invalid_indices = [], set()
        for index, row in enumerate(raw_rows):
            try:
                _need(isinstance(row, dict) and set(row) == {"race_id", "race_no", "deadline"}, "SCHEDULE_ROW_FIELDS_INVALID")
                _need(isinstance(row["race_id"], str) and _ID.fullmatch(row["race_id"]), "SCHEDULE_RACE_ID_INVALID")
                _need(type(row["race_no"]) is int and 1 <= row["race_no"] <= 12, "SCHEDULE_RACE_NUMBER_INVALID")
                _need(_time(row["deadline"]).astimezone(_JST).date().isoformat() == target_date, "SCHEDULE_DEADLINE_TARGET_DATE_MISMATCH")
                rows.append((index, row))
            except (_Invalid, TypeError, KeyError) as exc:
                invalid_indices.add(index)
                report["issues"].append({"schedule_index": index,
                                         "reason": exc.args[0] if isinstance(exc, _Invalid) else "SCHEDULE_ROW_INVALID"})
        id_counts, number_counts = Counter(row["race_id"] for _, row in rows), Counter(row["race_no"] for _, row in rows)
        duplicate_ids = {key for key, n in id_counts.items() if n > 1}
        duplicate_numbers = {key for key, n in number_counts.items() if n > 1}
        if duplicate_ids:
            report["issues"].append({"reason": "DUPLICATE_SCHEDULED_RACE_ID"})
        if duplicate_numbers:
            report["issues"].append({"reason": "DUPLICATE_SCHEDULE_RACE_NUMBER"})
        missing = sorted(set(range(1, 13)) - set(number_counts))
        report["missing_schedule_race_numbers"] = missing
        if missing:
            report["issues"].append({"reason": "SCHEDULE_RACE_NUMBERS_MISSING"})
        _need(isinstance(predictions, list), "PREDICTION_OBSERVATIONS_NOT_LIST")
        observed = {}
        scheduled_ids = set(id_counts)
        for index, item in enumerate(predictions):
            if not isinstance(item, dict) or not isinstance(item.get("race_id"), str) or not _ID.fullmatch(item["race_id"]):
                report["issues"].append({"prediction_index": index, "reason": "PREDICTION_OBSERVATION_ID_INVALID"})
                continue
            if item["race_id"] not in scheduled_ids:
                report["issues"].append({"prediction_index": index, "reason": "UNSCHEDULED_PREDICTION_OBSERVATION"})
            observed.setdefault(item["race_id"], []).append((index, item))
        counts = Counter()
        for index, row in rows:
            found = observed.get(row["race_id"], [])
            try:
                _need(row["race_id"] not in duplicate_ids and row["race_no"] not in duplicate_numbers, "SCHEDULE_ROW_DUPLICATED")
                _need(found, "NO_PREDICTION_OBSERVATION")
                _need(len(found) == 1, "DUPLICATE_PREDICTION_OBSERVATION")
                status = _prediction(found[0][1], row, target_date, namespace, expected_storage_id)
                counts["saved_predeadline_local"] += 1
                reasons = []
            except (_Invalid, TypeError, KeyError, ValueError, OverflowError, RecursionError) as exc:
                reason = exc.args[0] if isinstance(exc, _Invalid) else "PREDICTION_EVIDENCE_INPUT_INVALID"
                status, reasons = "HOLD", [reason]
                counts[_category(reason)] += 1
            report["rows"].append({"schedule_index": index, "race_no": row["race_no"],
                                   "prediction_index": found[0][0] if len(found) == 1 else None,
                                   "status": status, "reasons": reasons})
        report["counts"] = dict(counts)
        report["locally_verified_saved_predictions"] = counts["saved_predeadline_local"]
        if not report["issues"] and not invalid_indices and len(rows) == 12 and counts["saved_predeadline_local"] == 12:
            report["status"] = "OBSERVATION_COMPLETE_LOCAL"
        return report
    except (_Invalid, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        report["issues"].append({"reason": exc.args[0] if isinstance(exc, _Invalid) else "COVERAGE_INPUT_INVALID"})
        return report
