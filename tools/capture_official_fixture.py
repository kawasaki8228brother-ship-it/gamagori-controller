"""Bounded, read-only capture for candidate review; never changes production.

These are post-incident responses fetched now, not original 2026-09-18 runtime
bytes. A saved HTTP response is not automatically a valid official fixture.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parsers import parse_odds3t, parse_beforeinfo
from v11_candidate.odds import parse_trifecta


def capture(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    # Fixed public URLs only; no user-supplied host, credentials or redirects.
    targets = [(12, 'odds3t'), (12, 'beforeinfo'), (3, 'odds3t')]
    with httpx.Client(timeout=20.0, follow_redirects=False,
                      headers={'User-Agent': 'GamagoriResearchFixtureReview/1.1'}) as client:
        for race, endpoint in targets:
            url = f'https://www.boatrace.jp/owpc/pc/race/{endpoint}?hd=20260918&jcd=07&rno={race}'
            record = {'requested_url': url, 'target_date': '2026-09-18',
                      'race_no': race, 'endpoint': endpoint,
                      'original_incident_response': False,
                      'snapshot_persisted': False,
                      'content_identity_independently_verified': False,
                      'production_recovery_proven': False,
                      'started_at': dt.datetime.now(dt.timezone.utc).isoformat()}
            try:
                response = client.get(url)
                acquired = dt.datetime.now(dt.timezone.utc).isoformat()
                name = f'20260918_{race:02d}_{endpoint}.html'
                body = response.content
                path = out / name
                path.write_bytes(body)
                record.update(http_status=response.status_code, response_url=str(response.url),
                              content_type=response.headers.get('content-type'),
                              acquired_at=acquired, body_size_bytes=len(body),
                              body_sha256=hashlib.sha256(body).hexdigest(),
                              snapshot_reference=name, snapshot_persisted=True)
                record['saved_bytes_match'] = hashlib.sha256(path.read_bytes()).hexdigest() == record['body_sha256']
                if response.status_code != 200 or 'text/html' not in response.headers.get('content-type', '').lower():
                    record['parse_status'] = 'NOT_ATTEMPTED_HTTP_OR_CONTENT_TYPE'
                elif endpoint == 'odds3t':
                    for label, parser in [('old', lambda: parse_odds3t(response.text, url, acquired)[0]),
                                          ('candidate', lambda: parse_trifecta(response.text).odds)]:
                        try:
                            odds = parser()
                            record[label] = {'status': 'PARSED', 'count': len(odds), 'odds': odds}
                        except Exception as exc:
                            record[label] = {'status': 'REJECTED', 'error_type': type(exc).__name__, 'error': str(exc)}
                else:
                    parsed = parse_beforeinfo(response.text, url, acquired)
                    record['old_beforeinfo'] = {'exhibition_times': parsed.exhibition_times,
                                               'entry_courses': parsed.entry_courses,
                                               'start_st': parsed.start_exhibition_st,
                                               'missing_fields': parsed.missing_fields}
            except Exception as exc:
                record.update(fetch_or_parse_status='ERROR', error_type=type(exc).__name__, error=str(exc))
            record['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            reports.append(record)
            # Preserve progress after each bounded fetch, including failures.
            (out / 'capture_report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    return reports


if __name__ == '__main__':
    report = capture(ROOT / 'review_artifacts' / 'official_capture')
    print(json.dumps([{k: v for k, v in r.items() if k not in ('old', 'candidate')} for r in report], ensure_ascii=False, indent=2))
