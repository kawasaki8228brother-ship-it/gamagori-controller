"""Execute old/new controllers against isolated synthetic SQLite, never real DBs.

These compare actual repository CLOSING_OBSERVATION/RACE_TERMINAL events. The
repository has no formal A/B LOCK writer, so no such event is invented here.
"""
import asyncio
from copy import deepcopy
import datetime as dt
import hashlib
from itertools import count, permutations
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

with patch("os.getenv", side_effect=lambda name, default=None: default):
    import main
    import parsers
    import state_machine

from airtable import DryRunAirtableAdapter
from models import JST, LiveDataCompleteness, OfficialRaceInfo, RaceIndexSnapshot, SourceEvidence
from repositories import MockBaselineRepository, SQLiteStateRepository


REFERENCES = Path(__file__).resolve().parents[1] / "development/health_residuals_20261106_v003/references"
BASE_SHA = {"main_8172aec.py.txt": "8ba77c9371e999df08c012978cbb8d0a20654686fbd35846190e565b985a4447",
            "state_machine_8172aec.py.txt": "596fb1a4c1e81d694204bca6968372a2eee86933939046e85a81ea68864a6471",
            "parsers_8172aec.py.txt": "db18b989b409479c508c6a24d685c523b011adecef86ae652e57eb343024f479"}
DAY = dt.datetime(2099, 1, 7, tzinfo=JST)
DEADLINE = DAY.replace(hour=13)
STEPS = [DAY.replace(hour=12, minute=minute) for minute in (40, 45, 53, 54, 55)] + [DAY.replace(hour=13, minute=1)]


