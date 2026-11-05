# Branch-only rollout and STOP boundaries

This is an isolated-branch offline candidate, not live GO. No main push/merge, PR #6 change, deploy, Render/production Shell/DB audit, Airtable/Automation write or notification send is authorized. Any live read/change requires Andy's individual GO; this document instructs no execution.

Certifi's 11/6 window has priority; SYS-01/SYS-02/Model v007 stay untouched. Do not use the old base as a deploy target or bypass certifi. Legacy vulnerable-certifi rollback, suspend/resume and automatic rollback are **not authorized**.

## Review before any later main/deployment decision

1. Root's P0 offline candidate may change `parsers.py`, `official.py`, `main.py`. Inspect exact branch/base/head/diff and tests. Preserve `state_machine.py`, models, LOCK logic, requirements, render.yaml and other frozen behavior; do not import unrelated work. A changed file named main.py on an isolated branch is not permission to change GitHub main.
2. Strict parsing may reduce availability. Actual 11/5 HTML is unavailable: compatibility and incident cause stay UNVERIFIED. A stale-race code hypothesis is not a confirmed live cause; do not manufacture proof.
3. Official no-race provider defaults to None; no actual adapter is configured. Missing rows, ParserError, HTTP success, fallback/no-known-race logs do not automatically establish non-racing status. Never fill the provider from absence.
4. Local tests must separate parser correctness, freshness/fallback behavior and explicit official no-race evidence. The normal non-racing observation is not proof of complete source correctness. Preserve delivery/run-ID/OBS/duplicate uncertainties in P2 rather than adding speculative payload requirements.
5. Before future live GO, independently confirm approved code/dependency SHA, actual service/worker/disk/DB identity, DRY_RUN/C_ACTIVE meaning, safe read scope, authoritative originals and private receipt handling. Any drift, missing evidence or unknown behavior is HOLD/STOP; passing local tests does not fill these inputs.

Source drift, TLS/connection failure, false no-race/stale-race use, identity/LOCK/hash uncertainty, read failure or receipt mismatch means stop the proposed action/report. No DB repair, task change or active-work cancellation. This is not authorization to stop a running production process.

The candidate can be retained/discarded offline by its owner without changing production. Preserve test/initial-failure logs and exact source hashes. Actual application, readback, normal polling, independent review and CLOSE remain later separate gates. HQ14 alignment, Claude independent review and Andy individual GO are not replaced by internal agent review. G1-G6 definitions are not supplied here and must not be invented. No automatic promotion follows a date, count zero, green test suite or branch publication.
