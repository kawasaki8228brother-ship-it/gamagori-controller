"""Synthetic F1 endpoints, selection chronology, and diagnostic-adequacy checks."""
from copy import deepcopy
from itertools import permutations
import json
import math
import unittest

from model11.synthetic import make_dataset
from model11.revision_v003.course import COURSE_POLICIES, apply_course_fixture
from model11.revision_v003.pooling import DEFAULT_MARKET_WEIGHTS, pool_market
from model11.revision_v003.walkforward import walk_forward_v003


SMALL = {"train_days": 3, "selection_days": 2, "test_days": 2,
         "candidates": ["hierarchical", "contextual"], "alphas": [0.0],
         "temperatures": [1.0], "epochs": 2,
         "evaluation": {"day_bootstrap": {"enabled": False}}}


def data(days=8):
    result = make_dataset(days, 1, 20261105)
    result["races"] = [apply_course_fixture(race) for race in result["races"]]
    return result


def distribution(boost="1-2-3"):
    values = {"-".join(map(str, p)): 0.5/119 for p in permutations(range(1, 7), 3)}
    values[boost] = 0.5
    return values


class PoolTests(unittest.TestCase):
    def test_default_market_grid_is_exact(self):
        self.assertEqual(DEFAULT_MARKET_WEIGHTS, [0, .25, .5, .75, .9, 1.0])

    def test_endpoints_exact_copies_and_market_only_independent_of_model(self):
        market = distribution("6-5-4")
        first, second = distribution(), distribution("4-2-1")
        self.assertEqual(pool_market(first, market, 1.0), market)
        self.assertEqual(pool_market(second, market, 1.0), market)
        self.assertEqual(pool_market(first, market, 0), first)
        detached = pool_market(first, market, 1)
        self.assertIsNot(detached, market)
        detached["1-2-3"] = 0
        self.assertNotEqual(detached, market)

    def test_market_weight_orientation_and_normalization(self):
        model, market = distribution(), distribution("6-5-4")
        values = pool_market(model, market, .75)
        self.assertGreater(values["6-5-4"], values["1-2-3"])
        ratio = values["6-5-4"]/values["1-2-3"]
        expected = ((model["6-5-4"]/model["1-2-3"])**.25
                    * (market["6-5-4"]/market["1-2-3"])**.75)
        self.assertAlmostEqual(ratio, expected)
        self.assertAlmostEqual(math.fsum(values.values()), 1.0)
        self.assertEqual(len(values), 120)

    def test_both_inputs_validated_even_when_their_weight_is_zero(self):
        good = distribution()
        for bad_value in (-.1, math.nan, math.inf, True, .9):
            bad = dict(good)
            bad["1-2-3"] = bad_value
            for args in ((bad, good, 1), (good, bad, 0)):
                with self.assertRaises(ValueError):
                    pool_market(*args)
        for weight in (True, -1, 1.01, math.nan, math.inf):
            with self.assertRaises(ValueError):
                pool_market(good, good, weight)

    def test_bad_domain_is_not_repaired(self):
        good, bad = distribution(), distribution()
        bad["1-1-2"] = bad.pop("1-2-3")
        with self.assertRaises(ValueError):
            pool_market(good, bad, 1)
        with self.assertRaises(ValueError):
            pool_market({"a": 1.0}, {"a": 1.0}, .5)

    def test_zero_support_is_explicit_no_epsilon(self):
        first = {k: float(k == "1-2-3") for k in distribution()}
        second = {k: float(k == "6-5-4") for k in distribution()}
        self.assertEqual(pool_market(first, second, 1), second)
        self.assertEqual(pool_market(first, second, 0), first)
        with self.assertRaisesRegex(ValueError, "NO_COMMON_POSITIVE_SUPPORT"):
            pool_market(first, second, .5)


