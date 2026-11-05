"""Five separately named V003 research methods; no formal Human BOX comparison."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re

from ..metrics import evaluate_records as _old_evaluate
from ..metrics import _bound_outcome, _method_observation, _method_report
from .portfolios import validate_human_input


METHODS_V003 = ("five", "five_appearance_research", "human_input_research", "mechanical_research", "box_v11_research")


def _adapt(record):
    """Private old-kernel alias only; never serialize or return this container."""
    adapted = deepcopy(record)
    adapted.pop("legacy", None)
    boxes = record.get("boxes") if isinstance(record.get("boxes"), dict) else {}
    automatic = boxes.get("five_appearance_research")
    if (not isinstance(automatic, dict) or automatic.get("origin") != "AUTOMATED_FIVE_APPEARANCES"
            or automatic.get("method") != "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH"
            or automatic.get("human_origin") is not False):
        automatic = None
    adapted["boxes"] = {"human_research": deepcopy(automatic),
                        "mechanical_research": deepcopy(boxes.get("mechanical_research")),
                        "box_v11_research": deepcopy(boxes.get("box_v11_research"))}
    return adapted


def _empty_observations(report, status):
    report["status"] = status
    report["hit_n"] = None
    for key in ("bet", "skip_counterfactual", "action"):
        report[key].update(status=status, hit_n=None)
    return report


def evaluate_records_v003(records, config=None):
    """Keep null manual observations unknown; reuse only old statistical math.

    Old `legacy`/legacy_profile are explicitly excluded: this function is not a
    frozen Model 1.0 or formal BOX Ver.1 comparison adapter.
    """
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("V003_RECORDS_MUST_BE_LIST_OF_OBJECTS")
    config = {} if config is None else deepcopy(config)
    if not isinstance(config, dict) or set(config) - {"calibration_bins", "day_bootstrap"}:
        raise ValueError("V003_EVALUATION_CONFIGURATION_INVALID")
    adapted = [_adapt(record) for record in records]
    old = _old_evaluate(adapted, config)
    methods = {"five": old["methods"]["five"],
               "five_appearance_research": old["methods"]["human_research"],
               "mechanical_research": old["methods"]["mechanical_research"],
               "box_v11_research": old["methods"]["box_v11_research"]}
    for method in methods.values():
        if method["n"] == 0:
            _empty_observations(method, "UNVERIFIED_NO_OBSERVATIONS")
    issues = [{**issue, "component": "five_appearance_research" if issue.get("component") == "human_research" else issue.get("component")}
              for issue in old["record_issues"] if issue.get("component") != "legacy"]
    counts = Counter((record.get("race_id"), record.get("source")) for record in records
                     if isinstance(record.get("race_id"), str)
                     and (record.get("source") is None or isinstance(record.get("source"), str)))
    manual_rows = []
    absent_n = 0
    invalid_manual_n = 0
    for index, record in enumerate(records):
        boxes = record.get("boxes") if isinstance(record.get("boxes"), dict) else {}
        if "human_research" in boxes:
            issues.append({"record_index": index, "component": "schema", "reason": "V003_AMBIGUOUS_ACTIVE_SLOT_FORBIDDEN"})
        manual = boxes.get("human_input_research")
        if manual is None:
            absent_n += 1
            continue
        try:
            if counts[(record.get("race_id"), record.get("source"))] != 1:
                raise ValueError("V003_DUPLICATE_RACE_SOURCE")
            if not isinstance(manual, dict) or manual.get("origin") != "HUMAN_MANUAL":
                raise ValueError("V003_MANUAL_ORIGIN_REQUIRED")
            provenance = manual.get("input_provenance")
            active = record.get("active_boats")
            if active is None:
                distributions = record.get("distributions")
                if not isinstance(distributions, dict) or not isinstance(distributions.get("P_model"), dict):
                    raise ValueError("V003_ACTIVE_DOMAIN_UNKNOWN")
                if any(not isinstance(ticket, str) or not re.fullmatch(r"[1-6]-[1-6]-[1-6]", ticket) for ticket in distributions["P_model"]):
                    raise ValueError("V003_ACTIVE_DOMAIN_UNKNOWN")
                active = sorted({int(n) for ticket in distributions["P_model"] for n in ticket.split("-")})
            gate_race = {key: record.get(key) for key in ("race_id", "target_date", "prediction_at", "deadline")}
            gate_race["active_boats"] = active
            gate = validate_human_input(gate_race, provenance)
            if not gate["eligible"] or gate.get("input_sha256") != manual.get("human_input_sha256"):
                raise ValueError("V003_MANUAL_PROVENANCE_HOLD")
            if (manual.get("core") != provenance["core"] or manual.get("insertion") != provenance["insertion"]
                    or not isinstance(manual.get("boats"), list)
                    or set(manual["boats"]) != set(provenance["core"] + [provenance["insertion"]])):
                raise ValueError("V003_MANUAL_COMPOSITION_PROVENANCE_MISMATCH")
            five = record.get("selection")
            tickets = five.get("tickets") if isinstance(five, dict) else None
            if (not isinstance(tickets, list) or len(tickets) != 5
                    or any(not isinstance(ticket, str) or not re.fullmatch(r"[1-6]-[1-6]-[1-6]", ticket) for ticket in tickets)
                    or len(set(tickets)) != 5
                    or manual.get("five_appearance_counts") != {
                        str(boat): sum(str(boat) in ticket.split("-") for ticket in tickets) for boat in active}):
                raise ValueError("V003_MANUAL_NORMAL_FIVE_COUNTS_MISMATCH")
            actual, result = _bound_outcome(record)
            local = _adapt(record)
            local["boxes"]["human_research"] = deepcopy(manual)
            manual_rows.append(_method_observation(local, actual, result, "human_research"))
        except (ValueError, TypeError, KeyError):
            invalid_manual_n += 1
            issues.append({"record_index": index, "component": "human_input_research", "reason": "V003_MANUAL_OBSERVATION_UNVERIFIED"})
    manual_report = _method_report(manual_rows, len(records), config.get("day_bootstrap"))
    if not manual_rows:
        manual_report = _empty_observations(manual_report, "UNVERIFIED_NO_HUMAN_INPUT_OBSERVATIONS")
    manual_report.update(absent_input_n=absent_n, invalid_or_unmatched_input_n=invalid_manual_n,
                         formal_box_v1_reproduction=False, external_origin_authenticity="UNVERIFIED")
    methods["human_input_research"] = manual_report
    methods = {name: methods[name] for name in METHODS_V003}
    return {"schema": "MODEL11_EVALUATION_V003", "status": "OFFLINE_DESCRIPTIVE_RESEARCH_ONLY",
            "input_n": old["input_n"], "matched_final_outcome_n": old["matched_final_outcome_n"],
            "invalid_record_n": old["invalid_record_n"], "record_issues": issues,
            "methods": methods, "distributions": old["distributions"],
            "market_comparisons": old["market_comparisons"],
            "legacy_comparison": {"status": "OPEN", "formal_box_v1_reproduction": "UNVERIFIED_NOT_IMPLEMENTED",
                                  "performance_superiority": "UNVERIFIED"},
            "portfolio_policy": "FIVE_AND_FOUR_BOX_METHODS_SEPARATE_NO_OVERLAP_AGGREGATION",
            "config_status": "PROPOSED", "performance_improvement": "UNVERIFIED_REQUIRES_UNUSED_REAL_FUTURE_DATA",
            "production_go": False}
