"""Reproducible, wholly invented data for exercising the research pipeline.

There are no real races, fitted production weights, or external data here.
The simulator is an intentionally learnable conditional ranking process, not
evidence that any research candidate predicts actual Gamagori results.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import math
import random


FEATURES = ("st", "turn", "motor", "ability", "exhibition")
CLASSIFICATION = "SYNTHETIC_ONLY"
GENERATOR_VERSION = "conditional-synthetic-v001"
_JST = timezone(timedelta(hours=9))
_WEIGHTS = (
    (0.95, 0.25, 0.60, 0.90, 0.45),
    (0.30, 1.00, 0.45, 0.65, 0.30),
    (0.15, 0.85, 0.35, 0.50, 0.25),
)
_COURSE_PRIOR = (
    (0.85, 0.25, 0.05, -0.15, -0.35, -0.55),
    (0.15, 0.30, 0.20, 0.00, -0.15, -0.25),
    (0.00, 0.10, 0.20, 0.15, 0.00, -0.15),
)


def _rng(seed: int, namespace: str) -> random.Random:
    digest = sha256(f"{GENERATOR_VERSION}:{namespace}:{seed}".encode("ascii")).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _softmax(scores: dict[int, float]) -> dict[int, float]:
    offset = max(scores.values())
    masses = {boat: math.exp(score - offset) for boat, score in scores.items()}
    total = math.fsum(masses.values())
    return {boat: mass / total for boat, mass in masses.items()}


def _conditionals(boats: list[dict], previous: tuple[int, ...]) -> dict[int, float]:
    """Latent stage probabilities; no actual result or odds enter this method."""
    stage = len(previous)
    by_boat = {boat["boat"]: boat for boat in boats}
    scores = {}
    for boat in boats:
        number = boat["boat"]
        if number in previous:
            continue
        features = boat["features"]
        score = math.fsum(w * features[name] for w, name in zip(_WEIGHTS[stage], FEATURES))
        score += _COURSE_PRIOR[stage][boat["course"] - 1]
        if previous:
            leader = by_boat[previous[0]]
            # Invented conditional interaction: the leader's course changes the
            # relative value of a follower's turn and motor scores.
            sign = 1.0 if leader["course"] <= 3 else -1.0
            score += 0.25 * sign * features["turn"]
            score += 0.15 * leader["features"]["st"] * features["motor"]
        if len(previous) == 2:
            second = by_boat[previous[1]]
            score += 0.20 * second["features"]["turn"] * features["ability"]
        scores[number] = score
    return _softmax(scores)


def _latent_distribution(boats: list[dict]) -> dict[str, float]:
    """Factorize all 120 outcomes before any outcome is sampled."""
    joint = {}
    first = _conditionals(boats, ())
    for i, p_first in first.items():
        for j, p_second in _conditionals(boats, (i,)).items():
            for k, p_third in _conditionals(boats, (i, j)).items():
                joint[f"{i}-{j}-{k}"] = p_first * p_second * p_third
    return joint


def _sample(probabilities: dict[int, float], rng: random.Random) -> int:
    draw = rng.random()
    cumulative = 0.0
    for boat, probability in probabilities.items():
        cumulative += probability
        if draw < cumulative:
            return boat
    return next(reversed(probabilities))  # Floating-point roundoff only.


def make_dataset(days: int = 36, races_per_day: int = 2, seed: int = 20261105) -> dict:
    """Return canonical synthetic races and separately held outcomes.

    Odds are positive gross payout multiples constructed from noisy latent
    probabilities *before* the independent outcome RNG samples each stage.
    Settlement uses those existing synthetic odds, not subsequently invented
    winning odds. Their economics and all coefficients are PROPOSED fixtures.
    The default covers 36 invented dates starting 2099-01-01.
    """
    if type(days) is not int or not 1 <= days <= 366:
        raise ValueError("days must be an integer from 1 to 366")
    if type(races_per_day) is not int or not 1 <= races_per_day <= 12:
        raise ValueError("races_per_day must be an integer from 1 to 12")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    covariates_rng = _rng(seed, "covariates")
    market_rng = _rng(seed, "market-before-result")
    outcome_rng = _rng(seed, "independent-outcomes")
    races, outcomes = [], []
    base_date = date(2099, 1, 1)
    for day_index in range(days):
        target = base_date + timedelta(days=day_index)
        for race_number in range(1, races_per_day + 1):
            deadline = datetime.combine(target, time(13, 0), _JST) + timedelta(minutes=30 * (race_number - 1))
            prediction = deadline - timedelta(minutes=5)
            identity = f"{target:%Y%m%d}_GAMAGORI_{race_number}R"
            courses = list(range(1, 7))
            covariates_rng.shuffle(courses)
            boats = []
            for number in range(1, 7):
                features = {name: round(covariates_rng.uniform(-1, 1), 8) for name in FEATURES}
                boats.append({
                    "boat": number,
                    "course": courses[number - 1],
                    "features": features,
                    "feature_times": {
                        name: {
                            "acquired_at": (prediction - timedelta(minutes=2)).isoformat(),
                            "available_at": (prediction - timedelta(seconds=90)).isoformat(),
                            "revision_at": (prediction - timedelta(minutes=1)).isoformat(),
                        }
                        for name in FEATURES
                    },
                    "state_times": {
                        name: {
                            "acquired_at": (prediction - timedelta(minutes=2)).isoformat(),
                            "available_at": (prediction - timedelta(seconds=90)).isoformat(),
                            "revision_at": (prediction - timedelta(minutes=1)).isoformat(),
                        }
                        for name in ("course", "fl", "scratched")
                    },
                    "observed_at": (prediction - timedelta(minutes=2)).isoformat(),
                    "motor_updated_at": (prediction - timedelta(days=1)).isoformat(),
                    "revision_at": (prediction - timedelta(minutes=1)).isoformat(),
                    "fl": False,
                    "scratched": False,
                })

            latent = _latent_distribution(boats)
            market_masses = {
                ticket: probability * math.exp(market_rng.uniform(-0.20, 0.20))
                for ticket, probability in latent.items()
            }
            total = math.fsum(market_masses.values())
            market = {ticket: mass / total for ticket, mass in market_masses.items()}
            # 0.78 is an invented payout factor, not an official takeout rate.
            odds = {ticket: round(0.78 / probability, 8) for ticket, probability in market.items()}
            ranked_turn = sorted(boats, key=lambda b: (-b["features"]["turn"], b["boat"]))
            core = [boat["boat"] for boat in ranked_turn[:2]]
            insertion = max(
                (boat for boat in boats if boat["boat"] not in core),
                key=lambda b: (b["features"]["ability"], -b["boat"]),
            )["boat"]
            race = {
                "race_id": identity,
                "target_date": target.isoformat(),
                "venue": "GAMAGORI",
                "synthetic": True,
                "data_classification": CLASSIFICATION,
                "prediction_at": prediction.isoformat(),
                "deadline": deadline.isoformat(),
                "active_boats": list(range(1, 7)),
                "boats": boats,
                "odds_snapshot": {
                    "acquired_at": (prediction - timedelta(seconds=30)).isoformat(),
                    "available_at": (prediction - timedelta(seconds=29)).isoformat(),
                    "revision_at": (prediction - timedelta(seconds=30)).isoformat(),
                    "odds": odds,
                },
                "human_box_input": {
                    "core": core,
                    "insertion": insertion,
                    "observed_at": (prediction - timedelta(minutes=1)).isoformat(),
                    "acquired_at": (prediction - timedelta(minutes=1)).isoformat(),
                    "available_at": (prediction - timedelta(seconds=59)).isoformat(),
                    "revision_at": (prediction - timedelta(minutes=1)).isoformat(),
                },
            }
            races.append(race)

            # This happens only after the full predictor record is constructed.
            result = []
            for _ in range(3):
                result.append(_sample(_conditionals(boats, tuple(result)), outcome_rng))
            winning_ticket = "-".join(map(str, result))
            outcomes.append({
                "race_id": identity,
                "target_date": target.isoformat(),
                "synthetic": True,
                "data_classification": CLASSIFICATION,
                "result": result,
                "payout_per_100": round(100 * odds[winning_ticket], 2),
                "refund_tickets": [],
                "final": True,
                "available_at": (deadline + timedelta(minutes=10)).isoformat(),
            })

    return {
        "classification": CLASSIFICATION,
        "races": races,
        "outcomes": outcomes,
        "config": {
            "generator_version": GENERATOR_VERSION,
            "parameter_status": "PROPOSED_SYNTHETIC_FIXTURE",
            "seed": seed,
            "days": days,
            "races_per_day": races_per_day,
            "start_date": base_date.isoformat(),
            "feature_direction": "HIGHER_IS_BETTER",
            "outcome_process": "conditional_three_stage_categorical",
            "market_process": "noisy_latent_before_outcome",
            "synthetic_payout_factor": 0.78,
            "human_input_process": "synthetic_turn_core_ability_insertion_not_legacy",
            "real_data_used": False,
            "real_performance_claim": False,
        },
    }
