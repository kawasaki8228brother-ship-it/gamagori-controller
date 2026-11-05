"""Sign conventions for preintegration diagnostics; no adopted test or GO.

delta_pilot = champion logloss - market logloss.
d_M0 = market logloss - champion logloss = -delta_pilot.
Positive d_M0 and negative delta_pilot point toward lower champion loss.
"""
from __future__ import annotations
import math
from statistics import stdev


class SignInputError(ValueError):
    pass


def _finite(value):
    if type(value) not in (int, float):
        raise SignInputError("FINITE_REAL_NUMBER_REQUIRED")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise SignInputError("FINITE_REAL_NUMBER_REQUIRED") from None
    if not math.isfinite(number):
        raise SignInputError("FINITE_REAL_NUMBER_REQUIRED")
    if type(value) is int and int(number) != value:
        raise SignInputError("INTEGER_NOT_EXACTLY_REPRESENTABLE")
    return number


def pilot_to_m0(delta_pilot):
    return -_finite(delta_pilot)


def m0_to_pilot(d_m0):
    return -_finite(d_m0)


def convert_paired_day_means(pilot_day_means):
    """Input units are equally weighted paired DAY means, never race reweighting.

    Return summary only. At fewer than two days the sample SD stays None.
    Zero observed sample SD is not proof of zero future variance or adequacy.
    """
    if type(pilot_day_means) not in (list, tuple):
        raise SignInputError("PAIRED_DAY_SEQUENCE_REQUIRED")
    values = [_finite(value) for value in pilot_day_means]
    converted = [-value for value in values]
    try:
        pilot_mean = math.fsum(values) / len(values) if values else None
        d_mean = math.fsum(converted) / len(values) if values else None
        pilot_sd = stdev(values) if len(values) >= 2 else None
        d_sd = stdev(converted) if len(values) >= 2 else None
    except (OverflowError, ValueError):
        raise SignInputError("NUMERICAL_SUMMARY_LIMIT") from None
    if any(value is not None and not math.isfinite(value) for value in (pilot_mean, d_mean, pilot_sd, d_sd)):
        raise SignInputError("NUMERICAL_SUMMARY_LIMIT")
    if pilot_sd != d_sd:
        raise SignInputError("SD_SIGN_INVARIANCE_BROKEN")
    return {"status": "SIGN_TRANSFORM_DIAGNOSTIC_ONLY", "paired_day_clusters": len(values),
        "pilot_mean_model_minus_market": pilot_mean, "d_M0_mean_market_minus_model": d_mean,
        "pilot_sd_day": pilot_sd, "d_M0_sd_day": d_sd, "sd_unchanged": True,
        "sd_status": "UNVERIFIED_FEWER_THAN_TWO_DAYS" if pilot_sd is None else
                     "OBSERVED_ZERO_NOT_ZERO_FUTURE_VARIANCE" if pilot_sd == 0 else "SAMPLE_SD_ASSUMPTIONS_UNVERIFIED",
        "sample_variance_denominator": "K_MINUS_1", "unit": "PAIRED_DAY_MEANS_EQUAL_WEIGHT",
        "pilot_favorable_direction": "NEGATIVE", "M0_favorable_direction": "POSITIVE",
        "actual_test_performed": False, "performance_verdict": "NOT_PROVIDED", "production_go": False}


def convert_pilot_statistics(mean_delta, sd_day, paired_day_count):
    """Transform a supplied numeric summary; do not authenticate or fill it."""
    if type(paired_day_count) is not int or paired_day_count < 0:
        raise SignInputError("PAIRED_DAY_COUNT_INVALID")
    if paired_day_count == 0:
        if mean_delta is not None or sd_day is not None:
            raise SignInputError("EMPTY_SUMMARY_CONTRADICTION")
        return {"pilot_mean": None, "d_M0_mean": None, "pilot_sd_day": None, "d_M0_sd_day": None,
                "paired_day_clusters": 0, "status": "UNVERIFIED_EMPTY_SUMMARY", "production_go": False}
    mean = _finite(mean_delta)
    if paired_day_count < 2:
        if sd_day is not None:
            raise SignInputError("SAMPLE_SD_UNDEFINED_FOR_SINGLE_DAY")
        sd = None
    else:
        sd = _finite(sd_day)
        if sd < 0:
            raise SignInputError("NEGATIVE_SAMPLE_SD")
    return {"pilot_mean": mean, "d_M0_mean": -mean, "pilot_sd_day": sd, "d_M0_sd_day": sd,
            "paired_day_clusters": paired_day_count, "status": "TRANSFORMED_SUMMARY_NOT_INFERENCE",
            "source_summary_authenticity": "UNVERIFIED", "actual_test_performed": False, "production_go": False}


def one_sided_normal_tail_diagnostic(pilot_z):
    """Mathematical tail identity only; no actual holdout z-test or decision.

    Lower-tail P(Z <= z_pilot) equals upper-tail P(Z >= -z_pilot).
    No critical value, effect, sample size, alpha spending or adoption is set.
    """
    pilot = _finite(pilot_z)
    m0 = -pilot
    pilot_lower = 0.5 * math.erfc(-pilot / math.sqrt(2.0))
    m0_upper = 0.5 * math.erfc(m0 / math.sqrt(2.0))
    return {"status": "NORMAL_TAIL_SIGN_IDENTITY_ONLY", "pilot_z": pilot, "d_M0_z": m0,
        "pilot_tail": "LOWER", "M0_tail": "UPPER", "pilot_lower_tail": pilot_lower,
        "M0_upper_tail": m0_upper, "tail_values_equal": pilot_lower == m0_upper,
        "reference_distribution": "STANDARD_NORMAL_IDENTITY_NOT_DAY_CLUSTER_INFERENCE",
        "actual_test_performed": False, "test_pass": None, "production_go": False}
