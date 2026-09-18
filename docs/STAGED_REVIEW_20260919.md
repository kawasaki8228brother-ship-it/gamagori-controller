# Staged review — 2026-09-19 JST

## Scope and preservation
This work continues draft PR #2. No merge, deployment, historical prediction/result rewrite, A/B prediction-model change, or change to PR #1 was performed. Operational receipt/schedule verification is separate from prediction performance. Candidate modules are not yet integrated into the live fetcher.

## Receipt and scheduling review
Two pre-existing manual TEST AuditRuns receipts were read back. Python canonical SHA-256, receipt keys, timestamp ordering and millisecond column precision matched for both. Tampering and invalid-JSON negative checks passed. Health/Daily registered RRULEs were independently expanded. This does not prove future scheduled execution or push delivery. One isolated scheduled acceptance test was registered for 2026-09-19 01:15:45 JST; it may write only its own TEST AuditRuns START/END receipts.

## Candidate regression
The original candidate modules and tests were reconstructed from GitHub and their Git blob SHA-1 values matched the source. All 48 existing candidate cases passed. A further 22 synthetic counterexamples failed before fixes, covering ambiguous headers, malformed extra data rows, mistyped flags/reserves, invalid calendar dates, unexpected response container types and mutation through shared references. The corresponding guard fixes made all 70 cases pass. Two more split-header layout regressions brought the final local candidate run to **72 passed, zero failures** (Python 3.13.5). These are candidate-module tests, not the full application suite.

## Captured official response evidence
GitHub Actions run **35366320143**, job **105669556737**, successfully captured three public pages after the incident:

| Captured page | Bytes | SHA-256 |
|---|---:|---|
| 20260918 12R odds3t | 46613 | fb025cb40a651c2a566c5a5a91b039dc3b3c30d09a33e661279addfc3ab8e011 |
| 20260918 12R beforeinfo | 48614 | b59a7f33f8cf6c518b74bb29193a14163fe879275d25b32c78f644be39b0f1c5 |
| 20260918 3R odds3t | 46314 | 3b318561dc2102ef224782e4b8ef8a2bb65f2cd27f533a7ab17d13cd7c21827e |

Artifact **10556209220** ZIP SHA-256: `59daaa42d3690b4cdfac64474b83fb99ecff9b6de68c6ca7d77e72bef3543e07`. Downloaded ZIP and all three bodies were independently rehashed and matched.

On both captured odds pages, the old parser reproduced `no explicit trifecta+odds pairs found`. The first candidate also rejected the pages. Their actual first-place header uses alternating boat-number and racer-name cells, with the racer name spanning two columns, rather than six cells each spanning three columns. The candidate was updated to explicitly support this observed structure, retaining header-identity and ambiguity guards.

Replaying each archived odds page locally now returns exactly **120 combinations**. A separate physical-row traversal matched all **240 combination/odds pairs** across the two pages. This is evidence for these post-incident captures, not proof that the same bytes reached the live worker on September 18, all-layout compatibility, source freshness, or production recovery.

## Full application CI is NOT green
The first complete CI run produced **80 passed / 3 failed**. The failures are existing tests:

- `test_closing_event_persisted_and_idempotent`
- `test_atomic_duplicate_reuses_existing_event_uuid`
- `test_previous_version_event_does_not_hide_current_version_miss`

Logs show simulations using fixed September 17 datetimes, followed by post-evaluation deadline suppression. Next review must separate the simulation-clock contract from the production-clock contract. Do not weaken strict production deadline validation or erase these failures merely to get a green build. Add controlled-clock and deliberately late-evaluation cases.

The old beforeinfo parser also failed to extract exhibition times, courses and ST from the captured 12R page. That remains a separate input-parsing task.

## Next gates
1. Verify actual scheduled TEST START/END receipts; push delivery remains separately unverified.
2. Resolve the three whole-application time-test failures with explicit clock contracts.
3. Implement/test beforeinfo and ST/course handling against the captured structure.
4. Integrate source isolation before model contexts; a helper class alone is not database isolation.
5. Independently reconstruct frozen Events-to-Summary lineage and retain historical A5 context/decision impact as unverified without direct evidence.
6. Review integration with draft PR #1 and test migration on a SQLite copy, not the live database.
7. Evaluate missed outcomes cumulatively, then design a separate prospective F FINAL_LOCK layer.
8. Independent review and explicit merge/deployment authorization before any production promotion.
