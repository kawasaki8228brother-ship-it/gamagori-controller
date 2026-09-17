# 2026-09-17 蒲郡 実戦監査 — Final Audit

Audit date: 2026-09-17 JST  
Base commit: `057d024dd46797a77e8893ab30e4f4cbd58655bf`  
Runtime mode: `DRY_RUN=true` / C shadow only  
Primary objective: **無言の取りこぼしゼロ**

## Executive status

| Area | Final label | Evidence summary |
|---|---|---|
| A | `A_BASELINE_COMPLETE / FRESHNESS_HETEROGENEOUS` | 12/12 production LOCKs, all `VERIFIED_PRE_DEADLINE`; many later races were locked hours early |
| B | `B_BASELINE_PARTIAL / COVERAGE_UNVERIFIED` | Production B LOCKs exist for 9R and 11R only; current B spec has no deterministic target-selection algorithm, so expected coverage is not reproducible |
| C | `C_WATCHDOG_RC / DEGRADED_PATH_ONLY` | Official acquisition failed all day; source-error terminal path reached 12/12; normal official Closing path was not exercised |
| Daily | `NOT_EXECUTED / DISABLED` | Daily v3 ended with `enabled=false`, `last_run=null`; disable cause remains unverified |
| RESULT | `PERSISTED_AND_HASH_VERIFIED 12/12` | SYSTEM RESULT exists for all 12 races; canonical payload hash and deterministic RESULT idempotency derivation both verified 12/12 |
| RaceSummary | `DERIVED_LAYER_MISSING 0/12` | No 2026-09-17 RaceSummary rows; Events remain the source of truth |
| Official acquisition from Render | `FAIL` | `boatrace.jp` raceindex repeatedly timed out from Render Singapore; cause is not proven |

Whole experiment roll-up: **`AB_BASELINE_PARTIAL`**.

This audit does **not** declare full Ver1.0 PASS. A path is PASS only when it actually executed at least once and produced observable evidence.

## A — primary observer

- Production A LOCKs: **12/12**.
- Timing formula status: **12/12 `VERIFIED_PRE_DEADLINE`**.
- Fixed prompt-template hash: **12/12 matched** `d462767f4448e28fc735df7363fb6f54a577e014607d5ec3b2fb1a75137c5e7f`.
- No production A REVISION was observed.
- 1R was observed at 13:14:20 JST and ingested at 13:15:48 JST.
- 2R–12R were largely observed at 14:16:09 JST and ingested at 14:17:44 JST.
- Therefore timing completeness is good, but data freshness is heterogeneous. `pre-deadline` must not be interpreted as `fresh`.
- Payload-hash fields and idempotency keys are present. A full independent rehash of all 12 A payloads was not required to close this audit and remains separate from the timing/coverage conclusion.

## B — secondary observer

Production B LOCKs on 2026-09-17:

1. **9R** — record `rectVzwEY3qFn8zBk`
   - observed: 18:47:39 JST
   - ingested: 18:48:06 JST
   - deadline: 19:10 JST
   - timing: `VERIFIED_PRE_DEADLINE`
   - prompt hash matched expected B hash
   - canonical payload rehash matched stored payload hash

2. **11R** — record `rechQxMu02bzW0GrM`
   - observed: 19:49:00 JST
   - ingested: 19:45:49 JST
   - deadline: 20:10 JST
   - timing: `SUSPECT_TIMESTAMP`
   - signed observed-minus-ingested residual: **+191 s**
   - Airtable ingestion itself was pre-deadline
   - prompt hash matched expected B hash
   - canonical payload rehash matched stored payload hash
   - official result was `1-3-2`, which was included in B's five stored picks: factual HIT only; no model-performance inference is made from N=1

`B_PAYLOAD_HASH_INTEGRITY = VERIFIED 2/2`.

### B coverage limitation

Current B v3 does not specify a deterministic algorithm for which race(s) a run should target. It does not define, for example, earliest unlocked, next upcoming, all races in a window, or any other reproducible selection rule.

Therefore:

