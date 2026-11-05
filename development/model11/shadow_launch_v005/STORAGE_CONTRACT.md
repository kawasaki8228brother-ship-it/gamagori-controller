# v005 local research evidence store

This is a new, explicitly initialized, local-only third-research store. It
does not open a production DB or contact Render, Airtable, Drive, Automations,
or a source endpoint. Existing model, A/B, LOCK, BOX Ver.1, and parent artifacts
are unchanged. Construction performs no filesystem, clock, RNG, or SQLite I/O.
The runner's default DISABLED gate must short-circuit before `initialize` or
any source/store operation. Storage itself is not an authorization system.

Only invented 2099 SYNTHETIC_ONLY data were tested. A future private launch
requires separately verified authority, configuration, source, normalizer,
course, model, comparison, evaluation, storage, code, and operator evidence.
Presence of this implementation, a local owner marker, a self-hash, or matching
SQLite rows does not establish independent approval or real-data authenticity.
No execution GO or actual performance conclusion follows.

## API fixed for the candidate

```python
ShadowStore(root, namespace="MODEL11_THIRD_RESEARCH", clock=None, fault=None)
initialize()
bind_context(context_sha256)
reserve(race_id, input_sha256, model_sha256, deadline)
commit(reservation, input_raw: bytes, forecast_raw: bytes, metadata: dict)
readback(race_id)
list_forecasts()
mark_hold(reservation, reason="OPERATOR_HOLD")
stop(reason="OPERATOR_STOP")
is_stopped()
save_result(race_id, raw_result: bytes, metadata: dict)
list_results(race_id)
read_result(race_id, result_sha256)
select_result(race_id, result_sha256, selection_metadata)
read_selected_result(race_id)
save_audit_report(kind, identity, raw_bytes: bytes, metadata=None)
read_audit_report(kind, identity, report_sha256)
close()
```

`clock` is a callable returning an aware datetime or strict aware ISO timestamp;
default is local UTC time. Unknown offsets (`-00:00`), naive timestamps, and
precision beyond six fractional digits are rejected. Clock accuracy and the
truth of supplied generation timestamps require external verification; this
is not a timestamp authority. `fault(stage)` is a local testing hook, not a
retry callback or external transport.

`initialize` creates a new root only when its parent already exists. It may
adopt an existing **empty** local directory, but never a nonempty unowned root.
It rejects symlinks in the root/ancestors/owned tree and verifies the exact
namespace and storage identity. Wrong namespaces or unreviewed ledger formats
STOP. There is no automatic schema migration, directory change, cleanup, or
repair. Repeated/concurrent initialization of one instance is serialized,
revalidates ownership/STOP, and retains its original reservation session. A
forked child must construct its own instance rather than reuse an inherited
open-session object.

Successful initialization returns `READY`, `storage_id`, and `namespace`.
An owned root with a STOP flag returns HOLD. Unowned/invalid initialization
returns STOP without altering the unowned target. If safe durable STOP cannot
be written, the result remains STOP/HOLD/STOP_UNCERTAIN and must not be treated
as durably closed evidence.

## Layout and ownership

All names below are relative to the new approved local root, not production
paths or instructions to create a live store:

```
OWNER.json
ledger.sqlite3                  # New SQLite ledger only; its own auxiliaries
STOP.json                       # Immutable first durable STOP, if required
artifacts/<namespace-race-key>/input.raw
artifacts/<namespace-race-key>/forecast.raw
artifacts/<namespace-race-key>/receipt.json
artifacts/<namespace-race-key>/completion.json
results/<namespace-race-key>/<result-SHA256>.raw
audits/<kind>/<identity-SHA256>/<report-SHA256>.raw
audits/<kind>/<identity-SHA256>/<report-SHA256>.receipt.json
```

Keys are SHA-256 of `namespace + NUL + race_id`. Model updates do not change the
idempotency key. Bounded identifiers and full lowercase SHA-256 values are
validated; arbitrary paths/URLs are not used as relative file names. New
folders/files use private modes 0700/0600. SQLite metadata and raw evidence
remain private; the code does not publish them or create a plaintext export.
Physical deletion, manual ledger edits, VACUUM/repair, or relocation are not
provided operations.

The root is pinned by an immutable OWNER marker and the same storage ID in
SQLite. `bind_context` stores one exact context hash, or verifies the existing
one. A changed hash HOLDs and writes durable STOP; there is no reset API. The
runner binds that hash to actual `storage_id` plus approved code/config and
artifact fingerprints. A root path string or self-hash alone does not prove
independent custody. Do not silently choose another root when this one HOLDs.

## Exclusive reservation and crash behavior

