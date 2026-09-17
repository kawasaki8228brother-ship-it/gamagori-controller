import datetime as dt
from pathlib import Path

import pytest

from airtable import AirtableAdapter, DryRunAirtableAdapter
from models import (
    AppendOutcome,
    AppendOutcomeStatus,
    EventRecord,
    FailureClass,
    JST,
    LiveDataCompleteness,
    MissedObservationReason,
    OfficialRaceInfo,
    RaceState,
    RaceStatus,
    SourceEvidence,
    TerminalReason,
)
from repositories import MockBaselineRepository, SQLiteStateRepository
from state_machine import RaceStateMachine


class FakeFetcher:
    def __init__(self, complete=True):
        self.complete = complete

    async def fetch_live_data(self, race_id):
        if not self.complete:
            return LiveDataCompleteness(is_complete=False, missing_fields=["odds_3t"])
        return LiveDataCompleteness(
            is_complete=True,
            exhibition_times={i: 6.7 + i / 100 for i in range(1, 7)},
            entry_courses={i: i for i in range(1, 7)},
            start_exhibition_st={i: 0.10 for i in range(1, 7)},
            weather_info={"wind_speed_m": 2.0},
            odds_3t={"1-2-3": 4.5},
            source_evidence={
                "beforeinfo": SourceEvidence(url="u", acquired_at="t", status="OK")
            },
        )


class FixedFailureAdapter(AirtableAdapter):
    def __init__(self, failure_class=FailureClass.UNKNOWN, message="TEST_FAILURE"):
        self.failure_class = failure_class
        self.message = message

    async def append_event(self, record):
        return AppendOutcome(
            status=AppendOutcomeStatus.FAILED,
            failure_class=self.failure_class,
            message=self.message,
        )


class FlakyAdapter(AirtableAdapter):
    def __init__(self, delegate, failures=1):
        self.delegate = delegate
        self.failures = failures
        self.calls = 0

    async def append_event(self, record):
        self.calls += 1
        if self.calls <= self.failures:
            return AppendOutcome(
                status=AppendOutcomeStatus.FAILED,
                failure_class=FailureClass.RETRYABLE,
                message="TRANSIENT_TEST",
            )
        return await self.delegate.append_event(record)


@pytest.fixture
def repo(tmp_path: Path):
    return SQLiteStateRepository(str(tmp_path / "state.db"))


def info(race_id, deadline, closed=False, cancelled=False):
    return OfficialRaceInfo(
        race_id=race_id,
        official_deadline=deadline,
        is_closed=closed,
        is_cancelled=cancelled,
        sales_status="CLOSED" if closed else "OPEN",
        source_url="u",
        acquired_at="t",
    )


