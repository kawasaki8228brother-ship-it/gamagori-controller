import json
import sqlite3
from pathlib import Path

import pytest

from sqlite_readonly_audit import SQLiteReadOnlyAuditor


def _create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE race_states (
                race_id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE idempotency_keys (
                idempotency_key TEXT PRIMARY KEY,
                event_uuid TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE shadow_events (
                event_uuid TEXT PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                race_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                deadline_version INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def test_snapshot_reads_counts_and_current_date_states(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)

    state_today = {
        "race_id": "20260929_GAM_01R",
        "status": "TERMINAL",
        "terminal_reason": "OFFICIALLY_CLOSED",
        "terminal_missed_reason": None,
        "official_deadline": "2026-09-29T15:00:00+09:00",
        "tracking_deadline": None,
        "deadline_version": 1,
        "last_checked_at": "2026-09-29T15:00:01+09:00",
        "last_successful_official_fetch_at": "2026-09-29T14:59:55+09:00",
        "consecutive_source_error_count": 0,
        "total_source_error_count": 2,
        "c_events": ["event-1"],
        "terminal_event_id": "terminal-1",
    }
    state_other_day = {
        "race_id": "20260928_GAM_01R",
        "status": "PENDING",
        "c_events": [],
    }

    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO race_states (race_id, data_json, updated_at) VALUES (?, ?, ?)",
            (
                state_today["race_id"],
                json.dumps(state_today),
                "2026-09-29 06:00:02",
            ),
        )
        conn.execute(
            "INSERT INTO race_states (race_id, data_json, updated_at) VALUES (?, ?, ?)",
            (
                state_other_day["race_id"],
                json.dumps(state_other_day),
                "2026-09-28 06:00:02",
            ),
        )
        conn.execute(
            "INSERT INTO idempotency_keys VALUES (?, ?, ?)",
            ("idem-1", "event-1", "2026-09-29 06:00:00"),
        )
        conn.execute(
            """
            INSERT INTO shadow_events (
                event_uuid, idempotency_key, race_id, event_type,
                payload_json, payload_hash, observed_at, deadline_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-1",
                "idem-1",
                "20260929_GAM_01R",
                "CLOSING_OBSERVATION",
                "{}",
                "hash",
                "2026-09-29T05:59:00+00:00",
                1,
                "2026-09-29 06:00:00",
            ),
        )

    snapshot = SQLiteReadOnlyAuditor(str(db)).snapshot("20260929")

    assert snapshot["audit_mode"] == "STRICT_READ_ONLY"
    assert snapshot["sqlite_open_mode"] == "mode=ro"
    assert snapshot["table_counts"] == {
        "race_states": 2,
        "idempotency_keys": 1,
        "shadow_events": 1,
    }
    assert snapshot["current_date_race_state_count"] == 1
    assert snapshot["current_date_race_states"][0]["race_id"] == "20260929_GAM_01R"
    assert snapshot["current_date_race_states"][0]["terminal_reason"] == "OFFICIALLY_CLOSED"
    assert snapshot["current_date_race_states"][0]["c_event_count"] == 1
    assert snapshot["current_date_shadow_event_counts"] == {"CLOSING_OBSERVATION": 1}


def test_readonly_connection_rejects_writes(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)
    auditor = SQLiteReadOnlyAuditor(str(db))

    with auditor._connect_ro() as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO idempotency_keys VALUES ('x', 'y', '2026-09-29 00:00:00')"
            )


def test_missing_database_is_not_created(tmp_path):
    db = tmp_path / "missing.db"
    auditor = SQLiteReadOnlyAuditor(str(db))

    with pytest.raises(sqlite3.OperationalError):
        auditor.snapshot("20260929")

    assert not db.exists()


def test_malformed_state_json_is_reported_without_crashing_snapshot(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)

    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO race_states (race_id, data_json, updated_at) VALUES (?, ?, ?)",
            ("20260929_GAM_02R", "{not-json", "2026-09-29 06:00:02"),
        )

    snapshot = SQLiteReadOnlyAuditor(str(db)).snapshot("20260929")
    state = snapshot["current_date_race_states"][0]

    assert "parse_error" in state
    assert state["updated_at"] == "2026-09-29 06:00:02"


@pytest.mark.parametrize("bad_date", ["2026-09-29", "2026092", "abcdefgh", ""])
def test_target_date_must_be_yyyymmdd(tmp_path, bad_date):
    db = tmp_path / "shadow.db"
    _create_db(db)

    with pytest.raises(ValueError):
        SQLiteReadOnlyAuditor(str(db)).snapshot(bad_date)
