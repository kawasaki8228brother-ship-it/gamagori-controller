"""Validated prediction pipeline. Outcomes are never an input to this module."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from itertools import permutations
import json
import math

from .probabilities import market_distribution, loglinear_pool, temperature_scale
from .selection import select_five, build_boxes
from .validation import prediction_view, validate_race


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def check_distribution(dist, active):
    """Reject wrong domains and invalid mass; never repair an invalid prediction."""
    expected = {"-".join(map(str, t)) for t in permutations(sorted(active), 3)}
    if not isinstance(dist, dict) or set(dist) != expected:
        raise ValueError("PROBABILITY_DOMAIN_MISMATCH")
    if any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1
           for p in dist.values()):
        raise ValueError("PROBABILITY_NONFINITE_NEGATIVE_OR_OUT_OF_RANGE")
    total = math.fsum(dist.values())
    if not math.isclose(total, 1.0, abs_tol=1e-10, rel_tol=0):
        raise ValueError("PROBABILITY_MASS_NOT_ONE")
    return {"status": "PASS", "count": len(dist), "sum": total,
            "repeated_boat_count": 0, "invalid_probability_count": 0}


def usable_market(race, max_odds_age_seconds=120, gate=None):
    """Respect schema/provenance gates as well as numeric odds conversion."""
    gate = gate or validate_race(race, max_odds_age_seconds=max_odds_age_seconds)
    if not gate.get("market_available"):
        return {"status": gate.get("market_status", "UNAVAILABLE"), "P_market": None,
                "reason": "MARKET_VALIDATION_GATE", "warning_codes": gate["warnings"]}
    return market_distribution(race, max_odds_age_seconds=max_odds_age_seconds)


def predict_race(race, model, config=None):
    config = {} if config is None else deepcopy(config)
    if not isinstance(config, dict) or set(config) - {"temperature", "market_weight", "selection", "max_odds_age_seconds"}:
        raise ValueError("UNKNOWN_PIPELINE_CONFIGURATION")
    age = config.get("max_odds_age_seconds", 120)
    view = prediction_view(race)
    gate = validate_race(view, max_odds_age_seconds=age)
    if not gate["eligible"]:
        raise ValueError("PREDICTION_GATE:" + ",".join(gate["errors"]))
    if getattr(model, "training_count", 0) <= 0:
        raise ValueError("MODEL_NOT_FITTED")
    cutoff = datetime.fromisoformat(view["prediction_at"].replace("Z", "+00:00"))
    for field in ("training_max_available_at", "training_max_prediction_at"):
        value = getattr(model, field, None)
        if value is None:
            raise ValueError("MODEL_TRAINING_CHRONOLOGY_UNVERIFIED")
        if datetime.fromisoformat(value.replace("Z", "+00:00")) >= cutoff:
            raise ValueError("MODEL_TRAINING_NOT_BEFORE_PREDICTION")
    # P_model is the market-free course-prior distribution. Calibration is an
    # explicit optional derivative, never silently relabelled as P_raw/model.
    distributions = model.distributions(view)
    if set(distributions) != {"P_raw", "P_model"}:
        raise ValueError("MODEL_DISTRIBUTION_KEYS")
    diagnostics = {name: check_distribution(dist, view["active_boats"])
                   for name, dist in distributions.items()}
    market = usable_market(view, max_odds_age_seconds=age, gate=gate)
    distributions["P_market"] = market["P_market"]
    temperature = config.get("temperature", 1.0)
    calibrated = temperature_scale(distributions["P_model"], temperature)
    diagnostics["P_calibrated"] = check_distribution(calibrated, view["active_boats"])
    weight = config.get("market_weight", 0.25)
    if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("MARKET_WEIGHT_DOMAIN")
    if market["P_market"] is None:
        distributions["P_shrunk"] = None
        diagnostics["P_market"] = diagnostics["P_shrunk"] = {"status": "UNAVAILABLE", "reason": market["reason"]}
        selected_dist, selection_stage, odds = calibrated, "P_calibrated", None
    else:
        diagnostics["P_market"] = check_distribution(distributions["P_market"], view["active_boats"])
        distributions["P_shrunk"] = loglinear_pool(calibrated, distributions["P_market"], weight)
        diagnostics["P_shrunk"] = check_distribution(distributions["P_shrunk"], view["active_boats"])
        selected_dist, selection_stage = distributions["P_shrunk"], "P_shrunk"
        odds = view["odds_snapshot"]["odds"]
    selection = select_five(selected_dist, odds, config.get("selection"))
    boxes = build_boxes(view, selected_dist, selection, odds, config.get("selection"))
    model_spec = model.to_dict()
    output = {
        "classification": "LANE2_RESEARCH_ONLY", "version": "0.1.0-research",
        "race_id": view["race_id"], "target_date": view["target_date"],
        "prediction_at": view["prediction_at"], "deadline": view["deadline"],
        "source": "MODEL11_RESEARCH", "input_sha256": canonical_hash(view),
        "model_sha256": canonical_hash(model_spec), "config": config,
        "config_status": "PROPOSED", "model_spec": model_spec,
        "distributions": distributions, "P_calibrated": calibrated,
        "probability_integrity": diagnostics, "market": {k: v for k, v in market.items() if k != "P_market"},
        "selection_stage": selection_stage, "selection": selection, "boxes": boxes,
        "bet_decision": selection["bet_decision"],
        "first_course": None,  # outcome-specific course is attached only during evaluation.
        "gate": gate,
        "information": {
            "feature_times": {str(b["boat"]): b["feature_times"] for b in view["boats"]},
            "state_times": {str(b["boat"]): b["state_times"] for b in view["boats"]},
            "odds_acquired_at": None if view.get("odds_snapshot") is None else view["odds_snapshot"].get("acquired_at"),
            "odds_available_at": None if view.get("odds_snapshot") is None else view["odds_snapshot"].get("available_at"),
            "human_box_provenance": None if view.get("human_box_input") is None else {
                field: view["human_box_input"].get(field)
                for field in ("observed_at", "acquired_at", "available_at", "revision_at")},
            "missing_or_warning_codes": gate["warnings"],
            "timestamp_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT",
        },
        "explanation": {str(boat): detail for boat, detail in model.explain(view).items()},
        "legacy_model10": "OPEN_VERIFIED_SOURCE_OR_FROZEN_OUTPUT_REQUIRED",
        "legacy_box_v1": "OPEN_VERIFIED_SOURCE_OR_FROZEN_OUTPUT_REQUIRED",
        "performance_improvement": "UNVERIFIED", "production_go": False,
    }
    output["prediction_sha256"] = canonical_hash(output)
    return output
