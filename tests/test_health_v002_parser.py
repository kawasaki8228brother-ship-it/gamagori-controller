"""HQ14 description reproductions, not original Claude HTML or live evidence."""
import pytest

from parsers import ParserError, parse_race_index
from development.health_residuals_20261106_v002.parser_fixtures import (
    ACQUIRED, DATE, SOURCE, EXPECTED_RACE_NUMBERS, cases,
)


@pytest.mark.parametrize("case", [case for case in cases() if case["expected_status"] == "ACCEPT"], ids=lambda case: case["id"])
def test_reproducible_normal_and_seven_description_fixtures(case):
    races = parse_race_index(case["html"], DATE, SOURCE, ACQUIRED,
                             expected_race_numbers=EXPECTED_RACE_NUMBERS)
    assert len(races) == 12
    observed = {str(int(race.race_id[-3:-1])): race.official_deadline.strftime("%H:%M:%S") for race in races}
    assert observed == case["expected_seconds"]
    assert all(race.official_deadline.microsecond == 0 for race in races)
    assert case["source_identity"] == "UNVERIFIED_DESCRIPTION_ONLY_NOT_ORIGINAL_HTML"


@pytest.mark.parametrize("case", [case for case in cases() if case["expected_status"] == "REJECT"], ids=lambda case: case["id"])
def test_dangerous_cases_fail_closed(case):
    with pytest.raises(ParserError):
        parse_race_index(case["html"], DATE, SOURCE, ACQUIRED,
                         expected_race_numbers=EXPECTED_RACE_NUMBERS)


@pytest.mark.parametrize("tag,header", [("td", "投票締切時刻"), ("th", "発売締切予定時刻"),
                                        ("td", "締切予定時刻/投票")])
def test_semantically_clear_header_and_data_th_td_variants(tag, header):
    html = f"<table><tr><{tag}>レース</{tag}><{tag}>{header}</{tag}></tr>"
    html += "<tr><th><span>1</span><span>R</span></th><td>15:21:37 投票</td></tr></table>"
    parsed = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})
    assert parsed[0].official_deadline.second == 37


@pytest.mark.parametrize("clock", ["15:21:00", "0:00:01", "23:59:59", "15:21"])
def test_seconds_are_preserved_not_discarded(clock):
    html = f"<table><tr><td>レース</td><td>投票締切</td></tr><tr><td>1R</td><td>{clock}</td></tr></table>"
    deadline = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})[0].official_deadline
    parts = list(map(int, clock.split(":")))
    assert (deadline.hour, deadline.minute, deadline.second) == tuple(parts+[0] if len(parts) == 2 else parts)


@pytest.mark.parametrize("clock", ["15:21:60", "15:21:37.5", "15:21.5", "15:21:37:05",
                                    "24:00:00", "15:60:00", "15:21 15:22:30",
                                    "15:20 25:000", "15:20 99:999", "15:20 25:",
                                    "15:20 12:1", "15:20 :99", "15:20 25：000"])
def test_invalid_or_ambiguous_closing_clock_never_truncates(clock):
    html = f"<table><tr><th>レース</th><th>投票締切</th></tr><tr><td>1R</td><td>{clock}</td></tr></table>"
    with pytest.raises(ParserError):
        parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})


def test_header_reference_and_race_name_labels_do_not_add_records():
    html = """<h2>第12Rの展望</h2><table><tr><td>レース</td><td>締切時刻</td><td>参考2R</td></tr>
    <tr><td>1R</td><td>15:21:05</td><td>1R・12R記念</td></tr></table>"""
    parsed = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})
    assert len(parsed) == 1
    assert parsed[0].official_deadline.second == 5


def test_unanchored_page_labels_alone_do_not_prove_race_or_no_race_day():
    html = "<nav>"+" ".join(f"<a>{n}R</a>" for n in range(1, 13))+"</nav><h2>本日の12R</h2>"
    with pytest.raises(ParserError, match="no race rows"):
        parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers=EXPECTED_RACE_NUMBERS)
