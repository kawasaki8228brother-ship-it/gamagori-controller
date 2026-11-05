"""Synthetic-only v003 walk-forward; independent module, old workflow untouched."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math

from ..engine import canonical_hash, usable_market
from ..probabilities import temperature_scale
from ..validation import validate_dataset
from .pooling import DEFAULT_MARKET_WEIGHTS, pool_market


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _config(supplied, default_policy):
    defaults = {"train_days": 12, "selection_days": 4, "test_days": 4,
                "candidates": ["hierarchical", "contextual"], "alphas": [0.0, 0.5],
                "temperatures": [0.8, 1.0, 1.2], "market_weights": list(DEFAULT_MARKET_WEIGHTS),
                "epochs": 20, "learning_rate": 0.3, "l2": 0.01,
                "selection": {}, "max_odds_age_seconds": 120, "course_policy": deepcopy(default_policy),
                "evaluation": {"day_bootstrap": {"enabled": True, "confidence": 0.95,
                    "replicates": 500, "min_clusters": 5, "seed": 20261105,
                    "preregistration_reference": "PROPOSED_SYNTHETIC_V003_NOT_REAL_CONFIRMATORY"}}}
    supplied = {} if supplied is None else supplied
    if not isinstance(supplied, dict) or set(supplied) - set(defaults):
        raise ValueError("HOLD:UNKNOWN_V003_WALK_FORWARD_CONFIG")
    cfg = deepcopy({**defaults, **supplied})
    for key in ("train_days", "selection_days", "test_days", "epochs"):
        if type(cfg[key]) is not int or cfg[key] < 1:
            raise ValueError("HOLD:POSITIVE_INTEGER_CONFIG_REQUIRED")
    for key in ("candidates", "alphas", "temperatures", "market_weights"):
        if not isinstance(cfg[key], list) or not cfg[key]:
            raise ValueError("HOLD:INVALID_OR_DUPLICATE_SELECTION_GRID")
    if any(name not in ("hierarchical", "contextual") for name in cfg["candidates"]):
        raise ValueError("HOLD:UNKNOWN_CANDIDATE")
    for key, allow_zero, upper in (("alphas", True, 1), ("temperatures", False, None),
                                    ("market_weights", True, 1)):
        for value in cfg[key]:
            try:
                valid = (type(value) in (int, float) and math.isfinite(value) and value >= 0
                         and (allow_zero or value != 0) and (upper is None or value <= upper))
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("HOLD:INVALID_SELECTION_GRID_VALUE")
    for key in ("candidates", "alphas", "temperatures", "market_weights"):
        if len(set(cfg[key])) != len(cfg[key]):
            raise ValueError("HOLD:INVALID_OR_DUPLICATE_SELECTION_GRID")
    age = cfg["max_odds_age_seconds"]
    try:
        valid_age = type(age) in (int, float) and math.isfinite(age) and age >= 0
    except OverflowError:
        valid_age = False
    if not valid_age:
        raise ValueError("HOLD:INVALID_ODDS_AGE_CONFIG")
    return cfg


def _parameters(name, alpha, temperature, weight, score, signature):
    market_only = weight == 1
    return {"candidate": name, "alpha": alpha, "temperature": temperature,
            "market_weight": weight, "model_weight": 1-weight,
            "selection_mean_log_loss": score,
            "prediction_type": "MARKET_ONLY" if market_only else "MODEL_ONLY" if weight == 0 else "MODEL_MARKET_POOL",
            "underlying_candidate_role": "DIAGNOSTIC_ONLY_NOT_A_LEARNED_MODEL_VICTORY" if market_only else "CONTRIBUTING_MODEL",
            "equivalence_class": "MARKET_ONLY_ALL_CANDIDATES_ALPHA_TEMPERATURE" if market_only else signature,
            "selection_probability_sha256": signature}


def walk_forward_v003(dataset, config=None):
    """Frozen-grid diagnostic selection before each genuinely future test block.

    This path accepts invented 2099 fixtures only. F5 adequacy thresholds are not
    adopted; no amount of synthetic selection data is declared preregistered.
    Previous test days can become later training days in this expanding workflow,
    which is explicitly not an untouched final confirmatory holdout.
    """
    from .course import COURSE_POLICIES, CourseBoundModel, validate_course
    from .engine import predict_v003
    from .evaluation import evaluate_records_v003

    if not isinstance(dataset, dict) or dataset.get("classification") != "SYNTHETIC_ONLY":
        raise ValueError("HOLD:REAL_INPUT_REQUIRES_APPROVED_PREREGISTRATION")
    cfg = _config(config, COURSE_POLICIES["EXHIBITION_ONLY_V001"])
    races, outcomes = dataset.get("races"), dataset.get("outcomes")
    if not isinstance(races, list) or not isinstance(outcomes, list):
        raise ValueError("HOLD:DATASET_SHAPE_INVALID")
    if (any(not isinstance(r, dict) or r.get("synthetic") is not True
            or r.get("data_classification") != "SYNTHETIC_ONLY"
            or not str(r.get("target_date", "")).startswith("2099-") for r in races)
            or any(not isinstance(o, dict) or o.get("synthetic") is not True
                   or not str(o.get("target_date", "")).startswith("2099-") for o in outcomes)):
        raise ValueError("HOLD:SYNTHETIC_2099_INPUT_ONLY")
    frozen_config_sha = canonical_hash(cfg)
    # Validate the fixed course policy before seeing any outcomes during fitting.
    for race in races:
        course = validate_course(race, cfg["course_policy"])
        if not course["eligible"]:
            raise ValueError("HOLD:COURSE_GATE:" + ",".join(course["errors"]))
    data_gate = validate_dataset(races, outcomes)
    if not data_gate["eligible"]:
        raise ValueError("HOLD:DATASET_GATE:" + ",".join(data_gate["errors"]))
    by_id = {o["race_id"]: o for o in outcomes}
    if {r["race_id"] for r in races} != set(by_id):
        raise ValueError("HOLD:RACE_OUTCOME_PAIRING_NOT_EXACT")
    ordered = sorted(races, key=lambda r: (_time(r["prediction_at"]), r["race_id"]))
    days = sorted({r["target_date"] for r in ordered})
    first_test = cfg["train_days"] + cfg["selection_days"]
    if len(days) < first_test + cfg["test_days"]:
        raise ValueError("HOLD:INSUFFICIENT_CHRONOLOGICAL_DAYS")
    grid = {key: deepcopy(cfg[key]) for key in ("candidates", "alphas", "temperatures", "market_weights")}
    nominal = math.prod(len(values) for values in grid.values())
    nonmarket = len(cfg["market_weights"]) - int(1 in cfg["market_weights"])
    structural_bound = (len(cfg["candidates"])*len(cfg["alphas"])*len(cfg["temperatures"])*nonmarket
                        + int(1 in cfg["market_weights"]))
    folds, records = [], []
    candidate_records = {name: [] for name in cfg["candidates"]}

    def predict_block(block, fitted, chosen):
        result = []
        pipeline = {"temperature": chosen["temperature"], "market_weight": chosen["market_weight"],
                    "selection": deepcopy(cfg["selection"]), "max_odds_age_seconds": cfg["max_odds_age_seconds"]}
        for race in block:
            forecast = predict_v003(race, fitted, pipeline)
            # Forecast has already been frozen; neither the predictor nor
            # preselected hyperparameters receive this evaluation-only label.
            forecast["actual"] = deepcopy(by_id[race["race_id"]])
            forecast["first_course"] = next(b["course"] for b in race["boats"]
                                            if b["boat"] == forecast["actual"]["result"][0])
            result.append(forecast)
        return result

    for start in range(first_test, len(days)-cfg["test_days"]+1, cfg["test_days"]):
        train_days = days[:start-cfg["selection_days"]]
        selection_days = days[start-cfg["selection_days"]:start]
        test_days = days[start:start+cfg["test_days"]]
        train = [r for r in ordered if r["target_date"] in train_days]
        selected = [r for r in ordered if r["target_date"] in selection_days]
        test = [r for r in ordered if r["target_date"] in test_days]
        train_cutoff = min(_time(r["prediction_at"]) for r in selected)
        test_cutoff = min(_time(r["prediction_at"]) for r in test)
        if any(_time(by_id[r["race_id"]]["available_at"]) >= train_cutoff for r in train):
            raise ValueError("HOLD:TRAIN_LABEL_UNAVAILABLE_AT_SELECTION_CUTOFF")
        if any(_time(by_id[r["race_id"]]["available_at"]) >= test_cutoff for r in selected):
            raise ValueError("HOLD:SELECTION_LABEL_UNAVAILABLE_AT_TEST_CUTOFF")
        market_cache = {r["race_id"]: usable_market(r, cfg["max_odds_age_seconds"])["P_market"] for r in selected}
        paired = [r for r in selected if market_cache[r["race_id"]] is not None]
        if not paired:
            raise ValueError("HOLD:NO_MARKET_AVAILABLE_SELECTION_PAIRS")
        best, best_by_candidate, score_table = None, {}, []
        for name in cfg["candidates"]:
            for alpha in cfg["alphas"]:
                model = CourseBoundModel(name, {"epochs": cfg["epochs"], "alpha": alpha,
                    "learning_rate": cfg["learning_rate"], "l2": cfg["l2"]}, cfg["course_policy"])
                model.fit(train, [by_id[r["race_id"]] for r in train])
                cached = [(r, model.distributions(r)["P_model"], market_cache[r["race_id"]]) for r in paired]
                for temperature in cfg["temperatures"]:
                    calibrated = [(r, temperature_scale(dist, temperature), market) for r, dist, market in cached]
                    for weight in cfg["market_weights"]:
                        losses, vectors = [], {}
                        for race, dist, market in calibrated:
                            pooled = pool_market(dist, market, weight)
                            actual = "-".join(map(str, by_id[race["race_id"]]["result"]))
                            if pooled[actual] <= 0:
                                raise ValueError("HOLD:NONFINITE_SELECTION_LOGLOSS")
                            losses.append(-math.log(pooled[actual]))
                            vectors[race["race_id"]] = pooled
                        score = math.fsum(losses)/len(losses)
                        params = _parameters(name, alpha, temperature, weight, score, canonical_hash(vectors))
                        score_table.append(params)
                        # Stable first-in-frozen-grid tie policy; no test labels.
                        if best is None or score < best[0]:
                            best = (score, model, params)
                        if name not in best_by_candidate or score < best_by_candidate[name][0]:
                            best_by_candidate[name] = (score, model, params)
        _, model, params = best
        fold_records = predict_block(test, model, params)
        records.extend(fold_records)
        candidate_reports = {}
        for name, (_, candidate, chosen) in best_by_candidate.items():
            candidate_fold = predict_block(test, candidate, chosen)
            candidate_records[name].extend(candidate_fold)
            candidate_reports[name] = {"selected_on_past_selection_only": chosen,
                                       "evaluation": evaluate_records_v003(candidate_fold, cfg["evaluation"])}
        adequacy = {"status": "UNVERIFIED_NOT_PREREGISTERED", "reason": "F5_DESIGN_PENDING_NOT_ADOPTED",
                    "selection_days": len(selection_days), "selection_races": len(selected),
                    "common_market_paired_races": len(paired), "excluded_missing_market_races": len(selected)-len(paired),
                    "nominal_grid_members": nominal, "structural_probability_upper_bound": structural_bound,
                    "observed_distinct_selection_vectors": len({p["selection_probability_sha256"] for p in score_table}),
                    "interpretation": "SYNTHETIC_DIAGNOSTIC_UNDERPOWERED_NO_FORMAL_PASS"}
        folds.append({"fold": len(folds)+1, "train_days": train_days, "selection_days": selection_days,
                      "test_days": test_days, "train_ids": [r["race_id"] for r in train],
                      "selection_ids": [r["race_id"] for r in selected],
                      "selection_paired_ids": [r["race_id"] for r in paired], "test_ids": [r["race_id"] for r in test],
                      "train_label_cutoff": train_cutoff.isoformat(), "selection_label_cutoff": test_cutoff.isoformat(),
                      "selection_adequacy": adequacy, "selected": params, "selection_scores": score_table,
                      "model": model.to_dict(), "model_sha256": canonical_hash(model.to_dict()),
                      "forecast_hashes": [r["prediction_sha256"] for r in fold_records],
                      "candidate_comparisons": candidate_reports,
                      "evaluation": evaluate_records_v003(fold_records, cfg["evaluation"])})
    return {"schema": "MODEL11_WALK_FORWARD_V003", "classification": "SYNTHETIC_ONLY",
            "status": "SYNTHETIC_DIAGNOSTIC_ONLY", "config_status": "PROPOSED", "config": cfg,
            "frozen_config_sha256": frozen_config_sha, "candidate_grid": grid,
            "grid_freeze_scope": "COPIED_BEFORE_ALL_SELECTION_AND_TEST_ACCESS_SELF_REPORTED",
            "market_weight_definition": "w=MARKET_WEIGHT;1-w=MODEL_WEIGHT",
            "market_only_equivalence": "ALL_MODELS_ALPHA_TEMPERATURE_AT_W1_ARE_ONE_PROBABILITY_CLASS",
            "selection_adequacy": "UNVERIFIED_NOT_PREREGISTERED_F5_DESIGN_PENDING",
            "dataset_sha256": canonical_hash(dataset), "folds": folds, "records": records,
            "evaluation": evaluate_records_v003(records, cfg["evaluation"]),
            "candidate_evaluations": {name: evaluate_records_v003(rows, cfg["evaluation"]) for name, rows in candidate_records.items()},
            "initial_days_not_evaluated": days[:first_test],
            "trailing_days_not_evaluated": days[first_test+len(folds)*cfg["test_days"]:],
            "future_untouched_real_evaluation": "OPEN", "legacy_comparison": "OPEN",
            "superiority": "UNVERIFIED", "production_go": False, "real_data_execution_go": False}
