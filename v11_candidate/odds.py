"""Fail-closed trifecta parser candidate; no guessed numerical associations.

Supports explicit combination/odds cells and six-column boat matrices with
rowspan second-place cells. Fixtures are synthetic until an independently
captured official HTML response passes regression tests. This is NOT proof
of the exact 2026-09-18 incident response or complete live-data recovery.
"""
from __future__ import annotations
import itertools
import math
import re
import unicodedata
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag


class OddsParseError(ValueError):
    pass


@dataclass(frozen=True)
class OddsSnapshot:
    odds: dict[str, float]
    parser_format: str
    coverage: int
    complete: bool


def _text(node: Tag) -> str:
    return unicodedata.normalize('NFKC', ' '.join(node.stripped_strings)).strip()


def _boat(text: str) -> int:
    if not re.fullmatch(r'[1-6](?:号艇)?', text):
        raise OddsParseError('INVALID_BOAT_CELL')
    return int(text[0])


def _odds(text: str) -> float:
    # No extracting a plausible substring from "12.34", "1.2abc", etc.
    if not re.fullmatch(r'(?:0|[1-9]\d{0,3})(?:\.\d)?', text):
        raise OddsParseError('INVALID_ODDS_CELL')
    value = float(text)
    if not math.isfinite(value) or not 1 <= value <= 9999.9:
        raise OddsParseError('ODDS_OUT_OF_RANGE')
    return value


def _put(out: dict[str, float], boats: tuple[int, int, int], value: float) -> None:
    if len(set(boats)) != 3:
        raise OddsParseError('DUPLICATE_BOAT')
    key = '-'.join(map(str, boats))
    if key in out:
        # Repeated cells—even same-valued—can indicate a layout ambiguity.
        raise OddsParseError('DUPLICATE_COMBINATION')
    out[key] = value


def _cells(row: Tag) -> list[Tag]:
    return row.find_all(['td', 'th'], recursive=False)


def _matrix_header(table: Tag) -> list[int] | None:
    head = table.find('thead', recursive=False)
    if head is None:
        return None
    for row in head.find_all('tr'):
        cells = _cells(row)
        if len(cells) != 6 or any(c.get('colspan') != '3' for c in cells):
            continue
        try:
            boats = [_boat(_text(c)) for c in cells]
        except OddsParseError:
            continue
        if len(set(boats)) != 6:
            raise OddsParseError('DUPLICATE_FIRST_BOAT_HEADER')
        return boats
    return None


def _matrix(table: Tag, firsts: list[int]) -> dict[str, float]:
    """Expand body rowspan cells into a bounded logical 20-by-18 grid."""
    bodies = table.find_all('tbody', recursive=False)
    if not bodies:
        raise OddsParseError('MATRIX_BODY_MISSING')
    rows = [r for b in bodies for r in b.find_all('tr', recursive=False)]
    if len(rows) != 20:
        raise OddsParseError('MATRIX_ROW_COUNT')
    active: dict[int, tuple[Tag, int]] = {}
    out: dict[str, float] = {}
    for row in rows:
        expanded: dict[int, Tag] = {}
        next_active: dict[int, tuple[Tag, int]] = {}
        for col, (cell, remaining) in active.items():
            expanded[col] = cell
            if remaining > 1:
                next_active[col] = (cell, remaining - 1)
        col = 0
        for cell in _cells(row):
            while col in expanded:
                col += 1
            if col >= 18:
                raise OddsParseError('MATRIX_WIDTH')
            try:
                colspan, rowspan = int(cell.get('colspan', '1')), int(cell.get('rowspan', '1'))
            except (TypeError, ValueError) as exc:
                raise OddsParseError('INVALID_SPAN') from exc
            if colspan != 1 or not 1 <= rowspan <= 4:
                raise OddsParseError('UNSUPPORTED_SPAN')
            if rowspan > 1 and col % 3 != 0:
                raise OddsParseError('SPAN_NOT_SECOND_BOAT')
            expanded[col] = cell
            if rowspan > 1:
                next_active[col] = (cell, rowspan - 1)
            col += 1
        if set(expanded) != set(range(18)):
            raise OddsParseError('MATRIX_WIDTH')
        for group, first in enumerate(firsts):
            second = _boat(_text(expanded[group * 3]))
            third = _boat(_text(expanded[group * 3 + 1]))
            _put(out, (first, second, third), _odds(_text(expanded[group * 3 + 2])))
        active = next_active
    if active:
        raise OddsParseError('DANGLING_ROWSPAN')
    return out


def _explicit(table: Tag) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in table.find_all('tr'):
        if row.find_parent('table') is not table:
            raise OddsParseError('NESTED_TABLE')
        cells = _cells(row)
        if len(cells) != 2:
            continue
        match = re.fullmatch(r'([1-6])\s*[-－>]\s*([1-6])\s*[-－>]\s*([1-6])', _text(cells[0]))
        if match is None:
            continue
        _put(out, tuple(map(int, match.groups())), _odds(_text(cells[1])))
    return out


def parse_trifecta(html: str, *, require_complete: bool = True) -> OddsSnapshot:
    """Return exactly 120 entries in production mode; never normalize partial odds.

    Page identity/date/source freshness must be validated by the caller. This
    function does not infer those from odds or treat HTTP 200 as valid evidence.
    """
    if not isinstance(html, str) or len(html) > 2_000_000:
        raise OddsParseError('BODY_TYPE_OR_SIZE')
    soup = BeautifulSoup(html, 'html.parser')
    if '3連単' not in _text(soup):
        raise OddsParseError('TRIFECTA_SECTION_MISSING')
    candidates: list[tuple[dict[str, float], str]] = []
    # Tables must have local semantic anchoring, not just unrelated page text.
    for table in soup.find_all('table'):
        if table.find_parent('table') is not None:
            continue
        caption = table.find('caption', recursive=False)
        heading = table.find_previous(['h1', 'h2', 'h3', 'h4'])
        label = ' '.join(filter(None, [table.get('aria-label'), _text(caption) if caption else None, _text(heading) if heading else None]))
        if '3連単' not in label:
            continue
        if table.find('table') is not None:
            raise OddsParseError('NESTED_TABLE')
        header = _matrix_header(table)
        values = _matrix(table, header) if header is not None else _explicit(table)
        if values:
            candidates.append((values, 'BOAT_MATRIX' if header is not None else 'EXPLICIT_CELLS'))
    if len(candidates) != 1:
        raise OddsParseError('AMBIGUOUS_OR_MISSING_ODDS_TABLE')
    values, fmt = candidates[0]
    expected = {'-'.join(map(str, x)) for x in itertools.permutations(range(1, 7), 3)}
    complete = set(values) == expected
    if require_complete and not complete:
        raise OddsParseError('INCOMPLETE_120_COMBINATIONS')
    return OddsSnapshot(values, fmt, len(values), complete)
