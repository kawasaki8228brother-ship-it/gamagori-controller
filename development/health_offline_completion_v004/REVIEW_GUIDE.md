# P0 Health offline completion — Claude review guide

Status: offline candidate, independent Claude review pending. Nothing in this guide grants production access, a port, Shadow start, merge or deployment. Real official HTML, real transport/source evidence and the formal 208-byte specification remain external requirements.

Use an approved local Python 3.12.14 or 3.14.3 environment. Do not install packages or run the application constructor. Keep -B, disabled pytest plugin autoload, the explicit asyncio plugin and no cache. Run the commands only on synthetic/local artifacts; pause this work if it competes with certifi or SYS-01/02. No GitHub push is allowed during 2026-11-06 05:00–06:30 JST.

Common targeted-test command prefix:
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -q --tb=short

## Ten claims to independently verify

| # | Claim | Local command or test suffix | Expected result | Evidence file(s) |
| --- | --- | --- | --- | --- |
| 1 | All executed P0 regressions pass on both prepared interpreters, with the formal spec explicitly unverified | python -B development/health_residuals_20261106_v003/run_offline_tests.py --repo . --junit-output /tmp/health-offline-review-new.xml ; repeat with the other prepared interpreter and a different new output path | Actual parent-run result per environment: 593 passed, 1 skipped (formal208B original), 35 subtests passed. Skip is not PASS; counts are separate | Parent full-suite raw logs linked by INDEX/manifest; existing runner and tests/test_health_v003_spec_reference.py |
| 2 | Encoded wire bytes and decoded bytes are separately observed | tests/test_offline_transport.py -k 'encoded_and_decoded or prebuffered or empty_stream' | Gzip and identity retain exact independent counts. Prebuffered unobserved wire count remains null/UNVERIFIED; no decoded-to-wire inference | http_transport_observation.py; tests/test_offline_transport.py; TRANSPORT_DESIGN.md; final transport raw logs |
| 3 | HTTP status, body completion, document marker and HTML parse result are independent | tests/test_offline_transport.py -k 'http_status or complete_transfer or successful_parse or marker' | 403/404/500 do not become parser success. A missing HTML end marker is not itself proof of failed transport or parsing. Mocked transport does not fabricate measurements | Same test file; official.py diagnostic hooks; TRANSPORT_DESIGN.md |
| 4 | Partial, inconsistent, cancelled and unknown-decoding responses do not masquerade as a complete valid source | tests/test_offline_transport.py -k 'partial or mismatch or cancelled or invalid_gzip or duplicate_content_length or unknown_charset or timeout' | Safe fixed classification, no parser after known length mismatch, null unknown data, response/token cleanup; existing retry behavior retained | tests/test_offline_transport.py; http_transport_observation.py; official.py source diff |
| 5 | New diagnostic messages do not echo the supplied synthetic secrets | tests/test_offline_transport.py -k 'safe_logs or namespace or contexts' | No body, credential-bearing URL, header value, proxy value or arbitrary exception string in the new diagnostic namespace. Concurrent requests cannot attach another response to the raceindex parse | tests/test_offline_transport.py; TRANSPORT_DESIGN.md privacy boundary |
| 6 | Unsupported HTML formats can be studied without activating them | tests/test_offline_html_research.py -k 'optional_end or nested_layout or pc_mobile or colspan or repeated_header' | Only narrow, unambiguous synthetic normalization. Every successful research result still has go=false, runtime_execution_allowed=false, official compatibility UNVERIFIED and POLICY_PENDING_REAL_HTML | html_research.py; tests/test_offline_html_research.py; HTML_RESEARCH.md historical-stage account |
| 7 | Two orphan-row bugs were measured before the single allowed source correction and are now rejected | python -B development/health_offline_completion_v004/orphan_reproduction.py --stage before ; then repeat with --stage after | Pinned revision1: normal and both conflict cases RESEARCH_PARSED. Pinned revision2: normal remains research-parsed; outside-table tr and layout-parent own race/time conflict both HOLD with no accepted records. All have go=false | orphan_reproduction.py; references/html_research_rev1.py.txt; html_research.py; parent before/after raw logs |
| 8 | A race name cannot authorize irreversible cancellation; exact-cell policy does not change StateMachine rules | tests/test_offline_html_research.py -k 'names_never_cancel or ambiguous' ; separately tests/test_health_v003_event_equivalence.py | Research name containing 中止 is not cancellation. Existing E5 a/b/e match ordered C-event kind/time/semantic fields; c has no automatic terminal; d records the intentional removal of old false cancellation | tests/test_offline_html_research.py; tests/test_health_v003_event_equivalence.py; pinned8172 references in the v003 directory |
| 9 | Private-file inspection prints a summary only and refuses unsafe argument/file conditions | tests/test_offline_html_research.py -k 'PrivateCheckerTests' ; python -B development/health_offline_completion_v004/inspect_private_html.py | Synthetic body/URL/path/race IDs/time are absent from output. Bad arguments use a fixed JSON reason. No-input invocation returns BLOCKED_EXTERNAL and exit3, not a compatibility PASS or a capture claim | inspect_private_html.py; tests/test_offline_html_research.py; private-html privacy before/after proof published by parent if included |
| 10 | Source preservation, artifact identity and deferred trial-merge claims remain separate | sha256sum -c development/health_offline_completion_v004/SHA256SUMS.txt ; review PORT_SCOPE/diff and the final coordination receipt | All listed artifact hashes agree. Active parsers.py, StateMachine, LOCK, requirements and Render/CI settings are unchanged. Exact-final-candidate trial merge onto97640c8c is assessed only from the later coordination-only evidence, not inferred here | Parent manifest/SHA/diff/INDEX; TRANSPORT_DESIGN.md; final handoff coordination proof |

