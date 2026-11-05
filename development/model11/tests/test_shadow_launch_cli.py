"""Local CLI boundary checks; no real data, services, or approval is used."""
import base64
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from model11.shadow_launch import cli


def encoded_capture(payload=b"invented-original"):
    return {"payload_bytes_b64": base64.b64encode(payload).decode("ascii")}


class _FakeStore:
    def is_stopped(self):
        return False


class _FakeRunner:
    """Test only CLI decisions; actual runner behavior has a separate suite."""
    def __init__(self, statuses=("COMMITTED",), on_run=None):
        self.statuses = iter(statuses)
        self.on_run = on_run
        self.calls = []
        self.stop_reasons = []
        self.shutdown_calls = 0
        self._closed = False
        self.store = _FakeStore()

    def run_race(self, capture, operator_ack=None):
        self.calls.append(capture)
        if self.on_run:
            self.on_run()
        return {"status": next(self.statuses, "COMMITTED"), "production_go": False}

    def request_stop(self, reason="OPERATOR_STOP"):
        self.stop_reasons.append(reason)
        self._closed = True
        return {"status": "STOPPED", "reason": reason, "production_go": False}

    def shutdown(self):
        self.shutdown_calls += 1
        self._closed = True
        return {"status": "SHUTDOWN", "production_go": False}