def archived_module(filename, name):
    raw = (REFERENCES / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA[filename]
    module = ModuleType(name)
    module.__file__ = str(REFERENCES / filename)
    with patch("os.getenv", side_effect=lambda key, default=None: default):
        exec(compile(raw, filename, "exec"), module.__dict__)
    return module


class PollClock:
    def __init__(self):
        self.index = 0
    @property
    def current(self):
        return STEPS[self.index]


class StageStop:
    """Advance a synthetic clock only after all work in a poll completes."""
    def __init__(self, clock, observe):
        self.clock, self.observe, self.stopped = clock, observe, False
    def is_set(self):
        return self.stopped
    def set(self):
        self.stopped = True
    async def wait(self):
        await self.observe()
        if self.clock.index + 1 == len(STEPS):
            self.stopped = True
        else:
            self.clock.index += 1
        return self.stopped


class SyntheticFetcher:
    def __init__(self, clock, unknown_polls=(), *, parse_index=None, status_layout="explicit", sales_status_override=None):
        self.clock, self.unknown_polls = clock, set(unknown_polls)
        self.parse_index, self.status_layout, self.sales_status_override = parse_index, status_layout, sales_status_override
        self.index_observations = []
        self.index_html = []
        self.tracking_attempts = 0
        self.closed = False
    async def fetch_race_index(self, now):
        if self.clock.index in self.unknown_polls:
            class NoRaceVerified(RuntimeError):
                """Arbitrary legacy spelling, never a calendar authority."""
            raise NoRaceVerified("SYNTHETIC_UNKNOWN_NO_AUTHORITY")
        is_closed = now > DEADLINE and self.sales_status_override != "UNKNOWN"
        rows = [OfficialRaceInfo(
            race_id=f"20990107_GAM_{number:02}R", official_deadline=DEADLINE,
            is_closed=is_closed, is_cancelled=False,
            sales_status=self.sales_status_override or ("CLOSED" if is_closed else "OPEN"),
            source_url="SYNTHETIC_OFFICIAL_INDEX_ONLY", acquired_at=now.isoformat())
            for number in range(1, 13)]
        if self.parse_index is not None:
            word = "発売終了" if now > DEADLINE else "発売中"
            header = "<th>レース</th><th>締切予定時刻</th>"
            if self.status_layout == "explicit":
                header += "<th>発売状況</th>"
                body = "".join(f"<tr><td>{number}R</td><td>13:00</td><td>{word}</td></tr>" for number in range(1, 13))
            elif self.status_layout == "deadline_only":
                body = "".join(f"<tr><td>{number}R</td><td>13:00 {word}</td></tr>" for number in range(1, 13))
            elif self.status_layout == "unknown":
                body = "".join(f"<tr><td>{number}R</td><td>13:00</td></tr>" for number in range(1, 13))
            elif self.status_layout == "name_cancel":
                header += "<th>レース名</th>"
                body = "".join(f"<tr><td>{number}R</td><td>13:00 {word}</td><td>"
                    + ("特別中止記念" if number == 7 else "一般戦") + "</td></tr>" for number in range(1, 13))
            elif self.status_layout == "state_cancel":
                header += "<th>発売状況</th>"
                body = "".join(f"<tr><td>{number}R</td><td>13:00</td><td>"
                    + ("中止" if number == 7 else word) + "</td></tr>" for number in range(1, 13))
            else:
                raise ValueError("UNKNOWN_SYNTHETIC_STATUS_LAYOUT")
            html = "<table><tr>" + header + "</tr>" + body + "</table>"
            self.index_html.append({"at": now.isoformat(), "html": html})
            rows = self.parse_index(html, "20990107", "SYNTHETIC_OFFICIAL_INDEX_ONLY", now.isoformat())
        self.index_observations.append({"at": now.isoformat(), "rows": [row.model_dump(mode="json") for row in rows]})
        return RaceIndexSnapshot(date="20990107", races=rows,
            source_url="SYNTHETIC_OFFICIAL_INDEX_ONLY", acquired_at=now.isoformat())
    async def fetch_tracking_race_index(self, now):
        self.tracking_attempts += 1
        raise RuntimeError("SYNTHETIC_TRACKING_UNAVAILABLE")
    async def fetch_live_data(self, race_id):
        evidence = SourceEvidence(url="SYNTHETIC_COMPLETE_DATA_ONLY", acquired_at=self.clock.current.isoformat(), status="OK")
        return LiveDataCompleteness(is_complete=True,
            exhibition_times={boat: 6.7 + boat / 100 for boat in range(1, 7)},
            entry_courses={boat: boat for boat in range(1, 7)},
            start_exhibition_st={boat: .10 for boat in range(1, 7)},
            weather_info={"wind_speed_m": 2.0},
            odds_3t={"-".join(map(str, triple)): 100.0 for triple in permutations(range(1, 7), 3)},
            source_evidence={"beforeinfo": evidence, "odds3t": evidence})
    async def close(self):
        self.closed = True


class Limiter:
    def emit(self, *args, **kwargs):
        pass


def event_projection(events):
    """Exclude only SQLite's physical insertion timestamp across separate DBs.

    observed_at, payload JSON/hash, UUID, key, type and version remain exact.
    created_at uses SQL CURRENT_TIMESTAMP and is not the model observation time.
    """
    return [{key: value for key, value in row.items() if key != "created_at"} for row in events]


async def execute_scenario(module, machine_class, database, unknown_polls=(), *,
                           parse_index=None, status_layout="explicit", sales_status_override=None):
    database = Path(database)
    if database.exists():
        raise ValueError("NEW_SYNTHETIC_DATABASE_REQUIRED")
    repository = SQLiteStateRepository(str(database))  # A new pytest tmp_path file only.
    clock = PollClock()
    fetcher = SyntheticFetcher(clock, unknown_polls, parse_index=parse_index,
        status_layout=status_layout, sales_status_override=sales_status_override)
    machine = machine_class(repository, MockBaselineRepository(), fetcher,
        DryRunAirtableAdapter(repository), clock=lambda: clock.current)
    timeline = []
    async def observe():
        states = await repository.list_all_states()
        events = event_projection(await repository.list_shadow_events())
        timeline.append({"at": clock.current.isoformat(),
            "states": [row.model_dump(mode="json") for row in sorted(states, key=lambda row: row.race_id)],
            "events": deepcopy(events)})
    controller = module.GamagoriController.__new__(module.GamagoriController)
    controller.repo, controller.fetcher, controller.state_machine = repository, fetcher, machine
    controller._known_races = {}
    controller._day_evidence_date, controller._day_evidence_sources = None, set()
    controller._stop = StageStop(clock, observe)
    controller._error_log_limiter = Limiter()
    controller.poll_interval, controller.dry_run, controller.db_path = 1, True, "SYNTHETIC_TEMP_DB_ONLY"
    controller._last_sqlite_audit_at = None
    controller._maybe_log_sqlite_audit = lambda *args, **kwargs: None
    controller.run_watchdog_check = AsyncMock()
    class CurrentClock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.current if tz is None else clock.current.astimezone(tz)
    namespace = SimpleNamespace(datetime=CurrentClock, timedelta=dt.timedelta, timezone=dt.timezone)
    identifiers = count(1)
    with patch.object(module, "dt", namespace), patch.object(state_machine.uuid, "uuid4", side_effect=lambda: UUID(int=next(identifiers))):
        await controller.start()
    assert fetcher.closed
    return {"timeline": timeline, "events": event_projection(await repository.list_shadow_events()),
            "states": [row.model_dump(mode="json") for row in sorted(await repository.list_all_states(), key=lambda row: row.race_id)],
            "tracking_attempts": fetcher.tracking_attempts,
            "index_observations": fetcher.index_observations, "index_html": fetcher.index_html,
            "comparison_scope": "ALL_EVENT_FIELDS_EXCEPT_PHYSICAL_SQLITE_CREATED_AT"}


def event_timing(result):
    return [(row["race_id"], row["event_type"], row["observed_at"], row["deadline_version"])
            for row in result["events"]]


@pytest.mark.asyncio
async def test_e5_8172_old_main_and_v003_actual_ordered_events_and_states_match(tmp_path):
    original = archived_module("main_8172aec.py.txt", "_health_main_8172_reference")
    original_machine = archived_module("state_machine_8172aec.py.txt", "_health_machine_8172_reference")
    original_parser = archived_module("parsers_8172aec.py.txt", "_health_parser_8172_reference")
    assert Path(state_machine.__file__).read_bytes() == (REFERENCES / "state_machine_8172aec.py.txt").read_bytes()
    old = await execute_scenario(original, original_machine.RaceStateMachine, tmp_path / "old-normal.db",
                                 parse_index=original_parser.parse_race_index)
    current = await execute_scenario(main, state_machine.RaceStateMachine, tmp_path / "v003-normal.db",
                                     parse_index=parsers.parse_race_index)
    assert current == old  # Includes ordered UUIDs, raw payload JSON/hashes and per-poll states; see event_projection.
    assert [row["event_type"] for row in current["events"]] == ["CLOSING_OBSERVATION"] * 12 + ["RACE_TERMINAL"] * 12
    assert all(row["observed_at"] == STEPS[2].isoformat() for row in current["events"][:12])
    assert all(row["observed_at"] == STEPS[-1].isoformat() for row in current["events"][12:])
    assert [len(row["events"]) for row in current["timeline"]] == [0, 0, 12, 12, 12, 24]
    assert all(row["status"] == "TERMINAL" and row["terminal_reason"] == "OFFICIALLY_CLOSED"
               and row["official_deadline"] == DEADLINE.isoformat() for row in current["states"])
    assert not any(row["event_type"] == "LOCK" for row in current["events"])


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_poll", [1, 2], ids=["before-closing-window", "inside-closing-window"])
async def test_unknown_index_failure_preserves_deadlines_and_closing_terminal_timing(tmp_path, unknown_poll):
    original = archived_module("main_8172aec.py.txt", "_health_main_8172_outage_reference")
    original_machine = archived_module("state_machine_8172aec.py.txt", "_health_machine_8172_outage_reference")
    old = await execute_scenario(original, original_machine.RaceStateMachine, tmp_path / "old-unknown.db", unknown_polls={unknown_poll})
    current = await execute_scenario(main, state_machine.RaceStateMachine, tmp_path / "v003-unknown.db", unknown_polls={unknown_poll})
    normal = await execute_scenario(main, state_machine.RaceStateMachine, tmp_path / "v003-control.db")
    assert current == old
    assert current["tracking_attempts"] == 1
    if unknown_poll == 1:
        assert event_timing(current) == event_timing(normal)
    else:
        # When evidence is missing in the closing window, both versions wait
        # until the next successful poll; no retrospective closing is invented.
        assert all(row["observed_at"] == STEPS[3].isoformat() for row in current["events"][:12])
        assert event_timing(current)[12:] == event_timing(normal)[12:]
    for index, stage in enumerate(current["timeline"]):
        assert all(row["official_deadline"] == DEADLINE.isoformat() for row in stage["states"])
        if index == unknown_poll:
            assert all(row["total_source_error_count"] == 1 for row in stage["states"])
    assert all(row["status"] == "TERMINAL" and row["terminal_reason"] == "OFFICIALLY_CLOSED"
               and row["terminal_missed_reason"] is None for row in current["states"])


@pytest.mark.asyncio
async def test_true_unknown_sales_status_matches_old_machine_without_inventing_deadline_closure(tmp_path):
    original = archived_module("main_8172aec.py.txt", "_health_main_8172_unknown_status")
    original_machine = archived_module("state_machine_8172aec.py.txt", "_health_machine_8172_unknown_status")
    old = await execute_scenario(original, original_machine.RaceStateMachine, tmp_path / "old-status-unknown.db",
                                 sales_status_override="UNKNOWN")
    current = await execute_scenario(main, state_machine.RaceStateMachine, tmp_path / "v003-status-unknown.db",
                                     sales_status_override="UNKNOWN")
    assert current == old
    assert all(not row["is_closed"] and not row["is_cancelled"]
               for observation in current["index_observations"] for row in observation["rows"])
    assert [row["event_type"] for row in current["events"]] == ["CLOSING_OBSERVATION"] * 12
    assert all(row["status"] == "C_EVENT_DONE" and row["terminal_reason"] is None
               and row["official_deadline"] == DEADLINE.isoformat() for row in current["states"])


async def measure_status_evidence_gap(directory):
    """Measure case a under the current parser; never reuse an older verdict.

    The initial v003 candidate returned UNKNOWN here and produced a HOLD gap.
    The later 01:55 deadline-cell policy requires remeasurement, not that old
    verdict. Full acceptance/authentication remains separate from this fixture.
    """
    directory = Path(directory)
    original = archived_module("main_8172aec.py.txt", "_health_main_8172_status_gap")
    original_machine = archived_module("state_machine_8172aec.py.txt", "_health_machine_8172_status_gap")
    original_parser = archived_module("parsers_8172aec.py.txt", "_health_parser_8172_status_gap")
    old = await execute_scenario(original, original_machine.RaceStateMachine, directory / "old-status-gap.db",
                                 parse_index=original_parser.parse_race_index, status_layout="deadline_only")
    current = await execute_scenario(main, state_machine.RaceStateMachine, directory / "v003-status-gap.db",
                                     parse_index=parsers.parse_race_index, status_layout="deadline_only")
    equivalent = event_timing(old) == event_timing(current) and old["states"] == current["states"]
    return {"classification": "SYNTHETIC_ONLY", "E2_COMPATIBILITY": "MATCH" if equivalent else "HOLD",
        "scope": "CURRENT_SYNTHETIC_CASE_A_ONLY_NOT_OPERATIONAL_ACCEPTANCE",
        "reason": "MATCHED_DEADLINE_CELL_STATUS_FIXTURE" if equivalent else "FAIL_STATUS_EVIDENCE_GAP",
        "old_terminal_events": sum(row["event_type"] == "RACE_TERMINAL" for row in old["events"]),
        "candidate_terminal_events": sum(row["event_type"] == "RACE_TERMINAL" for row in current["events"]),
        "comparison_scope": "SQLITE_PHYSICAL_CREATED_AT_EXCLUDED_ONLY",
        "formal_AB_LOCK_comparison": "UNVERIFIED_NOT_IMPLEMENTED_IN_REPOSITORY",
        "old": old, "candidate": current, "production_go": False}


@pytest.mark.asyncio
async def test_e2_deadline_cell_closed_matches_after_the_0155_policy_revision(tmp_path):
    measured = await measure_status_evidence_gap(tmp_path)
    assert measured["E2_COMPATIBILITY"] == "MATCH"
    assert measured["reason"] == "MATCHED_DEADLINE_CELL_STATUS_FIXTURE"
    assert measured["old_terminal_events"] == 12
    assert measured["candidate_terminal_events"] == 12
    assert all(row["sales_status"] == "CLOSED" for row in measured["old"]["index_observations"][-1]["rows"])
    assert all(row["sales_status"] == "CLOSED" and row["is_closed"]
               for row in measured["candidate"]["index_observations"][-1]["rows"])


async def measure_status_case_comparisons(directory):
    """Execute the five final synthetic status cases for root evidence export."""
    directory = Path(directory)
    original = archived_module("main_8172aec.py.txt", "_health_main_8172_five_status_cases")
    original_machine = archived_module("state_machine_8172aec.py.txt", "_health_machine_8172_five_status_cases")
    original_parser = archived_module("parsers_8172aec.py.txt", "_health_parser_8172_five_status_cases")
    definitions = {
        "a": ("deadline_only", "DEADLINE_CELL_EXACT_CLOSED", "MATCH"),
        "b": ("explicit", "EXPLICIT_STATE_CELL_CLOSED", "MATCH"),
        "c": ("unknown", "STATUS_INFORMATION_ABSENT", "MATCH_UNKNOWN_WITHOUT_AUTOMATIC_TERMINAL"),
        "d": ("name_cancel", "R7_NAME_CONTAINS_CANCEL_WORD", "INTENTIONAL_NAME_FALSE_CANCEL_REMOVAL"),
        "e": ("state_cancel", "R7_EXPLICIT_STATE_CELL_CANCELLED", "MATCH"),
    }
    cases = {}
    for case, (layout, description, expected) in definitions.items():
        old = await execute_scenario(original, original_machine.RaceStateMachine, directory / f"old-status-{case}.db",
                                     parse_index=original_parser.parse_race_index, status_layout=layout)
        current = await execute_scenario(main, state_machine.RaceStateMachine, directory / f"v003-status-{case}.db",
                                         parse_index=parsers.parse_race_index, status_layout=layout)
        kinds_times_match = event_timing(old) == event_timing(current)
        cases[case] = {"description": description, "layout": layout, "expected_relation": expected,
            "event_kinds_times_match": kinds_times_match, "all_compared_semantic_fields_match": current == old,
            "old_terminal_events": sum(row["event_type"] == "RACE_TERMINAL" for row in old["events"]),
            "candidate_terminal_events": sum(row["event_type"] == "RACE_TERMINAL" for row in current["events"]),
            "old": old, "candidate": current}
    return {"classification": "SYNTHETIC_ONLY", "policy_stage": "CLAUDE_0155_SYNTHETIC_STATUS_MAPPING_PENDING_OFFICIAL_CONFIRMATION",
            "comparison_scope": "ALL_EVENT_FIELDS_EXCEPT_PHYSICAL_SQLITE_CREATED_AT",
            "formal_AB_LOCK_comparison": "UNVERIFIED_NOT_IMPLEMENTED_IN_REPOSITORY", "cases": cases, "production_go": False}


@pytest.mark.asyncio
async def test_final_five_status_cases_show_matches_unknown_and_intentional_name_fix(tmp_path):
    measured = await measure_status_case_comparisons(tmp_path)
    for case in ("a", "b", "e"):
        assert measured["cases"][case]["event_kinds_times_match"]
        assert measured["cases"][case]["all_compared_semantic_fields_match"]
    unknown = measured["cases"]["c"]
    assert unknown["event_kinds_times_match"] and unknown["all_compared_semantic_fields_match"]
    assert unknown["old_terminal_events"] == unknown["candidate_terminal_events"] == 0
    assert all(row["sales_status"] == "UNKNOWN" for row in unknown["candidate"]["index_observations"][-1]["rows"])
    names = measured["cases"]["d"]
    assert not names["event_kinds_times_match"]
    old_r7 = next(row for row in names["old"]["states"] if row["race_id"] == "20990107_GAM_07R")
    new_r7 = next(row for row in names["candidate"]["states"] if row["race_id"] == "20990107_GAM_07R")
    assert old_r7["terminal_reason"] == "CANCELLED"
    assert new_r7["terminal_reason"] == "OFFICIALLY_CLOSED"
    real_cancel = measured["cases"]["e"]
    assert next(row for row in real_cancel["candidate"]["states"] if row["race_id"] == "20990107_GAM_07R")["terminal_reason"] == "CANCELLED"
