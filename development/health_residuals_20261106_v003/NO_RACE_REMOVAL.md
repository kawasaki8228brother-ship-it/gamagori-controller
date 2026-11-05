# D3 removal of active calendar-authority paths; D4 narrow observation code

Offline candidate only, based on the root-pinned `48333…` parent. No live request,
actual official calendar, source/receipt authentication, real DB, environment
change, task, Render or Production operation was performed. All test input is
invented2099 HTML/JSON or mocked exceptions. Actual 11/5 cause remains UNVERIFIED.

## D3: remove the surface, not merely disable a compatible hook

S2 stopped trusting self-reported proof and kept twelve races, but retained inert
authority-shaped APIs and a special unverified exception route. D3 deliberately
removes those active production interfaces:

- `OfficialDataFetcher` no longer accepts or stores
  `schedule_evidence_provider` and has no `_expected_race_numbers` method.
- `NoRaceVerified` and `reviewed_schedule_decision` are absent from both official
  and status modules. There are no compatibility aliases or dormant activation
  flags.
- `SCHEDULE_UNVERIFIED` and its special classification are removed. Unknown
  names/legacy kind strings go through ordinary UNKNOWN_FAILURE handling.
- Both official and tracking fetch paths refer directly to
  `FULL_RACE_NUMBERS=frozenset(range(1,13))`. Self-hash, review boolean, receipt
  hash, dynamically attached old attribute or claimed calendar cannot select an
  empty/shorter universe or skip fetches.

Old callers passing the removed keyword now receive TypeError before client
construction. Code importing removed symbols must be updated; preserving a
misleading activation surface is not a compatibility goal of this correction.
A future actually authenticated calendar would require a separately designed,
reviewed and approved change, not an environment/test flag or restored alias.
An actual short day cannot be admitted by the present fetchers.

The safe classifier does not evaluate an unknown exception's str/repr. A custom
exception whose class is named NoRaceVerified is just an unknown exception.
Generic `IndexFailure` objects with removed kind strings normalize to
UNKNOWN_FAILURE; they do not certify absence, latch the whole monitor or cause
cache removal. Root owns the separate controller change that preserves normal
fallback for untrusted failures and removes the old latch/cache-clearing route.
This source change itself performs no state/cache/database operation.

Historical v001/v002 originals and documentation retain their exact old names
and behavior descriptions as evidence, not active API declarations. Root
archives the old test/source originals and excludes those historical materials
from the active production port scope. This new document supersedes, rather
than silently rewrites, their current-behavior claims.

## D4: no rows is an unauthenticated observation, not a non-race decision

The official wrapper emits this dedicated fixed pair only for the exact known
parser observation:

```text
kind = HTML_PARSE_FAILED
reason = RACE_INDEX_NO_RACE_ROWS_UNAUTHENTICATED
```

The selector requires **type exactly ParserError** and args exactly
`("raceindex: no race rows with race number + deadline found",)`. It does not
search exception strings, use a prefix/substring or invoke str/repr. A partial
parse, missing/ambiguous header, similar message with extra context, subclass,
unknown error, HTTP failure or arbitrary body failure does not acquire this code.
Other ParserError cases stay RACE_INDEX_HTML_INVALID; other exception types stay
UNKNOWN_FAILURE. New errors contain no HTML, URL, private path or original
exception representation.

This code means only that the parser found no race-row labels in that response.
HTML200/no rows cannot prove a non-race day. It is neither verified NO_RACE nor a
new cancellation/terminal rule. Root's separately owned D4 diagnostic may use
this reason **and** TRACKING_STADIUM_7_MISSING **and** absence of same-day racing
material to report an unauthenticated candidate. A generic parse failure must
not trigger that diagnostic. Its final controller behavior requires root's own
regression evidence; the scoped source tests below do not claim it was executed.

Tracking remains FALLBACK_TRACKING_ONLY and always has is_closed=false and
is_cancelled=false. Empty/malformed tracking does not prove official absence.
Existing strict date/deadline/domain checks remain in force. TLS, HTTP client
headers, timeout, retries/backoff, `_get_text` behavior, beforeinfo/odds helpers,
model logic, state-machine rules and dependency/Render settings are not changed
by this D3 task. C4 transport-metadata work is separate; none is added here.

## Exact reason for test replacements

