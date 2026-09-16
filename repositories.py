from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

from models import EventRecord, RaceState


class BaselineRepository(ABC):
    @abstractmethod
    async def get_latest_baseline_ids(self, race_id: str) -> tuple[Optional[str], Optional[str]]:
        raise NotImplementedError


class MockBaselineRepository(BaselineRepository):
    async def get_latest_baseline_ids(self, race_id: str) -> tuple[Optional[str], Optional[str]]:
        return f"mock_A_{race_id}_v1", f"mock_B_{race_id}_v1"


class StateRepository(ABC):
    @abstractmethod
    async def get_race_state(self, race_id: str) -> Optional[RaceState]:
        raise NotImplementedError

    @abstractmethod
    async def save_race_state(self, state: RaceState) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_all_states(self) -> List[RaceState]:
        raise NotImplementedError


class SQLiteStateRepository(StateRepository):
    """Shadow state/event store. Durable only when db_path is on a persistent disk."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS race_states (
                    race_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    event_uuid TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shadow_events (
                    event_uuid TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    race_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    deadline_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    async def get_race_state(self, race_id: str) -> Optional[RaceState]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM race_states WHERE race_id = ?", (race_id,)
            ).fetchone()
            return RaceState.model_validate_json(row["data_json"]) if row else None

    async def save_race_state(self, state: RaceState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO race_states (race_id, data_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(race_id) DO UPDATE SET
                    data_json = excluded.data_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (state.race_id, state.model_dump_json()),
            )

    async def list_all_states(self) -> List[RaceState]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data_json FROM race_states ORDER BY race_id").fetchall()
            return [RaceState.model_validate_json(row["data_json"]) for row in rows]

    async def append_shadow_event_atomic(self, record: EventRecord) -> Tuple[bool, str, str]:
        """One connection + one transaction: duplicate check, idempotency registration, event insert."""
        payload_json = json.dumps(
            record.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT event_uuid FROM idempotency_keys WHERE idempotency_key = ?",
                (record.idempotency_key,),
            ).fetchone()
            if existing:
                conn.rollback()
                return True, "DUPLICATE_SKIPPED", existing["event_uuid"]

            conn.execute(
                "INSERT INTO idempotency_keys (idempotency_key, event_uuid) VALUES (?, ?)",
                (record.idempotency_key, record.event_uuid),
            )
            conn.execute(
                """
                INSERT INTO shadow_events (
                    event_uuid, idempotency_key, race_id, event_type,
                    payload_json, payload_hash, observed_at, deadline_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_uuid,
                    record.idempotency_key,
                    record.race_id,
                    record.event_type,
                    payload_json,
                    record.payload_hash,
                    record.observed_at,
                    record.deadline_version,
                ),
            )
            conn.commit()
            return True, "SHADOW_EVENT_PERSISTED", record.event_uuid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def list_shadow_events(self, race_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if race_id:
                rows = conn.execute(
                    "SELECT * FROM shadow_events WHERE race_id = ? ORDER BY created_at, rowid",
                    (race_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shadow_events ORDER BY created_at, rowid"
                ).fetchall()
            return [dict(row) for row in rows]
