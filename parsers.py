from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

from models import JST, LiveDataCompleteness, OfficialRaceInfo, SourceEvidence


class ParserError(ValueError):
    pass


_RACE_ID_RE = re.compile(r"^(\d{8})_GAM_(\d{2})R$")
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")


def make_race_id(date_str: str, race_no: int) -> str:
    return f"{date_str}_GAM_{race_no:02d}R"


def _raceindex_labels(text: str) -> List[str]:
    # Scan broadly enough to reject invalid numbers instead of skipping them.
    return re.findall(r"(?<![A-Za-z0-9])([0-9]+)\s*R(?![A-Za-z])", text, re.IGNORECASE)


def _raceindex_partial(code: str):
    # Fixed codes preserve the legacy error category without echoing HTML/URLs.
    raise ParserError("raceindex: partial parse " + code)


def race_index_status_policy():
    """Candidate vocabulary only; no assertion of real official-page support."""
    return {"status": "PROPOSED_POLICY_PENDING", "official_state_confirmation": "UNVERIFIED",
            "vocabulary_policy_status": "POLICY_PENDING_REAL_HTML",
            "headers": ["発売状況", "状態"],
            "exact_words": {"投票": "OPEN", "発売中": "OPEN", "発売終了": "CLOSED", "締切": "CLOSED",
                            "中止": "CANCELLED", "レース中止": "CANCELLED", "発売中止": "CANCELLED", "取りやめ": "CANCELLED"},
            "scope": "UNIQUE_DEADLINE_AND_OPTIONAL_UNIQUE_STATE_CELL", "fallback": "UNKNOWN",
            "name_note_header_inference": False, "deadline_cell_exact_signal": True,
            "official_source_authentication": "NOT_IMPLEMENTED"}


def _raceindex_status_signal(cell):
    # Preserve token boundaries: split words and contradictory phrases must not
    # become an allowed word after joining. Only complete valid clocks vanish.
    text = " ".join(cell.stripped_strings)
    clock = r"(?<![0-9A-Za-z:.])(?:[01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?(?![0-9A-Za-z:.])"
    rest = " ".join(re.sub(clock, " ", text).split())
    if not rest:
        return None, False
    signal = race_index_status_policy()["exact_words"].get(rest)
    return signal, signal is None


def _raceindex_sales_status(cells, deadline_column, state_columns):
    if len(state_columns) > 1:
        return "UNKNOWN"
    signals = []
    for index in [deadline_column, *state_columns]:
        signal, unknown_rest = _raceindex_status_signal(cells[index])
        if unknown_rest:
            return "UNKNOWN"
        if signal is not None:
            signals.append(signal)
    return signals[0] if signals and len(set(signals)) == 1 else "UNKNOWN"


def _raceindex_expected(expected_race_numbers):
    if expected_race_numbers is None:
        return None
    if isinstance(expected_race_numbers, (str, bytes)):
        raise ParserError("raceindex: invalid expected race count/number")
    try:
        numbers = tuple(expected_race_numbers)
    except TypeError:
        raise ParserError("raceindex: invalid expected race count/number") from None
    if (not 1 <= len(numbers) <= 12 or any(type(n) is not int or not 1 <= n <= 12 for n in numbers)
            or len(set(numbers)) != len(numbers)):
        raise ParserError("raceindex: invalid expected race count/number")
    return set(numbers)


