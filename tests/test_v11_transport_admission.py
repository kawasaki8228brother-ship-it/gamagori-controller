"""Synthetic declarations test a necessary record gate, never real transport proof.

Positive cases are authored False declarations; they are NOT official captures.
The genuine Stage15 replay remains injected=True and must fail this new gate.
"""
from contextlib import closing
from dataclasses import asdict
import inspect
import json
import sqlite3

import pytest

from test_v11_archive_execution import (DAY, NOW, LATER, sources, ledger, claim, captured)
from v11_candidate.archive_execution import sha
from v11_candidate.contracts import canonical
from v11_candidate.evidence_capture import EvidenceArchive, full_day_phase
from v11_candidate.transport_admission import (
    TransportBoundaryError, inspect_archive_transport, require_noninjected_transport)


def authored_capture(tmp_path, *, injected=False, injected_race=None, status=200):
    """Fresh test records, no network and no editing of historical receipts."""
    cap = EvidenceArchive(tmp_path / 'authored.sqlite', full_day_phase(DAY, 'SYNTHETIC_RECORD_TEST'))
    for key, spec in zip(cap.keys, cap.specs):
        flag = spec.race_no == injected_race if injected_race is not None else injected
        stamp = NOW.isoformat()
        body = b'AUTHORED TEST BODY: NOT A REAL RESPONSE'
        common = dict(run_id=cap.run_id, key=key, spec=asdict(spec), review_only=True,
                      input_eligible=False, transport_injected=flag, started_at=stamp)
        cap.append(key, 'START', common | dict(stage='START'))
        cap.append(key, 'END', common | dict(stage='END', finished_at=stamp,
            requested_url=spec.url, response_url=spec.url, http_status=status,
            body_complete=True, body_sha256=sha(body), stored_body_bytes=len(body),
            attempted=True, clock_status='OK', error=None), body)
    return cap


def finished(tmp_path, sources, **kw):
    l = ledger(tmp_path); owner = claim(l, sources)
    cap = authored_capture(tmp_path, **kw)
    l.finish_from_archive(owner.work_key, owner.owner_token, cap.path, now=LATER)
    return l, owner, cap


def rewrite_output(l, owner, mutate):
    """Deliberately recompute links in disposable fixtures to test count distrust.

    This is not a signature attack test: a DB writer can replace this whole graph.
    """
    with closing(sqlite3.connect(l.path)) as conn, conn:
        head = conn.execute('SELECT head FROM jobs WHERE k=?', (owner.work_key,)).fetchone()[0]
        event = json.loads(conn.execute('SELECT json FROM objects WHERE h=?', (head,)).fetchone()[0])
        manifest = json.loads(conn.execute('SELECT json FROM objects WHERE h=?', (event['capture_manifest'],)).fetchone()[0])
        def put(value):
            text = canonical(value); h = sha(text.encode())
            conn.execute('INSERT OR IGNORE INTO objects VALUES(?,?)', (h, text))
            return h
        mutate(conn, manifest, put)
        event['capture_manifest'] = put(manifest)
        conn.execute('UPDATE jobs SET head=? WHERE k=?', (put(event), owner.work_key))


def rewrite_flag(l, owner, stage, value=None, *, delete=False):
    def mutate(conn, manifest, put):
        target = manifest['targets'][0]; ref = target['receipt_refs'][stage]
        record = json.loads(conn.execute('SELECT json FROM objects WHERE h=?', (ref,)).fetchone()[0])
        if delete:
            del record['original_payload']['transport_injected']
        else:
            record['original_payload']['transport_injected'] = value
        record['original_payload_sha256'] = sha(canonical(record['original_payload']).encode())
        target['receipt_refs'][stage] = put(record)
    rewrite_output(l, owner, mutate)


