"""Invented HTML only; no official 2026-11-05 page or network observations."""
import pytest

from parsers import ParserError, parse_race_index


def table(rows, header="<th>レース</th><th>締切予定時刻/投票</th>"):
    return "<html><body><table><tr>"+header+"</tr>"+"".join(rows)+"</table></body></html>"


def row(number, deadline="15:21", status="投票"):
    return f"<tr><td>{number}R</td><td>{deadline} {status}</td></tr>"


def parse(html, expected=None, date="20990101"):
    return parse_race_index(html, date, "SYNTHETIC_SOURCE_ONLY", "SYNTHETIC_ACQUISITION_METADATA",
                            expected_race_numbers=expected)


def test_synthetic_normal_twelve_and_status_semantics():
    html = table([f"<tr><td>{number}R</td><td>{14+number//6:02}:{number:02}</td>"
                  f"<td>{'発売終了' if number == 2 else '中止' if number == 3 else '発売中'}</td></tr>"
                  for number in range(1, 13)],
                 "<th>レース</th><th>締切予定時刻</th><th>発売状況</th>")
    races = parse(html, range(1, 13))
    assert len(races) == 12
    assert races[0].race_id == "20990101_GAM_01R"
    assert races[1].is_closed is True
    assert races[2].is_cancelled is True
    assert races[-1].official_deadline.minute == 12


def test_legacy_three_rows_remain_supported_without_completeness_claim():
    html = table([row(1), row(2, "15:48", "発売終了"), row(3, "16:14", "中止")])
    legacy = parse_race_index(html, "20990101", "u", "t")
    assert len(legacy) == 3
    assert len(parse(html, {1, 2, 3})) == 3
    with pytest.raises(ParserError, match="EXPECTED_RACE_SET_MISMATCH"):
        parse(html, range(1, 13))


@pytest.mark.parametrize("numbers", [range(1, 12), [n for n in range(1, 13) if n != 7]])
def test_missing_tail_or_middle_requires_exact_expected_set(numbers):
    with pytest.raises(ParserError, match="partial parse EXPECTED_RACE_SET_MISMATCH"):
        parse(table([row(n) for n in numbers]), range(1, 13))


@pytest.mark.parametrize("deadline", ["", "時刻取得失敗", "25:00", "13:60", "13:00:60"])
def test_missing_or_invalid_deadline_never_partially_accepts_other_rows(deadline):
    with pytest.raises(ParserError, match="partial parse"):
        parse(table([row(1), row(2, deadline)]))


@pytest.mark.parametrize("rows,header,expected_minute", [
    ([row(1, "15:21 15:31")], "<th>レース</th><th>締切予定時刻</th>", None),
    (["<tr><td>1R</td><td>14:00</td><td>15:21 投票</td></tr>"],
     "<th>レース</th><th>更新時刻</th><th>締切予定時刻</th>", 21)])
def test_multiple_times_do_not_choose_first_hhmm(rows, header, expected_minute):
    if expected_minute is None:
        with pytest.raises(ParserError, match="DEADLINE_MISSING_INVALID_OR_AMBIGUOUS"):
            parse(table(rows, header))
    else:
        assert parse(table(rows, header))[0].official_deadline.minute == expected_minute


@pytest.mark.parametrize("second", [row(1), row(1, "16:40")])
def test_all_duplicate_race_rows_rejected_including_identical_duplicates(second):
    with pytest.raises(ParserError, match="DUPLICATE_RACE_NUMBER"):
        parse(table([row(1), second]))


@pytest.mark.parametrize("bad", ["<tr><td>1R 2R</td><td>15:21</td></tr>",
                                  "<tr><td>1R</td><td>2R 15:21</td></tr>"])
def test_multiple_race_labels_in_one_row_rejected(bad):
    with pytest.raises(ParserError, match="partial parse"):
        parse(table([bad]))


@pytest.mark.parametrize("number", [0, 13, "01", "1234"])
def test_invalid_race_numbers_not_silently_skipped(number):
    with pytest.raises(ParserError, match="invalid race count/number"):
        parse(table([row(1), row(number)]))


@pytest.mark.parametrize("extra", ["<div>3R 18:30</div>", "<div>1R15:00</div>",
                                     "<table><tr><td>3R</td><td>18:30</td></tr></table>"])
def test_labels_outside_semantic_table_are_not_race_records(extra):
    assert len(parse(table([row(1), row(2)])+extra)) == 2


@pytest.mark.parametrize("html", [
    "<table>"+row(1)+"</table>",
    table([row(1)], "<th>レース</th><th>発走時刻</th>"),
    table([row(1)], "<th>レース</th><th>締切後更新時刻</th>"),
    table(["<tr><td>1R</td><td>15:21</td><td>15:31</td></tr>"],
          "<th>レース</th><th>締切時刻</th><th>締切予定時刻</th>"),
    table(["<tr><td>1R</td></tr>"]),
    table(["<tr><td colspan='2'>1R 15:21</td></tr>"]),
    table(["<tr><td>1R</td><td>15:21</td><td>取得失敗</td></tr>"],
          "<th>レース</th><th>更新時刻</th><th>締切予定時刻</th>")])
def test_missing_ambiguous_or_changed_header_cell_structure_holds(html):
    with pytest.raises(ParserError, match="partial parse"):
        parse(html)


@pytest.mark.parametrize("expected", [[], [1, 1], [0], [13], [True], [1.0], "123"])
def test_invalid_expected_manifest_is_not_inferred_from_page(expected):
    with pytest.raises(ParserError, match="invalid expected race count/number"):
        parse(table([row(1)]), expected)


def test_empty_http_body_is_error_not_verified_no_race_day_and_date_input_checked():
    # A successful HTTP status does not make this body a parse success.
    http_200_body = "<html><body>No scheduled content available</body></html>"
    with pytest.raises(ParserError, match="no race rows with race number \\+ deadline found"):
        parse(http_200_body, range(1, 13))
    for invalid in ("20990230", "2099-01-01", "", None):
        with pytest.raises(ParserError, match="date input"):
            parse(table([row(1)]), date=invalid)
