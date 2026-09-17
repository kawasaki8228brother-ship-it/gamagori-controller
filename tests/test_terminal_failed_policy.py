import datetime as dt

import pytest

from airtable import AirtableAdapter
from models import AppendOutcome, FailureClass, JST, RaceState, RaceStatus, TerminalReason
from repositories import MockBaselineRepository, SQLiteStateRepository
from state_machine import RaceStateMachine


class ExplodingAdapter(AirtableAdapter):
    def __init__(self):
        self.calls = 0

    async def append_event(self, record) -> AppendOutcome:
        self.calls += 1
        raise AssertionError("TERMINAL_FAILED must not auto-retry append_event")


class ExplodingFetcher:
    async def fetch_live_data(self, race_id):
        raise AssertionError("TERMINAL_FAILED must not resume live-data processing")


@pytest.mark.asyncio
async def test_terminal_failed_is_sticky_and_not_automatically_rearmed(tmp_path):
    repo = SQLiteStateRepository(str(tmp_path / "state.db"))
    rid = "20260918_GAM_01R"
    failed = RaceState(
        race_id=rid,
        status=RaceStatus.TERMINAL_FAILED,
        terminal_candidate_reason=TerminalReason.SOURCE_ERROR_TIMEOUT,
        terminal_emit_attempts=3,
        terminal_failure_class=FailureClass.RETRYABLE,
        terminal_failure_detail="TRANSIENT_TEST",
    )
    await repo.save_race_state(failed)

    adapter = ExplodingAdapter()
    now = dt.datetime(2026, 9, 18, 1, 30, tzinfo=JST)
    sm = RaceStateMachine(
        repo,
        MockBaselineRepository(),
        ExplodingFetcher(),
        adapter,
        terminal_max_retries=3,
        now_provider=lambda: now,
    )

    result = await sm.process_race(
        rid,
        now,
        official_info=None,
        official_fetch_failed=True,
    )

    assert result.status == RaceStatus.TERMINAL_FAILED
    assert result.terminal_emit_attempts == 3
    assert result.terminal_failure_class == FailureClass.RETRYABLE
    assert result.terminal_failure_detail == "TRANSIENT_TEST"
    assert adapter.calls == 0

    persisted = await repo.get_race_state(rid)
    assert persisted.status == RaceStatus.TERMINAL_FAILED
    assert persisted.terminal_emit_attempts == 3
