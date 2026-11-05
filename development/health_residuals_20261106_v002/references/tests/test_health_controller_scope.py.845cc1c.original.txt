"""Offline controller scope checks; only invented 2099 races and injected fakes.

Controller.__init__ is never called: it would construct transport/repository
dependencies from the runtime environment. No actual controller watch is run.
The start tests execute exactly one injected local loop cycle.
"""
import asyncio
from copy import deepcopy
import datetime as datetime_module
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import main
from models import JST, OfficialRaceInfo, RaceIndexSnapshot, RaceState, RaceStatus
from raceindex_scope import (RaceScopeError, filter_current_races, recover_current_states,
                             validate_index_snapshot)
from raceindex_status import NoRaceVerified


NOW = datetime_module.datetime(2099, 1, 7, 12, 0, tzinfo=JST)
YESTERDAY = NOW - datetime_module.timedelta(days=1)


def race(number=1, day=NOW, *, deadline=None, identity=None):
    return OfficialRaceInfo(race_id=identity or f"{day:%Y%m%d}_GAM_{number:02}R",
        official_deadline=deadline or day.replace(hour=13, minute=number),
        source_url="SYNTHETIC_INDEX_SOURCE_ONLY", acquired_at=NOW.isoformat())


def snapshot(races, **changes):
    fields = {"date": NOW.strftime("%Y%m%d"), "races": races,
              "source_url": "SYNTHETIC_INDEX_SOURCE_ONLY", "acquired_at": NOW.isoformat()}
    fields.update(changes)
    return RaceIndexSnapshot(**fields)


def state(number=1, day=NOW, **changes):
    fields = {"race_id": f"{day:%Y%m%d}_GAM_{number:02}R", "status": RaceStatus.PENDING,
              "official_deadline": day.replace(hour=13, minute=number)}
    fields.update(changes)
    return RaceState(**fields)


class _Limiter:
    def emit(self, *args, **kwargs):
        pass


def controller(states=(), known=None):
    value = main.GamagoriController.__new__(main.GamagoriController)
    value._known_races = {} if known is None else dict(known)
    value._error_log_limiter = _Limiter()
    value._stop = asyncio.Event()
    value.poll_interval = 0
    value.dry_run = True
    value.db_path = "SYNTHETIC_NO_DATABASE"
    value._last_sqlite_audit_at = None
    value._maybe_log_sqlite_audit = Mock()
    value.run_watchdog_check = AsyncMock()
    value.repo = SimpleNamespace(list_all_states=AsyncMock(return_value=list(states)),
        save_race_state=AsyncMock(side_effect=AssertionError("NO_DB_WRITE")),
        append_shadow_event_atomic=AsyncMock(side_effect=AssertionError("NO_EVENT_WRITE")))
    value.fetcher = SimpleNamespace(
        fetch_race_index=AsyncMock(side_effect=RuntimeError("SYNTHETIC_OFFICIAL_FAILURE")),
        fetch_tracking_race_index=AsyncMock(side_effect=RuntimeError("SYNTHETIC_TRACKING_FAILURE")),
        close=AsyncMock())
    value.state_machine = SimpleNamespace(process_race=AsyncMock())
    return value


