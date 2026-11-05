"""Synthetic R1-R20 and provisional explicit-cell status policy checks."""
import pytest

from parsers import ParserError, parse_race_index, race_index_status_policy
from development.health_residuals_20261106_v003.parser_fixtures import (
    ACQUIRED, DATE, SOURCE, EXPECTED_RACE_NUMBERS, PENDING_REAL_HTML, cases,
)
from development.health_residuals_20261106_v003 import e5_fixtures, p_fixtures


@pytest.mark.parametrize("case", [case for case in cases() if case["expected_status"] == "ACCEPT"], ids=lambda case: case["id"])
def test_r_descriptions_and_status_cells_expected_outputs(case):
    parsed = parse_race_index(case["html"], DATE, SOURCE, ACQUIRED, expected_race_numbers=EXPECTED_RACE_NUMBERS)
    times, flags = {}, {}
    for info in parsed:
        number = str(int(info.race_id[-3:-1]))
        times[number] = info.official_deadline.strftime("%H:%M:%S")
        flags[number] = {"sales_status": info.sales_status, "is_closed": info.is_closed, "is_cancelled": info.is_cancelled}
    assert times == case["expected_seconds"]
    assert flags == case["expected_flags"]
    assert len(parsed) == 12


@pytest.mark.parametrize("case", [case for case in cases() if case["expected_status"] == "REJECT"], ids=lambda case: case["id"])
def test_pending_or_dangerous_structure_refuses_with_precise_reason(case):
    with pytest.raises(ParserError) as caught:
        parse_race_index(case["html"], DATE, SOURCE, ACQUIRED, expected_race_numbers=EXPECTED_RACE_NUMBERS)
    assert case["expected_reason"] in str(caught.value)
    if int(case["id"][1:]) in PENDING_REAL_HTML:
        assert case["policy_status"] == "POLICY_PENDING_REAL_HTML"
        assert "POLICY_PENDING_REAL_HTML" in str(caught.value)
        assert "TRUNCATED" not in str(caught.value)


@pytest.mark.parametrize("header,word", [("状態", "中止/発売終了"), ("発売状況", "発売終了（確認中）"),
                                        ("状態", "投票受付中"), ("状態", "CANCELLED"),
                                        ("状態", "<span>中</span><span>止</span>"),
                                        ("status", "中止"), ("販売状況", "中止"), ("状態", "")])
def test_ambiguous_unknown_or_unreviewed_vocabulary_is_safe_unknown(header, word):
    html = f"<table><tr><th>レース</th><th>投票締切</th><th>{header}</th></tr>"
    html += f"<tr><td>1R</td><td>15:21</td><td>{word}</td></tr></table>"
    race = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})[0]
    assert race.sales_status == "UNKNOWN"
    assert race.is_cancelled is False
    assert race.is_closed is False


def test_pending_policy_metadata_is_not_official_authentication():
    policy = race_index_status_policy()
    assert policy["status"] == "PROPOSED_POLICY_PENDING"
    assert policy["official_state_confirmation"] == "UNVERIFIED"
    assert policy["name_note_header_inference"] is False
    assert policy["deadline_cell_exact_signal"] is True
    assert policy["vocabulary_policy_status"] == "POLICY_PENDING_REAL_HTML"
    assert policy["official_source_authentication"] == "NOT_IMPLEMENTED"
    assert policy["headers"] == ["発売状況", "状態"]
    policy["exact_words"]["雨天中止順延記念"] = "CANCELLED"
    assert "雨天中止順延記念" not in race_index_status_policy()["exact_words"]


def test_r_fixture_definition_count_and_pending_group():
    fixtures = cases()
    assert {case["id"] for case in fixtures if case["id"].startswith("R")} == {f"R{n}" for n in range(1, 21)}
    assert {int(case["id"][1:]) for case in fixtures if case["policy_status"] == "POLICY_PENDING_REAL_HTML"} == PENDING_REAL_HTML
    assert all("UNVERIFIED" in case["source_identity"] for case in fixtures)


