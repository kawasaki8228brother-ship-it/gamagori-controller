# HTML research and private capture preparation

Scope: new offline modules only. Active parsers.py, StateMachine, LOCK, requirements, Render settings and live source acquisition are unchanged. Research results always have go=false, runtime_execution_allowed=false, official_compatibility=UNVERIFIED and POLICY_PENDING_REAL_HTML.

The research normalizer supports a narrow, explicit set of synthetic constructions: omitted td/th/tr closing tags terminated by later structural tokens, one semantically anchored table inside a layout table, identical PC/mobile semantic tables, unrelated header colspan expansion, identical repeated headers and the research alias レースNo. It never invents an EOF table closure. It does not declare omitted closing tags invalid HTML.

The module selects direct rows of each table, does not count nested rows twice, preserves hidden duplicate data for rejection, and compares both semantic records and the complete checked header/cell profile before treating duplicate representations as equivalent. Different race/deadline/status/content profiles, conflicting headers, unsupported semantic spans, orphan race/time rows, missing races and ambiguous clocks HOLD. A timed annotation remains HOLD. No real official source has been used to adopt any format.

Sanitized research markup is passed through the existing v003 parser, retaining its exact-cell state-word rule. Names and annotations do not become CANCELLED. A research-only explicit cancellation observation still cannot drive a terminal action: no StateMachine is called or imported here, and no runtime consumer is integrated.

Private checker:
    python -B development/health_offline_completion_v004/inspect_private_html.py --private-html LOCAL_APPROVED_PRIVATE_FILE.html --date YYYYMMDD --encoding utf-8

The command performs one bounded regular-file read, refuses non-HTML extensions and symlinks where O_NOFOLLOW is supported, checks input stability, computes raw bytes/SHA, verifies both public parser reference hashes, and prints only status/count/digest/difference summaries. It never outputs source body, URL, headers, local path, race IDs or deadline values. Invalid CLI arguments also use a fixed JSON error instead of argparse value echo; invalid calendar dates and non-byte API input remain UNVERIFIED. No output file or network connection is created. Default no input means BLOCKED_EXTERNAL. Exit0 means local comparison executed; it is not official compatibility PASS. A future real-input use requires the separately approved private capture and review. The supplied date is only the requested comparison day; page date/venue and capture timing are not certified. Current Linux file-opening behavior is tested; other-OS atomic no-follow semantics remain external review work.

An 8MiB tool memory limit is an operational read bound, not a race-data quality threshold. Oversize input is not partially hashed or interpreted as valid. Encoding is explicit and strict; unknown decoding is UNVERIFIED. Capture time, HTTP framing/source authenticity and independent original linkage remain external evidence requirements.

## Claims for the case REVIEW_GUIDE

| Claim | Command/check | Expected | Evidence |
| --- | --- | --- | --- |
| Narrow optional ends can be analyzed without promoting to live | target test test_normal_and_legal_optional_end_candidates | same twelve records; research-only flags | tests/test_offline_html_research.py |
| Truncated/ambiguous/conflicting inputs do not become success | test_no_eof_repair_or_twelve_row_table_authentication and conflict tests | HOLD, no records or action permission | target test log |
| Duplicate/layout/colspan/repeated-header candidates remain pending | target synthetic tests | research observations only, go=false | module/test source and log |
| Race-name 中止 cannot authorize cancellation | test_names_never_cancel_and_explicit_state_stays_unapproved | no name-derived cancel; no runtime action | target log |
| Private checker does not disclose body/URL/path | test_private_summary_has_no_body_url_path_race_ids_or_times | marker and sensitive source strings absent | target log |
| Private input has not been obtained | run checker without --private-html | BLOCKED_EXTERNAL, exit3 | CLI no-input record |

Reproduction uses only existing Python3.12/3.14 environments, synthetic temporary HTML files and socket blocking. No real capture or Drive operation is performed.

State classification: IMPLEMENTED for the two tools and procedure; TESTED only for executed synthetic cases. BLOCKED_EXTERNAL for actual iPhone behavior, original raw-byte preservation, private Drive upload/readback, source/time/transport evidence and real official HTML policy review. If a synthetic defect remains after two content revisions of a file, FAILED_OPEN/STOP is required; do not rename files to evade the limit.

The shortest external path is operator approval/private capture → private artifact readback and SHA → Claude review of source mapping and parser difference summary. These are preparation artifacts, not approval to access production, introduce a source collector, modify A/B, merge or deploy.

## Executed evidence and revision limit

- Python3.14.3 / OpenSSL3.5.5 / Linux: 16 tests passed, 8 subtests passed, 0 failures (html314-final.raw.log).
- Python3.12.14 / OpenSSL3.5.8 / Linux: 16 tests passed, 8 subtests passed, 0 failures (html312-final.raw.log).
- The first 13-test run also passed. It did not cover invalid CLI arguments; do not claim the earlier run proved that privacy property.
- Review identified argparse's default invalid-value echo. Revision2 replaced it with a fixed JSON reason and added argument/date/type/size negatives. Synthetic before/after proof uses a reconstructed revision1 whose bytes were checked against the guard-recorded prior SHA, explicitly not an original disk archive. The marker was echoed before and was absent after. No actual secret was used.
- Private checker and its test file have reached revision2 and are FROZEN. Research module remains revision1. Any new content change to a revision2 file must STOP rather than rename or silently rewrite.
- The normalizer, iPhone procedure and safe-summary tests are IMPLEMENTED and TESTED only within the stated synthetic/local scope. Actual source capture, byte preservation by iPhone, Drive readback, page/time/venue authenticity and official policy adoption are BLOCKED_EXTERNAL.

Evidence locations under the case private directory: html314-final.raw.log, html312-final.raw.log, private-html-not-supplied.raw.log, private-html-privacy-before-after.json. Parent publication must preserve original hashes or mark redaction separately. The before/after source artifact is tagged BYTE_MATCHED_RECONSTRUCTION, not original disk preservation.
