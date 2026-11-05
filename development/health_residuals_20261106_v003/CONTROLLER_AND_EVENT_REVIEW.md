# Controller safety and actual event comparison: independent scoped review

Status: executed synthetic regression PASS; operational acceptance and actual
official-page vocabulary remain UNVERIFIED / POLICY_PENDING. Production GO is
false. This review covers only the four test files named below and the inspected
controller/source boundaries; it is not an independent review of the whole app.

## Executed scope and environment

The final scoped run executed:

```text
nice -n 10 /workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -q -p no:cacheprovider tests/test_health_controller_scope.py tests/test_health_v002_controller.py tests/test_health_v003_controller.py tests/test_health_v003_event_equivalence.py
................................                   [100%]
32 passed, 22 subtests passed in 1.42s
```

Measured runtime: Python 3.14.3; OpenSSL 3.5.5 27 Jan 2026;
Linux-6.18.57-x86_64-with-glibc2.41. These are development observations, not the
production runtime. No packages were installed. Tests do not create controller
or live HTTP-client constructors, query services, read real DBs, or obtain
credentials. Imports that evaluate os.getenv use a mock returning only the
declared default. Controller tests use __new__ and in-memory fakes. The event
tests create fresh synthetic SQLite files under pytest tmp_path, use an actual
SQLiteStateRepository and DryRunAirtableAdapter, and refuse an existing DB path.
All dates/races and HTML are invented for 2099-01-07; they are not official data.

## Controller regression observations

- Scope validation excludes previous-day cache/state and mismatched ID/deadline
  dates; an invalid snapshot is rejected as a whole. Persisted terminal state is
  not reopened. Recovery does not write or rewrite persisted states.
- Official failure followed by valid tracking supplies tracking_info only;
  tracking is not promoted to official_info or official timing confirmation.
- The v002 schedule-authentication provider, NoRaceVerified production API and
  process HOLD latch are removed. Test-local exceptions with that old spelling
  are adversarial inputs only: they classify UNKNOWN_FAILURE, take ordinary
  fallback, retain only valid current scope and permit later fetches. No automatic
  no-race certification or race cancellation is inferred.
- The exact official no-row reason plus exact tracking stadium-7-missing reason
  can yield NON_RACE_CANDIDATE_UNAUTHENTICATED. Same-day successful source/cache
  evidence, or same-day persisted terminal evidence, instead yields
  SOURCE_FAILURE_DAY_EVIDENCE_CONFLICT. Unknown persisted reads yield READ_FAILED,
  not an empty-calendar conclusion. Calendar status stays UNVERIFIED. The tests
  distinguish unrelated parse/HTTP failures from the two exact absence reasons.
- A next poll, next JST day and new instance still fetch; no automatic latch is
  retained. Ten empty polls call both fetchers ten times and watchdog at polls
  5 and 10. A watchdog read exception is logged with a fixed safe diagnostic and
  does not suppress subsequent polling.
- Explicit STOP during an awaited fetch prevents new race dispatch and later
  direct refresh. This is not a promise to cancel a process already dispatched.
  A midnight transition skips previous-day dispatch without state mutation.

The fake-controller tests assert no repository save/event-write calls and use a
process spy. They do not pretend to execute a formal A/B LOCK writer.

## E2/E5: actual old/new StateMachine execution

The executable comparison loads byte-verified public reference copies of main,
StateMachine and parser from main 8172aec010894a52f36f48b7091476d26494e4ee.
The current StateMachine is byte-identical to that reference. Both controllers
drive fresh SQLite repositories through 12 races at 12:40, 12:45, 12:53, 12:54,
12:55 and 13:01 JST, with a 13:00 deadline and complete invented live inputs.
The actual emitted event types are CLOSING_OBSERVATION and RACE_TERMINAL.

The comparison excludes exactly one field: SQLite physical insertion timestamp
created_at, which uses SQL CURRENT_TIMESTAMP and can differ across separate DB
runs crossing a wall-clock second. Ordered UUIDs (fixed synthetic sequence),
keys, race IDs, event type, observed_at, deadline_version, raw payload_json,
payload_hash and all per-poll/final state fields are compared exactly. It does
not claim identical raw DB-file bytes or all physical database-row bytes.

The final five dynamic HTML scenarios execute both old and current parsers:

