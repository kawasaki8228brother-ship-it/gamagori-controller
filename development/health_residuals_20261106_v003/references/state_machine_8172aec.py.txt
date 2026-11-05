from __future__ import annotations

import datetime as dt
import logging
import uuid
from typing import Callable, Optional

from airtable import DryRunAirtableAdapter
from closing import ClosingEvaluator
from models import (
    EventRecord,
    JST,
    MissedObservationReason,
    OfficialRaceInfo,
    RaceState,
    RaceStatus,
    TerminalReason,
)
from official import OfficialDataFetcher
from repositories import BaselineRepository, SQLiteStateRepository

logger = logging.getLogger("gamagori-controller")


class RaceStateMachine:
    def __init__(
        self,
        repository: SQLiteStateRepository,
        baseline_repo: BaselineRepository,
        fetcher: OfficialDataFetcher,
        airtable: DryRunAirtableAdapter,
        source_error_grace_minutes: int = 20,
        *,
        clock: Optional[Callable[[], dt.datetime]] = None,
    ):
        self.repo = repository
        self.baseline_repo = baseline_repo
        self.fetcher = fetcher
        self.airtable = airtable
        self.source_error_grace = dt.timedelta(minutes=source_error_grace_minutes)
        # Production uses a fresh wall-clock read; tests supply their own clock.
        # Never silently reuse process_race(now_jst) as the post-fetch timestamp.
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock if clock is not None else lambda: dt.datetime.now(JST)

    def _read_clock(self, not_before: dt.datetime) -> dt.datetime:
        value = self._clock()
        if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return an aware datetime")
        if value < not_before:
            raise ValueError("clock moved backwards relative to this processing stage")
        return value.astimezone(JST)

    def _classify_miss(self, state: RaceState) -> Optional[MissedObservationReason]:
        current = state.window_state()
        # Classification is per deadline_version. A valid v1 C event must not hide a v2 miss.
        if current.c_event_emitted:
            return None
        if current.window_skipped_by_shortening:
            return MissedObservationReason.MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE
        if state.last_error_streak_before_success > 0 or current.source_error_streak_max > 0:
            return MissedObservationReason.MISSED_SOURCE_ERROR
        if current.data_wait_seen or current.closing_window_entered:
            return MissedObservationReason.MISSED_DATA_INCOMPLETE
        return None

    async def _emit_terminal(
        self,
        state: RaceState,
        reason: TerminalReason,
        now_jst: dt.datetime,
        official_info: Optional[OfficialRaceInfo],
        officially_confirmed: bool,
    ) -> RaceState:
        state.status = RaceStatus.TERMINAL
        state.terminal_reason = reason
        state.terminal_missed_reason = self._classify_miss(state)
        terminal_uuid = str(uuid.uuid4())
        official_deadline = state.official_deadline or (official_info.official_deadline if official_info else None)
        payload = {
            "schema_version": 1,
            "model_version": "v0.4.1_shadow",
            "controller_version": "v0.4.1",
            "race_id": state.race_id,
            "source": "Observer_C",
            "event_type": "RACE_TERMINAL",
            "terminal_reason": reason.value,
            "terminal_missed_reason": state.terminal_missed_reason.value if state.terminal_missed_reason else None,
            "officially_confirmed": officially_confirmed,
            "official_deadline": official_deadline.isoformat() if official_deadline else None,
            "tracking_deadline": state.tracking_deadline.isoformat() if state.tracking_deadline else None,
            "tracking_source_url": state.tracking_source_url,
            "tracking_source_kind": state.tracking_source_kind,
            "deadline_version": state.deadline_version,
            "c_event_count": len(state.c_events),
            "current_version_c_event_emitted": state.window_state().c_event_emitted,
            "total_source_error_count": state.total_source_error_count,
            "last_error_streak_before_success": state.last_error_streak_before_success,
            "window_history": {k: v.model_dump() for k, v in state.window_history.items()},
            "observed_at": now_jst.isoformat(),
        }
        record = EventRecord(
            event_uuid=terminal_uuid,
            idempotency_key=f"{state.race_id}_TERMINAL_{reason.value}",
            race_id=state.race_id,
            event_type="RACE_TERMINAL",
            source="Observer_C",
            deadline_version=state.deadline_version,
            payload=payload,
            observed_at=now_jst.isoformat(),
            official_deadline=official_deadline.isoformat() if official_deadline else "",
            payload_hash=DryRunAirtableAdapter.generate_canonical_hash(payload),
        )
        success, _, persisted_uuid = await self.airtable.append_event(record)
        if success:
            state.terminal_event_id = persisted_uuid
        await self.repo.save_race_state(state)
        logger.warning(
            "[%s] TERMINAL reason=%s miss=%s c_events=%s confirmed=%s",
            state.race_id,
            reason.value,
            state.terminal_missed_reason.value if state.terminal_missed_reason else "NONE",
            len(state.c_events),
            officially_confirmed,
        )
        return state

    async def process_race(
        self,
        race_id: str,
        now_jst: dt.datetime,
        official_info: Optional[OfficialRaceInfo],
        official_fetch_failed: bool = False,
        tracking_info: Optional[OfficialRaceInfo] = None,
    ) -> RaceState:
        state = await self.repo.get_race_state(race_id) or RaceState(race_id=race_id)
        if state.status == RaceStatus.TERMINAL:
            return state

        state.last_checked_at = now_jst

        if tracking_info is not None:
            state.tracking_deadline = tracking_info.official_deadline
            state.tracking_source_url = tracking_info.source_url
            state.tracking_source_kind = tracking_info.sales_status

        if official_fetch_failed or official_info is None:
            state.consecutive_source_error_count += 1
            state.total_source_error_count += 1
            current = state.window_state()
            current.source_error_streak_max = max(
                current.source_error_streak_max, state.consecutive_source_error_count
            )

            # Formal timing uses only official_deadline. A non-official tracking deadline
            # is permitted only to prevent an unresolved race from hanging forever.
            timeout_deadline = state.official_deadline or state.tracking_deadline
            if timeout_deadline and now_jst > timeout_deadline + self.source_error_grace:
                state.last_error_streak_before_success = state.consecutive_source_error_count
                return await self._emit_terminal(
                    state,
                    TerminalReason.SOURCE_ERROR_TIMEOUT,
                    now_jst,
                    official_info=None,
                    officially_confirmed=False,
                )

            await self.repo.save_race_state(state)
            logger.warning(
                "[%s] official source error streak=%s total=%s tracking_deadline=%s",
                race_id,
                state.consecutive_source_error_count,
                state.total_source_error_count,
                state.tracking_deadline.isoformat() if state.tracking_deadline else "NONE",
            )
            return state

        previous_error_streak = state.consecutive_source_error_count
        state.last_error_streak_before_success = previous_error_streak
        state.consecutive_source_error_count = 0
        state.last_successful_official_fetch_at = now_jst

        if official_info.is_cancelled:
            if state.official_deadline is None:
                state.official_deadline = official_info.official_deadline
            return await self._emit_terminal(
                state, TerminalReason.CANCELLED, now_jst, official_info, officially_confirmed=True
            )
        if official_info.is_closed:
            if state.official_deadline is None:
                state.official_deadline = official_info.official_deadline
            return await self._emit_terminal(
                state, TerminalReason.OFFICIALLY_CLOSED, now_jst, official_info, officially_confirmed=True
            )

        old_deadline = state.official_deadline
        old_version = state.deadline_version
        old_window = state.window_state(old_version)
        if old_deadline is not None:
            diff_seconds = (official_info.official_deadline - old_deadline).total_seconds()
            if abs(diff_seconds) >= 30.0:
                old_remaining = ClosingEvaluator.calculate_time_to_deadline(old_deadline, now_jst)
                new_remaining = ClosingEvaluator.calculate_time_to_deadline(official_info.official_deadline, now_jst)
                new_status = ClosingEvaluator.evaluate_window_status(new_remaining)

                skipped_by_shortening = (
                    diff_seconds < 0
                    and not old_window.closing_window_entered
                    and old_remaining > 5.0
                    and new_status in {"FREEZE_ZONE", "SAFE_STOP"}
                )

                state.deadline_version += 1
                new_window = state.window_state(state.deadline_version)
                new_window.window_skipped_by_shortening = skipped_by_shortening
                state.status = RaceStatus.REOPENED
                logger.warning(
                    "[%s] DEADLINE_%s %s -> %s version=%s skipped_window=%s",
                    race_id,
                    "EXTENDED" if diff_seconds > 0 else "SHORTENED",
                    old_deadline.isoformat(),
                    official_info.official_deadline.isoformat(),
                    state.deadline_version,
                    skipped_by_shortening,
                )

        state.official_deadline = official_info.official_deadline
        remaining_minutes = ClosingEvaluator.calculate_time_to_deadline(state.official_deadline, now_jst)
        window_status = ClosingEvaluator.evaluate_window_status(remaining_minutes)
        current = state.window_state()

        if window_status == "TOO_EARLY":
            state.status = RaceStatus.PENDING
            await self.repo.save_race_state(state)
            return state

        if window_status == "SAFE_STOP":
            state.status = RaceStatus.SAFE_STOP if not current.c_event_emitted else RaceStatus.C_EVENT_DONE
            await self.repo.save_race_state(state)
            return state

        if window_status == "FREEZE_ZONE":
            state.status = RaceStatus.FREEZE_ZONE if not current.c_event_emitted else RaceStatus.C_EVENT_DONE
            await self.repo.save_race_state(state)
            return state

        # IN_CLOSING_WINDOW
        current.closing_window_entered = True
        if current.c_event_emitted:
            state.status = RaceStatus.C_EVENT_DONE
            await self.repo.save_race_state(state)
            return state

        state.status = RaceStatus.CLOSING_WINDOW
        live_data = await self.fetcher.fetch_live_data(race_id)
        if not live_data.is_complete:
            current.data_wait_seen = True
            state.status = RaceStatus.DATA_WAIT
            await self.repo.save_race_state(state)
            logger.info("[%s] DATA_WAIT missing=%s", race_id, live_data.missing_fields)
            return state

        baseline_a_id, baseline_b_id = await self.baseline_repo.get_latest_baseline_ids(race_id)
        # observed_at is the freeze time after all data acquisition/baseline reads are complete.
        try:
            observed_at = self._read_clock(now_jst)
        except Exception as exc:
            # A broken test or wall clock must not create a closing observation.
            state.status = RaceStatus.SAFE_STOP
            await self.repo.save_race_state(state)
            logger.warning("[%s] invalid observation clock; event suppressed (%s)", race_id, type(exc).__name__)
            return state
        if observed_at >= state.official_deadline:
            state.status = RaceStatus.SAFE_STOP
            await self.repo.save_race_state(state)
            logger.warning("[%s] evaluation completed after deadline; event suppressed", race_id)
            return state

        c_a_5pts, c_b_5pts, payload = ClosingEvaluator.evaluate_closing_signals(
            race_id=race_id,
            deadline_version=state.deadline_version,
            official_deadline_iso=state.official_deadline.isoformat(),
            baseline_a_id=baseline_a_id,
            baseline_b_id=baseline_b_id,
            live_data=live_data,
            observed_at_iso=observed_at.isoformat(),
        )
        event_uuid = str(uuid.uuid4())
        record = EventRecord(
            event_uuid=event_uuid,
            idempotency_key=f"{race_id}_C_v{state.deadline_version}",
            race_id=race_id,
            event_type="CLOSING_OBSERVATION",
            source="Observer_C",
            deadline_version=state.deadline_version,
            baseline_a_event_id=baseline_a_id,
            baseline_b_event_id=baseline_b_id,
            c_a_predictions=c_a_5pts,
            c_b_predictions=c_b_5pts,
            payload=payload,
            observed_at=observed_at.isoformat(),
            official_deadline=state.official_deadline.isoformat(),
            payload_hash=DryRunAirtableAdapter.generate_canonical_hash(payload),
        )
        # Recheck after evaluation/serialization too. This is a pre-append
        # safety check, NOT a guarantee that storage completes before deadline.
        try:
            append_at = self._read_clock(observed_at)
        except Exception as exc:
            state.status = RaceStatus.SAFE_STOP
            await self.repo.save_race_state(state)
            logger.warning("[%s] invalid pre-append clock; event suppressed (%s)", race_id, type(exc).__name__)
            return state
        if append_at >= state.official_deadline:
            state.status = RaceStatus.SAFE_STOP
            await self.repo.save_race_state(state)
            logger.warning("[%s] pre-append deadline reached; event suppressed", race_id)
            return state
        success, _, persisted_uuid = await self.airtable.append_event(record)
        if success:
            if persisted_uuid not in state.c_events:
                state.c_events.append(persisted_uuid)
            current.c_event_emitted = True
            state.status = RaceStatus.C_EVENT_DONE
            await self.repo.save_race_state(state)
            logger.info("[%s] C_EVENT_DONE v%s uuid=%s", race_id, state.deadline_version, persisted_uuid)
        return state
