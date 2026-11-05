"""Compare parser boundaries on invented HTML, never actual 11/5 originals."""
import argparse
import json
from pathlib import Path
import platform
import socket
import sys


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_PARSER_REPRO")


def page(rows, extra=""):
    return "<html><body><table><tr><th>レース</th><th>締切予定時刻/投票</th></tr>" + rows + "</table>" + extra + "</body></html>"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--label", choices=("BASELINE", "CANDIDATE"), required=True)
    args = parser.parse_args()
    socket.socket.connect = socket.create_connection = socket.getaddrinfo = blocked
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo.resolve()))
    from parsers import ParserError, parse_race_index
    cases = {
        "normal_twelve": page("".join(f"<tr><td>{number}R</td><td>13:{(number-1)*5:02} 投票</td></tr>" for number in range(1, 13))),
        "multiple_times": page("<tr><td>1R</td><td>13:00 13:15 投票</td></tr>"),
        "conflicting_duplicate": page("<tr><td>1R</td><td>13:00 投票</td></tr><tr><td>1R</td><td>13:15 投票</td></tr>"),
        "row_outside_table": page("<tr><td>1R</td><td>13:00 投票</td></tr>", "<div>2R 13:30 投票</div>"),
        "partial_missing_deadline": page("<tr><td>1R</td><td>13:00 投票</td></tr><tr><td>2R</td><td>未確認 投票</td></tr>"),
        "empty_no_race_message_only": page("", "<div>本日開催なし</div>"),
    }
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "classification": "SYNTHETIC_ONLY",
        "network": "BLOCKED", "label": args.label, "production_go": False}, sort_keys=True), flush=True)
    reports = {}
    for name, html in cases.items():
        try:
            races = parse_race_index(html, "20990107", "SYNTHETIC_ONLY", "2099-01-07T12:00:00+09:00")
            reports[name] = {"status": "PARSED", "races": [race.model_dump(mode="json") for race in races]}
        except ParserError:
            reports[name] = {"status": "REJECTED_PARSER_ERROR"}
    print(json.dumps({"label": args.label, "classification": "SYNTHETIC_ONLY", "cases": reports,
        "actual_11_05_root_cause": "UNVERIFIED", "production_go": False}, sort_keys=True))
