"""New owned temporary roots only; no production DB, sources, or credentials."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model11.shadow_launch.storage import ShadowStore


NOW = datetime(2099, 1, 17, 12, tzinfo=timezone.utc)
DEADLINE = "2099-01-17T13:00:00+00:00"
RAW = b'{"classification":"SYNTHETIC_ONLY","race_id":"SYNTHETIC-2099-R1"}'
FORECAST = b'{"classification":"LANE2_RESEARCH_ONLY","tickets":["1-2-3"]}'
SHA = hashlib.sha256(RAW).hexdigest()
MODEL = "1" * 64
RACE = "SYNTHETIC-2099-R1"


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def _worker(root, barrier, queue):
    store = ShadowStore(root, clock=lambda: NOW)
    initialized = store.initialize()
    barrier.wait(timeout=20)
    if initialized["status"] != "READY":
        queue.put(initialized["status"])
        return
    reserved = store.reserve(RACE, SHA, MODEL, DEADLINE)
    if reserved["status"] == "RESERVED":
        queue.put(store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})["status"])
    else:
        queue.put(reserved["status"])


def _crash_worker(root, stage):
    def crash(point):
        if point == stage:
            os._exit(23)
    store = ShadowStore(root, clock=lambda: NOW, fault=crash)
    if store.initialize()["status"] != "READY":
        os._exit(24)
    reserved = store.reserve(RACE, SHA, MODEL, DEADLINE)
    if stage == "after_reserve":
        os._exit(23)
    store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
    os._exit(25)


def result_bytes(payout=1000, final=True, **extra):
    value = {"race_id": RACE, "target_date": "2099-01-17", "result": [1, 2, 3],
             "payout_per_100": payout, "refund_tickets": [], "final": final,
             "available_at": "2099-01-17T13:01:00+00:00"}
    value.update(extra)
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "owned-new-store"
        self.clock = Clock()
        self.store = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(self.store.initialize()["status"], "READY")

    def tearDown(self):
        self.temp.cleanup()

    def commit(self):
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        self.assertEqual(reserved["status"], "RESERVED")
        answer = self.store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
        self.assertEqual(answer["status"], "COMMITTED", answer)
        return reserved, answer

    def save_result(self, payout=1000, final=True):
        raw = result_bytes(payout, final)
        answer = self.store.save_result(RACE, raw, {"classification": "SYNTHETIC_ONLY"})
        self.assertEqual(answer["status"], "RESULT_SAVED", answer)
        return raw, answer["result_sha256"]

    def test_constructor_has_no_filesystem_or_sqlite_activity(self):
        path = Path(self.temp.name) / "never-created"
        with patch("builtins.open", side_effect=AssertionError("I/O")), patch("sqlite3.connect", side_effect=AssertionError("I/O")), patch.object(Path, "stat", side_effect=AssertionError("I/O")), patch.object(Path, "mkdir", side_effect=AssertionError("I/O")):
            candidate = ShadowStore(path)
        self.assertFalse(path.exists())
        self.assertFalse(candidate._initialized)

    def test_repeated_and_concurrent_initialize_keeps_reservation_session(self):
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.initialize(), range(16)))
        self.assertTrue(all(result["status"] == "READY" for result in results))
        self.assertEqual(reserved["session"], self.store._session)
        self.assertEqual(self.store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})["status"], "COMMITTED")

    def test_list_forecasts_scope_never_claims_official_completeness(self):
        self.commit()
        listed = self.store.list_forecasts()
        self.assertEqual(listed["status"], "FORECASTS_LISTED")
        self.assertEqual(listed["forecasts"], [{"race_id": RACE, "state": "COMMITTED", "deadline": DEADLINE}])
        self.assertEqual(listed["official_schedule_completeness"], "UNVERIFIED")

    def test_separate_immutable_raw_forecast_receipt_completion_and_readback(self):
        reserved, answer = self.commit()
        read = self.store.readback(RACE)
        self.assertEqual(read["input_raw"], RAW)
        self.assertEqual(read["forecast_raw"], FORECAST)
        self.assertEqual(read["receipt_sha256"], answer["receipt_sha256"])
        files = {path.name for path in (self.root / "artifacts" / reserved["key"]).iterdir()}
        self.assertEqual(files, {"input.raw", "forecast.raw", "receipt.json", "completion.json"})

    def test_commit_duplicate_idempotent_and_never_overwrites(self):
        reserved, answer = self.commit()
        self.clock.now += timedelta(hours=2)
        duplicate = self.store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
        self.assertEqual(duplicate["status"], "DUPLICATE")
        self.assertEqual(duplicate["receipt_sha256"], answer["receipt_sha256"])
        self.assertFalse(self.store.is_stopped())

    def test_model_update_same_race_is_duplicate_even_after_deadline(self):
        self.commit()
        self.clock.now += timedelta(hours=2)
        answer = self.store.reserve(RACE, SHA, "2" * 64, DEADLINE)
        self.assertEqual(answer["status"], "DUPLICATE")
        self.assertEqual(answer["receipt"]["model_sha256"], MODEL)

    def test_changed_input_same_race_conflict_and_durable_stop(self):
        self.commit()
        answer = self.store.reserve(RACE, "3" * 64, MODEL, DEADLINE)
        self.assertEqual(answer["status"], "CONFLICT")
        self.assertTrue(self.store.is_stopped())
        self.assertEqual(self.store.readback(RACE)["forecast_raw"], FORECAST)

    def test_forecast_conflict_does_not_modify_original_bytes(self):
        reserved, _ = self.commit()
        answer = self.store.commit(reserved, RAW, b"changed", {"generated_at": NOW.isoformat()})
        self.assertEqual(answer["status"], "CONFLICT")
        self.assertEqual(self.store.readback(RACE)["forecast_raw"], FORECAST)

    def test_pending_reservation_never_reissued_and_restart_token_rejected(self):
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        other = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(other.initialize()["status"], "READY")
        self.assertEqual(other.reserve(RACE, SHA, MODEL, DEADLINE)["status"], "HOLD")
        self.assertEqual(other.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})["status"], "HOLD_UNCERTAIN")
        self.assertTrue(other.is_stopped())

    def test_concurrent_threads_get_exactly_one_reservation(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            statuses = list(pool.map(lambda _: self.store.reserve(RACE, SHA, MODEL, DEADLINE)["status"], range(24)))
        self.assertEqual(statuses.count("RESERVED"), 1)
        self.assertEqual(statuses.count("HOLD"), 23)
        self.assertFalse(self.store.is_stopped())

    def test_cross_process_unique_and_readable_across_restart(self):
        ctx = multiprocessing.get_context("fork")
        barrier, queue = ctx.Barrier(5), ctx.Queue()
        processes = [ctx.Process(target=_worker, args=(str(self.root), barrier, queue)) for _ in range(5)]
        for process in processes:
            process.start()
        statuses = [queue.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(statuses.count("COMMITTED"), 1, statuses)
        self.assertTrue(all(status in ("COMMITTED", "HOLD", "DUPLICATE") for status in statuses), statuses)
        restart = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(restart.initialize()["status"], "READY")
        self.assertEqual(restart.readback(RACE)["forecast_raw"], FORECAST)

    def test_crash_cutpoints_recover_hold_without_replay(self):
        ctx = multiprocessing.get_context("fork")
        for stage in ("after_reserve", "commit_after_input", "commit_after_ledger"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "new"
                process = ctx.Process(target=_crash_worker, args=(str(root), stage))
                process.start()
                process.join(timeout=30)
                self.assertEqual(process.exitcode, 23)
                restart = ShadowStore(root, clock=self.clock)
                self.assertEqual(restart.initialize()["status"], "HOLD")
                self.assertTrue(restart.is_stopped())
                self.assertEqual(restart.reserve(RACE, SHA, MODEL, DEADLINE)["status"], "HOLD")

    def test_fault_after_each_persist_preserves_and_stops(self):
        for stage in ("commit_after_claim", "commit_after_input", "commit_after_forecast", "commit_after_receipt", "commit_before_ledger", "commit_after_ledger"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                def fault(point):
                    if point == stage:
                        raise OSError("Do not echo private failure text")
                store = ShadowStore(Path(directory) / "new", clock=self.clock, fault=fault)
                store.initialize()
                reserved = store.reserve(RACE, SHA, MODEL, DEADLINE)
                answer = store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
                self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
                self.assertTrue(store.is_stopped())
                self.assertNotIn("private failure", json.dumps(answer))
                self.assertEqual(store.readback(RACE)["status"], "HOLD")

    def test_deadline_during_file_or_ledger_persist_invalidates(self):
        for stage in ("commit_after_forecast", "commit_after_ledger"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                clock = Clock()
                def fault(point):
                    if point == stage:
                        clock.now = NOW + timedelta(hours=1)
                store = ShadowStore(Path(directory) / "new", clock=clock, fault=fault)
                store.initialize()
                reserved = store.reserve(RACE, SHA, MODEL, DEADLINE)
                answer = store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
                self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
                self.assertTrue(store.is_stopped())
                self.assertEqual(store.readback(RACE)["status"], "HOLD")

    def test_generation_later_than_clock_or_deadline_cannot_commit(self):
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        answer = self.store.commit(reserved, RAW, FORECAST, {"generated_at": "2099-01-17T12:30:00+00:00"})
        self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
        self.assertTrue(self.store.is_stopped())

    def test_invalid_offset_not_normalized_into_valid_deadline(self):
        for suffix in ("+08:60", "+24:00", "-01:99", "+09", "+09:00:00", "-00:00"):
            with self.subTest(offset=suffix):
                answer = self.store.reserve(RACE, SHA, MODEL, "2099-01-17T13:00:00" + suffix)
                self.assertEqual(answer["status"], "HOLD")
                self.assertEqual(self.store.list_forecasts()["forecasts"], [])

    def test_invalid_generation_offset_is_hold_not_datetime_normalization(self):
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        answer = self.store.commit(reserved, RAW, FORECAST, {"generated_at": "2099-01-17T12:00:00+08:60"})
        self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
        self.assertTrue(self.store.is_stopped())

    def test_clock_regression_before_ledger_is_hold(self):
        def fault(stage):
            if stage == "commit_before_ledger":
                self.clock.now = NOW - timedelta(minutes=1)
        self.store.fault = fault
        reserved = self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        answer = self.store.commit(reserved, RAW, FORECAST, {"generated_at": NOW.isoformat()})
        self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
        self.assertTrue(self.store.is_stopped())

    def test_namespace_cannot_silently_change_owned_root(self):
        wrong = ShadowStore(self.root, namespace="OTHER_RESEARCH", clock=self.clock)
        self.assertEqual(wrong.initialize()["status"], "STOP")

    def test_nonempty_unowned_root_and_symlink_are_not_adopted(self):
        other = Path(self.temp.name) / "not-owned"
        other.mkdir()
        (other / "keep.txt").write_bytes(b"must not change")
        self.assertEqual(ShadowStore(other).initialize()["status"], "STOP")
        self.assertEqual({path.name for path in other.iterdir()}, {"keep.txt"})
        link = Path(self.temp.name) / "link"
        link.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(ShadowStore(link).initialize()["status"], "STOP")

    def test_store_subfolder_symlink_is_stop(self):
        (self.root / "artifacts").rmdir()
        (self.root / "artifacts").symlink_to(self.temp.name, target_is_directory=True)
        self.assertEqual(self.store.reserve(RACE, SHA, MODEL, DEADLINE)["status"], "HOLD")

    def test_context_and_owner_identity_pin_persist(self):
        self.assertEqual(self.store.bind_context("a" * 64)["status"], "CONTEXT_PINNED")
        other = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(other.initialize()["storage_id"], self.store._storage_id)
        self.assertEqual(other.bind_context("a" * 64)["status"], "CONTEXT_PINNED")
        self.assertEqual(other.bind_context("b" * 64)["status"], "HOLD")
        self.assertTrue(other.is_stopped())

    def test_stop_persists_and_no_clear_or_new_writes(self):
        self.assertEqual(self.store.stop("SYNTHETIC_OPERATOR_STOP")["status"], "STOPPED")
        first = (self.root / "STOP.json").read_bytes()
        self.store.stop("OTHER_STOP")
        self.assertEqual((self.root / "STOP.json").read_bytes(), first)
        other = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(other.initialize()["status"], "HOLD")
        self.assertEqual(other.reserve(RACE, SHA, MODEL, DEADLINE)["status"], "HOLD")

    def test_close_with_reservation_preserves_hold_no_automatic_resume(self):
        self.store.reserve(RACE, SHA, MODEL, DEADLINE)
        self.assertEqual(self.store.close()["status"], "HOLD")
        self.assertTrue(self.store.is_stopped())

    def test_tampered_forecast_detected_and_preserved(self):
        reserved, _ = self.commit()
        file = self.root / "artifacts" / reserved["key"] / "forecast.raw"
        file.write_bytes(b"tamper fixture only")
        self.assertEqual(self.store.readback(RACE)["status"], "HOLD")
        self.assertTrue(self.store.is_stopped())
        self.assertEqual(file.read_bytes(), b"tamper fixture only")


class ResultAndAuditTests(unittest.TestCase):
    setUp = StoreTests.setUp
    tearDown = StoreTests.tearDown
    commit = StoreTests.commit
    save_result = StoreTests.save_result
    def test_append_results_duplicate_and_forecast_unchanged(self):
        self.commit()
        before = self.store.readback(RACE)
        self.clock.now = NOW + timedelta(hours=2)
        raw, sha = self.save_result()
        self.assertEqual(self.store.save_result(RACE, raw, {"classification": "SYNTHETIC_ONLY"})["status"], "RESULT_DUPLICATE")
        self.save_result(2000)
        listing = self.store.list_results(RACE)
        self.assertEqual(listing["final_count"], 2)
        self.assertEqual(len(listing["results"]), 2)
        self.assertEqual(self.store.read_result(RACE, sha)["raw_result"], raw)
        self.assertEqual(self.store.read_selected_result(RACE)["status"], "HOLD")
        after = self.store.readback(RACE)
        for field in ("input_raw", "forecast_raw", "receipt_sha256"):
            self.assertEqual(before[field], after[field])

    def test_sameclock_new_final_invalidates_selection_and_old_explicit_reselect_allowed(self):
        self.commit()
        self.clock.now += timedelta(hours=2)
        _, old = self.save_result(1000)
        self.assertEqual(self.store.select_result(RACE, old, {"explicit": True, "selection_id": "SYNTHETIC-SELECT-1"})["status"], "RESULT_SELECTED")
        # Find a later raw result whose hash sorts before old: lexicographic SHA
        # ordering must not substitute for insertion chronology.
        payout = next(p for p in range(1001, 2000) if hashlib.sha256(result_bytes(p)).hexdigest() < old)
        _, new = self.save_result(payout)
        self.assertLess(new, old)
        self.assertEqual(self.store.read_selected_result(RACE)["reason"], "NEWER_FINAL_REQUIRES_EXPLICIT_SELECTION")
        selected = self.store.select_result(RACE, old, {"explicit": True, "selection_id": "SYNTHETIC-SELECT-OLD-AFTER-REVIEW"})
        self.assertEqual(selected["selection_sequence"], 2)
        self.assertEqual(self.store.read_selected_result(RACE)["result_sha256"], old)

    def test_nonfinal_not_selectable(self):
        self.commit()
        self.clock.now += timedelta(hours=2)
        _, sha = self.save_result(final=False)
        self.assertEqual(self.store.select_result(RACE, sha, {"explicit": True, "selection_id": "SYNTHETIC-SELECT"})["status"], "HOLD")
        self.assertTrue(self.store.is_stopped())

    def test_result_in_future_or_before_deadline_rejected(self):
        self.commit()
        answer = self.store.save_result(RACE, result_bytes(), {})
        self.assertEqual(answer["status"], "HOLD")
        self.assertTrue(self.store.is_stopped())

    def test_result_failure_partial_bytes_preserved_on_restart(self):
        self.commit()
        self.clock.now += timedelta(hours=2)
        self.store.fault = lambda stage: (_ for _ in ()).throw(OSError("private")) if stage == "result_after_file" else None
        answer = self.store.save_result(RACE, result_bytes(), {})
        self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
        files = list((self.root / "results").rglob("*.raw"))
        self.assertEqual(len(files), 1)
        other = ShadowStore(self.root, clock=self.clock)
        self.assertEqual(other.initialize()["status"], "STOP")
        self.assertEqual(files[0].read_bytes(), result_bytes())

    def test_persistent_daily_reports_bind_explicit_result_selection(self):
        self.commit()
        self.clock.now += timedelta(hours=2)
        _, sha = self.save_result()
        self.store.select_result(RACE, sha, {"explicit": True, "selection_id": "SYNTHETIC-DAILY"})
        metadata = {"selected_results": {RACE: sha}}
        raw = b'{"classification":"SYNTHETIC_ONLY","ledger":"standalone"}'
        saved = self.store.save_audit_report("DAILY_SETTLEMENT", "2099-01-17", raw, metadata)
        self.assertEqual(saved["status"], "AUDIT_SAVED", saved)
        duplicate = self.store.save_audit_report("DAILY_SETTLEMENT", "2099-01-17", raw, metadata)
        self.assertEqual(duplicate["status"], "AUDIT_DUPLICATE")
        checked = self.store.read_audit_report("DAILY_SETTLEMENT", "2099-01-17", saved["report_sha256"])
        self.assertEqual(checked["raw_report"], raw)
        self.assertEqual(checked["receipt"]["selected_results"], {RACE: sha})
        second = self.store.save_audit_report("DAILY_SETTLEMENT", "2099-01-17", raw + b"\n", metadata)
        self.assertEqual(second["status"], "AUDIT_SAVED")
        self.assertNotEqual(second["report_sha256"], saved["report_sha256"])
        self.assertEqual(self.store.read_audit_report("DAILY_SETTLEMENT", "2099-01-17", saved["report_sha256"])["raw_report"], raw)

    def test_daily_report_missing_or_wrong_selection_never_saved(self):
        self.commit()
        answer = self.store.save_audit_report("DAILY_SETTLEMENT", "2099-01-17", b"{}", {})
        self.assertEqual(answer["status"], "HOLD")
        self.assertTrue(self.store.is_stopped())
        self.assertEqual(list((self.root / "audits").rglob("*.raw")), [])

    def test_operations_audit_is_separate_append_only(self):
        saved = self.store.save_audit_report("OPERATIONS_AUDIT", "SYNTHETIC-STOP-DRILL", b'{"drill":true}')
        self.assertEqual(saved["status"], "AUDIT_SAVED")
        self.assertEqual(self.store.read_audit_report("OPERATIONS_AUDIT", "SYNTHETIC-STOP-DRILL", saved["report_sha256"])["raw_report"], b'{"drill":true}')

    def test_audit_fault_preserves_partial_or_complete_evidence_and_stops(self):
        for stage in ("audit_after_file", "audit_after_ledger"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                def fault(point):
                    if point == stage:
                        raise OSError("not echoed")
                store = ShadowStore(Path(directory) / "new", clock=self.clock, fault=fault)
                self.assertEqual(store.initialize()["status"], "READY")
                answer = store.save_audit_report("OPERATIONS_AUDIT", "SYNTHETIC-DRILL", b'{"drill":true}')
                self.assertEqual(answer["status"], "HOLD_UNCERTAIN")
                self.assertTrue(store.is_stopped())
                self.assertEqual(len(list((store.root / "audits").rglob("*.raw"))), 1)


if __name__ == "__main__":
    unittest.main()
