"""Read-only local v002 snapshot verification; not an authenticity/live audit."""
import difflib
import hashlib
import json
from pathlib import Path

SOURCE_CHANGES = {"main.py", "official.py", "parsers.py", "raceindex_status.py"}
TEST_CHANGES = {"tests/test_health_controller_scope.py", "tests/test_health_official_index.py", "tests/test_health_raceindex_parser.py"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify():
    doc = Path(__file__).resolve().parent
    root = doc.parents[1]
    manifest = json.loads((doc / "MANIFEST.json").read_bytes())
    names = set()
    for entry in manifest["files"]:
        path = Path(entry["path"])
        assert not path.is_absolute() and ".." not in path.parts, "UNSAFE_PATH"
        assert not (root / path).is_symlink(), "SYMLINK_UNSUPPORTED"
        data = (root / path).read_bytes()
        assert len(data) == entry["bytes"] and sha(data) == entry["sha256"] and blob(data) == entry["git_blob"], "FILE_HASH_MISMATCH:" + entry["path"]
        names.add(entry["path"])
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    assert actual == names | set(manifest["self_excluded_paths"]), "FILE_SET_MISMATCH"
    sums = "".join(e["sha256"] + "  " + e["path"] + "\n" for e in manifest["files"])
    assert (doc / "SHA256SUMS.txt").read_text("ascii") == sums, "SUMS_DISAGREE"
    parent = json.loads((doc / "PARENT_FILES.json").read_bytes())
    changed = set()
    patches = {"C_SOURCE.patch": "", "TEST_EXPECTATIONS.patch": ""}
    for entry in parent:
        data = (root / entry["path"]).read_bytes()
        if sha(data) == entry["sha256"]:
            continue
        changed.add(entry["path"])
        original = (doc / "references" / (entry["path"] + ".845cc1c.original.txt")).read_bytes()
        assert len(original) == entry["bytes"] and sha(original) == entry["sha256"] and blob(original) == entry["git_blob"], "PARENT_ORIGINAL_CHANGED"
        target = "C_SOURCE.patch" if entry["path"] in SOURCE_CHANGES else "TEST_EXPECTATIONS.patch"
        patches[target] += "".join(difflib.unified_diff(original.decode().splitlines(keepends=True), data.decode().splitlines(keepends=True),
            fromfile="a/" + entry["path"], tofile="b/" + entry["path"]))
    assert changed == SOURCE_CHANGES | TEST_CHANGES, "MODIFIED_FILE_SCOPE"
    for name, patch in patches.items():
        assert (doc / name).read_text() == patch, "EXACT_DIFF_MISMATCH"
    old_parser = (doc / "references/parsers.py.845cc1c.original.txt").read_bytes()
    new_parser = (root / "parsers.py").read_bytes()
    marker = b"def _find_section_table"
    assert old_parser[old_parser.index(marker):] == new_parser[new_parser.index(marker):], "UNRELATED_PARSER_CHANGED"
    correction = json.loads((doc / "OBS_SHA_CORRECTION.json").read_bytes())
    corrected = correction["corrected_reference"]
    value = corrected["received_hash_verbatim"]
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value), "CORRECTION_FORMAT"
    assert corrected["is_OBS_contract_SHA256"] is False and corrected["external_authenticity"] == "UNVERIFIED", "CORRECTION_SCOPE"
    for record in json.loads((doc / "LOG_PROVENANCE.json").read_bytes())["logs"]:
        data = (root / record["published_path"]).read_bytes()
        assert len(data) == record["published_bytes"] and sha(data) == record["published_sha256"], "LOG_HASH"
        if record["trust"] == "RAW_UNMODIFIED":
            assert record["original_bytes"] == len(data) and record["original_sha256"] == sha(data), "ORIGINAL_LOG_MISMATCH"
        else:
            assert record["trust"] == "REDACTED", "UNKNOWN_TRUST_LABEL"
    return {"status": "PASS", "scope": "LOCAL_BYTES_AND_DIFF_ONLY", "files_checked": len(names),
        "parent_files": len(parent), "modified_parent_files": sorted(changed), "unchanged_parent_files": len(parent) - len(changed),
        "prior_v001_documents_unchanged": True, "external_authenticity": "UNVERIFIED", "production_go": False}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
