# P1 source mapping: pure captured-input adapter

**Candidate / PROPOSED / OFFLINE ONLY.** `LOCAL_CAPTURE_V001` is an invented
fixture format. It is not a parser for boatrace.jp, an official exhibition page,
or any other actual source. No actual official format, raw race original,
credential, production service or live HTTP endpoint has been accessed. The real
format/mapping, independent source provenance and operational approval are OPEN.

## API and execution boundary

```python
fixture = make_synthetic_source_fixture(canonical_synthetic_race)
adapter = SourceAdapter(fixture["mapping"])
report = adapter.convert(fixture["capture"])
```

Construction and conversion perform no file, socket, HTTP, application or .env
I/O. The constructor freezes a detached mapping and computes `mapping_sha256`.
The `mapping` property returns another detached copy. In-memory private mapping
mutation is detected. `convert` returns READY or HOLD with fixed reason codes,
never submitted URL/path/credential values or exception strings. READY means
internally consistent submitted claims; it is not independent authentication,
mapping approval, execution GO or model-performance evidence.

`FixtureTransport(captures_by_id)` is an explicit in-memory lookup, and optional
`SourceAdapter(mapping, transport).fetch(id)` accepts only that exact class.
Unknown/live/custom transport objects are not called. There is **no live HTTP
client**, no implicit fetch, no retry and no service discovery. The launch runner
must perform its disabled/default and approval gates before obtaining a capture
or initializing storage. An actual source transport/parser needs separate review.

## Frozen SOURCE_MAPPING_V001

The mapping has exactly these fields (plus conditional private review metadata):

| Field | Meaning |
|---|---|
| schema_version | SOURCE_MAPPING_V001 |
| version | Restricted identifier for this explicit mapping |
| format_id | LOCAL_CAPTURE_V001 or PRIVATE_REVIEWED_JSON_V001 |
| data_classification / synthetic | SYNTHETIC_ONLY / true or PRIVATE_REAL / false, actual booleans |
| source_id | Exact declared materialized-capture source identifier |
| raw_fields | RAW_V001 top-level destination field → source JSON pointer |
| course_fields | N1 course-context destination field → source JSON pointer |
| feature_specs | Frozen explicit feature units, directions and train-only transform declarations |
| feature_units | Exactly the five declared RAW feature units, matching feature_specs |
| course_source_ids | Exact frame/exhibition source IDs matching the declared class |

JSON pointers implement RFC6901 escaping (`~0`, `~1`), dictionary keys and strict
zero-based list indices. Missing pointers, malformed paths, missing values or
unknown units HOLD. There is no numeric conversion, default filling, inferred
schema, scraped-string interpretation or implicit standardization. The mapper
copies reviewed canonical blocks; it cannot turn an unknown actual official
format into a verified RAW schema by guessing field semantics. New real source
formats or transformations remain OPEN pending exact private originals/review.

The RAW fields are exactly schema_version, data_classification, race_id,
target_date, venue, prediction_at, race_provenance, deadline, active_boats,
active_boats_provenance, boats, odds_snapshot. The course fields are exactly
course_inputs, course_policy_id, course_policy_sha256, data_classification,
synthetic. The old RAW validator and N1-fixed course validator still enforce
their full contracts. Course numeric values and exact per-state timestamps must
match the selected pre-LOCK observation; unused present source observations are
also checked. No result/actual-entry data is substituted into course inputs.

Registered capture sources are SYNTHETIC_LOCAL_CAPTURE_V001 for synthetic and
OFFICIAL_REVIEWED_LOCAL_CAPTURE_V001 for private. Course IDs remain the exact
N1-approved declarations for FRAME_NUMBER and EXHIBITION_ENTRY. OFFICIAL prefixes
are not authentication and unregistered prefix lookalikes HOLD. These source
names are interface declarations, not evidence that an actual official parser
has been implemented or that a real record originated there.

Private mapping requires `review_evidence={hq14_review_sha256,
claude_review_sha256}`, both full hashes matching the feature-spec review
metadata. Private feature specs must declare HQ14_PRIVATE_MAPPING_UNVERIFIED.
Synthetic invented mapping cannot be used with a private classification. Review
hashes are **SELF_REPORTED_HASHES_ONLY**: their presence does not prove a review,
its scope, PASS, authority or Andy's execution GO. Launch approvals and
independent artifact checks are separate mandatory gates.

## Capture: exact materialized bytes and history

The capture object has exactly:

