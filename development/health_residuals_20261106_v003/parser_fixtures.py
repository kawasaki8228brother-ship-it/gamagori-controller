"""Synthetic HQ14 R1-R20 descriptions, not originals or official-page evidence."""
DATE = "20990101"
ACQUIRED = "2099-01-01T12:00:00+09:00"
SOURCE = "SYNTHETIC_OFFLINE_STATUS_POLICY"
EXPECTED_RACE_NUMBERS = tuple(range(1, 13))
PENDING_REAL_HTML = {1, 3, 4, 5, 6, 13, 20}
SOURCE_IDENTITY = "SYNTHETIC_DESCRIPTION_REPRODUCTION_ORIGINAL_BYTES_UNVERIFIED"


def _rows(*, names=None, clock=None, state=None, state2=None, reverse=False, spaced=False, br=False):
    result = []
    for number in EXPECTED_RACE_NUMBERS:
        race = f"{number} R" if spaced else f"{number}R"
        time = clock(number) if clock else f"15:{number+10:02d}"
        if br:
            time += "<br/>投票"
        cells = [time, race] if reverse else [race, time]
        if names is not None:
            cells.append(names(number))
        if state is not None:
            cells.append(state(number))
        if state2 is not None:
            cells.append(state2(number))
        result.append("<tr>"+"".join("<td>"+value+"</td>" for value in cells)+"</tr>")
    return result


def _table(rows=None, *, names=False, state_header=None, state_header2=None, reverse=False, sections=False):
    headers = ["投票締切", "レース"] if reverse else ["レース", "投票締切"]
    if names:
        headers.append("レース名")
    if state_header is not None:
        headers.append(state_header)
    if state_header2 is not None:
        headers.append(state_header2)
    header = "<tr>"+"".join("<th>"+value+"</th>" for value in headers)+"</tr>"
    body = "".join(_rows() if rows is None else rows)
    if sections:
        return "<table><thead>"+header+"</thead><tbody>"+body+"</tbody></table>"
    return "<table>"+header+body+"</table>"


def _case(identity, description, html, *, reject=False, reason=None, pending=False, states=None):
    status = states or {}
    flags = {str(number): {"sales_status": status.get(number, "UNKNOWN"),
                           "is_closed": status.get(number) == "CLOSED",
                           "is_cancelled": status.get(number) == "CANCELLED"}
             for number in EXPECTED_RACE_NUMBERS}
    return {"id": identity, "description": description, "html": "<html><body>"+html+"</body></html>",
            "expected_status": "REJECT" if reject else "ACCEPT",
            "expected_seconds": None if reject else {str(n): f"15:{n+10:02d}:00" for n in EXPECTED_RACE_NUMBERS},
            "expected_flags": None if reject else flags, "expected_reason": reason,
            "policy_status": "POLICY_PENDING_REAL_HTML" if pending else "SYNTHETIC_EXPECTATION_ONLY",
            "state_vocabulary_status": "PROPOSED_POLICY_PENDING_OFFICIAL_CONFIRMATION",
            "source_identity": SOURCE_IDENTITY, "date_str": DATE,
            "expected_race_numbers": list(EXPECTED_RACE_NUMBERS),
            "category": "HQ14_R_DESCRIPTION" if identity.startswith("R") else "STATUS_POLICY_SYNTHETIC"}


