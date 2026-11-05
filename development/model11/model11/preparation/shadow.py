"""Pure offline third-research output preparation; no execution integration.

The SHA receipts demonstrate byte consistency, not independently authenticated
pre-deadline publication. No writer, scheduler, notifications, or betting API is
implemented here. The original research engine is preserved unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from itertools import permutations
import json
import re

from ..engine import canonical_hash, check_distribution
from ..validation import prediction_view, validate_race


WRAPPER_VERSION = "0.2.0-preparation-PROPOSED"
ENGINE_VERSION = "0.1.0-research"
SOURCE = "MODEL11_THIRD_RESEARCH"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")
_STAGES = {"P_raw", "P_model", "P_market", "P_shrunk"}
_FORBIDDEN = {"actual", "outcome", "outcomes", "result", "results", "label", "labels",
              "payout", "payout_per_100", "refund_tickets", "credentials", "password",
              "token", "secret", "url", "path", "proxy"}
_FORECAST_KEYS = {
    "P_calibrated", "bet_decision", "boxes", "classification", "config", "config_status",
    "deadline", "distributions", "explanation", "first_course", "gate", "information",
    "input_sha256", "legacy_box_v1", "legacy_model10", "market", "model_sha256",
    "model_spec", "performance_improvement", "prediction_at", "prediction_sha256",
    "probability_integrity", "production_go", "race_id", "selection", "selection_stage",
    "source", "target_date", "version",
}
_RECORD_KEYS = {
    "schema", "source", "classification", "wrapper_research_version", "engine_version",
    "race_id", "target_date", "generated_at", "prediction_at", "deadline", "active_boat_count",
    "stage_domain_count", "input_time_evidence", "forecast", "reproduction", "proof_scope",
    "execution_integration", "external_writers_notifications_bets", "production_go",
    "shadow_execution_go", "formal_model10_box_v1_reproduction",
}


def _hold(code):
    raise ValueError("HOLD:" + code)


def _canonical_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError):
        _hold("NONCANONICAL_JSON")


def _safe(value):
    """Never return arbitrary paths, URLs, secret fields, or outcome records."""
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN:
                _hold("FORBIDDEN_OUTPUT_FIELD")
            _safe(child)
    elif isinstance(value, list):
        for child in value:
            _safe(child)
    elif isinstance(value, str):
        if "://" in value or "/" in value or "\\" in value or any(ord(c) < 32 for c in value):
            _hold("UNSAFE_OUTPUT_TEXT")
    elif value is not None and type(value) not in (int, float, bool):
        _hold("NONCANONICAL_JSON")


def _time(value):
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value) or value.endswith("-00:00"):
        _hold("TIME_UNKNOWN_OR_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _hold("TIME_UNKNOWN_OR_INVALID")


def _forecast(prediction):
    if not isinstance(prediction, dict) or set(prediction) != _FORECAST_KEYS:
        _hold("FORECAST_SCHEMA_OR_OUTCOME_FIELD")
    _canonical_bytes(prediction)
    _safe(prediction)
    if (prediction["version"] != ENGINE_VERSION or prediction["source"] != "MODEL11_RESEARCH"
            or prediction["classification"] != "LANE2_RESEARCH_ONLY"
            or prediction["production_go"] is not False or prediction["first_course"] is not None):
        _hold("FORECAST_RESEARCH_BOUNDARY")
    claimed = prediction["prediction_sha256"]
    body = {key: value for key, value in prediction.items() if key != "prediction_sha256"}
    if not isinstance(claimed, str) or not _SHA256.fullmatch(claimed) or claimed != canonical_hash(body):
        _hold("FORECAST_SHA256_MISMATCH")
    if prediction["model_sha256"] != canonical_hash(prediction["model_spec"]):
        _hold("MODEL_SHA256_MISMATCH")
    stages = prediction["distributions"]
    if not isinstance(stages, dict) or set(stages) != _STAGES:
        _hold("FOUR_STAGES_REQUIRED")
    for distribution in list(stages.values()) + [prediction["P_calibrated"]]:
        if distribution is None:
            _hold("FOUR_STAGES_UNAVAILABLE")
        try:
            check_distribution(distribution, [1, 2, 3, 4, 5, 6])
        except (ValueError, TypeError):
            _hold("FULL_120_PROBABILITY_DOMAIN_REQUIRED")
    valid_tickets = set(stages["P_model"])
    selection = prediction["selection"]
    if not isinstance(selection, dict) or not isinstance(selection.get("tickets"), list):
        _hold("FIVE_SELECTION_INVALID")
    tickets = selection["tickets"]
    if len(tickets) != 5 or len(set(tickets)) != 5 or not set(tickets) <= valid_tickets or selection.get("stake_yen") != 500:
        _hold("FIVE_SELECTION_INVALID")
    boxes = prediction["boxes"]
    for method in ("human_research", "mechanical_research", "box_v11_research"):
        box = boxes.get(method) if isinstance(boxes, dict) else None
        if not isinstance(box, dict) or not isinstance(box.get("boats"), list) or not isinstance(box.get("tickets"), list):
            _hold("SEPARATE_BOX_RESEARCH_REQUIRED")
        boats = box["boats"]
        if (len(boats) != 3 or any(type(boat) is not int or boat not in range(1, 7) for boat in boats)
                or len(set(boats)) != 3):
            _hold("BOX_DOMAIN_INVALID")
        expected = {"-".join(map(str, triple)) for triple in permutations(boats, 3)}
        if (len(box["tickets"]) != 6 or set(box["tickets"]) != expected
                or box.get("stake_yen") != 600 or box.get("formal_box_v1_reproduction") is not False):
            _hold("BOX_DOMAIN_OR_FROZEN_BOUNDARY")
    differs = "YES" if set(boxes["human_research"]["boats"]) != set(boxes["mechanical_research"]["boats"]) else "NO"
    if boxes.get("composition_difference") != differs:
        _hold("COMPOSITION_DIFFERENCE_MISMATCH")
    if prediction["bet_decision"] not in {"BET", "SKIP"} or prediction["bet_decision"] != selection.get("bet_decision"):
        _hold("RESEARCH_BET_DECISION_INVALID")


def _reproduction(prediction, reproduction):
    required = {"code_commit", "input_artifact_sha256", "model_sha256", "config_sha256"}
    if not isinstance(reproduction, dict) or set(reproduction) != required:
        _hold("REPRODUCTION_FIELDS_REQUIRED")
    if not isinstance(reproduction["code_commit"], str) or not _COMMIT.fullmatch(reproduction["code_commit"]):
        _hold("CODE_COMMIT_UNKNOWN")
    for field in required - {"code_commit"}:
        if not isinstance(reproduction[field], str) or not _SHA256.fullmatch(reproduction[field]):
            _hold("REPRODUCTION_SHA256_INVALID")
    if reproduction["model_sha256"] != prediction["model_sha256"]:
        _hold("REPRODUCTION_MODEL_MISMATCH")
    if reproduction["config_sha256"] != canonical_hash(prediction["config"]):
        _hold("REPRODUCTION_CONFIG_MISMATCH")
    if reproduction["input_artifact_sha256"] != prediction["input_sha256"]:
        _hold("REPRODUCTION_INPUT_MISMATCH")


def _normalization_evidence(race):
    usage, provenance = race.get("normalization_usage"), race.get("normalization_provenance")
    if usage is None and provenance is None:
        return None
    if usage != "PREDICTION_AS_OF_GATE_PASSED":
        _hold("NORMALIZATION_NOT_FORECAST_ELIGIBLE")
    required = {"normalizer_sha256", "feature_specs_sha256", "fit_cutoff", "training_max_available_at",
                "training_input_sha256", "usage"}
    if not isinstance(provenance, dict) or set(provenance) != required or provenance["usage"] != "prediction":
        _hold("NORMALIZATION_PROVENANCE_REQUIRED")
    for field in ("normalizer_sha256", "feature_specs_sha256", "training_input_sha256"):
        if not isinstance(provenance[field], str) or not _SHA256.fullmatch(provenance[field]):
            _hold("NORMALIZATION_HASH_UNKNOWN")
    prediction_time = _time(race["prediction_at"])
    for field in ("fit_cutoff", "training_max_available_at"):
        if _time(provenance[field]) >= prediction_time:
            _hold("NORMALIZATION_NOT_BEFORE_PREDICTION")
    return {**deepcopy(provenance), "timestamp_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT"}


def build_shadow_output(prediction, race, generated_at, reproduction):
    """Create a new third-research envelope, without modifying supplied records.

    ``input_artifact_sha256`` identifies the canonical JSON encoding of the
    validated race, not unknown original file bytes. A code commit is only a
    syntactically checked reference; its content/authorship is UNVERIFIED here.
    Any unsupported/missing input raises a fixed ``ValueError('HOLD:...')``.
    """
    _forecast(prediction)
    _reproduction(prediction, reproduction)
    try:
        view = prediction_view(race)
        gate = validate_race(view)
    except (ValueError, TypeError):
        _hold("INPUT_VALIDATION_FAILED")
    if not gate["eligible"]:
        _hold("INPUT_VALIDATION_FAILED")
    if sorted(view["active_boats"]) != [1, 2, 3, 4, 5, 6]:
        _hold("SIX_ACTIVE_BOATS_REQUIRED_REDUCED_DOMAIN")
    if not gate["market_available"]:
        _hold("FOUR_STAGES_UNAVAILABLE")
    normalization = _normalization_evidence(view)
    for field in ("race_id", "target_date", "prediction_at", "deadline"):
        if prediction[field] != view[field]:
            _hold("FORECAST_RACE_IDENTITY_MISMATCH")
    if prediction["input_sha256"] != canonical_hash(view):
        _hold("INPUT_SHA256_MISMATCH")
    generated = _time(generated_at)
    if not _time(view["prediction_at"]) <= generated < _time(view["deadline"]):
        _hold("GENERATION_NOT_PREDEADLINE")

    manual = view.get("human_box_input")
    information = {
        "feature_times": {str(b["boat"]): deepcopy(b["feature_times"]) for b in view["boats"]},
        "state_times": {str(b["boat"]): deepcopy(b["state_times"]) for b in view["boats"]},
        "odds_times": {field: view["odds_snapshot"][field] for field in ("acquired_at", "available_at", "revision_at")},
        "human_box_times": None if manual is None else {
            field: manual[field] for field in ("observed_at", "acquired_at", "available_at", "revision_at")},
        "missing_input_codes": ["MANUAL_HUMAN_INPUT_ABSENT_RESEARCH_HEURISTIC"] if manual is None else [],
        "warning_codes": deepcopy(gate["warnings"]),
        "time_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT",
        "normalization_provenance": normalization,
    }
    expected_information = prediction["information"]
    if (information["feature_times"] != expected_information.get("feature_times")
            or information["state_times"] != expected_information.get("state_times")
            or information["human_box_times"] != expected_information.get("human_box_provenance")
            or information["odds_times"]["acquired_at"] != expected_information.get("odds_acquired_at")
            or information["odds_times"]["available_at"] != expected_information.get("odds_available_at")):
        _hold("FORECAST_INPUT_TIME_EVIDENCE_MISMATCH")
    result = {
        "schema": "MODEL11_SHADOW_PREPARATION_V001", "source": SOURCE,
        "classification": "LANE2_OFFLINE_PREPARATION_ONLY",
        "wrapper_research_version": WRAPPER_VERSION, "engine_version": ENGINE_VERSION,
        "race_id": view["race_id"], "target_date": view["target_date"],
        "generated_at": generated_at, "prediction_at": view["prediction_at"], "deadline": view["deadline"],
        "active_boat_count": 6, "stage_domain_count": 120,
        "input_time_evidence": information, "forecast": deepcopy(prediction),
        "reproduction": {**deepcopy(reproduction),
            "input_artifact_encoding": "CANONICAL_JSON_ASCII_NO_TRAILING_LF",
            "input_artifact_scope": "VALIDATED_RACE_NOT_ORIGINAL_FILE_BYTES",
            "forecast_sha256": prediction["prediction_sha256"],
            "input_sha256": prediction["input_sha256"],
            "code_commit_verification": "UNVERIFIED_REFERENCE_ONLY"},
        "proof_scope": "SELF_CONSISTENCY_NOT_INDEPENDENT_AUTHENTICITY_OR_PREDEADLINE_PUBLICATION",
        "execution_integration": "NOT_IMPLEMENTED",
        "external_writers_notifications_bets": "NOT_IMPLEMENTED",
        "production_go": False, "shadow_execution_go": False,
        "formal_model10_box_v1_reproduction": "UNVERIFIED",
    }
    _validate_record(result)
    return result


def _validate_record(record):
    _canonical_bytes(record)
    _safe(record)
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS or record.get("schema") != "MODEL11_SHADOW_PREPARATION_V001":
        _hold("SHADOW_SCHEMA_INVALID")
    if (record.get("source") != SOURCE or record.get("wrapper_research_version") != WRAPPER_VERSION
            or record.get("engine_version") != ENGINE_VERSION or record.get("production_go") is not False
            or record.get("classification") != "LANE2_OFFLINE_PREPARATION_ONLY"
            or record.get("shadow_execution_go") is not False or record.get("execution_integration") != "NOT_IMPLEMENTED"
            or record.get("external_writers_notifications_bets") != "NOT_IMPLEMENTED"
            or record.get("formal_model10_box_v1_reproduction") != "UNVERIFIED"
            or record.get("proof_scope") != "SELF_CONSISTENCY_NOT_INDEPENDENT_AUTHENTICITY_OR_PREDEADLINE_PUBLICATION"):
        _hold("SHADOW_RESEARCH_BOUNDARY")
    forecast = record.get("forecast")
    _forecast(forecast)
    repro = record.get("reproduction")
    if not isinstance(repro, dict):
        _hold("REPRODUCTION_FIELDS_REQUIRED")
    _reproduction(forecast, {field: repro.get(field) for field in ("code_commit", "input_artifact_sha256", "model_sha256", "config_sha256")})
    if (repro.get("forecast_sha256") != forecast["prediction_sha256"]
            or repro.get("input_sha256") != forecast["input_sha256"]
            or repro.get("input_artifact_encoding") != "CANONICAL_JSON_ASCII_NO_TRAILING_LF"
            or repro.get("input_artifact_scope") != "VALIDATED_RACE_NOT_ORIGINAL_FILE_BYTES"
            or repro.get("code_commit_verification") != "UNVERIFIED_REFERENCE_ONLY"):
        _hold("ENVELOPE_HASH_REFERENCE_MISMATCH")
    for field in ("race_id", "target_date", "prediction_at", "deadline"):
        if record.get(field) != forecast[field]:
            _hold("ENVELOPE_IDENTITY_MISMATCH")
    if not _time(record["prediction_at"]) <= _time(record.get("generated_at")) < _time(record["deadline"]):
        _hold("GENERATION_NOT_PREDEADLINE")
    if record.get("active_boat_count") != 6 or record.get("stage_domain_count") != 120:
        _hold("FULL_120_PROBABILITY_DOMAIN_REQUIRED")
    info, original = record.get("input_time_evidence"), forecast["information"]
    info_keys = {"feature_times", "state_times", "odds_times", "human_box_times", "missing_input_codes", "warning_codes", "time_authenticity", "normalization_provenance"}
    if (not isinstance(info, dict) or set(info) != info_keys
            or info["feature_times"] != original.get("feature_times")
            or info["state_times"] != original.get("state_times")
            or info["human_box_times"] != original.get("human_box_provenance")
            or info["warning_codes"] != original.get("missing_or_warning_codes")
            or info["time_authenticity"] != "UNVERIFIED_SELF_REPORTED_INPUT"):
        _hold("INPUT_TIME_EVIDENCE_INVALID")
    expected_missing = ["MANUAL_HUMAN_INPUT_ABSENT_RESEARCH_HEURISTIC"] if info["human_box_times"] is None else []
    if info["missing_input_codes"] != expected_missing:
        _hold("MISSING_INPUT_EVIDENCE_INVALID")
    prediction_time = _time(record["prediction_at"])
    for kind, fields in (("feature_times", {"st", "turn", "motor", "ability", "exhibition"}),
                         ("state_times", {"course", "fl", "scratched"})):
        mapping = info[kind]
        if not isinstance(mapping, dict) or set(mapping) != set(map(str, range(1, 7))):
            _hold("INPUT_TIME_EVIDENCE_INVALID")
        for boat in mapping.values():
            if not isinstance(boat, dict) or set(boat) != fields:
                _hold("INPUT_TIME_EVIDENCE_INVALID")
            for times in boat.values():
                _check_input_times(times, prediction_time)
    _check_input_times(info["odds_times"], prediction_time)
    if (info["odds_times"]["acquired_at"] != original.get("odds_acquired_at")
            or info["odds_times"]["available_at"] != original.get("odds_available_at")):
        _hold("INPUT_TIME_EVIDENCE_INVALID")
    if info["human_box_times"] is not None:
        _check_input_times(info["human_box_times"], prediction_time, observed=True)
    if info["normalization_provenance"] is not None:
        provenance = deepcopy(info["normalization_provenance"])
        if provenance.pop("timestamp_authenticity", None) != "UNVERIFIED_SELF_REPORTED_INPUT":
            _hold("NORMALIZATION_PROVENANCE_REQUIRED")
        _normalization_evidence({"normalization_usage": "PREDICTION_AS_OF_GATE_PASSED",
                                 "normalization_provenance": provenance, "prediction_at": record["prediction_at"]})


def _check_input_times(times, prediction_time, observed=False):
    required = {"acquired_at", "available_at", "revision_at"} | ({"observed_at"} if observed else set())
    if not isinstance(times, dict) or set(times) != required:
        _hold("INPUT_TIME_EVIDENCE_INVALID")
    parsed = {field: _time(value) for field, value in times.items()}
    if parsed["acquired_at"] > parsed["available_at"] or any(moment > prediction_time for moment in parsed.values()):
        _hold("INPUT_TIME_EVIDENCE_INVALID")


def serialize_shadow(record):
    """Return (payload bytes, external receipt), writing no files.

    The receipt is outside the hashed payload, avoiding recursive self-hashing.
    A changed receipt+payload pair can be forged together; this is not a seal.
    """
    _validate_record(record)
    payload = _canonical_bytes(record)
    receipt = {"schema": "MODEL11_SHADOW_RAW_RECEIPT_V001", "bytes": len(payload),
               "sha256": hashlib.sha256(payload).hexdigest(),
               "encoding": "CANONICAL_JSON_ASCII_NO_TRAILING_LF",
               "hash_scope": "PAYLOAD_ONLY_RECEIPT_EXTERNAL",
               "trust": "SELF_HASH_ONLY_EXTERNAL_AUTHENTICITY_UNVERIFIED",
               "production_go": False}
    return payload, receipt


def verify_shadow(payload, receipt):
    """Verify bytes and internal consistency only; never grant operational GO."""
    invalid = {"valid": False, "status": "HOLD", "authenticity": "UNVERIFIED", "production_go": False,
               "shadow_execution_go": False}
    if type(payload) is not bytes or not isinstance(receipt, dict):
        return {**invalid, "reason": "RAW_BYTES_AND_RECEIPT_REQUIRED"}
    if (type(receipt.get("bytes")) is not int or receipt["bytes"] != len(payload)
            or receipt.get("sha256") != hashlib.sha256(payload).hexdigest()):
        return {**invalid, "reason": "RAW_BYTES_SHA256_MISMATCH"}
    if (receipt.get("schema") != "MODEL11_SHADOW_RAW_RECEIPT_V001"
            or receipt.get("production_go") is not False
            or receipt.get("hash_scope") != "PAYLOAD_ONLY_RECEIPT_EXTERNAL"):
        return {**invalid, "reason": "RECEIPT_SCHEMA_INVALID"}
    try:
        record = json.loads(payload.decode("ascii"))
        _validate_record(record)
        if _canonical_bytes(record) != payload:
            _hold("NONCANONICAL_RAW_BYTES")
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        return {**invalid, "reason": "PAYLOAD_SCHEMA_OR_INTERNAL_CONSISTENCY_FAILURE"}
    return {"valid": True, "status": "SELF_CONSISTENT_ONLY", "authenticity": "UNVERIFIED",
            "predeadline_publication": "UNVERIFIED_NO_INDEPENDENT_RECEIPT",
            "code_commit_verification": "UNVERIFIED_REFERENCE_ONLY",
            "production_go": False, "shadow_execution_go": False}
