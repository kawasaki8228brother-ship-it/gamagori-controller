from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import signal
import sys
from typing import Dict

from airtable import DryRunAirtableAdapter
from error_rate_limit import RepeatedErrorRateLimiter
from models import JST, OfficialRaceInfo, RaceStatus
from official import OfficialDataFetcher
from repositories import MockBaselineRepository, SQLiteStateRepository
from state_machine import RaceStateMachine

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gamagori-controller")

REPEATED_ERROR_LOG_INTERVAL_SECONDS = 600.0
SQLITE_AUDIT_INTERVAL_SECONDS = 3600.0


class GamagoriController:
    def __init__(self):
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        if not self.dry_run:
            raise RuntimeError("v0.4.1 is SHADOW ONLY. DRY_RUN must remain true.")

        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
        self.db_path = os.getenv("STATE_DB_PATH", "./gamagori_shadow.db")
        self.repo = SQLiteStateRepository(self.db_path)
        self.baseline_repo = MockBaselineRepository()
        self.fetcher = OfficialDataFetcher(
            timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "8")),
            max_retries=int(os.getenv("HTTP_MAX_RETRIES", "3")),
            backoff_seconds=float(os.getenv("HTTP_BACKOFF_SECONDS", "0.5")),
            max_concurrency=int(os.getenv("HTTP_MAX_CONCURRENCY", "4")),
        )
        self.airtable = DryRunAirtableAdapter(self.repo)
        self.state_machine = RaceStateMachine(
            self.repo,
            self.baseline_repo,
            self.fetcher,
            self.airtable,
            source_error_grace_minutes=int(os.getenv("SOURCE_ERROR_GRACE_MINUTES", "20")),
        )
        self._stop = asyncio.Event()
        self._known_races: Dict[str, OfficialRaceInfo] = {}
        self._error_log_limiter = RepeatedErrorRateLimiter(
            REPEATED_ERROR_LOG_INTERVAL_SECONDS
        )
        self._last_sqlite_audit_at: dt.datetime | None = None

    def request_stop(self) -> None:
        self._stop.set()

    def _maybe_log_sqlite_audit(self, now_jst: dt.datetime, *, reason: str) -> None:
        if self._last_sqlite_audit_at is not None:
            elapsed = (now_jst - self._last_sqlite_audit_at).total_seconds()
            if 0 <= elapsed < SQLITE_AUDIT_INTERVAL_SECONDS:
                return

        # Mark the attempt time even when diagnostics fail so a transient
        # read error cannot create a tight retry/log loop.
        self._last_sqlite_audit_at = now_jst
        try:
            # Keep both import and call inside the safety boundary. Diagnostic
            # module failures must not prevent controller startup or polling.
            from sqlite_readonly_audit import SQLiteReadOnlyAuditor

            snapshot = SQLiteReadOnlyAuditor(
                self.db_path,
                busy_timeout_ms=2500,
            ).snapshot(
                now_jst.strftime("%Y%m%d"),
                process_now_jst=now_jst.isoformat(),
            )
            logger.info(
                "SQLITE_AUDIT_READONLY reason=%s snapshot=%s",
                reason,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        except Exception as exc:
            # Diagnostics must never change controller behavior or stop polling.
            logger.warning(
                "SQLITE_AUDIT_READONLY_FAILED reason=%s type=%s error=%s",
                reason,
                type(exc).__name__,
                exc,
            )

    async def run_watchdog_check(self, race_ids: list[str]) -> None:
        states = {s.race_id: s for s in await self.repo.list_all_states()}
        terminal_count = 0
        missed_count = 0
        for race_id in race_ids:
            st = states.get(race_id)
            if not st:
                logger.warning("WATCHDOG race=%s UNTOUCHED", race_id)
                continue
            if st.status == RaceStatus.TERMINAL:
                terminal_count += 1
                if st.terminal_missed_reason:
                    missed_count += 1
                logger.info(
                    "WATCHDOG race=%s TERMINAL reason=%s miss=%s c_events=%s",
                    race_id,
                    st.terminal_reason.value if st.terminal_reason else "UNKNOWN",
                    st.terminal_missed_reason.value if st.terminal_missed_reason else "NONE",
                    len(st.c_events),
                )
            else:
                logger.info(
                    "WATCHDOG race=%s status=%s dl_ver=%s c_events=%s errors=%s tracking_dl=%s",
                    race_id,
                    st.status.value,
                    st.deadline_version,
                    len(st.c_events),
                    st.consecutive_source_error_count,
                    st.tracking_deadline.isoformat() if st.tracking_deadline else "NONE",
                )
        logger.info(
            "WATCHDOG coverage terminal=%s/%s missed_observations=%s/%s",
            terminal_count,
            len(race_ids),
            missed_count,
            len(race_ids),
        )

    async def start(self) -> None:
        logger.info(
            "Starting gamagori-controller v0.4.1 LIVE TRANSPORT SHADOW dry_run=%s db=%s",
            self.dry_run,
            self.db_path,
        )
        iteration = 0
        try:
            while not self._stop.is_set():
                iteration += 1
                now_jst = dt.datetime.now(JST)
                self._maybe_log_sqlite_audit(
                    now_jst, reason="startup" if iteration == 1 else "hourly"
                )
                index_failed = False
                tracking_fallback_active = False
                try:
                    snapshot = await self.fetcher.fetch_race_index(now_jst)
                    self._known_races = {r.race_id: r for r in snapshot.races}
                    logger.info(
                        "Poll #%s raceindex OK races=%s acquired_at=%s",
                        iteration,
                        len(self._known_races),
                        snapshot.acquired_at,
                    )
                except Exception as exc:
                    index_failed = True
                    self._error_log_limiter.emit(
                        logger,
                        context="raceindex",
                        prefix=f"Poll #{iteration} raceindex FAILED",
                        exc=exc,
                    )

                    # Tracking-only fallback: discovers the expected Gamagori race universe and
                    # approximate published deadlines without promoting them to official evidence.
                    try:
                        tracking_snapshot = await self.fetcher.fetch_tracking_race_index(now_jst)
                        self._known_races = {r.race_id: r for r in tracking_snapshot.races}
                        tracking_fallback_active = True
                        logger.warning(
                            "Poll #%s TRACKING_FALLBACK OK races=%s source=%s acquired_at=%s; "
                            "NOT VALID FOR OFFICIAL LOCK/TIMING CONFIRMATION",
                            iteration,
                            len(self._known_races),
                            tracking_snapshot.source_url,
                            tracking_snapshot.acquired_at,
                        )
                    except Exception as fallback_exc:
                        self._error_log_limiter.emit(
                            logger,
                            context="tracking_fallback",
                            prefix=f"Poll #{iteration} tracking fallback FAILED",
                            exc=fallback_exc,
                        )
                        if not self._known_races:
                            # Recover known races from persistent states if this is a restart during an outage.
                            persisted = await self.repo.list_all_states()
                            self._known_races = {
                                s.race_id: OfficialRaceInfo(
                                    race_id=s.race_id,
                                    official_deadline=s.tracking_deadline or s.official_deadline,
                                    is_closed=False,
                                    is_cancelled=False,
                                    sales_status="PERSISTED_LAST_KNOWN",
                                    source_url=s.tracking_source_url or "PERSISTED_LAST_KNOWN",
                                    acquired_at=(s.last_successful_official_fetch_at or now_jst).isoformat(),
                                )
                                for s in persisted
                                if (s.tracking_deadline or s.official_deadline) is not None
                                and s.status != RaceStatus.TERMINAL
                            }

                race_ids = sorted(self._known_races)
                if not race_ids:
                    logger.info("No verified/tracked Gamagori races currently known for %s", now_jst.date())
                else:
                    tasks = []
                    for race_id in race_ids:
                        info = None if index_failed else self._known_races[race_id]
                        tracking_info = (
                            self._known_races[race_id]
                            if index_failed and tracking_fallback_active
                            else None
                        )
                        tasks.append(
                            self.state_machine.process_race(
                                race_id,
                                now_jst,
                                official_info=info,
                                official_fetch_failed=index_failed,
                                tracking_info=tracking_info,
                            )
                        )
                    await asyncio.gather(*tasks)

                    if iteration % 5 == 0:
                        await self.run_watchdog_check(race_ids)

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            await self.fetcher.close()
            logger.info("Controller stopped cleanly.")


def install_signal_handlers(controller: GamagoriController) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, controller.request_stop)
        except NotImplementedError:
            pass


async def _amain() -> None:
    controller = GamagoriController()
    install_signal_handlers(controller)
    await controller.start()


if __name__ == "__main__":
    asyncio.run(_amain())
