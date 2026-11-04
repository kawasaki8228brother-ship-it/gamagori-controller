"""Synthetic offline checks; these tests do not establish real-race performance."""

import copy
from itertools import combinations, permutations
import math
import random
import unittest

from model11.selection import build_boxes, select_five


def distribution(active=range(1, 7), weights=None):
    weights = weights or {}
    values = {"-".join(map(str, triple)): weights.get("-".join(map(str, triple)), 1.0)
              for triple in permutations(active, 3)}
    total = math.fsum(values.values())
    return {key: value / total for key, value in values.items()}


def race(active=None, manual=None):
    return {"active_boats": active or list(range(1, 7)),
            "prediction_at": "2026-11-05T14:00:00+09:00",
            "deadline": "2026-11-05T14:05:00+09:00",
            "human_box_input": manual}


def manual_input(core=None, insertion=3):
    return {"core": core or [1, 2], "insertion": insertion,
            "observed_at": "2026-11-05T13:59:56+09:00",
            "acquired_at": "2026-11-05T13:59:57+09:00",
            "available_at": "2026-11-05T13:59:58+09:00",
            "revision_at": "2026-11-05T13:59:59+09:00"}


class SelectionTests(unittest.TestCase):
    def test_missing_odds_never_fabricated_and_no_fake_hole(self):
        dist = distribution()
        result = select_five(dist)
        self.assertEqual(len(set(result["tickets"])), 5)
        self.assertEqual(len(result["main_tickets"]), 4)
        self.assertEqual(result["value_tickets"], [])
        self.assertEqual(len(result["fallback_tickets"]), 1)
        self.assertEqual(result["selection_labels"][result["fallback_tickets"][0]],
                         "PROBABILITY_FALLBACK_NOT_HOLE")
        self.assertEqual(result["bet_decision"], "SKIP")
        self.assertEqual(result["stake_yen"], 500)
        self.assertIsNone(result["expected_return_yen"])
        self.assertIsNone(result["expected_net_yen"])

    def test_three_main_two_supported_values(self):
        dist = distribution()
        odds = {key: 60.0 for key in dist}
        odds["6-5-4"], odds["6-5-3"] = 240, 180
        result = select_five(dist, odds, {"main_count": 3})
        self.assertEqual(result["main_tickets"], sorted(dist)[:3])
        self.assertEqual(result["value_tickets"], ["6-5-4", "6-5-3"])
        self.assertEqual(result["tickets"], sorted(result["tickets"]))
        self.assertEqual(result["selection_order"][-2:], ["6-5-4", "6-5-3"])
        self.assertEqual(result["fallback_tickets"], [])
        self.assertEqual(result["supported_hole_status"], "SUPPORTED")

    def test_only_one_supported_two_requested_labels_fallback(self):
        dist = distribution()
        odds = {key: 1.0 for key in dist}
        odds["6-5-4"] = 300
        result = select_five(dist, odds, {"main_count": 3})
        self.assertEqual(result["value_tickets"], ["6-5-4"])
        self.assertEqual(len(result["fallback_tickets"]), 1)
        self.assertEqual(result["supported_hole_status"], "INSUFFICIENT_SUPPORTED_HOLES")

    def test_supported_hole_does_not_force_bet(self):
        dist = distribution()
        odds = {key: 1.0 for key in dist}
        odds["6-5-4"] = 150
        result = select_five(dist, odds)
        self.assertEqual(result["value_tickets"], ["6-5-4"])
        self.assertLess(result["expected_net_yen"], 0)
        self.assertEqual(result["bet_decision"], "SKIP")

    def test_positive_expected_return_proposed_bet_and_coverage_gate(self):
        dist = distribution()
        odds = dict.fromkeys(dist, 240.0)
        result = select_five(dist, odds)
        self.assertAlmostEqual(result["expected_return_yen"], 1000)
        self.assertAlmostEqual(result["expected_net_yen"], 500)
        self.assertEqual(result["bet_decision"], "BET")
        self.assertTrue(result["simulation_only"])
        self.assertEqual(result["risk_policy_status"], "PROPOSED_NOT_ADOPTED")
        gated = select_five(dist, odds, {"min_coverage": 0.1})
        self.assertEqual(gated["bet_decision"], "SKIP")

    def test_partial_and_unexpected_odds_all_ev_unknown(self):
        dist = distribution()
        for odds in ({"1-2-3": 20}, dict(dict.fromkeys(dist, 20), **{"7-2-3": 50})):
            result = select_five(dist, odds)
            self.assertEqual(result["bet_decision"], "SKIP")
            self.assertIsNone(result["expected_return_yen"])
            self.assertIsNone(result["expected_roi"])
            self.assertEqual(result["odds_status"], "ODDS_DOMAIN_INCOMPLETE_OR_UNEXPECTED")

    def test_distribution_rejects_nonfinite_incomplete_and_wrong_types(self):
        dist = distribution()
        invalid = [None, [], {}, {"1-1-2": 1}, {"1-2-3": 1}]
        for value in (True, "0.1", float("nan"), float("inf"), -0.1):
            corrupt = dict(dist)
            corrupt["1-2-3"] = value
            invalid.append(corrupt)
        not_normalized = dict.fromkeys(dist, 0.1)
        invalid.append(not_normalized)
        for item in invalid:
            with self.subTest(item_type=type(item).__name__):
                with self.assertRaises(ValueError):
                    select_five(item)

    def test_rejects_invalid_odds_and_config(self):
        dist = distribution()
        for value in (True, "50", float("nan"), float("inf"), 0, -1):
            odds = dict.fromkeys(dist, 50)
            odds["1-2-3"] = value
            with self.subTest(odds=value):
                with self.assertRaises(ValueError):
                    select_five(dist, odds)
        for config in ([], {"main_count": True}, {"main_count": 5},
                       {"min_value_edge": -1}, {"min_coverage": 1.1}, {"unknown": 1}):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    select_five(dist, config=config)

    def test_zero_probability_valid_and_deterministic_ties(self):
        dist = distribution(range(1, 4))
        dist["1-2-3"], dist["1-3-2"] = 0, 1 / 3
        first = select_five(dist)
        second = select_five(dict(reversed(list(dist.items()))))
        self.assertEqual(first, second)
        self.assertEqual(len(first["tickets"]), 5)

    def test_coverage_is_sum_and_inputs_not_mutated(self):
        dist = distribution()
        original = copy.deepcopy(dist)
        output = select_five(dist)
        self.assertAlmostEqual(output["coverage"], sum(dist[t] for t in output["tickets"]))
        self.assertEqual(original, dist)

    def test_refunds_outcomes_not_input_to_selector(self):
        # Selection has no outcome/refund argument: refunds belong to the evaluator.
        dist = distribution()
        with self.assertRaises(TypeError):
            select_five(dist, refund_tickets=["1-2-3"])

    def test_monetary_overflow_is_rejected_not_returned_in_report(self):
        dist = distribution()
        with self.assertRaises(ValueError):
            select_five(dist, dict.fromkeys(dist, 1e308))


