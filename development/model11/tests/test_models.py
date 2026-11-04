"""Synthetic unit tests; none is evidence of real-race model improvement."""
from copy import deepcopy
from itertools import permutations
import json
import math
import unittest

from model11.models import FEATURES, make_model, from_dict
from model11.probabilities import market_distribution, loglinear_pool, temperature_scale


def race(race_id="synthetic-001", active=None):
    active = list(range(1, 7)) if active is None else active
    return {"race_id": race_id, "target_date": "2026-01-01", "venue": "GAMAGORI",
            "prediction_at": "2026-01-01T12:00:00+09:00",
            "deadline": "2026-01-01T12:05:00+09:00", "active_boats": active,
            "boats": [{"boat": b, "course": b,
                       "features": {f: 0.0 for f in FEATURES},
                       "observed_at": "2026-01-01T11:59:00+09:00",
                       "motor_updated_at": "2026-01-01T11:00:00+09:00",
                       "revision_at": "2026-01-01T11:59:00+09:00",
                       "fl": False, "scratched": False} for b in active],
            "odds_snapshot": None}


def outcome(record, order=(1, 2, 3)):
    return {"race_id": record["race_id"], "target_date": record["target_date"],
            "result": list(order), "payout_per_100": 1000.0, "refund_tickets": [],
            "final": True, "available_at": "2026-01-01T12:10:00+09:00"}


def snapshot(record):
    record["odds_snapshot"] = {
        "acquired_at": "2026-01-01T11:59:00+09:00",
        "available_at": "2026-01-01T11:59:00+09:00",
        "revision_at": "2026-01-01T11:59:00+09:00",
        "odds": {"-".join(map(str, p)): 120.0 for p in permutations(record["active_boats"], 3)}}
    return record


