# D5: C4/C5/C7/C8 offline audit-quality components

Parent `48333a2315628ae17e1fa3ce4f8ef12c70e2662f`. This addition reads supplied synthetic/local observations, not services. It neither imports the app nor opens a DB, starts a source client, sends a notification, changes an existing writer or integrates into runtime `_get_text`. `PORT_SCOPE=OFFLINE_ONLY_RUNTIME_INTEGRATION_OPEN` is present in every report; `official_success=NOT_ASSESSED` and `production_go=false`. Runtime porting and actual source/DB/receipt evidence remain OPEN.

## C4 HTTP/fetch/parse/length layers

`diagnose_http_observation(observation)` accepts only these proposed normalized fields: `status_code`, `fetch_state`, `parse_state`, `content_length`, `content_length_unit`, `wire_body_bytes`, `wire_count_unit`, `decoded_body_bytes`, `decoded_count_unit`, `content_encoding`, `text_encoding`, `stream_completed`, `document_end_observed`, `parsed_rows`, `table_tag_observed`. Unknown fields or malformed/missing measurements are diagnosed without echoing their values.

HTTP status is an integer 100-599 or unobserved; bool is not an integer measurement. Fetch RETURNED/FAILED/UNKNOWN is independent of parse PARSED/REJECTED/NOT_ATTEMPTED/UNKNOWN. A returned HTTP403 is recorded as 403, not a transport error or parser diagnosis. Failed fetch/rejected parse are separate reason codes. Body counts are nonnegative integers or unknown/null, never guessed from row count or string length.

The proposed units are explicit: Content-Length `OCTETS`; wire count `ENCODED_ENTITY_OCTETS`; decoded count `DECODED_ENTITY_OCTETS`. A TLS/TCP/header/chunk-frame byte total, Unicode character count or re-encoded text length is not automatically one of these. Comparable encoded entity counts can match/mismatch independently of decoded length. Gzip/br Content-Length must not be compared to decompressed bytes; with no encoded-byte measurement it is UNVERIFIED rather than proof of truncation. With an explicitly supplied comparable encoded count, only that comparison is reported. Identity encoding can separately expose contradictory encoded/decoded counts.

Stream completion, observed document end, charset declaration, parsed rows and table presence remain separate fields. Twelve rows or a table/closing tag do not prove stream completion, encoding correctness, official source success or calendar truth. Even all matching supplied declarations yield only `CONSISTENT_SUPPLIED_DECLARATIONS_ONLY`, never a network/official PASS. Missing status, unknown units, an impossible gzip comparison, incomplete stream or missing end remain UNVERIFIED; actual contradictory comparable counts are INCONSISTENCY. No HTTP body/header/URL is fetched or returned.

## C5 previous-day nonterminal states

`summarize_prior_unfinished(states, target_date)` accepts a provided list of normalized `{race_id,status}` views and strict YYYYMMDD target date. It uses the fixed parent's C `models.py::RaceStatus` names; TERMINAL alone is terminal for this count. A prior nonterminal state is not itself a missed LOCK, cancellation or eligibility verdict. The function neither reads nor modifies repository state.

The previous day means target minus one calendar day, separately from older days. Invalid calendar/ID, missing fields, unknown fields/status and duplicate identities are reported separately. It never chooses one version of a duplicate state. Unknown rows make the whole-cohort previous count null; a valid-subset observation count remains labelled as partial. An explicitly empty provided list has observed-scope count zero, whereas a missing/unreadable collection is unknown. Source completeness always remains UNVERIFIED_NO_DB_READ; no race IDs or raw field values are emitted.

## C7 reuse the reviewed A-only implementation

`audit_operational_rows(rows)` reuses `development/health_residuals_20261105_v001/obs_qa.py` from the pinned parent, rather than implementing another A schema. It verifies **16,027 bytes**, SHA-256 `dc6bdc6b77a3c4ce4f5b718cfd43be7fe1cc0d08d4e0e54057949ce7032e5634`, then compiles only those trusted local bytes in memory without a bytecode cache. No submitted payload is executed. A missing/mismatched source is UNVERIFIED; no fallback module is selected.

The original report is nested without rewriting history. It checks the already supplied A RUN_START/END formula, provided field disagreements, identical same-key observations and same-key/different-raw-payload conflict. A local hash match is not proof of the actual A canonical profile, full OBS contract, source authenticity or LOCK validity. B and LOCK remain outside that checker: B's formal formula is unprovided/UNVERIFIED and never receives A's formula. No deduplication, event edit, merge, replay or correction is performed.

The original module deliberately retains its historical 40-hex related reference. The wrapper points to the unchanged v002 `OBS_SHA_CORRECTION.json` alongside it: the later 64-hex related A prediction-spec reference is a received format correction, not an independently matched OBS contract. Payload UUID necessity, column-only eligibility, empty RUN_START and missing-property obligations stay contract-unverified. `make_synthetic_operational_fixture()` delegates to the same old invented fixture generator.

## C8 OFFHOURS read-only plan, never execution

`sqlite_offhours_audit_plan(request)` proposes exact fields: `window`, `window_confirmed`, `service_identity_confirmed`, `individual_go_reference_sha256`, `active_processing_absent_confirmed`, `db_open_mode`, `immutable`. OFFHOURS, verified identity/window/no competing processing and an individual GO reference are intended future review gates. They are not measured or authenticated by supplied flags/hash shapes. No schedule, reservation or Automation is created.

The sole proposed statement is the **value query** `PRAGMA journal_mode`, with no assignment. The live DB mode must be `mode=ro`, immutable false. Normal SQLite WAL SHM read-lock/read-mark effects may occur; do not claim physical-write-zero or use live `immutable=1` to bypass them. No journal-mode change, write transaction, checkpoint, VACUUM, app constructor, migration or repair is allowed. Unknown gate/window/identity/mode is UNVERIFIED. Even complete assertions return DESIGN_DECLARATIONS_ONLY_NOT_EXECUTION_GO, with DB-connection/reservation/execution flags false. Actual read requires a later scoped GO and reviewed original helper; none is run here. No real or temporary DB was needed for these pure design checks.

## Checks and remaining work

The new stdlib unittest file uses only invented observations/states and the pinned synthetic A fixture. It covers numeric status/fetch/parse separation, row/tag nonproof, units, gzip, mismatched counts, unknown values, date/status/duplicate aggregation, A agreement/disagreement/duplicate/conflict, B isolation, source-pin rejection and a forbidden-SQLite-connect assertion. Local commands use `nice -n 10`, `-B` and an existing interpreter; no install or environment change is requested. Root retains final logs/environment and hashes. These checks do not test runtime HTTP instrumentation, actual header units, stream drains, true prior-day state scope, B rules, off-hours scheduling, clock accuracy or production SQLite compatibility.
