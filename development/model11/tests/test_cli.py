import json
from pathlib import Path
import tempfile
import unittest

from model11.cli import _load, _write, run_backtest
from model11.engine import canonical_hash, predict_race
from model11.models import from_dict
from model11.synthetic import make_dataset


class LocalFileSafetyTests(unittest.TestCase):
    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local.json"
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError):
                    _load(path)

    def test_existing_files_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            _write(path, {"research": True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                _write(path, {"different": True})
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(json.loads(before), {"research": True})

    def test_exported_forecast_is_reproducible_without_labels(self):
        config = {"train_days": 3, "selection_days": 2, "test_days": 2,
                  "epochs": 2, "candidates": ["hierarchical"], "alphas": [.5],
                  "temperatures": [.8], "market_weights": [.5], "evaluation": {}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new"
            run_backtest(make_dataset(days=7, races_per_day=1), root, config)
            forecast = _load(root / "example-prediction.json")
            self.assertNotIn("actual", forecast)
            self.assertIsNone(forecast["first_course"])
            restored = predict_race(_load(root / "synthetic-example-input.json"),
                                    from_dict(_load(root / "selected-model.json")),
                                    _load(root / "selected-pipeline-config.json"))
            self.assertEqual(forecast, restored)
            without_digest = {k: v for k, v in forecast.items() if k != "prediction_sha256"}
            self.assertEqual(canonical_hash(without_digest), forecast["prediction_sha256"])


if __name__ == "__main__":
    unittest.main()
