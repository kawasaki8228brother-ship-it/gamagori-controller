"""Offline CLI guards and fixed diagnostics; no production inputs are loaded."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest
from unittest.mock import patch

from model11.offline_refinements import cli


class OfflineCliTests(unittest.TestCase):
    def invoke(self, arguments):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(arguments)
        self.assertEqual(err.getvalue(), "")
        return code, json.loads(out.getvalue())

    def test_default_and_missing_enable_do_not_read_supplied_files(self):
        cases = ([], ["schedule", "--schedule", "unread", "--predictions", "unread"],
                 ["pit", "--input", "unread"], ["pilot", "--observations", "unread", "--roster", "unread"])
        for case in cases:
            with self.subTest(case=case), patch.object(cli, "_load") as read:
                code, result = self.invoke(case)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "DISABLED")
            read.assert_not_called()

    def test_invalid_command_or_option_never_echoes_argument(self):
        sentinel = "INVENTED_PRIVATE_ARGUMENT_DO_NOT_ECHO"
        for arguments in ([sentinel], ["pit", "--unknown", sentinel], ["pilot", "--observations"]):
            with self.subTest(arguments=arguments), patch.object(cli, "_load") as read:
                code, result = self.invoke(arguments)
            self.assertEqual(code, 2)
            self.assertNotIn(sentinel, str(result))
            self.assertEqual(result["reasons"], ["INVALID_COMMAND_OR_OPTION"])
            read.assert_not_called()

    def test_read_failure_is_hold_without_path_or_exception_echo(self):
        sentinel = "INVENTED_PRIVATE_PATH_DO_NOT_ECHO"
        with patch.object(cli, "_load", side_effect=OSError(sentinel)):
            code, result = self.invoke(["pit", "--enable-offline", "--input", sentinel])
        self.assertEqual(code, 2)
        self.assertEqual(result["reasons"], ["LOCAL_OFFLINE_INPUT_UNVERIFIED"])
        self.assertNotIn(sentinel, str(result))

    def test_pilot_does_not_infer_complete_roster_from_an_input_path(self):
        with patch.object(cli, "_load", return_value=[]), \
             patch("model11.offline_refinements.pilot.summarize_pilot", return_value={"status": "UNVERIFIED"}) as summary:
            code, result = self.invoke(["pilot", "--enable-offline", "--roster", "roster.json",
                "--observations", "observations.json", "--baseline-id", "SYNTHETIC_MARKET",
                "--baseline-version", "V1"])
        self.assertEqual(code, 0)
        self.assertFalse(summary.call_args.kwargs["roster_complete"])
        self.assertEqual(result["application_status"], "HOLD")

    def test_schedule_owner_pin_is_passed_without_a_store_call(self):
        with patch.object(cli, "_load", return_value={}), \
             patch("model11.offline_refinements.schedule.audit_manifest_coverage", return_value={"status": "HOLD"}) as audit:
            code, result = self.invoke(["schedule", "--enable-offline", "--schedule", "schedule.json",
                "--predictions", "prediction.json", "--target-date", "2099-01-07", "--expected-storage-id", "a"*32])
        self.assertEqual(code, 2)
        self.assertEqual(audit.call_args.kwargs["expected_storage_id"], "a"*32)
        self.assertFalse(result["production_go"])

    def test_status_does_not_become_enabled_by_the_offline_flag(self):
        with patch.object(cli, "_load") as read:
            code, result = self.invoke(["status", "--enable-offline"])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "DISABLED")
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
