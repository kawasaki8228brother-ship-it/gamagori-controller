"""V003 portfolio names distinguish automation from asserted human input.

Old selection arithmetic is reused on detached objects. Formal BOX V1 rules are
neither reproduced nor inferred from these research candidates.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from itertools import combinations
import re

from ..engine import canonical_hash
from ..selection import build_boxes as _old_build_boxes


BOX_METHODS = ("five_appearance_research", "human_input_research", "mechanical_research", "box_v11_research")
_TIMES = ("observed_at", "acquired_at", "available_at", "revision_at", "evidence_recorded_at")
HUMAN_INPUT_FIELDS = frozenset({"race_id", "target_date", "core", "insertion", "origin", "source_id",
                               "evidence_sha256", *_TIMES})


def _stamp(value):
    if (not isinstance(value, str) or value.endswith("-00:00")
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value)):
        raise ValueError("HUMAN_TIMESTAMP_INVALID")
    if value[-6:-5] in ("+", "-") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError("HUMAN_TIMESTAMP_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("HUMAN_TIMESTAMP_INVALID") from None


def validate_human_input(race, human_input):
    """Validate an assertion, not external proof that a person supplied it."""
    base = {"eligible": False, "status": "ABSENT", "errors": [],
            "external_origin_authenticity": "UNVERIFIED", "production_go": False}
    if human_input is None:
        return base
    errors = []
    if not isinstance(race, dict):
        return dict(base, status="HOLD", errors=["HUMAN_RACE_REQUIRED"])
    if not isinstance(human_input, dict) or set(human_input) != HUMAN_INPUT_FIELDS:
        errors.append("HUMAN_INPUT_FIELDS_INVALID")
    else:
        if human_input["origin"] != "HUMAN_MANUAL":
            errors.append("HUMAN_ORIGIN_ASSERTION_REQUIRED")
        if (not isinstance(human_input["source_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", human_input["source_id"])):
            errors.append("HUMAN_SOURCE_REFERENCE_INVALID")
        if (not isinstance(human_input["evidence_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", human_input["evidence_sha256"])):
            errors.append("HUMAN_PREDEADLINE_EVIDENCE_HASH_REQUIRED")
        if any(human_input[key] != race.get(key) for key in ("race_id", "target_date")):
            errors.append("HUMAN_RACE_IDENTITY_MISMATCH")
        core, insertion, active = human_input["core"], human_input["insertion"], race.get("active_boats")
        if (not isinstance(core, list) or len(core) != 2 or any(type(b) is not int for b in core)
                or type(insertion) is not int or not isinstance(active, list)
                or not 3 <= len(active) <= 6 or any(type(b) is not int or not 1 <= b <= 6 for b in active)
                or len(set(active)) != len(active)
                or len(set(core + [insertion])) != 3 or not set(core + [insertion]) <= set(active)):
            errors.append("HUMAN_BOAT_COMPOSITION_INVALID")
        try:
            prediction, deadline = _stamp(race.get("prediction_at")), _stamp(race.get("deadline"))
            times = {name: _stamp(human_input[name]) for name in _TIMES}
            if prediction >= deadline or any(value > prediction or value >= deadline for value in times.values()):
                errors.append("HUMAN_INPUT_NOT_PREDEADLINE_AVAILABLE")
            if times["acquired_at"] > times["available_at"]:
                errors.append("HUMAN_AVAILABILITY_BEFORE_ACQUISITION")
            if times["observed_at"] > times["acquired_at"]:
                errors.append("HUMAN_ACQUISITION_BEFORE_SELECTION")
            if times["available_at"] > times["evidence_recorded_at"]:
                errors.append("HUMAN_EVIDENCE_BEFORE_AVAILABILITY")
            if times["revision_at"] < times["acquired_at"]:
                errors.append("HUMAN_REVISION_BEFORE_ACQUISITION")
            if times["revision_at"] > times["evidence_recorded_at"]:
                errors.append("HUMAN_REVISION_AFTER_EVIDENCE")
            if times["evidence_recorded_at"] < times["observed_at"]:
                errors.append("HUMAN_EVIDENCE_BEFORE_SELECTION")
        except (ValueError, TypeError, KeyError):
            errors.append("HUMAN_TIMESTAMP_INVALID")
    if errors:
        return dict(base, status="HOLD", errors=list(dict.fromkeys(errors)))
    return dict(base, eligible=True, status="LOCAL_ASSERTION_ACCEPTED",
                input_sha256=canonical_hash(human_input), evidence_sha256=human_input["evidence_sha256"])


def build_portfolios(race, dist, five, odds=None, human_input=None, config=None):
    """Always build automatic five-appearance BOX; manual BOX is a separate lane.

    Invalid present manual input returns HOLD/null. The V003 engine must propagate
    that HOLD. Absent input is not silently replaced by any automatic candidate.
    """
    if not isinstance(race, dict):
        raise ValueError("PORTFOLIO_RACE_REQUIRED")
    automatic_race = deepcopy(race)
    automatic_race["human_box_input"] = None  # Never consume the ambiguous old field.
    old = _old_build_boxes(automatic_race, dist, five, odds, config)
    automatic = deepcopy(old["human_research"])
    automatic.pop("manual_status", None)
    automatic.update(method="FIVE_APPEARANCE_CORE_INSERTION_RESEARCH", origin="AUTOMATED_FIVE_APPEARANCES",
                     display_name="Five-appearance research BOX", human_origin=False,
                     status="AUTOMATED_RESEARCH_NOT_FORMAL_HUMAN_BOX")
    mechanical, value_box = deepcopy(old["mechanical_research"]), deepcopy(old["box_v11_research"])
    gate = validate_human_input(race, human_input)
    manual = None
    if gate["eligible"]:
        manual_race = deepcopy(automatic_race)
        manual_race["human_box_input"] = {key: deepcopy(human_input[key])
                                         for key in ("core", "insertion", "observed_at", "acquired_at", "available_at", "revision_at")}
        manual = deepcopy(_old_build_boxes(manual_race, dist, five, odds, config)["human_research"])
        manual.pop("manual_status", None)
        manual.update(method="HUMAN_INPUT_RESEARCH_PREDEADLINE_ASSERTED", origin="HUMAN_MANUAL",
                      display_name="Human-input research BOX", status="ASSERTED_HUMAN_INPUT_NOT_FORMAL_BOX_V1",
                      human_input_sha256=gate["input_sha256"], input_provenance=deepcopy(human_input),
                      external_origin_authenticity="UNVERIFIED")
    outputs = {"five_appearance_research": automatic, "human_input_research": manual,
               "mechanical_research": mechanical, "box_v11_research": value_box}
    available = {name: box for name, box in outputs.items() if box is not None}
    overlaps = {"five_vs_" + name: sorted(set(five["tickets"]) & set(box["tickets"])) for name, box in available.items()}
    for first, second in combinations(available, 2):
        overlaps[first + "_vs_" + second] = sorted(set(available[first]["tickets"]) & set(available[second]["tickets"]))
    all_sets = [set(five["tickets"])] + [set(box["tickets"]) for box in available.values()]
    overlaps["unique_ticket_union"] = sorted(set.union(*all_sets))
    overlaps["aggregation_policy"] = "SEPARATE_METHODS_NO_CROSS_PORTFOLIO_PNL_AGGREGATION"
    outputs.update({
        "composition_difference": {
            "five_appearance_vs_mechanical": "YES" if set(automatic["boats"]) != set(mechanical["boats"]) else "NO",
            "human_input_vs_mechanical": ("YES" if set(manual["boats"]) != set(mechanical["boats"]) else "NO") if manual is not None else None},
        "composition_meaning": "BOAT_SET_EQUALITY_ONLY_NOT_QUALITY_OR_SUPERIORITY",
        "human_input_gate": gate, "canonical_human_box_input_consumed": False,
        "overlap": overlaps, "configuration": deepcopy(old["configuration"]),
        "configuration_status": "PROPOSED_NOT_ADOPTED", "schema": "MODEL11_PORTFOLIOS_V003",
        "formal_box_v1_status": "UNVERIFIED_NOT_REIMPLEMENTED",
        "live_eligible": False, "production_go": False,
    })
    return outputs
