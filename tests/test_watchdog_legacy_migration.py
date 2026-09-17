import logging

import pytest

from main import GamagoriController
from models import FailureClass, RaceState, RaceStatus, TerminalReason
from repositories import SQLiteStateRepository


@pytest.mark.asyncio
async def test_watchdog_reports_legacy_reconciled_and_unreconcilable_totals(tmp_path, caplog):
    repo = SQLiteStateRepository(str(tmp_path / "state.db"))

    reconciled = RaceState(
        race_id="OLD1",
        status=RaceStatus.TERMINAL,
        terminal_event_id="legacy-event-1",
        terminal_reason=TerminalReason.OFFICIALLY_CLOSED,
        legacy_migration_disposition="RECONCILED_TO_EVENT",
        legacy_reconciled=True,
        legacy_reconcile_source_uuid="legacy-event-1",
        pre_reconcile_status="TERMINAL",
        pre_reconcile_terminal_reason="CANCELLED",
    )
    quarantined = RaceState(
        race_id="OLD2",
        status=RaceStatus.TERMINAL_FAILED,
        terminal_candidate_reason=TerminalReason.CANCELLED,
        terminal_failure_class=FailureClass.NON_RETRYABLE,
        terminal_failure_detail="LEGACY_UNRECONCILABLE:AMBIGUOUS_EVENT_COUNT:2",
        legacy_migration_disposition="QUARANTINED_UNRECONCILABLE",
        legacy_candidate_event_uuids=["a", "b"],
        pre_reconcile_status="TERMINAL",
        pre_reconcile_terminal_reason="CANCELLED",
    )
    current = RaceState(race_id="CURRENT", status=RaceStatus.PENDING)

    await repo.save_race_state(reconciled)
    await repo.save_race_state(quarantined)
    await repo.save_race_state(current)

    controller = GamagoriController.__new__(GamagoriController)
    controller.repo = repo

    with caplog.at_level(logging.INFO, logger="gamagori-controller"):
        await controller.run_watchdog_check(["CURRENT"])

    summary = "\n".join(record.getMessage() for record in caplog.records)
    assert "legacy_reconciled_total=1" in summary
    assert "legacy_unreconcilable_total=1" in summary
