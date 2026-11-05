"""Byte preservation regression only; no old model or evaluation is executed."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
PACKAGE = HERE.parent
SPEC = importlib.util.spec_from_file_location("_f5_parent_static_audit", HERE / "static_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
audit_parent_bytes, load_json = AUDIT.audit_parent_bytes, AUDIT.load_json


class ParentPreservationTests(unittest.TestCase):
    def test_all245_parent_files_remain_exact_bytes_and_sizes(self):
        report = audit_parent_bytes(PACKAGE, load_json(HERE / "PARENT_BYTE_BASELINE.json"))
        self.assertEqual(report["status"], "PARENT_BYTES_UNCHANGED")
        self.assertEqual(report["checked_files"], 245)
        self.assertFalse(report["statistical_evaluation_performed"])
        self.assertFalse(report["production_go"])

    def test_expected_hash_mismatch_is_detected_without_editing_parent(self):
        baseline = deepcopy(load_json(HERE / "PARENT_BYTE_BASELINE.json"))
        baseline[0]["sha256"] = "0"*64
        report = audit_parent_bytes(PACKAGE, baseline)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("PARENT_FILE_CHANGED", report["issues"])

    def test_duplicate_metadata_cannot_fake_the_preserved_file_count(self):
        baseline = deepcopy(load_json(HERE / "PARENT_BYTE_BASELINE.json"))
        baseline[-1] = deepcopy(baseline[0])
        report = audit_parent_bytes(PACKAGE, baseline)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("PARENT_BASELINE_INVALID", report["issues"])


if __name__ == "__main__":
    unittest.main()
