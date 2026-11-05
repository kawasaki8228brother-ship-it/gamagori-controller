"""F3 synthetic course-definition/time/prior binding regressions."""
from copy import deepcopy
import unittest

from model11.models import make_model
from model11.revision_v003.course import (
    COURSE_POLICIES, CourseBoundModel, apply_course_fixture, canonical_hash,
    from_dict, validate_course,
)
from model11.synthetic import make_dataset


class CourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = make_dataset(days=6, races_per_day=1, seed=803)
        cls.races = [apply_course_fixture(race) for race in cls.original["races"]]

    def policy(self, ident="EXHIBITION_ONLY_V001"):
        return deepcopy(COURSE_POLICIES[ident])

    def fit(self, ident="EXHIBITION_ONLY_V001"):
        races = [apply_course_fixture(race, ident) for race in self.original["races"]]
        model = CourseBoundModel("hierarchical", {"epochs": 2, "alpha": 1.0}, self.policy(ident))
        return model.fit(races[:3], self.original["outcomes"][:3]), races

    def test_normal_prelock_exhibition_and_frame_distinct(self):
        for ident, definition in (("FRAME_ONLY_V001", "FRAME_NUMBER"),
                                   ("EXHIBITION_ONLY_V001", "EXHIBITION_ENTRY")):
            race = apply_course_fixture(self.original["races"][0], ident)
            report = validate_course(race, self.policy(ident))
            self.assertTrue(report["eligible"], report)
            self.assertEqual(report["definition"], definition)
            self.assertEqual(report["policy_sha256"], canonical_hash(self.policy(ident)))
            self.assertEqual(report["external_authenticity"], "UNVERIFIED")
            self.assertFalse(report["production_go"])
        race = self.races[0]
        self.assertNotEqual(race["course_inputs"]["frame"]["courses"], race["course_inputs"]["exhibition"]["courses"])

    def test_fixture_does_not_mutate_input_or_labels(self):
        before = deepcopy(self.original)
        altered = apply_course_fixture(self.original["races"][0])
        altered["boats"][0]["features"]["st"] = 0.999
        self.assertEqual(before, self.original)
        self.assertIsNone(altered["human_box_input"])

    def test_non_synthetic_fixture_prohibited(self):
        for key, value in (("synthetic", False), ("data_classification", "REAL"), ("target_date", "2026-11-05")):
            race = deepcopy(self.original["races"][0])
            race[key] = value
            with self.assertRaisesRegex(ValueError, "COURSE_SYNTHETIC_FIXTURE_ONLY"):
                apply_course_fixture(race)

    def test_course_numeric_mismatch_hold(self):
        race = deepcopy(self.races[0])
        race["boats"][0]["course"], race["boats"][1]["course"] = race["boats"][1]["course"], race["boats"][0]["course"]
        report = validate_course(race, self.policy())
        self.assertFalse(report["eligible"])
        self.assertIn("COURSE_NUMERIC_OBSERVATION_MISMATCH", report["errors"])

    def test_state_time_exact_binding(self):
        race = deepcopy(self.races[0])
        race["boats"][0]["state_times"]["course"]["available_at"] = race["prediction_at"]
        report = validate_course(race, self.policy())
        self.assertIn("COURSE_STATE_TIME_BINDING_MISMATCH", report["errors"])
        self.assertFalse(report["eligible"])

    def test_future_any_time_and_late_revision_hold(self):
        for source in ("frame", "exhibition"):
            for field in ("acquired_at", "available_at", "revision_at"):
                race = deepcopy(self.races[0])
                race["course_inputs"][source][field] = race["deadline"]
                report = validate_course(race, self.policy())
                self.assertIn("COURSE_OBSERVATION_FUTURE_OR_LATE_REVISION", report["errors"])
                self.assertFalse(report["eligible"])

    def test_invalid_naive_unknown_offset_and_precision_hold(self):
        for value in ("2099-01-01T12:00:00", "2099-01-01T12:00:00-00:00",
                      "2099-01-01T12:00:00.1234567+09:00"):
            race = deepcopy(self.races[0])
            race["course_inputs"]["exhibition"]["available_at"] = value
            self.assertIn("COURSE_OBSERVATION_TIME_INVALID", validate_course(race, self.policy())["errors"])

    def test_invalid_offset_in_unused_and_selected_observations_hold(self):
        for source in ("frame", "exhibition"):
            for suffix in ("+09:99", "+24:00", "-03:60"):
                race = deepcopy(self.races[0])
                observation = race["course_inputs"][source]
                observation["acquired_at"] = observation["acquired_at"][:-6] + suffix
                report = validate_course(race, self.policy())
                self.assertFalse(report["eligible"])
                self.assertIn("COURSE_OBSERVATION_TIME_INVALID", report["errors"])

    def test_actual_post_result_final_entry_prohibited(self):
        for field, value in (("definition", "ACTUAL_ENTRY_AFTER_RESULT"),
                             ("definition", "FINAL_ENTRY"), ("source_id", "POST_RESULT_ACTUAL_ENTRY"),
                             ("source_id", "PRIVATE_SOURCE_URL_NOT_OUTPUT")):
            race = deepcopy(self.races[0])
            race["course_inputs"]["exhibition"][field] = value
            report = validate_course(race, self.policy())
            self.assertFalse(report["eligible"])
            self.assertIsNone(report["selected_observation"])
            self.assertNotIn("PRIVATE_SOURCE_URL_NOT_OUTPUT", str(report))

    def test_unknown_definition_and_wrong_field_definition_hold(self):
        for definition in ("UNKNOWN", "FRAME_NUMBER", None, {"secret": "PRIVATE_VALUE"}):
            race = deepcopy(self.races[0])
            race["course_inputs"]["exhibition"]["definition"] = definition
            report = validate_course(race, self.policy())
            self.assertFalse(report["eligible"])
            self.assertNotIn("PRIVATE_VALUE", str(report))

    def test_hash_missing_or_malformed_hold(self):
        for value in (None, "a" * 63, "A" * 64, "not-a-hash"):
            race = deepcopy(self.races[0])
            race["course_inputs"]["exhibition"]["evidence_sha256"] = value
            self.assertIn("COURSE_EVIDENCE_HASH_INVALID", validate_course(race, self.policy())["errors"])

    def test_domain_duplicate_bool_missing_and_extra_hold(self):
        for change in ("duplicate", "bool", "missing", "extra"):
            race = deepcopy(self.races[0])
            courses = race["course_inputs"]["exhibition"]["courses"]
            if change == "duplicate":
                courses["1"] = courses["2"]
            elif change == "bool":
                courses["1"] = True
            elif change == "missing":
                del courses["1"]
            else:
                courses["7"] = 7
            self.assertIn("COURSE_DOMAIN_OR_PERMUTATION_INVALID", validate_course(race, self.policy())["errors"])

    def test_frame_numbers_cannot_be_exhibition_values(self):
        race = deepcopy(self.races[0])
        race["course_inputs"]["frame"]["courses"] = deepcopy(race["course_inputs"]["exhibition"]["courses"])
        self.assertIn("FRAME_NUMBER_MUST_EQUAL_BOAT_ID", validate_course(race, self.policy())["errors"])

    def test_observation_exact_shape_and_unknown_source_hold(self):
        race = deepcopy(self.races[0])
        race["course_inputs"]["exhibition"]["actual_result"] = "forbidden"
        self.assertFalse(validate_course(race, self.policy())["eligible"])
        race = deepcopy(self.races[0])
        del race["course_inputs"]["exhibition"]["revision_at"]
        self.assertIn("COURSE_OBSERVATION_FIELDS", validate_course(race, self.policy())["errors"])

    def test_exhibition_missing_never_falls_back_in_exhibition_only(self):
        race = apply_course_fixture(self.original["races"][0], exhibition_present=False)
        self.assertIn("COURSE_REQUIRED_OBSERVATION_MISSING", validate_course(race, self.policy())["errors"])

    def test_predeclared_mix_only_falls_back_when_null(self):
        ident = "EXHIBITION_ELSE_FRAME_V001"
        present = apply_course_fixture(self.original["races"][0], ident)
        missing = apply_course_fixture(self.original["races"][1], ident, False)
        self.assertEqual(validate_course(present, self.policy(ident))["definition"], "EXHIBITION_ENTRY")
        self.assertTrue(validate_course(missing, self.policy(ident))["eligible"])
        self.assertEqual(validate_course(missing, self.policy(ident))["definition"], "FRAME_NUMBER")
        present["course_inputs"]["exhibition"]["available_at"] = present["deadline"]
        self.assertFalse(validate_course(present, self.policy(ident))["eligible"])
        present["course_inputs"]["exhibition"] = {}
        self.assertFalse(validate_course(present, self.policy(ident))["eligible"])

    def test_missing_or_changed_race_policy_binding_hold(self):
        for key in ("course_policy_id", "course_policy_sha256"):
            race = deepcopy(self.races[0])
            del race[key]
            self.assertIn("COURSE_RACE_POLICY_BINDING_MISMATCH", validate_course(race, self.policy())["errors"])
        self.assertFalse(validate_course(self.races[0], self.policy("FRAME_ONLY_V001"))["eligible"])

    def test_unknown_or_adaptively_changed_policy_hold(self):
        policy = self.policy()
        policy["selection"] = "EXHIBITION_ELSE_FRAME"
        self.assertIn("COURSE_POLICY_UNKNOWN_OR_CHANGED", validate_course(self.races[0], policy)["errors"])
        with self.assertRaisesRegex(ValueError, "COURSE_POLICY_UNKNOWN_OR_CHANGED"):
            CourseBoundModel("hierarchical", course_policy=policy)

    def test_model_fit_prior_uses_selected_prelock_course(self):
        model, races = self.fit()
        report = model.to_dict()
        expected = [[0] * 6 for _ in range(3)]
        for race, outcome in zip(races[:3], self.original["outcomes"][:3]):
            by_boat = {boat["boat"]: boat["course"] for boat in race["boats"]}
            for head, boat in enumerate(outcome["result"]):
                expected[head][by_boat[boat] - 1] += 1
        self.assertEqual(report["base_model"]["course_counts"], expected)
        self.assertEqual(report["training_course_definitions"], ["EXHIBITION_ENTRY"])
        self.assertEqual(model.training_count, 3)
        self.assertEqual(model.training_max_available_at, report["base_model"]["training_max_available_at"])
        self.assertTrue(all(sum(row) == 3 for row in expected))

    def test_bound_train_and_prediction_policies_must_match(self):
        model, races = self.fit()
        frame_race = apply_course_fixture(self.original["races"][4], "FRAME_ONLY_V001")
        for call in (model.distributions, model.explain, model.conditionals):
            with self.assertRaisesRegex(ValueError, "COURSE_INPUT_HOLD"):
                call(frame_race)
        with self.assertRaisesRegex(ValueError, "COURSE_INPUT_HOLD"):
            CourseBoundModel("hierarchical").fit([races[0], frame_race], [self.original["outcomes"][0], self.original["outcomes"][4]])

    def test_declared_mix_can_train_both_definitions(self):
        ident = "EXHIBITION_ELSE_FRAME_V001"
        races = [apply_course_fixture(race, ident, index % 2 == 0) for index, race in enumerate(self.original["races"])]
        model = CourseBoundModel("hierarchical", {"epochs": 2}, self.policy(ident)).fit(races[:4], self.original["outcomes"][:4])
        self.assertEqual(model.to_dict()["training_course_definitions"], ["EXHIBITION_ENTRY", "FRAME_NUMBER"])
        self.assertEqual(len(model.distributions(races[4])["P_model"]), 120)

    def test_serialization_roundtrip_binds_policy_and_actual_weights(self):
        model, races = self.fit()
        encoded = model.to_dict()
        restored = CourseBoundModel.from_dict(encoded)
        self.assertEqual(encoded, restored.to_dict())
        self.assertEqual(model.distributions(races[4]), restored.distributions(races[4]))
        self.assertEqual(from_dict(encoded).to_dict(), encoded)
        self.assertEqual(restored.course_policy_sha256, canonical_hash(self.policy()))

    def test_serialized_policy_and_training_binding_tampering_rejected(self):
        model, _ = self.fit()
        payload = model.to_dict()
        payload["course_policy"] = self.policy("FRAME_ONLY_V001")
        with self.assertRaisesRegex(ValueError, "COURSE_MODEL_SERIALIZED_HASH_MISMATCH"):
            CourseBoundModel.from_dict(payload)
        payload["self_sha256"] = canonical_hash({k: v for k, v in payload.items() if k != "self_sha256"})
        with self.assertRaisesRegex(ValueError, "COURSE_MODEL_POLICY_MISMATCH"):
            CourseBoundModel.from_dict(payload)
        payload["course_policy_sha256"] = canonical_hash(self.policy("FRAME_ONLY_V001"))
        payload["training_course_definitions"] = ["FRAME_NUMBER"]
        payload["self_sha256"] = canonical_hash({k: v for k, v in payload.items() if k != "self_sha256"})
        with self.assertRaisesRegex(ValueError, "COURSE_SERIALIZED_TRAINING_BINDING_INVALID"):
            CourseBoundModel.from_dict(payload)

    def test_returned_policy_detached_and_live_mutation_detected(self):
        model, races = self.fit()
        detached = model.course_policy
        detached["selection"] = "FRAME_ONLY"
        self.assertEqual(model.course_policy["selection"], "EXHIBITION_ONLY")
        model._course_policy["selection"] = "FRAME_ONLY"
        with self.assertRaisesRegex(ValueError, "COURSE_BOUND_POLICY_CHANGED"):
            model.distributions(races[4])

    def test_unfitted_model_roundtrip_no_fabricated_train_binding(self):
        model = CourseBoundModel("contextual", {"epochs": 2})
        self.assertEqual(model.to_dict(), from_dict(model.to_dict()).to_dict())


if __name__ == "__main__":
    unittest.main()
