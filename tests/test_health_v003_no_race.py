"""D3/D4 local negative regressions; all HTML/HTTP are synthetic and mocked."""
import inspect
import json
from unittest.mock import Mock

import pytest

import official
from official import OfficialDataFetcher
from parsers import ParserError, parse_race_index
from raceindex_status import FULL_RACE_NUMBERS, IndexFailure, classify_index_exception
from test_health_official_index import NOW, fetcher, index_html, tracking


NO_ROWS = "raceindex: no race rows with race number + deadline found"
NO_ROWS_CODE = "RACE_INDEX_NO_RACE_ROWS_UNAUTHENTICATED"


def test_removed_constructor_hook_is_rejected_before_client_creation(monkeypatch):
    client = Mock(side_effect=AssertionError("MUST_NOT_CREATE_HTTP_CLIENT"))
    monkeypatch.setattr(official.httpx, "AsyncClient", client)
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=object())
    client.assert_not_called()
    assert "schedule_evidence_provider" not in inspect.signature(OfficialDataFetcher).parameters


@pytest.mark.asyncio
async def test_direct_fixed_official_expected_set_ignores_injected_old_attribute(monkeypatch):
    obj = fetcher(index_html())
    helper = Mock(return_value=frozenset(range(1, 9)))
    provider = Mock(side_effect=AssertionError("UNTRUSTED_PROVIDER_MUST_NOT_RUN"))
    obj._expected_race_numbers = helper  # Test-only dynamic attributes are never read.
    obj.schedule_evidence_provider = provider
    parser = Mock(wraps=parse_race_index)
    monkeypatch.setattr(official, "parse_race_index", parser)
    try:
        assert len((await obj.fetch_race_index(NOW)).races) == 12
        assert parser.call_args.kwargs["expected_race_numbers"] == FULL_RACE_NUMBERS
        helper.assert_not_called()
        provider.assert_not_called()
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["official", "tracking"])
async def test_injected_old_expected_method_cannot_accept_partial_eight(path):
    obj = fetcher(index_html(range(1, 9)) if path == "official" else json.dumps(tracking(range(1, 9))))
    helper = Mock(return_value=frozenset(range(1, 9)))
    obj._expected_race_numbers = helper
    try:
        with pytest.raises(IndexFailure) as caught:
            await (obj.fetch_race_index(NOW) if path == "official" else obj.fetch_tracking_race_index(NOW))
        assert caught.value.kind == ("HTML_PARSE_FAILED" if path == "official" else "TRACKING_PARSE_FAILED")
        helper.assert_not_called()
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_only_exact_no_rows_parser_observation_gets_unauthenticated_reason():
    obj = fetcher("<html><body>No row labels in this invented page</body></html>")
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert classify_index_exception(caught.value) == {"kind": "HTML_PARSE_FAILED", "reason": NO_ROWS_CODE}
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ParserError("raceindex: partial parse EXPECTED_RACE_SET_MISMATCH"),
                                   ParserError(NO_ROWS + " PRIVATE_SECRET"),
                                   ParserError(NO_ROWS, "extra context"),
                                   ParserError("unrelated parser failure")])
async def test_other_html_parser_failures_are_not_no_rows_candidates(error, monkeypatch):
    obj = fetcher(index_html())
    monkeypatch.setattr(official, "parse_race_index", Mock(side_effect=error))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert caught.value.kind == "HTML_PARSE_FAILED"
        assert caught.value.reason == "RACE_INDEX_HTML_INVALID"
        assert "PRIVATE_SECRET" not in str(caught.value)
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_parser_subclass_cannot_forge_exact_no_rows_category(monkeypatch):
    class UntrustedParserError(ParserError):
        def __str__(self):
            raise AssertionError("MUST_NOT_STRINGIFY")
    obj = fetcher(index_html())
    monkeypatch.setattr(official, "parse_race_index", Mock(side_effect=UntrustedParserError(NO_ROWS)))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert caught.value.reason == "RACE_INDEX_HTML_INVALID"
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_untrusted_no_race_named_exception_is_unknown_not_special(monkeypatch):
    class NoRaceVerified(Exception):
        kind = "NO_RACE_VERIFIED"
        def __str__(self):
            raise AssertionError("MUST_NOT_STRINGIFY")
    obj = fetcher(index_html())
    monkeypatch.setattr(official, "parse_race_index", Mock(side_effect=NoRaceVerified()))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert classify_index_exception(caught.value)["kind"] == "UNKNOWN_FAILURE"
    finally:
        await obj.close()


def test_no_production_schedule_authority_symbols_remain():
    import raceindex_status
    for module in (official, raceindex_status):
        for name in ("NoRaceVerified", "reviewed_schedule_decision"):
            assert not hasattr(module, name)
    assert not hasattr(OfficialDataFetcher, "_expected_race_numbers")
    assert "SCHEDULE_UNVERIFIED" not in raceindex_status.INDEX_KINDS


@pytest.mark.asyncio
@pytest.mark.parametrize("declared_in", ["payload", "programs"])
async def test_stale_declared_tracking_date_precedes_stadium_absence_diagnostic(declared_in, caplog):
    from test_health_controller_scope import controller
    payload = {"programs": {"stadiums": {"1": {}}}}
    (payload if declared_in == "payload" else payload["programs"])["date"] = "20990106"
    obj = fetcher("unused")
    obj._get_text.side_effect = [
        ("<html>No race rows in this invented official response</html>", NOW.isoformat()),
        (json.dumps(payload), NOW.isoformat()),
    ]
    value = controller()
    value.fetcher = obj
    try:
        assert await value._refresh_race_universe(NOW, 1) == (True, False)
        assert value._last_index_outcome["official_reason"] == NO_ROWS_CODE
        assert value._last_index_outcome["tracking"] == "TRACKING_PARSE_FAILED"
        assert value._last_index_outcome["tracking_reason"] == "TRACKING_PAYLOAD_DATE_MISMATCH"
        assert value._last_index_outcome["diagnostic"] == "NORMAL_SOURCE_FAILURE"
        assert "NON_RACE_CANDIDATE_UNAUTHENTICATED" not in caplog.text
        value.state_machine.process_race.assert_not_awaited()
        value.repo.save_race_state.assert_not_awaited()
        value.repo.append_shadow_event_atomic.assert_not_awaited()
    finally:
        await obj.close()
