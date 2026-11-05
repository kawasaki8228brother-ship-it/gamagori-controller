"""Local v003 reproducibility CLI. No production reader, writer or transport."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import platform
import ssl
import sys
from datetime import datetime, timezone

from ..cli import _load, _write
from ..engine import canonical_hash
from ..preparation.cli import forecast_only
from .course import CourseBoundModel
from .engine import predict_v003
from .fixtures import make_dataset_v003
from .migration import migrate_v001_prediction
from .walkforward import walk_forward_v003


def verify_originals():
    root = Path(__file__).resolve().parents[2]
    manifest_path = root / "preparation_v002/MANIFEST_V002.json"
    manifest_raw = manifest_path.read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != "816c8ceaabc9a7f02979de58bf8d011da49a4bf709a04f1f3b0848a1e5f2c38b":
        raise ValueError("HOLD_ORIGINAL_V002_MANIFEST_CHANGED")
    manifest = json.loads(manifest_raw)
    entries = manifest["retained_original_files"] + manifest["added_payload_files"]
    for entry in entries:
        path = root / entry["path"].removeprefix("development/model11/")
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("HOLD_ORIGINAL_ARTIFACT_CHANGED")
    if hashlib.sha256((root / "preparation_v002/SHA256SUMS_V002.txt").read_bytes()).hexdigest() != "fd586b961fa1ad66011fbb4377765e53dadd0ff2b33bebaa3e572c5a2861d69e":
        raise ValueError("HOLD_ORIGINAL_V002_SUMS_CHANGED")
    return {"original_artifacts": len(entries) + 2, "byte_unchanged": True}


def _new_directory(path):
    root = Path(path)
    root.mkdir(parents=True, exist_ok=False)
    return root


def run_demo(output_dir):
    original = verify_originals()
    root = _new_directory(output_dir)
    dataset = make_dataset_v003()
    report = walk_forward_v003(dataset)
    summary = {key: value for key, value in report.items() if key != "records"}
    _write(root / "walk-forward-summary.json", summary)
    prediction = forecast_only(report["records"][0])
    race_by_id = {race["race_id"]: race for race in dataset["races"]}
    outcome_by_id = {outcome["race_id"]: outcome for outcome in dataset["outcomes"]}
    race = race_by_id[prediction["race_id"]]
    model = CourseBoundModel.from_dict(report["folds"][0]["model"])
    _write(root / "prediction-v003.json", prediction)
    _write(root / "selected-model-v003.json", model.to_dict())
    _write(root / "selected-pipeline-v003.json", prediction["config"])
    _write(root / "synthetic-race-v003.json", race)
    _write(root / "synthetic-outcome-separate.json", outcome_by_id[race["race_id"]])

    a = predict_v003(race, model, {"market_weight": 1.0, "temperature": .8})
    fold = report["folds"][0]
    train = [race_by_id[ident] for ident in fold["train_ids"]]
    alternate = CourseBoundModel("contextual", {"epochs": 3, "alpha": 1.0}, model.course_policy)
    alternate.fit(train, [outcome_by_id[entry["race_id"]] for entry in train])
    b = predict_v003(race, alternate, {"market_weight": 1.0, "temperature": 1.5})
    if (a["distributions"]["P_shrunk"] != a["distributions"]["P_market"]
            or b["distributions"]["P_shrunk"] != a["distributions"]["P_market"]
            or a["selection"]["tickets"] != b["selection"]["tickets"]):
        raise ValueError("HOLD_F1_MARKET_ONLY_REGRESSION")
    _write(root / "F1-market-only-evidence.json", {
        "market_weights": report["config"]["market_weights"],
        "model_weight": 0, "market_weight": 1.0,
        "exact_market_probability_copy": True,
        "different_models_and_temperatures_same_market_forecast": True,
        "P_model_distributions_differ": a["distributions"]["P_model"] != b["distributions"]["P_model"],
        "same_five_tickets": True, "market_only_type": a["pool_definition"]["prediction_type"],
        "probability_integrity": a["probability_integrity"], "production_go": False})

    manual = {"race_id": race["race_id"], "target_date": race["target_date"],
              "core": [1, 2], "insertion": 3, "origin": "HUMAN_MANUAL",
              "source_id": "SYNTHETIC_MANUAL_ASSERTION_NOT_REAL_PERSON",
              "evidence_sha256": canonical_hash({"synthetic": "MANUAL_INPUT_TEST_ONLY"})}
    for field in ("observed_at", "acquired_at", "available_at", "revision_at", "evidence_recorded_at"):
        manual[field] = race["prediction_at"]
    manual_prediction = predict_v003(race, model, prediction["config"], human_input=manual)
    _write(root / "F4-manual-input-SYNTHETIC-ONLY.json", manual)
    _write(root / "F4-separate-manual-and-automatic.json", manual_prediction)
    package = Path(__file__).resolve().parents[2]
    old = _load(package / "results/demo/example-prediction.json")
    migrated = migrate_v001_prediction(old)
    _write(root / "F4-old-artifact-migration.json", migrated)
    _write(root / "preservation.json", {**original, "base_commit": "00d67eea0598ba83671eb400175749df294a6fad",
                                        "no_original_output_rewritten": True, "production_go": False})
    _write(root / "runtime.json", {"python": sys.version, "openssl": ssl.OPENSSL_VERSION,
                                   "platform": platform.platform(),
                                   "executed_at": datetime.now(timezone.utc).isoformat(), "production_go": False})
    files = [{"name": path.name, "bytes": path.stat().st_size,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(root.iterdir()) if path.is_file()]
    _write(root / "FILES.json", files)
    return {"status": "SYNTHETIC_V003_DIAGNOSTIC_COMPLETE", "records": len(report["records"]),
            "original88_unchanged": original["byte_unchanged"],
            "F2_F5": "DESIGN_PENDING_NOT_ADOPTED", "production_go": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="v003 F1/F3/F4 offline research only")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo")
    demo.add_argument("--output-dir", required=True)
    predict = commands.add_parser("predict")
    predict.add_argument("--race", required=True)
    predict.add_argument("--model", required=True)
    predict.add_argument("--config")
    predict.add_argument("--human-input")
    predict.add_argument("--output", required=True)
    migrate = commands.add_parser("migrate")
    migrate.add_argument("--old-forecast", required=True)
    migrate.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "demo":
        result = run_demo(args.output_dir)
    elif args.command == "predict":
        result = predict_v003(_load(args.race), CourseBoundModel.from_dict(_load(args.model)),
                              None if args.config is None else _load(args.config),
                              None if args.human_input is None else _load(args.human_input))
        _write(Path(args.output), result)
    else:
        result = migrate_v001_prediction(_load(args.old_forecast))
        _write(Path(args.output), result)
    print(json.dumps({"command": args.command, "status": result.get("status", "RESEARCH_FORECAST_WRITTEN"),
                      "production_go": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
