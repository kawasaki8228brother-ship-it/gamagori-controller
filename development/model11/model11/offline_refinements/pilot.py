"""Private-side pilot aggregation; summary only, no I/O or performance verdict."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import math
import re
from statistics import stdev

ENDPOINT = "JOINT_120_LOGLOSS"
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_REASONS = {"MISSING": {"MODEL_MISSING", "MARKET_MISSING", "BOTH_MISSING"},
            "READ_FAILED": {"MODEL_READ_FAILED", "MARKET_READ_FAILED", "BOTH_READ_FAILED", "SOURCE_READ_FAILED"}}
_REQUIRED = {"race_id", "target_date", "baseline_id", "baseline_version", "model_ll", "market_ll", "state"}
_OPTIONAL = {"missing_reason", "probability_endpoint", "model_id", "model_version"}


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _identity(row):
    race_id, target = row.get("race_id"), row.get("target_date")
    if not isinstance(race_id, str) or not _ID.fullmatch(race_id):
        raise ValueError("RACE_ID_INVALID")
    if not isinstance(target, str) or not _DATE.fullmatch(target):
        raise ValueError("TARGET_DATE_INVALID")
    try:
        date.fromisoformat(target)
    except ValueError:
        raise ValueError("TARGET_DATE_INVALID") from None
    return race_id, target


def _base():
    return {"status": "UNVERIFIED", "reason_codes": [], "sd_day": None,
            "dispersion_status": "UNVERIFIED", "counts": None,
            "missing_rates": {"MISSING": None, "READ_FAILED": None, "NO_OBSERVATION": None, "TOTAL_UNPAIRED": None},
            "missing_reason_counts": None,
            "estimand": "EQUAL_DAY_SAMPLE_SD_OF_WITHIN_DAY_MEAN_MODEL_LL_MINUS_MARKET_LL",
            "sample_variance_denominator": "K_MINUS_1", "logarithm": "NATURAL",
            "paired_eligibility": "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED",
            "baseline_binding": "UNVERIFIED", "roster_completeness": "UNVERIFIED",
            "source_data_authenticity": "UNVERIFIED_SELF_REPORTED_INPUT",
            "losses_origin": "CALLER_SUPPLIED_NOT_RECOMPUTED",
            "pit_and_predeadline_baseline_audit": "UNVERIFIED_EXTERNAL_EVIDENCE_REQUIRED_BEFORE_F5_USE",
            "odds_fallback": "NOT_IMPLEMENTED",
            "day_independence": "UNVERIFIED", "pilot_size_adequacy": "UNVERIFIED_NO_THRESHOLD_ADOPTED",
            "performance_verdict": "NOT_PROVIDED", "power_guarantee": False,
            "f5_adopted": False, "f2_changed": False, "production_go": False}


def summarize_pilot(roster, observations, *, baseline_id, baseline_version,
                    endpoint=ENDPOINT, roster_complete=False, model_id=None, model_version=None):
    """Compute sample SD of equally weighted paired DAY means; return no rows.

    Roster is None or a full planned list of {race_id,target_date}. Its declared
    completeness is distinct from authenticity. Without a declared full roster,
    planned-denominator missing rates stay None, even if every received row pairs.
    Nonpaired rows use MISSING/READ_FAILED with fixed missing_reason codes. No
    observation at all is NO_OBSERVATION, not a source read failure or score zero.
    """
    result = _base()
    try:
        if (not isinstance(baseline_id, str) or not _ID.fullmatch(baseline_id)
                or not isinstance(baseline_version, str) or not _ID.fullmatch(baseline_version)
                or endpoint != ENDPOINT or type(roster_complete) is not bool):
            raise ValueError("BASELINE_ENDPOINT_OR_COMPLETENESS_CONTROL_INVALID")
        if (model_id is None) != (model_version is None):
            raise ValueError("MODEL_BINDING_INCOMPLETE")
        if model_id is not None and any(not isinstance(value, str) or not _ID.fullmatch(value)
                                        for value in (model_id, model_version)):
            raise ValueError("MODEL_BINDING_INVALID")
        if roster is not None and not isinstance(roster, list):
            raise ValueError("ROSTER_NOT_LIST")
        if not isinstance(observations, list):
            raise ValueError("OBSERVATIONS_NOT_LIST")
        planned, seen = {}, {}
        if roster is not None:
            for row in roster:
                if not isinstance(row, dict) or set(row) != {"race_id", "target_date"}:
                    raise ValueError("ROSTER_FIELDS_INVALID")
                identity, target = _identity(row)
                if identity in planned:
                    raise ValueError("ROSTER_RACE_DATE_CONFLICT" if planned[identity] != target else "DUPLICATE_ROSTER_RACE")
                planned[identity] = target
        days, states, reasons = defaultdict(list), Counter(), Counter()
        observed_model_binding, observed_model_presence = None, None
        for row in observations:
            if not isinstance(row, dict) or not _REQUIRED <= set(row) or set(row) - (_REQUIRED | _OPTIONAL):
                raise ValueError("OBSERVATION_FIELDS_INVALID")
            identity, target = _identity(row)
            if identity in seen:
                raise ValueError("OBSERVATION_RACE_DATE_CONFLICT" if seen[identity] != target else "DUPLICATE_OBSERVATION_RACE")
            seen[identity] = target
            if roster is not None and (identity not in planned or planned[identity] != target):
                raise ValueError("OBSERVATION_ROSTER_IDENTITY_MISMATCH")
            if row["baseline_id"] != baseline_id or row["baseline_version"] != baseline_version:
                raise ValueError("BASELINE_ID_OR_VERSION_MISMATCH")
            if row.get("probability_endpoint", endpoint) != endpoint:
                raise ValueError("PROBABILITY_ENDPOINT_MISMATCH")
            supplied_model = (row.get("model_id"), row.get("model_version"))
            if (supplied_model[0] is None) != (supplied_model[1] is None):
                raise ValueError("OBSERVATION_MODEL_BINDING_INCOMPLETE")
            if model_id is not None and supplied_model != (model_id, model_version):
                raise ValueError("MODEL_ID_OR_VERSION_MISMATCH")
            present = supplied_model != (None, None)
            if observed_model_presence is not None and present != observed_model_presence:
                raise ValueError("MIXED_MODEL_BINDING_PRESENCE")
            observed_model_presence = present
            if supplied_model != (None, None):
                if any(not isinstance(value, str) or not _ID.fullmatch(value) for value in supplied_model):
                    raise ValueError("OBSERVATION_MODEL_BINDING_INVALID")
                if observed_model_binding is not None and supplied_model != observed_model_binding:
                    raise ValueError("MIXED_MODEL_ID_OR_VERSION")
                observed_model_binding = supplied_model
            model_ll, market_ll = row["model_ll"], row["market_ll"]
            for value in (model_ll, market_ll):
                if value is not None and (not _number(value) or value < 0):
                    raise ValueError("INVALID_NONFINITE_OR_NEGATIVE_LOGLOSS")
            state, reason = row["state"], row.get("missing_reason")
            if state == "PAIRED":
                if model_ll is None or market_ll is None or reason is not None:
                    raise ValueError("PAIRED_ROW_INCOMPLETE_OR_HAS_MISSING_REASON")
                delta = model_ll-market_ll
                if not _number(delta):
                    raise ValueError("NONFINITE_PAIRED_DIFFERENCE")
                days[target].append(delta)
            elif state in _REASONS:
                if model_ll is not None and market_ll is not None:
                    raise ValueError("NONPAIRED_ROW_CONTAINS_COMPLETE_PAIR")
                if reason not in _REASONS[state]:
                    raise ValueError("MISSING_REASON_UNREGISTERED_OR_STATE_MISMATCH")
                if ((reason.startswith("MODEL_") and model_ll is not None)
                        or (reason.startswith("MARKET_") and market_ll is not None)
                        or (reason.startswith("MODEL_") and market_ll is None)
                        or (reason.startswith("MARKET_") and model_ll is None)
                        or (reason.startswith("BOTH_") and (model_ll is not None or market_ll is not None))):
                    raise ValueError("MISSING_REASON_COMPONENT_CONTRADICTION")
                reasons[reason] += 1
            else:
                raise ValueError("OBSERVATION_STATE_UNREGISTERED")
            states[state] += 1
        means = [math.fsum(values)/len(values) for values in days.values()]
        if any(not _number(value) for value in means):
            raise ValueError("NONFINITE_DAY_MEAN")
        k = len(means)
        sd = stdev(means) if k >= 2 else None
        if sd is not None and not _number(sd):
            raise ValueError("NONFINITE_SAMPLE_SD")
        complete = roster is not None and roster_complete
        no_observation = len(planned)-len(seen) if roster is not None else None
        denominator = len(planned) if complete else None
        if denominator:
            rates = {name: states[name]/denominator for name in _REASONS}
            rates["NO_OBSERVATION"] = no_observation/denominator
            rates["TOTAL_UNPAIRED"] = (denominator-states["PAIRED"])/denominator
        else:
            rates = result["missing_rates"]
        if k < 2:
            result["reason_codes"].append("FEWER_THAN_TWO_PAIRED_DAY_CLUSTERS")
        if not complete:
            result["reason_codes"].append("FULL_PLANNED_ROSTER_COMPLETENESS_UNVERIFIED")
        if denominator == 0:
            result["reason_codes"].append("EMPTY_PLANNED_ROSTER_RATE_UNDEFINED")
        return {**result, "status": "SUMMARY_COMPUTED_UNVERIFIED" if k >= 2 else "UNVERIFIED",
                "sd_day": sd,
                "dispersion_status": "OBSERVED_ZERO_SAMPLE_SD_NOT_ZERO_FUTURE_VARIANCE" if sd == 0 else
                                     "OBSERVED_SAMPLE_SD_DAY_ASSUMPTIONS_UNVERIFIED" if sd is not None else "UNVERIFIED",
                "counts": {"paired_day_clusters": k, "paired_races": states["PAIRED"],
                           "supplied_observation_rows": len(observations),
                           "supplied_roster_rows": len(planned) if roster is not None else None,
                           "planned_race_denominator": denominator,
                           "missing_rows": states["MISSING"], "read_failed_rows": states["READ_FAILED"],
                           "no_observation_rows_in_supplied_roster": no_observation},
                "missing_rates": rates, "missing_reason_counts": dict(sorted(reasons.items())),
                "baseline_binding": "MATCHED_SELF_REPORTED_FIXED_ID_AND_VERSION" if observations else "UNVERIFIED_NO_OBSERVATIONS",
                "model_binding": "MATCHED_SELF_REPORTED_ID_AND_VERSION" if observed_model_binding is not None else "UNVERIFIED_NOT_SUPPLIED",
                "roster_completeness": "DECLARED_FULL_ROSTER_NOT_AUTHENTICATED" if complete else "UNVERIFIED"}
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        # Only internally authored codes are emitted; no submitted value or row.
        code = exc.args[0] if type(exc) is ValueError and exc.args else "PILOT_INPUT_INVALID"
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z_]+", code):
            code = "PILOT_INPUT_INVALID"
        return {**result, "status": "HOLD", "reason_codes": [code], "sd_day": None}
