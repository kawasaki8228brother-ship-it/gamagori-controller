"""Fail-closed gates for the synthetic-first Model 1.1 research schema.

This module does not infer missing data, contact a service, reproduce Model 1.0,
or establish that an input's claimed timestamps are independently authentic.
Reports contain fixed machine codes, never submitted values or private paths.
"""

from __future__ import annotations

import copy
import itertools
import math
import re
from datetime import date, datetime, timedelta, timezone


FEATURES = ("st", "turn", "motor", "ability", "exhibition")
STATES = ("course", "fl", "scratched")
JST = timezone(timedelta(hours=9))
_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TICKET = re.compile(r"[1-6]-[1-6]-[1-6]\Z")
_LABEL_TOKENS = {
    "result", "results", "outcome", "outcomes", "payout", "payouts",
    "refund", "refunds", "label", "labels", "actual", "winner", "winners",
}


def _add(items, code):
    if code not in items:
        items.append(code)


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _boat(value):
    return type(value) is int and 1 <= value <= 6


def _text(value):
    if not isinstance(value, str) or not value or len(value) > 256:
        return False
    try:
        value.encode("utf-8", "strict")
    except UnicodeError:
        return False
    return all(ord(char) >= 32 and ord(char) != 127 for char in value)


def _timestamp(value):
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        return None
    if value.endswith("-00:00"):
        return None  # RFC3339 unknown offset is not a measured timezone.
    if value[-6:-5] in ("+", "-"):
        if int(value[-5:-3]) > 23 or int(value[-2:]) > 59:
            return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed if parsed.utcoffset() is not None else None


def _day(value):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _forbidden_key(key):
    if not isinstance(key, str):
        return False
    camel_split = re.sub(r"([a-z])([A-Z])", r"\1_\2", key)
    tokens = set(re.findall(r"[a-z0-9]+", camel_split.lower()))
    flat = "_".join(re.findall(r"[a-z0-9]+", camel_split.lower()))
    # available_at is legitimate per-feature provenance, not itself a label.
    return bool(tokens & _LABEL_TOKENS) or flat == "final"


