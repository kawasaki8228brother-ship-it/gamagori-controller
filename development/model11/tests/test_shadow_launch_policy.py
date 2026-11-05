"""Pure policy tests with invented metadata only; no live approval or store."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from unittest import TestCase, main, mock

from model11.shadow_launch.policy import (
    NAMESPACE, OPERATION, artifact_fingerprints, preflight, settings_fingerprints,
    validate_settings,
)

NOW = datetime(2099, 1, 5, 12, tzinfo=timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def settings(mode="SIMULATION"):
    value = {"enabled": True, "mode": mode, "namespace": NAMESPACE,
             "storage_root": "/tmp/synthetic-shadow-owned-new", "code_commit": "a"*40,
             "input_classification": "SYNTHETIC_ONLY" if mode == "SIMULATION" else "HQ14_PRIVATE_OFFLINE",
             "storage_identity": "SYNTHETIC_STORE_001"}
    return pin(value)


def pin(value):
    hashes = settings_fingerprints(value)
    return {**value, "pinned_config_sha256": hashes["config_sha256"],
            "pinned_storage_sha256": hashes["storage_identity_sha256"]}


def artifacts(config, private=False):
    policy = {"policy_id": "SYNTHETIC_EXHIBITION_TEST_ONLY"}
    base = {"training_count": 3, "training_max_available_at": "2099-01-02T12:00:00+00:00",
            "training_max_prediction_at": "2099-01-02T11:00:00+00:00"}
    model = {"schema_version": "COURSE_BOUND_MODEL_V001", "course_policy": policy,
             "course_policy_sha256": digest(policy), "training_policy_sha256": digest(policy), "base_model": base}
    model["self_sha256"] = digest(model)
    normalizer = {"schema_version": "NORMALIZER_V001", "status": "PROPOSED",
                  "fit_cutoff": "2099-01-03T12:00:00+00:00",
                  "training_max_available_at": "2099-01-02T12:00:00+00:00",
                  "training_max_prediction_at": "2099-01-02T11:00:00+00:00"}
    normalizer["normalizer_sha256"] = digest(normalizer)
    result = {"model": model, "normalizer": normalizer, "source_mapping": {"synthetic_only": True},
              "course_policy": policy, "prediction_config": {},
              "simulation_context": {"classification": "SYNTHETIC_ONLY", "synthetic": True,
                  "target_year": 2099, "temporary_store_registered": True,
                  "storage_identity_sha256": config["pinned_storage_sha256"]}}
    if private:
        result["evaluation_plan"] = {"review_status": "EXTERNALLY_REVIEWED_FOR_SHADOW", "open_items": [],
                                     "test_only": "SYNTHETIC_METADATA_NOT_REAL_PREREGISTRATION"}
        result["formal_legacy_comparison"] = {"review_status": "EXTERNALLY_REVIEWED_FOR_SHADOW", "open_items": [],
                                              "test_only": "NOT_REAL_FORMAL_COMPARISON"}
    result["artifact_sha256s"] = artifact_fingerprints(result, config["mode"])
    return result


def approve_for_test(config, supplied):
    """Invent self-reported statements solely to exercise structural checks."""
    result = deepcopy(supplied)
    fps = settings_fingerprints(config)
    bindings = {**{key+"_sha256": value for key, value in result["artifact_sha256s"].items()},
                **fps, "code_commit": config["code_commit"]}
    start, end = (NOW-timedelta(hours=1)).isoformat(), (NOW+timedelta(hours=1)).isoformat()
    reviews = {authority: {"authority": authority, "reviewer_id": "SYNTHETIC_"+authority,
                          "evidence_sha256": digest({"invented_review": authority}),
                          "decision": "APPROVED_FOR_THIRD_RESEARCH_SHADOW", "operation": OPERATION,
                          "bindings_sha256": digest(bindings), "valid_from": start, "valid_until": end}
               for authority in ("HQ14", "CLAUDE", "ANDY")}
    result["approval_bundle"] = {"operation": OPERATION, "operator_id": "SYNTHETIC_OPERATOR",
                                  "valid_from": start, "valid_until": end, "bindings": bindings,
                                  "reviews": reviews, "review_truth_attested_by_operator": True}
    ack = {"ack": OPERATION, "operator_id": "SYNTHETIC_OPERATOR", "bindings_sha256": digest(bindings),
           "attested_at": NOW.isoformat(), "evidence_checked_outside_this_program": True}
    return result, ack


class PolicyTests(TestCase):
    def test_default_disabled_without_inspecting_any_context(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError("disabled path inspected supplied context")
        for value in (None, {}, {"enabled": False}, {"enabled": False, "storage_root": None}):
            with mock.patch("builtins.open", side_effect=AssertionError("unexpected open")):
                result = preflight(value, Forbidden(), Forbidden(), Forbidden())
            self.assertEqual(result["status"], "DISABLED")
            self.assertFalse(result["allowed"])
            self.assertFalse(result["filesystem_initialized"])

    def test_disabled_template_all_unknown_inputs_null_is_valid(self):
        value = {key: None for key in settings()}
        value.update(enabled=False, mode="PRIVATE_SHADOW", namespace=NAMESPACE,
                     input_classification="HQ14_PRIVATE_OFFLINE")
        self.assertEqual(validate_settings(value)["status"], "DISABLED")
        self.assertTrue(validate_settings(value)["valid"])

    def test_simulation_requires_explicit_enable_clock_and_temp_context(self):
        config = settings()
        supplied = artifacts(config)
        result = preflight(config, supplied, now=NOW)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["status"], "SIMULATION_PREFLIGHT_ONLY")
        self.assertFalse(preflight(config, supplied)["allowed"])
        for field in ("synthetic", "temporary_store_registered", "target_year"):
            changed = deepcopy(supplied)
            del changed["simulation_context"][field]
            self.assertFalse(preflight(config, changed, now=NOW)["allowed"])
        for field in ("synthetic", "temporary_store_registered"):
            changed = deepcopy(supplied)
            changed["simulation_context"][field] = 1
            self.assertFalse(preflight(config, changed, now=NOW)["allowed"])

    def test_active_preflight_performs_no_file_or_network_io(self):
        config = settings()
        supplied = artifacts(config)
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected open")), \
             mock.patch("socket.socket", side_effect=AssertionError("unexpected network")), \
             mock.patch("sqlite3.connect", side_effect=AssertionError("unexpected database")):
            self.assertTrue(preflight(config, supplied, now=NOW)["allowed"])

    def test_config_namespace_storage_and_code_changes_require_new_pins(self):
        for field, new in (("namespace", "PRODUCTION"), ("storage_root", "/tmp/another-store"),
                           ("storage_identity", "ANOTHER_STORE"), ("code_commit", "b"*40),
                           ("input_classification", "HQ14_PRIVATE_OFFLINE")):
            config = settings()
            config[field] = new
            self.assertFalse(preflight(config, artifacts(settings()), now=NOW)["allowed"])

    def test_bad_settings_and_unsafe_roots_hold(self):
        for change in ({"enabled": 1}, {"enabled": "true"}, {"storage_root": "/"},
                       {"storage_root": "/tmp/../production"}, {"storage_root": "relative"},
                       {"code_commit": "unknown"}, {"mode": "LIVE"}, {"surprise": True}):
            config = settings()
            config.update(change)
            self.assertFalse(validate_settings(config)["valid"])

    def test_mutated_or_missing_artifacts_do_not_match_hashes(self):
        config = settings()
        supplied = artifacts(config)
        for key in ("model", "normalizer", "source_mapping", "course_policy", "prediction_config"):
            changed = deepcopy(supplied)
            del changed[key]
            self.assertFalse(preflight(config, changed, now=NOW)["allowed"])
        changed = deepcopy(supplied)
        changed["source_mapping"]["new_mapping"] = True
        self.assertFalse(preflight(config, changed, now=NOW)["allowed"])

    def test_prediction_config_is_hash_bound_and_values_checked(self):
        config = settings()
        supplied = artifacts(config)
        supplied["prediction_config"] = {"market_weight": 1}
        self.assertFalse(preflight(config, supplied, now=NOW)["allowed"])
        supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
        self.assertTrue(preflight(config, supplied, now=NOW)["allowed"])
        for wrong in ({"market_weight": True}, {"temperature": 0}, {"market_weight": 2},
                      {"selection": "default"}, {"temperature": 10**1000}, {"future_option": True}):
            supplied["prediction_config"] = wrong
            supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
            self.assertFalse(preflight(config, supplied, now=NOW)["allowed"])

    def test_future_or_unknown_model_training_and_normalizer_cutoffs_hold(self):
        for owner, field in (("model", "training_max_available_at"), ("model", "training_max_prediction_at"),
                             ("normalizer", "fit_cutoff"), ("normalizer", "training_max_available_at")):
            for wrong in (None, NOW.isoformat(), (NOW+timedelta(seconds=1)).isoformat(), "2099-01-01T00:00:00"):
                config = settings()
                supplied = artifacts(config)
                target = supplied[owner]["base_model"] if owner == "model" else supplied[owner]
                target[field] = wrong
                hashkey = "self_sha256" if owner == "model" else "normalizer_sha256"
                supplied[owner][hashkey] = digest({k:v for k,v in supplied[owner].items() if k != hashkey})
                supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
                self.assertFalse(preflight(config, supplied, now=NOW)["allowed"])

    def test_model_course_and_artifact_self_hashes_are_bound(self):
        config = settings()
        for key in ("model", "normalizer"):
            supplied = artifacts(config)
            supplied[key]["unexpected_field"] = True
            supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
            self.assertFalse(preflight(config, supplied, now=NOW)["allowed"])
        supplied = artifacts(config)
        supplied["course_policy"]["different"] = True
        supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
        self.assertFalse(preflight(config, supplied, now=NOW)["allowed"])

    def test_private_missing_bundle_never_launches(self):
        config = settings("PRIVATE_SHADOW")
        supplied = artifacts(config, private=True)
        report = preflight(config, supplied, operator_ack=OPERATION, now=NOW)
        self.assertFalse(report["allowed"])
        self.assertIn("BOUND_APPROVAL_BUNDLE_REQUIRED", report["reasons"])

    def test_complete_invented_private_statements_only_structurally_match(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        report = preflight(config, supplied, ack, NOW)
        self.assertTrue(report["allowed"])
        self.assertEqual(report["status"], "PRIVATE_ATTESTED_PREFLIGHT_ONLY")
        self.assertIn("UNVERIFIED", report["independent_approval_authenticity"])
        self.assertEqual(report["actual_execution_go"], "NOT_ESTABLISHED_BY_PREFLIGHT")
        self.assertFalse(report["production_go"])
        self.assertFalse(report["auto_start"])

    def test_each_authority_evidence_and_actual_operator_ack_required(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        for authority in ("HQ14", "CLAUDE", "ANDY"):
            changed = deepcopy(supplied)
            del changed["approval_bundle"]["reviews"][authority]
            self.assertFalse(preflight(config, changed, ack, NOW)["allowed"])
        for wrong in (None, OPERATION, {**ack, "operator_id": "ANOTHER_OPERATOR"},
                      {**ack, "evidence_checked_outside_this_program": False},
                      {**ack, "bindings_sha256": "b"*64}):
            self.assertFalse(preflight(config, supplied, wrong, NOW)["allowed"])

    def test_wrong_operation_and_bound_artifact_changes_hold_even_rehashed(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        supplied["evaluation_plan"]["changed_after_approval"] = True
        supplied["artifact_sha256s"] = artifact_fingerprints(supplied, "PRIVATE_SHADOW")
        self.assertFalse(preflight(config, supplied, ack, NOW)["allowed"])
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        supplied["approval_bundle"]["operation"] = "DEPLOY"
        self.assertFalse(preflight(config, supplied, ack, NOW)["allowed"])

    def test_review_expiry_and_operator_attestation_clock_checked(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        self.assertFalse(preflight(config, supplied, ack, NOW+timedelta(hours=1))["allowed"])
        self.assertFalse(preflight(config, supplied, ack, NOW-timedelta(hours=2))["allowed"])
        ack["attested_at"] = (NOW+timedelta(seconds=1)).isoformat()
        self.assertFalse(preflight(config, supplied, ack, NOW)["allowed"])

    def test_malformed_offset_normalization_cannot_authorize_context(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        targets = [("bundle", None, field) for field in ("valid_from", "valid_until")]
        targets += [("review", authority, field) for authority in ("HQ14", "CLAUDE", "ANDY")
                    for field in ("valid_from", "valid_until")]
        targets.append(("ack", None, "attested_at"))
        for owner, authority, field in targets:
            changed, changed_ack = deepcopy(supplied), deepcopy(ack)
            target = (changed_ack if owner == "ack" else changed["approval_bundle"]
                      if owner == "bundle" else changed["approval_bundle"]["reviews"][authority])
            same_instant = datetime.fromisoformat(target[field]).astimezone(timezone(timedelta(hours=9))).isoformat()
            target[field] = same_instant.replace("+09:00", "+08:60")
            with self.subTest(owner=owner, authority=authority, field=field):
                self.assertFalse(preflight(config, changed, changed_ack, NOW)["allowed"])
        self.assertFalse(preflight(config, supplied, ack, "2099-01-05T12:00:00+00:60")["allowed"])

    def test_distinct_review_metadata_and_unresolved_gates_hold(self):
        config = settings("PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, artifacts(config, private=True))
        review = supplied["approval_bundle"]["reviews"]
        review["ANDY"]["evidence_sha256"] = review["HQ14"]["evidence_sha256"]
        self.assertFalse(preflight(config, supplied, ack, NOW)["allowed"])
        supplied = artifacts(config, private=True)
        supplied["evaluation_plan"]["open_items"] = ["F5_NOT_DECIDED"]
        supplied["artifact_sha256s"] = artifact_fingerprints(supplied, "PRIVATE_SHADOW")
        supplied, ack = approve_for_test(config, supplied)
        self.assertFalse(preflight(config, supplied, ack, NOW)["allowed"])

    def test_hashes_and_reports_do_not_mutate_or_echo_private_payload(self):
        config = settings()
        supplied = artifacts(config)
        supplied["source_mapping"]["private_note"] = "/private/internal/path?token=DO_NOT_ECHO"
        supplied["artifact_sha256s"] = artifact_fingerprints(supplied)
        original = deepcopy((config, supplied))
        report = preflight(config, supplied, now=NOW)
        self.assertEqual((config, supplied), original)
        raw = json.dumps(report, allow_nan=False)
        self.assertNotIn("DO_NOT_ECHO", raw)
        self.assertNotIn("/private/internal", raw)


if __name__ == "__main__":
    main()
