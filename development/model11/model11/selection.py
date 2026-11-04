"""Offline research selections. No implementation of formal BOX Ver.1 rules."""

from datetime import datetime
from itertools import combinations, permutations
import math
import re


_STAKE = 100
_DEFAULTS = {
    "main_count": 4,
    "min_value_edge": 0.05,
    "min_expected_roi": 0.0,
    "min_coverage": 0.0,
}


def _number(value, name, lower=None, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(name + " must be finite") from exc
    if not math.isfinite(value):
        raise ValueError(name + " must be finite")
    if ((lower is not None and value < lower)
            or (upper is not None and value > upper)):
        raise ValueError(name + " outside allowed range")
    return value


def _configuration(config):
    if config is None:
        config = {}
    if not isinstance(config, dict) or set(config) - set(_DEFAULTS):
        raise ValueError("unknown or invalid research selection configuration")
    result = dict(_DEFAULTS, **config)
    if type(result["main_count"]) is not int or result["main_count"] not in (3, 4):
        raise ValueError("main_count must be 3 or 4")
    result["min_value_edge"] = _number(result["min_value_edge"], "min_value_edge", 0)
    result["min_expected_roi"] = _number(result["min_expected_roi"], "min_expected_roi", 0)
    result["min_coverage"] = _number(result["min_coverage"], "min_coverage", 0, 1)
    return result


def _domain(dist):
    if not isinstance(dist, dict) or not dist:
        raise ValueError("distribution must be a nonempty dictionary")
    boats = set()
    values = {}
    for ticket, value in dist.items():
        if not isinstance(ticket, str) or not re.fullmatch(r"[1-6]-[1-6]-[1-6]", ticket):
            raise ValueError("invalid ordered ticket")
        triple = tuple(map(int, ticket.split("-")))
        if len(set(triple)) != 3:
            raise ValueError("ticket contains repeated boat")
        boats.update(triple)
        values[ticket] = _number(value, "probability", 0, 1)
    if not 3 <= len(boats) <= 6:
        raise ValueError("active domain requires three to six boats")
    expected = {_ticket(triple) for triple in permutations(sorted(boats), 3)}
    if set(values) != expected:
        raise ValueError("incomplete probability domain")
    if not math.isclose(math.fsum(values.values()), 1.0, abs_tol=1e-10, rel_tol=0):
        raise ValueError("probabilities must sum to one")
    return values, sorted(boats)


def _ticket(triple):
    return "-".join(map(str, triple))


def _odds(odds, dist):
    if odds is None:
        return None, "ODDS_MISSING"
    if not isinstance(odds, dict):
        raise ValueError("odds must be a dictionary or null")
    if set(odds) != set(dist):
        return None, "ODDS_DOMAIN_INCOMPLETE_OR_UNEXPECTED"
    clean = {ticket: _number(value, "odds") for ticket, value in odds.items()}
    if any(value <= 0 for value in clean.values()):
        raise ValueError("odds must be positive gross payout multiples")
    # Bound all possible monetary products before choosing a particular method.
    if any(not math.isfinite(_STAKE * dist[ticket] * value)
           for ticket, value in clean.items()):
        raise ValueError("expected monetary amount overflow")
    return clean, "ODDS_COMPLETE"


def _expected_return(tickets, dist, odds):
    try:
        result = math.fsum(_STAKE * dist[ticket] * odds[ticket] for ticket in tickets)
    except OverflowError as exc:
        raise ValueError("expected monetary amount overflow") from exc
    if not math.isfinite(result):
        raise ValueError("expected monetary amount overflow")
    return result


def _economics(tickets, dist, odds, odds_status, config):
    coverage = math.fsum(dist[ticket] for ticket in tickets)
    stake = _STAKE * len(tickets)
    reasons = []
    gross = net = roi = None
    decision = "SKIP"
    if odds is None:
        reasons.append(odds_status)
    else:
        gross = _expected_return(tickets, dist, odds)
        net = gross - stake
        roi = net / stake
        if roi <= config["min_expected_roi"]:
            reasons.append("RESEARCH_ROI_THRESHOLD_NOT_EXCEEDED")
        if coverage < config["min_coverage"]:
            reasons.append("RESEARCH_COVERAGE_THRESHOLD_NOT_MET")
        if not reasons:
            decision = "BET"
            reasons.append("PROPOSED_RESEARCH_RISK_GATES_MET")
    return {
        "coverage": coverage,
        "stake_yen": stake,
        "expected_return_yen": gross,
        "expected_net_yen": net,
        "expected_roi": roi,
        "bet_decision": decision,
        "reasons": reasons,
        "odds_status": odds_status,
        "risk_policy_status": "PROPOSED_NOT_ADOPTED",
        "simulation_only": True,
    }


def select_five(dist, odds=None, config=None):
    """Select five unique tickets; a value 'hole' requires complete observed odds.

    Odds freshness/as-of checks belong to the input validator. This function accepts
    only the already admitted numeric snapshot and never fills absent odds.
    """
    dist, _ = _domain(dist)
    config = _configuration(config)
    odds, odds_status = _odds(odds, dist)
    ranked = sorted(dist, key=lambda ticket: (-dist[ticket], ticket))
    main = ranked[:config["main_count"]]
    remaining = [ticket for ticket in ranked if ticket not in main]
    value = []
    if odds is not None:
        supported = [ticket for ticket in remaining
                     if dist[ticket] * odds[ticket] > 1 + config["min_value_edge"]]
        supported.sort(key=lambda ticket: (-dist[ticket] * odds[ticket], -dist[ticket], ticket))
        value = supported[:5 - len(main)]
    fallback = [ticket for ticket in remaining if ticket not in value][:5 - len(main) - len(value)]
    selection_order = main + value + fallback
    tickets = sorted(selection_order, key=lambda ticket: tuple(map(int, ticket.split("-"))))
    output = {
        "tickets": tickets,
        "selection_order": selection_order,
        "main_tickets": main,
        "value_tickets": value,
        "fallback_tickets": fallback,
        "selection_labels": {**{ticket: "MAIN_PROBABILITY" for ticket in main},
                             **{ticket: "VALUE_SUPPORTED" for ticket in value},
                             **{ticket: "PROBABILITY_FALLBACK_NOT_HOLE" for ticket in fallback}},
        "supported_hole_status": "SUPPORTED" if len(value) == 5 - len(main) else "INSUFFICIENT_SUPPORTED_HOLES",
        "configuration": config,
        "configuration_status": "PROPOSED_NOT_ADOPTED",
        "probability_stage": "SUPPLIED_RESEARCH_DISTRIBUTION",
        "method": "MAIN_PLUS_SUPPORTED_VALUE_RESEARCH",
    }
    output.update(_economics(tickets, dist, odds, odds_status, config))
    return output


def _aware(value):
    if not isinstance(value, str) or value.endswith("-00:00") or re.search(r"[.,]\d{7,}", value):
        raise ValueError("invalid timestamp")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("timestamp must be timezone aware ISO seconds")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return parsed


def _box(boats, dist, odds, odds_status, config, method):
    tickets = [_ticket(triple) for triple in permutations(sorted(boats), 3)]
    output = {
        "boats": sorted(boats),
        "tickets": tickets,
        "method": method,
        "formal_box_v1_reproduction": False,
        "status": "NOT_FORMAL_BOXV1_RESEARCH_ONLY",
    }
    output.update(_economics(tickets, dist, odds, odds_status, config))
    return output


def build_boxes(race, dist, five, odds=None, config=None):
    """Build separate Human-style, Mechanical, and EV BOX research candidates.

    These names denote research comparison lanes, never proof of frozen BOX V1.
    """
    if not isinstance(race, dict):
        raise ValueError("race must be a dictionary")
    dist, active = _domain(dist)
    supplied_active = race.get("active_boats")
    if (not isinstance(supplied_active, list) or any(type(b) is not int for b in supplied_active)
            or len(set(supplied_active)) != len(supplied_active) or sorted(supplied_active) != active):
        raise ValueError("race and probability active boat domains differ")
    prediction_at, deadline = _aware(race.get("prediction_at")), _aware(race.get("deadline"))
    if prediction_at >= deadline:
        raise ValueError("prediction must precede deadline")
    if not isinstance(five, dict) or not isinstance(five.get("tickets"), list):
        raise ValueError("five selection must contain tickets list")
    five_tickets = five["tickets"]
    if (len(five_tickets) != 5 or any(not isinstance(ticket, str) or ticket not in dist for ticket in five_tickets)
            or len(set(five_tickets)) != 5):
        raise ValueError("five tickets must be unique and in probability domain")
    config = _configuration(config)
    odds, odds_status = _odds(odds, dist)
    counts = {boat: sum(str(boat) in ticket.split("-") for ticket in five_tickets) for boat in active}
    first_counts = {boat: sum(ticket.startswith(str(boat) + "-") for ticket in five_tickets) for boat in active}
    frequency_rank = sorted(active, key=lambda boat: (-counts[boat], -first_counts[boat], boat))
    manual = race.get("human_box_input")
    if manual is not None:
        time_fields = {"observed_at", "acquired_at", "available_at", "revision_at"}
        if not isinstance(manual, dict) or set(manual) != {"core", "insertion"} | time_fields:
            raise ValueError("human research input has missing or unexpected availability metadata")
        core, insertion = manual["core"], manual["insertion"]
        if (not isinstance(core, list) or len(core) != 2 or any(type(boat) is not int for boat in core)
                or type(insertion) is not int or len(set(core + [insertion])) != 3
                or not set(core + [insertion]) <= set(active)):
            raise ValueError("human research input needs three distinct active boats")
        times = {field: _aware(manual[field]) for field in time_fields}
        if any(moment > prediction_at or moment >= deadline for moment in times.values()):
            raise ValueError("human research input not available before prediction")
        if times["acquired_at"] > times["available_at"]:
            raise ValueError("human research input available before acquisition")
        human_boats = core + [insertion]
        method = "MANUAL_CORE_INSERTION_RESEARCH"
        manual_status = "AS_OF_GATE_PASSED_NOT_LEGACY_PROOF"
    else:
        core, insertion = frequency_rank[:2], frequency_rank[2]
        human_boats = core + [insertion]
        method = "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH"
        manual_status = "NO_MANUAL_INPUT_AUTOMATIC_RESEARCH_HEURISTIC"
    human = _box(human_boats, dist, odds, odds_status, config, method)
    human.update({"core": list(core), "insertion": insertion,
                  "five_appearance_counts": {str(boat): counts[boat] for boat in active},
                  "manual_status": manual_status})

    # Mechanical evaluates all 20 sets at six active boats, independently of Human.
    candidates = list(combinations(active, 3))
    coverage = {boats: math.fsum(dist[_ticket(triple)] for triple in permutations(boats, 3))
                for boats in candidates}
    mechanical_boats = min(candidates, key=lambda boats: (-coverage[boats], boats))
    mechanical = _box(mechanical_boats, dist, odds, odds_status, config,
                      "EXHAUSTIVE_SIX_PERMUTATION_PROBABILITY_MASS_RESEARCH")
    if odds is not None:
        candidate_ev = {boats: _expected_return([_ticket(triple) for triple in permutations(boats, 3)],
                                               dist, odds) for boats in candidates}
        value_boats = min(candidates, key=lambda boats: (-candidate_ev[boats], -coverage[boats], boats))
        value_method = "EXHAUSTIVE_EXPECTED_RETURN_BOX_V11_RESEARCH"
        objective_status = "EXPECTED_RETURN_AVAILABLE_PROPOSED"
    else:
        value_boats = min(candidates, key=lambda boats: (-coverage[boats], boats))
        value_method = "BOX_V11_PROBABILITY_FALLBACK_UNKNOWN_EV"
        objective_status = "EV_UNKNOWN_PROBABILITY_FALLBACK"
    value_box = _box(value_boats, dist, odds, odds_status, config, value_method)
    value_box["objective_status"] = objective_status
    boxes = {"human_research": human, "mechanical_research": mechanical, "box_v11_research": value_box}
    overlaps = {"five_vs_" + name: sorted(set(five_tickets) & set(box["tickets"]))
                for name, box in boxes.items()}
    for first, second in combinations(boxes, 2):
        overlaps[first + "_vs_" + second] = sorted(set(boxes[first]["tickets"]) & set(boxes[second]["tickets"]))
    ticket_sets = [set(five_tickets)] + [set(box["tickets"]) for box in boxes.values()]
    overlaps["unique_ticket_union"] = sorted(set.union(*ticket_sets))
    overlaps["aggregation_policy"] = "REPORT_METHODS_SEPARATELY_DO_NOT_SUM_OVERLAPPING_PORTFOLIOS"
    boxes.update({
        "composition_difference": "YES" if set(human["boats"]) != set(mechanical["boats"]) else "NO",
        "composition_meaning": "BOAT_SET_EQUALITY_ONLY_NOT_QUALITY_OR_SUPERIORITY",
        "overlap": overlaps,
        "legacy_box_v1": {
            "status": "UNVERIFIED_ORIGINAL_BYTES_SHA_NOT_PROVIDED",
            "human": None, "mechanical": None,
            "reason": "FORMAL_FROZEN_RULES_NOT_RECONSTRUCTED",
        },
        "configuration": config,
        "configuration_status": "PROPOSED_NOT_ADOPTED",
    })
    return boxes
