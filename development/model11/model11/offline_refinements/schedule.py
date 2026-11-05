"""Pure dynamic scheduled-race coverage; normalized local contract PROPOSED.

No official source parser, cancellation inference, store access, or writer.
Active prediction validation reuses the immutable parent v006 byte verifier.
"""
from __future__ import annotations

from collections import Counter

from ..shadow_preparation.coverage import (
    _Invalid, _ID, _HEX, _JST, _canonical, _date, _decode, _need,
    _object, _prediction, _sha, _time, _category,
)


STATUSES = ("SCHEDULED", "CANCELLED_OFFICIAL", "WITHDRAWN_OFFICIAL")
PARENT_COMMIT = "7aec4fdb6b9f311ee01bf3a2752410e683d83e42"


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _hash(value):
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _frame(frame):
    _need(isinstance(frame, dict), "STATUS_PROOF_MISSING")
    raw = _decode(frame.get("raw_evidence_b64"))
    _need(type(frame.get("evidence_bytes")) is int and frame["evidence_bytes"] == len(raw), "STATUS_PROOF_BYTES_MISMATCH")
    _need(_hash(frame.get("evidence_sha256")) and _sha(raw) == frame["evidence_sha256"], "STATUS_PROOF_HASH_MISMATCH")
    return _object(raw)


def _manifest(schedule, target_date):
    _need(isinstance(schedule, dict), "MANIFEST_MISSING")
    raw = _decode(schedule.get("raw_manifest_b64"))
    _need(type(schedule.get("manifest_bytes")) is int and schedule["manifest_bytes"] == len(raw), "MANIFEST_BYTES_MISMATCH")
    _need(_hash(schedule.get("manifest_sha256")) and _sha(raw) == schedule["manifest_sha256"], "MANIFEST_HASH_MISMATCH")
    manifest, mapping = _object(raw), schedule.get("mapping")
    _need(isinstance(mapping, dict) and set(mapping) == {"schema", "mapping_id", "mapping_version", "venue", "source_id", "classification", "event_scope", "normalized_statuses"}, "NORMALIZED_MAPPING_FIELDS_INVALID")
    _need(mapping["schema"] == "LOCAL_RACE_SCHEDULE_MAPPING_V001_PROPOSED"
          and mapping["event_scope"] == "RACE_EVENT" and mapping["normalized_statuses"] == list(STATUSES), "NORMALIZED_MAPPING_UNREVIEWED")
    _need(_identifier(mapping["mapping_id"]) and _identifier(mapping["mapping_version"])
          and _identifier(mapping["source_id"]), "MAPPING_IDENTITY_INVALID")
    _need(mapping["classification"] in ("SYNTHETIC_ONLY", "PRIVATE_REAL"), "MAPPING_CLASSIFICATION_INVALID")
    mapping_sha = _sha(_canonical(mapping))
    _need(schedule.get("mapping_sha256") == mapping_sha, "MAPPING_HASH_MISMATCH")
    _need(set(manifest) == {"schema", "venue", "target_date", "source_id", "classification", "mapping_sha256", "races", "closed_official_evidence_sha256"}, "MANIFEST_FIELDS_INVALID")
    _need(manifest["schema"] == "LOCAL_DAY_SCHEDULE_V002_PROPOSED", "MANIFEST_SCHEMA_UNREVIEWED")
    _need(manifest["venue"] == mapping["venue"] == "GAMAGORI", "MANIFEST_VENUE_MISMATCH")
    _need(manifest["target_date"] == target_date, "MANIFEST_TARGET_DATE_MISMATCH")
    _need(manifest["source_id"] == mapping["source_id"] and manifest["classification"] == mapping["classification"]
          and manifest["mapping_sha256"] == mapping_sha, "MANIFEST_MAPPING_BINDING_MISMATCH")
    approval = schedule.get("approval")
    _need(isinstance(approval, dict) and approval.get("approved") is True
          and approval.get("declared_external_verification") is True, "MANIFEST_REVIEW_DECLARATION_MISSING")
    for field in ("venue", "target_date", "source_id", "classification", "mapping_sha256"):
        _need(approval.get(field) == manifest[field], "APPROVAL_BINDING_MISMATCH")
    _need(approval.get("manifest_sha256") == _sha(raw) and _hash(approval.get("evidence_sha256")), "APPROVAL_HASH_BINDING_MISMATCH")
    _need(isinstance(manifest["races"], list) and isinstance(schedule.get("status_evidence"), dict), "MANIFEST_OR_PROOF_ROWS_MISSING")
    return manifest, mapping


