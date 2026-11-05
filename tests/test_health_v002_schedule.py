"""S2: invented calendar claims cannot authenticate absence or a short day."""
from copy import deepcopy
from unittest.mock import Mock

import pytest

from raceindex_status import (
    FULL_RACE_NUMBERS, IndexFailure, NoRaceVerified,
    classify_index_exception, reviewed_schedule_decision,
)
from test_health_official_index import DATE, NOW, fetcher, index_html, proof, tracking
import json


def assert_unverified(decision):
    assert decision["accepted"] is False
    assert decision["event"] is None
    assert decision["race_numbers"] == FULL_RACE_NUMBERS
    assert decision["kind"] == "SCHEDULE_UNVERIFIED" and decision["status"] == "HOLD"
    assert decision["reason"] == "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED"
    assert decision["authentication_implemented"] is False
    assert decision["external_authenticity"] == "UNVERIFIED"


@pytest.mark.parametrize("event,numbers", [("NO_RACE", []), ("RACING_DAY", range(1, 9)), ("RACING_DAY", range(1, 13))])
def test_perfectly_self_consistent_claim_still_has_no_authentication(event, numbers):
    claimed = proof(event, numbers)
    before = deepcopy(claimed)
    assert_unverified(reviewed_schedule_decision(claimed, DATE))
    assert claimed == before


@pytest.mark.parametrize("receipt", ["0" * 64, "f" * 64, "a" * 64, None, True, "https://PRIVATE_SECRET.invalid"])
def test_receipt_shape_zero_hash_true_or_matching_raw_never_grants_authority(receipt):
    claimed = proof()
    claimed["independent_review"]["receipt_sha256"] = receipt
    result = reviewed_schedule_decision(claimed, DATE)
    assert_unverified(result)
    assert "PRIVATE_SECRET" not in str(result)
    claimed["independent_review"]["receipt_sha256"] = claimed["raw_sha256"]
    assert_unverified(reviewed_schedule_decision(claimed, DATE))


def test_evidence_and_target_are_not_inspected_or_stringified():
    class Forbidden:
        def __getattribute__(self, name):
            raise AssertionError("UNAUTHENTICATED_INPUT_MUST_NOT_BE_INSPECTED")
    assert_unverified(reviewed_schedule_decision(Forbidden(), Forbidden()))
    for value in (None, {}, [], True, b"SYNTHETIC_NOT_A_CALENDAR"):
        assert_unverified(reviewed_schedule_decision(value, value))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["official", "tracking"])
async def test_provider_is_not_called_even_when_claiming_no_race_or_raising(path, caplog):
    provider = Mock(side_effect=AssertionError("PRIVATE_PROVIDER_SECRET"))
    obj = fetcher(index_html() if path == "official" else json.dumps(tracking()), provider)
    try:
        snapshot = await (obj.fetch_race_index(NOW) if path == "official" else obj.fetch_tracking_race_index(NOW))
        assert len(snapshot.races) == 12
        provider.assert_not_called()
        assert "PRIVATE_PROVIDER_SECRET" not in caplog.text
        assert "NO_RACE_VERIFIED" not in caplog.text
        if path == "tracking":
            assert all(not race.is_closed and not race.is_cancelled and race.sales_status == "FALLBACK_TRACKING_ONLY"
                       for race in snapshot.races)
    finally:
        await obj.close()


@pytest.mark.asyncio
async def test_async_provider_is_also_not_invoked():
    calls = []
    async def provider(now):
        calls.append(now)
        return proof()
    obj = fetcher(index_html(), provider)
    try:
        assert len((await obj.fetch_race_index(NOW)).races) == 12
        assert calls == []
    finally:
        await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["official", "tracking"])
async def test_legacy_decision_function_cannot_reopen_short_count_bypass(path, monkeypatch):
    decision = Mock(return_value={"accepted": True, "event": "RACING_DAY", "race_numbers": frozenset(range(1, 9))})
    monkeypatch.setattr("official.reviewed_schedule_decision", decision)
    provider = Mock(return_value=proof("RACING_DAY", range(1, 9)))
    obj = fetcher(index_html(range(1, 9)) if path == "official" else json.dumps(tracking(range(1, 9))), provider)
    try:
        with pytest.raises(IndexFailure) as caught:
            await (obj.fetch_race_index(NOW) if path == "official" else obj.fetch_tracking_race_index(NOW))
        assert caught.value.kind == ("HTML_PARSE_FAILED" if path == "official" else "TRACKING_PARSE_FAILED")
        provider.assert_not_called()
        decision.assert_not_called()
    finally:
        await obj.close()


def test_legacy_no_race_name_and_forged_kind_are_quarantined():
    legacy = NoRaceVerified()
    assert legacy.kind == "SCHEDULE_UNVERIFIED"
    assert "NO_RACE_VERIFIED" not in str(legacy)
    expected = {"kind": "SCHEDULE_UNVERIFIED", "reason": "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED"}
    assert classify_index_exception(legacy) == expected
    forged = IndexFailure("NO_RACE_VERIFIED", "INDEPENDENT_OFFICIAL_CALENDAR_NO_RACE")
    assert classify_index_exception(forged) == expected
    forged.kind = "NO_RACE_VERIFIED"
    forged.reason = "PRIVATE_SECRET"
    assert classify_index_exception(forged) == expected
    legacy.kind, legacy.reason = "NO_RACE_VERIFIED", "PRIVATE_SECRET"
    assert classify_index_exception(legacy) == expected


def test_classifier_holds_malicious_attributes_without_echoing_or_promoting():
    class Malicious(IndexFailure):
        def __getattribute__(self, name):
            if name in ("kind", "reason"):
                raise RuntimeError("PRIVATE_CLASSIFIER_SECRET")
            return super().__getattribute__(name)
    bad = Malicious.__new__(Malicious)
    RuntimeError.__init__(bad, "PRIVATE_CLASSIFIER_SECRET")
    result = classify_index_exception(bad)
    assert result == {"kind": "UNKNOWN_FAILURE", "reason": "UNCLASSIFIED_EXCEPTION"}
    assert "PRIVATE_CLASSIFIER_SECRET" not in str(result)
