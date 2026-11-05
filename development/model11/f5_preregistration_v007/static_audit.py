"""Read-only document consistency checks, never a statistical decision engine."""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re

PARENT = "7aec4fdb6b9f311ee01bf3a2752410e683d83e42"
OPEN_IDS = {"SESOI", "MIN_SELECTION_DAYS", "HOLDOUT_START_AND_DAYS", "ALPHA_SPENDING_NEED",
            "SCRATCH_REFUND_CANCELLATION_RULES", "ODDS_MISSING_AND_MAX_RATE", "DAY_MEETING_DEPENDENCE",
            "POST_PASS_ALLOWED_SCOPE"}
WEIGHTS = [0, .25, .5, .75, .9, 1.0]
ROLES = ("training", "selection", "pilot", "holdout")
PERMISSIONS = {"private_data_ingestion", "source_connection", "shadow_start", "pilot_execution",
    "confirmatory_holdout_execution", "production_change", "model_or_box_change", "configuration_change",
    "task_or_schedule_change", "canonical_or_pointer_change", "render_operation", "pr_ready_merge_or_deploy",
    "formal_promotion", "automatic_post_pass_action"}


def _result(issues, success):
    return {"status": "HOLD" if issues else success, "issues": list(dict.fromkeys(issues)),
        "scope": "STATIC_DOCUMENT_OR_SYNTHETIC_METADATA_ONLY", "statistical_evaluation_performed": False,
        "real_data_go": False, "shadow_go": False, "production_go": False}


def _equal(actual, expected):
    if type(expected) is bool:
        return actual is expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    return actual == expected


def _fields(actual, expected):
    return isinstance(actual, dict) and all(key in actual and _equal(actual[key], value) for key, value in expected.items())


