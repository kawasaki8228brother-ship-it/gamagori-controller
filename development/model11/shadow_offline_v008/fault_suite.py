"""Offline synthetic fault replay. No launch interface, network, or model changes.

Frozen baseline test vectors are re-executed and identified as such; they are not
new independent production evidence. Fixtures use new temporary stores only.
"""
from __future__ import annotations
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import sqlite3
import ssl
import tempfile
import types
import unittest

BASE_COMMIT = "148c156f472c874075a0b25d4f0b6b7e9fafdcfe"
PINS = {
    "runner": ("test_shadow_launch_runner.py", "5b70cc75b4a8cf536ebf4bef9a0b33401e0df1d146b82d8438bb0bd656553bf4"),
    "storage": ("test_shadow_launch_storage.py", "cfc46ff18ee3af34122fc8c19e8489642b84fca35f381976bdf72ff1917bed60"),
}
# Deliberately omit fork/process-kill vectors from this short resource-bounded suite.
VECTORS = (
    ("12R_PROBABILITY_BOX_RAW_RECEIPT", "runner", "ShadowRunnerTests", "test_twelve_races_have_immutable_separate_forecasts_and_consistent_boxes"),
    ("CONCURRENT_DUPLICATE_RESTART", "runner", "ShadowRunnerTests", "test_concurrent_duplicate_and_restart_cannot_publish_second_forecast"),
    ("NEAR_DEADLINE_MISSING", "runner", "ShadowRunnerTests", "test_missing_input_near_deadline_holds_without_imputation"),
    ("SOURCE_EXCEPTION_SECRET_SUPPRESSION", "runner", "ShadowRunnerTests", "test_source_exception_is_safe_hold_without_sensitive_exception_text"),
    ("AMBIGUOUS_PERSIST_STOP", "runner", "ShadowRunnerTests", "test_ambiguous_persist_failure_is_durable_stop_and_preserves_partial_files"),
    ("DELAY_CROSSES_DEADLINE", "runner", "ShadowRunnerTests", "test_deadline_crossed_during_persist_is_not_a_valid_forecast"),
    ("FUTURE_COURSE_FL_SCRATCH", "runner", "ShadowRunnerTests", "test_future_course_fl_and_scratch_evidence_are_not_used"),
    ("KNOWN_FL_NO_RULE_INVENTED", "runner", "ShadowRunnerTests", "test_known_fl_flag_is_preserved_without_inventing_a_new_disqualification_rule"),
    ("SCRATCH_FULL120_HOLD", "runner", "ShadowRunnerTests", "test_reduced_scratch_domain_holds_instead_of_claiming_full120"),
    ("DURABLE_OPERATOR_STOP", "runner", "ShadowRunnerTests", "test_operator_stop_is_durable_and_normal_shutdown_does_not_replay"),
    ("PENDING_SHUTDOWN_NO_REPLAY", "runner", "ShadowRunnerTests", "test_shutdown_with_owned_pending_reservation_requires_hold_not_replay"),
    ("RESULT_CORRECTION_APPEND_ONLY", "runner", "ShadowRunnerTests", "test_result_revisions_are_append_only_and_do_not_change_forecast_bytes"),
    ("DAILY_EXPLICIT_FINAL_SELECTION", "runner", "ShadowRunnerTests", "test_daily_settlement_requires_every_explicit_final_result_version"),
    ("EVERY_PERSIST_STAGE", "storage", "StoreTests", "test_fault_after_each_persist_preserves_and_stops"),
    ("CLOCK_FORWARD_DEADLINE", "storage", "StoreTests", "test_deadline_during_file_or_ledger_persist_invalidates"),
    ("CLOCK_BACKWARDS", "storage", "StoreTests", "test_clock_regression_before_ledger_is_hold"),
    ("TAMPER_READBACK_PRESERVED", "storage", "StoreTests", "test_tampered_forecast_detected_and_preserved"),
    ("NEW_FINAL_REQUIRES_RESELECTION", "storage", "ResultAndAuditTests", "test_sameclock_new_final_invalidates_selection_and_old_explicit_reselect_allowed"),
)


