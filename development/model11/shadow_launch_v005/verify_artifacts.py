"""Read-only byte/hash verification; no network, installs, imports or rewrites."""
import hashlib
import json
from pathlib import Path, PurePosixPath


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    manifest = json.loads((here / "MANIFEST_V005.json").read_bytes())
    count = 0
    for entry in manifest["files"]:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("development", "model11"):
            raise ValueError("MANIFEST_PATH_INVALID")
        path = root.joinpath(*relative.parts)
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("MANIFEST_BYTE_OR_SHA_MISMATCH")
        count += 1
    sums_count = 0
    for line in (here / "SHA256SUMS_V005.txt").read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        relative = PurePosixPath(relative)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("development", "model11"):
            raise ValueError("SUMS_PATH_INVALID")
        if hashlib.sha256(root.joinpath(*relative.parts).read_bytes()).hexdigest() != digest:
            raise ValueError("SUMS_SHA_MISMATCH")
        sums_count += 1
    print(json.dumps({"status": "PASS", "manifest_files": count,
        "new_files_in_sums": sums_count, "scope": "LOCAL_BYTES_ONLY",
        "production_go": False}, sort_keys=True))


if __name__ == "__main__":
    main()
