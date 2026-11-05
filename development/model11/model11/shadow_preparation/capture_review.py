"""P1 preparation inventory and one-call audit over the frozen v005 adapter.

This module is not another converter, official parser, source client or launcher.
Every application result remains HOLD; synthetic software checks are separate.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import permutations
import re

from ..shadow_launch.sources import SourceAdapter

FEATURES = ("st", "turn", "motor", "ability", "exhibition")
TIMES = ("acquired_at", "available_at", "revision_at")
RAW_TOP_LEVEL = (
    "schema_version", "data_classification", "race_id", "target_date", "venue", "prediction_at",
    "race_provenance", "deadline", "active_boats", "active_boats_provenance", "boats", "odds_snapshot",
)
COURSE_TOP_LEVEL = ("course_inputs", "course_policy_id", "course_policy_sha256", "data_classification", "synthetic")
_REASON = re.compile(r"[A-Z0-9_]+\Z")


def required_mapping_inventory():
    """Known local destination requirements; all actual official mapping is OPEN.

    {boat_index}/{history_index} are local inventory patterns, not executable
    official JSON pointers. All 120 full-field odds destination keys are explicit.
    """
    rows = []

    def item(path, requirement, scope="ONE_CAPTURE"):
        rows.append({"local_target": path, "local_requirement": requirement, "scope": scope,
                     "actual_official_pointer": None, "actual_official_unit": None,
                     "actual_official_format": None, "actual_official_source": None,
                     "review_status": "OPEN"})

    def provenance(path, scope="ONE_CAPTURE"):
        for name in TIMES:
            item(path + "/" + name, "strict aware timestamp; no inference; <= prediction", scope)
        item(path + "/evidence_sha256", "64 lowercase hex; independent original required, not authentication", scope)

    for field, requirement in (
        ("schema_version", "exact RAW_V001"),
        ("data_classification", "RAW enum SYNTHETIC_ONLY or HQ14_PRIVATE_OFFLINE; never real-to-synthetic relabel"),
        ("race_id", "explicit opaque race identity; external official identity mapping OPEN"),
        ("target_date", "valid YYYY-MM-DD; source date identity must be independently checked"),
        ("venue", "exact GAMAGORI"),
        ("prediction_at", "strict aware pre-deadline snapshot time"),
        ("active_boats", "distinct integer IDs 1..6; launch requires six active boats"),
    ):
        item("/raw/" + field, requirement)
    provenance("/raw/race_provenance")
    provenance("/raw/active_boats_provenance")
    item("/raw/deadline/value", "strict aware deadline, prediction < deadline, JST target_date identity")
    item("/raw/deadline/unit", "local schema literal timestamp; actual official representation OPEN")
    provenance("/raw/deadline")
    boat = "/raw/boats/{boat_index}"
    item(boat + "/boat", "distinct integer boat ID 1..6, active-domain binding", "EACH_INCLUDED_BOAT")
    for state in ("course", "fl", "scratched"):
        base = boat + "/" + state
        item(base + "/value", "explicit integer course or actual boolean F/L/scratch; no missing-as-false", "EACH_INCLUDED_BOAT")
        item(base + "/unit", "course_number for course; boolean for F/L/scratch", "EACH_INCLUDED_BOAT")
        provenance(base, "EACH_INCLUDED_BOAT")
    for field, requirement in (("motor_id", "nonempty physical/statistical motor identity"),
                               ("version", "nonempty motor identity/statistics version"),
                               ("effective_at", "aware effective time <= identity acquisition and prediction")):
        item(boat + "/motor_identity/" + field, requirement, "EACH_INCLUDED_BOAT")
    provenance(boat + "/motor_identity", "EACH_INCLUDED_BOAT")
    for name in FEATURES:
        base = boat + "/features/" + name
        item(base + "/value", "observed finite numeric; missing/bool/null disallowed; no imputation", "EACH_INCLUDED_BOAT")
        item(base + "/unit", "must equal separately frozen feature_specs unit; actual raw unit OPEN", "EACH_INCLUDED_BOAT")
        provenance(base, "EACH_INCLUDED_BOAT")
        if name == "motor":
            item(base + "/motor_id", "must match motor_identity.motor_id", "EACH_INCLUDED_BOAT")
            item(base + "/motor_version", "must match motor_identity.version; all three motor-feature times >= effective_at", "EACH_INCLUDED_BOAT")
    item("/raw/odds_snapshot/unit", "exact gross_payout_multiple; no implicit inverse or payout conversion")
    provenance("/raw/odds_snapshot")
    for triple in permutations(range(1, 7), 3):
        ticket = "-".join(map(str, triple))
        item("/raw/odds_snapshot/odds/" + ticket, "positive finite gross payout multiple; complete pre-LOCK 120-domain", "ONE_FULL_FIELD_TICKET")
    for field in COURSE_TOP_LEVEL:
        item("/course/" + field, "N1 course context and frozen policy/classification binding; actual source mapping OPEN")
    for key, definition in (("frame", "FRAME_NUMBER"), ("exhibition", "EXHIBITION_ENTRY")):
        base = "/course/course_inputs/" + key
        item(base + "/definition", "exact " + definition + "; null only if frozen policy permits missing observation")
        item(base + "/source_id", "exact N1 predeclared source for class and definition; OFFICIAL prefix is not proof")
        provenance(base)
        for number in range(1, 7):
            item(base + "/courses/" + str(number), "distinct integer course; selected value and exact state timestamps bind to RAW boat")
    for field in ("format_id", "data_classification", "synthetic", "source_id", "payload_bytes", "payload_sha256"):
        item("/capture/" + field, "exact v005 envelope contract; original UTF-8 JSON bytes and full SHA, no secret output")
    for field in TIMES:
        item("/capture/" + field, "materialized capture time >= respective known component maximum and <= prediction")
    for field in ("payload_sha256", "evidence_sha256", *TIMES):
        item("/capture/history/{history_index}/" + field, "required ordered version evidence; final entry binds exact current bytes/times", "EACH_CAPTURE_HISTORY_ENTRY")
    for name in FEATURES:
        for field in ("unit", "direction", "normalization"):
            item("/mapping/feature_specs/features/" + name + "/" + field,
                 "explicit frozen PROPOSED spec; no automatic unit/direction/normalization guessing")
    for field in ("hq14_review_sha256", "claude_review_sha256"):
        item("/mapping/review_evidence/" + field, "private conditional review original hash; presence is SELF_REPORTED_HASHES_ONLY")
    return rows


def make_open_mapping_template():
    """Non-runnable disabled preparation record; no official paths or units guessed."""
    return {
        "schema_version": "CAPTURE_INPUT_PREPARATION_V006", "status": "OPEN", "enabled": False,
        "application_status": "HOLD", "production_go": False,
        "actual_official_format": None, "actual_official_source": None,
        "independent_review_originals": {"hq14_sha256": None, "claude_sha256": None},
        "source_mapping_candidate": {
            "schema_version": "SOURCE_MAPPING_V001", "version": None, "format_id": None,
            "data_classification": None, "synthetic": None, "source_id": None,
            "raw_fields": {field: None for field in RAW_TOP_LEVEL},
            "course_fields": {field: None for field in COURSE_TOP_LEVEL},
            "feature_units": {name: None for name in FEATURES}, "feature_specs": None,
            "course_source_ids": {"frame": None, "exhibition": None}, "review_evidence": None,
        },
        "required_field_inventory": required_mapping_inventory(),
        "official_mapping_authenticity": "UNVERIFIED", "actual_source_mapping": "OPEN",
        "notes": ["Local destinations are known; actual official pointers, units and formats are not supplied.",
                  "This preparation template is not accepted as an executable SOURCE_MAPPING_V001.",
                  "Independent approval and application GO are separate from this offline inventory."],
    }


def _base():
    return {"schema_version": "CAPTURE_READINESS_PREPARATION_V006", "status": "HOLD",
            "application_status": "HOLD", "application_ready": False,
            "software_check": "UNVERIFIED", "converter_status": None, "converter_called": False,
            "reasons": [], "official_mapping_status": "OPEN", "external_authenticity": "UNVERIFIED",
            "independent_review_status": "UNVERIFIED", "production_go": False}


def audit_capture_preparation(mapping=None, capture=None, *, synthetic_validation=False):
    """One v005 conversion for explicit synthetic validation; never application GO.

    Default is a no-inspection HOLD. Declared private data is held before bytes
    are decoded. All actual mapping/conversion gates are delegated unchanged.
    """
    report = _base()
    if synthetic_validation is not True:
        report["reasons"] = ["OFFLINE_SYNTHETIC_VALIDATION_NOT_REQUESTED"]
        return report
    if (isinstance(capture, dict) and capture.get("data_classification") in ("PRIVATE_REAL", "HQ14_PRIVATE_OFFLINE")):
        report["reasons"] = ["PRIVATE_SOURCE_REVIEW_AND_SEPARATE_GO_REQUIRED"]
        return report
    try:
        adapter = SourceAdapter(mapping)
    except Exception:
        report["reasons"] = ["CAPTURE_REVIEW_UNVERIFIED"]
        return report
    report["converter_called"] = True
    try:
        converted = adapter.convert(capture)  # the only conversion
        report["converter_status"] = converted["status"]
    except Exception:
        report["reasons"] = ["CAPTURE_REVIEW_UNVERIFIED"]
        return report
    if converted["status"] != "READY":
        codes = converted.get("reasons")
        report["reasons"] = [code if isinstance(code, str) and _REASON.fullmatch(code)
                             else "SOURCE_REASON_UNVERIFIED" for code in codes] if isinstance(codes, list) and codes else ["SOURCE_REVIEW_HOLD"]
        return report
    raw, course = converted.get("raw"), converted.get("course")
    if (not isinstance(raw, dict) or not isinstance(course, dict)
            or raw.get("data_classification") != "SYNTHETIC_ONLY"
            or course.get("data_classification") != "SYNTHETIC_ONLY" or course.get("synthetic") is not True
            or not isinstance(raw.get("target_date"), str) or not raw["target_date"].startswith("2099-")):
        report["reasons"] = ["SYNTHETIC_2099_VALIDATION_REQUIRED_NO_RELABEL"]
        return report
    evidence = converted.get("source_evidence", {})
    if evidence.get("active_boat_count") != 6 or evidence.get("odds_ticket_count") != 120:
        report["reasons"] = ["LAUNCH_SIX_ACTIVE_AND_120_ODDS_REQUIRED"]
        return report
    report.update(software_check="PASS", status="SYNTHETIC_CAPTURE_VALIDATION_CANDIDATE",
                  reasons=["ACTUAL_OFFICIAL_MAPPING_REMAINS_OPEN", "APPLICATION_GO_NOT_GRANTED"],
                  validated_scope="INVENTED_2099_LOCAL_CAPTURE_ONLY",
                  source_summary={key: deepcopy(evidence.get(key)) for key in
                                  ("mapping_sha256", "payload_sha256", "payload_bytes", "active_boat_count", "odds_ticket_count")})
    return report
