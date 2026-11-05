"""Invented-capture mapping/gate tests; no actual official source or network."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from model11.shadow_launch.sources import FixtureTransport, SourceAdapter, make_synthetic_source_fixture
from model11.synthetic import make_dataset


def resign(capture, document):
    body = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    capture["payload_bytes"] = body
    capture["payload_sha256"] = sha256(body).hexdigest()
    capture["history"][-1]["payload_sha256"] = capture["payload_sha256"]
    return capture


def private_looking_fixture(fixture):
    """Only edit invented fixture metadata; never process an actual private race."""
    item = deepcopy(fixture)
    mapping, capture = item["mapping"], item["capture"]
    mapping.update(data_classification="PRIVATE_REAL", synthetic=False,
                   format_id="PRIVATE_REVIEWED_JSON_V001", source_id="OFFICIAL_REVIEWED_LOCAL_CAPTURE_V001",
                   version="invented-private-looking-attack-v001")
    reviews = {"hq14_review_sha256": "a" * 64, "claude_review_sha256": "b" * 64}
    mapping["review_evidence"] = reviews
    mapping["feature_specs"].update(mapping_status="HQ14_PRIVATE_MAPPING_UNVERIFIED", review_evidence=deepcopy(reviews),
                                     version="invented-private-looking-feature-specs")
    mapping["course_source_ids"] = {"frame": "OFFICIAL_FRAME_PRELOCK_V001", "exhibition": "OFFICIAL_EXHIBITION_PRELOCK_V001"}
    capture.update(data_classification="PRIVATE_REAL", synthetic=False,
                   format_id=mapping["format_id"], source_id=mapping["source_id"])
    doc = json.loads(capture["payload_bytes"])
    doc["invented_raw"]["data_classification"] = "HQ14_PRIVATE_OFFLINE"
    course = doc["invented_course"]
    course.update(data_classification="PRIVATE_REAL", synthetic=False)
    for key, source in mapping["course_source_ids"].items():
        if course["course_inputs"][key] is not None:
            course["course_inputs"][key]["source_id"] = source
    resign(capture, doc)
    return item


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.race = make_dataset(days=3, races_per_day=1, seed=630)["races"][0]
        cls.fixture = make_synthetic_source_fixture(cls.race)

    def converted(self, fixture=None):
        fixture = self.fixture if fixture is None else fixture
        return SourceAdapter(fixture["mapping"]).convert(fixture["capture"])

    def test_complete_fixture_preserves_bytes_provenance_and_claim_limits(self):
        before = deepcopy(self.fixture)
        result = self.converted()
        self.assertEqual(result["status"], "READY", result)
        self.assertEqual(result["source_evidence"]["payload_sha256"], sha256(self.fixture["capture"]["payload_bytes"]).hexdigest())
        self.assertEqual(result["source_evidence"]["history"], self.fixture["capture"]["history"])
        self.assertEqual(result["source_evidence"]["odds_ticket_count"], 120)
        self.assertEqual(result["source_evidence"]["active_boat_count"], 6)
        self.assertEqual(result["source_evidence"]["external_authenticity"], "UNVERIFIED")
        self.assertEqual(result["source_evidence"]["actual_official_mapping"], "OPEN")
        self.assertFalse(result["production_go"])
        self.assertEqual(self.fixture, before)

    def test_constructor_and_conversion_no_file_or_socket_io(self):
        with patch("builtins.open", side_effect=AssertionError("NO_IO")), patch("socket.socket", side_effect=AssertionError("NO_NETWORK")):
            adapter = SourceAdapter(self.fixture["mapping"])
            self.assertEqual(adapter.convert(self.fixture["capture"])["status"], "READY")

    def test_mapping_is_frozen_detached_and_changes_do_not_adapt(self):
        mapping = deepcopy(self.fixture["mapping"])
        adapter = SourceAdapter(mapping)
        mapping["raw_fields"]["race_id"] = "/wrong"
        separate = adapter.mapping
        separate["raw_fields"]["race_id"] = "/also_wrong"
        self.assertEqual(adapter.convert(self.fixture["capture"])["status"], "READY")
        adapter._mapping["version"] = "changed"
        self.assertEqual(adapter.convert(self.fixture["capture"])["reasons"], ["SOURCE_FROZEN_MAPPING_CHANGED"])

    def test_classification_flags_missing_unknown_contradictory_hold(self):
        for key, value in (("data_classification", "UNKNOWN"), ("synthetic", False), ("synthetic", 1), ("synthetic", None)):
            fixture = deepcopy(self.fixture)
            fixture["capture"][key] = value
            self.assertEqual(self.converted(fixture)["status"], "HOLD")
        fixture = deepcopy(self.fixture)
        del fixture["capture"]["synthetic"]
        self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_unregistered_official_prefix_and_secret_url_not_output(self):
        secret = "https://user:PRIVATE_SECRET@proxy.invalid/private"
        for field in ("source_id", "format_id"):
            fixture = deepcopy(self.fixture)
            fixture["capture"][field] = secret
            result = self.converted(fixture)
            self.assertEqual(result["status"], "HOLD")
            self.assertNotIn(secret, json.dumps(result))
            fixture = deepcopy(self.fixture)
            fixture["mapping"][field] = "OFFICIAL_UNREGISTERED"
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_private_looking_claims_never_relabel_synthetic_or_authenticate(self):
        fixture = private_looking_fixture(self.fixture)
        result = self.converted(fixture)
        self.assertEqual(result["status"], "READY", result)
        self.assertEqual(result["raw"]["data_classification"], "HQ14_PRIVATE_OFFLINE")
        self.assertEqual(result["course"]["data_classification"], "PRIVATE_REAL")
        self.assertIs(result["course"]["synthetic"], False)
        self.assertEqual(result["source_evidence"]["mapping_review"], "SELF_REPORTED_HASHES_ONLY")
        self.assertEqual(result["source_evidence"]["external_authenticity"], "UNVERIFIED")
        self.assertFalse(result["production_go"])

    def test_private_mapping_missing_dummy_review_metadata_hold(self):
        fixture = private_looking_fixture(self.fixture)
        del fixture["mapping"]["review_evidence"]
        self.assertEqual(self.converted(fixture)["status"], "HOLD")
        fixture = private_looking_fixture(self.fixture)
        fixture["mapping"]["review_evidence"]["claude_review_sha256"] = "missing"
        self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_private_payload_cannot_be_converted_under_synthetic_class(self):
        fixture = deepcopy(self.fixture)
        doc = json.loads(fixture["capture"]["payload_bytes"])
        doc["invented_raw"]["data_classification"] = "HQ14_PRIVATE_OFFLINE"
        resign(fixture["capture"], doc)
        result = self.converted(fixture)
        self.assertIn("SOURCE_PAYLOAD_CLASSIFICATION_MISMATCH_NO_RELABEL", result["reasons"])
        self.assertIsNone(result["raw"])

    def test_missing_and_invalid_pointer_fields_hold_no_defaults(self):
        fixture = deepcopy(self.fixture)
        fixture["mapping"]["raw_fields"]["race_id"] = "/missing/race_id"
        self.assertIn("SOURCE_CAPTURE_JSON_OR_FIELDS_INVALID", self.converted(fixture)["reasons"])
        for pointer in (None, "https://PRIVATE_SECRET.invalid/path", "/bad~2escape"):
            fixture = deepcopy(self.fixture)
            fixture["mapping"]["raw_fields"]["race_id"] = pointer
            result = self.converted(fixture)
            self.assertEqual(result["status"], "HOLD")
            self.assertNotIn("PRIVATE_SECRET", json.dumps(result))

    def test_json_pointer_rfc6901_escaping(self):
        fixture = deepcopy(self.fixture)
        doc = json.loads(fixture["capture"]["payload_bytes"])
        doc["invented/raw~data"] = doc.pop("invented_raw")
        for key in fixture["mapping"]["raw_fields"]:
            fixture["mapping"]["raw_fields"][key] = "/invented~1raw~0data/" + key
        resign(fixture["capture"], doc)
        self.assertEqual(self.converted(fixture)["status"], "READY")

    def test_payload_hash_bytes_utf8_json_duplicates_and_nonfinite(self):
        fixture = deepcopy(self.fixture)
        fixture["capture"]["payload_bytes"] += b" "
        self.assertIn("SOURCE_CAPTURE_HASH_MISMATCH", self.converted(fixture)["reasons"])
        for payload in (b"\xff", b"{bad", b'{"x":1,"x":2}', b'{"x":NaN}'):
            fixture = deepcopy(self.fixture)
            fixture["capture"]["payload_bytes"] = payload
            fixture["capture"]["payload_sha256"] = sha256(payload).hexdigest()
            result = self.converted(fixture)
            self.assertEqual(result["status"], "HOLD")
            self.assertIsNone(result["raw"])

    def test_missing_feature_exhibition_unknown_fl_and_motor_mismatch_hold(self):
        for kind in ("feature", "exhibition", "unknown_fl", "motor"):
            fixture = deepcopy(self.fixture)
            doc = json.loads(fixture["capture"]["payload_bytes"])
            boat = doc["invented_raw"]["boats"][0]
            if kind == "feature": boat["features"]["st"]["value"] = None
            elif kind == "exhibition": del boat["features"]["exhibition"]
            elif kind == "unknown_fl": boat["fl"]["value"] = None
            else: boat["features"]["motor"]["motor_id"] = "SYNTHETIC_WRONG_ID"
            resign(fixture["capture"], doc)
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_known_fl_true_preserved_without_invented_penalty(self):
        fixture = deepcopy(self.fixture)
        doc = json.loads(fixture["capture"]["payload_bytes"])
        doc["invented_raw"]["boats"][0]["fl"]["value"] = True
        resign(fixture["capture"], doc)
        result = self.converted(fixture)
        self.assertEqual(result["status"], "READY")
        self.assertIs(result["raw"]["boats"][0]["fl"]["value"], True)
        self.assertIn("FL_PRESENT_RESEARCH_INPUT", result["source_evidence"]["raw_warning_codes"])

    def test_future_course_fl_scratch_and_feature_hold(self):
        for kind in ("course", "fl", "scratched", "feature"):
            fixture = deepcopy(self.fixture)
            doc = json.loads(fixture["capture"]["payload_bytes"])
            raw = doc["invented_raw"]
            target = raw["boats"][0][kind] if kind != "feature" else raw["boats"][0]["features"]["st"]
            target["available_at"] = raw["deadline"]["value"]
            resign(fixture["capture"], doc)
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_course_source_classification_and_numeric_binding_hold(self):
        for kind in ("unused_official", "course_numeric", "course_time"):
            fixture = deepcopy(self.fixture)
            doc = json.loads(fixture["capture"]["payload_bytes"])
            course = doc["invented_course"]
            if kind == "unused_official": course["course_inputs"]["frame"]["source_id"] = "OFFICIAL_FRAME_PRELOCK_V001"
            elif kind == "course_numeric":
                courses = course["course_inputs"]["exhibition"]["courses"]
                courses["1"], courses["2"] = courses["2"], courses["1"]
            else: course["course_inputs"]["exhibition"]["available_at"] = doc["invented_raw"]["deadline"]["value"]
            resign(fixture["capture"], doc)
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_complete_market_missing_stale_future_or_partial_hold(self):
        for kind in ("missing", "stale", "future", "partial", "unit"):
            fixture = deepcopy(self.fixture)
            doc = json.loads(fixture["capture"]["payload_bytes"])
            raw = doc["invented_raw"]
            if kind == "missing": raw["odds_snapshot"] = None
            elif kind == "stale":
                raw["odds_snapshot"]["acquired_at"] = (datetime.fromisoformat(raw["prediction_at"]) - timedelta(minutes=3)).isoformat()
            elif kind == "future": raw["odds_snapshot"]["available_at"] = raw["deadline"]["value"]
            elif kind == "unit": raw["odds_snapshot"]["unit"] = "UNKNOWN"
            else: del raw["odds_snapshot"]["odds"]["1-2-3"]
            resign(fixture["capture"], doc)
            self.assertIn("SOURCE_COMPLETE_MARKET_REQUIRED", self.converted(fixture)["reasons"])

    def test_capture_history_preserved_but_late_unknown_or_missing_hold(self):
        for kind in ("missing", "mismatch", "future", "bad_hash"):
            fixture = deepcopy(self.fixture)
            capture = fixture["capture"]
            if kind == "missing": capture["history"] = []
            elif kind == "mismatch": capture["history"][-1]["payload_sha256"] = "a" * 64
            elif kind == "bad_hash": capture["history"][-1]["evidence_sha256"] = "unknown"
            else:
                deadline = json.loads(capture["payload_bytes"])["invented_raw"]["deadline"]["value"]
                capture["history"][-1]["revision_at"] = deadline
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_capture_invalid_offset_and_future_envelope_hold(self):
        for stamp in ("2099-01-01T12:00:00+09:99", "2099-01-01T12:00:00+24:00", "2099-01-01T12:00:00-00:00"):
            fixture = deepcopy(self.fixture)
            fixture["capture"]["available_at"] = stamp
            self.assertEqual(self.converted(fixture)["status"], "HOLD")

    def test_materialized_capture_cannot_predate_known_component_times(self):
        fixture = deepcopy(self.fixture)
        doc = json.loads(fixture["capture"]["payload_bytes"])
        oldest = min(datetime.fromisoformat(doc["invented_raw"]["boats"][0]["features"]["st"][field])
                     for field in ("acquired_at", "available_at", "revision_at")) - timedelta(seconds=1)
        for field in ("acquired_at", "available_at", "revision_at"):
            fixture["capture"][field] = oldest.isoformat()
            fixture["capture"]["history"][-1][field] = oldest.isoformat()
        result = self.converted(fixture)
        self.assertEqual(result["status"], "HOLD")
        for field in ("ACQUIRED_AT", "AVAILABLE_AT", "REVISION_AT"):
            self.assertIn("SOURCE_CAPTURE_MATERIALIZATION_PRECEDES_COMPONENT_" + field, result["reasons"])

    def test_explicit_fixture_transport_only_and_no_implicit_fetch(self):
        class ForbiddenTransport:
            calls = 0
            def fetch(self, key):
                self.calls += 1
                raise AssertionError("MUST_NOT_CALL")
        forbidden = ForbiddenTransport()
        adapter = SourceAdapter(self.fixture["mapping"], forbidden)
        self.assertEqual(forbidden.calls, 0)
        self.assertEqual(adapter.fetch("PRIVATE_SECRET")["status"], "HOLD")
        self.assertEqual(forbidden.calls, 0)
        fixture_transport = FixtureTransport({"invented": self.fixture["capture"]})
        adapter = SourceAdapter(self.fixture["mapping"], fixture_transport)
        self.assertEqual(adapter.fetch("invented")["status"], "READY")
        self.assertEqual(adapter.fetch("missing")["status"], "HOLD")

    def test_helper_never_converts_real_input_to_synthetic(self):
        for key, value in (("synthetic", False), ("data_classification", "PRIVATE_REAL"), ("target_date", "2026-11-05")):
            race = deepcopy(self.race)
            race[key] = value
            with self.assertRaisesRegex(ValueError, "SOURCE_SYNTHETIC_FIXTURE_ONLY"):
                make_synthetic_source_fixture(race)


if __name__ == "__main__":
    unittest.main()
