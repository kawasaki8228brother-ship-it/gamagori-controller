from __future__ import annotations

import datetime as dt
import logging
import uuid
from typing import Callable, Optional

from airtable import DryRunAirtableAdapter
from closing import ClosingEvaluator
from models import (
    AppendOutcomeStatus,
    EventRecord,
    FailureClass,
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
        terminal_max_retries: int = 3,
        now_provider: Optional[Callable[[], dt.datetime]] = None,
    ):
        self.repo = repository
        self.baseline_repo = baseline_repo
        self.fetcher = fetcher
        self.airtable = airtable
        self.source_error_grace = dt.timedelta(minutes=source_error_grace_minutes)
        self.terminal_max_retries = max(1, terminal_max_retries)
        self.now_provider = now_provider or (lambda: dt.datetime.now(JST))

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

    @staticmethod
    def _terminal_identity_hash(race_id: str, reason: TerminalReason) -> str:
        return DryRunAirtableAdapter.generate_canonical_hash(
            {
                "race_id": race_id,
                "terminal_reason": reason.value,
            }
        )

    @staticmethod
    def _closing_identity_hash(race_id: str, deadline_version: int) -> str:
        return DryRunAirtableAdapter.generate_canonical_hash(
            {
                "event_type": "CLOSING_OBSERVATION",
                "race_id": race_id,
                "deadline_version": deadline_version,
            }
        )

    @staticmethod
    def _reason_from_payload(payload: Optional[dict]) -> Optional[TerminalReason]:
        if not payload:
            return None
        value = payload.get("terminal_reason")
        if not value:
            return None
        try:
            return TerminalReason(value)
        except ValueError:
            return None

    @staticmethod
    def _miss_from_payload(payload: Optional[dict]) -> Optional[MissedObservationReason]:
        if not payload:
            return None
        value = payload.get("terminal_missed_reason")
        if not value:
            return None
        try:
            return MissedObservationReason(value)
        except ValueError:
            return None

    async def _emit_terminal(
        self,
        state: RaceState,
        reason: TerminalReason,
        now_jst: dt.datetime,
        official_info: Optional[OfficialRaceInfo],
        officially_confirmed: bool,
    ) -> RaceState:
        candidate_miss = self._classify_miss(state)
        official_deadline = state.official_deadline or (
            official_info.official_deadline if official_info else None
        )

        # Persist intent before the Event append. A crash after Event persistence but before
        # final State commit will restart from TERMINAL_PENDING and reconcile by idempotency.
        state.status = RaceStatus.TERMINAL_PENDING
        state.terminal_candidate_reason = reason
        state.terminal_emit_attempts += 1
        state.terminal_failure_class = None
        state.terminal_failure_detail = None
        await self.repo.save_race_state(state)

        terminal_uuid = str(uuid.uuid4())
        payload = {
            "schema_version": 1,
            "model_version": "v0.5.0_shadow",
            "controller_version": "v0.5.0",
            "race_id": state.race_id,
            "source": "Observer_C",
            "event_type": "RACE_TERMINAL",
            "terminal_reason": reason.value,
            "terminal_missed_reason": candidate_miss.value if candidate_miss else None,
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
            "terminal_emit_attempts": state.terminal_emit_attempts,
            "observed_at": now_jst.isoformat(),
        }
        record = EventRecord(
            event_uuid=terminal_uuid,
            idempotency_key=f"{state.race_id}_TERMINAL",
            identity_hash=self._terminal_identity_hash(state.race_id, reason),
            race_id=state.race_id,
            event_type="RACE_TERMINAL",
            source="Observer_C",
            deadline_version=state.deadline_version,
            payload=payload,
            observed_at=now_jst.isoformat(),
            official_deadline=official_deadline.isoformat() if official_deadline else "",
            payload_hash=DryRunAirtableAdapter.generate_canonical_hash(payload),
        )
        outcome = await self.airtable.append_event(record)

        if outcome.status in {
            AppendOutcomeStatus.CREATED,
            AppendOutcomeStatus.DUPLICATE_MATCH,
            AppendOutcomeStatus.DUPLICATE_CONFLICT,
        }:
            canonical_payload = (
                outcome.existing_payload
                if outcome.status != AppendOutcomeStatus.CREATED
                else payload
            )
            canonical_reason = self._reason_from_payload(canonical_payload)
            canonical_miss = self._miss_from_payload(canonical_payload)

            state.terminal_event_id = outcome.event_uuid
            state.terminal_reason = canonical_reason or reason
            state.terminal_missed_reason = canonical_miss
            state.terminal_failure_class = None
            state.terminal_failure_detail = None
            state.idempotency_conflict = (
                outcome.status == AppendOutcomeStatus.DUPLICATE_CONFLICT
            )
            state.status = RaceStatus.TERMINAL
            await self.repo.save_race_state(state)

            if outcome.status == AppendOutcomeStatus.DUPLICATE_CONFLICT:
                logger.critical(
                    "[%s] DUPLICATE_CONFLICT terminal key=%s candidate_reason=%s "
                    "existing_reason=%s existing_uuid=%s",
                    state.race_id,
                    record.idempotency_key,
                    reason.value,
                    canonical_reason.value if canonical_reason else "UNKNOWN",
                    outcome.event_uuid,
                )

            logger.warning(
                "[%s] TERMINAL reason=%s miss=%s c_events=%s confirmed=%s "
                "attempts=%s append_outcome=%s",
                state.race_id,
                state.terminal_reason.value if state.terminal_reason else "UNKNOWN",
                state.terminal_missed_reason.value if state.terminal_missed_reason else "NONE",
                len(state.c_events),
                officially_confirmed,
                state.terminal_emit_attempts,
                outcome.status.value,
            )
            return state

        failure_class = outcome.failure_class or FailureClass.UNKNOWN
        state.terminal_failure_class = failure_class
        state.terminal_failure_detail = outcome.message or "APPEND_FAILED"
        state.terminal_event_id = None
        state.terminal_reason = None
        state.terminal_missed_reason = None

        if (
            failure_class == FailureClass.NON_RETRYABLE
            or state.terminal_emit_attempts >= self.terminal_max_retries
        ):
            state.status = RaceStatus.TERMINAL_FAILED
            logger.critical(
                "[%s] TERMINAL_FAILED candidate_reason=%s attempts=%s/%s "
                "failure_class=%s detail=%s",
                state.race_id,
                reason.value,
                state.terminal_emit_attempts,
                self.terminal_max_retries,
                failure_class.value,
                state.terminal_failure_detail,
            )
        else:
            state.status = RaceStatus.TERMINAL_PENDING
            logger.error(
                "[%s] TERMINAL_PENDING candidate_reason=%s attempts=%s/%s "
                "failure_class=%s detail=%s",
                state.race_id,
                reason.value,
                state.terminal_emit_attempts,
                self.terminal_max_retries,
                failure_class.value,
                state.terminal_failure_detail,
            )

        await self.repo.save_race_state(state)
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
        if state.status == RaceStatus.TERMINAL_FAILED:
            return state
        if state.status == RaceStatus.TERMINAL_PENDING:
            if state.terminal_candidate_reason is None:
                state.status = RaceStatus.TERMINAL_FAILED
                state.terminal_failure_class = FailureClass.NON_RETRYABLE
                state.terminal_failure_detail = "PENDING_WITHOUT_CANDIDATE_REASON"
                await self.repo.save_race_state(state)
                logger.critical("[%s] TERMINAL_FAILED pending state has no candidate reason", race_id)
                return state
            return await self._emit_terminal(
                state,
                state.terminal_candidate_reason,
                now_jst,
                official_info,
                officially_confirmed=(
                    state.terminal_candidate_reason != TerminalReason.SOURCE_ERROR_TIMEOUT
                ),
            )

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
                new_remaining = ClosingEvaluator.calculate_time_to_deadline(
                    official_info.official_deadline, now_jst
                )
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
        remaining_minutes = ClosingEvaluator.calculate_time_to_deadline(
            state.official_deadline, now_jst
        )
        window_status = ClosingEvaluator.evaluate_window_status(remaining_minutes)
        current = state.window_state()

        if window_status == "TOO_EARLY":
            state.status = RaceStatus.PENDING
            await self.repo.save_race_state(state)
            return state

        if window_status == "SAFE_STOP":
            state.status = (
                RaceStatus.SAFE_STOP
                if not current.c_event_emitted
                else RaceStatus.C_EVENT_DONE
            )
            await self.repo.save_race_state(state)
            return state

        if window_status == "FREEZE_ZONE":
            state.status = (
                RaceStatus.FREEZE_ZONE
                if not current.c_event_emitted
                else RaceStatus.C_EVENT_DONE
            )
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
        observed_at = self.now_provider()
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
            identity_hash=self._closing_identity_hash(race_id, state.deadline_version),
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
        outcome = await self.airtable.append_event(record)
        if outcome.status in {
            AppendOutcomeStatus.CREATED,
            AppendOutcomeStatus.DUPLICATE_MATCH,
        }:
            persisted_uuid = outcome.event_uuid
            if persisted_uuid and persisted_uuid not in state.c_events:
                state.c_events.append(persisted_uuid)
            current.c_event_emitted = True
            state.status = RaceStatus.C_EVENT_DONE
            await self.repo.save_race_state(state)
            logger.info(
                "[%s] C_EVENT_DONE v%s uuid=%s outcome=%s",
                race_id,
                state.deadline_version,
                persisted_uuid,
                outcome.status.value,
            )
        elif outcome.status == AppendOutcomeStatus.DUPLICATE_CONFLICT:
            logger.critical(
                "[%s] C_EVENT DUPLICATE_CONFLICT v%s key=%s existing_uuid=%s",
                race_id,
                state.deadline_version,
                record.idempotency_key,
                outcome.event_uuid,
            )
        return state
