# Operational A OBS QA — offline normalized proposal

This tool performs read-only observations on supplied strings. It does not
query Airtable, open an Automation, repair Events, produce a new OBS event,
change a schema, decide LOCK eligibility, or certify actual production data.
Its input contract is PROPOSED normalization, **not** the independently
verified field mapping or complete OBS contract of current A.

## Confirmed scope versus missing authority

HQ14's answer confirms that A's RUN_START and RUN_END are operational OBS.
`producer_run_id` is retained, and their idempotency keys are separate:

```
SHA256(UTF8("1|A|" + producer_run_id + "|RUN_START"))
SHA256(UTF8("1|A|" + producer_run_id + "|RUN_END"))
```

Start/end time, stages, actual errors, and canonical-JSON SHA verification
before/after are retained requirements in the answer. This does not supply
the current payload field names, complete current OBS version/body/hash,
canonicalization implementation, or independent evidence of producer history.
The checker compares supplied normalized values; it cannot authenticate them.
It never imports A's task, edits its prediction text, or reproduces B under A.

The related reference is A main v3 / Model 1.0 FROZEN /
`execution_patch=2026-09-18.1`. The received hash labelled `SHA256` is preserved
exactly:

```
d462767f4448e28fc735df7363fb1a75137c5e7f
```

It has **40 hexadecimal characters**, not 64. Algorithm and any truncation are
UNVERIFIED. It is not silently relabelled, padded, repaired, or treated as the
OBS contract hash. No independently matched full OBS contract/version/SHA was
provided. The same distinction is included in every QA report.

These four questions remain UNVERIFIED independently:

1. Is UUID mandatory inside the payload?
2. Can a column-side UUID alone make a record eligible?
3. May RUN_START use an empty source_evidence array when no external fetch
   occurred?
4. Is omission of the source_evidence property a formal contract violation?

Missing payload UUID is therefore **not** a formal FAIL here. Empty arrays
are **not** uniformly FAIL. No absent property is silently filled or promoted
to an existing implementation requirement.

## Pure API and normalized local input

```python
audit_obs_rows(rows) -> dict
confirmed_a_idempotency(producer_run_id, event_kind) -> sha256_hex
make_synthetic_obs_fixture() -> dict
```

`audit_obs_rows` uses only caller-supplied memory. It performs no filesystem,
network, credential, database, writer, task, clock, or execution-origin action.
Input rows have this PROPOSED local representation:

```
{
  columns: {
    event_uuid?, source?, producer_run_id?, event_kind?, idempotency_key?
  },
  payload_raw: exact JSON string,
  hashes: {
    raw_sha256?,
    canonical_before_sha256?,
    canonical_after_sha256?
  }
}
```

`event_uuid` is the explicitly supplied user field name, in both columns and
payload. It is not renamed or copied while hashing; no `uuid` alias is merged.
Its requiredness remains UNVERIFIED. Other field mapping/requiredness remains
the normalized local proposal, not an independently matched producer contract.
The payload object may provide the same normalized identity fields,
`source_evidence`, `started_at`, `ended_at`, `stages`, and `errors`. These names
are an offline interface, **not** evidence that current A uses these exact
names or requires their presence. Actual mapping is OPEN. The payload string
is not rewritten or reserialized back into input records. Missing properties,
null, empty strings, and provided values remain distinct observations.

The local raw-size guard is 1,000,000 UTF-8 bytes; duplicate JSON keys,
unreadable/non-object JSON, NaN/Infinity, malformed UTF-8, or recursion failures
produce fixed diagnostic codes, never exception text or a fabricated payload.
This local resource/representation check is not an official A contract limit.

Column/payload UUID, source, producer ID, event kind, and idempotency values
are compared where provided. Reports expose only comparison states such as
MATCH, MISMATCH, MISSING_PAYLOAD, MISSING_COLUMNS, NULL_PAYLOAD, or BOTH_NULL.
An explicit discrepancy is labelled INCONSISTENCY; missing authority or
information remains CONTRACT_UNVERIFIED. Neither label is a formal Events /
OBS / LOCK validity decision.

Explicit column-side B or LOCK metadata is excluded without processing it
under A's formula or contract. A conflicting A/payload source or event kind
is unresolved and no A formula is applied. Missing/ambiguous producer identity
is not replaced by UUID, a generated ID, another row, or a selected winner.

## Source-evidence categories

The local normalized array-item labels are proposals only; they are not a
guessed mapping of an actual official or task payload format.

