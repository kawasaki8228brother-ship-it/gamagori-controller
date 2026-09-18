"""Manual review-only capture of one 24-request phase; never schedules itself."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v11_candidate.evidence_capture import (
    CaptureLimits, EvidenceArchive, full_day_phase, run_capture_phase)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date', required=True, help='Explicit target YYYY-MM-DD; not inferred from clock')
    ap.add_argument('--phase', required=True, help='Explicit label, not a schedule or freshness claim')
    ap.add_argument('--output', required=True, type=Path, help='NEW review SQLite path; existing files refused')
    ap.add_argument('--max-body-bytes', required=True, type=int, help='Resource cap, not a production policy')
    ap.add_argument('--timeout-seconds', required=True, type=float, help='HTTPX per-operation timeout; not an end-to-end deadline')
    ap.add_argument('--allow-network', action='store_true', help='Explicit opt-in for 24 public GET attempts')
    args = ap.parse_args()
    if not args.allow_network:
        ap.error('No network authorization: specify --allow-network only after reviewing the scope.')
    specs = full_day_phase(args.date, args.phase)
    limits = CaptureLimits(args.max_body_bytes, args.timeout_seconds)
    archive = EvidenceArchive(args.output, specs)
    report = run_capture_phase(archive, limits, network_enabled=True)
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    with args.output.with_suffix('.summary.json').open('x', encoding='utf-8') as f:
        f.write(text + '\n')
    print(text)
    # Independent storage accounting and acquisition completeness; neither
    # grants a content/participants/freshness/readiness success certificate.
    c = report['counts']
    return 0 if c['readback_verified'] == 24 and c['http_200'] == 24 and c['body_complete'] == 24 else 2


if __name__ == '__main__':
    raise SystemExit(main())
