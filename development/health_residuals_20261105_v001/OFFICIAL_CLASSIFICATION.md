# Official index classification candidate

Offline development and mocked-HTTP verification only. No actual website,
2026-11-05 response, Render service, task, calendar original or Production state
was inspected or changed. The actual 11/5 HTML failure cause remains UNVERIFIED.
No new Model/BOX/LOCK/deadline decision, terminal rule or cancellation is adopted.

## Typed observations, never absence inferred from failure

`raceindex_status.IndexFailure(kind,reason)` carries only fixed allowlisted
fields. `str`/`repr` contains no source URL or original exception detail.
`classify_index_exception(exc)` returns `{kind,reason}`; unknown exceptions are
UNKNOWN_FAILURE / UNCLASSIFIED_EXCEPTION without invoking their str/repr.

| Kind | Meaning |
|---|---|
| HTTP_FETCH_FAILED | No usable official/tracking response after fetch failure; no schedule inference |
| HTML_PARSE_FAILED | Official response arrived but the conservative HTML contract failed |
| TRACKING_MISSING | Tracking stadium 7/races absent, never official proof of no races |
| TRACKING_PARSE_FAILED | Tracking JSON/schema/race/date/deadline/domain invalid |
| UNKNOWN_FAILURE | Unsupported exception or unknown invocation state |
| NO_RACE_VERIFIED | Only the optional externally reviewed calendar contract below matched |

`NoRaceVerified()` is an IndexFailure subclass for the last case. The controller
must catch it before general failure handling, log the observation and skip the
poll's race processing. It is not an instruction to mark existing races
TERMINAL/CANCELLED, clear authoritative state, or reinterpret a tracking status.
No rows, HTTP200, empty HTML, a ParserError, a missing tracking stadium, DNS,
timeout, TLS or other fetch error can produce this exception by themselves.

## Conservative expected universe

`OfficialDataFetcher(..., schedule_evidence_provider=None)` defaults to no
calendar provider and expected race numbers 1–12. Its official fetch calls
`parse_race_index(...,expected_race_numbers=frozenset(range(1,13)))`; the parser's
legacy optional small-fixture mode is never the fetcher's default. Partial pages
therefore fail, even if their few rows are individually readable. Only accepted
RACING_DAY calendar evidence can provide a smaller explicit expected set.
The same expectation applies to the non-official tracking universe.

Both index methods require an aware caller time and convert its instant to JST
before target-date construction. Naive time is UNKNOWN_FAILURE; wrong timezone
or payload date is not repaired by overwriting a date or attaching JST silently.

## Optional normalized calendar contract: PROPOSED, actual adapter OPEN

The optional provider is a synchronous callback `(now_jst)->evidence`. No real
provider, calendar URL fetch, runtime setting, environment switch or actual
source parser is implemented/configured. Invalid, missing, unavailable or
unreviewed evidence retains the conservative twelve-race expectation; it never
authorizes absence or a shorter day. The actual provider and independent review
protocol require separate approval before configuration.

Exact normalized evidence fields:

```text
schema: OFFICIAL_SCHEDULE_EVIDENCE_V001_PROPOSED
date: YYYYMMDD (exact requested JST date)
venue: "07"
event: NO_RACE | RACING_DAY
race_numbers: [] for NO_RACE; distinct integer1..12 list for RACING_DAY
authority: OFFICIAL_SCHEDULE
raw_evidence: nonempty original bytes
raw_sha256: full lowercase SHA-256 of those exact bytes
independent_review: {
  reviewed: true, receipt_sha256: full lowercase SHA-256,
  date, venue, event, race_numbers, raw_sha256: exact normalized binding
}
```

The review flag is an actual boolean, never 1. Raw digest, target date, venue,
event and universe must bind exactly. Accepted NO_RACE raises before HTTP in
both index methods; accepted RACING_DAY supplies the exact expected set. An
unaccepted contract proceeds with twelve, rather than quietly accepting eight
rows or mislabeling an outage as a non-race day.

**Verification scope:** raw SHA and normalized/review bindings establish local
consistency only. The code does not parse an unknown actual calendar format or
authenticate its truth, reviewer independence, receipt original or authority.
`reviewed_schedule_decision` explicitly reports external_authenticity=UNVERIFIED.
An actual provider must supply independently checked originals with date/venue
and planned-universe semantics; a hash-shaped metadata claim alone is not that
external check. Tests use invented2099 calendar bytes and a fake receipt, not
an actual official NO_RACE observation or permission to configure a provider.

## Tracking remains tracking only

Tracking parsing rejects malformed/non-object JSON, duplicate JSON keys,
nonfinite JSON, unsupported object shapes, absent/ambiguous stadium keys,
contradictory explicit dates or stadium IDs, malformed rows/numbers, key-number
mismatch, duplicate race numbers, missing/malformed deadlines and incomplete
expected universes. One invalid row invalidates the snapshot; rows are not
silently skipped into an apparently successful partial result.

The existing explicit legacy tracking `YYYY-MM-DD HH:MM:SS` format means JST.
ISO form must instead have an explicit valid offset/Z. Naive ISO, -00:00,
invalid offsets, invalid clock values and excess fractional precision fail.
After conversion to JST every deadline must match the requested day. A UTC
timestamp belonging to the next JST day is rejected, never redated.

All returned tracking records always have `FALLBACK_TRACKING_ONLY`,
is_closed=false and is_cancelled=false, even if payload flags claim closure.
They are not evidence for official LOCK, timing confirmation, cancellation,
closure or formal scoring. Existing state-machine/model behavior is not edited.

## Transport and tests

`_get_text(url)->(text,acquired_at)` retains its signature, timeout, configured
retry count, host alternation, exponential backoff, concurrency, HTTP headers,
redirects, HTTPX default TLS verification and trust behavior. Only diagnostics
and typed terminal fetch errors change: retry logs omit URLs/exception repr,
and terminal errors are fixed codes. Beforeinfo/odds fetching/parsing helpers
retain their APIs; no `verify=False`, dependency or Render configuration change.

The scoped suite has 41 passing cases on Python3.14.3: complete12 HTML, no-row
HTTP200, partial/unsupported HTML, valid/invalid calendar bindings, fake reviewed
short schedule, provider exception, mocked HTTP/proxy failures and safe logs,
tracking-only flags, stadium7 absence, malformed JSON, duplicate/partial/wrong
date records, bad timezones/deadlines, JST target-date conversion and safe typed
classification. All HTTP calls are mocked; no actual source response is used.

```sh
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -p no:cacheprovider tests/test_health_official_index.py -q
```

Production application, real calendar mapping, actual 11/5 root cause, source
authenticity and natural-run behavior remain OPEN/UNVERIFIED. No merge/deploy,
task change, live request or calendar-provider activation is authorized here.
