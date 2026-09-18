from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Dict, Optional

import httpx

from models import JST, LiveDataCompleteness, OfficialRaceInfo, RaceIndexSnapshot, SourceEvidence
from parsers import ParserError, parse_race_index
from beforeinfo_bridge import prepare_beforeinfo
from odds_bridge import parse_c_odds

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
    ):
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.semaphore = asyncio.Semaphore(max_concurrency)
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
                    logger.info("HTTP fallback host succeeded: %s", request_url)
                return response.text, acquired_at
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "HTTP attempt %s/%s failed for %s: type=%s repr=%r",
                    attempt,
                    self.max_retries,
                    request_url,
                    type(exc).__name__,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"HTTP fetch failed after {self.max_retries} attempts: {url}: "
            f"{type(last_error).__name__ if last_error else 'UnknownError'} {last_error!r}"
        )

    async def fetch_race_index(self, now_jst: dt.datetime) -> RaceIndexSnapshot:
        date_str = now_jst.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/raceindex?hd={date_str}&jcd=07"
        html, acquired_at = await self._get_text(url)
        races = parse_race_index(html, date_str, url, acquired_at)
        return RaceIndexSnapshot(date=date_str, races=races, source_url=url, acquired_at=acquired_at)

    async def fetch_tracking_race_index(self, now_jst: dt.datetime) -> RaceIndexSnapshot:
        """Non-official fallback used only to track the expected race universe/deadlines.

        Data from this method must never be treated as official confirmation for locks,
        closure, cancellation, or formal scoring.
        """
        date_str = now_jst.strftime("%Y%m%d")
        year = now_jst.strftime("%Y")
        url = f"{self.TRACKING_FALLBACK_BASE}/{year}/{date_str}.json"
        text, acquired_at = await self._get_text(url)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"tracking fallback returned invalid JSON: {url}: {exc}") from exc

        stadiums = payload.get("programs", {}).get("stadiums", {})
        stadium = stadiums.get("7") or stadiums.get("07")
        if not isinstance(stadium, dict):
            raise RuntimeError(f"tracking fallback has no Gamagori stadium 7: {url}")

        raw_races = stadium.get("races", {})
        if not isinstance(raw_races, dict):
            raise RuntimeError(f"tracking fallback races is not an object: {url}")

        races = []
        for race_key, raw in raw_races.items():
            if not isinstance(raw, dict):
                continue
            try:
                race_no = int(raw.get("race_number", race_key))
            except (TypeError, ValueError):
                continue
            if not 1 <= race_no <= 12:
                continue

            closed_at = raw.get("closed_at")
            if not isinstance(closed_at, str) or not closed_at.strip():
                continue
            try:
                deadline = dt.datetime.strptime(closed_at.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
            except ValueError:
                try:
                    deadline = dt.datetime.fromisoformat(closed_at.strip())
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=JST)
                    else:
                        deadline = deadline.astimezone(JST)
                except ValueError:
                    continue

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

        if not races:
            raise RuntimeError(f"tracking fallback returned no usable Gamagori races: {url}")
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
