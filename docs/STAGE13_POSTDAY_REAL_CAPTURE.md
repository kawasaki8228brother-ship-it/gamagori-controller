# Stage13: one actual post-day capture, not routine production collection

Base 3fe8a32f22f6e2d06fabb745c389b07c07336f51. Tested code 57047fb50638469e58475de577ee0faf13277076.
Draft PR #2 only. The existing stage12 collector was reused unchanged; three
new executable/test/workflow files and this note were added. No predictor,
readiness, old results/locks, production DB, Render or task changes.

## Actual trial (not MockTransport)

One isolated GitHub Actions trial executed the fixed target date 2026-09-18,
racelist/beforeinfo for all twelve races. It used normal HTTPX network access,
not an injected transport. All24 planned GETs returned200 with complete bodies;
24 bodies/END receipts were saved and independently read back. START24/END24,
24 unique bodies. After downloading the artifact, separate raw SQL verification
recomputed all48 receipt canonical hashes and all24 body hashes and checked
plan keys, target context, time order and SQLite integrity/foreign keys.

Run35382722645; artifact10562448322. Artifact ZIP SHA256:
48aa0aeb2db095fdfe6ebabf258259c12b0a21d99deb168b8df2611fec47dd03
This was recomputed from downloaded bytes and matches GitHub metadata.
SQLite SHA256: faa8cdb563d3840efc13f35fdcbebde36dc65ef242f5b366f4be0c45144d74b9.
Bodies total1,433,036 bytes; DB1,552,384 bytes. The reported capture plus replay
ran from2026-09-18T18:53:01.485858Z to18:53:09.359679Z (next day JST),7.873821s.
This single observation is not a percentile, latency promise, resource-impact
measurement or evidence that a similar predeadline load will be safe.

Local and CI590 tests pass;573 baseline IDs retained and17 added, no failure,
error or skip. Test identity sets match. Supplied40 baseline source files are
byte-identical. Each new uploaded source blob matches the tested local bytes.

## Replay scope

The24 real bodies were replayed locally and match CI outputs. Racelist12/12
produced six listed registrations/names. Beforeinfo12/12 produced six
exhibition times, courses and recognized/numeric ST readings. Markers remain
separate; this does not establish what was published before the races.
One-off body checks matched role, venue, selected date and menu race context
for24/24. Those offline assertions are not installed as live validators.
The withdrawal scanner found zero supported target-field signals. This is not
proof of no withdrawal; genuine withdrawal-positive fixtures still number0.
Returning readable data is not ACTIVE, fresh-data or readiness acceptance.

## Timing/resources/retention limits

The script refuses execution on/before the fixed target date in JST. That is
an elapsed-date guard, NOT a general official-results completion detector. No
clock time for routine collection has been selected. There is no cron, recurring
automation, live fetcher import or production store.

New workflow is restricted to PR2 and the candidate branch; only run_number1
and run_attempt1 execute the job. Later PR events and reruns do not implicitly
repeat this24-target network trial. A deliberate workflow change could alter
that guard; it is operational control, not a permission boundary.

Each request has one attempt, no redirect,1,000,000-byte saved-body cap and12s
per-operation timeout. A shell timeout bounds this trial process to420s (with
10s kill grace), job limit10min; killed attempts remain visible in the DB and
artifacts are uploaded on failure. No performance/freshness threshold is learned.

Artifact retention14days is review-artifact configuration only, not the chosen
production retention policy. The downloaded evidence is included in the handoff
bundle. Main/Render are untouched; GitHub-hosted collection is not inserted into
prediction-critical work. This is not a measured guarantee of zero shared-network
or official-site load impact.

## Clarification for external review

Independent-connection readback checks committed visibility/content integrity,
not by itself disk-flush correctness or power-loss survival. The unchanged
stage12 DB uses synchronous FULL and DELETE journaling. No power-cut experiment
or durability upgrade was performed. SQLite's own isolation/PRAGMA documents
distinguish these issues; do not call this a production durability certificate.

The claimed relative frequency/timing of withdrawals and their immediate
reflection in official pages have not been measured by this project. Postday
collection is selected as a bounded experiment, not as a proven detection-rate
optimum. Results/notices still require semantic validation before categorizing
withdrawals; absent rows or F/L alone are not automatic withdrawal labels.

## Next boundary

A recurring postrace collector needs a reviewed completion trigger, persisted
state, request budget, production storage and retention plus results/notices
matching. No such deployment is enabled here. Predeadline capture, true
withdrawal layouts, old-API restrictions, PR1 integration, marker-aware scoring,
Final F and end-to-end production acceptance remain outstanding.
