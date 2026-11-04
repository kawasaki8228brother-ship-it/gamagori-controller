import copy
import math
import unittest

from model11.engine import check_distribution, predict_race
from model11.models import make_model
from model11.synthetic import make_dataset


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_dataset(days=8, races_per_day=1)
        cls.model = make_model("contextual", {"epochs": 5, "alpha": .5}).fit(
            cls.data["races"][:6], cls.data["outcomes"][:6])

    def test_end_to_end_four_distinct_distributions_and_boxes(self):
        prediction = predict_race(self.data["races"][6], self.model)
        for name in ("P_raw", "P_model", "P_market", "P_shrunk"):
            self.assertEqual(prediction["probability_integrity"][name]["count"], 120)
            self.assertAlmostEqual(sum(prediction["distributions"][name].values()), 1)
        five = prediction["selection"]["tickets"]
        self.assertEqual(len(set(five)), 5)
        self.assertEqual(five, sorted(five))
        self.assertEqual(prediction["selection"]["stake_yen"], 500)
        for method in ("human_research", "mechanical_research", "box_v11_research"):
            box = prediction["boxes"][method]
            self.assertEqual(len(set(box["tickets"])), 6)
            self.assertEqual(box["stake_yen"], 600)
            self.assertFalse(box["formal_box_v1_reproduction"])
        self.assertFalse(prediction["production_go"])
        self.assertIn("OPEN", prediction["legacy_model10"])

    def test_absent_and_stale_market_not_fabricated(self):
        race = copy.deepcopy(self.data["races"][6])
        race["odds_snapshot"] = None
        output = predict_race(race, self.model)
        self.assertIsNone(output["distributions"]["P_market"])
        self.assertIsNone(output["distributions"]["P_shrunk"])
        self.assertEqual(output["bet_decision"], "SKIP")
        self.assertIsNone(output["selection"]["expected_net_yen"])
        self.assertEqual(len(output["distributions"]["P_model"]), 120)

    def test_future_feature_availability_blocks_all_prediction(self):
        race = copy.deepcopy(self.data["races"][6])
        race["boats"][0]["feature_times"]["motor"]["available_at"] = race["deadline"]
        with self.assertRaisesRegex(ValueError, "PREDICTION_GATE"):
            predict_race(race, self.model)

    def test_cross_race_odds_never_used(self):
        race = copy.deepcopy(self.data["races"][6])
        race["odds_snapshot"]["race_id"] = "OTHER_SYNTHETIC_RACE"
        result = predict_race(race, self.model)
        self.assertIsNone(result["distributions"]["P_market"])
        self.assertIsNone(result["distributions"]["P_shrunk"])
        self.assertEqual(result["bet_decision"], "SKIP")

    def test_late_odds_availability_is_excluded(self):
        race = copy.deepcopy(self.data["races"][6])
        race["odds_snapshot"]["available_at"] = race["deadline"]
        result = predict_race(race, self.model)
        self.assertIsNone(result["distributions"]["P_market"])
        self.assertIsNone(result["distributions"]["P_shrunk"])
        self.assertEqual(result["bet_decision"], "SKIP")
        self.assertEqual(len(result["distributions"]["P_model"]), 120)

    def test_late_manual_box_availability_is_not_used(self):
        race = copy.deepcopy(self.data["races"][6])
        race["human_box_input"]["available_at"] = race["deadline"]
        with self.assertRaises(ValueError):
            predict_race(race, self.model)

    def test_results_cannot_enter_prediction(self):
        race = copy.deepcopy(self.data["races"][6])
        race["metadata"] = {"payout_per_100": 100}
        with self.assertRaises(ValueError):
            predict_race(race, self.model)

    def test_invalid_mass_domain_and_nonfinite_are_stop(self):
        dist = self.model.distributions(self.data["races"][6])["P_raw"]
        for value in (-.1, math.nan, math.inf, .7):
            broken = dict(dist)
            broken[next(iter(broken))] = value
            with self.assertRaises(ValueError):
                check_distribution(broken, [1, 2, 3, 4, 5, 6])
        broken = dict(dist)
        broken["1-1-2"] = broken.pop("1-2-3")
        with self.assertRaises(ValueError):
            check_distribution(broken, [1, 2, 3, 4, 5, 6])

    def test_unfitted_model_not_prediction_success(self):
        with self.assertRaisesRegex(ValueError, "MODEL_NOT_FITTED"):
            predict_race(self.data["races"][0], make_model("hierarchical"))

    def test_future_or_unknown_model_training_cutoff_is_stop(self):
        with self.assertRaisesRegex(ValueError, "MODEL_TRAINING_NOT_BEFORE"):
            predict_race(self.data["races"][0], self.model)
        model = copy.deepcopy(self.model)
        model.training_max_available_at = None
        with self.assertRaisesRegex(ValueError, "MODEL_TRAINING_CHRONOLOGY_UNVERIFIED"):
            predict_race(self.data["races"][7], model)


if __name__ == "__main__":
    unittest.main()