def _scan(value, labels=True):
    """Inspect a JSON-shaped object without including submitted values in errors."""
    errors = []
    budget = [50000]
    ancestors = set()

    def visit(item, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > 32:
            _add(errors, "INPUT_LIMIT_EXCEEDED")
            return
        if isinstance(item, (dict, list)):
            identity = id(item)
            if identity in ancestors:
                _add(errors, "INPUT_CYCLE")
                return
            ancestors.add(identity)
            if isinstance(item, dict):
                for key, val in item.items():
                    if not isinstance(key, str):
                        _add(errors, "INPUT_KEY_TYPE")
                    else:
                        try:
                            key.encode("utf-8", "strict")
                        except UnicodeError:
                            _add(errors, "INPUT_TEXT_ENCODING")
                        if labels and _forbidden_key(key):
                            _add(errors, "FORBIDDEN_PREDICTOR_FIELD")
                    visit(val, depth + 1)
            else:
                for val in item:
                    visit(val, depth + 1)
            ancestors.remove(identity)
        elif isinstance(item, str):
            try:
                item.encode("utf-8", "strict")
            except UnicodeError:
                _add(errors, "INPUT_TEXT_ENCODING")
        elif type(item) in (int, float):
            if not _number(item):
                _add(errors, "INPUT_NONFINITE")
        elif item is not None and type(item) is not bool:
            _add(errors, "INPUT_VALUE_TYPE")

    visit(value, 0)
    return errors


def _report(errors, warnings, **extra):
    return {
        "eligible": not errors,
        "status": "ELIGIBLE" if not errors else "INELIGIBLE",
        "errors": errors,
        "warnings": warnings,
        **extra,
    }


def _identity(record, errors, prefix=""):
    if not _text(record.get("race_id")):
        _add(errors, prefix + "RACE_ID_INVALID")
    if _day(record.get("target_date")) is None:
        _add(errors, prefix + "TARGET_DATE_INVALID")


def _matching_identity(child, race, codes, prefix):
    for field in ("race_id", "target_date", "venue"):
        if field in child and child[field] != race.get(field):
            _add(codes, prefix + "IDENTITY_MISMATCH")


def _ticket(value):
    return (isinstance(value, str) and _TICKET.fullmatch(value) is not None
            and len(set(value.split("-"))) == 3)


def _market(race, prediction_at, active, max_age, warnings):
    snapshot = race.get("odds_snapshot")
    if snapshot is None:
        _add(warnings, "ODDS_MISSING")
        return "MISSING"
    if not isinstance(snapshot, dict):
        _add(warnings, "ODDS_SHAPE_INVALID")
        return "INVALID"
    problems = []
    _matching_identity(snapshot, race, problems, "ODDS_")
    acquired = _timestamp(snapshot.get("acquired_at"))
    available = _timestamp(snapshot.get("available_at"))
    revised = _timestamp(snapshot.get("revision_at"))
    if acquired is None or available is None or revised is None:
        _add(problems, "ODDS_TIME_INVALID")
    if acquired and available and acquired > available:
        _add(problems, "ODDS_AVAILABILITY_BEFORE_ACQUISITION")
    if acquired and revised and revised < acquired:
        _add(problems, "ODDS_REVISION_BEFORE_ACQUISITION")
    if prediction_at and any(stamp and stamp > prediction_at for stamp in (acquired, available, revised)):
        _add(problems, "ODDS_FUTURE")
    if acquired and prediction_at and (prediction_at - acquired).total_seconds() > max_age:
        _add(problems, "ODDS_STALE")
    odds = snapshot.get("odds")
    domain = {"-".join(map(str, item)) for item in itertools.permutations(active, 3)}
    if not isinstance(odds, dict) or not domain or set(odds) != domain:
        _add(problems, "ODDS_DOMAIN_MISMATCH")
    if isinstance(odds, dict) and any(not _number(value) or value <= 0 for value in odds.values()):
        _add(problems, "ODDS_VALUE_INVALID")
    for code in problems:
        _add(warnings, code)
    if not problems and prediction_at is not None:
        return "AVAILABLE"
    if "ODDS_FUTURE" in problems:
        return "FUTURE"
    if "ODDS_STALE" in problems:
        return "STALE"
    return "INVALID"


def _human_box(race, prediction_at, active, warnings):
    manual = race.get("human_box_input")
    if manual is None:
        return "MISSING"
    problems = []
    if not isinstance(manual, dict):
        _add(warnings, "HUMAN_BOX_SHAPE_INVALID")
        return "INVALID"
    _matching_identity(manual, race, problems, "HUMAN_BOX_")
    core = manual.get("core")
    insertion = manual.get("insertion")
    if (not isinstance(core, list) or len(core) != 2
            or any(not _boat(item) for item in core)
            or not _boat(insertion) or len(set(core + [insertion])) != 3
            or not set(core + [insertion]).issubset(active)):
        _add(problems, "HUMAN_BOX_COMPOSITION_INVALID")
    observed = _timestamp(manual.get("observed_at"))
    times = {"observed_at": observed}
    for field in ("acquired_at", "available_at", "revision_at"):
        times[field] = _timestamp(manual.get(field))
    if any(stamp is None for stamp in times.values()):
        _add(problems, "HUMAN_BOX_TIME_INVALID")
    if prediction_at and any(stamp and stamp > prediction_at for stamp in times.values()):
        _add(problems, "HUMAN_BOX_FUTURE")
    acquired, available = times["acquired_at"], times["available_at"]
    if acquired and available and acquired > available:
        _add(problems, "HUMAN_BOX_AVAILABILITY_BEFORE_ACQUISITION")
    for code in problems:
        _add(warnings, code)
    return "AVAILABLE" if not problems and prediction_at else "INVALID"


def validate_race(race, max_odds_age_seconds=120):
    """Validate pre-deadline features; market failures do not block P_model.

    The reports' market/human flags must also gate consumers of those optional
    inputs. They must never treat malformed odds or a future manual box as valid.
    """
    if not _number(max_odds_age_seconds) or max_odds_age_seconds < 0:
        raise ValueError("ODDS_MAX_AGE_INVALID")
    errors, warnings = [], []
    if not isinstance(race, dict):
        return _report(["RACE_SHAPE_INVALID"], [], market_status="INVALID", market_available=False,
                       human_box_status="INVALID")
    errors.extend(_scan(race))
    _identity(race, errors)
    if race.get("venue") != "GAMAGORI":
        _add(errors, "VENUE_INVALID")
    prediction = _timestamp(race.get("prediction_at"))
    deadline = _timestamp(race.get("deadline"))
    if prediction is None:
        _add(errors, "PREDICTION_TIME_INVALID")
    if deadline is None:
        _add(errors, "DEADLINE_INVALID")
    if prediction and deadline and prediction >= deadline:
        _add(errors, "PREDICTION_NOT_BEFORE_DEADLINE")
    target = _day(race.get("target_date"))
    if deadline and target and deadline.astimezone(JST).date() != target:
        _add(errors, "RACE_DATE_MISMATCH")
    raw_active = race.get("active_boats")
    valid_active = (isinstance(raw_active, list) and 3 <= len(raw_active) <= 6
                    and all(_boat(item) for item in raw_active)
                    and len(set(raw_active)) == len(raw_active))
    active = raw_active if valid_active else []
    if not valid_active:
        _add(errors, "ACTIVE_BOATS_INVALID")
    if len(active) < 6 and active:
        _add(warnings, "REDUCED_FIELD_RESEARCH_ONLY")
    records = race.get("boats")
    seen, courses = set(), set()
    if not isinstance(records, list) or not 3 <= len(records) <= 6:
        _add(errors, "BOATS_SHAPE_INVALID")
        records = []
    for record in records:
        if not isinstance(record, dict):
            _add(errors, "BOAT_SHAPE_INVALID")
            continue
        number = record.get("boat")
        if not _boat(number):
            _add(errors, "BOAT_ID_INVALID")
            continue
        if number in seen:
            _add(errors, "BOAT_DUPLICATE")
        seen.add(number)
        _matching_identity(record, race, errors, "BOAT_")
        course = record.get("course")
        if not _boat(course):
            _add(errors, "COURSE_INVALID")
        elif number in active:
            if course in courses:
                _add(errors, "COURSE_DUPLICATE")
            courses.add(course)
        if type(record.get("scratched")) is not bool:
            _add(errors, "SCRATCH_STATUS_UNKNOWN")
        elif (number in active and record["scratched"]) or (number not in active and not record["scratched"]):
            _add(errors, "SCRATCH_ACTIVE_MISMATCH")
        if type(record.get("fl")) is not bool:
            _add(errors, "FL_STATUS_UNKNOWN")
        elif number in active and record["fl"]:
            _add(warnings, "FL_PRESENT_RESEARCH_INPUT")
        state_times = record.get("state_times")
        if not isinstance(state_times, dict):
            _add(errors, "STATE_PROVENANCE_MISSING")
        else:
            for name in STATES:
                provenance = state_times.get(name)
                if not isinstance(provenance, dict):
                    _add(errors, "STATE_PROVENANCE_MISSING")
                    continue
                times = {}
                for field in ("acquired_at", "available_at", "revision_at"):
                    stamp = _timestamp(provenance.get(field))
                    times[field] = stamp
                    if stamp is None:
                        _add(errors, "STATE_PROVENANCE_TIME_INVALID")
                    elif prediction and stamp > prediction:
                        _add(errors, "STATE_PROVENANCE_FUTURE")
                acquired, available = times["acquired_at"], times["available_at"]
                if acquired and available and acquired > available:
                    _add(errors, "STATE_AVAILABILITY_BEFORE_ACQUISITION")
        if number not in active:
            continue
        features = record.get("features")
        if not isinstance(features, dict):
            _add(errors, "FEATURES_MISSING")
        else:
            for name in FEATURES:
                if name not in features or features[name] is None:
                    _add(errors, "EXHIBITION_MISSING" if name == "exhibition" else "FEATURE_MISSING")
                elif not _number(features[name]) or not -1 <= features[name] <= 1:
                    _add(errors, "FEATURE_VALUE_INVALID")
            if set(features) - set(FEATURES):
                _add(errors, "FEATURE_NAME_UNREGISTERED")
        feature_times = record.get("feature_times")
        if not isinstance(feature_times, dict):
            _add(errors, "FEATURE_PROVENANCE_MISSING")
        else:
            for name in FEATURES:
                provenance = feature_times.get(name)
                if not isinstance(provenance, dict):
                    _add(errors, "FEATURE_PROVENANCE_MISSING")
                    continue
                times = {}
                for field in ("acquired_at", "available_at", "revision_at"):
                    stamp = _timestamp(provenance.get(field))
                    times[field] = stamp
                    if stamp is None:
                        _add(errors, "FEATURE_PROVENANCE_TIME_INVALID")
                    elif prediction and stamp > prediction:
                        _add(errors, "FEATURE_PROVENANCE_FUTURE")
                acquired, available = times["acquired_at"], times["available_at"]
                if acquired and available and acquired > available:
                    _add(errors, "FEATURE_AVAILABILITY_BEFORE_ACQUISITION")
        stamps = {}
        for field in ("observed_at", "motor_updated_at", "revision_at"):
            stamp = _timestamp(record.get(field))
            stamps[field] = stamp
            if stamp is None:
                _add(errors, "FEATURE_TIME_INVALID")
            elif prediction and stamp > prediction:
                _add(errors, "FEATURE_FUTURE")
        observed, motor = stamps["observed_at"], stamps["motor_updated_at"]
        if observed and motor and motor > observed:
            _add(errors, "MOTOR_UPDATE_AFTER_OBSERVATION")
        if stamps["revision_at"] and observed and stamps["revision_at"] < observed:
            _add(errors, "REVISION_BEFORE_OBSERVATION")
        for field in ("course_updated_at", "scratch_updated_at", "fl_updated_at"):
            if field in record:
                stamp = _timestamp(record[field])
                if stamp is None:
                    _add(errors, "STATUS_TIME_INVALID")
                elif prediction and stamp > prediction:
                    _add(errors, "STATUS_FUTURE")
    if set(active) - seen:
        _add(errors, "ACTIVE_BOAT_MISSING")
    market = _market(race, prediction, active, max_odds_age_seconds, warnings)
    human = _human_box(race, prediction, active, warnings)
    return _report(errors, warnings, market_status=market, market_available=market == "AVAILABLE",
                   human_box_status=human, legacy_profile_status="UNVERIFIED")


def prediction_view(record):
    """Copy a JSON-shaped predictor input; never remove labels to disguise a leak.

    Race eligibility must still be checked by validate_race. Optional unavailable
    market/manual data remain visible for that validator rather than being used.
    """
    if not isinstance(record, dict):
        raise ValueError("RACE_SHAPE_INVALID")
    errors = _scan(record)
    if errors:
        raise ValueError(errors[0])
    return copy.deepcopy(record)


def validate_outcome(outcome):
    """Validate a separately held final label; training also needs a cutoff gate."""
    if not isinstance(outcome, dict):
        return _report(["OUTCOME_SHAPE_INVALID"], [])
    errors, warnings = _scan(outcome, labels=False), []
    _identity(outcome, errors)
    result = outcome.get("result")
    if (not isinstance(result, list) or len(result) != 3
            or not all(_boat(item) for item in result) or len(set(result)) != 3):
        _add(errors, "OUTCOME_RESULT_INVALID")
    payout = outcome.get("payout_per_100")
    if not _number(payout) or payout < 0:
        _add(errors, "OUTCOME_PAYOUT_INVALID")
    refunds = outcome.get("refund_tickets")
    if (not isinstance(refunds, list) or any(not _ticket(item) for item in refunds)
            or len(set(refunds)) != len(refunds)):
        _add(errors, "OUTCOME_REFUNDS_INVALID")
    if type(outcome.get("final")) is not bool:
        _add(errors, "OUTCOME_FINAL_STATUS_UNKNOWN")
    elif not outcome["final"]:
        _add(errors, "OUTCOME_NOT_FINAL")
    if _timestamp(outcome.get("available_at")) is None:
        _add(errors, "OUTCOME_AVAILABILITY_INVALID")
    return _report(errors, warnings)


def validate_dataset(races, outcomes):
    """Validate snapshots and separate labels, duplicate keys and join identity.

    Missing labels are explicit warnings; orphan/contradictory labels are errors.
    This is not a train/test splitter, nor proof of provenance or completeness.
    """
    if not isinstance(races, list) or not isinstance(outcomes, list):
        return _report(["DATASET_SHAPE_INVALID"], [], race_reports=[], outcome_reports=[])
    errors, warnings, race_reports, outcome_reports = [], [], [], []
    by_race, by_outcome = {}, {}
    for race in races:
        report = validate_race(race)
        race_reports.append(report)
        if not report["eligible"]:
            _add(errors, "DATASET_RACE_INVALID")
        if isinstance(race, dict) and _text(race.get("race_id")):
            key = race["race_id"]
            if key in by_race:
                _add(errors, "DUPLICATE_RACE_ID")
            by_race[key] = race
    for outcome in outcomes:
        report = validate_outcome(outcome)
        outcome_reports.append(report)
        if not report["eligible"]:
            _add(errors, "DATASET_OUTCOME_INVALID")
        if isinstance(outcome, dict) and _text(outcome.get("race_id")):
            key = outcome["race_id"]
            if key in by_outcome:
                _add(errors, "DUPLICATE_OUTCOME_ID")
            by_outcome[key] = outcome
    for key, outcome in by_outcome.items():
        race = by_race.get(key)
        if race is None:
            _add(errors, "OUTCOME_WITHOUT_RACE")
            continue
        if outcome.get("target_date") != race.get("target_date"):
            _add(errors, "OUTCOME_DATE_MISMATCH")
        if "venue" in outcome and outcome["venue"] != race.get("venue"):
            _add(errors, "OUTCOME_VENUE_MISMATCH")
        result, active = outcome.get("result"), race.get("active_boats")
        if (isinstance(result, list) and isinstance(active, list)
                and all(_boat(item) for item in result + active)
                and not set(result).issubset(active)):
            _add(errors, "OUTCOME_INACTIVE_BOAT")
        available = _timestamp(outcome.get("available_at"))
        deadline = _timestamp(race.get("deadline"))
        if available and deadline and available < deadline:
            _add(errors, "OUTCOME_AVAILABLE_BEFORE_DEADLINE")
    if set(by_race) - set(by_outcome):
        _add(warnings, "OUTCOME_MISSING")
    if not races:
        _add(warnings, "DATASET_EMPTY")
    return _report(errors, warnings, race_reports=race_reports, outcome_reports=outcome_reports,
                   race_count=len(races), outcome_count=len(outcomes), legacy_profile_status="UNVERIFIED")
