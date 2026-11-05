"""Static design guards only; no log anonymizer, exporter or host is tested."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_f5_proposal_static_audit", HERE / "static_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ReviewProposalTests(unittest.TestCase):
    def test_received_proposal_remains_nonexecutable_and_unadopted(self):
        result = AUDIT.audit_review_proposal(AUDIT.load_json(HERE / "SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json"))
        self.assertEqual(result["status"], "PROPOSAL_REMAINS_UNADOPTED")
        self.assertFalse(result["statistical_evaluation_performed"])
        self.assertFalse(result["production_go"])

    def test_suggestion_cannot_become_execution_or_threshold_approval(self):
        original = AUDIT.load_json(HERE / "SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json")
        for change in ("export", "buffer", "policy"):
            value = deepcopy(original)
            if change == "export":
                value["operational_go"]["external_share"] = True
            elif change == "buffer":
                value["unadopted_parameters"]["deadline_buffer_seconds"] = 3
            else:
                value["M0_M2_M1_policy_changed"] = True
            with self.subTest(change=change):
                self.assertEqual(AUDIT.audit_review_proposal(value)["status"], "HOLD")

    def test_free_text_and_regex_masking_are_not_the_allowlisted_schema(self):
        original = AUDIT.load_json(HERE / "SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json")
        for change in ("free_text", "unknown_fields", "anonymity"):
            value = deepcopy(original)
            if change == "free_text":
                value["proposed_summary_schema"]["properties"]["exception_text"] = {"type": "string"}
            elif change == "unknown_fields":
                value["proposed_summary_schema"]["additionalProperties"] = True
            else:
                value["proposed_additional_checks"]["complete_anonymity"] = "GUARANTEED"
            with self.subTest(change=change):
                self.assertEqual(AUDIT.audit_review_proposal(value)["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
