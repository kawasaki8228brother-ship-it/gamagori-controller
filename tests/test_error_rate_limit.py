import logging

from error_rate_limit import RepeatedErrorRateLimiter
from parsers import ParserError


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _errors(caplog):
    return [record for record in caplog.records if record.levelno == logging.ERROR]


def test_first_occurrence_is_always_error(caplog):
    clock = FakeClock()
    limiter = RepeatedErrorRateLimiter(600, clock=clock)
    logger = logging.getLogger("test.rate_limit.first")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        emitted = limiter.emit(
            logger,
            context="raceindex",
            prefix="Poll #1 raceindex FAILED",
            exc=ParserError("raceindex: no race rows with race number + deadline found"),
        )

    assert emitted is True
    assert len(_errors(caplog)) == 1


def test_exact_repeat_is_suppressed_inside_window(caplog):
    clock = FakeClock()
    limiter = RepeatedErrorRateLimiter(600, clock=clock)
    logger = logging.getLogger("test.rate_limit.repeat")
    exc = ParserError("raceindex: no race rows with race number + deadline found")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        assert limiter.emit(
            logger, context="raceindex", prefix="Poll #1 raceindex FAILED", exc=exc
        )
        clock.advance(40)
        assert not limiter.emit(
            logger, context="raceindex", prefix="Poll #2 raceindex FAILED", exc=exc
        )
        clock.advance(40)
        assert not limiter.emit(
            logger, context="raceindex", prefix="Poll #3 raceindex FAILED", exc=exc
        )

    assert len(_errors(caplog)) == 1


def test_periodic_error_reports_suppressed_count(caplog):
    clock = FakeClock()
    limiter = RepeatedErrorRateLimiter(600, clock=clock)
    logger = logging.getLogger("test.rate_limit.periodic")
    exc = RuntimeError(
        "tracking fallback has no Gamagori stadium 7: https://example.invalid/20260921.json"
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        limiter.emit(
            logger,
            context="tracking_fallback",
            prefix="Poll #1 tracking fallback FAILED",
            exc=exc,
        )
        clock.advance(100)
        limiter.emit(
            logger,
            context="tracking_fallback",
            prefix="Poll #2 tracking fallback FAILED",
            exc=exc,
        )
        clock.advance(100)
        limiter.emit(
            logger,
            context="tracking_fallback",
            prefix="Poll #3 tracking fallback FAILED",
            exc=exc,
        )
        clock.advance(400)
        emitted = limiter.emit(
            logger,
            context="tracking_fallback",
            prefix="Poll #4 tracking fallback FAILED",
            exc=exc,
        )

    errors = _errors(caplog)
    assert emitted is True
    assert len(errors) == 2
    assert "suppressed 2 occurrences since last report" in errors[-1].getMessage()


def test_different_parser_messages_have_different_signatures_and_emit_immediately(caplog):
    clock = FakeClock()
    limiter = RepeatedErrorRateLimiter(600, clock=clock)
    logger = logging.getLogger("test.rate_limit.signature")

    no_rows = ParserError("raceindex: no race rows with race number + deadline found")
    partial = ParserError("raceindex: partial parse labelled=[1, 2] parsed=[1]")

    assert limiter.signature("raceindex", no_rows) != limiter.signature("raceindex", partial)

    with caplog.at_level(logging.ERROR, logger=logger.name):
        limiter.emit(
            logger,
            context="raceindex",
            prefix="Poll #1 raceindex FAILED",
            exc=no_rows,
        )
        clock.advance(1)
        limiter.emit(
            logger,
            context="raceindex",
            prefix="Poll #2 raceindex FAILED",
            exc=partial,
        )

    assert len(_errors(caplog)) == 2


def test_same_exception_in_different_contexts_is_not_coalesced(caplog):
    clock = FakeClock()
    limiter = RepeatedErrorRateLimiter(600, clock=clock)
    logger = logging.getLogger("test.rate_limit.context")
    exc = RuntimeError("same message")

    with caplog.at_level(logging.ERROR, logger=logger.name):
        limiter.emit(logger, context="raceindex", prefix="raceindex FAILED", exc=exc)
        limiter.emit(
            logger,
            context="tracking_fallback",
            prefix="tracking fallback FAILED",
            exc=exc,
        )

    assert len(_errors(caplog)) == 2
