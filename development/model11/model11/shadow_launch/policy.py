"""Pure launch-context gates. No filesystem, network, clock or startup I/O.

An allowed preflight is a structural consistency result, never independently
authenticated approval, actual execution GO, production GO, or auto-start.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import re

NAMESPACE = "MODEL11_THIRD_RESEARCH"
OPERATION = "START_THIRD_RESEARCH_SHADOW"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")
_SETTINGS = {"enabled", "mode", "namespace", "storage_root", "code_commit",
             "input_classification", "storage_identity", "pinned_config_sha256", "pinned_storage_sha256"}
_PINS = {"pinned_config_sha256", "pinned_storage_sha256"}
_CORE = ("model", "normalizer", "source_mapping", "course_policy", "prediction_config")
_PRIVATE = ("evaluation_plan", "formal_legacy_comparison")
_AUTHORITIES = ("HQ14", "CLAUDE", "ANDY")


def _hash(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("NONCANONICAL_CONTEXT") from None
    return hashlib.sha256(raw).hexdigest()


def _hex(value):
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _timestamp(value):
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("AWARE_CLOCK_REQUIRED")
        return value
    if not isinstance(value, str) or not _TIME.fullmatch(value) or value.endswith("-00:00"):
        raise ValueError("AWARE_TIME_REQUIRED")
    # fromisoformat normalizes e.g. +08:60 to +09:00. Such malformed source
    # offsets must fail before parsing, even if the resulting instant matches.
    if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError("AWARE_TIME_REQUIRED")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("AWARE_TIME_REQUIRED") from None
    if result.utcoffset() is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    return result


def _root(value):
    # Lexical check only. No resolve/stat/is_dir/open/ownership claim here.
    return (isinstance(value, str) and value.startswith("/") and value != "/"
            and not value.endswith("/") and "//" not in value and "\\" not in value
            and all(ord(c) >= 32 and ord(c) != 127 for c in value)
            and all(part not in {".", ".."} for part in value.split("/")))


def _disabled(settings):
    return (settings is None or (isinstance(settings, dict)
            and ("enabled" not in settings or settings["enabled"] is False)))


def settings_fingerprints(settings):
    """Pure hashes for explicit caller pinning; never writes or grants approval."""
    if not isinstance(settings, dict) or not (_SETTINGS - _PINS) <= set(settings):
        raise ValueError("SETTINGS_CONTEXT_INCOMPLETE")
    if set(settings) - _SETTINGS:
        raise ValueError("SETTINGS_FIELDS_UNREGISTERED")
    config = {key: deepcopy(settings[key]) for key in sorted(_SETTINGS - _PINS)}
    storage = {key: deepcopy(settings[key]) for key in ("namespace", "storage_root", "storage_identity")}
    return {"config_sha256": _hash(config), "storage_identity_sha256": _hash(storage)}


def artifact_fingerprints(artifacts, mode="SIMULATION"):
    if mode not in ("SIMULATION", "PRIVATE_SHADOW") or not isinstance(artifacts, dict):
        raise ValueError("ARTIFACT_CONTEXT_INVALID")
    names = _CORE + (_PRIVATE if mode == "PRIVATE_SHADOW" else ())
    if any(not isinstance(artifacts.get(name), dict) or (name != "prediction_config" and not artifacts[name]) for name in names):
        raise ValueError("REQUIRED_ARTIFACT_MISSING")
    return {name: _hash(artifacts[name]) for name in names}


def validate_settings(settings):
    """Default OFF; disabled templates may retain null, unknown launch inputs."""
    if settings is None:
        return {"valid": True, "status": "DISABLED", "reasons": [], "enabled": False}
    if not isinstance(settings, dict):
        return {"valid": False, "status": "HOLD", "reasons": ["SETTINGS_NOT_OBJECT"], "enabled": False}
    reasons = []
    if set(settings) - _SETTINGS:
        reasons.append("SETTINGS_FIELDS_UNREGISTERED")
    if "enabled" in settings and type(settings["enabled"]) is not bool:
        reasons.append("ENABLED_MUST_BE_EXPLICIT_BOOLEAN")
    if _disabled(settings):
        return {"valid": not reasons, "status": "HOLD" if reasons else "DISABLED",
                "reasons": reasons, "enabled": False}
    if set(settings) != _SETTINGS:
        reasons.append("SETTINGS_FIELDS_MISSING")
    if settings.get("mode") not in ("SIMULATION", "PRIVATE_SHADOW"):
        reasons.append("MODE_UNREGISTERED")
    if settings.get("namespace") != NAMESPACE:
        reasons.append("INDEPENDENT_NAMESPACE_REQUIRED")
    if not _root(settings.get("storage_root")):
        reasons.append("DEDICATED_ABSOLUTE_STORAGE_ROOT_REQUIRED")
    if not _identifier(settings.get("storage_identity")):
        reasons.append("STORAGE_IDENTITY_REQUIRED")
    commit = settings.get("code_commit")
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        reasons.append("CODE_COMMIT_REQUIRED")
    expected = "SYNTHETIC_ONLY" if settings.get("mode") == "SIMULATION" else "HQ14_PRIVATE_OFFLINE"
    if settings.get("input_classification") != expected:
        reasons.append("INPUT_CLASSIFICATION_MODE_MISMATCH")
    if any(not _hex(settings.get(key)) for key in _PINS):
        reasons.append("EXPLICIT_CONFIG_AND_STORAGE_PINS_REQUIRED")
    if not reasons:
        fingerprints = settings_fingerprints(settings)
        if settings["pinned_config_sha256"] != fingerprints["config_sha256"]:
            reasons.append("CONFIG_PIN_MISMATCH")
        if settings["pinned_storage_sha256"] != fingerprints["storage_identity_sha256"]:
            reasons.append("STORAGE_PIN_MISMATCH")
    return {"valid": not reasons, "status": "VALID_SETTINGS" if not reasons else "HOLD",
            "reasons": reasons, "enabled": settings.get("enabled") is True}


def _artifact_time_errors(artifacts, fingerprints, now):
    reasons = []
    model, normalizer = artifacts["model"], artifacts["normalizer"]
    if (model.get("schema_version") != "COURSE_BOUND_MODEL_V001"
            or model.get("course_policy") != artifacts["course_policy"]
            or model.get("course_policy_sha256") != fingerprints["course_policy"]
            or model.get("training_policy_sha256") != fingerprints["course_policy"]):
        reasons.append("MODEL_COURSE_POLICY_BINDING_INVALID")
    if model.get("self_sha256") != _hash({k: v for k, v in model.items() if k != "self_sha256"}):
        reasons.append("MODEL_SELF_HASH_MISMATCH")
    base = model.get("base_model")
    if not isinstance(base, dict) or type(base.get("training_count")) is not int or base["training_count"] <= 0:
        reasons.append("FITTED_MODEL_REQUIRED")
    else:
        for field in ("training_max_available_at", "training_max_prediction_at"):
            try:
                if _timestamp(base.get(field)) >= now:
                    reasons.append("MODEL_TRAINING_NOT_BEFORE_CLOCK")
            except ValueError:
                reasons.append("MODEL_TRAINING_TIME_UNKNOWN")
    if normalizer.get("schema_version") != "NORMALIZER_V001" or normalizer.get("status") != "PROPOSED":
        reasons.append("NORMALIZER_METADATA_INVALID")
    if normalizer.get("normalizer_sha256") != _hash({k: v for k, v in normalizer.items() if k != "normalizer_sha256"}):
        reasons.append("NORMALIZER_SELF_HASH_MISMATCH")
    try:
        cutoff = _timestamp(normalizer.get("fit_cutoff"))
        available = _timestamp(normalizer.get("training_max_available_at"))
        predicted = _timestamp(normalizer.get("training_max_prediction_at"))
        if not available < cutoff < now or not predicted < cutoff:
            reasons.append("NORMALIZER_FIT_NOT_BEFORE_CLOCK")
    except ValueError:
        reasons.append("NORMALIZER_TRAINING_TIME_UNKNOWN")
    config = artifacts["prediction_config"]
    if set(config) - {"temperature", "market_weight", "selection", "max_odds_age_seconds"}:
        reasons.append("PREDICTION_CONFIG_UNREGISTERED_FIELDS")
    for key in ("temperature", "market_weight", "max_odds_age_seconds"):
        if key not in config:
            continue
        value = config[key]
        # Hash canonicalization already rejects NaN/inf. Avoid bool-as-number.
        if (not _finite(value) or value < 0
                or (key == "temperature" and value == 0)
                or (key == "market_weight" and value > 1)):
            reasons.append("PREDICTION_CONFIG_VALUE_INVALID")
    if "selection" in config and not isinstance(config["selection"], dict):
        reasons.append("PREDICTION_SELECTION_CONFIG_INVALID")
    return reasons


def _bindings(settings, artifacts_sha, settings_sha):
    return {**{name + "_sha256": artifacts_sha[name] for name in _CORE + _PRIVATE},
            "config_sha256": settings_sha["config_sha256"],
            "storage_identity_sha256": settings_sha["storage_identity_sha256"],
            "code_commit": settings["code_commit"]}


def _approval_errors(bundle, ack, expected_bindings, now):
    reasons = []
    required = {"operation", "operator_id", "valid_from", "valid_until", "bindings",
                "reviews", "review_truth_attested_by_operator"}
    if not isinstance(bundle, dict) or set(bundle) != required:
        return ["BOUND_APPROVAL_BUNDLE_REQUIRED"]
    if (bundle["operation"] != OPERATION or not _identifier(bundle["operator_id"])
            or bundle["review_truth_attested_by_operator"] is not True
            or bundle["bindings"] != expected_bindings):
        reasons.append("APPROVAL_OPERATION_OPERATOR_OR_BINDINGS_INVALID")
    try:
        start, end = _timestamp(bundle["valid_from"]), _timestamp(bundle["valid_until"])
        if not start <= now < end:
            reasons.append("APPROVAL_NOT_CURRENT")
    except ValueError:
        reasons.append("APPROVAL_TIME_INVALID")
        start = end = None
    binding_hash = _hash(expected_bindings)
    reviews = bundle.get("reviews")
    review_fields = {"authority", "reviewer_id", "evidence_sha256", "decision", "operation",
                     "bindings_sha256", "valid_from", "valid_until"}
    identities, evidence, review_starts = [], [], []
    if not isinstance(reviews, dict) or set(reviews) != set(_AUTHORITIES):
        reasons.append("ALL_THREE_AUTHORITY_REVIEWS_REQUIRED")
    else:
        for authority in _AUTHORITIES:
            review = reviews[authority]
            if not isinstance(review, dict) or set(review) != review_fields:
                reasons.append("REVIEW_FIELDS_INVALID")
                continue
            if (review["authority"] != authority or not _identifier(review["reviewer_id"])
                    or not _hex(review["evidence_sha256"])
                    or review["decision"] != "APPROVED_FOR_THIRD_RESEARCH_SHADOW"
                    or review["operation"] != OPERATION or review["bindings_sha256"] != binding_hash):
                reasons.append("REVIEW_IDENTITY_DECISION_OR_BINDING_INVALID")
            else:
                identities.append(review["reviewer_id"])
                evidence.append(review["evidence_sha256"])
            try:
                review_start = _timestamp(review["valid_from"])
                review_starts.append(review_start)
                if not review_start <= now < _timestamp(review["valid_until"]):
                    reasons.append("REVIEW_NOT_CURRENT")
            except ValueError:
                reasons.append("REVIEW_TIME_INVALID")
        if len(set(identities)) != len(identities) or len(set(evidence)) != len(evidence):
            reasons.append("DISTINCT_REVIEW_IDENTITIES_AND_EVIDENCE_REQUIRED")
    ack_fields = {"ack", "operator_id", "bindings_sha256", "attested_at", "evidence_checked_outside_this_program"}
    if not isinstance(ack, dict) or set(ack) != ack_fields:
        reasons.append("EXPLICIT_IDENTITY_BOUND_OPERATOR_ACK_REQUIRED")
    else:
        if (ack["ack"] != OPERATION or ack["operator_id"] != bundle["operator_id"]
                or ack["bindings_sha256"] != binding_hash
                or ack["evidence_checked_outside_this_program"] is not True):
            reasons.append("OPERATOR_ACK_BINDING_OR_ATTESTATION_INVALID")
        try:
            attested = _timestamp(ack["attested_at"])
            if start is None or end is None or not start <= attested <= now or not attested < end:
                reasons.append("OPERATOR_ACK_TIME_INVALID")
            if review_starts and attested < max(review_starts):
                reasons.append("OPERATOR_ACK_PREDATES_REVIEW_VALIDITY")
        except ValueError:
            reasons.append("OPERATOR_ACK_TIME_INVALID")
    return reasons


def preflight(settings, artifacts, operator_ack=None, now=None):
    """No I/O ever. Default DISABLED short-circuits before context inspection."""
    base = {"allowed": False, "status": "HOLD", "reasons": [], "production_go": False,
            "independent_approval_authenticity": "UNVERIFIED_NOT_AUTHENTICATED_BY_CODE",
            "actual_execution_go": "NOT_ESTABLISHED_BY_PREFLIGHT",
            "auto_start": False, "filesystem_initialized": False}
    if _disabled(settings):
        return {**base, "status": "DISABLED", "reasons": ["SHADOW_DISABLED"]}
    report = validate_settings(settings)
    if not report["valid"]:
        return {**base, "reasons": report["reasons"]}
    try:
        clock = _timestamp(now)
    except (ValueError, TypeError):
        return {**base, "reasons": ["EXPLICIT_AWARE_CLOCK_REQUIRED"]}
    try:
        fingerprints = artifact_fingerprints(artifacts, settings["mode"])
        declared = artifacts.get("artifact_sha256s")
        if not isinstance(declared, dict) or declared != fingerprints:
            return {**base, "reasons": ["EXPLICIT_ARTIFACT_HASH_BINDINGS_REQUIRED_OR_MISMATCH"]}
        reasons = _artifact_time_errors(artifacts, fingerprints, clock)
        settings_sha = settings_fingerprints(settings)
        if settings["mode"] == "SIMULATION":
            context = artifacts.get("simulation_context")
            expected = {"classification": "SYNTHETIC_ONLY", "synthetic": True, "target_year": 2099,
                        "temporary_store_registered": True,
                        "storage_identity_sha256": settings_sha["storage_identity_sha256"]}
            if (not isinstance(context, dict) or context != expected
                    or type(context.get("target_year")) is not int
                    or context.get("synthetic") is not True
                    or context.get("temporary_store_registered") is not True):
                reasons.append("EXPLICIT_SYNTHETIC_TEMP_STORE_CONTEXT_REQUIRED")
            status = "SIMULATION_PREFLIGHT_ONLY"
        else:
            for name in _PRIVATE:
                artifact = artifacts[name]
                if artifact.get("review_status") != "EXTERNALLY_REVIEWED_FOR_SHADOW" or artifact.get("open_items") != []:
                    reasons.append("REVIEWED_EVAL_AND_LEGACY_ARTIFACTS_REQUIRED")
            expected = _bindings(settings, fingerprints, settings_sha)
            reasons.extend(_approval_errors(artifacts.get("approval_bundle"), operator_ack, expected, clock))
            status = "PRIVATE_ATTESTED_PREFLIGHT_ONLY"
        reasons = sorted(set(reasons))
        if reasons:
            return {**base, "reasons": reasons}
        return {**base, "allowed": True, "status": status, "reasons": [],
                "config_sha256": settings_sha["config_sha256"],
                "storage_identity_sha256": settings_sha["storage_identity_sha256"],
                "artifact_sha256s": fingerprints,
                "scope": "SIMULATION_ONLY" if settings["mode"] == "SIMULATION" else "PRIVATE_THIRD_RESEARCH_SHADOW_ONLY",
                "storage_ownership": "NOT_VERIFIED_HERE_STORE_MUST_CHECK_BEFORE_WRITES",
                "review_truth": "OPERATOR_ATTESTATION_ONLY_EXTERNAL_CHECK_REQUIRED"}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {**base, "reasons": ["ARTIFACT_OR_APPROVAL_CONTEXT_INVALID"]}