def _raceindex_structure_complete(html: str, table):
    """Gate unreviewed nesting/end tags; this is not an HTML validity verdict."""
    from html.parser import HTMLParser

    class Structure(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.active = []
            self.tables = {}

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                frame = {"stack": ["table"], "valid": not self.active, "closed": False}
                self.tables[self.getpos()] = frame
                if self.active:
                    self.active[-1]["valid"] = False
                self.active.append(frame)
            elif self.active and tag in ("tr", "td", "th"):
                frame = self.active[-1]
                required = "table" if tag == "tr" else "tr"
                if frame["stack"][-1] != required:
                    frame["valid"] = False
                frame["stack"].append(tag)

        def handle_endtag(self, tag):
            if not self.active or tag not in ("table", "tr", "td", "th"):
                return
            frame = self.active[-1]
            if not frame["stack"] or frame["stack"][-1] != tag:
                frame["valid"] = False
            elif frame["stack"]:
                frame["stack"].pop()
            if tag == "table":
                frame["closed"] = True
                self.active.pop()

        def handle_startendtag(self, tag, attrs):
            if self.active and tag in ("table", "tr", "td", "th"):
                self.active[-1]["valid"] = False

    parser = Structure()
    parser.feed(html)
    parser.close()
    frame = parser.tables.get((table.sourceline, table.sourcepos))
    if not frame or not frame["valid"] or not frame["closed"] or frame["stack"]:
        # HTML5 permits some omitted closing tags. Without the real page and a
        # reviewed policy, rejection is a policy boundary, not a validity claim.
        _raceindex_partial("POLICY_PENDING_REAL_HTML_TABLE_END_TAG_STRUCTURE")


def _raceindex_clock(text: str):
    if text.strip() == "中止":
        _raceindex_partial("POLICY_PENDING_REAL_HTML_DEADLINE_CANCEL_LABEL_WITHOUT_TIME")
    if text.strip() == "締切":
        _raceindex_partial("POLICY_PENDING_REAL_HTML_DEADLINE_CLOSING_LABEL_WITHOUT_TIME")
    # Count malformed time-shaped spans too. A valid clock must not hide an
    # additional "25:000", "99:999", short-minute or missing-hour candidate.
    tokens = re.findall(r"[0-9０-９]+(?:[:：][0-9０-９.]*)+|(?<![0-9０-９])[:：][0-9０-９.]+", text)
    if len(tokens) != 1:
        _raceindex_partial("DEADLINE_MISSING_INVALID_OR_AMBIGUOUS")
    match = re.fullmatch(r"([01]?[0-9]|2[0-3]):([0-5][0-9])(?::([0-5][0-9]))?", tokens[0])
    if not match:
        _raceindex_partial("DEADLINE_MISSING_INVALID_OR_AMBIGUOUS")
    return int(match[1]), int(match[2]), int(match[3]) if match[3] is not None else 0


def parse_race_index(html: str, date_str: str, source_url: str, acquired_at: str,
                     *, expected_race_numbers=None) -> List[OfficialRaceInfo]:
    """Semantically anchored table contract; unsupported/partial structure raises.

    Expected numbers must come from caller policy/external schedule evidence.
    None preserves the legacy small-fixture API; it does not prove completeness,
    page date, official origin, or non-race-day status. HTTP 200 is not proof.
    """
    expected = _raceindex_expected(expected_race_numbers)
    if not isinstance(html, str) or not isinstance(date_str, str) or not re.fullmatch(r"[0-9]{8}", date_str):
        raise ParserError("raceindex: invalid HTML/date input")
    try:
        day = dt.datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise ParserError("raceindex: invalid date input") from None
    soup = BeautifulSoup(html, "html.parser")
    for hidden in soup.find_all(["script", "style"]):
        hidden.decompose()
    rows = list(soup.find_all("tr"))
    anchors = []
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        texts = [re.sub(r"\s+", "", "".join(cell.stripped_strings)) for cell in cells]
        # A race's name may itself be "レース" or "投票締切"; a numeric
        # race cell makes this a data row, not a semantic-header candidate.
        if any(re.fullmatch(r"[0-9]+R", text, re.IGNORECASE) for text in texts):
            continue
        race_columns = [i for i, text in enumerate(texts) if text in ("レース", "レース番号", "R")]
        deadline_columns = [i for i, text in enumerate(texts)
                            if re.fullmatch(r"(?:投票|発売)?締切(?:予定)?(?:時刻|時間)?(?:[/／・]?投票)?", text)]
        if race_columns and deadline_columns:
            if len(race_columns) != 1 or len(deadline_columns) != 1 or race_columns[0] == deadline_columns[0]:
                _raceindex_partial("SEMANTIC_HEADER_AMBIGUOUS")
            if any(cell.get("rowspan", "1") != "1" or cell.get("colspan", "1") != "1" for cell in cells):
                _raceindex_partial("POLICY_PENDING_REAL_HTML_MERGED_HEADER")
            anchors.append((row, row.find_parent("table"), race_columns[0], deadline_columns[0], len(cells)))
    if not anchors and not any(_raceindex_labels(" ".join(row.stripped_strings)) for row in rows):
        raise ParserError("raceindex: no race rows with race number + deadline found")
    if not anchors:
        _raceindex_partial("POLICY_PENDING_REAL_HTML_HEADER_UNSUPPORTED")
    if len(anchors) != 1 or anchors[0][1] is None:
        _raceindex_partial("POLICY_PENDING_REAL_HTML_MULTIPLE_SEMANTIC_HEADERS")
    header, table, race_column, deadline_column, width = anchors[0]
    _raceindex_structure_complete(html, table)
    header_cells = header.find_all(["th", "td"], recursive=False)
    state_columns = [index for index, cell in enumerate(header_cells)
                     if re.sub(r"\s+", "", "".join(cell.stripped_strings)) in race_index_status_policy()["headers"]]
    races: List[OfficialRaceInfo] = []
    seen = set()
    header_seen = False
    for row in rows:
        if row.find_parent("table") is not table:
            continue
        if row is header:
            header_seen = True
            continue
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        race_cell = re.sub(r"\s+", "", "".join(cells[race_column].stripped_strings)) if race_column < len(cells) else ""
        canonical = re.fullmatch(r"([0-9]+)R", race_cell, re.IGNORECASE)
        if not canonical:
            # Named headings and labels in race-name/annotation columns are not
            # records. A labelled/missing race cell with a deadline is partial.
            deadline_text = " ".join(cells[deadline_column].stripped_strings) if deadline_column < len(cells) else ""
            if _raceindex_labels(race_cell):
                _raceindex_partial("RACE_CELL_NOT_CANONICAL")
            if re.search(r"[0-9]{1,2}:[0-9]{2}", deadline_text):
                _raceindex_partial("POLICY_PENDING_REAL_HTML_TIMED_NONRACE_ROW")
            continue
        if not header_seen:
            _raceindex_partial("RACE_DATA_PRECEDES_HEADER")
        if len(cells) != width or any(cell.get("rowspan", "1") != "1" or cell.get("colspan", "1") != "1" for cell in cells):
            _raceindex_partial("ROW_CELL_STRUCTURE_CHANGED")
        number = canonical[1]
        if not re.fullmatch(r"(?:1[0-2]|[1-9])", number):
            raise ParserError("raceindex: invalid race count/number")
        race_no = int(number)
        if race_no in seen:
            _raceindex_partial("DUPLICATE_RACE_NUMBER")
        deadline_text = " ".join(cells[deadline_column].stripped_strings)
        if _raceindex_labels(deadline_text):
            _raceindex_partial("DEADLINE_CONTAINS_RACE_LABEL")
        hh, mm, ss = _raceindex_clock(deadline_text)
        deadline = dt.datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=JST)
        status = _raceindex_sales_status(cells, deadline_column, state_columns)
        races.append(OfficialRaceInfo(
            race_id=make_race_id(date_str, race_no), official_deadline=deadline,
            is_closed=(status == "CLOSED"), is_cancelled=(status == "CANCELLED"),
            sales_status=status, source_url=source_url, acquired_at=acquired_at,
        ))
        seen.add(race_no)
    if not races:
        raise ParserError("raceindex: no race rows with race number + deadline found")
    if expected is not None and seen != expected:
        _raceindex_partial("EXPECTED_RACE_SET_MISMATCH")
    if len(races) > 12:
        raise ParserError("raceindex: invalid race count/number")
    return sorted(races, key=lambda race: race.race_id)


