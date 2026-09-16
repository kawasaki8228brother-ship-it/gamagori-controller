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


def parse_race_index(html: str, date_str: str, source_url: str, acquired_at: str) -> List[OfficialRaceInfo]:
    """Fail-closed parser: only rows that clearly contain '<n>R' + HH:MM are accepted."""
    soup = BeautifulSoup(html, "html.parser")
    races: List[OfficialRaceInfo] = []
    seen = set()
    labelled_races = set()

    rows = list(soup.find_all("tr"))
    for tr in rows:
        text = " ".join(tr.stripped_strings)
        race_match = re.search(r"(?:^|\s)(1[0-2]|[1-9])R(?:\s|$)", text)
        if race_match:
            labelled_races.add(int(race_match.group(1)))
        time_match = _TIME_RE.search(text)
        if not race_match or not time_match:
            continue

        race_no = int(race_match.group(1))
        if race_no in seen:
            continue
        hh, mm = int(time_match.group(1)), int(time_match.group(2))
        day = dt.datetime.strptime(date_str, "%Y%m%d").date()
        deadline = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=JST)

        status = "UNKNOWN"
        if "中止" in text or "取りやめ" in text:
            status = "CANCELLED"
        elif "発売終了" in text:
            status = "CLOSED"
        elif "投票" in text or "発売中" in text:
            status = "OPEN"

        races.append(
            OfficialRaceInfo(
                race_id=make_race_id(date_str, race_no),
                official_deadline=deadline,
                is_closed=(status == "CLOSED"),
                is_cancelled=(status == "CANCELLED"),
                sales_status=status,
                source_url=source_url,
                acquired_at=acquired_at,
            )
        )
        seen.add(race_no)

    # BOAT RACE normally runs 12 races; allow fewer only when the page explicitly contains race rows.
    if not races:
        raise ParserError("raceindex: no race rows with race number + deadline found")
    parsed_races = {int(r.race_id[-3:-1]) for r in races}
    if labelled_races and labelled_races != parsed_races:
        raise ParserError(
            f"raceindex: partial parse labelled={sorted(labelled_races)} parsed={sorted(parsed_races)}"
        )
    if len(races) > 12 or any(not 1 <= int(r.race_id[-3:-1]) <= 12 for r in races):
        raise ParserError("raceindex: invalid race count/number")
    return sorted(races, key=lambda x: x.race_id)


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
