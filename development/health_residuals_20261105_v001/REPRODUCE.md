# Offline reproduction only

Run from the isolated candidate repository with an already approved Python environment. These instructions do not authorize installing packages, network access, Render/Shell access, production reads, source capture or deployment. All output directories below must be new local directories. No actual 11/5 source is required or accepted by these examples.

Use `python -B`; do not run `main.py`, `_amain()` or the real Controller constructor. The runners block network in-process; controller integration uses `__new__`, invented states, fake repositories, fake fetchers and a dispatch spy. The existing regression suite creates only local temporary synthetic SQLite databases.

## Candidate regression

An existing environment must provide the versions reported in the retained logs. No environment is modified by this command. Choose a new, writable offline output path outside the repository.

```sh
python -B development/health_residuals_20261105_v001/run_offline_tests.py --junit-output /tmp/health-candidate-new.xml
```

The retained run used Python 3.14.3, pytest 9.0.2, pytest-asyncio 1.3.0, pydantic 2.13.4, beautifulsoup4 4.14.3, httpx 0.28.1 and certifi 2026.10.23 from an existing offline environment. The unchanged base requirements do not pin all these versions. Full Python 3.12 C-runtime equivalence was not tested.

Expected primary collection: 353 cases, plus 14 subtests. The emitted JUnit record count includes subtests and is 367. Do not report 367 independently collected tests.

For baseline comparison, use a separate local byte-verified copy of the 40 files at commit `8172aec010894a52f36f48b7091476d26494e4ee`, described in PARENT_FILES.json. Do not overwrite the candidate or an existing checkout. No GitHub write is needed for reproduction.

```sh
python -B development/health_residuals_20261105_v001/run_offline_tests.py --repo /tmp/health-baseline-new --junit-output /tmp/health-baseline-new.xml
```

Expected baseline collection: 248 cases. Compare the two run environments before interpreting results.

## Fail-closed parsing and old-day dispatch

```sh
python -B development/health_residuals_20261105_v001/reproduce_parser_boundaries.py --repo /tmp/health-baseline-new --label BASELINE
python -B development/health_residuals_20261105_v001/reproduce_parser_boundaries.py --repo . --label CANDIDATE
python -B development/health_residuals_20261105_v001/reproduce_stale_dispatch.py --repo /tmp/health-baseline-new --label BASELINE
python -B development/health_residuals_20261105_v001/reproduce_stale_dispatch.py --repo . --label CANDIDATE
```

Normal twelve-race parser fields must agree exactly. Multiple-times, conflicting-duplicate and out-of-table cases must be rejected by the candidate. Empty content never proves a non-racing day.

All three old-day dispatch examples must have `prior_day_dispatched=false` in the candidate. Current-day recovery remains unconfirmed; no real StateMachine/DB/HTTP is used. The example is not incident reconstruction.

## Pure OBS QA

```sh
python -B development/health_residuals_20261105_v001/run_obs_synthetic.py --unittest-only
python -B development/health_residuals_20261105_v001/run_obs_synthetic.py --output-dir /tmp/health-obs-new
```

The stdlib-only test is independently usable with Python 3.12/3.14. `--output-dir` writes only a new invented fixture and QA report, never to Events or a production path. Existing directories are refused.

The pure API `audit_obs_rows(rows)` takes the proposed normalized input described in ../../docs/OBS_QA_SPEC.md; no real source connector or writer is present. A private HQ14 mapping and approved contract review are prerequisites to any later real-data audit.

## Evidence integrity

```sh
python -B development/health_residuals_20261105_v001/verify_artifacts.py
```

This reads local files only, checks all manifest bytes/SHA/Git blobs, original preservation and exact diff, and verifies SHA256SUMS agreement. It does not prove external source authenticity or live behavior. MANIFEST.json and SHA256SUMS.txt exclude themselves to avoid recursive hashes; their own bytes/SHA must be read from the final commit-fixed handoff/readback receipt.

Raw logs are retained separately from any redacted copy. LOG_PROVENANCE.json records the original and published SHA and trust label. Public XML is omitted because it can contain internal paths. Never silently redact a log and claim its original hash.
