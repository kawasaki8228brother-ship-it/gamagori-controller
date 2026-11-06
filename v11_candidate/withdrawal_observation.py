"""Observe exact withdrawal text without deciding official race status.

Scope: the existing six-row beforeinfo layout's exhibition-time and start-ST
cells only. A raw token elsewhere, an empty cell, F/L or absence of a token is
NOT an ACTIVE/WITHDRAWN decision. Real withdrawal layouts remain unvalidated.
No caller in the runtime is wired to this optional pure scanner.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import unicodedata
from bs4 import BeautifulSoup, Tag

from . import beforeinfo as parser
from . import table_selection


@dataclass(frozen=True)
class WithdrawalTextSignal:
    boat: int
    section: str
    field: str
    raw_text: str
    normalized_text: str
    locator: str
    body_sha256: str
    kind: str = 'WITHDRAWAL_TEXT_OBSERVED'


@dataclass(frozen=True)
class SectionScan:
    section: str
    state: str  # SCANNED / PARTIAL / MISSING / PARSE_FAILED
    error_code: str | None = None


@dataclass(frozen=True)
class WithdrawalScan:
    body_sha256: str
    signals: tuple[WithdrawalTextSignal, ...]
    sections: tuple[SectionScan, ...]
    coexisting_observations: tuple[str, ...]
    # These are deliberately not caller-set acceptance decisions.
    # They only document the boundary of this extraction result.
    official_status_verified: bool = False
    page_identity_verified: bool = False
    source_effective_at: None = None


def _signal(cell: Tag, *, boat: int, section: str, field: str,
            locator: str, digest: str) -> WithdrawalTextSignal | None:
    raw = cell.get_text('', strip=False)
    normalized = unicodedata.normalize('NFKC', raw).strip()
    if normalized != '欠場':
        return None
    return WithdrawalTextSignal(boat, section, field, raw, normalized, locator, digest)


def _exhibition_signals(table: Tag, index: int, digest: str):
    """Validate the entire section before returning even one marker."""
    staged = parser.BeforeInfoSnapshot()
    parser._exhibition(table, staged)
    heads = table.find('thead', recursive=False).find_all('tr', recursive=False)
    width = sum(parser.span(c, 'colspan') for c in parser.cells(heads[0]))
    expanded = parser.grid(heads, width)
    positions = {key: next(c for c in range(width) if any(parser.label(r[c]) == key for r in expanded))
                 for key in ('枠', '展示タイム')}
    seen, found = set(), []
    bodies = table.find_all('tbody', recursive=False)
    for bi, body in enumerate(bodies, 1):
        rows = body.find_all('tr', recursive=False)
        if not rows:
            continue
        for ri, row in enumerate(parser.grid(rows, width), 1):
            bcell, tcell = row[positions['枠']], row[positions['展示タイム']]
            if id(bcell) in seen:
                continue
            seen.add(id(bcell))
            number = parser.boat(parser.text(bcell))
            # The absolute table index and logical column work with rowspans.
            locator = f'table[{index}]/tbody[{bi}]/tr[{ri}]/logical-column[{positions["展示タイム"]+1}]'
            signal = _signal(tcell, boat=number, section='exhibition', field='exhibition_time',
                             locator=locator, digest=digest)
            if signal:
                found.append(signal)
    return found, staged, 'SCANNED' if len(seen) == 6 else 'PARTIAL'


def _start_signals(table: Tag, index: int, digest: str):
    staged = parser.BeforeInfoSnapshot()
    parser._starts(table, staged)
    if 'start_rows_six' in staged.missing_fields:
        # Never slide five rows into six course positions or guess a boat.
        return [], staged, 'PARTIAL'
    found = []
    for bi, body in enumerate(table.find_all('tbody', recursive=False), 1):
        for ri, row in enumerate(body.find_all('tr', recursive=False), 1):
            figures = row.select('div.table1_boatImage1')
            if not figures:
                continue
            # Layout, duplicates and boat/class agreement validated by _starts.
            numbers = figures[0].select('span.table1_boatImage1Number')
            times = figures[0].select('span.table1_boatImage1Time')
            raw_number = parser.text(numbers[0])
            if parser.blank(raw_number) or not times:
                continue
            number = parser.boat(raw_number)
            locator = f'table[{index}]/tbody[{bi}]/tr[{ri}]/.table1_boatImage1Time'
            signal = _signal(times[0], boat=number, section='start', field='start_st',
                             locator=locator, digest=digest)
            if signal:
                found.append(signal)
    return found, staged, 'SCANNED' if len(staged.entry_courses) == 6 else 'PARTIAL'


def scan_withdrawal_text(body: bytes) -> WithdrawalScan:
    """Return source-byte-bound observations, never an official withdrawal set.

    Identity, authenticated acquisition, source semantics and state-at-decision
    require separate verification. UTF-8 input only; no guessed decoding.
    Unknown or malformed sections publish no valid-looking marker prefixes.
    Existing strict parser/coverage/readiness APIs are deliberately unchanged.
    """
    if type(body) is not bytes or len(body) > 2_000_000:
        raise parser.BeforeInfoParseError('BODY_TYPE_OR_SIZE')
    try:
        html = body.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise parser.BeforeInfoParseError('BODY_ENCODING') from exc
    digest = hashlib.sha256(body).hexdigest()
    soup = BeautifulSoup(html, 'html.parser')
    candidates = table_selection.select_beforeinfo_tables(soup)
    signals, reports, parsed = [], [], {}
    for section, parse in (('exhibition', _exhibition_signals), ('start', _start_signals)):
        tables = candidates[section]
        if not tables:
            reports.append(SectionScan(section, 'MISSING'))
            continue
        try:
            if len(tables) != 1:
                raise parser.BeforeInfoParseError('AMBIGUOUS_DATA_TABLES')
            index, table = tables[0].absolute_index, tables[0].table
            found, snapshot, state = parse(table, index, digest)
        except Exception as exc:
            code = str(exc) if isinstance(exc, parser.BeforeInfoParseError) else 'UNEXPECTED_SECTION_ERROR:' + type(exc).__name__
            reports.append(SectionScan(section, 'PARSE_FAILED', code))
            continue
        signals.extend(found)
        parsed[section] = snapshot
        reports.append(SectionScan(section, state))
    # Coexistence can reflect changing or stale states; do not resolve it by
    # declaring the text or the numeric field to be the authoritative winner.
    notes = []
    for b in sorted({s.boat for s in signals}):
        if 'exhibition' in parsed and b in parsed['exhibition'].exhibition_times:
            notes.append(f'BOAT_{b}:WITHDRAWAL_TEXT_AND_NUMERIC_EXHIBITION')
        if 'start' in parsed and b in parsed['start'].starts:
            notes.append(f'BOAT_{b}:WITHDRAWAL_TEXT_AND_START_READING')
    return WithdrawalScan(digest, tuple(signals), tuple(reports), tuple(notes))
