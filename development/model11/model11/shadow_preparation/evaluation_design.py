"""PROPOSED F5 arithmetic only. No data fitting, gate adoption, I/O or GO."""
from __future__ import annotations

from copy import deepcopy
import math
from statistics import NormalDist


CURRENT_GRID = {"candidates": ["hierarchical", "contextual"], "alphas": [0.0, 0.5],
                "temperatures": [0.8, 1.0, 1.2], "market_weights": [0, .25, .5, .75, .9, 1.0]}


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def grid_accounting(candidates, alphas, temperatures, market_weights):
    """Count structural w=1 equivalence, never infer independent hypotheses."""
    supplied = {"candidates": candidates, "alphas": alphas,
                "temperatures": temperatures, "market_weights": market_weights}
    for name, values in supplied.items():
        if not isinstance(values, list) or not values:
            raise ValueError("NONEMPTY_GRID_LIST_REQUIRED")
        if name == "candidates":
            if any(value not in ("hierarchical", "contextual") for value in values):
                raise ValueError("UNREGISTERED_MODEL_CANDIDATE")
        else:
            if any(not _number(value) or value < 0 or (name == "temperatures" and value <= 0)
                   or (name != "temperatures" and value > 1) for value in values):
                raise ValueError("INVALID_GRID_VALUE")
        if len(set(values)) != len(values):
            raise ValueError("DUPLICATE_GRID_VALUE")
    base = len(candidates)*len(alphas)*len(temperatures)
    nominal = base*len(market_weights)
    pure_market_members = base if 1 in market_weights else 0
    upper = nominal-pure_market_members+int(pure_market_members > 0)
    return {"status": "PROPOSED_ARITHMETIC_ONLY", "adopted": False,
            "nominal_grid_members": nominal, "market_only_nominal_members": pure_market_members,
            "market_only_structural_classes": int(pure_market_members > 0),
            "structural_probability_upper_bound": upper,
            "independent_hypothesis_count": None,
            "equivalence_caveat": "OTHER_EQUAL_VECTORS_MAY_EXIST_NOT_INDEPENDENT_TEST_COUNTS",
            "production_go": False}


def multiplicity_plan(alpha=0.025, comparisons=1):
    """Illustrative union bound / Holm endpoints, not tests or adopted levels."""
    if not _number(alpha) or not 0 < alpha < .5 or type(comparisons) is not int or comparisons < 1:
        raise ValueError("INVALID_MULTIPLICITY_CONTROLS")
    try:
        per_test = alpha/comparisons
        if per_test <= 0 or not math.isfinite(per_test):
            raise ValueError("NUMERICAL_MULTIPLICITY_LIMIT")
        unadjusted_bound = min(1.0, alpha*comparisons)
    except OverflowError:
        raise ValueError("NUMERICAL_MULTIPLICITY_LIMIT") from None
    return {"status": "PROPOSED_NOT_ADOPTED", "adopted": False,
            "family_alpha": alpha, "comparisons": comparisons,
            "bonferroni_per_test_alpha": per_test,
            "holm_first_rank_alpha": per_test, "holm_last_rank_alpha": alpha,
            "uncorrected_union_bound_if_each_uses_family_alpha": unadjusted_bound,
            "bonferroni_union_bound": min(1.0, per_test*comparisons),
            "assumptions": "VALID_COMPONENT_TESTS_REQUIRED_INDEPENDENCE_NOT_REQUIRED_FOR_UNION_BOUND",
            "actual_tests_performed": False, "production_go": False}


