"""Synthetic arithmetic vectors; no external records or network calls."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
import math
import unittest

from model11.metrics import evaluate_records, legacy_adapter


DOMAIN = ["-".join(map(str, p)) for p in itertools.permutations(range(1, 7), 3)]
FIVE = DOMAIN[:5]
BOX = ["-".join(map(str, p)) for p in itertools.permutations((1, 2, 3))]


def uniform():
    return {ticket: 1 / 120 for ticket in DOMAIN}


def record(number=1, result=(1, 2, 3), payout=1000, decision="BET", day="2030-01-01"):
    method = {"boats": [1, 2, 3], "tickets": list(BOX), "bet_decision": decision}
    return {"race_id": f"SYNTHETIC-{number}", "target_date": day,
            "source": "MODEL11_RESEARCH", "first_course": 1,
            "prediction_at": f"{day}T12:{number:02}:00+09:00",
            "deadline": f"{day}T13:00:00+09:00", "active_boats": list(range(1, 7)),
            "selection": {"tickets": list(FIVE), "bet_decision": decision},
            "boxes": {name: copy.deepcopy(method) for name in
                      ("human_research", "mechanical_research", "box_v11_research")},
            "distributions": {name: uniform() for name in ("P_raw", "P_model", "P_market", "P_shrunk")},
            "actual": {"race_id": f"SYNTHETIC-{number}", "target_date": day,
                       "result": list(result), "payout_per_100": payout,
                       "refund_tickets": [], "final": True,
                       "available_at": f"{day}T14:00:00+09:00"}}


class DistributionMetricTests(unittest.TestCase):
    def test_uniform_joint_and_conditional_known_vectors(self):
        result = evaluate_records([record()])
        scores = result["distributions"]["P_model"]
        self.assertAlmostEqual(scores["joint_logloss"]["value"], math.log(120))
        self.assertAlmostEqual(scores["joint_brier"]["value"], 119 / 120)
        self.assertAlmostEqual(scores["conditional_first_logloss"]["value"], math.log(6))
        self.assertAlmostEqual(scores["conditional_second_logloss"]["value"], math.log(5))
        self.assertAlmostEqual(scores["conditional_third_logloss"]["value"], math.log(4))
        self.assertAlmostEqual(sum(scores[f"conditional_{s}_logloss"]["value"]
                                   for s in ("first", "second", "third")), scores["joint_logloss"]["value"])

    def test_zero_actual_is_infinite_not_dropped(self):
        first = record()
        zero = {key: 0.0 for key in DOMAIN}
        zero["6-5-4"] = 1.0
        first["distributions"]["P_model"] = zero
        result = evaluate_records([first, record(2)])
        scores = result["distributions"]["P_model"]
        self.assertEqual(scores["joint_logloss"]["status"], "INFINITE")
        self.assertIsNone(scores["joint_logloss"]["value"])
        self.assertEqual(scores["joint_logloss"]["observed"], 2)
        self.assertEqual(scores["joint_logloss"]["infinite_count"], 1)
        self.assertEqual(scores["joint_logloss"]["coverage"], 1)
        self.assertAlmostEqual(scores["joint_brier"]["value"], (2 + 119 / 120) / 2)
        self.assertEqual(scores["conditional_first_logloss"]["status"], "INFINITE")
        self.assertEqual(scores["conditional_second_logloss"]["missing"], 1)
        paired = result["market_comparisons"]["P_model"]["logloss_difference"]
        self.assertIsNone(paired["value"])
        self.assertEqual(paired["nonfinite_pairs"], 1)
        json.dumps(result, allow_nan=False)

    def test_zero_at_second_conditional_reports_correct_stage(self):
        item = record()
        item["distributions"]["P_model"] = {key: float(key == "1-3-2") for key in DOMAIN}
        scores = evaluate_records([item])["distributions"]["P_model"]
        self.assertEqual(scores["conditional_first_logloss"]["value"], 0)
        self.assertEqual(scores["conditional_second_logloss"]["status"], "INFINITE")
        self.assertEqual(scores["conditional_third_logloss"]["status"], "UNVERIFIED")

    def test_missing_or_invalid_distribution_has_no_zero_metrics(self):
        item = record()
        del item["distributions"]["P_market"]
        item["distributions"]["P_raw"]["1-2-3"] = -1
        item["distributions"]["P_model"].pop("1-2-3")
        result = evaluate_records([item])
        for stage in ("P_raw", "P_model", "P_market"):
            self.assertIsNone(result["distributions"][stage]["joint_brier"]["value"])
            self.assertEqual(result["distributions"][stage]["n"], 0)
        self.assertEqual(result["market_comparisons"]["P_shrunk"]["paired_n"], 0)

    def test_domain_mismatch_is_explicit(self):
        item = record()
        item["active_boats"] = [1, 2, 3]
        result = evaluate_records([item])
        self.assertTrue(any(issue["reason"] == "DISTRIBUTION_ACTIVE_DOMAIN_MISMATCH"
                            for issue in result["record_issues"]))

    def test_calibration_uniform_known_vector_and_missing_bin(self):
        scores = evaluate_records([record()], {"calibration_bins": 2})["distributions"]["P_model"]
        bins = scores["calibration"]["bins"]
        self.assertAlmostEqual(bins[0]["mean_confidence"], 1 / 120)
        self.assertEqual(bins[0]["accuracy"], 1)
        self.assertIsNone(bins[1]["accuracy"])
        self.assertAlmostEqual(scores["calibration"]["ece"], 119 / 120)

    def test_paired_market_difference_vector(self):
        item = record()
        dist = {key: 0.5 / 119 for key in DOMAIN}
        dist["1-2-3"] = 0.5
        item["distributions"]["P_model"] = dist
        result = evaluate_records([item])
        pair = result["market_comparisons"]["P_model"]
        self.assertAlmostEqual(pair["logloss_difference"]["value"], math.log(60))
        self.assertGreater(pair["brier_difference"]["value"], 0)
        self.assertEqual(pair["superiority"], "UNVERIFIED")


class MoneyMetricTests(unittest.TestCase):
    def test_five_and_boxes_have_independent_stakes_and_payouts(self):
        result = evaluate_records([record()])
        self.assertEqual(result["methods"]["five"]["stake_yen"], 500)
        self.assertEqual(result["methods"]["five"]["net_yen"], 500)
        for method in ("human_research", "mechanical_research", "box_v11_research"):
            self.assertEqual(result["methods"][method]["stake_yen"], 600)
            self.assertEqual(result["methods"][method]["net_yen"], 400)
            self.assertAlmostEqual(result["methods"][method]["roi"], 2 / 3)
        self.assertNotIn("combined_stake", result)

    def test_refund_arithmetic_hit_is_not_profit_and_drawdown_sorted(self):
        first = record(1, payout=1000)
        second = record(2, result=(6, 5, 4), payout=2000)
        second["actual"]["refund_tickets"] = ["1-2-4"]
        third = record(3, payout=200)
        report = evaluate_records([third, first, second])["methods"]["five"]
        self.assertEqual(report["hit_n"], 2)
        self.assertEqual(report["stake_yen"], 1500)
        self.assertEqual(report["gross_payout_yen"], 1200)
        self.assertEqual(report["refund_yen"], 100)
        self.assertEqual(report["net_yen"], -200)
        self.assertAlmostEqual(report["return_rate"], 1300 / 1500)
        self.assertAlmostEqual(report["roi"], -200 / 1500)
        self.assertEqual(report["max_drawdown"]["value_yen"], 700)

    def test_bet_and_skip_are_separate_counterfactuals(self):
        result = evaluate_records([record(1, decision="SKIP"), record(2, result=(6, 5, 4))])
        method = result["methods"]["five"]
        self.assertEqual(method["stake_yen"], 1000)
        self.assertEqual(method["skip_counterfactual"]["net_yen"], 500)
        self.assertEqual(method["action"]["stake_yen"], 500)
        self.assertEqual(method["action"]["net_yen"], -500)
        self.assertEqual(method["action"]["skipped_n"], 1)

    def test_known_all_skip_has_zero_action_cashflow_but_undefined_roi(self):
        method = evaluate_records([record(decision="SKIP")])["methods"]["five"]
        self.assertEqual(method["action"]["stake_yen"], 0)
        self.assertEqual(method["action"]["net_yen"], 0)
        self.assertIsNone(method["action"]["roi"])

    def test_missing_refund_information_never_assumed_zero(self):
        item = record()
        del item["actual"]["refund_tickets"]
        report = evaluate_records([item])["methods"]["five"]
        self.assertEqual(report["hit_n"], 1)
        self.assertIsNone(report["refund_yen"])
        self.assertIsNone(report["roi"])
        self.assertEqual(report["money_unknown_n"], 1)

    def test_missing_payout_can_preserve_known_miss_without_inventing_winner_payout(self):
        loser = record(result=(6, 5, 4))
        del loser["actual"]["payout_per_100"]
        report = evaluate_records([loser])["methods"]["five"]
        self.assertEqual(report["gross_payout_yen"], 0)
        self.assertEqual(report["net_yen"], -500)
        winner = record()
        del winner["actual"]["payout_per_100"]
        self.assertIsNone(evaluate_records([winner])["methods"]["five"]["net_yen"])

    def test_refunded_winner_is_inconsistent_not_double_paid(self):
        item = record()
        item["actual"]["refund_tickets"] = ["1-2-3"]
        report = evaluate_records([item])["methods"]["five"]
        self.assertEqual(report["n"], 0)

    def test_duplicate_ticket_invalid_and_does_not_inflate_stake(self):
        item = record()
        item["selection"]["tickets"][1] = item["selection"]["tickets"][0]
        report = evaluate_records([item])["methods"]["five"]
        self.assertEqual(report["n"], 0)
        self.assertIsNone(report["stake_yen"])
        self.assertIsNone(report["max_drawdown"]["value_yen"])

    def test_wrong_box_permutation_invalid(self):
        item = record()
        item["boxes"]["human_research"]["tickets"][0] = "1-2-4"
        report = evaluate_records([item])["methods"]["human_research"]
        self.assertEqual(report["n"], 0)

    def test_unknown_decision_and_chronology_not_invented(self):
        item = record()
        del item["prediction_at"]
        del item["selection"]["bet_decision"]
        report = evaluate_records([item])["methods"]["five"]
        self.assertEqual(report["unknown_decision_n"], 1)
        self.assertEqual(report["action"]["status"], "UNVERIFIED_UNKNOWN_DECISIONS")
        self.assertEqual(report["max_drawdown"]["status"], "UNVERIFIED_CHRONOLOGY")

    def test_course_and_popularity_buckets_are_ex_post_diagnostics(self):
        item = record()
        item["first_course"] = None
        report = evaluate_records([item])["methods"]["five"]
        self.assertEqual(report["course_buckets"]["UNVERIFIED"]["n"], 1)
        self.assertEqual(report["popularity_buckets"]["1-3"]["n"], 1)


class BindingAndIntervalTests(unittest.TestCase):
    def test_outcome_race_source_and_final_binding(self):
        for field, invalid in (("race_id", "OTHER"), ("target_date", "2030-01-02"),
                               ("source", "OTHER"), ("final", False)):
            item = record()
            item["actual"][field] = invalid
            result = evaluate_records([item])
            self.assertEqual(result["invalid_record_n"], 1, field)
            self.assertEqual(result["distributions"]["P_model"]["n"], 0)

    def test_all_duplicate_race_source_records_are_rejected(self):
        item = record()
        result = evaluate_records([item, copy.deepcopy(item)])
        self.assertEqual(result["invalid_record_n"], 2)
        self.assertIsNone(result["methods"]["five"]["hit_rate"])

    def test_no_ci_without_explicit_config_or_insufficient_clusters(self):
        pair = evaluate_records([record()])["market_comparisons"]["P_model"]
        self.assertEqual(pair["day_block_brier_interval"]["status"], "UNVERIFIED_NOT_CONFIGURED")
        cfg = {"day_bootstrap": {"enabled": True, "confidence": .95, "replicates": 100,
                                  "min_clusters": 2, "seed": 10, "preregistration_reference": "SYNTHETIC-ONLY"}}
        pair = evaluate_records([record()], cfg)["market_comparisons"]["P_model"]
        self.assertEqual(pair["day_block_brier_interval"]["status"], "UNVERIFIED_TOO_FEW_DAY_CLUSTERS")

    def test_day_bootstrap_known_zero_difference_and_reproducibility(self):
        rows = [record(1, day="2030-01-01"), record(2, day="2030-01-02")]
        cfg = {"day_bootstrap": {"enabled": True, "confidence": .95, "replicates": 200,
                                  "min_clusters": 2, "seed": 10, "preregistration_reference": "SYNTHETIC-ONLY"}}
        first = evaluate_records(rows, cfg)["market_comparisons"]["P_model"]["day_block_brier_interval"]
        second = evaluate_records(rows, cfg)["market_comparisons"]["P_model"]["day_block_brier_interval"]
        self.assertEqual(first, second)
        self.assertEqual(first["interval"], [0, 0])
        self.assertEqual(first["clusters"], 2)
        self.assertEqual(first["status"], "EXPLORATORY_NOT_SUPERIORITY_EVIDENCE")
        hit_interval = evaluate_records(rows, cfg)["methods"]["five"]["day_block_hit_rate_interval"]
        self.assertEqual(hit_interval["interval"], [1, 1])
        self.assertEqual(hit_interval["estimand"], "RACE_WEIGHTED_MEAN_RESAMPLE_WHOLE_DAYS")

    def test_nonhashable_scope_rejected_as_record_error(self):
        item = record()
        item["source"] = []
        report = evaluate_records([item])
        self.assertEqual(report["invalid_record_n"], 1)
        self.assertEqual(report["record_issues"][0]["reason"], "RECORD_SCOPE_INVALID")

    def test_empty_report_is_unknown_and_json_safe(self):
        result = evaluate_records([])
        self.assertIsNone(result["methods"]["five"]["hit_rate"])
        self.assertIsNone(result["distributions"]["P_model"]["joint_logloss"]["value"])
        self.assertFalse(result["production_go"])
        json.dumps(result, allow_nan=False)


class LegacyAdapterTests(unittest.TestCase):
    def profile_and_record(self):
        item = record()
        raw = b"SYNTHETIC reference only; not the real frozen model"
        digest = hashlib.sha256(raw).hexdigest()
        profile = {"verified": True, "raw_bytes": raw, "sha256": digest,
                   "source_identity": "SYNTHETIC-LEGACY", "verification_evidence": "SYNTHETIC-ATTESTATION"}
        item["legacy"] = {"race_id": item["race_id"], "target_date": item["target_date"],
                          "source": item["source"], "source_identity": "SYNTHETIC-LEGACY",
                          "reference_sha256": digest, "prediction_at": item["prediction_at"],
                          "tickets": list(FIVE), "bet_decision": "BET"}
        return profile, item

    def test_missing_profile_never_reconstructs_legacy(self):
        self.assertEqual(legacy_adapter(record())["status"], "OPEN")
        self.assertEqual(evaluate_records([record()])["legacy"]["status"], "OPEN")

    def test_verified_local_bytes_enable_only_fixed_output_comparison(self):
        profile, item = self.profile_and_record()
        adapted = legacy_adapter(item, profile)
        self.assertEqual(adapted["status"], "LOCAL_INPUTS_MATCHED")
        self.assertEqual(adapted["external_authenticity"], "UNVERIFIED_BY_LOCAL_CODE")
        report = evaluate_records([item], {"legacy_profile": profile})["legacy"]
        self.assertEqual(report["paired_hit_delta"]["value"], 0)
        self.assertEqual(report["methods"]["five"]["fixed_output_metrics"]["net_yen"], 500)
        self.assertEqual(report["superiority"], "UNVERIFIED")

    def test_wrong_hash_source_or_late_legacy_is_open(self):
        for field, value in (("reference_sha256", "0" * 64), ("source", "OTHER"),
                             ("prediction_at", "2030-01-01T13:00:00+09:00")):
            profile, item = self.profile_and_record()
            item["legacy"][field] = value
            self.assertEqual(legacy_adapter(item, profile)["status"], "OPEN")
        profile, item = self.profile_and_record()
        profile["raw_bytes"] = b"MODIFIED"
        self.assertEqual(legacy_adapter(item, profile)["status"], "OPEN")


if __name__ == "__main__":
    unittest.main()