def audit_records(ledger, source_reference, partition_register):
    """Check this received-policy snapshot, not authenticity or future readiness."""
    issues = []
    try:
        json.dumps([ledger, source_reference, partition_register], allow_nan=False)
        if not _fields(ledger, {"schema_version": "F5_DECISION_LEDGER_V007", "parent_commit": PARENT,
                               "document_version": "v007", "executable_configuration": False}):
            issues.append("DOCUMENT_IDENTITY_OR_EXECUTION_DRIFT")
        m0 = ledger.get("M0", {})
        if not _fields(m0, {"status": "DECIDED", "candidate": "SINGLE_FROZEN_CHAMPION", "comparator": "P_market",
                "endpoint": "JOINT_120_LOGLOSS", "market_snapshot_requirement": "THE_SAME_PREDEADLINE_FULL_120_ODDS_SNAPSHOT",
                "weighting": "PAIRED_DAY_EQUAL_WEIGHT", "within_day": "MEAN_OVER_IDENTICAL_PAIRED_ELIGIBLE_RACES",
                "comparison_direction": "LOWER_CHAMPION_LOGLOSS", "test_sidedness": "ONE_SIDED",
                "significance_alpha": .025, "power_target": .8, "confirmatory_family_size": 1,
                "six_market_weights_are_six_confirmatory_tests": False, "optional_stopping_allowed": False,
                "posthoc_changes_allowed": False, "market_only_w1_interpretation": "NO_MODEL_SUPERIORITY",
                "statistical_pass_implemented_or_granted": False}) or type(m0.get("confirmatory_family_size")) is not int:
            issues.append("M0_LOCKED_DECISION_DRIFT")
        m2 = ledger.get("M2", {})
        if not _fields(m2, {"status": "DECIDED", "role": "PILOT_ONLY",
                "entry_rule": "FIRST_THIRD_RESEARCH_SHADOW_OPERATING_DAY_IS_PILOT_ENTRY", "first_operating_day": None,
                "actual_pilot_duration_days": None, "separate_execution_go_required": True, "pilot_is_holdout": False,
                "pilot_duration_status": "UNSPECIFIED_NOT_FIXED_TO_ONE_DAY_OR_CANDIDATE_WINDOW",
                "sd_day_constraint": "UNVERIFIED_WHEN_FEWER_THAN_TWO_PAIRED_DAYS_NO_AUTOMATIC_EXTENSION",
                "improvement_claim_allowed": False, "profit_claim_allowed": False, "promotion_claim_allowed": False,
                "scheduled_or_execution_authorized": False}) or not _fields(m2.get("candidate_window"),
                {"start": "2026-11-21", "end": "2026-11-24", "timezone": "Asia/Tokyo", "or_later": True,
                 "status": "CANDIDATE_ONLY_NOT_SCHEDULED"}):
            issues.append("M2_PILOT_OR_AUTHORITY_DRIFT")
        goals = ["FULL_120_PREDEADLINE_ODDS_CAPTURE_RATE", "MISSING_RATE_AND_MISSING_CAUSES",
                 "PAIRED_DAILY_LOGLOSS_DIFFERENCES", "SD_DAY_IF_ESTIMABLE",
                 "TIMING_EVIDENCE_AND_SOURCE_MAPPING_PRACTICAL_CHECK", "PREDICTION_SAVE_AND_RESULT_RECONCILIATION_OPERATIONS"]
        if m2.get("measurements") != goals:
            issues.append("M2_PILOT_GOALS_DRIFT")
        m1 = ledger.get("M1", {})
        weights = m1.get("market_weights")
        if (not _fields(m1, {"status": "FUTURE_DESIGN_DECIDED", "option": "A_REDUCED_FIXED_CALIBRATION",
                "model": "hierarchical", "course_alpha": .5, "temperature": 1.0,
                "market_weight_definition": "w_MARKET_AND_1_MINUS_w_MODEL",
                "selection_action": "CHOOSE_w_ON_SELECTION_THEN_FREEZE_ONE_CHAMPION_BEFORE_HOLDOUT",
                "confirmatory_option": "A_ONLY", "B_role": "EXPLORATORY_ONLY", "C_role": "EXPLORATORY_ONLY",
                "existing_model_or_grid_changed": False, "executable_application_authorized": False})
                or weights != WEIGHTS or not isinstance(weights, list)
                or any(type(value) not in (int, float) for value in weights)):
            issues.append("M1_FUTURE_A_DESIGN_DRIFT")
        items = ledger.get("open_items")
        if (not isinstance(items, list) or len(items) != 8
                or {row.get("id") for row in items if isinstance(row, dict)} != OPEN_IDS
                or any(not _fields(row, {"status": "OPEN", "value": None}) for row in items)):
            issues.append("EIGHT_OPEN_ITEMS_FILLED_OR_DRIFTED")
        examples = ledger.get("prior_examples")
        if not isinstance(examples, list) or len(examples) != 3 or any(
                not _fields(row, {"status": "ILLUSTRATIVE_NOT_ADOPTED"}) for row in examples):
            issues.append("OLD_EXAMPLES_SILENTLY_ADOPTED")
        permissions = ledger.get("operational_permissions")
        if not isinstance(permissions, dict) or set(permissions) != PERMISSIONS or any(value is not False for value in permissions.values()):
            issues.append("POLICY_IS_NOT_OPERATIONAL_GO")
        if not _fields(ledger.get("F2"), {"status": "PROPOSED_NOT_ADOPTED", "existing_thresholds_or_logic_changed": False,
                                          "new_thresholds_adopted": False}):
            issues.append("F2_ADOPTION_DRIFT")
        if not _fields(ledger.get("source"), {"original_sha256": None, "approval_receipt": None,
                "hq14_claude_independent_linkage": "PENDING", "execution_approval_status": "NOT_GRANTED_BY_THIS_DOCUMENT"}):
            issues.append("UNOBTAINED_ORIGINAL_OR_RECEIPT_FILLED")
        if datetime.fromisoformat(ledger["source"]["decision_time"]) != datetime.fromisoformat("2026-11-05T20:36+09:00"):
            issues.append("REPORTED_DECISION_TIME_DRIFT")
        if not _fields(ledger.get("freeze_and_gates", {}).get("G1_G6"),
                       {"status": "PRESERVED_NO_CHANGE", "definitions_status": "UNVERIFIED_NOT_PROVIDED",
                        "definitions": None, "redefinition_allowed": False}):
            issues.append("UNPROVIDED_GATE_DEFINITIONS_INVENTED")

        source = source_reference
        if not _fields(source, {"namespace": "F5_PREREGISTRATION_V007", "parent_commit": PARENT,
                               "source_fetch_performed": False, "production_go": False}):
            issues.append("SOURCE_REFERENCE_SCOPE_DRIFT")
        if not _fields(source.get("received_information"), {"reported_decider": "ANDY", "forwarded_by": "HQ14",
                "reported_forward_source": "CLAUDE12", "received_at": None,
                "basis": "USER_FORWARDED_INFORMATION_NO_ORIGINAL_BYTES", "policy_status": "DECIDED_AS_RECEIVED",
                "external_authenticity": "UNVERIFIED_PENDING_INDEPENDENT_MATCH"}):
            issues.append("FORWARDED_POLICY_AND_AUTHENTICITY_CONFLATED")
        if datetime.fromisoformat(source["received_information"]["reported_decision_time"]) != datetime.fromisoformat(ledger["source"]["decision_time"]):
            issues.append("SOURCE_AND_LEDGER_DECISION_TIME_DIFFER")
        refs = source.get("source_references", {})
        if set(refs) != {"raw_original", "andy_decision_receipt", "forward_receipt"} or any(
                not _fields(row, {"id": None, "bytes": None, "sha256": None, "status": "NOT_PROVIDED"}) for row in refs.values()):
            issues.append("MISSING_SOURCE_BYTES_FABRICATED")
        matches = source.get("independent_source_match", {})
        if set(matches) != {"HQ14", "CLAUDE"} or any(not _fields(row, {"status": "PENDING", "evidence_id": None,
                "evidence_sha256": None}) for row in matches.values()):
            issues.append("SOURCE_MATCH_NOT_YET_VERIFIED")
        if not _fields(source.get("formal_claude_review"), {"status": "AWAITING", "original_id": None,
                "original_bytes": None, "original_sha256": None}):
            issues.append("FORMAL_REVIEW_NOT_RECEIVED")
        op_go = source.get("operational_go")
        if not isinstance(op_go, dict) or set(op_go) != {"actual_data_use", "pilot_execution", "shadow_start", "runtime_enablement",
                "production_change", "deployment_or_merge", "promotion_or_close"} or any(value is not False for value in op_go.values()):
            issues.append("SOURCE_REFERENCE_IS_NOT_OPERATIONAL_GO")

        partitions = partition_register
        if not _fields(partitions, {"schema": "F5_PARTITION_REGISTRY_DESIGN_V007", "status": "OPEN", "enabled": False,
                "executable": False, "application_go": False, "production_go": False, "actual_data_present": False,
                "registry_sealed_at": None, "registry_sha256": None, "pilot_start": None, "holdout_start": None,
                "pilot_disallowed_in_holdout": True, "expanding_walk_forward_is_sealed_holdout": False,
                "required_selection_days": None, "required_holdout_days": None, "pilot_sd_day": None,
                "pilot_sd_day_status": "UNVERIFIED_K_LESS_THAN_2_IS_UNDEFINED",
                "additional_pilot_span": "OPEN_SEPARATE_REVIEW_NOT_AUTOMATIC",
                "pilot_development_reuse": "OPEN_EXPLICIT_PRESEAL_DECISION_REQUIRED",
                "statistics_after_pilot_before_holdout_seal": True,
                "entries": [], "old_predeadline_odds_ownership": "UNVERIFIED", "F2_adopted": False}):
            issues.append("OPEN_PARTITION_REGISTER_ACTIVATED_OR_FILLED")
        roles = partitions.get("partitions", {})
        if set(roles) != set(ROLES) or any(not _fields(row, {"start": None, "end": None, "day_ids": [], "race_ids": [],
                                                           "manifest_sha256": None}) for row in roles.values()):
            issues.append("ACTUAL_PARTITIONS_NOT_ASSIGNED")
        if any(not _fields(roles.get(role), {"status": "OPEN_UNTOUCHED_FUTURE_REQUIRED" if role == "holdout" else "OPEN"}) for role in ROLES):
            issues.append("PARTITION_STATUS_FALSIFIED")
        template = partitions.get("entry_template_not_an_actual_record")
        expected_template = {"partition", "day_id", "race_id", "prediction_as_of", "deadline", "snapshot_id", "snapshot_version",
            "raw_sha256", "predeadline_odds_sha256", "point_in_time_audit_sha256", "label_available_at", "source_evidence_sha256",
            "receipt_sha256", "independent_readback_sha256"}
        if not isinstance(template, dict) or set(template) != expected_template or any(value is not None for value in template.values()):
            issues.append("EMPTY_TEMPLATE_IS_NOT_AN_ACTUAL_RECORD")
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        issues.append("STATIC_DOCUMENT_INPUT_INVALID")
    return _result(issues, "DOCUMENT_CONSISTENT")


