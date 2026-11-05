"""Scoped static boundary and synthetic data-flow probes; not universal proof.

The frozen legacy comparison adapter is evaluation-only. No code is integrated
from the separately developed P1 independent raw evaluation component.
"""
from __future__ import annotations
import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from shadow_offline_v008.fault_suite import load_pinned_fixture

SELECTED = (
    "shadow_launch/sources.py", "shadow_launch/runner.py", "preparation/adapter.py",
    "revision_v003/engine.py", "revision_v003/course.py", "revision_v003/portfolios.py",
    "revision_v003/pooling.py", "models.py", "selection.py", "validation.py",
)
DENIED_ROOTS = {"airtable", "pyairtable", "automations", "requests", "httpx", "urllib", "boto3"}
DENIED_CALLS = {"read_ab_events", "read_ab_locks", "read_airtable", "fetch_ab_predictions", "read_production_events"}


def static_boundary():
    root = Path(__file__).resolve().parents[1] / "model11"
    rows, violations = [], []
    for relative in SELECTED:
        raw = (root / relative).read_bytes()
        tree = ast.parse(raw)
        imports, calls = set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                if name:
                    calls.add(name)
        bad = sorted((imports & DENIED_ROOTS) | (calls & DENIED_CALLS))
        violations.extend({"path": relative, "symbol": name} for name in bad)
        rows.append({"path": relative, "bytes": len(raw), "sha256": sha256(raw).hexdigest(),
                     "denied_symbols": bad})
    return {"status": "TESTED" if not violations else "FAILED_OPEN", "scope": "TEN_SELECTED_SOURCE_FILES_AST_IMPORT_CALL_SCAN",
            "files": rows, "violations": violations, "universal_proof": False,
            "excluded_evaluation": ["preparation/legacy.py", "revision_v003/evaluation.py"], "go": False}


def dataflow_probe():
    """Exact declared-pointer read spy plus ignored/rejected A/B poison cases."""
    from model11.preparation.adapter import normalize_race
    from model11.revision_v003.engine import predict_v003
    import model11.shadow_launch.sources as sources
    fixture = load_pinned_fixture("runner")
    with tempfile.TemporaryDirectory(prefix="synthetic-ab-boundary-") as root:
        context = fixture.make_simulation_context(root)
        capture = context["captures"][0]
        adapter = context["source_adapter"]
        baseline = adapter.convert(capture)
        poison = fixture.resign_capture(capture, lambda doc: doc.update({
            "A_Events": {"source": "A", "prediction": "SYNTHETIC_AB_POISON"},
            "B_LOCK": {"source": "B", "prediction": "SYNTHETIC_AB_POISON"}}))
        reads = []
        original = sources._resolve
        def spy(document, pointer):
            reads.append(pointer)
            return original(document, pointer)
        with patch.object(sources, "_resolve", spy):
            observed = adapter.convert(poison)
        expected = list(context["mapping"]["raw_fields"].values()) + list(context["mapping"]["course_fields"].values())
        same_inputs = baseline.get("raw") == observed.get("raw") and baseline.get("course") == observed.get("course")
        same_prediction = False
        if baseline["status"] == observed["status"] == "READY" and same_inputs:
            def predict(item):
                race = normalize_race(item["raw"], context["normalizer"], usage="prediction")["race"]
                race.update(deepcopy(item["course"]))
                return predict_v003(race, context["model"], context["model_config"])
            same_prediction = predict(baseline) == predict(observed)
        nested = fixture.resign_capture(capture, lambda doc: doc["invented_raw"]["boats"][0]["features"].update({"A_Events": {"source": "A"}}))
        wrong_source = deepcopy(capture)
        wrong_source["source_id"] = "A"
        rejected = {"declared_feature_nested_ab": adapter.convert(nested)["status"],
                    "capture_source_A": adapter.convert(wrong_source)["status"]}
        pointer_exact = sorted(reads) == sorted(expected) and len(reads) == len(expected)
        no_ab_reads = all("A_Events" not in pointer and "B_LOCK" not in pointer for pointer in reads)
        passed = same_inputs and same_prediction and pointer_exact and no_ab_reads and all(status == "HOLD" for status in rejected.values())
        return {"status": "TESTED" if passed else "FAILED_OPEN", "declared_pointer_count": len(expected),
                "observed_pointer_count": len(reads), "declared_pointer_set_exact": pointer_exact,
                "no_ab_pointer_resolved": no_ab_reads, "normalized_feature_inputs_equal": same_inputs,
                "all_prediction_and_selection_outputs_equal": same_prediction,
                "rejected_cases": rejected, "poison_origin": "INVENTED_SYNTHETIC_ONLY",
                "limitations": ["TOP_LEVEL_CAPTURE_JSON_IS_PARSED_BUT_NOT_RESOLVED_TO_FEATURES",
                                "ONLY_EXERCISED_POINTERS_AND_DECLARED_BOUNDARY_SCANNED", "NOT_REAL_HOST_OR_ALL_PYTHON_PROOF"],
                "go": False}


def run_independence():
    static, dynamic = static_boundary(), dataflow_probe()
    return {"schema": "SHADOW_AB_BOUNDARY_V008", "static": static, "dataflow": dynamic,
            "status": "TESTED" if static["status"] == dynamic["status"] == "TESTED" else "FAILED_OPEN",
            "ab_prediction_reader_added": False, "p1_evaluator_imported": False,
            "real_ab_access": False, "go": False}


if __name__ == "__main__":
    print(json.dumps(run_independence(), ensure_ascii=True, sort_keys=True, indent=2))
