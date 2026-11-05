"""V003 diagnoses source absence without authorizing a calendar or stopping polls."""
from copy import deepcopy
import datetime as dt
import unittest
from unittest.mock import AsyncMock, patch

import main
from models import RaceStatus
from raceindex_status import IndexFailure
from test_health_controller_scope import NOW, controller, fixed_clock_namespace, race, snapshot, state


def absent_sources(value):
    value.fetcher.fetch_race_index = AsyncMock(side_effect=IndexFailure(
        "HTML_PARSE_FAILED", "RACE_INDEX_NO_RACE_ROWS_UNAUTHENTICATED"))
    value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=IndexFailure(
        "TRACKING_MISSING", "TRACKING_STADIUM_7_MISSING"))


def unchanged(case, value, records, before):
    case.assertEqual(records, before)
    value.repo.save_race_state.assert_not_awaited()
    value.repo.append_shadow_event_atomic.assert_not_awaited()
    case.assertFalse(hasattr(value, "_index_hold_reason"))
    case.assertEqual(value._last_index_outcome["calendar_status"], "UNVERIFIED")


class V003DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_candidate_requires_exact_two_missing_sources_and_no_day_evidence(self):
        value = controller()
        absent_sources(value)
        self.assertEqual(await value._refresh_race_universe(NOW, 1), (True, False))
        self.assertEqual(value._last_index_outcome["diagnostic"], "NON_RACE_CANDIDATE_UNAUTHENTICATED")
        self.assertEqual(value._known_races, {})
        for official_kind, official_reason, tracking_kind, tracking_reason in (
            ("HTML_PARSE_FAILED", "RACE_INDEX_HTML_INVALID", "TRACKING_MISSING", "TRACKING_STADIUM_7_MISSING"),
            ("HTTP_FETCH_FAILED", "HTTP_REQUEST_FAILED", "TRACKING_MISSING", "TRACKING_STADIUM_7_MISSING"),
            ("HTML_PARSE_FAILED", "RACE_INDEX_NO_RACE_ROWS_UNAUTHENTICATED", "TRACKING_PARSE_FAILED", "TRACKING_JSON_INVALID"),
        ):
            value = controller()
            value.fetcher.fetch_race_index = AsyncMock(side_effect=IndexFailure(official_kind, official_reason))
            value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=IndexFailure(tracking_kind, tracking_reason))
            await value._refresh_race_universe(NOW, 1)
            self.assertEqual(value._last_index_outcome["diagnostic"], "NORMAL_SOURCE_FAILURE")
            value.state_machine.process_race.assert_not_awaited()
            unchanged(self, value, [], [])

    async def test_same_day_success_cache_or_persisted_terminal_is_conflicting_evidence(self):
        for origin in ("official", "tracking", "cache", "persisted_terminal"):
            with self.subTest(origin=origin):
                records = [state(1, status=RaceStatus.TERMINAL)] if origin == "persisted_terminal" else []
                before = deepcopy(records)
                value = controller(records, {race(1).race_id: race(1)} if origin == "cache" else None)
                if origin == "official":
                    value.fetcher.fetch_race_index = AsyncMock(return_value=snapshot([race(1)]))
                    await value._refresh_race_universe(NOW, 1)
                elif origin == "tracking":
                    value.fetcher.fetch_tracking_race_index = AsyncMock(return_value=snapshot([race(1)]))
                    await value._refresh_race_universe(NOW, 1)
                absent_sources(value)
                await value._refresh_race_universe(NOW, 2)
                self.assertEqual(value._last_index_outcome["diagnostic"], "SOURCE_FAILURE_DAY_EVIDENCE_CONFLICT")
                self.assertTrue(value._day_evidence_sources)
                if origin == "persisted_terminal":
                    self.assertEqual(value._known_races, {})  # Diagnostic evidence never reopens TERMINAL.
                value.state_machine.process_race.assert_not_awaited()
                unchanged(self, value, records, before)

    async def test_next_day_and_new_instance_continue_fetching_without_old_day_latch(self):
        value = controller()
        value.fetcher.fetch_race_index = AsyncMock(return_value=snapshot([race(1)]))
        await value._refresh_race_universe(NOW, 1)
        tomorrow = NOW + dt.timedelta(days=1)
        absent_sources(value)
        await value._refresh_race_universe(tomorrow, 2)
        self.assertEqual(value._last_index_outcome["diagnostic"], "NON_RACE_CANDIDATE_UNAUTHENTICATED")
        self.assertEqual(value._day_evidence_sources, set())
        fresh = snapshot([race(1, tomorrow)], date="20990108", acquired_at=tomorrow.isoformat())
        value.fetcher.fetch_race_index = AsyncMock(return_value=fresh)
        self.assertEqual(await value._refresh_race_universe(tomorrow, 3), (False, False))
        self.assertEqual(set(value._known_races), {"20990108_GAM_01R"})
        restarted = controller()
        absent_sources(restarted)
        await restarted._refresh_race_universe(tomorrow, 1)
        self.assertEqual(restarted._last_index_outcome["diagnostic"], "NON_RACE_CANDIDATE_UNAUTHENTICATED")
        restarted.fetcher.fetch_race_index.assert_awaited_once()
        restarted.fetcher.fetch_tracking_race_index.assert_awaited_once()
        unchanged(self, restarted, [], [])

    async def test_persisted_read_failure_is_not_an_empty_calendar_and_can_recover_next_poll(self):
        value = controller()
        absent_sources(value)
        value.repo.list_all_states = AsyncMock(side_effect=OSError("SYNTHETIC_PRIVATE_READ_ERROR"))
        await value._refresh_race_universe(NOW, 1)
        self.assertEqual(value._last_index_outcome["diagnostic"], "READ_FAILED")
        self.assertNotIn("SYNTHETIC_PRIVATE", str(value._last_index_outcome))
        value.repo.list_all_states = AsyncMock(return_value=[])
        await value._refresh_race_universe(NOW, 2)
        self.assertEqual(value._last_index_outcome["diagnostic"], "NON_RACE_CANDIDATE_UNAUTHENTICATED")
        self.assertEqual(value.fetcher.fetch_race_index.await_count, 2)
        value.state_machine.process_race.assert_not_awaited()
        unchanged(self, value, [], [])

    async def test_ten_empty_polls_keep_fetching_and_call_watchdog_on_five_and_ten(self):
        value = controller()
        absent_sources(value)
        watchdog = []
        async def record_watchdog(ids):
            watchdog.append((value.fetcher.fetch_race_index.await_count, list(ids)))
            if len(watchdog) == 2:
                value.request_stop()
        value.run_watchdog_check = AsyncMock(side_effect=record_watchdog)
        with patch.object(main, "dt", fixed_clock_namespace()):
            await value.start()
        self.assertEqual(watchdog, [(5, []), (10, [])])
        self.assertEqual(value.fetcher.fetch_race_index.await_count, 10)
        self.assertEqual(value.fetcher.fetch_tracking_race_index.await_count, 10)
        value.state_machine.process_race.assert_not_awaited()
        unchanged(self, value, [], [])

    async def test_watchdog_read_exception_does_not_silently_stop_subsequent_polls(self):
        value = controller()
        absent_sources(value)
        watchdog = []
        async def record_watchdog(ids):
            watchdog.append(value.fetcher.fetch_race_index.await_count)
            if len(watchdog) == 1:
                raise OSError("SYNTHETIC_PRIVATE_WATCHDOG_ERROR")
            value.request_stop()
        value.run_watchdog_check = AsyncMock(side_effect=record_watchdog)
        with patch.object(main, "dt", fixed_clock_namespace()), self.assertLogs("gamagori-controller", level="INFO") as logged:
            await value.start()
        self.assertEqual(watchdog, [5, 10])
        self.assertEqual(value.fetcher.fetch_race_index.await_count, 10)
        self.assertTrue(any("WATCHDOG_READ_FAILED" in message for message in logged.output))
        self.assertFalse(any("SYNTHETIC_PRIVATE_WATCHDOG_ERROR" in message for message in logged.output))
        value.state_machine.process_race.assert_not_awaited()
        unchanged(self, value, [], [])


if __name__ == "__main__":
    unittest.main()
