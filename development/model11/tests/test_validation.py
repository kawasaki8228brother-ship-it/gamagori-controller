"""Synthetic-only acceptance and adversarial data-gate tests (no connections)."""

import copy
import itertools
import json
import unittest

from model11.validation import (
    FEATURES, STATES, prediction_view, validate_dataset, validate_outcome, validate_race,
)


def synthetic_race():
    before = "2099-11-09T12:58:00+09:00"
    feature_times = {name: {"acquired_at": before, "available_at": before,
                            "revision_at": before} for name in FEATURES}
    state_times = {name: {"acquired_at": before, "available_at": before,
                          "revision_at": before} for name in STATES}
    return {
        "race_id": "SYNTHETIC_GAMAGORI_20991109_R01",
        "target_date": "2099-11-09", "venue": "GAMAGORI",
        "prediction_at": "2099-11-09T12:59:00+09:00",
        "deadline": "2099-11-09T13:00:00+09:00",
        "active_boats": [1, 2, 3, 4, 5, 6],
        "boats": [{"boat": boat, "course": boat,
                   "features": {name: 0.0 for name in FEATURES},
                   "feature_times": copy.deepcopy(feature_times),
                   "state_times": copy.deepcopy(state_times),
                   "observed_at": before, "motor_updated_at": before,
                   "revision_at": before, "fl": False, "scratched": False}
                  for boat in range(1, 7)],
        "odds_snapshot": {
            "acquired_at": "2099-11-09T12:58:30+09:00",
            "available_at": "2099-11-09T12:58:30+09:00",
            "revision_at": "2099-11-09T12:58:30+09:00",
            "odds": {"-".join(map(str, item)): 100.0
                     for item in itertools.permutations(range(1, 7), 3)}},
        "synthetic": True, "data_classification": "SYNTHETIC_ONLY",
    }


