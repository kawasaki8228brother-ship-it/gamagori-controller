"""Read local interpreter/package metadata, never environment values or URLs."""
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import sqlite3
import ssl
import sys

NAMES = ["Pygments", "annotated-types", "anyio", "beautifulsoup4", "certifi", "h11", "httpcore", "httpx", "idna",
         "iniconfig", "packaging", "pluggy", "pydantic", "pydantic_core", "pytest-asyncio", "pytest", "soupsieve",
         "typing-inspection", "typing_extensions"]


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    raw = (root / "requirements.txt").read_bytes()
    expected = dict(line.split("==") for line in raw.decode("ascii").splitlines() if line)
    installed = {}
    for name in NAMES:
        try:
            installed[name] = version(name)
        except PackageNotFoundError:
            installed[name] = None
    mismatch = {name: {"expected": value, "actual": installed.get(name)}
                for name, value in expected.items() if installed.get(name) != value}
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "sqlite": sqlite3.sqlite_version, "selected_versions": installed,
        "distribution_scope": "SELECTED_19_NOT_ALL_INSTALLED", "requirements_bytes": len(raw),
        "requirements_sha256": hashlib.sha256(raw).hexdigest(), "direct_pins": expected,
        "direct_mismatches": mismatch, "direct_requirements_match": not mismatch,
        "current_production_runtime": "UNVERIFIED_NOT_READ", "production_go": False}, sort_keys=True))
