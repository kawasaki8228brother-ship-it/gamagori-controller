"""Typed safe index observations and an opt-in calendar-evidence contract.

No calendar is fetched or configured here. Hash/receipt consistency cannot
authenticate official truth or independent review; that protocol remains OPEN.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re


INDEX_KINDS = frozenset({"HTTP_FETCH_FAILED", "HTML_PARSE_FAILED", "TRACKING_MISSING",
                         "TRACKING_PARSE_FAILED", "UNKNOWN_FAILURE", "NO_RACE_VERIFIED"})
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
    "INDEPENDENT_OFFICIAL_CALENDAR_NO_RACE",
})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
FULL_RACE_NUMBERS = frozenset(range(1, 13))


class IndexFailure(RuntimeError):
    """Fixed-code diagnostic: never retain a source URL or exception string."""
    def __init__(self, kind="UNKNOWN_FAILURE", reason="UNCLASSIFIED_EXCEPTION"):
        self.kind = kind if isinstance(kind, str) and kind in INDEX_KINDS else "UNKNOWN_FAILURE"
        self.reason = reason if isinstance(reason, str) and reason in _REASONS else "UNCLASSIFIED_EXCEPTION"
        super().__init__(self.kind + ":" + self.reason)


class NoRaceVerified(IndexFailure):
    """Local validated calendar-proof contract, not HTML-derived absence.

    An actual provider must be independently reviewed before it is configured.
    The default application has no such provider; this class alone grants none.
    """
    def __init__(self):
        super().__init__("NO_RACE_VERIFIED", "INDEPENDENT_OFFICIAL_CALENDAR_NO_RACE")


def classify_index_exception(exc):
    """Return safe fields without evaluating an untrusted exception's str/repr."""
    if isinstance(exc, IndexFailure):
        normalized = IndexFailure(exc.kind, exc.reason)
    else:
        normalized = IndexFailure()
    return {"kind": normalized.kind, "reason": normalized.reason}


def reviewed_schedule_decision(evidence, target_date):
    """Validate only submitted binding claims; unaccepted evidence keeps 12 races.

    Review must bind date/venue/event/numbers/raw SHA and have an explicit true
    flag plus a separate receipt reference. No raw-calendar parser is invented.
    """
    base = {"accepted": False, "event": None, "race_numbers": FULL_RACE_NUMBERS,
            "reason": "SCHEDULE_EVIDENCE_UNVERIFIED", "external_authenticity": "UNVERIFIED"}
    try:
        if (not isinstance(target_date, str) or not re.fullmatch(r"[0-9]{8}", target_date)
                or dt.datetime.strptime(target_date, "%Y%m%d").strftime("%Y%m%d") != target_date):
            return base
        fields = {"schema", "date", "venue", "event", "race_numbers", "authority",
                  "raw_evidence", "raw_sha256", "independent_review"}
        if not isinstance(evidence, dict) or set(evidence) != fields:
            return base
        if (evidence["schema"] != "OFFICIAL_SCHEDULE_EVIDENCE_V001_PROPOSED"
                or evidence["date"] != target_date or evidence["venue"] != "07"
                or evidence["authority"] != "OFFICIAL_SCHEDULE"
                or evidence["event"] not in ("NO_RACE", "RACING_DAY")):
            return base
        raw, digest = evidence["raw_evidence"], evidence["raw_sha256"]
        if (not isinstance(raw, bytes) or not raw or not isinstance(digest, str)
                or not _SHA.fullmatch(digest) or hashlib.sha256(raw).hexdigest() != digest):
            return base
        numbers = evidence["race_numbers"]
        if (not isinstance(numbers, list) or any(type(number) is not int or not 1 <= number <= 12 for number in numbers)
                or len(set(numbers)) != len(numbers)):
            return base
        if evidence["event"] == "NO_RACE" and numbers or evidence["event"] == "RACING_DAY" and not numbers:
            return base
        review = evidence["independent_review"]
        if (not isinstance(review, dict) or set(review) != {"reviewed", "receipt_sha256", "date", "venue", "event", "race_numbers", "raw_sha256"}
                or review["reviewed"] is not True or not isinstance(review["receipt_sha256"], str)
                or not _SHA.fullmatch(review["receipt_sha256"])
                or any(review[key] != evidence[key] for key in ("date", "venue", "event", "race_numbers", "raw_sha256"))):
            return base
        return {"accepted": True, "event": evidence["event"], "race_numbers": frozenset(numbers),
                "reason": "SCHEDULE_REVIEW_BINDINGS_MATCHED", "external_authenticity": "UNVERIFIED"}
    except (ValueError, TypeError, KeyError, OverflowError):
        return base
