"""Synthetic-only RAW contract and normalization leakage regression tests."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import unittest

from model11.preparation.adapter import (
    fit_normalizer, make_raw_fixture, normalize_race, synthetic_feature_specs,
    validate_raw_race,
)
from model11.synthetic import make_dataset
from model11.validation import FEATURES, validate_race


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = make_dataset(days=6, races_per_day=1, seed=741)["races"]
        cls.raws = [make_raw_fixture(race) for race in cls.canonical]

    def setup_fit(self):
        specs = synthetic_feature_specs()
        training = deepcopy(self.raws[:3])
        normalizer = fit_normalizer(training, self.raws[3]["prediction_at"], specs)
        return training, normalizer, specs

    def test_full_raw_contract_synthetic_only(self):
        for raw in self.raws:
            report = validate_raw_race(raw, synthetic_feature_specs())
            self.assertTrue(report["eligible"], report)
            self.assertEqual(report["external_authenticity"], "UNVERIFIED")
            self.assertEqual(report["real_mapping"], "OPEN")
            self.assertFalse(report["production_go"])
            self.assertEqual(len(raw["odds_snapshot"]["odds"]), 120)

    def test_explicit_unit_direction_and_no_implicit_transform(self):
        for name in FEATURES:
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"][name]["unit"] = "unknown_unit"
            self.assertIn("RAW_FEATURE_UNIT_MISMATCH", validate_raw_race(raw, synthetic_feature_specs())["errors"])
        specs = synthetic_feature_specs()
        specs["features"]["st"]["unit"] = "milliseconds"
        self.assertIn("FEATURE_UNIT_UNREGISTERED", validate_raw_race(self.raws[0], specs)["errors"])
        with self.assertRaisesRegex(ValueError, "FEATURE_SPECS_INVALID"):
            fit_normalizer(self.raws[:3], self.raws[3]["prediction_at"], specs)
        for field, value, code in (("direction", "AUTO", "FEATURE_DIRECTION_UNREGISTERED"),
                                   ("normalization", "AUTO", "NORMALIZATION_NOT_EXPLICITLY_SUPPORTED")):
            specs = synthetic_feature_specs()
            specs["features"]["st"][field] = value
            self.assertIn(code, validate_raw_race(self.raws[0], specs)["errors"])

    def test_every_feature_has_three_times_and_evidence(self):
        for name in FEATURES:
            for field in ("acquired_at", "available_at", "revision_at", "evidence_sha256"):
                raw = deepcopy(self.raws[0])
                del raw["boats"][0]["features"][name][field]
                self.assertFalse(validate_raw_race(raw, synthetic_feature_specs())["eligible"])

    def test_late_and_posthoc_feature_revisions_rejected(self):
        for name in FEATURES:
            for field in ("acquired_at", "available_at", "revision_at"):
                raw = deepcopy(self.raws[0])
                raw["boats"][0]["features"][name][field] = raw["deadline"]["value"]
                report = validate_raw_race(raw, synthetic_feature_specs())
                self.assertIn("RAW_FEATURE_LATE_OR_FUTURE_REVISION", report["errors"])
                with self.assertRaisesRegex(ValueError, "TRAINING_RAW_INVALID"):
                    fit_normalizer([raw], self.raws[3]["prediction_at"], synthetic_feature_specs())

    def test_naive_unknown_offset_overprecision_rejected(self):
        for value in ("2099-01-01T12:00:00", "2099-01-01T12:00:00-00:00",
                      "2099-01-01T12:00:00.1234567+09:00"):
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"]["st"]["available_at"] = value
            self.assertFalse(validate_raw_race(raw, synthetic_feature_specs())["eligible"])

    def test_state_deadline_race_and_motor_provenance_required(self):
        for which in ("race", "active", "deadline", "course", "fl", "scratched", "motor"):
            raw = deepcopy(self.raws[0])
            items = {"race": raw["race_provenance"], "active": raw["active_boats_provenance"],
                     "deadline": raw["deadline"], "motor": raw["boats"][0]["motor_identity"],
                     **{key: raw["boats"][0][key] for key in ("course", "fl", "scratched")}}
            del items[which]["evidence_sha256"]
            self.assertFalse(validate_raw_race(raw, synthetic_feature_specs())["eligible"])
            raw = deepcopy(self.raws[0])
            if which in ("course", "fl", "scratched"):
                raw["boats"][0][which]["available_at"] = raw["deadline"]["value"]
                self.assertFalse(validate_raw_race(raw, synthetic_feature_specs())["eligible"])

    def test_motor_identity_version_and_effective_date(self):
        for field in ("motor_id", "motor_version"):
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"]["motor"][field] = "SYNTHETIC_WRONG"
            self.assertIn("RAW_MOTOR_IDENTITY_OR_VERSION_MISMATCH", validate_raw_race(raw, synthetic_feature_specs())["errors"])
        raw = deepcopy(self.raws[0])
        raw["boats"][0]["motor_identity"]["effective_at"] = raw["deadline"]["value"]
        self.assertIn("RAW_MOTOR_EFFECTIVE_TIME_INVALID", validate_raw_race(raw, synthetic_feature_specs())["errors"])
        raw = deepcopy(self.raws[0])
        raw["boats"][0]["motor_identity"]["revision_at"] = raw["deadline"]["value"]
        self.assertIn("RAW_MOTOR_IDENTITY_LATE_OR_FUTURE_REVISION", validate_raw_race(raw, synthetic_feature_specs())["errors"])

    def test_motor_stat_times_bound_to_current_identity_effective_time(self):
        for field in ("acquired_at", "available_at", "revision_at"):
            raw = deepcopy(self.raws[0])
            boat = raw["boats"][0]
            effective = datetime.fromisoformat(boat["motor_identity"]["effective_at"])
            boat["features"]["motor"][field] = (effective - timedelta(hours=1)).isoformat()
            report = validate_raw_race(raw, synthetic_feature_specs())
            self.assertFalse(report["eligible"])
            self.assertIn("RAW_MOTOR_STAT_PREDATES_IDENTITY_EFFECTIVE", report["errors"])
        raw = deepcopy(self.raws[0])
        boat = raw["boats"][0]
        for field in ("acquired_at", "available_at", "revision_at"):
            boat["features"]["motor"][field] = boat["motor_identity"]["effective_at"]
        self.assertTrue(validate_raw_race(raw, synthetic_feature_specs())["eligible"])

    def test_missing_feature_and_exhibition_never_zero_imputed(self):
        for value in (None, True, "0", float("nan")):
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"]["exhibition"]["value"] = value
            self.assertFalse(validate_raw_race(raw, synthetic_feature_specs())["eligible"])
        raw = deepcopy(self.raws[0])
        del raw["boats"][0]["features"]["exhibition"]
        self.assertIn("RAW_FEATURE_DOMAIN", validate_raw_race(raw, synthetic_feature_specs())["errors"])

    def test_forbidden_labels_ab_predictions_and_unknown_source(self):
        for key in ("result", "payout_per_100", "actual", "predictions", "A_prediction", "B_prediction", "legacy_model10"):
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"]["st"][key] = "PRIVATE_NOT_OUTPUT"
            report = validate_raw_race(raw, synthetic_feature_specs())
            self.assertFalse(report["eligible"])
            self.assertIn("FORBIDDEN_OUTCOME_OR_LEGACY_INPUT", report["errors"])
            self.assertNotIn("PRIVATE_NOT_OUTPUT", json.dumps(report))
        for source in ("A", "B", "MODEL1.0"):
            raw = deepcopy(self.raws[0])
            raw["source"] = source
            self.assertIn("FORBIDDEN_AB_SOURCE_INPUT", validate_raw_race(raw, synthetic_feature_specs())["errors"])
        raw = deepcopy(self.raws[0])
        raw["boats"][0]["features"]["st"]["source"] = "UNKNOWN"
        self.assertIn("RAW_FEATURE_FIELDS_UNREGISTERED_OR_MISSING", validate_raw_race(raw, synthetic_feature_specs())["errors"])

    def test_unknown_feature_schema_shape_rejected(self):
        raw = deepcopy(self.raws[0])
        raw["boats"][0]["features"]["arbitrary"] = 0
        self.assertIn("RAW_FEATURE_DOMAIN", validate_raw_race(raw, synthetic_feature_specs())["errors"])
        raw = deepcopy(self.raws[0])
        raw["boats"][0]["course"]["source"] = "UNKNOWN"
        self.assertIn("RAW_STATE_FIELDS", validate_raw_race(raw, synthetic_feature_specs())["errors"])

    def test_train_fit_records_frozen_inputs_and_stats(self):
        training, norm, specs = self.setup_fit()
        self.assertEqual(norm["training_race_ids"], sorted(raw["race_id"] for raw in training))
        self.assertEqual(len(norm["training_input_sha256"]), 64)
        self.assertEqual(len(norm["feature_specs_sha256"]), 64)
        self.assertEqual(len(norm["normalizer_sha256"]), 64)
        self.assertEqual(norm["feature_specs"], specs)
        self.assertEqual(norm["status"], "PROPOSED")
        for name in FEATURES:
            vals = [boat["features"][name]["value"] for raw in training for boat in raw["boats"]]
            self.assertEqual(norm["statistics"][name]["min"], min(vals))
            self.assertEqual(norm["statistics"][name]["max"], max(vals))
            self.assertEqual(norm["statistics"][name]["count"], 18)

    def test_no_data_constant_statistics_and_duplicates_stop(self):
        with self.assertRaisesRegex(ValueError, "TRAINING_DATA_MISSING"):
            fit_normalizer([], self.raws[3]["prediction_at"], synthetic_feature_specs())
        training = deepcopy(self.raws[:2])
        for raw in training:
            for boat in raw["boats"]:
                boat["features"]["st"]["value"] = 0.1
        with self.assertRaisesRegex(ValueError, "TRAIN_FEATURE_STATISTICS_ABSENT_OR_CONSTANT"):
            fit_normalizer(training, self.raws[3]["prediction_at"], synthetic_feature_specs())
        with self.assertRaisesRegex(ValueError, "TRAINING_RACE_DUPLICATE"):
            fit_normalizer([self.raws[0], self.raws[0]], self.raws[3]["prediction_at"], synthetic_feature_specs())

    def test_future_train_and_cutoff_boundary_rejected(self):
        for cutoff in (self.raws[0]["prediction_at"], self.raws[0]["race_provenance"]["acquired_at"]):
            with self.assertRaisesRegex(ValueError, "TRAINING_NOT_BEFORE_FIT_CUTOFF"):
                fit_normalizer(self.raws[:2], cutoff, synthetic_feature_specs())
        with self.assertRaisesRegex(ValueError, "FIT_CUTOFF_INVALID"):
            fit_normalizer(self.raws[:2], "2099-01-01", synthetic_feature_specs())

    def test_default_cannot_forecast_past_with_future_fitted_stats(self):
        _, norm, _ = self.setup_fit()
        with self.assertRaisesRegex(ValueError, "NORMALIZER_NOT_AVAILABLE_AT_PREDICTION"):
            normalize_race(self.raws[0], norm)
        with self.assertRaisesRegex(ValueError, "NORMALIZER_NOT_AVAILABLE_AT_PREDICTION"):
            normalize_race(self.raws[3], norm)  # exact cutoff is not after fit

    def test_training_usage_explicit_frozen_members_only(self):
        _, norm, _ = self.setup_fit()
        output = normalize_race(self.raws[0], norm, usage="training")
        self.assertEqual(output["audit"]["status"], "TRAINING_ONLY_NOT_FORECAST")
        self.assertEqual(output["race"]["normalization_usage"], "TRAINING_ONLY_NOT_FORECAST")
        with self.assertRaisesRegex(ValueError, "TRAINING_USAGE_REQUIRES_FROZEN_TRAINING_ID"):
            normalize_race(self.raws[4], norm, usage="training")
        changed = deepcopy(self.raws[0])
        changed["boats"][0]["features"]["st"]["value"] += 0.01
        with self.assertRaisesRegex(ValueError, "TRAINING_RECORD_CHANGED"):
            normalize_race(changed, norm, usage="training")

    def test_holdout_outlier_never_refits_training_statistics(self):
        training, norm, _ = self.setup_fit()
        frozen = deepcopy(norm)
        raw = deepcopy(self.raws[4])
        raw["boats"][0]["features"]["ability"]["value"] = 100000
        source = deepcopy(raw)
        result = normalize_race(raw, norm)
        self.assertEqual(norm, frozen)
        self.assertEqual(raw, source)
        self.assertEqual(result["race"]["boats"][0]["features"]["ability"], 1.0)
        self.assertIn({"boat": 1, "feature": "ability", "code": "OUTSIDE_TRAINING_RANGE_CLIPPED"}, result["audit"]["clipped"])
        self.assertTrue(validate_race(result["race"])["eligible"])
        self.assertFalse(result["audit"]["production_go"])
        self.assertEqual(len(training), 3)

    def test_lower_direction_st_and_exhibition_inverted_explicitly(self):
        _, norm, _ = self.setup_fit()
        raw = deepcopy(self.raws[4])
        for name in ("st", "exhibition"):
            raw["boats"][0]["features"][name]["value"] = norm["statistics"][name]["min"]
        for name in ("turn", "motor", "ability"):
            raw["boats"][0]["features"][name]["value"] = norm["statistics"][name]["max"]
        out = normalize_race(raw, norm)
        self.assertTrue(all(out["race"]["boats"][0]["features"][name] == 1.0 for name in FEATURES))

    def test_normalizer_tamper_and_bad_input_stop(self):
        _, norm, _ = self.setup_fit()
        norm["statistics"]["st"]["max"] += 0.1
        with self.assertRaisesRegex(ValueError, "NORMALIZER_HASH_MISMATCH"):
            normalize_race(self.raws[4], norm)
        _, norm, _ = self.setup_fit()
        with self.assertRaisesRegex(ValueError, "NORMALIZATION_USAGE_INVALID"):
            normalize_race(self.raws[4], norm, usage="auto")

    def test_recomputed_self_hash_cannot_override_inconsistent_metadata(self):
        _, norm, _ = self.setup_fit()
        norm["training_max_available_at"] = self.raws[5]["prediction_at"]
        body = {key: value for key, value in norm.items() if key != "normalizer_sha256"}
        norm["normalizer_sha256"] = sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                                        ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
        with self.assertRaisesRegex(ValueError, "NORMALIZER_METADATA_INVALID"):
            normalize_race(self.raws[4], norm)

    def test_known_unit_domains_do_not_allow_invalid_physical_values(self):
        for name, value in (("st", 0), ("exhibition", -1), ("motor", 1.01), ("turn", 101), ("ability", -1)):
            raw = deepcopy(self.raws[0])
            raw["boats"][0]["features"][name]["value"] = value
            self.assertIn("RAW_FEATURE_UNIT_DOMAIN", validate_raw_race(raw, synthetic_feature_specs())["errors"])

    def test_normalization_provenance_survives_race_handoff(self):
        _, norm, _ = self.setup_fit()
        out = normalize_race(self.raws[4], norm)
        proof = out["race"]["normalization_provenance"]
        self.assertEqual(set(proof), {"normalizer_sha256", "feature_specs_sha256", "fit_cutoff",
                                     "training_max_available_at", "training_input_sha256", "usage"})
        self.assertEqual(proof["normalizer_sha256"], norm["normalizer_sha256"])
        self.assertEqual(proof["usage"], "prediction")
        self.assertEqual(out["audit"]["external_authenticity"], "UNVERIFIED")

    def test_raw_missing_future_invalid_odds_do_not_block_model(self):
        _, norm, _ = self.setup_fit()
        for change in ("missing", "late", "hash", "time", "shape"):
            raw = deepcopy(self.raws[4])
            if change == "missing":
                raw["odds_snapshot"] = None
            elif change == "late":
                raw["odds_snapshot"]["available_at"] = raw["deadline"]["value"]
            elif change == "hash":
                raw["odds_snapshot"]["evidence_sha256"] = "not-a-hash"
            elif change == "time":
                del raw["odds_snapshot"]["available_at"]
            else:
                raw["odds_snapshot"] = []
            self.assertTrue(validate_raw_race(raw, synthetic_feature_specs())["eligible"])
            normalized = normalize_race(raw, norm)
            self.assertIsNone(normalized["race"]["odds_snapshot"])
            self.assertTrue(validate_race(normalized["race"])["eligible"])

    def test_full_120_odds_not_filled_when_incomplete(self):
        raw = deepcopy(self.raws[0])
        del raw["odds_snapshot"]["odds"]["1-2-3"]
        report = validate_raw_race(raw, synthetic_feature_specs())
        self.assertTrue(report["eligible"])
        self.assertIn("ODDS_DOMAIN_MISMATCH", report["warnings"])

    def test_no_implicit_actual_real_fixture_conversion(self):
        for field, value in (("synthetic", False), ("data_classification", "REAL"), ("target_date", "2026-11-05")):
            race = deepcopy(self.canonical[0])
            race[field] = value
            with self.assertRaisesRegex(ValueError, "SYNTHETIC_FIXTURE_ONLY"):
                make_raw_fixture(race)

    def test_synthetic_unit_mapping_rejected_for_claimed_private_data(self):
        raw = deepcopy(self.raws[0])
        raw["data_classification"] = "HQ14_PRIVATE_OFFLINE"  # still invented fixture
        report = validate_raw_race(raw, synthetic_feature_specs())
        self.assertFalse(report["eligible"])
        self.assertIn("SYNTHETIC_MAPPING_FORBIDDEN_FOR_PRIVATE_DATA", report["errors"])
        with self.assertRaisesRegex(ValueError, "TRAINING_RAW_INVALID"):
            fit_normalizer([raw], self.raws[3]["prediction_at"], synthetic_feature_specs())

    def test_private_mapping_requires_both_review_metadata_hashes(self):
        raw = deepcopy(self.raws[0])
        raw["data_classification"] = "HQ14_PRIVATE_OFFLINE"  # never real data
        specs = synthetic_feature_specs()
        specs["mapping_status"] = "HQ14_PRIVATE_MAPPING_UNVERIFIED"
        self.assertFalse(validate_raw_race(raw, specs)["eligible"])
        for evidence in (None, {}, {"hq14_review_sha256": "a" * 64},
                         {"hq14_review_sha256": "a" * 64, "claude_review_sha256": "bad"}):
            specs["review_evidence"] = evidence
            self.assertIn("PRIVATE_MAPPING_REVIEW_METADATA_MISSING_OR_INVALID",
                          validate_raw_race(raw, specs)["errors"])
            with self.assertRaisesRegex(ValueError, "FEATURE_SPECS_INVALID"):
                fit_normalizer([raw], self.raws[3]["prediction_at"], specs)

    def test_dummy_review_hash_presence_never_authenticates_or_grants_go(self):
        raw = deepcopy(self.raws[0])
        raw["data_classification"] = "HQ14_PRIVATE_OFFLINE"
        specs = synthetic_feature_specs()
        specs["mapping_status"] = "HQ14_PRIVATE_MAPPING_UNVERIFIED"
        specs["review_evidence"] = {"hq14_review_sha256": "a" * 64,
                                    "claude_review_sha256": "b" * 64}
        report = validate_raw_race(raw, specs)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["review_evidence_status"], "SELF_REPORTED_HASHES_ONLY")
        self.assertEqual(report["external_authenticity"], "UNVERIFIED")
        self.assertEqual(report["real_mapping"], "OPEN")
        self.assertFalse(report["production_go"])
        norm = fit_normalizer([raw], self.raws[3]["prediction_at"], specs)
        self.assertEqual(norm["external_authenticity"], "UNVERIFIED")
        self.assertFalse(norm["production_go"])


if __name__ == "__main__":
    unittest.main()
