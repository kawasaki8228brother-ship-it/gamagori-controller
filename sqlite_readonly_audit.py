from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteReadOnlyAuditor:
    """Strictly read-only diagnostics for the controller's persistent SQLite DB.

    The auditor opens SQLite with URI mode=ro. It never initializes schemas,
    changes PRAGMAs, or writes audit data back into the database.
    """

    TABLES = ("race_states", "idempotency_keys", "shadow_events")

    def __init__(self, db_path: str):
        self.db_path = str(db_path)

    def _connect_ro(self) -> sqlite3.Connection:
        path = Path(self.db_path).resolve()
        uri = f"{path.as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
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

    def snapshot(self, target_date_yyyymmdd: str) -> dict[str, Any]:
        if len(target_date_yyyymmdd) != 8 or not target_date_yyyymmdd.isdigit():
            raise ValueError("target_date_yyyymmdd must be YYYYMMDD")

        race_prefix = f"{target_date_yyyymmdd}_GAM_%"

        with self._connect_ro() as conn:
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

            table_counts = {
                table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
                for table in self.TABLES
            }

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

            journal_mode_row = conn.execute("PRAGMA journal_mode").fetchone()
            journal_mode = journal_mode_row[0] if journal_mode_row else None

        return {
            "audit_mode": "STRICT_READ_ONLY",
            "sqlite_open_mode": "mode=ro",
            "db_path": self.db_path,
            "target_date": target_date_yyyymmdd,
            "journal_mode": journal_mode,
            "table_counts": table_counts,
            "current_date_race_state_count": len(race_states),
            "current_date_race_states": race_states,
            "current_date_shadow_event_counts": current_date_event_counts,
        }
