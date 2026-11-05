"""Execute five synthetic cases and export summaries; no external app/DB."""
import argparse
import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import socket
import ssl
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_HEALTH_V003_EVENTS")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


async def run(directory):
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("synthetic_event_cases", root / "tests/test_health_v003_event_equivalence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    measured = await module.measure_status_case_comparisons(directory)
    full = canonical(measured) + b"\n"
    with (directory / "full_semantic_traces.json").open("xb") as output:
        output.write(full)
    summary = {key: value for key, value in measured.items() if key != "cases"}
    summary.update(full_semantic_trace_bytes=len(full), full_semantic_trace_sha256=hashlib.sha256(full).hexdigest(),
                   full_trace_scope="HELPER_TRACE_SQLITE_PHYSICAL_CREATED_AT_EXCLUDED", cases={})
    for name, case in measured["cases"].items():
        item = {key: value for key, value in case.items() if key not in ("old", "candidate")}
        for label in ("old", "candidate"):
            trace = case[label]
            item[label] = {"semantic_trace_sha256": hashlib.sha256(canonical(trace)).hexdigest(),
                "event_timing": module.event_timing(trace),
                "final_state_counts": dict(Counter(row["status"] for row in trace["states"])),
                "terminal_reasons": {row["race_id"]: row["terminal_reason"] for row in trace["states"]},
                "timeline": [{"at": poll["at"], "events": len(poll["events"]),
                    "state_counts": dict(Counter(row["status"] for row in poll["states"]))} for poll in trace["timeline"]]}
        summary["cases"][name] = item
    assert all(summary["cases"][name]["event_kinds_times_match"] and
               summary["cases"][name]["all_compared_semantic_fields_match"] for name in ("a", "b", "e"))
    assert summary["cases"]["c"]["old_terminal_events"] == summary["cases"]["c"]["candidate_terminal_events"] == 0
    assert not summary["cases"]["d"]["event_kinds_times_match"]
    summary["status"] = "SYNTHETIC_FIVE_CASE_EXPECTATIONS_MATCHED"
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work == Path("/var/data") or Path("/var/data") in work.parents:
        parser.error("PRODUCTION_MOUNT_NOT_ALLOWED_FOR_OFFLINE_FIXTURE")
    work.mkdir(parents=True, exist_ok=False)
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    sys.dont_write_bytecode = True
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "classification": "SYNTHETIC_ONLY", "network": "BLOCKED", "production_go": False}, sort_keys=True), flush=True)
    print(json.dumps(asyncio.run(run(work)), sort_keys=True, ensure_ascii=True))
