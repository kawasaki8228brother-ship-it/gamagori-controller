"""Reproductions of HQ14's seven descriptions; original HTML bytes UNVERIFIED.

No source request, private content or actual schedule is included. All expected
deadlines are invented 2099 fixture values, not observations of an official page.
"""
DATE = "20990101"
ACQUIRED = "2099-01-01T12:00:00+09:00"
SOURCE = "SYNTHETIC_OFFLINE_HTML"
EXPECTED_RACE_NUMBERS = tuple(range(1, 13))
SOURCE_IDENTITY = "UNVERIFIED_DESCRIPTION_ONLY_NOT_ORIGINAL_HTML"


def _row(number, deadline=None, *, name=False, other_time=False, race_tag="td"):
    deadline = f"15:{number+10:02d}" if deadline is None else deadline
    extra = "<td>12R特別戦</td>" if name else "<td>14:00</td>" if other_time else ""
    return f"<tr><{race_tag}>{number}R</{race_tag}>{extra}<td>{deadline} 投票</td></tr>"


def _page(rows, *, header_tag="th", deadline_header="締切予定時刻/投票", name=False, other_time=False, outside=""):
    extra = f"<{header_tag}>レース名</{header_tag}>" if name else f"<{header_tag}>更新時刻</{header_tag}>" if other_time else ""
    header = f"<tr><{header_tag}>レース</{header_tag}>{extra}<{header_tag}>{deadline_header}</{header_tag}></tr>"
    return "<html><body>"+outside+"<table>"+header+"".join(rows)+"</table></body></html>"


def normal_12r():
    return _page([_row(number) for number in EXPECTED_RACE_NUMBERS])


def _case(identity, description, html, category, seconds=False, reject=False):
    return {"id": identity, "description": description, "html": html,
            "category": category, "expected_status": "REJECT" if reject else "ACCEPT",
            "expected_seconds": None if reject else {
                str(number): f"15:{number+10:02d}:{number if seconds else 0:02d}"
                for number in EXPECTED_RACE_NUMBERS},
            "source_identity": SOURCE_IDENTITY,
            "date_str": DATE, "expected_race_numbers": list(EXPECTED_RACE_NUMBERS)}


def cases():
    """Baseline + seven one-to-one description fixtures + dangerous cases."""
    rows = [_row(number) for number in EXPECTED_RACE_NUMBERS]
    category = "HQ14_DESCRIPTION_REPRODUCTION"
    result = [_case("BASELINE_12R", "Invented ordinary full 12R table", normal_12r(), "BASELINE")]
    tabs = "<nav>"+" ".join(f"<a>{number}R</a>" for number in EXPECTED_RACE_NUMBERS)+"</nav>"
    result += [
        _case("S1_F01", "表外1R〜12Rタブ", _page(rows, outside=tabs), category),
        _case("S1_F02", "表外見出し12R", _page(rows, outside="<h2>本日の12R特集</h2>"), category),
        _case("S1_F03", "ヘッダtd", _page(rows, header_tag="td"), category),
        _case("S1_F04", "投票締切", _page(rows, deadline_header="投票締切"), category),
        _case("S1_F05", "別列に2つ目の時刻・確定締切列のみ採用",
              _page([_row(n, other_time=True) for n in EXPECTED_RACE_NUMBERS], other_time=True), category),
        _case("S1_F06", "レース名12R",
              _page([_row(n, name=True) for n in EXPECTED_RACE_NUMBERS], name=True), category),
        _case("S1_F07", "HH:MM:SS秒保持",
              _page([_row(n, f"15:{n+10:02d}:{n:02d}") for n in EXPECTED_RACE_NUMBERS]), category, seconds=True),
    ]
    result += [
        _case("D01_CONFLICT_DUPLICATE", "Conflicting duplicate race 1", _page(rows+[_row(1, "18:59")]), "DANGER", reject=True),
        _case("D02_MISSING_TAIL", "Expected race 12 absent", _page(rows[:-1]), "DANGER", reject=True),
        _case("D03_MISSING_DEADLINE", "Race 6 closing time absent",
              _page([_row(n, "取得失敗") if n == 6 else _row(n) for n in EXPECTED_RACE_NUMBERS]), "DANGER", reject=True),
        _case("D04_AMBIGUOUS_CLOSING_CELL", "Two clocks in the same closing cell",
              _page([_row(n, "15:16 15:17") if n == 6 else _row(n) for n in EXPECTED_RACE_NUMBERS]), "DANGER", reject=True),
        _case("D05_TWO_CLOSING_COLUMNS", "Two equally closing-semantic columns",
              _page([_row(n, other_time=True) for n in EXPECTED_RACE_NUMBERS], other_time=True).replace("更新時刻", "投票締切"), "DANGER", reject=True),
        _case("D06_INVALID_SECONDS", "Seconds 60 are invalid",
              _page([_row(n, "15:16:60") if n == 6 else _row(n) for n in EXPECTED_RACE_NUMBERS]), "DANGER", reject=True),
        _case("D07_MULTIPLE_RACE_CELL", "Two race labels in the race-number cell",
              _page(rows).replace("<td>1R</td>", "<td>1R 2R</td>", 1), "DANGER", reject=True),
        _case("D08_TRUNCATED_TABLE", "Full labels but missing final closing tags",
              normal_12r().rsplit("</td>", 1)[0], "DANGER", reject=True),
        _case("D09_NO_CLOSING_HEADER", "Start time is not a closing-time header",
              _page(rows, deadline_header="発走時刻"), "DANGER", reject=True),
        _case("D10_MULTIPLE_TABLES", "Two complete semantic race tables",
              normal_12r()+normal_12r(), "DANGER", reject=True),
        _case("D11_MALFORMED_EXTRA_CLOCK", "Valid closing clock plus malformed second clock",
              _page([_row(n, "15:20 25:000") if n == 6 else _row(n) for n in EXPECTED_RACE_NUMBERS]), "DANGER", reject=True),
    ]
    return result
