"""HQ14/Claude supplied P1-P14 generator, reproduced locally without network.

Generator definitions were received. Original execution HTML bytes/SHA and old
Claude observations are not authenticated by this reproduction.
"""
DATE = "20990107"
SOURCE = "S"
ACQUIRED = "A"
EXPECTED_RACE_NUMBERS = tuple(range(1, 13))
HDR = "<th>レース</th><th>締切予定時刻/投票</th>"


def rows(nums=range(1, 13), extra=""):
    return "".join(f"<tr><td>{n}R</td><td>13:{n:02d} 投票</td>{extra}</tr>" for n in nums)


def page(before="", hdr=HDR, rws=None, after="", extra_hdr=""):
    return f"<html><body>{before}<table><tr>{hdr}{extra_hdr}</tr>{rws if rws is not None else rows()}</table>{after}</body></html>"


def cases():
    nav = "<ul>"+"".join(f"<li><a>{n}R</a></li>" for n in range(1, 13))+"</ul>"
    full = page()
    htmls = [
        page(),
        page(nav),
        page("<h2>本日の最終 12R</h2>"),
        page(hdr="<td>レース</td><td>締切予定時刻</td>"),
        page(hdr="<th>レース</th><th>投票締切</th>"),
        page(hdr="<th>R</th><th>締切予定</th>"),
        page(extra_hdr="<th>発走</th>", rws=rows(extra="<td>13:15</td>")),
        full[:int(len(full)*0.6)],
        page(after="<table><tr><th>気温</th></tr><tr><td>18℃</td></tr></table>"),
        page(extra_hdr="<th>レース名</th>", rws="".join(
            f'<tr><td>{n}R</td><td>13:{n:02d}</td><td>{"ドリーム12R" if n == 12 else "一般"}</td></tr>' for n in range(1, 13))),
        page(rws=rows(range(1, 12))+"<tr><td>12R</td><td>中止</td></tr>"),
        page(rws="".join(f'<tr><td>{chr(0xFF10+n) if n < 10 else n}Ｒ</td><td>13:{n:02d}</td></tr>' for n in range(1, 13))),
        page(rws="<tr><td>1R</td><td>締切</td></tr>"+rows(range(2, 13))),
        page(rws="".join(f"<tr><td>{n}R</td><td>13:{n:02d}:00</td></tr>" for n in range(1, 13))),
    ]
    descriptions = ["通常12R", "表外1R〜12R nav", "表外最終12R見出し", "td header", "投票締切header",
                    "R/締切予定header", "別の発走時刻列", "先頭60%文字で切断", "表後の気温table",
                    "レース名ドリーム12R", "12R無時刻中止", "全角race label", "1R無時刻締切", "HH:MM:SS秒00"]
    accepted = {1, 2, 3, 4, 5, 6, 7, 9, 10, 14}
    pending_reasons = {
        11: "POLICY_PENDING_REAL_HTML_DEADLINE_CANCEL_LABEL_WITHOUT_TIME",
        13: "POLICY_PENDING_REAL_HTML_DEADLINE_CLOSING_LABEL_WITHOUT_TIME",
    }
    result = []
    for number, html in enumerate(htmls, 1):
        accept = number in accepted
        state = "OPEN" if number in {1, 2, 3, 4, 5, 6, 7, 9} else "UNKNOWN"
        result.append({"id": f"P{number}", "description": descriptions[number-1], "html": html,
                       "expected_status": "ACCEPT" if accept else "REJECT",
                       "expected_seconds": {str(n): f"13:{n:02d}:00" for n in EXPECTED_RACE_NUMBERS} if accept else None,
                       "expected_flags": {str(n): {"sales_status": state, "is_closed": False, "is_cancelled": False}
                                          for n in EXPECTED_RACE_NUMBERS} if accept else None,
                       "expected_reason": pending_reasons.get(number),
                       "policy_status": "POLICY_PENDING_REAL_HTML" if number in pending_reasons else "SYNTHETIC_EXPECTATION_ONLY",
                       "state_vocabulary_status": "PROPOSED_POLICY_PENDING_OFFICIAL_CONFIRMATION",
                       "source_identity": "GENERATOR_RECEIVED_ORIGINAL_BYTES_UNVERIFIED",
                       "date_str": DATE, "expected_race_numbers": list(EXPECTED_RACE_NUMBERS),
                       "category": "HQ14_CLAUDE_P_GENERATOR_REPRODUCTION"})
    return result
