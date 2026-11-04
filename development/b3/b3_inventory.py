"""Offline four-meet inventory. No network, writer or LOCK validity engine."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
import argparse
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
SOURCES = ("A", "B")
RACE = re.compile(r"^(\d{8})_GAMAGORI_([1-9]|1[0-2])R$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$")


class InputError(ValueError):
    """Schema/configuration error; messages do not echo private values."""


def _fail(code: str):
    raise InputError(code)


def _day(value: Any) -> date:
    if not isinstance(value, str): _fail("DATE_INVALID")
    try: parsed = date.fromisoformat(value)
    except ValueError: _fail("DATE_INVALID")
    if parsed.isoformat() != value: _fail("DATE_INVALID")
    return parsed


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or not STAMP.fullmatch(value): _fail("TIME_MISSING_OR_INVALID")
    if value.endswith('-00:00'): _fail("UNKNOWN_TIMEZONE_OFFSET")
    try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: _fail("TIME_MISSING_OR_INVALID")
    if parsed.tzinfo is None or parsed.utcoffset() is None: _fail("TIMEZONE_REQUIRED")
    return parsed.astimezone(JST)


def _triple(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(type(n) is int and 1 <= n <= 6 for n in value) and len(set(value)) == 3


def _tickets(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 5 and all(_triple(t) for t in value) and len({tuple(t) for t in value}) == 5


def _money(value: Any) -> bool:
    return type(value) is int and value >= 0


def _source(row: dict) -> str:
    if row.get("source") not in SOURCES: _fail("SOURCE_INVALID")
    return row["source"]


def _validate(data: dict) -> tuple[dict, dict, dict, dict, dict, set]:
    if not isinstance(data, dict): _fail("ROOT_OBJECT_REQUIRED")
    if data.get("schema") != "B3_INPUT_V1_PROPOSED": _fail("SCHEMA_INVALID")
    for key in ("meets", "races", "locks", "results", "summaries"):
        if not isinstance(data.get(key), list): _fail("ARRAY_REQUIRED")
    if len(data["meets"]) != 4: _fail("EXACTLY_FOUR_CONFIGURED_MEETS_REQUIRED")
    meets = {}
    for row in data["meets"]:
        if not isinstance(row, dict) or not isinstance(row.get("meet_id"), str) or not row["meet_id"]: _fail("MEET_ID_INVALID")
        if row["meet_id"] in meets: _fail("MEET_DUPLICATE")
        first, last = _day(row.get("start_date")), _day(row.get("end_date"))
        if first > last: _fail("MEET_RANGE_INVALID")
        meets[row["meet_id"]] = row
    ordered = sorted((_day(m["start_date"]), _day(m["end_date"])) for m in meets.values())
    if any(previous[1] >= current[0] for previous, current in zip(ordered, ordered[1:])): _fail("MEET_DATE_RANGES_OVERLAP")
    races = {}
    for row in data["races"]:
        if not isinstance(row, dict): _fail("RACE_OBJECT_REQUIRED")
        rid = row.get("race_id")
        match = RACE.fullmatch(rid) if isinstance(rid, str) else None
        if match is None or rid in races: _fail("RACE_ID_INVALID_OR_DUPLICATE")
        day = _day(row.get("date"))
        if day.strftime("%Y%m%d") != match.group(1): _fail("RACE_DATE_ID_MISMATCH")
        if not isinstance(row.get("meet_id"), str): _fail("MEET_ID_INVALID")
        meet = meets.get(row.get("meet_id"))
        if meet is None or not _day(meet["start_date"]) <= day <= _day(meet["end_date"]): _fail("RACE_MEET_DATE_MISMATCH")
        if row.get("scheduled") is not True: _fail("OFFICIAL_SCHEDULE_SCOPE_REQUIRED")
        if _time(row.get("deadline")).date() != day: _fail("DEADLINE_DATE_MISMATCH")
        races[rid] = row
    locks, results, summaries = defaultdict(list), defaultdict(list), defaultdict(list)
    ids = Counter()
    for kind, target in (("locks", locks), ("results", results), ("summaries", summaries)):
        for row in data[kind]:
            if not isinstance(row, dict) or not isinstance(row.get("record_id"), str) or not row["record_id"]: _fail("RECORD_ID_INVALID")
            if not isinstance(row.get("race_id"), str) or row.get("race_id") not in races: _fail("RECORD_OUTSIDE_CONFIGURED_RACE_SCOPE")
            ids[row["record_id"]] += 1
            key = row["race_id"] if kind == "results" else (row["race_id"], _source(row))
            target[key].append(row)
    return meets, races, locks, results, summaries, {key for key, n in ids.items() if n > 1}


def _miss_label(lock: dict, order: list[int], hit: bool) -> str:
    if hit: return "HIT"
    audit = lock.get("selection_audit")
    if not isinstance(audit, dict) or audit.get("verification") != "VERIFIED" or audit.get("predeadline_verified") is not True or audit.get("coverage_complete") is not True:
        return "UNSPECIFIED_INSUFFICIENT_EVIDENCE"
    def candidates(value):
        return isinstance(value, list) and all(type(x) is int and 1 <= x <= 6 for x in value) and len(value) == len(set(value))
    a, b, c = order
    first = audit.get("first_candidates")
    if not candidates(first): return "UNSPECIFIED_INSUFFICIENT_EVIDENCE"
    if a not in first: return "FIRST_CANDIDATE_COVERAGE_MISS"
    second_map = audit.get("second_candidates_by_first")
    second = second_map.get(str(a)) if isinstance(second_map, dict) else None
    if not candidates(second): return "UNSPECIFIED_INSUFFICIENT_EVIDENCE"
    if b not in second: return "SECOND_CANDIDATE_COVERAGE_MISS"
    third_map = audit.get("third_candidates_by_pair")
    third = third_map.get(f"{a}-{b}") if isinstance(third_map, dict) else None
    if not candidates(third): return "UNSPECIFIED_INSUFFICIENT_EVIDENCE"
    if c not in third: return "THIRD_CANDIDATE_COVERAGE_MISS"
    return "FIVE_TICKET_SELECTION_MISS"


def _evaluate(race: dict, source: str, locks: list, results: list, summaries: list, collisions: set, coverage: dict) -> dict:
    row = {"race_id": race["race_id"], "source": source, "meet_id": race["meet_id"], "date": race["date"],
           "valid_N": False, "monetary_N": False, "status": "UNVERIFIED", "issues": [],
           "existing_LOCK_validity": None, "timing_observation": "UNVERIFIED", "hit": None,
           "stake_yen": None, "payout_yen": None, "refund_yen": None,
           "gross_return_rate": None, "net_ROI": None, "miss_label": "UNSPECIFIED_INSUFFICIENT_EVIDENCE"}
    issues = row["issues"]
    if coverage.get("schedule") != "VERIFIED_COMPLETE": issues.append("SCHEDULE_COVERAGE_UNVERIFIED")
    for name, key, records in (("LOCK", "locks", locks), ("RESULT", "results", results), ("SUMMARY", "summaries", summaries)):
        declared = coverage.get(key)
        complete = (declared.get(source) if isinstance(declared, dict) else declared) == "VERIFIED_COMPLETE"
        if not complete: issues.append(name+"_READ_UNVERIFIED")
        if not records: issues.append(name + ("_MISSING" if complete else "_NOT_OBSERVED_UNVERIFIED"))
        elif len(records) > 1: issues.append(name + "_DUPLICATE")
    if issues: return row
    lock, result, summary = locks[0], results[0], summaries[0]
    if any(rec["record_id"] in collisions for rec in (lock, result, summary)): issues.append("RECORD_ID_COLLISION")
    row["existing_LOCK_validity"] = lock.get("existing_LOCK_validity", "UNVERIFIED")
    if row["existing_LOCK_validity"] != "VALID": issues.append("EXISTING_LOCK_NOT_VERIFIED_VALID")
    if lock.get("existing_deadline_verdict") != "PASS": issues.append("UPSTREAM_PREDEADLINE_NOT_VERIFIED")
    if lock.get("payload_hash_verified") is not True: issues.append("LOCK_HASH_UNVERIFIED")
    if lock.get("saved_readback_verified") is not True: issues.append("LOCK_READBACK_UNVERIFIED")
    try:
        observed, saved, deadline = _time(lock.get("observed_at")), _time(lock.get("saved_at")), _time(race["deadline"])
    except InputError:
        issues.append("LOCK_TIME_UNVERIFIED")
    else:
        if observed > saved: issues.append("LOCK_TIME_ORDER_INCONSISTENT")
        before = observed < deadline and saved < deadline
        row["timing_observation"] = "BOTH_BEFORE" if before else "AT_OR_AFTER_DEADLINE"
        if not before: issues.append("POSTDEADLINE_OR_BOUNDARY_OBSERVATION")
        if lock.get("existing_deadline_verdict") == "PASS" and not before: issues.append("UPSTREAM_TIME_CONTRADICTION")
    if not _tickets(lock.get("tickets")): issues.append("FIVE_UNIQUE_ORDERED_TICKETS_INVALID")
    if result.get("status") != "FINAL" or result.get("official_result_verified") is not True: issues.append("RESULT_NOT_VERIFIED_FINAL")
    if not _triple(result.get("order")): issues.append("RESULT_ORDER_INVALID")
    if summary.get("lock_record_id") != lock["record_id"] or summary.get("result_record_id") != result["record_id"]: issues.append("SUMMARY_LINK_MISMATCH")
    if summary.get("verification") != "VERIFIED": issues.append("SUMMARY_UNVERIFIED")
    if issues: return row
    hit = result["order"] in lock["tickets"]
    if type(summary.get("hit")) is not bool or summary["hit"] != hit:
        issues.append("SUMMARY_HIT_MISMATCH_OR_UNKNOWN")
        return row
    row.update(valid_N=True, status="VALID_HIT_ANALYSIS", hit=hit, miss_label=_miss_label(lock, result["order"], hit), stake_yen=500)
    payout_unit = result.get("payout_yen_per_100")
    refunded = result.get("refunded_combinations")
    if not _money(payout_unit) or not isinstance(refunded, list) or result.get("refund_evidence_verified") is not True:
        issues.append("MONETARY_DATA_UNVERIFIED")
        return row
    if not all(_triple(ticket) for ticket in refunded) or len(refunded) != len({tuple(t) for t in refunded}):
        issues.append("REFUND_COMBINATIONS_INVALID")
        return row
    refunds = [i for i, ticket in enumerate(lock["tickets"]) if ticket in refunded]
    if hit and lock["tickets"].index(result["order"]) in refunds:
        issues.append("WINNING_TICKET_REFUND_CONFLICT")
        return row
    payout = payout_unit if hit else 0
    refund = 100 * len(refunds)
    expected_money = {"stake_yen":500, "payout_yen":payout, "refund_yen":refund}
    if any(not _money(summary.get(k)) for k in expected_money):
        issues.append("SUMMARY_MONEY_UNVERIFIED")
        return row
    if any(summary[k] != value for k, value in expected_money.items()):
        issues.append("SUMMARY_MONETARY_MISMATCH")
        return row
    row.update(monetary_N=True, payout_yen=payout, refund_yen=refund,
               gross_return_rate=(payout+refund)/500, net_ROI=(payout+refund-500)/500)
    return row


def _aggregate(rows: list[dict]) -> dict:
    valid = [r for r in rows if r["valid_N"]]
    monetary = [r for r in rows if r["monetary_N"]]
    stake = sum(r["stake_yen"] for r in monetary)
    payout = sum(r["payout_yen"] for r in monetary)
    refund = sum(r["refund_yen"] for r in monetary)
    n = len(valid)
    return {"scheduled_opportunities":len(rows), "valid_N":n, "excluded_or_unverified_N":len(rows)-n,
            "hits":sum(r["hit"] for r in valid), "hit_rate":sum(r["hit"] for r in valid)/n if n else None,
            "monetary_N":len(monetary), "money_unverified_N":n-len(monetary),
            "monetary_scope":"ONLY_VALID_ROWS_WITH_FULL_VERIFIED_MONETARY_DATA",
            "stake_yen":stake if monetary else None, "payout_yen":payout if monetary else None,
            "refund_yen":refund if monetary else None,
            "gross_return_rate":(payout+refund)/stake if stake else None,
            "net_ROI":(payout+refund-stake)/stake if stake else None,
            "miss_labels":dict(Counter(r["miss_label"] for r in valid if not r["hit"])),
            "issue_counts_nonexclusive":dict(Counter(issue for r in rows for issue in r["issues"]))}


def inventory(data: dict) -> dict:
    """Analyze private data in the caller's environment; never reads a service."""
    meets, races, locks, results, summaries, collisions = _validate(data)
    coverage = data.get("read_coverage") if isinstance(data.get("read_coverage"),dict) else {}
    rows = [_evaluate(race, source, locks[(rid,source)], results[rid], summaries[(rid,source)], collisions, coverage)
            for rid, race in sorted(races.items()) for source in SOURCES]
    report = {"schema":"B3_REPORT_V1_PROPOSED", "scope":"FOUR_CONFIGURED_MEETS_OFFLINE_ONLY", "rows":rows,
              "sources":{}, "existing_LOCK_rules_modified":False, "input_origin_assertion":data.get("classification", "UNVERIFIED_CALLER_INPUT"),
              "miss_labels_are_causal_proof":False, "production_GO":False,
              "schedule_coverage_assertion":coverage.get("schedule","UNVERIFIED"),
              "provenance_warning":"Input verification flags are assertions by HQ14; this tool cannot establish timestamp, source or DB authenticity."}
    for source in SOURCES:
        selected = [r for r in rows if r["source"] == source]
        report["sources"][source] = {"cumulative":_aggregate(selected),
            "meets":{mid:_aggregate([r for r in selected if r["meet_id"]==mid]) for mid in meets},
            "months":{month:_aggregate([r for r in selected if r["date"][:7]==month]) for month in sorted({r['date'][:7] for r in selected})}}
    return report


def _pairs(items):
    obj={}
    for k,v in items:
        if k in obj: _fail("DUPLICATE_INPUT_JSON_KEY")
        obj[k]=v
    return obj


def main() -> int:
    parser=argparse.ArgumentParser(description="Offline B3 inventory; local input only, no external services.")
    parser.add_argument("input_json",type=Path)
    args=parser.parse_args()
    try:
        data=json.loads(args.input_json.read_text(encoding="utf-8"),object_pairs_hook=_pairs,parse_constant=lambda _: _fail("NONFINITE_INPUT_JSON"))
        print(json.dumps(inventory(data),ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2))
    except (InputError,UnicodeError,json.JSONDecodeError,OSError) as exc:
        code=str(exc) if isinstance(exc,InputError) else type(exc).__name__
        print(json.dumps({"status":"INPUT_REJECTED", "reason":code,"production_GO":False}))
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
