import datetime as dt
from pathlib import Path

import pytest

from airtable import DryRunAirtableAdapter
from models import (
    JST,
    LiveDataCompleteness,
    MissedObservationReason,
    OfficialRaceInfo,
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
            source_evidence={"beforeinfo": SourceEvidence(url="u", acquired_at="t", status="OK")},
        )


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


@pytest.mark.asyncio
async def test_closing_event_persisted_and_idempotent(repo):
    now = dt.datetime(2026, 9, 17, 15, 14, tzinfo=JST)
    rid = "20260917_GAM_01R"
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), DryRunAirtableAdapter(repo), clock=lambda: now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.status == RaceStatus.C_EVENT_DONE
    assert len(st.c_events) == 1
    events = await repo.list_shadow_events(rid)
    assert len(events) == 1

    # restart: same repo, same version -> no duplicate event
    sm2 = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), DryRunAirtableAdapter(repo), clock=lambda: now)
    st2 = await sm2.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert len(st2.c_events) == 1
    assert len(await repo.list_shadow_events(rid)) == 1


@pytest.mark.asyncio
async def test_shortening_skips_window_and_is_recorded(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_02R"
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), DryRunAirtableAdapter(repo), clock=lambda: now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    assert st.status == RaceStatus.PENDING

    st = await sm.process_race(rid, now + dt.timedelta(minutes=1), info(rid, now + dt.timedelta(minutes=5)))
    assert st.deadline_version == 2
    assert st.window_state().window_skipped_by_shortening is True
    assert st.status in {RaceStatus.FREEZE_ZONE, RaceStatus.SAFE_STOP}

    closed_now = now + dt.timedelta(minutes=6)
    st = await sm.process_race(rid, closed_now, info(rid, now + dt.timedelta(minutes=5), closed=True))
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE


@pytest.mark.asyncio
async def test_data_incomplete_miss(repo):
    now = dt.datetime(2026, 9, 17, 15, 10, tzinfo=JST)
    rid = "20260917_GAM_03R"
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(complete=False), DryRunAirtableAdapter(repo), clock=lambda: now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.status == RaceStatus.DATA_WAIT
    st = await sm.process_race(rid, now + dt.timedelta(minutes=8), info(rid, now + dt.timedelta(minutes=7), closed=True))
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_DATA_INCOMPLETE


@pytest.mark.asyncio
async def test_source_error_timeout_from_last_known_official_deadline(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_04R"
    sm = RaceStateMachine(
        repo,
        MockBaselineRepository(),
        FakeFetcher(),
        DryRunAirtableAdapter(repo),
        source_error_grace_minutes=10,
        clock=lambda: now,
    )
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    assert st.official_deadline is not None

    # outage continues beyond last known deadline + grace
    fail_time = now + dt.timedelta(minutes=31)
    st = await sm.process_race(rid, fail_time, None, official_fetch_failed=True)
    assert st.status == RaceStatus.TERMINAL
    assert st.terminal_reason == TerminalReason.SOURCE_ERROR_TIMEOUT
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_SOURCE_ERROR


@pytest.mark.asyncio
async def test_terminal_payload_records_zero_observation(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_05R"
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), DryRunAirtableAdapter(repo), clock=lambda: now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=20)))
    st = await sm.process_race(rid, now + dt.timedelta(minutes=21), info(rid, now + dt.timedelta(minutes=20), closed=True))
    events = await repo.list_shadow_events(rid)
    terminal = [e for e in events if e["event_type"] == "RACE_TERMINAL"][0]
    assert '\"c_event_count\":0' in terminal["payload_json"]


@pytest.mark.asyncio
async def test_atomic_duplicate_reuses_existing_event_uuid(repo):
    now = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
    rid = "20260917_GAM_06R"
    adapter = DryRunAirtableAdapter(repo)
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), adapter, clock=lambda: now)
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    first_uuid = st.c_events[0]

    # Simulate crash after event transaction but before state had marked the event.
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
    sm = RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(), DryRunAirtableAdapter(repo), clock=lambda: now)

    # v1 gets a valid C event.
    st = await sm.process_race(rid, now, info(rid, now + dt.timedelta(minutes=7)))
    assert st.window_state(1).c_event_emitted is True

    # Deadline extends, creating v2, then live data is unavailable in the new closing window.
    new_deadline = now + dt.timedelta(minutes=20)
    st = await sm.process_race(rid, now + dt.timedelta(minutes=1), info(rid, new_deadline))
    sm.fetcher.complete = False
    st = await sm.process_race(rid, now + dt.timedelta(minutes=13), info(rid, new_deadline))
    assert st.deadline_version == 2
    assert st.window_state(2).data_wait_seen is True

    st = await sm.process_race(rid, now + dt.timedelta(minutes=21), info(rid, new_deadline, closed=True))
    assert st.terminal_missed_reason == MissedObservationReason.MISSED_DATA_INCOMPLETE
