# S2 controller regression and independent review — v002

Scope: controller admission, STOP/HOLD dispatch boundaries, and the removal of
the earlier dictionary/hash-based no-race trust path. This reviewer edited only
the authorized controller test file, the new v002 controller test file, and this
review. No controller/state-machine source was edited by this reviewer.

All inputs are invented 2099 examples. Tests construct controllers and the one
fetcher example with `__new__`; they do not call constructors that read runtime
configuration or create live HTTP/database dependencies. Main-module environment
lookups during these test imports return declared defaults through a mock; no
environment value is inspected or changed. Repository/writer methods are fakes,
HTTP text is injected, and no real DB, host command, site, Shell, task, or watch
process is used.

## Executed results

Using the existing read-only Python 3.14.3 environment, from this isolated
repository root:

```text
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -q -p no:cacheprovider tests/test_health_controller_scope.py tests/test_health_v002_controller.py
```

Observed: **20 passed, 18 subtests passed in 0.41s**. This consists of the twelve
updated scope methods and eight new v002 safety methods. Environment metadata:
Linux 6.18.57 x86_64/glibc 2.41, OpenSSL 3.5.5. No package install, bytecode/cache
write, actual TLS/source test, or live compatibility claim is involved. The
parent task retains the complete raw test logs separately.

## Revised expectation: a no-race claim is not authentication

The v001 expectation that a `NoRaceVerified` exception clears the current race
universe is explicitly withdrawn in v002. Self-reported dictionaries, matching
raw hashes, receipt references and `reviewed=true` do not prove official absence.
The calendar authentication adapter is not implemented. The old class name is
legacy import compatibility and is classified as SCHEDULE_UNVERIFIED.

The controller therefore retains its admissible **current-day** cache, latches
`SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED`, and prevents fallback, persisted
recovery, and prediction dispatch. Prior-day entries are still filtered. No
terminal/cancelled state or successful no-race observation is inferred.

Executed cases confirm:

- A valid complete twelve-race official index remains normally dispatchable;
  all twelve admitted calls carry official information and no false HOLD.
- A forged afternoon calendar claim, including matching SHA/receipt-shaped
  metadata and contradictory invented raw content, cannot suppress twelve
  supplied race rows. The provider callback is not invoked; twelve remain the
  conservative expectation and the valid index replaces the cache.
- Legacy no-race exceptions from either official or tracking fetch preserve
  current races, remove prior-day entries, set the HOLD latch, and do not invoke
  recovery, processing or event writes.
- A hostile no-race exception whose string/repr raises is not stringified or
  accepted. A manually constructed legacy NO_RACE_VERIFIED kind is also
  quarantined, rather than treated as calendar authority.

## STOP/HOLD lifetime and ordering

STOP received during either awaited fetch prevents new dispatch after that
fetch returns. A later direct refresh or start on the same stopped instance
does not refetch or replay predictions. The tracking-only regression now stops
from the accepted processing spy; it no longer requests STOP in the fetch and
then incorrectly expects a new processing call.

A HOLD latch survives later refreshes and a start on the **same instance** even
when newly injected snapshots would otherwise be valid. There is no supported
automatic latch-clear/resume API. A held next-day refresh can discard entries
that have become prior-day while retaining HOLD and making no new fetch or
processing call. Ordinary full HTTP/parse outages retain the established
current-day fallback behavior; they do not authorize historical recovery or
silently become confirmed calendar absence.

During read review, the owner moved the STOP check before any refresh work and
kept current-day filtering before the HOLD early return. Regression cases now
verify no fetch after STOP and no stale prior-day cache after a held date
transition. The original date-rollover dispatch regression remains in place.

**Important limit:** STOP here suppresses new dispatch. It does not cancel a
state-machine call that was already running when STOP arrived. The tests do not
claim cancellation of accepted in-flight work.

**OPEN:** HOLD and STOP state are in process/instance memory only. Persistence
across process restart is not implemented. Constructing a new instance does not
load a durable HOLD record. No SQLite table, DB flag, disk STOP file, scheduler
setting, or restart policy was added; durable restart handling requires a
separate reviewed design/approval. This candidate must not be described as a
durable process-wide or production STOP mechanism.

## State/LOCK boundary and preservation

In held/stopped cases, the processing spy receives zero calls. Fake state/event
writers receive zero calls, and the supplied state objects remain unchanged.
Universe filtering/projection does not repair, delete or terminalize historical
states. For a normal twelve-race case, the spy verifies the argument boundary;
it is not a test of real write behavior inside the unchanged state machine.

Read-only byte/size/SHA-256/Git-blob comparison against the parent metadata
matched all seven protected files checked:

- `state_machine.py`
- `models.py`
- `repositories.py`
- `airtable.py`
- `closing.py`
- `requirements.txt`
- `tests/test_state_machine.py`

The unchanged state machine is 15,012 bytes, SHA-256
`596fb1a4c1e81d694204bca6968372a2eee86933939046e85a81ea68864a6471`, Git blob
`60b06789285a812d3c6314d3e398e0f10126be2a`. Its existing tests were not edited by
this reviewer. LOCK validity, deadlines, state-transition rules, A/B prediction
logic, Model/BOX, Freeze and canonical artifacts are not changed by these tests.

The old dependency-base `requirements.txt` remains 90 bytes with SHA-256
`125749db489c1885b54524b46ce4ed032896e2cf12d72021a69590e72220febd`.
This isolated candidate is not a deployment target. Applying a reviewed patch
onto the approved certifi state and obtaining operation-specific GO remain
separate work.

## Remaining evidence limits

No real 11/5 HTML, official response, tracking response, production state,
OBS original, or actual calendar proof was supplied to these tests. The actual
incident root cause and actual source compatibility remain UNVERIFIED. No
official no-race status, independent source authentication, real-data PASS,
formal Claude review, rollout, rollback, or Production GO is established.

Within the tested offline controller scope, the revised cache-retention and
in-memory HOLD/STOP behavior passed. The restart-persistence limitation remains
OPEN rather than being hidden by the successful same-instance regressions.
