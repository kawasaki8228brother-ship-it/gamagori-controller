"""Read-only beforeinfo extraction candidate, not a live-readiness policy.

Recognizes semantic table headers plus the boat-image start layout captured
post-incident. Never turns a blank into zero or infers a start marker from its
color. Date/venue/race/freshness and eligibility remain caller responsibilities.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag


class BeforeInfoParseError(ValueError):
    pass


def text(node: Tag) -> str:
    return unicodedata.normalize('NFKC', node.get_text(' ', strip=True)).strip()


def label(node: Tag) -> str:
    return re.sub(r'\s+', '', text(node))


def cells(row: Tag) -> list[Tag]:
    return row.find_all(['td', 'th'], recursive=False)


def span(cell: Tag, name: str) -> int:
    raw = cell.get(name, '1')
    if not isinstance(raw, str) or not re.fullmatch(r'[1-9]\d?', raw):
        raise BeforeInfoParseError('INVALID_SPAN')
    value = int(raw)
    if value > 32:
        raise BeforeInfoParseError('SPAN_LIMIT')
    return value


def grid(rows: list[Tag], width: int) -> list[list[Tag]]:
    """Bounded table expansion; rowspan objects retain their cell identity."""
    if not 1 <= width <= 32 or not 1 <= len(rows) <= 256:
        raise BeforeInfoParseError('GRID_SIZE')
    pending: dict[int, tuple[Tag, int]] = {}
    result = []
    for row in rows:
        current = {c: v[0] for c, v in pending.items()}
        following = {c: (v[0], v[1]-1) for c, v in pending.items() if v[1] > 1}
        col = 0
        for cell in cells(row):
            while col in current:
                col += 1
            cols, runs = span(cell, 'colspan'), span(cell, 'rowspan')
            if col+cols > width or any(c in current for c in range(col, col+cols)):
                raise BeforeInfoParseError('OVERLAPPING_OR_WIDE_GRID')
            for c in range(col, col+cols):
                current[c] = cell
                if runs > 1:
                    following[c] = (cell, runs-1)
            col += cols
        if set(current) != set(range(width)):
            raise BeforeInfoParseError('INCOMPLETE_GRID')
        result.append([current[c] for c in range(width)])
        pending = following
    if pending:
        raise BeforeInfoParseError('DANGLING_ROWSPAN')
    return result


def boat(raw: str) -> int:
    if not re.fullmatch(r'[1-6]', raw):
        raise BeforeInfoParseError('INVALID_BOAT_NUMBER')
    return int(raw)


def blank(raw: str) -> bool:
    return raw in {'', '-', '--', '―', '—', 'ー', '欠場'}


@dataclass(frozen=True)
class StartReading:
    raw: str
    marker: str | None
    seconds_magnitude: float | None


def parse_start(raw: str) -> StartReading | None:
    normalized = unicodedata.normalize('NFKC', raw).strip()
    if blank(normalized):
        return None
    # F/L are losslessly retained, never silently converted to ordinary ST.
    if normalized in {'F', 'L'}:
        return StartReading(raw, normalized, None)
    match = re.fullmatch(r'([FL])?((?:[0-9])?\.\d{2})', normalized)
    if match is None:
        raise BeforeInfoParseError('INVALID_START_CELL')
    return StartReading(raw, match[1], float(match[2]))


@dataclass
class BeforeInfoSnapshot:
    exhibition_times: dict[int, float] = field(default_factory=dict)
    entry_courses: dict[int, int] = field(default_factory=dict)
    starts: dict[int, StartReading] = field(default_factory=dict)
    weather: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    # These only describe extraction coverage, never BET/CLOSING eligibility.
    exhibition_six: bool = False
    entry_six: bool = False
    numeric_st_six: bool = False


def _exhibition(table: Tag, out: BeforeInfoSnapshot) -> None:
    if table.find('table') is not None:
        raise BeforeInfoParseError('NESTED_TABLE')
    head = table.find('thead', recursive=False)
    header_rows = head.find_all('tr', recursive=False)
    width = sum(span(c, 'colspan') for c in cells(header_rows[0]))
    expanded = grid(header_rows, width)
    positions = {}
    for key in ('枠', '展示タイム'):
        matches = [c for c in range(width) if any(label(r[c]) == key for r in expanded)]
        if len(matches) != 1:
            raise BeforeInfoParseError('AMBIGUOUS_EXHIBITION_HEADER')
        positions[key] = matches[0]
    seen_ids, seen_boats = {}, set()
    bodies = table.find_all('tbody', recursive=False)
    if not bodies:
        out.missing_fields.append('exhibition_rows')
    for body in bodies:
        rows = body.find_all('tr', recursive=False)
        if not rows:
            continue
        for row in grid(rows, width):
            bcell = row[positions['枠']]
            tcell = row[positions['展示タイム']]
            if id(bcell) in seen_ids:
                if seen_ids[id(bcell)] != id(tcell):
                    raise BeforeInfoParseError('CONFLICTING_SPANNED_TIME')
                continue
            seen_ids[id(bcell)] = id(tcell)
            b = boat(text(bcell))
            if b in seen_boats:
                raise BeforeInfoParseError('DUPLICATE_EXHIBITION_BOAT')
            seen_boats.add(b)
            value = text(row[positions['展示タイム']])
            if blank(value):
                continue
            if not re.fullmatch(r'[1-9]\.\d{2}', value):
                raise BeforeInfoParseError('INVALID_EXHIBITION_TIME')
            out.exhibition_times[b] = float(value)


def _starts(table: Tag, out: BeforeInfoSnapshot) -> None:
    if table.find('table') is not None:
        raise BeforeInfoParseError('NESTED_TABLE')
    head = table.find('thead', recursive=False)
    if not {'コース', '並び', 'ST'} <= {label(c) for c in head.find_all('th')}:
        raise BeforeInfoParseError('START_HEADER_CONTRACT')
    rows = [r for b in table.find_all('tbody', recursive=False) for r in b.find_all('tr', recursive=False)]
    # The known layout encodes course via row position. With a missing row,
    # enumerating the remainder would incorrectly shift every later course.
    if len(rows) != 6:
        out.missing_fields.append('start_rows_six')
        return
    for course, row in enumerate(rows, 1):
        direct = cells(row)
        if len(direct) != 1 or span(direct[0], 'colspan') != 3 or span(direct[0], 'rowspan') != 1:
            raise BeforeInfoParseError('START_ROW_LAYOUT')
        figures = row.select('div.table1_boatImage1')
        if not figures:
            if label(row):
                raise BeforeInfoParseError('UNRECOGNIZED_START_ROW')
            continue
        if len(figures) != 1:
            raise BeforeInfoParseError('AMBIGUOUS_START_ROW')
        numbers = figures[0].select('span.table1_boatImage1Number')
        times = figures[0].select('span.table1_boatImage1Time')
        if len(numbers) != 1 or len(times) > 1:
            raise BeforeInfoParseError('AMBIGUOUS_START_CELLS')
        number_text = text(numbers[0])
        if blank(number_text):
            if times and text(times[0]):
                raise BeforeInfoParseError('START_WITHOUT_BOAT')
            continue
        b = boat(number_text)
        codes = [c for c in numbers[0].get('class', []) if re.fullmatch(r'is-type[1-6]', c)]
        if codes and codes != [f'is-type{b}']:
            raise BeforeInfoParseError('START_BOAT_CLASS_CONFLICT')
        if b in out.entry_courses:
            raise BeforeInfoParseError('DUPLICATE_START_BOAT')
        out.entry_courses[b] = course
        reading = parse_start(times[0].get_text('', strip=True)) if times else None
        if reading is not None:
            out.starts[b] = reading


def _weather(soup: BeautifulSoup, out: BeforeInfoSnapshot) -> None:
    blocks = soup.select('div.weather1')
    if not blocks:
        out.missing_fields.append('weather_section')
        return
    if len(blocks) != 1:
        raise BeforeInfoParseError('AMBIGUOUS_WEATHER_SECTION')
    block = blocks[0]
    titles = block.select('.weather1_title')
    if len(titles) != 1:
        raise BeforeInfoParseError('WEATHER_REFERENCE_MISSING')
    out.weather['reference_text'] = text(titles[0])
    match = re.search(r'(\d{1,2})R時点', label(titles[0]))
    out.weather['reference_race_no'] = int(match[1]) if match else None
    definitions = {'気温': ('air_temperature_c', r'(-?\d{1,2}(?:\.\d)?)°?C'),
                   '水温': ('water_temperature_c', r'(-?\d{1,2}(?:\.\d)?)°?C'),
                   '風速': ('wind_speed_m', r'(\d{1,2}(?:\.\d)?)m'),
                   '波高': ('wave_height_cm', r'(\d{1,3}(?:\.\d)?)cm')}
    seen_weather = set()
    for unit in block.select('.weather1_bodyUnitLabel'):
        names, values = unit.select('.weather1_bodyUnitLabelTitle'), unit.select('.weather1_bodyUnitLabelData')
        if len(names) != 1 or len(values) > 1:
            raise BeforeInfoParseError('AMBIGUOUS_WEATHER_CELLS')
        name = label(names[0])
        if name not in definitions:
            continue
        key, pattern = definitions[name]
        if key in seen_weather:
            raise BeforeInfoParseError('DUPLICATE_WEATHER_VALUE')
        seen_weather.add(key)
        raw = text(values[0]) if values else ''
        if blank(raw):
            continue
        match = re.fullmatch(pattern, raw)
        if match is None:
            raise BeforeInfoParseError('INVALID_WEATHER_VALUE')
        out.weather[key] = float(match[1])
    for key, _ in definitions.values():
        if key not in out.weather:
            out.missing_fields.append('weather_' + key)
    direction = block.select('.is-windDirection .weather1_bodyUnitImage')
    if len(direction) > 1:
        raise BeforeInfoParseError('AMBIGUOUS_WIND_DIRECTION')
    if direction:
        codes = [c for c in direction[0].get('class', []) if re.fullmatch(r'is-wind\d+', c)]
        if len(codes) == 1:
            out.weather['wind_direction_code'] = codes[0]  # no compass guess


def parse_beforeinfo_snapshot(html: str) -> BeforeInfoSnapshot:
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise BeforeInfoParseError('BODY_TYPE_OR_SIZE')
    soup = BeautifulSoup(html, 'html.parser')
    out = BeforeInfoSnapshot()
    exhibitions, starts = [], []
    for table in soup.find_all('table'):
        if table.find_parent('table') is not None:
            continue
        head = table.find('thead', recursive=False)
        labels = {label(c) for c in head.find_all('th')} if head else set()
        if {'枠', '展示タイム'} <= labels:
            exhibitions.append(table)
        if 'スタート展示' in labels:
            starts.append(table)
    if len(exhibitions) > 1 or len(starts) > 1:
        raise BeforeInfoParseError('AMBIGUOUS_DATA_TABLES')
    if exhibitions:
        _exhibition(exhibitions[0], out)
    else:
        out.missing_fields.append('exhibition_section')
    if starts:
        _starts(starts[0], out)
    else:
        out.missing_fields.append('start_section')
    _weather(soup, out)
    expected = set(range(1, 7))
    out.exhibition_six = set(out.exhibition_times) == expected
    out.entry_six = set(out.entry_courses) == expected and set(out.entry_courses.values()) == expected
    out.numeric_st_six = set(out.starts) == expected and all(s.seconds_magnitude is not None for s in out.starts.values())
    for flag, field_name in ((out.exhibition_six, 'exhibition_times_6boats'),
                             (out.entry_six, 'entry_courses_6boats'),
                             (out.numeric_st_six, 'start_st_numeric_6boats')):
        if not flag:
            out.missing_fields.append(field_name)
    return out
