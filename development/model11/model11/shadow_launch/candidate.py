"""Future privately approved research path; never weakens v003 real-data HOLD.

Simulation calls the immutable v003 predictor. The separate private kernel uses
the same math after an explicit launch preflight, not a synthetic relabelling.
Approval metadata remains operator-attested and externally UNVERIFIED.
"""
from copy import deepcopy
from datetime import datetime
import math

from ..engine import canonical_hash, check_distribution, usable_market
from ..validation import prediction_view, validate_race, _timestamp as _strict_timestamp
from ..probabilities import temperature_scale
from ..selection import select_five
from ..preparation.shadow import _normalization_evidence
from ..revision_v003.course import CourseBoundModel, validate_course
from ..revision_v003.engine import predict_v003
from ..revision_v003.pooling import pool_market
from ..revision_v003.portfolios import build_portfolios
from .policy import preflight


def _time(value):
    result = _strict_timestamp(value)
    if result is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    return result


def forecast_candidate(race, model, model_config, settings, artifacts, now, operator_ack=None, human_input=None):
    gate = preflight(settings, artifacts, operator_ack=operator_ack, now=now)
    if not gate["allowed"]:
        raise ValueError("LAUNCH_PREFLIGHT_HOLD")
    config = {} if model_config is None else deepcopy(model_config)
    if (not isinstance(model, CourseBoundModel) or model.to_dict() != artifacts["model"]
            or config != artifacts["prediction_config"]):
        raise ValueError("FROZEN_MODEL_OR_CONFIG_MISMATCH")
    if not isinstance(race, dict) or race.get("active_boats") != [1, 2, 3, 4, 5, 6]:
        raise ValueError("SIX_ACTIVE_BOATS_REQUIRED_FOR_120_OUTCOMES")
    normalization = _normalization_evidence(race)
    approved_normalizer = artifacts["normalizer"]
    if normalization is None or any(normalization.get(field) != approved_normalizer.get(field)
            for field in ("normalizer_sha256", "feature_specs_sha256", "training_input_sha256",
                          "fit_cutoff", "training_max_available_at")):
        raise ValueError("APPROVED_NORMALIZATION_PROVENANCE_REQUIRED")
    if settings["mode"] == "SIMULATION":
        return predict_v003(race, model, config, human_input=human_input)
    # This path is callable only after private preflight and explicit operator
    # attestation. It does not contact an official source or grant an actual GO.
    if race.get("data_classification") != "PRIVATE_REAL" or race.get("synthetic") is not False:
        raise ValueError("PRIVATE_SOURCE_CLASSIFICATION_REQUIRED")
    view = prediction_view(race)
    if view.get("human_box_input") is not None:
        raise ValueError("SEPARATE_HUMAN_INPUT_REQUIRED")
    core = validate_race(view, config.get("max_odds_age_seconds", 120))
    course = validate_course(view, model.course_policy)
    if not core["eligible"] or not course["eligible"]:
        raise ValueError("PRIVATE_INPUT_OR_COURSE_HOLD")
    if not _time(view["prediction_at"]) <= now < _time(view["deadline"]):
        raise ValueError("PRIVATE_PREDICTION_CLOCK_HOLD")
    for field in ("training_max_available_at", "training_max_prediction_at"):
        stamp = getattr(model, field, None)
        if stamp is None or _time(stamp) >= _time(view["prediction_at"]):
            raise ValueError("PRIVATE_TRAINING_CHRONOLOGY_HOLD")
    weight = config.get("market_weight", .25)
    if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("PRIVATE_MARKET_WEIGHT_HOLD")
    distributions = model.distributions(view)
    integrity = {key: check_distribution(value, view["active_boats"])
                 for key, value in distributions.items()}
    calibrated = temperature_scale(distributions["P_model"], config.get("temperature", 1.0))
    market = usable_market(view, config.get("max_odds_age_seconds", 120), core)
    if market["P_market"] is None:
        raise ValueError("COMPLETE_MARKET_REQUIRED_FOR_SHADOW")
    distributions["P_market"] = market["P_market"]
    distributions["P_shrunk"] = pool_market(calibrated, market["P_market"], weight)
    integrity.update({key: check_distribution(distributions[key], view["active_boats"])
                      for key in ("P_market", "P_shrunk")})
    odds = view["odds_snapshot"]["odds"]
    five = select_five(distributions["P_shrunk"], odds, config.get("selection"))
    boxes = build_portfolios(view, distributions["P_shrunk"], five, odds, human_input, config.get("selection"))
    if human_input is not None and not boxes["human_input_gate"]["eligible"]:
        raise ValueError("PRIVATE_HUMAN_INPUT_HOLD")
    output = {"schema": "MODEL11_PRIVATE_RESEARCH_FORECAST_V005", "version": "0.5.0-shadow-launch-candidate",
              "model_version": "MODEL_1.1_RESEARCH_CANDIDATE", "classification": "PRIVATE_RESEARCH_ONLY",
              "source": "MODEL11_THIRD_RESEARCH", "race_id": view["race_id"],
              "target_date": view["target_date"], "prediction_at": view["prediction_at"],
              "deadline": view["deadline"], "input_sha256": canonical_hash(view),
              "model_sha256": canonical_hash(model.to_dict()), "model_spec": model.to_dict(),
              "config": config, "distributions": distributions, "P_calibrated": calibrated,
              "probability_integrity": integrity, "selection": five, "boxes": boxes,
              "bet_decision": five["bet_decision"], "first_course": None,
              "course_evidence": course, "normalization_provenance": normalization,
              "approval_authenticity": "OPERATOR_ATTESTATION_EXTERNAL_REVIEW_REQUIRED",
              "performance_improvement": "UNVERIFIED", "production_go": False}
    output["prediction_sha256"] = canonical_hash(output)
    return output