def synthetic_outcome():
    return {"race_id": "SYNTHETIC_GAMAGORI_20991109_R01",
            "target_date": "2099-11-09", "result": [1, 2, 3],
            "payout_per_100": 10000.0, "refund_tickets": [],
            "final": True, "available_at": "2099-11-09T13:10:00+09:00",
            "synthetic": True}


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, race, code):
        report = validate_race(race)
        self.assertFalse(report["eligible"])
        self.assertIn(code, report["errors"])

    def test_valid_full_domain(self):
        race = synthetic_race()
        before = copy.deepcopy(race)
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["market_status"], "AVAILABLE")
        self.assertTrue(report["market_available"])
        self.assertEqual(report["legacy_profile_status"], "UNVERIFIED")
        self.assertEqual(race, before)
        self.assertEqual(len(race["odds_snapshot"]["odds"]), 120)

    def test_zero_is_real_score_but_bool_null_missing_are_not(self):
        self.assertTrue(validate_race(synthetic_race())["eligible"])
        for value in (None, True, False, "0", [], float("nan"), float("inf"), -1.01, 1.01, 10 ** 1000):
            with self.subTest(type=type(value).__name__):
                race = synthetic_race()
                race["boats"][0]["features"]["st"] = value
                self.assertFalse(validate_race(race)["eligible"])
        race = synthetic_race()
        del race["boats"][0]["features"]["st"]
        self.assert_invalid(race, "FEATURE_MISSING")

    def test_missing_exhibition_no_imputation(self):
        race = synthetic_race()
        del race["boats"][0]["features"]["exhibition"]
        self.assert_invalid(race, "EXHIBITION_MISSING")
        self.assertNotIn("exhibition", race["boats"][0]["features"])

    def test_no_unregistered_predictor_feature(self):
        race = synthetic_race()
        race["boats"][0]["features"]["unapproved"] = 0
        self.assert_invalid(race, "FEATURE_NAME_UNREGISTERED")

    def test_feature_missing_container(self):
        race = synthetic_race()
        race["boats"][0]["features"] = None
        self.assert_invalid(race, "FEATURES_MISSING")

    def test_strict_timestamp_syntax(self):
        bad = ("2099-11-09T12:59:00", "2099-11-09 12:59:00+09:00",
               "2099-11-09T12:59:00-00:00", "2099-11-09T12:59:00.1234567+09:00",
               "2099-11-09T12:59+09:00", "2099-11-09T12:59:60+09:00",
               "2099-11-09T12:59:00+24:00", "2099-11-09T12:59:00+09:99", None, 0)
        for stamp in bad:
            with self.subTest(stamp=stamp):
                race = synthetic_race()
                race["prediction_at"] = stamp
                self.assert_invalid(race, "PREDICTION_TIME_INVALID")

    def test_timezone_and_microsecond_valid(self):
        race = synthetic_race()
        race["prediction_at"] = "2099-11-09T03:59:00.123456Z"
        self.assertTrue(validate_race(race)["eligible"])

    def test_deadline_is_strict(self):
        for stamp in ("2099-11-09T13:00:00+09:00", "2099-11-09T13:00:01+09:00"):
            race = synthetic_race()
            race["prediction_at"] = stamp
            self.assert_invalid(race, "PREDICTION_NOT_BEFORE_DEADLINE")

    def test_deadline_date_compares_jst_not_utc(self):
        race = synthetic_race()
        race["target_date"] = "2099-11-10"
        self.assert_invalid(race, "RACE_DATE_MISMATCH")

    def test_identity_malformed_and_mismatched(self):
        for field, value, code in (("race_id", "", "RACE_ID_INVALID"),
                                   ("race_id", "x\nPRIVATE", "RACE_ID_INVALID"),
                                   ("target_date", "2099-02-30", "TARGET_DATE_INVALID"),
                                   ("venue", "OTHER", "VENUE_INVALID")):
            race = synthetic_race()
            race[field] = value
            self.assert_invalid(race, code)
        for field in ("race_id", "target_date", "venue"):
            race = synthetic_race()
            race["boats"][0][field] = "MISMATCH"
            self.assert_invalid(race, "BOAT_IDENTITY_MISMATCH")

    def test_all_aggregate_future_times_rejected(self):
        for field in ("observed_at", "motor_updated_at", "revision_at"):
            race = synthetic_race()
            race["boats"][0][field] = "2099-11-09T12:59:01+09:00"
            self.assert_invalid(race, "FEATURE_FUTURE")

    def test_aggregate_time_consistency(self):
        race = synthetic_race()
        race["boats"][0]["motor_updated_at"] = "2099-11-09T12:58:01+09:00"
        self.assert_invalid(race, "MOTOR_UPDATE_AFTER_OBSERVATION")
        race = synthetic_race()
        race["boats"][0]["revision_at"] = "2099-11-09T12:57:59+09:00"
        self.assert_invalid(race, "REVISION_BEFORE_OBSERVATION")

    def test_feature_provenance_required_for_every_feature(self):
        race = synthetic_race()
        del race["boats"][0]["feature_times"]
        self.assert_invalid(race, "FEATURE_PROVENANCE_MISSING")
        for name in FEATURES:
            race = synthetic_race()
            del race["boats"][0]["feature_times"][name]
            self.assert_invalid(race, "FEATURE_PROVENANCE_MISSING")

    def test_feature_availability_acquisition_revision_future_and_missing(self):
        for name, field in itertools.product(FEATURES, ("acquired_at", "available_at", "revision_at")):
            with self.subTest(name=name, field=field):
                race = synthetic_race()
                race["boats"][0]["feature_times"][name][field] = "2099-11-09T12:59:01+09:00"
                self.assert_invalid(race, "FEATURE_PROVENANCE_FUTURE")
                del race["boats"][0]["feature_times"][name][field]
                self.assert_invalid(race, "FEATURE_PROVENANCE_TIME_INVALID")

    def test_availability_cannot_precede_acquisition(self):
        race = synthetic_race()
        race["boats"][0]["feature_times"]["motor"]["available_at"] = "2099-11-09T12:57:59+09:00"
        self.assert_invalid(race, "FEATURE_AVAILABILITY_BEFORE_ACQUISITION")

    def test_state_provenance_required_without_aggregate_inference(self):
        race = synthetic_race()
        del race["boats"][0]["state_times"]
        self.assert_invalid(race, "STATE_PROVENANCE_MISSING")
        for name in STATES:
            race = synthetic_race()
            del race["boats"][0]["state_times"][name]
            self.assert_invalid(race, "STATE_PROVENANCE_MISSING")

    def test_every_state_time_future_or_missing_is_invalid(self):
        for name, field in itertools.product(STATES, ("acquired_at", "available_at", "revision_at")):
            with self.subTest(name=name, field=field):
                race = synthetic_race()
                race["boats"][0]["state_times"][name][field] = "2099-11-09T12:59:01+09:00"
                self.assert_invalid(race, "STATE_PROVENANCE_FUTURE")
                del race["boats"][0]["state_times"][name][field]
                self.assert_invalid(race, "STATE_PROVENANCE_TIME_INVALID")

    def test_state_availability_must_follow_acquisition(self):
        for name in STATES:
            race = synthetic_race()
            race["boats"][0]["state_times"][name]["available_at"] = "2099-11-09T12:57:59+09:00"
            self.assert_invalid(race, "STATE_AVAILABILITY_BEFORE_ACQUISITION")

    def test_state_times_reject_unknown_timezone_and_precision(self):
        for stamp in ("2099-11-09T12:58:00", "2099-11-09T12:58:00-00:00",
                      "2099-11-09T12:58:00.1234567+09:00"):
            race = synthetic_race()
            race["boats"][0]["state_times"]["course"]["available_at"] = stamp
            self.assert_invalid(race, "STATE_PROVENANCE_TIME_INVALID")

    def test_inactive_boat_scratch_state_still_needs_prior_provenance(self):
        race = synthetic_race()
        race["active_boats"] = [1, 2, 3, 4, 5]
        race["boats"][5]["scratched"] = True
        del race["boats"][5]["state_times"]["scratched"]
        self.assert_invalid(race, "STATE_PROVENANCE_MISSING")

    def test_course_scratch_fl_update_future(self):
        for field in ("course_updated_at", "scratch_updated_at", "fl_updated_at"):
            race = synthetic_race()
            race["boats"][0][field] = "2099-11-09T12:59:01+09:00"
            self.assert_invalid(race, "STATUS_FUTURE")

    def test_active_boats_invalid(self):
        for value in ([1, 2], [1, 2, 3, 3], [1, 2, True], [1, 2, 7], [1, 2, []], None):
            race = synthetic_race()
            race["active_boats"] = value
            self.assert_invalid(race, "ACTIVE_BOATS_INVALID")

    def test_missing_duplicate_boat_and_course(self):
        race = synthetic_race()
        race["boats"] = race["boats"][:-1]
        self.assert_invalid(race, "ACTIVE_BOAT_MISSING")
        race = synthetic_race()
        race["boats"][1]["boat"] = 1
        self.assert_invalid(race, "BOAT_DUPLICATE")
        race = synthetic_race()
        race["boats"][1]["course"] = 1
        self.assert_invalid(race, "COURSE_DUPLICATE")

    def test_scratch_and_fl_distinguish_unknown_from_false(self):
        for field, code in (("scratched", "SCRATCH_STATUS_UNKNOWN"), ("fl", "FL_STATUS_UNKNOWN")):
            for value in (None, 0, 1, "false"):
                race = synthetic_race()
                race["boats"][0][field] = value
                self.assert_invalid(race, code)
        race = synthetic_race()
        race["boats"][0]["scratched"] = True
        self.assert_invalid(race, "SCRATCH_ACTIVE_MISMATCH")
        race = synthetic_race()
        race["boats"][0]["fl"] = True
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertIn("FL_PRESENT_RESEARCH_INPUT", report["warnings"])

    def test_reduced_field_domain_and_inactive_scratched_record(self):
        race = synthetic_race()
        race["active_boats"] = [1, 2, 3, 4, 5]
        race["boats"][5]["scratched"] = True
        race["odds_snapshot"]["odds"] = {key: value for key, value in race["odds_snapshot"]["odds"].items()
                                         if "6" not in key}
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertTrue(report["market_available"])
        self.assertEqual(len(race["odds_snapshot"]["odds"]), 60)
        self.assertIn("REDUCED_FIELD_RESEARCH_ONLY", report["warnings"])

    def test_missing_stale_future_odds_preserve_model_eligibility(self):
        for kind in ("MISSING", "STALE", "FUTURE"):
            race = synthetic_race()
            if kind == "MISSING":
                race["odds_snapshot"] = None
            elif kind == "STALE":
                race["odds_snapshot"]["acquired_at"] = "2099-11-09T12:56:59+09:00"
            else:
                race["odds_snapshot"]["revision_at"] = "2099-11-09T12:59:01+09:00"
            report = validate_race(race)
            self.assertTrue(report["eligible"])
            self.assertFalse(report["market_available"])
            self.assertEqual(report["market_status"], kind)

    def test_odds_age_boundary(self):
        race = synthetic_race()
        race["odds_snapshot"]["acquired_at"] = "2099-11-09T12:57:00+09:00"
        self.assertTrue(validate_race(race)["market_available"])
        self.assertEqual(validate_race(race, 119)["market_status"], "STALE")

    def test_bad_market_metadata_is_not_fabricated(self):
        changes = (("race_id", "WRONG", "ODDS_IDENTITY_MISMATCH"),
                   ("acquired_at", "no-time", "ODDS_TIME_INVALID"),
                   ("revision_at", "2099-11-09T12:58:00+09:00", "ODDS_REVISION_BEFORE_ACQUISITION"),
                   ("odds", {"1-2-3": 100.0}, "ODDS_DOMAIN_MISMATCH"))
        for field, value, code in changes:
            race = synthetic_race()
            race["odds_snapshot"][field] = value
            report = validate_race(race)
            self.assertTrue(report["eligible"])
            self.assertFalse(report["market_available"])
            self.assertIn(code, report["warnings"])

    def test_market_availability_required_and_not_future(self):
        for value in (None, "2099-11-09T12:58:30", "2099-11-09T12:58:30-00:00"):
            race = synthetic_race()
            race["odds_snapshot"]["available_at"] = value
            report = validate_race(race)
            self.assertTrue(report["eligible"])
            self.assertFalse(report["market_available"])
            self.assertIn("ODDS_TIME_INVALID", report["warnings"])
        race = synthetic_race()
        del race["odds_snapshot"]["available_at"]
        self.assertFalse(validate_race(race)["market_available"])
        race = synthetic_race()
        race["odds_snapshot"]["available_at"] = race["deadline"]
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["market_status"], "FUTURE")
        self.assertIn("ODDS_FUTURE", report["warnings"])

    def test_market_availability_cannot_precede_acquisition(self):
        race = synthetic_race()
        race["odds_snapshot"]["available_at"] = "2099-11-09T12:58:29+09:00"
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertFalse(report["market_available"])
        self.assertIn("ODDS_AVAILABILITY_BEFORE_ACQUISITION", report["warnings"])

    def test_odds_values_must_be_positive_and_not_bool(self):
        for value in (None, True, 0, -1, "2"):
            race = synthetic_race()
            race["odds_snapshot"]["odds"]["1-2-3"] = value
            report = validate_race(race)
            self.assertTrue(report["eligible"])
            self.assertFalse(report["market_available"])
            self.assertIn("ODDS_VALUE_INVALID", report["warnings"])

    def test_bad_max_age_is_caller_error(self):
        for value in (True, None, -1, float("nan"), "120"):
            with self.assertRaisesRegex(ValueError, "^ODDS_MAX_AGE_INVALID$"):
                validate_race(synthetic_race(), value)

    def test_manual_box_optional_and_time_gated(self):
        race = synthetic_race()
        race["human_box_input"] = {"core": [1, 2], "insertion": 3,
                                   "observed_at": "2099-11-09T12:58:00+09:00",
                                   "acquired_at": "2099-11-09T12:58:00+09:00",
                                   "available_at": "2099-11-09T12:58:00+09:00",
                                   "revision_at": "2099-11-09T12:58:00+09:00"}
        self.assertEqual(validate_race(race)["human_box_status"], "AVAILABLE")
        race["human_box_input"]["observed_at"] = "2099-11-09T13:01:00+09:00"
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["human_box_status"], "INVALID")
        self.assertIn("HUMAN_BOX_FUTURE", report["warnings"])

    def test_manual_box_duplicate_invalid(self):
        race = synthetic_race()
        race["human_box_input"] = {"core": [1, 2], "insertion": 1,
                                   "observed_at": "2099-11-09T12:58:00+09:00",
                                   "acquired_at": "2099-11-09T12:58:00+09:00",
                                   "available_at": "2099-11-09T12:58:00+09:00",
                                   "revision_at": "2099-11-09T12:58:00+09:00"}
        self.assertIn("HUMAN_BOX_COMPOSITION_INVALID", validate_race(race)["warnings"])

    def test_manual_all_provenance_times_required_and_not_future(self):
        for field in ("acquired_at", "available_at", "revision_at"):
            race = synthetic_race()
            race["human_box_input"] = {"core": [1, 2], "insertion": 3,
                                       **{key: "2099-11-09T12:58:00+09:00" for key in
                                          ("observed_at", "acquired_at", "available_at", "revision_at")}}
            manual = race["human_box_input"]
            manual[field] = race["deadline"]
            report = validate_race(race)
            self.assertTrue(report["eligible"])
            self.assertEqual(report["human_box_status"], "INVALID")
            self.assertIn("HUMAN_BOX_FUTURE", report["warnings"])
            del manual[field]
            self.assertIn("HUMAN_BOX_TIME_INVALID", validate_race(race)["warnings"])

    def test_manual_availability_cannot_precede_acquisition(self):
        race = synthetic_race()
        race["human_box_input"] = {"core": [1, 2], "insertion": 3,
                                   **{key: "2099-11-09T12:58:00+09:00" for key in
                                      ("observed_at", "acquired_at", "available_at", "revision_at")}}
        race["human_box_input"]["available_at"] = "2099-11-09T12:57:59+09:00"
        report = validate_race(race)
        self.assertTrue(report["eligible"])
        self.assertEqual(report["human_box_status"], "INVALID")
        self.assertIn("HUMAN_BOX_AVAILABILITY_BEFORE_ACQUISITION", report["warnings"])

    def test_recursive_labels_rejected_even_in_odds_or_metadata(self):
        for field in ("result", "payout_per_100", "outcome", "refund_tickets", "labels",
                      "raceResult", "final"):
            race = synthetic_race()
            race["metadata"] = {"nested": [{field: "PRIVATE_VALUE_NOT_PRINTED"}]}
            self.assert_invalid(race, "FORBIDDEN_PREDICTOR_FIELD")
            with self.assertRaisesRegex(ValueError, "^FORBIDDEN_PREDICTOR_FIELD$"):
                prediction_view(race)

    def test_prediction_view_is_separate_and_never_drops_labels(self):
        race = synthetic_race()
        view = prediction_view(race)
        view["boats"][0]["features"]["st"] = 0.5
        self.assertEqual(race["boats"][0]["features"]["st"], 0)
        with self.assertRaisesRegex(ValueError, "^FORBIDDEN_PREDICTOR_FIELD$"):
            prediction_view({"race": race, "actual": synthetic_outcome()})

    def test_json_shape_encoding_cycles_and_depth(self):
        for field, value, code in (("bad", {1: "x"}, "INPUT_KEY_TYPE"),
                                   ("bad", object(), "INPUT_VALUE_TYPE"),
                                   ("bad", "\ud800", "INPUT_TEXT_ENCODING"),
                                   ("bad", float("nan"), "INPUT_NONFINITE")):
            race = synthetic_race()
            race[field] = value
            self.assert_invalid(race, code)
        race = synthetic_race()
        race["bad"] = race
        self.assert_invalid(race, "INPUT_CYCLE")
        race = synthetic_race()
        chain = race
        for _ in range(35):
            chain["nested"] = {}
            chain = chain["nested"]
        self.assert_invalid(race, "INPUT_LIMIT_EXCEEDED")

    def test_errors_do_not_contain_submitted_private_values(self):
        race = synthetic_race()
        race["venue"] = "PRIVATE_SECRET_VALUE"
        race["boats"][0]["observed_at"] = "/private/token"
        serialized = json.dumps(validate_race(race))
        self.assertNotIn("PRIVATE_SECRET_VALUE", serialized)
        self.assertNotIn("/private/token", serialized)

    def test_outcome_is_separate_final_label(self):
        self.assertTrue(validate_outcome(synthetic_outcome())["eligible"])
        self.assertFalse(validate_race(synthetic_outcome())["eligible"])
        outcome = synthetic_outcome()
        outcome["final"] = False
        self.assertIn("OUTCOME_NOT_FINAL", validate_outcome(outcome)["errors"])

    def test_outcome_status_availability_payout_and_refunds(self):
        for field, value, code in (("final", 1, "OUTCOME_FINAL_STATUS_UNKNOWN"),
                                   ("available_at", "2099-11-09T13:10:00", "OUTCOME_AVAILABILITY_INVALID"),
                                   ("payout_per_100", None, "OUTCOME_PAYOUT_INVALID"),
                                   ("payout_per_100", True, "OUTCOME_PAYOUT_INVALID"),
                                   ("payout_per_100", -1, "OUTCOME_PAYOUT_INVALID"),
                                   ("refund_tickets", None, "OUTCOME_REFUNDS_INVALID"),
                                   ("refund_tickets", ["1-1-2"], "OUTCOME_REFUNDS_INVALID"),
                                   ("refund_tickets", ["1-2-3", "1-2-3"], "OUTCOME_REFUNDS_INVALID")):
            outcome = synthetic_outcome()
            outcome[field] = value
            self.assertIn(code, validate_outcome(outcome)["errors"])
        for value in ([1, 1, 2], [1, 2, True], [1, 2], None, [1, 2, []]):
            outcome = synthetic_outcome()
            outcome["result"] = value
            self.assertIn("OUTCOME_RESULT_INVALID", validate_outcome(outcome)["errors"])

    def test_dataset_duplicate_races_and_labels(self):
        race, outcome = synthetic_race(), synthetic_outcome()
        self.assertTrue(validate_dataset([race], [outcome])["eligible"])
        self.assertIn("DUPLICATE_RACE_ID", validate_dataset([race, copy.deepcopy(race)], [outcome])["errors"])
        self.assertIn("DUPLICATE_OUTCOME_ID", validate_dataset([race], [outcome, copy.deepcopy(outcome)])["errors"])

    def test_dataset_join_identity_and_outcome_availability(self):
        for field, value, code in (("target_date", "2099-11-10", "OUTCOME_DATE_MISMATCH"),
                                   ("venue", "OTHER", "OUTCOME_VENUE_MISMATCH"),
                                   ("available_at", "2099-11-09T12:59:59+09:00", "OUTCOME_AVAILABLE_BEFORE_DEADLINE"),
                                   ("race_id", "UNKNOWN", "OUTCOME_WITHOUT_RACE")):
            outcome = synthetic_outcome()
            outcome[field] = value
            self.assertIn(code, validate_dataset([synthetic_race()], [outcome])["errors"])

    def test_missing_label_remains_unlabeled_not_invented(self):
        report = validate_dataset([synthetic_race()], [])
        self.assertTrue(report["eligible"])
        self.assertIn("OUTCOME_MISSING", report["warnings"])
        self.assertEqual(report["outcome_count"], 0)

    def test_non_dict_shapes_report_instead_of_throwing(self):
        for value in (None, "x", [], 0, True):
            self.assertFalse(validate_race(value)["eligible"])
            self.assertFalse(validate_outcome(value)["eligible"])
        self.assertFalse(validate_dataset(None, [])["eligible"])


if __name__ == "__main__":
    unittest.main()