| Observation | Report category |
| --- | --- |
| Property absent | MISSING_FIELD |
| Explicit null | NULL |
| Exact empty list | EMPTY_ARRAY |
| Nonempty array entirely `{status: MISSING}` or the local `EXPLICIT_MISSING` label | EXPLICIT_MISSING |
| Entirely `{status: FETCH_FAILED}` | FETCH_FAILED |
| Entirely `{status: DECLARED_NORMAL}` | DECLARED_NORMAL |
| Mixture of known distinct labels | MIXED |
| Wrong container/item type or unrecognized normalized label | MALFORMED |

The literal MISSING label is explicitly supplied input semantics; its bucket
does not rewrite any raw string or hash. Unknown OK/ERROR aliases are not
guessed. MALFORMED means outside this **proposed normalized representation**, not a
formal violation by actual A. A source's DECLARED_NORMAL flag is a claim, not
verified retrieval or provenance. Failed-fetch/error declarations likewise
are not authenticated by this tool. RUN_START may represent operational work
before external fetching; an empty source array stays CONTRACT_UNVERIFIED
unless the independent formal contract settles its meaning.

Presence/counts of start/end fields, stages, and errors are recorded without
echoing actual timestamp values, stage bodies, source URLs, error text, or
producer identifiers. Absent data is not fabricated. Actual error content
remains in the caller's unchanged protected payload; QA does not replace it
with a synthetic success/failure description.

## Hash and idempotency interpretation

`raw_sha256` is compared with SHA-256 of the exact supplied UTF-8 string bytes.
This proves local byte agreement only. The before/after declarations are
compared with each other and with a **local proposed** canonical profile:
sorted keys, compact separators, ASCII escaping, no NaN/Infinity.

Equal supplied before/after digests do not prove that a real producer performed
those checks at the claimed times. Matching the local canonical profile does
not verify A's actual canonicalizer. Consistent equal digests that differ from
this proposed profile remain CONTRACT_UNVERIFIED, not an A canonicalization
violation. Different provided before/after SHA values are an observed
inconsistency. Hash format/algorithm labels are not silently corrected.

The confirmed A formula is evaluated only for unambiguous A RUN_START/END
and one provided nonempty producer identity. Each provided key is compared
with that computed result. Conflicting producer IDs are not arbitrarily
chosen. Missing key placement inside a payload is not adopted as a new
mandatory rule. Reports contain match flags and counts, not run/key values.

Repeated identical key/raw observations are counted, not deduplicated or
repaired. A shared key with different raw payloads is flagged as an observed
inconsistency for review; no row is selected as authoritative and no claim is
made about unverified production update/retry semantics. RUN_START and RUN_END
remain separate even for the same producer ID.

## Outputs and synthetic evidence

Per-row statuses are OBSERVED, CONTRACT_UNVERIFIED, INCONSISTENCY, or
OUT_OF_SCOPE. OBSERVED means only that supplied observations agreed; it is
not VALID, eligible LOCK, a real source success, or permission to apply.
The report contains row indices, fixed reason codes and counts. It omits raw
payloads, actual UUIDs, producer IDs, idempotency keys, source URLs, error
values, and arbitrary submitted exception text. `query_completeness` remains
UNVERIFIED_NO_SOURCE_QUERY_PERFORMED: zero supplied rows never proves zero
Airtable events or a successful query.

`make_synthetic_obs_fixture()` creates twenty invented rows with explicit
SYNTHETIC_ONLY classification, 2099 times, and purpose
NOT_2026_11_05_OBS_RECONSTRUCTION. It matches **only** the requested count
pattern:

- 12 rows omit payload UUID while retaining a column UUID.
- One omits source_evidence; three have empty arrays.
- All twenty agree with their supplied local canonical hashes and confirmed
  synthetic A idempotency formula; twenty distinct keys are observed.

These are neither the 11/5 records nor a reconstructed distribution of their
errors, provenance, contents or eligibility. Their 20/20 local results do not
validate current A or close the missing-contract questions.

```sh
python -B -m unittest discover -s tests -p test_health_obs_qa.py -v
```

The focused tests cover the exact synthetic counts, known START/END SHA
vectors, UUID missing/null/discrepancy, all source-evidence categories,
unresolved source/producer identity, B/LOCK exclusion, raw/pre-post/profile
differences, duplicate-key observations, privacy, and no-I/O/no-mutation.
Full actual OBS contract/mapping, independent canonical profile, source
authenticity, source-query completeness, and any formal production decision
remain OPEN for HQ14/Claude review and separate Andy GO.