Commands in table rows2–9 that begin with a test path are suffixes to the common targeted-test prefix. Use separate fresh scratch outputs; do not overwrite an earlier receipt or run a live request to complete these checks. The final INDEX and manifest record the actual retained log filenames.

## Current-source addendum: supersedes the earlier revision-count sentence

HTML_RESEARCH.md was frozen before the independent orphan-row finding. Its sentence that the research module remains revision1 is a historical-stage statement, not the current source count. The current html_research.py is revision2, 12,145 bytes, SHA-256:
dc84153b86811cad8666ee734615c96690b298f112ca99f7f2cbc11f120bec88

The preserved revision1 is 11,380 bytes, SHA-256:
7863bea4c520cba48bedb719c7f9c635c98dc9b664a73d5be82cc1f6e4ef45c0

The source2 correction inspects own text in direct cells of unanchored/outside rows while excluding descendants belonging to nested tables. It does not discard an entire layout row merely because one cell contains a nested table. The previously valid simple layout construction remains a research candidate.

After that correction, the existing HTML scoped suite passed on both interpreters: 16 tests and 8 subtests. The two new orphan outcomes are checked by the separate pinned before/after reproduction; the already revision2 test file was not edited a third time. CLI, test and both earlier HTML documents also remain at revision2 and are frozen. A third required content change is STOP, not permission to rename files or silently rewrite a frozen artifact.

The private-checker invalid-argument privacy hardening has separate evidence. Its before source was reconstructed and byte-matched to the guard's prior SHA; it is not described as an original disk archive. The initial13-test success did not cover argument reflection. The final16-test suite does. No real secret was supplied.

## Limits that must stay visible

- New logging privacy is scoped to the newly added diagnostics. Existing HTTPX Request INFO logging and unrelated application logs were not globally rewritten or certified secret-free.
- Semantic event comparison excludes only the physical SQLite created_at metadata field, because separate local writes can cross wall-clock seconds. Observed event times, UUIDs, idempotency keys, raw payload/hash and deadline version remain compared.
- Formal A/B LOCK writer/events are not in this repository. They remain UNVERIFIED; CLOSING_OBSERVATION must not be relabeled as formal LOCK.
- A normalized HTML result does not prove legal official structure, page date/venue, transport integrity, source authenticity or that the saved artifact is original network bytes.
- Real private capture is not performed. iPhone Shortcuts behavior, private Drive byte preservation/readback, actual HTML/source policy and current Render compatibility remain BLOCKED_EXTERNAL.
- Formal208B spec is not supplied; the remaining skip cannot be cleared by a different208B string or a hash assertion copied from a report.
- F3 exact final-commit local merge onto97640c8c is not executed or passed by this guide. Root's coordination-only branch/final handoff will supply that separate proof and its test counts. An initial/preliminary merge is not an exact-final-candidate result.
- Review is after the certifi work window and actual work completion; a clock time alone does not imply certifi success/CLOSE. No automatic integration, promotion, source access or deploy follows a green local test run.

## External block owners and shortest paths

| Block | Owner / needed evidence | Minimum safe steps |
| --- | --- | --- |
| Official HTML/source/capture identity | Andy/HQ14: separately approved operator and private destination; raw saved artifact, SHA/time/readback evidence | 1 approve private capture; 2 operator captures/readbacks; 3 Claude compares safe summary and source mapping |
| iPhone file/Drive behavior | Approved operator: device-specific nonpublic readback evidence, no account/secret screenshots | 1 test approved workflow privately; 2 retain bytes/SHA receipt; 3 independent comparison |
| Current production/runtime and operational application | HQ14/Andy: separately authorized metadata; Claude review plus individual GO | 1 capture approved read-only evidence after priority work; 2 compare candidate/runtime; 3 decide a distinct port/application request |
| Formal208B specification | HQ14/Claude: approved private original and independent digest link | 1 supply privately; 2 recalculate bytes/SHA; 3 review whether the UNVERIFIED skip can be removed |
| Final trial merge / actual adoption | Root prepares local proof; HQ14/Claude/Andy assess it | 1 inspect exact final coordination evidence; 2 independently review; 3 separate explicit adoption GO |