def audit_partition_fixture(fixture):
    """Illustrate disjointness on fake metadata only; no real registry or scores."""
    issues = []
    try:
        if not isinstance(fixture, dict) or fixture.get("classification") != "SYNTHETIC_ONLY":
            return _result(["SYNTHETIC_PARTITION_FIXTURE_REQUIRED"], "FIXTURE_CONSISTENT")
        roles = fixture.get("partitions")
        if not isinstance(roles, dict) or set(roles) != set(ROLES):
            return _result(["PARTITION_ROLES_INVALID"], "FIXTURE_CONSISTENT")
        days, races = {}, {}
        for role in ROLES:
            row = roles[role]
            if not isinstance(row, dict) or set(row) != {"day_ids", "race_ids"}:
                return _result(["PARTITION_FIXTURE_FIELDS_INVALID"], "FIXTURE_CONSISTENT")
            d, r = row["day_ids"], row["race_ids"]
            if not isinstance(d, list) or not isinstance(r, list) or not d or not r:
                return _result(["PARTITION_FIXTURE_MEMBERSHIP_EMPTY"], "FIXTURE_CONSISTENT")
            if any(not isinstance(value, str) or not value.startswith("2099-") or date.fromisoformat(value).isoformat() != value for value in d):
                return _result(["SYNTHETIC_DAY_ID_INVALID"], "FIXTURE_CONSISTENT")
            if any(not isinstance(value, str) or not re.fullmatch(r"SYNTHETIC_[A-Za-z0-9_]{1,100}", value) for value in r):
                return _result(["SYNTHETIC_RACE_ID_INVALID"], "FIXTURE_CONSISTENT")
            if len(set(d)) != len(d) or len(set(r)) != len(r):
                issues.append("DUPLICATE_PARTITION_MEMBERSHIP")
            days[role], races[role] = set(d), set(r)
        for role in ("training", "selection", "pilot"):
            if days["holdout"] & days[role] or races["holdout"] & races[role]:
                issues.append("HOLDOUT_REUSES_PREVIOUSLY_SEEN_DAY_OR_RACE")
        if days["training"] & days["selection"] or races["training"] & races["selection"]:
            issues.append("TRAINING_SELECTION_OVERLAP")
        if any(days["pilot"] & days[role] or races["pilot"] & races[role] for role in ("training", "selection")):
            issues.append("PILOT_DEVELOPMENT_REUSE_OPEN")
        if not max(days["training"]) < min(days["selection"]) or not max(days["selection"]) < min(days["holdout"]) or not max(days["pilot"]) < min(days["holdout"]):
            issues.append("PARTITION_CHRONOLOGY_INVALID")
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        issues.append("SYNTHETIC_PARTITION_INPUT_INVALID")
    return _result(issues, "FIXTURE_CONSISTENT")


