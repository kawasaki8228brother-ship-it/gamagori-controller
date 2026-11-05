"""Invented HTML only; transport, active parser and production remain untouched."""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from development.health_offline_completion_v004.html_research import inspect_research_html
from development.health_offline_completion_v004 import inspect_private_html as private_check

DAY = "20990107"


def table(*, name=None, other_header="", other_cell="", state=None, clock=lambda n: f"13:{n:02d}"):
    header = "<tr><th>レース</th><th>投票締切</th>" + ("<th>レース名</th>" if name else "") + ("<th>状態</th>" if state else "") + other_header + "</tr>"
    rows = []
    for n in range(1, 13):
        cells = f"<td>{n}R</td><td>{clock(n)}</td>" + (f"<td>{name(n)}</td>" if name else "") + (f"<td>{state(n)}</td>" if state else "") + other_cell
        rows.append("<tr>" + cells + "</tr>")
    return "<table>" + header + "".join(rows) + "</table>"


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.block = patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.block.start()
    def tearDown(self):
        self.block.stop()

    def assert_research(self, value):
        self.assertEqual(value["status"], "RESEARCH_PARSED", value["reason"])
        self.assertEqual(len(value["records"]), 12)
        self.assertFalse(value["go"])
        self.assertFalse(value["runtime_execution_allowed"])
        self.assertEqual(value["official_compatibility"], "UNVERIFIED")
        self.assertEqual(value["policy_status"], "POLICY_PENDING_REAL_HTML")

    def test_normal_and_legal_optional_end_candidates(self):
        normal = inspect_research_html(table(), DAY)
        self.assert_research(normal)
        rows = "".join(f"<tr><td>{n}R<td>13:{n:02d}" for n in range(1, 13))
        omitted = "<table><tr><th>レース<th>投票締切" + rows + "</table>"
        answer = inspect_research_html(omitted, DAY)
        self.assert_research(answer)
        self.assertEqual(answer["records"], normal["records"])
        self.assertIn("OPTIONAL_CELL_ROW_ENDS", answer["normalization"]["forms"])

    def test_no_eof_repair_or_twelve_row_table_authentication(self):
        for html in (table()[:-8], table().replace("</table>", ""), "<table><tr><td>1R</td><td>13:01</td></tr></table>"):
            with self.subTest(case=len(html)):
                value = inspect_research_html(html, DAY)
                self.assertEqual(value["status"], "HOLD")
                self.assertFalse(value["go"])
                self.assertIsNone(value["records"])
        self.assertEqual(inspect_research_html(table(), DAY)["official_compatibility"], "UNVERIFIED")

    def test_nested_layout_candidate_is_research_only(self):
        nested = "<table><tr><td>layout" + table() + "</td></tr></table>"
        answer = inspect_research_html(nested, DAY)
        self.assert_research(answer)
        self.assertIn("LAYOUT_NESTING", answer["normalization"]["forms"])

    def test_equal_pc_mobile_tables_and_one_conflicting_value(self):
        same = "<section class='pc'>" + table() + "</section><section class='mobile'>" + table() + "</section>"
        answer = inspect_research_html(same, DAY)
        self.assert_research(answer)
        self.assertEqual(answer["candidate_table_count"], 2)
        self.assertIn("EQUIVALENT_MULTIPLE_TABLES", answer["normalization"]["forms"])
        conflict = table() + table(clock=lambda n: "18:59" if n == 3 else f"13:{n:02d}")
        self.assertEqual(inspect_research_html(conflict, DAY)["reason"], "DUPLICATE_TABLE_CONFLICT")

    def test_colspan_only_unrelated_header_and_semantic_span_rejected(self):
        answer = inspect_research_html(table(other_header="<th colspan='2'>補足</th>", other_cell="<td>注A</td><td>注B</td>"), DAY)
        self.assert_research(answer)
        self.assertIn("NONSEMANTIC_HEADER_COLSPAN", answer["normalization"]["forms"])
        bad = table().replace("<th>レース</th>", "<th colspan='2'>レース</th>")
        self.assertEqual(inspect_research_html(bad, DAY)["reason"], "SEMANTIC_COLUMN_SPAN_AMBIGUOUS")

    def test_repeated_header_and_alias_with_conflicting_header_rejected(self):
        original = table()
        header = "<tr><th>レース</th><th>投票締切</th></tr>"
        repeated = original.replace("<tr><td>7R</td>", header + "<tr><td>7R</td>")
        answer = inspect_research_html(repeated, DAY)
        self.assert_research(answer)
        self.assertIn("IDENTICAL_REPEATED_HEADERS", answer["normalization"]["forms"])
        alias = original.replace("<th>レース</th>", "<th>レースNo.</th>")
        self.assert_research(inspect_research_html(alias, DAY))
        bad = repeated.replace("<th>レース</th><th>投票締切</th></tr><tr><td>7R", "<th>投票締切</th><th>レース</th></tr><tr><td>7R")
        self.assertEqual(inspect_research_html(bad, DAY)["reason"], "CONFLICTING_REPEATED_HEADERS")

    def test_orphan_duplicate_missing_and_ambiguous_time_hold(self):
        candidates = [
            table() + "<table><tr><td>3R</td><td>18:00</td></tr></table>",
            table().replace("</table>", "<tr><td>1R</td><td>00:00</td></tr></table>"),
            table().replace("<tr><td>12R</td><td>13:12</td></tr>", ""),
            table(clock=lambda n: "13:03 13:04" if n == 3 else f"13:{n:02d}"),
            table().replace("</table>", "<tr><td>注記</td><td>18:00更新</td></tr></table>"),
        ]
        for html in candidates:
            with self.subTest(case=len(html)):
                value = inspect_research_html(html, DAY)
                self.assertEqual(value["status"], "HOLD")
                self.assertFalse(value["runtime_execution_allowed"])

    def test_names_never_cancel_and_explicit_state_stays_unapproved(self):
        answer = inspect_research_html(table(name=lambda n: "雨天中止順延記念"), DAY)
        self.assert_research(answer)
        self.assertTrue(all(not row["is_cancelled"] for row in answer["records"]))
        explicit = inspect_research_html(table(state=lambda n: "中止"), DAY)
        self.assert_research(explicit)
        self.assertTrue(all(row["is_cancelled"] for row in explicit["records"]))
        self.assertFalse(explicit["runtime_execution_allowed"])

    def test_unrelated_weather_and_commented_table_do_not_create_races(self):
        html = "<!-- " + table(clock=lambda n: "00:00") + " -->" + table() + "<table><tr><th>気温</th></tr><tr><td>18℃</td></tr></table>"
        self.assert_research(inspect_research_html(html, DAY))


