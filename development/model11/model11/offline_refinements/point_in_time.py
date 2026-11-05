"""Pure proposed point-in-time audit; not a loader, model or live input gateway."""
from __future__ import annotations

from datetime import date, timedelta, timezone
from itertools import permutations
import math
import re

from ..validation import FEATURES, _timestamp, prediction_view

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TIMES = ("acquired_at", "available_at", "revision_at")
_JST = timezone(timedelta(hours=9))


def _add(codes, code):
    if code not in codes:
        codes.append(code)


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _version(value):
    return _identifier(value) and value.upper() not in {"LATEST", "CURRENT", "LATEST_TABLE", "CURRENT_TABLE"}


def _sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _provenance(item, snapshot, as_of, errors, prefix, effective=False):
    if not isinstance(item, dict):
        _add(errors, prefix + "_MISSING")
        return
    stamps = {field: _timestamp(item.get(field)) for field in _TIMES}
    if any(value is None for value in stamps.values()):
        _add(errors, prefix + "_TIME_UNKNOWN_OR_INVALID")
    if as_of and any(value and value > as_of for value in stamps.values()):
        _add(errors, prefix + "_UPDATED_OR_AVAILABLE_AFTER_AS_OF")
    preserved = _timestamp(snapshot.get("preserved_at")) if isinstance(snapshot, dict) else None
    if preserved and any(value and value > preserved for value in stamps.values()):
        _add(errors, prefix + "_SOURCE_TIME_AFTER_SNAPSHOT_PRESERVATION")
    acquired, available, revised = (stamps[key] for key in _TIMES)
    if acquired and available and acquired > available or acquired and revised and acquired > revised:
        _add(errors, prefix + "_TIME_ORDER_INVALID")
    if not _version(item.get("version")):
        _add(errors, prefix + "_VERSION_UNKNOWN_OR_LATEST")
    if not _identifier(item.get("source_id")):
        _add(errors, prefix + "_SOURCE_ID_UNKNOWN")
    if not _sha(item.get("evidence_sha256")):
        _add(errors, prefix + "_EVIDENCE_SHA_UNKNOWN")
    if not isinstance(snapshot, dict) or item.get("snapshot_id") != snapshot.get("snapshot_id"):
        _add(errors, prefix + "_IMMUTABLE_SNAPSHOT_BINDING_MISMATCH")
    if effective:
        stamp = _timestamp(item.get("effective_at"))
        if stamp is None:
            _add(errors, prefix + "_EFFECTIVE_TIME_UNKNOWN")
        elif as_of and stamp > as_of:
            _add(errors, prefix + "_EFFECTIVE_AFTER_AS_OF")
        elif acquired and stamp > acquired:
            _add(errors, prefix + "_EFFECTIVE_AFTER_ACQUISITION")


def _training(context, as_of):
    if context is None:
        return "UNVERIFIED_NOT_SUPPLIED", []
    errors = []
    if not isinstance(context, dict) or set(context) != {"normalizer_fit_cutoff", "model_fit_cutoff", "training_rows"}:
        return "HOLD", ["TRAINING_CONTEXT_FIELDS_UNKNOWN"]
    normalizer = _timestamp(context["normalizer_fit_cutoff"])
    model = _timestamp(context["model_fit_cutoff"])
    if normalizer is None or model is None or as_of is None:
        _add(errors, "TRAINING_FIT_CUTOFF_UNKNOWN")
    elif not normalizer <= model < as_of:
        _add(errors, "TRAINING_FIT_NOT_BEFORE_AS_OF")
    rows = context["training_rows"]
    if not isinstance(rows, list) or not rows:
        _add(errors, "TRAINING_ROW_CHRONOLOGY_MISSING")
        rows = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"prediction_at", "feature_available_at", "label_available_at"}:
            _add(errors, "TRAINING_ROW_FIELDS_UNKNOWN")
            continue
        predicted, feature, label = (_timestamp(row[key]) for key in ("prediction_at", "feature_available_at", "label_available_at"))
        if any(value is None for value in (predicted, feature, label)):
            _add(errors, "TRAINING_ROW_TIME_UNKNOWN")
        elif normalizer and model and not (feature <= predicted < normalizer <= model and predicted < label <= model):
            _add(errors, "TRAINING_FEATURE_OR_LABEL_NOT_AVAILABLE_AT_FIT")
    return ("CLAIMS_CONSISTENT" if not errors else "HOLD"), errors


