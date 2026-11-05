"""Exhaustive synthetic mutations over the frozen 264-pattern input inventory.

This is not a new official mapping, model normalizer, writer or input gateway.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json

from model11.synthetic import make_dataset
from model11.shadow_launch.sources import SourceAdapter, make_synthetic_source_fixture
from model11.shadow_preparation.capture_review import required_mapping_inventory
from model11.offline_refinements.point_in_time import audit_point_in_time

BASE_COMMIT = '148c156f472c874075a0b25d4f0b6b7e9fafdcfe'
TIMES = ('acquired_at', 'available_at', 'revision_at')
PRIVATE_REVIEW = {'/mapping/review_evidence/hq14_review_sha256', '/mapping/review_evidence/claude_review_sha256'}
MODES = ('missing', 'null', 'wrong_type', 'nonfinite')


def make_fixture(seed=735):
    return make_synthetic_source_fixture(make_dataset(1, 1, seed)['races'][0])


def _view(fixture):
    capture = fixture['capture']
    if capture.get('data_classification') != 'SYNTHETIC_ONLY' or capture.get('synthetic') is not True:
        raise ValueError('SYNTHETIC_FIXTURE_REQUIRED')
    document = json.loads(capture['payload_bytes'].decode('utf-8'))
    raw, course = document['invented_raw'], document['invented_course']
    if raw.get('data_classification') != 'SYNTHETIC_ONLY' or not raw.get('target_date', '').startswith('2099-'):
        raise ValueError('SYNTHETIC_2099_FIXTURE_REQUIRED')
    return {'raw': raw, 'course': course, 'capture': deepcopy(capture), 'mapping': deepcopy(fixture['mapping'])}


def _resign(view):
    capture = view['capture']
    payload = json.dumps({'invented_raw': view['raw'], 'invented_course': view['course']},
                         sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=True).encode('ascii')
    digest = sha256(payload).hexdigest()
    capture['payload_bytes'], capture['payload_sha256'] = payload, digest
    # Keep envelope/history integrity consistent, so RAW/COURSE mutations probe
    # the field contract rather than merely failing the outer byte hash.
    capture['history'][-1]['payload_sha256'] = digest
    return {'mapping': view['mapping'], 'capture': capture}


def expanded_inventory(fixture=None):
    fixture = make_fixture() if fixture is None else fixture
    view = _view(fixture)
    inventory = required_mapping_inventory()
    targets = []
    for index, item in enumerate(inventory):
        path = item['local_target']
        boat_indices = range(len(view['raw']['boats'])) if '{boat_index}' in path else (None,)
        history_indices = range(len(view['capture']['history'])) if '{history_index}' in path else (None,)
        for boat in boat_indices:
            for history in history_indices:
                materialized = path.replace('{boat_index}', str(boat)).replace('{history_index}', str(history))
                targets.append({'pattern_index': index, 'pattern': path, 'path': materialized,
                    'scope': item['scope'], 'requirement': item['local_requirement'],
                    'applicability': 'PRIVATE_REVIEW_NOT_APPLICABLE_SYNTHETIC' if path in PRIVATE_REVIEW else 'PRESENT_IN_SYNTHETIC_FIXTURE'})
    return targets


def _leaf(view, path):
    tokens = path.removeprefix('/').split('/')
    current = view
    for token in tokens[:-1]:
        current = current[int(token)] if isinstance(current, list) else current[token]
    last = int(tokens[-1]) if isinstance(current, list) else tokens[-1]
    if isinstance(current, dict) and last not in current:
        raise KeyError('INVENTORY_TARGET_NOT_PRESENT')
    return current, last


def mutate_fixture(fixture, path, mode, *, replacement=None):
    view = _view(fixture)
    container, key = _leaf(view, path)
    if mode == 'missing':
        del container[key]
    elif mode == 'null':
        container[key] = None
    elif mode == 'wrong_type':
        container[key] = {'INVALID_SYNTHETIC_TYPE': True}
    elif mode == 'nonfinite':
        container[key] = float('nan')
    elif mode == 'replace':
        container[key] = deepcopy(replacement)
    else:
        raise ValueError('MUTATION_MODE_NOT_DECLARED')
    if path.startswith(('/raw/', '/course/')):
        return _resign(view)
    return {'mapping': view['mapping'], 'capture': view['capture']}


def _converted(fixture):
    try:
        report = SourceAdapter(fixture['mapping']).convert(fixture['capture'])
        return report['status'], list(report.get('reasons', []))
    except Exception:
        # An uncaught frozen-validator exception is an OPEN defect, not a PASS.
        return 'EXCEPTION_UNVERIFIED', ['FROZEN_VALIDATOR_EXCEPTION_NOT_ECHOED']


def run_contract_matrix(*, include_rows=False):
    fixture = make_fixture()
    untouched = deepcopy(fixture)
    baseline, _ = _converted(fixture)
    patterns = required_mapping_inventory()
    targets = expanded_inventory(fixture)
    rows, failures, totals = [], [], Counter()
    for target in targets:
        for mode in MODES:
            if target['applicability'] != 'PRESENT_IN_SYNTHETIC_FIXTURE':
                observed, reasons = 'NOT_APPLICABLE_CONDITIONAL_PROFILE', ['PRIVATE_REVIEW_ORIGINALS_NOT_SUPPLIED']
                expected = observed
            else:
                try:
                    altered = mutate_fixture(fixture, target['path'], mode)
                    observed, reasons = _converted(altered)
                except Exception:
                    observed, reasons = 'EXCEPTION_UNVERIFIED', ['MATRIX_CONSTRUCTION_EXCEPTION_NOT_ECHOED']
                expected = 'HOLD'
            totals[observed] += 1
            record = {'pattern_index': target['pattern_index'], 'pattern': target['pattern'],
                      'path': target['path'], 'mode': mode, 'expected': expected, 'observed': observed,
                      'reasons': reasons, 'matched': observed == expected}
            if not record['matched']:
                failures.append(record)
            if include_rows:
                rows.append(record)
    unchanged = fixture == untouched
    result = {'schema': 'SYNTHETIC_264_PATTERN_MUTATION_MATRIX_V008_PREPARATION',
              'classification': 'SYNTHETIC_ONLY', 'base_commit': BASE_COMMIT,
              'inventory_patterns': len(patterns), 'materialized_targets': len(targets),
              'pattern_scopes': dict(Counter(item['scope'] for item in patterns)),
              'mutation_modes': list(MODES), 'attempts': sum(totals.values()), 'outcomes': dict(totals),
              'baseline_converter_status': baseline, 'input_unchanged': unchanged,
              'failures': failures, 'software_check': 'PASS' if baseline == 'READY' and unchanged and not failures else 'FAILED_OPEN',
              'inventory_sha256': sha256(json.dumps(patterns, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('ascii')).hexdigest(),
              '264_means': 'LOCAL_REQUIREMENT_PATTERNS_NOT_OFFICIAL_JSON_FIELDS',
              'application_status': 'HOLD', 'actual_official_mapping': 'BLOCKED_EXTERNAL',
              'external_authenticity': 'UNVERIFIED', 'production_go': False}
    if include_rows:
        result['rows'] = rows
    return result


def make_point_in_time_fixture():
    race = make_dataset(1, 1, 735)['races'][0]
    snapshot_id = 'SYNTHETIC_IMMUTABLE_CAPTURE_001'
    observed = deepcopy(race['odds_snapshot'])
    provenance = {key: observed[key] for key in TIMES}
    provenance.update(version='SYNTHETIC_PRELOCK_v001', snapshot_id=snapshot_id,
                      source_id='SYNTHETIC_LOCAL_PIT', evidence_sha256='a' * 64)
    as_of = datetime.fromisoformat(race['prediction_at'])
    return {'data_classification': 'SYNTHETIC_ONLY', 'synthetic': True,
        'race_id': race['race_id'], 'target_date': race['target_date'], 'as_of': race['prediction_at'], 'deadline': race['deadline'],
        'snapshot': {'mode': 'IMMUTABLE_SNAPSHOT', 'snapshot_id': snapshot_id, 'version': 'SYNTHETIC_SNAPSHOT_v001',
                     'preserved_at': (as_of - timedelta(seconds=20)).isoformat(), 'source_id': 'SYNTHETIC_LOCAL_PIT',
                     'content_sha256': 'b' * 64, 'evidence_sha256': 'c' * 64},
        'features': [{'boat': boat['boat'], 'name': name, 'value': boat['features'][name],
                      'unit': 'SYNTHETIC_NORMALIZED_SCORE', 'effective_at': boat['motor_updated_at'], **deepcopy(provenance)}
                     for boat in race['boats'] for name in ('st', 'turn', 'motor', 'ability', 'exhibition')],
        'odds': {'kind': 'PRE_DEADLINE', 'values': deepcopy(observed['odds']), **deepcopy(provenance)}}


def audit_past_sample(sample):
    return audit_point_in_time(sample)


if __name__ == '__main__':
    print(json.dumps(run_contract_matrix(), sort_keys=True, ensure_ascii=True))
