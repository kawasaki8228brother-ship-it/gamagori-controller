"""PIT examples are wholly invented 2099 metadata, not historical observations."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from model11.offline_refinements.point_in_time import audit_point_in_time


def sample_fixture():
    snapshot_id = "SYNTHETIC_CAPTURE_001"
    provenance = {"acquired_at": "2099-01-07T12:58:00+09:00", "available_at": "2099-01-07T12:58:10+09:00",
                  "revision_at": "2099-01-07T12:58:05+09:00", "version": "SYNTHETIC_STATS_v001",
                  "snapshot_id": snapshot_id, "source_id": "SYNTHETIC_PIT_SOURCE", "evidence_sha256": "a" * 64}
    from itertools import permutations
    return {"data_classification": "SYNTHETIC_ONLY", "synthetic": True,
            "race_id": "SYNTHETIC_20990107_R01", "target_date": "2099-01-07",
            "as_of": "2099-01-07T12:59:00+09:00", "deadline": "2099-01-07T13:00:00+09:00",
            "snapshot": {"mode": "IMMUTABLE_SNAPSHOT", "snapshot_id": snapshot_id,
                         "version": "SYNTHETIC_CAPTURE_v001", "preserved_at": "2099-01-07T12:58:30+09:00",
                         "source_id": "SYNTHETIC_PIT_SOURCE", "content_sha256": "b" * 64, "evidence_sha256": "c" * 64},
            "features": [{"boat": boat, "name": name, "value": 0.0, "unit": "declared_fixture_score",
                          "effective_at": "2099-01-01T00:00:00+09:00", **provenance}
                         for boat in range(1, 7) for name in ("st", "turn", "motor", "ability", "exhibition")],
            "odds": {"kind": "PRE_DEADLINE", "values": {"-".join(map(str, t)): 100.0
                        for t in permutations(range(1, 7), 3)}, **provenance}}


def training_context():
    return {"normalizer_fit_cutoff": "2099-01-06T20:00:00+09:00",
            "model_fit_cutoff": "2099-01-06T21:00:00+09:00",
            "training_rows": [{"prediction_at": "2099-01-05T12:59:00+09:00",
                               "feature_available_at": "2099-01-05T12:58:00+09:00",
                               "label_available_at": "2099-01-05T13:10:00+09:00"}]}


class PointInTimeTests(unittest.TestCase):
    def test_valid_pure_synthetic_is_candidate_not_source_authentication(self):
        sample = sample_fixture()
        before = deepcopy(sample)
        with patch("builtins.open", side_effect=AssertionError("NO_FILE_IO")), \
             patch("socket.socket", side_effect=AssertionError("NO_NETWORK")), \
             patch("sqlite3.connect", side_effect=AssertionError("NO_DB_IO")):
            report = audit_point_in_time(sample)
        self.assertEqual(report["software_check"], "PASS")
        self.assertTrue(report["feature_eligible"])
        self.assertTrue(report["market_eligible"])
        self.assertEqual(report["training_context_status"], "UNVERIFIED_NOT_SUPPLIED")
        self.assertEqual(report["origin_proof"], "SELF_REPORTED_ONLY")
        self.assertEqual(report["external_authenticity"], "UNVERIFIED")
        self.assertEqual(report["application_status"], "HOLD")
        self.assertEqual(report["real_input_status"], "HOLD")
        self.assertFalse(report["production_go"])
        self.assertEqual(sample, before)

    def test_latest_table_missing_version_and_later_archive_never_old_snapshot(self):
        for field, value in (("mode", "LATEST_TABLE"), ("version", "latest"), ("version", None),
                             ("snapshot_id", None), ("content_sha256", None),
                             ("preserved_at", "2099-01-07T13:10:00+09:00")):
            sample = sample_fixture()
            sample["snapshot"][field] = value
            self.assertEqual(audit_point_in_time(sample)["status"], "HOLD")
        for component, prefix in (("feature", "FEATURE"), ("odds", "ODDS")):
            for field in ("acquired_at", "available_at", "revision_at"):
                sample = sample_fixture()
                target = sample["features"][0] if component == "feature" else sample["odds"]
                target[field] = "2099-01-07T12:58:59+09:00"  # beforeasof but after preservedversion
                report = audit_point_in_time(sample)
                self.assertEqual(report["status"], "HOLD")
                self.assertIn(prefix + "_SOURCE_TIME_AFTER_SNAPSHOT_PRESERVATION", report["reasons"])

    def test_later_statistical_revision_rejected_even_earlier_effective_date(self):
        for name in ("st", "turn", "motor", "ability", "exhibition"):
            for field in ("acquired_at", "available_at", "revision_at"):
                sample = sample_fixture()
                feature = next(item for item in sample["features"] if item["boat"] == 1 and item["name"] == name)
                feature[field] = "2099-01-07T14:00:00+09:00"  # later backfilled statistics
                self.assertLess(feature["effective_at"], sample["as_of"])
                report = audit_point_in_time(sample)
                self.assertFalse(report["feature_eligible"])
                self.assertTrue(report["market_eligible"])
                self.assertIn("FEATURE_UPDATED_OR_AVAILABLE_AFTER_AS_OF", report["feature_reasons"])
                self.assertEqual(report["status"], "HOLD")

    def test_effective_version_source_sha_and_snapshot_binding_required(self):
        for field, value in (("effective_at", "2099-01-07T13:10:00+09:00"),
                             ("effective_at", None), ("version", "current"), ("source_id", None),
                             ("evidence_sha256", None), ("snapshot_id", "SYNTHETIC_WRONG_CAPTURE")):
            sample = sample_fixture()
            sample["features"][0][field] = value
            self.assertFalse(audit_point_in_time(sample)["feature_eligible"])

    def test_result_payout_or_other_label_feature_is_rejected(self):
        for key in ("result", "payout_per_100", "outcome", "actual"):
            sample = sample_fixture()
            sample["features"][0][key] = "SYNTHETIC_LABEL_NOT_A_FEATURE"
            report = audit_point_in_time(sample)
            self.assertFalse(report["feature_eligible"])
            self.assertIn("FEATURE_OR_PAYLOAD_LABEL_LEAKAGE_OR_INVALID_JSON", report["reasons"])
        sample = sample_fixture()
        sample["features"][0]["name"] = "result"
        self.assertFalse(audit_point_in_time(sample)["feature_eligible"])

    def test_missing_bool_nonfinite_duplicate_and_unknown_features_not_imputed(self):
        for value in (None, True, "0", float("nan"), float("inf")):
            sample = sample_fixture()
            sample["features"][0]["value"] = value
            self.assertFalse(audit_point_in_time(sample)["feature_eligible"])
        for kind in ("missing", "duplicate", "unknown"):
            sample = sample_fixture()
            if kind == "missing": sample["features"].pop()
            elif kind == "duplicate": sample["features"].append(deepcopy(sample["features"][0]))
            else: sample["features"][0]["name"] = "UNREGISTERED_FEATURE"
            self.assertFalse(audit_point_in_time(sample)["feature_eligible"])
        sample = sample_fixture()  # zero is a real fixture observation, not a missing default
        self.assertTrue(audit_point_in_time(sample)["feature_eligible"])

    def test_missing_final_or_postrace_odds_never_substitute_for_predeadline(self):
        for kind in (None, "FINAL", "POST_RACE"):
            sample = sample_fixture()
            if kind is None: sample["odds"] = None
            else: sample["odds"]["kind"] = kind
            report = audit_point_in_time(sample)
            self.assertTrue(report["feature_eligible"])
            self.assertFalse(report["market_eligible"])
            self.assertFalse(report["market_baseline_eligible"])
            self.assertFalse(report["expected_value_eligible"])
            self.assertEqual(report["status"], "HOLD")

    def test_odds_domain_values_version_and_all_snapshot_times_are_gated(self):
        for kind in ("missing_ticket", "invalid_value", "future_acquired", "future_available", "future_revision", "latest_version"):
            sample = sample_fixture()
            if kind == "missing_ticket": del sample["odds"]["values"]["1-2-3"]
            elif kind == "invalid_value": sample["odds"]["values"]["1-2-3"] = None
            elif kind == "latest_version": sample["odds"]["version"] = "LATEST"
            else: sample["odds"][kind.replace("future_", "") + "_at"] = "2099-01-07T13:00:00+09:00"
            report = audit_point_in_time(sample)
            self.assertFalse(report["market_eligible"])
            self.assertEqual(report["status"], "HOLD")

    def test_strict_aware_asof_and_predeadline_boundary_no_rounding(self):
        for value in ("2099-01-07T12:59:00", "2099-01-07T12:59:00-00:00",
                      "2099-01-07T12:59:00.1234567+09:00", "2099-01-07T12:59:00+08:60",
                      "2099-01-07T13:00:00+09:00"):
            sample = sample_fixture()
            sample["as_of"] = value
            self.assertEqual(audit_point_in_time(sample)["status"], "HOLD")

    def test_training_feature_label_and_both_fit_cutoffs_respect_past_only(self):
        sample = sample_fixture()
        sample["training_context"] = training_context()
        self.assertEqual(audit_point_in_time(sample)["training_context_status"], "CLAIMS_CONSISTENT")
        for kind in ("model_cutoff", "normalizer_cutoff", "late_label", "late_feature", "missing_label_time"):
            altered = deepcopy(sample)
            context = altered["training_context"]
            if kind == "model_cutoff": context["model_fit_cutoff"] = altered["as_of"]
            elif kind == "normalizer_cutoff": context["normalizer_fit_cutoff"] = altered["as_of"]
            elif kind == "late_label": context["training_rows"][0]["label_available_at"] = "2099-01-07T00:00:00+09:00"
            elif kind == "late_feature": context["training_rows"][0]["feature_available_at"] = "2099-01-05T13:10:00+09:00"
            else: context["training_rows"][0]["label_available_at"] = None
            report = audit_point_in_time(altered)
            self.assertEqual(report["training_context_status"], "HOLD")
            self.assertEqual(report["status"], "HOLD")

    def test_real_missing_and_conflicting_classification_remain_hold(self):
        for sample in (None, {}, {"data_classification": "PRIVATE_REAL", "synthetic": False},
                       {**sample_fixture(), "synthetic": False}, {**sample_fixture(), "synthetic": 1}):
            report = audit_point_in_time(sample)
            self.assertEqual(report["status"], "HOLD")
            self.assertFalse(report["production_go"])
            self.assertEqual(report["external_authenticity"], "UNVERIFIED")

    def test_safe_diagnostics_never_echo_submitted_source_or_sha_values(self):
        sample = sample_fixture()
        secret = "https://PRIVATE_SECRET:credential@private.invalid/path"
        sample["features"][0]["source_id"] = secret
        sample["snapshot"]["evidence_sha256"] = secret
        report = audit_point_in_time(sample)
        self.assertEqual(report["status"], "HOLD")
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))
        self.assertNotIn("private.invalid", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
