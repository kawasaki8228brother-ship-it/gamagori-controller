"""C fetcher integration of strict-six 120-outcome odds extraction.

No market normalization, readiness-policy change or legacy-parser fallback.
SourceEvidence OK means extraction succeeded, not independent verification of
body date, live freshness, withdrawal status, transport or BET eligibility.
"""
from __future__ import annotations
import hashlib
import logging

from models import SourceEvidence
from parsers import ParserError
from v11_candidate.odds import parse_trifecta, OddsParseError

logger = logging.getLogger("gamagori-controller")
PARSER_VERSION = "C_ODDS_STRICT120_V1"


def parse_c_odds(html: str, url: str, acquired_at: str) -> tuple[dict[str, float], SourceEvidence]:
    """Keep the existing fetcher return contract; refuse partial matrices."""
    try:
        parsed = parse_trifecta(html, require_complete=True)
    except OddsParseError as exc:
        # Never rescue failed/ambiguous input through the old regex parser.
        raise ParserError(f"odds3t[{PARSER_VERSION}]: {exc}") from exc
    evidence = SourceEvidence(
        url=url, acquired_at=acquired_at, status="OK",
        parser_status=f"{PARSER_VERSION}:{parsed.parser_format}:{parsed.coverage}",
    )
    # This hashes the decoded/re-encoded string, NOT original HTTP entity bytes.
    text_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    logger.info("odds3t parser=%s format=%s outcomes=%d decoded_text_sha256=%s url=%s",
                PARSER_VERSION, parsed.parser_format, parsed.coverage, text_hash, url)
    return dict(parsed.odds), evidence
