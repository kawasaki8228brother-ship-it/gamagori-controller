"""V003 pipeline: course-bound learning, explicit market weight, named BOX lanes."""
from copy import deepcopy
from datetime import datetime
import math

from ..engine import canonical_hash, check_distribution, usable_market
from ..probabilities import temperature_scale
from ..selection import select_five
from ..validation import prediction_view, validate_race
from ..preparation.shadow import _normalization_evidence
from .course import CourseBoundModel, validate_course
from .pooling import pool_market
from .portfolios import build_portfolios


def predict_v003(race, model, config=None, human_input=None):
    """No result inputs, no inferred course origin, no automatic Human BOX label."""
    if (not isinstance(race, dict) or race.get("synthetic") is not True
            or race.get("data_classification") != "SYNTHETIC_ONLY"
            or not str(race.get("target_date", "")).startswith("2099-")):
        raise ValueError("HOLD_REAL_INPUT_REVIEW_REQUIRED")
    if not isinstance(model, CourseBoundModel):
        raise ValueError("HOLD_COURSE_BOUND_MODEL_REQUIRED")
    cfg = {} if config is None else deepcopy(config)
    if not isinstance(cfg, dict) or set(cfg) - {"temperature", "market_weight", "selection", "max_odds_age_seconds"}:
        raise ValueError("HOLD_PIPELINE_CONFIGURATION")
    view = prediction_view(race)
    normalization = _normalization_evidence(view)
    if view.get("human_box_input") is not None:
        raise ValueError("HOLD_LEGACY_HUMAN_INPUT_REQUIRES_SEPARATE_V003_EVIDENCE")
    gate = validate_race(view, cfg.get("max_odds_age_seconds", 120))
    if not gate["eligible"]:
        raise ValueError("HOLD_INPUT:" + ",".join(gate["errors"]))
    course = validate_course(view, model.course_policy)
    if not course["eligible"]:
        raise ValueError("HOLD_COURSE:" + ",".join(course["errors"]))
    if model.training_count <= 0:
        raise ValueError("HOLD_MODEL_NOT_FITTED")
    predicted = datetime.fromisoformat(view["prediction_at"].replace("Z", "+00:00"))
    for field in ("training_max_available_at", "training_max_prediction_at"):
        value = getattr(model, field, None)
        if value is None or datetime.fromisoformat(value.replace("Z", "+00:00")) >= predicted:
            raise ValueError("HOLD_MODEL_TRAINING_CHRONOLOGY")
    weight = cfg.get("market_weight", .25)
    if type(weight) not in (int, float) or not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("HOLD_MARKET_WEIGHT")
    distributions = model.distributions(view)
    if set(distributions) != {"P_raw", "P_model"}:
        raise ValueError("HOLD_MODEL_DISTRIBUTION_KEYS")
    integrity = {key: check_distribution(value, view["active_boats"])
                 for key, value in distributions.items()}
    calibrated = temperature_scale(distributions["P_model"], cfg.get("temperature", 1.0))
    integrity["P_calibrated"] = check_distribution(calibrated, view["active_boats"])
    market = usable_market(view, cfg.get("max_odds_age_seconds", 120), gate)
    distributions["P_market"] = market["P_market"]
    if market["P_market"] is None:
        if weight == 1:
            raise ValueError("HOLD_MARKET_ONLY_REQUIRES_VALID_MARKET")
        distributions["P_shrunk"] = None
        integrity["P_market"] = integrity["P_shrunk"] = {"status": "UNAVAILABLE", "reason": market["reason"]}
        selected, selected_stage, odds = calibrated, "P_calibrated_MODEL_ONLY_NO_MARKET", None
    else:
        integrity["P_market"] = check_distribution(distributions["P_market"], view["active_boats"])
        distributions["P_shrunk"] = pool_market(calibrated, market["P_market"], weight)
        integrity["P_shrunk"] = check_distribution(distributions["P_shrunk"], view["active_boats"])
        selected, selected_stage, odds = distributions["P_shrunk"], "P_shrunk", view["odds_snapshot"]["odds"]
    five = select_five(selected, odds, cfg.get("selection"))
    boxes = build_portfolios(view, selected, five, odds=odds, human_input=human_input, config=cfg.get("selection"))
    if human_input is not None and not boxes["human_input_gate"]["eligible"]:
        raise ValueError("HOLD_HUMAN_INPUT:" + ",".join(boxes["human_input_gate"]["errors"]))
    spec = model.to_dict()
    result = {
        "schema": "MODEL11_FORECAST_V003", "version": "0.3.0-research",
        "model_version": "MODEL_1.1_RESEARCH_CANDIDATE_V003", "classification": "LANE2_RESEARCH_ONLY",
        "race_id": view["race_id"], "target_date": view["target_date"],
        "prediction_at": view["prediction_at"], "deadline": view["deadline"],
        "source": "MODEL11_RESEARCH_V003", "input_sha256": canonical_hash(view),
        "model_sha256": canonical_hash(spec), "model_spec": spec,
        "config": cfg, "config_status": "PROPOSED",
        "distributions": distributions, "P_calibrated": calibrated,
        "probability_integrity": integrity, "selection_stage": selected_stage,
        "pool_definition": {"market_weight": weight, "model_weight": 1 - weight,
                            "model_component": "P_calibrated", "market_component": "P_market",
                            "formula": "normalize(P_calibrated^(1-w)*P_market^w)",
                            "market_only": weight == 1,
                            "prediction_type": "MARKET_ONLY" if weight == 1 else "MODEL_ONLY" if weight == 0 else "MODEL_MARKET_POOL"},
        "market": {key: value for key, value in market.items() if key != "P_market"},
        "selection": five, "boxes": boxes, "bet_decision": five["bet_decision"],
        "first_course": None, "course_evidence": course,
        "information": {
            "feature_times": {str(boat["boat"]): boat["feature_times"] for boat in view["boats"]},
            "state_times": {str(boat["boat"]): boat["state_times"] for boat in view["boats"]},
            "odds_times": None if view.get("odds_snapshot") is None else {
                field: view["odds_snapshot"].get(field) for field in ("acquired_at", "available_at", "revision_at")},
            "missing_or_warning_codes": gate["warnings"],
            "normalization_provenance": normalization,
            "human_input_status": boxes["human_input_gate"],
            "timestamp_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT"},
        "explanation": {str(boat): detail for boat, detail in model.explain(view).items()},
        "legacy_comparison": "OPEN_VERIFIED_FROZEN_INPUTS_REQUIRED",
        "F2_BOX_DESIGN": "PROPOSED_NOT_IMPLEMENTED_OR_ADOPTED",
        "F5_SELECTION_ADEQUACY": "UNVERIFIED_PREREGISTRATION_PENDING",
        "performance_improvement": "UNVERIFIED", "live_eligible": False,
        "real_data_execution_go": False, "production_go": False,
    }
    result["prediction_sha256"] = canonical_hash(result)
    return result
