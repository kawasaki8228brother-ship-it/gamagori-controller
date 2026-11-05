# Dynamic schedule states — normalized local proposal

This is a new **pure, offline checker**. Expected active races come from the
supplied approved-manifest declaration rather than a hardcoded twelve-row
rule. The old v006 fixed-twelve checker and all parent files remain unchanged.
No source fetcher, official parser, writer, LOCK edit, task operation,
prediction replay, or cancellation feed is implemented. Real official-field
mapping, source approval, and notice authenticity remain OPEN/UNVERIFIED.

## API and preserved evidence

```python
audit_manifest_coverage(schedule, predictions, *, target_date,
                        expected_storage_id=None) -> report
```

Inputs are JSON-safe supplied values. The function does not read files, SQLite,
clocks, services, credentials, or source endpoints and never changes inputs.
Active rows reuse the pinned parent v006 `_prediction` byte/receipt/identity/
timing verifier from commit `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`.
They do not use a new weaker saved-state test. Prediction frames are exactly
the retained v006 format; a COMMITTED string alone remains insufficient.

The result is OBSERVATION_COMPLETE_LOCAL only when the entire supplied current
manifest, status proofs, and required active predictions agree locally.
Otherwise it is HOLD. These are neither authentic official-source verdicts
nor permission to run anything. `production_go` is always false, and source /
cancellation authenticity always remains UNVERIFIED.

## Local schedule envelope

The contract below is **PROPOSED normalized local JSON**, not a claim about
any current official site's fields, API, status strings, or actual mapping.
HQ14 must privately review a real field mapping before a real-data use.

```
schedule = {
  raw_manifest_b64, manifest_bytes, manifest_sha256,
  mapping, mapping_sha256,
  approval,
  status_evidence: {full_evidence_sha: evidence_frame, ...}
}
```

`raw_manifest_b64` carries exact UTF-8 JSON bytes; count and full SHA-256 must
match. Base64 is transport encoding, not encryption. The mapping object has
exactly:

```
schema: LOCAL_RACE_SCHEDULE_MAPPING_V001_PROPOSED
mapping_id: bounded identifier
mapping_version: bounded version identifier
venue: GAMAGORI
source_id: bounded identifier
classification: SYNTHETIC_ONLY | PRIVATE_REAL
event_scope: RACE_EVENT
normalized_statuses: [SCHEDULED, CANCELLED_OFFICIAL, WITHDRAWN_OFFICIAL]
```

`mapping_sha256` is SHA-256 of canonical JSON (sorted keys, compact separators,
ASCII escaping, no NaN/Infinity). The decoded manifest has exactly:

```
schema: LOCAL_DAY_SCHEDULE_V002_PROPOSED
venue: GAMAGORI
target_date: YYYY-MM-DD
source_id: same mapping source
classification: same mapping classification
mapping_sha256: same full digest
races: [{race_id, race_no, deadline, status, status_evidence_sha256}, ...]
closed_official_evidence_sha256: null | full digest
```

`approval` requires explicit boolean `approved=true` and
`declared_external_verification=true`, plus matching venue, target-date,
source-id, classification, mapping-SHA, manifest-SHA, and a full
`evidence_sha256`. These are **self-reported review metadata**, not independent
proof that HQ14/Claude approved anything. A source name containing “official”
or a consistent self-hash does not authenticate origin.

Race IDs and numbers must be explicit and unique. Race numbers are positive
integers (local schema resource range 1–99); their numeric gaps are not filled
and the checker does not infer how many real venue races should exist. Each
deadline must be strict known-offset RFC3339 on the requested JST day. Duplicate
IDs, duplicate numbers, conflicting status declarations, wrong dates, invalid
offset/time ranges, unknown statuses, or unbound proof hashes HOLD.

## Race states and notice proof

- SCHEDULED is an active expected race and requires a valid saved prediction
  observation. Its `status_evidence_sha256` is null.
- CANCELLED_OFFICIAL excludes the **race event** under this current manifest
  only after its notice proof binds locally.
- WITHDRAWN_OFFICIAL also describes a **race event**. It does not mean a boat
  scratched, a competitor withdrew, or an absent forecast.

Missing predictions, absent rows, READ_FAILED, boat flags, or an empty list
never generate either excluded status. A status declaration without valid
proof HOLDs; it is not silently treated as an approved exclusion.

Each referenced evidence frame has `raw_evidence_b64`, integer
`evidence_bytes`, and exact `evidence_sha256`, also equal to its map key.
Decoded race-status proof has exactly:

```
schema: LOCAL_RACE_STATUS_EVIDENCE_V001_PROPOSED
event_scope: RACE_EVENT
status: CANCELLED_OFFICIAL | WITHDRAWN_OFFICIAL
race_id, race_no
venue, target_date, source_id, classification
mapping_sha256, mapping_version
effective_at, acquired_at, available_at, revision_at
```

