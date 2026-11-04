"""SYS-27/SYS-09 offline timing diagnostics; no scheduler, writer or LOCK rule."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from typing import Any

FIELDS = ("scheduled_for", "started_at", "observed_at", "completed_at", "saved_at", "deadline")
JST = timezone(timedelta(hours=9))
NAIVE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\Z")
AWARE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")
TIME_STATUSES = frozenset({"MISSING", "NULL", "EMPTY", "INVALID_TYPE", "NAIVE_TIME", "UNKNOWN_OFFSET", "MALFORMED", "CLOCK_FAILED", "CONFLICT_CLOCK_FAILURE_WITH_VALUE", "VALID"})
MISSING = object()


def parse_time(raw: Any = MISSING, *, clock_failed: bool = False) -> tuple[dict[str, Any], datetime | None]:
    presence = "MISSING" if raw is MISSING else "NULL" if raw is None else "EMPTY" if raw == "" else "PRESENT"
    result: dict[str, Any] = {"status": presence, "presence": presence, "jst": None, "utc": None}
    if clock_failed:
        result["status"] = "CLOCK_FAILED" if raw is MISSING or raw is None or raw == "" else "CONFLICT_CLOCK_FAILURE_WITH_VALUE"
        return result, None
    if presence != "PRESENT":
        return result, None
    if not isinstance(raw, str):
        result["status"] = "INVALID_TYPE"
        return result, None
    if NAIVE.fullmatch(raw):
        try:
            datetime.fromisoformat(raw)
        except ValueError:
            result["status"] = "MALFORMED"
        else:
            result["status"] = "NAIVE_TIME"
        return result, None
    if not AWARE.fullmatch(raw):
        result["status"] = "MALFORMED"
        return result, None
    if raw.endswith("-00:00"):
        result["status"] = "UNKNOWN_OFFSET"
        return result, None
    if not raw.endswith("Z") and (int(raw[-2:]) >= 60 or int(raw[-5:-3]) >= 24):
        result["status"] = "MALFORMED"
        return result, None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError
        utc = value.astimezone(timezone.utc)
        jst = value.astimezone(JST)
    except (ValueError, OverflowError):
        result["status"] = "MALFORMED"
        return result, None
    result.update(status="VALID", utc=utc.isoformat(timespec="microseconds"), jst=jst.isoformat(timespec="microseconds"))
    return result, utc


def interval(a: datetime | None, b: datetime | None) -> dict[str, Any]:
    if a is None or b is None:
        return {"status": "UNVERIFIED", "microseconds": None, "seconds": None}
    delta = b - a
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    sign = "-" if micros < 0 else ""
    magnitude = abs(micros)
    return {"status": "OBSERVED", "microseconds": micros,
            "seconds": f"{sign}{magnitude // 1_000_000}.{magnitude % 1_000_000:06d}"}


def _policy(raw: Any) -> tuple[dict[str, Any], dict[str, Decimal] | None]:
    if raw is MISSING or raw is None:
        return {"status": "NOT_PROVIDED", "adopted": False}, None
    if not isinstance(raw, dict) or raw.get("status") != "PROPOSED":
        return {"status": "INVALID_OR_UNADOPTED_POLICY", "adopted": False}, None
    values = {}
    for key in ("early_seconds", "late_seconds"):
        n = raw.get(key)
        if type(n) not in (int, float):
            return {"status": "INVALID_OR_UNADOPTED_POLICY", "adopted": False}, None
        try:
            decimal = Decimal(str(n))
        except (ValueError, OverflowError, InvalidOperation):
            return {"status": "INVALID_OR_UNADOPTED_POLICY", "adopted": False}, None
        if not decimal.is_finite() or decimal < 0:
            return {"status": "INVALID_OR_UNADOPTED_POLICY", "adopted": False}, None
        values[key] = decimal
    return {"status": "PROPOSED_ONLY", "adopted": False,
            "early_seconds": str(values["early_seconds"]), "late_seconds": str(values["late_seconds"])}, values


def _scheduler(record: dict[str, Any], times: dict[str, datetime | None]) -> dict[str, Any]:
    run_id = record.get("run_id", MISSING)
    present = isinstance(run_id, str) and bool(run_id.strip())
    claim = record.get("execution_origin_claim", "UNKNOWN")
    if claim not in ("SCHEDULED_CONTEXT", "MANUAL_AUDIT", "UNKNOWN"):
        claim = "UNRECOGNIZED_CLAIM"
    result = {"origin_claim": claim, "origin_proven": False,
              "internal_run_id_status": "UNVERIFIED", "link_status": "UNVERIFIED",
              "evidence_authenticity": "NOT_PROVEN_OFFLINE"}
    proof = record.get("scheduler_evidence")
    if not present or not isinstance(proof, dict):
        return result
    if proof.get("evidence_class") != "INTERNAL_SCHEDULER_RECORD":
        return result
    evidence_id = proof.get("internal_run_id")
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        return result
    if evidence_id != run_id:
        result.update(internal_run_id_status="CONFLICT", link_status="CONFLICT")
        return result
    result["internal_run_id_status"] = "MATCHING_PROVIDED_RECORD"
    checks = []
    for field in ("scheduled_for", "started_at"):
        _, supplied = parse_time(proof.get(field, MISSING))
        checks.append(supplied is not None and times[field] is not None and supplied == times[field])
    result["link_status"] = "CONSISTENT_PROVIDED_RECORD" if all(checks) else "CONFLICT_OR_INCOMPLETE"
    # Even consistent supplied metadata cannot establish a service's real origin.
    return result


def audit(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise TypeError("RECORD_OBJECT_REQUIRED")
    failures = record.get("clock_failures", [])
    if not isinstance(failures, list) or any(not isinstance(f, str) or f not in FIELDS for f in failures):
        raise ValueError("CLOCK_FAILURE_FIELDS_INVALID")
    reports, parsed = {}, {}
    for name in FIELDS:
        reports[name], parsed[name] = parse_time(record.get(name, MISSING), clock_failed=name in failures)
    pairs = {
        "scheduled_to_started": ("scheduled_for", "started_at"),
        "started_to_observed": ("started_at", "observed_at"),
        "started_to_completed": ("started_at", "completed_at"),
        "observed_to_saved": ("observed_at", "saved_at"),
        "completed_to_saved": ("completed_at", "saved_at"),
        "started_to_deadline": ("started_at", "deadline"),
        "saved_to_deadline": ("saved_at", "deadline"),
    }
    intervals = {key: interval(parsed[a], parsed[b]) for key, (a, b) in pairs.items()}
    start_delta = intervals["scheduled_to_started"]["microseconds"]
    start_class = "UNVERIFIED" if start_delta is None else "EARLY" if start_delta < 0 else "LATE" if start_delta > 0 else "AT_SCHEDULE"
    policy, thresholds = _policy(record.get("tolerance_policy", MISSING))
    outside = None
    if thresholds is not None and start_delta is not None:
        outside = (Decimal(-start_delta) > thresholds["early_seconds"] * 1_000_000) if start_delta < 0 else Decimal(start_delta) > thresholds["late_seconds"] * 1_000_000
    completed_delta = intervals["started_to_completed"]["microseconds"]
    anomalies = ["COMPLETED_BEFORE_STARTED"] if completed_delta is not None and completed_delta < 0 else []
    save_delta = intervals["saved_to_deadline"]["microseconds"]
    save_relation = "UNVERIFIED" if save_delta is None else "BEFORE_DEADLINE" if save_delta > 0 else "AFTER_DEADLINE" if save_delta < 0 else "AT_DEADLINE"
    date_diff = None
    if parsed["scheduled_for"] is not None and parsed["started_at"] is not None:
        date_diff = parsed["scheduled_for"].astimezone(JST).date() != parsed["started_at"].astimezone(JST).date()
    return {
        "profile": "SYS27_SYS09_OFFLINE_V001_PROPOSED",
        "times": reports, "intervals": intervals,
        "start_comparison": {"classification": start_class, "JST_date_changed": date_diff,
                             "outside_proposed_tolerance": outside},
        "tolerance_policy": policy, "save_deadline_relation": save_relation,
        "scheduler": _scheduler(record, parsed), "anomalies": anomalies,
        "timestamp_authenticity": "NOT_PROVEN_OFFLINE",
        "LOCK_validity": "NOT_EVALUATED", "production_GO": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Local JSON file, or - for stdin")
    args = parser.parse_args()
    try:
        if args.input == "-":
            data = sys.stdin.buffer.read(1_048_577)
        else:
            with Path(args.input).open("rb") as stream:
                data = stream.read(1_048_577)
        if len(data) > 1_048_576:
            raise ValueError("INPUT_SIZE_LIMIT")
        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("AMBIGUOUS_JSON")
                result[key] = item
            return result
        def constant(_value):
            raise ValueError("NONFINITE_JSON")
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
        result = [audit(r) for r in value] if isinstance(value, list) else audit(value)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "INPUT_UNVERIFIED", "error_type": type(exc).__name__, "production_GO": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
