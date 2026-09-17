# 2026-09-17 P0 Independent Review Disposition

Branch: `p0-terminal-durability-v1.1`  
PR: `#1 P0: harden terminal durability and idempotency semantics`  
Status: Draft / not merged / production `main` and Render unchanged

This addendum records the disposition of the second independent review. It does not rewrite the factual 2026-09-17 live audit. The live audit remains the evidence record; this document records post-audit implementation decisions.

## Review principle

The same evidence rule used by the live audit applies here:

> A path is PASS only when it actually executed and produced observable evidence.

Code inspection and automated tests can verify implementation properties, but they do not convert an unexercised production path into a live PASS.

## S2-1 — legacy reconciliation must leave evidence

**Disposition: FIXED BEFORE MERGE.**

A pre-P0 row with `status=TERMINAL` and no `terminal_event_id` is no longer silently normalized into an indistinguishable clean row.

RaceState now preserves migration provenance:

- `legacy_migration_disposition`
- `legacy_reconciled`
- `legacy_reconciled_at`
- `legacy_reconcile_source_uuid`
- `pre_reconcile_status`
- `pre_reconcile_terminal_reason`
- `legacy_candidate_event_uuids`

For a successful legacy reconcile, the disposition is `RECONCILED_TO_EVENT`. The original State status/reason and the Event UUID used for repair remain persisted after migration and across restart.

For an unreconcilable row, the disposition is `QUARANTINED_UNRECONCILABLE`.

RaceState remains a derived layer and may be repaired, but the fact that a repair occurred is now retained.

## S2-2 — persisted Event is canonical during legacy reconcile

**Disposition: FIXED BEFORE MERGE.**

Legacy reconciliation occurs only when exactly one `RACE_TERMINAL` Event exists for the race and that Event has a valid `terminal_reason`.

On reconcile:

- `terminal_event_id` adopts the persisted Event UUID.
- `terminal_reason` adopts the persisted Event's `terminal_reason`.
- valid persisted `terminal_missed_reason` is adopted when present.
- the old State reason is retained as `pre_reconcile_terminal_reason` and, when valid, as `terminal_candidate_reason`.

Therefore a legacy State/Event disagreement cannot be repaired by copying only the UUID while retaining a contradictory State reason.

If the sole Event has an invalid/missing terminal reason, the row is not normalized; it is quarantined as `TERMINAL_FAILED` with `LEGACY_UNRECONCILABLE:INVALID_EVENT_REASON`.

## S2-3 — legacy quarantine is distinct from runtime append failure

**Disposition: FIXED / EXPLICITLY SEPARATED.**

Legacy migration failures use a dedicated failure-detail namespace:

- `LEGACY_UNRECONCILABLE:NO_TERMINAL_EVENT`
- `LEGACY_UNRECONCILABLE:AMBIGUOUS_EVENT_COUNT:<n>`
- `LEGACY_UNRECONCILABLE:INVALID_EVENT_REASON`

When more than one candidate Terminal Event exists, all candidate UUIDs are stored in `legacy_candidate_event_uuids` and included in the critical migration log.

The watchdog separately exposes persistent totals:

- `legacy_reconciled_total`
- `legacy_unreconcilable_total`

These totals are calculated across the persisted State DB rather than only the current race universe, so a historical migration repair does not disappear merely because today's races are different.

## S2-4 / S2-5 — TERMINAL_FAILED retry and guard policy

**P0 policy decision: `TERMINAL_FAILED` is intentionally sticky.**

`process_race()` returns immediately for `TERMINAL_FAILED`. It does not automatically call `append_event`, fetch live data, or consume more retry attempts.

Rationale for P0:

1. bounded retry must remain bounded;
2. automatic re-arm without a separate retry epoch/time budget can silently recreate an infinite retry loop;
3. a failed terminal must stay visible to the watchdog rather than oscillating between states;
4. the current controller is still `DRY_RUN=true` shadow-only. Its real adapter persists locally to SQLite; transport-level retry behavior for a future production external-write adapter has not yet been validated.

Current default remains `TERMINAL_MAX_RETRIES=3`. This is an **attempt bound, not a claim that three attempts is the correct future production network budget**.

Before any non-shadow external write path is enabled, a follow-up must choose and test one of:

- time-window retry budget;
- explicit operator/manual re-arm with audit evidence;
- a bounded retry-epoch model with a durable re-arm event.

Until that design exists, automatic re-arm is deliberately prohibited.

A dedicated test verifies that a persisted `TERMINAL_FAILED` is not reprocessed and that its attempt count remains unchanged.

## Closing identity semantics — explicit limitation

P0 Closing identity is:

`event_type + race_id + deadline_version`

and Closing idempotency key is effectively scoped by:

`race_id + deadline_version`.

Therefore Closing identity does **not** independently encode the contents/conclusion of the observation. For a duplicate key in the same deadline version, the first persisted observation is treated as canonical when the structured identity fields match.

This is intentionally narrower than Terminal identity:

- Terminal key: race scope
- Terminal identity: race + terminal reason
- Closing key/identity: race + deadline version (+ fixed event type)

Implication: P0 duplicate conflict protection is meaningfully stronger for Terminal than for Closing. The current Closing identity should not be described as proving full payload-semantic equality.

The normal official Closing path had zero verified live executions on 2026-09-17. Therefore this identity choice remains a **P1 design decision**, not a production-proven behavior. P1 must decide whether Closing identity should include additional semantic decision fields before broader production use.

## Merge gate after this disposition

Observed on the updated PR merge-result checkout:

- Python compile check: **PASS**
- pytest: **29 passed** on Python 3.12
- migration provenance tests: **PASS**
- canonical Event reason adoption test: **PASS**
- ambiguous legacy candidate quarantine test: **PASS**
- invalid legacy Event reason quarantine test: **PASS**
- sticky `TERMINAL_FAILED` guard test: **PASS**
- watchdog legacy migration counter test: **PASS**

Still required before merge:

- independent review of the updated branch or explicit acceptance of the recorded dispositions;
- intentional merge approval;
- no production deploy until that approval.

No statement in this addendum upgrades the unexercised normal official Closing path to PASS.