def machine(repo, now, fetcher=None, adapter=None, **kwargs):
    return RaceStateMachine(
        repo,
        MockBaselineRepository(),
        fetcher or FakeFetcher(),
        adapter or DryRunAirtableAdapter(repo),
        now_provider=lambda: now,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_closing_event_persisted_and_idempotent(repo):
    now = dt.datetime(2026, 9, 17, 15, 14, tzinfo=JST)
    rid = "20260917_GAM_01R"
    sm = machine(repo, now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.status == RaceStatus.C_EVENT_DONE
    assert len(st.c_events) == 1
    events = await repo.list_shadow_events(rid)
    assert len(events) == 1
    assert events[0]["identity_hash"]

    # restart: same repo, same version -> no duplicate event
    sm2 = machine(repo, now)
    st2 = await sm2.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert len(st2.c_events) == 1
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_shortening_skips_window_and_is_recorded(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_02R"
    sm = machine(repo, now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    assert st.status == RaceStatus.PENDING

    st = await sm.process_race(
        rid,
        now + dt.timedelta(minutes=1),
        info(rid, now + dt.timedelta(minutes=5)),
    )
    assert st.deadline_version == 2
    assert st.window_state().window_skipped_by_shortening is True
    assert st.status in {RaceStatus.FREEZE_ZONE, RaceStatus.SAFE_STOP}

    closed_now = now + dt.timedelta(minutes=6)
    st = await sm.process_race(
        rid,
        closed_now,
        info(rid, now + dt.timedelta(minutes=5), closed=True),
    )
    assert st.status == RaceStatus.TERMINAL
    assert (
        st.terminal_missed_reason
        == MissedObservationReason.MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE
    )
    assert st.terminal_event_id is not None


@pytest.mark.asyncio
async def test_data_incomplete_miss(repo):
    now = dt.datetime(2026, 9, 17, 15, 10, tzinfo=JST)
    rid = "20260917_GAM_03R"
    sm = machine(repo, now, fetcher=FakeFetcher(complete=False))
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.status == RaceStatus.DATA_WAIT
    st = await sm.process_race(
        rid,
        now + dt.timedelta(minutes=8),
        info(rid, now + dt.timedelta(minutes=7), closed=True),
    )
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_DATA_INCOMPLETE


@pytest.mark.asyncio
async def test_source_error_timeout_from_last_known_official_deadline(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_04R"
    sm = machine(repo, now, source_error_grace_minutes=10)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    assert st.official_deadline is not None

    fail_time = now + dt.timedelta(minutes=31)
    st = await sm.process_race(rid, fail_time, None, official_fetch_failed=True)
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_reason == TerminalReason.SOURCE_ERROR_TIMEOUT
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_SOURCE_ERROR
    assert st.terminal_event_id is not None


@pytest.mark.asyncio
async def test_terminal_payload_records_zero_observation(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_05R"
    sm = machine(repo, now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    st = await sm.process_race(
        rid,
        now + dt.timedelta(minutes=21),
        info(rid, now + dt.timedelta(minutes=20), closed=True),
    )
    assert st.status == RaceStatus.TERMINAL
    events = await repo.list_shadow_events(rid)
    terminal = [e for e in events if e["event_type"] == "RACE_TERMINAL"][0]
    assert '"c_event_count":0' in terminal["payload_json"]
    assert terminal["idempotency_key"] == f"{rid}_TERMINAL"


@pytest.mark.asyncio
async def test_atomic_duplicate_reuses_existing_event_uuid(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_06R"
    adapter = DryRunAirtableAdapter(repo)
    sm = machine(repo, now, adapter=adapter)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    first_uuid = st.c_events[0]

    st.c_events = []
    st.window_state().c_event_emitted = False
    st.status = RaceStatus.CLOSING_WINDOW
    await repo.save_race_state(st)

    st2 = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st2.c_events == [first_uuid]
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_previous_version_event_does_not_hide_current_version_miss(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_07R"
    fetcher = FakeFetcher()
    sm = machine(repo, now, fetcher=fetcher)

    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.window_state(1).c_event_emitted is True

    new_deadline = now + dt.timedelta(minutes=20)
    st = await sm.process_race(
        rid, now + dt.timedelta(minutes=1), info(rid, new_deadline)
    )
    fetcher.complete = False
    st = await sm.process_race(
        rid, now + dt.timedelta(minutes=13), info(rid, new_deadline)
    )
    assert st.deadline_version == 2
    assert st.window_state(2).data_wait_seen is True

    st = await sm.process_race(
        rid,
        now + dt.timedelta(minutes=21),
        info(rid, new_deadline, closed=True),
    )
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_DATA_INCOMPLETE


@pytest.mark.asyncio
async def test_non_retryable_terminal_append_failure_never_persists_terminal(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_08R"
    sm = machine(
        repo,
        now,
        adapter=FixedFailureAdapter(
            FailureClass.NON_RETRYABLE, "HASH_MISMATCH"
        ),
    )

    st = await sm.process_race(
        rid,
        now,
        info(rid, now, closed=True),
    )
    assert st.status == RaceStatus.TERMINAL_FAILED
    assert st.terminal_event_id is None
    assert st.terminal_reason is None
    assert st.terminal_candidate_reason == TerminalReason.OFFICIALLY_CLOSED
    assert st.terminal_failure_class == FailureClass.NON_RETRYABLE

    persisted = await repo.get_race_state(rid)
    assert persisted.status == RaceStatus.TERMINAL_FAILED
    assert persisted.terminal_event_id is None


@pytest.mark.asyncio
async def test_retryable_terminal_append_recovers_from_pending(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_09R"
    flaky = FlakyAdapter(DryRunAirtableAdapter(repo), failures=1)
    sm = machine(repo, now, adapter=flaky, terminal_max_retries=3)

    st = await sm.process_race(rid, now, info(rid, now, closed=True))
    assert st.status == RaceStatus.TERMINAL_PENDING
    assert st.terminal_emit_attempts == 1
    assert st.terminal_event_id is None

    st = await sm.process_race(rid, now + dt.timedelta(seconds=30), None)
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_emit_attempts == 2
    assert st.terminal_event_id is not None
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_retryable_terminal_append_fails_at_bound(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_10R"
    sm = machine(
        repo,
        now,
        adapter=FixedFailureAdapter(FailureClass.RETRYABLE, "TRANSIENT_TEST"),
        terminal_max_retries=2,
    )

    st = await sm.process_race(rid, now, info(rid, now, closed=True))
    assert st.status == RaceStatus.TERMINAL_PENDING
    st = await sm.process_race(rid, now + dt.timedelta(seconds=30), None)
    assert st.status == RaceStatus.TERMINAL_FAILED
    assert st.terminal_emit_attempts == 2
    assert st.terminal_event_id is None


def terminal_record(sm, rid, reason, now, event_uuid):
    payload = {
        "schema_version": 1,
        "event_type": "RACE_TERMINAL",
        "race_id": rid,
        "terminal_reason": reason.value,
        "terminal_missed_reason": None,
        "observed_at": now.isoformat(),
    }
    return EventRecord(
        event_uuid=event_uuid,
        idempotency_key=f"{rid}_TERMINAL",
        identity_hash=sm._terminal_identity_hash(rid, reason),
        race_id=rid,
        event_type="RACE_TERMINAL",
        deadline_version=1,
        payload=payload,
        observed_at=now.isoformat(),
        official_deadline=now.isoformat(),
        payload_hash=DryRunAirtableAdapter.generate_canonical_hash(payload),
    )


@pytest.mark.asyncio
async def test_pending_restart_adopts_existing_terminal_event(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_11R"
    adapter = DryRunAirtableAdapter(repo)
    sm = machine(repo, now, adapter=adapter)
    existing_uuid = "existing-terminal-uuid"

    outcome = await adapter.append_event(
        terminal_record(sm, rid, TerminalReason.OFFICIALLY_CLOSED, now, existing_uuid)
    )
    assert outcome.status == AppendOutcomeStatus.CREATED

    pending = RaceState(
        race_id=rid,
        status=RaceStatus.TERMINAL_PENDING,
        terminal_candidate_reason=TerminalReason.OFFICIALLY_CLOSED,
        terminal_emit_attempts=1,
        official_deadline=now,
    )
    await repo.save_race_state(pending)

    st = await sm.process_race(rid, now + dt.timedelta(seconds=30), None)
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_event_id == existing_uuid
    assert st.terminal_reason == TerminalReason.OFFICIALLY_CLOSED
    assert st.idempotency_conflict is False
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_terminal_duplicate_conflict_adopts_existing_event_and_alerts(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_12R"
    adapter = DryRunAirtableAdapter(repo)
    sm = machine(repo, now, adapter=adapter)
    existing_uuid = "existing-terminal-conflict-uuid"

    await adapter.append_event(
        terminal_record(sm, rid, TerminalReason.OFFICIALLY_CLOSED, now, existing_uuid)
    )
    pending = RaceState(
        race_id=rid,
        status=RaceStatus.TERMINAL_PENDING,
        terminal_candidate_reason=TerminalReason.CANCELLED,
        terminal_emit_attempts=1,
        official_deadline=now,
    )
    await repo.save_race_state(pending)

    st = await sm.process_race(
        rid,
        now + dt.timedelta(seconds=30),
        info(rid, now, cancelled=True),
    )
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_event_id == existing_uuid
    assert st.terminal_reason == TerminalReason.OFFICIALLY_CLOSED
    assert st.idempotency_conflict is True
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_repository_rejects_terminal_without_event_id(repo):
    state = RaceState(race_id="X")
    state.status = RaceStatus.TERMINAL
    with pytest.raises(ValueError, match="terminal_event_id"):
        await repo.save_race_state(state)
