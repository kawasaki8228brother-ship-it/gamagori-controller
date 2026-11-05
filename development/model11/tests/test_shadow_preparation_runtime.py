"""Read-only local probe checks; no production host or clock authority exists."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model11.shadow_preparation.runtime_probe import probe_local_runtime


class RuntimePreparationTests(unittest.TestCase):
    def test_default_disabled_does_not_touch_directory_clock_or_process(self):
        with patch("model11.shadow_preparation.runtime_probe.Path") as path, \
             patch("model11.shadow_preparation.runtime_probe.datetime") as clock, \
             patch("model11.shadow_preparation.runtime_probe._process_identity") as process:
            result = probe_local_runtime(object())
        self.assertEqual(result["status"], "DISABLED")
        for component in (path, clock, process):
            component.assert_not_called()

    def test_private_or_unknown_scope_is_not_observed(self):
        for classification in (None, "PRIVATE_REAL", "HQ14_PRIVATE_OFFLINE", "UNKNOWN"):
            with self.subTest(classification=classification), \
                 patch("model11.shadow_preparation.runtime_probe.Path") as path:
                result = probe_local_runtime(object(), enable_offline=True, classification=classification)
            self.assertEqual(result["status"], "HOLD")
            path.assert_not_called()

    def test_truthy_nonbool_enable_does_not_enable(self):
        for enabled in (1, "true", [], {}):
            result = probe_local_runtime(object(), enable_offline=enabled, classification="SYNTHETIC_ONLY")
            self.assertEqual(result["status"], "DISABLED")

    def test_observation_is_read_only_and_does_not_claim_clock_or_capacity_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "invented-source.json"
            marker.write_bytes(b'{"synthetic":true}\n')
            before = {item.name: item.read_bytes() for item in Path(directory).iterdir()}
            result = probe_local_runtime(directory, enable_offline=True, classification="SYNTHETIC_ONLY")
            after = {item.name: item.read_bytes() for item in Path(directory).iterdir()}
        self.assertEqual(before, after)
        self.assertEqual(result["status"], "LOCAL_OBSERVATION_ONLY")
        self.assertEqual(result["clock"]["external_utc_accuracy"], "UNVERIFIED")
        self.assertIsNone(result["clock"]["synchronization_evidence"])
        self.assertFalse(result["launch_allowed"])
        self.assertFalse(result["files_written"])
        self.assertFalse(result["database_opened"])
        self.assertFalse(result["network_used"])
        self.assertNotIn(directory, str(result))

    def test_missing_directory_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "not-created"
            result = probe_local_runtime(missing, enable_offline=True, classification="SYNTHETIC_ONLY")
            self.assertFalse(missing.exists())
        self.assertEqual(result["status"], "HOLD")

    def test_symlink_and_file_are_not_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "invented-file"
            file.write_bytes(b"invented")
            link = root / "invented-link"
            link.symlink_to(root, target_is_directory=True)
            for target in (file, link):
                with self.subTest(target=target.name):
                    result = probe_local_runtime(target, enable_offline=True, classification="SYNTHETIC_ONLY")
                    self.assertEqual(result["status"], "HOLD")

    def test_unavailable_process_identity_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("model11.shadow_preparation.runtime_probe._process_identity", return_value=None):
            result = probe_local_runtime(directory, enable_offline=True, classification="SYNTHETIC_ONLY")
        self.assertEqual(result["status"], "LOCAL_OBSERVATION_ONLY")
        self.assertFalse(result["process"]["identity_available"])
        self.assertIsNone(result["process"]["identity_sha256"])


if __name__ == "__main__":
    unittest.main()
