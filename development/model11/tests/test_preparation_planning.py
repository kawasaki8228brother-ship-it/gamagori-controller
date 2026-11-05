"""Invented protocol checks only; no real pilot/outcome or external approvals."""
from copy import deepcopy
from itertools import permutations
import json
import math
import unittest

from model11.preparation.planning import (
    PRIMARY, equal_day_logloss_estimand, paired_cluster_sample_size, protocol_readiness,
)


def record(identity, day, ratio=1.0):
    market = {"-".join(map(str, p)): 1/120 for p in permutations(range(1, 7), 3)}
    candidate = {key: (1-ratio/120)/119 for key in market}
    candidate["1-2-3"] = ratio/120
    return {"race_id": identity, "target_date": day, "model_sha256": "a"*64,
            "prediction_at": f"{day}T12:00:00+09:00", "deadline": f"{day}T12:05:00+09:00",
            "distributions": {"P_market": market, "P_shrunk": candidate},
            "actual": {"race_id": identity, "target_date": day, "result": [1, 2, 3],
                       "final": True, "available_at": f"{day}T12:10:00+09:00"}}


def protocol():
    fields = ("candidate_sha256", "parameters_sha256", "input_schema_sha256",
              "split_plan_sha256", "sealed_holdout_ids_sha256", "seal_receipt_sha256",
              "approval_raw_sha256", "hypothesis_family_sha256",
              "pilot_variance_receipt_sha256", "serial_dependence_review_sha256")
    return {**{field: "a"*64 for field in fields},
            "protocol_id": "SYNTHETIC_TEST_NOT_REAL_APPROVAL", "review_authority": "SYNTHETIC_TEST",
            "training_cutoff": "2026-11-01T00:00:00+09:00",
            "selection_cutoff": "2026-11-08T00:00:00+09:00",
            "holdout_start": "2026-11-21T00:00:00+09:00",
            "holdout_end": "2028-01-01T00:00:00+09:00",
            "primary_metric": PRIMARY, "comparator": "P_market",
            "multiplicity": "SINGLE_FROZEN_CHAMPION", "comparisons": 1,
            "sd_day": 0.1, "effect": 0.02, "power": 0.8, "alpha": 0.025,
            "planned_holdout_days": 400}


class SampleSizeTests(unittest.TestCase):
    def test_known_normal_vectors_and_days_not_races(self):
        self.assertEqual(paired_cluster_sample_size(1, 1)["required_days"], 8)
        estimate = paired_cluster_sample_size(0.1, 0.02)
        self.assertEqual(estimate["required_days"], 197)
        self.assertEqual(estimate["unit"], "PAIRED_DAY_CLUSTERS_NOT_RACES")
        self.assertFalse(estimate["production_go"])

    def test_multiplicity_power_variance_and_effect_monotonicity(self):
        baseline = paired_cluster_sample_size(0.1, 0.02)["required_days"]
        self.assertGreater(paired_cluster_sample_size(0.1, 0.02, comparisons=3)["required_days"], baseline)
        self.assertGreater(paired_cluster_sample_size(0.1, 0.02, power=0.9)["required_days"], baseline)
        self.assertGreater(paired_cluster_sample_size(0.2, 0.02)["required_days"], baseline)
        self.assertLess(paired_cluster_sample_size(0.1, 0.04)["required_days"], baseline)

    def test_unknown_or_zero_variance_does_not_imply_zero_days(self):
        for value in (None, 0):
            estimate = paired_cluster_sample_size(value, 0.02)
            self.assertEqual(estimate["status"], "UNVERIFIED")
            self.assertIsNone(estimate["required_days"])

    def test_invalid_controls_and_numerical_limits_stop(self):
        attempts = ((-1, .02, .8, .025, 1), (float("nan"), .02, .8, .025, 1),
                    (1, 0, .8, .025, 1), (1, 1, .5, .025, 1),
                    (1, 1, .8, 0, 1), (1, 1, .8, .025, True),
                    (1e308, 1e-308, .8, .025, 1), (1, 1, .8, 1e-300, 1))
        for arguments in attempts:
            with self.subTest(arguments=arguments):
                estimate = paired_cluster_sample_size(*arguments)
                self.assertEqual(estimate["status"], "STOP")
                self.assertIsNone(estimate["required_days"])
                json.dumps(estimate, allow_nan=False)


