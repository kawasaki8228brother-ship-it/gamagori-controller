# P2 read-only audit plan: NOT EXECUTED

Base `8172aec010894a52f36f48b7091476d26494e4ee`. Evidence is local source inspection or labelled received information. No live tool, production Shell/DB read, send or app import occurred. Later live inspection requires Andy's individual GO and a bounded private plan.

## Context and DB identity

Local facts: `main.py` defaults DRY_RUN=true and raises when false; its constructor wires DryRunAirtableAdapter and opens the repository. Do not instantiate/import it. C_ACTIVE was not found in base sources; actual definition/value is UNVERIFIED, not inferred from DRY_RUN. `render.yaml` declares `gamagori-controller-shadow`, mount `/var/data`, DB `/var/data/gamagori_shadow.db`; declarations are not actual Render evidence.

Future readback must bind actual service ID/name, approved app SHA, time, disk/mount, limited STATE_DB_PATH if needed, and the same worker's startup `dry_run=... db=...` line. Verify DRY_RUN without environment dumps/secrets; obtain C_ACTIVE's authoritative definition, never set/invent it. Old audits/path strings are insufficient. Unknown/mismatched identity is HOLD before DB access.

Verify deployed `sqlite_readonly_audit.py` against the local reviewed copy: **6,348 bytes; SHA-256 `354940e9a77d2eaf86feaa1c50089db4a0e410cc5f2fdafd6598d66367566b94`**. This is a local hash, not Render readback. It uses short URI `mode=ro` connections, no live `immutable=1`, connection-local busy_timeout and read-only journal-mode inspection. No app/repository initialization, write transaction, migration, checkpoint, VACUUM, file copy or repair.

Live WAL reads can update normal SHM locks/read-marks: do not claim physical-write-zero or use `immutable=1`. DB/WAL data changes/custom SHM writes stay forbidden. Unexpected files/changes, errors or unknown behavior mean STOP, no workaround. Sequential autocommit queries are not a cross-table atomic snapshot or execution trace; concurrent counts may differ.

Keep paths/states/error text private. Total counts span all dates; current-date filters are race-prefix scoped, not all Events/AuditRuns/unlinked records. Read failure is unknown, not COUNT=0. Pending/nonterminal/unknown interpretation needs reviewed state definitions, not absent-row inference.

## Delivery and run identity

DryRunAirtableAdapter persists local events and logs external readback NOT_APPLICABLE_DRY_RUN, not Airtable/notification arrival. Separate dry-run/local persistence, send attempt, transport acknowledgment, destination delivery and human read. Scheduler success proves none of them. Actual external receipts are absent; do not send a test or write a receipt to fill the gap.

Scheduler internal run ID, producer_run_id and AuditRuns UUID are separate identifiers. Require original scheduler/API and START/END receipt evidence for any mapping; timestamps, similar strings and UUID fragments are insufficient. Never fabricate a missing run ID.

Latest received A-OBS answer: the dedicated original contract has not been matched. Only A RUN_START/END producer_run_id and the idempotency SHA-256 pattern `1|A|...|RUN_START` are confirmed as received; the ellipsis is not a complete hash test vector. This does not establish OBS payload-UUID requirements, column-only eligibility, empty-RUN_START behavior or whether a missing property violates OBS. Those remain UNKNOWN. Related predictive-spec reference `d462767f4448e28fc735df7363fb1a75137c5e7f` was labelled SHA256 but is 40 hex characters; preserve that label/value, mark algorithm UNVERIFIED, do not reinterpret it as the dedicated OBS contract or guess an algorithm.

## Reported B duplicates: private classification only

Past 24 B duplicate LOCKs are user-reported, not reread live. Later private grouping needs the formal source-bound key: same-key/same-hash differs from same-key/different-hash conflict. Neither authorizes deletion/replay. Same canonical content/different encoding requires verified serializer/hash rules. Missing/null/empty/0/false stay distinct; cross-source/key equal hashes are not automatic duplicates.

Local C uniqueness/serialization does not define B's payload/column-hash contract or disprove external duplicates. SYS-07 review is required: no integration, merge, correction, deletion, deduplication or new VALID rule. Preserve LOCK, deadlines, A/B independence, Model/BOX/Freeze and G1-G6; missing gate definitions stay OPEN.