def test_actual_mocktransport_replay_remains_complete_but_admission_fails(tmp_path, sources):
    l = ledger(tmp_path); owner = claim(l, sources); cap = captured(tmp_path)
    l.finish_from_archive(owner.work_key, owner.owner_token, cap.path, now=LATER)
    before = sha(l.path.read_bytes())
    report = inspect_archive_transport(l.path, owner.work_key)
    assert report['state'] == 'FAIL' and not report['capture_record_gate_passed']
    assert report['injected_starts'] == report['injected_ends'] == 24
    assert report['records_with_injected_transport'] == 48
    assert report['ledger_graph_verified'] and len(report['receipt_evidence']) == 48
    assert l.inspect(owner.work_key)['event']['state'] == 'COMPLETE'
    assert sha(l.path.read_bytes()) == before


def test_authored_false_declarations_pass_only_narrow_record_gate(tmp_path, sources):
    l, owner, cap = finished(tmp_path, sources)
    before = sha(l.path.read_bytes())
    report = inspect_archive_transport(l.path, owner.work_key)
    assert report['state'] == 'PASS' and report['capture_record_gate_passed']
    assert report['injected_ends'] == report['injected_starts'] == 0
    assert report['recomputed_counts'] == report['recorded_counts']
    assert report['ledger_graph_verified']
    for key in ('production_authorized', 'network_execution_proven', 'decision_basis_transport_checked', 'runtime_integration'):
        assert report[key] is False
    assert report['review_only'] is True
    digest = report.pop('binding_sha256')
    assert sha(canonical(report).encode()) == digest
    assert sha(l.path.read_bytes()) == before


@pytest.mark.parametrize('race', [1, 6, 12])
def test_single_race_injected_pair_rejected_even_with_22_false_ends(tmp_path, sources, race):
    l, owner, _ = finished(tmp_path, sources, injected_race=race)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'FAIL' and r['injected_ends'] == 2


def test_zero_summary_cannot_hide_raw_true_flags(tmp_path, sources):
    l, owner, _ = finished(tmp_path, sources, injected=True)
    rewrite_output(l, owner, lambda c, m, p: m['counts'].update(injected_ends=0))
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'FAIL' and r['injected_ends'] == 24
    assert 'INJECTED_END_COUNT_CONFLICT' in r['reasons']


@pytest.mark.parametrize('stage', ['START', 'END'])
def test_missing_flag_never_defaults_to_false(tmp_path, sources, stage):
    l, owner, _ = finished(tmp_path, sources)
    rewrite_flag(l, owner, stage, delete=True)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'UNVERIFIED' and r['missing_transport_flags'] == 1
    assert not r['capture_record_gate_passed']


@pytest.mark.parametrize('stage', ['START', 'END'])
@pytest.mark.parametrize('flag', [0, 1, 'false', 'true', None, [], {}])
def test_nonboolean_transport_flags_are_rejected_not_coerced(tmp_path, sources, stage, flag):
    l, owner, _ = finished(tmp_path, sources)
    rewrite_flag(l, owner, stage, flag)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'FAIL' and r['invalid_transport_flags'] == 1


@pytest.mark.parametrize('stage', ['START', 'END'])
def test_start_end_flag_disagreement_rejected(tmp_path, sources, stage):
    l, owner, _ = finished(tmp_path, sources)
    rewrite_flag(l, owner, stage, True)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'FAIL'
    assert 'START_END_TRANSPORT_CONFLICT' in r['reasons']


@pytest.mark.parametrize('value', [False, 0.0, '0', None, -1])
def test_manifest_counter_type_is_strict(tmp_path, sources, value):
    l, owner, _ = finished(tmp_path, sources)
    rewrite_output(l, owner, lambda c, m, p: m['counts'].update(injected_ends=value))
    assert inspect_archive_transport(l.path, owner.work_key)['state'] == 'FAIL'


