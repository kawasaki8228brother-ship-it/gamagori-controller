"""Invented Health/index examples. Every HTTP operation is mocked locally."""
import datetime as dt
from hashlib import sha256
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from models import JST
from official import OfficialDataFetcher
from raceindex_status import IndexFailure, classify_index_exception


NOW = dt.datetime(2099, 1, 7, 12, tzinfo=JST)
DATE = "20990107"
ACQUIRED = NOW.isoformat()


def index_html(numbers=range(1, 13)):
    return ("<table><tr><th>レース</th><th>締切予定時刻/投票</th></tr>" +
            "".join(f"<tr><td>{n}R</td><td>13:{n:02d} 投票</td></tr>" for n in numbers) + "</table>")


def tracking(numbers=range(1, 13)):
    return {"date": "2099-01-07", "programs": {"stadiums": {"7": {"stadium_number": 7,
            "races": {str(n): {"race_number": n, "closed_at": f"2099-01-07 13:{n:02d}:00",
                                "is_closed": True, "is_cancelled": True} for n in numbers}}}}}


def proof(event="NO_RACE", numbers=None):
    numbers = [] if event == "NO_RACE" else list(range(1, 13)) if numbers is None else list(numbers)
    body = {"date": DATE, "venue": "07", "event": event, "race_numbers": numbers, "authority": "OFFICIAL_SCHEDULE"}
    raw = json.dumps({"SYNTHETIC_CALENDAR_ONLY": body}, sort_keys=True).encode()
    digest = sha256(raw).hexdigest()
    return {"schema": "OFFICIAL_SCHEDULE_EVIDENCE_V001_PROPOSED", **body, "raw_evidence": raw,
            "raw_sha256": digest, "independent_review": {"reviewed": True,
                "receipt_sha256": sha256(b"SYNTHETIC_REVIEW_NOT_ACTUAL_APPROVAL").hexdigest(),
                **{key: body[key] for key in ("date", "venue", "event", "race_numbers")}, "raw_sha256": digest}}


def fetcher(text):
    obj = OfficialDataFetcher(max_retries=1)
    obj._get_text = AsyncMock(return_value=(text, ACQUIRED))
    return obj


@pytest.mark.asyncio
async def test_complete_official_12_is_success_with_conservative_default():
    obj = fetcher(index_html())
    try:
        result = await obj.fetch_race_index(NOW)
        assert result.date == DATE and len(result.races) == 12
        assert {r.race_id for r in result.races} == {f"{DATE}_GAM_{n:02d}R" for n in range(1, 13)}
        obj._get_text.assert_awaited_once()
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("html,reason", [
    ("<html>No races shown</html>", "RACE_INDEX_NO_RACE_ROWS_UNAUTHENTICATED"),
    (index_html(range(1, 12)), "RACE_INDEX_HTML_INVALID"),
    ("<table><tr><td>1R</td><td>13:01</td></tr></table>", "RACE_INDEX_HTML_INVALID")])
async def test_http_200_empty_partial_or_wrong_structure_is_not_no_race(html, reason):
    obj = fetcher(html)
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert type(caught.value) is IndexFailure
        assert classify_index_exception(caught.value) == {"kind": "HTML_PARSE_FAILED", "reason": reason}
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_removed_calendar_provider_is_not_an_admission_api():
    # D3 removes the S2 inert argument rather than retaining an authority hook.
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=lambda now: proof())
    obj = fetcher(index_html())
    try:
        assert len((await obj.fetch_race_index(NOW)).races) == 12
        obj._get_text.assert_awaited_once()
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["no_review", "truthy_review", "raw_hash", "date", "venue", "receipt", "review_binding", "empty_raw"])
async def test_invalid_calendar_never_verifies_absence_or_relaxes_count(kind):
    p = proof()
    if kind == "no_review": p["independent_review"]["reviewed"] = False
    elif kind == "truthy_review": p["independent_review"]["reviewed"] = 1
    elif kind == "raw_hash": p["raw_sha256"] = "f" * 64
    elif kind == "date": p["date"] = "20990106"
    elif kind == "venue": p["venue"] = "08"
    elif kind == "receipt": p["independent_review"]["receipt_sha256"] = None
    elif kind == "review_binding": p["independent_review"]["event"] = "RACING_DAY"
    else: p["raw_evidence"] = b""
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=lambda now: p)


@pytest.mark.asyncio
async def test_partial_day_cannot_change_fixed_expected_twelve():
    # D3 has no calendar argument; expected twelve is a direct constant.
    obj = fetcher(index_html(range(1, 9)))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(NOW)
        assert caught.value.kind == "HTML_PARSE_FAILED"
    finally:
        await obj.close()
    obj = fetcher(json.dumps(tracking(range(1, 9))))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_tracking_race_index(NOW)
        assert caught.value.kind == "TRACKING_PARSE_FAILED"
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_removed_provider_argument_never_executes_or_echoes_callback(caplog):
    def bad_provider(now):
        raise RuntimeError("PRIVATE_PROVIDER_SECRET")
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=bad_provider)
    assert "PRIVATE_PROVIDER_SECRET" not in caplog.text


