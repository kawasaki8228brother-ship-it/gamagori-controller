"""Read one explicitly supplied private HTML file; print only a safe summary."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
from types import ModuleType

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
LEGACY_SHA256 = "db18b989b409479c508c6a24d685c523b011adecef86ae652e57eb343024f479"
CURRENT_SHA256 = "5bc001879c7df45dfa20086cfdecf8c3794349e391f3458a02bb1b53e64a3cf9"
MAX_LOCAL_BYTES = 8 * 1024 * 1024


def _safe_parse(function, text, day, expected):
    try:
        kwargs = {"expected_race_numbers": range(1, 13)} if expected else {}
        races = function(text, day, "LOCAL_PRIVATE_INPUT", "UNVERIFIED_CAPTURE_TIME", **kwargs)
        rows = [row.model_dump(mode="json") for row in races]
        return {"status": "ACCEPT", "records": rows}
    except Exception:
        return {"status": "REJECT_OR_UNVERIFIED", "records": None}


def compare_raw_bytes(raw, day, encoding="utf-8"):
    if not isinstance(raw, bytes):
        return {"status":"UNVERIFIED","reason":"INPUT_BYTES_REQUIRED","go":False,"raw_bytes":None,"raw_sha256":None}
    summary = {"status": "UNVERIFIED", "go": False, "official_compatibility": "UNVERIFIED",
               "capture_time": "UNVERIFIED_NOT_PROVIDED", "raw_bytes": len(raw),
               "raw_sha256": hashlib.sha256(raw).hexdigest()}
    if not isinstance(day, str) or not re.fullmatch(r"[0-9]{8}", day):
        return dict(summary, reason="REQUESTED_DAY_UNVERIFIED")
    try:
        if dt.datetime.strptime(day, "%Y%m%d").strftime("%Y%m%d") != day:
            raise ValueError("DATE")
    except ValueError:
        return dict(summary, reason="REQUESTED_DAY_UNVERIFIED")
    if encoding not in ("utf-8", "shift_jis", "cp932", "euc_jp"):
        return dict(summary, reason="ENCODING_UNVERIFIED")
    try:
        text = raw.decode(encoding, errors="strict")
    except (UnicodeError, LookupError):
        return dict(summary, reason="ENCODING_UNVERIFIED")
    current_raw = (ROOT / "parsers.py").read_bytes()
    legacy_raw = (ROOT / "development/health_residuals_20261106_v003/references/parsers_8172aec.py.txt").read_bytes()
    if hashlib.sha256(current_raw).hexdigest() != CURRENT_SHA256 or hashlib.sha256(legacy_raw).hexdigest() != LEGACY_SHA256:
        return dict(summary, reason="REFERENCE_SHA_MISMATCH")
    sys.path.insert(0, str(ROOT))
    import parsers
    from development.health_offline_completion_v004.html_research import inspect_research_html
    legacy = ModuleType("_private_html_8172_parser")
    exec(compile(legacy_raw, "SHA_PINNED_PUBLIC_LEGACY_PARSER", "exec"), legacy.__dict__)
    old, current = _safe_parse(legacy.parse_race_index, text, day, False), _safe_parse(parsers.parse_race_index, text, day, True)
    def digest(rows):
        if rows is None:
            return None
        return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()
    def counts(rows):
        return None if rows is None else {"races": len(rows), "cancelled": sum(r["is_cancelled"] for r in rows),
                                         "closed": sum(r["is_closed"] for r in rows)}
    delta = {"same_acceptance": old["status"] == current["status"],
             "same_semantic_records": None if old["records"] is None or current["records"] is None else old["records"] == current["records"],
             "deadline_differences": None, "state_flag_differences": None}
    if old["records"] is not None and current["records"] is not None:
        a, b = ({r["race_id"]: r for r in result["records"]} for result in (old, current))
        common = set(a) & set(b)
        delta["deadline_differences"] = sum(a[k]["official_deadline"] != b[k]["official_deadline"] for k in common)
        delta["state_flag_differences"] = sum((a[k]["is_closed"], a[k]["is_cancelled"]) != (b[k]["is_closed"], b[k]["is_cancelled"]) for k in common)
    research = inspect_research_html(text, day)
    return dict(summary, status="OBSERVED_LOCAL_BYTES_ONLY", reason="COMPARISON_COMPLETED_NOT_COMPATIBILITY_PASS",
                reference_hashes_verified=True,
                old={"status": old["status"], "counts": counts(old["records"]), "semantic_sha256": digest(old["records"])},
                v003={"status": current["status"], "counts": counts(current["records"]), "semantic_sha256": digest(current["records"])},
                differences=delta,
                research={"status": research["status"], "reason": research["reason"], "policy_status": research["policy_status"],
                          "candidate_table_count": research["candidate_table_count"], "normalization": research["normalization"],
                          "runtime_execution_allowed": False})


def inspect_private_file(path, day, encoding="utf-8"):
    empty = {"status": "BLOCKED_EXTERNAL", "reason": "PRIVATE_HTML_NOT_SUPPLIED", "go": False,
             "official_compatibility": "UNVERIFIED"}
    if path is None:
        return empty
    selected = Path(path)
    if selected.suffix.lower() not in (".html", ".htm"):
        return dict(empty, status="UNVERIFIED", reason="HTML_FILE_EXTENSION_REQUIRED")
    descriptor = None
    try:
        if selected.is_symlink():
            return dict(empty, status="UNVERIFIED", reason="SYMLINK_INPUT_NOT_ALLOWED")
        descriptor = os.open(selected, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return dict(empty, status="UNVERIFIED", reason="REGULAR_FILE_REQUIRED")
        if before.st_size > MAX_LOCAL_BYTES:
            return dict(empty, status="UNVERIFIED", reason="LOCAL_SIZE_LIMIT_NO_READ", raw_bytes=before.st_size)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(MAX_LOCAL_BYTES + 1)
            after = os.fstat(handle.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != before.st_size:
            return dict(empty, status="UNVERIFIED", reason="INPUT_CHANGED_DURING_READ")
        return compare_raw_bytes(raw, day, encoding)
    except Exception:
        return dict(empty, status="UNVERIFIED", reason="PRIVATE_READ_OR_COMPARE_FAILED")
    finally:
        if descriptor is not None:
            os.close(descriptor)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Never echo invalid argument values, URLs or private paths.
        print(json.dumps({"status":"UNVERIFIED","reason":"ARGUMENTS_INVALID","go":False},sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    parser = SafeArgumentParser(description="Private local bytes only; no source collection or output files.")
    parser.add_argument("--private-html", type=Path)
    parser.add_argument("--date", default="")
    parser.add_argument("--encoding", default="utf-8", choices=["utf-8", "shift_jis", "cp932", "euc_jp"])
    args = parser.parse_args()
    answer = inspect_private_file(args.private_html, args.date, args.encoding)
    answer["runtime"] = {"python": platform.python_version(), "os": platform.system()}
    print(json.dumps(answer, sort_keys=True, ensure_ascii=True))
    raise SystemExit(3 if answer["status"] == "BLOCKED_EXTERNAL" else 0 if answer["status"] == "OBSERVED_LOCAL_BYTES_ONLY" else 2)
