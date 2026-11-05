"""Current-JST-day admission only; never edits persisted states or LOCK rules."""
from __future__ import annotations

import datetime as dt
import re
from typing import Dict, Iterable, Mapping

from models import JST, OfficialRaceInfo, RaceIndexSnapshot, RaceState, RaceStatus

_RACE = re.compile(r"(?P<day>\d{8})_GAM_(?P<number>0[1-9]|1[0-2])R\Z")


class RaceScopeError(ValueError):
    pass


def _day(now_jst: dt.datetime) -> str:
    if not isinstance(now_jst, dt.datetime) or now_jst.tzinfo is None or now_jst.utcoffset() is None:
        raise RaceScopeError("CURRENT_JST_DAY_UNVERIFIED")
    return now_jst.astimezone(JST).strftime("%Y%m%d")


def _same_day(race_id: object, deadline: object, day: str) -> bool:
    matched = _RACE.fullmatch(race_id) if isinstance(race_id, str) else None
    return bool(matched and matched["day"] == day and isinstance(deadline, dt.datetime)
        and deadline.tzinfo is not None and deadline.utcoffset() is not None
        and deadline.astimezone(JST).strftime("%Y%m%d") == day)


def filter_current_races(races: Mapping[str, OfficialRaceInfo], now_jst: dt.datetime) -> Dict[str, OfficialRaceInfo]:
    """Exclude stale cache entries; no historical state gets updated or deleted."""
    day = _day(now_jst)
    return {key: info for key, info in races.items() if key == info.race_id
            and _same_day(key, info.official_deadline, day)}


def validate_index_snapshot(snapshot: RaceIndexSnapshot, now_jst: dt.datetime) -> Dict[str, OfficialRaceInfo]:
    """Reject the whole fetched snapshot when one identity/date is inconsistent."""
    day = _day(now_jst)
    if snapshot.date != day or not snapshot.races:
        raise RaceScopeError("FETCHED_SNAPSHOT_DAY_OR_UNIVERSE_INVALID")
    try:
        acquired = dt.datetime.fromisoformat(snapshot.acquired_at)
    except (ValueError, TypeError):
        raise RaceScopeError("FETCHED_SNAPSHOT_ACQUISITION_UNVERIFIED") from None
    if acquired.tzinfo is None or acquired.utcoffset() is None or acquired.astimezone(JST).strftime("%Y%m%d") != day:
        raise RaceScopeError("FETCHED_SNAPSHOT_ACQUISITION_DAY_INVALID")
    accepted = {}
    for info in snapshot.races:
        if info.race_id in accepted or not _same_day(info.race_id, info.official_deadline, day):
            raise RaceScopeError("FETCHED_SNAPSHOT_IDENTITY_OR_DEADLINE_INVALID")
        accepted[info.race_id] = info
    return accepted


def recover_current_states(states: Iterable[RaceState], now_jst: dt.datetime) -> Dict[str, OfficialRaceInfo]:
    """Project only current-day nonterminal records as unconfirmed cache data."""
    day = _day(now_jst)
    recovered = {}
    for state in states:
        deadline = state.tracking_deadline or state.official_deadline
        if state.status == RaceStatus.TERMINAL or not _same_day(state.race_id, deadline, day):
            continue
        if state.race_id in recovered:
            raise RaceScopeError("DUPLICATE_PERSISTED_RACE_ID")
        recovered[state.race_id] = OfficialRaceInfo(
            race_id=state.race_id, official_deadline=deadline, is_closed=False, is_cancelled=False,
            sales_status="PERSISTED_LAST_KNOWN", source_url=state.tracking_source_url or "PERSISTED_LAST_KNOWN",
            acquired_at=(state.last_successful_official_fetch_at or now_jst).isoformat())
    return recovered