class WalkForwardV003Tests(unittest.TestCase):
    def test_future_whole_day_splits_and_frozen_six_weight_grid(self):
        fixture = data(10)
        original = deepcopy(fixture)
        result = walk_forward_v003(fixture, SMALL)
        self.assertEqual(result["candidate_grid"]["market_weights"], [0, .25, .5, .75, .9, 1.0])
        self.assertIn("F5_DESIGN_PENDING", result["selection_adequacy"])
        seen = set()
        for fold in result["folds"]:
            train, select, test = map(set, (fold["train_days"], fold["selection_days"], fold["test_days"]))
            self.assertFalse(train & select or train & test or select & test or seen & test)
            self.assertLess(max(train), min(select))
            self.assertLess(max(select), min(test))
            seen |= test
            self.assertEqual(fold["selection_adequacy"]["status"], "UNVERIFIED_NOT_PREREGISTERED")
        self.assertEqual(fixture, original)
        self.assertFalse(result["production_go"])
        self.assertEqual(result["superiority"], "UNVERIFIED")

    def test_market_only_can_win_selection_not_forced_model_contribution(self):
        fixture = data()
        for index, (race, outcome) in enumerate(zip(fixture["races"], fixture["outcomes"])):
            outcome["result"] = [6, 5, 4] if index < 3 else [1, 2, 3]
            outcome["payout_per_100"] = 1000.0
            race["odds_snapshot"]["odds"] = {
                ticket: (1.0/(1-1e-9) if ticket == "1-2-3" else 119/1e-9)
                for ticket in race["odds_snapshot"]["odds"]}
        result = walk_forward_v003(fixture, SMALL)
        chosen = result["folds"][0]["selected"]
        self.assertEqual(chosen["market_weight"], 1.0)
        self.assertEqual(chosen["model_weight"], 0)
        self.assertEqual(chosen["prediction_type"], "MARKET_ONLY")
        self.assertIn("NOT_A_LEARNED_MODEL_VICTORY", chosen["underlying_candidate_role"])
        for forecast in result["records"]:
            self.assertEqual(forecast["distributions"]["P_shrunk"], forecast["distributions"]["P_market"])

    def test_w1_is_one_equivalence_class_not_twelve_independent_hypotheses(self):
        cfg = {**SMALL, "alphas": [0, .5], "temperatures": [.8, 1, 1.2]}
        result = walk_forward_v003(data(), cfg)
        fold = result["folds"][0]
        pure = [row for row in fold["selection_scores"] if row["market_weight"] == 1]
        self.assertEqual(len(pure), 12)
        self.assertEqual(len({row["selection_probability_sha256"] for row in pure}), 1)
        self.assertEqual(len({row["equivalence_class"] for row in pure}), 1)
        self.assertEqual(fold["selection_adequacy"]["nominal_grid_members"], 72)
        self.assertEqual(fold["selection_adequacy"]["structural_probability_upper_bound"], 61)

    def test_test_outcomes_cannot_change_selection_or_forecasts(self):
        fixture = data(10)
        original = walk_forward_v003(fixture, SMALL)
        changed = deepcopy(fixture)
        changed["outcomes"][5]["result"] = [6, 5, 4]
        changed["outcomes"][5]["payout_per_100"] = 77777.0
        alternate = walk_forward_v003(changed, SMALL)
        for key in ("selected", "selection_scores", "forecast_hashes"):
            self.assertEqual(original["folds"][0][key], alternate["folds"][0][key])

    def test_future_features_do_not_retroactively_change_first_fold(self):
        fixture = data(10)
        original = walk_forward_v003(fixture, SMALL)
        fixture["races"][-1]["boats"][0]["features"]["turn"] = -.99
        changed = walk_forward_v003(fixture, SMALL)
        self.assertEqual(original["folds"][0]["forecast_hashes"], changed["folds"][0]["forecast_hashes"])

    def test_late_training_and_selection_labels_stop(self):
        for index, reason in ((0, "TRAIN_LABEL_UNAVAILABLE"), (3, "SELECTION_LABEL_UNAVAILABLE")):
            fixture = data()
            fixture["outcomes"][index]["available_at"] = fixture["races"][-1]["deadline"]
            with self.assertRaisesRegex(ValueError, reason):
                walk_forward_v003(fixture, SMALL)

    def test_selection_coverage_and_tiny_n_remain_unverified(self):
        fixture = data()
        fixture["races"][3]["odds_snapshot"] = None
        result = walk_forward_v003(fixture, SMALL)
        adequacy = result["folds"][0]["selection_adequacy"]
        self.assertEqual(adequacy["selection_races"], 2)
        self.assertEqual(adequacy["common_market_paired_races"], 1)
        self.assertEqual(adequacy["excluded_missing_market_races"], 1)
        self.assertEqual(adequacy["status"], "UNVERIFIED_NOT_PREREGISTERED")
        fixture["races"][4]["odds_snapshot"] = None
        with self.assertRaisesRegex(ValueError, "NO_MARKET_AVAILABLE_SELECTION_PAIRS"):
            walk_forward_v003(fixture, SMALL)

    def test_real_or_unprovenanced_inputs_and_unknown_grid_stop(self):
        fixture = data()
        fixture["classification"] = "HQ14_PRIVATE_OFFLINE"
        with self.assertRaisesRegex(ValueError, "REAL_INPUT_REQUIRES_APPROVED"):
            walk_forward_v003(fixture, SMALL)
        fixture = data()
        del fixture["races"][0]["course_inputs"]
        with self.assertRaisesRegex(ValueError, "COURSE_GATE"):
            walk_forward_v003(fixture, SMALL)
        for change in ({"market_weights": [True]}, {"market_weights": [0, 0]},
                       {"market_weights": [2]}, {"temperatures": [math.nan]}):
            with self.assertRaises(ValueError):
                walk_forward_v003(data(), {**SMALL, **change})

    def test_probability_and_separate_portfolio_regression(self):
        result = walk_forward_v003(data(), SMALL)
        for record in result["records"]:
            for stage in ("P_raw", "P_model", "P_market", "P_shrunk"):
                dist = record["distributions"][stage]
                self.assertEqual(len(dist), 120)
                self.assertAlmostEqual(math.fsum(dist.values()), 1.0)
                self.assertTrue(all(math.isfinite(p) and p >= 0 for p in dist.values()))
            self.assertEqual(len(record["selection"]["tickets"]), 5)
            self.assertEqual(record["selection"]["stake_yen"], 500)
            self.assertNotIn("human_research", record["boxes"])
            for name in ("five_appearance_research", "mechanical_research", "box_v11_research"):
                self.assertEqual(len(record["boxes"][name]["tickets"]), 6)
                self.assertEqual(record["boxes"][name]["stake_yen"], 600)
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
