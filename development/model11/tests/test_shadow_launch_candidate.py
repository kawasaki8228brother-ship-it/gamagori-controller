"""Independent candidate-kernel review using invented 2099 rows only.

PRIVATE_REAL tags and approval metadata here are deliberately fake test inputs,
not actual private data, an authentic approval, or permission to execute a shadow.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model11.preparation.adapter import normalize_race
from model11.revision_v003.engine import predict_v003
from model11.shadow_launch.candidate import forecast_candidate
from model11.shadow_launch.policy import artifact_fingerprints, preflight
from model11.shadow_launch.runner import ShadowRunner
from model11.shadow_launch.storage import ShadowStore

from test_shadow_launch_runner import make_simulation_context
import test_shadow_launch_policy as policy_tests
from test_shadow_launch_sources import private_looking_fixture


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="candidate-review-invented-")
        cls.context = make_simulation_context(cls.temporary.name)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def normalized_synthetic(self):
        ctx = self.context
        converted = ctx["source_adapter"].convert(ctx["captures"][0])
        race = normalize_race(converted["raw"], ctx["normalizer"])["race"]
        race.update(deepcopy(converted["course"]))
        return race

    def private_case(self, config=None, now=None):
        """Exercise private branch locally; these are not independently reviewed artifacts."""
        ctx = self.context
        config = {} if config is None else deepcopy(config)
        now = ctx["clock"]() if now is None else now
        private_race = self.normalized_synthetic()
        private_race.update(data_classification="PRIVATE_REAL", synthetic=False)
        for key, source in (("frame", "OFFICIAL_FRAME_PRELOCK_V001"), ("exhibition", "OFFICIAL_EXHIBITION_PRELOCK_V001")):
            if private_race["course_inputs"][key] is not None:
                private_race["course_inputs"][key]["source_id"] = source
        settings = deepcopy(ctx["settings"])
        settings.update(mode="PRIVATE_SHADOW", input_classification="HQ14_PRIVATE_OFFLINE")
        settings = policy_tests.pin(settings)
        artifacts = deepcopy(ctx["artifacts"])
        artifacts.pop("simulation_context", None)
        artifacts["source_mapping"] = private_looking_fixture({"mapping": ctx["mapping"], "capture": ctx["captures"][0]})["mapping"]
        artifacts["prediction_config"] = config
        for key in ("evaluation_plan", "formal_legacy_comparison"):
            artifacts[key] = {"review_status": "EXTERNALLY_REVIEWED_FOR_SHADOW", "open_items": [],
                              "test_only": "INVENTED_OPERATOR_STATEMENTS_NOT_REAL_APPROVAL"}
        artifacts["artifact_sha256s"] = artifact_fingerprints(artifacts, "PRIVATE_SHADOW")
        with patch.object(policy_tests, "NOW", now):
            artifacts, ack = policy_tests.approve_for_test(settings, artifacts)
        return private_race, settings, artifacts, ack, now

    def call_private(self, case, config=None):
        race, settings, artifacts, ack, now = case
        return forecast_candidate(race, self.context["model"], artifacts["prediction_config"] if config is None else config,
                                  settings, artifacts, now, operator_ack=ack)

    def test_private_missing_approvals_and_ack_hold_without_computation(self):
        case = self.private_case()
        race, settings, artifacts, ack, now = case
        del artifacts["approval_bundle"]
        with patch.object(self.context["model"], "distributions", side_effect=AssertionError("MUST_NOT_COMPUTE")):
            with self.assertRaisesRegex(ValueError, "LAUNCH_PREFLIGHT_HOLD"):
                forecast_candidate(race, self.context["model"], {}, settings, artifacts, now, operator_ack=ack)
        case = self.private_case()
        race, settings, artifacts, ack, now = case
        with self.assertRaisesRegex(ValueError, "LAUNCH_PREFLIGHT_HOLD"):
            forecast_candidate(race, self.context["model"], {}, settings, artifacts, now, operator_ack=None)

    def test_fake_private_statements_do_not_authenticate_or_grant_go(self):
        case = self.private_case()
        race, settings, artifacts, ack, now = case
        gate = preflight(settings, artifacts, ack, now)
        self.assertTrue(gate["allowed"])
        self.assertEqual(gate["status"], "PRIVATE_ATTESTED_PREFLIGHT_ONLY")
        self.assertIn("UNVERIFIED", gate["independent_approval_authenticity"])
        self.assertEqual(gate["actual_execution_go"], "NOT_ESTABLISHED_BY_PREFLIGHT")
        output = self.call_private(case)
        self.assertEqual(output["approval_authenticity"], "OPERATOR_ATTESTATION_EXTERNAL_REVIEW_REQUIRED")
        self.assertFalse(output["production_go"])

    def test_private_kernel_math_matches_immutable_v003_for_same_numbers(self):
        for weight in (0.0, .25, 1.0):
            with self.subTest(weight=weight):
                config = {"market_weight": weight, "temperature": 1.2}
                case = self.private_case(config)
                before = deepcopy(case[0])
                private = self.call_private(case)
                synthetic = predict_v003(self.normalized_synthetic(), self.context["model"], config)
                for key in ("distributions", "P_calibrated", "selection", "boxes", "bet_decision"):
                    self.assertEqual(private[key], synthetic[key], key)
                self.assertEqual(case[0], before)

    def test_private_input_is_not_relabelled_synthetic_inside_model(self):
        case = self.private_case()
        model = self.context["model"]
        with patch.object(model, "distributions", wraps=model.distributions) as watched:
            result = self.call_private(case)
        used = watched.call_args.args[0]
        self.assertEqual(used["data_classification"], "PRIVATE_REAL")
        self.assertIs(used["synthetic"], False)
        self.assertEqual(used["course_inputs"]["exhibition"]["source_id"], "OFFICIAL_EXHIBITION_PRELOCK_V001")
        self.assertEqual(result["classification"], "PRIVATE_RESEARCH_ONLY")
        with self.assertRaisesRegex(ValueError, "HOLD_REAL_INPUT_REVIEW_REQUIRED"):
            predict_v003(case[0], model)

    def test_private_missing_or_unapproved_normalization_provenance_hold(self):
        for kind in ("absent", "normalizer", "feature_specs", "training_input", "fit_cutoff", "training_available"):
            case = self.private_case()
            race = case[0]
            if kind == "absent":
                race.pop("normalization_usage")
                race.pop("normalization_provenance")
            elif kind in ("normalizer", "feature_specs", "training_input"):
                race["normalization_provenance"][kind + "_sha256"] = "f" * 64
            elif kind == "fit_cutoff":
                race["normalization_provenance"]["fit_cutoff"] = "2099-01-06T23:59:59+09:00"
            else:
                race["normalization_provenance"]["training_max_available_at"] = "2099-01-06T23:59:59+09:00"
            with self.assertRaisesRegex(ValueError, "NORMALIZ"):
                self.call_private(case)

    def test_actual_prediction_config_must_equal_approved_artifact(self):
        case = self.private_case()
        with self.assertRaisesRegex(ValueError, "FROZEN_MODEL_OR_CONFIG_MISMATCH"):
            self.call_private(case, {"market_weight": .9})
        race, settings, artifacts, ack, now = case
        tampered = deepcopy(artifacts)
        tampered["source_mapping"]["version"] = "edited_after_operator_attestation"
        with self.assertRaisesRegex(ValueError, "LAUNCH_PREFLIGHT_HOLD"):
            forecast_candidate(race, self.context["model"], {}, settings, tampered, now, ack)

    def test_private_generation_clock_boundaries(self):
        race = self.normalized_synthetic()
        prediction, deadline = datetime.fromisoformat(race["prediction_at"]), datetime.fromisoformat(race["deadline"])
        for now in (prediction - timedelta(seconds=1), deadline, deadline + timedelta(seconds=1)):
            case = self.private_case(now=now)
            with self.assertRaisesRegex(ValueError, "PRIVATE_PREDICTION_CLOCK_HOLD"):
                self.call_private(case)

    def test_invalid_approval_offset_cannot_normalize_into_valid_window(self):
        race, settings, artifacts, ack, now = self.private_case()
        bundle = artifacts["approval_bundle"]
        for owner in (bundle, *bundle["reviews"].values()):
            for field in ("valid_from", "valid_until"):
                owner[field] = owner[field][:-6] + "+08:60"  # parser otherwise normalizes to +09:00
        ack["attested_at"] = ack["attested_at"][:-6] + "+08:60"
        self.assertFalse(preflight(settings, artifacts, ack, now)["allowed"])
        with self.assertRaisesRegex(ValueError, "LAUNCH_PREFLIGHT_HOLD"):
            forecast_candidate(race, self.context["model"], {}, settings, artifacts, now, ack)

    def test_result_fields_never_enter_prediction_kernel(self):
        case = self.private_case()
        case[0]["result"] = [1, 2, 3]
        with self.assertRaises(ValueError):
            self.call_private(case)

    def test_default_runner_disabled_does_not_touch_dependencies(self):
        class Forbidden:
            def __getattr__(self, name):
                raise AssertionError("DISABLED_CONTEXT_INSPECTED")
            def __call__(self):
                raise AssertionError("DISABLED_CLOCK_READ")
        forbidden = Forbidden()
        with patch("builtins.open", side_effect=AssertionError("FILE_IO")), patch("socket.socket", side_effect=AssertionError("NETWORK_IO")), patch("sqlite3.connect", side_effect=AssertionError("DB_IO")):
            runner = ShadowRunner(model=forbidden, normalizer=forbidden, source_adapter=forbidden,
                                  store=forbidden, artifacts=forbidden, clock=forbidden)
            self.assertEqual(runner.run_race(None)["status"], "DISABLED")

    def test_runner_generated_after_deadline_never_commits_valid_forecast(self):
        with tempfile.TemporaryDirectory(prefix="candidate-clock-invented-") as tmp:
            context = make_simulation_context(tmp)
            store = ShadowStore(context["settings"]["storage_root"], clock=context["clock"])
            runner = ShadowRunner(context["settings"], context["model"], context["model_config"], context["normalizer"],
                                  context["source_adapter"], store, context["artifacts"], context["clock"])
            def advance_after_compute(*args, **kwargs):
                result = forecast_candidate(*args, **kwargs)
                context["clock"].set(context["races"][0]["deadline"])
                return result
            with patch("model11.shadow_launch.runner.forecast_candidate", side_effect=advance_after_compute):
                report = runner.run_race(context["captures"][0])
            self.assertEqual(report["status"], "HOLD")
            self.assertIn("FORECAST_CLOCK_HOLD", report["reasons"])
            self.assertNotEqual(store.readback(context["races"][0]["race_id"])["status"], "COMMITTED")

    def test_result_ingestion_does_not_refit_or_rewrite_forecast(self):
        with tempfile.TemporaryDirectory(prefix="candidate-result-invented-") as tmp:
            context = make_simulation_context(tmp)
            store = ShadowStore(context["settings"]["storage_root"], clock=context["clock"])
            runner = ShadowRunner(context["settings"], context["model"], context["model_config"], context["normalizer"],
                                  context["source_adapter"], store, context["artifacts"], context["clock"])
            self.assertEqual(runner.run_race(context["captures"][0])["status"], "COMMITTED")
            race_id = context["races"][0]["race_id"]
            original = store.readback(race_id)["forecast_raw"]
            model, normalizer = deepcopy(context["model"].to_dict()), deepcopy(context["normalizer"])
            context["clock"].set(context["outcomes"][0]["available_at"])
            report = runner.ingest_result(race_id, context["outcomes"][0])
            self.assertEqual(report["status"], "RESULT_SAVED", report)
            self.assertEqual(store.readback(race_id)["forecast_raw"], original)
            self.assertEqual(context["model"].to_dict(), model)
            self.assertEqual(context["normalizer"], normalizer)


if __name__ == "__main__":
    unittest.main()
