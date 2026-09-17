import json
import sqlite3

import pytest
from pydantic import ValidationError

from airtable import DryRunAirtableAdapter
from models import (
    AppendOutcomeStatus,
    EventRecord,
    FailureClass,
    RaceState,
    RaceStatus,
    TerminalReason,
)
from repositories import SQLiteStateRepository


def _canonical(payload):
    return DryRunAirtableAdapter.generate_canonical_hash(payload)


def _insert_legacy_state(repo, race_id, *, reason="OFFICIALLY_CLOSED"):
    data = {
        "race_id": race_id,
        "status": "TERMINAL",
        "terminal_reason": reason,
        "terminal_event_id": None,
    }
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO race_states (race_id, data_json) VALUES (?, ?)",
            (race_id, json.dumps(data)),
        )


def _insert_legacy_event(
    repo,
    *,
    race_id,
    event_uuid,
    idempotency_key,
    event_type,
    deadline_version=1,
    payload=None,
):
    payload = payload or {"race_id": race_id, "event_type": event_type}
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_keys (idempotency_key, event_uuid) VALUES (?, ?)",
            (idempotency_key, event_uuid),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO shadow_events (
                event_uuid, idempotency_key, identity_hash, race_id, event_type,
                payload_json, payload_hash, observed_at, deadline_version
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_uuid,
                idempotency_key,
                race_id,
                event_type,
                payload_json,
                _canonical(payload),
                "2026-09-17T15:00:00+09:00",
                deadline_version,
            ),
        )


def test_pydantic_rejects_terminal_without_event_id():
    with pytest.raises(ValidationError, match="terminal_event_id"):
        RaceState(race_id="legacy-invalid", status=RaceStatus.TERMINAL)


@pytest.mark.asyncio
async def test_legacy_terminal_without_event_is_quarantined_instead_of_crashing(tmp_path):
    db_path = tmp_path / "legacy.db"
    repo = SQLiteStateRepository(str(db_path))
    rid = "20260916_GAM_01R"
    _insert_legacy_state(repo, rid)

    migrated = SQLiteStateRepository(str(db_path))
    state = await migrated.get_race_state(rid)

    assert state is not None
    assert state.status == RaceStatus.TERMINAL_FAILED
    assert state.terminal_event_id is None
    assert state.terminal_reason is None
    assert state.terminal_candidate_reason == TerminalReason.OFFICIALLY_CLOSED
    assert state.terminal_failure_class == FailureClass.NON_RETRYABLE
    assert state.terminal_failure_detail == "LEGACY_UNRECONCILABLE:NO_TERMINAL_EVENT"
    assert state.legacy_migration_disposition == "QUARANTINED_UNRECONCILABLE"
    assert state.legacy_reconciled is False
    assert state.pre_reconcile_status == "TERMINAL"
    assert state.pre_reconcile_terminal_reason == "OFFICIALLY_CLOSED"
    assert state.legacy_candidate_event_uuids == []


@pytest.mark.asyncio
async def test_legacy_terminal_reconcile_preserves_trace_and_adopts_event_reason(tmp_path):
    db_path = tmp_path / "legacy.db"
    repo = SQLiteStateRepository(str(db_path))
    rid = "20260916_GAM_02R"
    event_uuid = "legacy-terminal-event"

    # Deliberately make State and Event disagree: the persisted Event is canonical.
    _insert_legacy_state(repo, rid, reason="CANCELLED")
    _insert_legacy_event(
        repo,
        race_id=rid,
        event_uuid=event_uuid,
        idempotency_key=f"{rid}_TERMINAL_OFFICIALLY_CLOSED",
        event_type="RACE_TERMINAL",
        payload={
            "race_id": rid,
            "event_type": "RACE_TERMINAL",
            "terminal_reason": "OFFICIALLY_CLOSED",
            "terminal_missed_reason": None,
        },
    )

    migrated = SQLiteStateRepository(str(db_path))
    state = await migrated.get_race_state(rid)

    assert state is not None
    assert state.status == RaceStatus.TERMINAL
    assert state.terminal_event_id == event_uuid
    assert state.terminal_reason == TerminalReason.OFFICIALLY_CLOSED
    assert state.terminal_candidate_reason == TerminalReason.CANCELLED
    assert state.legacy_migration_disposition == "RECONCILED_TO_EVENT"
    assert state.legacy_reconciled is True
    assert state.legacy_reconciled_at is not None
    assert state.legacy_reconcile_source_uuid == event_uuid
    assert state.pre_reconcile_status == "TERMINAL"
    assert state.pre_reconcile_terminal_reason == "CANCELLED"
    assert state.legacy_candidate_event_uuids == [event_uuid]

    first_reconciled_at = state.legacy_reconciled_at

    # Migration must be idempotent across another process restart and must not erase provenance.
    migrated_again = SQLiteStateRepository(str(db_path))
    state_again = await migrated_again.get_race_state(rid)
    assert state_again.status == RaceStatus.TERMINAL
    assert state_again.terminal_event_id == event_uuid
    assert state_again.terminal_reason == TerminalReason.OFFICIALLY_CLOSED
    assert state_again.terminal_candidate_reason == TerminalReason.CANCELLED
    assert state_again.legacy_reconciled_at == first_reconciled_at
    assert state_again.legacy_reconcile_source_uuid == event_uuid


