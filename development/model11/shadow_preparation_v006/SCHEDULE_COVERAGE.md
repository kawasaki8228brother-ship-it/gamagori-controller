# P4: supplied official-day schedule versus saved forecast evidence

Status: offline residual preparation only. This adds a **pure read-only
checker**, not a schedule fetcher, live database crawler, prediction writer,
LOCK edit, replay action, source parser, or production operation. Parent v005
software and saved forecasts remain unchanged. Real schedule/source approval
and real shadow execution are not provided or authorized.

## Interface and scope

```python
audit_schedule_coverage(schedule, predictions, *, target_date,
                        namespace="MODEL11_THIRD_RESEARCH",
                        expected_storage_id=None) -> report

frame_prediction_evidence(ledger, *, input_raw, forecast_raw, receipt_raw,
                          completion_raw, metadata_raw,
                          observation="READ_OK") -> JSON_safe_frame
```

Both functions operate only on caller-supplied memory values. No file, SQLite,
network, source, clock, store constructor, `initialize`, or write API is called.
The framing helper base64-encodes exact supplied bytes and whitelists ledger
fields; it does not authenticate a store. Base64 is transport encoding, not
encryption. Evidence exports containing raw input/forecasts remain private and
must not be committed publicly. Raw byte sizes are limited to 16,000,000 per
blob as a local resource guard, not a study or operational threshold.

An offline CLI may load pre-existing private JSON exports. The caller must
obtain them through independently reviewed read-only procedures. This module
does not supply a live-store extraction or backup mechanism. In particular,
calling v005 `initialize` or integrity methods that can set STOP is not a
read-only export. The included reproduction/tests use **only** a newly created,
closed, sidecar-free synthetic store; SQLite `mode=ro&immutable=1` in that
fixture is not an approved recipe for a concurrently active WAL database.

## Exact twelve-race schedule input

`schedule` contains:

```
raw_manifest_b64: base64 of exact UTF-8 JSON manifest bytes
manifest_bytes: exact integer byte count
manifest_sha256: full lowercase SHA-256 of those bytes
approval: {
    approved: true,
    declared_external_verification: true,
    venue: GAMAGORI,
    target_date: YYYY-MM-DD,
    source_id: bounded source identifier,
    manifest_sha256: same exact manifest digest,
    mapping_sha256: full digest,
    evidence_sha256: full review-evidence digest
}
```

The decoded manifest has exactly:

```
schema: OFFICIAL_DAY_SCHEDULE_V001_PROPOSED
venue: GAMAGORI
target_date: YYYY-MM-DD
source_id: bounded source identifier
races: [{race_id, race_no, deadline}, ...]
```

It must contain exactly twelve rows, twelve distinct explicit race IDs, and
each integer race number 1–12 exactly once. IDs are not generated from race
numbers or guessed from a date. Every deadline requires a strict RFC3339
timestamp with a known offset, and its JST calendar date must equal the
requested target date. Invalid clock/offset ranges such as `+08:60`, naive or
unknown `-00:00` offsets, excessive fractional precision, duplicate JSON keys,
nonfinite JSON constants, malformed/deep-recursion JSON, and wrong venue/date
HOLD. There is no automatic fill for a missing row or race ID.

Required approval fields are checked for exact local binding and explicit
boolean declarations. **They remain self-reported metadata.** An `approved`
flag, source name containing “official”, a review digest, or
`declared_external_verification=true` is not independent proof of authenticity
or actual HQ14/Claude approval. The report always retains
`external_schedule_authenticity=UNVERIFIED`. HQ14 must privately verify the
source, exact manifest/mapping bytes, review receipt, publication/correction
history, and actual official-day scope. None is invented by this checker.

## Prediction evidence frame

Each observation identifies the explicit scheduled `race_id`. The framing
helper produces:

```
evidence_schema: SHADOW_READONLY_EVIDENCE_V001_PROPOSED
race_id: exact saved-race identifier
observation: READ_OK
ledger: {
    race_key, namespace, race_id, storage_id,
    input_sha, model_sha, deadline, state, receipt_sha,
    committed_at, finalized_at
}
raw_blobs: {
    input_b64, forecast_b64, receipt_b64,
    completion_b64, metadata_b64
}
```

The ledger names are those of immutable v005: `race_key`, `input_sha`,
`model_sha`, and `receipt_sha`, not renamed guesses. `storage_id` comes from
the independently read OWNER/meta identity. `metadata_b64` contains the exact
`commit_metadata` SQLite BLOB. Tokens, sessions, PID data, and paths are not
exported by the whitelist. Optional `expected_storage_id` pins all observations
to a separately supplied reviewed storage identity; without it, identity
agreement remains local only.

