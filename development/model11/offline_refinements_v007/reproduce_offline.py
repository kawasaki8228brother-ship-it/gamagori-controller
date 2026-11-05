"""Generate only local synthetic examples; no model/store writer is invoked."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import socket
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_OFFLINE_REFINEMENTS")


def write(path, value):
    with path.open("x", encoding="ascii", newline="\n") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")


def load_fixture_module(package, filename, name):
    spec = importlib.util.spec_from_file_location(name, package / "tests" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reproduce(output_dir):
    from model11.offline_refinements.schedule import audit_manifest_coverage
    from model11.offline_refinements.point_in_time import audit_point_in_time
    from model11.offline_refinements.pilot import summarize_pilot
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=False)
    package = Path(__file__).resolve().parents[1]
    schedule_factory = load_fixture_module(package, "test_offline_refinements_schedule.py", "_synthetic_v007_schedule")
    pit_factory = load_fixture_module(package, "test_offline_refinements_point_in_time.py", "_synthetic_v007_pit")
    schedule_reports = {}
    for case in ("full", "short8", "one_cancelled", "one_withdrawn", "one_cancelled_with_prediction",
                 "cancel_after_deadline_with_prediction", "all_cancelled", "empty", "empty_closed"):
        fixture = schedule_factory.build_fixture(case)
        report = audit_manifest_coverage(fixture["schedule"], fixture["predictions"],
            target_date=fixture["target_date"], expected_storage_id=fixture["expected_storage_id"])
        expected = "HOLD" if case == "empty" else "OBSERVATION_COMPLETE_LOCAL"
        if report["status"] != expected:
            raise ValueError("SYNTHETIC_SCHEDULE_EXPECTATION_FAILED")
        schedule_reports[case] = report
        if case == "one_cancelled":
            write(root / "schedule.one-cancelled.SYNTHETIC.json", fixture["schedule"])
            write(root / "predictions.reused.SYNTHETIC.json", fixture["predictions"])
    base = pit_factory.sample_fixture()
    pit_cases = {"valid": deepcopy(base), "later_revision": deepcopy(base),
                 "component_after_archive": deepcopy(base), "missing_odds": deepcopy(base), "final_odds": deepcopy(base)}
    pit_cases["later_revision"]["features"][0]["revision_at"] = "2099-01-08T00:00:00+09:00"
    pit_cases["component_after_archive"]["features"][0]["revision_at"] = "2099-01-07T12:58:40+09:00"
    pit_cases["missing_odds"]["odds"] = None
    pit_cases["final_odds"]["odds"]["kind"] = "FINAL"
    pit_reports = {name: audit_point_in_time(sample) for name, sample in pit_cases.items()}
    if pit_reports["valid"]["software_check"] != "PASS" or any(
            value["status"] != "HOLD" for name, value in pit_reports.items() if name != "valid"):
        raise ValueError("SYNTHETIC_POINT_IN_TIME_EXPECTATION_FAILED")
    write(root / "point-in-time.valid.SYNTHETIC.json", base)
    rows, roster = [], []
    number = 0
    for day, deltas in ((1, [1]), (2, [1, 3]), (3, [2, 4, 6])):
        for delta in deltas:
            number += 1
            identity = {"race_id": "SYNTHETIC_PILOT_" + str(number), "target_date": f"2099-02-{day:02}"}
            roster.append(identity)
            rows.append({**identity, "baseline_id": "SYNTHETIC_MARKET", "baseline_version": "v001",
                "model_ll": 10 + delta, "market_ll": 10, "state": "PAIRED", "missing_reason": None})
    for index, state, reason in ((7, "MISSING", "MARKET_MISSING"), (8, "READ_FAILED", "BOTH_READ_FAILED")):
        identity = {"race_id": "SYNTHETIC_PILOT_" + str(index), "target_date": "2099-02-03"}
        roster.append(identity)
        rows.append({**identity, "baseline_id": "SYNTHETIC_MARKET", "baseline_version": "v001",
            "model_ll": 10 if index == 7 else None, "market_ll": None, "state": state, "missing_reason": reason})
    roster.append({"race_id": "SYNTHETIC_PILOT_9", "target_date": "2099-02-03"})
    pilot = summarize_pilot(roster, rows, baseline_id="SYNTHETIC_MARKET", baseline_version="v001", roster_complete=True)
    if not math.isclose(pilot["sd_day"], math.sqrt(7/3), abs_tol=1e-12):
        raise ValueError("SYNTHETIC_PILOT_KNOWN_VECTOR_FAILED")
    if not math.isclose(pilot["missing_rates"]["TOTAL_UNPAIRED"], 1/3, abs_tol=1e-12):
        raise ValueError("SYNTHETIC_PILOT_MISSING_RATE_FAILED")
    if any(str(row["race_id"]) in json.dumps(pilot) or row["target_date"] in json.dumps(pilot) for row in roster):
        raise ValueError("PILOT_SUMMARY_ECHOED_IDENTIFIERS")
    write(root / "pilot-roster.SYNTHETIC.json", roster)
    write(root / "pilot-observations.SYNTHETIC.json", rows)
    write(root / "pilot-summary.json", pilot)
    unknown = summarize_pilot(roster, rows, baseline_id="SYNTHETIC_MARKET", baseline_version="v001")
    if any(value is not None for value in unknown["missing_rates"].values()):
        raise ValueError("INCOMPLETE_ROSTER_WAS_ASSUMED_COMPLETE")
    write(root / "pilot-unconfirmed-roster-summary.json", unknown)
    source = package / "shadow_preparation_v006/results/SYNTHETIC_ONLY.prediction-evidence-python312.json.gz.b64.txt"
    source_raw = source.read_bytes()
    write(root / "scenario-results.json", {"classification": "SYNTHETIC_ONLY_INVENTED_2099", "schedule": schedule_reports,
        "point_in_time": pit_reports, "pilot": pilot, "pilot_roster_unconfirmed": unknown,
        "source_fixture": {"parent_commit": "7aec4fdb6b9f311ee01bf3a2752410e683d83e42",
            "path": source.relative_to(package).as_posix(), "bytes": len(source_raw), "sha256": hashlib.sha256(source_raw).hexdigest()},
        "model_run": False, "store_opened": False, "predictions_changed": False,
        "monotonic_implementation": "NOT_ADDED_DESIGN_ONLY", "thresholds_adopted": False,
        "application_status": "HOLD", "production_go": False})
    return {"status": "SYNTHETIC_OFFLINE_REFINEMENTS_COMPLETE", "schedule_cases": len(schedule_reports),
        "point_in_time_cases": len(pit_reports), "pilot_paired_days": pilot["counts"]["paired_day_clusters"],
        "application_status": "HOLD", "production_go": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED_IN_PROCESS", "data": "SYNTHETIC_ONLY", "production_go": False}, sort_keys=True), flush=True)
    print(json.dumps(reproduce(arguments.output_dir), sort_keys=True))