def _find_section_table(soup: BeautifulSoup, keywords: Tuple[str, ...]):
    for tag in soup.find_all(["h2", "h3", "h4", "div", "p", "th", "caption"]):
        text = " ".join(tag.stripped_strings)
        if all(k in text for k in keywords):
            table = tag.find_next("table")
            if table:
                return table
    return None


def _parse_boat_rows_with_metric(table, metric_range: Tuple[float, float]) -> Dict[int, float]:
    result: Dict[int, float] = {}
    for tr in table.find_all("tr"):
        cells = [" ".join(td.stripped_strings) for td in tr.find_all(["th", "td"])]
        row_text = " ".join(cells)
        boat_match = re.search(r"(?:^|\s)([1-6])(?:号艇|\s|$)", row_text)
        if not boat_match:
            continue
        boat = int(boat_match.group(1))
        numeric = [float(x) for x in re.findall(r"(?<!\d)(\d+\.\d{2})(?!\d)", row_text)]
        values = [x for x in numeric if metric_range[0] <= x <= metric_range[1]]
        if len(values) == 1:
            result[boat] = values[0]
    return result


def _parse_start_exhibition(table) -> tuple[Dict[int, int], Dict[int, float]]:
    courses: Dict[int, int] = {}
    sts: Dict[int, float] = {}
    for tr in table.find_all("tr"):
        text = " ".join(tr.stripped_strings)
        boat_match = re.search(r"(?:^|\s)([1-6])(?:号艇|\s|$)", text)
        course_match = re.search(r"(?:進入|コース)\s*([1-6])", text)
        st_match = re.search(r"(?:ST|スタート)\s*([+-]?\d\.\d{2})", text, re.IGNORECASE)
        if boat_match and course_match:
            boat = int(boat_match.group(1))
            courses[boat] = int(course_match.group(1))
            if st_match:
                sts[boat] = float(st_match.group(1))
    return courses, sts