`state=COMMITTED` alone is insufficient. The checker verifies:

- Namespace+race key, declared storage identity, ledger/receipt identifiers.
- Exact receipt SHA; exact input/forecast byte counts and hashes; exact commit
  metadata SHA; completion marker's receipt binding.
- The v005 independent-shadow envelope and actual inner source identity:
  SIMULATION uses `MODEL11_RESEARCH_V003`; PRIVATE_SHADOW uses
  `MODEL11_THIRD_RESEARCH`. A/B inputs cannot substitute for this namespace.
- Race/date/deadline agreement across schedule, ledger, receipt, envelope,
  and inner forecast; inner forecast SHA and model-spec/model hashes.
- Source payload SHA and commit metadata bindings to raw input and forecast.
- Snapshot ≤ generation ≤ persisted observation ≤ first ledger observation
  ≤ completion observation ≤ finalization, with **all** strictly before the
  approved schedule deadline. Equivalent known-offset instants are compared;
  invalid ranges are never normalized into apparently valid times.

Late saves, clock-chain inconsistencies, or mismatched dates/deadlines HOLD.
The checker does not rebuild probabilities or duplicate the predictor's
120-outcome, feature, normalization, course, or source-semantic validation.
Those prior gates remain required. Local SHA agreement cannot authenticate
history; `external_prediction_authenticity` is always UNVERIFIED. The stored
receipt also does not contain a separate final runner-readback timestamp, so
that observation stays `UNVERIFIED_NOT_IN_STORED_RECEIPT`. This is a local
saved-evidence coverage check, not a claim of complete runtime compliance.

## Missingness and failure distinctions

For each scheduled race, preserve these separate outcomes:

| Supplied observation | Local interpretation |
| --- | --- |
| No observation entry | NO_PREDICTION_OBSERVATION: no supplied evidence, not a zero or a proven failed save. |
| ABSENT | OBSERVED_ABSENT: caller explicitly reports absence; authenticity remains unverified. |
| NOT_SAVED | PREDICTION_NOT_SAVED: known unsaved attempt declared, not a read failure. |
| READ_FAILED | PREDICTION_READ_FAILED: cannot determine save/absence. |
| UNCERTAIN or pending/held ledger state | PREDICTION_SAVE_UNCERTAIN: no successful saved-forecast claim. |
| CORRUPT or invalid/mismatched bytes | Corrupt/unverified evidence; preserve separately from absence. |
| Valid chain reaching/passing deadline | PREDICTION_SAVED_LATE. |
| Wrong date / wrong deadline | Separate identity/deadline mismatch categories. |
| Complete valid supplied byte/time chain | SAVED_PREDEADLINE_LOCAL only. |

Duplicate schedule IDs, duplicate race numbers, duplicated prediction
observations, and unscheduled extra predictions HOLD. No first/last copy is
silently selected; no observations are automatically deduplicated. A corrupt
or unreadable row is not COUNT=0. Missing race-number output describes the
manifest defect; it does not fabricate missing schedule IDs or forecasts.

Reports expose counts, schedule/prediction indices, race numbers, and fixed
reason codes. They do not echo received raw bytes, race IDs, source URLs,
paths, tokens, arbitrary exception text, or approval prose. Counts refer only
to supplied observations; absent categories are not inferred as real zero
failures. Invalid schedule structure can prevent per-race checking entirely.

## Result meaning and evidence

`OBSERVATION_COMPLETE_LOCAL` requires all twelve unique scheduled races to
have exactly one valid supplied committed byte/time chain and no schedule,
observation, or approval-binding issues. Any other outcome is HOLD. This
status is distinct from authentic official-schedule verification, operator
approval, prediction quality, real-data readiness, production GO, or CLOSE.
`production_go` is always false. The checker neither opens missing evidence
elsewhere nor changes an existing writer, LOCK, task, forecast, or receipt.

Tests generate twelve **invented 2099** races through the unchanged actual
v005 runner/model/store demo once, close it, then export its saved bytes using
read-only SQLite. Synthetic manifest and review declarations explicitly do
not represent official source data or real approval. Focused negative cases
cover missing/duplicate schedule rows and observations, unapproved schedules,
wrong dates/deadlines, unsaved/read-failed/uncertain/corrupt evidence, late
finalization, key/owner/model/hash mismatches, malformed deep JSON, and no-I/O /
no-mutation behavior. Stored synthetic files are compared before/after audit.

```sh
python -B -m unittest discover -s tests -p test_shadow_preparation_coverage.py -v
```

Actual schedule/export access, live read-only extraction safety, mapping
approval, source authenticity, publication/revision history, complete-day
capture, and real operator authorization remain OPEN for HQ14/Claude private
review. No live crawler or production operation is implemented or approved.
