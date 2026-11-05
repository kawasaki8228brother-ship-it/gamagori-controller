"""Offline preparation tests; all examples use invented 2099 races."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import unittest

from model11.engine import canonical_hash, predict_race
from model11.models import make_model
from model11.preparation.shadow import build_shadow_output, serialize_shadow, verify_shadow
from model11.synthetic import make_dataset


class ShadowPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_dataset(days=8, races_per_day=1)
        cls.model = make_model("contextual", {"epochs": 2}).fit(cls.data["races"][:6], cls.data["outcomes"][:6])
        cls.race = cls.data["races"][6]
        cls.prediction = predict_race(cls.race, cls.model)
        cls.generated = (datetime.fromisoformat(cls.race["prediction_at"]) + timedelta(seconds=1)).isoformat()

    def reproduction(self, prediction=None):
        prediction = prediction or self.prediction
        return {"code_commit": "71ddd13dd5869aaf892a504ea0553c60e8b8abe2",
                "input_artifact_sha256": prediction["input_sha256"],
                "model_sha256": prediction["model_sha256"],
                "config_sha256": canonical_hash(prediction["config"])}

    def record(self):
        return build_shadow_output(self.prediction, self.race, self.generated, self.reproduction())

    def rehash(self, prediction):
        prediction["prediction_sha256"] = canonical_hash({k: v for k, v in prediction.items() if k != "prediction_sha256"})
        return prediction

    def test_canonical_raw_roundtrip_receipt_is_external(self):
        record = self.record()
        payload, receipt = serialize_shadow(record)
        self.assertEqual(receipt["bytes"], len(payload))
        self.assertEqual(receipt["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(json.loads(payload.decode("ascii")), record)
        self.assertNotIn(b'"receipt"', payload)
        self.assertFalse(payload.endswith(b"\n"))
        verified = verify_shadow(payload, receipt)
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["status"], "SELF_CONSISTENT_ONLY")
        self.assertEqual(verified["authenticity"], "UNVERIFIED")
        self.assertFalse(verified["production_go"])
        self.assertFalse(verified["shadow_execution_go"])

    def test_full_four_stages_and_separate_research_selections_preserved(self):
        record = self.record()
        self.assertEqual(record["source"], "MODEL11_THIRD_RESEARCH")
        self.assertNotEqual(record["wrapper_research_version"], record["engine_version"])
        self.assertEqual(record["engine_version"], "0.1.0-research")
        for stage in ("P_raw", "P_model", "P_market", "P_shrunk"):
            self.assertEqual(len(record["forecast"]["distributions"][stage]), 120)
        self.assertEqual(record["forecast"], self.prediction)
        self.assertEqual(len(record["forecast"]["selection"]["tickets"]), 5)
        for method in ("human_research", "mechanical_research", "box_v11_research"):
            self.assertEqual(len(record["forecast"]["boxes"][method]["tickets"]), 6)
        self.assertIn(record["forecast"]["boxes"]["composition_difference"], ("YES", "NO"))
        self.assertIn(record["forecast"]["bet_decision"], ("BET", "SKIP"))
        self.assertTrue(record["target_date"].startswith("2099-"))

    def test_pure_function_inputs_immutable_and_return_is_detached(self):
        before_prediction, before_race = deepcopy(self.prediction), deepcopy(self.race)
        reproduction = self.reproduction()
        before_reproduction = deepcopy(reproduction)
        record = build_shadow_output(self.prediction, self.race, self.generated, reproduction)
        record["forecast"]["config"]["new_only_in_return"] = 1
        record["input_time_evidence"]["feature_times"]["1"]["st"]["available_at"] = "changed"
        self.assertEqual(self.prediction, before_prediction)
        self.assertEqual(self.race, before_race)
        self.assertEqual(reproduction, before_reproduction)

    def test_generation_clock_is_aware_and_strictly_predeadline(self):
        prediction_time = datetime.fromisoformat(self.race["prediction_at"])
        for bad in ((prediction_time - timedelta(seconds=1)).isoformat(), self.race["deadline"],
                    "2099-01-07T12:55:01", "2099-01-07T12:55:01-00:00", "not-a-time"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "HOLD:"):
                build_shadow_output(self.prediction, self.race, bad, self.reproduction())
        build_shadow_output(self.prediction, self.race, self.race["prediction_at"], self.reproduction())

    def test_forecast_tampering_and_outcome_records_are_rejected(self):
        for mutate in (lambda p: p.update(actual=self.data["outcomes"][6]),
                       lambda p: p.update(first_course=2),
                       lambda p: p["selection"].update(coverage=0.99),
                       lambda p: p["model_spec"]["config"].update(alpha=0.72)):
            prediction = deepcopy(self.prediction)
            mutate(prediction)
            with self.assertRaisesRegex(ValueError, "HOLD:"):
                build_shadow_output(prediction, self.race, self.generated, self.reproduction())

    def test_hash_reference_and_artifact_convention_are_verified(self):
        for field in ("input_artifact_sha256", "model_sha256", "config_sha256"):
            reproduction = self.reproduction()
            reproduction[field] = "0" * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "HOLD:REPRODUCTION"):
                build_shadow_output(self.prediction, self.race, self.generated, reproduction)
        reproduction = self.reproduction()
        reproduction["code_commit"] = "unknown"
        with self.assertRaisesRegex(ValueError, "HOLD:CODE_COMMIT_UNKNOWN"):
            build_shadow_output(self.prediction, self.race, self.generated, reproduction)
        changed_race = deepcopy(self.race)
        changed_race["boats"][0]["features"]["turn"] *= -1
        with self.assertRaisesRegex(ValueError, "HOLD:INPUT_SHA256_MISMATCH"):
            build_shadow_output(self.prediction, changed_race, self.generated, self.reproduction())

    def test_market_unavailable_holds_instead_of_filling_four_stages(self):
        race = deepcopy(self.race)
        race["odds_snapshot"] = None
        prediction = predict_race(race, self.model)
        self.assertEqual(prediction["bet_decision"], "SKIP")
        with self.assertRaisesRegex(ValueError, "HOLD:FOUR_STAGES_UNAVAILABLE"):
            build_shadow_output(prediction, race, self.generated, self.reproduction(prediction))

    def test_scratched_boat_reduced_domain_holds_instead_of_claiming_120(self):
        race = deepcopy(self.race)
        race["active_boats"] = [1, 2, 3, 4, 5]
        race["boats"][5]["scratched"] = True
        race["odds_snapshot"]["odds"] = {key: value for key, value in race["odds_snapshot"]["odds"].items() if "6" not in key}
        race["human_box_input"] = None
        prediction = predict_race(race, self.model)
        self.assertEqual(len(prediction["distributions"]["P_model"]), 60)
        with self.assertRaisesRegex(ValueError, "HOLD:FULL_120_PROBABILITY_DOMAIN_REQUIRED"):
            build_shadow_output(prediction, race, self.generated, self.reproduction(prediction))

    def test_missing_manual_input_explicit_not_silently_formal_human(self):
        race = deepcopy(self.race)
        race["human_box_input"] = None
        prediction = predict_race(race, self.model)
        record = build_shadow_output(prediction, race, self.generated, self.reproduction(prediction))
        self.assertEqual(record["input_time_evidence"]["missing_input_codes"], ["MANUAL_HUMAN_INPUT_ABSENT_RESEARCH_HEURISTIC"])
        self.assertIsNone(record["input_time_evidence"]["human_box_times"])
        self.assertFalse(record["forecast"]["boxes"]["human_research"]["formal_box_v1_reproduction"])

    def test_input_times_are_recorded_and_mismatch_is_rejected(self):
        record = self.record()
        self.assertEqual(record["input_time_evidence"]["feature_times"], self.prediction["information"]["feature_times"])
        self.assertEqual(record["input_time_evidence"]["state_times"], self.prediction["information"]["state_times"])
        self.assertEqual(record["input_time_evidence"]["odds_times"]["revision_at"], self.race["odds_snapshot"]["revision_at"])
        prediction = deepcopy(self.prediction)
        prediction["information"]["odds_available_at"] = self.generated
        self.rehash(prediction)
        with self.assertRaisesRegex(ValueError, "HOLD:FORECAST_INPUT_TIME_EVIDENCE_MISMATCH"):
            build_shadow_output(prediction, self.race, self.generated, self.reproduction(prediction))

    def test_raw_tampering_newline_and_truncated_copy_are_rejected(self):
        payload, receipt = serialize_shadow(self.record())
        for changed in (payload[:-1], payload + b"\n", payload.replace(b'MODEL11_THIRD_RESEARCH', b'MODEL11_OTHER_RESEARCH')):
            with self.subTest(length=len(changed)):
                self.assertFalse(verify_shadow(changed, receipt)["valid"])

    def test_recomputed_self_hash_never_becomes_external_authentication(self):
        record = self.record()
        record["reproduction"]["code_commit"] = "a" * 40
        payload, receipt = serialize_shadow(record)
        verified = verify_shadow(payload, receipt)
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["authenticity"], "UNVERIFIED")
        self.assertEqual(verified["code_commit_verification"], "UNVERIFIED_REFERENCE_ONLY")
        self.assertEqual(verified["predeadline_publication"], "UNVERIFIED_NO_INDEPENDENT_RECEIPT")

    def test_no_independent_proof_or_operation_go_can_be_injected(self):
        for mutate in (lambda r: r.update(shadow_execution_go=True),
                       lambda r: r.update(proof_scope="INDEPENDENTLY_VERIFIED"),
                       lambda r: r.update(extra_operation="run"),
                       lambda r: r["reproduction"].update(code_commit_verification="PASS")):
            record = self.record()
            mutate(record)
            with self.assertRaisesRegex(ValueError, "HOLD:"):
                serialize_shadow(record)

    def test_sensitive_path_url_and_secret_fields_are_not_emitted(self):
        for key, value in (("url", "https://example.invalid/secret"), ("path", "/private/input"), ("token", "never-output")):
            prediction = deepcopy(self.prediction)
            prediction["model_spec"][key] = value
            prediction["model_sha256"] = canonical_hash(prediction["model_spec"])
            self.rehash(prediction)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "HOLD:FORBIDDEN_OUTPUT_FIELD"):
                build_shadow_output(prediction, self.race, self.generated, self.reproduction(prediction))

    def test_training_only_normalization_cannot_be_misrepresented_as_forecast(self):
        race = deepcopy(self.race)
        race["normalization_usage"] = "TRAINING_ONLY_NOT_FORECAST"
        prediction = predict_race(race, self.model)
        with self.assertRaisesRegex(ValueError, "HOLD:NORMALIZATION_NOT_FORECAST_ELIGIBLE"):
            build_shadow_output(prediction, race, self.generated, self.reproduction(prediction))

    def test_normalization_provenance_must_fit_before_prediction(self):
        race = deepcopy(self.race)
        race["normalization_usage"] = "PREDICTION_AS_OF_GATE_PASSED"
        provenance = {
            "normalizer_sha256": "a" * 64, "feature_specs_sha256": "b" * 64,
            "fit_cutoff": self.data["races"][5]["prediction_at"],
            "training_max_available_at": self.data["outcomes"][5]["available_at"],
            "training_input_sha256": "c" * 64, "usage": "prediction",
        }
        race["normalization_provenance"] = deepcopy(provenance)
        prediction = predict_race(race, self.model)
        record = build_shadow_output(prediction, race, self.generated, self.reproduction(prediction))
        self.assertEqual(record["input_time_evidence"]["normalization_provenance"]["fit_cutoff"], provenance["fit_cutoff"])
        self.assertEqual(record["input_time_evidence"]["normalization_provenance"]["timestamp_authenticity"], "UNVERIFIED_SELF_REPORTED_INPUT")
        for field in ("fit_cutoff", "training_max_available_at"):
            late_race = deepcopy(race)
            late_race["normalization_provenance"][field] = self.race["prediction_at"]
            late_prediction = predict_race(late_race, self.model)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "HOLD:NORMALIZATION_NOT_BEFORE_PREDICTION"):
                build_shadow_output(late_prediction, late_race, self.generated, self.reproduction(late_prediction))

    def test_verify_bad_receipt_and_noncanonical_payload_fail_closed(self):
        payload, receipt = serialize_shadow(self.record())
        self.assertFalse(verify_shadow(payload.decode("ascii"), receipt)["valid"])
        self.assertFalse(verify_shadow(payload, {})["valid"])
        noncanonical = payload + b"\n"
        receipt.update(bytes=len(noncanonical), sha256=hashlib.sha256(noncanonical).hexdigest())
        self.assertFalse(verify_shadow(noncanonical, receipt)["valid"])


if __name__ == "__main__":
    unittest.main()
