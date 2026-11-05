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
from raceindex_scope import RaceScopeError, filter_current_races, recover_current_states, validate_index_snapshot
from raceindex_status import IndexFailure, NoRaceVerified, classify_index_exception
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

    def _log_index_failure(self, *, context: str, iteration: int, exc: Exception) -> dict:
        outcome = classify_index_exception(exc)
        # Do not feed source URLs, proxy values or arbitrary exception text into
        # the repeated-error logger. The diagnostic is a fixed classification.
        self._error_log_limiter.emit(
            logger, context=context,
            prefix=f"Poll #{iteration} {context} FAILED status={outcome['kind']}",
            exc=RuntimeError(f"{outcome['kind']}:{outcome['reason']}"))
        return outcome

    async def _refresh_race_universe(self, now_jst: dt.datetime, iteration: int) -> tuple[bool, bool]:
        previous_count = len(self._known_races)
        self._known_races = filter_current_races(self._known_races, now_jst)
        if len(self._known_races) != previous_count:
            logger.warning("Poll #%s STALE_RACE_SCOPE_EXCLUDED count=%s target_day=%s", iteration,
                           previous_count - len(self._known_races), now_jst.astimezone(JST).strftime("%Y%m%d"))
        self._last_index_outcome = {"official": "NOT_ATTEMPTED", "tracking": "NOT_ATTEMPTED", "persisted": "NOT_NEEDED"}
        try:
            snapshot = await self.fetcher.fetch_race_index(now_jst)
            try:
                accepted = validate_index_snapshot(snapshot, now_jst)
            except RaceScopeError:
                raise IndexFailure("HTML_PARSE_FAILED", "OFFICIAL_SNAPSHOT_SCOPE_INVALID") from None
            self._known_races = accepted
            self._last_index_outcome["official"] = "OFFICIAL_INDEX_PARSED"
            logger.info("Poll #%s raceindex OK races=%s acquired_at=%s", iteration, len(accepted), snapshot.acquired_at)
            return False, False
        except NoRaceVerified:
            self._known_races = {}
            self._last_index_outcome["official"] = "NO_RACE_VERIFIED"
            logger.info("Poll #%s NO_RACE_VERIFIED basis=INDEPENDENT_OFFICIAL_SCHEDULE target_day=%s",
                        iteration, now_jst.astimezone(JST).strftime("%Y%m%d"))
            return False, False
        except Exception as exc:
            outcome = self._log_index_failure(context="raceindex", iteration=iteration, exc=exc)
            self._last_index_outcome["official"] = outcome["kind"]

        try:
            tracking = await self.fetcher.fetch_tracking_race_index(now_jst)
            try:
                accepted = validate_index_snapshot(tracking, now_jst)
            except RaceScopeError:
                raise IndexFailure("TRACKING_PARSE_FAILED", "TRACKING_SNAPSHOT_SCOPE_INVALID") from None
            self._known_races = accepted
            self._last_index_outcome["tracking"] = "TRACKING_ONLY"
            logger.warning("Poll #%s TRACKING_FALLBACK OK races=%s; NOT VALID FOR OFFICIAL LOCK/TIMING CONFIRMATION",
                           iteration, len(accepted))
            return True, True
        except NoRaceVerified:
            # This exception can also originate from the independent schedule
            # provider consulted by the fallback. It is never inferred from a
            # missing stadium or an empty tracking payload.
            self._known_races = {}
            self._last_index_outcome["tracking"] = "NO_RACE_VERIFIED"
            logger.info("Poll #%s NO_RACE_VERIFIED basis=INDEPENDENT_OFFICIAL_SCHEDULE target_day=%s",
                        iteration, now_jst.astimezone(JST).strftime("%Y%m%d"))
            return False, False
        except Exception as exc:
            outcome = self._log_index_failure(context="tracking_fallback", iteration=iteration, exc=exc)
            self._last_index_outcome["tracking"] = outcome["kind"]
        if not self._known_races:
            try:
                persisted = await self.repo.list_all_states()
                self._known_races = recover_current_states(persisted, now_jst)
                self._last_index_outcome["persisted"] = "CURRENT_DAY_UNCONFIRMED_PROJECTION"
            except Exception:
                self._known_races = {}
                self._last_index_outcome["persisted"] = "READ_FAILED_OR_SCOPE_INVALID"
                logger.warning("Poll #%s PERSISTED_RACE_RECOVERY_UNVERIFIED; no processing universe established", iteration)
        return True, False

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
                index_failed, tracking_fallback_active = await self._refresh_race_universe(now_jst, iteration)

                # A fetch/retry crossing midnight must not dispatch the previous
                # day's universe under the new civil date. No terminal/replay
                # action is inferred; the next poll obtains a fresh target day.
                dispatch_day = dt.datetime.now(JST).date()
                if dispatch_day != now_jst.date():
                    self._known_races = {}
                    logger.warning("Poll #%s DAY_ROLLOVER_DURING_INDEX_POLL; processing skipped", iteration)

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
