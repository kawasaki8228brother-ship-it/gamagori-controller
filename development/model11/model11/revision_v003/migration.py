"""Detached schema migration preview. Old forecasts are never rewritten."""
from __future__ import annotations

from copy import deepcopy
import re

from ..engine import canonical_hash, check_distribution, usable_market
from ..validation import validate_race
from .portfolios import build_portfolios


def migrate_v001_prediction(oldforecast, race=None, course_policy=None, human_input=None):
    """Return a HOLD review preview, never a newly generated V003 prediction.

    A legacy model was not trained with the new course-policy binding. Even a
    well-formed schema preview cannot repair that scientific lineage retroactively.
    """
    result = {"schema": "MODEL11_MIGRATION_REVIEW_V003", "status": "HOLD",
              "candidate": None, "reason_codes": [], "old_object_mutated": False,
              "original_raw_bytes": "NOT_RECEIVED_OBJECT_HASH_ONLY",
              "external_authenticity": "UNVERIFIED", "live_eligible": False,
              "requires_new_course_bound_prediction": True, "production_go": False}
    try:
        if not isinstance(oldforecast, dict):
            raise ValueError("OLD_FORECAST_REQUIRED")
        result["original_object_sha256"] = canonical_hash(oldforecast)
        original_digest = canonical_hash({k: v for k, v in oldforecast.items() if k != "prediction_sha256"})
        if (oldforecast.get("prediction_sha256") != original_digest or "actual" in oldforecast
                or oldforecast.get("first_course") is not None):
            raise ValueError("OLD_SEALED_FORECAST_REQUIRED")
        result["original_prediction_sha256"] = original_digest
        old_boxes = oldforecast.get("boxes")
        if not isinstance(old_boxes, dict):
            raise ValueError("OLD_PORTFOLIO_CONTAINER_REQUIRED")
        previous = old_boxes.get("human_research")
        if not isinstance(previous, dict):
            raise ValueError("OLD_AMBIGUOUS_BOX_REQUIRED")
        result["old_ambiguous_component_sha256"] = canonical_hash(previous)
        result["old_ambiguous_origin"] = ("AUTOMATED_FIVE_APPEARANCES" if previous.get("method") == "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH"
                                          else "UNVERIFIED_PREVIOUS_MANUAL_OR_UNKNOWN")
        result["reason_codes"].append("OLD_MODEL_NOT_COURSE_POLICY_BOUND")
        if previous.get("method") != "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH":
            result["reason_codes"].append("OLD_MANUAL_ORIGIN_EVIDENCE_NOT_ACCEPTED")
        if race is None:
            result["reason_codes"].extend(["CANONICAL_RACE_REQUIRED_FOR_PREVIEW", "COURSE_PROVENANCE_UNVERIFIED"])
            return result
        if not isinstance(race, dict) or oldforecast.get("input_sha256") != canonical_hash(race):
            raise ValueError("OLD_FORECAST_RACE_HASH_MISMATCH")
        cfg = oldforecast.get("config")
        if not isinstance(cfg, dict):
            raise ValueError("OLD_CONFIGURATION_REQUIRED")
        gate = validate_race(race, max_odds_age_seconds=cfg.get("max_odds_age_seconds", 120))
        if not gate["eligible"]:
            raise ValueError("CANONICAL_RACE_UNVERIFIED")
        if any(oldforecast.get(key) != race.get(key) for key in ("race_id", "target_date", "prediction_at", "deadline")):
            raise ValueError("OLD_FORECAST_RACE_IDENTITY_MISMATCH")
        if not race.get("course_inputs") or course_policy is None:
            result["reason_codes"].append("COURSE_PROVENANCE_UNVERIFIED")
        else:
            from .course import validate_course
            result["course_gate"] = validate_course(race, course_policy)
            if not result["course_gate"]["eligible"]:
                result["reason_codes"].append("COURSE_PROVENANCE_HOLD")
        stage = oldforecast.get("selection_stage")
        if stage == "P_calibrated":
            dist = oldforecast.get("P_calibrated")
        elif stage == "P_shrunk" and isinstance(oldforecast.get("distributions"), dict):
            dist = oldforecast["distributions"].get("P_shrunk")
        else:
            raise ValueError("OLD_SELECTION_DISTRIBUTION_UNVERIFIED")
        check_distribution(dist, race["active_boats"])
        market = usable_market(race, max_odds_age_seconds=cfg.get("max_odds_age_seconds", 120), gate=gate)
        odds = race["odds_snapshot"]["odds"] if market["P_market"] is not None else None
        portfolios = build_portfolios(race, dist, oldforecast.get("selection"), odds, human_input, cfg.get("selection"))
        if human_input is not None and not portfolios["human_input_gate"]["eligible"]:
            result["reason_codes"].append("NEW_HUMAN_INPUT_HOLD")
        preview = {"schema": "V003_MIGRATION_PREVIEW_NOT_NEW_PREDICTION",
                   "classification": "RESEARCH_MIGRATION_PREVIEW_ONLY", "source_prediction_sha256": original_digest,
                   "source_model_lineage": "V001_OUTPUT_NOT_RETRAINED_OR_COURSE_REBOUND",
                   "race_id": oldforecast["race_id"], "target_date": oldforecast["target_date"],
                   "prediction_at": oldforecast["prediction_at"], "deadline": oldforecast["deadline"],
                   "selection": deepcopy(oldforecast["selection"]), "boxes": portfolios,
                   "config": deepcopy(cfg), "distributions": deepcopy(oldforecast["distributions"]),
                   "P_calibrated": deepcopy(oldforecast.get("P_calibrated")),
                   "config_status": "PROPOSED", "live_eligible": False, "production_go": False}
        preview["migration_preview_sha256"] = canonical_hash(preview)
        result["candidate"] = preview
        result["migration_actions"] = {
            "five_appearance": "RECOMPUTED_FROM_FROZEN_FIVE_ONLY_NO_MODEL_OR_TICKET_RESELECTION",
            "previous_ambiguous_component": "HASH_RETAINED_IN_REVIEW_NO_ACTIVE_LEGACY_LABEL",
            "manual": "SEPARATE_NEW_ASSERTION_ONLY_OLD_FIELD_NEVER_REUSED",
            "mechanical_and_box_v11": "ORIGINAL_ARITHMETIC_KERNEL_UNCHANGED",
            "original_file_or_forecast": "UNCHANGED"}
        return result
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        code = str(exc) if type(exc) is ValueError and re.fullmatch(r"[A-Z_]+", str(exc)) else "MIGRATION_INPUT_UNVERIFIED"
        if code not in result["reason_codes"]:
            result["reason_codes"].append(code)
        return result