@pytest.mark.asyncio
async def test_fetch_failures_distinct_from_html_and_safe():
    obj = fetcher(index_html())
    obj._get_text.side_effect = httpx.ProxyError("https://PRIVATE_SECRET:password@proxy.invalid")
    try:
        for call in (obj.fetch_race_index, obj.fetch_tracking_race_index):
            with pytest.raises(IndexFailure) as caught:
                await call(NOW)
            assert caught.value.kind == "HTTP_FETCH_FAILED"
            assert "PRIVATE_SECRET" not in str(caught.value) and "proxy.invalid" not in repr(caught.value)
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_get_text_retry_logs_and_terminal_error_never_expose_exception(caplog):
    obj = OfficialDataFetcher(max_retries=2, backoff_seconds=0)
    obj.client.get = AsyncMock(side_effect=httpx.ProxyError("PRIVATE_PROXY_SECRET"))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj._get_text("https://www.boatrace.jp/synthetic-only")
        assert caught.value.reason == "HTTP_RETRIES_EXHAUSTED" and obj.client.get.await_count == 2
        assert "PRIVATE_PROXY_SECRET" not in caplog.text
        assert "boatrace.jp" not in caplog.text
        assert obj.client.follow_redirects is True
        assert obj.client.headers["Cache-Control"] == "no-cache"
        assert "Chrome/140.0" in obj.client.headers["User-Agent"]
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_tracking_complete_remains_tracking_only_even_raw_closed_flags():
    obj = fetcher(json.dumps(tracking()))
    try:
        snapshot = await obj.fetch_tracking_race_index(NOW)
        assert len(snapshot.races) == 12
        assert all(r.sales_status == "FALLBACK_TRACKING_ONLY" and not r.is_closed and not r.is_cancelled for r in snapshot.races)
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_tracking_absent_stadium7_is_missing_never_calendar_absence():
    obj = fetcher(json.dumps({"programs": {"stadiums": {"5": {}}}}))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_tracking_race_index(NOW)
        assert type(caught.value) is IndexFailure
        assert caught.value.kind == "TRACKING_MISSING" and caught.value.reason == "TRACKING_STADIUM_7_MISSING"
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["<html>200 but not JSON</html>", "[]", '{"programs":null}',
                                  '{"programs":{"stadiums":[]}}', '{"programs":{},"programs":{}}',
                                  '{"unused":NaN,"programs":{"stadiums":{}}}'])
async def test_tracking_malformed_payload_is_parse_failure(text):
    obj = fetcher(text)
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_tracking_race_index(NOW)
        assert caught.value.kind == "TRACKING_PARSE_FAILED"
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["partial", "null_row", "bool_number", "key_number", "duplicate_number", "wrong_payload_date", "ambiguous_stadium"])
async def test_tracking_invalid_row_date_duplicate_and_partial_fail_closed(kind):
    p = tracking()
    races = p["programs"]["stadiums"]["7"]["races"]
    if kind == "partial": del races["12"]
    elif kind == "null_row": races["1"] = None
    elif kind == "bool_number": races["1"]["race_number"] = True
    elif kind == "key_number": races["1"]["race_number"] = 2
    elif kind == "duplicate_number": races["01"] = dict(races["1"])
    elif kind == "wrong_payload_date": p["date"] = "2099-01-06"
    else: p["programs"]["stadiums"]["07"] = p["programs"]["stadiums"]["7"]
    obj = fetcher(json.dumps(p))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_tracking_race_index(NOW)
        assert caught.value.kind == "TRACKING_PARSE_FAILED"
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("deadline", ["2099-01-06 13:00:00", "2099-01-07T20:00:00+00:00",
                                      "2099-01-07T13:00:00", "2099-01-07T13:00:00-00:00",
                                      "2099-01-07T13:00:00+08:60", "2099-01-07 25:00:00", ""])
async def test_tracking_deadlines_never_relabel_wrong_date_or_unknown_timezone(deadline):
    p = tracking()
    p["programs"]["stadiums"]["7"]["races"]["1"]["closed_at"] = deadline
    obj = fetcher(json.dumps(p))
    try:
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_tracking_race_index(NOW)
        assert caught.value.kind == "TRACKING_PARSE_FAILED"
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_utc_now_maps_to_requested_jst_day_and_naive_now_is_unknown():
    obj = fetcher(index_html())
    try:
        result = await obj.fetch_race_index(dt.datetime(2099, 1, 6, 16, tzinfo=dt.timezone.utc))
        assert result.date == DATE
        assert "hd=20990107" in obj._get_text.await_args.args[0]
        with pytest.raises(IndexFailure) as caught:
            await obj.fetch_race_index(dt.datetime(2099, 1, 7, 12))
        assert caught.value.kind == "UNKNOWN_FAILURE"
    finally:
        await obj.close()


def test_typed_classifier_never_evaluates_unknown_exception_string():
    class SecretException(Exception):
        def __str__(self):
            raise AssertionError("MUST_NOT_STRINGIFY")
    assert classify_index_exception(SecretException()) == {"kind": "UNKNOWN_FAILURE", "reason": "UNCLASSIFIED_EXCEPTION"}
    unsafe = IndexFailure("https://PRIVATE_SECRET", "PRIVATE_SECRET")
    assert str(unsafe) == "UNKNOWN_FAILURE:UNCLASSIFIED_EXCEPTION"
    for reason in ("OFFICIAL_SNAPSHOT_SCOPE_INVALID", "TRACKING_SNAPSHOT_SCOPE_INVALID"):
        assert IndexFailure("HTML_PARSE_FAILED", reason).reason == reason
