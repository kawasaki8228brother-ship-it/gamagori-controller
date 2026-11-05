"""Pre-outcome sensitivity is invariant to subsequently supplied synthetic labels."""
from copy import deepcopy
from itertools import product
import json
import unittest

from model11.engine import canonical_hash, predict_race
from model11.models import make_model
from model11.synthetic import make_dataset
from model11.preparation.sensitivity import audit_forecast, diagnose, METHODS, DEFAULT_SCENARIOS


def seal(forecast):
    forecast["prediction_sha256"] = canonical_hash({k: v for k, v in forecast.items() if k != "prediction_sha256"})
    return forecast


class SensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = make_dataset(4, 1, 20261105)
        cls.model = make_model("hierarchical", {"epochs": 2})
        cls.model.fit(cls.dataset["races"][:2], cls.dataset["outcomes"][:2])
        cls.race = deepcopy(cls.dataset["races"][2])
        cls.forecast = predict_race(cls.race, cls.model)
        cls.outcome = deepcopy(cls.dataset["outcomes"][2])

    def test_complete_fixed_grid_and_four_separate_stakes(self):
        audit = audit_forecast(self.forecast, self.race)
        self.assertEqual(audit["status"], "DESCRIPTIVE")
        self.assertEqual(len(audit["scenario_grid"]), 27)
        self.assertFalse(audit["production_go"])
        self.assertFalse(audit["tickets_reselected"])
        self.assertEqual(audit["preregistration_authenticity"], "UNVERIFIED")
        for name in METHODS:
            method = audit["methods"][name]
            self.assertEqual(method["stake_yen"], 500 if name == "five" else 600)
            old = self.forecast["selection"] if name == "five" else self.forecast["boxes"][name]
            self.assertEqual(method["tickets"], old["tickets"])
            self.assertEqual(method["original_bet_decision"], old["bet_decision"])
            self.assertEqual(len(method["scenarios"]), 27)
            self.assertEqual(method["original_portfolio_sha256"], canonical_hash(old))
            self.assertTrue(method["risk_overlay"]["candidate_id"].startswith("EV_ROBUST_OVERLAY_PROPOSED_V002:"))

    def test_no_mutation_of_inputs_or_fixed_config(self):
        original = deepcopy((self.forecast, self.race, DEFAULT_SCENARIOS))
        audit_forecast(self.forecast, self.race)
        diagnose([self.forecast], [self.race], [self.outcome])
        self.assertEqual(original, (self.forecast, self.race, DEFAULT_SCENARIOS))

    def test_haircut_monotonically_decreases_ev_for_each_fixed_probability_case(self):
        audit = audit_forecast(self.forecast, self.race)
        coordinate = {scenario["scenario_id"]: scenario for scenario in audit["scenario_grid"]}
        for name, method in audit["methods"].items():
            for weight, flat in product((0.0, 0.5, 1.0), (0.0, 0.25, 0.5)):
                cases = [row for row in method["scenarios"]
                         if coordinate[row["scenario_id"]]["market_weight"] == weight
                         and coordinate[row["scenario_id"]]["uniform_weight"] == flat]
                cases.sort(key=lambda row: coordinate[row["scenario_id"]]["odds_multiplier"], reverse=True)
                self.assertGreaterEqual(cases[0]["expected_return_yen"], cases[1]["expected_return_yen"])
                self.assertGreaterEqual(cases[1]["expected_return_yen"], cases[2]["expected_return_yen"])
                self.assertAlmostEqual(cases[1]["expected_return_yen"], 0.9 * cases[0]["expected_return_yen"])

    def test_exact_baseline_matches_original_ev_and_market_pool_formula(self):
        audit = audit_forecast(self.forecast, self.race)
        base = next(row for row in audit["scenario_grid"] if row["market_weight"] == row["uniform_weight"] == 0 and row["odds_multiplier"] == 1)
        market_case = next(row for row in audit["scenario_grid"] if row["market_weight"] == 1 and row["uniform_weight"] == 0 and row["odds_multiplier"] == 1)
        for name, method in audit["methods"].items():
            indexed = {row["scenario_id"]: row for row in method["scenarios"]}
            self.assertAlmostEqual(indexed[base["scenario_id"]]["expected_return_yen"], method["predicted_expected_return_yen"])
            expected = sum(100 * self.forecast["distributions"]["P_market"][t] * self.race["odds_snapshot"]["odds"][t] for t in method["tickets"])
            self.assertAlmostEqual(indexed[market_case["scenario_id"]]["expected_return_yen"], expected)

    def test_outcome_changes_cannot_change_risk_decision_or_preoutcome_audit(self):
        first = deepcopy(self.outcome)
        second = deepcopy(first)
        second["result"] = list(map(int, self.forecast["selection"]["tickets"][0].split("-")))
        second["payout_per_100"] = 98765
        old = diagnose([self.forecast], [self.race], [first])
        new = diagnose([self.forecast], [self.race], [second])
        absent = diagnose([self.forecast], [self.race])
        self.assertEqual(old["audits"], new["audits"])
        self.assertEqual(new["audits"], absent["audits"])
        for name in METHODS:
            self.assertEqual(old["methods"][name]["overlay_decision_counts"], new["methods"][name]["overlay_decision_counts"])
        self.assertNotEqual(old["methods"]["five"]["observed_settlement"], new["methods"]["five"]["observed_settlement"])

    def test_audit_has_no_outcome_argument_and_rejects_embedded_outcome(self):
        with self.assertRaises(TypeError):
            audit_forecast(self.forecast, self.race, outcomes=[self.outcome])
        for label in ({"actual": self.outcome}, {"extra": {"result": [1, 2, 3]}}, {"first_course": 1}):
            altered = deepcopy(self.forecast)
            altered.update(label)
            seal(altered)
            audit = audit_forecast(altered, self.race)
            self.assertEqual(audit["status"], "UNVERIFIED")
            self.assertEqual(audit["reason_codes"], ["OUTCOME_INFORMATION_IN_FORECAST"])

    def test_self_hash_is_consistency_only_and_invalid_hash_fails_closed(self):
        altered = deepcopy(self.forecast)
        altered["prediction_sha256"] = "0" * 64
        audit = audit_forecast(altered, self.race)
        self.assertEqual(audit["reason_codes"], ["FORECAST_SELF_HASH_MISMATCH"])
        self.assertEqual(audit["external_authenticity"], "UNVERIFIED")

    def test_missing_odds_is_null_ev_and_unverified_risk_never_zero_imputation(self):
        missing_race = deepcopy(self.race)
        missing_race["odds_snapshot"] = None
        forecast = predict_race(missing_race, self.model)
        audit = audit_forecast(forecast, missing_race)
        self.assertEqual(audit["status"], "UNVERIFIED")
        for method in audit["methods"].values():
            self.assertIsNone(method["predicted_expected_return_yen"])
            self.assertIsNone(method["predicted_expected_net_yen"])
            self.assertEqual(method["risk_overlay"]["decision"], "UNVERIFIED")
            self.assertEqual(method["original_bet_decision"], "SKIP")
            self.assertTrue(any(case["status"] == "UNVERIFIED_MARKET_MISSING" for case in method["scenarios"]))

    def test_missing_invalid_component_and_changed_input_are_unverified(self):
        self.assertEqual(audit_forecast(None, self.race)["status"], "UNVERIFIED")
        self.assertEqual(audit_forecast(self.forecast, None)["status"], "UNVERIFIED")
        for field, value in (("boxes", []), ("config", []), ("distributions", []), ("P_calibrated", None)):
            altered = deepcopy(self.forecast)
            altered[field] = value
            self.assertEqual(audit_forecast(seal(altered), self.race)["status"], "UNVERIFIED")
        changed_race = deepcopy(self.race)
        changed_race["boats"][0]["features"]["st"] *= -1
        self.assertEqual(audit_forecast(self.forecast, changed_race)["reason_codes"], ["FORECAST_RACE_SELF_HASH_MISMATCH"])

    def test_portfolio_ev_mismatch_or_duplicate_ticket_not_silently_repaired(self):
        for field, value in (("expected_return_yen", 123456), ("tickets", ["1-2-3"] * 5)):
            altered = deepcopy(self.forecast)
            altered["selection"][field] = value
            audit = audit_forecast(seal(altered), self.race)
            self.assertEqual(audit["status"], "UNVERIFIED")
            self.assertEqual(audit["methods"]["five"]["risk_overlay"]["decision"], "UNVERIFIED")

    def test_invalid_or_optimistic_grid_rejected_no_unknown_thresholds(self):
        invalid = [{"unknown": 1}, {"odds_multipliers": [1, 1.1]}, {"odds_multipliers": [0.9]},
                   {"market_weights": [1]}, {"uniform_weights": [False]},
                   {"risk_policy": {"min_coverage": float("nan")}},
                   {"preregistration_reference": "https://secret.invalid/token"}]
        for config in invalid:
            with self.subTest(config=config):
                audit = audit_forecast(self.forecast, self.race, config)
                self.assertEqual(audit["status"], "UNVERIFIED")
                self.assertNotIn("secret.invalid", json.dumps(audit))

    def test_refunds_counted_per_method_without_cross_portfolio_aggregation(self):
        outcome = deepcopy(self.outcome)
        tickets = self.forecast["selection"]["tickets"]
        outcome["result"] = list(map(int, tickets[0].split("-")))
        outcome["payout_per_100"] = 1300
        outcome["refund_tickets"] = [tickets[1]]
        report = diagnose([self.forecast], [self.race], [outcome])
        five = report["methods"]["five"]["observed_settlement"]
        self.assertEqual(five["stake_yen"], 500)
        self.assertEqual(five["refund_yen"], 100)
        self.assertEqual(five["return_yen"], 1400)
        self.assertEqual(five["net_yen"], 900)
        for name in METHODS[1:]:
            self.assertEqual(report["methods"][name]["observed_settlement"]["stake_yen"], 600)
        self.assertNotIn("combined_roi", report)

    def test_refunded_winner_unknown_refund_or_unknown_payout_is_unverified(self):
        variants = []
        bad = deepcopy(self.outcome)
        bad["refund_tickets"] = ["-".join(map(str, bad["result"]))]
        variants.append(bad)
        for field in ("refund_tickets", "payout_per_100"):
            bad = deepcopy(self.outcome)
            bad.pop(field)
            variants.append(bad)
        for outcome in variants:
            report = diagnose([self.forecast], [self.race], [outcome])
            self.assertEqual(report["methods"]["five"]["observed_settlement"]["n"], 0)
            self.assertIsNone(report["methods"]["five"]["observed_settlement"]["net_yen"])

    def test_duplicate_forecasts_or_outcomes_fail_closed(self):
        duplicate_forecasts = diagnose([self.forecast, self.forecast], [self.race])
        duplicate_outcomes = diagnose([self.forecast], [self.race], [self.outcome, self.outcome])
        self.assertEqual(duplicate_forecasts["status"], "UNVERIFIED")
        self.assertEqual(duplicate_outcomes["status"], "UNVERIFIED")
        self.assertEqual(duplicate_forecasts["methods"], {})

    def test_missing_labels_remain_unknown_but_do_not_stop_preoutcome_work(self):
        report = diagnose([self.forecast], [self.race])
        self.assertEqual(report["input_n"], 1)
        self.assertEqual(report["audits"][0]["status"], "DESCRIPTIVE")
        self.assertEqual(report["methods"]["box_v11_research"]["settlement_unknown_n"], 1)
        self.assertIsNone(report["focus_observations"]["box_v11_zero_hits"])
        self.assertIsNone(report["probability_diagnostics"]["paired_model_minus_market"]["mean_joint_logloss_delta"])

    def test_overlay_never_upgrades_original_skip_and_has_distinct_candidate_id(self):
        config = {"market_weights": [0], "uniform_weights": [0], "odds_multipliers": [1],
                  "risk_policy": {"min_coverage": 0, "max_single_ticket_ev_share": 1, "max_gross_odds": 1e12}}
        altered = deepcopy(self.forecast)
        altered["selection"]["bet_decision"] = altered["bet_decision"] = "SKIP"
        audit = audit_forecast(seal(altered), self.race, config)
        self.assertEqual(audit["methods"]["five"]["risk_overlay"]["decision"], "SKIP")
        self.assertIn("ORIGINAL_SKIP_PRESERVED", audit["methods"]["five"]["risk_overlay"]["reason_codes"])
        self.assertNotEqual(audit["risk_candidate_id"], self.forecast["model_spec"].get("candidate_id"))

    def test_risk_trigger_sensitivity_is_proposed_and_never_reselects(self):
        config = {"risk_policy": {"min_coverage": 0.99, "max_single_ticket_ev_share": 0.01, "max_gross_odds": 1}}
        audit = audit_forecast(self.forecast, self.race, config)
        for name, method in audit["methods"].items():
            self.assertIn("LOW_PREDICTED_COVERAGE_PROPOSED_TRIGGER", method["observations"])
            self.assertIn("CONCENTRATED_EXPECTED_RETURN_PROPOSED_TRIGGER", method["observations"])
            self.assertIn("HIGH_PAYOFF_DEPENDENCE_PROPOSED_TRIGGER", method["observations"])
            self.assertEqual(method["risk_overlay"]["decision"], "SKIP")
            self.assertGreater(method["worst_stressed_single_ticket_ev_share"], 0.01)
            old = self.forecast["selection"] if name == "five" else self.forecast["boxes"][name]
            self.assertEqual(method["tickets"], old["tickets"])

    def test_no_outcome_case_is_not_recorded_as_zero_hits(self):
        report = diagnose([self.forecast], [self.race], [])
        for method in report["methods"].values():
            self.assertIsNone(method["observed_settlement"]["hit_n"])
            self.assertIsNone(method["observed_settlement"]["return_yen"])
            self.assertEqual(method["observed_settlement"]["n"], 0)

    def test_custom_policy_has_distinct_hash_without_modifying_original_config(self):
        default = audit_forecast(self.forecast, self.race)
        custom = audit_forecast(self.forecast, self.race, {"risk_policy": {"min_coverage": 0.1}})
        self.assertNotEqual(default["protocol_sha256"], custom["protocol_sha256"])
        self.assertEqual(default["original_config_sha256"], custom["original_config_sha256"])
        self.assertNotEqual(default["methods"]["five"]["risk_overlay"]["candidate_id"],
                            custom["methods"]["five"]["risk_overlay"]["candidate_id"])


if __name__ == "__main__":
    unittest.main()
