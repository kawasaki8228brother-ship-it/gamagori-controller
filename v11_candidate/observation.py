"""Section-isolated extraction candidate; no scoring, persistence or readiness.

The original strict parser stays unchanged. Each section is staged separately;
a failed section never publishes its partially populated dictionaries. Absence
is not proof of non-publication. SourceStatus is used only for known failures:
parsing success cannot declare a prediction change or no-change decision.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from bs4 import BeautifulSoup

from . import beforeinfo as parser
from .contracts import SourceStatus
from . import table_selection


class ParseState(str, Enum):
    PARSED = 'PARSED'
    PARTIAL = 'PARTIAL'
    MISSING = 'MISSING'
    PARSE_FAILED = 'PARSE_FAILED'


@dataclass(frozen=True)
class SectionReport:
    state: ParseState
    missing_fields: tuple[str, ...] = ()
    error_code: str | None = None
    source_status: SourceStatus | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, ParseState):
            raise ValueError('INVALID_SECTION_STATE')
        if type(self.missing_fields) is not tuple or any(not isinstance(x, str) or not x for x in self.missing_fields):
            raise ValueError('INVALID_SECTION_MISSING_FIELDS')
        if self.state == ParseState.PARSE_FAILED:
            if not isinstance(self.error_code, str) or not self.error_code or self.source_status != SourceStatus.SOURCE_PARSE_FAILED:
                raise ValueError('PARSE_FAILURE_REQUIRES_ERROR')
        elif self.error_code is not None or self.source_status is not None:
            raise ValueError('INCONSISTENT_SECTION_REPORT')


class ObservationContractError(ValueError):
    pass


def _boat_keys(values: dict) -> bool:
    return type(values) is dict and all(type(k) is int and 1 <= k <= 6 for k in values)


def coverage(snapshot: parser.BeforeInfoSnapshot) -> dict[str, bool]:
    """Recompute capabilities; do not trust cached boolean fields or coerce ST.

    This describes the fixed six-boat format only. It never infers active boats
    from missing cells. Marker-only F/L counts as a recognized reading, not a
    number; F.01 has both a magnitude and a marker, not an ordinary +.01 ST.
    """
    if not isinstance(snapshot, parser.BeforeInfoSnapshot):
        raise ObservationContractError('INVALID_SNAPSHOT_TYPE')
    ex, entry, starts = snapshot.exhibition_times, snapshot.entry_courses, snapshot.starts
    if not all(_boat_keys(v) for v in (ex, entry, starts)):
        raise ObservationContractError('INVALID_BOAT_MAPPING')
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 10 for v in ex.values()):
        raise ObservationContractError('INVALID_EXHIBITION_VALUE')
    if any(type(v) is not int or not 1 <= v <= 6 for v in entry.values()) or len(set(entry.values())) != len(entry):
        raise ObservationContractError('INVALID_COURSE_MAPPING')
    for value in starts.values():
        if not isinstance(value, parser.StartReading):
            raise ObservationContractError('INVALID_START_READING_TYPE')
        try:
            parsed = parser.parse_start(value.raw)
        except (parser.BeforeInfoParseError, TypeError, AttributeError) as exc:
            raise ObservationContractError('INVALID_START_RAW') from exc
        if parsed is None or parsed != value:
            raise ObservationContractError('START_RAW_MARKER_MAGNITUDE_CONFLICT')
        if value.seconds_magnitude is not None and type(value.seconds_magnitude) not in (int, float):
            raise ObservationContractError('INVALID_START_MAGNITUDE_TYPE')
    expected = set(range(1, 7))
    start_data_six = set(starts) == expected
    return {
        'exhibition_six': set(ex) == expected,
        'entry_six': set(entry) == expected and set(entry.values()) == expected,
        'start_data_six': start_data_six,
        'numeric_st_six': start_data_six and all(s.seconds_magnitude is not None for s in starts.values()),
    }


@dataclass
class BeforeObservation:
    data: parser.BeforeInfoSnapshot
    sections: dict[str, SectionReport]

    @property
    def start_data_six(self) -> bool:
        return coverage(self.data)['start_data_six']


def parse_beforeinfo_observation(html: str) -> BeforeObservation:
    """Return independent section outcomes without relaxing the strict parser.

    Bad whole-body type/size still raises. Page identity and information age
    are NOT checked here; readable cells never authorize evaluation or a bet.
    """
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise parser.BeforeInfoParseError('BODY_TYPE_OR_SIZE')
    soup = BeautifulSoup(html, 'html.parser')
    tables = table_selection.select_beforeinfo_tables(soup)

    data, reports = parser.BeforeInfoSnapshot(), {}
    fields = {'exhibition': ('exhibition_times',), 'start': ('entry_courses', 'starts'), 'weather': ('weather',)}
    for name in ('exhibition', 'start', 'weather'):
        staged = parser.BeforeInfoSnapshot()
        try:
            if name != 'weather':
                candidates = tables[name]
                if len(candidates) > 1:
                    raise parser.BeforeInfoParseError('AMBIGUOUS_DATA_TABLES')
                if not candidates:
                    staged.missing_fields.append(name + '_section')
                elif name == 'exhibition':
                    parser._exhibition(candidates[0].table, staged)
                else:
                    parser._starts(candidates[0].table, staged)
            else:
                parser._weather(soup, staged)
            caps = coverage(staged)
        except Exception as exc:
            # No prefix of a failed section is promoted to valid observation.
            code = str(exc) if isinstance(exc, (parser.BeforeInfoParseError, ObservationContractError)) else 'UNEXPECTED_SECTION_ERROR:' + type(exc).__name__
            reports[name] = SectionReport(ParseState.PARSE_FAILED, (), code, SourceStatus.SOURCE_PARSE_FAILED)
            data.missing_fields.append(name + '_parse_failed')
            continue
        for key in fields[name]:
            setattr(data, key, getattr(staged, key))
        if name == 'exhibition':
            complete, any_data = caps['exhibition_six'], bool(staged.exhibition_times)
        elif name == 'start':
            complete = caps['entry_six'] and caps['start_data_six']
            any_data = bool(staged.entry_courses or staged.starts)
        else:
            required = {'air_temperature_c', 'water_temperature_c', 'wind_speed_m', 'wave_height_cm'}
            complete, any_data = required <= set(staged.weather), bool(staged.weather)
        state = ParseState.PARSED if complete else ParseState.PARTIAL if any_data else ParseState.MISSING
        reports[name] = SectionReport(state, tuple(staged.missing_fields))
        data.missing_fields.extend(staged.missing_fields)

    caps = coverage(data)
    data.exhibition_six, data.entry_six, data.numeric_st_six = caps['exhibition_six'], caps['entry_six'], caps['numeric_st_six']
    for key, missing in (('exhibition_six', 'exhibition_times_6boats'), ('entry_six', 'entry_courses_6boats'),
                         ('start_data_six', 'start_readings_6boats'), ('numeric_st_six', 'start_st_numeric_6boats')):
        if not caps[key]:
            data.missing_fields.append(missing)
    data.missing_fields = sorted(set(data.missing_fields))
    return BeforeObservation(data, reports)