def fixed_clock_namespace():
    class Clock(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is None else NOW.astimezone(tz)
    return SimpleNamespace(datetime=Clock, timedelta=datetime_module.timedelta,
                           timezone=datetime_module.timezone)


class PureRaceScopeTests(unittest.TestCase):
    def test_cache_filter_requires_current_id_and_matching_aware_deadline(self):
        good = race(1)
        rows = [good, race(2, YESTERDAY), race(3, deadline=YESTERDAY.replace(hour=14)),
                race(4, deadline=NOW.replace(tzinfo=None)), race(0), race(13)]
        supplied = {row.race_id: row for row in rows}
        supplied["20990107_GAM_05R"] = race(6)
        original = deepcopy(supplied)
        self.assertEqual(set(filter_current_races(supplied, NOW)), {good.race_id})
        self.assertEqual(supplied, original)

    def test_snapshot_is_all_or_none_for_date_acquisition_duplicates_and_bad_deadline(self):
        valid = snapshot([race(1), race(2)])
        self.assertEqual(set(validate_index_snapshot(valid, NOW)), {race(1).race_id, race(2).race_id})
        invalid = [snapshot([race(1), race(2, deadline=YESTERDAY)]),
                   snapshot([race(1), race(1)]), snapshot([race(1)], date="20990106"),
                   snapshot([race(1)], acquired_at=YESTERDAY.isoformat()),
                   snapshot([race(1)], acquired_at=NOW.replace(tzinfo=None).isoformat())]
        for value in invalid:
            with self.subTest(date=value.date), self.assertRaises(RaceScopeError):
                validate_index_snapshot(value, NOW)

    def test_persisted_recovery_skips_history_terminal_and_invalid_deadlines(self):
        current = state(1)
        tracked = state(2, official_deadline=None, tracking_deadline=NOW.replace(hour=14))
        rows = [current, tracked, state(3, status=RaceStatus.TERMINAL), state(4, YESTERDAY),
                state(5, official_deadline=YESTERDAY), state(6, official_deadline=NOW.replace(tzinfo=None))]
        original = deepcopy(rows)
        recovered = recover_current_states(rows, NOW)
        self.assertEqual(set(recovered), {current.race_id, tracked.race_id})
        self.assertEqual(rows, original)
        self.assertTrue(all(value.official_deadline.astimezone(JST).date() == NOW.date() for value in recovered.values()))

    def test_scope_helpers_reject_an_unknown_or_naive_current_clock(self):
        for bad in (None, NOW.replace(tzinfo=None)):
            for function, argument in ((filter_current_races, {}), (recover_current_states, []),
                                       (validate_index_snapshot, snapshot([race(1)]))):
                with self.subTest(function=function.__name__), self.assertRaises(RaceScopeError):
                    function(argument, bad)


class ControllerScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_failures_prune_prior_day_cache_without_processing_history(self):
        old = race(1, YESTERDAY)
        records = [state(1, YESTERDAY), state(2, status=RaceStatus.TERMINAL)]
        before = deepcopy(records)
        value = controller(records, {old.race_id: old})
        failed, active = await value._refresh_race_universe(NOW, 1)
        self.assertTrue(failed)
        self.assertFalse(active)
        self.assertEqual(value._known_races, {})
        self.assertEqual(records, before)
        value.state_machine.process_race.assert_not_awaited()
        value.repo.save_race_state.assert_not_awaited()

    async def test_current_day_persisted_state_can_be_recovered_during_full_outage(self):
        current = state(1)
        records = [current, state(2, YESTERDAY)]
        before = deepcopy(records)
        value = controller(records)
        failed, _ = await value._refresh_race_universe(NOW, 1)
        self.assertTrue(failed)
        self.assertEqual(set(value._known_races), {current.race_id})
        self.assertEqual(records, before)
        value.repo.save_race_state.assert_not_awaited()

    async def test_invalid_official_snapshot_is_not_partially_accepted_before_tracking(self):
        value = controller()
        value.fetcher.fetch_race_index = AsyncMock(return_value=snapshot([race(1), race(2, YESTERDAY)]))
        value.fetcher.fetch_tracking_race_index = AsyncMock(return_value=snapshot([race(3)]))
        failed, active = await value._refresh_race_universe(NOW, 1)
        self.assertTrue(failed)
        self.assertTrue(active)
        self.assertEqual(set(value._known_races), {race(3).race_id})

    async def test_valid_official_snapshot_replaces_old_cache(self):
        old = race(1, YESTERDAY)
        value = controller(known={old.race_id: old})
        value.fetcher.fetch_race_index = AsyncMock(return_value=snapshot([race(2)]))
        self.assertEqual(await value._refresh_race_universe(NOW, 1), (False, False))
        self.assertEqual(set(value._known_races), {race(2).race_id})
        value.fetcher.fetch_tracking_race_index.assert_not_awaited()

    async def test_invalid_tracking_snapshot_does_not_partially_enter_universe(self):
        value = controller()
        value.fetcher.fetch_tracking_race_index = AsyncMock(return_value=snapshot([race(1), race(2, YESTERDAY)]))
        failed, active = await value._refresh_race_universe(NOW, 1)
        self.assertTrue(failed)
        self.assertFalse(active)
        self.assertEqual(value._known_races, {})

    async def test_verified_no_race_day_skips_fallback_recovery_and_state_machine(self):
        for origin in ("official", "tracking"):
            with self.subTest(origin=origin):
                current, old = race(1), race(2, YESTERDAY)
                records = [state(1), state(2, YESTERDAY)]
                original = deepcopy(records)
                value = controller(records, {current.race_id: current, old.race_id: old})
                async def no_race(_):
                    value.request_stop()
                    raise NoRaceVerified()
                if origin == "official":
                    value.fetcher.fetch_race_index = AsyncMock(side_effect=no_race)
                else:
                    value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=no_race)
                with patch.object(main, "dt", fixed_clock_namespace()), self.assertLogs("gamagori-controller", level="INFO") as logged:
                    await value.start()
                self.assertTrue(any("NO_RACE" in line for line in logged.output))
                self.assertEqual(value._known_races, {})
                if origin == "official":
                    value.fetcher.fetch_tracking_race_index.assert_not_awaited()
                else:
                    value.fetcher.fetch_tracking_race_index.assert_awaited_once()
                value.repo.list_all_states.assert_not_awaited()
                value.state_machine.process_race.assert_not_awaited()
                value.repo.save_race_state.assert_not_awaited()
                self.assertEqual(records, original)

    async def test_one_local_poll_cycle_never_processes_old_states_after_two_failures(self):
        old = race(1, YESTERDAY)
        records = [state(1, YESTERDAY), state(2, YESTERDAY)]
        original = deepcopy(records)
        value = controller(records, {old.race_id: old})
        async def fail_tracking(_):
            value.request_stop()
            raise RuntimeError("SYNTHETIC_TRACKING_FAILURE")
        value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=fail_tracking)
        with patch.object(main, "dt", fixed_clock_namespace()):
            await value.start()
        value.state_machine.process_race.assert_not_awaited()
        self.assertEqual(value._known_races, {})
        self.assertEqual(records, original)
        value.repo.save_race_state.assert_not_awaited()
        value.fetcher.close.assert_awaited_once()
        with self.subTest(rollover_after_fetch=True):
            current = race(1)
            value = controller([state(1)])
            async def success_then_stop(_):
                value.request_stop()
                return snapshot([current])
            value.fetcher.fetch_race_index = AsyncMock(side_effect=success_then_stop)
            next_day = NOW + datetime_module.timedelta(days=1)
            reads = iter((NOW, next_day))
            class CrossingClock(datetime_module.datetime):
                @classmethod
                def now(cls, tz=None):
                    value = next(reads, next_day)
                    return value if tz is None else value.astimezone(tz)
            namespace = SimpleNamespace(datetime=CrossingClock, timedelta=datetime_module.timedelta,
                                        timezone=datetime_module.timezone)
            with patch.object(main, "dt", namespace):
                await value.start()
            value.state_machine.process_race.assert_not_awaited()
            value.repo.save_race_state.assert_not_awaited()
            self.assertEqual(value._known_races, {})

    async def test_tracking_only_fallback_is_never_passed_as_official_info(self):
        value = controller()
        expected = race(1)
        async def tracking(_):
            value.request_stop()
            return snapshot([expected])
        value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=tracking)
        with patch.object(main, "dt", fixed_clock_namespace()):
            await value.start()
        value.state_machine.process_race.assert_awaited_once()
        args, kwargs = value.state_machine.process_race.call_args
        self.assertEqual(args[0], expected.race_id)
        self.assertIsNone(kwargs["official_info"])
        self.assertTrue(kwargs["official_fetch_failed"])
        self.assertEqual(kwargs["tracking_info"], expected)
        value.repo.save_race_state.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
