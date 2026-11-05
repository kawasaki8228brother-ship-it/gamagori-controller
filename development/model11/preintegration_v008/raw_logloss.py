"""Independent stdlib audit of saved raw probability bytes; no model/writer import.

This verifies arithmetic and self-reported bindings, never external authenticity,
F5 adequacy or permission to use private data. No source, sink or file I/O exists.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import hashlib
from itertools import permutations
import json
import math
import re

STAGES = frozenset({"P_raw", "P_model", "P_market", "P_shrunk"})
TICKETS = frozenset("-".join(map(str, p)) for p in permutations(range(1, 7), 3))
NUMERICAL_SUM_TOLERANCE = 1e-12  # Floating-point consistency only, not an F5 threshold.
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
_TIMES = {"acquired_at", "available_at", "revision_at"}
_FORBIDDEN = {"actual", "outcome", "outcomes", "result", "results", "label", "labels", "payout", "payout_per_100", "refund_tickets"}
_FEATURES = {"st", "turn", "motor", "ability", "exhibition"}
_INNER_KEYS = set("F2_BOX_DESIGN F5_SELECTION_ADEQUACY P_calibrated bet_decision boxes classification config config_status course_evidence deadline distributions explanation first_course information input_sha256 legacy_comparison live_eligible market model_sha256 model_spec model_version performance_improvement pool_definition prediction_at prediction_sha256 probability_integrity production_go race_id real_data_execution_go schema selection selection_stage source target_date version".split())
_OUTER_KEYS = set("ModelVersion deadline external_authenticity forecast generated_at mode namespace production_go race_id reproduction schema source_evidence target_date validity".split())
_BINDING_KEYS = set("schema forecast_sha256 result_sha256 race_id lock_at prediction_available_at prediction_revision_at model_odds_snapshot_sha256 market_odds_snapshot_sha256 odds_acquired_at odds_available_at odds_revision_at evaluation_purpose".split())

class AuditHold(ValueError):
    """Only internally authored fixed reason codes are emitted."""

def _need(ok, reason):
    if not ok: raise AuditHold(reason)

def sha256(raw):
    _need(type(raw) is bytes, "RAW_BYTES_REQUIRED")
    return hashlib.sha256(raw).hexdigest()

def parse_raw(raw, expected_sha256):
    _need(type(raw) is bytes and len(raw) > 0, "RAW_BYTES_REQUIRED")
    _need(isinstance(expected_sha256, str) and _SHA.fullmatch(expected_sha256) is not None, "EXPECTED_RAW_SHA_INVALID")
    _need(sha256(raw) == expected_sha256, "RAW_SHA256_MISMATCH")
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_): raise AuditHold("NONFINITE_JSON_TOKEN")
    try: return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except AuditHold: raise
    except (UnicodeError, ValueError, TypeError, RecursionError): raise AuditHold("RAW_JSON_INVALID") from None

def aware_time(value):
    _need(type(value) is str and _TIME.fullmatch(value) is not None and not value.endswith("-00:00"), "AWARE_TIME_INVALID")
    if value[-1] != "Z":
        _need(int(value[-5:-3]) <= 23 and int(value[-2:]) <= 59, "AWARE_TIME_INVALID")
    try: result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: raise AuditHold("AWARE_TIME_INVALID") from None
    _need(result.tzinfo is not None and result.utcoffset() is not None, "AWARE_TIME_INVALID")
    return result

def _safe_tree(value):
    if isinstance(value, dict):
        _need(not any(not isinstance(key, str) or key.lower() in _FORBIDDEN for key in value), "OUTCOME_OR_PAYOUT_IN_PREDICTION")
        for child in value.values(): _safe_tree(child)
    elif isinstance(value, list):
        for child in value: _safe_tree(child)

def _time_tree(value, cutoff):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _TIMES | {"effective_at", "fit_cutoff", "training_max_available_at", "training_max_prediction_at", "motor_updated_at"}:
                _need(aware_time(child) <= cutoff, "FUTURE_INFORMATION_IN_SAVED_FORECAST")
            else: _time_tree(child, cutoff)
    elif isinstance(value, list):
        for child in value: _time_tree(child, cutoff)

def _information(info, cutoff):
    _need(isinstance(info, dict) and {"feature_times", "state_times", "odds_times"} <= set(info), "INPUT_TIME_EVIDENCE_MISSING")
    for group, fields in (("feature_times", _FEATURES), ("state_times", {"course", "fl", "scratched"})):
        values = info[group]
        _need(isinstance(values, dict) and set(values) == set(map(str, range(1, 7))), "BOAT_TIME_DOMAIN_INCOMPLETE")
        for per_boat in values.values():
            _need(isinstance(per_boat, dict) and set(per_boat) == fields, "FEATURE_TIME_DOMAIN_INCOMPLETE")
            for times in per_boat.values():
                _need(isinstance(times, dict) and set(times) == _TIMES, "FEATURE_TIMES_MISSING")
    _need(isinstance(info["odds_times"], dict) and set(info["odds_times"]) == _TIMES, "ODDS_TIMES_MISSING")
    _time_tree(info, cutoff)

def _prediction(record):
    _need(isinstance(record, dict), "PREDICTION_NOT_OBJECT")
    if record.get("schema") == "MODEL11_INDEPENDENT_SHADOW_RECORD_V005":
        _need(set(record) == _OUTER_KEYS and record.get("mode") == "SIMULATION" and record.get("production_go") is False, "SAVED_V005_SCHEMA_OR_MODE_INVALID")
        evidence = record.get("source_evidence")
        _need(isinstance(evidence, dict) and evidence.get("data_classification") == "SYNTHETIC_ONLY" and evidence.get("synthetic") is True, "PRIVATE_DATA_EXECUTION_NOT_APPROVED")
        forecast = record.get("forecast")
        _need(isinstance(forecast, dict) and set(forecast) == _INNER_KEYS and forecast.get("schema") == "MODEL11_FORECAST_V003", "SAVED_FORECAST_SCHEMA_UNSUPPORTED")
        _need(forecast.get("production_go") is False and forecast.get("real_data_execution_go") is False and forecast.get("live_eligible") is False, "LIVE_FORECAST_NOT_SUPPORTED")
        for key in ("race_id", "target_date", "deadline"):
            _need(record.get(key) == forecast.get(key), "SAVED_HEADER_IDENTITY_MISMATCH")
        projection = {key: forecast.get(key) for key in ("race_id", "target_date", "prediction_at", "deadline", "source", "information", "distributions")}
        projection["generated_at"] = record.get("generated_at")
        return projection, evidence
    expected = set("schema data_classification synthetic source race_id target_date generated_at prediction_at deadline information distributions production_go".split())
    _need(record.get("schema") == "INDEPENDENT_PROBABILITY_INPUT_V001_PROPOSED" and set(record) == expected, "PREDICTION_SCHEMA_UNSUPPORTED")
    _need(record.get("data_classification") == "SYNTHETIC_ONLY" and record.get("synthetic") is True and record.get("production_go") is False, "PRIVATE_DATA_EXECUTION_NOT_APPROVED")
    return record, None

def audit_saved_prediction(prediction_raw, prediction_sha256, result_raw, result_sha256, binding, *, stage):
    """Recompute one loss from exact supplied bytes. No likelihood floor/fitting.

    The binding is a proposed audit sidecar, not an authenticated LOCK receipt.
    Unknown production/A/B schemas need a separately approved private adapter.
    """
    base = {"status": "HOLD", "reason_codes": [], "production_go": False, "formal_eligibility": "UNVERIFIED",
            "source_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT", "logarithm": "NATURAL", "logloss": None,
            "normalization_applied": False, "probability_floor_applied": False, "raw_hash_scope": "EXACT_INPUT_BYTES_NOT_REENCODED",
            "integration": "EVALUATION_ONLY_NO_MODEL_FEATURE_SELECTION_OR_WRITER_CONNECTION"}
    try:
        _need(type(stage) is str and stage in STAGES, "PROBABILITY_STAGE_MUST_BE_EXPLICIT")
        record = parse_raw(prediction_raw, prediction_sha256)
        result = parse_raw(result_raw, result_sha256)
        _need(type(binding) is dict and set(binding) == _BINDING_KEYS and binding.get("schema") == "SAVED_RAW_LOGLOSS_BINDING_V001_PROPOSED", "AUDIT_BINDING_SCHEMA_INVALID")
        _need(binding.get("forecast_sha256") == prediction_sha256 and binding.get("result_sha256") == result_sha256, "AUDIT_BINDING_RAW_SHA_MISMATCH")
        _need(binding.get("evaluation_purpose") == "HASHED_RAW_EVALUATION_ONLY", "EVALUATION_BOUNDARY_REQUIRED")
        projected, evidence = _prediction(record)
        _safe_tree(projected)
        race = projected.get("race_id")
        _need(isinstance(race, str) and _ID.fullmatch(race) is not None and binding.get("race_id") == race, "RACE_IDENTITY_INVALID_OR_MISMATCH")
        _need(isinstance(projected.get("source"), str) and _ID.fullmatch(projected["source"]) is not None, "SOURCE_ID_INVALID")
        deadline = aware_time(projected.get("deadline"));predicted = aware_time(projected.get("prediction_at"));generated = aware_time(projected.get("generated_at"));locked = aware_time(binding.get("lock_at"))
        _need(predicted <= generated <= locked < deadline, "PREDICTION_NOT_PREDEADLINE_OR_TIME_ORDER_INVALID")
        _need(projected.get("target_date") == deadline.astimezone(timezone(timedelta(hours=9))).date().isoformat(), "TARGET_DATE_DEADLINE_MISMATCH")
        for key in ("prediction_available_at", "prediction_revision_at"):
            _need(generated <= aware_time(binding[key]) <= locked, "PREDICTION_PUBLICATION_TIME_INVALID")
        _information(projected.get("information"), predicted)
        _time_tree(projected, predicted)
        if evidence is not None:
            _safe_tree(record["forecast"])
            _time_tree(record["forecast"], predicted)
            _time_tree(evidence, predicted)
        for key in ("model_odds_snapshot_sha256", "market_odds_snapshot_sha256"):
            _need(isinstance(binding[key], str) and _SHA.fullmatch(binding[key]) is not None, "ODDS_SNAPSHOT_SHA_INVALID")
        _need(binding["model_odds_snapshot_sha256"] == binding["market_odds_snapshot_sha256"], "MODEL_MARKET_SNAPSHOT_MISMATCH")
        for key, inner in (("odds_acquired_at", "acquired_at"), ("odds_available_at", "available_at"), ("odds_revision_at", "revision_at")):
            value = aware_time(binding[key]);_need(value <= predicted and value == aware_time(projected["information"]["odds_times"][inner]), "ODDS_SNAPSHOT_TIME_MISMATCH_OR_FUTURE")
        distributions = projected.get("distributions")
        _need(isinstance(distributions, dict) and set(distributions) == STAGES, "FOUR_DISTINCT_PROBABILITY_STAGES_REQUIRED")
        for values in distributions.values():
            _need(isinstance(values, dict) and set(values) == TICKETS, "PROBABILITY_120_DOMAIN_INVALID")
            _need(all(type(p) in (int,float) and math.isfinite(p) and 0 <= p <= 1 for p in values.values()), "PROBABILITY_VALUE_INVALID")
            _need(abs(math.fsum(values.values()) - 1.0) <= NUMERICAL_SUM_TOLERANCE, "PROBABILITY_SUM_INVALID")
        expected_result = set("schema race_id outcome published_at available_at revision_at status".split())
        _need(isinstance(result, dict) and set(result) == expected_result and result.get("schema") == "INDEPENDENT_RESULT_INPUT_V001_PROPOSED", "RESULT_SCHEMA_UNSUPPORTED")
        _need(result.get("race_id") == race and result.get("status") == "FINAL", "RESULT_IDENTITY_OR_FINALITY_INVALID")
        published = aware_time(result.get("published_at"))
        _need(published >= deadline and aware_time(result.get("available_at")) >= published and aware_time(result.get("revision_at")) >= published, "RESULT_PREDEADLINE_OR_TIME_INVALID")
        outcome = result.get("outcome")
        _need(isinstance(outcome, list) and len(outcome) == 3 and all(type(n) is int and 1 <= n <= 6 for n in outcome) and len(set(outcome)) == 3, "RESULT_TRIFECTA_INVALID")
        probability = distributions[stage]["-".join(map(str, outcome))]
        output = {**base, "reason_codes": [], "prediction_raw_sha256": prediction_sha256, "result_raw_sha256": result_sha256,
                  "stage": stage, "probability_sum_observed": math.fsum(distributions[stage].values()),
                  "same_snapshot_claim": "MATCHED_SELF_REPORTED_SHA_AND_TIMES_NOT_AUTHENTICATED",
                  "timing_claim": "MATCHED_SELF_REPORTED_NOT_AUTHENTICATED", "AB_input_role": "INDEPENDENT_RAW_EVALUATION_ONLY" if projected["source"] in ("A","B") else "RESEARCH_RAW_EVALUATION_ONLY"}
        if probability == 0:
            return {**output, "status": "UNVERIFIED_INFINITE_LOGLOSS", "reason_codes": ["OBSERVED_OUTCOME_HAS_ZERO_PROBABILITY"], "nonfinite_logloss": "POSITIVE_INFINITY", "loss_is_finite": False}
        loss = -math.log(probability)
        return {**output, "status": "RECOMPUTED_AUDIT_ONLY", "logloss": 0.0 if loss == 0 else loss, "loss_is_finite": True}
    except AuditHold as exc:
        return {**base, "reason_codes": [exc.args[0]]}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {**base, "reason_codes": ["AUDIT_INPUT_INVALID"]}
