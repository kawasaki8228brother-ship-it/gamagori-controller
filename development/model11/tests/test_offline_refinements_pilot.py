"""Invented score summaries only, never real races or pilot variance evidence."""
from copy import deepcopy
import json
import math
import unittest
from unittest import mock

from model11.offline_refinements.pilot import summarize_pilot

BASE = {"baseline_id": "SYNTHETIC_MARKET", "baseline_version": "SYNTHETIC_v001"}


def row(number, day, difference=1):
    return {"race_id": f"SYNTHETIC_SECRET_RACE_{number}", "target_date": f"2099-01-{day:02}",
            **BASE, "model_ll": 1+difference, "market_ll": 1.0,
            "state": "PAIRED", "missing_reason": None}


def roster_for(rows):
    return [{key: item[key] for key in ("race_id", "target_date")} for item in rows]


def summarize(rows, roster=None, **options):
    return summarize_pilot(roster_for(rows) if roster is None else roster,
                           rows, **BASE, roster_complete=True, **options)


class PilotSummaryTests(unittest.TestCase):
    def test_two_days_unequal_race_counts_equal_day_sample_sd(self):
        rows = [row(1, 1, 1), row(2, 2, 3), row(3, 2, 3), row(4, 2, 3)]
        report = summarize(rows)
        self.assertAlmostEqual(report["sd_day"], math.sqrt(2))
        self.assertEqual(report["counts"]["paired_day_clusters"], 2)
        self.assertEqual(report["counts"]["paired_races"], 4)
        self.assertEqual(report["sample_variance_denominator"], "K_MINUS_1")
        self.assertEqual(report["missing_rates"]["TOTAL_UNPAIRED"], 0)

    def test_three_day_known_vector_uses_n_minus_one(self):
        report = summarize([row(1, 1, 1), row(2, 2, 3), row(3, 3, 5)])
        self.assertEqual(report["sd_day"], 2)
        self.assertNotEqual(report["sd_day"], math.sqrt(8/3))
        self.assertFalse(report["power_guarantee"])

    def test_missing_read_failed_and_absent_observation_are_distinct(self):
        rows = [row(1, 1), row(2, 2), row(3, 3)]
        rows[1].update(model_ll=None, state="MISSING", missing_reason="MODEL_MISSING")
        rows[2].update(market_ll=None, state="READ_FAILED", missing_reason="MARKET_READ_FAILED")
        planned = roster_for(rows+[row(4, 4)])
        report = summarize(rows, roster=planned)
        self.assertEqual(report["counts"]["planned_race_denominator"], 4)
        self.assertEqual(report["missing_rates"], {"MISSING": .25, "READ_FAILED": .25,
                                                 "NO_OBSERVATION": .25, "TOTAL_UNPAIRED": .75})
        self.assertEqual(report["missing_reason_counts"], {"MARKET_READ_FAILED": 1, "MODEL_MISSING": 1})
        self.assertEqual(report["status"], "UNVERIFIED")

    def test_absent_or_unconfirmed_roster_never_claims_complete_zero_missingness(self):
        rows = [row(1, 1), row(2, 2, 3)]
        for planned in (None, roster_for(rows)):
            report = summarize_pilot(planned, rows, **BASE)
            self.assertAlmostEqual(report["sd_day"], math.sqrt(2))
            self.assertIsNone(report["counts"]["planned_race_denominator"])
            self.assertTrue(all(value is None for value in report["missing_rates"].values()))
            self.assertEqual(report["roster_completeness"], "UNVERIFIED")

    def test_single_day_none_and_actual_zero_sd_are_distinct(self):
        one = summarize([row(1, 1), row(2, 1)])
        self.assertIsNone(one["sd_day"])
        zero = summarize([row(1, 1), row(2, 2)])
        self.assertEqual(zero["sd_day"], 0)
        self.assertIn("NOT_ZERO_FUTURE_VARIANCE", zero["dispersion_status"])
        empty = summarize_pilot([], [], **BASE, roster_complete=True)
        self.assertIsNone(empty["sd_day"])
        self.assertEqual(empty["baseline_binding"], "UNVERIFIED_NO_OBSERVATIONS")
        self.assertTrue(all(value is None for value in empty["missing_rates"].values()))

    def test_duplicate_and_conflicting_date_stop_entire_summary(self):
        one = row(1, 1)
        for bad in (deepcopy(one), {**one, "target_date": "2099-01-02"}):
            report = summarize_pilot(None, [one, bad], **BASE)
            self.assertEqual(report["status"], "HOLD")
            self.assertIsNone(report["sd_day"])
            self.assertIsNone(report["counts"])
        self.assertEqual(summarize_pilot([*roster_for([one]), *roster_for([one])], [one], **BASE)["status"], "HOLD")

    def test_nan_infinity_negative_bool_and_reason_contradictions_hold(self):
        for value in (math.nan, math.inf, -0.01, True, "1"):
            bad = row(1, 1)
            bad["model_ll"] = value
            self.assertEqual(summarize([bad])["status"], "HOLD")
        for change in ({"state": "PAIRED", "model_ll": None},
                       {"state": "MISSING", "missing_reason": "MODEL_MISSING"},
                       {"state": "READ_FAILED", "market_ll": None, "missing_reason": "MARKET_MISSING"},
                       {"state": "MISSING", "model_ll": None, "market_ll": None, "missing_reason": "MODEL_MISSING"}):
            bad = row(1, 1)
            bad.update(change)
            self.assertEqual(summarize([bad])["status"], "HOLD")

    def test_baseline_endpoint_and_model_version_binding_never_mix(self):
        for change in ({"baseline_id": "OTHER"}, {"baseline_version": "v002"},
                       {"probability_endpoint": "FIRST_PLACE_LOGLOSS"}):
            bad = row(1, 1)
            bad.update(change)
            self.assertEqual(summarize([bad])["status"], "HOLD")
        rows = [row(1, 1), row(2, 2)]
        rows[0].update(model_id="SYNTHETIC_MODEL", model_version="v1")
        rows[1].update(model_id="SYNTHETIC_MODEL", model_version="v2")
        self.assertEqual(summarize(rows)["status"], "HOLD")
        rows[0].pop("model_id"); rows[0].pop("model_version")
        self.assertEqual(summarize(rows)["status"], "HOLD")

    def test_unmatched_roster_extra_fields_and_invalid_dates_hold(self):
        one = row(1, 1)
        for planned in ([{"race_id": "OTHER", "target_date": one["target_date"]}],
                        [{"race_id": one["race_id"], "target_date": "2099-01-02"}]):
            self.assertEqual(summarize([one], roster=planned)["status"], "HOLD")
        for change in ({"target_date": "2099-02-30"}, {"secret": "DO_NOT_ECHO"}):
            bad = row(1, 1)
            bad.update(change)
            self.assertEqual(summarize([bad])["status"], "HOLD")

    def test_summary_only_privacy_immutability_and_no_io_or_adoption(self):
        rows = [row(1, 1, 1), row(2, 2, 3)]
        original = deepcopy(rows)
        with mock.patch("builtins.open", side_effect=AssertionError("unexpected file I/O")), \
             mock.patch("socket.socket", side_effect=AssertionError("unexpected network")):
            report = summarize(rows)
        self.assertEqual(rows, original)
        encoded = json.dumps(report, allow_nan=False)
        for forbidden in ("SYNTHETIC_SECRET", "2099-01", "SYNTHETIC_MARKET", "SYNTHETIC_v001", "model_ll", "market_ll"):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(report["performance_verdict"], "NOT_PROVIDED")
        self.assertFalse(report["f5_adopted"])
        self.assertFalse(report["f2_changed"])
        self.assertFalse(report["production_go"])


if __name__ == "__main__":
    unittest.main()
