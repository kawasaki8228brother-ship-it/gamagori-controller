"""Pinned F5 policy projection only; no model/Shadow integration or execution GO.

The ledger artifact hash authenticates this selected public artifact, not Andy's
spoken decision, original approval record, source data or a production action.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

LEDGER_COMMIT = "1778d2e4080dad8b5f1e80b7cc22ea0f5ce7df67"
LEDGER_PATH = "development/model11/f5_preregistration_v007/DECISION_LEDGER.json"
LEDGER_BYTES = 6541
LEDGER_SHA256 = "1eda58d7b8aaa221314b02c2be90ae2b5f9640873a33d192aa5b59411e9a222d"
OVERRIDE_SHA256 = "3ac9eb6f3ad22475785e50bb60cc829c4930c6b66c7d8662d3e1f9cc92755d73"
OPEN_IDS = ("SESOI", "MIN_SELECTION_DAYS", "HOLDOUT_START_AND_DAYS", "ALPHA_SPENDING_NEED",
            "SCRATCH_REFUND_CANCELLATION_RULES", "ODDS_MISSING_AND_MAX_RATE",
            "DAY_MEETING_DEPENDENCE", "POST_PASS_ALLOWED_SCOPE")


class AuthorityHold(ValueError):
    """Only internally authored codes, never input contents or local paths."""


def _ledger(raw):
    if type(raw) is not bytes:
        raise AuthorityHold("LEDGER_RAW_BYTES_REQUIRED")
    if len(raw) != LEDGER_BYTES or hashlib.sha256(raw).hexdigest() != LEDGER_SHA256:
        raise AuthorityHold("PINNED_LEDGER_ARTIFACT_MISMATCH")
    try:
        value = json.loads(raw)
        if value["schema_version"] != "F5_DECISION_LEDGER_V007":
            raise AuthorityHold("LEDGER_SCHEMA_MISMATCH")
        if (value["source"]["original_sha256"] is not None
                or value["source"]["approval_receipt"] is not None):
            raise AuthorityHold("UNAVAILABLE_APPROVAL_EVIDENCE_MUST_REMAIN_NULL")
        items = value["open_items"]
        if (type(items) is not list or tuple(item["id"] for item in items) != OPEN_IDS
                or any(item["status"] != "OPEN" or item["value"] is not None for item in items)):
            raise AuthorityHold("EIGHT_OPEN_VALUES_MUST_REMAIN_NULL")
        if (value["M0"]["status"] != "DECIDED" or value["M2"]["status"] != "DECIDED"
                or value["M1"]["status"] != "FUTURE_DESIGN_DECIDED"):
            raise AuthorityHold("LEDGER_DECISION_STATUS_MISMATCH")
        if any(permission is not False for permission in value["operational_permissions"].values()):
            raise AuthorityHold("NO_OPERATIONAL_PERMISSION_GRANTED")
        return value
    except AuthorityHold:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise AuthorityHold("LEDGER_STRUCTURE_UNVERIFIED") from None


def project_authority(raw):
    """Derive decided values solely from pinned bytes; omit historical examples."""
    ledger = _ledger(raw)
    return {
        "status": "PINNED_DECISIONS_PROJECTED_NOT_EXECUTABLE",
        "policy_authority": {"commit": LEDGER_COMMIT, "path": LEDGER_PATH,
            "artifact_bytes": LEDGER_BYTES, "artifact_sha256": LEDGER_SHA256,
            "original_decision_record_sha256": None, "approval_receipt": None,
            "artifact_hash_is_original_decision_hash": False},
        "decision_order": ["M0", "M2", "M1"],
        "M0": deepcopy(ledger["M0"]), "M2": deepcopy(ledger["M2"]), "M1": deepcopy(ledger["M1"]),
        "open_items": [{"id": item["id"], "status": "OPEN", "value": None} for item in ledger["open_items"]],
        "historical_examples": "EXCLUDED_NOT_NEW_ADOPTED_VALUES",
        "provenance_record": "DECISION_PROVENANCE_OVERRIDE.json",
        "original_decision_linkage": "NOT_ESTABLISHED_BY_THIS_ARTIFACT_HASH",
        "actual_statistical_test_performed": False, "model_superiority": "UNVERIFIED",
        "branch_integration_authorized": False, "execution_go": False, "production_go": False,
    }


def authority_report(raw):
    try:
        return project_authority(raw)
    except AuthorityHold as exc:
        return {"status": "HOLD", "reason": exc.args[0], "execution_go": False, "production_go": False}


def load_authority():
    """Read only this packaged public ledger reference; no arbitrary path API."""
    try:
        raw = (Path(__file__).resolve().parent / "references/F5_DECISION_LEDGER_1778d2e.json").read_bytes()
    except OSError:
        return {"status": "HOLD", "reason": "PINNED_LEDGER_ARTIFACT_UNAVAILABLE",
                "execution_go": False, "production_go": False}
    return authority_report(raw)


def load_provenance_override():
    """Additive historical clarification, never another source of policy values."""
    try:
        raw = (Path(__file__).resolve().parent / "DECISION_PROVENANCE_OVERRIDE.json").read_bytes()
    except OSError:
        raise AuthorityHold("PROVENANCE_OVERRIDE_UNAVAILABLE") from None
    if hashlib.sha256(raw).hexdigest() != OVERRIDE_SHA256:
        raise AuthorityHold("PROVENANCE_OVERRIDE_ARTIFACT_MISMATCH")
    return json.loads(raw)


def model_claim_status(market_weight, *, ledger_raw):
    """Structural w=1 safeguard; never issue a performance claim for other w."""
    policy = project_authority(ledger_raw)
    if type(market_weight) not in (int, float):
        raise AuthorityHold("MARKET_WEIGHT_INVALID")
    try:
        finite = math.isfinite(market_weight)
    except OverflowError:
        finite = False
    if not finite or market_weight not in policy["M1"]["market_weights"]:
        raise AuthorityHold("MARKET_WEIGHT_OUTSIDE_DECIDED_GRID")
    return {"status": "NO_MODEL_SUPERIORITY" if market_weight == 1.0 else "UNVERIFIED_UNTOUCHED_HOLDOUT_REQUIRED",
            "weight_definition": policy["M1"]["market_weight_definition"],
            "confirmatory_family_size": policy["M0"]["confirmatory_family_size"],
            "model_superiority_allowed": False, "actual_test_performed": False,
            "execution_go": False, "production_go": False}
