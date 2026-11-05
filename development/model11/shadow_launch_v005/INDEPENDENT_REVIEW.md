# Independent Shadow launch-candidate review

Scope: offline implementation and fault handling only. All fixtures are invented
2099 races labelled SYNTHETIC_ONLY. No actual official captures, credentials,
production stores, notification services, or real-money bets are used.

The candidate remains disabled by default. A structurally complete approval
bundle or local hash is not independent authentication, and this software review
does not grant permission to execute a private or production shadow process.
Current Model1.0, formal A/B, BOX Ver.1, LOCK rules, tasks, and original artifacts
remain outside the implementation's write scope.

## Executed observation status

The runner integration suite executed 15 test methods successfully on Python
3.12.14 / Linux 6.18.57 x86_64 / glibc 2.41. The final scoped run reported
`Ran 15 tests in 34.938s / OK`. These are software PASS observations only;
actual sources, independently authenticated approval, and production remain
UNVERIFIED. Other Python versions require separately recorded execution.

| Local fault or workflow | Observed result |
|---|---|
| Default DISABLED constructor/run | PASS: exploding adapter/model/store/clock spies receive zero calls; ingest/settlement/stop/shutdown also perform no dependency action |
| Invented 12-race sequence | PASS: separate race receipts, exact captured input bytes, matching input/output SHA, four full 120-outcome stages and separate research portfolios |
| Concurrent duplicate race | PASS: two threads produce exactly one committed forecast; same-process new-store-instance restart returns duplicate without changing bytes |
| Missing input near deadline | PASS: HOLD; no guessed exhibition score or successful forecast receipt |
| Injected source exception | PASS: fixed HOLD; injected private exception sentinel is absent from report |
| Ambiguous persistence failure | PASS: injected failure after input write preserves partial evidence, sets durable STOP, and prevents restart replay |
| Deadline crossed during persistence | PASS: no valid committed forecast; durable STOP |
| Results received or revised later | PASS: separate append-only final versions, duplicate result idempotency, original forecast bytes unchanged |
| Future course/FL/scratch evidence | PASS: each future availability causes HOLD |
| Known FL state / reduced scratch domain | PASS: known FL=True is preserved without a new disqualification rule; valid five-boat source input is held by full-120 runner gate |
| Original probability and portfolio math | PASS: runner distributions, calibrated stage, five selection, BOX objects and BET/SKIP equal the immutable V003 reference on the same normalized input |
| Separate five/BOX economics | PASS: 12-race five stake 6,000 yen, each available BOX stake 7,200 yen; hit/return/net recomputed independently from stored tickets and separate invented results; BET action stakes checked separately |
| Absent manual Human input | PASS: no automatic Human label; manual method n=0 and hit/stake/rate remain null rather than fabricated zero performance |
| Daily settlement with missing result selections | PASS: incomplete/empty selection HOLD; every committed race requires an explicit final version |
| Normal shutdown, pending reservation and STOP | PASS after fix: pending reservation is held by store close; no abandoned reservation reuse or implicit resume after STOP |

Reproduce the scoped suite from the package directory:

```text
python -B -m unittest discover -s tests -p test_shadow_launch_runner.py -v
```

The helper `make_simulation_context(tmp_root)` builds earlier six-day training
artifacts and twelve target races on the seventh invented date. Its local
context hashes and temporary-store registration are explicit test assertions.
They are not launch approval and do not register a production schedule.

## Findings resolved before the final scoped run

The first targeted shutdown check failed: `shutdown()` closed only the runner's
in-memory flag and did not call the store's close operation for its pending
reservation. The owner changed the new runner to close the initialized store;
the same regression passed in the final fifteen-test run. No existing source
file was changed by this review agent.

Read-only review also identified a possible result-ordering ambiguity if final
revisions shared a clock timestamp and were sorted by hash. The storage owner
uses SQLite insertion revision plus the selection's observed-revision frontier,
and reports a separate same-clock regression. This suite verifies append-only
result handling; the store's more detailed same-clock and process fault tests
must be read in its own recorded results, not inferred from this runner suite.

## Boundaries requiring later independent review