class ModelTests(unittest.TestCase):
    def test_uniform_120_and_all_active_domains(self):
        for name in ("hierarchical", "contextual"):
            for count in range(3, 7):
                dist = make_model(name).distributions(race(active=list(range(1, count+1))))
                for values in dist.values():
                    self.assertEqual(len(values), count*(count-1)*(count-2))
                    self.assertAlmostEqual(math.fsum(values.values()), 1.0, places=13)
                    for key, value in values.items():
                        self.assertEqual(len(set(key.split("-"))), 3)
                        self.assertAlmostEqual(value, 1.0 / len(values), places=14)

    def test_exact_conditional_factorization(self):
        record = race()
        record["boats"][0]["features"]["st"] = 1.0
        model = make_model("contextual")
        model.weights[0][0] = 2.0
        model.weights[1][1] = -1.3
        model.weights[2][2] = 0.6
        values = model.distributions(record)["P_raw"]
        for a, b, c in permutations(record["active_boats"], 3):
            product = (model.conditionals(record)[a] * model.conditionals(record, a)[b]
                       * model.conditionals(record, a, b)[c])
            self.assertAlmostEqual(values[f"{a}-{b}-{c}"], product, places=14)

    def test_learns_three_distinct_stage_heads(self):
        records = [race(f"train-{n:02}") for n in range(12)]
        for record in records:
            for entry in record["boats"]:
                entry["features"]["st"] = 1.0 if entry["boat"] == 1 else -1.0
                entry["features"]["turn"] = 1.0 if entry["boat"] == 2 else -1.0
                entry["features"]["motor"] = 1.0 if entry["boat"] == 3 else -1.0
        for name in ("hierarchical", "contextual"):
            model = make_model(name).fit(records, [outcome(r) for r in records])
            self.assertGreater(model.conditionals(records[0])[1], 0.85)
            self.assertGreater(model.conditionals(records[0], 1)[2], 0.85)
            self.assertGreater(model.conditionals(records[0], 1, 2)[3], 0.85)
            self.assertNotEqual(model.weights[0], model.weights[1])
            self.assertNotEqual(model.weights[1], model.weights[2])

    def test_contextual_learns_context_flip_linear_cannot(self):
        records, outcomes = [], []
        for n in range(24):
            record = race(f"context-{n:02}", active=[1, 2, 3])
            direction = 1.0 if n % 2 else -1.0
            record["boats"][0]["features"].update(ability=1.0, st=direction)
            record["boats"][1]["features"].update(ability=-1.0, turn=1.0)
            record["boats"][2]["features"].update(ability=-1.0, turn=-1.0)
            records.append(record)
            outcomes.append(outcome(record, (1, 2, 3) if direction > 0 else (1, 3, 2)))
        linear = make_model("hierarchical").fit(records, outcomes)
        contextual = make_model("contextual").fit(records, outcomes)
        for record, result in zip(records[:2], outcomes[:2]):
            wanted = result["result"][1]
            self.assertAlmostEqual(linear.conditionals(record, 1)[wanted], 0.5, places=12)
            self.assertGreater(contextual.conditionals(record, 1)[wanted], 0.9)

    def test_course_prior_is_separate_from_raw_and_market(self):
        records = [race(f"prior-{n}") for n in range(10)]
        model = make_model("hierarchical", {"alpha": 1.0}).fit(records, [outcome(r) for r in records])
        raw, adjusted = model.conditionals(records[0]), model.conditionals(records[0], stage="model")
        self.assertAlmostEqual(raw[1], 1/6)
        self.assertGreater(adjusted[1], adjusted[2])
        before = model.distributions(records[0])
        with_odds = snapshot(deepcopy(records[0]))
        with_odds["odds_snapshot"]["odds"]["1-2-3"] = 2.0
        self.assertEqual(before, model.distributions(with_odds))

    def test_deterministic_fit_and_json_roundtrip(self):
        records = [race(f"fit-{n}") for n in range(3)]
        results = [outcome(r) for r in records]
        model = make_model("contextual").fit(records, results)
        second = make_model("contextual").fit(list(reversed(records)), list(reversed(results)))
        self.assertEqual(model.to_dict(), second.to_dict())
        encoded = json.dumps(model.to_dict(), allow_nan=False, sort_keys=True)
        restored = from_dict(json.loads(encoded))
        self.assertEqual(model.distributions(records[0]), restored.distributions(records[0]))
        model.fit(records, results)
        self.assertEqual(model.to_dict(), second.to_dict())

    def test_training_time_provenance_and_unknown_not_filled(self):
        record = race()
        result = outcome(record)
        model = make_model("hierarchical").fit([record], [result])
        self.assertEqual(model.training_max_available_at, result["available_at"])
        self.assertEqual(model.training_max_prediction_at, record["prediction_at"])
        self.assertEqual(model.to_dict()["training_time_provenance"], "UNVERIFIED_SELF_REPORTED_INPUT")
        incomplete = deepcopy(result)
        del incomplete["available_at"]
        model.fit([record], [incomplete])
        self.assertIsNone(model.training_max_available_at)
        self.assertIsNotNone(model.training_max_prediction_at)
        payload = model.to_dict()
        payload["training_max_available_at"] = "2026-01-01T12:00:00"
        with self.assertRaises(ValueError):
            from_dict(payload)

    def test_prediction_relabels_equivariantly_without_course_prior(self):
        record = race()
        record["boats"][0]["features"]["motor"] = 0.7
        model = make_model("hierarchical")
        model.weights[0][2] = 2.0
        mapping = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
        changed = deepcopy(record)
        changed["active_boats"] = [mapping[b] for b in record["active_boats"]]
        for entry in changed["boats"]:
            entry["boat"] = mapping[entry["boat"]]
        original = model.distributions(record)["P_raw"]
        relabeled = model.distributions(changed)["P_raw"]
        for ticket, value in original.items():
            key = "-".join(str(mapping[int(b)]) for b in ticket.split("-"))
            self.assertAlmostEqual(value, relabeled[key], places=14)

    def test_extreme_finite_logits_remain_positive_and_normalized(self):
        model = make_model("hierarchical")
        payload = model.to_dict()
        payload["weights"] = [[1e6] * 5 for _ in range(3)]
        model = from_dict(payload)
        record = race()
        for item in record["boats"]:
            item["features"] = {f: (1.0 if item["boat"] == 1 else -1.0) for f in FEATURES}
        for values in model.distributions(record).values():
            self.assertAlmostEqual(math.fsum(values.values()), 1.0, places=13)
            self.assertTrue(all(math.isfinite(v) and v > 0 for v in values.values()))

    def test_explanation_sums_to_logits(self):
        record = race()
        record["boats"][0]["features"]["st"] = 0.5
        model = make_model("contextual")
        model.weights[0][0] = 2.0
        explanation = model.explain(record)
        e = math.exp(1.0)
        self.assertAlmostEqual(sum(explanation[1]["contributions"].values()), 1.0)
        self.assertAlmostEqual(explanation[1]["probability"], e/(e+5))

    def test_feature_availability_metadata_allowed_and_outcomes_still_rejected(self):
        record = race()
        for entry in record["boats"]:
            entry["feature_times"] = {
                feature: {"acquired_at": "2026-01-01T11:55:00+09:00",
                          "available_at": "2026-01-01T11:56:00+09:00",
                          "revision_at": "2026-01-01T11:57:00+09:00"}
                for feature in FEATURES}
        self.assertEqual(len(make_model("hierarchical").distributions(record)["P_model"]), 120)
        record["boats"][0]["feature_times"]["st"]["outcome"] = [1, 2, 3]
        with self.assertRaises(ValueError):
            make_model("hierarchical").distributions(record)

    def test_shape_finite_and_outcome_rejections(self):
        mutations = [lambda r: r["boats"][0]["features"].update(st=float("nan")),
                     lambda r: r["boats"][0]["features"].update(st=1.01),
                     lambda r: r["boats"][0]["features"].update(st=True),
                     lambda r: r["boats"][0].update(scratched=True),
                     lambda r: r["active_boats"].append(1),
                     lambda r: r.update(extra={"result": [1, 2, 3]}),
                     lambda r: r["boats"][0]["features"].pop("exhibition"),
                     lambda r: r["boats"][1].update(course=1)]
        for mutate in mutations:
            record = race()
            mutate(record)
            with self.assertRaises(ValueError):
                make_model("hierarchical").distributions(record)
        for arguments in ({"second": 2}, {"first": 1, "second": 1}, {"first": 7}, {"stage": "unknown"}):
            with self.assertRaises(ValueError):
                make_model("hierarchical").conditionals(race(), **arguments)

    def test_fit_rejects_duplicate_nonfinal_or_mismatched_results(self):
        record = race()
        good = outcome(record)
        bad = deepcopy(good)
        bad["final"] = False
        attempts = [([record, record], [good]), ([record], [good, good]),
                    ([record], [bad]), ([record], []), ([record], [{**good, "result": [1, 1, 2]}]),
                    ([record], [{**good, "target_date": "2026-01-02"}])]
        for records, outcomes in attempts:
            model = make_model("hierarchical")
            original = model.to_dict()
            with self.assertRaises(ValueError):
                model.fit(records, outcomes)
            self.assertEqual(original, model.to_dict())

    def test_config_and_serialization_reject_invalid(self):
        for config in ({"alpha": 1.1}, {"epochs": True}, {"prior_strength": 0},
                       {"learning_rate": float("inf")}, {"future_optimize": True}):
            with self.assertRaises(ValueError):
                make_model("hierarchical", config)
        payload = make_model("hierarchical").to_dict()
        payload["weights"][0][0] = float("nan")
        with self.assertRaises(ValueError):
            from_dict(payload)