`tests/test_health_official_index.py` retains the 41-case collection and the
ordinary HTTP, complete12, malformed/partial HTML, tracking, date/deadline and
safe-diagnostic regressions. Its old provider fixture argument and imports are
removed. Authority-hook cases now verify that the removed keyword is rejected,
and partial-day cases use the fixed twelve-race path without a provider. The
three-way HTML observation case distinguishes exact no-row reason from generic
HTML parsing failure. No successful absence or partial8 acceptance is restored.

`tests/test_health_v002_schedule.py` is intentionally replaced for D3. The S2
tests that called an inert decision function, instantiated its legacy class or
expected an ignored provider argument are no longer valid API tests. Their
replacement checks absence of the symbols/constructor hook, rejection of
matching and arbitrary self-reported claims, full12 operation, ordinary unknown
classification and safe handling of malicious exception attributes. The root's
archive preserves the exact old file for diff review. This replacement has 15
cases versus the S2 file's 17; the reduction is not an unreported test deletion
or a statement that authentication became implemented.

`tests/test_health_v003_no_race.py` adds 12 cases: removed-argument rejection
before HTTP client creation, direct full-set parser binding, injected old
attributes remaining unused, partial8 rejection, exact no-row selector, generic
or subclass parser error nonselection, unknown exception names and active-symbol
absence.

Executed scoped result: **68 passed** (41 + 15 + 12), Python3.14.3, mocked HTTP,
nice10, `-B`, pytest cache disabled:

```sh
nice -n 10 /workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -p no:cacheprovider tests/test_health_official_index.py tests/test_health_v002_schedule.py tests/test_health_v003_no_race.py -q
```

No commit/push, application, provider activation, merge or deploy is included.
Actual source truth, authenticated calendar handling and natural-run operation
remain OPEN/UNVERIFIED. The new observation code grants no operational authority.

## D4 review correction: stale declared date before stadium absence

Review found that tracking top-level/programs date checks ran only after stadium7
was found. A previous-day document with stadium7 absent could therefore produce
TRACKING_STADIUM_7_MISSING and, with official no-row HTML and no current material,
the wrong current-day absence diagnostic. The existing date conditions are moved
before that missing-stadium branch; the stadium's own date check remains after
its object is obtained. Accepted date formats, types and target-date comparison
are unchanged. No HTML or transport change is involved.

Two added end-to-end synthetic regressions cover a stale declaration at payload
and programs level with stadiums={"1":{}}. Together with actual no-row parsing,
both yield TRACKING_PARSE_FAILED / TRACKING_PAYLOAD_DATE_MISMATCH and
NORMAL_SOURCE_FAILURE, never NON_RACE_CANDIDATE_UNAUTHENTICATED; no race/event
write or dispatch occurs. Root main is unchanged by this correction. Final
scoped count becomes 70 (41 + 15 + 14), with existing index/tracking cases retained.

## 02:20 review addendum: explicit document date is required

The tracking document must explicitly declare date in payload or programs (at
least one). Every declared date still must match the requested target using the
unchanged date/type/format conditions. If neither document-level field exists,
classification is TRACKING_PARSE_FAILED / TRACKING_PAYLOAD_DATE_UNVERIFIED,
regardless of stadium7 presence. A stadium-internal date cannot substitute:
when stadium7 is missing, its internal metadata cannot be inspected at all.
Unsupported actual source shapes therefore remain OPEN/UNVERIFIED.

Absent/previous-day dates do not yield TRACKING_STADIUM_7_MISSING and cannot
support D4's current-day diagnostic. A current request URL or local acquisition
timestamp does not freshen an old mocked JSON body. No actual response cache
headers, CDN behavior or Age values were observed; no new Age threshold, cache
rule or HTTP behavior is introduced.

Five added synthetic cases cover missing document date with stadium7 absent or
present, preserving an existing current-day cache, a current request receiving
old JSON, and a current root date with previous-day programs date. Combined with
official no-row HTML, all remain normal source failure with calendar UNVERIFIED;
there is no NON_RACE candidate, fabricated official zero universe, write or
dispatch. One old stadium7-absence fixture now explicitly includes current date
to preserve its existing TRACKING_MISSING assertion. That input clarification,
not an assertion weakening, is reported to root's separate test-change table.
Final scoped verification after this addendum: 75 passed (41 + 15 + 19), plus
in-memory compilation of owned Python files; no bytecode/pytest cache written.