def illustrative_sample_days(sd_day, effect=.02, power=.8, alpha=.025,
                             comparisons=1, design_effect=1.0, planned_days=None):
    """Paired-day normal approximation under explicit UNVALIDATED assumptions.

    n=ceil(((z(1-alpha/m)+z(power))*sd_day/effect)^2 * design_effect).
    design_effect is a caller's illustrative variance multiplier, not estimated
    from races, a proven correction for serial dependence, or a formal threshold.
    """
    base = {"status": "UNVERIFIED", "assumptions": "ASSUMPTIONS_NOT_VALIDATED",
            "adopted": False, "estimated_days": None, "unit": "PAIRED_DAY_CLUSTERS_NOT_RACES",
            "power_guarantee": False, "production_go": False, "reason": None}
    if (not _number(effect) or effect <= 0 or not _number(power) or not .5 < power < 1
            or not _number(alpha) or not 0 < alpha < .5
            or type(comparisons) is not int or comparisons < 1
            or not _number(design_effect) or design_effect < 1
            or (planned_days is not None and (type(planned_days) is not int or planned_days < 1))):
        return {**base, "status": "STOP", "reason": "INVALID_ILLUSTRATIVE_CONTROLS"}
    if sd_day is None or (_number(sd_day) and sd_day == 0):
        return {**base, "reason": "PILOT_DAY_VARIANCE_UNKNOWN_OR_ZERO"}
    if not _number(sd_day) or sd_day < 0:
        return {**base, "status": "STOP", "reason": "INVALID_PILOT_DAY_STANDARD_DEVIATION"}
    try:
        adjusted = alpha/comparisons
        z = NormalDist().inv_cdf(1-adjusted)+NormalDist().inv_cdf(power)
        unrounded = ((z*sd_day/effect)**2)*design_effect
        if not math.isfinite(unrounded):
            raise ValueError("NONFINITE_PLANNING")
        days = max(2, math.ceil(unrounded))
    except (ValueError, OverflowError, ZeroDivisionError):
        return {**base, "status": "STOP", "reason": "NUMERICAL_ILLUSTRATIVE_LIMIT"}
    return {**base, "status": "PROPOSED_ILLUSTRATION", "estimated_days": days,
            "unrounded_days": unrounded, "sd_day": sd_day, "effect": effect,
            "power": power, "alpha": alpha, "comparisons": comparisons,
            "planning_alpha": adjusted, "design_effect": design_effect,
            "planned_days": planned_days,
            "arithmetic_shortfall_days": max(0, days-planned_days) if planned_days is not None else None,
            "adequacy": "UNVERIFIED_EVEN_IF_PLANNED_DAYS_EXCEED_ARITHMETIC",
            "variance_authenticity": "NOT_VERIFIED_NO_PRIVATE_PILOT_RECEIVED"}


def proposed_options():
    """Numerical choices for human review, never a replacement execution config."""
    weights = list(CURRENT_GRID["market_weights"])
    alternatives = [
        {"option_id": "A_REDUCED_FIXED_CALIBRATION", "selection_target_days": 24,
         "holdout_target_days_illustrative": 60,
         "grid": {"candidates": ["hierarchical"], "alphas": [.5],
                  "temperatures": [1.0], "market_weights": list(weights)},
         "justification": "FEWER_RESEARCH_CHOICES_PRESERVE_ALL_SIX_MARKET_WEIGHTS"},
        {"option_id": "B_TWO_MODELS_FIXED_CALIBRATION", "selection_target_days": 36,
         "holdout_target_days_illustrative": 90,
         "grid": {"candidates": ["hierarchical", "contextual"], "alphas": [.5],
                  "temperatures": [1.0], "market_weights": list(weights)},
         "justification": "COMPARE_TWO_CONDITIONAL_STRUCTURES_WITHOUT_ALPHA_TEMPERATURE_SEARCH"},
        {"option_id": "C_CURRENT_FULL_GRID", "selection_target_days": 60,
         "holdout_target_days_illustrative": 120, "grid": deepcopy(CURRENT_GRID),
         "justification": "LARGER_EXPLORATORY_BUDGET_NOT_PROOF_OF_SELECTION_ADEQUACY"},
    ]
    for item in alternatives:
        item.update(status="PROPOSED_NOT_ADOPTED", adopted=False,
                    accounting=grid_accounting(**item["grid"]),
                    formal_selection_minimum="UNVERIFIED_NOT_SET",
                    formal_holdout_required_days="UNVERIFIED_PRIVATE_PILOT_AND_REVIEW_REQUIRED",
                    default_execution_grid_changed=False, production_go=False)
        item["confirmatory_family_proposal"] = "SINGLE_FROZEN_CHAMPION_VS_MARKET_M1"
        item["nonbaseline_structural_comparison_upper_bound"] = item["accounting"]["structural_probability_upper_bound"]-1
    return {"status": "REVIEW_ALTERNATIVES_ONLY", "adopted": False,
            "alternatives": alternatives, "actual_grid_unchanged": True,
            "decision_authorities": ["HQ14", "CLAUDE", "ANDY"], "production_go": False}