def audit_point_in_time(sample):
    """Audit invented snapshots at one fixed as_of; no data/odds substitution.

    Feature and market results are separate, but missing/final odds make the
    overall check HOLD. Real inputs remain held; authenticity stays unverified.
    """
    report = {"schema": "POINT_IN_TIME_AUDIT_V007_PROPOSED", "status": "HOLD", "software_check": "UNVERIFIED",
              "feature_eligible": False, "market_eligible": False, "market_baseline_eligible": False,
              "expected_value_eligible": False, "feature_reasons": [], "market_reasons": [], "reasons": [],
              "training_context_status": "UNVERIFIED_NOT_SUPPLIED", "application_status": "HOLD",
              "real_input_status": "HOLD", "external_authenticity": "UNVERIFIED",
              "origin_proof": "SELF_REPORTED_ONLY", "actual_source_mapping": "OPEN", "production_go": False}
    if not isinstance(sample, dict):
        report["reasons"] = ["POINT_IN_TIME_SAMPLE_REQUIRED"]
        return report
    if (sample.get("data_classification") != "SYNTHETIC_ONLY" or sample.get("synthetic") is not True
            or not isinstance(sample.get("target_date"), str) or not sample["target_date"].startswith("2099-")):
        report["reasons"] = ["REAL_INPUT_OR_UNVERIFIED_CLASSIFICATION_HOLD"]
        return report
    common, features, market = [], [], []
    required = {"data_classification", "synthetic", "race_id", "target_date", "as_of", "deadline", "snapshot", "features", "odds"}
    if set(sample) - {"training_context"} != required:
        _add(common, "POINT_IN_TIME_FIELDS_MISSING_OR_UNKNOWN")
    try:
        prediction_view({key: value for key, value in sample.items() if key != "training_context"})
    except Exception:
        _add(common, "FEATURE_OR_PAYLOAD_LABEL_LEAKAGE_OR_INVALID_JSON")
    if not _identifier(sample.get("race_id")):
        _add(common, "RACE_ID_UNKNOWN")
    as_of, deadline = _timestamp(sample.get("as_of")), _timestamp(sample.get("deadline"))
    if as_of is None or deadline is None:
        _add(common, "AS_OF_OR_DEADLINE_UNKNOWN")
    elif as_of >= deadline:
        _add(common, "AS_OF_NOT_PRE_DEADLINE")
    try:
        target_date = date.fromisoformat(sample["target_date"])
        if target_date.isoformat() != sample["target_date"] or deadline and deadline.astimezone(_JST).date() != target_date:
            _add(common, "TARGET_DATE_DEADLINE_MISMATCH")
    except (ValueError, TypeError, KeyError):
        _add(common, "TARGET_DATE_UNKNOWN")
    snapshot = sample.get("snapshot")
    if (not isinstance(snapshot, dict) or set(snapshot) != {"mode", "snapshot_id", "version", "preserved_at", "source_id", "content_sha256", "evidence_sha256"}
            or snapshot.get("mode") != "IMMUTABLE_SNAPSHOT"):
        _add(common, "IMMUTABLE_OLD_SNAPSHOT_REQUIRED_NO_LATEST_TABLE")
    if isinstance(snapshot, dict):
        if not _identifier(snapshot.get("snapshot_id")) or not _version(snapshot.get("version")):
            _add(common, "IMMUTABLE_SNAPSHOT_ID_OR_VERSION_UNKNOWN")
        if not _identifier(snapshot.get("source_id")) or not _sha(snapshot.get("content_sha256")) or not _sha(snapshot.get("evidence_sha256")):
            _add(common, "IMMUTABLE_SNAPSHOT_SOURCE_OR_SHA_UNKNOWN")
        preserved = _timestamp(snapshot.get("preserved_at"))
        if preserved is None:
            _add(common, "IMMUTABLE_SNAPSHOT_PRESERVATION_TIME_UNKNOWN")
        elif as_of and preserved > as_of:
            _add(common, "SNAPSHOT_PRESERVED_AFTER_AS_OF")
    items = sample.get("features")
    domain = {(boat, name) for boat in range(1, 7) for name in FEATURES}
    seen = set()
    if not isinstance(items, list):
        _add(features, "FEATURE_OBSERVATIONS_REQUIRED")
        items = []
    for item in items:
        fields = {"boat", "name", "value", "unit", "effective_at", *_TIMES, "version", "snapshot_id", "source_id", "evidence_sha256"}
        if not isinstance(item, dict) or set(item) != fields:
            _add(features, "FEATURE_FIELDS_UNKNOWN_OR_MISSING")
            continue
        key = (item["boat"], item["name"])
        if type(item["boat"]) is not int or not isinstance(item["name"], str) or key not in domain:
            _add(features, "FEATURE_DOMAIN_UNKNOWN")
            continue
        if key in seen:
            _add(features, "FEATURE_OBSERVATION_DUPLICATE")
        seen.add(key)
        if not _number(item["value"]) or not _identifier(item["unit"]):
            _add(features, "FEATURE_VALUE_OR_DECLARED_UNIT_UNKNOWN")
        _provenance(item, snapshot, as_of, features, "FEATURE", effective=True)
    if seen != domain:
        _add(features, "REQUIRED_FEATURE_OBSERVATION_MISSING")
    odds = sample.get("odds")
    if odds is None:
        _add(market, "PRE_DEADLINE_ODDS_MISSING_NO_FINAL_FALLBACK")
    elif not isinstance(odds, dict):
        _add(market, "PRE_DEADLINE_ODDS_FIELDS_UNKNOWN")
    else:
        if set(odds) != {"kind", "values", *_TIMES, "version", "snapshot_id", "source_id", "evidence_sha256"}:
            _add(market, "PRE_DEADLINE_ODDS_FIELDS_UNKNOWN")
        if odds.get("kind") != "PRE_DEADLINE":
            _add(market, "FINAL_OR_POST_RACE_ODDS_FORBIDDEN")
        values = odds.get("values")
        expected = {"-".join(map(str, triple)) for triple in permutations(range(1, 7), 3)}
        if not isinstance(values, dict) or set(values) != expected:
            _add(market, "PRE_DEADLINE_ODDS_120_DOMAIN_REQUIRED")
        if isinstance(values, dict) and any(not _number(value) or value <= 0 for value in values.values()):
            _add(market, "PRE_DEADLINE_ODDS_VALUE_UNKNOWN")
        _provenance(odds, snapshot, as_of, market, "ODDS")
    context_status, training_errors = _training(sample.get("training_context"), as_of)
    report["training_context_status"] = context_status
    feature_errors = list(dict.fromkeys(common + features + training_errors))
    market_errors = list(dict.fromkeys(common + market))
    report.update(feature_reasons=feature_errors, market_reasons=market_errors,
                  feature_eligible=not feature_errors, market_eligible=not market_errors,
                  market_baseline_eligible=not market_errors, expected_value_eligible=not feature_errors and not market_errors,
                  reasons=list(dict.fromkeys(feature_errors + market_errors)))
    if not report["reasons"]:
        report.update(status="SYNTHETIC_POINT_IN_TIME_CANDIDATE", software_check="PASS")
    return report