SQLite uses a per-call connection, `BEGIN IMMEDIATE`, uniqueness constraints,
foreign keys, and `synchronous=FULL`. No application code shares a SQLite
connection across threads/processes. The unique race row covers namespace and
race ID **across model changes and restarts**.

`reserve` returns:

- `RESERVED`: the sole claim, with opaque token/session/storage identity.
- `DUPLICATE`: a committed identical-input race already exists; readback is
  verified and its receipt returned. Different model version alone cannot
  authorize replay. Duplicate lookup remains possible after the deadline.
- `CONFLICT`: the race's frozen input or deadline differs. Preserve evidence
  and STOP; do not overwrite or reinterpret it as a new opportunity.
- `HOLD`: not initialized/stopped/late, or an existing pending/held claim.
  A pending claim never receives another usable token automatically.

Tokens are session-bound for a pending commit. A new instance cannot resume
another instance's pending reservation. On normal close, this instance's
pending reservations become HOLD_UNCERTAIN with durable STOP. A closed
instance cannot continue writing or silently initialize a new session.

For abrupt process exit, Linux PID/start-tick plus boot identity distinguish a
dead/reused process from another still-active initializer. Restart detects
abandoned RESERVED/STAGING/COMPLETION_PENDING rows and incomplete committed artifacts, preserves
them, HOLDs them, and writes STOP. Unsupported/unreadable process identity is
UNVERIFIED/STOP, not a guessed liveness result. Tests run on Linux; another OS,
network filesystem, power-loss semantics, or storage platform needs separate
review. An active owner's pending race is held against duplicate claim, never
replayed by another process. A commit-completion-pending row is not a usable
duplicate receipt until completion exists and verifies.

## Commit, deadline, and integrity

`metadata.generated_at` is required, aware, no later than the current clock,
and strictly before the reserved deadline. Raw input SHA must equal the
reservation. The caller separately validates the forecast's model/schema/race
and source semantics: storage hashes exact bytes and does not pretend to
reconstruct those semantics from arbitrary opaque bytes.

Commit transitions RESERVED → STAGING → COMPLETION_PENDING → COMMITTED under the ledger. It writes
raw input, raw forecast, and receipt as separate exclusively created files.
Writes use `O_EXCL`/`O_NOFOLLOW`, file fsync, directory fsync, and byte readback;
preexisting files/folders are never overwritten. Receipt binds input/forecast
lengths and SHA, model SHA, key, storage identity, namespace, generation/time
observations, deadline, and metadata SHA. Full commit metadata is retained in
the private ledger and verified against that SHA on readback.

After the first durable ledger staging write, a separate exclusive completion
marker binds its receipt SHA and completion observation. COMMITTED is exposed
only after that marker is fully fsynced/read back and a final ledger transition
is persisted; duplicate readers cannot consume a just-created empty marker.
A process crash at the
post-ledger fault cut has no completion marker and is HOLD on restart, not a
successful forecast. The immutable receipt's validity field explicitly
requires committed ledger **and** complete readback; a receipt file alone is
insufficient evidence.

Clock observations are checked before claim, during/after file persistence,
before/after the ledger commit, before/after completion persistence, and after
final readback. Required observation order is generation ≤ persisted ≤ ledger
staging ≤ completion observation ≤ finalization < deadline. A clock regression or late
observation invalidates the claim, preserves all files, and writes durable
STOP. No late forecast is retroactively called predeadline merely because
its input snapshot had an earlier timestamp. These are bounded software
observations, not a mathematical atomicity proof between wall clock and disk
hardware; actual clock/storage guarantees still require independent review.

An exact repeat of an already completed commit is a readback-verified
DUPLICATE, without any file rewrite. A changed repeat is CONFLICT/STOP with
the original forecast bytes retained. Other uncertain/rejected pending
commits become HOLD_UNCERTAIN. There is no automatic cleanup or retry, even
if the caller received no response. The runner must stop rather than generate
another forecast under a different model/version key.

`readback` returns COMMITTED only after verifying receipt, input, forecast,
metadata, completion marker, owner/key, and stored predeadline clock chain.
It returns private `input_raw`, `forecast_raw`, and `metadata` to the caller;
those fields must not be printed into public logs or committed to GitHub.
Responses themselves contain no filesystem paths. Tampering/missing files
HOLD and attempt durable STOP; artifacts are retained for investigation.

`list_forecasts` returns FORECASTS_LISTED with race/state/deadline rows for
this local namespace. It is suitable for ensuring a daily report does not
omit locally committed forecasts. It is **not** evidence that all official
scheduled races were captured; official-schedule completeness stays UNVERIFIED.

