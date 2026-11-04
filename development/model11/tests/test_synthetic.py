"""Generator correctness checks; not tests of real forecasting performance."""

from datetime import datetime
from itertools import permutations
import json
import math
import unittest
from unittest.mock import patch

from model11.synthetic import FEATURES, _latent_distribution, make_dataset


class SyntheticTests(unittest.TestCase):
    def test_deterministic_seed(self):
        first = make_dataset(days=2, seed=7)
        self.assertEqual(first, make_dataset(days=2, seed=7))
        self.assertNotEqual(first, make_dataset(days=2, seed=8))
        json.dumps(first, allow_nan=False)

    def test_size_identity_and_classification(self):
        data = make_dataset(days=3, races_per_day=2)
        self.assertEqual(data["classification"], "SYNTHETIC_ONLY")
        self.assertFalse(data["config"]["real_data_used"])
        self.assertFalse(data["config"]["real_performance_claim"])
        self.assertEqual(len(data["races"]), 6)
        self.assertEqual(len(data["outcomes"]), 6)
        self.assertEqual(data["races"][0]["race_id"], "20990101_GAMAGORI_1R")
        self.assertEqual(data["races"][-1]["target_date"], "2099-01-03")
        self.assertEqual(len({r["race_id"] for r in data["races"]}), 6)
        for race, outcome in zip(data["races"], data["outcomes"]):
            self.assertTrue(race["synthetic"])
            self.assertTrue(outcome["synthetic"])
            self.assertEqual(race["race_id"], outcome["race_id"])
            self.assertEqual(race["target_date"], outcome["target_date"])

    def test_boats_features_and_timing(self):
        for race in make_dataset(days=2)["races"]:
            self.assertEqual(race["active_boats"], list(range(1, 7)))
            self.assertEqual(sorted(b["course"] for b in race["boats"]), list(range(1, 7)))
            prediction, deadline = map(datetime.fromisoformat, (race["prediction_at"], race["deadline"]))
            self.assertLess(prediction, deadline)
            self.assertIsNotNone(prediction.utcoffset())
            for boat in race["boats"]:
                self.assertEqual(set(boat["features"]), set(FEATURES))
                self.assertTrue(all(math.isfinite(v) and -1 <= v <= 1 for v in boat["features"].values()))
                self.assertEqual(set(boat["feature_times"]), set(FEATURES))
                self.assertEqual(set(boat["state_times"]), {"course", "fl", "scratched"})
                for provenance in list(boat["feature_times"].values()) + list(boat["state_times"].values()):
                    acquired, available, revised = [datetime.fromisoformat(provenance[key]) for key in ("acquired_at", "available_at", "revision_at")]
                    self.assertLessEqual(acquired, available)
                    self.assertLessEqual(available, prediction)
                    self.assertLessEqual(revised, prediction)
                for name in ("observed_at", "motor_updated_at", "revision_at"):
                    self.assertLessEqual(datetime.fromisoformat(boat[name]), prediction)
                self.assertFalse(boat["scratched"])
            for name in ("acquired_at", "available_at", "revision_at"):
                self.assertLessEqual(datetime.fromisoformat(race["odds_snapshot"][name]), prediction)
            self.assertLessEqual(datetime.fromisoformat(race["odds_snapshot"]["acquired_at"]), datetime.fromisoformat(race["odds_snapshot"]["available_at"]))
            manual = race["human_box_input"]
            self.assertEqual(len(set(manual["core"] + [manual["insertion"]])), 3)
            for name in ("observed_at", "acquired_at", "available_at", "revision_at"):
                self.assertLessEqual(datetime.fromisoformat(manual[name]), prediction)
            self.assertLessEqual(datetime.fromisoformat(manual["acquired_at"]), datetime.fromisoformat(manual["available_at"]))

    def test_full_odds_and_latent_probability_domain(self):
        expected = {"-".join(map(str, ticket)) for ticket in permutations(range(1, 7), 3)}
        for race in make_dataset(days=2)["races"]:
            odds = race["odds_snapshot"]["odds"]
            self.assertEqual(set(odds), expected)
            self.assertTrue(all(math.isfinite(v) and v > 0 for v in odds.values()))
            latent = _latent_distribution(race["boats"])
            self.assertEqual(set(latent), expected)
            self.assertAlmostEqual(math.fsum(latent.values()), 1.0, places=12)
            self.assertTrue(all(p > 0 for p in latent.values()))
            self.assertAlmostEqual(math.fsum(1 / value for value in odds.values()), 1 / 0.78, places=7)

    def test_outcome_is_separate_later_and_settlement_uses_existing_odds(self):
        data = make_dataset(days=3)
        for race, outcome in zip(data["races"], data["outcomes"]):
            self.assertNotIn("result", race)
            self.assertNotIn("payout_per_100", race)
            self.assertEqual(len(outcome["result"]), 3)
            self.assertEqual(len(set(outcome["result"])), 3)
            self.assertTrue(set(outcome["result"]).issubset(set(race["active_boats"])))
            self.assertGreater(datetime.fromisoformat(outcome["available_at"]), datetime.fromisoformat(race["deadline"]))
            key = "-".join(map(str, outcome["result"]))
            self.assertEqual(outcome["payout_per_100"], round(100 * race["odds_snapshot"]["odds"][key], 2))
            self.assertTrue(outcome["final"])
            self.assertEqual(outcome["refund_tickets"], [])

    def test_outcome_draws_do_not_change_predictor_record_or_odds(self):
        original = make_dataset(days=2, seed=13)
        # Force different outcomes. Predictor records and all odds must remain
        # byte-equivalent because neither uses the sampled winning ticket.
        with patch("model11.synthetic._sample", side_effect=lambda probabilities, rng: next(reversed(probabilities))):
            alternative = make_dataset(days=2, seed=13)
        self.assertEqual(original["races"], alternative["races"])
        self.assertNotEqual(original["outcomes"], alternative["outcomes"])

    def test_probability_process_not_a_fixed_total_score_ranking(self):
        data = make_dataset(days=12, seed=17)
        differing = 0
        for race, outcome in zip(data["races"], data["outcomes"]):
            latent = _latent_distribution(race["boats"])
            most_likely = [int(i) for i in max(latent, key=latent.get).split("-")]
            differing += outcome["result"] != most_likely
        self.assertGreater(differing, 0)

    def test_invalid_sizes_and_seeds_fail_explicitly(self):
        for kwargs in ({"days": 0}, {"days": True}, {"days": 367}, {"days": 1.5},
                       {"races_per_day": 0}, {"races_per_day": 13},
                       {"races_per_day": False}, {"seed": True}, {"seed": "7"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                make_dataset(**kwargs)


if __name__ == "__main__":
    unittest.main()
