"""Deterministic, learnable conditional-rank research candidates (stdlib only).

Separate stage parameters model P(first), P(second|first), P(third|first,second).
No odds/results are predictor features. Weights and defaults are PROPOSED;
synthetic correctness tests do not establish real-race predictive performance.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

from .probabilities import _number, _normalized_logits, _time

FEATURES = ("st", "turn", "motor", "ability", "exhibition")
VERSION = "model11-research-0.1"
DEFAULTS = {"epochs": 100, "learning_rate": 0.3, "l2": 0.01,
            "alpha": 0.0, "prior_strength": 2.0}
_FORBIDDEN = {"result", "results", "payout", "payout_per_100", "outcome", "actual",
              "refund_tickets"}


def _reject_outcomes(value):
    if isinstance(value, dict):
        if any(str(key).lower() in _FORBIDDEN for key in value):
            raise ValueError("outcome fields forbidden in predictor input")
        for child in value.values():
            _reject_outcomes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_outcomes(child)


def _race_view(race):
    if not isinstance(race, dict):
        raise ValueError("race dictionary required")
    _reject_outcomes(race)
    if not isinstance(race.get("race_id"), str) or not race["race_id"]:
        raise ValueError("nonempty race_id required")
    active = race.get("active_boats")
    if not isinstance(active, list) or not 3 <= len(active) <= 6:
        raise ValueError("3..6 active boats required")
    if any(type(b) is not int or not 1 <= b <= 6 for b in active):
        raise ValueError("boats must be ints 1..6")
    if len(set(active)) != len(active):
        raise ValueError("duplicate active boats")
    boats = race.get("boats")
    if not isinstance(boats, list):
        raise ValueError("boats list required")
    indexed = {}
    for item in boats:
        if not isinstance(item, dict) or type(item.get("boat")) is not int:
            raise ValueError("boat entry shape")
        boat = item["boat"]
        if not 1 <= boat <= 6 or boat in indexed:
            raise ValueError("duplicate/out-of-domain boat entry")
        indexed[boat] = item
    view = {}
    for boat in sorted(active):
        item = indexed.get(boat)
        if item is None or item.get("scratched") is not False:
            raise ValueError("active boat missing or scratch status unverified")
        course = item.get("course")
        if type(course) is not int or not 1 <= course <= 6:
            raise ValueError("course must be int 1..6")
        features = item.get("features")
        if not isinstance(features, dict) or set(features) != set(FEATURES):
            raise ValueError("exact named normalized features required")
        vector = tuple(_number(features[f], f) for f in FEATURES)
        if any(not -1 <= f <= 1 for f in vector):
            raise ValueError("features outside normalized [-1,1] domain")
        view[boat] = {"features": vector, "course": course}
    if len({item["course"] for item in view.values()}) != len(view):
        raise ValueError("duplicate active courses")
    return view


def _max_timestamp(records, key):
    """Unknown provenance stays unknown; never invent a training cutoff."""
    try:
        stamps = [_time(record[key]) for record in records]
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return max(stamps).isoformat() if stamps else None


class ConditionalRankModel:
    """Batch-gradient conditional likelihood model with train-only course prior.

    Course prior is a smoothed stage/course frequency, conditionalized over the
    remaining boats, added as alpha*log(prior) to logits. Alpha is a proposed
    selection parameter, not a learned claim of venue-specific advantage.
    Contextual variant adds feature cross-products with selected first/second
    boats, enabling interaction-specific rankings rather than one shared score.
    """
    def __init__(self, name, config=None):
        if name not in {"hierarchical", "contextual"}:
            raise ValueError("unknown candidate model")
        supplied = {} if config is None else config
        if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
            raise ValueError("unknown model config")
        self.config = {**DEFAULTS, **supplied}
        epochs = self.config["epochs"]
        if type(epochs) is not int or not 1 <= epochs <= 2000:
            raise ValueError("epochs must be int 1..2000")
        for key in ("learning_rate", "l2", "alpha", "prior_strength"):
            self.config[key] = _number(self.config[key], key)
        if not 0 < self.config["learning_rate"] <= 10:
            raise ValueError("learning_rate outside (0,10]")
        if not 0 <= self.config["l2"] <= 10 or not 0 <= self.config["alpha"] <= 1:
            raise ValueError("l2 or alpha outside proposed config domain")
        if not 0 < self.config["prior_strength"] <= 1e6:
            raise ValueError("prior_strength outside (0,1e6]")
        self.name = name
        self.feature_names = list(FEATURES)
        if name == "contextual":
            self.feature_names += [f"{a}*first.{b}" for a in FEATURES for b in FEATURES]
            self.feature_names += [f"{a}*second.{b}" for a in FEATURES for b in FEATURES]
        self.weights = [[0.0] * len(self.feature_names) for _ in range(3)]
        self.course_counts = [[0] * 6 for _ in range(3)]
        self.training_count = 0
        self.training_ids_sha256 = None
        self.training_max_available_at = None
        self.training_max_prediction_at = None
        self.fit_status = "UNFITTED_RESEARCH"

    def _vector(self, view, boat, first=None, second=None):
        features = view[boat]["features"]
        if self.name == "hierarchical":
            return features
        first_f = view[first]["features"] if first is not None else (0.0,) * 5
        second_f = view[second]["features"] if second is not None else (0.0,) * 5
        return features + tuple(a*b for a in features for b in first_f) + tuple(
            a*b for a in features for b in second_f)

    def _conditional(self, view, first=None, second=None, stage="raw"):
        if stage not in {"raw", "model"}:
            raise ValueError("stage must be raw or model")
        if second is not None and first is None:
            raise ValueError("second requires first")
        for selected in (first, second):
            if selected is not None and (type(selected) is not int or selected not in view):
                raise ValueError("conditioned boat absent")
        if first is not None and first == second:
            raise ValueError("duplicate conditioning boat")
        head = int(first is not None) + int(second is not None)
        candidates = [b for b in view if b != first and b != second]
        logits = {}
        for boat in candidates:
            vector = self._vector(view, boat, first, second)
            score = math.fsum(w*x for w, x in zip(self.weights[head], vector))
            if stage == "model" and self.config["alpha"]:
                count = self.course_counts[head][view[boat]["course"] - 1]
                score += self.config["alpha"] * math.log(count + self.config["prior_strength"])
            logits[boat] = score
        return _normalized_logits(logits)

    def conditionals(self, race, first=None, second=None, stage="raw"):
        return self._conditional(_race_view(race), first, second, stage)

    def distributions(self, race):
        view = _race_view(race)
        result = {}
        for stage, key in (("raw", "P_raw"), ("model", "P_model")):
            joint = {}
            for first, p1 in self._conditional(view, stage=stage).items():
                for second, p2 in self._conditional(view, first, stage=stage).items():
                    for third, p3 in self._conditional(view, first, second, stage).items():
                        # Log product avoids multiplication underflow with extreme weights.
                        joint[f"{first}-{second}-{third}"] = (
                            math.log(p1) + math.log(p2) + math.log(p3))
            result[key] = _normalized_logits(joint)
        return result

    def fit(self, races, outcomes):
        """Deterministic full-batch optimization, reset on every call.

        Caller must enforce train cutoff/availability before invoking fit; no
        feature engineering from result, payout, or odds occurs here.
        """
        if not isinstance(races, list) or not isinstance(outcomes, list) or not races:
            raise ValueError("nonempty training races/outcomes lists required")
        by_id = {}
        for outcome in outcomes:
            if not isinstance(outcome, dict) or not isinstance(outcome.get("race_id"), str):
                raise ValueError("outcome identity missing")
            if outcome["race_id"] in by_id:
                raise ValueError("duplicate training outcomes")
            by_id[outcome["race_id"]] = outcome
        examples, seen = [], set()
        for race in races:
            view = _race_view(race)
            race_id = race["race_id"]
            if race_id in seen:
                raise ValueError("duplicate training races")
            seen.add(race_id)
            outcome = by_id.get(race_id)
            if outcome is None or outcome.get("final") is not True:
                raise ValueError("matching final outcome required")
            if race.get("target_date") != outcome.get("target_date") or not race.get("target_date"):
                raise ValueError("race/outcome date mismatch")
            order = outcome.get("result")
            if (not isinstance(order, list) or len(order) != 3 or
                    any(type(b) is not int or b not in view for b in order) or len(set(order)) != 3):
                raise ValueError("valid distinct active result triple required")
            examples.append((race_id, view, tuple(order)))
        if set(by_id) != seen:
            raise ValueError("training race/outcome identities differ")
        examples.sort(key=lambda example: example[0])
        weights = [[0.0] * len(self.feature_names) for _ in range(3)]
        # Only commit fitted state after all validation and optimization succeeds.
        for _ in range(self.config["epochs"]):
            gradients = [[0.0] * len(self.feature_names) for _ in range(3)]
            for _, view, order in examples:
                for head in range(3):
                    first = order[0] if head >= 1 else None
                    second = order[1] if head >= 2 else None
                    candidates = [b for b in view if b not in order[:head]]
                    vectors = {b: self._vector(view, b, first, second) for b in candidates}
                    logits = {b: math.fsum(w*x for w, x in zip(weights[head], vectors[b])) for b in candidates}
                    probs = _normalized_logits(logits)
                    for boat in candidates:
                        residual = float(boat == order[head]) - probs[boat]
                        for index, feature in enumerate(vectors[boat]):
                            gradients[head][index] += residual * feature
            for head in range(3):
                for index in range(len(self.feature_names)):
                    update = gradients[head][index] / len(examples) - self.config["l2"] * weights[head][index]
                    weights[head][index] += self.config["learning_rate"] * update
                    if not math.isfinite(weights[head][index]):
                        raise ValueError("nonfinite fit: STOP, no parameter substitution")
        counts = [[0] * 6 for _ in range(3)]
        for _, view, order in examples:
            for head, boat in enumerate(order):
                counts[head][view[boat]["course"] - 1] += 1
        ids = [example[0] for example in examples]
        self.weights, self.course_counts = weights, counts
        self.training_count = len(examples)
        self.training_ids_sha256 = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        self.training_max_available_at = _max_timestamp(outcomes, "available_at")
        self.training_max_prediction_at = _max_timestamp(races, "prediction_at")
        self.fit_status = "FITTED_RESEARCH_NOT_REAL_DATA_VALIDATED"
        return self

    def explain(self, race, first=None, second=None, stage="model"):
        view = _race_view(race)
        probabilities = self._conditional(view, first, second, stage)
        head = int(first is not None) + int(second is not None)
        explanations = {}
        for boat in probabilities:
            vector = self._vector(view, boat, first, second)
            contributions = {name: w*x for name, w, x in zip(self.feature_names, self.weights[head], vector)}
            prior = 0.0
            if stage == "model" and self.config["alpha"]:
                prior = self.config["alpha"] * math.log(
                    self.course_counts[head][view[boat]["course"] - 1] + self.config["prior_strength"])
            explanations[boat] = {"head": head + 1, "contributions": contributions,
                                  "course_prior_logit": prior, "probability": probabilities[boat]}
        return explanations

    def to_dict(self):
        return {"version": VERSION, "candidate_id": self.name, "config_status": "PROPOSED",
                "config": deepcopy(self.config), "feature_names": list(self.feature_names),
                "weights": deepcopy(self.weights), "course_counts": deepcopy(self.course_counts),
                "training_count": self.training_count, "training_ids_sha256": self.training_ids_sha256,
                "training_max_available_at": self.training_max_available_at,
                "training_max_prediction_at": self.training_max_prediction_at,
                "training_time_provenance": "UNVERIFIED_SELF_REPORTED_INPUT",
                "fit_status": self.fit_status, "performance_improvement": "UNVERIFIED"}


def make_model(name, config=None):
    return ConditionalRankModel(name, config)


def from_dict(payload):
    """Load only same-version finite, shape-checked research parameters."""
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        raise ValueError("unknown model serialization version")
    model = make_model(payload.get("candidate_id"), payload.get("config"))
    if payload.get("feature_names") != model.feature_names:
        raise ValueError("serialized feature names differ")
    weights, counts = payload.get("weights"), payload.get("course_counts")
    if (not isinstance(weights, list) or len(weights) != 3 or
            any(not isinstance(row, list) or len(row) != len(model.feature_names) for row in weights)):
        raise ValueError("serialized weight shape")
    model.weights = [[_number(w, "weight") for w in row] for row in weights]
    if any(abs(w) > 1e6 for row in model.weights for w in row):
        raise ValueError("weights beyond numerical safety domain")
    if (not isinstance(counts, list) or len(counts) != 3 or
            any(not isinstance(row, list) or len(row) != 6 for row in counts) or
            any(type(n) is not int or not 0 <= n <= 10**12 for row in counts for n in row)):
        raise ValueError("serialized course counts")
    count = payload.get("training_count")
    if type(count) is not int or not 0 <= count <= 10**12 or any(sum(row) != count for row in counts):
        raise ValueError("serialized training count inconsistent")
    digest = payload.get("training_ids_sha256")
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or
                               any(c not in "0123456789abcdef" for c in digest)):
        raise ValueError("serialized training digest")
    model.course_counts, model.training_count = deepcopy(counts), count
    model.training_ids_sha256 = digest
    for key in ("training_max_available_at", "training_max_prediction_at"):
        value = payload.get(key)
        if value is not None:
            try:
                _time(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("serialized training timestamp invalid") from exc
        if count == 0 and value is not None:
            raise ValueError("unfitted training timestamp present")
        setattr(model, key, value)
    expected = "UNFITTED_RESEARCH" if count == 0 else "FITTED_RESEARCH_NOT_REAL_DATA_VALIDATED"
    if payload.get("fit_status") != expected:
        raise ValueError("serialized fit status inconsistent")
    model.fit_status = expected
    return model
