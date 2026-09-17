from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import signal
import sys
from typing import Dict

from airtable import DryRunAirtableAdapter
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


class GamagoriController:
    def __init__(self):
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        if not self.dry_run:
            raise RuntimeError("v0.5.0 is SHADOW ONLY. DRY_RUN must remain true.")

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
            terminal_max_retries=int(os.getenv("TERMINAL_MAX_RETRIES", "3")),
        )
        self._stop = asyncio.Event()
        self._known_races: Dict[str, OfficialRaceInfo] = {}

    def request_stop(self) -> None:
        self._stop.set()

    async def run_watchdog_check(self, race_ids: list[str]) -> None:
        states = {s.race_id: s for s in await self.repo.list_all_states()}
        terminal_count = 0
        terminal_pending_count = 0
        terminal_failed_count = 0
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
                    "WATCHDOG race=%s TERMINAL reason=%s miss=%s terminal_event_id=%s "
                    "attempts=%s conflict=%s c_events=%s",
                    race_id,
                    st.terminal_reason.value if st.terminal_reason else "UNKNOWN",
                    st.terminal_missed_reason.value if st.terminal_missed_reason else "NONE",
                    st.terminal_event_id,
                    st.terminal_emit_attempts,
                    st.idempotency_conflict,
                    len(st.c_events),
                )
            elif st.status == RaceStatus.TERMINAL_PENDING:
                terminal_pending_count += 1
                logger.warning(
                    "WATCHDOG race=%s TERMINAL_PENDING candidate_reason=%s attempts=%s "
                    "failure_class=%s detail=%s",
                    race_id,
                    st.terminal_candidate_reason.value
                    if st.terminal_candidate_reason
                    else "UNKNOWN",
                    st.terminal_emit_attempts,
                    st.terminal_failure_class.value
                    if st.terminal_failure_class
                    else "NONE",
                    st.terminal_failure_detail or "NONE",
                )
            elif st.status == RaceStatus.TERMINAL_FAILED:
                terminal_failed_count += 1
                logger.critical(
                    "WATCHDOG race=%s TERMINAL_FAILED candidate_reason=%s attempts=%s "
                    "failure_class=%s detail=%s",
                    race_id,
                    st.terminal_candidate_reason.value
                    if st.terminal_candidate_reason
                    else "UNKNOWN",
                    st.terminal_emit_attempts,
                    st.terminal_failure_class.value
                    if st.terminal_failure_class
                    else "NONE",
                    st.terminal_failure_detail or "NONE",
                )
            else:
                logger.info(
                    "WATCHDOG race=%s status=%s dl_ver=%s c_events=%s errors=%s tracking_dl=%s",
                    race_id,
                    st.status.value,
                    st.deadline_version,
                    len(st.c_events),
                    st.consecutive_source_error_count,
                    st.tracking_deadline.isoformat()
                    if st.tracking_deadline
                    else "NONE",
                )
        logger.info(
            "WATCHDOG coverage TERMINAL=%s/%s TERMINAL_PENDING=%s/%s "
            "TERMINAL_FAILED=%s/%s terminal_reached=%s/%s "
            "terminal_in_progress=%s terminal_unrecorded=%s missed_observations=%s/%s",
            terminal_count,
            len(race_ids),
            terminal_pending_count,
            len(race_ids),
            terminal_failed_count,
            len(race_ids),
            terminal_count,
            len(race_ids),
            terminal_pending_count,
            terminal_failed_count,
            missed_count,
            len(race_ids),
        )

    async def start(self) -> None:
        logger.info(
            "Starting gamagori-controller v0.5.0 LIVE TRANSPORT SHADOW dry_run=%s db=%s",
            self.dry_run,
            self.db_path,
        )
        iteration = 0
        try:
            while not self._stop.is_set():
                iteration += 1
                now_jst = dt.datetime.now(JST)
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
                    logger.error("Poll #%s raceindex FAILED: %s", iteration, exc)

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
                        logger.error(
                            "Poll #%s tracking fallback FAILED: %s",
                            iteration,
                            fallback_exc,
                        )
                        if not self._known_races:
                            # Recover known races from persistent states if this is a restart during an outage.
                            persisted = await self.repo.list_all_states()
                            self._known_races = {
                                s.race_id: OfficialRaceInfo(
                                    race_id=s.race_id,
                                    official_deadline=s.tracking_deadline
                                    or s.official_deadline,
                                    is_closed=False,
                                    is_cancelled=False,
                                    sales_status="PERSISTED_LAST_KNOWN",
                                    source_url=s.tracking_source_url
                                    or "PERSISTED_LAST_KNOWN",
                                    acquired_at=(
                                        s.last_successful_official_fetch_at or now_jst
                                    ).isoformat(),
                                )
                                for s in persisted
                                if (s.tracking_deadline or s.official_deadline)
                                is not None
                                and s.status != RaceStatus.TERMINAL
                            }

                race_ids = sorted(self._known_races)
                if not race_ids:
                    logger.info(
                        "No verified/tracked Gamagori races currently known for %s",
                        now_jst.date(),
                    )
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
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_interval
                    )
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
