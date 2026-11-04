"""Offline probability operations. No I/O, network, or outcome inputs."""
from __future__ import annotations

from datetime import datetime
from itertools import permutations
import math
import re


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label}: finite number required")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label}: finite number required") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label}: finite number required")
    return value


def _normalized_logits(logits):
    """Stable softmax with explicit floating-point floor (not zero mass)."""
    if not logits or any(not math.isfinite(v) for v in logits.values()):
        raise ValueError("finite nonempty logits required")
    largest = max(logits.values())
    masses = {k: math.exp(max(-700.0, v - largest)) for k, v in logits.items()}
    total = math.fsum(masses.values())
    return {k: value / total for k, value in masses.items()}


def _distribution(dist):
    if not isinstance(dist, dict) or not dist:
        raise ValueError("nonempty probability dictionary required")
    values = {key: _number(value, "probability") for key, value in dist.items()}
    if any(not isinstance(k, str) or not k for k in values):
        raise ValueError("string distribution keys required")
    if any(value <= 0.0 or value > 1.0 for value in values.values()):
        raise ValueError("strictly positive probabilities required")
    if not math.isclose(math.fsum(values.values()), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("distribution must sum to one")
    return values


def loglinear_pool(model, other, weight):
    """Return model^(1-w) * other^w, normalized; w is market weight."""
    weight = _number(weight, "weight")
    if not 0.0 <= weight <= 1.0:
        raise ValueError("weight must be in [0,1]")
    model, other = _distribution(model), _distribution(other)
    if model.keys() != other.keys():
        raise ValueError("distribution domains differ")
    return _normalized_logits({
        key: (1.0 - weight) * math.log(model[key]) + weight * math.log(other[key])
        for key in model
    })


def temperature_scale(dist, temperature):
    """Research calibration only: fit/select temperature outside held-out data."""
    temperature = _number(temperature, "temperature")
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    values = _distribution(dist)
    logs = {k: math.log(v) for k, v in values.items()}
    largest = max(logs.values())
    # Subtract before dividing, keeping a tiny positive mass at numerical limits.
    logits = {k: max(-700.0, (v - largest) / temperature) for k, v in logs.items()}
    return _normalized_logits(logits)


def _time(value):
    if not isinstance(value, str) or value.endswith("-00:00"):
        raise ValueError("aware timestamp required")
    if re.search(r"\.\d{7,}", value):
        raise ValueError("timestamp precision exceeds microseconds")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return parsed


def market_distribution(race, max_odds_age_seconds=120):
    """Normalize reciprocal complete pre-cutoff odds; never impute missing odds.

    The proportional-odds conversion is a research baseline, not a claim that
    pari-mutuel odds are fair probabilities. No results or later snapshots used.
    """
    age_limit = _number(max_odds_age_seconds, "max_odds_age_seconds")
    if age_limit < 0:
        raise ValueError("nonnegative max odds age required")

    def unavailable(status, reason):
        return {"status": status, "P_market": None, "reason": reason}

    if not isinstance(race, dict):
        return unavailable("INVALID", "RACE_SHAPE")
    snapshot = race.get("odds_snapshot")
    if snapshot is None:
        return unavailable("UNAVAILABLE", "ODDS_MISSING")
    try:
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot shape")
        for field in ("race_id", "target_date", "venue"):
            if field in snapshot and snapshot[field] != race.get(field):
                return unavailable("INVALID", "ODDS_IDENTITY_MISMATCH")
        active = race["active_boats"]
        if not isinstance(active, list) or not 3 <= len(active) <= 6:
            raise ValueError("active boats shape")
        if any(type(boat) is not int or not 1 <= boat <= 6 for boat in active):
            raise ValueError("active boats domain")
        if len(set(active)) != len(active):
            raise ValueError("duplicate boats")
        predicted, deadline = _time(race["prediction_at"]), _time(race["deadline"])
        acquired = _time(snapshot["acquired_at"])
        available = _time(snapshot["available_at"])
        revised = _time(snapshot["revision_at"])
        if predicted >= deadline:
            return unavailable("INVALID", "PREDICTION_NOT_BEFORE_DEADLINE")
        if acquired > predicted or available > predicted or revised > predicted:
            return unavailable("INVALID", "ODDS_FUTURE_OR_LATE_REVISION")
        if available < acquired:
            return unavailable("INVALID", "ODDS_AVAILABILITY_BEFORE_ACQUISITION")
        age = (predicted - acquired).total_seconds()
        if age > age_limit:
            return unavailable("UNAVAILABLE", "ODDS_STALE")
        odds = snapshot["odds"]
        expected = {"-".join(map(str, ticket)) for ticket in permutations(sorted(active), 3)}
        if not isinstance(odds, dict) or odds.keys() != expected:
            return unavailable("UNAVAILABLE", "ODDS_INCOMPLETE_OR_EXTRA_TICKETS")
        checked = {k: _number(v, "odds") for k, v in odds.items()}
        if any(v <= 0 for v in checked.values()):
            raise ValueError("nonpositive odds")
        market = _normalized_logits({k: -math.log(checked[k]) for k in sorted(checked)})
    except (KeyError, TypeError, ValueError, OverflowError):
        return unavailable("INVALID", "ODDS_SCHEMA_OR_VALUE")
    return {"status": "AVAILABLE", "P_market": market, "reason": None,
            "age_seconds": age, "method": "PROPORTIONAL_RECIPROCAL_ODDS_RESEARCH"}
