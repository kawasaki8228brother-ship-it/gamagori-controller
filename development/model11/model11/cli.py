"""Local JSON CLI; every output directory must be new. No network clients."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import ssl
import sys

from .engine import predict_race
from .metrics import evaluate_records
from .models import from_dict
from .synthetic import make_dataset
from .walkforward import walk_forward


def _load(path):
    def reject_constant(_):
        raise ValueError("NONFINITE_JSON")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_constant, object_pairs_hook=unique_pairs)


def _write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        handle.write("\n")


def run_backtest(dataset, output_dir, config=None):
    # No real/private input is copied automatically to the output directory.
    report = walk_forward(dataset, config)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False)
    example = report["records"][0]
    summary = {k: v for k, v in report.items() if k != "records"}
    _write(root / "summary.json", summary)
    forecast_only = {k: v for k, v in example.items() if k != "actual"}
    forecast_only["first_course"] = None
    _write(root / "example-prediction.json", forecast_only)
    _write(root / "example-evaluation.json", evaluate_records([example]))
    _write(root / "selected-model.json", report["folds"][0]["model"])
    _write(root / "selected-pipeline-config.json", example["config"])
    # The exact predictor input is exported only for an explicitly synthetic run.
    if dataset.get("classification") == "SYNTHETIC_ONLY":
        _write(root / "synthetic-example-input.json", next(
            r for r in dataset["races"] if r["race_id"] == example["race_id"]))
        _write(root / "synthetic-example-outcome.json", example["actual"])
    _write(root / "runtime.json", {
        "executed_at": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "dataset_classification": dataset.get("classification", "PRIVATE_INPUT_UNVERIFIED"),
        "production_go": False,
    })
    sums = []
    for path in sorted(root.iterdir()):
        raw = path.read_bytes()
        sums.append({"name": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    _write(root / "FILES.json", sums)
    return {"classification": report["classification"], "folds": len(report["folds"]),
            "evaluated_races": len(report["records"]), "example_race": example["race_id"],
            "five": example["selection"]["tickets"], "bet_decision": example["bet_decision"],
            "superiority": "UNVERIFIED", "production_go": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Model 1.1 research; no production integration")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate invented 2099 races and run full walk-forward")
    demo.add_argument("--output-dir", required=True)
    demo.add_argument("--days", type=int, default=36)
    demo.add_argument("--races-per-day", type=int, default=2)
    demo.add_argument("--seed", type=int, default=20261105)
    backtest = commands.add_parser("backtest", help="HQ14 approved private local JSON only; no upload")
    backtest.add_argument("--input", required=True)
    backtest.add_argument("--config")
    backtest.add_argument("--output-dir", required=True)
    predict = commands.add_parser("predict", help="Local prediction using a frozen research artifact")
    predict.add_argument("--race", required=True)
    predict.add_argument("--model", required=True)
    predict.add_argument("--config")
    predict.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "demo":
        result = run_backtest(make_dataset(args.days, args.races_per_day, args.seed), args.output_dir)
    elif args.command == "backtest":
        result = run_backtest(_load(args.input), args.output_dir, None if args.config is None else _load(args.config))
    else:
        result = predict_race(_load(args.race), from_dict(_load(args.model)),
                              None if args.config is None else _load(args.config))
        _write(Path(args.output), result)
        result = {"status": "RESEARCH_PREDICTION_WRITTEN", "prediction_sha256": result["prediction_sha256"],
                  "production_go": False}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