class PrivateCheckerTests(unittest.TestCase):
    def test_no_input_is_external_block_and_invalid_reference_stops(self):
        self.assertEqual(private_check.inspect_private_file(None, DAY)["status"], "BLOCKED_EXTERNAL")
        with patch.object(private_check, "LEGACY_SHA256", "0" * 64):
            answer = private_check.compare_raw_bytes(table().encode(), DAY)
        self.assertEqual(answer["reason"], "REFERENCE_SHA_MISMATCH")

    def test_private_summary_has_no_body_url_path_race_ids_or_times(self):
        marker = "PRIVATE_DO_NOT_SHARE_TOKEN_9387"
        body = ("<div>https://example.invalid/auth?secret=" + marker + "</div>" + table(name=lambda n: marker)).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-only.html"
            path.write_bytes(body)
            answer = private_check.inspect_private_file(path, DAY)
            encoded = json.dumps(answer, sort_keys=True)
            self.assertEqual(answer["status"], "OBSERVED_LOCAL_BYTES_ONLY")
            self.assertEqual(answer["raw_bytes"], len(body))
            self.assertEqual(answer["raw_sha256"], hashlib.sha256(body).hexdigest())
            for forbidden in (marker, str(path), "https://", "20990107_GAM", "13:01"):
                self.assertNotIn(forbidden, encoded)
            self.assertFalse(answer["go"])
            self.assertEqual(path.read_bytes(), body)

    def test_non_regular_extension_symlink_and_bad_encoding_are_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual.html"
            actual.write_bytes(table().encode())
            link = root / "link.html"
            link.symlink_to(actual)
            self.assertEqual(private_check.inspect_private_file(link, DAY)["status"], "UNVERIFIED")
            with patch.object(private_check.os, "O_NOFOLLOW", 0, create=True):
                self.assertEqual(private_check.inspect_private_file(link, DAY)["reason"], "SYMLINK_INPUT_NOT_ALLOWED")
            self.assertEqual(private_check.inspect_private_file(root / ".env", DAY)["reason"], "HTML_FILE_EXTENSION_REQUIRED")
            bad = private_check.compare_raw_bytes(b"\xff\xfe", DAY)
            self.assertEqual(bad["reason"], "ENCODING_UNVERIFIED")

    def test_old_vs_v003_difference_is_summary_only(self):
        body = table(name=lambda n: "雨天中止順延記念").encode()
        answer = private_check.compare_raw_bytes(body, DAY)
        self.assertEqual(answer["status"], "OBSERVED_LOCAL_BYTES_ONLY")
        self.assertEqual(answer["old"]["counts"]["cancelled"], 12)
        self.assertEqual(answer["v003"]["counts"]["cancelled"], 0)
        self.assertEqual(answer["differences"]["state_flag_differences"], 12)
        self.assertEqual(answer["research"]["policy_status"], "POLICY_PENDING_REAL_HTML")

    def test_unknown_or_invalid_day_and_nonbytes_never_become_observed(self):
        for bad in ("20990231", "00000101", "2099-01-07", None):
            answer = private_check.compare_raw_bytes(table().encode(), bad)
            self.assertEqual(answer["status"], "UNVERIFIED")
            self.assertEqual(answer["reason"], "REQUESTED_DAY_UNVERIFIED")
        answer = private_check.compare_raw_bytes("PRIVATE_BODY", DAY)
        self.assertEqual(answer["reason"], "INPUT_BYTES_REQUIRED")
        self.assertIsNone(answer["raw_bytes"])

    def test_cli_argument_errors_do_not_echo_values(self):
        marker = "https://private.invalid/SHOULD_NOT_ECHO_9127"
        command = [sys.executable, "-B", str(Path(private_check.__file__)), "--encoding", marker]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(marker, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["reason"], "ARGUMENTS_INVALID")
        self.assertEqual(result.stderr, "")

    def test_size_limit_does_not_read_or_hash_a_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.html"
            path.write_bytes(b"PRIVATE_LARGE_HTML_NOT_READ")
            with patch.object(private_check, "MAX_LOCAL_BYTES", 2), patch.object(private_check, "compare_raw_bytes", side_effect=AssertionError("NO_PARTIAL_COMPARE")):
                answer = private_check.inspect_private_file(path, DAY)
            self.assertEqual(answer["reason"], "LOCAL_SIZE_LIMIT_NO_READ")
            self.assertNotIn("raw_sha256", answer)