def load_pinned_fixture(kind):
    name, expected = PINS[kind]
    path = Path(__file__).resolve().parents[1] / "tests" / name
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError("FROZEN_FIXTURE_HASH_MISMATCH")
    module = types.ModuleType("pinned_synthetic_" + kind)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def run_frozen_vectors():
    loaded = {kind: load_pinned_fixture(kind) for kind in PINS}
    records = []
    for vector_id, kind, class_name, method in VECTORS:
        result = unittest.TestResult()
        getattr(loaded[kind], class_name)(method).run(result)
        passed = result.testsRun == 1 and result.wasSuccessful() and not result.skipped
        records.append({"id": vector_id, "status": "TESTED" if passed else "FAILED_OPEN",
                        "origin": "EXACT_BASELINE_TEST_REPLAY", "tests_run": result.testsRun,
                        "failures": len(result.failures), "errors": len(result.errors),
                        "skips": len(result.skipped), "raw_exception_text_exported": False})
    return records


def diagnose_clock_pair(wall_before, wall_after, monotonic_before, monotonic_after):
    """Observation only: no buffer threshold, clock setting, or runner integration."""
    try:
        first = datetime.fromisoformat(wall_before)
        last = datetime.fromisoformat(wall_after)
        if first.tzinfo is None or last.tzinfo is None:
            raise ValueError
        values = (monotonic_before, monotonic_after)
        if any(type(value) not in (float, int) or not math.isfinite(value) for value in values):
            raise ValueError
        wall = (last - first).total_seconds()
        mono = monotonic_after - monotonic_before
    except (ValueError, TypeError, OverflowError):
        return {"status": "HOLD", "reason": "CLOCK_EVIDENCE_INVALID", "go": False}
    reason = "MONOTONIC_REGRESSION" if mono < 0 else "WALL_BACKWARD" if wall < 0 else "WALL_MONOTONIC_DISAGREE" if wall != mono else "CONSISTENT_PAIR"
    return {"status": "OBSERVED", "reason": reason, "wall_delta_seconds": wall,
            "monotonic_delta_seconds": mono, "threshold_adopted": False, "go": False}


def classify_research_status(event):
    """New isolated classification only, not financial/terminal writer policy."""
    allowed = {"RESULT_CORRECTION", "TICKET_REFUND", "RACE_CANCELLED", "BOAT_SCRATCHED"}
    kind = event.get("kind") if isinstance(event, dict) else None
    if kind not in allowed or event.get("classification") != "SYNTHETIC_ONLY":
        return {"status": "HOLD", "reason": "EXPLICIT_SYNTHETIC_EVENT_REQUIRED", "go": False}
    blocked = kind in {"RACE_CANCELLED", "BOAT_SCRATCHED"}
    return {"status": "CLASSIFIED", "kind": kind, "settlement": "BLOCKED_EXTERNAL" if blocked else "EXPLICIT_EXISTING_CONTRACT_REQUIRED",
            "pnl_yen": None, "writer_integrated": False, "go": False}


