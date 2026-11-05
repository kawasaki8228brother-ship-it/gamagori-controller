"""Synthetic E5 a-e compatibility comparisons; no original official HTML."""
DATE = "20990107"
SOURCE = "S"
ACQUIRED = "A"
EXPECTED_RACE_NUMBERS = tuple(range(1, 13))


def cases():
    definitions = [
        ("E5_a", "締切cellの時刻+発売終了", "deadline_closed", "CLOSED"),
        ("E5_b", "明示状態cellの発売終了", "state_closed", "CLOSED"),
        ("E5_c", "時刻だけで状態情報なし", "no_information", "UNKNOWN"),
        ("E5_d", "R7レース名の雨天中止順延記念", "misleading_name", "UNKNOWN"),
        ("E5_e", "一意の状態cellに中止", "state_cancelled", "CANCELLED"),
    ]
    result = []
    for identity, description, mode, status in definitions:
        extra_header = "<th>状態</th>" if mode in ("state_closed", "state_cancelled") else "<th>レース名</th>" if mode == "misleading_name" else ""
        body = []
        for number in EXPECTED_RACE_NUMBERS:
            deadline = f"13:{number:02d}"+(" 発売終了" if mode == "deadline_closed" else "")
            extra = "<td>発売終了</td>" if mode == "state_closed" else "<td>中止</td>" if mode == "state_cancelled" else "<td>雨天中止順延記念</td>" if mode == "misleading_name" else ""
            body.append(f"<tr><td>{number}R</td><td>{deadline}</td>{extra}</tr>")
        html = "<html><body><table><tr><th>レース</th><th>締切予定時刻</th>"+extra_header+"</tr>"+"".join(body)+"</table></body></html>"
        result.append({"id": identity, "description": description, "html": html,
                       "expected_status": "ACCEPT", "expected_reason": None,
                       "expected_seconds": {str(n): f"13:{n:02d}:00" for n in EXPECTED_RACE_NUMBERS},
                       "expected_flags": {str(n): {"sales_status": status, "is_closed": status == "CLOSED", "is_cancelled": status == "CANCELLED"} for n in EXPECTED_RACE_NUMBERS},
                       "policy_status": "POLICY_PENDING_REAL_HTML_VOCABULARY",
                       "source_identity": "SYNTHETIC_E5_DESCRIPTION_ORIGINAL_BYTES_UNVERIFIED",
                       "category": "E5_STATUS_COMPATIBILITY_REPRODUCTION",
                       "date_str": DATE, "expected_race_numbers": list(EXPECTED_RACE_NUMBERS)})
    return result
