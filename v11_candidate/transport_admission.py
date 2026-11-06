"""Fail-closed transport-record gate candidate; not production authorization.

Stage15 COMPLETE remains a capture/storage status, including honest replays.
This separate read-only gate inspects the bound START/END records, not a caller's
summary count. False declarations are not proof of real networking. The result
basis, producer trust and actual runtime wiring remain outside this narrow gate.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import hashlib
import re
import sqlite3

from .archive_execution import ArchiveExecutionLedger, LedgerError
from .contracts import canonical


POLICY_ID = 'CAPTURE_NONINJECTED_RECORDS_V1_CANDIDATE'


class TransportBoundaryError(ValueError):
    pass


def require_noninjected_transport(transport: object | None, *, network_enabled: bool) -> None:
    """Prospective BEFORE-request guard; rejects any injected transport object.

    Merely defining/calling this function does not constrain a bypassing worker.
    No requests, retries, scheduler, credentials or state changes occur here.
    """
    if type(network_enabled) is not bool:
        raise TransportBoundaryError('NETWORK_FLAG_MUST_BE_BOOLEAN')
    if transport is not None:
        raise TransportBoundaryError('INJECTED_TRANSPORT_FORBIDDEN')
    if network_enabled is not True:
        raise TransportBoundaryError('NETWORK_NOT_AUTHORIZED')


def inspect_archive_transport(path: Path, work_key: str) -> dict:
    """Inspect one Stage15 review ledger in a single read-only transaction.

    No manifest/count/expected outcome can be supplied by the caller. Existing
    objects and bodies are hash-checked by the ledger reader. Flags are checked
    on BOTH START and END with strict bool typing; missing is not false. A zero
    injected_ends count is necessary but insufficient for this gate to pass.

    PASS means only complete capture records declare no injected transport.
    It does not authenticate the producer, prove that GETs actually ran, verify
    the transport provenance of the 12 result inputs, or approve production use.
    """
    if type(work_key) is not str or re.fullmatch(r'[0-9a-f]{64}', work_key) is None:
        raise TransportBoundaryError('INVALID_WORK_KEY')
    failed, unknown = [], []
    out = dict(policy_id=POLICY_ID, work_key=work_key, event_hash=None,
               decision_hash=None, manifest_hash=None, capture_state=None,
               recorded_counts=None, recomputed_counts=None, receipt_evidence=[],
               records_with_injected_transport=0, injected_starts=0, injected_ends=0,
               missing_transport_flags=0, invalid_transport_flags=0,
               ledger_graph_verified=False, stable_read_transaction=False,
               inspection_scope='CAPTURE_OUTPUT_TRANSPORT_DECLARATIONS_ONLY',
               review_only=True, network_execution_proven=False,
               decision_basis_transport_checked=False, production_authorized=False,
               runtime_integration=False)
    try:
        ledger = ArchiveExecutionLedger(Path(path))
        with closing(ledger._connect(True)) as conn:
            conn.execute('BEGIN')
            out['stable_read_transaction'] = True
            job = ledger._job(conn, work_key)
            if job is None:
                unknown.append('JOB_NOT_FOUND')
            else:
                event_hash, event = job
                out.update(event_hash=event_hash, decision_hash=event['decision_hash'],
                           manifest_hash=event['capture_manifest'], capture_state=event['state'])
                if event['state'] != 'COMPLETE':
                    unknown.append('CAPTURE_NOT_COMPLETE')
                if not event['capture_manifest']:
                    unknown.append('CAPTURE_MANIFEST_MISSING')
                else:
                    manifest = ledger._get(conn, event['capture_manifest'], 'CAPTURE_MANIFEST')
                    if (manifest.get('role') != 'POST_DECISION_CAPTURE_OUTPUT_NOT_DECISION_BASIS'
                            or manifest.get('review_only') is not True):
                        raise LedgerError('MANIFEST_ROLE_OR_REVIEW_FLAG')
                    targets = manifest['targets']
                    counts = manifest.get('counts')
                    if type(counts) is not dict or any(type(n) is not int or n < 0 for n in counts.values()):
                        raise LedgerError('MANIFEST_COUNTS_TYPE')
                    out['recorded_counts'] = dict(counts)
                    if 'injected_ends' not in counts:
                        unknown.append('INJECTED_END_COUNT_MISSING')
                    for target in targets:
                        refs = target['receipt_refs']
                        if type(refs) is not dict or set(refs) - {'START', 'END'}:
                            raise LedgerError('UNEXPECTED_RECEIPT_STAGE')
                        flags = {}
                        for stage in ('START', 'END'):
                            ref = refs.get(stage)
                            if ref is None:
                                unknown.append('CAPTURE_RECEIPT_MISSING')
                                continue
                            record = ledger._get(conn, ref, 'CAPTURE_RECEIPT')
                            p = record['original_payload']
                            present = 'transport_injected' in p
                            flag = p.get('transport_injected')
                            valid = type(flag) is bool
                            out['receipt_evidence'].append(dict(
                                source_key=target['source_key'], spec=target['spec'], stage=stage,
                                object_hash=ref, payload_hash=record['original_payload_sha256'],
                                body_sha256=record['body_sha256'],
                                declaration_present=present, declaration_type=type(flag).__name__,
                                transport_injected=flag if valid else None))
                            if not present:
                                out['missing_transport_flags'] += 1
                                unknown.append('TRANSPORT_DECLARATION_MISSING')
                            elif not valid:
                                out['invalid_transport_flags'] += 1
                                failed.append('TRANSPORT_DECLARATION_NOT_BOOLEAN')
                            else:
                                flags[stage] = flag
                                if flag:
                                    out['records_with_injected_transport'] += 1
                                    out['injected_starts' if stage == 'START' else 'injected_ends'] += 1
                                    failed.append('INJECTED_TRANSPORT_PRESENT')
                        if set(flags) == {'START', 'END'} and flags['START'] != flags['END']:
                            failed.append('START_END_TRANSPORT_CONFLICT')
                    if (out['missing_transport_flags'] == 0 and out['invalid_transport_flags'] == 0
                            and 'injected_ends' in counts):
                        if counts['injected_ends'] != out['injected_ends']:
                            failed.append('INJECTED_END_COUNT_CONFLICT')
                        # Rebuild target/body/capture counts using the existing reader,
                        # after strict flag typing. No bool/int or missing->false coercion.
                        recomputed = ledger._verify_capture(conn, manifest, event)
                        out['recomputed_counts'] = recomputed
                        out['ledger_graph_verified'] = True
                        if any(recomputed[k] != 24 for k in ('planned', 'starts', 'ends', 'bodies', 'complete_http200')):
                            unknown.append('CAPTURE_COVERAGE_INCOMPLETE')
                    else:
                        unknown.append('FULL_CAPTURE_GRAPH_VERIFICATION_INCOMPLETE')
    except (OSError, sqlite3.OperationalError) as exc:
        unknown.append('LEDGER_UNAVAILABLE:' + type(exc).__name__)
    except (LedgerError, KeyError, TypeError, ValueError, sqlite3.DatabaseError) as exc:
        failed.append('LEDGER_VERIFICATION_FAILED:' + type(exc).__name__)
    state = 'FAIL' if failed else 'UNVERIFIED' if unknown else 'PASS'
    out.update(state=state, capture_record_gate_passed=state == 'PASS',
               reasons=sorted(set(failed + unknown)))
    out['binding_sha256'] = hashlib.sha256(canonical(out).encode('utf-8')).hexdigest()
    return out