```text
format_id, data_classification, synthetic, source_id
payload_bytes: actual bytes containing one UTF-8 JSON document
payload_sha256: SHA-256 of those exact original bytes
acquired_at, available_at, revision_at
history: [ {payload_sha256,evidence_sha256,acquired_at,available_at,revision_at}, ... ]
```

Payload size is 1 byte–4 MiB. Invalid UTF-8/JSON, duplicate JSON keys, NaN/infinity,
hash mismatch or missing fields HOLD. No raw exception body is printed. The
runner should retain **capture.payload_bytes unchanged** in its new private
owned store, alongside returned source_evidence; reserializing JSON is not a
substitute for the original captured bytes. Public evidence contains invented
fixtures only; never upload private captures or source credentials.

The envelope denotes this complete **materialized payload version**, not the
publication timestamp of one underlying source. All three envelope times must
be <= prediction and must be at/after the respective latest known component time
across RAW identity/deadline/field states/motor/features/odds and both non-null
course observations. A supposedly complete payload cannot be available before
one of its included components. Acquisition <= availability and acquisition <=
revision. No clock time is invented or inferred to repair an inconsistency.

All timestamps are strict timezone-aware seconds with at most six fractional
digits. Naive times, `-00:00`, malformed offsets including +09:99/+24:00, future
availability or late revisions HOLD. History requires 1–256 entries, valid
hashes/timestamps, nondecreasing revision times and a final entry whose exact
payload hash and three times match the current envelope. Every history entry is
preserved in source_evidence. Earlier payload bytes and independent chronology
are not available to this module: history hashes alone do not authenticate those
versions. HQ14 must separately preserve/check private earlier originals.

## Output and classification preservation

```text
READY:
  raw: validated RAW_V001 object
  course: validated N1 course context, including original class and strict flag
  source_evidence: frozen mapping SHA, original byte count/hash, envelope times,
                   history, both course observations, counts, warnings,
                   external_authenticity=UNVERIFIED, actual_official_mapping=OPEN
  reasons: []
  production_go: false
HOLD:
  raw: null
  course: null
  reasons: fixed machine codes only
  production_go: false
```

Private classification is never relabeled synthetic. RAW uses its existing
HQ14_PRIVATE_OFFLINE enum while the N1 course context preserves PRIVATE_REAL
and synthetic=false; both are explicitly checked against capture and mapping.
This is a documented enum bridge between two existing contracts, not invented
synthetic truth. The runner normalizes raw with the separately approved frozen
normalizer, attaches the returned course context, then revalidates before any
new research forecast. The adapter does not train/refit or call a prediction.

Launch-source completeness is stricter than the older model-only RAW path:
missing, stale, future, malformed or incomplete odds HOLD. Six boats require
all 120 ordered triples with correct gross-payout units and full provenance.
Reduced-field RAW may be represented with its complete permutation domain;
source_evidence reports actual active/ticket counts, and the launch runner's
separate six-active gate HOLDs it. There is no false claim of 120 observations.
Known F/L=true remains an explicit flag/warning; no new penalty, LOCK rule or
betting rule is invented. Unknown or future F/L/course/scratch state HOLDs.
An internal zero-valued schema probe validates N1 shape only; it is never
returned, fitted, saved as a forecast, or used for prediction. Missing raw
features/exhibition are rejected before this probe; no zero imputation occurs.

## Synthetic fixture and OPEN inputs

`make_synthetic_source_fixture` only accepts explicit synthetic=true,
SYNTHETIC_ONLY year2099 races. It builds invented canonical RAW and course blocks,
JSON pointers, original bytes and a current-version history receipt. If needed it
uses the existing invented course fixture; it never reconstructs an actual
official record. The physical-looking raw-unit transformations remain the old
PROPOSED synthetic plumbing, not adopted real feature definitions.

Before any real path can be reviewed, HQ14 must provide privately: exact format
specification and source identity; approved JSON field/block mapping; raw units
and definitions; capture materialization semantics; per-field availability and
revision history; motor replacement identity/version; exhibition snapshots;
complete pre-LOCK odds originals; independent review originals and bound artifact
hashes. No such actual official mapping or independent source proof is provided
by this development. Existing A/B, Model1.0, BOXV1, production storage, LOCK,
deadline decisions and prior source code remain unchanged.

Reproduce synthetic tests without any source connection:

```sh
python -B -m unittest discover -s tests -p test_shadow_launch_sources.py -v
```