class ShadowCliTests(unittest.TestCase):
    def invoke(self, arguments):
        output = StringIO()
        with redirect_stdout(output):
            code = cli.main(arguments)
        return code, [json.loads(line) for line in output.getvalue().splitlines() if line]

    def mocked_context(self, runner):
        return patch.object(cli, "_context", return_value=(runner,
            {"allowed": True, "status": "SIMULATION_PREFLIGHT_ONLY"}, None))

    def test_default_disabled_does_not_read_artifacts_capture_or_construct_dependencies(self):
        with patch.object(cli, "_load", side_effect=AssertionError("NO_INPUT_READ")) as load, \
             patch.object(cli, "ShadowRunner") as runner, patch.object(cli, "ShadowStore") as store, \
             patch.object(cli, "SourceAdapter") as source, \
             patch.object(cli.CourseBoundModel, "from_dict") as model:
            code, records = self.invoke(["run", "--artifacts", "unread-artifacts.json",
                "--operator-ack", "unread-ack.json", "--captures", "unread-captures.json"])
        self.assertEqual(code, 0)
        self.assertEqual(records[-1]["status"], "DISABLED")
        for dependency in (load, runner, store, source, model):
            dependency.assert_not_called()

    def test_disabled_config_reads_only_that_config(self):
        def load(path):
            self.assertEqual(path, "disabled-config.json")
            return {"enabled": False}
        with patch.object(cli, "_load", side_effect=load) as reader:
            code, records = self.invoke(["run", "--config", "disabled-config.json",
                "--artifacts", "unread-artifacts.json", "--captures", "unread-captures.json"])
        self.assertEqual(code, 0)
        self.assertEqual(records[-1]["status"], "DISABLED")
        reader.assert_called_once_with("disabled-config.json")

    def test_stop_does_not_create_or_adopt_an_unowned_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            nonexistent = Path(temporary) / "unowned-do-not-create"
            settings = {"storage_root": str(nonexistent), "namespace": "MODEL11_THIRD_RESEARCH"}
            with patch.object(cli, "_load", return_value=settings), patch.object(cli, "ShadowStore") as store:
                code, records = self.invoke(["stop", "--config", "invented.json"])
            self.assertEqual(code, 0)
            self.assertEqual(records[-1]["status"], "DISABLED")
            store.assert_not_called()
            self.assertFalse(nonexistent.exists())
            nonexistent.mkdir()
            marker = nonexistent / "OWNER.json"
            marker.write_text('{"invented_unowned_marker":true}', encoding="ascii")
            before = {item.name: item.read_bytes() for item in nonexistent.iterdir()}
            with patch.object(cli, "_load", return_value=settings):
                code, records = self.invoke(["stop", "--config", "invented.json"])
            self.assertEqual(code, 2)
            self.assertEqual(records[-1]["status"], "STOP")
            self.assertEqual(before, {item.name: item.read_bytes() for item in nonexistent.iterdir()})

    def test_simulation_time_requires_strict_aware_offset_before_preflight_or_model(self):
        bad_values = ("2099-01-07T12:55:01", "2099-01-07T12:55:01+09:99",
                      "2099-01-07T12:55:01+24:00", "2099-01-07T12:55:01-00:00",
                      "2099-01-07T12:55:01.1234567+09:00", "not-a-time")
        def load(path):
            return {"enabled": True, "mode": "SIMULATION"} if path == "config.json" else {}
        for value in bad_values:
            with self.subTest(value=value), patch.object(cli, "_load", side_effect=load), \
                 patch.object(cli, "preflight") as gate, \
                 patch.object(cli.CourseBoundModel, "from_dict") as model:
                code, records = self.invoke(["preflight", "--config", "config.json",
                    "--artifacts", "artifacts.json", "--simulation-now", value])
            self.assertEqual(code, 2)
            self.assertEqual(records[-1]["status"], "HOLD")
            gate.assert_not_called()
            model.assert_not_called()

    def test_private_clock_override_is_forbidden(self):
        def load(path):
            return {"enabled": True, "mode": "PRIVATE_SHADOW"} if path == "config.json" else {}
        with patch.object(cli, "_load", side_effect=load), patch.object(cli, "preflight") as gate:
            code, records = self.invoke(["preflight", "--config", "config.json", "--artifacts", "artifacts.json",
                                         "--simulation-now", "2099-01-07T12:55:01+09:00"])
        self.assertEqual(code, 2)
        self.assertEqual(records[-1]["status"], "HOLD")
        gate.assert_not_called()

    def test_enabled_run_hold_and_other_failures_have_nonzero_exit_and_visible_statuses(self):
        for status in ("HOLD", "STOPPED", "CONFLICT", "HOLD_UNCERTAIN", "DISABLED"):
            runner = _FakeRunner(("COMMITTED", status))
            with self.subTest(status=status), self.mocked_context(runner), \
                 patch.object(cli, "_load", return_value=[encoded_capture(), encoded_capture()]), \
                 patch.object(cli.signal, "signal"):
                code, records = self.invoke(["run", "--captures", "invented.json"])
            self.assertEqual(code, 2)
            self.assertEqual(records[-1]["status"], "HOLD")
            self.assertEqual(records[-1]["statuses"], ["COMMITTED", status])
            self.assertEqual(runner.shutdown_calls, 1)

    def test_enabled_run_success_exposes_committed_and_duplicate_statuses(self):
        runner = _FakeRunner(("COMMITTED", "DUPLICATE"))
        with self.mocked_context(runner), patch.object(cli, "_load", return_value=[encoded_capture(), encoded_capture()]), \
             patch.object(cli.signal, "signal"):
            code, records = self.invoke(["run", "--captures", "invented.json"])
        self.assertEqual(code, 0)
        self.assertEqual(records[-1]["status"], "RUN_COMPLETE")
        self.assertEqual(records[-1]["statuses"], ["COMMITTED", "DUPLICATE"])

    def test_watch_finite_cycle_terminates_without_sleep_or_input_processing(self):
        runner = _FakeRunner()
        with tempfile.TemporaryDirectory() as folder, self.mocked_context(runner), \
             patch.object(cli.signal, "signal"), patch.object(cli.time, "sleep") as sleep:
            code, records = self.invoke(["watch", "--input-dir", folder, "--poll-seconds", "0.01", "--max-iterations", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(records[-1]["iterations"], 1)
        self.assertEqual(runner.calls, [])
        self.assertEqual(runner.shutdown_calls, 1)
        sleep.assert_not_called()

    def test_watch_invalid_bounds_cannot_process_even_one_capture(self):
        variants = (("--poll-seconds", "nan"), ("--poll-seconds", "inf"), ("--poll-seconds", "0"),
                    ("--poll-seconds", "-1"), ("--max-iterations", "0"), ("--max-iterations", "-1"))
        for flag, value in variants:
            runner = _FakeRunner()
            with self.subTest(flag=flag, value=value), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / "capture.json").write_text(json.dumps(encoded_capture()), encoding="ascii")
                args = ["watch", "--input-dir", folder, "--max-iterations", "1"]
                if flag == "--max-iterations":
                    args[-1] = value
                else:
                    args.extend((flag, value))
                with self.mocked_context(runner), patch.object(cli.signal, "signal"), patch.object(cli.time, "sleep"):
                    code, records = self.invoke(args)
                self.assertEqual(code, 2)
                self.assertEqual(records[-1]["status"], "HOLD")
                self.assertEqual(runner.calls, [])

    def test_watch_rewritten_capture_stops_without_reprocessing_and_is_visible_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.json"
            path.write_text(json.dumps(encoded_capture()), encoding="ascii")
            def rewrite():
                path.write_text(json.dumps(encoded_capture(b"invented-rewritten")), encoding="ascii")
            runner = _FakeRunner(on_run=rewrite)
            with self.mocked_context(runner), patch.object(cli.signal, "signal"), patch.object(cli.time, "sleep"):
                code, records = self.invoke(["watch", "--input-dir", folder, "--poll-seconds", "0.01", "--max-iterations", "3"])
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("INPUT_CAPTURE_FILE_REWRITTEN", runner.stop_reasons)
        self.assertEqual(code, 2)
        self.assertEqual(records[-1]["status"], "HOLD")

    def test_watch_does_not_hash_one_snapshot_and_process_a_different_reopened_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "capture.json"
            path.write_text(json.dumps(encoded_capture(b"invented-original")), encoding="ascii")
            runner = _FakeRunner()
            read = Path.read_bytes
            modified = []
            def read_then_rewrite(item):
                raw = read(item)
                if item == path and not modified:
                    modified.append(True)
                    item.write_text(json.dumps(encoded_capture(b"invented-rewritten")), encoding="ascii")
                return raw
            with self.mocked_context(runner), patch.object(cli.signal, "signal"), \
                 patch.object(cli.time, "sleep"), patch.object(Path, "read_bytes", new=read_then_rewrite):
                self.invoke(["watch", "--input-dir", folder, "--max-iterations", "1"])
        self.assertTrue(modified)
        self.assertTrue(all(capture["payload_bytes"] == b"invented-original" for capture in runner.calls))

    def test_watch_symlink_is_not_read_or_processed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "invented-not-input.txt"
            target.write_text("invented-private-sentinel", encoding="ascii")
            (root / "capture.json").symlink_to(target)
            runner = _FakeRunner()
            with self.mocked_context(runner), patch.object(cli.signal, "signal"), patch.object(cli, "_load") as load:
                code, records = self.invoke(["watch", "--input-dir", folder, "--max-iterations", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(records[-1]["status"], "HOLD")
        self.assertIn("INPUT_SYMLINK_FORBIDDEN", runner.stop_reasons)
        self.assertEqual(runner.calls, [])
        load.assert_not_called()

    def test_watch_snapshot_preserves_duplicate_key_and_nonfinite_json_rejection(self):
        invalid_values = (
            '{"payload_bytes_b64":"aW52ZW50ZWQ=","payload_bytes_b64":"aW52ZW50ZWQ="}',
            '{"payload_bytes_b64":"aW52ZW50ZWQ=","invented_extra":NaN}',
            '{"payload_bytes_b64":"aW52ZW50ZWQ=","invented_extra":Infinity}',
        )
        for raw in invalid_values:
            runner = _FakeRunner()
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / "capture.json").write_text(raw, encoding="ascii")
                with self.mocked_context(runner), patch.object(cli.signal, "signal"):
                    code, records = self.invoke(["watch", "--input-dir", folder, "--max-iterations", "1"])
            self.assertEqual(code, 2)
            self.assertEqual(records[-1]["status"], "HOLD")
            self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