Identity, date, status, classification, source, mapping hash, and version must
match the row/header. All times require explicit valid offsets. Acquired and
revision times cannot exceed available time; the effective event cannot be
after the target JST day. Earlier effective dates can represent a prior-day
announcement taking effect for a later race day. Effective time need not be
after announcement time: a future-effective notice can be known beforehand.
Actual source time semantics and truth still require independent review.

Unused or conflicting notice records HOLD rather than choosing a convenient
revision. This minimal contract represents one selected current snapshot, not
a notice-history resolver; historical corrections require an independently
reviewed selection. No real status code mapping is guessed.

## Existing forecasts and deadline obligations

Excluded-race observations remain supplied and unmodified. They are reported
as UNASSESSED_OFFICIAL_EXCLUSION, not rewritten, deleted, retimed, converted
to a miss, or labelled invalid merely because a later cancellation exists.
Their raw byte presence and declared read-failure status are counted
separately from active requirements. `excluded_predictions_present` means
supplied READ_OK forecast bytes, not an authenticity/validity verdict;
`excluded_observations_supplied` also counts absent/failed/uncertain observation
entries. `excluded_read_failed` is separate from active `read_failed`.

Where receipt/forecast hashes and generation attributes bind locally, the
report shows effective-versus-generation and evidence-known-versus-generation
relations. The latter conservatively uses the latest acquired/available/
revision observation. This is a byte-bound timestamp comparison, not proof of
when the official public or the production operator actually knew a notice.
Unreadable or unbound timing remains UNVERIFIED; the excluded prediction is
not automatically assessed by the active coverage verifier.

**A current/day-end cancellation does not retroactively waive the original
first-LOCK or AC1 obligation.** Effective-versus-deadline is explicit, including
AFTER_DEADLINE. This checker has no original predeadline schedule snapshot or
AC1 intervention evidence. It therefore always reports:

```
ac1_or_first_lock_assessment = NOT_PERFORMED_CURRENT_MANIFEST_ONLY
prior_deadline_obligation = UNVERIFIED_ORIGINAL_SNAPSHOT_NOT_PROVIDED
active_expected_basis = DECLARED_SCHEDULED_ROWS_NOT_AC1_OR_LOCK_DENOMINATOR
lock_semantics = UNCHANGED
```

Even locally bound cancellation before the deadline is not an AC1 PASS here.
The original opportunity set, notice availability, intervention record, and
denominator treatment require separate authorized review. No existing LOCK
validity, AC1 writer, timing rule, or saved forecast is changed.

## Zero active races and missingness

A nonempty manifest where every race is cancelled/withdrawn can have zero
active expected races only if **each** exclusion proof binds locally. An
empty manifest alone HOLDs. An explicitly reviewed closed-day declaration
requires `closed_official_evidence_sha256` and a proof with:

```
schema: LOCAL_OFFICIAL_DAY_CLOSURE_EVIDENCE_V001_PROPOSED
event_scope: OFFICIAL_DAY
status: CLOSED_OFFICIAL
venue, target_date, source_id, classification, mapping_sha256, mapping_version
effective_at, acquired_at, available_at, revision_at
```

It has no fabricated race ID/number. Its hash, source/class/version and times
obey the same checks. A closure proof combined with nonempty race rows HOLDs
as an ambiguous snapshot. Extra predictions whose IDs are absent from that
empty manifest remain preserved/unassessed and cause HOLD; the checker does
not invent cancelled race IDs for them.

Active expected count comes from declared SCHEDULED rows, independently of
prediction availability. Active `no_observation`, `read_failed`, `not_saved`,
`uncertain`, `late`, and other-invalid counts remain separate. Official status
counts describe locally bound exclusions only. Invalid proof or an unknown
manifest means HOLD, not a validated reduced obligation denominator.
No automatic fill, first/last-copy selection, duplicate elimination, or
missing-as-zero settlement occurs. Outputs expose indices, race numbers,
counts, timing relations and fixed reason codes; raw IDs, tokens, paths,
URLs, notices and arbitrary exception text are not echoed.

## Reproduction and boundaries

Tests decode the retained v006 `SYNTHETIC_ONLY` gzip/base64 evidence bundle and
its invented 2099 schedule. They do not rerun predictions or create a new
v005 store. Synthetic local mapping, cancellation and closure notices are
invented solely to exercise this PROPOSED interface, never represented as
actual official notices or approval.

`tests/test_offline_refinements_schedule.py` exposes offline-only
`build_fixture(case="full")`, returning schedule, predictions, target-date,
expected-owner and an explicit SYNTHETIC_ONLY label. Cases include short8,
one_cancelled, one_withdrawn, one_cancelled_with_prediction,
cancel_after_deadline_with_prediction, all_cancelled, empty, and empty_closed.
The reproduction driver may import this test helper explicitly for synthetic
demonstration only; it is not a live input adapter.

```sh
python -B -m unittest discover -s tests -p test_offline_refinements_schedule.py -v
```

Actual official schedule completeness, source time semantics, normalized
field mapping, notice/correction authenticity, original predeadline snapshot,
AC1 denominator treatment, and real operator GO remain OPEN. Development
readiness, independent review, real-data validation, production application,
natural-run verification and CLOSE are separate decisions.
