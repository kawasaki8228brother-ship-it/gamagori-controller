from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Dict, Optional

import httpx

from models import JST, LiveDataCompleteness, OfficialRaceInfo, RaceIndexSnapshot, SourceEvidence
from parsers import ParserError, parse_beforeinfo, parse_odds3t, parse_race_index

logger = logging.getLogger("gamagori-controller")


class OfficialDataFetcher:
    BASE_URL = "https://www.boatrace.jp/owpc/pc/race"

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
            headers={"User-Agent": "gamagori-controller-shadow/0.4.1"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_text(self, url: str) -> tuple[str, str]:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with self.semaphore:
                    response = await self.client.get(url)
                response.raise_for_status()
                acquired_at = dt.datetime.now(JST).isoformat()
                return response.text, acquired_at
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning("HTTP attempt %s/%s failed for %s: %s", attempt, self.max_retries, url, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
        raise RuntimeError(f"HTTP fetch failed after {self.max_retries} attempts: {url}: {last_error}")

    async def fetch_race_index(self, now_jst: dt.datetime) -> RaceIndexSnapshot:
        date_str = now_jst.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/raceindex?hd={date_str}&jcd=07"
        html, acquired_at = await self._get_text(url)
        races = parse_race_index(html, date_str, url, acquired_at)
        return RaceIndexSnapshot(date=date_str, races=races, source_url=url, acquired_at=acquired_at)

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
            return parse_beforeinfo(html, before_url, acquired_at)

        async def fetch_odds():
            html, acquired_at = await self._get_text(odds_url)
            return parse_odds3t(html, odds_url, acquired_at)

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
            result.start_exhibition_st = before_result.start_exhibition_st
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
