# Stage12: one bounded evidence-capture phase, not scheduled production collection

Base: 9cea4a0afc20d6a6237462bda96f49185ad42eae, draft PR #2.
Scope: new isolated capture/storage candidate, tests and opt-in CLI. No existing
source/test edits; no main/Render/Events/AuditRuns/task/model change. The SQLite
backend is a local review backend, NOT the decided production evidence store.

## Timing first: no automatic frequency chosen

One phase plans exactly 24 requests: racelist and beforeinfo for each of 12
races on an explicit date. A phase label is not an execution schedule, race-day
confirmation, closing-window membership or freshness check. Reusing this primitive
for earlier/near-deadline/post-race phases requires a separately reviewed planner.
There is no background loop, trigger, retry, wait-until or new scheduled task.

Before operational rollout, choose capture phases/timing and request budget,
prefer reuse of existing response bytes, then choose production store, retention
and deletion policy. In particular, moving archive I/O to a prediction-critical
path has NOT been approved or measured here. Do not treat raw MiB illustrations
or old 198-246s figures as measured performance of this new collector.

## Implemented preservation path

1. Create a NEW exclusive 0600 review DB; never open an existing path for writes.
2. Persist and reread all 24 planned targets before network activity.
3. Save and independently reread START for one target before its request.
4. Make at most one fixed-host GET attempt, sequentially; no redirects or cookies
   reused, no inherited proxy environment, no caller URL/host/auth parameters.
5. Preserve HTTP entity bytes, including non-200 or stream-interrupted prefixes.
   Content-encoding is retained, not silently decoded. A body-size cap marks
   truncated prefixes incomplete; its hash describes the saved prefix only.
6. Store body plus END receipt in one SQLite transaction. Identical bodies may
   deduplicate, but each target/attempt retains its own times and receipt.
7. Read back via a new read-only connection and recompute receipt/body hashes.

A failed racelist never prevents the paired beforeinfo attempt, or vice versa.
Failed START persistence prevents that network request, not all later targets.
Failed END persistence leaves START and exposes the missing end. Interrupting
execution leaves planned/unstarted or START-without-END rows; no automatic
retry relabels them as success. Restart/resume/retry is deliberately not built.

All connections close explicitly. SQLite transactions/fsync are local storage
mechanisms, not a tested power-loss, cloud durability or trusted-producer boundary.
A file owner can rewrite the DB and hashes; hashing is not a signature. The
archive has no purge operation, retention service, public hosting or backup.
No production account, bucket, Render disk or payment was provisioned.

## Exact claims and units

Counts separately report planned targets, attempted calls this invocation,
received headers, HTTP200s, complete bodies, body/END persistence and independent
readback. Persisting a failure receipt is not receiving a successful response.
START means the start receipt was written, not independent proof of a request.
Actual request-start/header/body-finish times remain separate; two pages are not
called simultaneous. Clock problems remain recorded, with no fabricated finish.

Only content-type/length/encoding, Date, Last-Modified, ETag and Cache-Control
response headers are retained; no Cookie, Set-Cookie or authentication headers.
HTTP Date/Last-Modified/acquired times do not become source_effective_at.
The per-request byte cap (maximum candidate limit 2,000,000) bounds saved body
bytes to 48,000,000 per phase before dedup. SQLite/receipt overhead is additional.
HTTPX timeouts are per operation, NOT a global hard deadline. Limits must be
explicit inputs; test values are not live timing/freshness policy decisions.

## Shared snapshot review

`review_saved_beforeinfo` reads one verified END/body, then supplies that same
body to observation and withdrawal scanning. Its wrapper binds both outputs to
the exact receipt key and body hash. It refuses partial/non200/nonHTML/encoded
bodies for this review parser, without discarding the archived evidence. Parser
exceptions are reportable independently and never delete stored bytes. Body
identity/freshness/official withdrawal/readiness are NOT established by this step.
No real evaluator or production runtime is connected to the new path.

## Tests and evidence

The 509 baseline tests remain unedited. 64 new tests exercise full 24-target
planning, pairing failures, HTTP503, no redirect-following, header/cookie policy,
body cap boundaries, broken streams, compressed entities, failed starts/ends,
transaction rollback, interrupted attempts, no implicit retry, corrupted data,
clock failures and both parsers reading the same saved body.
Local result: 573 pass / zero failures/skips. CI is separately verified by exact
code/run/artifact. HTTP transports in these tests are injected/offline, explicitly
marked in every receipt; this is NOT 24 real official pages captured live.

Additional local replay uses only three existing captured target pages:
3R racelist, 12R racelist and 12R beforeinfo. Missing fixture URLs are injected
HTTP404s, never substituted with another race's body. All replay transports are
labelled injected; original source manifests stay separate. Zero new genuine
withdrawal examples are claimed. No absence-of-withdrawal inference is allowed.

## Outstanding choices / deployment gate

Phase timings/frequency, production store/retention, hard global request budget,
queue/backpressure and isolated collector scheduling require explicit review.
Routine collection is NOT enabled. A one-off CLI requires explicit --allow-network;
the Stage12 tests did not execute that live option. Existing CI's five-page
recapture is a different, pre-existing review tool, not the new all-race collector.

Actual withdrawal fixture coverage, naming/corroboration acceptance, participant
state-at-decision, section freshness, old-API bypass prevention, PR#1 integration,
durable prediction save deadline and Final Layer F remain separate work.
