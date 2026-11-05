"""P1 pure-local preparation checks on invented year2099 captures only."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from model11.synthetic import make_dataset
from model11.shadow_launch.sources import SourceAdapter, make_synthetic_source_fixture
from model11.shadow_preparation.capture_review import (
    COURSE_TOP_LEVEL, RAW_TOP_LEVEL, audit_capture_preparation,
    make_open_mapping_template, required_mapping_inventory,
)


def resign(capture, document):
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    digest = sha256(payload).hexdigest()
    capture["payload_bytes"] = payload
    capture["payload_sha256"] = digest
    capture["history"][-1]["payload_sha256"] = digest
    capture["history"][-1]["evidence_sha256"] = sha256(("SYNTHETIC_TEST_VERSION:" + digest).encode()).hexdigest()


class CapturePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = make_synthetic_source_fixture(make_dataset(3, 1, 735)["races"][0])

    def audit(self, fixture):
        return audit_capture_preparation(fixture["mapping"], fixture["capture"], synthetic_validation=True)

    def test_default_hold_does_not_inspect_context_or_convert(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError("DEFAULT_INSPECTED_CONTEXT")
        with patch("model11.shadow_preparation.capture_review.SourceAdapter", side_effect=AssertionError("MUST_NOT_CONSTRUCT")):
            for flag in (False, None, 0, 1, "true"):
                report = audit_capture_preparation(Forbidden(), Forbidden(), synthetic_validation=flag)
                self.assertEqual(report["status"], "HOLD")
                self.assertFalse(report["converter_called"])
                self.assertFalse(report["application_ready"])

    def test_explicit_valid_synthetic_capture_is_software_candidate_only(self):
        before = deepcopy(self.fixture)
        report = self.audit(self.fixture)
        self.assertEqual(report["software_check"], "PASS")
        self.assertEqual(report["converter_status"], "READY")
        self.assertEqual(report["status"], "SYNTHETIC_CAPTURE_VALIDATION_CANDIDATE")
        self.assertEqual(report["application_status"], "HOLD")
        self.assertFalse(report["application_ready"])
        self.assertEqual(report["official_mapping_status"], "OPEN")
        self.assertEqual(report["external_authenticity"], "UNVERIFIED")
        self.assertFalse(report["production_go"])
        self.assertEqual(report["source_summary"]["odds_ticket_count"], 120)
        self.assertEqual(self.fixture, before)

    def test_existing_converter_called_exactly_once(self):
        adapter = SourceAdapter(self.fixture["mapping"])
        with patch("model11.shadow_preparation.capture_review.SourceAdapter", return_value=adapter), \
             patch.object(adapter, "convert", wraps=adapter.convert) as convert:
            result = self.audit(self.fixture)
        self.assertEqual(convert.call_count, 1)
        self.assertIs(convert.call_args.args[0], self.fixture["capture"])
        self.assertTrue(result["converter_called"])

    def test_no_file_socket_database_io(self):
        with patch("builtins.open", side_effect=AssertionError("FILE_IO")), \
             patch("socket.socket", side_effect=AssertionError("NETWORK_IO")), \
             patch("sqlite3.connect", side_effect=AssertionError("DB_IO")):
            self.assertEqual(self.audit(self.fixture)["software_check"], "PASS")
            self.assertFalse(make_open_mapping_template()["enabled"])

    def test_private_claims_remain_hold_without_decoding_or_relabel(self):
        for classification in ("PRIVATE_REAL", "HQ14_PRIVATE_OFFLINE"):
            capture = {"data_classification": classification, "synthetic": False,
                       "payload_bytes": b"NOT_READ_NOT_ACTUAL_DATA"}
            with patch("model11.shadow_preparation.capture_review.SourceAdapter", side_effect=AssertionError("PRIVATE_CONVERSION_FORBIDDEN")):
                report = audit_capture_preparation(self.fixture["mapping"], capture, synthetic_validation=True)
            self.assertEqual(report["status"], "HOLD")
            self.assertFalse(report["converter_called"])
            self.assertEqual(capture["data_classification"], classification)
            self.assertFalse(capture["synthetic"])

    def test_mapping_absent_missing_path_and_unknown_unit_keep_old_codes(self):
        report = audit_capture_preparation(None, self.fixture["capture"], synthetic_validation=True)
        self.assertEqual(report["reasons"], ["SOURCE_MAPPING_REQUIRED"])
        fixture = deepcopy(self.fixture)
        fixture["mapping"]["raw_fields"]["boats"] = "/missing_boats"
        self.assertEqual(self.audit(fixture)["reasons"], ["SOURCE_CAPTURE_JSON_OR_FIELDS_INVALID"])
        fixture = deepcopy(self.fixture)
        fixture["mapping"]["feature_units"]["st"] = "UNKNOWN_UNIT"
        self.assertEqual(self.audit(fixture)["reasons"], ["SOURCE_MAPPING_FEATURE_UNITS_UNREVIEWED"])

    def test_known_units_pass_unknown_raw_unit_holds_without_conversion(self):
        self.assertEqual(self.audit(self.fixture)["software_check"], "PASS")
        fixture = deepcopy(self.fixture)
        document = json.loads(fixture["capture"]["payload_bytes"])
        document["invented_raw"]["boats"][0]["features"]["st"]["unit"] = "UNREGISTERED_SECONDS_TRANSFORM"
        resign(fixture["capture"], document)
        report = self.audit(fixture)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("RAW_FEATURE_UNIT_MISMATCH", report["reasons"])

    def test_missing_feature_and_exhibition_never_imputed(self):
        for kind in ("missing", "null", "exhibition"):
            fixture = deepcopy(self.fixture)
            document = json.loads(fixture["capture"]["payload_bytes"])
            features = document["invented_raw"]["boats"][0]["features"]
            if kind == "missing": del features["st"]["value"]
            elif kind == "null": features["st"]["value"] = None
            else: del features["exhibition"]
            resign(fixture["capture"], document)
            report = self.audit(fixture)
            self.assertEqual(report["software_check"], "UNVERIFIED")
            self.assertEqual(report["status"], "HOLD")
            self.assertIn("SOURCE_RAW_GATE_HOLD", report["reasons"])

    def test_future_feature_and_capture_times_preserve_old_reason_codes(self):
        fixture = deepcopy(self.fixture)
        document = json.loads(fixture["capture"]["payload_bytes"])
        raw = document["invented_raw"]
        raw["boats"][0]["features"]["motor"]["revision_at"] = raw["deadline"]["value"]
        resign(fixture["capture"], document)
        self.assertIn("RAW_FEATURE_LATE_OR_FUTURE_REVISION", self.audit(fixture)["reasons"])
        fixture = deepcopy(self.fixture)
        raw = json.loads(fixture["capture"]["payload_bytes"])["invented_raw"]
        fixture["capture"]["available_at"] = raw["deadline"]["value"]
        fixture["capture"]["history"][-1]["available_at"] = raw["deadline"]["value"]
        self.assertIn("SOURCE_CAPTURE_LATE_OR_FUTURE_REVISION", self.audit(fixture)["reasons"])

    def test_missing_invalid_future_and_mismatched_history_hold(self):
        for kind, code in (("missing", "SOURCE_CAPTURE_HISTORY_REQUIRED"),
                           ("mismatch", "SOURCE_CAPTURE_HISTORY_CURRENT_VERSION_MISMATCH"),
                           ("bad_hash", "SOURCE_CAPTURE_HISTORY_INVALID"),
                           ("future", "SOURCE_HISTORY_LATE_OR_FUTURE_REVISION")):
            fixture = deepcopy(self.fixture)
            if kind == "missing": fixture["capture"]["history"] = []
            elif kind == "mismatch": fixture["capture"]["history"][-1]["payload_sha256"] = "f" * 64
            elif kind == "bad_hash": fixture["capture"]["history"][-1]["evidence_sha256"] = "UNKNOWN"
            else:
                raw = json.loads(fixture["capture"]["payload_bytes"])["invented_raw"]
                fixture["capture"]["history"][-1]["revision_at"] = raw["deadline"]["value"]
            self.assertIn(code, self.audit(fixture)["reasons"])

    def test_incomplete_or_stale_120_market_holds(self):
        for kind in ("incomplete", "stale"):
            fixture = deepcopy(self.fixture)
            document = json.loads(fixture["capture"]["payload_bytes"])
            raw = document["invented_raw"]
            if kind == "incomplete": del raw["odds_snapshot"]["odds"]["1-2-3"]
            else:
                raw["odds_snapshot"]["acquired_at"] = (datetime.fromisoformat(raw["prediction_at"]) - timedelta(minutes=3)).isoformat()
            resign(fixture["capture"], document)
            self.assertIn("SOURCE_COMPLETE_MARKET_REQUIRED", self.audit(fixture)["reasons"])

    def test_private_secret_values_and_converter_exception_are_not_echoed(self):
        fixture = deepcopy(self.fixture)
        fixture["capture"]["source_id"] = "https://PRIVATE_SECRET:credential@private.invalid/path"
        report = self.audit(fixture)
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))
        with patch("model11.shadow_preparation.capture_review.SourceAdapter", side_effect=RuntimeError("PRIVATE_SECRET")):
            report = self.audit(self.fixture)
        self.assertFalse(report["converter_called"])
        self.assertEqual(report["reasons"], ["CAPTURE_REVIEW_UNVERIFIED"])
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))

    def test_inventory_covers_full_raw_contract_and_all_120_tickets(self):
        from model11.shadow_launch.sources import _RAW_FIELDS, _COURSE_FIELDS
        self.assertEqual(set(RAW_TOP_LEVEL), _RAW_FIELDS)
        self.assertEqual(set(COURSE_TOP_LEVEL), _COURSE_FIELDS)
        rows = required_mapping_inventory()
        targets = [row["local_target"] for row in rows]
        self.assertEqual(len(targets), len(set(targets)))
        odds = {path.rsplit("/", 1)[1] for path in targets if path.startswith("/raw/odds_snapshot/odds/")}
        self.assertEqual(odds, {"-".join(map(str, t)) for t in permutations(range(1, 7), 3)})
        for name in ("st", "turn", "motor", "ability", "exhibition"):
            for field in ("value", "unit", "acquired_at", "available_at", "revision_at", "evidence_sha256"):
                self.assertIn("/raw/boats/{boat_index}/features/" + name + "/" + field, targets)
        self.assertIn("/raw/boats/{boat_index}/motor_identity/effective_at", targets)
        self.assertIn("/capture/history/{history_index}/evidence_sha256", targets)
        for row in rows:
            for key in ("actual_official_pointer", "actual_official_unit", "actual_official_format", "actual_official_source"):
                self.assertIsNone(row[key])
            self.assertEqual(row["review_status"], "OPEN")

    def test_open_template_null_unknowns_disabled_and_not_runnable(self):
        template = make_open_mapping_template()
        self.assertFalse(template["enabled"])
        self.assertEqual(template["status"], "OPEN")
        self.assertEqual(template["application_status"], "HOLD")
        self.assertTrue(all(value is None for value in template["source_mapping_candidate"]["raw_fields"].values()))
        self.assertTrue(all(value is None for value in template["source_mapping_candidate"]["feature_units"].values()))
        self.assertEqual(SourceAdapter(template["source_mapping_candidate"]).convert(self.fixture["capture"])["status"], "HOLD")
        file = Path(__file__).resolve().parents[1] / "shadow_preparation_v006/templates/field_mapping.OPEN.json"
        self.assertEqual(json.loads(file.read_bytes()), template)


if __name__ == "__main__":
    unittest.main()
