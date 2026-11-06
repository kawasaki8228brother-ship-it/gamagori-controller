# Stage17: wire C odds calls in the draft; diagnose initial A LOCK delay

Base: d0251b2f728c1ab9b1b8f8ce1a6f22ff3925929a, draft PR #2.
The running Render deployment was read as 057d024dd46797a77e8893ab30e4f4cbd58655bf.
Render follows main with autoDeploy=yes. This stage does NOT merge, deploy,
change environment variables, run a live collector or modify research records.

## Actual integration in the proposed runtime call path

OfficialDataFetcher.fetch_live_data now calls odds_bridge.parse_c_odds instead
of the legacy explicit-combination regex. The bridge calls the already-tested
strict parser with require_complete=True and preserves the tuple (odds,
SourceEvidence) contract. Partial, ambiguous or invalid odds remain errors,
with no fallback to the old parser. All120 raw odds values are retained without
P_market normalization or score changes. SourceEvidence gets a parser-version/
format/count label. The log hash explicitly describes decoded UTF8 text, NOT
raw HTTP entity bytes. It is not an independently signed source snapshot.

The beforeinfo path, result.is_complete expression, state_machine, LiveData model,
retry policy, clocks, storage adapters and model thresholds were not changed.
SourceEvidence OK is extraction status, not body-identity/freshness proof.
This is the first odds wiring into official.py in the draft, not a new unused
helper alone. It is not present in the running service until an approved release.

## Tests and recorded-page replay

All760 baseline tests retained;25 new integration cases pass locally (785 total).
The tests call the real fetch_live_data via HTTPX MockTransport, include parser
failure and half-pair HTTP failure, and prove a good odds response never masks
missing beforeinfo. One all-synthetic complete-input test reaches the shadow
state-machine event using a temporary SQLite and dummy baselines. That is not a
real-race prediction success. CI must be checked by its own exact commit/XML.

Recorded3R/12R odds each returned120 entries through the actual fetcher call
path and matched the earlier capture outputs for all240 combinations/values.
Each beforeinfo response used the same race's separately recorded body; no
12R-to-3R substitution. The legacy odds parser failed both original inputs.
The OLD beforeinfo parser remains on the path and extracted0 exhibition/entry
values from those same-race pages, so is_complete remains false. Therefore
ODDS-ONLY WIRING DOES NOT RESTORE C END-TO-END. Do not weaken is_complete to
turn these failures into success. Both replay transports are explicitly injected;
acquisition timestamps in the replay are not the historical source timestamps.

## Delay diagnosis:198/246 seconds are not late-race CLOSING_WINDOW samples

The 12 original A LOCK records were reread from Airtable using source=A and
LOCK filters. Source/type/producer/timestamps/acceptance groups were compared
with the frozen export, whose12 payload hashes were also recomputed.
All12 are EARLY_BASELINE_RESEARCH in the SAME producer run. Payload timestamps
span only0.00136s at13:23:23 JST. Current column values have millisecond resolution.

| A LOCK races | Shared ingested_at JST | Exact observed-to-ingested interval |
|---|---|---|
|1-4|13:24:52|88.958393-88.958776s|
|5-8|13:26:42|198.957932-198.958324s|
|9-12|13:27:30|246.957416-246.957806s|

The stored integer delay fields are88/198/246. Four-record acceptance groups
form a staircase, not12 independent time-of-day executions. Descriptive OLS
with race number gives R2~0.8514; acceptance-group indicators explain essentially
all variation by construction. Neither is causal evidence. Comparing record
number with its derived acceptance delay cannot isolate CPU, reasoning, queue,
network, API service time or rate limiting. No significance test is reported.
These198/246s values were NOT recorded at5R-12R's actual deadlines. The earlier
claim that these particular observations coincided with evening closing-window
work is contradicted by the stored timestamps. Batch handling is the immediate
investigation lead, but exact append/readback stages are missing. One source=A/
producer/OBS query returned0; that does not prove all other logs absent.

One initial name-based Airtable query returned400; an exact-field-ID query then
returned all12 records. No record was written, no false failure hidden.
This diagnosis covers initial A LOCKs, not B8 revision or Daily result delays.

## Scoped release/unfreeze plan (not executed)

1. Pin running commit/service/branch and preserved9/18 research evidence. Verify
   no active race processing at release time from actual sources, not a calendar
   assumption. Readiness of the next meet and this task's date are separate.
2. Extract a minimal release diff from main: official.py odds call, bridge,
   strict odds parser and dependencies/tests only. DO NOT merge the entire PR2
   archive/research implementation merely to deploy this small parser fix.
   Test on that exact main-based release tree, not just the larger draft suite.
3. Verify the running main entry's shadow-only DRY_RUN enforcement and actual
   settings, persistent SQLite state and backup/restore procedure. C_ACTIVE is
   not read by the inspected main entry and is not a substitute for that check.
   No backup, live-setting check or power-loss test was completed in this stage.
4. Obtain scoped release approval/unfreeze, then merge only the tested release
   tree. main autoDeploy means merge already starts deployment; do not trigger
   a duplicate deploy. Preserve full rollback commit, configuration and state
   backup references before doing so. No retrospective LOCK revision.
5. Verify deployed commit and startup/shadow status, parser-version log and
   post-release same-race smoke read. Record ODDS success separately from
   beforeinfo and C E2E. Roll back by an explicit reviewed revert/redeploy of the
   scoped change if imports/identity/coverage regress; code rollback alone does
   not revert database effects. Refreeze the accepted release.

These are requirements, not completed steps. Runtime snapshot freshness, real
withdrawal layout coverage and collection scheduling remain unproven. The old
beforeinfo float-ST model cannot silently discard F/L markers when wired later;
that separate adapter needs review. No new withdrawal rules were added. A scanner
candidate being implemented does not mean actual future evidence is already saved.
