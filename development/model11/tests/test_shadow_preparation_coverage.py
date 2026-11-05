"""Coverage only; genuine v005 pipeline outputs from invented 2099 inputs."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from model11.shadow_launch.cli import run_demo
from model11.shadow_preparation.coverage import audit_schedule_coverage, frame_prediction_evidence


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def decode(entry, name):
    return json.loads(base64.b64decode(entry["raw_blobs"][name + "_b64"]))


def refresh_entry(entry, *, envelope=None, rehash_inner=True):
    """Controlled synthetic tampering, keeping outer byte bindings coherent."""
    if envelope is None:
        envelope = decode(entry, "forecast")
    if rehash_inner:
        inner = dict(envelope["forecast"])
        inner.pop("prediction_sha256", None)
        envelope["forecast"]["prediction_sha256"] = hashlib.sha256(canonical(inner)).hexdigest()
    forecast_raw = canonical(envelope)
    metadata, receipt, completion = (decode(entry, name) for name in ("metadata", "receipt", "completion"))
    metadata["forecast_sha256"] = hashlib.sha256(forecast_raw).hexdigest()
    metadata_raw = canonical(metadata)
    receipt.update(forecast_sha256=hashlib.sha256(forecast_raw).hexdigest(), forecast_bytes=len(forecast_raw),
                   metadata_sha256=hashlib.sha256(metadata_raw).hexdigest())
    receipt_raw = canonical(receipt)
    entry["ledger"]["receipt_sha"] = hashlib.sha256(receipt_raw).hexdigest()
    completion["receipt_sha256"] = entry["ledger"]["receipt_sha"]
    for name, raw in (("forecast", forecast_raw), ("metadata", metadata_raw),
                      ("receipt", receipt_raw), ("completion", canonical(completion))):
        entry["raw_blobs"][name + "_b64"] = base64.b64encode(raw).decode("ascii")


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name) / "new-synthetic-demo"
        # Explicit isolated test writer. The checker itself never calls this.
        summary = run_demo(cls.directory)
        if summary["forecast_count"] != 12:
            raise AssertionError("SYNTHETIC_V005_DEMO_NOT_12")
        store = cls.directory / "third_research"
        owner = json.loads((store / "OWNER.json").read_bytes())
        cls.storage_id = owner["storage_id"]
        connection = sqlite3.connect((store / "ledger.sqlite3").as_uri() + "?mode=ro&immutable=1", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            ledgers = [dict(row) for row in connection.execute("SELECT * FROM races ORDER BY deadline,race_id")]
        finally:
            connection.close()
        cls.base_predictions, races = [], []
        for number, ledger in enumerate(ledgers, 1):
            folder = store / "artifacts" / ledger["race_key"]
            ledger["storage_id"] = cls.storage_id
            cls.base_predictions.append(frame_prediction_evidence(ledger,
                input_raw=(folder / "input.raw").read_bytes(), forecast_raw=(folder / "forecast.raw").read_bytes(),
                receipt_raw=(folder / "receipt.json").read_bytes(), completion_raw=(folder / "completion.json").read_bytes(),
                metadata_raw=bytes(ledger["commit_metadata"])))
            races.append({"race_id": ledger["race_id"], "race_no": number, "deadline": ledger["deadline"]})
        cls.target_date = decode(cls.base_predictions[0], "forecast")["target_date"]
        manifest = {"schema": "OFFICIAL_DAY_SCHEDULE_V001_PROPOSED", "venue": "GAMAGORI",
                    "target_date": cls.target_date, "source_id": "SYNTHETIC_SCHEDULE_NOT_OFFICIAL", "races": races}
        raw = canonical(manifest)
        digest = hashlib.sha256(raw).hexdigest()
        cls.base_schedule = {"fixture_classification": "SYNTHETIC_ONLY", "raw_manifest_b64": base64.b64encode(raw).decode("ascii"),
                             "manifest_bytes": len(raw), "manifest_sha256": digest,
                             "approval": {"approved": True, "declared_external_verification": True,
                                          "venue": "GAMAGORI", "target_date": cls.target_date,
                                          "source_id": manifest["source_id"], "manifest_sha256": digest,
                                          "mapping_sha256": "1" * 64, "evidence_sha256": "2" * 64}}
        cls.store_hashes = {path.relative_to(store).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in store.rglob("*") if path.is_file()}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.schedule, self.predictions = deepcopy(self.base_schedule), deepcopy(self.base_predictions)

    def audit(self):
        return audit_schedule_coverage(self.schedule, self.predictions, target_date=self.target_date,
                                       expected_storage_id=self.storage_id)

    def change_manifest(self, mutate):
        manifest = json.loads(base64.b64decode(self.schedule["raw_manifest_b64"]))
        mutate(manifest)
        raw = canonical(manifest)
        self.schedule.update(raw_manifest_b64=base64.b64encode(raw).decode("ascii"),
                             manifest_bytes=len(raw), manifest_sha256=hashlib.sha256(raw).hexdigest())
        self.schedule["approval"]["manifest_sha256"] = self.schedule["manifest_sha256"]

    def test_actual_v005_pipeline_twelve_records_locally_complete_not_authenticated(self):
        envelope = decode(self.predictions[0], "forecast")
        self.assertEqual(envelope["forecast"]["source"], "MODEL11_RESEARCH_V003")
        report = self.audit()
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE_LOCAL", report)
        self.assertEqual(report["locally_verified_saved_predictions"], 12)
        self.assertEqual(report["external_schedule_authenticity"], "UNVERIFIED")
        self.assertEqual(report["external_prediction_authenticity"], "UNVERIFIED")
        self.assertFalse(report["production_go"])

    def test_schedule_missing_row_duplicate_id_or_duplicate_number_hold(self):
        for mutation, code in ((lambda m: m["races"].pop(), "SCHEDULE_ROW_COUNT_NOT_12"),
                               (lambda m: m["races"][1].update(race_id=m["races"][0]["race_id"]), "DUPLICATE_SCHEDULED_RACE_ID"),
                               (lambda m: m["races"][1].update(race_no=1), "DUPLICATE_SCHEDULE_RACE_NUMBER")):
            self.schedule = deepcopy(self.base_schedule)
            self.change_manifest(mutation)
            report = self.audit()
            self.assertEqual(report["status"], "HOLD")
            self.assertIn(code, [issue["reason"] for issue in report["issues"]])

    def test_unapproved_undeclared_or_tampered_schedule_hold(self):
        for field, value in (("approved", False), ("declared_external_verification", False), ("mapping_sha256", None)):
            self.schedule = deepcopy(self.base_schedule)
            self.schedule["approval"][field] = value
            self.assertEqual(self.audit()["status"], "HOLD")
        self.schedule = deepcopy(self.base_schedule)
        self.schedule["manifest_sha256"] = "0" * 64
        self.assertEqual(self.audit()["issues"][0]["reason"], "SCHEDULE_HASH_MISMATCH")

    def test_schedule_target_date_venue_and_invalid_offset_are_not_inferred(self):
        for field, value, reason in (("target_date", "2099-01-01", "SCHEDULE_TARGET_DATE_MISMATCH"),
                                     ("venue", "OTHER", "SCHEDULE_VENUE_MISMATCH")):
            self.schedule = deepcopy(self.base_schedule)
            self.change_manifest(lambda m: m.update({field: value}))
            self.assertIn(reason, [issue["reason"] for issue in self.audit()["issues"]])
        self.schedule = deepcopy(self.base_schedule)
        self.change_manifest(lambda m: m["races"][0].update(deadline="2099-01-01T12:00:00+08:60"))
        self.assertEqual(self.audit()["status"], "HOLD")

    def test_no_entry_absent_unsaved_readfailed_uncertain_are_separate(self):
        for observation, category in ((None, "no_observation"), ("ABSENT", "observed_absent"),
                                      ("NOT_SAVED", "not_saved"), ("READ_FAILED", "read_failed"), ("UNCERTAIN", "uncertain")):
            self.predictions = deepcopy(self.base_predictions)
            if observation is None:
                self.predictions.pop(0)
            else:
                self.predictions[0] = {"race_id": self.predictions[0]["race_id"], "observation": observation}
            report = self.audit()
            self.assertEqual(report["status"], "HOLD")
            self.assertEqual(report["counts"][category], 1)
            self.assertEqual(report["locally_verified_saved_predictions"], 11)

    def test_committed_string_alone_is_not_verified_saved_evidence(self):
        self.predictions[0].pop("raw_blobs")
        report = self.audit()
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["rows"][0]["reasons"], ["READBACK_RAW_BLOBS_MISSING"])

    def test_pending_save_corruption_and_namespace_key_mismatch_hold(self):
        changes = (("state", "COMPLETION_PENDING", "PREDICTION_SAVE_UNCERTAIN"),
                   ("race_key", "0" * 64, "LEDGER_KEY_OR_NAMESPACE_MISMATCH"),
                   ("receipt_sha", "0" * 64, "RECEIPT_HASH_MISMATCH"))
        for field, value, reason in changes:
            self.predictions = deepcopy(self.base_predictions)
            self.predictions[0]["ledger"][field] = value
            self.assertEqual(self.audit()["rows"][0]["reasons"], [reason])

    def test_prediction_target_date_deadline_and_late_saved_are_distinct(self):
        envelope = decode(self.predictions[0], "forecast")
        envelope["target_date"] = "2099-01-01"
        refresh_entry(self.predictions[0], envelope=envelope)
        self.assertEqual(self.audit()["counts"]["target_date_mismatch"], 1)
        self.predictions = deepcopy(self.base_predictions)
        self.predictions[0]["ledger"]["deadline"] = "2099-01-01T12:00:00+09:00"
        self.assertEqual(self.audit()["counts"]["deadline_mismatch"], 1)
        self.predictions = deepcopy(self.base_predictions)
        self.predictions[0]["ledger"]["finalized_at"] = self.predictions[0]["ledger"]["deadline"]
        self.assertEqual(self.audit()["counts"]["late"], 1)

    def test_duplicate_or_unscheduled_observation_never_silently_deduplicated(self):
        self.predictions.append(deepcopy(self.predictions[0]))
        report = self.audit()
        self.assertEqual(report["counts"]["duplicate_observation"], 1)
        self.assertEqual(report["status"], "HOLD")
        self.predictions = deepcopy(self.base_predictions)
        self.predictions.append({"race_id": "SYNTHETIC-UNSCHEDULED", "observation": "ABSENT"})
        self.assertIn("UNSCHEDULED_PREDICTION_OBSERVATION", [issue["reason"] for issue in self.audit()["issues"]])

    def test_input_and_inner_forecast_tampering_not_hidden_by_committed_state(self):
        self.predictions[0]["raw_blobs"]["input_b64"] = base64.b64encode(b"synthetic-corruption").decode("ascii")
        self.assertEqual(self.audit()["rows"][0]["reasons"], ["RAW_INPUT_READBACK_MISMATCH"])
        self.predictions = deepcopy(self.base_predictions)
        envelope = decode(self.predictions[0], "forecast")
        envelope["forecast"]["prediction_sha256"] = "0" * 64
        refresh_entry(self.predictions[0], envelope=envelope, rehash_inner=False)
        self.assertEqual(self.audit()["rows"][0]["reasons"], ["INNER_FORECAST_HASH_MISMATCH"])

    def test_expected_owner_and_model_binding_not_just_any_saved_race(self):
        self.predictions[0]["ledger"]["storage_id"] = "0" * 32
        self.assertEqual(self.audit()["rows"][0]["reasons"], ["STORAGE_IDENTITY_MISMATCH"])
        self.predictions = deepcopy(self.base_predictions)
        self.predictions[0]["ledger"]["model_sha"] = "0" * 64
        self.assertEqual(self.audit()["rows"][0]["reasons"], ["MODEL_HASH_BINDING_MISMATCH"])

    def test_deep_json_recursion_is_fixed_hold_not_exception(self):
        # Decoder depth behavior differs across CPython builds. A parsed deep
        # object still fails its receipt hash; either path must remain HOLD.
        depth = max(10000, sys.getrecursionlimit() + 100)
        raw = ("{" + '"x":' + "[" * depth + "0" + "]" * depth + "}").encode("ascii")
        self.predictions[0]["raw_blobs"]["receipt_b64"] = base64.b64encode(raw).decode("ascii")
        report = self.audit()
        self.assertEqual(report["status"], "HOLD")
        self.assertIn(report["rows"][0]["reasons"], (["RAW_JSON_INVALID"], ["RECEIPT_HASH_MISMATCH"]))
        # Independently exercise an actual decoder exception deterministically
        # without depending on a build's C stack or changing global limits.
        real_loads = json.loads
        def decoder_failure(value, *args, **kwargs):
            if value == raw.decode("ascii"):
                raise RecursionError("INVENTED_DECODER_DEPTH_FAILURE")
            return real_loads(value, *args, **kwargs)
        with patch("model11.shadow_preparation.coverage.json.loads", side_effect=decoder_failure):
            report = self.audit()
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["rows"][0]["reasons"], ["RAW_JSON_INVALID"])

    def test_checker_has_no_io_no_mutation_no_arbitrary_input_echo(self):
        before = deepcopy((self.schedule, self.predictions))
        with patch("builtins.open", side_effect=AssertionError("NO_IO")), patch("sqlite3.connect", side_effect=AssertionError("NO_IO")), patch.object(Path, "read_bytes", side_effect=AssertionError("NO_IO")), patch.object(Path, "write_bytes", side_effect=AssertionError("NO_IO")):
            report = self.audit()
        self.assertEqual(report["status"], "OBSERVATION_COMPLETE_LOCAL")
        self.assertEqual((self.schedule, self.predictions), before)
        store = self.directory / "third_research"
        after = {path.relative_to(store).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in store.rglob("*") if path.is_file()}
        self.assertEqual(after, self.store_hashes)
        output = json.dumps(report, allow_nan=False)
        self.assertNotIn("raw_blobs", output)
        self.assertNotIn(self.predictions[0]["race_id"], output)
        self.assertNotIn("token", output)


if __name__ == "__main__":
    unittest.main()