def load_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    def constant(_):
        raise ValueError("NONFINITE_JSON")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def audit_package(directory):
    directory = Path(directory)
    try:
        core = audit_records(load_json(directory / "DECISION_LEDGER.json"),
            load_json(directory / "SOURCE_RECEIPT_REFERENCE.json"), load_json(directory / "DATA_PARTITIONS.OPEN.json"))
        proposal = audit_review_proposal(load_json(directory / "SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json"))
        return _result(core["issues"] + proposal["issues"], "DOCUMENT_CONSISTENT")
    except Exception:
        return _result(["STATIC_DOCUMENT_READ_FAILED"], "DOCUMENT_CONSISTENT")


def audit_review_proposal(proposal):
    """Check proposal non-adoption and schema design, not an actual log export."""
    issues = []
    try:
        if not _fields(proposal, {"namespace": "F5_PREREGISTRATION_V007", "status": "PROPOSED_NOT_ADOPTED",
                "executable": False, "exporter_implemented": False, "actual_host_or_logs_tested": False,
                "third_party_original_sha256": None, "M0_M2_M1_policy_changed": False,
                "eight_open_choices_filled": False, "F2_adopted": False, "production_go": False}):
            issues.append("THIRD_PARTY_PROPOSAL_IS_NOT_ADOPTION")
        go = proposal.get("operational_go")
        if not isinstance(go, dict) or set(go) != {"implementation", "host_probe", "actual_export", "external_share", "shadow_start", "production_change"} or any(value is not False for value in go.values()):
            issues.append("DIAGNOSTIC_DESIGN_IS_NOT_OPERATIONAL_GO")
        params = proposal.get("unadopted_parameters")
        if not isinstance(params, dict) or set(params) != {"deadline_buffer_seconds", "clock_drift_tolerance", "maximum_odds_age_override",
                "retry_policy", "no_odds_statistical_cohort_rule", "tail_quantile_levels", "tail_bin_edges", "minimum_disclosure_group_count"} or any(value is not None for value in params.values()):
            issues.append("DIAGNOSTIC_THRESHOLDS_NOT_ADOPTED")
        schema = proposal.get("proposed_summary_schema", {})
        if (not _fields(schema, {"type": "object", "additionalProperties": False})
                or set(schema.get("properties", {})) != {"kind", "stage", "error_code", "code_commit", "counts"}
                or set(schema.get("required", [])) != {"kind", "stage", "error_code", "code_commit", "counts"}):
            issues.append("DIAGNOSTIC_SCHEMA_MUST_USE_EXACT_ALLOWLIST")
        properties = schema.get("properties", {})
        if not _fields(properties.get("kind"), {"const": "SAFE_DIAGNOSTIC_SUMMARY"}) or not _fields(
                properties.get("code_commit"), {"type": "string", "pattern": "^[0-9a-f]{40}$"}):
            issues.append("DIAGNOSTIC_FIXED_FIELDS_DRIFT")
        counts = properties.get("counts", {})
        if not _fields(counts, {"type": "object", "additionalProperties": False}) or set(counts.get("properties", {})) != {"observations", "failures", "unknown"}:
            issues.append("DIAGNOSTIC_COUNTS_MUST_USE_ALLOWLIST")
        checks = proposal.get("proposed_additional_checks", {})
        if not _fields(checks, {"unknown_field_or_enum": "REJECT_EXPORT", "invalid_or_unsafe_value": "REJECT_EXPORT",
                "boolean_as_count": "REJECT_EXPORT", "missing_count": "UNKNOWN_NULL_NEVER_FILL_ZERO",
                "raw_source": "REMAINS_PRIVATE_NO_RAW_LOG_PASS_THROUGH",
                "external_share": "HQ14_MANUAL_REVIEW_REQUIRED_BEFORE_ANY_SHARE", "complete_anonymity": "NOT_GUARANTEED"}):
            issues.append("DIAGNOSTIC_SHARING_BOUNDARY_DRIFT")
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        issues.append("STATIC_PROPOSAL_INPUT_INVALID")
    return _result(issues, "PROPOSAL_REMAINS_UNADOPTED")


