"""PROPOSED offline preregistration support; never issues a production GO.

Day-cluster units, self-reported seals and normal-approximation planning are
kept distinct from authenticated evidence or confirmatory performance claims.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import permutations
import math
from statistics import NormalDist, stdev


PRIMARY = "EQUAL_DAY_JOINT_120_LOGLOSS_DELTA_MARKET_MINUS_SHRUNK"
_DOMAIN = {"-".join(map(str, p)) for p in permutations(range(1, 7), 3)}
_DIGEST_FIELDS = (
    "candidate_sha256", "parameters_sha256", "input_schema_sha256",
    "split_plan_sha256", "sealed_holdout_ids_sha256", "seal_receipt_sha256",
    "approval_raw_sha256", "hypothesis_family_sha256",
    "pilot_variance_receipt_sha256", "serial_dependence_review_sha256",
)
_TIME_FIELDS = ("training_cutoff", "selection_cutoff", "holdout_start", "holdout_end")


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _timestamp(value):
    if not isinstance(value, str) or value.endswith("-00:00"):
        raise ValueError("AWARE_TIME_REQUIRED")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    return result


def paired_cluster_sample_size(sd_day, effect, power=0.8, alpha=0.025, comparisons=1):
    """One-sided paired normal approximation in DAYS, never race count.

    n = ceil(((z_(1-alpha/m) + z_power) * sd_day / effect)**2).
    For a fixed Holm family, alpha/m is a conservative planning allocation;
    this function does not perform Holm tests. Independence and pilot variance
    adequacy need external review. Unknown/zero variance never means zero days.
    """
    base = {"status": "STOP", "required_days": None, "reason": None,
            "unit": "PAIRED_DAY_CLUSTERS_NOT_RACES", "sidedness": "ONE_SIDED",
            "method": "PROPOSED_NORMAL_APPROXIMATION_NOT_CONFIRMATORY_PROOF",
            "formula": "ceil(((z(1-alpha/comparisons)+z(power))*sd_day/effect)^2)",
            "serial_dependence": "UNVERIFIED_INDEPENDENT_DAY_ASSUMPTION",
            "production_go": False}
    if (not _number(effect) or effect <= 0 or not _number(power) or not 0.5 < power < 1
            or not _number(alpha) or not 0 < alpha < 0.5
            or type(comparisons) is not int or comparisons < 1):
        return dict(base, reason="INVALID_PLANNING_CONTROL")
    if sd_day is None or (_number(sd_day) and sd_day == 0):
        return dict(base, status="UNVERIFIED", reason="DAY_VARIANCE_UNKNOWN_OR_ZERO")
    if not _number(sd_day) or sd_day < 0:
        return dict(base, reason="INVALID_DAY_STANDARD_DEVIATION")
    try:
        adjusted_alpha = alpha / comparisons
        z_alpha = NormalDist().inv_cdf(1 - adjusted_alpha)
        z_power = NormalDist().inv_cdf(power)
        unrounded = ((z_alpha + z_power) * sd_day / effect) ** 2
        if not math.isfinite(unrounded):
            raise ValueError("NONFINITE_ESTIMATE")
        required = max(2, math.ceil(unrounded))
    except (ValueError, OverflowError, ZeroDivisionError):
        return dict(base, reason="NUMERICAL_PLANNING_LIMIT")
    return dict(base, status="PROPOSED_ESTIMATE", reason=None, required_days=required,
                unrounded_days=unrounded, sd_day=float(sd_day), effect=float(effect),
                power=float(power), alpha=float(alpha), comparisons=comparisons,
                planning_alpha=adjusted_alpha,
                multiplicity="BONFERRONI_PLANNING_BOUND_FOR_FIXED_FAMILY",
                variance_authenticity="UNVERIFIED_INPUT_NOT_PRIVATE_PILOT_EVIDENCE")


def _probability_at(dist, ticket):
    if not isinstance(dist, dict) or set(dist) != _DOMAIN:
        raise ValueError("PRIMARY_REQUIRES_120_SIX_BOAT_TICKETS")
    if any(not _number(value) or not 0 <= value <= 1 for value in dist.values()):
        raise ValueError("INVALID_PROBABILITY_VALUE")
    if not math.isclose(math.fsum(dist.values()), 1.0, abs_tol=1e-10, rel_tol=0):
        raise ValueError("INVALID_PROBABILITY_MASS")
    return dist[ticket]


def equal_day_logloss_estimand(records):
    """Descriptive equal-day paired logloss on existing offline records.

    Positive delta favors P_shrunk: mean_day(mean_race(log p_shrunk - log
    p_market)). Days have equal weight, unlike the old race-weighted metrics.
    Missing markets and infinite losses are counted, never epsilon-repaired.
    This function cannot attest eligibility, a seal, or an untouched holdout.
    """
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError("RECORDS_MUST_BE_LIST_OF_OBJECTS")
    identities = [record.get("race_id") for record in records]
    counts = Counter(identity for identity in identities if isinstance(identity, str))
    by_day = defaultdict(list)
    issues = []
    skipped = nonfinite = 0
    hashes = set()
    for index, record in enumerate(records):
        try:
            race_id, day = record.get("race_id"), record.get("target_date")
            if not isinstance(race_id, str) or not race_id or counts[race_id] != 1:
                raise ValueError("DUPLICATE_OR_MISSING_RACE_ID")
            if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
                raise ValueError("INVALID_TARGET_DATE")
            actual = record.get("actual")
            if not isinstance(actual, dict) or actual.get("final") is not True:
                raise ValueError("MATCHED_FINAL_OUTCOME_REQUIRED")
            if actual.get("race_id") != race_id or actual.get("target_date") != day:
                raise ValueError("OUTCOME_IDENTITY_MISMATCH")
            order = actual.get("result")
            if (not isinstance(order, list) or len(order) != 3 or len(set(order)) != 3
                    or any(type(b) is not int or not 1 <= b <= 6 for b in order)):
                raise ValueError("INVALID_RESULT_TRIPLE")
            if not _timestamp(record["prediction_at"]) < _timestamp(record["deadline"]):
                raise ValueError("PREDICTION_NOT_BEFORE_DEADLINE")
            if _timestamp(actual["available_at"]) < _timestamp(record["deadline"]):
                raise ValueError("OUTCOME_AVAILABLE_BEFORE_DEADLINE")
            distributions = record.get("distributions")
            if not isinstance(distributions, dict):
                raise ValueError("DISTRIBUTIONS_REQUIRED")
            if distributions.get("P_market") is None or distributions.get("P_shrunk") is None:
                skipped += 1
                raise ValueError("PAIR_UNAVAILABLE_MARKET_OR_SHRUNK")
            ticket = "-".join(map(str, order))
            candidate = _probability_at(distributions["P_shrunk"], ticket)
            market = _probability_at(distributions["P_market"], ticket)
            if candidate == 0 or market == 0:
                nonfinite += 1
                raise ValueError("INFINITE_LOGLOSS_OR_UNDEFINED_PAIRED_DELTA")
            delta = math.log(candidate) - math.log(market)
            by_day[day].append(delta)
            digest = record.get("model_sha256")
            if isinstance(digest, str):
                hashes.add(digest)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            reason = exc.args[0] if isinstance(exc, ValueError) and exc.args else "INVALID_RECORD"
            # Never echo submitted values, source paths, URLs or exception text.
            allowed = {"DUPLICATE_OR_MISSING_RACE_ID", "INVALID_TARGET_DATE",
                       "MATCHED_FINAL_OUTCOME_REQUIRED", "OUTCOME_IDENTITY_MISMATCH",
                       "INVALID_RESULT_TRIPLE", "PREDICTION_NOT_BEFORE_DEADLINE",
                       "OUTCOME_AVAILABLE_BEFORE_DEADLINE", "DISTRIBUTIONS_REQUIRED",
                       "PAIR_UNAVAILABLE_MARKET_OR_SHRUNK", "PRIMARY_REQUIRES_120_SIX_BOAT_TICKETS",
                       "INVALID_PROBABILITY_VALUE", "INVALID_PROBABILITY_MASS",
                       "INFINITE_LOGLOSS_OR_UNDEFINED_PAIRED_DELTA", "AWARE_TIME_REQUIRED"}
            issues.append({"record_index": index, "reason": reason if reason in allowed else "INVALID_RECORD"})
    days = [{"target_date": day, "paired_races": len(values),
             "mean_logloss_delta": math.fsum(values) / len(values)}
            for day, values in sorted(by_day.items())]
    finite_pairs = sum(day["paired_races"] for day in days)
    deltas = [day["mean_logloss_delta"] for day in days]
    equal_mean = math.fsum(deltas) / len(deltas) if deltas else None
    race_mean = math.fsum(v for values in by_day.values() for v in values) / finite_pairs if finite_pairs else None
    complete = finite_pairs == len(records) and bool(records)
    return {"status": "DESCRIPTIVE_ONLY" if complete else "UNVERIFIED_INCOMPLETE_OR_NONFINITE_PAIRING",
            "primary_definition": PRIMARY, "positive_delta": "LOWER_CANDIDATE_LOGLOSS",
            "input_races": len(records), "finite_paired_races": finite_pairs,
            "unavailable_pair_races": skipped, "nonfinite_pair_races": nonfinite,
            "invalid_or_unpaired_races": len(records) - finite_pairs,
            "finite_day_clusters": len(days), "days": days,
            "equal_day_mean_delta": equal_mean if nonfinite == 0 else None,
            "finite_observed_equal_day_mean_delta": equal_mean,
            "race_weighted_mean_delta_comparison_only": race_mean,
            "estimand_scope": "COMPLETE_SUPPLIED_PAIR_SCOPE" if complete else "FINITE_OBSERVED_SUBSET_ONLY",
            "sample_sd_day_exploratory": stdev(deltas) if len(deltas) >= 2 else None,
            "model_hash_count": len(hashes),
            "frozen_candidate_evidence": "UNVERIFIED_MULTIPLE_MODELS" if len(hashes) > 1 else "UNVERIFIED_NOT_AUTHENTICATED",
            "issues": issues, "confirmatory_test": "NOT_PERFORMED",
            "real_performance": "UNVERIFIED", "production_go": False}


def protocol_readiness(inputs):
    """Check locally supplied review fields; never authenticates or grants GO."""
    if not isinstance(inputs, dict):
        raise ValueError("PROTOCOL_INPUTS_MUST_BE_OBJECT")
    missing, invalid = [], []
    for field in _DIGEST_FIELDS:
        value = inputs.get(field)
        if value is None:
            missing.append(field)
        elif (not isinstance(value, str) or len(value) != 64
              or any(char not in "0123456789abcdef" for char in value)):
            invalid.append(field)
    times = []
    for field in _TIME_FIELDS:
        if inputs.get(field) is None:
            missing.append(field)
        else:
            try:
                times.append(_timestamp(inputs[field]))
            except (TypeError, ValueError, OverflowError):
                invalid.append(field)
    if len(times) == 4 and not all(a < b for a, b in zip(times, times[1:])):
        invalid.append("data_cutoff_order")
    for field in ("protocol_id", "review_authority"):
        if not isinstance(inputs.get(field), str) or not inputs[field].strip():
            missing.append(field)
    if inputs.get("primary_metric") != PRIMARY:
        invalid.append("primary_metric")
    if inputs.get("comparator") != "P_market":
        invalid.append("comparator")
    comparisons = inputs.get("comparisons")
    multiplicity = inputs.get("multiplicity")
    if (not isinstance(multiplicity, str)
            or (multiplicity == "SINGLE_FROZEN_CHAMPION" and comparisons != 1)
            or multiplicity not in {"SINGLE_FROZEN_CHAMPION", "HOLM_FIXED_FAMILY"}):
        invalid.append("multiplicity")
    planning_fields = ("sd_day", "effect", "power", "alpha", "comparisons")
    for field in planning_fields:
        if inputs.get(field) is None:
            missing.append(field)
    plan = paired_cluster_sample_size(*(inputs.get(k) for k in planning_fields))
    planned = inputs.get("planned_holdout_days")
    if planned is None:
        missing.append("planned_holdout_days")
    elif type(planned) is not int or planned < 1:
        invalid.append("planned_holdout_days")
    elif plan["required_days"] is not None and planned < plan["required_days"]:
        invalid.append("INSUFFICIENT_PLANNED_DAY_CLUSTERS")
    reasons = []
    if missing:
        reasons.append("MISSING_REVIEW_INPUTS")
    if invalid:
        reasons.append("INVALID_OR_INCONSISTENT_REVIEW_INPUTS")
    if plan["status"] != "PROPOSED_ESTIMATE":
        reasons.append("SAMPLE_SIZE_UNVERIFIED_OR_STOP")
    ready = not reasons
    return {"status": "READY_FOR_REVIEW" if ready else "HOLD",
            "missing_fields": sorted(set(missing)), "invalid_fields": sorted(set(invalid)),
            "reason_codes": reasons, "sample_size_plan": plan,
            "evidence_authenticity": "UNVERIFIED_SELF_REPORTED_FIELDS_ONLY",
            "review_outcome": "NOT_GRANTED", "production_go": False,
            "real_data_access_go": False, "model_promotion_go": False}