def _proof(schedule, manifest, mapping, proof_sha, row=None):
    _need(_hash(proof_sha), "OFFICIAL_STATUS_PROOF_REQUIRED")
    frame = schedule["status_evidence"].get(proof_sha)
    proof = _frame(frame)
    _need(frame["evidence_sha256"] == proof_sha, "STATUS_PROOF_REFERENCE_MISMATCH")
    base = {"schema", "event_scope", "status", "venue", "target_date", "source_id", "classification",
            "mapping_sha256", "mapping_version", "effective_at", "acquired_at", "available_at", "revision_at"}
    _need(set(proof) == base | ({"race_id", "race_no"} if row is not None else set()), "STATUS_PROOF_FIELDS_INVALID")
    for field in ("venue", "target_date", "source_id", "classification", "mapping_sha256"):
        _need(proof[field] == manifest[field], "STATUS_PROOF_SOURCE_OR_DATE_MISMATCH")
    _need(proof["mapping_version"] == mapping["mapping_version"], "STATUS_PROOF_MAPPING_VERSION_MISMATCH")
    if row is None:
        _need(proof["schema"] == "LOCAL_OFFICIAL_DAY_CLOSURE_EVIDENCE_V001_PROPOSED"
              and proof["event_scope"] == "OFFICIAL_DAY" and proof["status"] == "CLOSED_OFFICIAL", "OFFICIAL_DAY_CLOSURE_PROOF_REQUIRED")
    else:
        _need(proof["schema"] == "LOCAL_RACE_STATUS_EVIDENCE_V001_PROPOSED"
              and proof["event_scope"] == "RACE_EVENT", "RACE_EVENT_STATUS_PROOF_REQUIRED")
        _need(proof["race_id"] == row["race_id"] and type(proof["race_no"]) is int
              and proof["race_no"] == row["race_no"] and proof["status"] == row["status"], "RACE_STATUS_PROOF_BINDING_MISMATCH")
    times = {field: _time(proof[field]) for field in ("effective_at", "acquired_at", "available_at", "revision_at")}
    _need(times["acquired_at"] <= times["available_at"] and times["revision_at"] <= times["available_at"], "STATUS_PROOF_TIME_ORDER_INVALID")
    _need(times["effective_at"].astimezone(_JST).date().isoformat() <= manifest["target_date"], "STATUS_EFFECTIVE_AFTER_TARGET_DAY")
    return times


