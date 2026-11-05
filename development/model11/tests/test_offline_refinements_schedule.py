"""Derived invented fixtures; decode retained v006 evidence, never rerun writer."""
import base64
from copy import deepcopy
from datetime import timedelta
import gzip
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from model11.offline_refinements.schedule import audit_manifest_coverage


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def frame_proof(proof):
    raw = canonical(proof)
    digest = hashlib.sha256(raw).hexdigest()
    return digest, {"raw_evidence_b64": base64.b64encode(raw).decode("ascii"),
                    "evidence_bytes": len(raw), "evidence_sha256": digest}


def repack(fixture, manifest):
    raw = canonical(manifest)
    digest = hashlib.sha256(raw).hexdigest()
    fixture["schedule"].update(raw_manifest_b64=base64.b64encode(raw).decode("ascii"),
                                manifest_bytes=len(raw), manifest_sha256=digest)
    fixture["schedule"]["approval"]["manifest_sha256"] = digest


def build_fixture(case="full"):
    """Public offline reproduction helper; every case is invented SYNTHETIC_ONLY.

    Returns schedule/predictions/target_date/expected_storage_id plus label.
    Reads only immutable retained v006 bundle; does not create a store or model.
    """
    package = Path(__file__).resolve().parents[1]
    retained = package / "shadow_preparation_v006" / "results"
    predictions = json.loads(gzip.decompress(base64.b64decode(
        (retained / "SYNTHETIC_ONLY.prediction-evidence-python312.json.gz.b64.txt").read_text(encoding="ascii"))))
    old = json.loads((retained / "python312-SYNTHETIC_ONLY.schedule.json").read_bytes())
    old_manifest = json.loads(base64.b64decode(old["raw_manifest_b64"]))
    day = old_manifest["target_date"]
    if not day.startswith("2099-") or len(predictions) != 12:
        raise ValueError("SYNTHETIC_PARENT_FIXTURE_REQUIRED")
    source = "SYNTHETIC_NORMALIZED_SCHEDULE_NOT_OFFICIAL"
    mapping = {"schema": "LOCAL_RACE_SCHEDULE_MAPPING_V001_PROPOSED", "mapping_id": "SYNTHETIC_V007",
               "mapping_version": "1", "venue": "GAMAGORI", "source_id": source,
               "classification": "SYNTHETIC_ONLY", "event_scope": "RACE_EVENT",
               "normalized_statuses": ["SCHEDULED", "CANCELLED_OFFICIAL", "WITHDRAWN_OFFICIAL"]}
    mapping_sha = hashlib.sha256(canonical(mapping)).hexdigest()
    manifest = {"schema": "LOCAL_DAY_SCHEDULE_V002_PROPOSED", "venue": "GAMAGORI", "target_date": day,
                "source_id": source, "classification": "SYNTHETIC_ONLY", "mapping_sha256": mapping_sha,
                "races": [dict(row, status="SCHEDULED", status_evidence_sha256=None) for row in old_manifest["races"]],
                "closed_official_evidence_sha256": None}
    schedule = {"fixture_classification": "SYNTHETIC_ONLY", "mapping": mapping, "mapping_sha256": mapping_sha,
                "status_evidence": {}, "approval": {"approved": True, "declared_external_verification": True,
                "venue": "GAMAGORI", "target_date": day, "source_id": source,
                "classification": "SYNTHETIC_ONLY", "mapping_sha256": mapping_sha,
                "evidence_sha256": hashlib.sha256(b"SYNTHETIC_REVIEW_NOT_ACTUAL_APPROVAL").hexdigest()}}
    fixture = {"classification": "SYNTHETIC_ONLY", "case": case, "schedule": schedule,
               "predictions": predictions, "target_date": day,
               "expected_storage_id": predictions[0]["ledger"]["storage_id"]}
    from model11.shadow_preparation.coverage import _time
    def add_status(row=None, *, status="CANCELLED_OFFICIAL", after_deadline=False):
        effect = day + "T12:00:00+09:00"
        if after_deadline:
            effect = (_time(row["deadline"]) + timedelta(minutes=1)).isoformat()
        proof = {"schema": "LOCAL_RACE_STATUS_EVIDENCE_V001_PROPOSED" if row else "LOCAL_OFFICIAL_DAY_CLOSURE_EVIDENCE_V001_PROPOSED",
                 "event_scope": "RACE_EVENT" if row else "OFFICIAL_DAY", "status": status,
                 "venue": "GAMAGORI", "target_date": day, "source_id": source, "classification": "SYNTHETIC_ONLY",
                 "mapping_sha256": mapping_sha, "mapping_version": "1", "effective_at": effect,
                 "acquired_at": effect, "available_at": effect, "revision_at": effect}
        if row:
            proof.update(race_id=row["race_id"], race_no=row["race_no"])
        digest, frame = frame_proof(proof)
        schedule["status_evidence"][digest] = frame
        if row:
            row.update(status=status, status_evidence_sha256=digest)
        else:
            manifest["closed_official_evidence_sha256"] = digest
    if case == "short8":
        manifest["races"] = manifest["races"][:8]
        fixture["predictions"] = predictions[:8]
    elif case in ("one_cancelled", "one_withdrawn", "one_cancelled_with_prediction", "cancel_after_deadline_with_prediction"):
        add_status(manifest["races"][0], status="WITHDRAWN_OFFICIAL" if case == "one_withdrawn" else "CANCELLED_OFFICIAL",
                   after_deadline=case == "cancel_after_deadline_with_prediction")
        if case in ("one_cancelled", "one_withdrawn"):
            fixture["predictions"] = predictions[1:]
    elif case == "all_cancelled":
        for row in manifest["races"]:
            add_status(row)
        fixture["predictions"] = []
    elif case in ("empty", "empty_closed"):
        manifest["races"] = []
        fixture["predictions"] = []
        if case == "empty_closed":
            add_status(status="CLOSED_OFFICIAL")
    elif case != "full":
        raise ValueError("UNKNOWN_SYNTHETIC_FIXTURE_CASE")
    repack(fixture, manifest)
    return fixture


class ScheduleStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = build_fixture()

    def setUp(self):
        self.fixture = deepcopy(self.base)

    def audit(self, fixture=None):
        value = self.fixture if fixture is None else fixture
        return audit_manifest_coverage(value["schedule"], value["predictions"], target_date=value["target_date"],
                                       expected_storage_id=value["expected_storage_id"])

    def test_full_and_approved_short_manifest_take_count_from_rows(self):
        self.assertEqual(self.audit()["active_expected"], 12)
        short = self.audit(build_fixture("short8"))
        self.assertEqual(short["status"], "OBSERVATION_COMPLETE_LOCAL")
        self.assertEqual(short["active_expected"], 8)
        self.assertEqual(short["saved_predeadline_local"], 8)

    def test_official_cancel_and_race_withdrawal_are_not_missing_prediction(self):
        for case, key in (("one_cancelled", "cancelled_official"), ("one_withdrawn", "withdrawn_official")):
            result = self.audit(build_fixture(case))
            self.assertEqual(result["status"], "OBSERVATION_COMPLETE_LOCAL")
            self.assertEqual(result["active_expected"], 11)
            self.assertEqual(result[key], 1)
            self.assertEqual(result["no_observation"], 0)
        value = build_fixture("one_cancelled_with_prediction")
        value["predictions"][0] = {"race_id": value["predictions"][0]["race_id"], "observation": "READ_FAILED"}
        result = self.audit(value)
        self.assertEqual(result["status"], "OBSERVATION_COMPLETE_LOCAL")
        self.assertEqual(result["read_failed"], 0)
        self.assertEqual(result["excluded_read_failed"], 1)
        self.assertEqual(result["excluded_predictions_present"], 0)

    def test_missing_active_or_read_failed_never_infers_cancel(self):
        self.fixture["predictions"].pop(0)
        result = self.audit()
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["active_expected"], 12)
        self.assertEqual(result["no_observation"], 1)
        self.assertEqual(result["cancelled_official"], 0)
        self.fixture = deepcopy(self.base)
        self.fixture["predictions"][0] = {"race_id": self.fixture["predictions"][0]["race_id"], "observation": "READ_FAILED"}
        self.assertEqual(self.audit()["read_failed"], 1)

    def test_cancel_requires_hash_bound_race_status_proof(self):
        value = build_fixture("one_cancelled")
        value["schedule"]["status_evidence"] = {}
        result = self.audit(value)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["cancelled_official"], 0)
        value = build_fixture("one_cancelled")
        frame = next(iter(value["schedule"]["status_evidence"].values()))
        frame["evidence_sha256"] = "0" * 64
        self.assertEqual(self.audit(value)["status"], "HOLD")

    def test_boat_withdrawal_source_class_version_and_date_mismatch_hold(self):
        for field, replacement in (("event_scope", "BOAT_WITHDRAWAL"), ("source_id", "OTHER"),
                                   ("classification", "PRIVATE_REAL"), ("mapping_version", "2"), ("target_date", "2099-01-08")):
            value = build_fixture("one_withdrawn")
            manifest = json.loads(base64.b64decode(value["schedule"]["raw_manifest_b64"]))
            old_sha = manifest["races"][0]["status_evidence_sha256"]
            proof = json.loads(base64.b64decode(value["schedule"]["status_evidence"][old_sha]["raw_evidence_b64"]))
            proof[field] = replacement
            digest, frame = frame_proof(proof)
            value["schedule"]["status_evidence"] = {digest: frame}
            manifest["races"][0]["status_evidence_sha256"] = digest
            repack(value, manifest)
            self.assertEqual(self.audit(value)["status"], "HOLD", field)

    def test_invalid_effective_or_source_times_hold(self):
        for field, replacement in (("effective_at", "2099-01-08T12:00:00+09:00"),
                                   ("effective_at", "2099-01-07T12:00:00+08:60"),
                                   ("revision_at", "2099-01-07T12:01:00+09:00")):
            value = build_fixture("one_cancelled")
            manifest = json.loads(base64.b64decode(value["schedule"]["raw_manifest_b64"]))
            old_sha = manifest["races"][0]["status_evidence_sha256"]
            proof = json.loads(base64.b64decode(value["schedule"]["status_evidence"][old_sha]["raw_evidence_b64"]))
            proof[field] = replacement
            digest, frame = frame_proof(proof)
            value["schedule"]["status_evidence"] = {digest: frame}
            manifest["races"][0]["status_evidence_sha256"] = digest
            repack(value, manifest)
            self.assertEqual(self.audit(value)["status"], "HOLD", field)

    def test_existing_excluded_prediction_preserved_and_timing_visible(self):
        value = build_fixture("one_cancelled_with_prediction")
        before = deepcopy(value)
        result = self.audit(value)
        self.assertEqual(result["status"], "OBSERVATION_COMPLETE_LOCAL")
        self.assertEqual(result["excluded_predictions_present"], 1)
        self.assertEqual(result["rows"][0]["prediction_assessment"], "UNASSESSED_OFFICIAL_EXCLUSION")
        self.assertEqual(result["rows"][0]["effective_vs_generation"], "BEFORE_GENERATION")
        self.assertEqual(value, before)

    def test_after_deadline_cancellation_never_waives_prior_lock_or_ac1(self):
        result = self.audit(build_fixture("cancel_after_deadline_with_prediction"))
        self.assertEqual(result["rows"][0]["effective_vs_deadline"], "AFTER_DEADLINE")
        self.assertEqual(result["rows"][0]["effective_vs_generation"], "AFTER_GENERATION")
        self.assertEqual(result["prior_deadline_obligation"], "UNVERIFIED_ORIGINAL_SNAPSHOT_NOT_PROVIDED")
        self.assertEqual(result["ac1_or_first_lock_assessment"], "NOT_PERFORMED_CURRENT_MANIFEST_ONLY")

    def test_zero_active_requires_each_status_proof_or_explicit_closed_day(self):
        cancelled = self.audit(build_fixture("all_cancelled"))
        self.assertEqual(cancelled["status"], "OBSERVATION_COMPLETE_LOCAL")
        self.assertEqual(cancelled["active_expected"], 0)
        self.assertEqual(cancelled["cancelled_official"], 12)
        self.assertEqual(self.audit(build_fixture("empty"))["status"], "HOLD")
        self.assertEqual(self.audit(build_fixture("empty_closed"))["status"], "OBSERVATION_COMPLETE_LOCAL")

    def test_duplicate_conflicting_status_and_prediction_are_not_deduplicated(self):
        manifest = json.loads(base64.b64decode(self.fixture["schedule"]["raw_manifest_b64"]))
        manifest["races"][1]["race_id"] = manifest["races"][0]["race_id"]
        manifest["races"][1]["status"] = "WITHDRAWN_OFFICIAL"
        repack(self.fixture, manifest)
        self.assertEqual(self.audit()["status"], "HOLD")
        self.fixture = deepcopy(self.base)
        self.fixture["predictions"].append(deepcopy(self.fixture["predictions"][0]))
        result = self.audit()
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["active_expected"], 12)

    def test_unused_or_conflicting_proofs_and_unapproved_manifest_hold(self):
        value = build_fixture("one_cancelled")
        value["schedule"]["status_evidence"]["f" * 64] = next(iter(value["schedule"]["status_evidence"].values()))
        self.assertEqual(self.audit(value)["status"], "HOLD")
        self.fixture["schedule"]["approval"]["approved"] = False
        self.assertEqual(self.audit()["status"], "HOLD")

    def test_active_raw_corruption_still_uses_parent_integrity_checks(self):
        self.fixture["predictions"][0]["raw_blobs"]["input_b64"] = base64.b64encode(b"synthetic-corrupt").decode("ascii")
        result = self.audit()
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["rows"][0]["reasons"], ["RAW_INPUT_READBACK_MISMATCH"])

    def test_pure_checker_no_io_no_secret_echo_and_no_authenticity_pass(self):
        before = deepcopy(self.fixture)
        with patch("builtins.open", side_effect=AssertionError("NO_IO")), patch.object(Path, "read_bytes", side_effect=AssertionError("NO_IO")), patch.object(Path, "write_bytes", side_effect=AssertionError("NO_IO")):
            result = self.audit()
        self.assertEqual(self.fixture, before)
        self.assertEqual(result["external_source_authenticity"], "UNVERIFIED")
        self.assertEqual(result["cancellation_authenticity"], "UNVERIFIED")
        self.assertFalse(result["production_go"])
        output = json.dumps(result, allow_nan=False)
        self.assertNotIn(self.fixture["predictions"][0]["race_id"], output)


if __name__ == "__main__":
    unittest.main()
