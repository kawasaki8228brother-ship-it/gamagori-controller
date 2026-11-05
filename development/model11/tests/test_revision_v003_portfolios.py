"""Synthetic F4 regression: automatic names cannot stand in for human inputs."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import unittest

from model11.engine import canonical_hash, predict_race
from model11.models import make_model
from model11.selection import build_boxes
from model11.synthetic import make_dataset
from model11.revision_v003.portfolios import build_portfolios, validate_human_input
from model11.revision_v003.migration import migrate_v001_prediction
from model11.revision_v003.evaluation import evaluate_records_v003, METHODS_V003


def asserted_manual(race, boats=None):
    boats = boats or [1, 2, 3]
    prediction = datetime.fromisoformat(race["prediction_at"])
    return {"race_id": race["race_id"], "target_date": race["target_date"],
            "core": boats[:2], "insertion": boats[2], "origin": "HUMAN_MANUAL",
            "source_id": "SYNTHETIC_ASSERTION_NOT_ACTUAL_HUMAN",
            "observed_at": (prediction - timedelta(seconds=60)).isoformat(),
            "acquired_at": (prediction - timedelta(seconds=50)).isoformat(),
            "available_at": (prediction - timedelta(seconds=40)).isoformat(),
            "revision_at": (prediction - timedelta(seconds=30)).isoformat(),
            "evidence_recorded_at": (prediction - timedelta(seconds=20)).isoformat(),
            "evidence_sha256": canonical_hash({"synthetic": True, "race_id": race["race_id"], "boats": boats})}


class V003PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = make_dataset(4, 1, 20261105)
        cls.race = cls.dataset["races"][2]
        model = make_model("hierarchical", {"epochs": 2})
        model.fit(cls.dataset["races"][:2], cls.dataset["outcomes"][:2])
        cls.old = predict_race(cls.race, model)
        cls.dist = cls.old["distributions"]["P_shrunk"]
        cls.five = cls.old["selection"]
        cls.odds = cls.race["odds_snapshot"]["odds"]

    def build(self, manual=None, race=None):
        return build_portfolios(race or self.race, self.dist, self.five, self.odds, manual)

    def record(self, manual=None):
        record = deepcopy(self.old)
        record["boxes"] = self.build(manual)
        record["source"] = "MODEL11_RESEARCH_V003"
        record["schema"] = "MODEL11_FORECAST_V003"
        record["actual"] = deepcopy(self.dataset["outcomes"][2])
        record["first_course"] = next(boat["course"] for boat in self.race["boats"] if boat["boat"] == record["actual"]["result"][0])
        return record

    def test_automatic_always_present_and_no_active_ambiguous_key(self):
        boxes = self.build()
        self.assertNotIn("human_research", boxes)
        self.assertNotIn('"human_research"', json.dumps(boxes))
        auto = boxes["five_appearance_research"]
        self.assertEqual(auto["origin"], "AUTOMATED_FIVE_APPEARANCES")
        self.assertFalse(auto["human_origin"])
        self.assertEqual(auto["method"], "FIVE_APPEARANCE_CORE_INSERTION_RESEARCH")
        self.assertIsNone(boxes["human_input_research"])
        self.assertEqual(boxes["human_input_gate"]["status"], "ABSENT")
        self.assertIsNone(boxes["composition_difference"]["human_input_vs_mechanical"])
        self.assertIn(boxes["composition_difference"]["five_appearance_vs_mechanical"], ("YES", "NO"))

    def test_old_canonical_manual_field_never_reused_as_new_human_input(self):
        changed = deepcopy(self.race)
        changed["human_box_input"] = {"core": [6, 5], "insertion": 4, "origin": "HUMAN_MANUAL"}
        self.assertEqual(self.build(), self.build(race=changed))
        self.assertFalse(self.build(race=changed)["canonical_human_box_input_consumed"])

    def test_automatic_counts_and_old_arithmetic_kernels_unchanged(self):
        boxes = self.build()
        auto_race = deepcopy(self.race)
        auto_race["human_box_input"] = None
        old = build_boxes(auto_race, self.dist, self.five, self.odds)
        self.assertEqual(boxes["five_appearance_research"]["tickets"], old["human_research"]["tickets"])
        for name in ("mechanical_research", "box_v11_research"):
            self.assertEqual(boxes[name], old[name])
        self.assertEqual(boxes["five_appearance_research"]["five_appearance_counts"],
                         {str(boat): sum(str(boat) in t.split("-") for t in self.five["tickets"]) for boat in range(1, 7)})

    def test_explicit_human_input_is_a_separate_nullable_lane(self):
        auto = self.build()["five_appearance_research"]
        complement = sorted(set(range(1, 7)) - set(auto["boats"]))
        manual = asserted_manual(self.race, complement)
        boxes = self.build(manual)
        self.assertEqual(boxes["five_appearance_research"], auto)
        human = boxes["human_input_research"]
        self.assertEqual(human["boats"], complement)
        self.assertEqual(human["input_provenance"], manual)
        self.assertEqual(human["human_input_sha256"], canonical_hash(manual))
        self.assertEqual(human["origin"], "HUMAN_MANUAL")
        self.assertEqual(human["external_origin_authenticity"], "UNVERIFIED")
        self.assertFalse(human["formal_box_v1_reproduction"])
        self.assertTrue(boxes["human_input_gate"]["eligible"])
        self.assertFalse(boxes["live_eligible"])

    def test_manual_origin_missing_field_extra_field_hash_and_identity_hold(self):
        manual = asserted_manual(self.race)
        cases = [dict(manual, origin="AUTOMATED"), dict(manual, evidence_sha256="bad"),
                 dict(manual, race_id="OTHER_RACE"), dict(manual, extra="unreviewed"),
                 {key: value for key, value in manual.items() if key != "origin"}]
        for item in cases:
            with self.subTest(case=item):
                boxes = self.build(item)
                self.assertIsNone(boxes["human_input_research"])
                self.assertEqual(boxes["human_input_gate"]["status"], "HOLD")
                self.assertFalse(boxes["human_input_gate"]["eligible"])

    def test_all_manual_timestamps_must_be_available_before_prediction(self):
        manual = asserted_manual(self.race)
        future = (datetime.fromisoformat(self.race["prediction_at"]) + timedelta(seconds=1)).isoformat()
        for field in ("observed_at", "acquired_at", "available_at", "revision_at", "evidence_recorded_at"):
            with self.subTest(field=field):
                self.assertEqual(self.build(dict(manual, **{field: future}))["human_input_gate"]["status"], "HOLD")
        self.assertEqual(self.build(dict(manual, available_at=manual["observed_at"]))["human_input_gate"]["status"], "HOLD")
        self.assertEqual(self.build(dict(manual, evidence_recorded_at="2098-01-01T00:00:00+09:00"))["human_input_gate"]["status"], "HOLD")

    def test_invalid_timestamps_and_composition_rejected_without_echo(self):
        manual = asserted_manual(self.race)
        for stamp in ("2099-01-03T12:54:00", "2099-01-03T12:54:00-00:00", "2099-01-03T12:54:00+00:99"):
            self.assertEqual(self.build(dict(manual, observed_at=stamp))["human_input_gate"]["status"], "HOLD")
        for insertion in (True, 7, manual["core"][0]):
            self.assertEqual(self.build(dict(manual, insertion=insertion))["human_input_gate"]["status"], "HOLD")
        self.assertEqual(validate_human_input(None, manual)["status"], "HOLD")
        self.assertEqual(validate_human_input(dict(self.race, active_boats=[{}]), manual)["status"], "HOLD")

    def test_manual_receipt_cannot_precede_final_revision_or_available_selection(self):
        manual = asserted_manual(self.race)
        vectors = [
            (dict(manual, revision_at=self.race["prediction_at"]), "HUMAN_REVISION_AFTER_EVIDENCE"),
            (dict(manual, revision_at=manual["observed_at"]), "HUMAN_REVISION_BEFORE_ACQUISITION"),
            (dict(manual, acquired_at=manual["revision_at"]), "HUMAN_AVAILABILITY_BEFORE_ACQUISITION"),
            (dict(manual, observed_at=manual["available_at"]), "HUMAN_ACQUISITION_BEFORE_SELECTION"),
            (dict(manual, evidence_recorded_at=manual["acquired_at"]), "HUMAN_EVIDENCE_BEFORE_AVAILABILITY"),
        ]
        for item, code in vectors:
            with self.subTest(code=code):
                gate = validate_human_input(self.race, item)
                self.assertEqual(gate["status"], "HOLD")
                self.assertIn(code, gate["errors"])

    def test_manual_equal_ordering_boundaries_are_allowed(self):
        manual = asserted_manual(self.race)
        for field in ("observed_at", "acquired_at", "available_at", "revision_at", "evidence_recorded_at"):
            manual[field] = self.race["prediction_at"]
        self.assertTrue(validate_human_input(self.race, manual)["eligible"])

    def test_each_box_six_tickets_600_yen_and_overlaps_named_unambiguously(self):
        boxes = self.build(asserted_manual(self.race))
        for name in ("five_appearance_research", "human_input_research", "mechanical_research", "box_v11_research"):
            self.assertEqual(boxes[name]["stake_yen"], 600)
            self.assertEqual(len(set(boxes[name]["tickets"])), 6)
            self.assertFalse(boxes[name]["formal_box_v1_reproduction"])
            self.assertEqual(boxes["overlap"]["five_vs_" + name], sorted(set(self.five["tickets"]) & set(boxes[name]["tickets"])))
        self.assertNotIn("five_vs_human_research", boxes["overlap"])

    def test_build_does_not_mutate_any_input(self):
        manual = asserted_manual(self.race)
        inputs = deepcopy((self.race, self.dist, self.five, self.odds, manual))
        self.build(manual)
        self.assertEqual(inputs, (self.race, self.dist, self.five, self.odds, manual))

    def test_migration_old_only_holds_for_missing_race_course_evidence(self):
        old = deepcopy(self.old)
        report = migrate_v001_prediction(old)
        self.assertEqual(old, self.old)
        self.assertEqual(report["status"], "HOLD")
        self.assertFalse(report["live_eligible"])
        self.assertIsNone(report["candidate"])
        self.assertIn("COURSE_PROVENANCE_UNVERIFIED", report["reason_codes"])

    def test_migration_ambiguous_old_manual_not_renamed_to_automatic(self):
        old = deepcopy(self.old)
        self.assertEqual(old["boxes"]["human_research"]["method"], "MANUAL_CORE_INSERTION_RESEARCH")
        report = migrate_v001_prediction(old, self.race)
        preview = report["candidate"]
        self.assertIsNotNone(preview)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn("OLD_MANUAL_ORIGIN_EVIDENCE_NOT_ACCEPTED", report["reason_codes"])
        self.assertIn("COURSE_PROVENANCE_UNVERIFIED", report["reason_codes"])
        self.assertEqual(preview["selection"], old["selection"])
        self.assertEqual(preview["distributions"], old["distributions"])
        self.assertEqual(preview["boxes"]["five_appearance_research"], self.build()["five_appearance_research"])
        self.assertIsNone(preview["boxes"]["human_input_research"])
        self.assertNotIn('"human_research"', json.dumps(preview))
        self.assertNotIn("prediction_sha256", preview)
        self.assertEqual(old, self.old)

    def test_migration_explicit_new_manual_does_not_repair_old_course_lineage(self):
        report = migrate_v001_prediction(self.old, self.race, human_input=asserted_manual(self.race))
        self.assertIsNotNone(report["candidate"]["boxes"]["human_input_research"])
        self.assertTrue(report["requires_new_course_bound_prediction"])
        self.assertFalse(report["live_eligible"])
        self.assertFalse(report["production_go"])

    def test_migration_tampered_old_forecast_or_race_holds(self):
        altered = deepcopy(self.old)
        altered["prediction_sha256"] = "0" * 64
        self.assertIsNone(migrate_v001_prediction(altered, self.race)["candidate"])
        changed_race = deepcopy(self.race)
        changed_race["human_box_input"] = None
        self.assertIn("OLD_FORECAST_RACE_HASH_MISMATCH", migrate_v001_prediction(self.old, changed_race)["reason_codes"])

    def test_evaluation_has_five_separate_names_null_manual_unknown(self):
        record = self.record()
        report = evaluate_records_v003([record])
        self.assertEqual(tuple(report["methods"]), METHODS_V003)
        self.assertNotIn('"human_research"', json.dumps(report))
        self.assertEqual(report["methods"]["five"]["stake_yen"], 500)
        for name in ("five_appearance_research", "mechanical_research", "box_v11_research"):
            self.assertEqual(report["methods"][name]["stake_yen"], 600)
        manual = report["methods"]["human_input_research"]
        self.assertEqual(manual["n"], 0)
        self.assertEqual(manual["absent_input_n"], 1)
        self.assertIsNone(manual["hit_n"])
        self.assertIsNone(manual["stake_yen"])
        self.assertIsNone(manual["roi"])
        self.assertEqual(report["legacy_comparison"]["status"], "OPEN")

    def test_evaluation_explicit_manual_metrics_and_refunds_are_independent(self):
        record = self.record(asserted_manual(self.race))
        record["actual"]["result"] = [1, 2, 3]
        record["actual"]["payout_per_100"] = 1100
        record["actual"]["refund_tickets"] = ["1-3-2"]
        report = evaluate_records_v003([record])
        manual = report["methods"]["human_input_research"]
        self.assertEqual(manual["n"], 1)
        self.assertEqual(manual["hit_n"], 1)
        self.assertEqual(manual["stake_yen"], 600)
        self.assertEqual(manual["refund_yen"], 100)
        self.assertEqual(manual["net_yen"], 600)
        self.assertNotIn("combined_roi", report)

    def test_evaluation_cannot_accept_automatic_box_as_human_or_forged_composition(self):
        record = self.record()
        record["boxes"]["human_input_research"] = deepcopy(record["boxes"]["five_appearance_research"])
        self.assertIsNone(evaluate_records_v003([record])["methods"]["human_input_research"]["hit_n"])
        record = self.record(asserted_manual(self.race))
        record["boxes"]["human_input_research"]["core"] = [4, 5]
        self.assertIsNone(evaluate_records_v003([record])["methods"]["human_input_research"]["hit_n"])

    def test_evaluation_rejects_false_auto_origin_and_wrong_normal_five_counts(self):
        record = self.record()
        record["boxes"]["five_appearance_research"]["origin"] = "HUMAN_MANUAL"
        automatic = evaluate_records_v003([record])["methods"]["five_appearance_research"]
        self.assertEqual(automatic["n"], 0)
        self.assertIsNone(automatic["hit_n"])
        record = self.record(asserted_manual(self.race))
        record["boxes"]["human_input_research"]["five_appearance_counts"]["1"] = 1000
        manual = evaluate_records_v003([record])["methods"]["human_input_research"]
        self.assertEqual(manual["invalid_or_unmatched_input_n"], 1)
        self.assertIsNone(manual["hit_n"])

    def test_evaluation_no_legacy_formal_comparison_or_duplicate_inflation(self):
        record = self.record(asserted_manual(self.race))
        report = evaluate_records_v003([record, record])
        self.assertEqual(report["matched_final_outcome_n"], 0)
        self.assertIsNone(report["methods"]["human_input_research"]["hit_n"])
        with self.assertRaises(ValueError):
            evaluate_records_v003([record], {"legacy_profile": {"verified": True}})

    def test_evaluation_does_not_mutate_records_and_preserves_old_math(self):
        record = self.record()
        original = deepcopy(record)
        report = evaluate_records_v003([record])
        self.assertEqual(record, original)
        from model11.metrics import evaluate_records
        legacy_record = deepcopy(record)
        legacy_record["boxes"]["human_research"] = legacy_record["boxes"]["five_appearance_research"]
        old = evaluate_records([legacy_record])
        for name in ("five", "mechanical_research", "box_v11_research"):
            self.assertEqual(report["methods"][name], old["methods"][name])


if __name__ == "__main__":
    unittest.main()