def cases():
    normal = _table()
    rows = _rows()
    header = "<tr><th>レース</th><th>投票締切</th></tr>"
    omitted = "<table>"+header+"".join(f"<tr><td>{n}R<td>15:{n+10:02d}" for n in EXPECTED_RACE_NUMBERS)+"</table>"
    spans = "<table><tr><th>レース</th><th>投票締切</th><th colspan='2'>補足</th></tr>"
    spans += "".join(f"<tr><td>{n}R</td><td>15:{n+10:02d}</td><td>注A</td><td>注B</td></tr>" for n in EXPECTED_RACE_NUMBERS)+"</table>"
    data = [
        ("R1", "閉じtd/tr省略：合法HTML5であり得るが原本方針待ち", omitted, True, "POLICY_PENDING_REAL_HTML_TABLE_END_TAG_STRUCTURE"),
        ("R2", "thead/tbody", _table(sections=True), False, None),
        ("R3", "レイアウト表内の出走表", "<table><tr><td>"+normal+"</td></tr></table>", True, "POLICY_PENDING_REAL_HTML_TABLE_END_TAG_STRUCTURE"),
        ("R4", "PCとスマホの表2つ", "<section class='pc'>"+normal+"</section><section class='mobile'>"+normal+"</section>", True, "POLICY_PENDING_REAL_HTML_MULTIPLE_SEMANTIC_HEADERS"),
        ("R5", "レースNo.ヘッダ", normal.replace("<th>レース</th>", "<th>レースNo.</th>", 1), True, "POLICY_PENDING_REAL_HTML_HEADER_UNSUPPORTED"),
        ("R6", "締切/レース以外headerのcolspan", spans, True, "POLICY_PENDING_REAL_HTML_MERGED_HEADER"),
        ("R7", "レース名：雨天中止順延記念はnotcancel", _table(_rows(names=lambda n: "雨天中止順延記念"), names=True), False, None),
        ("R8", "レース/締切列の逆順", _table(_rows(reverse=True), reverse=True), False, None),
        ("R9", "非表示の重複1R 00:00", normal.replace("</table>", "<tr hidden style='display:none'><td>1R</td><td>00:00</td></tr></table>"), True, "DUPLICATE_RACE_NUMBER"),
        ("R10", "全角時刻", _table(_rows(clock=lambda n: "１５：２０" if n == 1 else f"15:{n+10:02d}")), True, "DEADLINE_MISSING_INVALID_OR_AMBIGUOUS"),
        ("R11", "時刻25:10", _table(_rows(clock=lambda n: "25:10" if n == 1 else f"15:{n+10:02d}")), True, "DEADLINE_MISSING_INVALID_OR_AMBIGUOUS"),
        ("R12", "時刻なし注記行", normal.replace("</table>", "<tr><td>注記</td><td>本日の注意</td></tr></table>"), False, None),
        ("R13", "時刻あり注記行", normal.replace("</table>", "<tr><td>注記</td><td>18:00更新</td></tr></table>"), True, "POLICY_PENDING_REAL_HTML_TIMED_NONRACE_ROW"),
        ("R14", "1 Rの空白", _table(_rows(spaced=True)), False, None),
        ("R15", "13R", normal.replace("</table>", "<tr><td>13R</td><td>18:00</td></tr></table>"), True, "invalid race count/number"),
        ("R16", "CRLF", normal.replace("><", ">\r\n<"), False, None),
        ("R17", "締切cell br", _table(_rows(br=True)), False, None),
        ("R18", "コメントアウトされたtable", "<!-- "+normal+" -->"+normal, False, None),
        ("R19", "締切cellの時刻除去後exact発売終了はCLOSED", _table(_rows(clock=lambda n: f"15:{n+10:02d} 発売終了")), False, None),
        ("R20", "途中repeated header", "<table>"+header+"".join(rows[:6])+header+"".join(rows[6:])+"</table>", True, "POLICY_PENDING_REAL_HTML_MULTIPLE_SEMANTIC_HEADERS"),
    ]
    result = [_case("NORMAL_12R", "通常12R・状態列なしはUNKNOWN", normal)]
    result += [_case(identity, description, html, reject=reject, reason=reason,
                     pending=int(identity[1:]) in PENDING_REAL_HTML,
                     states={n: "OPEN" for n in EXPECTED_RACE_NUMBERS} if identity == "R17" else
                            {n: "CLOSED" for n in EXPECTED_RACE_NUMBERS} if identity == "R19" else None)
               for identity, description, html, reject, reason in data]
    mapping = {"CANCELLED": "中止", "CLOSED": "発売終了", "OPEN": "発売中", "UNKNOWN": "不明"}
    for status, word in mapping.items():
        result.append(_case("STATUS_"+status, "明示発売状況cellの暫定exact語彙："+status,
                            _table(_rows(state=lambda n, word=word: word), state_header="発売状況"),
                            states={n: status for n in EXPECTED_RACE_NUMBERS}))
    result += [
        _case("STATUS_CONTRADICTORY", "同一状態cellの中止/発売終了はUNKNOWN",
              _table(_rows(state=lambda n: "中止 発売終了"), state_header="状態")),
        _case("STATUS_MULTIPLE_COLUMNS", "複数状態列はUNKNOWN",
              _table(_rows(state=lambda n: "中止", state2=lambda n: "発売中"), state_header="状態", state_header2="発売状況")),
        _case("STATUS_ENGLISH_UNREVIEWED", "未確認英語語彙はUNKNOWN",
              _table(_rows(state=lambda n: "CANCELLED"), state_header="状態")),
        _case("STATUS_NOTE_AND_NAME", "名前/注記cell内の中止等から状態推定しない",
              _table(_rows(names=lambda n: "中止 発売終了 発売中"), names=True)),
    ]
    return result
