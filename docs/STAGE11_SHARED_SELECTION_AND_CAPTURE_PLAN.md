# Stage11: shared table discovery; capture plan is not deployed

Base: `6188b9fb3a357361e253d7ccb625929ed7fd8442`, draft PR #2.
Scope: refactor two candidate callers, one shared discovery module, 50 new
regression cases and this design note. No runtime connection, model/Readiness
change, new acquisition schedule, storage service, historical write or deploy.

## Implemented refactor

`table_selection.select_beforeinfo_tables()` owns the table-discovery rules
previously duplicated in `observation.py` and `withdrawal_observation.py`.
Both call the module function at runtime. It preserves the existing semantic
headers, direct-thead rule, exclusion of nested candidates and absolute table
index including skipped nested tables. It returns all matches, never the first
of ambiguous matches. Existing section validation and failure semantics remain
in the callers. The strict legacy beforeinfo parser remains unchanged and is
not silently redirected through this candidate path.

SelectedTable containers are frozen; BeautifulSoup nodes themselves are mutable.
This is not an immutability/security boundary. The selector does not mutate the
DOM. Within one parse a selected table is the same node (`is`) at its absolute
index. Across separately created DOMs, `id()` equality is meaningless and is not
used as an assertion of evidence identity. Future integration must bind both
outputs to the same raw-body snapshot/hash and locator; this refactor alone
does not implement or enforce that acquisition boundary.

## Regression evidence

Baseline459 tests pass before and after the refactor, without changes to any
existing test. Fifty new cases test duplicate/missing tables, nested/irrelevant
prefixes, ordering, misleading headers and notes, withdrawal tokens, invalid
late rows, nonmutation, absolute locator stability and both consumers actually
using the shared function. A controlled interception verifies the same selected
table content reaches each caller's helpers for each of20 authored cases.
Local total509 / no failures or skips. Remote CI must be checked separately.

Full observation/scanner outputs were compared with Stage10 in isolated Python
processes across33 inputs:20 authored cases, one unchanged post-incident12R
capture, and12 deliberately mutated captures (two fields x six boats). All
previously returned fields are identical. There are still zero genuine
withdrawal-positive captures. The unchanged real page produces SCANNED with
signals=[], not proof of absence of withdrawal or ACTIVE status. One future real
positive fixture will validate its observed layout, not all possible layouts.

## Proposed routine capture scope — NOT IMPLEMENTED

Prefer scheduled coverage of all12 races over a trigger that requires detecting
withdrawal first. Retain racelist and beforeinfo responses for every planned
observation phase and later classify affected races using verified official
results/notices. Neither a missing result nor F/L alone establishes withdrawal.
Do not promise all transient changes will be caught between observation times.

The following must be resolved before code or configuration is enabled:
- Collection phases/frequency: consider reusing existing reads and filling
  coverage gaps rather than issuing unbounded extra polling. A full-day planned
  set must be explicit; opportunistic reads alone may leave races uncaptured.
  Closing-window membership, remaining processing budget and content freshness
  remain separate checks. No interval or cutoff is fixed by this stage.
- Store body bytes before parsing, with an independent acquisition receipt per
  URL/attempt. Preserve the successful side when the paired request fails.
  Record race/date/venue, run/phase/attempt, request and final URL, HTTP status,
  content type, start/end/acquired times, response length, body SHA256, storage
  reference and readback outcome. Unknown publication times stay null.
  A 'pair' records its actual acquisition skew, not a fictional common instant.
- Separate scheduled/attempted/received/persisted/readback counts. HTTP success
  or parser success is not storage success. Parser failure must not discard the
  body. Failed/truncated responses remain marked and are never eligible input.
- Content-addressed blob deduplication may save space, but preserve every
  timestamped receipt. Repeated body hashes do not prove no change between
  captures, or freshness of the publisher's data.
- Decide store type, byte/request limits, access control, retention period and
  deletion policy before use. Archive to a distinct evidence store; do not
  overwrite historical Events/RESULT/Summary or put all HTML inside those rows.
  Only public response data and an allowlist of useful headers belong in this
  archive, not authentication headers, credentials or cookies.
- After a genuine withdrawal case is found, pin its original captured bodies,
  error receipts and provenance plus a reviewed expected interpretation. Paired
  pages are different endpoints from one publisher, not independent publishers.
  Observe variations (pre-publication/withdrawal/refund/cancellation) before
  introducing new eligibility or OFFICIALLY_WITHDRAWN mappings.

## Size illustration, not a cost or capacity promise

The stored Stage10 captures used here are69,902/70,032 bytes for two racelist
pages and48,615 bytes for one beforeinfo page. Mean pair=118,582 bytes.
For12 races and k paired snapshots per race, raw bodies only are:

    bytes_per_day = 12 * k * 118582
    request_attempts_before_retries = 24 * k

k=1:1.36MiB/day; k=3:4.07MiB/day; k=10:13.57MiB/day. Multiply by retained
race-days for a raw illustration. These sample sizes are not maxima; no retries,
headers, manifests, result pages, duplicate versions, indexes, backups or storage
overhead are included. Compression/dedup savings are not assumed. No retention
period, k, storage cost or acquisition configuration is selected here.

## Unchanged holds

No new ROSTER_CORROBORATED eligibility, ACTIVE mapping, reduced participant
policy, official withdrawal status, freshness threshold or confidence score.
No PR #1 integration, enforced old-API isolation, production completion claim or
push-delivery claim. Next is a scoped capture implementation proposal and real
source examples, not relaxing unknown states to force a replay PASS.