def audit_parent_bytes(package_root, baseline):
    """Read and hash old files only; execute no preserved model or workflow."""
    try:
        if not isinstance(baseline, list) or len(baseline) != 245:
            return _result(["PARENT_BASELINE_INVALID"], "PARENT_BYTES_UNCHANGED")
        if len({entry.get("path") for entry in baseline}) != 245:
            return _result(["PARENT_BASELINE_INVALID"], "PARENT_BYTES_UNCHANGED")
        for entry in baseline:
            name = entry["path"]
            if not name.startswith("development/model11/") or ".." in Path(name).parts:
                return _result(["PARENT_PATH_INVALID"], "PARENT_BYTES_UNCHANGED")
            path = Path(package_root) / name.removeprefix("development/model11/")
            raw = path.read_bytes()
            if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                return _result(["PARENT_FILE_CHANGED"], "PARENT_BYTES_UNCHANGED")
        return {**_result([], "PARENT_BYTES_UNCHANGED"), "checked_files": len(baseline)}
    except Exception:
        return _result(["PARENT_REGRESSION_READ_FAILED"], "PARENT_BYTES_UNCHANGED")


if __name__ == "__main__":
    report = audit_package(Path(__file__).resolve().parent)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["status"] == "DOCUMENT_CONSISTENT" else 2)
