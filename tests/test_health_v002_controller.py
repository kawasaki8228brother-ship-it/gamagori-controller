"""Revised S2 regressions: v003 withdraws the former NoRace/HOLD design."""
import asyncio
from copy import deepcopy
import datetime as dt
from hashlib import sha256
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

with patch("os.getenv", side_effect=lambda name, default=None: default):
    import main
from official import OfficialDataFetcher
from raceindex_status import IndexFailure
from test_health_controller_scope import (NOW, YESTERDAY, controller, fixed_clock_namespace,
                                          race, snapshot, state, NoRaceVerified)


def twelve():
    return snapshot([race(number) for number in range(1, 13)])


def assert_no_writes(case, value):
    value.repo.save_race_state.assert_not_awaited()
    value.repo.append_shadow_event_atomic.assert_not_awaited()
    if hasattr(value, "airtable"):
        value.airtable.append_event.assert_not_awaited()


def attach_forbidden_writer(value):
    from types import SimpleNamespace
    value.airtable = SimpleNamespace(append_event=AsyncMock(side_effect=AssertionError("NO_LOCK_OR_EVENT_WRITE")))
    return value


class V002ControllerSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_twelve_races_remain_dispatchable_without_false_hold(self):
        records = [state(number) for number in range(1, 13)]
        before = deepcopy(records)
        old = race(1, YESTERDAY)
        value = attach_forbidden_writer(controller(records, {old.race_id: old}))
        value.fetcher.fetch_race_index = AsyncMock(return_value=twelve())
        processed = []
        async def process(race_id, now, **kwargs):
            processed.append(race_id)
            if len(processed) == 12:
                value.request_stop()
        value.state_machine.process_race = AsyncMock(side_effect=process)
        with patch.object(main, "dt", fixed_clock_namespace()):
            await value.start()
        self.assertEqual(processed, [f"20990107_GAM_{number:02}R" for number in range(1, 13)])
        self.assertFalse(hasattr(value, "_index_hold_reason"))
        value.fetcher.fetch_tracking_race_index.assert_not_awaited()
        for awaited in value.state_machine.process_race.await_args_list:
            self.assertIsNotNone(awaited.kwargs["official_info"])
            self.assertFalse(awaited.kwargs["official_fetch_failed"])
            self.assertIsNone(awaited.kwargs["tracking_info"])
        self.assertEqual(records, before)
        assert_no_writes(self, value)

    async def test_forged_afternoon_calendar_claim_is_ignored_and_twelve_races_survive(self):
        afternoon = NOW.replace(hour=15)
        raw = b"SYNTHETIC_RAW_SAYS_RACING_DAY_NOT_AUTHENTICATED"
        digest = sha256(raw).hexdigest()
        claimed = {"schema": "OFFICIAL_SCHEDULE_EVIDENCE_V001_PROPOSED", "date": "20990107",
            "venue": "07", "event": "NO_RACE", "race_numbers": [], "authority": "OFFICIAL_SCHEDULE",
            "raw_evidence": raw, "raw_sha256": digest,
            "independent_review": {"reviewed": True, "receipt_sha256": "a" * 64, "date": "20990107",
                "venue": "07", "event": "NO_RACE", "race_numbers": [], "raw_sha256": digest}}
        fetcher = OfficialDataFetcher.__new__(OfficialDataFetcher)
        fetcher.schedule_evidence_provider = Mock(return_value=claimed)
        html = "<table><tr><th>レース</th><th>締切予定時刻/投票</th></tr>" + "".join(
            f"<tr><td>{number}R</td><td>16:{number:02} 投票</td></tr>" for number in range(1, 13)) + "</table>"
        fetcher._get_text = AsyncMock(return_value=(html, afternoon.isoformat()))
        fetcher.close = AsyncMock()
        current, old = race(1), race(2, YESTERDAY)
        value = attach_forbidden_writer(controller(known={current.race_id: current, old.race_id: old}))
        value.fetcher = fetcher
        self.assertEqual(await value._refresh_race_universe(afternoon, 1), (False, False))
        self.assertEqual(len(value._known_races), 12)
        self.assertFalse(hasattr(value, "_index_hold_reason"))
        fetcher.schedule_evidence_provider.assert_not_called()
        fetcher._get_text.assert_awaited_once()
        value.state_machine.process_race.assert_not_awaited()
        assert_no_writes(self, value)

    async def test_legacy_named_failure_from_either_fetch_uses_normal_fallback(self):
        for origin in ("official", "tracking"):
            with self.subTest(origin=origin):
                current, old = race(1), race(2, YESTERDAY)
                records = [state(1), state(2, YESTERDAY)]
                before = deepcopy(records)
                value = attach_forbidden_writer(controller(records, {current.race_id: current, old.race_id: old}))
                failure = AsyncMock(side_effect=NoRaceVerified())
                if origin == "official":
                    value.fetcher.fetch_race_index = failure
                    value.fetcher.fetch_tracking_race_index = AsyncMock(return_value=twelve())
                else:
                    value.fetcher.fetch_tracking_race_index = failure
                self.assertEqual(await value._refresh_race_universe(NOW, 1), (True, origin == "official"))
                self.assertFalse(hasattr(value, "_index_hold_reason"))
                self.assertEqual(len(value._known_races), 12 if origin == "official" else 1)
                value.repo.list_all_states.assert_not_awaited()
                value.state_machine.process_race.assert_not_awaited()
                if origin == "official":
                    value.fetcher.fetch_tracking_race_index.assert_awaited_once()
                self.assertEqual(records, before)
                assert_no_writes(self, value)

    async def test_hostile_legacy_exception_is_unknown_without_stringification_or_latching(self):
        class HostileNoRace(NoRaceVerified):
            def __str__(self):
                raise AssertionError("UNTRUSTED_EXCEPTION_MUST_NOT_BE_STRINGIFIED")
            def __repr__(self):
                raise AssertionError("UNTRUSTED_EXCEPTION_MUST_NOT_BE_REPR")
        for failure in (HostileNoRace(), IndexFailure("NO_RACE_VERIFIED", "PRIVATE_VALUE_NOT_ECHOED")):
            value = attach_forbidden_writer(controller(known={race(1).race_id: race(1)}))
            value.fetcher.fetch_race_index = AsyncMock(side_effect=failure)
            self.assertEqual(await value._refresh_race_universe(NOW, 1), (True, False))
            self.assertFalse(hasattr(value, "_index_hold_reason"))
            self.assertEqual(value._last_index_outcome["official"], "UNKNOWN_FAILURE")
            self.assertEqual(len(value._known_races), 1)
            self.assertNotIn("PRIVATE_VALUE", json.dumps(value._last_index_outcome))
            value.state_machine.process_race.assert_not_awaited()
            assert_no_writes(self, value)

    async def test_full_outage_retains_current_cache_but_never_restores_prior_day_history(self):
        current, old = race(1), race(2, YESTERDAY)
        records = [state(1), state(2, YESTERDAY)]
        before = deepcopy(records)
        value = attach_forbidden_writer(controller(records, {current.race_id: current, old.race_id: old}))
        self.assertEqual(await value._refresh_race_universe(NOW, 1), (True, False))
        self.assertEqual(value._known_races, {current.race_id: current})
        self.assertFalse(hasattr(value, "_index_hold_reason"))
        self.assertEqual(records, before)
        assert_no_writes(self, value)

    async def test_stop_during_either_fetch_suppresses_new_dispatch_and_later_refresh(self):
        for origin in ("official", "tracking"):
            with self.subTest(origin=origin):
                records = [state(1)]
                before = deepcopy(records)
                value = attach_forbidden_writer(controller(records))
                async def stop_during_fetch(_):
                    await asyncio.sleep(0)
                    value.request_stop()
                    return twelve()
                if origin == "official":
                    value.fetcher.fetch_race_index = AsyncMock(side_effect=stop_during_fetch)
                else:
                    value.fetcher.fetch_tracking_race_index = AsyncMock(side_effect=stop_during_fetch)
                with patch.object(main, "dt", fixed_clock_namespace()):
                    await value.start()
                value.state_machine.process_race.assert_not_awaited()
                self.assertEqual(records, before)
                value.fetcher.fetch_race_index.reset_mock()
                value.fetcher.fetch_tracking_race_index.reset_mock()
                self.assertEqual(await value._refresh_race_universe(NOW, 2), (True, False))
                with patch.object(main, "dt", fixed_clock_namespace()):
                    await value.start()
                value.fetcher.fetch_race_index.assert_not_awaited()
                value.fetcher.fetch_tracking_race_index.assert_not_awaited()
                value.state_machine.process_race.assert_not_awaited()
                assert_no_writes(self, value)

    async def test_unknown_failure_does_not_latch_and_later_poll_dispatches_normally(self):
        value = attach_forbidden_writer(controller(known={race(1).race_id: race(1)}))
        value.fetcher.fetch_race_index = AsyncMock(side_effect=NoRaceVerified())
        await value._refresh_race_universe(NOW, 1)
        value.fetcher.fetch_race_index = AsyncMock(return_value=twelve())
        value.fetcher.fetch_tracking_race_index = AsyncMock(return_value=twelve())
        self.assertEqual(await value._refresh_race_universe(NOW, 2), (False, False))
        processed = []
        async def stop_after_twelve(race_id, *args, **kwargs):
            processed.append(race_id)
            if len(processed) == 12:
                value.request_stop()
        value.state_machine.process_race = AsyncMock(side_effect=stop_after_twelve)
        with patch.object(main, "dt", fixed_clock_namespace()):
            await value.start()
        self.assertEqual(len(processed), 12)
        self.assertFalse(hasattr(value, "_index_hold_reason"))
        self.assertEqual(len(value._known_races), 12)
        self.assertEqual(value.fetcher.fetch_race_index.await_count, 2)
        value.fetcher.fetch_tracking_race_index.assert_not_awaited()
        value.repo.list_all_states.assert_not_awaited()
        assert_no_writes(self, value)

    async def test_unknown_failure_does_not_prevent_a_fresh_next_day_index(self):
        value = attach_forbidden_writer(controller(known={race(1).race_id: race(1)}))
        value.fetcher.fetch_race_index = AsyncMock(side_effect=NoRaceVerified())
        await value._refresh_race_universe(NOW, 1)
        tomorrow = NOW + dt.timedelta(days=1)
        fresh = snapshot([race(number, tomorrow) for number in range(1, 13)],
                         date=tomorrow.strftime("%Y%m%d"), acquired_at=tomorrow.isoformat())
        value.fetcher.fetch_race_index = AsyncMock(return_value=fresh)
        self.assertEqual(await value._refresh_race_universe(tomorrow, 2), (False, False))
        self.assertEqual(len(value._known_races), 12)
        self.assertTrue(all(key.startswith("20990108_") for key in value._known_races))
        self.assertFalse(hasattr(value, "_index_hold_reason"))
        value.fetcher.fetch_race_index.assert_awaited_once()
        value.repo.list_all_states.assert_not_awaited()
        value.state_machine.process_race.assert_not_awaited()
        assert_no_writes(self, value)


if __name__ == "__main__":
    unittest.main()