- `B_TARGET_SELECTION_REPRODUCIBILITY = NOT_GUARANTEED_BY_SPEC`
- `B_COVERAGE = UNVERIFIED`
- absence of B Event for another race must **not** be classified as persistence failure without first proving that race was an eligible target for that run
- historical Event existence remains factual; historical expectations about what "should" have existed must be reassessed after a target policy is defined

## C — controller / watchdog

### Runtime outcome

- Worker stayed alive through the observation day.
- Official raceindex acquisition failed throughout the relevant window.
- Tracking fallback discovered 12 races and maintained tracking-only deadlines; it was never promoted to official timing evidence.
- All 12 races reached `TERMINAL` with:
  - `terminal_reason = SOURCE_ERROR_TIMEOUT`
  - `terminal_missed_reason = MISSED_SOURCE_ERROR`

### Direct SQLite persistence proof

Read-only SQL was executed against `/var/data/gamagori_shadow.db` in the Render Web Shell.

Confirmed:

- `RACE_TERMINAL` rows: **12/12**
- race IDs 1R–12R: **12/12 present**
- Terminal Event ↔ `idempotency_keys` on key + UUID: **12/12**
- `RaceState.terminal_event_id` ↔ Terminal Event UUID: **12/12**
- RaceState race_id ↔ Event race_id + payload `terminal_reason=SOURCE_ERROR_TIMEOUT`: **12/12**

Final classification for this path:

`C_TERMINAL_DURABILITY = VERIFIED_BY_DIRECT_SQLITE_SELECT`

This proves today's successful persistence path. It does **not** remove code-level failure cases discovered below.

### Not exercised / not verified

Because the official source never recovered, the following normal paths had zero verified live executions:

- successful official raceindex route
- official-deadline update route
- normal `CLOSING_WINDOW -> FREEZE_ZONE / SAFE_STOP / C_EVENT_DONE` route on real official data
- real `REOPENED` deadline-shorten/extend behavior
- `MISSED_DATA_INCOMPLETE`
- `MISSED_WINDOW_SKIPPED_BY_DEADLINE_CHANGE`
- parser fail-closed checks against real race HTML
- restart/crash durability during the live day

C predictions are still based on the mock baseline repository; no prediction-performance conclusion is permitted from C.

## RESULT / Daily / derived layer

### RESULT Events

Production SYSTEM RESULT Events exist for all 12 races.

- source: `SYSTEM`
- model_version: `1.0-system`
- schema_version: `1`
- source acquisition time in payload: **22:31:54 JST**
- Airtable ingestion/creation time: **22:33:13 JST**
- producer_run_id: **blank on all 12**
- no production CORRECTION Event was observed for 2026-09-17

Independent verification performed with the frozen canonicalization rule:

`json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))`

- payload hash matched stored value: **12/12**
- RESULT idempotency key matched `SHA256("1|{race_id}|SYSTEM|RESULT")`: **12/12**

Therefore:

- `RESULT_PERSISTENCE = VERIFIED 12/12`
- `RESULT_PAYLOAD_HASH_INTEGRITY = VERIFIED 12/12`
- `RESULT_IDEMPOTENCY_DERIVATION = VERIFIED 12/12`
- `RESULT_PRODUCER_PATH = UNVERIFIED`

The timing is compatible with a process running around the Daily window, but the blank producer_run_id and Daily `last_run=null` prevent attribution. Temporal correlation is not treated as provenance.

### Daily

- configured schedule: 22:30 JST
- observed final task state: `enabled=false`
- `last_run=null`
- metadata was updated shortly after the RESULT ingestion window

Classification:

- `DAILY_TASK = NOT_EXECUTED / DISABLED`
- `DAILY_DISABLE_CAUSE = UNVERIFIED`
- `DAILY_FINANCIAL_ROLLUP = NOT_VERIFIED`

### RaceSummary

Direct table read found only the two existing TEST summaries and no 2026-09-17 production rows.

- `RACESUMMARY = DERIVED_LAYER_MISSING 0/12`

