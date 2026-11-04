"""Offline research evaluation. No I/O, production integration, or promotion rule.

Money is evaluated per method, never pooled across overlapping selections.
Unknown observations are counted explicitly rather than replaced with zero.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import itertools
import math
import random


METHODS = ("five", "human_research", "mechanical_research", "box_v11_research")
STAGES = ("P_raw", "P_model", "P_market", "P_shrunk")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ticket(value):
    if not isinstance(value, str):
        raise ValueError("TICKET_NOT_STRING")
    pieces = value.split("-")
    if len(pieces) != 3 or any(p not in "123456" or len(p) != 1 for p in pieces):
        raise ValueError("TICKET_FORMAT")
    boats = tuple(map(int, pieces))
    if len(set(boats)) != 3:
        raise ValueError("TICKET_REPEATS_BOAT")
    return boats


def _distribution(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("DISTRIBUTION_MISSING")
    domain = {_ticket(key) for key in value}
    boats = set(itertools.chain.from_iterable(domain))
    expected = set(itertools.permutations(sorted(boats), 3))
    if len(boats) < 3 or domain != expected:
        raise ValueError("DISTRIBUTION_INCOMPLETE_DOMAIN")
    if any(not _number(p) or not 0 <= p <= 1 for p in value.values()):
        raise ValueError("DISTRIBUTION_INVALID_PROBABILITY")
    if not math.isclose(math.fsum(value.values()), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("DISTRIBUTION_NOT_NORMALIZED")
    return {key: float(p) for key, p in value.items()}, boats


def _time(value):
    if not isinstance(value, str):
        raise ValueError("TIME_MISSING")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("TIME_NOT_AWARE")
    return stamp


def _bound_outcome(record):
    actual = record.get("actual")
    if not isinstance(actual, dict):
        raise ValueError("OUTCOME_MISSING")
    for field in ("race_id", "target_date"):
        if not isinstance(record.get(field), str) or actual.get(field) != record[field]:
            raise ValueError("OUTCOME_" + field.upper() + "_MISMATCH")
    if "source" in actual and actual["source"] != record.get("source"):
        raise ValueError("OUTCOME_SOURCE_MISMATCH")
    if actual.get("final") is not True:
        raise ValueError("OUTCOME_NOT_FINAL")
    result = actual.get("result")
    if (not isinstance(result, (list, tuple)) or len(result) != 3
            or any(type(n) is not int or not 1 <= n <= 6 for n in result)
            or len(set(result)) != 3):
        raise ValueError("OUTCOME_RESULT_INVALID")
    return actual, "-".join(map(str, result))


def _loss(probability):
    return math.inf if probability == 0 else -math.log(probability)


def _mean_loss(values, total):
    infinite = sum(math.isinf(value) for value in values)
    return {
        "value": None if not values or infinite else math.fsum(values) / len(values),
        "status": "INFINITE" if infinite else ("FINITE" if values else "UNVERIFIED"),
        "observed": len(values), "infinite_count": infinite,
        "missing": total - len(values),
        "coverage": len(values) / total if total else None,
        "scope": "OBSERVED_ONLY" if len(values) != total else "COMPLETE_INPUT_SCOPE",
    }


def _mean(values, total):
    return {"value": math.fsum(values) / len(values) if values else None,
            "observed": len(values), "missing": total - len(values),
            "scope": "OBSERVED_ONLY" if len(values) != total else "COMPLETE_INPUT_SCOPE"}


def _score(dist, result):
    if result not in dist:
        raise ValueError("OUTCOME_OUTSIDE_DISTRIBUTION_DOMAIN")
    first, second, _ = _ticket(result)
    p1 = math.fsum(p for key, p in dist.items() if _ticket(key)[0] == first)
    p12 = math.fsum(p for key, p in dist.items() if _ticket(key)[:2] == (first, second))
    # Undefined conditionals remain unknown; the zero conditioning mass already
    # contributes infinite loss at its first zero-probability stage.
    p2 = p12 / p1 if p1 > 0 else None
    p3 = dist[result] / p12 if p12 > 0 else None
    top = min(dist, key=lambda key: (-dist[key], key))
    return {"joint_logloss": _loss(dist[result]),
            "joint_brier": math.fsum((p - (key == result)) ** 2 for key, p in dist.items()),
            "conditional_first_logloss": _loss(p1),
            "conditional_second_logloss": _loss(p2) if p2 is not None else None,
            "conditional_third_logloss": _loss(p3) if p3 is not None else None,
            "p_first": p1, "p_second_given_first": p2,
            "p_third_given_first_second": p3,
            "top_confidence": dist[top], "top_correct": int(top == result)}


def _calibration(rows, bins):
    result = []
    error = 0.0
    for index in range(bins):
        bucket = [row for row in rows if min(int(row["top_confidence"] * bins), bins - 1) == index]
        confidence = math.fsum(r["top_confidence"] for r in bucket) / len(bucket) if bucket else None
        accuracy = math.fsum(r["top_correct"] for r in bucket) / len(bucket) if bucket else None
        if bucket:
            error += len(bucket) * abs(confidence - accuracy)
        result.append({"lower": index / bins, "upper": (index + 1) / bins,
                       "n": len(bucket), "mean_confidence": confidence, "accuracy": accuracy})
    return {"definition": "TOP_LABEL_EQUAL_WIDTH", "bins": result,
            "ece": error / len(rows) if rows else None,
            "status": "DESCRIPTIVE_PROPOSED", "n": len(rows)}


def _distribution_report(rows, total, bins):
    report = {"n": len(rows), "input_n": total,
              "joint_logloss": _mean_loss([r["joint_logloss"] for r in rows], total),
              "joint_brier": _mean([r["joint_brier"] for r in rows], total),
              "calibration": _calibration(rows, bins)}
    for name in ("first", "second", "third"):
        field = "conditional_" + name + "_logloss"
        report[field] = _mean_loss([r[field] for r in rows if r[field] is not None], total)
    report["conditional_definition"] = "ACTUAL_PREFIX_CONDITIONALS_DERIVED_FROM_JOINT"
    return report


def _method_input(record, name):
    return record.get("selection") if name == "five" else record.get("boxes", {}).get(name)


def _method_observation(record, actual, result, name):
    method = _method_input(record, name)
    if not isinstance(method, dict):
        raise ValueError("METHOD_MISSING")
    tickets = method.get("tickets")
    count = 5 if name == "five" else 6
    if not isinstance(tickets, list) or len(tickets) != count or len(set(tickets)) != count:
        raise ValueError("METHOD_TICKET_COUNT")
    triples = [_ticket(t) for t in tickets]
    if name != "five":
        boats = method.get("boats")
        if (not isinstance(boats, list) or len(boats) != 3
                or any(type(b) is not int for b in boats) or len(set(boats)) != 3
                or set(triples) != set(itertools.permutations(boats))):
            raise ValueError("BOX_DOMAIN_INVALID")
    active = record.get("active_boats")
    if active is not None and any(not set(t).issubset(active) for t in triples):
        raise ValueError("METHOD_OUTSIDE_ACTIVE_DOMAIN")
    hit = result in tickets
    refunds = actual.get("refund_tickets")
    payout = actual.get("payout_per_100")
    refunds_valid = isinstance(refunds, list) and len(refunds) == len(set(refunds))
    if refunds_valid:
        try:
            for ticket in refunds:
                _ticket(ticket)
        except ValueError:
            refunds_valid = False
    if refunds_valid and result in refunds:
        raise ValueError("WINNING_TICKET_ALSO_REFUNDED")
    payout_valid = _number(payout) and payout >= 0
    money_known = refunds_valid and (payout_valid or not hit)
    stake = count * 100
    gross = (float(payout) if hit else 0.0) if money_known else None
    refund = 100 * len(set(tickets).intersection(refunds)) if money_known else None
    returned = gross + refund if money_known else None
    decision = method.get("bet_decision")
    if name == "five" and decision is None:
        decision = record.get("bet_decision")
    decision = decision if decision in ("BET", "SKIP") else None
    try:
        timestamp = _time(record.get("prediction_at"))
    except (ValueError, TypeError, OverflowError):
        timestamp = None
    return {"race_id": record["race_id"], "source": record.get("source"), "target_date": record["target_date"],
            "hit": int(hit), "stake": stake, "gross_payout": gross, "refund": refund,
            "return": returned, "net": returned - stake if money_known else None,
            "decision": decision, "timestamp": timestamp,
            "first_course": record.get("first_course"), "result": result,
            "market": record.get("distributions", {}).get("P_market"),
            "tickets": tickets}


def _drawdown(rows, action=False):
    if not rows:
        return {"status": "UNVERIFIED_NO_OBSERVATIONS", "value_yen": None}
    usable = [r for r in rows if (not action or r["decision"] == "BET")]
    if action and any(r["decision"] is None for r in rows):
        return {"status": "UNVERIFIED_UNKNOWN_BET_DECISION", "value_yen": None}
    if any(r["net"] is None for r in usable):
        return {"status": "UNVERIFIED_MISSING_MONEY", "value_yen": None}
    if any(r["timestamp"] is None for r in usable):
        return {"status": "UNVERIFIED_CHRONOLOGY", "value_yen": None}
    timestamps = [r["timestamp"] for r in usable]
    if len(set(timestamps)) != len(timestamps):
        return {"status": "UNVERIFIED_TIED_CHRONOLOGY", "value_yen": None}
    capital = peak = maximum = 0.0
    for row in sorted(usable, key=lambda r: r["timestamp"]):
        capital += row["net"]
        peak = max(peak, capital)
        maximum = max(maximum, peak - capital)
    return {"status": "OBSERVED", "value_yen": maximum, "n": len(usable),
            "initial_cumulative_net_yen": 0}


def _money_report(rows):
    known = [r for r in rows if r["net"] is not None]
    stake = sum(r["stake"] for r in known) if known else None
    returned = math.fsum(r["return"] for r in known) if known else None
    return {"n": len(rows), "hit_n": sum(r["hit"] for r in rows),
            "hit_rate": sum(r["hit"] for r in rows) / len(rows) if rows else None,
            "money_n": len(known), "money_unknown_n": len(rows) - len(known),
            "stake_yen": stake, "gross_payout_yen": math.fsum(r["gross_payout"] for r in known) if known else None,
            "refund_yen": math.fsum(r["refund"] for r in known) if known else None,
            "return_yen": returned, "net_yen": returned - stake if known else None,
            "return_rate": returned / stake if stake else None,
            "roi": (returned - stake) / stake if stake else None,
            "money_scope": "OBSERVED_ONLY" if len(known) != len(rows) else "COMPLETE_INPUT_SCOPE"}


def _popularity(row):
    try:
        market, _ = _distribution(row["market"])
        result_p = market[row["result"]]
    except (ValueError, KeyError, TypeError):
        return "UNVERIFIED"
    # Competition rank: ties share rank. Ex-post diagnostic, never a feature.
    rank = 1 + sum(p > result_p for p in market.values())
    return "1-3" if rank <= 3 else "4-10" if rank <= 10 else "11-30" if rank <= 30 else "31+"


def _method_report(rows, total, bootstrap_config=None):
    report = _money_report(rows)
    report.update({"input_n": total, "method_unavailable_n": total - len(rows),
                   "max_drawdown": _drawdown(rows),
                   "bet": _money_report([r for r in rows if r["decision"] == "BET"]),
                   "skip_counterfactual": _money_report([r for r in rows if r["decision"] == "SKIP"]),
                   "unknown_decision_n": sum(r["decision"] is None for r in rows)})
    bet_rows = [r for r in rows if r["decision"] == "BET"]
    known_actions = all(r["decision"] is not None for r in rows)
    report["action"] = _money_report(bet_rows)
    report["action"]["skipped_n"] = sum(r["decision"] == "SKIP" for r in rows)
    report["action"]["status"] = "OBSERVED" if known_actions else "UNVERIFIED_UNKNOWN_DECISIONS"
    report["action"]["max_drawdown"] = _drawdown(rows, action=True)
    if not bet_rows and known_actions and rows:
        # Known SKIP has zero stake/cashflow, but undefined ROI.
        report["action"].update(stake_yen=0, gross_payout_yen=0, refund_yen=0, return_yen=0, net_yen=0)
    courses = defaultdict(list)
    popularity = defaultdict(list)
    for row in rows:
        course = row["first_course"]
        key = str(course) if type(course) is int and 1 <= course <= 6 else "UNVERIFIED"
        courses[key].append(row)
        popularity[_popularity(row)].append(row)
    report["course_buckets"] = {k: _money_report(v) for k, v in sorted(courses.items())}
    report["popularity_buckets"] = {k: _money_report(v) for k, v in sorted(popularity.items())}
    report["popularity_definition"] = "ACTUAL_OUTCOME_MARKET_COMPETITION_RANK_EX_POST"
    report["stake_scope"] = "STANDALONE_METHOD_NEVER_POOLED_WITH_OTHER_METHODS"
    report["day_block_hit_rate_interval"] = _day_interval(
        [(row["target_date"], row["hit"]) for row in rows], bootstrap_config)
    report["day_block_hit_rate_interval"]["metric"] = "HIT_RATE_STANDALONE_METHOD"
    return report


def _percentile(sorted_values, fraction):
    index = (len(sorted_values) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    return sorted_values[lower] * (upper - index) + sorted_values[upper] * (index - lower) if upper != lower else sorted_values[lower]


def _day_interval(observations, configuration, estimand="RACE_WEIGHTED_MEAN_RESAMPLE_WHOLE_DAYS"):
    """Whole-day bootstrap of race-weighted observations; no superiority test."""
    if not isinstance(configuration, dict) or configuration.get("enabled") is not True:
        return {"status": "UNVERIFIED_NOT_CONFIGURED", "interval": None}
    confidence = configuration.get("confidence")
    repeats = configuration.get("replicates")
    minimum = configuration.get("min_clusters")
    seed = configuration.get("seed")
    reference = configuration.get("preregistration_reference")
    if (not _number(confidence) or not 0 < confidence < 1
            or type(repeats) is not int or not 100 <= repeats <= 100000
            or type(minimum) is not int or minimum < 2 or type(seed) is not int
            or not isinstance(reference, str) or not reference):
        return {"status": "UNVERIFIED_INVALID_EXPLICIT_CONFIG", "interval": None}
    days = defaultdict(list)
    for day, delta in observations:
        if not _number(delta):
            return {"status": "UNVERIFIED_NONFINITE_PAIR", "interval": None}
        days[day].append(delta)
    if len(days) < minimum:
        return {"status": "UNVERIFIED_TOO_FEW_DAY_CLUSTERS", "interval": None,
                "clusters": len(days), "required": minimum}
    keys = sorted(days)
    rng = random.Random(seed)
    sampled = []
    for _ in range(repeats):
        values = list(itertools.chain.from_iterable(days[rng.choice(keys)] for _ in keys))
        sampled.append(math.fsum(values) / len(values))
    sampled.sort()
    tail = (1 - confidence) / 2
    return {"status": "EXPLORATORY_NOT_SUPERIORITY_EVIDENCE", "clusters": len(days),
            "race_pairs": len(observations), "confidence": confidence,
            "replicates": repeats, "seed": seed,
            "preregistration_reference": reference,
            "estimand": estimand,
            "interval": [_percentile(sampled, tail), _percentile(sampled, 1 - tail)]}


def legacy_adapter(record, profile=None):
    """Match supplied fixed legacy outputs to verified raw-reference bytes.

    Hash agreement proves local bytes only. It cannot authenticate the human
    attestation, historic output, or reproduce the frozen production algorithm.
    """
    opened = {"status": "OPEN", "reproduction": "UNVERIFIED", "prediction": None,
              "external_authenticity": "UNVERIFIED_BY_LOCAL_CODE"}
    if not isinstance(profile, dict):
        return dict(opened, reason="VERIFIED_REFERENCE_PROFILE_REQUIRED")
    raw = profile.get("raw_bytes")
    expected = profile.get("sha256")
    if (profile.get("verified") is not True or not isinstance(raw, bytes)
            or not isinstance(expected, str) or hashlib.sha256(raw).hexdigest() != expected
            or not profile.get("source_identity") or not profile.get("verification_evidence")):
        return dict(opened, reason="REFERENCE_BYTES_HASH_OR_ATTESTATION_MISSING")
    legacy = record.get("legacy")
    if not isinstance(legacy, dict):
        return dict(opened, reason="FIXED_LEGACY_OUTPUT_REQUIRED")
    for field in ("race_id", "target_date"):
        if legacy.get(field) != record.get(field):
            return dict(opened, reason="LEGACY_" + field.upper() + "_MISMATCH")
    if (legacy.get("source_identity") != profile["source_identity"]
            or legacy.get("reference_sha256") != expected
            or ("source" in record and legacy.get("source") != record["source"])):
        return dict(opened, reason="LEGACY_SOURCE_OR_REFERENCE_MISMATCH")
    try:
        if not _time(legacy.get("prediction_at")) < _time(record.get("deadline")):
            return dict(opened, reason="LEGACY_NOT_BEFORE_DEADLINE")
    except (ValueError, TypeError, OverflowError):
        return dict(opened, reason="LEGACY_DEADLINE_EVIDENCE_MISSING")
    tickets = legacy.get("tickets")
    if not isinstance(tickets, list) or len(tickets) not in (5, 6) or len(set(tickets)) != len(tickets):
        return dict(opened, reason="LEGACY_TICKETS_INVALID")
    try:
        for ticket in tickets:
            _ticket(ticket)
    except ValueError:
        return dict(opened, reason="LEGACY_TICKETS_INVALID")
    return {"status": "LOCAL_INPUTS_MATCHED", "reproduction": "UNVERIFIED_NOT_REIMPLEMENTED",
            "external_authenticity": "UNVERIFIED_BY_LOCAL_CODE", "prediction": dict(legacy),
            "reference_sha256": expected}


def evaluate_records(records, config=None):
    """Evaluate matched offline records. JSON safe, including infinite losses.

    One candidate and source-scoped race per call. Repeated race/source keys are
    rejected in full, so duplicates cannot silently inflate effective N.
    Config choices remain PROPOSED and never trigger deployment/GO.
    """
    config = config or {}
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError("RECORDS_MUST_BE_LIST_OF_OBJECTS")
    bins = config.get("calibration_bins", 10)
    if type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("INVALID_CALIBRATION_BINS")
    counts = Counter((r.get("race_id"), r.get("source")) for r in records
                     if isinstance(r.get("race_id"), str)
                     and (r.get("source") is None or isinstance(r.get("source"), str)))
    issues = []
    methods = {name: [] for name in METHODS}
    stages = {stage: [] for stage in STAGES}
    pairs = {stage: [] for stage in STAGES if stage != "P_market"}
    legacy_status = Counter()
    legacy_hit_deltas = []
    legacy_methods = {name: [] for name in METHODS}
    legacy_method_deltas = {name: [] for name in METHODS}
    valid = 0
    for index, record in enumerate(records):
        try:
            if (not isinstance(record.get("race_id"), str)
                    or (record.get("source") is not None and not isinstance(record.get("source"), str))):
                raise ValueError("RECORD_SCOPE_INVALID")
            if counts[(record.get("race_id"), record.get("source"))] != 1:
                raise ValueError("DUPLICATE_RACE_SOURCE")
            actual, result = _bound_outcome(record)
        except (ValueError, TypeError) as exc:
            issues.append({"record_index": index, "component": "record", "reason": exc.args[0]})
            continue
        valid += 1
        for method in METHODS:
            try:
                methods[method].append(_method_observation(record, actual, result, method))
            except (ValueError, TypeError, KeyError) as exc:
                issues.append({"record_index": index, "component": method,
                               "reason": exc.args[0] if exc.args else "INVALID_INPUT"})
        scores = {}
        for stage in STAGES:
            try:
                dist, boats = _distribution(record.get("distributions", {}).get(stage))
                if record.get("active_boats") is not None and boats != set(record["active_boats"]):
                    raise ValueError("DISTRIBUTION_ACTIVE_DOMAIN_MISMATCH")
                score = _score(dist, result)
                stages[stage].append(score)
                scores[stage] = score
            except (ValueError, TypeError, KeyError) as exc:
                issues.append({"record_index": index, "component": stage,
                               "reason": exc.args[0] if exc.args else "INVALID_INPUT"})
        if "P_market" in scores:
            for stage in pairs:
                if stage in scores:
                    pairs[stage].append((record["target_date"], scores[stage], scores["P_market"]))
        legacy = legacy_adapter(record, config.get("legacy_profile"))
        legacy_status[legacy["status"]] += 1
        if legacy["status"] == "LOCAL_INPUTS_MATCHED":
            old = legacy["prediction"]
            # Compare like for like only; a legacy 6-ticket BOX is not a five-ticket model.
            requested = old.get("method", "five" if len(old["tickets"]) == 5 else None)
            if requested in methods:
                current = next((r for r in methods[requested]
                                if r["race_id"] == record["race_id"] and r["source"] == record.get("source")), None)
                if current is not None and len(old["tickets"]) == len(current["tickets"]):
                    adapted = dict(record)
                    if requested == "five":
                        adapted["selection"] = old
                    else:
                        adapted["boxes"] = {requested: old}
                    try:
                        fixed = _method_observation(adapted, actual, result, requested)
                        legacy_methods[requested].append(fixed)
                        delta = current["hit"] - fixed["hit"]
                        legacy_hit_deltas.append(delta)
                        legacy_method_deltas[requested].append(delta)
                    except (ValueError, TypeError, KeyError):
                        issues.append({"record_index": index, "component": "legacy",
                                       "reason": "FIXED_OUTPUT_METHOD_INVALID"})
    comparisons = {}
    for stage, paired in pairs.items():
        # Positive difference always means candidate lower loss than market.
        brier = [(day, market["joint_brier"] - candidate["joint_brier"]) for day, candidate, market in paired]
        finite_log = []
        nonfinite = 0
        for day, candidate, market in paired:
            if math.isfinite(candidate["joint_logloss"]) and math.isfinite(market["joint_logloss"]):
                finite_log.append((day, market["joint_logloss"] - candidate["joint_logloss"]))
            else:
                nonfinite += 1
        comparisons[stage] = {"paired_n": len(paired), "unpaired_n": len(records) - len(paired),
                              "difference_definition": "MARKET_LOSS_MINUS_CANDIDATE_LOSS",
                              "brier_difference": _mean([value for _, value in brier], len(records)),
                              "logloss_difference": {"value": None if nonfinite or not finite_log else math.fsum(v for _, v in finite_log) / len(finite_log),
                                                     "status": "UNVERIFIED_NONFINITE_PAIRS" if nonfinite else "FINITE" if finite_log else "UNVERIFIED",
                                                     "nonfinite_pairs": nonfinite, "finite_pairs": len(finite_log)},
                              "day_block_brier_interval": _day_interval(brier, config.get("day_bootstrap"),
                                                                        "RACE_WEIGHTED_PAIRED_DIFFERENCE_RESAMPLE_WHOLE_DAYS"),
                              "superiority": "UNVERIFIED"}
    return {"status": "OFFLINE_DESCRIPTIVE_RESEARCH_ONLY", "input_n": len(records),
            "matched_final_outcome_n": valid, "invalid_record_n": len(records) - valid,
            "record_issues": issues,
            "methods": {name: _method_report(rows, len(records), config.get("day_bootstrap")) for name, rows in methods.items()},
            "distributions": {stage: _distribution_report(rows, len(records), bins) for stage, rows in stages.items()},
            "market_comparisons": comparisons,
            "legacy": {"status_counts": dict(legacy_status), "paired_hit_delta": _mean(legacy_hit_deltas, len(records)),
                       "methods": {name: {"fixed_output_metrics": _method_report(rows, len(records), config.get("day_bootstrap")),
                                           "paired_hit_delta": _mean(legacy_method_deltas[name], len(records))}
                                   for name, rows in legacy_methods.items()},
                       "status": "OPEN" if len(legacy_hit_deltas) != len(records) else "FIXED_OUTPUT_COMPARISON_ONLY",
                       "reproduction": "UNVERIFIED_NOT_REIMPLEMENTED", "superiority": "UNVERIFIED"},
            "performance_improvement": "UNVERIFIED_REQUIRES_UNUSED_REAL_FUTURE_DATA",
            "production_go": False, "config_status": "PROPOSED"}