@pytest.mark.parametrize("case", p_fixtures.cases(), ids=lambda case: case["id"])
def test_received_p_generator_expectations_without_claiming_original_bytes(case):
    if case["expected_status"] == "REJECT":
        with pytest.raises(ParserError) as caught:
            parse_race_index(case["html"], p_fixtures.DATE, p_fixtures.SOURCE, p_fixtures.ACQUIRED,
                             expected_race_numbers=p_fixtures.EXPECTED_RACE_NUMBERS)
        if case["expected_reason"] is not None:
            assert case["expected_reason"] in str(caught.value)
    else:
        parsed = parse_race_index(case["html"], p_fixtures.DATE, p_fixtures.SOURCE, p_fixtures.ACQUIRED,
                                  expected_race_numbers=p_fixtures.EXPECTED_RACE_NUMBERS)
        observed = {str(int(info.race_id[-3:-1])): info.official_deadline.strftime("%H:%M:%S") for info in parsed}
        flags = {str(int(info.race_id[-3:-1])): {"sales_status": info.sales_status,
                                             "is_closed": info.is_closed, "is_cancelled": info.is_cancelled} for info in parsed}
        assert observed == case["expected_seconds"]
        assert flags == case["expected_flags"]
        assert len(parsed) == 12
    assert case["source_identity"] == "GENERATOR_RECEIVED_ORIGINAL_BYTES_UNVERIFIED"


@pytest.mark.parametrize("case", e5_fixtures.cases(), ids=lambda case: case["id"])
def test_e5_compatibility_and_no_information_or_name_fallback(case):
    parsed = parse_race_index(case["html"], e5_fixtures.DATE, e5_fixtures.SOURCE, e5_fixtures.ACQUIRED,
                             expected_race_numbers=e5_fixtures.EXPECTED_RACE_NUMBERS)
    flags = {str(int(info.race_id[-3:-1])): {"sales_status": info.sales_status,
                                         "is_closed": info.is_closed, "is_cancelled": info.is_cancelled} for info in parsed}
    assert flags == case["expected_flags"]
    assert len(parsed) == 12


@pytest.mark.parametrize("word,status", [("発売終了", "CLOSED"), ("締切", "CLOSED"),
                                         ("中止", "CANCELLED"), ("レース中止", "CANCELLED"),
                                         ("発売中止", "CANCELLED"), ("取りやめ", "CANCELLED"),
                                         ("投票", "OPEN"), ("発売中", "OPEN")])
@pytest.mark.parametrize("position", ["deadline", "state"])
def test_exact_provisional_words_in_allowed_cell_only(word, status, position):
    closing = "13:01:37 "+word if position == "deadline" else "13:01:37"
    extra_header, extra = ("<th>状態</th>", "<td>"+word+"</td>") if position == "state" else ("", "")
    html = "<table><tr><th>レース</th><th>投票締切</th>"+extra_header+"</tr>"
    html += "<tr><td>1R</td><td>"+closing+"</td>"+extra+"</tr></table>"
    info = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})[0]
    assert info.sales_status == status
    assert info.is_cancelled is (status == "CANCELLED")
    assert info.is_closed is (status == "CLOSED")
    assert info.official_deadline.second == 37


@pytest.mark.parametrize("closing,state,expected", [
    ("13:01 投票", "中止", "UNKNOWN"),
    ("13:01 発売終了", "発売中", "UNKNOWN"),
    ("13:01 発売終了", "調査中", "UNKNOWN"),
    ("13:01 備考", "中止", "UNKNOWN"),
    ("13:01 発売終了", "発売終了", "CLOSED"),
    ("13:01", "", "UNKNOWN"),
    ("13:01", "１３：０１ 中止", "UNKNOWN"),
])
def test_conflicting_signals_unknown_rest_and_neutral_cells(closing, state, expected):
    html = "<table><tr><th>レース</th><th>締切時刻</th><th>状態</th></tr>"
    html += f"<tr><td>1R</td><td>{closing}</td><td>{state}</td></tr></table>"
    info = parse_race_index(html, DATE, SOURCE, ACQUIRED, expected_race_numbers={1})[0]
    assert info.sales_status == expected
    assert info.is_cancelled is False
    assert info.is_closed is (expected == "CLOSED")
