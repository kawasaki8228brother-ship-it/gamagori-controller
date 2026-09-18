"""Opt-in one-off post-day review. No recurring task or production writes.

The guard enforces an elapsed target date in JST, not official race completion.
Acquisition and readback success are distinct from semantic/freshness success.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v11_candidate.evidence_capture import (
    CaptureError, CaptureLimits, EvidenceArchive, full_day_phase,
    run_capture_phase, review_saved_beforeinfo,
)
from v11_candidate.roster_semantics import parse_listed_roster

TARGET_DATE = '2026-09-18'
PHASE = 'POSTDAY_ONEOFF_REVIEW'
JST = dt.timezone(dt.timedelta(hours=9))


def ensure_postday(now: dt.datetime, target_date: str) -> None:
    if type(now) is not dt.datetime or now.tzinfo is None or now.utcoffset() is None:
        raise CaptureError('AWARE_NOW_REQUIRED')
    if target_date != TARGET_DATE:
        raise CaptureError('ONEOFF_TARGET_DATE_MISMATCH')
    if now.astimezone(JST).date() <= dt.date.fromisoformat(target_date):
        raise CaptureError('TARGET_DAY_NOT_ELAPSED')


def review_archive(archive: EvidenceArchive) -> list[dict]:
    """All parsers run after capture, on independent DB readbacks only."""
    out = []
    for key, spec in zip(archive.keys, archive.specs):
        item = {'key': key, 'spec': asdict(spec), 'semantic_status': 'UNVERIFIED',
                'official_withdrawal_confirmed': False, 'input_eligible': False}
        try:
            loaded = archive.read(key, 'END')
            if loaded is None:
                item['error'] = 'END_MISSING'
            else:
                receipt, body = loaded
                item['body_sha256'] = receipt.get('body_sha256')
                if spec.endpoint == 'beforeinfo':
                    item['parsed'] = review_saved_beforeinfo(archive, key)
                    item['semantic_status'] = 'REPLAY_RETURNED_NOT_ELIGIBILITY'
                elif (receipt['http_status'] == 200 and receipt['body_complete']
                      and receipt['error'] is None and body is not None
                      and receipt['headers'].get('content-type', '').split(';')[0].strip().lower() == 'text/html'
                      and receipt['headers'].get('content-encoding', 'identity').lower() == 'identity'):
                    roster = parse_listed_roster(body)
                    if (roster.body_identity.target_date != spec.target_date or
                            roster.body_identity.venue_code != '07' or
                            roster.body_identity.race_no != spec.race_no):
                        raise CaptureError('ROSTER_BODY_TARGET_MISMATCH')
                    item['parsed'] = asdict(roster)
                    item['semantic_status'] = 'LISTING_PARSED_NOT_ACTIVE'
                else:
                    item['error'] = 'BODY_NOT_ELIGIBLE_FOR_REVIEW_PARSE'
        except Exception as exc:
            item['error'] = type(exc).__name__ + ':' + str(exc)
        out.append(item)
    return out


def execute_review(out: Path, *, allow_network: bool = False, target_date: str = TARGET_DATE,
                   transport=None, clock=lambda: dt.datetime.now(dt.timezone.utc)) -> dict:
    if type(allow_network) is not bool or (transport is None and not allow_network):
        raise CaptureError('NETWORK_NOT_AUTHORIZED')
    ensure_postday(clock(), target_date)
    out = Path(out)
    # Exclusive directory prevents accidentally reusing or overwriting evidence.
    out.mkdir(parents=False, exist_ok=False)
    manifest = {'target_date': target_date, 'phase': PHASE,
                'started_at': clock().isoformat(), 'transport_injected': transport is not None,
                'review_only': True, 'official_completion_verified': False,
                'predeadline_state_proven': False, 'production_recovery_proven': False,
                'request_count_limit': 24, 'attempts_per_target': 1,
                'max_body_bytes_per_target': 1_000_000, 'io_timeout_seconds': 12.0,
                'source_effective_at': None, 'automatic_recurrence': False}
    path = out/'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = EvidenceArchive(out/'evidence.sqlite', full_day_phase(target_date, PHASE))
    result = run_capture_phase(archive, CaptureLimits(1_000_000, 12.0),
                               transport=transport, network_enabled=allow_network, clock=clock)
    (out/'capture_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    parsed = review_archive(archive)
    (out/'parsed_review.json').write_text(json.dumps(parsed, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    manifest.update(finished_at=clock().isoformat(), run_id=archive.run_id)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--allow-network', action='store_true')
    args = p.parse_args()
    result = execute_review(args.output, allow_network=args.allow_network)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    c = result['counts']
    # Do not report a successful live acquisition if only error receipts saved.
    good = all(c[k] == 24 for k in ('planned','attempted_this_run','received_headers','http_200',
                                   'body_complete','body_persisted','end_persisted','readback_verified'))
    raise SystemExit(0 if good and not result['storage_failures'] else 2)