This is a missing derived layer, **not** loss of source-of-truth Events.

## Official transport failure

Render Singapore repeatedly timed out reading the BOAT RACE official raceindex endpoint. The same Render service could reach the non-official tracking fallback.

Verified fact: endpoint-specific official acquisition failed from this runtime.

Not verified: why. WAF/CDN policy, ASN/IP reputation, overseas routing/filtering, or other transport causes remain hypotheses only.

Post-audit network diagnostics should proceed in order:

1. DNS
2. TCP
3. TLS
4. HTTP

and compare Render with another cloud environment and a Japan-hosted environment under standard, permitted connection conditions.

## Code-level P0 findings

Current source inspection identified two critical durability defects and one missing semantic duplicate check:

1. **Terminal idempotency key is reason-specific**: current key is `{race_id}_TERMINAL_{reason}`. A crash after Event persistence but before State persistence can allow a second Terminal Event if reason changes after restart.
2. **False append result can still persist TERMINAL State**: `_emit_terminal` mutates State to TERMINAL before append and saves it even when append returns false. This can create `TERMINAL` with no `terminal_event_id` and block future processing.
3. **Duplicate handling is UUID-only**: repository duplicate handling returns an existing UUID but does not return/compare existing semantic Event material.

Required invariant:

`status == TERMINAL => terminal_event_id is not None`

## P0 implementation contract

P0-1 and P0-6 ship together:

- Terminal idempotency key becomes `{race_id}_TERMINAL`.
- Duplicate lookup returns full existing Event material.
- Add an `identity_hash` distinct from full `payload_hash`.
- Terminal identity is initially defined as semantic `race_id + terminal_reason`; volatile counters/timestamps are excluded.
- Existing persisted Event is canonical on duplicate; RaceState adopts its UUID/reason.
- Duplicate semantic mismatch becomes `DUPLICATE_CONFLICT` with explicit audit logging/health signal, but State remains TERMINAL because a real Terminal Event exists.
- Adapter outcome becomes explicit: `CREATED`, `DUPLICATE_MATCH`, `DUPLICATE_CONFLICT`, `FAILED`.

Additional P0:

- add `TERMINAL_PENDING` and `TERMINAL_FAILED`
- add `terminal_candidate_reason`
- add `terminal_emit_attempts`
- classify append failures as `RETRYABLE`, `NON_RETRYABLE`, or `UNKNOWN`
- HASH mismatch is non-retryable
- explicit unknown false result is treated as retryable until bounded retry limit
- watchdog reports `TERMINAL`, `TERMINAL_PENDING`, and `TERMINAL_FAILED` separately; only `TERMINAL` counts as terminal reached

## P1 follow-up

- deterministic B `select_targets()` policy + `policy_version`
- B and Health share exactly the same target-selection function and policy version
- persist TARGET_RACES / SKIPPED_RACES and reasons
- eligible-set provenance using policy spec hash, deadline snapshot hash, declared schedule hash, actual run timestamps, and schedule-drift flag
- split read status from write status (`EVENT_READ_STATUS` vs `EVENT_WRITE_STATUS`)
- immutable Terminal + CORRECTION for later truth changes
- clarify LOCK uniqueness scope, likely race x source
- explicit freshness tiers / residual timing fields

## Structural lessons

1. No observed error does not prove a path was exercised.
2. Terminal State does not prove Terminal Event persistence.
3. Matching idempotency key does not prove matching semantic meaning.
4. Missing Event does not prove persistence failure; the item may never have been a target.
5. To prove "not targeted", target-selection rules and runtime application evidence must exist before execution.
6. Scheduled time is not the same thing as observed execution.

Auditability requirement:

**auditability = predefined rule + runtime application evidence + reproducible rule/input provenance**

## Freeze decision

The 2026-09-17 evidence-gathering freeze is closed by this saved audit.

- Production/main/Render remains unchanged while P0 is developed and reviewed.
- Development is released **only on branch `p0-terminal-durability-v1.1`**.
- P0 must pass tests and review before merge to `main`.