def lost_ack_probe():
    """Commit bytes exist but acknowledgement is lost: preserve and stop, no replay."""
    fixture = load_pinned_fixture("runner")
    with tempfile.TemporaryDirectory(prefix="synthetic-ack-only-") as root:
        context = fixture.make_simulation_context(root)
        helper = fixture.ShadowRunnerTests()
        runner, store = helper.runner(context)
        original = store.commit
        def lost_ack(*args, **kwargs):
            answer = original(*args, **kwargs)
            if answer["status"] == "COMMITTED":
                raise OSError("SYNTHETIC_PRIVATE_ACK_ERROR_NOT_FOR_EXPORT")
            return answer
        store.commit = lost_ack
        report = runner.run_race(context["captures"][0])
        stopped = store.is_stopped()
        artifacts = sorted(path.name for path in (Path(root) / "third_research" / "artifacts").glob("*/*") if path.is_file())
        restart, new_store = helper.runner(context)
        after = restart.run_race(context["captures"][0])
        passed = report["status"] == "HOLD" and stopped and after["status"] == "HOLD" and set(artifacts) == {"input.raw", "forecast.raw", "receipt.json", "completion.json"}
        runner.shutdown()
        restart.shutdown()
        return {"id": "LOST_ACK_AFTER_COMPLETE_COMMIT", "status": "TESTED" if passed else "FAILED_OPEN",
                "runner_status": report["status"], "durable_stop": stopped,
                "restart_status": after["status"], "preserved_files": artifacts, "go": False}


def refund_probe():
    """Independent yen arithmetic expectations for two separate fixed portfolios."""
    from itertools import permutations
    from model11.metrics import _method_observation
    five = ["1-2-3", "1-2-4", "1-3-2", "2-1-3", "3-1-2"]
    box = ["-".join(map(str, triple)) for triple in permutations([1, 2, 3])]
    record = {"race_id": "SYNTHETIC-2099-REFUND", "target_date": "2099-01-07",
              "prediction_at": "2099-01-07T12:00:00+09:00", "source": "MODEL11_RESEARCH",
              "selection": {"tickets": five, "bet_decision": "BET"},
              "boxes": {"mechanical_research": {"boats": [1, 2, 3], "tickets": box, "bet_decision": "BET"}}}
    actual = {"payout_per_100": 1000, "refund_tickets": ["1-3-2"]}
    rows = {name: _method_observation(record, actual, "1-2-3", name)
            for name in ("five", "mechanical_research")}
    # Stake=5*100/6*100; one winning payout=1000, one returned ticket=100.
    expected = {"five": {"stake": 500, "refund": 100, "return": 1100, "net": 600},
                "mechanical_research": {"stake": 600, "refund": 100, "return": 1100, "net": 500}}
    matched = all(all(rows[name][field] == value for field, value in fields.items())
                  for name, fields in expected.items())
    unknown = _method_observation(record, {"payout_per_100": 1000}, "1-2-3", "five")
    contradictory_rejected = False
    try:
        _method_observation(record, {"payout_per_100": 1000, "refund_tickets": ["1-2-3"]}, "1-2-3", "five")
    except ValueError:
        contradictory_rejected = True
    passed = matched and unknown["net"] is None and contradictory_rejected
    return {"id": "SEPARATE_STAKES_EXPLICIT_REFUND", "status": "TESTED" if passed else "FAILED_OPEN",
            "methods": {name: {key: rows[name][key] for key in ("stake", "refund", "return", "net")} for name in rows},
            "missing_refund_not_zero": unknown["net"] is None,
            "winning_ticket_refund_rejected": contradictory_rejected,
            "combined_portfolio_pnl_created": False, "go": False}


def runtime():
    return {"python": platform.python_version(), "os": platform.platform(),
            "openssl": ssl.OPENSSL_VERSION, "sqlite": sqlite3.sqlite_version}


def run_fault_suite():
    records = run_frozen_vectors()
    records.extend((lost_ack_probe(), refund_probe()))
    return {"schema": "SHADOW_OFFLINE_FAULTS_V008", "base_commit": BASE_COMMIT,
            "environment": runtime(), "vectors": records,
            "status": "TESTED" if all(row["status"] == "TESTED" for row in records) else "FAILED_OPEN",
            "external_gates": ["OFFICIAL_CANCEL_SCRATCH_SETTLEMENT_CONTRACT", "REAL_HOST_CLOCK_AND_FILESYSTEM", "REVIEW_AND_INDIVIDUAL_GO"],
            "network": False, "shadow_started": False, "go": False}


if __name__ == "__main__":
    print(json.dumps(run_fault_suite(), ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
