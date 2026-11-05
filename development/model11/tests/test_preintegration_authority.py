"""Synthetic-only preintegration tests; no engine, real data, service or GO."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from preintegration_v008.authority import (AuthorityHold, LEDGER_SHA256, OPEN_IDS, authority_report,
    load_authority, load_provenance_override, model_claim_status, project_authority)
from preintegration_v008.signs import (SignInputError, convert_paired_day_means, convert_pilot_statistics,
    m0_to_pilot, one_sided_normal_tail_diagnostic, pilot_to_m0)

MODEL_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = MODEL_ROOT / "preintegration_v008/references/F5_DECISION_LEDGER_1778d2e.json"
OLD = MODEL_ROOT / "offline_refinements_v007/results/TEST_RESULTS.json"
OLD_SHA = "255f559f186cbdd351f03a876855fcea2c83cb7023764fa96bbce7421b7edfb2"


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.raw = REFERENCE.read_bytes()

    def test_projection_uses_pinned_decisions_and_keeps_eight_open_values_null(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), LEDGER_SHA256)
        projection = project_authority(self.raw)
        self.assertEqual(projection["decision_order"], ["M0", "M2", "M1"])
        self.assertEqual(projection["M0"]["significance_alpha"], .025)
        self.assertEqual(projection["M0"]["power_target"], .8)
        self.assertEqual(projection["M0"]["confirmatory_family_size"], 1)
        self.assertEqual(projection["M0"]["weighting"], "PAIRED_DAY_EQUAL_WEIGHT")
        self.assertFalse(projection["M0"]["six_market_weights_are_six_confirmatory_tests"])
        self.assertEqual(projection["M1"]["market_weights"], [0,.25,.5,.75,.9,1.0])
        self.assertEqual(projection["M1"]["course_alpha"], .5)
        self.assertEqual(projection["M1"]["temperature"], 1.0)
        self.assertEqual(tuple(row["id"] for row in projection["open_items"]), OPEN_IDS)
        self.assertTrue(all(row["value"] is None and row["status"] == "OPEN" for row in projection["open_items"]))
        self.assertNotIn("prior_examples", projection)
        self.assertFalse(projection["execution_go"])
        self.assertFalse(projection["production_go"])
        self.assertIsNone(projection["policy_authority"]["original_decision_record_sha256"])
        self.assertIsNone(projection["policy_authority"]["approval_receipt"])
        self.assertEqual(load_authority(), projection)

    def test_changed_self_asserted_document_never_becomes_an_authority(self):
        original = json.loads(self.raw)
        attacks = []
        for field in ("SESOI", "MIN_SELECTION_DAYS"):
            changed = deepcopy(original)
            next(row for row in changed["open_items"] if row["id"] == field)["value"] = "UNAPPROVED_VALUE"
            attacks.append(json.dumps(changed).encode())
        changed = deepcopy(original)
        changed["source"]["original_sha256"] = "0" * 64
        changed["source"]["approval_receipt"] = {"self_asserted": True}
        attacks += [json.dumps(changed).encode(), self.raw + b" ", b"private secret must not echo"]
        for raw in attacks:
            with self.subTest(length=len(raw)):
                report = authority_report(raw)
                self.assertEqual(report["status"], "HOLD")
                self.assertFalse(report["production_go"])
                self.assertNotIn("secret", json.dumps(report))
        for value in (None, True, "not bytes", bytearray(self.raw)):
            self.assertEqual(authority_report(value)["status"], "HOLD")

    def test_projection_is_a_copy_and_no_arbitrary_configuration_is_accepted(self):
        projected = project_authority(self.raw)
        projected["M0"]["confirmatory_family_size"] = "UNAPPROVED_VALUE"
        projected["open_items"][0]["value"] = "UNAPPROVED_VALUE"
        again = project_authority(self.raw)
        self.assertEqual(again["M0"]["confirmatory_family_size"], 1)
        self.assertIsNone(again["open_items"][0]["value"])
        with patch.object(Path, "read_bytes", side_effect=AssertionError("UNEXPECTED_IO")):
            self.assertFalse(project_authority(self.raw)["production_go"])

    def test_provenance_routes_are_distinct_and_historical_A_is_not_rewritten(self):
        record = load_provenance_override()
        direct, transfer = record["provenance_routes"]
        self.assertEqual(direct["confirmation"], "CLAUDE_CONFIRMED_PER_FORWARDED_REPORT")
        self.assertEqual(direct["statement"], "先生のおすすめを採用で！")
        self.assertEqual(direct["Codex_observation"], "RECEIVED_FORWARD_ONLY_NOT_DIRECT_WITNESS")
        self.assertEqual(transfer["Claude_confirmation"], "UNVERIFIED")
        self.assertEqual(transfer["reported_time"], "2026-11-05T20:36:00+09:00")
        self.assertTrue(all(row["source_original_sha256"] is None and row["approval_receipt"] is None
                            for row in record["provenance_routes"]))
        self.assertTrue(all(row["value"] is None for row in record["open_items"]))
        self.assertFalse(record["new_numeric_candidates_created"])
        self.assertEqual(hashlib.sha256(OLD.read_bytes()).hexdigest(), OLD_SHA)
        self.assertEqual(json.loads(OLD.read_bytes())["M0_M2_M1_ORDER"], "RECOMMENDATION_ONLY_NOT_ADOPTED")
        self.assertFalse(record["production_go"])

    def test_market_only_and_all_other_weights_never_grant_superiority(self):
        for weight in [0,.25,.5,.75,.9,1.0]:
            report = model_claim_status(weight, ledger_raw=self.raw)
            self.assertFalse(report["model_superiority_allowed"])
            self.assertEqual(report["confirmatory_family_size"], 1)
            self.assertFalse(report["actual_test_performed"])
            if weight == 1.0: self.assertEqual(report["status"], "NO_MODEL_SUPERIORITY")
            else: self.assertIn("UNVERIFIED", report["status"])
        for bad in (True, False, None, -1, .1, math.nan, math.inf, "1.0"):
            with self.assertRaises(AuthorityHold):
                model_claim_status(bad, ledger_raw=self.raw)


class SignTests(unittest.TestCase):
    def test_roundtrip_and_favorable_direction(self):
        for value in (-10.,-1.,-.25,-0.,0.,.25,1.,10.):
            self.assertEqual(m0_to_pilot(pilot_to_m0(value)), value)
            self.assertEqual(pilot_to_m0(m0_to_pilot(value)), value)
        self.assertGreater(pilot_to_m0(-1), 0)
        self.assertLess(m0_to_pilot(1), 0)
        self.assertEqual(math.copysign(1,pilot_to_m0(0.)), -1)
        self.assertEqual(math.copysign(1,m0_to_pilot(pilot_to_m0(-0.))), -1)

    def test_day_mean_sign_changes_sd_does_not_and_input_remains_unchanged(self):
        values = [-2.,0.,4.]
        original = values[:]
        summary = convert_paired_day_means(values)
        self.assertEqual(values, original)
        self.assertAlmostEqual(summary["d_M0_mean_market_minus_model"], -summary["pilot_mean_model_minus_market"])
        self.assertEqual(summary["pilot_sd_day"], summary["d_M0_sd_day"])
        self.assertEqual(summary["pilot_sd_day"], math.sqrt(28/3))
        self.assertEqual(summary["sample_variance_denominator"], "K_MINUS_1")
        self.assertEqual(summary["unit"], "PAIRED_DAY_MEANS_EQUAL_WEIGHT")
        self.assertFalse(summary["actual_test_performed"])
        self.assertFalse(summary["production_go"])

    def test_missing_and_zero_dispersion_are_not_relabelled_as_adequacy(self):
        for values in ([],[1.]):
            report = convert_paired_day_means(values)
            self.assertIsNone(report["pilot_sd_day"])
            self.assertIn("UNVERIFIED", report["sd_status"])
        zero = convert_paired_day_means([1.,1.])
        self.assertEqual(zero["pilot_sd_day"], 0)
        self.assertEqual(zero["d_M0_sd_day"], 0)
        self.assertEqual(zero["sd_status"], "OBSERVED_ZERO_NOT_ZERO_FUTURE_VARIANCE")
        for bad in (None,"1",[True],[math.nan],[math.inf],["1"],[10**10000]):
            with self.assertRaises(SignInputError): convert_paired_day_means(bad)

    def test_one_sided_tail_identity_and_rejection_direction_not_an_actual_test(self):
        for value in (-8.,-3.,-1.,0.,1.,3.,8.):
            result = one_sided_normal_tail_diagnostic(value)
            self.assertEqual(result["pilot_tail"], "LOWER")
            self.assertEqual(result["M0_tail"], "UPPER")
            self.assertEqual(result["d_M0_z"], -value)
            self.assertEqual(result["pilot_lower_tail"], result["M0_upper_tail"])
            self.assertFalse(result["actual_test_performed"])
            self.assertIsNone(result["test_pass"])
            for cutoff in (.5,1.,2.):
                self.assertEqual(value < -cutoff, result["d_M0_z"] > cutoff)
        self.assertEqual(one_sided_normal_tail_diagnostic(0)["pilot_lower_tail"], .5)
        self.assertLess(one_sided_normal_tail_diagnostic(-1)["pilot_lower_tail"], .5)
        self.assertGreater(one_sided_normal_tail_diagnostic(1)["pilot_lower_tail"], .5)

    def test_supplied_summary_keeps_unknown_variance_and_rejects_contradictions(self):
        report = convert_pilot_statistics(-.25,.5,3)
        self.assertEqual(report["d_M0_mean"], .25)
        self.assertEqual(report["pilot_sd_day"], report["d_M0_sd_day"])
        self.assertFalse(report["actual_test_performed"])
        self.assertIsNone(convert_pilot_statistics(1,None,1)["d_M0_sd_day"])
        self.assertIsNone(convert_pilot_statistics(None,None,0)["d_M0_mean"])
        for args in ((1,0,1),(None,None,1),(1,None,2),(1,-1,2),(1,1,True),(0,None,0)):
            with self.assertRaises(SignInputError): convert_pilot_statistics(*args)

    def test_nonfinite_scalar_and_tail_values_fail_safe_without_echo(self):
        for value in (True,None,"DO_NOT_ECHO",math.nan,math.inf,-math.inf,10**10000):
            for function in (pilot_to_m0,m0_to_pilot,one_sided_normal_tail_diagnostic):
                with self.assertRaises(SignInputError) as caught: function(value)
                self.assertNotIn("DO_NOT_ECHO", str(caught.exception))


if __name__ == "__main__": unittest.main()
