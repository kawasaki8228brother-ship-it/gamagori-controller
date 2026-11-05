# Third-party review disposition: documents only

Namespace `F5_PREREGISTRATION_V007`. The relayed Chrome suggestions are not Andy's GO; original bytes/SHA are absent. M0/M2/M1 policy stays unchanged, eight choices OPEN, F2 unadopted, operational GO absent. The earlier two source/review documents remain byte unchanged.

| Suggestion | Disposition in this scope |
| --- | --- |
| Implement clock checks and a safety buffer | Retain as design/review input; no implementation or numeric buffer adopted |
| ABORT when odds unavailable | Existing third-research Shadow already HOLDs incomplete/unavailable market input; preserve that behavior, no new terminal enum or betting decision |
| Per-race tail/outlier summaries | PROPOSED secondary diagnostics in HQ14's private analysis; no alteration of primary estimand or data |
| Anonymous error export | PROPOSED minimal allowlist summary, not arbitrary-log masking or guaranteed anonymity; no exporter or actual sharing |

## Clock: separate three sources of evidence

The [v006 runtime design](../shadow_preparation_v006/INDEPENDENT_RUNTIME_DESIGN.md) separates wall time, within-origin monotonic elapsed time and external UTC/sync evidence. The separate `148c...` offline-refinements v007 monotonic design is not integrated. v005 has no paired monotonic forecast chain.

Future paired wall/counter samples need boot/process context and independently reviewed sync evidence. Counters cannot replace UTC/deadline evidence, compare unrelated reboot origins, authenticate timestamps or justify backdating. Steps, pauses, suspend/reboot and PID reuse differ. No grace period, buffer, drift tolerance, LOCK gate or host probe is adopted/run. Actual clock/host review stays OPEN; completion/readback deadlines remain unchanged.

## Odds: verified code scope, not a new policy adoption

Read-only proof points in the unchanged parent:

- `model11/shadow_launch/sources.py`: odds-related RAW warnings return `SOURCE_COMPLETE_MARKET_REQUIRED`/HOLD. `tests/test_shadow_launch_sources.py::test_complete_market_missing_stale_future_or_partial_hold` covers missing, stale, future, partial and unknown-unit snapshots.
- `model11/shadow_launch/runner.py::run_race`: propagates converter HOLD before forecasting. `candidate.py` separately requires admitted market probabilities on the private Shadow path. `test_missing_input_near_deadline_holds_without_imputation` checks HOLD/noncommit near deadline for missing exhibition input; it is not itself an odds-specific test.

These synthetic observations do not verify an actual collector. Older model-only fallback APIs do not permit missing odds in this Shadow. No final-odds substitution, fabrication or retrospective prediction is allowed. ABORT is reviewer wording, not a new enum or change to HOLD/BET/SKIP. Fallback, maximum age, retry and no-odds statistical-cohort rules stay OPEN. There is no live HTTP collector, Teleboat, purchase or production connection.

## Tail diagnostics preserve the decided primary analysis

M0's paired racing-day-equal joint120 log-loss comparison is DECIDED. `sd_day` describes variation in the declared day-level differences; it is not display rounding or a device for discarding extreme races. Keep calculation precision distinct from presentation rounding.

PROPOSED secondary private diagnostics: per-race loss-difference maxima, quantiles and tail bins. Levels, edges and disclosure/minimum-cell rules stay OPEN. No outlier deletion, winsorization, loss caps, day-weight/primary-metric changes or filtered-win claim without a new reviewed plan. Holdout outcomes must not choose these rules.

Full race-level inspection stays with HQ14 privately. Any proposed external statistical summary is aggregate-only, without race IDs, dates or score rows, and requires manual disclosure review. The separate SAFE_DIAGNOSTIC_SUMMARY proposal below permits counts only; it does not silently permit score distributions or tail tables.

## Diagnostic sharing is a proposal, not anonymization

[SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json](SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json) defines an illustrative exact allowlist: fixed kind, stage/error enums, a syntactically safe code commit and typed counts. If implemented, unknown fields/enums, unsafe values and inconsistent counts must reject export. Pattern checking is limited to commit syntax, not a claim that regex masking removes secrets.

Never include arbitrary exception text/tracebacks/locals, URL/query/header/proxy/environment values, internal paths/host identities, raw race data, predictions/scores, PII, tokens or approval originals. Keep raw logs private; a summary is a distinct derivative, not a redacted-original receipt. Counts and code versions can still be linkable, so there is no complete-anonymity guarantee. HQ14 must manually review before any external sharing and may instead supply a minimal wholly synthetic reproduction. No actual exporter, host/log examination, external upload or privacy test occurred. Code READY is not source authenticity, real-data PASS, formal Claude review, launch GO or CLOSE.