| Case | Invented state evidence | Observed comparison |
| --- | --- | --- |
| a | One semantic deadline cell: time plus exact 発売終了 | MATCH; 12 terminal events in each version |
| b | Explicit 発売状況 cell with 発売終了 | MATCH; 12 terminal events in each version |
| c | Time only; no state information | MATCH UNKNOWN; 12 closing observations and zero terminal events in each version |
| d | R7 race name contains 中止; legitimate deadline-cell state remains separate | Intentional difference: old false CANCELLED, current OFFICIALLY_CLOSED when that deadline-cell state closes |
| e | Actual R7 explicit state cell is 中止 | MATCH; R7 CANCELLED in each version |

For a/b/e (and the unchanged UNKNOWN case c), the complete compared semantic
fields match, not just event counts. Normal b has ordered event counts
0/0/12/12/12/24 over the six polls; closing observations occur at 12:53 and
terminal events at 13:01. Case d is an intentional removal of row-wide name-text
cancellation inference; it is not reported as event equivalence.

The dynamic case-d fixture differs from the separate static E5 input corpus:
it includes legitimate changing deadline-cell state so that actual event timing
can be observed. It must not be substituted for the static corpus's raw bytes.

True sales_status UNKNOWN with both flags false is separately tested, including
before and after the deadline. Both unchanged StateMachines retain C_EVENT_DONE
after the closing observation and emit no automatic RACE_TERMINAL. Passing the
deadline alone is not invented as official CLOSED. This is existing behavior,
not proof that absent official status is an operational success condition.

Supplemental UNKNOWN index-fetch failures are a different scenario from UNKNOWN
sales status. Both versions preserve stored deadline and event semantics for a
failure before or inside the closing window. If the closing-window poll fails,
both wait until the next successful poll (12:54 here); neither backdates it.

An earlier, explicit-status-cell-only candidate produced an observed old CLOSED
versus new UNKNOWN compatibility gap for case a. That was a valid observation of
that intermediate candidate. The later Claude 01:55 policy explicitly permits
limited exact state evidence in a unique semantic deadline cell as well; the
current final candidate was rerun and case a now matches. The old HOLD observation
is not silently reused as the current result, and the new fixture PASS is not
official-page authentication. The mapping vocabulary remains POLICY_PENDING.

Root evidence-export APIs retained in test_health_v003_event_equivalence.py:
execute_scenario(..., parse_index=None, status_layout="explicit",
sales_status_override=None), measure_status_evidence_gap(directory), and
measure_status_case_comparisons(directory). New DB paths are mandatory. The
gap helper's current MATCH is explicitly scoped to synthetic case a and sets
production_go=false. All old references are SHA-verified before execution.

## Protected bytes independently rechecked

The following seven files were reread and compared against the preserved 8172aec
baseline; all byte comparisons were true:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| state_machine.py | 15012 | 596fb1a4c1e81d694204bca6968372a2eee86933939046e85a81ea68864a6471 |
| models.py | 4922 | 2a1dfefe8b5bc1ebac40b7b1ddff042f0967532c36c032b74e9a74f508f0271b |
| repositories.py | 6385 | 05ffbbdaad5cc8a2e4806d90cb0913d250089e2347207e96a9e9c9c2630b7aad |
| airtable.py | 1747 | f4f3d3efc898697db75a99455341b97290daf8b1164bd17a8f3040643e9433d5 |
| closing.py | 2603 | c46b6ada4be9b981f9a110a4d2eec7c34381e9b5583725e465722f88ace9bace |
| requirements.txt | 90 | 125749db489c1885b54524b46ce4ed032896e2cf12d72021a69590e72220febd |
| tests/test_state_machine.py | 7570 | dfcc33edd342219c6427af3c054bee3f8aba0d42c950826ab6103e29bb9e08b0 |

## OPEN / STOP boundaries

1. Formal A/B LOCK and its writer are not implemented in this repository. Their
   event equivalence, counts and saved content remain UNVERIFIED; no LOCK event
   was fabricated from a closing observation.
2. Original official HTML, confirmed production vocabulary and the actual 11/5
   incident's source bytes are not inputs to these tests. Actual root cause and
   real-page status mapping remain UNVERIFIED / POLICY_PENDING.
3. These tests do not authenticate an official calendar or prove a non-racing
   day. Candidate absence diagnostics must not clear current state or certify
   cancellation. New evidence of unexpected mutation or timing divergence is STOP.
4. Actual controller transport, existing DBs, service restart behavior and natural
   production polling were not exercised. Production compatibility remains a
   separate review and GO, not inferred from scoped synthetic PASS.
5. This branch retains the original 90-byte requirements file. It is not a deploy
   candidate: any future approved code port must use the approved certifi base
   and undergo its own checks. No merge, deploy, Shell or service operation was
   performed or authorized by this review.
