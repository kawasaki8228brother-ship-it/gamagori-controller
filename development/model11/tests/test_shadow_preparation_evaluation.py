"""Pure planning arithmetic; no actual datasets or adopted F5 rules."""
from copy import deepcopy
import json
import math
import unittest

from model11.shadow_preparation.evaluation_design import (
    CURRENT_GRID, grid_accounting, illustrative_sample_days, multiplicity_plan, proposed_options,
)


class EvaluationDesignTests(unittest.TestCase):
    def test_actual_frozen_v003_grid_is_72_nominal_61_structural_bound(self):
        from model11.revision_v003.course import COURSE_POLICIES
        from model11.revision_v003.walkforward import _config
        actual = _config(None, COURSE_POLICIES["EXHIBITION_ONLY_V001"])
        self.assertEqual({key: actual[key] for key in CURRENT_GRID}, CURRENT_GRID)
        counted = grid_accounting(**CURRENT_GRID)
        self.assertEqual(counted["nominal_grid_members"], 72)
        self.assertEqual(counted["market_only_nominal_members"], 12)
        self.assertEqual(counted["structural_probability_upper_bound"], 61)
        self.assertIsNone(counted["independent_hypothesis_count"])

    def test_grid_without_market_endpoint_and_invalid_values(self):
        smaller = {**deepcopy(CURRENT_GRID), "market_weights": [0, .5]}
        report = grid_accounting(**smaller)
        self.assertEqual(report["nominal_grid_members"], 24)
        self.assertEqual(report["structural_probability_upper_bound"], 24)
        for wrong in ({"alphas": [True]}, {"temperatures": [0]}, {"market_weights": [0, 0]},
                      {"candidates": []}, {"market_weights": [math.nan]}, {"alphas": [1.1]}):
            with self.assertRaises(ValueError):
                grid_accounting(**{**deepcopy(CURRENT_GRID), **wrong})

    def test_sample_known_vector_and_unrounded_variance_inflation(self):
        self.assertEqual(illustrative_sample_days(1, 1)["estimated_days"], 8)
        base = illustrative_sample_days(.1, .02)
        self.assertEqual(base["estimated_days"], 197)
        doubled = illustrative_sample_days(.1, .02, design_effect=2)
        self.assertEqual(doubled["estimated_days"], 393)
        self.assertEqual(doubled["assumptions"], "ASSUMPTIONS_NOT_VALIDATED")
        self.assertFalse(doubled["power_guarantee"])

    def test_unknown_variance_and_invalid_controls_never_impute_days(self):
        for sd in (None, 0):
            result = illustrative_sample_days(sd)
            self.assertEqual(result["status"], "UNVERIFIED")
            self.assertIsNone(result["estimated_days"])
        for change in ({"effect": 0}, {"power": .5}, {"alpha": 0}, {"comparisons": True},
                       {"design_effect": .9}, {"planned_days": 0}):
            result = illustrative_sample_days(.1, **change)
            self.assertEqual(result["status"], "STOP")
            self.assertIsNone(result["estimated_days"])
        for sd in (-1, math.nan, math.inf, 10**1000):
            self.assertEqual(illustrative_sample_days(sd)["status"], "STOP")

    def test_more_comparisons_more_uncertainty_and_no_adequacy_pass(self):
        one = illustrative_sample_days(.1, .02, planned_days=4)
        many = illustrative_sample_days(.1, .02, comparisons=61, planned_days=10000)
        self.assertGreater(many["estimated_days"], one["estimated_days"])
        self.assertEqual(one["arithmetic_shortfall_days"], 193)
        self.assertEqual(many["arithmetic_shortfall_days"], 0)
        self.assertTrue(many["adequacy"].startswith("UNVERIFIED"))
        self.assertFalse(many["adopted"])

    def test_union_bound_and_holm_known_arithmetic_not_actual_tests(self):
        one = multiplicity_plan(.025, 1)
        self.assertEqual(one["bonferroni_per_test_alpha"], .025)
        many = multiplicity_plan(.025, 61)
        self.assertAlmostEqual(many["bonferroni_per_test_alpha"], .025/61)
        self.assertEqual(many["holm_first_rank_alpha"], many["bonferroni_per_test_alpha"])
        self.assertEqual(many["holm_last_rank_alpha"], .025)
        self.assertEqual(many["uncorrected_union_bound_if_each_uses_family_alpha"], 1)
        self.assertAlmostEqual(many["bonferroni_union_bound"], .025)
        self.assertFalse(many["actual_tests_performed"])
        for alpha, m in ((0, 1), (.025, 0), (.025, True), (math.nan, 1)):
            with self.assertRaises(ValueError):
                multiplicity_plan(alpha, m)

    def test_options_concrete_but_never_adopt_or_change_default_grid(self):
        frozen = deepcopy(CURRENT_GRID)
        result = proposed_options()
        self.assertEqual([item["selection_target_days"] for item in result["alternatives"]], [24, 36, 60])
        self.assertEqual([item["accounting"]["nominal_grid_members"] for item in result["alternatives"]], [6, 12, 72])
        self.assertEqual([item["accounting"]["structural_probability_upper_bound"] for item in result["alternatives"]], [6, 11, 61])
        self.assertEqual([item["nonbaseline_structural_comparison_upper_bound"] for item in result["alternatives"]], [5, 10, 60])
        for item in result["alternatives"]:
            self.assertFalse(item["adopted"])
            self.assertFalse(item["default_execution_grid_changed"])
            self.assertFalse(item["production_go"])
            self.assertEqual(item["grid"]["market_weights"], frozen["market_weights"])
        result["alternatives"][0]["grid"]["market_weights"].append(.99)
        self.assertEqual(len(result["alternatives"][1]["grid"]["market_weights"]), 6)
        self.assertEqual(CURRENT_GRID, frozen)
        self.assertEqual(len(proposed_options()["alternatives"][0]["grid"]["market_weights"]), 6)

    def test_all_helpers_emit_finite_json_and_no_go(self):
        reports = [grid_accounting(**CURRENT_GRID), multiplicity_plan(),
                   illustrative_sample_days(.1), illustrative_sample_days(None), proposed_options()]
        for report in reports:
            json.dumps(report, allow_nan=False)
            self.assertFalse(report["production_go"])
            self.assertFalse(report["adopted"])


if __name__ == "__main__":
    unittest.main()
