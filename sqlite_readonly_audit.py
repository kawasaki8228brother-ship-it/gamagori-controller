from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class SQLiteReadOnlyAuditor:
    """Point-in-time, strictly read-only diagnostics for the persistent SQLite DB.

    Safety invariants:
    - DB is opened with URI mode=ro.
    - immutable=1 is intentionally forbidden for a live database.
    - Connections are opened for one short snapshot and explicitly closed.
    - No schema creation, checkpoint, or database-mutating PRAGMA is executed.
    """

    TABLES = ("race_states", "idempotency_keys", "shadow_events")

    def __init__(self, db_path: str, *, busy_timeout_ms: int = 2500):
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be > 0")
        self.db_path = str(db_path)
        self.busy_timeout_ms = int(busy_timeout_ms)

    def _connect_ro(self) -> sqlite3.Connection:
        path = Path(self.db_path).resolve()
        # Do not add immutable=1. The production DB is live and can change.
        uri = f"{path.as_uri()}?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        # Connection-local timeout only; this does not mutate the database.
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        return conn

    @staticmethod
    def _safe_state(data_json: str, updated_at: str) -> dict[str, Any]:
        try:
            payload = json.loads(data_json)
        except Exception as exc:
            return {
                "parse_error": f"{type(exc).__name__}: {exc}",
                "updated_at": updated_at,
            }

        c_events = payload.get("c_events")
        return {
            "race_id": payload.get("race_id"),
            "status": payload.get("status"),
            "terminal_reason": payload.get("terminal_reason"),
            "terminal_missed_reason": payload.get("terminal_missed_reason"),
            "official_deadline": payload.get("official_deadline"),
            "tracking_deadline": payload.get("tracking_deadline"),
            "deadline_version": payload.get("deadline_version"),
            "last_checked_at": payload.get("last_checked_at"),
            "last_successful_official_fetch_at": payload.get(
                "last_successful_official_fetch_at"
            ),
            "consecutive_source_error_count": payload.get(
                "consecutive_source_error_count"
            ),
            "total_source_error_count": payload.get("total_source_error_count"),
            "c_event_count": len(c_events) if isinstance(c_events, list) else None,
            "terminal_event_id": payload.get("terminal_event_id"),
            "updated_at": updated_at,
        }

    def snapshot(
        self,
        target_date_yyyymmdd: str,
        *,
        process_now_jst: str,
    ) -> dict[str, Any]:
        if len(target_date_yyyymmdd) != 8 or not target_date_yyyymmdd.isdigit():
            raise ValueError("target_date_yyyymmdd must be YYYYMMDD")

        path = Path(self.db_path).resolve()
        stat = path.stat()  # Missing DB must fail; mode=ro must never create it.
        race_prefix = f"{target_date_yyyymmdd}_GAM_%"

        # This is intentionally one short-lived connection. isolation_level=None
        # avoids holding an explicit multi-query read transaction between queries.
        with closing(self._connect_ro()) as conn:
            existing_tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

            missing_tables = [name for name in self.TABLES if name not in existing_tables]
            if missing_tables:
                raise RuntimeError(
                    "required SQLite tables missing: " + ",".join(missing_tables)
                )

            journal_mode_row = conn.execute("PRAGMA journal_mode").fetchone()
            journal_mode = journal_mode_row[0] if journal_mode_row else None
            busy_timeout_row = conn.execute("PRAGMA busy_timeout").fetchone()
            busy_timeout_ms = busy_timeout_row[0] if busy_timeout_row else None

            table_counts = {}
            for table in self.TABLES:
                row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                table_counts[table] = int(row["n"])

            state_rows = conn.execute(
                """
                SELECT race_id, data_json, updated_at
                FROM race_states
                WHERE race_id LIKE ?
                ORDER BY race_id
                """,
                (race_prefix,),
            ).fetchall()
            race_states = [
                self._safe_state(row["data_json"], row["updated_at"]) for row in state_rows
            ]

            event_type_rows = conn.execute(
                """
                SELECT event_type, COUNT(*) AS n
                FROM shadow_events
                WHERE race_id LIKE ?
                GROUP BY event_type
                ORDER BY event_type
                """,
                (race_prefix,),
            ).fetchall()
            current_date_event_counts = {
                row["event_type"]: int(row["n"]) for row in event_type_rows
            }

        return {
            "audit_mode": "STRICT_READ_ONLY",
            "snapshot_semantics": "POINT_IN_TIME_NOT_TRACE",
            "sqlite_open_mode": "mode=ro",
            "immutable": False,
            "db_path": self.db_path,
            "db_file_size_bytes": stat.st_size,
            "db_file_mtime_ns": stat.st_mtime_ns,
            "db_file_mtime_utc": dt.datetime.fromtimestamp(
                stat.st_mtime, tz=dt.timezone.utc
            ).isoformat(),
            "process_now_jst": process_now_jst,
            "target_date": target_date_yyyymmdd,
            "journal_mode": journal_mode,
            "busy_timeout_ms": busy_timeout_ms,
            "table_counts": table_counts,
            "current_date_race_state_count": len(race_states),
            "current_date_race_states": race_states,
            "current_date_shadow_event_counts": current_date_event_counts,
        }
