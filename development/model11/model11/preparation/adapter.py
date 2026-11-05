"""RAW_V001 private-input preparation; explicit proposed, train-only transforms.

No real source adapter, unit conversion, production rule or authenticity verifier
is implemented. All diagnostics are fixed codes, never raw submitted values.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import re

from ..validation import FEATURES, validate_race

_STATES = ("course", "fl", "scratched")
_TIMES = ("acquired_at", "available_at", "revision_at")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UNITS = {"seconds", "score_0_100", "rate_fraction", "rating_points"}
_FORBIDDEN = {"result", "results", "outcome", "outcomes", "payout", "payouts", "actual",
              "refund", "refunds", "label", "labels", "prediction", "predictions",
              "legacy", "model10", "box", "winner", "winners", "final"}
_SOURCE_FORBIDDEN = {"A", "B", "MODEL1.0", "MODEL_1.0", "MODEL10", "BOXV1", "BOX_VER_1"}
_NORMALIZATION = "TRAIN_MINMAX_CLIP_V001"


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _time(value):
    if not isinstance(value, str) or not _TIME.fullmatch(value) or value.endswith("-00:00"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _num(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _add(codes, code):
    if code not in codes:
        codes.append(code)


def _scan(raw):
    codes, ancestors = [], set()
    budget = [50000]

    def walk(value, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 32:
            _add(codes, "RAW_INPUT_LIMIT")
            return
        if isinstance(value, (dict, list)):
            ident = id(value)
            if ident in ancestors:
                _add(codes, "RAW_INPUT_CYCLE")
                return
            ancestors.add(ident)
            pairs = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in pairs:
                if isinstance(value, dict):
                    if not isinstance(key, str):
                        _add(codes, "RAW_KEY_TYPE")
                    else:
                        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", key).lower()
                        tokens = set(re.findall(r"[a-z0-9]+", normalized))
                        if key != "prediction_at" and tokens & _FORBIDDEN:
                            _add(codes, "FORBIDDEN_OUTCOME_OR_LEGACY_INPUT")
                        if normalized in {"source", "source_id", "origin", "system"}:
                            if isinstance(child, str) and child.upper() in _SOURCE_FORBIDDEN:
                                _add(codes, "FORBIDDEN_AB_SOURCE_INPUT")
                walk(child, depth + 1)
            ancestors.remove(ident)
        elif isinstance(value, str):
            try:
                value.encode("utf-8", "strict")
            except UnicodeError:
                _add(codes, "RAW_TEXT_ENCODING")
        elif value is not None and type(value) is not bool and not _num(value):
            _add(codes, "RAW_NON_JSON_OR_NONFINITE")
    walk(raw)
    return codes


def synthetic_feature_specs():
    """Invented physical-looking units for simulator plumbing, NOT real mapping."""
    return {
        "schema_version": "FEATURE_SPECS_V001", "version": "synthetic-proposed-v001",
        "status": "PROPOSED", "mapping_status": "SYNTHETIC_INVENTED_ONLY",
        "features": {
            "st": {"unit": "seconds", "direction": "LOWER_IS_BETTER", "normalization": _NORMALIZATION},
            "turn": {"unit": "score_0_100", "direction": "HIGHER_IS_BETTER", "normalization": _NORMALIZATION},
            "motor": {"unit": "rate_fraction", "direction": "HIGHER_IS_BETTER", "normalization": _NORMALIZATION},
            "ability": {"unit": "rating_points", "direction": "HIGHER_IS_BETTER", "normalization": _NORMALIZATION},
            "exhibition": {"unit": "seconds", "direction": "LOWER_IS_BETTER", "normalization": _NORMALIZATION},
        },
    }


def _spec_errors(specs):
    errors = []
    if not isinstance(specs, dict):
        return ["FEATURE_SPECS_SHAPE"]
    required = {"schema_version", "version", "status", "mapping_status", "features"}
    if specs.get("mapping_status") == "HQ14_PRIVATE_MAPPING_UNVERIFIED":
        required.add("review_evidence")
    if set(specs) != required:
        return ["FEATURE_SPECS_SHAPE"]
    if specs["schema_version"] != "FEATURE_SPECS_V001" or specs["status"] != "PROPOSED":
        _add(errors, "FEATURE_SPECS_STATUS")
    if (not isinstance(specs["version"], str) or not specs["version"]
            or specs["mapping_status"] not in ("SYNTHETIC_INVENTED_ONLY", "HQ14_PRIVATE_MAPPING_UNVERIFIED")):
        _add(errors, "FEATURE_SPECS_VERSION_OR_MAPPING")
    if specs["mapping_status"] == "HQ14_PRIVATE_MAPPING_UNVERIFIED":
        evidence = specs["review_evidence"]
        if (not isinstance(evidence, dict) or set(evidence) != {"hq14_review_sha256", "claude_review_sha256"}
                or any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in evidence.values())):
            _add(errors, "PRIVATE_MAPPING_REVIEW_METADATA_MISSING_OR_INVALID")
    items = specs["features"]
    if not isinstance(items, dict) or set(items) != set(FEATURES):
        return errors + ["FEATURE_SPECS_DOMAIN"]
    for spec in items.values():
        if not isinstance(spec, dict) or set(spec) != {"unit", "direction", "normalization"}:
            _add(errors, "FEATURE_SPEC_SHAPE")
            continue
        if not isinstance(spec["unit"], str) or spec["unit"] not in _UNITS:
            _add(errors, "FEATURE_UNIT_UNREGISTERED")
        if spec["direction"] not in ("LOWER_IS_BETTER", "HIGHER_IS_BETTER"):
            _add(errors, "FEATURE_DIRECTION_UNREGISTERED")
        if spec["normalization"] != _NORMALIZATION:
            _add(errors, "NORMALIZATION_NOT_EXPLICITLY_SUPPORTED")
    return errors


def _provenance(item, predicted, errors, prefix):
    if not isinstance(item, dict):
        _add(errors, prefix + "_PROVENANCE_MISSING")
        return
    times = {field: _time(item.get(field)) for field in _TIMES}
    if any(stamp is None for stamp in times.values()):
        _add(errors, prefix + "_TIME_INVALID")
    if predicted and any(stamp and stamp > predicted for stamp in times.values()):
        _add(errors, prefix + "_LATE_OR_FUTURE_REVISION")
    acquired, available, revised = (times[field] for field in _TIMES)
    if acquired and available and acquired > available:
        _add(errors, prefix + "_AVAILABLE_BEFORE_ACQUIRED")
    if acquired and revised and acquired > revised:
        _add(errors, prefix + "_REVISION_BEFORE_ACQUIRED")
    if not isinstance(item.get("evidence_sha256"), str) or not _SHA.fullmatch(item["evidence_sha256"]):
        _add(errors, prefix + "_EVIDENCE_HASH_INVALID")


def _times(item):
    return {field: item[field] for field in _TIMES}


def _fields(item, allowed, errors, code):
    if not isinstance(item, dict) or set(item) != set(allowed):
        _add(errors, code)


def _compatible(raw, values):
    """Build only the public old schema; do not pass source/raw metadata through."""
    result = {field: deepcopy(raw[field]) for field in ("race_id", "target_date", "venue", "prediction_at", "active_boats")}
    result["deadline"] = raw["deadline"]["value"]
    result["boats"] = []
    for item in raw["boats"]:
        acquired = [item["features"][name]["acquired_at"] for name in FEATURES]
        revised = [item["features"][name]["revision_at"] for name in FEATURES]
        acquired += [item[name]["acquired_at"] for name in _STATES]
        revised += [item[name]["revision_at"] for name in _STATES]
        identity = item["motor_identity"]
        acquired.append(identity["acquired_at"])
        revised.append(identity["revision_at"])
        result["boats"].append({
            "boat": item["boat"], "course": item["course"]["value"],
            "fl": item["fl"]["value"], "scratched": item["scratched"]["value"],
            "features": dict(values[item["boat"]]),
            "feature_times": {name: _times(item["features"][name]) for name in FEATURES},
            "state_times": {name: _times(item[name]) for name in _STATES},
            "observed_at": max(acquired, key=_time),
            "motor_updated_at": identity["effective_at"],
            "revision_at": max(revised + acquired, key=_time),
        })
    market = raw.get("odds_snapshot")
    if (isinstance(market, dict) and "odds" in market
            and all(_time(market.get(field)) is not None for field in _TIMES)):
        result["odds_snapshot"] = {**_times(market), "odds": deepcopy(market["odds"])}
    else:
        result["odds_snapshot"] = None
    # No manual prediction input is accepted by this raw feature adapter.
    result["human_box_input"] = None
    result["data_classification"] = raw["data_classification"]
    return result


def validate_raw_race(raw, feature_specs):
    """Check RAW_V001 claims without mistaking hashes for external authenticity."""
    errors, warnings = _spec_errors(feature_specs), []
    if not isinstance(raw, dict):
        return {"eligible": False, "status": "HOLD", "errors": errors + ["RAW_SHAPE"], "warnings": []}
    errors += [code for code in _scan(raw) if code not in errors]
    allowed = {"schema_version", "data_classification", "race_id", "target_date", "venue", "prediction_at",
               "race_provenance", "deadline", "active_boats", "active_boats_provenance", "boats", "odds_snapshot"}
    if set(raw) != allowed:
        _add(errors, "RAW_FIELDS_MISSING_OR_UNREGISTERED")
    if raw.get("schema_version") != "RAW_V001":
        _add(errors, "RAW_VERSION")
    if raw.get("data_classification") not in ("SYNTHETIC_ONLY", "HQ14_PRIVATE_OFFLINE"):
        _add(errors, "RAW_CLASSIFICATION")
    if (raw.get("data_classification") == "HQ14_PRIVATE_OFFLINE"
            and isinstance(feature_specs, dict)
            and feature_specs.get("mapping_status") == "SYNTHETIC_INVENTED_ONLY"):
        _add(errors, "SYNTHETIC_MAPPING_FORBIDDEN_FOR_PRIVATE_DATA")
    prediction = _time(raw.get("prediction_at"))
    if prediction is None:
        _add(errors, "RAW_PREDICTION_TIME")
    for key in ("race_provenance", "active_boats_provenance"):
        _provenance(raw.get(key), prediction, errors, "RAW_" + key.upper())
        _fields(raw.get(key), {*_TIMES, "evidence_sha256"}, errors, "RAW_PROVENANCE_FIELDS")
    deadline = raw.get("deadline")
    _provenance(deadline, prediction, errors, "RAW_DEADLINE")
    _fields(deadline, {"value", "unit", *_TIMES, "evidence_sha256"}, errors, "RAW_DEADLINE_FIELDS")
    if not isinstance(deadline, dict) or deadline.get("unit") != "timestamp" or _time(deadline.get("value")) is None:
        _add(errors, "RAW_DEADLINE_VALUE_OR_UNIT")
    boats, values, seen = raw.get("boats"), {}, set()
    if not isinstance(boats, list) or not 3 <= len(boats) <= 6:
        _add(errors, "RAW_BOATS_SHAPE")
        boats = []
    for boat in boats:
        allowed_boat = {"boat", "course", "fl", "scratched", "motor_identity", "features"}
        if not isinstance(boat, dict) or set(boat) != allowed_boat:
            _add(errors, "RAW_BOAT_FIELDS")
            continue
        number = boat["boat"]
        if type(number) is not int or not 1 <= number <= 6 or number in seen:
            _add(errors, "RAW_BOAT_ID_OR_DUPLICATE")
            continue
        seen.add(number)
        for state in _STATES:
            val = boat.get(state)
            _provenance(val, prediction, errors, "RAW_STATE")
            _fields(val, {"value", "unit", *_TIMES, "evidence_sha256"}, errors, "RAW_STATE_FIELDS")
            expected = "course_number" if state == "course" else "boolean"
            if not isinstance(val, dict) or val.get("unit") != expected:
                _add(errors, "RAW_STATE_UNIT")
            elif state == "course" and (type(val.get("value")) is not int or not 1 <= val["value"] <= 6):
                _add(errors, "RAW_COURSE_VALUE")
            elif state != "course" and type(val.get("value")) is not bool:
                _add(errors, "RAW_STATE_VALUE")
        identity = boat.get("motor_identity")
        _provenance(identity, prediction, errors, "RAW_MOTOR_IDENTITY")
        _fields(identity, {"motor_id", "version", "effective_at", *_TIMES, "evidence_sha256"}, errors, "RAW_MOTOR_IDENTITY_FIELDS")
        if not isinstance(identity, dict):
            _add(errors, "RAW_MOTOR_IDENTITY_MISSING")
        else:
            if any(not isinstance(identity.get(key), str) or not identity[key] for key in ("motor_id", "version")):
                _add(errors, "RAW_MOTOR_IDENTITY_INVALID")
            effective, acquired = _time(identity.get("effective_at")), _time(identity.get("acquired_at"))
            if effective is None or (prediction and effective > prediction) or (effective and acquired and effective > acquired):
                _add(errors, "RAW_MOTOR_EFFECTIVE_TIME_INVALID")
        features = boat.get("features")
        if not isinstance(features, dict) or set(features) != set(FEATURES):
            _add(errors, "RAW_FEATURE_DOMAIN")
            continue
        values[number] = {}
        for name in FEATURES:
            item = features[name]
            _provenance(item, prediction, errors, "RAW_FEATURE")
            if not isinstance(item, dict):
                _add(errors, "RAW_FEATURE_VALUE")
                continue
            allowed_feature = {"value", "unit", *_TIMES, "evidence_sha256"}
            if name == "motor":
                allowed_feature |= {"motor_id", "motor_version"}
            if set(item) != allowed_feature:
                _add(errors, "RAW_FEATURE_FIELDS_UNREGISTERED_OR_MISSING")
            if not _num(item.get("value")):
                _add(errors, "RAW_FEATURE_VALUE")
            elif (item.get("unit") == "seconds" and item["value"] <= 0
                  or item.get("unit") == "score_0_100" and not 0 <= item["value"] <= 100
                  or item.get("unit") == "rate_fraction" and not 0 <= item["value"] <= 1
                  or item.get("unit") == "rating_points" and item["value"] < 0):
                _add(errors, "RAW_FEATURE_UNIT_DOMAIN")
            if not errors or not _spec_errors(feature_specs):
                specs = feature_specs.get("features", {})
                if name in specs and isinstance(specs[name], dict) and item.get("unit") != specs[name].get("unit"):
                    _add(errors, "RAW_FEATURE_UNIT_MISMATCH")
            if name == "motor" and isinstance(identity, dict):
                if item.get("motor_id") != identity.get("motor_id") or item.get("motor_version") != identity.get("version"):
                    _add(errors, "RAW_MOTOR_IDENTITY_OR_VERSION_MISMATCH")
                effective = _time(identity.get("effective_at"))
                if effective and any(_time(item.get(field)) and _time(item[field]) < effective for field in _TIMES):
                    _add(errors, "RAW_MOTOR_STAT_PREDATES_IDENTITY_EFFECTIVE")
            values[number][name] = 0.0  # schema probe only, never returned or used as data
    market = raw.get("odds_snapshot")
    if market is not None:
        market_errors = []
        _provenance(market, prediction, market_errors, "RAW_ODDS")
        _fields(market, {"unit", "odds", *_TIMES, "evidence_sha256"}, market_errors, "RAW_ODDS_FIELDS")
        if not isinstance(market, dict) or market.get("unit") != "gross_payout_multiple":
            _add(market_errors, "RAW_ODDS_UNIT_OR_SHAPE")
        for code in market_errors:
            _add(warnings, code)
    else:
        _add(warnings, "RAW_ODDS_MISSING")
    if not errors:
        compatible = _compatible(raw, values)
        core = validate_race(compatible)
        errors.extend(core["errors"])
        warnings.extend(code for code in core["warnings"] if code not in warnings)
    return {"eligible": not errors, "status": "RAW_VALID_CLAIMS_ONLY" if not errors else "HOLD",
            "errors": errors, "warnings": warnings,
            "external_authenticity": "UNVERIFIED", "real_mapping": "OPEN", "production_go": False,
            "review_evidence_status": "SELF_REPORTED_HASHES_ONLY" if isinstance(feature_specs, dict)
            and feature_specs.get("mapping_status") == "HQ14_PRIVATE_MAPPING_UNVERIFIED"
            else "NOT_REQUIRED_SYNTHETIC_ONLY"}


def fit_normalizer(training_records, fit_cutoff, feature_specs):
    """Fit only supplied earlier raw snapshots; no labels or A/B inputs accepted."""
    if not isinstance(training_records, list) or not training_records:
        raise ValueError("TRAINING_DATA_MISSING")
    cutoff = _time(fit_cutoff)
    if cutoff is None:
        raise ValueError("FIT_CUTOFF_INVALID")
    if _spec_errors(feature_specs):
        raise ValueError("FEATURE_SPECS_INVALID")
    snapshots, ids, observed = {}, [], {name: [] for name in FEATURES}
    latest_prediction, latest_availability = [], []
    for raw in training_records:
        report = validate_raw_race(raw, feature_specs)
        if not report["eligible"]:
            raise ValueError("TRAINING_RAW_INVALID")
        ident = raw["race_id"]
        if ident in snapshots:
            raise ValueError("TRAINING_RACE_DUPLICATE")
        if _time(raw["prediction_at"]) >= cutoff:
            raise ValueError("TRAINING_NOT_BEFORE_FIT_CUTOFF")
        snapshots[ident] = _hash(raw)
        ids.append(ident)
        latest_prediction.append(raw["prediction_at"])
        for boat in raw["boats"]:
            if boat["boat"] not in raw["active_boats"]:
                continue
            for name in FEATURES:
                feature = boat["features"][name]
                if any(_time(feature[field]) >= cutoff for field in _TIMES):
                    raise ValueError("TRAINING_FEATURE_NOT_AVAILABLE_BEFORE_FIT")
                observed[name].append(feature["value"])
                latest_availability.append(feature["available_at"])
    statistics = {}
    for name, vals in observed.items():
        if not vals or min(vals) == max(vals):
            raise ValueError("TRAIN_FEATURE_STATISTICS_ABSENT_OR_CONSTANT")
        statistics[name] = {"min": min(vals), "max": max(vals), "count": len(vals),
                            **deepcopy(feature_specs["features"][name])}
    normalizer = {
        "schema_version": "NORMALIZER_V001", "status": "PROPOSED",
        "method": _NORMALIZATION, "fit_cutoff": fit_cutoff,
        "feature_specs": deepcopy(feature_specs), "feature_specs_sha256": _hash(feature_specs),
        "training_race_ids": sorted(ids), "training_record_sha256s": dict(sorted(snapshots.items())),
        "training_input_sha256": _hash(dict(sorted(snapshots.items()))),
        "training_max_prediction_at": max(latest_prediction, key=_time),
        "training_max_available_at": max(latest_availability, key=_time),
        "statistics": statistics, "external_authenticity": "UNVERIFIED", "production_go": False,
    }
    normalizer["normalizer_sha256"] = _hash(normalizer)
    return normalizer


def _normalizer_metadata_valid(normalizer):
    """Validate internal claims too: a recomputed self-hash grants no authority."""
    try:
        specs = normalizer["feature_specs"]
        cutoff = _time(normalizer["fit_cutoff"])
        availability = _time(normalizer["training_max_available_at"])
        predicted = _time(normalizer["training_max_prediction_at"])
        if (_spec_errors(specs) or normalizer["method"] != _NORMALIZATION
                or normalizer["status"] != "PROPOSED" or cutoff is None
                or availability is None or predicted is None
                or availability >= cutoff or predicted >= cutoff):
            return False
        ids, snapshots = normalizer["training_race_ids"], normalizer["training_record_sha256s"]
        if (not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids)
                or len(set(ids)) != len(ids) or not isinstance(snapshots, dict)
                or set(ids) != set(snapshots)
                or any(not isinstance(digest, str) or not _SHA.fullmatch(digest) for digest in snapshots.values())
                or normalizer["training_input_sha256"] != _hash(dict(sorted(snapshots.items())))):
            return False
        stats = normalizer["statistics"]
        if not isinstance(stats, dict) or set(stats) != set(FEATURES):
            return False
        for name in FEATURES:
            stat = stats[name]
            if (not isinstance(stat, dict) or set(stat) != {"min", "max", "count", "unit", "direction", "normalization"}
                    or not _num(stat["min"]) or not _num(stat["max"]) or stat["min"] >= stat["max"]
                    or type(stat["count"]) is not int or stat["count"] < 2
                    or any(stat[key] != specs["features"][name][key] for key in ("unit", "direction", "normalization"))):
                return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def normalize_race(raw, normalizer, usage="prediction"):
    """Apply a frozen explicit transform; never fit/refit using the target race."""
    if not isinstance(normalizer, dict) or normalizer.get("schema_version") != "NORMALIZER_V001":
        raise ValueError("NORMALIZER_INVALID")
    if usage not in ("prediction", "training"):
        raise ValueError("NORMALIZATION_USAGE_INVALID")
    claimed = normalizer.get("normalizer_sha256")
    try:
        actual = _hash({key: value for key, value in normalizer.items() if key != "normalizer_sha256"})
    except (TypeError, ValueError):
        raise ValueError("NORMALIZER_INVALID") from None
    if claimed != actual:
        raise ValueError("NORMALIZER_HASH_MISMATCH")
    if not _normalizer_metadata_valid(normalizer):
        raise ValueError("NORMALIZER_METADATA_INVALID")
    specs = normalizer.get("feature_specs")
    if _spec_errors(specs) or normalizer.get("feature_specs_sha256") != _hash(specs):
        raise ValueError("NORMALIZER_SPEC_MISMATCH")
    if not validate_raw_race(raw, specs)["eligible"]:
        raise ValueError("RAW_INPUT_INVALID")
    training_hash = normalizer["training_record_sha256s"].get(raw["race_id"])
    if training_hash is not None and training_hash != _hash(raw):
        raise ValueError("TRAINING_RECORD_CHANGED")
    if usage == "training" and training_hash is None:
        raise ValueError("TRAINING_USAGE_REQUIRES_FROZEN_TRAINING_ID")
    if usage == "prediction" and (_time(raw["prediction_at"]) <= _time(normalizer["fit_cutoff"])
                                   or _time(raw["prediction_at"]) <= _time(normalizer["training_max_available_at"])):
        raise ValueError("NORMALIZER_NOT_AVAILABLE_AT_PREDICTION")
    values, clips = {}, []
    for boat in raw["boats"]:
        values[boat["boat"]] = {}
        for name in FEATURES:
            stat = normalizer["statistics"].get(name)
            if (not isinstance(stat, dict) or not _num(stat.get("min")) or not _num(stat.get("max"))
                    or stat["min"] >= stat["max"]):
                raise ValueError("NORMALIZER_STATISTICS_INVALID")
            val = boat["features"][name]["value"]
            if not _num(val):
                raise ValueError("RAW_FEATURE_MISSING_NO_IMPUTATION")
            scaled = 2.0 * (val - stat["min"]) / (stat["max"] - stat["min"]) - 1.0
            if not math.isfinite(scaled):
                raise ValueError("NORMALIZATION_NONFINITE")
            if scaled < -1 or scaled > 1:
                clips.append({"boat": boat["boat"], "feature": name, "code": "OUTSIDE_TRAINING_RANGE_CLIPPED"})
            scaled = min(1.0, max(-1.0, scaled))
            if stat["direction"] == "LOWER_IS_BETTER":
                scaled = -scaled
            values[boat["boat"]][name] = scaled
    race = _compatible(raw, values)
    race["normalization_usage"] = "TRAINING_ONLY_NOT_FORECAST" if usage == "training" else "PREDICTION_AS_OF_GATE_PASSED"
    race["normalization_provenance"] = {
        "normalizer_sha256": claimed, "feature_specs_sha256": _hash(specs),
        "fit_cutoff": normalizer["fit_cutoff"],
        "training_max_available_at": normalizer["training_max_available_at"],
        "training_input_sha256": normalizer["training_input_sha256"], "usage": usage,
    }
    raw_report = validate_raw_race(raw, specs)
    # Bad optional market provenance is never passed to an otherwise valid model.
    if any(code.startswith("RAW_ODDS_") for code in raw_report["warnings"]):
        race["odds_snapshot"] = None
    final_gate = validate_race(race)
    if not final_gate["eligible"]:
        raise ValueError("NORMALIZED_SCHEMA_INVALID")
    return {"race": race, "audit": {
        "status": "TRAINING_ONLY_NOT_FORECAST" if usage == "training" else "TRANSFORMED_PROPOSED",
        "usage": usage, "raw_input_sha256": _hash(raw),
        "normalizer_sha256": claimed, "feature_specs_sha256": _hash(specs),
        "fit_cutoff": normalizer["fit_cutoff"], "training_input": training_hash is not None,
        "clipped": clips, "warnings": raw_report["warnings"],
        "market_status": final_gate["market_status"], "external_authenticity": "UNVERIFIED",
        "real_mapping": "OPEN", "production_go": False}}


def make_raw_fixture(race):
    """Invent raw physical-looking values ONLY from an explicitly synthetic race."""
    if (not isinstance(race, dict) or race.get("synthetic") is not True
            or race.get("data_classification") != "SYNTHETIC_ONLY"
            or not isinstance(race.get("target_date"), str) or not race["target_date"].startswith("2099-")):
        raise ValueError("SYNTHETIC_FIXTURE_ONLY")
    if not validate_race(race)["eligible"]:
        raise ValueError("SYNTHETIC_SOURCE_INVALID")
    def prov(times, salt):
        return {**deepcopy(times), "evidence_sha256": _hash({"synthetic_evidence": salt})}
    def wrapper(value, unit, times, salt):
        return {"value": value, "unit": unit, **prov(times, salt)}
    observed = race["boats"][0]["feature_times"]["st"]
    raw = {field: deepcopy(race[field]) for field in ("race_id", "target_date", "venue", "prediction_at", "active_boats")}
    raw.update({"schema_version": "RAW_V001", "data_classification": "SYNTHETIC_ONLY",
                "race_provenance": prov(observed, "race"),
                "active_boats_provenance": prov(observed, "active"),
                "deadline": wrapper(race["deadline"], "timestamp", observed, "deadline"), "boats": []})
    for original in race["boats"]:
        number = original["boat"]
        motor_id = "SYNTHETIC_MOTOR_" + str(number)
        motor_version = "SYNTHETIC_v001"
        item = {"boat": number, "features": {}}
        for state in _STATES:
            item[state] = wrapper(original[state], "course_number" if state == "course" else "boolean",
                                  original["state_times"][state], state + str(number))
        item["motor_identity"] = {"motor_id": motor_id, "version": motor_version,
                                  "effective_at": original["motor_updated_at"],
                                  **prov(original["feature_times"]["motor"], "motor_identity" + str(number))}
        for name in FEATURES:
            x = original["features"][name]
            invented = {"st": 0.25 - 0.2 * x, "turn": 50 + 50 * x,
                        "motor": (x + 1) / 2, "ability": 50 + 10 * x,
                        "exhibition": 7.0 - 0.6 * x}[name]
            item["features"][name] = wrapper(invented, synthetic_feature_specs()["features"][name]["unit"],
                                              original["feature_times"][name], name + str(number))
            if name == "motor":
                item["features"][name].update(motor_id=motor_id, motor_version=motor_version)
        raw["boats"].append(item)
    market = race.get("odds_snapshot")
    raw["odds_snapshot"] = None if market is None else {
        "odds": deepcopy(market["odds"]), "unit": "gross_payout_multiple",
        **prov(_times(market), "odds")}
    return raw
