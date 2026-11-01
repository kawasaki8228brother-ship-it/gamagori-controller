"""Offline frame verifier. Prints no diagnostic body or file path."""
import hashlib
import json
import re
import sys
from pathlib import Path

def verify(data):
    lines = data.splitlines(keepends=True)
    if len(lines) < 3 or lines[0] != b"BEGIN CERTIFI_AUDIT_V002\n":
        return False
    match = re.fullmatch(br"END CERTIFI_AUDIT_V002 lines=([0-9]+) bytes=([0-9]+) sha256=([a-f0-9]{64})\n", lines[-1])
    if match is None:
        return False
    body = b"".join(lines[1:-1])
    if len(lines) - 2 != int(match[1]) or len(body) != int(match[2]) or hashlib.sha256(body).hexdigest().encode() != match[3]:
        return False
    try:
        return all(isinstance(json.loads(line), dict) for line in lines[1:-1])
    except (ValueError, UnicodeError):
        return False

if __name__ == "__main__":
    try:
        result = len(sys.argv) == 2 and verify(Path(sys.argv[1]).read_bytes())
    except Exception:
        result = False
    print("FRAME_VERIFIED" if result else "FRAME_REJECTED")
    raise SystemExit(0 if result else 2)
