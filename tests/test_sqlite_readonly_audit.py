import json
import sqlite3
from pathlib import Path

import pytest

from sqlite_readonly_audit import SQLiteReadOnlyAuditor


NOW_JST = "2026-09-29T14:00:00+09:00"


def _create_db(path: Path, *, journal_mode: str | None = None) -> None:
    with sqlite3.connect(path) as conn:
        if journal_mode is not None:
            actual = conn.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0]
            assert actual.lower() == journal_mode.lower()
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


def test_snapshot_reads_counts_times_file_metadata_and_current_date_states(tmp_path):
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

    snapshot = SQLiteReadOnlyAuditor(str(db)).snapshot(
        "20260929", process_now_jst=NOW_JST
    )

    assert snapshot["audit_mode"] == "STRICT_READ_ONLY"
    assert snapshot["snapshot_semantics"] == "POINT_IN_TIME_NOT_TRACE"
    assert snapshot["sqlite_open_mode"] == "mode=ro"
    assert snapshot["immutable"] is False
    assert snapshot["process_now_jst"] == NOW_JST
    assert snapshot["db_file_size_bytes"] > 0
    assert snapshot["db_file_mtime_ns"] > 0
    assert snapshot["db_file_mtime_utc"].endswith("+00:00")
    assert snapshot["busy_timeout_ms"] == 2500
    assert snapshot["table_counts"] == {
        "race_states": 2,
        "idempotency_keys": 1,
        "shadow_events": 1,
    }
    assert snapshot["current_date_race_state_count"] == 1
    assert snapshot["current_date_race_states"][0]["race_id"] == "20260929_GAM_01R"
    assert snapshot["current_date_race_states"][0]["terminal_reason"] == "OFFICIALLY_CLOSED"
    assert snapshot["current_date_race_states"][0]["last_checked_at"] == "2026-09-29T15:00:01+09:00"
    assert snapshot["current_date_race_states"][0]["updated_at"] == "2026-09-29 06:00:02"
    assert snapshot["current_date_race_states"][0]["c_event_count"] == 1
    assert snapshot["current_date_shadow_event_counts"] == {"CLOSING_OBSERVATION": 1}


def test_readonly_connection_rejects_writes(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)
    auditor = SQLiteReadOnlyAuditor(str(db))

    conn = auditor._connect_ro()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO idempotency_keys VALUES ('x', 'y', '2026-09-29 00:00:00')"
            )
    finally:
        conn.close()


def test_missing_database_is_not_created(tmp_path):
    db = tmp_path / "missing.db"
    auditor = SQLiteReadOnlyAuditor(str(db))

    with pytest.raises((sqlite3.OperationalError, FileNotFoundError)):
        auditor.snapshot("20260929", process_now_jst=NOW_JST)

    assert not db.exists()


def test_malformed_state_json_is_reported_without_crashing_snapshot(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)

    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO race_states (race_id, data_json, updated_at) VALUES (?, ?, ?)",
            ("20260929_GAM_02R", "{not-json", "2026-09-29 06:00:02"),
        )

    snapshot = SQLiteReadOnlyAuditor(str(db)).snapshot(
        "20260929", process_now_jst=NOW_JST
    )
    state = snapshot["current_date_race_states"][0]

    assert "parse_error" in state
    assert state["updated_at"] == "2026-09-29 06:00:02"


def test_wal_mode_with_writer_connection_open_allows_readonly_snapshot(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db, journal_mode="wal")

    writer = sqlite3.connect(db, timeout=2.5)
    try:
        actual = writer.execute("PRAGMA journal_mode").fetchone()[0]
        assert actual.lower() == "wal"
        writer.execute(
            "INSERT INTO race_states (race_id, data_json, updated_at) VALUES (?, ?, ?)",
            (
                "20260929_GAM_03R",
                json.dumps(
                    {
                        "race_id": "20260929_GAM_03R",
                        "status": "PENDING",
                        "c_events": [],
                    }
                ),
                "2026-09-29 06:00:02",
            ),
        )
        writer.commit()

        snapshot = SQLiteReadOnlyAuditor(str(db), busy_timeout_ms=2500).snapshot(
            "20260929", process_now_jst=NOW_JST
        )

        assert snapshot["journal_mode"].lower() == "wal"
        assert snapshot["busy_timeout_ms"] == 2500
        assert snapshot["current_date_race_state_count"] == 1
        assert snapshot["current_date_race_states"][0]["race_id"] == "20260929_GAM_03R"
    finally:
        writer.close()


def test_readonly_connection_is_explicitly_short_lived(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)
    auditor = SQLiteReadOnlyAuditor(str(db))

    snapshot = auditor.snapshot("20260929", process_now_jst=NOW_JST)
    assert snapshot["audit_mode"] == "STRICT_READ_ONLY"

    # A fresh writer should be able to open immediately after the snapshot.
    with sqlite3.connect(db, timeout=0.1) as conn:
        conn.execute(
            "INSERT INTO idempotency_keys VALUES ('after', 'snapshot', '2026-09-29 00:00:00')"
        )


@pytest.mark.parametrize("bad_date", ["2026-09-29", "2026092", "abcdefgh", ""])
def test_target_date_must_be_yyyymmdd(tmp_path, bad_date):
    db = tmp_path / "shadow.db"
    _create_db(db)

    with pytest.raises(ValueError):
        SQLiteReadOnlyAuditor(str(db)).snapshot(bad_date, process_now_jst=NOW_JST)


def test_busy_timeout_must_be_positive(tmp_path):
    db = tmp_path / "shadow.db"
    _create_db(db)

    with pytest.raises(ValueError):
        SQLiteReadOnlyAuditor(str(db), busy_timeout_ms=0)
