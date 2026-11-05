"""Verify local bytes, exact diffs and preserved scope; never query live state."""
import difflib
import hashlib
import json
from pathlib import Path

SOURCE = {"main.py", "official.py", "parsers.py", "raceindex_status.py"}
TESTS = {"tests/test_health_controller_scope.py", "tests/test_health_official_index.py", "tests/test_health_raceindex_parser.py",
         "tests/test_health_v002_controller.py", "tests/test_health_v002_schedule.py"}
REMOVED = ("NoRaceVerified", "reviewed_schedule_decision", "schedule_evidence_provider", "_expected_race_numbers",
           "_index_hold_reason", "_hold_unverified_schedule")


def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify():
    doc = Path(__file__).resolve().parent
    root = doc.parents[1]
    manifest = json.loads((doc / "MANIFEST.json").read_bytes())
    names = set()
    for entry in manifest["files"]:
        path = Path(entry["path"])
        assert not path.is_absolute() and ".." not in path.parts and not (root / path).is_symlink(), "UNSAFE_PATH"
        data = (root / path).read_bytes()
        assert len(data) == entry["bytes"] and sha(data) == entry["sha256"] and blob(data) == entry["git_blob"], "FILE_MISMATCH:" + entry["path"]
        names.add(entry["path"])
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    assert actual == names | set(manifest["self_excluded_paths"]), "FILESET_MISMATCH"
    assert (doc / "SHA256SUMS.txt").read_text("ascii") == "".join(e["sha256"] + "  " + e["path"] + "\n" for e in manifest["files"]), "SUMS_MISMATCH"
    parent = json.loads((doc / "PARENT_FILES.json").read_bytes())
    changed = set()
    patches = {"C_SOURCE.patch": "", "TEST_EXPECTATIONS.patch": ""}
    for entry in parent:
        data = (root / entry["path"]).read_bytes()
        if sha(data) == entry["sha256"]: continue
        changed.add(entry["path"])
        original = (doc / "references" / (entry["path"] + ".48333a2.original.txt")).read_bytes()
        assert len(original) == entry["bytes"] and sha(original) == entry["sha256"] and blob(original) == entry["git_blob"], "PARENT_ARCHIVE_CHANGED"
        target = "C_SOURCE.patch" if entry["path"] in SOURCE else "TEST_EXPECTATIONS.patch"
        patches[target] += "".join(difflib.unified_diff(original.decode().splitlines(keepends=True), data.decode().splitlines(keepends=True),
            fromfile="a/" + entry["path"], tofile="b/" + entry["path"]))
    assert changed == SOURCE | TESTS, "CHANGE_SCOPE_MISMATCH"
    for name, patch in patches.items(): assert (doc / name).read_text() == patch, "EXACT_DIFF_MISMATCH"
    for name in ("main.py", "official.py", "raceindex_status.py"):
        text = (root / name).read_text()
        assert not any(token in text for token in REMOVED), "LEGACY_ACTIVE_PATH_REMAINS"
    old_parser = (doc / "references/parsers.py.48333a2.original.txt").read_bytes()
    new_parser = (root / "parsers.py").read_bytes()
    marker = b"def _find_section_table"
    assert old_parser[old_parser.index(marker):] == new_parser[new_parser.index(marker):], "OTHER_PARSER_CHANGED"
    records = json.loads((doc / "LOG_PROVENANCE.json").read_bytes())
    for record in records["logs"]:
        data = (root / record["published_path"]).read_bytes()
        assert len(data) == record["published_bytes"] and sha(data) == record["published_sha256"], "LOG_HASH_MISMATCH"
        if record["trust"] == "RAW_UNMODIFIED":
            assert len(data) == record["original_bytes"] and sha(data) == record["original_sha256"], "RAW_NOT_ORIGINAL"
        else: assert record["trust"] == "REDACTED", "UNKNOWN_LOG_TRUST"
    outcomes = json.loads((doc / "evidence/RESULTS.json").read_bytes())
    for runtime in ("312", "314"):
        result = outcomes["candidate_matrix"][runtime]
        assert result["pytest_result_categories"]["passed"] == 554 and result["skipped"] == 1, "MATRIX_COUNTS"
        assert result["pytest_result_categories"]["subtests passed"] == 27, "SUBTEST_COUNTS"
    assert outcomes["formal_208B_original"] == "SKIP_UNVERIFIED_NOT_SUPPLIED", "SPEC_MUST_NOT_BE_PASS"
    return {"status": "PASS", "scope": "LOCAL_ARTIFACT_INTEGRITY_ONLY", "manifest_files": len(names),
        "parent_files": len(parent), "changed_parent_files": sorted(changed), "unchanged_parent_files": len(parent) - len(changed),
        "historical_evidence_preserved": True, "legacy_active_paths_removed": True,
        "official_HTML_and_production_compatibility": "UNVERIFIED", "production_go": False}


if __name__ == "__main__": print(json.dumps(verify(), sort_keys=True))
