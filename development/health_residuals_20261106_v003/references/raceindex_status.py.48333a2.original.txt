"""Typed index observations; calendar authentication is NOT implemented.

Self-reported bytes, hashes, review booleans and receipt references never verify
absence or shorten the expected universe. Legacy names are quarantined.
"""
from __future__ import annotations

INDEX_KINDS = frozenset({"HTTP_FETCH_FAILED", "HTML_PARSE_FAILED", "TRACKING_MISSING",
                         "TRACKING_PARSE_FAILED", "UNKNOWN_FAILURE", "SCHEDULE_UNVERIFIED"})
_REASONS = frozenset({
    "UNCLASSIFIED_EXCEPTION", "HTTP_RETRIES_EXHAUSTED", "HTTP_REQUEST_FAILED",
    "RACE_INDEX_HTML_INVALID", "RACE_INDEX_UNKNOWN_FAILURE", "NOW_JST_AWARE_REQUIRED",
    "OFFICIAL_SNAPSHOT_SCOPE_INVALID", "TRACKING_SNAPSHOT_SCOPE_INVALID",
    "TRACKING_JSON_INVALID", "TRACKING_PAYLOAD_NOT_OBJECT", "TRACKING_PROGRAMS_NOT_OBJECT",
    "TRACKING_STADIUMS_NOT_OBJECT", "TRACKING_STADIUM_7_MISSING", "TRACKING_STADIUM_AMBIGUOUS",
    "TRACKING_STADIUM_NOT_OBJECT", "TRACKING_STADIUM_ID_MISMATCH", "TRACKING_RACES_MISSING",
    "TRACKING_RACES_NOT_OBJECT", "TRACKING_RACE_NOT_OBJECT", "TRACKING_RACE_NUMBER_INVALID",
    "TRACKING_RACE_KEY_NUMBER_MISMATCH", "TRACKING_RACE_NUMBER_DUPLICATE",
    "TRACKING_DEADLINE_INVALID", "TRACKING_DEADLINE_TARGET_DATE_MISMATCH",
    "TRACKING_PAYLOAD_DATE_MISMATCH", "TRACKING_EXPECTED_RACE_SET_MISMATCH",
    "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED",
})
FULL_RACE_NUMBERS = frozenset(range(1, 13))


class IndexFailure(RuntimeError):
    """Fixed-code diagnostic: never retain a source URL or exception string."""
    def __init__(self, kind="UNKNOWN_FAILURE", reason="UNCLASSIFIED_EXCEPTION"):
        if isinstance(kind, str) and kind == "NO_RACE_VERIFIED":
            # A manually constructed legacy status is not a calendar proof.
            kind, reason = "SCHEDULE_UNVERIFIED", "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED"
        self.kind = kind if isinstance(kind, str) and kind in INDEX_KINDS else "UNKNOWN_FAILURE"
        self.reason = reason if isinstance(reason, str) and reason in _REASONS else "UNCLASSIFIED_EXCEPTION"
        super().__init__(self.kind + ":" + self.reason)


class NoRaceVerified(IndexFailure):
    """Legacy import compatibility only; never represents verified absence."""
    def __init__(self):
        super().__init__("SCHEDULE_UNVERIFIED", "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED")


def classify_index_exception(exc):
    """Return safe fields without evaluating an untrusted exception's str/repr."""
    normalized = IndexFailure()
    try:
        if isinstance(exc, NoRaceVerified):
            normalized = NoRaceVerified()
        elif isinstance(exc, IndexFailure):
            normalized = IndexFailure(exc.kind, exc.reason)
    except Exception:
        pass  # Malicious/unsupported attributes do not become diagnostics.
    return {"kind": normalized.kind, "reason": normalized.reason}


def reviewed_schedule_decision(evidence, target_date):
    """Always hold: no real calendar-authentication adapter exists.

    Inputs are deliberately not inspected, hashed, stringified or treated as
    authenticated evidence. Even genuine originals need a reviewed real adapter.
    The legacy signature is retained, without a bypass flag or test exception.
    """
    return {"accepted": False, "event": None, "race_numbers": FULL_RACE_NUMBERS,
            "status": "HOLD", "kind": "SCHEDULE_UNVERIFIED",
            "reason": "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED",
            "authentication_implemented": False, "external_authenticity": "UNVERIFIED"}
