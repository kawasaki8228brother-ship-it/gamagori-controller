"""Preparation CLI is a reader and never a launch or persistence command."""
from contextlib import redirect_stdout
from io import StringIO
import json
import tempfile
import unittest
from unittest.mock import patch

from model11.shadow_preparation import cli


class PreparationCliTests(unittest.TestCase):
    def invoke(self, argv):
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(argv)
        return code, json.loads(output.getvalue())

    def test_default_disabled_and_command_without_explicit_enable_do_not_read_inputs(self):
        for argv in ([], ["coverage", "--schedule", "unread.json", "--predictions", "unread.json"],
                     ["capture", "--mapping", "unread.json", "--capture", "unread.json"],
                     ["runtime", "--storage-directory", "unread"]):
            with self.subTest(argv=argv), patch.object(cli, "_load") as load, \
                 patch.object(cli, "probe_local_runtime") as probe:
                code, result = self.invoke(argv)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "DISABLED")
            load.assert_not_called()
            probe.assert_not_called()

    def test_capture_without_explicit_synthetic_validation_does_not_read_input(self):
        with patch.object(cli, "_load") as load:
            code, result = self.invoke(["capture", "--enable-offline", "--capture", "unread.json"])
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "HOLD")
        load.assert_not_called()

    def test_unknown_official_mapping_remains_null_open_and_disabled(self):
        code, result = self.invoke(["inventory", "--enable-offline"])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "OPEN")
        self.assertIsNone(result["actual_official_format"])
        self.assertFalse(result["enabled"])
        self.assertEqual(result["application_status"], "HOLD")

    def test_private_capture_does_not_load_mapping_or_decode_payload(self):
        capture = {"data_classification": "PRIVATE_REAL", "synthetic": False,
                   "payload_bytes_b64": "not-even-decoded"}
        with patch.object(cli, "_load", return_value=capture) as load, \
             patch.object(cli, "_capture") as decode:
            code, result = self.invoke(["capture", "--enable-offline", "--synthetic-validation",
                                        "--capture", "capture.json", "--mapping", "unread.json"])
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "HOLD")
        load.assert_called_once_with("capture.json")
        decode.assert_not_called()

    def test_f5_is_a_proposal_not_an_adopted_execution_config(self):
        code, result = self.invoke(["f5", "--enable-offline"])
        self.assertEqual(code, 0)
        self.assertFalse(result["adopted"])
        self.assertTrue(result["actual_grid_unchanged"])
        self.assertEqual(result["application_status"], "HOLD")

    def test_bad_input_emits_fixed_reason_without_echoing_exception(self):
        sentinel = "INVENTED_PRIVATE_PATH_OR_SECRET_SHOULD_NOT_ECHO"
        with patch.object(cli, "_load", side_effect=ValueError(sentinel)):
            code, result = self.invoke(["capture", "--enable-offline", "--synthetic-validation",
                                        "--capture", "input.json", "--mapping", "mapping.json"])
        self.assertEqual(code, 2)
        self.assertNotIn(sentinel, str(result))
        self.assertEqual(result["reasons"], ["LOCAL_PREPARATION_INPUT_UNVERIFIED"])

    def test_invalid_command_and_arguments_do_not_echo_submitted_values(self):
        sentinel = "INVENTED_PRIVATE_ARGUMENT_DO_NOT_LOG"
        for argv in ([sentinel], ["coverage", "--unknown", sentinel], ["runtime", "--storage-directory"]):
            with self.subTest(argv=argv), patch.object(cli, "_load") as load:
                code, result = self.invoke(argv)
            self.assertEqual(code, 2)
            self.assertNotIn(sentinel, str(result))
            self.assertEqual(result["reasons"], ["INVALID_COMMAND_OR_OPTION"])
            load.assert_not_called()

    def test_runtime_observation_never_enables_or_creates_a_shadow(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result = self.invoke(["runtime", "--enable-offline", "--synthetic-validation",
                                        "--storage-directory", directory])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "LOCAL_OBSERVATION_ONLY")
        self.assertFalse(result["launch_allowed"])
        self.assertFalse(result["files_written"])
        self.assertEqual(result["application_status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
