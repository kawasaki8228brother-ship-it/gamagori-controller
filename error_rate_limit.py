from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class _ErrorState:
    last_emitted_at: float
    suppressed_count: int = 0


class RepeatedErrorRateLimiter:
    """Rate-limit only repeated error logs; never changes caller control flow."""

    def __init__(
        self,
        interval_seconds: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        self.interval_seconds = float(interval_seconds)
        self._clock = clock or time.monotonic
        self._states: dict[tuple[str, str, str], _ErrorState] = {}

    @staticmethod
    def signature(context: str, exc: Exception) -> tuple[str, str, str]:
        """Exact signature: call-site context + exception type + full message."""
        return (context, type(exc).__name__, str(exc))

    def emit(
        self,
        logger,
        *,
        context: str,
        prefix: str,
        exc: Exception,
    ) -> bool:
        """Emit first/periodic ERRORs and suppress only exact repeats in-between.

        Returns True when an ERROR record was emitted, False when the repeat was
        suppressed. Suppression state is process-local and therefore resets on
        process restart.
        """
        now = float(self._clock())
        key = self.signature(context, exc)
        state = self._states.get(key)

        if state is None:
            self._states[key] = _ErrorState(last_emitted_at=now)
            logger.error("%s: %s", prefix, exc)
            return True

        elapsed = now - state.last_emitted_at
        if elapsed < 0:
            # A monotonic clock should never move backwards. Fail open for
            # observability rather than suppressing on an invalid clock.
            self._states[key] = _ErrorState(last_emitted_at=now)
            logger.error("%s: %s (rate-limit clock moved backwards; state reset)", prefix, exc)
            return True

        if elapsed < self.interval_seconds:
            state.suppressed_count += 1
            logger.debug(
                "Suppressed repeated error context=%s type=%s count=%s",
                context,
                type(exc).__name__,
                state.suppressed_count,
            )
            return False

        logger.error(
            "%s: %s (suppressed %s occurrences since last report)",
            prefix,
            exc,
            state.suppressed_count,
        )
        state.last_emitted_at = now
        state.suppressed_count = 0
        return True