Actual source mapping, transport, approved model/normalizer artifacts, source
authenticity, operating identity, approval identity/expiry, live storage identity,
real-data performance, F2/F5 criteria, and a permitted observation window are not
established by synthetic tests. A live schedule is not enabled or inferred.
The daily denominator is all committed forecasts in this owned store for the
date. Synthetic twelve-race coverage does not verify completeness against a
real official schedule. Thread concurrency and a new store instance do not
independently prove behavior under an actual machine power loss or live-worker
process termination; those claims require their own evidence.

The review will distinguish successful software tests from development readiness,
Claude review, Andy's explicit GO, application, natural-run verification, and
CLOSE. A failure or unresolved safety behavior is a STOP/HOLD, not a reason to
silently relax a gate or modify existing production behavior.

## Additional independent candidate/private-kernel review

A separate validation reviewer added and ran
`tests/test_shadow_launch_candidate.py`: **12 test methods PASS** on Python
3.12.14 / Linux, after the findings below were corrected. This reviewer changed
only that new test file and this appended review section; source fixes were made
by their owners. This is not a Claude independent audit or actual launch GO.

These additional tests use the same invented year2099 fixture numbers, sometimes
with deliberately PRIVATE_REAL/false and registered OFFICIAL metadata tags to
exercise the separate private branch. Those tags do not make the invented rows
real. Approval bundles, reviewer IDs, evidence hashes and operator attestations
in these tests are fake local test statements, not actual HQ14/Claude/Andy
approval. No official capture, private real race, network transport or production
store was used. Numerical parity tests exercise the private computation kernel;
they do not validate an actual approved private source/normalizer/model bundle.

Observed additional checks:

| Check | Executed result |
|---|---|
| Private missing bundle or operator acknowledgement | HOLD before model computation |
| Complete invented approval statements | Structurally attested only; independent approval UNVERIFIED, actual execution GO not established, production_go=false |
| Same normalized numbers and frozen model, private vs immutable V003 | Exact distributions, calibrated probabilities, five selection, all BOX objects and BET/SKIP at market weights 0, .25 and 1 |
| Private class inside the actual model call | PRIVATE_REAL and synthetic=false preserved; no synthetic relabeling; old V003 real-input HOLD unchanged |
| Missing or unapproved normalization provenance | HOLD for absent metadata or different normalizer/spec/training hashes, fit cutoff or training-availability metadata |
| Actual configuration/artifact disagreement | HOLD; no implicit recomputation of an approval binding |
| Private clock before snapshot or at/after deadline | HOLD |
| Generation crosses deadline after computing | Runner HOLD; no valid committed forecast |
| Default runner DISABLED | No supplied dependency inspection, clock read, file open, socket or SQLite connection in the tested path |
| Result fields in predictor input | Rejected |
| Later result ingestion | Separate result save; original forecast bytes, fitted model and normalizer unchanged |
| Malformed approval offset +08:60 | HOLD rather than normalization into a valid +09:00 instant |

Two concrete findings were reproduced and resolved before the final twelve-test
run. First, the private computation entry point accepted absent normalization
metadata or a different hash-shaped normalizer reference while the approved
normalizer artifact remained unchanged. The source owner added an explicit
non-null binding check against the approved normalizer's own hash, feature-spec
hash, training-input hash, fit cutoff and maximum training availability. The
runner already computed normalization from its matched frozen artifact; the fix
also guards direct candidate calls.

Second, approval validity and operator timestamps containing malformed +08:60
offsets were normalized by `datetime.fromisoformat` into +09:00 and accepted.
The policy owner added explicit offset-hour/minute range checks, with its own
approval-field regressions; the additional independent regression now passes.
The root owner also aligned its new candidate/runner timestamp helpers with the
existing strict validator. No old source was modified by this reviewer.

Reproduce the additional scoped suite:

```text
python -B -m unittest discover -s tests -p test_shadow_launch_candidate.py -v
```

No remaining concrete defect was found in this scoped candidate/runner review.
It does not prove arbitrary live behavior, external approval truth, official
mapping correctness, real-data performance or production applicability. Those
OPEN/UNVERIFIED and authorization boundaries remain exactly as stated above.
