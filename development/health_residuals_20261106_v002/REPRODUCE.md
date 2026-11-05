# Isolated reproduction

Only local, invented fixtures are accepted by these examples. Use an existing approved Python environment; no package installation, source fetch, production connection, app constructor/start command, credentials or real data are authorized. Create output paths outside the repository. Runners use `-B`, disable network in-process and avoid pytest caches.

The measured interpreter/package/OS details are retained in each log. Full regression uses Python 3.14.3 with the pre-existing offline dependencies; it does not establish host/runtime equivalence or validate the old requirements for deployment.

## Full candidate and preserved parent

From the v002 repository, using an already populated environment:

```sh
python -B development/health_residuals_20261105_v001/run_offline_tests.py --repo . --junit-output /tmp/health-v002-new.xml
python -B development/health_residuals_20261105_v001/run_offline_tests.py --repo /tmp/health-v001-byte-verified --junit-output /tmp/health-v001-new.xml
```

The second path must be a separate byte-verified copy of parent `845cc1c9c6667699a21933cb4b9d7c324c79ce44`; do not overwrite an existing worktree. Parent inventory is PARENT_FILES.json. That version's 353 collected tests and 14 subtests are separate counts. A revised expectation is documented in TEST_EXPECTATIONS.patch, never concealed as an unchanged regression.

The preserved v001 runner is a generic offline harness. Its older reproduction scripts and manifests describe the historical v001 snapshot; do not run its source-snapshot verifier against changed v002 files or interpret its reports as new measurements.

## S1 three-version comparison

```sh
python -B development/health_residuals_20261106_v002/compare_parser.py --repo /tmp/health-old-main-byte-verified --label OLD_MAIN
python -B development/health_residuals_20261106_v002/compare_parser.py --repo /tmp/health-v001-byte-verified --label V001
python -B development/health_residuals_20261106_v002/compare_parser.py --repo . --label V002
```

OLD_MAIN is `8172aec010894a52f36f48b7091476d26494e4ee`. These commands do not download it. Each command must run in a separate process to isolate module imports. The fixture module is always the v002 local file; source identity remains UNVERIFIED_DESCRIPTION_ONLY_NOT_ORIGINAL_HTML.

For V002, the normal12 + 7 description fixtures must match all expected deadlines including seconds; all DANGER cases must reject. The old version accepting input is recorded separately from correct expected output.

## S2 self-claim and legacy signal comparison

```sh
python -B development/health_residuals_20261106_v002/compare_no_race.py --repo /tmp/health-v001-byte-verified --label V001
python -B development/health_residuals_20261106_v002/compare_no_race.py --repo . --label V002
```

The V002 result must have claim_accepted=false, expected race count12, provider_calls0. Both injected legacy signals must retain12 current-day cache entries, set HOLD, and avoid new fetches after the first refresh. This runner uses Controller.__new__, fake dependencies and `_refresh` only; it never starts actual state processing or opens a DB.

Controller start-loop, STOP during fetch, sticky HOLD, tracking11/12/missing time, old-day scope and fake-writer assertions are covered separately by the regression tests. The real StateMachine remains byte-unchanged and its original tests are retained. Process-local HOLD is not durable across new processes; restart/recovery remains OPEN and requires later independent approval.

## Artifact verification

```sh
python -B development/health_residuals_20261106_v002/verify_artifacts.py
```

This reads files only and proves local bytes/hash/diff consistency, not external authenticity or live safety. MANIFEST.json and SHA256SUMS.txt exclude themselves; their own hashes appear in the final commit-fixed handoff receipt. All archived source/test originals must match parent inventory. Public logs are either RAW_UNMODIFIED or explicitly REDACTED with a different hash; never confuse them.
