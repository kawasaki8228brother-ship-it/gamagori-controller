# Offline reproduction and limits

Use a new isolated checkout and an already prepared, approved local environment. No command below downloads real HTML, accesses a service, installs packages, changes production or starts the app constructor. Do not run `python main.py`. All temporary/output directories must be new local scratch paths, never `/var/data`.

## Runtime and full suite

Prepare Python 3.12 and 3.14 environments with the unchanged five direct requirements and the selected dependency versions in RUNTIME_MATRIX.md. This work used 3.12.14 and 3.14.3. The 3.12 diagnostic environment reads existing system-site native dependencies and therefore is not a hermetic clean install. Existing environments remained unchanged. Runtime version/site metadata is evidence of the test environment, not current Render.

```sh
python -B development/health_residuals_20261106_v003/inspect_runtime.py
python -B development/health_residuals_20261106_v003/run_offline_tests.py --repo . --junit-output /tmp/health-v003-new.xml
```

Run once with each prepared interpreter. The runner disables network, pytest plugin autoload and pytest cache, explicitly loads the asyncio plugin and records environment/counts. Expected measured result per interpreter: **549 passed, 1 UNVERIFIED skipped, 27 subtests passed**; 550 primary collected, JUnit records577. These are separate counts. The formal208-byte specification test is not a PASS.

To repeat parent regression, use `--repo` with a separate byte-verified local copy of `48333a2315628ae17e1fa3ce4f8ef12c70e2662f`. Do not overwrite an existing branch or worktree. Parent measured result is418 passed/18 subtests for both interpreters. PARENT_FILES.json inventories all123 parent files.

## Four parser versions

```sh
python -B development/health_residuals_20261106_v003/compare_parser.py --repo /tmp/health-8172-byte-verified --label OLD_MAIN
python -B development/health_residuals_20261106_v003/compare_parser.py --repo /tmp/health-v001-byte-verified --label V001
python -B development/health_residuals_20261106_v003/compare_parser.py --repo /tmp/health-v002-byte-verified --label V002
python -B development/health_residuals_20261106_v003/compare_parser.py --repo . --label V003
```

Each command must be a fresh process to isolate imports. OLD_MAIN is8172aec010894a52f36f48b7091476d26494e4ee; V001 is845cc1c9c6667699a21933cb4b9d7c324c79ce44; V002 is the parent above. This runner does not obtain those versions from the network. The67 fixtures combine R/state-policy29, P14, staticE5 five, preservedS1 nineteen. V003 must match all67 current synthetic expectations. Older acceptance/rejection and flags are recorded, not judged as official truth.

Fixture bytes and hashes are generated in FIXTURE_INVENTORY.json. They are Codex reconstructions, not independently matched Claude originals. P fixtures use the forwarded generator; observations forwarded by Claude are separate from these executed logs. POLICY_PENDING_REAL_HTML results are rejected, never silently accepted for convenience.

## Five actual C-event scenarios

```sh
python -B development/health_residuals_20261106_v003/run_event_comparison.py --work-dir /tmp/health-v003-events-new
```

This creates synthetic SQLite files only in that new directory and loads SHA-pinned8172 main/parser/StateMachine text references in memory. It executes actual C StateMachine/local shadow writes with fake source data, deterministic clocks and UUIDs, then exports an unmodified summary log and a full semantic trace file. It does not instantiate the actual Controller or use external transport.

a/b/e must match ordered event kinds/times and all compared semantic fields. c must show UNKNOWN/nonterminal behavior without invented deadline termination. d must expose the intentional removal of the old name-derived cancellation. Physical SQLite `created_at` is excluded from semantic comparison because separate local runs may cross real wall-clock seconds; UUIDs, idempotency keys, payloads/hashes, observed_at and deadline versions remain compared. Formal A/B LOCK is absent from this repository and remains UNVERIFIED.

The public log is the runner's raw output and includes a summary and full-trace SHA. The roughly3MB full semantic trace remains local/reproducible; it is not a production DB or backup. No raw A/B events are claimed. C5_UNKNOWN_NEXT_DAY.json shows a derived read-only count from the supplied synthetic c states only.

## 208B specification and integrity

`spec_sha_check.py` can be given an explicitly approved private local original in a future audit; no such path/file is supplied or read here. It never prints the source body or path. Without the original, the formal test skips with UNVERIFIED. Public tests check the40/64 relationship and negative synthetic inputs, not the unknown original's hash.

```sh
python -B development/health_residuals_20261106_v003/verify_artifacts.py
```

The verifier reads local artifact bytes only. MANIFEST.json and SHA256SUMS.txt exclude themselves; their own hashes appear in the final commit-fixed handoff. Historical v001/v002 manifests refer to their snapshots, not the changed v003 worktree. Byte/hash agreement is not external source authentication, current production equivalence or permission to port.
