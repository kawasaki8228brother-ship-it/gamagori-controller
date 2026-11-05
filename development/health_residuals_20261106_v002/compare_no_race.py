"""Expose local claim/exception behavior; no HTTP client, actual DB or forecast."""
import argparse
import asyncio
import datetime as dt
from hashlib import sha256
import json
from pathlib import Path
import platform
import socket
import ssl
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_OFFLINE_HEALTH_V002")


async def run():
    from main import GamagoriController
    from models import JST, OfficialRaceInfo
    from official import OfficialDataFetcher
    from raceindex_status import NoRaceVerified, reviewed_schedule_decision
    now = dt.datetime(2099, 1, 7, 15, tzinfo=JST)
    fields = {"date": "20990107", "venue": "07", "event": "NO_RACE", "race_numbers": []}
    raw = b"INVENTED_ARBITRARY_NOT_OFFICIAL_CALENDAR"
    digest = sha256(raw).hexdigest()
    claim = {"schema": "OFFICIAL_SCHEDULE_EVIDENCE_V001_PROPOSED", **fields,
        "authority": "OFFICIAL_SCHEDULE", "raw_evidence": raw, "raw_sha256": digest,
        "independent_review": {"reviewed": True, "receipt_sha256": "0" * 64, **fields, "raw_sha256": digest}}
    decision = reviewed_schedule_decision(claim, fields["date"])
    provider_calls = []
    def provider(*args):
        provider_calls.append(1)
        return claim
    fetcher = OfficialDataFetcher.__new__(OfficialDataFetcher)
    fetcher.schedule_evidence_provider = provider
    try:
        expected = fetcher._expected_race_numbers(now)
        fetcher_result = {"status": "FULL_EXPECTATION" if len(expected) == 12 else "SHORT_EXPECTATION", "race_count": len(expected)}
    except NoRaceVerified:
        fetcher_result = {"status": "LEGACY_CERTIFICATION_RAISED", "race_count": 0}
    cases = []
    for origin in ("official", "tracking"):
        value = GamagoriController.__new__(GamagoriController)
        value._stop = asyncio.Event()
        value._index_hold_reason = None
        value._known_races = {f"20990107_GAM_{n:02d}R": OfficialRaceInfo(race_id=f"20990107_GAM_{n:02d}R",
            official_deadline=now.replace(hour=16, minute=n), source_url="SYNTHETIC_ONLY", acquired_at=now.isoformat()) for n in range(1, 13)}
        before = {k: v.model_dump(mode="json") for k, v in value._known_races.items()}
        value._error_log_limiter = SimpleNamespace(emit=lambda *args, **kwargs: None)
        value.repo = SimpleNamespace(list_all_states=AsyncMock(return_value=[]), save_race_state=AsyncMock(side_effect=AssertionError("NO_WRITES")))
        value.state_machine = SimpleNamespace(process_race=AsyncMock(side_effect=AssertionError("NO_FORECAST_EXECUTION")))
        value.fetcher = SimpleNamespace(fetch_race_index=AsyncMock(side_effect=RuntimeError("SYNTHETIC_FETCH_ERROR")),
            fetch_tracking_race_index=AsyncMock(side_effect=NoRaceVerified()))
        if origin == "official":
            value.fetcher.fetch_race_index = AsyncMock(side_effect=NoRaceVerified())
        await value._refresh_race_universe(now, 1)
        count_after_first = len(value._known_races)
        await value._refresh_race_universe(now, 2)
        cases.append({"origin": origin, "count_before": len(before), "count_after_first": count_after_first,
            "count_after_second": len(value._known_races), "held": value._index_hold_reason is not None,
            "cached_current_bytes_preserved": before == {k: v.model_dump(mode="json") for k, v in value._known_races.items()},
            "official_calls": value.fetcher.fetch_race_index.await_count, "tracking_calls": value.fetcher.fetch_tracking_race_index.await_count,
            "repo_read_calls": value.repo.list_all_states.await_count, "repo_write_calls": value.repo.save_race_state.await_count,
            "forecast_calls": value.state_machine.process_race.await_count, "scope": "REFRESH_ONLY_NOT_ACTUAL_STATE_MACHINE"})
    return {"claim_accepted": decision["accepted"], "decision_expected_races": len(decision["race_numbers"]),
        "external_authenticity": decision["external_authenticity"], "provider_calls": len(provider_calls),
        "expected_races_gate": fetcher_result, "legacy_signal_cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--label", required=True, choices=["V001", "V002"])
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    sys.path.insert(0, str(args.repo.resolve()))
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED", "classification": "SYNTHETIC_ONLY", "label": args.label, "production_go": False}, sort_keys=True), flush=True)
    result = asyncio.run(run())
    print(json.dumps({"label": args.label, **result, "production_go": False, "actual_official_evidence": "NOT_OBTAINED"}, sort_keys=True))
