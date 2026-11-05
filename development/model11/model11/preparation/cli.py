"""Explicit local-file interfaces. No services, writers, notifications or bets."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import ssl
import sys

from model11.cli import _load, _write
from model11.engine import canonical_hash, predict_race
from model11.models import make_model
from model11.synthetic import make_dataset
from model11.walkforward import walk_forward

from . import BASE_ENGINE_COMMIT


def forecast_only(record):
    forecast = deepcopy(record)
    forecast.pop("actual", None)
    forecast["first_course"] = None
    digest = forecast.pop("prediction_sha256", None)
    if digest != canonical_hash(forecast):
        raise ValueError("FROZEN_FORECAST_HASH_MISMATCH")
    forecast["prediction_sha256"] = digest
    return forecast


def _new_directory(path):
    result = Path(path)
    result.mkdir(parents=True, exist_ok=False)
    return result


def _runtime():
    return {"python": sys.version, "platform": platform.platform(),
            "openssl": ssl.OPENSSL_VERSION, "executed_at": datetime.now(timezone.utc).isoformat(),
            "production_go": False}


def _files_receipt(root):
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            files.append({"name": path.relative_to(root).as_posix(), "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    _write(root / "FILES.json", files)


def run_demo(output_dir):
    """Exercise all five additions with wholly invented input, never real data."""
    from .adapter import fit_normalizer, normalize_race, make_raw_fixture, synthetic_feature_specs
    from .legacy import make_synthetic_legacy_fixture, compare_frozen
    from .planning import paired_cluster_sample_size, equal_day_logloss_estimand, protocol_readiness
    from .sensitivity import diagnose
    from .shadow import build_shadow_output, serialize_shadow, verify_shadow

    root = _new_directory(output_dir)
    dataset = make_dataset(36, 2, 20261105)
    baseline = walk_forward(dataset)
    original_summary = {k: v for k, v in baseline.items() if k != "records"}
    raw_summary = (json.dumps(original_summary, indent=2, sort_keys=True, ensure_ascii=True,
                              allow_nan=False) + "\n").encode()
    baseline_hash = hashlib.sha256(raw_summary).hexdigest()
    if baseline_hash != "09a2c12c68583cf02e111276380df007027d0d0750a866052365b1e4e366d587":
        raise ValueError("BASE71_BEHAVIOUR_REGRESSION")
    forecasts = [forecast_only(record) for record in baseline["records"]]
    race_by_id = {race["race_id"]: race for race in dataset["races"]}
    test_races = [race_by_id[forecast["race_id"]] for forecast in forecasts]
    _write(root / "baseline-preservation.json", {
        "base_engine_commit": BASE_ENGINE_COMMIT, "full_summary_bytes": len(raw_summary),
        "full_summary_sha256": baseline_hash, "matches_base71": True,
        "synthetic_evaluated_races": len(forecasts), "production_go": False})

    # A new adapter-trained smoke candidate has separate weights. Never feed a
    # different normalizer's values into the frozen base candidate's weights.
    specs = synthetic_feature_specs()
    raw_training = [make_raw_fixture(race) for race in dataset["races"][:24]]
    fit_cutoff = dataset["races"][24]["prediction_at"]
    normalizer = fit_normalizer(raw_training, fit_cutoff, specs)
    normalized_training = [normalize_race(raw, normalizer, usage="training")["race"]
                           for raw in raw_training]
    adapted = normalize_race(make_raw_fixture(test_races[0]), normalizer)
    smoke_model = make_model("hierarchical", {"epochs": 5, "alpha": .5}).fit(
        normalized_training, dataset["outcomes"][:24])
    smoke_forecast = predict_race(adapted["race"], smoke_model)
    _write(root / "adapter-synthetic-normalizer.json", normalizer)
    _write(root / "adapter-smoke-audit.json", adapted["audit"])
    _write(root / "adapter-smoke-prediction.json", smoke_forecast)

    sensitivity = diagnose(forecasts, test_races, dataset["outcomes"])
    _write(root / "sensitivity.json", sensitivity)
    legacy_fixture = make_synthetic_legacy_fixture(baseline["records"], synthetic_only=True)
    comparison = compare_frozen(baseline["records"], legacy_fixture["envelopes"], legacy_fixture["profiles"])
    _write(root / "legacy-synthetic-comparison.json", comparison)
    _write(root / "sample-size-planning.json", {
        "classification": "PROPOSED_ILLUSTRATIONS_NOT_REAL_VARIANCE_ESTIMATES",
        "cases": [paired_cluster_sample_size(sd, effect) for sd in (.1, .2, .3) for effect in (.02, .05)],
        "variance_unknown": paired_cluster_sample_size(None, .05),
        "protocol_readiness": protocol_readiness({}),
        "equal_day_synthetic_logloss": equal_day_logloss_estimand(baseline["records"]),
        "production_go": False})
    forecast, race = forecasts[0], test_races[0]
    reproduction = {"code_commit": BASE_ENGINE_COMMIT, "input_artifact_sha256": canonical_hash(race),
                    "model_sha256": canonical_hash(forecast["model_spec"]),
                    "config_sha256": canonical_hash(forecast["config"])}
    shadow = build_shadow_output(forecast, race, race["prediction_at"], reproduction)
    payload, receipt = serialize_shadow(shadow)
    with (root / "shadow-synthetic.raw.json").open("xb") as handle:
        handle.write(payload)
    _write(root / "shadow-synthetic.receipt.json", receipt)
    _write(root / "shadow-synthetic.verification.json", verify_shadow(payload, receipt))
    _write(root / "runtime.json", _runtime())
    _files_receipt(root)
    return {"status": "SYNTHETIC_PREPARATION_DEMO_COMPLETE", "base71_unchanged": True,
            "evaluated_races": len(forecasts), "real_data": "NOT_USED",
            "legacy_authenticity": "UNVERIFIED", "protocol": "PROPOSED_HOLD",
            "shadow_live_execution": "NOT_AUTHORIZED", "production_go": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lane2 local preparation; real input remains HQ14-private")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="All five additions, synthetic only")
    demo.add_argument("--output-dir", required=True)
    fit = commands.add_parser("fit-normalizer", help="Only explicitly supplied training snapshots")
    fit.add_argument("--training", required=True)
    fit.add_argument("--specs", required=True)
    fit.add_argument("--fit-cutoff", required=True)
    fit.add_argument("--output", required=True)
    normalize = commands.add_parser("normalize", help="Prediction use only, no refit")
    normalize.add_argument("--raw", required=True)
    normalize.add_argument("--normalizer", required=True)
    normalize.add_argument("--output", required=True)
    audit = commands.add_parser("diagnose", help="Fixed forecasts; no tuning/reselection")
    audit.add_argument("--forecasts", required=True)
    audit.add_argument("--races", required=True)
    audit.add_argument("--outcomes")
    audit.add_argument("--output", required=True)
    compare = commands.add_parser("compare", help="Independent frozen A/B external-input comparison")
    compare.add_argument("--research", required=True)
    compare.add_argument("--envelopes", required=True)
    compare.add_argument("--profiles", required=True)
    compare.add_argument("--output", required=True)
    shadow = commands.add_parser("shadow", help="Serialize local research record; no writer or transport")
    shadow.add_argument("--prediction", required=True)
    shadow.add_argument("--race", required=True)
    shadow.add_argument("--generated-at", required=True)
    shadow.add_argument("--reproduction", required=True)
    shadow.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "demo":
        result = run_demo(args.output_dir)
    elif args.command == "fit-normalizer":
        from .adapter import fit_normalizer
        result = fit_normalizer(_load(args.training), args.fit_cutoff, _load(args.specs))
        _write(Path(args.output), result)
    elif args.command == "normalize":
        from .adapter import normalize_race
        result = normalize_race(_load(args.raw), _load(args.normalizer))
        _write(Path(args.output), result)
    elif args.command == "diagnose":
        from .sensitivity import diagnose
        result = diagnose(_load(args.forecasts), _load(args.races),
                          None if args.outcomes is None else _load(args.outcomes))
        _write(Path(args.output), result)
    elif args.command == "compare":
        from .legacy import compare_frozen
        result = compare_frozen(_load(args.research), _load(args.envelopes), _load(args.profiles))
        _write(Path(args.output), result)
    else:
        from .shadow import build_shadow_output, serialize_shadow, verify_shadow
        record = build_shadow_output(_load(args.prediction), _load(args.race),
                                     args.generated_at, _load(args.reproduction))
        payload, receipt = serialize_shadow(record)
        root = _new_directory(args.output_dir)
        with (root / "shadow.raw.json").open("xb") as handle:
            handle.write(payload)
        _write(root / "shadow.receipt.json", receipt)
        result = verify_shadow(payload, receipt)
        _write(root / "shadow.verification.json", result)
    print(json.dumps({"command": args.command, "completed": True,
                      "assessment_status": result.get("status", "SEE_LOCAL_AUDIT"),
                      "production_go": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
