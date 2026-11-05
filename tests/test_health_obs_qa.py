"""SYNTHETIC_ONLY inputs; not a reconstruction of 2026-11-05 event rows."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from development.health_residuals_20261105_v001.obs_qa import (
    audit_obs_rows, confirmed_a_idempotency, make_synthetic_obs_fixture,
)


def replace_payload(row, payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    digest = hashlib.sha256(raw).hexdigest()
    row.update(payload_raw=raw.decode("ascii"), hashes={"raw_sha256": digest,
               "canonical_before_sha256": digest, "canonical_after_sha256": digest})


class ObsQaTests(unittest.TestCase):
    def setUp(self):
        self.fixture = make_synthetic_obs_fixture()
        self.row = deepcopy(self.fixture["rows"][-1])  # Fully provided synthetic RUN_END.

    def test_synthetic_twenty_counts_exact_and_not_actual_reconstruction(self):
        result = audit_obs_rows(self.fixture["rows"])
        self.assertEqual(self.fixture["classification"], "SYNTHETIC_ONLY")
        self.assertEqual(self.fixture["purpose"], "NOT_2026_11_05_OBS_RECONSTRUCTION")
        self.assertEqual(result["input_rows"], 20)
        self.assertEqual(result["payload_uuid_missing_rows"], 12)
        self.assertEqual(result["source_evidence_counts"], {"MISSING_FIELD": 1, "EMPTY_ARRAY": 3, "DECLARED_NORMAL": 16})
        self.assertEqual(result["hash_counts"], {"raw_matches": 20, "pre_post_equal": 20, "local_canonical_matches": 20})
        self.assertEqual(result["idempotency_counts"], {"evaluated_A_rows": 20, "matching_A_rows": 20,
                                                       "unique_A_provided_keys": 20, "duplicate_key_groups": 0})
        self.assertEqual(result["status_counts"], {"CONTRACT_UNVERIFIED": 12, "OBSERVED": 8})

    def test_missing_payload_uuid_and_column_only_never_formal_violation(self):
        result = audit_obs_rows([self.fixture["rows"][0]])
        self.assertEqual(result["rows"][0]["field_comparisons"]["event_uuid"], "MISSING_PAYLOAD")
        self.assertEqual(result["rows"][0]["status"], "CONTRACT_UNVERIFIED")
        self.assertEqual(result["unverified_questions"]["payload_uuid_mandatory"], "UNVERIFIED")
        self.assertEqual(result["unverified_questions"]["column_uuid_only_eligibility"], "UNVERIFIED")
        self.assertEqual(result["lock_eligibility"], "NOT_ASSESSED_UNCHANGED")

    def test_null_uuid_and_missing_uuid_are_not_collapsed(self):
        payload = json.loads(self.row["payload_raw"])
        payload["event_uuid"] = None
        replace_payload(self.row, payload)
        result = audit_obs_rows([self.row])
        self.assertEqual(result["payload_uuid_missing_rows"], 0)
        self.assertEqual(result["rows"][0]["field_comparisons"]["event_uuid"], "NULL_PAYLOAD")
        self.assertEqual(result["rows"][0]["status"], "CONTRACT_UNVERIFIED")

    def test_provided_uuid_mismatch_is_observed_inconsistency_without_value_echo(self):
        payload = json.loads(self.row["payload_raw"])
        payload["event_uuid"] = "SYNTHETIC_DIFFERENT_UUID_DO_NOT_ECHO"
        replace_payload(self.row, payload)
        result = audit_obs_rows([self.row])
        self.assertEqual(result["rows"][0]["status"], "INCONSISTENCY")
        self.assertIn("EVENT_UUID_PROVIDED_VALUES_DIFFER", result["rows"][0]["reasons"])
        self.assertNotIn(payload["event_uuid"], json.dumps(result))

    def test_source_evidence_states_all_separate_without_uniform_empty_failure(self):
        missing = object()
        values = [(missing, "MISSING_FIELD"), (None, "NULL"), ([], "EMPTY_ARRAY"),
                  ([{"status": "MISSING"}], "EXPLICIT_MISSING"),
                  ([{"status": "EXPLICIT_MISSING"}], "EXPLICIT_MISSING"),
                  ([{"status": "FETCH_FAILED"}], "FETCH_FAILED"),
                  ([{"status": "DECLARED_NORMAL"}], "DECLARED_NORMAL"),
                  ([{"status": "DECLARED_NORMAL"}, {"status": "FETCH_FAILED"}], "MIXED"),
                  ([{"status": {"unrecognized": True}}], "MALFORMED")]
        for value, expected in values:
            row = deepcopy(self.row)
            payload = json.loads(row["payload_raw"])
            if value is missing:
                payload.pop("source_evidence")
            else:
                payload["source_evidence"] = value
            replace_payload(row, payload)
            result = audit_obs_rows([row])
            self.assertEqual(result["rows"][0]["source_evidence"], expected)
            self.assertNotEqual(result["rows"][0]["status"], "INCONSISTENCY")
            self.assertEqual(result["source_claim_authenticity"], "UNVERIFIED")
        start = audit_obs_rows([self.fixture["rows"][2]])
        self.assertEqual(start["rows"][0]["event_kind"], "RUN_START")
        self.assertEqual(start["rows"][0]["source_evidence"], "EMPTY_ARRAY")
        self.assertEqual(start["unverified_questions"]["run_start_empty_source_evidence_allowed"], "UNVERIFIED")

    def test_confirmed_start_end_idempotency_known_vectors_not_merged(self):
        self.assertEqual(confirmed_a_idempotency("fixture-run", "RUN_START"),
                         "d2ea0c718dd5bcc6a8fcad23f09eb33fd30ac685f837b5af2cfd1944ad1dedf5")
        self.assertEqual(confirmed_a_idempotency("fixture-run", "RUN_END"),
                         "c62129eff6dc02588b4d2382860596e574560d26a7dc297938e740e0e683cb23")
        result = audit_obs_rows(self.fixture["rows"][:2])
        self.assertEqual(result["idempotency_counts"]["unique_A_provided_keys"], 2)

    def test_wrong_confirmed_key_and_conflicting_producer_not_chosen_arbitrarily(self):
        payload = json.loads(self.row["payload_raw"])
        payload["idempotency_key"] = "0" * 64
        self.row["columns"]["idempotency_key"] = "0" * 64
        replace_payload(self.row, payload)
        result = audit_obs_rows([self.row])["rows"][0]
        self.assertEqual(result["status"], "INCONSISTENCY")
        self.assertFalse(result["a_idempotency"]["all_provided_keys_match"])
        payload["producer_run_id"] = "SYNTHETIC_OTHER_PRODUCER"
        replace_payload(self.row, payload)
        result = audit_obs_rows([self.row])["rows"][0]
        self.assertEqual(result["status"], "INCONSISTENCY")
        self.assertFalse(result["a_idempotency"]["evaluated"])

    def test_source_mismatch_is_not_processed_under_a_or_b_contract(self):
        payload = json.loads(self.row["payload_raw"])
        payload["source"] = "B"
        replace_payload(self.row, payload)
        result = audit_obs_rows([self.row])["rows"][0]
        self.assertEqual(result["status"], "INCONSISTENCY")
        self.assertEqual(result["scope"], "SOURCE_OR_OPERATION_UNRESOLVED")
        self.assertFalse(result["a_idempotency"]["evaluated"])

    def test_b_and_lock_metadata_excluded_without_a_formula_or_eligibility(self):
        b = {"columns": {"source": "B"}, "payload_raw": "NOT_PARSED_BY_A_CHECKER"}
        lock = {"columns": {"source": "A", "event_kind": "LOCK"}, "payload_raw": "NOT_PARSED_BY_OBS_CHECKER"}
        result = audit_obs_rows([b, lock])
        self.assertEqual(result["status_counts"], {"OUT_OF_SCOPE": 2})
        self.assertEqual(result["A_operational_rows"], 0)
        self.assertEqual(result["idempotency_counts"]["evaluated_A_rows"], 0)

    def test_raw_hash_and_pre_post_differences_are_not_hidden(self):
        raw_changed = deepcopy(self.row)
        raw_changed["hashes"]["raw_sha256"] = "0" * 64
        result = audit_obs_rows([raw_changed])["rows"][0]
        self.assertEqual(result["status"], "INCONSISTENCY")
        self.assertFalse(result["hashes"]["raw_match"])
        self.row["hashes"]["canonical_before_sha256"] = "0" * 64
        result = audit_obs_rows([self.row])["rows"][0]
        self.assertEqual(result["status"], "INCONSISTENCY")
        self.assertFalse(result["hashes"]["pre_post_equal"])

    def test_consistent_other_canonical_profile_stays_unverified_not_a_violation(self):
        self.row["hashes"].update(canonical_before_sha256="0" * 64, canonical_after_sha256="0" * 64)
        report = audit_obs_rows([self.row])
        self.assertEqual(report["rows"][0]["status"], "CONTRACT_UNVERIFIED")
        self.assertTrue(report["rows"][0]["hashes"]["pre_post_equal"])
        self.assertFalse(report["rows"][0]["hashes"]["local_canonical_match"])
        self.assertEqual(report["actual_A_canonicalization"], "UNVERIFIED")

    def test_duplicate_key_same_and_different_raw_are_observations_not_repairs(self):
        repeated = audit_obs_rows([self.row, deepcopy(self.row)])
        self.assertEqual(repeated["idempotency_counts"]["duplicate_key_groups"], 1)
        self.assertEqual(repeated["status_counts"], {"OBSERVED": 2})
        changed = deepcopy(self.row)
        payload = json.loads(changed["payload_raw"])
        payload["errors"] = ["SYNTHETIC_ERROR_DO_NOT_ECHO"]
        replace_payload(changed, payload)
        report = audit_obs_rows([self.row, changed])
        self.assertEqual(report["status_counts"], {"INCONSISTENCY": 2})
        self.assertNotIn(payload["errors"][0], json.dumps(report))
        self.assertEqual(report["rows"][1]["error_count"], 1)

    def test_unreadable_payload_and_related_40hex_reference_never_relabelled(self):
        self.row["payload_raw"] = '{"event_uuid":"SYNTHETIC_SECRET","event_uuid":2}'
        result = audit_obs_rows([self.row])
        self.assertEqual(result["rows"][0]["status"], "INCONSISTENCY")
        self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))
        reference = result["related_A_reference"]
        self.assertEqual(reference["received_hash_verbatim"], "d462767f4448e28fc735df7363fb1a75137c5e7f")
        self.assertEqual(reference["observed_hex_characters"], 40)
        self.assertFalse(reference["sha256_length_matches"])
        self.assertEqual(reference["algorithm"], "UNVERIFIED")
        self.assertFalse(reference["is_independently_matched_OBS_contract"])

    def test_pure_no_io_no_mutation_and_no_raw_identifiers_or_error_echo(self):
        before = deepcopy(self.fixture)
        with patch("builtins.open", side_effect=AssertionError("NO_IO")), patch.object(Path, "read_bytes", side_effect=AssertionError("NO_IO")), patch.object(Path, "write_bytes", side_effect=AssertionError("NO_IO")):
            result = audit_obs_rows(self.fixture["rows"])
        self.assertEqual(self.fixture, before)
        output = json.dumps(result, allow_nan=False)
        self.assertNotIn("SYNTHETIC_A_RUN_", output)
        self.assertNotIn("SYNTHETIC_OBS_COLUMN_", output)
        self.assertNotIn("payload_raw", output)
        self.assertFalse(result["production_go"])
        self.assertEqual(set(result["unverified_questions"].values()), {"UNVERIFIED"})


if __name__ == "__main__":
    unittest.main()
