"""New offline fault harness tests; embedded frozen vectors are separately counted."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from shadow_offline_v008.fault_suite import (
    classify_research_status, diagnose_clock_pair, load_pinned_fixture, lost_ack_probe,
    run_frozen_vectors, refund_probe, VECTORS,
)
from shadow_offline_v008.independence import static_boundary, dataflow_probe


class OfflineFaultTests(unittest.TestCase):
    def test_frozen_baseline_vectors_reexecute_without_skip(self):
        rows = run_frozen_vectors()
        self.assertEqual(len(rows), len(VECTORS))
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertTrue(all(row["status"] == "TESTED" and row["tests_run"] == 1 for row in rows), rows)

    def test_lost_ack_preserves_all_files_and_stops_across_restart(self):
        self.assertEqual(lost_ack_probe()["status"], "TESTED")

    def test_clock_backward_and_forward_are_observation_not_new_policy(self):
        start = datetime(2099, 1, 7, tzinfo=timezone.utc)
        for delta, reason in ((-5, "WALL_BACKWARD"), (500, "WALL_MONOTONIC_DISAGREE"), (1, "CONSISTENT_PAIR")):
            row = diagnose_clock_pair(start.isoformat(), (start+timedelta(seconds=delta)).isoformat(), 100, 101)
            self.assertEqual(row["reason"], reason)
            self.assertFalse(row["threshold_adopted"])
            self.assertFalse(row["go"])
        self.assertEqual(diagnose_clock_pair(start.isoformat(), start.isoformat(), 2, 1)["reason"], "MONOTONIC_REGRESSION")

    def test_clock_missing_nonfinite_naive_and_boolean_fail_closed(self):
        start = "2099-01-07T00:00:00+00:00"
        for first,last,a,b in ((None,start,0,1), (start,start,float("nan"),1), (start,start,True,1), ("2099-01-07T00:00:00",start,0,1)):
            self.assertEqual(diagnose_clock_pair(first,last,a,b)["status"], "HOLD")

    def test_correction_refund_cancel_scratch_are_distinct_and_no_money_invented(self):
        rows = [classify_research_status({"kind":kind, "classification":"SYNTHETIC_ONLY"})
                for kind in ("RESULT_CORRECTION", "TICKET_REFUND", "RACE_CANCELLED", "BOAT_SCRATCHED")]
        self.assertEqual(len({row["kind"] for row in rows}), 4)
        self.assertTrue(all(row["pnl_yen"] is None and not row["writer_integrated"] and not row["go"] for row in rows))
        for row in rows[2:]:
            self.assertEqual(row["settlement"], "BLOCKED_EXTERNAL")
        self.assertEqual(classify_research_status({"kind":"RACE_CANCELLED", "classification":"PRIVATE_REAL"})["status"], "HOLD")

    def test_refunds_existing_contract_separate_method_stakes(self):
        row = refund_probe()
        self.assertEqual(row["status"], "TESTED")
        self.assertEqual(row["methods"]["five"], {"stake":500,"refund":100,"return":1100,"net":600})
        self.assertEqual(row["methods"]["mechanical_research"], {"stake":600,"refund":100,"return":1100,"net":500})
        self.assertTrue(row["missing_refund_not_zero"])
        self.assertTrue(row["winning_ticket_refund_rejected"])
        self.assertFalse(row["combined_portfolio_pnl_created"])

    def test_scoped_ast_has_no_named_production_connectors(self):
        row = static_boundary()
        self.assertEqual(row["status"], "TESTED")
        self.assertEqual(len(row["files"]), 10)
        self.assertFalse(row["universal_proof"])

    def test_ab_poison_and_pointer_readspy_do_not_enter_prediction(self):
        row = dataflow_probe()
        self.assertEqual(row["status"], "TESTED", row)
        self.assertTrue(row["all_prediction_and_selection_outputs_equal"])
        self.assertFalse(row["go"])

    def test_log_exports_do_not_contain_synthetic_exception_sentinel(self):
        row = lost_ack_probe()
        output = json.dumps(row, sort_keys=True)
        self.assertNotIn("SYNTHETIC_PRIVATE_ACK_ERROR_NOT_FOR_EXPORT", output)
        self.assertFalse(row["go"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
