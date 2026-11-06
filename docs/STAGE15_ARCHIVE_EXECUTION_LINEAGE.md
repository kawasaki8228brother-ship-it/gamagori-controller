# Stage15: full decision lineage and one local claim per day

Base: e40564b1d88ada7ba952996450687b9a5a88480e, draft PR #2.
Scope: one isolated candidate, tests and this note. Existing modules/tests are
unchanged. No network acquisition, runtime/scheduler/Render connection,
production store/retention, historical score changes, merge or deploy.

## Do not conflate basis with output

The Stage14 decision is based on TWELVE result snapshots. A subsequent archive
produces TWENTY-FOUR racelist/beforeinfo outputs. These are different graph roles;
the later pages are not retroactively called evidence for the earlier decision.

The ledger first commits the exact supplied result bytes and full snapshot
metadata into a content-addressed input batch. It then runs the unchanged
assess_postrace_day and stores its COMPLETE result_publications array, flags,
original binding_sha256 and a reference to every original result snapshot.
No caller PASS flag or flattened summary is accepted instead of source inputs.
A failed/unsupported assessment is stored without authorizing a claim. Even an
unexpected parser exception leaves already committed input bytes available.

A separate read-only connection verifies all object/body hashes and recomputes
the assessment from the same snapshots at the original decision time. The
primary assessor source hash is recorded; a changed primary assessor requires
an explicit version/migration decision, not silent re-interpretation. That hash
is not a lockfile for the entire transitive Python environment.

## Local execution state

A work key binds target day, venue, POSTRACE_ARCHIVE and assessment policy ID,
NOT the varying decision hash or invocation time. BEGIN IMMEDIATE plus the jobs
primary key admits one claim owner across concurrent users of the SAME SQLite
review store. A new decision for the same day does not start a second job or
replace the original basis. Secondary assessments are retained separately.

Events are immutable content-addressed objects: RUNNING -> COMPLETE/PARTIAL/
FAILED. A small materialized jobs head points at its current event; readers
check the linked initial claim, timestamps and decision association. Only the
returned owner token can finalize through this API. The token check is not an
application security sandbox; an actor with write access can replace the DB.

RUNNING does not expire automatically. A restart reads its existing status and
does not steal the claim. The owning caller can explicitly mark failure. No
implicit retry, forced takeover, lease TTL or network exactly-once guarantee
is implemented. Interrupted owners require a reviewed recovery operation in a
later stage. An external worker bypassing this API or using another DB is not
prevented from issuing requests.

## Importing acquisition results

finish_from_archive reads a Stage12 review DB using a read-only connection and
stable read transaction. It validates its 24 plans, meta/context, raw START/END
canonical hashes, body hashes/lengths and claim/capture time ordering. It retains
full original receipts, including HTTP errors, timing and injected-transport
markers. Each output target links to its START/END objects and raw body.

Body/receipt import, capture manifest and terminal event commit together. An
invalid archive rolls back this import and leaves the claim RUNNING. A valid
partial archive retains successes, failed responses and unstarted targets, and
ends PARTIAL (or FAILED if no END exists). COMPLETE means 24 complete HTTP200
captures with matching request/final URLs and recorded clock status, NOT parser
success, freshness, official truth, eligibility or power-loss durability.
The source DB is never edited. Stored outputs are checked again on later reads.

All writes are confined to a newly created or explicitly recognized local review
store. Creation refuses existing paths and symlinks; opening requires the review
schema marker. No cloud storage, fee, retention deletion or production database
is provisioned. Content-addressing is integrity checking, not a signature or
protection against rewriting the entire graph. Readback is committed visibility
and consistency, not a crash/power-cut experiment or storage hardware warranty.

## Verification at this checkpoint

The 668 baseline test IDs remain unchanged. Forty-one new tests passed locally:
709 /0fail /0error /0skip. They cover concurrent connections, reopening and
no-expiry behavior, repeated decisions, ownership, failures/partial completion,
corrupt inputs, atomic rollback, raw-before-parse, old/future capture rejection,
complete 12-basis/24-output linking and repeated finalization rejection.

One initial pytest invocation was launched from /mnt/data instead of work/ and
failed collection with import errors. The correctly scoped baseline then passed
668/668. This invocation error is retained in the supplied verification logs;
no test was edited or skipped to address it. CI must be separately verified.

Stored-source replay uses the original Stage14 result12 and Stage13 capture24
bodies. The 24 acquisition responses are explicitly MockTransport/injected, with
new replay times; original source captures/manifests remain separate. There are
ZERO new official requests or new withdrawal-positive examples in this stage.

Independent direct SQL (not ledger/collector readers) rechecks65 canonical
objects,36 raw bodies,12 result proofs,24 output targets/48 capture receipts and
the two-event claim chain. All12 result/payout values match the supplied report.
This demonstrates preserved provenance and local duplicate suppression, not a
live scheduled collector. Cloud retention, retries/recovery, nonstandard results,
PR #1 durability, A/B isolation and final prediction F remain separate gates.
