"""Write a new invented QA example; never query or change Events/tasks."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import socket
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_OBS_QA")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--unittest-only", action="store_true")
    args = parser.parse_args()
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from development.health_residuals_20261105_v001.obs_qa import audit_obs_rows, make_synthetic_obs_fixture
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "network": "BLOCKED",
        "classification": "SYNTHETIC_ONLY", "production_go": False}, sort_keys=True), flush=True)
    if args.unittest_only:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[2] / "tests"),
                                                  pattern="test_health_obs_qa.py")
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
        print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
            "scope": "STDLIB_SYNTHETIC_OBS_QA_ONLY", "production_go": False}, sort_keys=True))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if args.output_dir is None:
        parser.error("OUTPUT_DIRECTORY_REQUIRED_FOR_SYNTHETIC_EXAMPLE")
    fixture = make_synthetic_obs_fixture()
    before = json.dumps(fixture, sort_keys=True, ensure_ascii=True, allow_nan=False)
    report = audit_obs_rows(fixture["rows"])
    assert before == json.dumps(fixture, sort_keys=True, ensure_ascii=True, allow_nan=False)
    assert report["input_rows"] == 20 and report["payload_uuid_missing_rows"] == 12
    assert report["source_evidence_counts"] == {"MISSING_FIELD": 1, "EMPTY_ARRAY": 3, "DECLARED_NORMAL": 16}
    assert report["hash_counts"]["local_canonical_matches"] == 20
    assert report["idempotency_counts"]["matching_A_rows"] == report["idempotency_counts"]["unique_A_provided_keys"] == 20
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (("SYNTHETIC_ONLY.obs-rows.json", fixture), ("obs-qa-report.json", report)):
        with (args.output_dir / name).open("x", encoding="ascii", newline="\n") as output:
            output.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n")
    print(json.dumps({"status": "SYNTHETIC_OBS_QA_COMPLETE", "input_rows": 20, "input_bytes_unchanged": True,
        "actual_11_05_rows_obtained": False, "OBS_contract": "UNVERIFIED", "production_go": False}, sort_keys=True))
