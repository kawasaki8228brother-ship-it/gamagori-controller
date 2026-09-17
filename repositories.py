from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from models import (
    AppendOutcome,
    AppendOutcomeStatus,
    EventRecord,
    FailureClass,
    RaceState,
    RaceStatus,
)

logger = logging.getLogger("gamagori-controller")


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
                    identity_hash TEXT,
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
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(shadow_events)").fetchall()
            }
            if "identity_hash" not in columns:
                conn.execute("ALTER TABLE shadow_events ADD COLUMN identity_hash TEXT")

            self._migrate_legacy_terminal_states(conn)

    @staticmethod
    def _quarantine_legacy_terminal(data: dict, detail: str) -> dict:
        candidate_reason = data.get("terminal_candidate_reason") or data.get("terminal_reason")
        data["status"] = RaceStatus.TERMINAL_FAILED.value
        data["terminal_candidate_reason"] = candidate_reason
        data["terminal_reason"] = None
        data["terminal_event_id"] = None
        data["terminal_failure_class"] = FailureClass.NON_RETRYABLE.value
        data["terminal_failure_detail"] = detail
        return data

    def _migrate_legacy_terminal_states(self, conn: sqlite3.Connection) -> None:
        """Make pre-P0 TERMINAL rows safe before Pydantic load validation runs.

        A legacy TERMINAL row without terminal_event_id is reconciled to its sole persisted
        RACE_TERMINAL Event when that linkage is unambiguous. Otherwise the row is quarantined
        as TERMINAL_FAILED with a critical log instead of crashing worker startup.
        """
        rows = conn.execute(
            "SELECT race_id, data_json FROM race_states ORDER BY race_id"
        ).fetchall()
        for row in rows:
            try:
                data = json.loads(row["data_json"])
            except json.JSONDecodeError:
                logger.critical(
                    "[%s] LEGACY_STATE_JSON_INVALID; row left unchanged for explicit investigation",
                    row["race_id"],
                )
                continue

            if (
                data.get("status") != RaceStatus.TERMINAL.value
                or data.get("terminal_event_id")
            ):
                continue

            terminal_events = conn.execute(
                """
                SELECT event_uuid, payload_json
                FROM shadow_events
                WHERE race_id = ? AND event_type = 'RACE_TERMINAL'
                ORDER BY created_at, rowid
                """,
                (row["race_id"],),
            ).fetchall()

            if len(terminal_events) == 1:
                existing = terminal_events[0]
                data["terminal_event_id"] = existing["event_uuid"]
                try:
                    payload = json.loads(existing["payload_json"])
                except json.JSONDecodeError:
                    payload = {}
                if payload.get("terminal_reason"):
                    data["terminal_reason"] = payload["terminal_reason"]
                conn.execute(
                    "UPDATE race_states SET data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE race_id = ?",
                    (
                        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                        row["race_id"],
                    ),
                )
                logger.warning(
                    "[%s] LEGACY_TERMINAL_RECONCILED event_uuid=%s",
                    row["race_id"],
                    existing["event_uuid"],
                )
                continue

            detail = (
                "LEGACY_TERMINAL_WITHOUT_EVENT"
                if not terminal_events
                else f"LEGACY_TERMINAL_EVENT_AMBIGUOUS:{len(terminal_events)}"
            )
            data = self._quarantine_legacy_terminal(data, detail)
            conn.execute(
                "UPDATE race_states SET data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE race_id = ?",
                (
                    json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    row["race_id"],
                ),
            )
            logger.critical(
                "[%s] %s; quarantined as TERMINAL_FAILED",
                row["race_id"],
                detail,
            )

    async def get_race_state(self, race_id: str) -> Optional[RaceState]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM race_states WHERE race_id = ?", (race_id,)
            ).fetchone()
            return RaceState.model_validate_json(row["data_json"]) if row else None

    async def save_race_state(self, state: RaceState) -> None:
        if state.status == RaceStatus.TERMINAL and not state.terminal_event_id:
            raise ValueError("Refusing to persist TERMINAL without terminal_event_id")
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

    @staticmethod
    def _legacy_identity_matches(row: sqlite3.Row, record: EventRecord) -> bool:
        """Backward compatibility for pre-P0 rows that have no identity_hash.

        Closing identity is exactly race_id + event_type + deadline_version, all of which were
        already persisted as structured columns before identity_hash existed. A legacy row is
        therefore semantically verifiable for that event class rather than merely assumed equal.
        """
        return (
            row["race_id"] == record.race_id
            and row["event_type"] == record.event_type
            and int(row["deadline_version"]) == record.deadline_version
        )

    async def append_shadow_event_atomic(self, record: EventRecord) -> AppendOutcome:
        """One transaction: duplicate lookup, semantic comparison, key registration, event insert."""
        payload_json = json.dumps(
            record.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT event_uuid, idempotency_key, identity_hash, race_id, event_type,
                       payload_json, payload_hash, observed_at, deadline_version
                FROM shadow_events
                WHERE idempotency_key = ?
                """,
                (record.idempotency_key,),
            ).fetchone()
            if existing:
                existing_payload = json.loads(existing["payload_json"])
                existing_identity_hash = existing["identity_hash"]
                if existing_identity_hash is None:
                    semantic_match = self._legacy_identity_matches(existing, record)
                else:
                    semantic_match = existing_identity_hash == record.identity_hash
                conn.rollback()
                return AppendOutcome(
                    status=(
                        AppendOutcomeStatus.DUPLICATE_MATCH
                        if semantic_match
                        else AppendOutcomeStatus.DUPLICATE_CONFLICT
                    ),
                    event_uuid=existing["event_uuid"],
                    message=(
                        "DUPLICATE_MATCH"
                        if semantic_match
                        else "DUPLICATE_CONFLICT"
                    ),
                    existing_payload=existing_payload,
                    existing_payload_hash=existing["payload_hash"],
                    existing_identity_hash=existing_identity_hash,
                )

            conn.execute(
                "INSERT INTO idempotency_keys (idempotency_key, event_uuid) VALUES (?, ?)",
                (record.idempotency_key, record.event_uuid),
            )
            conn.execute(
                """
                INSERT INTO shadow_events (
                    event_uuid, idempotency_key, identity_hash, race_id, event_type,
                    payload_json, payload_hash, observed_at, deadline_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_uuid,
                    record.idempotency_key,
                    record.identity_hash,
                    record.race_id,
                    record.event_type,
                    payload_json,
                    record.payload_hash,
                    record.observed_at,
                    record.deadline_version,
                ),
            )
            conn.commit()
            return AppendOutcome(
                status=AppendOutcomeStatus.CREATED,
                event_uuid=record.event_uuid,
                message="SHADOW_EVENT_PERSISTED",
            )
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