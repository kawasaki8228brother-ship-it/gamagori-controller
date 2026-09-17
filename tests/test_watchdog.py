import logging

import pytest

from main import GamagoriController
from models import FailureClass, RaceState, RaceStatus, TerminalReason
from repositories import SQLiteStateRepository


@pytest.mark.asyncio
async def test_watchdog_does_not_count_terminal_failed_as_terminal_reached(tmp_path, caplog):
    repo = SQLiteStateRepository(str(tmp_path / "state.db"))

    reached = RaceState(
        race_id="R1",
        status=RaceStatus.TERMINAL,
        terminal_event_id="terminal-event-1",
        terminal_reason=TerminalReason.OFFICIALLY_CLOSED,
    )
    failed = RaceState(
        race_id="R2",
        status=RaceStatus.TERMINAL_FAILED,
        terminal_candidate_reason=TerminalReason.SOURCE_ERROR_TIMEOUT,
        terminal_emit_attempts=3,
        terminal_failure_class=FailureClass.RETRYABLE,
        terminal_failure_detail="TRANSIENT_TEST",
    )
    await repo.save_race_state(reached)
    await repo.save_race_state(failed)

    controller = GamagoriController.__new__(GamagoriController)
    controller.repo = repo

    with caplog.at_level(logging.INFO, logger="gamagori-controller"):
        await controller.run_watchdog_check(["R1", "R2"])

    summary = "\n".join(record.getMessage() for record in caplog.records)
    assert "TERMINAL=1/2" in summary
    assert "TERMINAL_FAILED=1/2" in summary
    assert "terminal_reached=1/2" in summary
    assert "terminal_unrecorded=1" in summary
