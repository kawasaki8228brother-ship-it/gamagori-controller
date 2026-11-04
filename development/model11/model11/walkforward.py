"""Expanding-day walk-forward with train/selection/test information barriers."""
from __future__ import annotations

from datetime import datetime
import math

from .engine import canonical_hash, predict_race, usable_market
from .metrics import evaluate_records
from .models import make_model
from .probabilities import temperature_scale, loglinear_pool
from .validation import validate_dataset


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _integer(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + " must be positive int")
    return value


def walk_forward(dataset, config=None):
    """Choose every candidate/calibration/market parameter on past selection days.

    Fit uses training outcomes only; no refit on selection/test labels. Tests
    are nonoverlapping chronological blocks. Reuse of an earlier test day as
    later historical training is explicit expanding-window prequential research,
    not a single untouched final holdout. A separately sealed future evaluation
    is still required before any performance claim.
    """
    defaults = {"train_days": 12, "selection_days": 4, "test_days": 4,
                "candidates": ["hierarchical", "contextual"],
                "alphas": [0.0, 0.5], "temperatures": [0.8, 1.0, 1.2],
                "market_weights": [0.0, 0.25, 0.5], "epochs": 20,
                "learning_rate": 0.3, "l2": 0.01, "selection": {},
                "evaluation": {"day_bootstrap": {"enabled": True, "confidence": 0.95,
                    "replicates": 500, "min_clusters": 5, "seed": 20261105,
                    "preregistration_reference": "PROPOSED_SYNTHETIC_SOFTWARE_DEMO_NOT_REAL_CONFIRMATORY"}}}
    config = {} if config is None else config
    if not isinstance(config, dict) or set(config) - set(defaults):
        raise ValueError("UNKNOWN_WALK_FORWARD_CONFIG")
    cfg = {**defaults, **config}
    for key in ("train_days", "selection_days", "test_days", "epochs"):
        _integer(cfg[key], key)
    for key in ("candidates", "alphas", "temperatures", "market_weights"):
        if not isinstance(cfg[key], list) or not cfg[key]:
            raise ValueError("EMPTY_SELECTION_GRID:" + key)
    if any(name not in {"hierarchical", "contextual"} for name in cfg["candidates"]):
        raise ValueError("UNKNOWN_CANDIDATE")
    for key, lower, upper in (("alphas", 0, 1), ("temperatures", 0, None), ("market_weights", 0, 1)):
        for value in cfg[key]:
            if (type(value) not in (int, float) or not math.isfinite(value) or value < lower
                    or (key == "temperatures" and value == 0) or (upper is not None and value > upper)):
                raise ValueError("INVALID_SELECTION_GRID:" + key)
    races, outcomes = dataset["races"], dataset["outcomes"]
    data_gate = validate_dataset(races, outcomes)
    if not data_gate["eligible"]:
        raise ValueError("DATASET_GATE:" + ",".join(data_gate["errors"]))
    by_id = {o["race_id"]: o for o in outcomes}
    if {r["race_id"] for r in races} != set(by_id):
        raise ValueError("RACE_OUTCOME_PAIRING_NOT_EXACT")
    ordered = sorted(races, key=lambda r: (_time(r["prediction_at"]), r["race_id"]))
    days = sorted({r["target_date"] for r in ordered})
    first_test = cfg["train_days"] + cfg["selection_days"]
    if len(days) < first_test + cfg["test_days"]:
        raise ValueError("INSUFFICIENT_CHRONOLOGICAL_DAYS")
    folds, records = [], []
    candidate_records = {name: [] for name in cfg["candidates"]}
    for start in range(first_test, len(days) - cfg["test_days"] + 1, cfg["test_days"]):
        train_days = days[:start - cfg["selection_days"]]
        selection_days = days[start - cfg["selection_days"]:start]
        test_days = days[start:start + cfg["test_days"]]
        train = [r for r in ordered if r["target_date"] in train_days]
        selected = [r for r in ordered if r["target_date"] in selection_days]
        test = [r for r in ordered if r["target_date"] in test_days]
        train_cutoff = min(_time(r["prediction_at"]) for r in selected)
        test_cutoff = min(_time(r["prediction_at"]) for r in test)
        if any(_time(by_id[r["race_id"]]["available_at"]) >= train_cutoff for r in train):
            raise ValueError("TRAIN_LABEL_UNAVAILABLE_AT_SELECTION_CUTOFF")
        if any(_time(by_id[r["race_id"]]["available_at"]) >= test_cutoff for r in selected):
            raise ValueError("SELECTION_LABEL_UNAVAILABLE_AT_TEST_CUTOFF")
        best = None
        best_by_candidate = {}
        score_table = []
        for name in cfg["candidates"]:
            for alpha in cfg["alphas"]:
                model = make_model(name, {"epochs": cfg["epochs"], "alpha": alpha,
                                         "learning_rate": cfg["learning_rate"], "l2": cfg["l2"]})
                model.fit(train, [by_id[r["race_id"]] for r in train])
                cached = [(r, model.distributions(r)["P_model"], usable_market(r)["P_market"])
                          for r in selected]
                for temperature in cfg["temperatures"]:
                    for weight in cfg["market_weights"]:
                        losses = []
                        for race, dist, market in cached:
                            calibrated = temperature_scale(dist, temperature)
                            pooled = calibrated if market is None else loglinear_pool(calibrated, market, weight)
                            actual = "-".join(map(str, by_id[race["race_id"]]["result"]))
                            losses.append(-math.log(pooled[actual]))
                        score = math.fsum(losses) / len(losses)
                        params = {"candidate": name, "alpha": alpha, "temperature": temperature,
                                  "market_weight": weight, "selection_mean_log_loss": score}
                        score_table.append(params)
                        if best is None or score < best[0]:
                            best = (score, model, params)
                        if name not in best_by_candidate or score < best_by_candidate[name][0]:
                            best_by_candidate[name] = (score, model, params)
        _, model, params = best
        pipeline = {"temperature": params["temperature"], "market_weight": params["market_weight"],
                    "selection": cfg["selection"]}
        fold_records = []
        for race in test:
            pred = predict_race(race, model, pipeline)
            # Freeze/hash forecast before labels are attached; no result is used
            # by predictor, selectors, or parameter-selection code above.
            actual = by_id[race["race_id"]]
            pred["actual"] = actual
            pred["first_course"] = next(b["course"] for b in race["boats"] if b["boat"] == actual["result"][0])
            fold_records.append(pred)
        records.extend(fold_records)
        candidate_fold_reports = {}
        for name, (_, fixed_model, fixed_params) in best_by_candidate.items():
            fixed_records = []
            for race in test:
                pred = predict_race(race, fixed_model, {
                    "temperature": fixed_params["temperature"], "market_weight": fixed_params["market_weight"],
                    "selection": cfg["selection"]})
                pred["actual"] = by_id[race["race_id"]]
                pred["first_course"] = next(b["course"] for b in race["boats"] if b["boat"] == pred["actual"]["result"][0])
                fixed_records.append(pred)
            candidate_records[name].extend(fixed_records)
            candidate_fold_reports[name] = {"selected_on_past_selection_only": fixed_params,
                                            "evaluation": evaluate_records(fixed_records, cfg["evaluation"])}
        folds.append({"fold": len(folds) + 1, "train_days": train_days,
                      "selection_days": selection_days, "test_days": test_days,
                      "train_ids": [r["race_id"] for r in train],
                      "selection_ids": [r["race_id"] for r in selected],
                      "test_ids": [r["race_id"] for r in test],
                      "train_label_cutoff": train_cutoff.isoformat(),
                      "selection_label_cutoff": test_cutoff.isoformat(),
                      "selected": params, "selection_scores": score_table,
                      "model": model.to_dict(), "model_sha256": canonical_hash(model.to_dict()),
                      "forecast_hashes": [r["prediction_sha256"] for r in fold_records],
                      "candidate_comparisons": candidate_fold_reports,
                      "evaluation": evaluate_records(fold_records, cfg["evaluation"])})
    return {"classification": dataset.get("classification", "PRIVATE_INPUT_UNVERIFIED"),
            "status": "SYNTHETIC_SOFTWARE_OBSERVATION" if dataset.get("classification") == "SYNTHETIC_ONLY" else "RESEARCH_UNREVIEWED",
            "config_status": "PROPOSED", "config": cfg, "dataset_sha256": canonical_hash(dataset),
            "folds": folds, "records": records, "evaluation": evaluate_records(records, cfg["evaluation"]),
            "candidate_evaluations": {name: evaluate_records(rows, cfg["evaluation"])
                                      for name, rows in candidate_records.items()},
            "initial_days_not_evaluated": days[:first_test],
            "trailing_days_not_evaluated": days[first_test + len(folds) * cfg["test_days"]:],
            "future_untouched_real_evaluation": "OPEN", "legacy_comparison": "OPEN",
            "superiority": "UNVERIFIED", "production_go": False}
