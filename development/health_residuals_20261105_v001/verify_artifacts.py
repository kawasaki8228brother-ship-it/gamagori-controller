"""Read-only integrity checks for this offline candidate, not a live-state audit."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify() -> dict:
    directory = Path(__file__).resolve().parent
    root = directory.parents[1]
    manifest = json.loads((directory / "MANIFEST.json").read_bytes())
    expected_paths = set()
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        assert not relative.is_absolute() and ".." not in relative.parts, "UNSAFE_MANIFEST_PATH"
        path = root / relative
        assert not path.is_symlink(), "SYMLINK_NOT_ALLOWED"
        data = path.read_bytes()
        assert len(data) == entry["bytes"], "BYTE_COUNT_MISMATCH:" + entry["path"]
        assert digest(data) == entry["sha256"], "SHA256_MISMATCH:" + entry["path"]
        assert git_blob(data) == entry["git_blob"], "GIT_BLOB_MISMATCH:" + entry["path"]
        expected_paths.add(entry["path"])
    expected_sums = "".join(entry["sha256"] + "  " + entry["path"] + "\n" for entry in manifest["files"])
    assert (directory / "SHA256SUMS.txt").read_text("ascii") == expected_sums, "SUMS_MANIFEST_MISMATCH"
    excluded = set(manifest["self_excluded_paths"])
    actual_paths = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts}
    assert actual_paths == expected_paths | excluded, "UNEXPECTED_OR_MISSING_LOCAL_FILE"

    originals = json.loads((directory / "PARENT_FILES.json").read_bytes())
    changed = []
    patch = ""
    for original in originals:
        name = original["path"]
        current = (root / name).read_bytes()
        if digest(current) != original["sha256"]:
            changed.append(name)
            archived = (directory / "references" / (name + ".8172aec.original.txt")).read_bytes()
            assert len(archived) == original["bytes"] and digest(archived) == original["sha256"], "ORIGINAL_CHANGED"
            assert git_blob(archived) == original["git_blob"], "ORIGINAL_GIT_BLOB_CHANGED"
            patch += "".join(difflib.unified_diff(archived.decode().splitlines(keepends=True),
                current.decode().splitlines(keepends=True), fromfile="a/" + name, tofile="b/" + name))
    assert sorted(changed) == ["main.py", "official.py", "parsers.py"], "CHANGE_SCOPE_MISMATCH"
    assert (directory / "C_SOURCE.patch").read_text() == patch, "SOURCE_DIFF_MISMATCH"
    original_parser = (directory / "references/parsers.py.8172aec.original.txt").read_bytes()
    current_parser = (root / "parsers.py").read_bytes()
    boundary = b"def _find_section_table"
    assert original_parser[original_parser.index(boundary):] == current_parser[current_parser.index(boundary):], "OTHER_PARSER_FUNCTIONS_CHANGED"

    provenance = json.loads((directory / "LOG_PROVENANCE.json").read_bytes())
    for record in provenance["logs"]:
        data = (root / record["published_path"]).read_bytes()
        assert len(data) == record["published_bytes"] and digest(data) == record["published_sha256"], "PUBLISHED_LOG_MISMATCH"
        if record["trust"] == "RAW_UNMODIFIED":
            assert record["original_sha256"] == record["published_sha256"], "RAW_LOG_HASH_MISMATCH"
            assert record["original_bytes"] == record["published_bytes"], "RAW_LOG_SIZE_MISMATCH"
        else:
            assert record["trust"] == "REDACTED", "UNKNOWN_LOG_TRUST"
    return {"status": "PASS", "scope": "LOCAL_ARTIFACT_BYTES_ONLY", "files_checked": len(expected_paths),
            "original_files": len(originals), "modified_original_files": changed,
            "unchanged_original_files": len(originals) - len(changed), "source_diff_exact": True,
            "production_state": "UNVERIFIED", "production_go": False}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, ensure_ascii=True))
