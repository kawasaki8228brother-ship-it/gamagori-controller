"""Four-version synthetic comparison; no actual HTML, network or app start."""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import re
import socket
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_HEALTH_V003")


def load_fixtures(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--label", choices=["OLD_MAIN", "V001", "V002", "V003"], required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED", "classification": "SYNTHETIC_ONLY", "label": args.label, "production_go": False}, sort_keys=True), flush=True)
    directory = Path(__file__).resolve().parent
    modules = [load_fixtures(directory / "parser_fixtures.py", "v003_fixtures"),
               load_fixtures(directory / "p_fixtures.py", "claude_p_fixtures"),
               load_fixtures(directory / "e5_fixtures.py", "e5_status_fixtures"),
               load_fixtures(directory.parent / "health_residuals_20261106_v002/parser_fixtures.py", "s1_fixtures")]
    sys.path.insert(0, str(args.repo.resolve()))
    from parsers import ParserError, parse_race_index
    records = []
    for module in modules:
        for case in module.cases():
            record = {key: case.get(key) for key in ("id", "description", "category", "expected_status", "policy_status", "source_identity")}
            record["family"] = ("R_AND_STATE_POLICY" if module is modules[0] else
                                "HQ14_CLAUDE_P_GENERATOR" if module is modules[1] else
                                "E5_STATIC_STATUS" if module is modules[2] else "PRESERVED_S1_DESCRIPTION")
            try:
                kwargs = {} if args.label == "OLD_MAIN" else {"expected_race_numbers": module.EXPECTED_RACE_NUMBERS}
                races = parse_race_index(case["html"], module.DATE, module.SOURCE, module.ACQUIRED, **kwargs)
                record["status"] = "ACCEPT"
                record["classification"] = "ACCEPT"
                record["races"] = [race.model_dump(mode="json") for race in races]
            except ParserError as exc:
                record["status"] = "REJECT"
                text = exc.args[0] if len(exc.args) == 1 and type(exc.args[0]) is str else ""
                pending = re.search(r"\bPOLICY_PENDING_REAL_HTML_[A-Z0-9_]+\Z", text)
                record["classification"] = "POLICY_PENDING_REAL_HTML" if pending else "REJECT"
                expected_reason = case.get("expected_reason")
                record["reason_matches"] = None if expected_reason is None else expected_reason in text
                record["safe_reason"] = pending.group(0) if pending else "FIXED_PARSER_REJECTION"
                record["races"] = []
            except Exception as exc:
                record.update(status="UNVERIFIED_INTERNAL_ERROR", classification="UNVERIFIED", error_type=type(exc).__name__, races=[])
            matches = record["status"] == case["expected_status"]
            if record["status"] == "ACCEPT":
                actual_seconds = {str(int(r["race_id"][-3:-1])): r["official_deadline"][11:19] for r in record["races"]}
                actual_flags = {str(int(r["race_id"][-3:-1])): {key: r[key] for key in ("sales_status", "is_closed", "is_cancelled")} for r in record["races"]}
                record["seconds_match"] = actual_seconds == case.get("expected_seconds")
                record["flags_match"] = None if case.get("expected_flags") is None else actual_flags == case["expected_flags"]
                record["full_twelve_unique"] = len(record["races"]) == len(actual_seconds) == 12
                matches = matches and record["seconds_match"] and record["full_twelve_unique"] and record["flags_match"] is not False
            if case.get("policy_status") == "POLICY_PENDING_REAL_HTML":
                matches = matches and record["classification"] == "POLICY_PENDING_REAL_HTML" and record.get("reason_matches") is True
            record["expectation_matches"] = matches
            records.append(record)
    print(json.dumps({"label": args.label, "classification": "SYNTHETIC_ONLY", "cases": records,
        "Claude_fixture_byte_identity": "UNVERIFIED_NOT_RECEIVED", "official_HTML_compatibility": "UNVERIFIED",
        "P1_P14_number_mapping": "GENERATOR_RECEIVED_RECONSTRUCTED_BYTE_IDENTITY_UNVERIFIED", "production_go": False}, sort_keys=True))
