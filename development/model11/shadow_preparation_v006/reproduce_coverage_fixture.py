"""Generate invented 12R evidence, then audit it without changing saved bytes.

The writer below is solely the unchanged v005 synthetic demo. The coverage
checker itself never opens SQLite, writes a file, or obtains an actual schedule.
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import socket
import sqlite3
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_PREPARATION")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def write(path, value):
    with path.open("x", encoding="ascii", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")


def generate(output_dir):
    from model11.shadow_launch.cli import run_demo
    from model11.shadow_preparation.coverage import audit_schedule_coverage, frame_prediction_evidence
    root = Path(output_dir)
    run = run_demo(root)  # Requires an entirely new directory and invented input.
    if run["forecast_count"] != 12:
        raise ValueError("SYNTHETIC_DEMO_INCOMPLETE")
    store = root / "third_research"
    if any((store / ("ledger.sqlite3" + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("SYNTHETIC_STORE_MUST_BE_CLOSED_AND_SIDECAR_FREE")
    before = {path.relative_to(store).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in store.rglob("*") if path.is_file()}
    owner = json.loads((store / "OWNER.json").read_bytes())
    # Safe only for this just-created, closed, exclusively synthetic fixture.
    # This is not a live-store export/backup implementation.
    db = sqlite3.connect((store / "ledger.sqlite3").resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in db.execute("SELECT * FROM races ORDER BY deadline,race_id")]
    finally:
        db.close()
    observations, races = [], []
    for number, ledger in enumerate(rows, 1):
        directory = store / "artifacts" / ledger["race_key"]
        ledger["storage_id"] = owner["storage_id"]
        observations.append(frame_prediction_evidence(ledger,
            input_raw=(directory / "input.raw").read_bytes(),
            forecast_raw=(directory / "forecast.raw").read_bytes(),
            receipt_raw=(directory / "receipt.json").read_bytes(),
            completion_raw=(directory / "completion.json").read_bytes(),
            metadata_raw=bytes(ledger["commit_metadata"])))
        races.append({"race_id": ledger["race_id"], "race_no": number, "deadline": ledger["deadline"]})
    target_date = json.loads((root / "example-forecast.raw.json").read_bytes())["target_date"]
    manifest = {"schema": "OFFICIAL_DAY_SCHEDULE_V001_PROPOSED", "venue": "GAMAGORI",
                "target_date": target_date, "source_id": "SYNTHETIC_SCHEDULE_V006", "races": races}
    raw = canonical(manifest)
    digest = hashlib.sha256(raw).hexdigest()
    schedule = {"fixture_classification": "SYNTHETIC_ONLY", "disclaimer": "INVENTED_METADATA_NOT_ACTUAL_OFFICIAL_APPROVAL",
        "raw_manifest_b64": base64.b64encode(raw).decode("ascii"), "manifest_bytes": len(raw), "manifest_sha256": digest,
        "approval": {"approved": True, "declared_external_verification": True,
            "target_date": target_date, "venue": "GAMAGORI", "source_id": manifest["source_id"],
            "manifest_sha256": digest, "mapping_sha256": hashlib.sha256(b"SYNTHETIC_MAPPING_NOT_REAL").hexdigest(),
            "evidence_sha256": hashlib.sha256(b"INVENTED_REVIEW_NOT_ACTUAL_APPROVAL").hexdigest()}}
    report = audit_schedule_coverage(schedule, observations, target_date=target_date,
                                     expected_storage_id=owner["storage_id"])
    if report["status"] != "OBSERVATION_COMPLETE_LOCAL":
        raise ValueError("SYNTHETIC_COVERAGE_NOT_COMPLETE")
    scenarios = {"complete": report}
    scenarios["one_observation_missing"] = audit_schedule_coverage(schedule, observations[:-1], target_date=target_date)
    scenarios["duplicate_observation"] = audit_schedule_coverage(schedule, observations + [observations[0]], target_date=target_date)
    for label, observed in (("explicit_absent", "ABSENT"), ("unsaved", "NOT_SAVED"),
                            ("read_failed", "READ_FAILED"), ("uncertain_save", "UNCERTAIN")):
        modified = deepcopy(observations)
        modified[0]["observation"] = observed
        scenarios[label] = audit_schedule_coverage(schedule, modified, target_date=target_date)
    modified = deepcopy(observations)
    modified[0]["ledger"]["finalized_at"] = races[0]["deadline"]
    scenarios["late_finalization"] = audit_schedule_coverage(schedule, modified, target_date=target_date)
    if any(report["status"] != "HOLD" for name, report in scenarios.items() if name != "complete"):
        raise ValueError("NEGATIVE_COVERAGE_SCENARIO_ACCEPTED")
    after = {path.relative_to(store).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in store.rglob("*") if path.is_file()}
    if before != after:
        raise ValueError("COVERAGE_CHECK_CHANGED_SYNTHETIC_STORE")
    write(root / "SYNTHETIC_ONLY.schedule.json", schedule)
    write(root / "SYNTHETIC_ONLY.prediction-evidence.json", observations)
    write(root / "coverage-scenarios.json", {"classification": "SYNTHETIC_ONLY", "target_date": target_date,
        "store_files_byte_unchanged": True, "store_files": len(before), "scenarios": scenarios,
        "external_authenticity": "UNVERIFIED", "application_status": "HOLD", "production_go": False})
    return {"status": "SYNTHETIC_PREPARATION_COMPLETE", "forecasts": len(rows),
        "coverage_scenarios": len(scenarios), "store_files_byte_unchanged": True,
        "application_status": "HOLD", "production_go": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "sqlite": sqlite3.sqlite_version, "network": "BLOCKED_IN_PROCESS", "data": "SYNTHETIC_ONLY",
        "production_go": False}, sort_keys=True), flush=True)
    print(json.dumps(generate(args.output_dir), sort_keys=True))
