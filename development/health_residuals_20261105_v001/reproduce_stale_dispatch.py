"""One-cycle injected controller proof. No constructor, DB, HTTP or writer."""
import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
import platform
import socket
import ssl
import sys
from types import SimpleNamespace


def blocked(*args, **kwargs):
    raise AssertionError("NETWORK_DISABLED_DURING_SYNTHETIC_CONTROLLER_REPRO")


async def run_case(module, name):
    from models import JST, OfficialRaceInfo, RaceState, RaceStatus
    from error_rate_limit import RepeatedErrorRateLimiter
    now = dt.datetime(2099, 1, 7, 12, tzinfo=JST)
    yesterday = now-dt.timedelta(days=1)
    old = RaceState(race_id="20990106_GAM_01R", status=RaceStatus.PENDING,
                    official_deadline=yesterday.replace(hour=15))
    current = RaceState(race_id="20990107_GAM_02R", status=RaceStatus.PENDING,
                        official_deadline=now.replace(hour=15))
    states = [old] if name == "persisted_old_only" else [old, current]
    before = [state.model_dump(mode="json") for state in states]
    controller = module.GamagoriController.__new__(module.GamagoriController)
    controller.dry_run, controller.db_path, controller.poll_interval = True, "SYNTHETIC_NOT_OPENED", 0
    controller._stop = asyncio.Event()
    controller._known_races = {}
    if name == "cached_old_with_current_persisted":
        controller._known_races[old.race_id] = OfficialRaceInfo(race_id=old.race_id,
            official_deadline=old.official_deadline, source_url="SYNTHETIC_ONLY", acquired_at=yesterday.isoformat())
    controller._error_log_limiter = RepeatedErrorRateLimiter(600)
    controller._last_sqlite_audit_at = None
    controller._maybe_log_sqlite_audit = lambda *args, **kwargs: None
    calls = []
    async def all_states():
        return states
    async def official(*args):
        raise RuntimeError("SYNTHETIC_OFFICIAL_FAILURE_NOT_REAL_11_05")
    async def tracking(*args):
        controller._stop.set()
        raise RuntimeError("SYNTHETIC_TRACKING_FAILURE_NOT_REAL_11_05")
    async def process(race_id, timestamp, **kwargs):
        calls.append({"race_id": race_id, "official_info_is_none": kwargs.get("official_info") is None,
                      "official_fetch_failed": kwargs.get("official_fetch_failed"),
                      "tracking_info_is_none": kwargs.get("tracking_info") is None})
    async def close():
        pass
    controller.repo = SimpleNamespace(list_all_states=all_states)
    controller.fetcher = SimpleNamespace(fetch_race_index=official, fetch_tracking_race_index=tracking, close=close)
    controller.state_machine = SimpleNamespace(process_race=process)
    class FixedClock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)
    module.dt = SimpleNamespace(datetime=FixedClock, timedelta=dt.timedelta, timezone=dt.timezone)
    await controller.start()
    after = [state.model_dump(mode="json") for state in states]
    if before != after:
        raise AssertionError("INJECTED_REPRO_CHANGED_INPUT_STATE")
    return {"case": name, "dispatched": calls,
        "prior_day_dispatched": any(row["race_id"].startswith("20990106_") for row in calls),
        "current_day_dispatched": any(row["race_id"].startswith("20990107_") for row in calls),
        "input_states_byte_equivalent": True, "actual_state_machine_executed": False,
        "database_opened": False, "http_used": False, "production_go": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--label", choices=("BASELINE", "CANDIDATE"), required=True)
    args = parser.parse_args()
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo.resolve()))
    print(json.dumps({"python": sys.version, "platform": platform.platform(), "openssl": ssl.OPENSSL_VERSION,
        "network": "BLOCKED", "classification": "SYNTHETIC_ONLY", "label": args.label,
        "production_go": False}, sort_keys=True), flush=True)
    import main
    results = [asyncio.run(run_case(main, name)) for name in
               ("persisted_old_only", "persisted_old_and_current", "cached_old_with_current_persisted")]
    print(json.dumps({"label": args.label, "classification": "SYNTHETIC_ONLY", "cases": results,
        "actual_11_05_occurrence": "UNVERIFIED_NOT_REPRODUCED_FROM_REAL_SOURCE",
        "production_go": False}, sort_keys=True))
