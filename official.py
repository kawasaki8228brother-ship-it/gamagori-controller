from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
from typing import Dict, Optional

import httpx

from models import JST, LiveDataCompleteness, OfficialRaceInfo, RaceIndexSnapshot, SourceEvidence
from parsers import ParserError, parse_race_index
from beforeinfo_bridge import prepare_beforeinfo
from odds_bridge import parse_c_odds
from raceindex_status import FULL_RACE_NUMBERS, IndexFailure, NoRaceVerified, reviewed_schedule_decision

logger = logging.getLogger("gamagori-controller")


class OfficialDataFetcher:
    BASE_URL = "https://www.boatrace.jp/owpc/pc/race"
    TRACKING_FALLBACK_BASE = "https://boatraceopenapi.github.io/api/v1"

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        max_concurrency: int = 4,
        schedule_evidence_provider=None,
    ):
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)
        # Optional synchronous, independently reviewed calendar contract only.
        # No real adapter, URL fetch, environment flag or default proof exists.
        self.schedule_evidence_provider = schedule_evidence_provider
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.7,en;q=0.6",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _candidate_urls(url: str) -> list[str]:
        """Try both official host spellings without increasing total retry count."""
        candidates = [url]
        if url.startswith("https://www.boatrace.jp/"):
            candidates.append(url.replace("https://www.boatrace.jp/", "https://boatrace.jp/", 1))
        elif url.startswith("https://boatrace.jp/"):
            candidates.append(url.replace("https://boatrace.jp/", "https://www.boatrace.jp/", 1))
        return candidates

    async def _get_text(self, url: str) -> tuple[str, str]:
        last_error: Optional[Exception] = None
        candidates = self._candidate_urls(url)

        for attempt in range(1, self.max_retries + 1):
            request_url = candidates[(attempt - 1) % len(candidates)]
            try:
                async with self.semaphore:
                    response = await self.client.get(request_url)
                response.raise_for_status()
                acquired_at = dt.datetime.now(JST).isoformat()
                if request_url != url:
                    logger.info("HTTP fallback host succeeded")
                return response.text, acquired_at
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "HTTP attempt %s/%s failed type=%s",
                    attempt,
                    self.max_retries,
                    type(exc).__name__,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise IndexFailure("HTTP_FETCH_FAILED", "HTTP_RETRIES_EXHAUSTED") from None

    @staticmethod
    def _local_now(now_jst):
        if not isinstance(now_jst, dt.datetime) or now_jst.utcoffset() is None:
            raise IndexFailure("UNKNOWN_FAILURE", "NOW_JST_AWARE_REQUIRED")
        return now_jst.astimezone(JST)

    def _expected_race_numbers(self, now_jst):
        if self.schedule_evidence_provider is None:
            return FULL_RACE_NUMBERS
        try:
            evidence = self.schedule_evidence_provider(now_jst)
            decision = reviewed_schedule_decision(evidence, now_jst.strftime("%Y%m%d"))
        except Exception:
            logger.warning("Schedule evidence unavailable; conservative twelve-race expectation retained")
            return FULL_RACE_NUMBERS
        if decision["accepted"] and decision["event"] == "NO_RACE":
            raise NoRaceVerified()
        if decision["accepted"] and decision["event"] == "RACING_DAY":
            return decision["race_numbers"]
        logger.warning("Schedule evidence unverified; conservative twelve-race expectation retained")
        return FULL_RACE_NUMBERS

    async def fetch_race_index(self, now_jst: dt.datetime) -> RaceIndexSnapshot:
        now_jst = self._local_now(now_jst)
        expected = self._expected_race_numbers(now_jst)
        date_str = now_jst.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/raceindex?hd={date_str}&jcd=07"
        try:
            html, acquired_at = await self._get_text(url)
        except Exception:
            raise IndexFailure("HTTP_FETCH_FAILED", "HTTP_REQUEST_FAILED") from None
        try:
            races = parse_race_index(html, date_str, url, acquired_at, expected_race_numbers=expected)
        except ParserError:
            raise IndexFailure("HTML_PARSE_FAILED", "RACE_INDEX_HTML_INVALID") from None
        except Exception:
            raise IndexFailure("UNKNOWN_FAILURE", "RACE_INDEX_UNKNOWN_FAILURE") from None
        return RaceIndexSnapshot(date=date_str, races=races, source_url=url, acquired_at=acquired_at)

    async def fetch_tracking_race_index(self, now_jst: dt.datetime) -> RaceIndexSnapshot:
        """Non-official fallback used only to track the expected race universe/deadlines.

        Data from this method must never be treated as official confirmation for locks,
        closure, cancellation, or formal scoring.
        """
        now_jst = self._local_now(now_jst)
        expected = self._expected_race_numbers(now_jst)
        date_str = now_jst.strftime("%Y%m%d")
        year = now_jst.strftime("%Y")
        url = f"{self.TRACKING_FALLBACK_BASE}/{year}/{date_str}.json"
        try:
            text, acquired_at = await self._get_text(url)
        except Exception:
            raise IndexFailure("HTTP_FETCH_FAILED", "HTTP_REQUEST_FAILED") from None
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("TRACKING_JSON_DUPLICATE_KEY")
                result[key] = value
            return result

        def reject_constant(_):
            raise ValueError("TRACKING_JSON_NONFINITE")
        try:
            payload = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, TypeError, RecursionError):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_JSON_INVALID") from None
        if not isinstance(payload, dict):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_PAYLOAD_NOT_OBJECT")
        programs = payload.get("programs")
        if not isinstance(programs, dict):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_PROGRAMS_NOT_OBJECT")
        stadiums = programs.get("stadiums")
        if not isinstance(stadiums, dict):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_STADIUMS_NOT_OBJECT")
        keys = [key for key in ("7", "07") if key in stadiums]
        if not keys:
            raise IndexFailure("TRACKING_MISSING", "TRACKING_STADIUM_7_MISSING")
        if len(keys) != 1:
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_STADIUM_AMBIGUOUS")
        stadium = stadiums[keys[0]]
        if not isinstance(stadium, dict):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_STADIUM_NOT_OBJECT")
        for container in (payload, programs, stadium):
            if "date" in container and container["date"] not in (date_str, now_jst.date().isoformat()):
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_PAYLOAD_DATE_MISMATCH")
        if "stadium_number" in stadium and (type(stadium["stadium_number"]) not in (int, str)
                                             or stadium["stadium_number"] not in (7, "7", "07")):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_STADIUM_ID_MISMATCH")

        raw_races = stadium.get("races")
        if not isinstance(raw_races, dict):
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACES_NOT_OBJECT")
        if not raw_races:
            raise IndexFailure("TRACKING_MISSING", "TRACKING_RACES_MISSING")

        races = []
        seen = set()
        for race_key, raw in raw_races.items():
            if not isinstance(raw, dict):
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACE_NOT_OBJECT")
            if not isinstance(race_key, str) or not re.fullmatch(r"(?:0?[1-9]|1[0-2])", race_key):
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACE_NUMBER_INVALID")
            number = raw.get("race_number", race_key)
            if not (type(number) is int and 1 <= number <= 12
                    or isinstance(number, str) and re.fullmatch(r"(?:0?[1-9]|1[0-2])", number)):
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACE_NUMBER_INVALID")
            race_no = int(number)
            if race_no != int(race_key):
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACE_KEY_NUMBER_MISMATCH")
            if race_no in seen:
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_RACE_NUMBER_DUPLICATE")
            seen.add(race_no)

            closed_at = raw.get("closed_at")
            if not isinstance(closed_at, str) or not closed_at.strip():
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_DEADLINE_INVALID")
            closed_at = closed_at.strip()
            deadline = None
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", closed_at):
                try:
                    deadline = dt.datetime.strptime(closed_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
                except ValueError:
                    pass
            elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", closed_at) and not closed_at.endswith("-00:00"):
                offset_valid = (closed_at.endswith("Z") or int(closed_at[-5:-3]) <= 23 and int(closed_at[-2:]) <= 59)
                if offset_valid:
                    try:
                        deadline = dt.datetime.fromisoformat(closed_at.replace("Z", "+00:00")).astimezone(JST)
                    except ValueError:
                        pass
            if deadline is None:
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_DEADLINE_INVALID")
            if deadline.date() != now_jst.date():
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_DEADLINE_TARGET_DATE_MISMATCH")

            races.append(
                OfficialRaceInfo(
                    race_id=f"{date_str}_GAM_{race_no:02d}R",
                    official_deadline=deadline,
                    is_closed=False,
                    is_cancelled=False,
                    sales_status="FALLBACK_TRACKING_ONLY",
                    source_url=url,
                    acquired_at=acquired_at,
                )
            )

        if seen != expected:
            raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_EXPECTED_RACE_SET_MISMATCH")
        return RaceIndexSnapshot(
            date=date_str,
            races=sorted(races, key=lambda item: item.race_id),
            source_url=url,
            acquired_at=acquired_at,
        )

    async def fetch_live_data(self, race_id: str) -> LiveDataCompleteness:
        # race_id format validated by parsers/state layer usage
        date_str = race_id[:8]
        race_no = int(race_id[-3:-1])
        before_url = f"{self.BASE_URL}/beforeinfo?hd={date_str}&jcd=07&rno={race_no}"
        odds_url = f"{self.BASE_URL}/odds3t?hd={date_str}&jcd=07&rno={race_no}"

        result = LiveDataCompleteness(is_complete=False)
        missing = []

        async def fetch_before():
            html, acquired_at = await self._get_text(before_url)
            return prepare_beforeinfo(html, before_url, acquired_at).live_data

        async def fetch_odds():
            html, acquired_at = await self._get_text(odds_url)
            return parse_c_odds(html, odds_url, acquired_at)

        before_task = asyncio.create_task(fetch_before())
        odds_task = asyncio.create_task(fetch_odds())
        before_result, odds_result = await asyncio.gather(before_task, odds_task, return_exceptions=True)

        if isinstance(before_result, Exception):
            logger.error("beforeinfo unavailable/parser-failed for %s: %s", race_id, before_result)
            missing.extend(["beforeinfo", "exhibition_times_6boats", "entry_courses_6boats", "weather_info"])
            result.source_evidence["beforeinfo"] = SourceEvidence(
                url=before_url,
                acquired_at=dt.datetime.now(JST).isoformat(),
                status="ERROR",
                parser_status="ERROR",
            )
        else:
            result.exhibition_times = before_result.exhibition_times
            result.entry_courses = before_result.entry_courses
            # Compatibility projection only: not a six-boat coverage field.
            result.start_exhibition_st = before_result.start_exhibition_st
            result.start_exhibition_readings = dict(before_result.start_exhibition_readings)
            result.weather_info = before_result.weather_info
            result.source_evidence.update(before_result.source_evidence)
            missing.extend(before_result.missing_fields)

        if isinstance(odds_result, Exception):
            logger.error("odds3t unavailable/parser-failed for %s: %s", race_id, odds_result)
            missing.append("odds_3t")
            result.source_evidence["odds3t"] = SourceEvidence(
                url=odds_url,
                acquired_at=dt.datetime.now(JST).isoformat(),
                status="ERROR",
                parser_status="ERROR",
            )
        else:
            odds, evidence = odds_result
            result.odds_3t = odds
            result.source_evidence["odds3t"] = evidence

        result.missing_fields = sorted(set(missing))
        result.is_complete = (
            set(result.exhibition_times) == set(range(1, 7))
            and set(result.entry_courses) == set(range(1, 7))
            and bool(result.weather_info)
            and bool(result.odds_3t)
            and not result.missing_fields
        )
        return result
