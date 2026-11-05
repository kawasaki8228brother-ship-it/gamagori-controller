"""Static document mutations only; never invokes prediction or evaluation code."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


DIRECTORY = Path(__file__).resolve().parents[1]
SENTINEL = "SYNTHETIC_PRIVATE_DOCUMENT_VALUE_NEVER_ECHO"


def fixture():
    return {"classification": "SYNTHETIC_ONLY", "partitions": {
        "training": {"day_ids": ["2099-01-01"], "race_ids": ["SYNTHETIC_R1"]},
        "selection": {"day_ids": ["2099-01-02"], "race_ids": ["SYNTHETIC_R2"]},
        "pilot": {"day_ids": ["2099-01-03"], "race_ids": ["SYNTHETIC_R3"]},
        "holdout": {"day_ids": ["2099-01-04"], "race_ids": ["SYNTHETIC_R4"]},
    }}


class DocumentConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load(name):
            return json.loads((DIRECTORY / name).read_bytes())
        cls.ledger = load("DECISION_LEDGER.json")
        cls.source = load("SOURCE_RECEIPT_REFERENCE.json")
        cls.registry = load("DATA_PARTITIONS.OPEN.json")
        spec = importlib.util.spec_from_file_location("f5_static_audit_test", DIRECTORY / "static_audit.py")
        cls.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.api)

    def audit(self, ledger=None, source=None, registry=None):
        return self.api.audit_records(deepcopy(self.ledger) if ledger is None else ledger,
            deepcopy(self.source) if source is None else source,
            deepcopy(self.registry) if registry is None else registry)

    def assert_hold(self, result):
        self.assertEqual(result["status"], "HOLD")
        self.assertTrue(result["issues"])
        self.assertFalse(result["production_go"])
        self.assertTrue(all(isinstance(code, str) for code in result["issues"]))
        self.assertNotIn(SENTINEL, json.dumps(result))

    def test_current_three_records_are_consistent_without_granting_execution(self):
        report = self.audit()
        self.assertEqual(report["status"], "DOCUMENT_CONSISTENT")
        self.assertEqual(report["issues"], [])
        self.assertFalse(report["production_go"])
        self.assertEqual(self.ledger["M0"]["status"], "DECIDED")
        self.assertEqual(self.ledger["M2"]["status"], "DECIDED")
        self.assertIsNone(self.ledger["source"]["original_sha256"])
        self.assertIsNone(self.ledger["source"]["approval_receipt"])
        self.assertEqual(len(self.ledger["open_items"]), 8)
        self.assertTrue(all(row["status"] == "OPEN" and row["value"] is None for row in self.ledger["open_items"]))
        self.assertTrue(all(value is False for value in self.ledger["operational_permissions"].values()))

    def test_m0_alpha_power_family_endpoint_day_weight_and_one_sidedness_are_frozen(self):
        variants = {"significance_alpha": .05, "power_target": .9, "confirmatory_family_size": 6,
            "six_market_weights_are_six_confirmatory_tests": True,
            "test_sidedness": "TWO_SIDED", "candidate": "SIX_WEIGHT_CHAMPIONS",
            "endpoint": "HIT_RATE", "weighting": "RACE_WEIGHTED",
            "market_snapshot_requirement": "FINAL_ODDS",
            "optional_stopping_allowed": True, "posthoc_changes_allowed": True,
            "statistical_pass_implemented_or_granted": True}
        for field, value in variants.items():
            ledger = deepcopy(self.ledger)
            ledger["M0"][field] = value
            with self.subTest(field=field):
                self.assert_hold(self.audit(ledger=ledger))

    def test_market_only_w1_cannot_be_recorded_as_a_model_victory(self):
        ledger = deepcopy(self.ledger)
        ledger["M0"]["market_only_w1_interpretation"] = "MODEL_SUPERIORITY"
        self.assert_hold(self.audit(ledger=ledger))

    def test_future_a_only_design_does_not_expand_search_or_apply_configuration(self):
        variants = {"model": "contextual", "course_alpha": .7, "temperature": .8,
            "market_weights": [0, .25, .5], "confirmatory_option": "A_B_C",
            "B_role": "CONFIRMATORY", "C_role": "CONFIRMATORY",
            "selection_action": "CHOOSE_w_AFTER_HOLDOUT_RESULTS",
            "existing_model_or_grid_changed": True, "executable_application_authorized": True}
        for field, value in variants.items():
            ledger = deepcopy(self.ledger)
            ledger["M1"][field] = value
            with self.subTest(field=field):
                self.assert_hold(self.audit(ledger=ledger))

    def test_open_choices_examples_and_f2_cannot_be_promoted_to_adopted_values(self):
        for identity, value in (("MIN_SELECTION_DAYS", 24), ("HOLDOUT_START_AND_DAYS", 60), ("SESOI", .01)):
            ledger = deepcopy(self.ledger)
            row = next(item for item in ledger["open_items"] if item["id"] == identity)
            row.update(status="DECIDED", value=value)
            with self.subTest(identity=identity):
                self.assert_hold(self.audit(ledger=ledger))
        for mutate in (lambda value: value["prior_examples"][0].update(status="ADOPTED"),
                       lambda value: value["open_items"].pop(),
                       lambda value: value["F2"].update(new_thresholds_adopted=True)):
            ledger = deepcopy(self.ledger)
            mutate(ledger)
            self.assert_hold(self.audit(ledger=ledger))

    def test_policy_decision_never_implies_any_operational_go(self):
        for field in self.ledger["operational_permissions"]:
            ledger = deepcopy(self.ledger)
            ledger["operational_permissions"][field] = True
            with self.subTest(permission=field):
                self.assert_hold(self.audit(ledger=ledger))
        source = deepcopy(self.source)
        source["operational_go"]["shadow_start"] = True
        self.assert_hold(self.audit(source=source))
        for field, value in (("pilot_is_holdout", True), ("improvement_claim_allowed", True),
                             ("profit_claim_allowed", True), ("promotion_claim_allowed", True),
                             ("scheduled_or_execution_authorized", True), ("separate_execution_go_required", False)):
            ledger = deepcopy(self.ledger)
            ledger["M2"][field] = value
            with self.subTest(pilot_policy=field):
                self.assert_hold(self.audit(ledger=ledger))
        for field in ("enabled", "executable", "application_go", "production_go"):
            registry = deepcopy(self.registry)
            registry[field] = True
            with self.subTest(partition_permission=field):
                self.assert_hold(self.audit(registry=registry))

    def test_source_original_sha_receipts_and_independent_match_are_not_fabricated(self):
        ledger, source = deepcopy(self.ledger), deepcopy(self.source)
        ledger["source"]["original_sha256"] = "a" * 64
        source["source_references"]["raw_original"]["sha256"] = "a" * 64
        self.assert_hold(self.audit(ledger=ledger, source=source))
        for name in ("raw_original", "andy_decision_receipt", "forward_receipt"):
            source = deepcopy(self.source)
            source["source_references"][name]["sha256"] = "b" * 64
            with self.subTest(source=name):
                self.assert_hold(self.audit(source=source))
        for authority in ("HQ14", "CLAUDE"):
            source = deepcopy(self.source)
            source["independent_source_match"][authority]["status"] = "VERIFIED"
            with self.subTest(authority=authority):
                self.assert_hold(self.audit(source=source))
        ledger = deepcopy(self.ledger)
        ledger["freeze_and_gates"]["G1_G6"]["definitions"] = {"G1": SENTINEL}
        self.assert_hold(self.audit(ledger=ledger))

    def test_actual_dates_or_unknown_registry_roles_do_not_close_the_open_design(self):
        for field in ("pilot_start", "holdout_start", "registry_sealed_at"):
            registry = deepcopy(self.registry)
            registry[field] = "2099-01-04"
            with self.subTest(field=field):
                self.assert_hold(self.audit(registry=registry))
        registry = deepcopy(self.registry)
        registry["partitions"]["unknown_role"] = deepcopy(registry["partitions"]["pilot"])
        self.assert_hold(self.audit(registry=registry))
        for field, value in (("additional_pilot_span", "AUTO_EXTEND_UNTIL_K_GE_2"),
                             ("pilot_development_reuse", "ALLOWED"),
                             ("pilot_sd_day_status", "VERIFIED"), ("pilot_sd_day", 0.0)):
            registry = deepcopy(self.registry)
            registry[field] = value
            with self.subTest(pilot_registry=field):
                self.assert_hold(self.audit(registry=registry))
        registry = deepcopy(self.registry)
        registry["partitions"]["holdout"]["status"] = "SEALED"
        self.assert_hold(self.audit(registry=registry))
        ledger = deepcopy(self.ledger)
        ledger["M2"]["candidate_window"]["status"] = "SCHEDULED"
        ledger["M2"]["first_operating_day"] = "2026-11-21"
        self.assert_hold(self.audit(ledger=ledger))

    def test_synthetic_disjoint_partition_fixture_is_consistent_but_not_adoption(self):
        value = fixture()
        original = deepcopy(value)
        report = self.api.audit_partition_fixture(value)
        self.assertEqual(report["status"], "FIXTURE_CONSISTENT")
        self.assertEqual(report["issues"], [])
        self.assertFalse(report["production_go"])
        self.assertEqual(value, original)
        self.assertFalse(self.registry["actual_data_present"])
        self.assertFalse(self.registry["F2_adopted"])

    def test_pilot_holdout_overlap_by_day_or_race_is_rejected(self):
        for field in ("day_ids", "race_ids"):
            value = fixture()
            value["partitions"]["holdout"][field] = deepcopy(value["partitions"]["pilot"][field])
            with self.subTest(field=field):
                self.assert_hold(self.api.audit_partition_fixture(value))

    def test_date_inversion_unknown_roles_and_unresolved_pilot_development_reuse_hold(self):
        for mutate in (
            lambda value: value["partitions"]["training"].update(day_ids=["2099-01-02"]),
            lambda value: value["partitions"]["selection"].update(day_ids=["2099-01-05"]),
            lambda value: value["partitions"].update(unknown_role={"day_ids": ["2099-01-05"], "race_ids": ["SYNTHETIC_R5"]}),
            lambda value: value["partitions"]["pilot"].update(day_ids=["2099-01-01"]),
            lambda value: value["partitions"]["selection"].update(race_ids=["SYNTHETIC_R1"]),
        ):
            value = fixture()
            mutate(value)
            self.assert_hold(self.api.audit_partition_fixture(value))

    def test_static_audits_are_pure_fixed_diagnostics_with_no_file_network_or_database_calls(self):
        ledger, source, registry = deepcopy(self.ledger), deepcopy(self.source), deepcopy(self.registry)
        before = deepcopy((ledger, source, registry))
        with patch("builtins.open", side_effect=AssertionError("NO_FILE_IO")), \
             patch("socket.socket", side_effect=AssertionError("NO_NETWORK")), \
             patch("sqlite3.connect", side_effect=AssertionError("NO_DATABASE")):
            self.assertEqual(self.api.audit_records(ledger, source, registry)["status"], "DOCUMENT_CONSISTENT")
            self.assertEqual(self.api.audit_partition_fixture(fixture())["status"], "FIXTURE_CONSISTENT")
        self.assertEqual((ledger, source, registry), before)
        ledger["M0"]["endpoint"] = SENTINEL
        self.assert_hold(self.audit(ledger=ledger))


if __name__ == "__main__":
    unittest.main()
