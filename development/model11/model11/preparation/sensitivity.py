"""Pre-outcome EV stress diagnostics on immutable, already selected portfolios.

No outcome is accepted by audit_forecast. diagnose attaches descriptive settlement
only after every pre-outcome audit is finished. Nothing here selects new tickets,
changes a forecast, fits a threshold, or authorizes a real purchase.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from itertools import permutations, product
import math
import re

from ..engine import canonical_hash, check_distribution, usable_market
from ..validation import validate_outcome, validate_race


METHODS = ("five", "human_research", "mechanical_research", "box_v11_research")
DEFAULT_SCENARIOS = {
    "protocol_id": "EV_STRESS_GRID_PROPOSED_V002",
    "market_weights": [0.0, 0.5, 1.0],
    "uniform_weights": [0.0, 0.25, 0.5],
    "odds_multipliers": [1.0, 0.9, 0.75],
    "risk_policy": {
        "min_stressed_roi": 0.0,
        "min_coverage": 0.05,
        "max_single_ticket_ev_share": 0.5,
        "max_gross_odds": 1000.0,
    },
    "preregistration_reference": "PROPOSED_NOT_EXTERNALLY_REGISTERED",
}
_RISK_ID = "EV_ROBUST_OVERLAY_PROPOSED_V002"
_LABEL_KEYS = {"actual", "result", "results", "outcome", "outcomes", "payout_per_100", "refund_tickets"}


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _fail(code):
    raise ValueError(code)


def _config(value):
    if value is None:
        return deepcopy(DEFAULT_SCENARIOS)
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SCENARIOS):
        _fail("SCENARIO_CONFIGURATION_INVALID")
    cfg = deepcopy(DEFAULT_SCENARIOS)
    for name, item in value.items():
        if name == "risk_policy":
            if not isinstance(item, dict) or set(item) - set(cfg[name]):
                _fail("RISK_CONFIGURATION_INVALID")
            cfg[name].update(deepcopy(item))
        else:
            cfg[name] = deepcopy(item)
    for name in ("protocol_id", "preregistration_reference"):
        if not isinstance(cfg[name], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", cfg[name]):
            _fail("SCENARIO_REFERENCE_INVALID")
    for name in ("market_weights", "uniform_weights", "odds_multipliers"):
        items = cfg[name]
        if (not isinstance(items, list) or not 1 <= len(items) <= 5
                or any(not _finite(x) or not 0 <= x <= 1 for x in items)
                or len(set(items)) != len(items)):
            _fail("SCENARIO_GRID_INVALID")
        if name == "odds_multipliers" and (0 in items or 1 not in items):
            _fail("ODDS_GRID_MUST_INCLUDE_BASELINE_AND_POSITIVE_HAIRCUTS")
        if name != "odds_multipliers" and 0 not in items:
            _fail("PROBABILITY_GRID_MUST_INCLUDE_BASELINE")
    policy = cfg["risk_policy"]
    for name, item in policy.items():
        if not _finite(item) or item < 0:
            _fail("RISK_CONFIGURATION_INVALID")
        if name in ("min_coverage", "max_single_ticket_ev_share") and item > 1:
            _fail("RISK_CONFIGURATION_INVALID")
        if name == "max_gross_odds" and item <= 0:
            _fail("RISK_CONFIGURATION_INVALID")
    return cfg


def _has_label(value, depth=0):
    if depth > 32:
        return True
    if isinstance(value, dict):
        return any(not isinstance(key, str) or key.lower() in _LABEL_KEYS or _has_label(item, depth + 1)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_has_label(item, depth + 1) for item in value)
    return False


def _unverified(code):
    return {"status": "UNVERIFIED", "reason_codes": [code], "methods": {},
            "risk_candidate_id": _RISK_ID, "config_status": "PROPOSED",
            "external_authenticity": "UNVERIFIED", "performance_improvement": "UNVERIFIED",
            "production_go": False}


def _public_id(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) else None


def _forecast_gate(forecast, race):
    if not isinstance(forecast, dict) or not isinstance(race, dict):
        _fail("FORECAST_OR_RACE_MISSING")
    if _has_label(forecast) or forecast.get("first_course") is not None:
        _fail("OUTCOME_INFORMATION_IN_FORECAST")
    try:
        digest = canonical_hash({key: item for key, item in forecast.items() if key != "prediction_sha256"})
    except (ValueError, TypeError, OverflowError, RecursionError):
        _fail("FORECAST_JSON_INVALID")
    if forecast.get("prediction_sha256") != digest:
        _fail("FORECAST_SELF_HASH_MISMATCH")
    if (not isinstance(forecast.get("config"), dict) or not isinstance(forecast.get("model_spec"), dict)
            or not isinstance(forecast.get("distributions"), dict)
            or set(forecast["distributions"]) != {"P_raw", "P_model", "P_market", "P_shrunk"}
            or not isinstance(forecast.get("boxes"), dict)):
        _fail("FORECAST_COMPONENTS_MISSING_OR_INVALID")
    age = forecast["config"].get("max_odds_age_seconds", 120)
    if not _finite(age) or age < 0:
        _fail("FORECAST_CONFIGURATION_INVALID")
    gate = validate_race(race, max_odds_age_seconds=age)
    if not gate["eligible"]:
        _fail("RACE_VALIDATION_UNVERIFIED")
    for key in ("race_id", "target_date", "prediction_at", "deadline"):
        if forecast.get(key) != race.get(key):
            _fail("FORECAST_RACE_IDENTITY_MISMATCH")
    if forecast.get("input_sha256") != canonical_hash(race):
        _fail("FORECAST_RACE_SELF_HASH_MISMATCH")
    if forecast.get("model_sha256") != canonical_hash(forecast.get("model_spec")):
        _fail("MODEL_SELF_HASH_MISMATCH")
    try:
        check_distribution(forecast.get("P_calibrated"), race["active_boats"])
        for name, dist in forecast["distributions"].items():
            if dist is not None or name in ("P_raw", "P_model"):
                check_distribution(dist, race["active_boats"])
    except (ValueError, TypeError, KeyError, OverflowError):
        _fail("FORECAST_DISTRIBUTION_INVALID")
    stage = forecast.get("selection_stage")
    if stage == "P_calibrated":
        selected = forecast.get("P_calibrated")
    elif stage == "P_shrunk":
        selected = forecast.get("distributions", {}).get(stage)
    else:
        _fail("SELECTION_STAGE_UNKNOWN")
    try:
        check_distribution(selected, race["active_boats"])
    except (ValueError, TypeError, KeyError, OverflowError):
        _fail("SELECTED_DISTRIBUTION_INVALID")
    market = usable_market(race, max_odds_age_seconds=age, gate=gate)["P_market"]
    declared = forecast.get("distributions", {}).get("P_market")
    if market is None:
        if declared is not None:
            _fail("MARKET_GATE_MISMATCH")
    else:
        if not isinstance(declared, dict) or set(declared) != set(market):
            _fail("MARKET_DISTRIBUTION_MISMATCH")
        if any(not _finite(declared[key]) or abs(declared[key] - market[key]) > 1e-10 for key in market):
            _fail("MARKET_DISTRIBUTION_MISMATCH")
    odds = None if market is None else race["odds_snapshot"]["odds"]
    if (market is None) != (forecast["distributions"]["P_shrunk"] is None):
        _fail("MARKET_SHRINKAGE_AVAILABILITY_MISMATCH")
    if stage != ("P_calibrated" if market is None else "P_shrunk"):
        _fail("SELECTION_STAGE_AVAILABILITY_MISMATCH")
    return selected, market, odds


def _money(tickets, dist, odds, multiplier=1.0):
    try:
        gross = math.fsum(100 * dist[ticket] * odds[ticket] * multiplier for ticket in tickets)
    except OverflowError:
        _fail("MONETARY_OVERFLOW")
    if not math.isfinite(gross):
        _fail("MONETARY_OVERFLOW")
    return gross


def _method(forecast, name, domain):
    method = forecast.get("selection") if name == "five" else forecast.get("boxes", {}).get(name)
    if not isinstance(method, dict):
        _fail("PORTFOLIO_MISSING")
    tickets, count = method.get("tickets"), 5 if name == "five" else 6
    if (not isinstance(tickets, list) or len(tickets) != count
            or any(not isinstance(ticket, str) or ticket not in domain for ticket in tickets)
            or len(set(tickets)) != count or method.get("stake_yen") != 100 * count):
        _fail("PORTFOLIO_TICKETS_OR_STAKE_INVALID")
    if name != "five":
        boats = method.get("boats")
        if (not isinstance(boats, list) or len(boats) != 3 or any(type(b) is not int for b in boats)
                or len(set(boats)) != 3
                or set(tickets) != {"-".join(map(str, triple)) for triple in permutations(boats)}):
            _fail("BOX_PERMUTATION_DOMAIN_INVALID")
    if method.get("bet_decision") not in ("BET", "SKIP"):
        _fail("ORIGINAL_BET_DECISION_UNKNOWN")
    if name == "five" and forecast.get("bet_decision") != method["bet_decision"]:
        _fail("ORIGINAL_BET_DECISION_MISMATCH")
    return method


def _grid(cfg):
    return [{"scenario_id": "S%03d" % i, "market_weight": w, "uniform_weight": u,
             "odds_multiplier": multiplier}
            for i, (w, u, multiplier) in enumerate(product(cfg["market_weights"], cfg["uniform_weights"],
                                                           cfg["odds_multipliers"]), 1)]


def _audit_method(forecast, name, selected, market, odds, cfg, scenarios, protocol_hash):
    method = _method(forecast, name, selected)
    tickets, stake = method["tickets"], method["stake_yen"]
    coverage = math.fsum(selected[ticket] for ticket in tickets)
    if not _finite(method.get("coverage")) or abs(method["coverage"] - coverage) > 1e-10:
        _fail("DECLARED_COVERAGE_MISMATCH")
    baseline_gross = None if odds is None else _money(tickets, selected, odds)
    baseline_net = None if baseline_gross is None else baseline_gross - stake
    for field, value in (("expected_return_yen", baseline_gross), ("expected_net_yen", baseline_net)):
        declared = method.get(field)
        if value is None and declared is not None or value is not None and (
                not _finite(declared) or not math.isclose(declared, value, rel_tol=1e-9, abs_tol=1e-6)):
            _fail("DECLARED_EV_MISMATCH")
    contributions = None if odds is None else {ticket: 100 * selected[ticket] * odds[ticket] for ticket in tickets}
    share = (max(contributions.values()) / baseline_gross
             if contributions is not None and baseline_gross > 0 else None)
    max_odds = max(odds[ticket] for ticket in tickets) if odds is not None else None
    policy = cfg["risk_policy"]
    observations = []
    if coverage < policy["min_coverage"]:
        observations.append("LOW_PREDICTED_COVERAGE_PROPOSED_TRIGGER")
    if share is not None and share > policy["max_single_ticket_ev_share"]:
        observations.append("CONCENTRATED_EXPECTED_RETURN_PROPOSED_TRIGGER")
    if max_odds is not None and max_odds > policy["max_gross_odds"]:
        observations.append("HIGH_PAYOFF_DEPENDENCE_PROPOSED_TRIGGER")
    stress = []
    for scenario in scenarios:
        weight, uniform = scenario["market_weight"], scenario["uniform_weight"]
        if market is None and weight > 0:
            stress.append({"scenario_id": scenario["scenario_id"], "status": "UNVERIFIED_MARKET_MISSING",
                           "coverage": None, "expected_return_yen": None, "expected_net_yen": None, "roi": None})
            continue
        # A zero market weight uses the supplied model directly. An absent
        # market is never replaced with numeric zero in a probability input.
        pooled = selected if weight == 0 else {
            ticket: (1 - weight) * probability + weight * market[ticket]
            for ticket, probability in selected.items()}
        stressed = {ticket: (1 - uniform) * probability + uniform / len(selected)
                    for ticket, probability in pooled.items()}
        scenario_coverage = math.fsum(stressed[ticket] for ticket in tickets)
        gross = None if odds is None else _money(tickets, stressed, odds, scenario["odds_multiplier"])
        net = None if gross is None else gross - stake
        scenario_share = (max(100 * stressed[t] * odds[t] * scenario["odds_multiplier"] for t in tickets) / gross
                          if gross is not None and gross > 0 else None)
        stress.append({"scenario_id": scenario["scenario_id"], "status": "OBSERVED_FORMULA" if gross is not None else "UNVERIFIED_ODDS_MISSING",
                       "coverage": scenario_coverage, "expected_return_yen": gross,
                       "expected_net_yen": net, "roi": None if net is None else net / stake,
                       "single_ticket_ev_share_max": scenario_share})
    known = [row["roi"] for row in stress if row["roi"] is not None]
    worst_roi = min(known) if len(known) == len(stress) else None
    known_coverages = [row["coverage"] for row in stress if row["coverage"] is not None]
    worst_coverage = min(known_coverages) if len(known_coverages) == len(stress) else None
    known_shares = [row.get("single_ticket_ev_share_max") for row in stress if row.get("single_ticket_ev_share_max") is not None]
    worst_share = max(known_shares) if len(known_shares) == len(stress) else None
    risk_reasons = list(observations)
    if worst_roi is not None and worst_roi <= policy["min_stressed_roi"]:
        risk_reasons.append("STRESSED_ROI_THRESHOLD_NOT_EXCEEDED")
    if worst_coverage is not None and worst_coverage < policy["min_coverage"]:
        risk_reasons.append("STRESSED_COVERAGE_THRESHOLD_NOT_MET")
    if worst_share is not None and worst_share > policy["max_single_ticket_ev_share"]:
        risk_reasons.append("STRESSED_RETURN_CONCENTRATION_THRESHOLD_EXCEEDED")
    if worst_roi is None or share is None or worst_share is None or odds is None:
        risk_decision = "UNVERIFIED"
        risk_reasons.append("RISK_INPUTS_INCOMPLETE")
    elif method["bet_decision"] == "SKIP":
        risk_decision = "SKIP"
        risk_reasons.append("ORIGINAL_SKIP_PRESERVED")
    else:
        risk_decision = "SKIP" if risk_reasons else "BET"
        if not risk_reasons:
            risk_reasons.append("PROPOSED_RISK_GATES_MET")
    high = [] if odds is None else [t for t in tickets if odds[t] > policy["max_gross_odds"]]
    return {"status": "DESCRIPTIVE" if odds is not None else "UNVERIFIED",
            "reason_codes": [] if odds is not None else ["ADMITTED_ODDS_MISSING"],
            "tickets": list(tickets), "original_portfolio_sha256": canonical_hash(method),
            "stake_yen": stake, "original_bet_decision": method["bet_decision"],
            "predicted_coverage": coverage, "predicted_expected_return_yen": baseline_gross,
            "predicted_expected_net_yen": baseline_net,
            "single_ticket_ev_share_max": share, "selected_gross_odds_max": max_odds,
            "high_payoff_probability_mass": None if odds is None else math.fsum(selected[t] for t in high),
            "high_payoff_ev_share": (math.fsum(contributions[t] for t in high) / baseline_gross
                                      if contributions is not None and baseline_gross > 0 else None),
            "observations": observations, "scenarios": stress,
            "worst_stressed_roi": worst_roi, "worst_stressed_coverage": worst_coverage,
            "worst_stressed_single_ticket_ev_share": worst_share,
            "risk_overlay": {"candidate_id": _RISK_ID + ":" + protocol_hash[:12] + ":" + name,
                             "status": "PROPOSED_NOT_ADOPTED", "decision": risk_decision,
                             "reason_codes": risk_reasons, "original_decision_unchanged": True,
                             "production_go": False}}


def audit_forecast(forecast, race, scenario_config=None):
    """Audit four fixed portfolios using only information in a sealed forecast/race.

    Returned DESCRIPTIVE means the formulas are computable, not an accuracy,
    authenticity, independent-registration, or production-readiness PASS.
    """
    try:
        cfg = _config(scenario_config)
        selected, market, odds = _forecast_gate(forecast, race)
        protocol_hash = canonical_hash(cfg)
        scenarios = _grid(cfg)
        methods = {}
        for name in METHODS:
            try:
                methods[name] = _audit_method(forecast, name, selected, market, odds, cfg, scenarios, protocol_hash)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                code = str(exc) if type(exc) is ValueError and re.fullmatch(r"[A-Z_]+", str(exc)) else "PORTFOLIO_UNVERIFIED"
                methods[name] = {"status": "UNVERIFIED", "reason_codes": [code],
                                 "risk_overlay": {"candidate_id": _RISK_ID + ":" + protocol_hash[:12] + ":" + name,
                                                  "status": "PROPOSED_NOT_ADOPTED", "decision": "UNVERIFIED",
                                                  "reason_codes": [code], "production_go": False}}
        all_known = all(item["status"] == "DESCRIPTIVE" for item in methods.values())
        return {"status": "DESCRIPTIVE" if all_known else "UNVERIFIED",
                "reason_codes": [] if all_known else ["PORTFOLIO_OR_MARKET_UNVERIFIED"],
                "race_id": _public_id(race["race_id"]), "race_id_sha256": canonical_hash(race["race_id"]),
                "original_forecast_sha256": forecast["prediction_sha256"],
                "original_config_sha256": canonical_hash(forecast["config"]),
                "protocol": cfg, "protocol_sha256": protocol_hash, "scenario_grid": scenarios,
                "methods": methods, "risk_candidate_id": _RISK_ID,
                "config_status": "PROPOSED", "external_authenticity": "UNVERIFIED",
                "preregistration_authenticity": "UNVERIFIED", "tickets_reselected": False,
                "performance_improvement": "UNVERIFIED", "production_go": False}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        code = str(exc) if type(exc) is ValueError and re.fullmatch(r"[A-Z_]+", str(exc)) else "AUDIT_INPUT_UNVERIFIED"
        return _unverified(code)


def _index(items):
    if not isinstance(items, list):
        _fail("INPUT_COLLECTION_INVALID")
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("race_id"), str) or item["race_id"] in result:
            _fail("INPUT_ID_MISSING_OR_DUPLICATE")
        result[item["race_id"]] = item
    return result


def _settlement(forecast, race, outcome, method):
    if not isinstance(outcome, dict) or not validate_outcome(outcome)["eligible"]:
        return {"status": "UNVERIFIED", "reason_codes": ["FINAL_OUTCOME_MISSING_OR_INVALID"]}
    if any(outcome.get(key) != race.get(key) for key in ("race_id", "target_date")):
        return {"status": "UNVERIFIED", "reason_codes": ["OUTCOME_IDENTITY_MISMATCH"]}
    if "source" in outcome and outcome["source"] != forecast.get("source"):
        return {"status": "UNVERIFIED", "reason_codes": ["OUTCOME_SOURCE_MISMATCH"]}
    available = datetime.fromisoformat(outcome["available_at"].replace("Z", "+00:00"))
    deadline = datetime.fromisoformat(race["deadline"].replace("Z", "+00:00"))
    if available < deadline:
        return {"status": "UNVERIFIED", "reason_codes": ["OUTCOME_AVAILABLE_BEFORE_DEADLINE"]}
    ticket = "-".join(map(str, outcome["result"]))
    domain = forecast["P_calibrated"]
    refunds = outcome["refund_tickets"]
    if ticket not in domain or not set(refunds) <= set(domain) or ticket in refunds:
        return {"status": "UNVERIFIED", "reason_codes": ["OUTCOME_OR_REFUND_DOMAIN_INCONSISTENT"]}
    hit = ticket in method["tickets"]
    gross = outcome["payout_per_100"] if hit else 0.0
    refund = 100 * len(set(method["tickets"]) & set(refunds))
    returned = gross + refund
    if not _finite(returned):
        return {"status": "UNVERIFIED", "reason_codes": ["SETTLEMENT_NONFINITE"]}
    return {"status": "OBSERVED_SEPARATE_SETTLEMENT", "hit": hit, "stake_yen": method["stake_yen"],
            "gross_payout_yen": gross, "refund_yen": refund, "return_yen": returned,
            "net_yen": returned - method["stake_yen"],
            "original_bet_decision": method["original_bet_decision"]}


def _sum_or_none(values):
    return math.fsum(values) if values else None


def _aggregate_method(name, audits, settlements):
    rows = [audit["methods"][name] for audit in audits
            if name in audit["methods"] and "tickets" in audit["methods"][name]]
    known_ev = [row for row in rows if row["predicted_expected_return_yen"] is not None]
    actual = [entry[name] for entry in settlements if name in entry and entry[name]["status"] == "OBSERVED_SEPARATE_SETTLEMENT"]
    action = [row for row in actual if row["original_bet_decision"] == "BET"]
    predicted_hit_n = _sum_or_none([row["predicted_coverage"] for row in rows])
    zero_hit_independence = None
    if rows:
        coverages = [max(0.0, min(1.0, row["predicted_coverage"])) for row in rows]
        zero_hit_independence = 0.0 if 1 in coverages else math.exp(math.fsum(math.log1p(-p) for p in coverages))
    def observed(group):
        stake = sum(item["stake_yen"] for item in group) if group else None
        returned = _sum_or_none([item["return_yen"] for item in group])
        return {"n": len(group), "hit_n": sum(item["hit"] for item in group) if group else None,
                "stake_yen": stake, "return_yen": returned,
                "refund_yen": _sum_or_none([item["refund_yen"] for item in group]),
                "net_yen": returned - stake if stake is not None else None,
                "roi": (returned - stake) / stake if stake else None}
    return {"forecast_n": len(rows), "input_n": len(audits), "predicted_ev_n": len(known_ev),
            "predicted_stake_yen": sum(row["stake_yen"] for row in known_ev) if known_ev else None,
            "predicted_expected_return_yen": _sum_or_none([row["predicted_expected_return_yen"] for row in known_ev]),
            "predicted_expected_net_yen": _sum_or_none([row["predicted_expected_net_yen"] for row in known_ev]),
            "predicted_expected_hit_count": predicted_hit_n,
            "zero_hit_probability_if_conditionally_independent_and_model_correct": zero_hit_independence,
            "zero_hit_probability_status": "HYPOTHETICAL_NOT_A_P_VALUE_DAY_DEPENDENCE_UNACCOUNTED",
            "observed_settlement": observed(actual), "original_bet_subset_settlement": observed(action),
            "settlement_unknown_n": len(audits) - len(actual),
            "overlay_decision_counts": {
                decision: sum(audit["methods"].get(name, {}).get("risk_overlay", {}).get("decision", "UNVERIFIED") == decision
                              for audit in audits) for decision in ("BET", "SKIP", "UNVERIFIED")},
            "interpretation": "DESCRIPTIVE_NO_CAUSAL_OR_SUPERIORITY_CLAIM"}


def _losses(forecasts, races, outcomes, settlements):
    stages = ("P_raw", "P_model", "P_market", "P_shrunk", "P_calibrated")
    values = {stage: [] for stage in stages}
    pairs = []
    for forecast, settlement in zip(forecasts, settlements):
        if not any(row.get("status") == "OBSERVED_SEPARATE_SETTLEMENT" for row in settlement.values()):
            continue
        identity = forecast["race_id"]
        outcome, race = outcomes[identity], races[identity]
        ticket = "-".join(map(str, outcome["result"]))
        row = {}
        for stage in stages:
            dist = forecast.get("P_calibrated") if stage == "P_calibrated" else forecast.get("distributions", {}).get(stage)
            try:
                check_distribution(dist, race["active_boats"])
            except (ValueError, TypeError, OverflowError):
                continue
            loss = math.inf if dist[ticket] == 0 else -math.log(dist[ticket])
            values[stage].append(loss)
            row[stage] = loss
        if "P_model" in row and "P_market" in row and all(math.isfinite(row[s]) for s in ("P_model", "P_market")):
            pairs.append(row["P_model"] - row["P_market"])
    report = {}
    for stage, losses in values.items():
        infinite = sum(math.isinf(value) for value in losses)
        report[stage] = {"n": len(losses), "mean_joint_logloss": math.fsum(losses) / len(losses) if losses and not infinite else None,
                         "status": "INFINITE" if infinite else "OBSERVED" if losses else "UNVERIFIED",
                         "infinite_n": infinite, "unknown_n": len(forecasts) - len(losses)}
    mean_delta = math.fsum(pairs) / len(pairs) if pairs else None
    return {"stages": report, "paired_model_minus_market": {
                "n": len(pairs), "unknown_n": len(forecasts) - len(pairs), "mean_joint_logloss_delta": mean_delta,
                "market_lower_observed_mean": mean_delta > 0 if mean_delta is not None else None,
                "meaning": "POSITIVE_DELTA_MARKET_LOWER_LOSS_NOT_PROOF_OF_FUTURE_SUPERIORITY"}}


def diagnose(forecasts, races, outcomes=None, scenarios=None):
    """Join already frozen forecasts/races and optional final labels by race_id.

    races/outcomes may include extra training dates. Duplicate IDs fail closed.
    scenarios is the audit_forecast scenario_config. It must be fixed before labels
    are inspected; a supplied registration string is not external proof of that.
    """
    try:
        forecast_map, race_map = _index(forecasts), _index(races)
        outcome_map = {} if outcomes is None else _index(outcomes)
        # Pre-outcome audit and policy block has no access to outcome_map values.
        audits = [audit_forecast(forecast, race_map.get(identity), scenarios)
                  for identity, forecast in forecast_map.items()]
        settlements = []
        for (identity, forecast), audit in zip(forecast_map.items(), audits):
            row = {}
            for name, method in audit["methods"].items():
                if "tickets" in method:
                    row[name] = _settlement(forecast, race_map[identity], outcome_map.get(identity), method)
            settlements.append(row)
        summaries = {name: _aggregate_method(name, audits, settlements) for name in METHODS}
        losses = _losses(list(forecast_map.values()), race_map, outcome_map, settlements)
        box = summaries["box_v11_research"]["observed_settlement"]
        return {"status": "DESCRIPTIVE" if audits and all(a["status"] == "DESCRIPTIVE" for a in audits) else "UNVERIFIED",
                "reason_codes": (["NO_FORECASTS"] if not audits else [] if all(a["status"] == "DESCRIPTIVE" for a in audits)
                                 else ["AUDIT_SCOPE_UNVERIFIED"]), "input_n": len(audits),
                "audits": audits, "methods": summaries, "probability_diagnostics": losses,
                "settlements": settlements,
                "focus_observations": {
                    "box_v11_observed_n": box["n"], "box_v11_hit_n": box["hit_n"],
                    "box_v11_zero_hits": box["hit_n"] == 0 if box["n"] else None,
                    "market_lower_observed_model_loss": losses["paired_model_minus_market"]["market_lower_observed_mean"],
                    "cause_of_any_performance_gap": "UNVERIFIED_DESCRIPTIVE_STRESS_ONLY"},
                "portfolio_policy": "FOUR_METHODS_SEPARATE_NO_OVERLAP_AGGREGATION",
                "threshold_optimization": "NOT_PERFORMED", "tickets_reselected": False,
                "preregistration_authenticity": "UNVERIFIED", "config_status": "PROPOSED",
                "real_data_validation": "OPEN", "legacy_comparison": "OPEN",
                "performance_improvement": "UNVERIFIED", "production_go": False}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {"status": "UNVERIFIED", "reason_codes": ["DIAGNOSIS_INPUT_UNVERIFIED"],
                "audits": [], "methods": {}, "production_go": False,
                "performance_improvement": "UNVERIFIED", "config_status": "PROPOSED"}