## Append-only result versions and explicit selection

`save_result` accepts exact UTF-8 JSON bytes with bound race ID, boolean
`final`, and aware `available_at`. Metadata fields, if supplied, must agree
with those raw attributes. A final result must be available at/after the
forecast deadline and no later than the current clock. The runner separately
validates complete result/payout/refund source semantics.

Results are new SHA-addressed files and immutable ledger versions. Their
revision is an integer AUTOINCREMENT insertion sequence, not lexicographic
SHA or a possibly tied/backward wall-clock timestamp. Exact raw+metadata
duplicates return RESULT_DUPLICATE; changed duplicate metadata HOLDs instead
of mutating an earlier receipt. New bytes return RESULT_SAVED. Forecast,
input, and original receipt never change after result ingestion.

`list_results` lists revisions, final flags, availability, and selected-version
metadata. `read_result` verifies raw SHA and returns RESULT_READ with private
`raw_result`/metadata. It never chooses the truth between conflicting finals.

`select_result` requires `{"explicit": true, "selection_id": "bounded-ID"}`
and a verified final result SHA. It appends a selection history row and pins
the highest observed result revision. The operator assertion is UNVERIFIED
external authority. `read_selected_result` requires such a selection; any
later ingested final beyond its pinned frontier causes HOLD. No automatic
latest-result choice occurs. A reviewer can explicitly choose an older SHA
after inspecting all known revisions by making a new selection event/ID.
Identical selection metadata is idempotent and does not silently extend an
old event's authority to newly arrived results.

This frontier rule handles different final versions ingested at the same
clock time even when the newer SHA sorts earlier. Nonfinal versions are not
settlement selections. Missing or conflicting outcomes/refunds are not zero
returns. Settlement calculation remains the separate runner module with
independent 500/600-yen ledgers and BET/SKIP treatment.

## Immutable daily and operations audit reports

`save_audit_report` permits only DAILY_SETTLEMENT or OPERATIONS_AUDIT. A report
identity is a bounded identifier (e.g. a date or digest), hashed for its folder.
Each report version has exact raw bytes and a separate immutable receipt.
Same raw+metadata yields AUDIT_DUPLICATE; different raw creates an additional
version, never overwrites. Same raw with changed metadata HOLDs/STOPs.

DAILY_SETTLEMENT requires metadata
`{"selected_results": {"race_id": "full-result-SHA256"}}`. Every mapping entry
must match the explicitly selected verified final result, with no newer final
beyond its selection frontier. These checks repeat inside the exclusive audit
transaction to prevent a correction arriving between validation and save.
The receipt includes that exact mapping and metadata SHA. The runner must also
require the mapping to cover all committed forecasts in the intended local
day; this does not certify official schedule completeness.

Readback verifies report/receipt/metadata/identity/storage hashes and returns
AUDIT_READ. Full raw report and metadata stay private. Operations reports are
separate artifacts, not mutations of an original forecast. STOP blocks these
writes as well; the first STOP flag itself remains durable evidence. There is
no post-STOP write exception that could reopen prediction or result handling.

## STOP, partial preservation, and fault tests

`stop` exclusively creates the first immutable STOP.json, fsyncs it, and never
clears/overwrites it. `is_stopped` fails closed on uninitialized/unsafe roots.
All further write APIs HOLD after STOP; readback for investigation remains
possible. On uncertain I/O, fixed reason codes are returned; arbitrary
exception text, URLs, paths, secrets, or submitted raw values are not echoed.

Restart checks result/audit files against their ledger rows. Orphaned partial
result/report files, missing expected files, or unsupported ledger formats
STOP rather than becoming successful duplicate evidence. Partial artifacts
are never deleted, renamed over, completed automatically, or reused for
replay. Manual recovery, storage relocation, evidence copying, or a new root
requires separately reviewed instructions; this module supplies none.

Fault stage names are `commit_after_claim`, `commit_after_input`,
`commit_after_forecast`, `commit_after_receipt`, `commit_before_ledger`,
`commit_after_ledger`, `result_after_file`, `result_after_ledger`,
`select_after_ledger`, `audit_after_file`, and `audit_after_ledger`.
The tests use only owned temporary stores, fake clocks, synthetic bytes,
concurrent threads/processes, and forced process exits. They cover exclusive
race claims, repeated initialization, cross-model no-replay, restart HOLD,
deadline/clock failures, immutable forecasts after corrections, same-clock
revision order, explicit result frontier, separate persistent reports, and
durable STOP. They do not certify actual disk hardware, clock authenticity,
production launch, site parsing, or permission to execute a real shadow run.
