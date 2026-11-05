"""Synthetic comparison runner; no app start, source capture or network."""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import socket
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_OFFLINE_HEALTH_V002")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--label", required=True, choices=["OLD_MAIN", "V001", "V002"])
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED", "classification": "SYNTHETIC_ONLY", "label": args.label, "production_go": False}, sort_keys=True), flush=True)
    fixture_path = Path(__file__).resolve().parent / "parser_fixtures.py"
    spec = importlib.util.spec_from_file_location("health_v002_synthetic_fixture", fixture_path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    sys.path.insert(0, str(args.repo.resolve()))
    from parsers import ParserError, parse_race_index
    results = []
    for case in fixtures.cases():
        result = {key: case[key] for key in ("id", "description", "category", "source_identity", "expected_status")}
        try:
            kwargs = {} if args.label == "OLD_MAIN" else {"expected_race_numbers": fixtures.EXPECTED_RACE_NUMBERS}
            races = parse_race_index(case["html"], fixtures.DATE, fixtures.SOURCE, fixtures.ACQUIRED, **kwargs)
            result["status"] = "ACCEPT"
            result["races"] = [{"race_id": race.race_id, "deadline": race.official_deadline.isoformat(),
                "is_cancelled": race.is_cancelled, "is_closed": race.is_closed, "sales_status": race.sales_status,
                "source_url": race.source_url, "acquired_at": race.acquired_at} for race in races]
        except ParserError:
            result["status"] = "REJECT"
            result["races"] = []
        except Exception as exc:
            result["status"] = "UNVERIFIED_INTERNAL_ERROR"
            result["error_type"] = type(exc).__name__
            result["races"] = []
        result["expectation_matches"] = result["status"] == case["expected_status"]
        if result["status"] == "ACCEPT":
            expected = case.get("expected_seconds")
            result["full_twelve"] = len(result["races"]) == 12 and len({r["race_id"] for r in result["races"]}) == 12
            if expected is not None:
                actual = {str(int(r["race_id"][-3:-1])): r["deadline"][11:19] for r in result["races"]}
                result["seconds_match"] = actual == expected
                result["expectation_matches"] = result["expectation_matches"] and result["seconds_match"]
            result["expectation_matches"] = result["expectation_matches"] and result["full_twelve"]
        results.append(result)
    print(json.dumps({"label": args.label, "classification": "SYNTHETIC_ONLY", "cases": results,
        "official_HTML_compatibility": "UNVERIFIED", "Claude_original_fixture_byte_identity": "UNVERIFIED_NOT_RECEIVED",
        "production_go": False}, sort_keys=True))