def _timing(entry, row, times):
    """Only byte-bound generation observation; not excluded forecast validity."""
    answer = {"prediction_assessment": "UNASSESSED_OFFICIAL_EXCLUSION",
              "effective_vs_generation": "UNVERIFIED", "evidence_known_vs_generation": "UNVERIFIED"}
    try:
        _need(isinstance(entry, dict) and entry.get("observation") == "READ_OK", "TIMING_UNAVAILABLE")
        raw = entry["raw_blobs"]
        forecast_raw, receipt_raw = _decode(raw["forecast_b64"]), _decode(raw["receipt_b64"])
        receipt, envelope = _object(receipt_raw), _object(forecast_raw)
        _need(_sha(receipt_raw) == entry["ledger"]["receipt_sha"]
              and _sha(forecast_raw) == receipt["forecast_sha256"]
              and receipt["forecast_bytes"] == len(forecast_raw), "TIMING_HASH_UNVERIFIED")
        _need(envelope["race_id"] == receipt["race_id"] == row["race_id"]
              and envelope["target_date"] == _time(row["deadline"]).astimezone(_JST).date().isoformat(), "TIMING_IDENTITY_UNVERIFIED")
        generated = _time(envelope["generated_at"])
        _need(generated == _time(receipt["generated_at"]), "TIMING_BINDING_UNVERIFIED")
        def relation(value):
            return "BEFORE_GENERATION" if value < generated else "AFTER_GENERATION" if value > generated else "AT_GENERATION"
        answer.update(effective_vs_generation=relation(times["effective_at"]),
                      evidence_known_vs_generation=relation(max(times[field] for field in ("acquired_at", "available_at", "revision_at"))),
                      timing_basis="LOCAL_BYTE_BOUND_GENERATION_ONLY_NOT_VALIDITY_OR_AUTHENTICITY")
    except (_Invalid, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        answer["timing_basis"] = "UNVERIFIED_SUPPLIED_OBSERVATION"
    return answer


def audit_manifest_coverage(schedule, predictions, *, target_date, expected_storage_id=None):
    """Expected active races come only from an explicitly reviewed manifest."""
    result = {"status": "HOLD", "active_expected": 0, "cancelled_official": 0, "withdrawn_official": 0,
              "saved_predeadline_local": 0, "no_observation": 0, "read_failed": 0, "not_saved": 0,
              "uncertain": 0, "late": 0, "other_invalid": 0, "excluded_predictions_present": 0,
              "excluded_observations_supplied": 0, "excluded_read_failed": 0,
              "rows": [], "issues": [], "review_metadata": "UNVERIFIED",
              "external_source_authenticity": "UNVERIFIED", "cancellation_authenticity": "UNVERIFIED",
              "existing_predictions": "NEVER_MODIFIED", "lock_semantics": "UNCHANGED",
              "ac1_or_first_lock_assessment": "NOT_PERFORMED_CURRENT_MANIFEST_ONLY",
              "prior_deadline_obligation": "UNVERIFIED_ORIGINAL_SNAPSHOT_NOT_PROVIDED",
              "active_expected_basis": "DECLARED_SCHEDULED_ROWS_NOT_AC1_OR_LOCK_DENOMINATOR",
              "parent_verifier_commit": PARENT_COMMIT, "production_go": False}
    try:
        _date(target_date)
        _need(isinstance(predictions, list), "PREDICTIONS_NOT_LIST")
        manifest, mapping = _manifest(schedule, target_date)
        result["review_metadata"] = "SELF_REPORTED_REQUIRED_BINDINGS_MATCHED"
        result["manifest_sha256"] = schedule["manifest_sha256"]
        if expected_storage_id is not None:
            _need(isinstance(expected_storage_id, str) and len(expected_storage_id) == 32
                  and all(c in "0123456789abcdef" for c in expected_storage_id), "EXPECTED_STORAGE_ID_INVALID")
        ids, numbers = [], []
        for row in manifest["races"]:
            _need(isinstance(row, dict) and set(row) == {"race_id", "race_no", "deadline", "status", "status_evidence_sha256"}, "RACE_ROW_FIELDS_INVALID")
            _need(_identifier(row["race_id"]) and type(row["race_no"]) is int and 1 <= row["race_no"] <= 99, "RACE_ID_OR_NUMBER_INVALID")
            _need(row["status"] in STATUSES, "RACE_STATUS_UNRECOGNIZED")
            _need(_time(row["deadline"]).astimezone(_JST).date().isoformat() == target_date, "RACE_DEADLINE_TARGET_DATE_MISMATCH")
            ids.append(row["race_id"])
            numbers.append(row["race_no"])
        _need(len(set(ids)) == len(ids), "DUPLICATE_OR_CONFLICTING_RACE_ID")
        _need(len(set(numbers)) == len(numbers), "DUPLICATE_RACE_NUMBER")
        result["active_expected"] = sum(row["status"] == "SCHEDULED" for row in manifest["races"])
        observed = {}
        for index, entry in enumerate(predictions):
            _need(isinstance(entry, dict) and _identifier(entry.get("race_id")), "PREDICTION_ID_INVALID")
            observed.setdefault(entry["race_id"], []).append((index, entry))
            if entry["race_id"] not in set(ids):
                result["issues"].append({"prediction_index": index, "reason": "UNSCHEDULED_PREDICTION_PRESERVED_UNASSESSED"})
        used_proofs = set()
        closure = manifest["closed_official_evidence_sha256"]
        if not ids:
            _proof(schedule, manifest, mapping, closure)
            used_proofs.add(closure)
            result["empty_day_basis"] = "LOCAL_BOUND_CLOSED_OFFICIAL_PROOF_AUTHENTICITY_UNVERIFIED"
        else:
            _need(closure is None, "DAY_CLOSURE_CONFLICTS_WITH_RACE_ROWS")
        for index, row in enumerate(manifest["races"]):
            found = observed.get(row["race_id"], [])
            info = {"manifest_index": index, "race_no": row["race_no"], "manifest_status": row["status"],
                    "prediction_indices": [i for i, _ in found], "status": "HOLD", "reasons": []}
            try:
                if row["status"] != "SCHEDULED":
                    times = _proof(schedule, manifest, mapping, row["status_evidence_sha256"], row)
                    used_proofs.add(row["status_evidence_sha256"])
                    result["cancelled_official" if row["status"] == "CANCELLED_OFFICIAL" else "withdrawn_official"] += 1
                    result["excluded_observations_supplied"] += len(found)
                    for _, supplied in found:
                        result["excluded_predictions_present"] += (supplied.get("observation") == "READ_OK"
                            and isinstance(supplied.get("raw_blobs"), dict)
                            and isinstance(supplied["raw_blobs"].get("forecast_b64"), str))
                        result["excluded_read_failed"] += supplied.get("observation") == "READ_FAILED"
                    info.update(status="EXCLUDED_BY_DECLARED_STATUS_LOCAL_PROOF", prediction_assessment="UNASSESSED_OFFICIAL_EXCLUSION",
                                prior_deadline_obligation="UNVERIFIED_ORIGINAL_SNAPSHOT_NOT_PROVIDED",
                                effective_vs_deadline="BEFORE_DEADLINE" if times["effective_at"] < _time(row["deadline"]) else
                                "AFTER_DEADLINE" if times["effective_at"] > _time(row["deadline"]) else "AT_DEADLINE")
                    _need(len(found) <= 1, "DUPLICATE_PREDICTION_OBSERVATION")
                    if found:
                        info["excluded_observation"] = (found[0][1].get("observation") if found[0][1].get("observation") in
                                                        ("READ_OK", "ABSENT", "NOT_SAVED", "READ_FAILED", "UNCERTAIN", "CORRUPT") else "UNVERIFIED")
                        info.update(_timing(found[0][1], row, times))
                    else:
                        info["excluded_observation"] = "NO_OBSERVATION_NO_PREDICTION_REQUIRED_BY_THIS_MANIFEST"
                else:
                    _need(len(found) <= 1, "DUPLICATE_PREDICTION_OBSERVATION")
                    _need(row["status_evidence_sha256"] is None, "SCHEDULED_ROW_HAS_CONFLICTING_STATUS_PROOF")
                    _need(found, "NO_PREDICTION_OBSERVATION")
                    _prediction(found[0][1], row, target_date, "MODEL11_THIRD_RESEARCH", expected_storage_id)
                    info["status"] = "SAVED_PREDEADLINE_LOCAL"
                    result["saved_predeadline_local"] += 1
            except (_Invalid, TypeError, KeyError, ValueError, RecursionError, OverflowError) as exc:
                reason = exc.args[0] if isinstance(exc, _Invalid) else "ROW_EVIDENCE_INVALID"
                info["reasons"].append(reason)
                category = _category(reason)
                destination = {"no_observation": "no_observation", "read_failed": "read_failed", "not_saved": "not_saved",
                               "uncertain": "uncertain", "late": "late"}.get(category, "other_invalid")
                result[destination] += 1
            result["rows"].append(info)
        _need(set(schedule["status_evidence"]) == used_proofs, "UNREFERENCED_OR_CONFLICTING_STATUS_PROOF")
        if not result["issues"] and all(not row["reasons"] for row in result["rows"]) and result["active_expected"] == result["saved_predeadline_local"]:
            result["status"] = "OBSERVATION_COMPLETE_LOCAL"
        return result
    except (_Invalid, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        result["issues"].append({"reason": exc.args[0] if isinstance(exc, _Invalid) else "MANIFEST_COVERAGE_INPUT_INVALID"})
        return result
