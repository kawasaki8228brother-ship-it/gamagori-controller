# Independent Health/index/OBS offline review

Scope: current-day controller admission, conservative race-index parsing,
typed fetch observations/calendar-evidence boundary, and the new read-only OBS
QA prototype. Tests use invented 2099 data, locally mocked HTTP operations,
fake repositories, and a spy state machine. No actual 2026-11-05 HTML, tracking
response, production database, OBS original, source service, or collector was
accessed. No Render Shell, watch process, deployment, database cleanup, task
change, or production operation was performed.

The controller tests construct the object with `__new__`, never `__init__`.
Their `start()` calls execute exactly one injected local cycle, with fake
fetchers, a fake read-only repository, a fake audit hook, an in-memory stop
event, and a fixed clock. They do not instantiate the live controller or invoke
the real state-machine transition logic.

## Executed results

The read-only existing Python environment reported Python **3.14.3**, Linux
6.18.57 x86_64/glibc 2.41, OpenSSL 3.5.5. No installation or environment change
was made. Bytecode and pytest cache writes were disabled for these commands.
The OpenSSL observation is environment metadata; no live TLS test was performed.

Controller-only command, from the isolated repository root:

```text
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -q -p no:cacheprovider tests/test_health_controller_scope.py
```

Observed: **12 passed, 14 subtests passed in 0.26s**.

The reviewer then executed the four new Health test files together:

```text
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -q -p no:cacheprovider tests/test_health_controller_scope.py tests/test_health_raceindex_parser.py tests/test_health_official_index.py tests/test_health_obs_qa.py
```

Observed: **105 passed, 14 subtests passed in 1.34s**. These are local software
observations, not source authenticity, actual OBS eligibility, real-root-cause
confirmation, a production compatibility verdict, or execution GO.

## Controller boundary observations

- Cached races are admitted only when their canonical current-JST-day race ID
  and aware deadline agree. Prior-day entries and ID/deadline conflicts are
  excluded without modifying the supplied objects.
- A fetched snapshot is accepted as a whole or rejected as a whole. Wrong
  snapshot/acquisition dates, duplicate race IDs, and one invalid deadline do
  not leave a partially official universe behind.
- Persisted recovery projects only current-day nonterminal records with an
  admissible deadline. Prior-day, terminal, mismatched-date, and naive-deadline
  records do not enter the processing universe. No state repair or deletion is
  performed by these helpers.
- Both index-fetch failures with only old persisted/cache records produce no
  processing calls in the injected poll. Original historical state objects and
  fake write methods remain untouched.
- Tracking fallback is passed as `tracking_info`, while `official_info=None`
  and `official_fetch_failed=True`. It is never promoted to official timing,
  closure, cancellation, or LOCK evidence.
- A typed verified-calendar no-race outcome clears the universe and skips state
  recovery/processing. The direct official path also skips tracking fallback.
  No empty HTML or missing tracking stadium is treated as this outcome.
- A fetch cycle crossing to the next JST date clears dispatch even after a
  valid snapshot, so the previous-day universe is not processed under the new
  civil date.

### Concrete finding and regression closure

Independent fault injection initially found that `NoRaceVerified` raised during
the tracking attempt entered the generic failure branch. With a retained
current-day cache, that one-cycle experiment dispatched one `process_race`
call and retained one race. This matters because the optional schedule provider
is consulted again for tracking and can supply newly accepted evidence after
the official attempt fails.

The owner added a typed no-race catch before tracking's generic failure path.
The existing no-race regression now exercises both origins: current universe
cleared, NO_RACE observation logged, no persisted recovery, no state-machine
call, and no state write. Both variants pass in the final run. This does not
infer no-race status from a tracking payload; it handles only the separately
typed calendar-contract outcome.

## Parsing and source-status observations

The reviewed parser rejects unsupported or partial layouts, duplicate race
rows, ambiguous/missing closing-time cells, race labels outside the semantic
table, and missing expected race numbers. The official fetcher uses a
conservative expected set unless separately bound calendar evidence is
provided. HTTP success with empty/unparseable content is a parse failure, not
verified absence. Typed HTTP/HTML/tracking diagnostics do not preserve raw URL,
proxy, or arbitrary exception text in their new index error records.

The calendar provider is optional and not configured by the default application.
Its accepted metadata/hash/receipt binding is not independent authentication of
official truth. Source tests use invented calendar bytes and an invented
review receipt. Actual source integration and review remain OPEN/UNVERIFIED.

## OBS QA interpretation

The new OBS helper reads supplied normalized local rows; it performs no source
query, Airtable write, repair, or eligibility decision. The synthetic 20-row
fixture is explicitly not a reconstruction of 2026-11-05 OBS originals.

Executed examples retain separate missing/null/empty/malformed source-evidence
states and column/payload UUID differences. Missing payload UUID or empty
RUN_START evidence remains CONTRACT_UNVERIFIED rather than an invented formal
violation. Provided mismatches are reported without echoing UUIDs, run IDs,
URLs, or arbitrary errors. The confirmed A start/end idempotency formula is
checked only in its admitted A operational scope; B and LOCK are excluded.

Raw-byte SHA, pre/post declarations, and a local canonical JSON profile are
distinct observations. Local profile agreement is not proof that the actual A
writer uses that profile. The related A reference labelled SHA256 but containing
40 hexadecimal characters is preserved verbatim with algorithm UNVERIFIED; it
is not silently rewritten or relabelled. The independently matched OBS contract,
payload-UUID requirement, and actual source completeness remain UNVERIFIED.

## Preservation and remaining limits

The local `state_machine.py` is 15,012 bytes, SHA-256
`596fb1a4c1e81d694204bca6968372a2eee86933939046e85a81ea68864a6471`, Git blob
`60b06789285a812d3c6314d3e398e0f10126be2a`. The parent reviewer confirmed that
blob against base `8172aec010894a52f36f48b7091476d26494e4ee`. The independent
controller tests check call boundaries with a spy; they do not claim to have
retested every unchanged state-machine transition or executed an existing task.

The demonstrated stale-history recovery path is a concrete software hazard
under injected failures. **It is not a verified explanation of the actual
2026-11-05 incident.** Its HTML, transport responses, environment and original
OBS evidence were not supplied. Actual parser/source compatibility and the
incident root cause remain UNVERIFIED.

This isolated candidate starts from the older 8172 dependency base and must not
be used as a deployment branch. Integration onto the separately approved
certifi state, independent review, and Andy's operation-specific GO remain
separate work. No historical DB rewrite, retry/replay, weakened evidence rule,
LOCK change, A/B/Model/BOX/Freeze change, or production authority follows from
this review. No unresolved blocking finding remained in the examined offline
scope after the tracking-no-race fix.