class BoxTests(unittest.TestCase):
    def test_all_box_ticket_stakes_coverage_null_ev_and_legacy_status(self):
        dist = distribution()
        five = select_five(dist)
        boxes = build_boxes(race(), dist, five)
        for name in ("human_research", "mechanical_research", "box_v11_research"):
            box = boxes[name]
            self.assertEqual(len(box["boats"]), 3)
            self.assertEqual(len(set(box["tickets"])), 6)
            self.assertEqual(box["stake_yen"], 600)
            self.assertAlmostEqual(box["coverage"], 6 / 120)
            self.assertIsNone(box["expected_return_yen"])
            self.assertEqual(box["bet_decision"], "SKIP")
            self.assertFalse(box["formal_box_v1_reproduction"])
        self.assertEqual(boxes["box_v11_research"]["objective_status"], "EV_UNKNOWN_PROBABILITY_FALLBACK")
        self.assertEqual(boxes["legacy_box_v1"]["status"], "UNVERIFIED_ORIGINAL_BYTES_SHA_NOT_PROVIDED")
        self.assertIsNone(boxes["legacy_box_v1"]["human"])

    def test_human_automatic_can_differ_from_mechanical(self):
        # Fixed synthetic seed; no actual race inputs or fitted coefficients.
        rng = random.Random(47)
        weights = {"-".join(map(str, triple)): rng.random() ** 4
                   for triple in permutations(range(1, 7), 3)}
        dist = distribution(weights=weights)
        five = select_five(dist)
        boxes = build_boxes(race(), dist, five)
        self.assertNotEqual(boxes["human_research"]["boats"], boxes["mechanical_research"]["boats"])
        self.assertEqual(boxes["composition_difference"], "YES")
        human = boxes["human_research"]
        expected_counts = {str(boat): sum(str(boat) in ticket.split("-") for ticket in five["tickets"])
                           for boat in range(1, 7)}
        self.assertEqual(human["five_appearance_counts"], expected_counts)
        self.assertEqual(human["method"], "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH")

    def test_no_artificial_difference_on_equal_best_sets(self):
        dist = distribution()
        boxes = build_boxes(race(), dist, select_five(dist))
        self.assertEqual(boxes["composition_difference"], "NO")
        self.assertEqual(boxes["human_research"]["boats"], [1, 2, 3])
        self.assertEqual(boxes["mechanical_research"]["boats"], [1, 2, 3])

    def test_manual_human_asof_core_insertion(self):
        dist = distribution()
        manual = manual_input([6, 5], 4)
        boxes = build_boxes(race(manual=manual), dist, select_five(dist))
        self.assertEqual(boxes["human_research"]["core"], [6, 5])
        self.assertEqual(boxes["human_research"]["insertion"], 4)
        self.assertEqual(boxes["human_research"]["boats"], [4, 5, 6])
        self.assertEqual(boxes["mechanical_research"]["boats"], [1, 2, 3])

    def test_manual_future_invalid_duplicate_and_naive_rejected(self):
        dist = distribution()
        valid = manual_input()
        variants = [dict(valid, observed_at="2026-11-05T14:00:01+09:00"),
                    dict(valid, observed_at="2026-11-05T13:59:59"),
                    dict(valid, observed_at="2026-11-05T13:59:59-00:00"),
                    dict(valid, observed_at="2026-11-05T13:59:59.1234567+09:00"),
                    dict(valid, insertion=2), dict(valid, insertion=True),
                    dict(valid, core=[1, 7]), dict(valid, extra="unrecognized")]
        for manual in variants:
            with self.subTest(manual=manual):
                with self.assertRaises(ValueError):
                    build_boxes(race(manual=manual), dist, select_five(dist))

    def test_manual_all_availability_fields_mandatory_and_pre_prediction(self):
        dist = distribution()
        valid = manual_input()
        fields = ["observed_at", "acquired_at", "available_at", "revision_at"]
        for field in fields:
            missing = dict(valid)
            del missing[field]
            variants = [missing, dict(valid, **{field: "2026-11-05T14:00:01+09:00"})]
            for manual in variants:
                with self.subTest(field=field, manual=manual):
                    with self.assertRaises(ValueError):
                        build_boxes(race(manual=manual), dist, select_five(dist))
        with self.assertRaises(ValueError):
            build_boxes(race(manual=dict(valid, available_at="2026-11-05T13:59:56+09:00")),
                        dist, select_five(dist))

    def test_manual_availability_exactly_at_prediction_is_allowed(self):
        dist = distribution()
        manual = manual_input()
        for field in ["observed_at", "acquired_at", "available_at", "revision_at"]:
            manual[field] = "2026-11-05T14:00:00+09:00"
        boxes = build_boxes(race(manual=manual), dist, select_five(dist))
        self.assertEqual(boxes["human_research"]["manual_status"], "AS_OF_GATE_PASSED_NOT_LEGACY_PROOF")

    def test_mechanical_global_optimum_six_permutation_mass(self):
        weights = {"-".join(map(str, triple)): 50 for triple in permutations((3, 5, 6), 3)}
        dist = distribution(weights=weights)
        boxes = build_boxes(race(), dist, select_five(dist))
        mechanical = boxes["mechanical_research"]
        self.assertEqual(mechanical["boats"], [3, 5, 6])
        for boats in combinations(range(1, 7), 3):
            mass = sum(dist["-".join(map(str, triple))] for triple in permutations(boats))
            self.assertGreaterEqual(mechanical["coverage"] + 1e-12, mass)

    def test_v11_optimizes_ev_independently_of_mechanical(self):
        dist = distribution()
        odds = dict.fromkeys(dist, 1.0)
        for triple in permutations((4, 5, 6), 3):
            odds["-".join(map(str, triple))] = 300.0
        boxes = build_boxes(race(), dist, select_five(dist, odds), odds)
        self.assertEqual(boxes["mechanical_research"]["boats"], [1, 2, 3])
        self.assertEqual(boxes["box_v11_research"]["boats"], [4, 5, 6])
        self.assertAlmostEqual(boxes["box_v11_research"]["expected_return_yen"], 1500)
        self.assertAlmostEqual(boxes["box_v11_research"]["expected_net_yen"], 900)

    def test_overlap_report_is_set_intersection_no_double_count(self):
        dist = distribution()
        five = select_five(dist)
        boxes = build_boxes(race(), dist, five)
        expected = sorted(set(five["tickets"]) & set(boxes["human_research"]["tickets"]))
        self.assertEqual(boxes["overlap"]["five_vs_human_research"], expected)
        union = set(five["tickets"])
        for name in ("human_research", "mechanical_research", "box_v11_research"):
            union.update(boxes[name]["tickets"])
        self.assertEqual(boxes["overlap"]["unique_ticket_union"], sorted(union))
        self.assertEqual(len(boxes["overlap"]["unique_ticket_union"]), len(union))

    def test_three_active_boat_domain(self):
        dist = distribution((2, 4, 6))
        result = build_boxes(race([2, 4, 6]), dist, select_five(dist))
        self.assertEqual(result["human_research"]["boats"], [2, 4, 6])
        self.assertAlmostEqual(result["mechanical_research"]["coverage"], 1.0)

    def test_race_mismatch_and_invalid_five_rejected(self):
        dist = distribution()
        five = select_five(dist)
        for invalid_race in (None, race([1, 2, 3]), race([1, 2, 3, 4, 5, True]),
                             dict(race(), prediction_at="2026-11-05T14:05:00+09:00")):
            with self.assertRaises(ValueError):
                build_boxes(invalid_race, dist, five)
        for invalid in (None, {"tickets": ["1-2-3"] * 5}, {"tickets": [True] * 5}):
            with self.assertRaises(ValueError):
                build_boxes(race(), dist, invalid)

    def test_partial_odds_all_box_returns_null(self):
        dist = distribution()
        boxes = build_boxes(race(), dist, select_five(dist), {"1-2-3": 100})
        for name in ("human_research", "mechanical_research", "box_v11_research"):
            self.assertIsNone(boxes[name]["expected_net_yen"])
            self.assertEqual(boxes[name]["bet_decision"], "SKIP")


if __name__ == "__main__":
    unittest.main()