def test_missing_manifest_count_remains_unverified(tmp_path, sources):
    l, owner, _ = finished(tmp_path, sources)
    rewrite_output(l, owner, lambda c, m, p: m['counts'].pop('injected_ends'))
    assert inspect_archive_transport(l.path, owner.work_key)['state'] == 'UNVERIFIED'


def test_no_claim_or_manifest_is_not_zero_injection_success(tmp_path, sources):
    l = ledger(tmp_path)
    assert inspect_archive_transport(l.path, '0' * 64)['state'] == 'UNVERIFIED'
    owner = claim(l, sources)
    assert inspect_archive_transport(l.path, owner.work_key)['state'] == 'UNVERIFIED'
    l.fail(owner.work_key, owner.owner_token, 'TEST_ABORT', now=LATER)
    assert inspect_archive_transport(l.path, owner.work_key)['state'] == 'UNVERIFIED'


def test_http_failure_with_false_flags_is_not_complete_success(tmp_path, sources):
    l, owner, _ = finished(tmp_path, sources, status=503)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['state'] == 'UNVERIFIED' and r['injected_ends'] == 0
    assert r['capture_state'] == 'PARTIAL'


def test_unmatched_injected_start_cannot_be_hidden_by_zero_end_count(tmp_path, sources):
    l = ledger(tmp_path); owner = claim(l, sources)
    cap = EvidenceArchive(tmp_path / 'partial.sqlite', full_day_phase(DAY, 'TEST'))
    key, spec = cap.keys[0], cap.specs[0]
    cap.append(key, 'START', dict(run_id=cap.run_id, key=key, spec=asdict(spec), stage='START',
        review_only=True, input_eligible=False, transport_injected=True, started_at=NOW.isoformat()))
    l.finish_from_archive(owner.work_key, owner.owner_token, cap.path, now=LATER)
    r = inspect_archive_transport(l.path, owner.work_key)
    assert r['injected_ends'] == 0 and r['injected_starts'] == 1 and r['state'] == 'FAIL'
    assert 'CAPTURE_RECEIPT_MISSING' in r['reasons']


@pytest.mark.parametrize('table,field', [('blobs', 'body'), ('objects', 'json')])
def test_corruption_cannot_be_admitted(tmp_path, sources, table, field):
    l, owner, _ = finished(tmp_path, sources)
    with sqlite3.connect(l.path) as conn:
        conn.execute(f'UPDATE {table} SET {field}=?', (b'bad' if table == 'blobs' else '{}',))
    assert inspect_archive_transport(l.path, owner.work_key)['state'] == 'FAIL'


def test_missing_store_is_not_created_and_caller_cannot_supply_counts(tmp_path):
    missing = tmp_path / 'does-not-exist.sqlite'
    assert inspect_archive_transport(missing, '0' * 64)['state'] == 'UNVERIFIED'
    assert not missing.exists()
    assert set(inspect.signature(inspect_archive_transport).parameters) == {'path', 'work_key'}
    with pytest.raises(TypeError):
        inspect_archive_transport(missing, '0' * 64, injected_ends=0)


@pytest.mark.parametrize('key', [None, '', 'z' * 64, '0' * 63, 123])
def test_invalid_keys_rejected_before_store_open(tmp_path, key):
    with pytest.raises(TransportBoundaryError):
        inspect_archive_transport(tmp_path / 'absent.sqlite', key)


@pytest.mark.parametrize('transport', [False, 0, [], object()])
def test_preflight_rejects_all_non_none_transports(transport):
    with pytest.raises(TransportBoundaryError, match='INJECTED'):
        require_noninjected_transport(transport, network_enabled=True)


@pytest.mark.parametrize('flag', [False, 1, 0, 'true', None])
def test_preflight_requires_explicit_boolean_authorization(flag):
    with pytest.raises(TransportBoundaryError):
        require_noninjected_transport(None, network_enabled=flag)


def test_preflight_can_pass_without_network_call_or_completion_claim():
    assert require_noninjected_transport(None, network_enabled=True) is None