@pytest.mark.asyncio
async def test_legacy_terminal_multiple_events_is_quarantined_with_candidate_uuids(tmp_path):
    db_path = tmp_path / "legacy.db"
    repo = SQLiteStateRepository(str(db_path))
    rid = "20260916_GAM_04R"
    _insert_legacy_state(repo, rid)

    for suffix, reason in (("a", "OFFICIALLY_CLOSED"), ("b", "CANCELLED")):
        _insert_legacy_event(
            repo,
            race_id=rid,
            event_uuid=f"legacy-terminal-{suffix}",
            idempotency_key=f"{rid}_TERMINAL_{reason}_{suffix}",
            event_type="RACE_TERMINAL",
            payload={
                "race_id": rid,
                "event_type": "RACE_TERMINAL",
                "terminal_reason": reason,
            },
        )

    migrated = SQLiteStateRepository(str(db_path))
    state = await migrated.get_race_state(rid)

    assert state.status == RaceStatus.TERMINAL_FAILED
    assert state.legacy_migration_disposition == "QUARANTINED_UNRECONCILABLE"
    assert state.terminal_failure_detail == "LEGACY_UNRECONCILABLE:AMBIGUOUS_EVENT_COUNT:2"
    assert state.legacy_candidate_event_uuids == [
        "legacy-terminal-a",
        "legacy-terminal-b",
    ]


@pytest.mark.asyncio
async def test_legacy_terminal_invalid_event_reason_is_quarantined(tmp_path):
    db_path = tmp_path / "legacy.db"
    repo = SQLiteStateRepository(str(db_path))
    rid = "20260916_GAM_05R"
    _insert_legacy_state(repo, rid)
    _insert_legacy_event(
        repo,
        race_id=rid,
        event_uuid="legacy-terminal-invalid-reason",
        idempotency_key=f"{rid}_TERMINAL_BAD",
        event_type="RACE_TERMINAL",
        payload={
            "race_id": rid,
            "event_type": "RACE_TERMINAL",
            "terminal_reason": "NOT_A_REAL_REASON",
        },
    )

    migrated = SQLiteStateRepository(str(db_path))
    state = await migrated.get_race_state(rid)

    assert state.status == RaceStatus.TERMINAL_FAILED
    assert state.terminal_reason is None
    assert state.terminal_failure_detail == "LEGACY_UNRECONCILABLE:INVALID_EVENT_REASON"
    assert state.legacy_candidate_event_uuids == ["legacy-terminal-invalid-reason"]


@pytest.mark.asyncio
async def test_legacy_null_identity_closing_duplicate_is_semantically_verified(tmp_path):
    repo = SQLiteStateRepository(str(tmp_path / "legacy.db"))
    rid = "20260916_GAM_03R"
    key = f"{rid}_C_v1"
    existing_uuid = "legacy-closing-event"
    old_payload = {
        "schema_version": 1,
        "model_version": "v0.4.1_shadow",
        "controller_version": "v0.4.1",
        "race_id": rid,
        "event_type": "CLOSING_OBSERVATION",
        "deadline_version": 1,
    }
    _insert_legacy_event(
        repo,
        race_id=rid,
        event_uuid=existing_uuid,
        idempotency_key=key,
        event_type="CLOSING_OBSERVATION",
        deadline_version=1,
        payload=old_payload,
    )

    new_payload = {
        **old_payload,
        "model_version": "v0.5.0_shadow",
        "controller_version": "v0.5.0",
    }
    identity_hash = _canonical(
        {
            "event_type": "CLOSING_OBSERVATION",
            "race_id": rid,
            "deadline_version": 1,
        }
    )
    record = EventRecord(
        event_uuid="new-uuid-must-not-persist",
        idempotency_key=key,
        identity_hash=identity_hash,
        race_id=rid,
        event_type="CLOSING_OBSERVATION",
        deadline_version=1,
        payload=new_payload,
        observed_at="2026-09-17T15:00:30+09:00",
        official_deadline="2026-09-17T15:07:00+09:00",
        payload_hash=_canonical(new_payload),
    )

    outcome = await DryRunAirtableAdapter(repo).append_event(record)

    assert outcome.status == AppendOutcomeStatus.DUPLICATE_MATCH
    assert outcome.event_uuid == existing_uuid
    assert outcome.existing_identity_hash is None
    events = await repo.list_shadow_events(rid)
    assert len(events) == 1
    assert events[0]["event_uuid"] == existing_uuid


@pytest.mark.asyncio
async def test_missing_identity_hash_fails_closed_with_explicit_outcome(tmp_path):
    repo = SQLiteStateRepository(str(tmp_path / "state.db"))
    payload = {"race_id": "X", "event_type": "TEST"}
    record = EventRecord(
        event_uuid="x",
        idempotency_key="x",
        identity_hash="",
        race_id="X",
        event_type="TEST",
        payload=payload,
        observed_at="2026-09-17T15:00:00+09:00",
        official_deadline="",
        payload_hash=_canonical(payload),
    )

    outcome = await DryRunAirtableAdapter(repo).append_event(record)

    assert outcome.status == AppendOutcomeStatus.FAILED
    assert outcome.failure_class == FailureClass.NON_RETRYABLE
    assert outcome.message == "IDENTITY_HASH_MISSING"
    assert await repo.list_shadow_events("X") == []
