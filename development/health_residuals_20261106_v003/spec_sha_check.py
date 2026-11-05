"""Optional private-file byte check. Never fetches or prints specification text.

The actual 208-byte original is not bundled. A local match is not authenticity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


CORRECTED_A_SPEC_SHA256 = "d462767f4448e28fc735df7363fb6f54a577e014607d5ec3b2fb1a75137c5e7f"
HISTORICAL_40_HEX = "d462767f4448e28fc735df7363fb1a75137c5e7f"
EXPECTED_UTF8_BYTES = 208
SKIP_STATUS = "SKIP_UNVERIFIED_PRIVATE_ORIGINAL_NOT_SUPPLIED"
MATCH_STATUS = "MATCHED_LOCAL_BYTES_EXTERNAL_AUTHENTICITY_UNVERIFIED"


def historical_projection_matches():
    """Literal string relationship only; no claim about its historical cause."""
    return HISTORICAL_40_HEX == CORRECTED_A_SPEC_SHA256[:28] + CORRECTED_A_SPEC_SHA256[-12:]


def check_private_spec(private_path=None):
    """Read only an explicitly supplied local file; return status/bytes/digest.

    No whitespace/newline/BOM normalization, no acquisition, and no raw output.
    Absence/read failure is unknown rather than zero bytes or digest success.
    """
    if private_path is None:
        return {"status": SKIP_STATUS, "bytes": None, "digest": None}
    try:
        path = Path(private_path)
        if not path.is_file():
            return {"status": "UNVERIFIED_PRIVATE_READ_FAILED", "bytes": None, "digest": None}
        raw = path.read_bytes()
    except (OSError, TypeError, ValueError):
        return {"status": "UNVERIFIED_PRIVATE_READ_FAILED", "bytes": None, "digest": None}
    digest = hashlib.sha256(raw).hexdigest()
    try:
        raw.decode("utf-8")
    except UnicodeError:
        return {"status": "MISMATCH_UTF8_ENCODING", "bytes": len(raw), "digest": digest}
    if len(raw) != EXPECTED_UTF8_BYTES:
        return {"status": "MISMATCH_EXPECTED_208_UTF8_BYTES", "bytes": len(raw), "digest": digest}
    return {"status": MATCH_STATUS if digest == CORRECTED_A_SPEC_SHA256 else "MISMATCH_REFERENCE_SHA256",
            "bytes": len(raw), "digest": digest}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        report = check_private_spec()
    elif len(arguments) == 2 and arguments[0] == "--private-spec-file":
        report = check_private_spec(arguments[1])
    else:
        # Do not let an argument parser echo a private path in an error message.
        report = {"status": "UNVERIFIED_ARGUMENT_SHAPE", "bytes": None, "digest": None}
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    if report["status"] == MATCH_STATUS:
        return 0
    return 1 if report["status"].startswith("MISMATCH_") else 3


if __name__ == "__main__":
    raise SystemExit(main())
