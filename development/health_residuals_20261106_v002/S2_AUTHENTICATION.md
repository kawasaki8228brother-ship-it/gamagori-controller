# S2: calendar authentication unavailable; absence/short-day admission disabled

Parent: `845cc1c9` (the fixed full parent SHA is recorded by root).
This change is offline development only. No actual official calendar, 11/5 HTML,
independent receipt, private source, live HTTP, real DB, Render, task or Production
operation was used. Actual source/receipt authentication remains **OPEN**.

## Corrected boundary

A raw-byte self-hash, matching normalized date/venue/event, `reviewed=true`, a
hash-shaped receipt or an OFFICIAL authority string does not authenticate
calendar truth or reviewer independence. All-zero hashes and arbitrary valid
hex strings are also not proof. V001 admitted a locally self-consistent calendar
claim into a no-race or short-universe action; that admission is withdrawn.

No real authentication adapter exists. The selected S2 remedy is to disable
calendar-based non-race/short-day admission completely, rather than add another
self-asserted flag, test-only acceptance mode, environment variable or bypass.
Even an actually correct calendar cannot be recognized as authenticated by this
implementation. Its legitimate content requires a future independently reviewed
real adapter and approval; it is not inferred from metadata here.

## API compatibility and fixed results

`reviewed_schedule_decision(evidence,target_date)` retains its signature, but
does not inspect, hash, stringify or act on either argument. It always returns:

```text
accepted = false
event = null
race_numbers = frozenset(1..12)
status = HOLD
kind = SCHEDULE_UNVERIFIED
reason = SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED
authentication_implemented = false
external_authenticity = UNVERIFIED
```

There is no result containing accepted=true or NO_RACE_VERIFIED. A malformed,
apparently complete, allegedly reviewed, malicious or genuinely correct input
cannot select a different code path. Source/receipt originals are not fetched
or inspected as part of this stub; no authentication is claimed.

`NoRaceVerified` remains importable for legacy compatibility only. Its instance
now carries SCHEDULE_UNVERIFIED / SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED, not a
verified absence. Generic `IndexFailure("NO_RACE_VERIFIED",...)` is quarantined
to the same unverified pair. The safe classifier also reclassifies mutated legacy
instances and handles malicious exception attributes without reflecting input
strings. Unknown exceptions remain UNKNOWN_FAILURE / UNCLASSIFIED_EXCEPTION.
The legacy class name must not be used as an authorization signal.

## Fetcher behavior

The constructor's `schedule_evidence_provider` argument remains accepted to
avoid breaking callers, but the provider is **never called**. This prevents its
claims, exceptions, async body or unreviewed I/O from changing the universe.
Both official HTML and tracking fetch paths always require races 1–12. They do
not invoke the legacy decision helper, so monkeypatching that helper to return
accepted=true cannot reopen the old admission path.

No provider claim skips HTTP, raises a certified-no-race event or permits an
eight-race source result. A short HTML index remains HTML_PARSE_FAILED, and a
short tracking index remains TRACKING_PARSE_FAILED. Complete12 data may still
be observed under its existing official/tracking gates. Tracking always remains
FALLBACK_TRACKING_ONLY with is_closed=false / is_cancelled=false. No parser
fixture API is promoted into an authenticated expected-universe source.

Transport/TLS verification, headers, timeout, retry/backoff, host alternation,
tracking date validation, models, state machine, requirements and Render config
are unchanged by S2. This code does not clear caches, mark terminal/cancelled,
modify a deadline or bypass a HOLD. Root owns the separate controller latch and
cache-preservation changes: a legacy or forged absence exception must be treated
as an unverified schedule observation, never unconditional cache removal.

HTTP200 with no rows, source/parsing failures and tracking stadium7 absence are
still not calendar evidence. Actual 11/5 root cause and actual official calendar
authentication are UNVERIFIED; this correction does not establish either.

## Precisely withdrawn old-test expectations

Only two v001 success expectations in `tests/test_health_official_index.py` are
revised for the S2 decision; their cases are retained, not deleted:

| V001 expectation | S2 regression |
|---|---|
| `test_only_reviewed_calendar_no_race_skips_http`: self-reported proof raises NoRaceVerified without fetching | `test_self_reported_calendar_does_not_skip_http_or_verify_absence`: HTTP remains attempted; complete12 returns12; decision remains unverified |
| `test_short_calendar_racing_day_is_explicit_independent_contract`: self-reported reviewed8 permits official/tracking8 | `test_self_reported_short_calendar_does_not_relax_expected_twelve`: both eight-race paths fail closed |

This is a documented safety correction, not an unexplained test relaxation.
All 41 old scoped cases, including those two retained/revised cases, execute.
The other old index, HTTP, tracking, date, deadline and safe-diagnostic cases are
unchanged. Historical v001 documentation describing claim-based admission is
superseded by this S2 restriction, not treated as current behavior.

`tests/test_health_v002_schedule.py` adds 17 synthetic cases: complete matching
claims, zero/arbitrary/equal raw-receipt hashes, no input inspection, sync/async
provider non-invocation, helper-monkeypatch isolation, legacy/forged-kind
quarantine and malicious classifier attributes. All fixtures are invented2099
data, not actual official proof or production validation.

Executed scoped result: **58 passed** on Python3.14.3 with HTTP mocked, no
network/install/real-DB use, `-B` and pytest cache disabled:

```sh
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -p no:cacheprovider tests/test_health_official_index.py tests/test_health_v002_schedule.py -q
```

No commit, push, merge, deploy, provider activation or Production GO is included.
