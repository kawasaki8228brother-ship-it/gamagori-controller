# Stage14: result-publication evidence before postrace archive planning

Base: c039eb9d003881b495cbc8e572d1826e1b544096, draft PR #2.
No runtime connection, prediction/scoring/old-record writes, schedule change,
production store, main merge or deployment. Existing 44 supplied source files
remain unchanged. Candidate completion is not a claim that the whole project
is complete.

## Concrete beginning condition

The normal-result path requires result snapshots for each of the twelve target
races, with matching date/venue/race identity inside the body and in both request
and response URLs. Merely passing midnight, passing scheduled deadlines, or
having a 12R result is insufficient. All six finish-table rows must be present
and unambiguous; ranks 1,2,3 and a single numeric trifecta payout must agree.
Only then is archive_input_eligible=true. This represents observed publication,
not an irrevocable settlement promise and not a BET/REVISION authorization.
No caller-supplied PASS flag or generic database FINISHED field bypasses parsing.

Raw visible finish labels (including full-width characters) remain separate
from normalized numeric-rank matching. Other nonempty rank labels are retained
without semantic classification; a numeric top-three/payout can be observed even
if another finisher has a nonnumeric token. This is NOT a withdrawal detector.
F/L, missing rows, missing results or refunds never automatically imply withdrawal.

Unknown/unpublished/cancelled layouts without supported result evidence stay
UNVERIFIED. Corrupt bytes, mismatched identity or conflicting top-three/payout
produce FAIL. A missing result must never be treated as NO_RACE or as completed.
This first path does not handle ties/multiple trifecta winners, cancellation,
non-establishment or an authoritative reduced race universe. They require
separate reviewed evidence adapters, not a permissive time-only fallback.

The candidate is pure. It does not start jobs. Acquisition evidence is preserved
BEFORE this decision, so failure must not erase the very pages needed for review.
A future recurring collector needs persistent claims/deduplication, concurrency
and retry budgets, an explicit completion-evidence acquisition path, a reviewed
nonstandard-result fallback, storage/retention and backpressure. None is enabled.

## Acquisition and evidence limits

A first-run/first-attempt-only workflow fetches the twelve fixed 2026-09-18
raceresult URLs after the target date has elapsed. One request each, no retries,
no redirects, 1MB retained-body cap, 12s per-I/O timeout; outer command 240s plus
10s termination grace and job 8min. No cron. It records per-request starts, bodies,
ends and metadata without reusing cookies. Review artifacts use 14-day retention;
this is not production retention selection. Raw responses are not source-signed.

The twelve actual responses were HTTP200 and complete. ZIP digest and all twelve
body digests were independently recomputed. End records matched the manifest.
The new parser was then replayed on all twelve bodies, cross-checked against
the already-reported daily result/payout values, and raw finish labels were
checked with a separate DOM walk (72 labels). These are after-the-event result
publications, not predeadline evidence. Real withdrawal-positive examples remain
zero. The acquisition workflow did not run a live recurring gated collector.

## Regression

590 baseline tests remain unedited; 78 new authored cases cover full-day versus
last-race-only evidence, missing results, repeated page substitution, wrong
body/URL identity, malformed tables, nonnumeric labels, payout contradictions,
clock conflicts and duplicate snapshots. Local: 668 pass /0fail /0skip. CI must
be verified for its own exact code commit and artifact before claiming parity.
Raw source, API metadata and semantic interpretation remain distinct layers.

## Timing recheck of Stage13 (not a new performance benchmark)

The old SQLite's 48 receipt hashes and 24 body hashes were rechecked. Per-race
sum of the two recorded request elapsed_seconds ranged 0.403800392 to
0.688011996 seconds; first START to second body-finish ranged 0.414293 to
0.695525 seconds. These exclude at least the final END commit/readback and
subsequent parser work. Total capture plus replay was 7.873821 seconds.
The arithmetic mean 7.873821/12 is not a bound for a future pair. Neither these
values nor old 198-246-second observed-to-ingested intervals establish a causal
bottleneck or negligible overhead in a different predeadline environment.
No timeout, polling interval, P95/P99 or freshness threshold is inferred.

## Remaining scope

Regular postrace launch/claim/retry and retention; cancellation/withdrawal source
semantics; predeadline identity/freshness and data adoption; A/B isolation;
PR #1/SQLite migration and durable prediction-save completion; actual marker-aware
C evaluation and Final Layer F; production Health/Daily and push delivery.
