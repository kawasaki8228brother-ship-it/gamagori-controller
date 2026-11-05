"""Explicit local capture runner. No automatic startup or live HTTP collector."""
import argparse
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import signal
import sys
import time

from ..cli import _load, _write
from ..revision_v003.course import CourseBoundModel
from ..validation import _timestamp as _strict_timestamp
from .policy import preflight
from .runner import ShadowRunner
from .sources import SourceAdapter
from .storage import ShadowStore


def _capture(value):
    if not isinstance(value, dict) or "payload_bytes_b64" not in value or "payload_bytes" in value:
        raise ValueError("CAPTURE_FILE_ENCODING_REQUIRED")
    result = deepcopy(value)
    result["payload_bytes"] = base64.b64decode(result.pop("payload_bytes_b64"), validate=True)
    return result


def _load_snapshot(raw):
    def reject_constant(_):
        raise ValueError("NONFINITE_JSON")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), parse_constant=reject_constant, object_pairs_hook=unique_pairs)


def _context(args):
    settings = {"enabled": False} if args.config is None else _load(args.config)
    if not isinstance(settings, dict) or settings.get("enabled") is not True:
        return None, preflight({"enabled": False}, {}, now=None), None
    if args.artifacts is None:
        return None, {"status": "HOLD", "allowed": False, "reasons": ["ARTIFACTS_REQUIRED"]}, None
    artifacts = _load(args.artifacts)
    ack = None if args.operator_ack is None else _load(args.operator_ack)
    if args.simulation_now is not None:
        if settings.get("mode") != "SIMULATION":
            raise ValueError("PRIVATE_CLOCK_OVERRIDE_FORBIDDEN")
        now = _strict_timestamp(args.simulation_now)
        if now is None:
            raise ValueError("SIMULATION_AWARE_CLOCK_REQUIRED")
        clock = lambda: now
    else:
        clock = lambda: datetime.now(timezone.utc)
    gate = preflight(settings, artifacts, operator_ack=ack, now=clock())
    if not gate["allowed"]:
        return None, gate, ack
    runner = ShadowRunner(settings, CourseBoundModel.from_dict(artifacts["model"]),
        model_config=artifacts["prediction_config"], normalizer=artifacts["normalizer"],
        source_adapter=SourceAdapter(artifacts["source_mapping"]), artifacts=artifacts, clock=clock)
    return runner, gate, ack