class ProbabilityTests(unittest.TestCase):
    def test_market_complete_and_unequal_odds(self):
        record = snapshot(race())
        record["odds_snapshot"]["odds"]["1-2-3"] = 60.0
        report = market_distribution(record)
        self.assertEqual(report["status"], "AVAILABLE")
        self.assertAlmostEqual(report["P_market"]["1-2-3"], 2/121)
        self.assertAlmostEqual(sum(report["P_market"].values()), 1.0)
        # A source may have been revised before its latest acquisition.
        record["odds_snapshot"]["revision_at"] = "2026-01-01T11:58:00+09:00"
        self.assertEqual(market_distribution(record)["status"], "AVAILABLE")

    def test_market_absent_stale_and_missing_never_fabricated(self):
        record = race()
        self.assertIsNone(market_distribution(record)["P_market"])
        snapshot(record)
        self.assertIsNone(market_distribution(record, 59)["P_market"])
        self.assertEqual(market_distribution(record, 60)["status"], "AVAILABLE")
        record["odds_snapshot"]["odds"].pop("1-2-3")
        self.assertIsNone(market_distribution(record)["P_market"])

    def test_market_rejects_cross_race_date_or_venue_snapshot(self):
        for field, wrong in (("race_id", "another-race"), ("target_date", "2026-01-02"),
                             ("venue", "ANOTHER_VENUE")):
            record = snapshot(race())
            record["odds_snapshot"][field] = wrong
            self.assertEqual(market_distribution(record)["reason"], "ODDS_IDENTITY_MISMATCH")
            self.assertIsNone(market_distribution(record)["P_market"])

    def test_market_rejects_future_revision_and_invalid_values(self):
        record = snapshot(race())
        for field in ("acquired_at", "available_at", "revision_at"):
            bad = deepcopy(record)
            bad["odds_snapshot"][field] = "2026-01-01T12:01:00+09:00"
            self.assertEqual(market_distribution(bad)["status"], "INVALID")
        for value in (0, -1, True, float("nan"), float("inf")):
            bad = deepcopy(record)
            bad["odds_snapshot"]["odds"]["1-2-3"] = value
            self.assertEqual(market_distribution(bad)["status"], "INVALID")
        bad = deepcopy(record)
        bad["prediction_at"] = "2026-01-01T12:00:00"
        self.assertEqual(market_distribution(bad)["status"], "INVALID")

    def test_market_availability_is_required_aware_and_ordered(self):
        for value in (None, "2026-01-01T11:59:00", "2026-01-01T11:58:59+09:00"):
            record = snapshot(race())
            record["odds_snapshot"]["available_at"] = value
            self.assertEqual(market_distribution(record)["status"], "INVALID")
            self.assertIsNone(market_distribution(record)["P_market"])
        record = snapshot(race())
        del record["odds_snapshot"]["available_at"]
        self.assertEqual(market_distribution(record)["status"], "INVALID")
        self.assertIsNone(market_distribution(record)["P_market"])

    def test_market_extreme_finite_odds_stable(self):
        record = snapshot(race(active=[1, 2, 3]))
        record["odds_snapshot"]["odds"]["1-2-3"] = 1e-300
        record["odds_snapshot"]["odds"]["1-3-2"] = 1e300
        values = market_distribution(record)["P_market"]
        self.assertAlmostEqual(sum(values.values()), 1.0)
        self.assertTrue(all(math.isfinite(v) and v > 0 for v in values.values()))

    def test_loglinear_endpoints_and_temperature(self):
        left, right = {"a": 0.9, "b": 0.1}, {"a": 0.2, "b": 0.8}
        for weight, expected in ((0, left), (1, right)):
            result = loglinear_pool(left, right, weight)
            for key in left:
                self.assertAlmostEqual(result[key], expected[key])
        middle = loglinear_pool(left, right, 0.5)
        self.assertAlmostEqual(middle["a"] / middle["b"], math.sqrt(18/8))
        self.assertGreater(temperature_scale(left, 0.5)["a"], left["a"])
        self.assertLess(temperature_scale(left, 2)["a"], left["a"])
        for temperature in (1e-308, 1e308):
            values = temperature_scale(left, temperature)
            self.assertAlmostEqual(sum(values.values()), 1.0)
            self.assertTrue(all(math.isfinite(v) and v > 0 for v in values.values()))

    def test_probability_operations_reject_invalid_domains(self):
        for bad in ({"a": 0, "b": 1}, {"a": float("nan")}, {"a": 0.4}, {}):
            with self.assertRaises(ValueError):
                temperature_scale(bad, 1)
        for weight in (-0.1, 1.1, float("inf"), True):
            with self.assertRaises(ValueError):
                loglinear_pool({"a": 1.0}, {"a": 1.0}, weight)
        with self.assertRaises(ValueError):
            loglinear_pool({"a": 1.0}, {"b": 1.0}, 0.5)
        with self.assertRaises(ValueError):
            temperature_scale({"a": 1.0}, 0)


if __name__ == "__main__":
    unittest.main()
