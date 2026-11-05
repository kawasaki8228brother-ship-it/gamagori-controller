"""Synthetic byte-binding, chronology, source isolation, and ledger vectors."""
import base64
from copy import deepcopy
import hashlib
import json
import unittest

from model11.engine import canonical_hash
from model11.preparation.legacy import (
    compare_frozen, make_synthetic_legacy_fixture, validate_frozen_predictions,
)


def decode(frame):
    return json.loads(base64.b64decode(frame["raw_bytes_b64"]))


def encode(frame, prediction):
    raw = json.dumps(prediction, sort_keys=True, separators=(",", ":")).encode("utf-8")
    frame.update(raw_bytes_b64=base64.b64encode(raw).decode("ascii"),
                 raw_byte_count=len(raw), raw_sha256=hashlib.sha256(raw).hexdigest())
    if "predeadline_evidence" in frame:
        for key in ("source", "race_id", "target_date", "deadline", "generated_at"):
            frame["predeadline_evidence"][key] = prediction[key]
        frame["predeadline_evidence"]["raw_sha256"] = frame["raw_sha256"]


def rehash_research(record):
    forecast = deepcopy(record)
    forecast.pop("actual", None)
    forecast.pop("prediction_sha256", None)
    forecast["first_course"] = None
    record["prediction_sha256"] = canonical_hash(forecast)


class FrozenEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = make_synthetic_legacy_fixture(synthetic_only=True)
        self.envelopes = self.fixture["envelopes"]
        self.profiles = self.fixture["profiles"]
        self.records = self.fixture["research_records"]

    def validate(self):
        return validate_frozen_predictions(self.envelopes, self.profiles)

    def test_dummy_fixture_is_locally_matched_never_authenticity_pass(self):
        result = self.validate()
        self.assertEqual(result["local_matched_n"], 6)
        self.assertEqual(result["status"], "LOCAL_MATCHED")
        self.assertEqual(result["external_authenticity"], "UNVERIFIED")
        self.assertFalse(result["production_go"])
        self.assertEqual(self.fixture["classification"], "SYNTHETIC_ONLY")
        encoded = json.dumps(result, allow_nan=False)
        self.assertNotIn("tickets", encoded)
        self.assertNotIn("raw_bytes_b64", encoded)

    def test_opaque_raw_byte_count_and_digest_checked(self):
        self.envelopes[0]["raw_byte_count"] += 1
        result = self.validate()
        self.assertEqual(result["rows"][0]["reason"], "PREDICTION_BYTE_COUNT_MISMATCH")
        self.assertEqual(result["local_matched_n"], 5)

    def test_wrong_digest_rejected(self):
        self.envelopes[0]["raw_sha256"] = "0" * 64
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDICTION_HASH_MISMATCH")

    def test_parsed_sidecar_cannot_replace_hashed_prediction_content(self):
        self.envelopes[0]["parsed_prediction"] = decode(self.envelopes[0])
        self.envelopes[0]["parsed_prediction"]["methods"]["normal5"]["tickets"][0] = "6-5-4"
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDICTION_PARSED_CONTENT_MISMATCH")

    def test_raw_changed_and_rehashed_requires_receipt_binding(self):
        prediction = decode(self.envelopes[0])
        prediction["methods"]["mechanical_box"]["boats"] = [1, 2, 4]
        prediction["methods"]["mechanical_box"]["tickets"] = ["1-2-4", "1-4-2", "2-1-4", "2-4-1", "4-1-2", "4-2-1"]
        old_receipt = deepcopy(self.envelopes[0]["predeadline_evidence"])
        encode(self.envelopes[0], prediction)
        self.envelopes[0]["predeadline_evidence"] = old_receipt
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDEADLINE_HASH_BINDING")

    def test_self_rehash_and_metadata_rewrite_never_prove_authenticity(self):
        prediction = decode(self.envelopes[0])
        prediction["methods"]["normal5"]["tickets"] = list(reversed(prediction["methods"]["normal5"]["tickets"]))
        encode(self.envelopes[0], prediction)
        result = self.validate()
        self.assertEqual(result["status"], "LOCAL_MATCHED")
        self.assertEqual(result["external_authenticity"], "UNVERIFIED")

    def test_source_profile_cannot_be_swapped(self):
        self.profiles["A"] = deepcopy(self.profiles["B"])
        self.assertEqual(self.validate()["rows"][0]["reason"], "PROFILE_SOURCE_MISMATCH")

    def test_raw_source_must_match_envelope_source(self):
        self.envelopes[0]["source"] = "B"
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDICTION_SOURCE_MISMATCH")

    def test_missing_source_profiles_are_open(self):
        del self.profiles["A"]
        result = self.validate()
        self.assertEqual(result["rows"][0]["status"], "OPEN")
        comparison = compare_frozen(self.records, self.envelopes, self.profiles)
        self.assertEqual(comparison["comparisons"]["research_vs_A"]["status"], "OPEN")
        self.assertEqual(comparison["comparisons"]["research_vs_B"]["status"], "LOCAL_MATCHED_COMPARISON")

    def test_version_label_cannot_silently_change(self):
        prediction = decode(self.envelopes[0])
        prediction["model_version"] = "1.1"
        encode(self.envelopes[0], prediction)
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDICTION_PROFILE_BINDING")

    def test_missing_and_late_receipt_never_treated_as_predeadline(self):
        del self.envelopes[0]["predeadline_evidence"]
        self.assertEqual(self.validate()["rows"][0]["status"], "OPEN")
        self.envelopes[1]["predeadline_evidence"]["recorded_at"] = "2099-01-17T13:02:00+09:00"
        self.assertEqual(self.validate()["rows"][1]["reason"], "PREDEADLINE_RECEIPT_TIME")

    def test_actual_generation_at_deadline_is_hold(self):
        prediction = decode(self.envelopes[0])
        prediction["generated_at"] = prediction["deadline"]
        encode(self.envelopes[0], prediction)
        self.assertEqual(self.validate()["rows"][0]["reason"], "PREDICTION_NOT_PREDEADLINE")

    def test_naive_and_unknown_offset_and_precision_not_accepted(self):
        for value in ("2099-01-17T12:01:00", "2099-01-17T12:01:00-00:00", "2099-01-17T12:01:00.1234567+09:00"):
            envelopes = deepcopy(self.envelopes)
            envelopes[0]["predeadline_evidence"]["recorded_at"] = value
            result = validate_frozen_predictions(envelopes, self.profiles)
            self.assertEqual(result["rows"][0]["status"], "HOLD")

    def test_duplicate_freezes_all_copies_instead_of_selecting_first(self):
        self.envelopes.append(deepcopy(self.envelopes[0]))
        result = self.validate()
        self.assertEqual(result["local_matched_n"], 5)
        self.assertEqual(result["rows"][0]["reason"], "DUPLICATE_SOURCE_RACE_DATE")
        self.assertEqual(result["rows"][-1]["reason"], "DUPLICATE_SOURCE_RACE_DATE")

    def test_metadata_is_validation_not_selection_logic(self):
        prediction = decode(self.envelopes[0])
        prediction["methods"]["human_box"]["normal5_frequencies"]["1"] = 0
        encode(self.envelopes[0], prediction)
        self.assertEqual(self.validate()["rows"][0]["reason"], "HUMAN_FREQUENCY_MISMATCH")

    def test_duplicate_ticket_or_wrong_box_domain_rejected(self):
        prediction = decode(self.envelopes[0])
        prediction["methods"]["normal5"]["tickets"][1] = prediction["methods"]["normal5"]["tickets"][0]
        encode(self.envelopes[0], prediction)
        self.assertEqual(self.validate()["rows"][0]["reason"], "METHOD_DUPLICATE_TICKET")

    def test_bad_raw_json_and_secret_text_never_echoed(self):
        secret = b'{"source":"A","source":"token-do-not-echo"}'
        frame = self.envelopes[0]
        frame.update(raw_bytes_b64=base64.b64encode(secret).decode("ascii"), raw_byte_count=len(secret),
                     raw_sha256=hashlib.sha256(secret).hexdigest())
        result = self.validate()
        self.assertEqual(result["rows"][0]["status"], "HOLD")
        self.assertNotIn("token-do-not-echo", json.dumps(result))


