# C4 transport observation candidate — offline implementation

IMPLEMENTED + TESTED within the synthetic HTTPX scope. Claude independent review,
real-source behavior, current production compatibility and application GO are
separate. No official HTML or production service was accessed.

## What changed

`official.py` preserves `_get_text(url) -> (text, acquired_at)`, existing client.get,
timeouts, headers, total retry count, host alternation, backoff, concurrency and
HTTPX defaults for TLS/proxy environment behavior. A response hook captures only
safe scalar metadata. A local request extension token links each response to its
observation; that token is not an HTTP header and is not logged.

`http_transport_observation.py` stores status, encoded-body byte count, decoded
body byte count, declared Content-Length, safe encoding categories, body-read
completion, transport integrity, an ASCII HTML end-marker observation and a
separate parse result. It never records URL, request/response headers, response
body, proxy values or exception text. HTTP status403 is recorded numerically;
HTML parsing is not attempted after status failure.

HTTPX's wire counter is used only when a response hook observed the stream before
it was consumed. A prebuffered response cannot demonstrate transferred bytes:
wire_bytes and transport_complete remain null/UNVERIFIED. Gzip tests confirm that
encoded and decoded byte counts differ. No count is inferred from another count.

Counters cover the final returned response's entity body, excluding headers,
TLS and earlier redirect bodies. If get never returns a completed response, the
record is LAST_OBSERVED_RESPONSE_NOT_CONFIRMED_FINAL instead. It must not be used
as evidence that the final target returned that status. A failed proxy connection
with no response has http_status=null.

Content-Length is accepted only as one nonnegative integer. Duplicate, malformed
or unavailable declarations are UNVERIFIED; values are never echoed. A known
wire-length mismatch is a fixed HTTP protocol failure, follows existing retries
and cannot enter the parser. Successful read/length agreement is not original
document completeness, official authenticity, correct schedule or valid LOCK.

HTML parse status is recorded only by fetch_race_index. Its per-task ContextVar
prevents simultaneous beforeinfo/odds or other requests from attaching a different
response to the raceindex parse. If _get_text is replaced with an offline mock,
the transport field remains null rather than fabricating a status/counter.

An ASCII closing-html marker is an observation only. Legal HTML can omit it, and
a truncated document can contain misleading markers. Parsing success and marker
presence never authenticate transport/source completeness. HTTPX decoding is not
an independently verified compression checksum or source-charset assertion.
Unknown declared charset is recorded by a fixed UNSUPPORTED enum; HTTPX's prior
text fallback behavior is preserved, with no raw charset/header output.

Cancellation produces a fixed CANCELLED observation and re-raises CancelledError
without retry. The token registry and any response reference are released in all
paths, including partial bodies. The original StateMachine, closing rules,
parsers and Model/BOX/A/B logic are unchanged.

## Privacy boundary

The new gamagori-controller diagnostic messages contain fixed enums, numeric
counts and booleans only. Successful requests with synthetic credential-bearing
URLs and sensitive-looking headers/bodies do not echo those values in this
diagnostic namespace. Existing HTTPX Request INFO logging and other application
logging policies are a separate scope and were not globally rewritten. This
candidate does not claim that every logger in the application can never print a
URL or secret. No real credentials were used to run the tests.

## Executed tests

Both prepared local environments ran the same scoped command:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -q --tb=short tests/test_offline_transport.py tests/test_health_official_index.py tests/test_v11_official_header.py tests/test_c_beforeinfo_fetcher.py tests/test_v11_candidate.py
```

Result: **128 passed** per environment =23 new transport cases plus105 preserved
compatibility cases. No skip in this scoped run. Python3.14.3/OpenSSL3.5.5 and
Python3.12.14/OpenSSL3.5.8, HTTPX0.28.1, pytest9.0.2, Linux. The3.12 environment is
the existing private diagnostic setup using read-only system-site dependencies;
this is not a claim of a clean production-equivalent install. No new dependency
was installed. No real network request was made; HTTPX MockTransport supplies all
responses. Parent full regressions and certifi-head trial merge are distinct
checks and are not implied by this scoped result.

Private retained logs: transport-initial314.raw.log (16 passed),
transport-compat-initial314.raw.log (105 passed), transport-final314.raw.log and
transport-final312.raw.log (128 each). The final environment metadata is retained
separately as transport-environment314.json and transport-environment312.json.
The parent evidence manifest records exact bytes/SHA for published copies.

Revision guard receipts record **2 content revisions each** for official.py,
http_transport_observation.py and tests/test_offline_transport.py. These are now
frozen. A third required source/test revision is STOP, not permission to rename a
file or bypass the guard. The second revision combined planned cancellation,
unknown-charset, invalid-gzip, duplicate-length and privacy boundary cases; the
initial round had no failing tests.

## Review-guide inputs

| Claim to independently check | Command/test | Expected | Evidence |
| --- | --- | --- | --- |
| Wire and decoded bytes are distinct and observed | `tests/test_offline_transport.py -k encoded_and_decoded` | identity/gzip exact counts, no decoded-to-wire inference | final scoped logs; helper/official source diff |
| HTTP status, completed read, marker and parse are separate | `-k 'http_status or marker or complete_transfer'` |403/404/500 never parser success; marker false can coexist with successful parse | same raw logs and parser diagnostic asserts |
| Partial, cancel and mismatched bodies cannot masquerade as complete | `-k 'partial or cancelled or mismatch'` | fixed safe failure, no parser on mismatch, tokens/response references cleared | same raw logs; revision2 source |
| New diagnostics do not echo secrets and keep API compatibility | `-k 'safe_logs or namespace or retry_api or contexts'` | no secret in own namespace, 2 get retries, parse paired with same task | final scoped logs plus preserved105-case run |

All commands in this table are suffixes to the prepared interpreter's offline
pytest invocation above. They are review instructions, not production Shell GO.

## Remaining external blocks

| Item | State | Owner/evidence | Shortest safe resolution |
| --- | --- | --- | --- |
| Actual official response/corpus behavior | BLOCKED_EXTERNAL | Andy/HQ14 private capture + SHA/time/transport metadata |1 approved private capture;2 Claude compares summary;3 individually approve any mapping/port |
| Current Render runtime and real HTTP behavior | BLOCKED_EXTERNAL | Andy/HQ14 approved read-only observation |1 separately authorized metadata capture;2 compare pinned candidate/runtime/tests |
| Application/port | BLOCKED_EXTERNAL | Claude review, HQ14 alignment, Andy individual GO |1 independent review after certifi work;2 explicit port/deploy authorization outside this task |

No current FAILED_OPEN defect is known in this assigned scoped implementation.
This statement does not upgrade external blocks or the rest of the P0 package.