def parse_beforeinfo(html: str, source_url: str, acquired_at: str) -> LiveDataCompleteness:
    """Parse only semantically anchored sections. Any structural mismatch becomes MISSING."""
    soup = BeautifulSoup(html, "html.parser")
    missing: List[str] = []

    exhibition_table = _find_section_table(soup, ("展示", "タイム"))
    if not exhibition_table:
        exhibition_times = {}
        missing.append("exhibition_section")
    else:
        exhibition_times = _parse_boat_rows_with_metric(exhibition_table, (5.0, 8.5))
        if set(exhibition_times) != set(range(1, 7)):
            missing.append("exhibition_times_6boats")

    start_table = _find_section_table(soup, ("スタート", "展示"))
    if not start_table:
        entry_courses, start_st = {}, {}
        missing.append("start_exhibition_section")
    else:
        entry_courses, start_st = _parse_start_exhibition(start_table)
        if set(entry_courses) != set(range(1, 7)):
            missing.append("entry_courses_6boats")

    text = " ".join(soup.stripped_strings)
    weather: Dict[str, object] = {}
    wind_speed = re.search(r"風速\s*([0-9]+(?:\.[0-9]+)?)\s*m", text)
    wave = re.search(r"波高\s*([0-9]+(?:\.[0-9]+)?)\s*cm", text)
    wind_dir = re.search(r"(?:風向|風)\s*[:：]?\s*([東西南北]{1,3})", text)
    if wind_speed:
        weather["wind_speed_m"] = float(wind_speed.group(1))
    if wave:
        weather["wave_cm"] = float(wave.group(1))
    if wind_dir:
        weather["wind_dir"] = wind_dir.group(1)
    if not weather:
        missing.append("weather_info")

    return LiveDataCompleteness(
        is_complete=False,  # odds are parsed separately
        exhibition_times=exhibition_times,
        entry_courses=entry_courses,
        start_exhibition_st=start_st,
        weather_info=weather,
        missing_fields=missing,
        source_evidence={
            "beforeinfo": SourceEvidence(
                url=source_url,
                acquired_at=acquired_at,
                status="OK" if not missing else "PARTIAL",
                parser_status="OK" if exhibition_table or start_table else "STRUCTURE_MISMATCH",
            )
        },
    )


def parse_odds3t(html: str, source_url: str, acquired_at: str) -> tuple[Dict[str, float], SourceEvidence]:
    """Fail closed: parse only explicit trifecta combinations and odds from odds section/table text."""
    soup = BeautifulSoup(html, "html.parser")
    page_text = " ".join(soup.stripped_strings)
    if "3連単" not in page_text:
        raise ParserError("odds3t: 3連単 section not found")

    odds: Dict[str, float] = {}
    # Supports forms such as 1-2-3 12.4 or 1 2 3 12.4 inside a row.
    for tr in soup.find_all("tr"):
        text = " ".join(tr.stripped_strings)
        combo = re.search(r"([1-6])\s*[-－>]\s*([1-6])\s*[-－>]\s*([1-6])", text)
        if not combo:
            continue
        a, b, c = combo.groups()
        if len({a, b, c}) != 3:
            continue
        tail = text[combo.end():]
        odd_match = re.search(r"(?<!\d)(\d{1,4}(?:\.\d)?)(?!\d)", tail)
        if odd_match:
            value = float(odd_match.group(1))
            if 1.0 <= value <= 9999.9:
                odds[f"{a}-{b}-{c}"] = value

    if not odds:
        # Some pages flatten cells. Still anchor the search to explicit combos, never arbitrary numbers.
        for combo in re.finditer(r"([1-6])\s*[-－>]\s*([1-6])\s*[-－>]\s*([1-6])\s+(\d{1,4}(?:\.\d)?)", page_text):
            a, b, c, raw = combo.groups()
            if len({a, b, c}) == 3:
                odds[f"{a}-{b}-{c}"] = float(raw)

    if not odds:
        raise ParserError("odds3t: no explicit trifecta+odds pairs found")

    evidence = SourceEvidence(
        url=source_url,
        acquired_at=acquired_at,
        status="OK",
        parser_status="OK",
    )
    return odds, evidence