class FrozenComparisonTests(unittest.TestCase):
    def setUp(self):
        self.fixture = make_synthetic_legacy_fixture(synthetic_only=True)
        self.envelopes, self.profiles, self.records = (self.fixture[k] for k in ("envelopes", "profiles", "research_records"))

    def compare(self):
        return compare_frozen(self.records, self.envelopes, self.profiles)

    def test_sources_are_separate_and_normal_box_stakes_independent(self):
        result = self.compare()
        first = result["comparisons"]["research_vs_A"]["methods"]
        second = result["comparisons"]["research_vs_B"]["methods"]
        self.assertEqual(first["normal5"]["research"]["stake_yen"], 1500)
        self.assertEqual(first["human_box"]["research"]["stake_yen"], 1800)
        self.assertEqual(first["mechanical_box"]["research"]["stake_yen"], 1800)
        self.assertEqual(first["normal5"]["frozen"]["hit_n"], 3)
        self.assertEqual(second["normal5"]["frozen"]["hit_n"], 0)
        self.assertEqual(first["normal5"]["frozen"]["net_yen"], 1500)
        self.assertEqual(second["normal5"]["frozen"]["net_yen"], -1500)
        self.assertEqual(first["normal5"]["frozen"]["roi"], 1)
        self.assertEqual(second["normal5"]["frozen"]["roi"], -1)
        self.assertEqual(result["pooled_AB_result"], "NOT_COMPUTED")
        self.assertEqual(second["normal5"]["superiority"], "UNVERIFIED")

    def test_missing_one_source_race_is_open_with_visible_coverage(self):
        self.envelopes.pop(0)
        result = self.compare()["comparisons"]
        normal = result["research_vs_A"]["methods"]["normal5"]
        self.assertEqual(normal["status"], "OPEN")
        self.assertEqual(normal["paired_n"], 2)
        self.assertEqual(normal["missing_or_invalid_n"], 1)
        self.assertEqual(result["research_vs_B"]["methods"]["normal5"]["paired_n"], 3)

    def test_raw_research_hash_detects_changed_selection(self):
        self.records[0]["selection"]["tickets"][0] = "6-5-4"
        result = self.compare()["comparisons"]["research_vs_A"]
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["methods"]["normal5"]["paired_n"], 2)

    def test_deadline_mismatch_hold_even_both_independently_predeadline(self):
        self.records[0]["deadline"] = "2099-01-17T13:05:00+09:00"
        rehash_research(self.records[0])
        result = self.compare()["comparisons"]["research_vs_A"]
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["race_bindings"][0]["reason"], "DEADLINE_MISMATCH")

    def test_outcome_identity_not_silently_joined_by_order(self):
        self.records[0]["actual"]["race_id"] = self.records[1]["race_id"]
        result = self.compare()["comparisons"]["research_vs_A"]
        self.assertEqual(result["race_bindings"][0]["reason"], "OUTCOME_RACE_DATE_BINDING")

    def test_missing_naive_or_predeadline_outcome_availability_is_hold(self):
        for available in (None, "2099-01-17T14:00:00", "2099-01-17T00:00:00+09:00"):
            records = deepcopy(self.records)
            if available is None:
                del records[0]["actual"]["available_at"]
            else:
                records[0]["actual"]["available_at"] = available
            result = compare_frozen(records, self.envelopes, self.profiles)
            for source in ("A", "B"):
                comparison = result["comparisons"]["research_vs_" + source]
                self.assertEqual(comparison["status"], "HOLD")
                self.assertEqual(comparison["methods"]["normal5"]["paired_n"], 2)

    def test_outcome_availability_at_deadline_is_accepted_boundary(self):
        self.records[0]["actual"]["available_at"] = self.records[0]["deadline"]
        self.assertEqual(self.compare()["comparisons"]["research_vs_A"]["status"], "LOCAL_MATCHED_COMPARISON")

    def test_partial_method_missing_stays_open_only_that_method(self):
        prediction = decode(self.envelopes[0])
        del prediction["methods"]["mechanical_box"]
        encode(self.envelopes[0], prediction)
        result = self.compare()["comparisons"]["research_vs_A"]["methods"]
        self.assertEqual(result["normal5"]["paired_n"], 3)
        self.assertEqual(result["mechanical_box"]["paired_n"], 2)
        self.assertEqual(result["mechanical_box"]["status"], "OPEN")

    def test_refund_counted_per_ticket_and_not_a_hit(self):
        for record in self.records:
            record["actual"]["result"] = [6, 4, 2]
            record["actual"]["refund_tickets"] = ["1-2-3"]
        result = self.compare()["comparisons"]["research_vs_A"]["methods"]
        self.assertEqual(result["normal5"]["research"]["hit_n"], 0)
        self.assertEqual(result["normal5"]["research"]["refund_yen"], 300)
        self.assertEqual(result["normal5"]["research"]["net_yen"], -1200)
        self.assertEqual(result["human_box"]["research"]["net_yen"], -1500)

    def test_missing_refund_or_winning_payout_never_filled(self):
        del self.records[0]["actual"]["refund_tickets"]
        del self.records[1]["actual"]["payout_per_100"]
        result = self.compare()["comparisons"]["research_vs_A"]["methods"]["normal5"]
        self.assertEqual(result["status"], "UNVERIFIED_MONEY")
        self.assertEqual(result["research"]["money_unknown_n"], 2)
        self.assertEqual(result["paired_money_n"], 1)
        self.assertEqual(result["research"]["hit_n"], 3)

    def test_refunded_winner_is_hold(self):
        self.records[0]["actual"]["refund_tickets"] = ["1-2-3"]
        result = self.compare()["comparisons"]["research_vs_A"]["methods"]["normal5"]
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["issues"][0]["reason"], "OUTCOME_WINNER_REFUNDED")

    def test_duplicate_research_records_all_excluded(self):
        self.records.append(deepcopy(self.records[0]))
        result = self.compare()["comparisons"]["research_vs_A"]["methods"]["normal5"]
        self.assertEqual(result["paired_n"], 2)
        self.assertEqual(result["missing_or_invalid_n"], 2)

    def test_inputs_are_not_mutated_and_output_json_safe(self):
        before = deepcopy(self.fixture)
        result = self.compare()
        self.assertEqual(self.fixture, before)
        json.dumps(result, allow_nan=False)
        self.assertFalse(result["production_go"])

    def test_fixture_requires_explicit_synthetic_flag_and_2099_scope(self):
        with self.assertRaises(ValueError):
            make_synthetic_legacy_fixture()
        self.records[0]["target_date"] = "2026-11-05"
        with self.assertRaises(ValueError):
            make_synthetic_legacy_fixture(self.records, synthetic_only=True)

    def test_dummy_tickets_not_cloned_from_research(self):
        old_a = decode(self.envelopes[0])["methods"]["normal5"]["tickets"]
        self.records[0]["selection"]["tickets"] = ["2-3-4", "2-4-3", "3-2-4", "3-4-2", "4-2-3"]
        rehash_research(self.records[0])
        fresh = make_synthetic_legacy_fixture(self.records, synthetic_only=True)
        self.assertEqual(decode(fresh["envelopes"][0])["methods"]["normal5"]["tickets"], old_a)
        self.assertEqual(self.records[0]["source"], "MODEL11_RESEARCH")


if __name__ == "__main__":
    unittest.main()
