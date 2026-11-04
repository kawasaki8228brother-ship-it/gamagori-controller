import copy
import unittest

from model11.synthetic import make_dataset
from model11.walkforward import walk_forward


SMALL = {"train_days": 5, "selection_days": 2, "test_days": 2,
         "candidates": ["hierarchical", "contextual"], "alphas": [0, .5],
         "temperatures": [1.0], "market_weights": [0, .25], "epochs": 3}


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.data = make_dataset(days=11, races_per_day=1)

    def test_disjoint_whole_days_and_nonoverlapping_heldout(self):
        result = walk_forward(self.data, SMALL)
        self.assertEqual(len(result["records"]), 4)
        seen = set()
        for fold in result["folds"]:
            train, select, test = map(set, (fold["train_days"], fold["selection_days"], fold["test_days"]))
            self.assertFalse(train & select or train & test or select & test or seen & test)
            self.assertLess(max(train), min(select))
            self.assertLess(max(select), min(test))
            seen |= test
        self.assertFalse(result["production_go"])
        self.assertEqual(result["superiority"], "UNVERIFIED")

    def test_test_labels_never_change_that_fold_selection_or_predictions(self):
        original = walk_forward(self.data, SMALL)
        changed = copy.deepcopy(self.data)
        changed["outcomes"][7]["result"] = [6, 5, 4]
        changed["outcomes"][7]["payout_per_100"] = 77777
        alternate = walk_forward(changed, SMALL)
        self.assertEqual(original["folds"][0]["selected"], alternate["folds"][0]["selected"])
        self.assertEqual(original["folds"][0]["forecast_hashes"], alternate["folds"][0]["forecast_hashes"])

    def test_repeatability_and_future_features_do_not_change_past_predictions(self):
        first = walk_forward(self.data, SMALL)
        self.assertEqual(first, walk_forward(self.data, SMALL))
        changed = copy.deepcopy(self.data)
        changed["races"][-1]["boats"][0]["features"]["turn"] = -.999
        second = walk_forward(changed, SMALL)
        self.assertEqual(first["folds"][0]["forecast_hashes"], second["folds"][0]["forecast_hashes"])

    def test_late_training_label_is_stop_not_silently_fit(self):
        self.data["outcomes"][0]["available_at"] = self.data["races"][-1]["deadline"]
        with self.assertRaisesRegex(ValueError, "TRAIN_LABEL_UNAVAILABLE"):
            walk_forward(self.data, SMALL)

    def test_late_selection_label_is_stop(self):
        self.data["outcomes"][5]["available_at"] = self.data["races"][-1]["deadline"]
        with self.assertRaisesRegex(ValueError, "SELECTION_LABEL_UNAVAILABLE"):
            walk_forward(self.data, SMALL)

    def test_duplicate_and_missing_labels_are_stop(self):
        self.data["races"].append(copy.deepcopy(self.data["races"][0]))
        with self.assertRaisesRegex(ValueError, "DATASET_GATE"):
            walk_forward(self.data, SMALL)
        self.data["races"].pop()
        self.data["outcomes"].pop()
        with self.assertRaisesRegex(ValueError, "PAIRING_NOT_EXACT"):
            walk_forward(self.data, SMALL)

    def test_invalid_grid_is_rejected_even_without_market(self):
        for race in self.data["races"]:
            race["odds_snapshot"] = None
        for field, value in (("market_weights", float("nan")), ("alphas", 2), ("temperatures", 0)):
            with self.assertRaisesRegex(ValueError, "INVALID_SELECTION_GRID"):
                walk_forward(self.data, {**SMALL, field: [value]})


if __name__ == "__main__":
    unittest.main()