class EstimandTests(unittest.TestCase):
    def test_equal_day_mean_is_distinct_from_race_weighted_mean(self):
        rows = [record("one", "2099-01-01", math.exp(1)),
                record("two", "2099-01-02", 1), record("three", "2099-01-02", 1),
                record("four", "2099-01-02", 1)]
        original = deepcopy(rows)
        report = equal_day_logloss_estimand(rows)
        self.assertAlmostEqual(report["equal_day_mean_delta"], 0.5)
        self.assertAlmostEqual(report["race_weighted_mean_delta_comparison_only"], 0.25)
        self.assertEqual(report["finite_day_clusters"], 2)
        self.assertEqual(report["finite_paired_races"], 4)
        self.assertEqual(report["confirmatory_test"], "NOT_PERFORMED")
        self.assertEqual(rows, original)

    def test_missing_market_is_coverage_gap_not_zero_loss(self):
        rows = [record("known", "2099-01-01", 2), record("missing", "2099-01-02")]
        rows[1]["distributions"]["P_market"] = None
        report = equal_day_logloss_estimand(rows)
        self.assertEqual(report["unavailable_pair_races"], 1)
        self.assertEqual(report["finite_paired_races"], 1)
        self.assertAlmostEqual(report["equal_day_mean_delta"], math.log(2))
        self.assertTrue(report["status"].startswith("UNVERIFIED"))

    def test_zero_probability_is_infinite_not_hidden_epsilon(self):
        rows = [record("zero", "2099-01-01", 0)]
        report = equal_day_logloss_estimand(rows)
        self.assertEqual(report["nonfinite_pair_races"], 1)
        self.assertIsNone(report["equal_day_mean_delta"])
        self.assertIn("INFINITE", report["issues"][0]["reason"])
        json.dumps(report, allow_nan=False)
        mixed = equal_day_logloss_estimand(rows + [record("finite", "2099-01-02", 2)])
        self.assertIsNone(mixed["equal_day_mean_delta"])
        self.assertAlmostEqual(mixed["finite_observed_equal_day_mean_delta"], math.log(2))

    def test_repeated_or_mismatched_outcomes_are_not_independent_samples(self):
        row = record("duplicate", "2099-01-01")
        report = equal_day_logloss_estimand([row, deepcopy(row)])
        self.assertEqual(report["finite_paired_races"], 0)
        changed = deepcopy(row)
        changed["actual"]["race_id"] = "another"
        self.assertEqual(equal_day_logloss_estimand([changed])["finite_paired_races"], 0)

    def test_invalid_probabilities_or_domains_not_repaired(self):
        for value in (-0.1, math.nan, math.inf, 0.7):
            row = record("invalid", "2099-01-01")
            row["distributions"]["P_shrunk"]["1-2-3"] = value
            self.assertEqual(equal_day_logloss_estimand([row])["finite_paired_races"], 0)
        row = record("domain", "2099-01-01")
        row["distributions"]["P_market"]["1-1-2"] = row["distributions"]["P_market"].pop("1-2-3")
        self.assertEqual(equal_day_logloss_estimand([row])["finite_paired_races"], 0)

    def test_multiple_models_or_single_day_do_not_become_frozen_evidence(self):
        rows = [record("one", "2099-01-01"), record("two", "2099-01-02")]
        rows[1]["model_sha256"] = "b"*64
        report = equal_day_logloss_estimand(rows)
        self.assertIn("MULTIPLE", report["frozen_candidate_evidence"])
        self.assertIsNone(equal_day_logloss_estimand(rows[:1])["sample_sd_day_exploratory"])
        self.assertFalse(report["production_go"])


class ProtocolTests(unittest.TestCase):
    def test_complete_self_report_is_only_ready_for_review(self):
        report = protocol_readiness(protocol())
        self.assertEqual(report["status"], "READY_FOR_REVIEW")
        self.assertIn("UNVERIFIED", report["evidence_authenticity"])
        self.assertEqual(report["review_outcome"], "NOT_GRANTED")
        self.assertFalse(report["production_go"])

    def test_four_day_shadow_candidate_is_not_formal_power(self):
        inputs = protocol()
        inputs["planned_holdout_days"] = 4
        report = protocol_readiness(inputs)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("INSUFFICIENT_PLANNED_DAY_CLUSTERS", report["invalid_fields"])

    def test_missing_hash_variance_cutoffs_and_approval_hold(self):
        inputs = protocol()
        for field in ("approval_raw_sha256", "sealed_holdout_ids_sha256", "sd_day"):
            del inputs[field]
        report = protocol_readiness(inputs)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["sample_size_plan"]["status"], "UNVERIFIED")
        self.assertIn("approval_raw_sha256", report["missing_fields"])

    def test_invalid_chronology_family_and_forged_hash_shape_hold(self):
        for change in ({"selection_cutoff": "2030-01-01T00:00:00+09:00"},
                       {"multiplicity": "SINGLE_FROZEN_CHAMPION", "comparisons": 3},
                       {"multiplicity": []}, {"candidate_sha256": "pretend"},
                       {"holdout_start": "2099-01-01T12:00:00"}):
            inputs = protocol()
            inputs.update(change)
            self.assertEqual(protocol_readiness(inputs)["status"], "HOLD")

    def test_holm_requires_fixed_family_hash_and_conservative_planning(self):
        inputs = protocol()
        inputs.update(multiplicity="HOLM_FIXED_FAMILY", comparisons=3)
        report = protocol_readiness(inputs)
        self.assertEqual(report["status"], "READY_FOR_REVIEW")
        self.assertGreater(report["sample_size_plan"]["required_days"], 197)
        del inputs["hypothesis_family_sha256"]
        self.assertEqual(protocol_readiness(inputs)["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