def run_demo(output_dir):
    """Use only the shipped invented fixture factory; persist no live state."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False)
    package = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("_shadow_synthetic_demo_fixture", package / "tests/test_shadow_launch_runner.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    context = fixture.make_simulation_context(root)
    runner = ShadowRunner(context["settings"], context["model"], model_config=context["model_config"],
        normalizer=context["normalizer"], source_adapter=context["source_adapter"],
        artifacts=context["artifacts"], clock=context["clock"])
    run_records, raw_hashes = [], {}
    for capture, race in zip(context["captures"], context["races"]):
        context["clock"].set(datetime.fromisoformat(race["prediction_at"]) + timedelta(seconds=1))
        result = runner.run_race(capture)
        if result["status"] != "COMMITTED":
            raise ValueError("DEMO_FORECAST_HOLD")
        raw = runner.store.readback(race["race_id"])
        raw_hashes[race["race_id"]] = hashlib.sha256(raw["forecast_raw"]).hexdigest()
        run_records.append({"race_id": race["race_id"], "status": result["status"], "receipt": result["receipt"]})
    duplicate = runner.run_race(context["captures"][-1])
    if duplicate["status"] != "DUPLICATE":
        raise ValueError("DEMO_DUPLICATE_HOLD")
    context["clock"].set(datetime.fromisoformat(context["outcomes"][-1]["available_at"]) + timedelta(minutes=1))
    selections = {}
    for outcome in context["outcomes"]:
        saved = runner.ingest_result(outcome["race_id"], outcome)
        if saved["status"] != "RESULT_SAVED":
            raise ValueError("DEMO_RESULT_HOLD")
        selections[outcome["race_id"]] = saved["result_sha256"]
    settled = runner.daily_settlement(context["races"][0]["target_date"], selections)
    if settled["status"] != "SETTLED":
        raise ValueError("DEMO_SETTLEMENT_HOLD")
    for race_id, digest in raw_hashes.items():
        if hashlib.sha256(runner.store.readback(race_id)["forecast_raw"]).hexdigest() != digest:
            raise ValueError("DEMO_FORECAST_CHANGED_BY_RESULT")
    first = runner.store.readback(context["races"][0]["race_id"])
    (root / "example-input.raw.json").write_bytes(first["input_raw"])
    (root / "example-forecast.raw.json").write_bytes(first["forecast_raw"])
    _write(root / "example-receipt.json", first["receipt"])
    _write(root / "daily-settlement.json", settled)
    _write(root / "demo-audit.json", {"classification": "SYNTHETIC_ONLY", "forecasts": run_records,
        "forecast_hashes": raw_hashes, "duplicate": duplicate, "result_versions": selections,
        "default_disabled": ShadowRunner().run_race(None), "shutdown": runner.shutdown(),
        "production_go": False})
    return {"status": "SYNTHETIC_SHADOW_DEMO_COMPLETE", "forecast_count": len(run_records),
            "result_count": len(selections), "default": "DISABLED", "production_go": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independent Shadow candidate; default DISABLED; no live collector")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output-dir", required=True)
    stop = sub.add_parser("stop")
    stop.add_argument("--config", required=True)
    for command in ("preflight", "run", "watch", "result", "settle"):
        item = sub.add_parser(command)
        item.add_argument("--config")
        item.add_argument("--artifacts")
        item.add_argument("--operator-ack")
        item.add_argument("--simulation-now")
        if command == "run":
            item.add_argument("--captures")
        elif command == "watch":
            item.add_argument("--input-dir")
            item.add_argument("--poll-seconds", type=float, default=1.0)
            item.add_argument("--max-iterations", type=int)
        elif command == "result":
            item.add_argument("--outcome")
        elif command == "settle":
            item.add_argument("--date")
            item.add_argument("--selection")
    args = parser.parse_args(argv)
    runner = None
    try:
        if args.command == "demo":
            result = run_demo(args.output_dir)
        elif args.command == "stop":
            settings = _load(args.config)
            location = settings.get("storage_root")
            if not isinstance(location, str) or not (Path(location) / "OWNER.json").is_file():
                result = {"status": "DISABLED", "reasons": ["NO_EXISTING_OWNED_SHADOW_STORE"]}
            else:
                store = ShadowStore(location, settings.get("namespace"))
                initialized = store.initialize()
                result = store.stop("OPERATOR_STOP") if initialized["status"] in ("READY", "HOLD") else initialized
        else:
            runner, gate, ack = _context(args)
            result = gate
            if runner is not None and args.command != "preflight":
                signal.signal(signal.SIGTERM, lambda *_: runner.request_stop("PROCESS_SIGTERM"))
                signal.signal(signal.SIGINT, lambda *_: runner.request_stop("PROCESS_SIGINT"))
                if args.command == "run":
                    values = _load(args.captures)
                    if not isinstance(values, list):
                        raise ValueError("CAPTURE_LIST_REQUIRED")
                    reports = [runner.run_race(_capture(value), operator_ack=ack) for value in values]
                    statuses = [report["status"] for report in reports]
                    result = {"status": "RUN_COMPLETE" if statuses and all(status in ("COMMITTED", "DUPLICATE")
                              for status in statuses) else "HOLD", "statuses": statuses}
                elif args.command == "watch":
                    if (args.input_dir is None or not math.isfinite(args.poll_seconds) or args.poll_seconds <= 0
                            or (args.max_iterations is not None and args.max_iterations <= 0)):
                        raise ValueError("EXPLICIT_INPUT_DIRECTORY_REQUIRED")
                    folder, seen, cycles = Path(args.input_dir), {}, 0
                    if not folder.is_dir() or folder.is_symlink():
                        raise ValueError("INPUT_DIRECTORY_INVALID")
                    failure_code = None
                    hold_seen = False
                    while not runner._closed:
                        for path in sorted(folder.glob("*.json")):
                            if path.is_symlink():
                                runner.request_stop("INPUT_SYMLINK_FORBIDDEN")
                                failure_code = "INPUT_SYMLINK_FORBIDDEN"
                                break
                            snapshot = path.read_bytes()
                            digest = hashlib.sha256(snapshot).hexdigest()
                            if path.name in seen:
                                if seen[path.name] != digest:
                                    runner.request_stop("INPUT_CAPTURE_FILE_REWRITTEN")
                                    failure_code = "INPUT_CAPTURE_FILE_REWRITTEN"
                                    break
                                continue
                            report = runner.run_race(_capture(_load_snapshot(snapshot)), operator_ack=ack)
                            seen[path.name] = digest
                            hold_seen = hold_seen or report["status"] not in ("COMMITTED", "DUPLICATE")
                            print(json.dumps({"status": report["status"], "production_go": False}), flush=True)
                        cycles += 1
                        if (args.max_iterations is not None and cycles >= args.max_iterations) or (runner.store and runner.store.is_stopped()):
                            break
                        time.sleep(min(args.poll_seconds, 30))
                    result = {"status": "HOLD" if failure_code or hold_seen else "WATCH_STOPPED", "iterations": cycles}
                    if failure_code or hold_seen:
                        result["reasons"] = [failure_code or "CAPTURE_INGEST_HOLD"]
                elif args.command == "result":
                    outcome = _load(args.outcome)
                    result = runner.ingest_result(outcome["race_id"], outcome, operator_ack=ack)
                else:
                    result = runner.daily_settlement(args.date, _load(args.selection), operator_ack=ack)
        public = {"command": args.command, "status": result.get("status"), "production_go": False}
        for field in ("statuses", "reasons", "iterations", "forecast_count", "result_count"):
            if field in result:
                public[field] = result[field]
        print(json.dumps(public, sort_keys=True))
        return 0 if result.get("status") not in ("HOLD", "STOP", "STOP_UNCERTAIN") else 2
    except Exception:
        print(json.dumps({"command": args.command, "status": "HOLD", "reason": "LOCAL_INPUT_OR_EXECUTION_UNVERIFIED",
                          "production_go": False}, sort_keys=True))
        return 2
    finally:
        if runner is not None:
            runner.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
