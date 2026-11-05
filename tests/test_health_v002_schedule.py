"""D3 replaces S2 inert-hook tests with explicit active-API removal regressions.

The exact v002 original is preserved by root. No old calendar assertion remains
an admission interface; all examples below are invented local claims only.
"""
import inspect
import json
from unittest.mock import Mock

import pytest

import official
import raceindex_status
from official import OfficialDataFetcher
from raceindex_status import FULL_RACE_NUMBERS, IndexFailure, classify_index_exception
from test_health_official_index import NOW, fetcher, index_html, proof, tracking


def test_schedule_authority_names_and_constructor_hook_are_absent():
    assert "schedule_evidence_provider" not in inspect.signature(OfficialDataFetcher).parameters
    assert not hasattr(OfficialDataFetcher, "_expected_race_numbers")
    for module in (official, raceindex_status):
        assert not hasattr(module, "NoRaceVerified")
        assert not hasattr(module, "reviewed_schedule_decision")
    assert "SCHEDULE_UNVERIFIED" not in raceindex_status.INDEX_KINDS


@pytest.mark.parametrize("event,numbers", [("NO_RACE", []), ("RACING_DAY", range(1, 9)), ("RACING_DAY", range(1, 13))])
def test_matching_calendar_claim_cannot_be_injected_as_an_argument(event, numbers):
    provider = Mock(return_value=proof(event, numbers))
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=provider)
    provider.assert_not_called()


@pytest.mark.parametrize("receipt", ["0" * 64, "f" * 64, None, True, "https://PRIVATE_SECRET.invalid"])
def test_arbitrary_self_asserted_receipt_cannot_reopen_removed_api(receipt):
    claimed = proof()
    claimed["independent_review"]["receipt_sha256"] = receipt
    provider = Mock(return_value=claimed)
    with pytest.raises(TypeError):
        OfficialDataFetcher(schedule_evidence_provider=provider)
    provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["official", "tracking"])
async def test_fixed_twelve_remains_without_provider_attribute(path):
    obj = fetcher(index_html() if path == "official" else json.dumps(tracking()))
    try:
        assert not hasattr(obj, "schedule_evidence_provider")
        result = await (obj.fetch_race_index(NOW) if path == "official" else obj.fetch_tracking_race_index(NOW))
        assert len(result.races) == len(FULL_RACE_NUMBERS) == 12
        if path == "tracking":
            assert all(not r.is_closed and not r.is_cancelled and r.sales_status == "FALLBACK_TRACKING_ONLY" for r in result.races)
    finally:
        await obj.close()


@pytest.mark.parametrize("kind,reason", [("NO_RACE_VERIFIED", "INDEPENDENT_OFFICIAL_CALENDAR_NO_RACE"),
                                        ("SCHEDULE_UNVERIFIED", "SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED")])
def test_removed_exception_kind_strings_are_ordinary_unknown_failures(kind, reason):
    forged = IndexFailure(kind, reason)
    expected = {"kind": "UNKNOWN_FAILURE", "reason": "UNCLASSIFIED_EXCEPTION"}
    assert classify_index_exception(forged) == expected
    forged.kind, forged.reason = kind, "PRIVATE_SECRET"
    assert classify_index_exception(forged) == expected


def test_unknown_exception_name_cannot_certify_absence_or_stop_monitor():
    class NoRaceVerified(Exception):
        def __str__(self):
            raise AssertionError("MUST_NOT_STRINGIFY_UNTRUSTED_EXCEPTION")
    result = classify_index_exception(NoRaceVerified())
    assert result == {"kind": "UNKNOWN_FAILURE", "reason": "UNCLASSIFIED_EXCEPTION"}


def test_classifier_handles_malicious_attributes_as_unknown():
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
