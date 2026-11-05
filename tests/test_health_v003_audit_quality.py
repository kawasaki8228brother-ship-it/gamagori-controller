"""Stdlib-only, supplied synthetic inputs; no HTTP, app or DB operations."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import hashlib
import unittest
from unittest.mock import patch


_PATH = Path(__file__).resolve().parents[1] / "development/health_residuals_20261106_v003/audit_quality.py"
_SPEC = importlib.util.spec_from_file_location("health_v003_audit_quality", _PATH)
qa = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qa)


def http_observation():
    return {"status_code": 200, "fetch_state": "RETURNED", "parse_state": "PARSED",
            "content_length": 100, "content_length_unit": "OCTETS", "wire_body_bytes": 100,
            "wire_count_unit": "ENCODED_ENTITY_OCTETS", "decoded_body_bytes": 100,
            "decoded_count_unit": "DECODED_ENTITY_OCTETS", "content_encoding": "identity",
            "text_encoding": "utf-8", "stream_completed": True, "document_end_observed": True,
            "parsed_rows": 12, "table_tag_observed": True}


def rehash(row):
    payload = json.loads(row["payload_raw"])
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    digest = hashlib.sha256(raw).hexdigest()
    row["payload_raw"] = raw.decode("ascii")
    row["hashes"] = {"raw_sha256": digest, "canonical_before_sha256": digest, "canonical_after_sha256": digest}


class HTTPQualityTests(unittest.TestCase):
    def test_consistent_input_never_official_success_or_runtime_port(self):
        report = qa.diagnose_http_observation(http_observation())
        self.assertEqual(report["status"], "CONSISTENT_SUPPLIED_DECLARATIONS_ONLY")
        self.assertEqual(report["http_status"], 200)
        self.assertEqual(report["official_success"], "NOT_ASSESSED")
        self.assertFalse(report["runtime_integrated"])

    def test_twelve_rows_table_tag_do_not_prove_transport(self):
        value = http_observation()
        for field in ("status_code", "wire_body_bytes", "stream_completed", "document_end_observed"):
            value.pop(field)
        report = qa.diagnose_http_observation(value)
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertIsNone(report["http_status"])
        self.assertIn("HTTP_STATUS_UNOBSERVED", report["reasons"])
        self.assertEqual(report["parsed_rows"], 12)

    def test_http_status_and_fetch_parse_observations_are_separate(self):
        report = qa.diagnose_http_observation(dict(http_observation(), status_code=403, parse_state="REJECTED"))
        self.assertEqual(report["http_status"], 403)
        self.assertEqual(report["fetch_state"], "RETURNED")
        self.assertEqual(report["parse_state"], "REJECTED")
        self.assertEqual(report["status"], "UNVERIFIED")

    def test_unknown_units_never_compare_text_character_count(self):
        report = qa.diagnose_http_observation(dict(http_observation(), content_length_unit="CHARACTERS", wire_body_bytes=17, decoded_body_bytes=17))
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertEqual(report["length_comparison"], "UNVERIFIED")

    def test_gzip_only_decoded_size_is_unverified_not_truncation(self):
        value = dict(http_observation(), content_encoding="gzip", decoded_body_bytes=1000)
        value["wire_body_bytes"] = None
        report = qa.diagnose_http_observation(value)
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertIn("COMPRESSED_DECODED_LENGTH_NOT_COMPARABLE", report["reasons"])
        self.assertNotIn("ENCODED_ENTITY_LENGTH_MISMATCH", report["reasons"])

    def test_gzip_encoded_entity_count_can_match_independently(self):
        report = qa.diagnose_http_observation(dict(http_observation(), content_encoding="gzip", decoded_body_bytes=1000))
        self.assertEqual(report["length_comparison"], "ENCODED_ENTITY_MATCH")
        self.assertEqual(report["decoded_body_bytes"], 1000)
        self.assertEqual(report["official_success"], "NOT_ASSESSED")

    def test_encoded_mismatch_and_identity_contradiction_detected(self):
        report = qa.diagnose_http_observation(dict(http_observation(), wire_body_bytes=99))
        self.assertEqual(report["status"], "INCONSISTENCY")
        self.assertIn("ENCODED_ENTITY_LENGTH_MISMATCH", report["reasons"])

    def test_noncomplete_stream_and_unknown_status_remain_unverified(self):
        for field, value in (("stream_completed", False), ("document_end_observed", False),
                             ("status_code", True), ("status_code", None), ("decoded_body_bytes", True)):
            with self.subTest(field=field):
                self.assertEqual(qa.diagnose_http_observation(dict(http_observation(), **{field: value}))["status"], "UNVERIFIED")

    def test_unknown_fields_and_strings_not_echoed_and_input_immutable(self):
        value = dict(http_observation(), text_encoding="PRIVATE_SECRET_CHARSET", arbitrary="PRIVATE_SECRET_FIELD")
        before = deepcopy(value)
        report = qa.diagnose_http_observation(value)
        self.assertEqual(value, before)
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))
        self.assertEqual(report["status"], "UNVERIFIED")

    def test_failed_fetch_and_parser_rejection_stay_separate(self):
        failed = qa.diagnose_http_observation(dict(http_observation(), fetch_state="FAILED"))
        rejected = qa.diagnose_http_observation(dict(http_observation(), parse_state="REJECTED"))
        self.assertIn("FETCH_FAILED_DECLARED", failed["reasons"])
        self.assertNotIn("PARSE_REJECTED_DECLARED", failed["reasons"])
        self.assertIn("PARSE_REJECTED_DECLARED", rejected["reasons"])
        self.assertEqual(failed["status"], "UNVERIFIED")


class StateQualityTests(unittest.TestCase):
    def test_previous_day_nonterminal_separate_older_current_and_terminal(self):
        rows = [{"race_id": "20990106_GAM_01R", "status": "PENDING"},
                {"race_id": "20990106_GAM_02R", "status": "SAFE_STOP"},
                {"race_id": "20990106_GAM_03R", "status": "TERMINAL"},
                {"race_id": "20990105_GAM_01R", "status": "PENDING"},
                {"race_id": "20990107_GAM_01R", "status": "PENDING"}]
        before = deepcopy(rows)
        report = qa.summarize_prior_unfinished(rows, "20990107")
        self.assertEqual(report["previous_day_nonterminal_count"], 2)
        self.assertEqual(report["older_nonterminal_count"], 1)
        self.assertEqual(rows, before)
        self.assertNotIn("20990106_GAM", json.dumps(report))
        self.assertEqual(report["query_completeness"], "UNVERIFIED_NO_DB_READ")

    def test_bad_calendar_unknown_fields_missing_and_status_distinguished(self):
        rows = [{"race_id": "20990230_GAM_01R", "status": "PENDING"},
                {"race_id": "20990106_GAM_01R", "status": "PENDING", "PRIVATE": "SECRET"},
                {"race_id": "20990106_GAM_02R"},
                {"race_id": "20990106_GAM_03R", "status": "UNREVIEWED"}]
        report = qa.summarize_prior_unfinished(rows, "20990107")
        self.assertEqual(report["invalid_date_rows"], 1)
        self.assertEqual(report["unknown_field_rows"], 1)
        self.assertEqual(report["missing_field_rows"], 1)
        self.assertEqual(report["unknown_status_rows"], 2)
        self.assertIsNone(report["previous_day_nonterminal_count"])
        self.assertNotIn("SECRET", json.dumps(report))

    def test_duplicate_identity_not_arbitrarily_deduplicated(self):
        report = qa.summarize_prior_unfinished([
            {"race_id": "20990106_GAM_01R", "status": "PENDING"},
            {"race_id": "20990106_GAM_01R", "status": "TERMINAL"}], "20990107")
        self.assertEqual(report["duplicate_identity_rows"], 2)
        self.assertIsNone(report["previous_day_nonterminal_count"])

    def test_no_collection_is_unknown_empty_collection_is_observed_scope_zero(self):
        self.assertIsNone(qa.summarize_prior_unfinished(None, "20990107")["previous_day_nonterminal_count"])
        self.assertEqual(qa.summarize_prior_unfinished([], "20990107")["previous_day_nonterminal_count"], 0)
        self.assertIsNone(qa.summarize_prior_unfinished([], "20990230")["previous_day_nonterminal_count"])
        self.assertIsNone(qa.summarize_prior_unfinished([], "00010101")["previous_day_nonterminal_count"])


class OperationalQualityTests(unittest.TestCase):
    def row(self):
        return deepcopy(qa.make_synthetic_operational_fixture()["rows"][12])

    def test_reuses_pinned_a_checker_consistent_and_inconsistent_synthetic_rows(self):
        row = self.row()
        before = deepcopy(row)
        observed = qa.audit_operational_rows([row])
        self.assertEqual(observed["report"]["rows"][0]["status"], "OBSERVED")
        self.assertEqual(observed["implementation_reference"]["commit"], qa.OBS_COMMIT)
        self.assertEqual(row, before)
        row["columns"]["event_uuid"] = "SYNTHETIC_CONFLICT"
        self.assertEqual(qa.audit_operational_rows([row])["report"]["rows"][0]["status"], "INCONSISTENCY")

    def test_identical_duplicate_and_same_key_different_raw_hash_conflict(self):
        row = self.row()
        same = qa.audit_operational_rows([row, deepcopy(row)])["report"]
        self.assertIn("REPEATED_IDENTICAL_KEY_OBSERVATION", same["rows"][0]["reasons"])
        changed = deepcopy(row)
        payload = json.loads(changed["payload_raw"])
        payload["synthetic_extra"] = "DIFFERENT"
        changed["payload_raw"] = json.dumps(payload)
        rehash(changed)
        different = qa.audit_operational_rows([row, changed])["report"]
        self.assertIn("DUPLICATE_KEY_DIFFERENT_RAW_PAYLOAD", different["rows"][0]["reasons"])
        self.assertEqual(different["rows"][0]["status"], "INCONSISTENCY")

    def test_b_never_uses_confirmed_a_formula(self):
        row = self.row()
        row["columns"]["source"] = "B"
        report = qa.audit_operational_rows([row])
        self.assertEqual(report["report"]["rows"][0]["status"], "OUT_OF_SCOPE")
        self.assertFalse(report["report"]["rows"][0]["a_idempotency"]["evaluated"])
        self.assertIn("UNVERIFIED", report["B_formula"])

    def test_pinned_source_mismatch_is_not_executed(self):
        with patch.object(qa.Path, "read_bytes", return_value=b"raise RuntimeError('PRIVATE_SECRET')"):
            report = qa.audit_operational_rows([])
        self.assertEqual(report["status"], "UNVERIFIED")
        self.assertNotIn("PRIVATE_SECRET", json.dumps(report))


class SQLiteDesignTests(unittest.TestCase):
    def request(self):
        return {"window": "OFFHOURS", "window_confirmed": True, "service_identity_confirmed": True,
                "individual_go_reference_sha256": "a" * 64, "active_processing_absent_confirmed": True,
                "db_open_mode": "mode=ro", "immutable": False}

    def test_read_value_only_even_declared_context_grants_no_execution(self):
        report = qa.sqlite_offhours_audit_plan(self.request())
        self.assertEqual(report["planned_query"], "PRAGMA journal_mode")
        self.assertEqual(report["status"], "DESIGN_DECLARATIONS_ONLY_NOT_EXECUTION_GO")
        self.assertFalse(report["live_execution_authorized"])
        self.assertFalse(report["db_connection_performed"])
        self.assertFalse(report["offhours_reservation_created"])
        self.assertTrue(report["normal_shm_read_marks_possible"])

    def test_live_immutable_wrong_mode_and_missing_gate_are_unverified(self):
        for changes in ({"immutable": True}, {"db_open_mode": "rw"}, {"window": "ACTIVE"},
                        {"service_identity_confirmed": False}, {"individual_go_reference_sha256": None}):
            request = dict(self.request(), **changes)
            self.assertEqual(qa.sqlite_offhours_audit_plan(request)["status"], "UNVERIFIED")
        self.assertEqual(qa.sqlite_offhours_audit_plan({})["status"], "UNVERIFIED")

    def test_design_never_opens_sqlite_even_with_complete_assertions(self):
        with patch("sqlite3.connect", side_effect=AssertionError("NO_DATABASE_CONNECTION")) as connect:
            qa.sqlite_offhours_audit_plan(self.request())
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
