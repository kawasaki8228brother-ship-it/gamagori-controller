"""Document/reference regression; actual private original remains optional."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from development.health_residuals_20261106_v003.spec_sha_check import (
    CORRECTED_A_SPEC_SHA256, HISTORICAL_40_HEX, MATCH_STATUS, SKIP_STATUS,
    check_private_spec, historical_projection_matches, main,
)


class SpecReferenceTests(unittest.TestCase):
    def test_literal_lengths_and_measured_prefix_suffix_relationship(self):
        self.assertEqual(CORRECTED_A_SPEC_SHA256,
                         "d462767f4448e28fc735df7363fb6f54a577e014607d5ec3b2fb1a75137c5e7f")
        self.assertEqual(len(CORRECTED_A_SPEC_SHA256), 64)
        self.assertIsNotNone(re.fullmatch("[0-9a-f]{64}", CORRECTED_A_SPEC_SHA256))
        self.assertEqual(len(HISTORICAL_40_HEX), 40)
        self.assertEqual(HISTORICAL_40_HEX, CORRECTED_A_SPEC_SHA256[:28] + CORRECTED_A_SPEC_SHA256[-12:])
        self.assertTrue(historical_projection_matches())

    def test_v002_reference_scope_and_historical_v001_record_preserved(self):
        root = Path(__file__).resolve().parents[1]
        correction = json.loads((root / "development/health_residuals_20261106_v002/OBS_SHA_CORRECTION.json").read_bytes())
        self.assertEqual(correction["corrected_reference"]["received_hash_verbatim"], CORRECTED_A_SPEC_SHA256)
        self.assertFalse(correction["corrected_reference"]["is_OBS_contract_SHA256"])
        self.assertEqual(correction["historical_reference"]["received_hash_verbatim"], HISTORICAL_40_HEX)
        for item in correction["preserved_historical_artifacts"]:
            raw = (root / item["path"]).read_bytes()
            self.assertEqual(len(raw), item["bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])

    def test_absent_original_does_not_open_any_path_or_become_match(self):
        with patch.object(Path, "read_bytes", side_effect=AssertionError("NO_IMPLICIT_PATH_READ")):
            report = check_private_spec()
        self.assertEqual(report, {"status": SKIP_STATUS, "bytes": None, "digest": None})

    def test_exact_utf8_byte_count_negative_vector_never_claimed_original(self):
        # This invented text is deliberately NOT the actual specification body.
        raw = ("蒲" * 69 + "\n").encode("utf-8")
        self.assertEqual(len(raw), 208)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-negative-vector.txt"
            path.write_bytes(raw)
            report = check_private_spec(path)
            self.assertEqual(report["status"], "MISMATCH_REFERENCE_SHA256")
            self.assertEqual(report["bytes"], 208)
            self.assertEqual(report["digest"], hashlib.sha256(raw).hexdigest())
            path.write_bytes(raw + b"\n")
            self.assertEqual(check_private_spec(path)["status"], "MISMATCH_EXPECTED_208_UTF8_BYTES")
            path.write_bytes(b"\xff" * 208)
            self.assertEqual(check_private_spec(path)["status"], "MISMATCH_UTF8_ENCODING")
            if hasattr(os, "mkfifo"):
                fifo = Path(directory) / "synthetic-not-a-regular-file"
                os.mkfifo(fifo)
                self.assertEqual(check_private_spec(fifo)["status"], "UNVERIFIED_PRIVATE_READ_FAILED")

    def test_cli_emits_only_status_bytes_digest_and_never_private_path(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main(["--private-spec-file", "/SYNTHETIC_PRIVATE_MISSING_INPUT_DO_NOT_ECHO"])
        report = json.loads(stream.getvalue())
        self.assertEqual(code, 3)
        self.assertEqual(set(report), {"status", "bytes", "digest"})
        self.assertEqual(report["status"], "UNVERIFIED_PRIVATE_READ_FAILED")
        self.assertNotIn("SYNTHETIC_PRIVATE_MISSING_INPUT", stream.getvalue())
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = main([])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(stream.getvalue())["status"], SKIP_STATUS)

    def test_private_208_byte_original_only_if_operator_already_supplied_local_path(self):
        # Reads only this explicitly opted-in path; never requests/retrieves it.
        report = check_private_spec(os.environ.get("HEALTH_PRIVATE_SPEC_FILE"))
        if report["status"] == SKIP_STATUS:
            if "PYTEST_CURRENT_TEST" in os.environ:
                import pytest
                pytest.skip("UNVERIFIED_PROMPT_TEMPLATE_SPEC_ORIGINAL_NOT_SUPPLIED")
            self.skipTest("UNVERIFIED_PROMPT_TEMPLATE_SPEC_ORIGINAL_NOT_SUPPLIED")
        self.assertEqual(report["status"], MATCH_STATUS, "PRIVATE_ORIGINAL_LOCAL_CHECK_NOT_MATCHED")
        self.assertEqual(report["bytes"], 208)
        self.assertEqual(report["digest"], CORRECTED_A_SPEC_SHA256)


if __name__ == "__main__":
    unittest.main()
