"""Cross-module contracts and frozen-v001 boundary, wholly invented data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from model11.engine import canonical_hash, predict_race
from model11.models import make_model
from model11.synthetic import make_dataset
from model11.preparation import BASE_ENGINE_COMMIT
from model11.preparation.adapter import fit_normalizer, normalize_race, make_raw_fixture, synthetic_feature_specs
from model11.preparation.cli import forecast_only
from model11.preparation.legacy import make_synthetic_legacy_fixture, compare_frozen
from model11.preparation.sensitivity import audit_forecast
from model11.preparation.shadow import build_shadow_output, serialize_shadow, verify_shadow


class PreparationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = make_dataset(8, 1, 20261105)
        train = [make_raw_fixture(race) for race in cls.dataset["races"][:4]]
        cls.normalizer = fit_normalizer(train, cls.dataset["races"][4]["prediction_at"], synthetic_feature_specs())
        normalized = [normalize_race(raw, cls.normalizer, usage="training")["race"] for raw in train]
        cls.race = normalize_race(make_raw_fixture(cls.dataset["races"][6]), cls.normalizer)["race"]
        cls.model = make_model("hierarchical", {"epochs": 3}).fit(normalized, cls.dataset["outcomes"][:4])
        cls.prediction = predict_race(cls.race, cls.model)

    def test_frozen_v001_all_47_files_are_byte_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "MANIFEST.json").read_text())
        for row in manifest["files"]:
            raw = (root / row["path"]).read_bytes()
            self.assertEqual(len(raw), row["bytes"], row["path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"], row["path"])
        self.assertEqual(hashlib.sha256((root / "MANIFEST.json").read_bytes()).hexdigest(),
                         "9b60545e5277418fd3e36612b216f2dbb16e5116d46b8971f16306f4cfe3e82f")
        self.assertEqual(hashlib.sha256((root / "SHA256SUMS.txt").read_bytes()).hexdigest(),
                         "f5c7360bef149e7352c7659c93f8ae9c66779e290b70cf7b42e56c189b639daf")

    def test_adapter_train_only_predict_and_shadow_receipt_roundtrip(self):
        pred = self.prediction
        reproduction = {"code_commit": BASE_ENGINE_COMMIT,
                        "input_artifact_sha256": canonical_hash(self.race),
                        "model_sha256": canonical_hash(pred["model_spec"]),
                        "config_sha256": canonical_hash(pred["config"])}
        record = build_shadow_output(pred, self.race, self.race["prediction_at"], reproduction)
        payload, receipt = serialize_shadow(record)
        self.assertEqual(receipt["bytes"], len(payload))
        self.assertEqual(receipt["sha256"], hashlib.sha256(payload).hexdigest())
        verified = verify_shadow(payload, receipt)
        self.assertFalse(verified["production_go"])
        self.assertNotIn('"actual"', payload.decode())

    def test_outcome_attachment_is_removed_before_shadow_or_risk(self):
        evaluated = deepcopy(self.prediction)
        evaluated["actual"] = deepcopy(self.dataset["outcomes"][6])
        evaluated["first_course"] = 1
        restored = forecast_only(evaluated)
        self.assertEqual(restored, self.prediction)
        audit = audit_forecast(restored, self.race)
        self.assertFalse(audit["production_go"])
        altered = deepcopy(evaluated)
        altered["actual"]["result"] = [6, 5, 4]
        altered["actual"]["payout_per_100"] = 99999
        self.assertEqual(audit, audit_forecast(forecast_only(altered), self.race))

    def test_external_AB_comparison_does_not_change_or_feed_predictor(self):
        record = deepcopy(self.prediction)
        record["actual"] = deepcopy(self.dataset["outcomes"][6])
        before = deepcopy(record)
        fixture = make_synthetic_legacy_fixture([record], synthetic_only=True)
        comparison = compare_frozen([record], fixture["envelopes"], fixture["profiles"])
        self.assertEqual(record, before)
        self.assertEqual(set(comparison["comparisons"]), {"research_vs_A", "research_vs_B"})
        self.assertEqual(comparison["training_input_export"], "NOT_PROVIDED")
        self.assertEqual(comparison["pooled_AB_result"], "NOT_COMPUTED")
        self.assertFalse(comparison["production_go"])


if __name__ == "__main__":
    unittest.main()
