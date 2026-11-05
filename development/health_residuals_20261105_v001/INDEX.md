# HQ14 / Claude review index: Health residuals v001

Status: OFFLINE DEV_READY within synthetic scope; LIVE_UNVERIFIED; production GO=false.

Base: `8172aec010894a52f36f48b7091476d26494e4ee`  
Isolated branch: `dev/health-residuals-20261105-v001`

1. [Outcome, limits and future review gates](REPORT.md)
2. [Exact source diff](C_SOURCE.patch) / [file-level scope](DIFF_STAT.json)
3. [Parser analysis](PARSER_ANALYSIS.md)
4. [Official/fallback and calendar-evidence classification](OFFICIAL_CLASSIFICATION.md)
5. [OBS QA contract and known/unknown obligations](../../docs/OBS_QA_SPEC.md)
6. [Task change proposal only](../../docs/OBS_TASK_CHANGE_PROPOSAL.md)
7. [Read-only audit designs](P2_READONLY_AUDIT_PLAN.md) / [OPEN register](P2_OPEN_REGISTER.json)
8. [Rollout and STOP boundaries](ROLLOUT_AND_STOP.md)
9. [Internal independent code review](INDEPENDENT_REVIEW.md), which is not Claude's external review
10. [Reproduction instructions](REPRODUCE.md)
11. [Measured test/evidence summary](evidence/RESULTS.json)
12. [Raw/published log provenance and hashes](LOG_PROVENANCE.json)
13. [Original 40-file inventory](PARENT_FILES.json) / [byte-preserved changed originals](references/)
14. [All repository file bytes, SHA256 and Git blobs](MANIFEST.json) / [SHA256SUMS.txt](SHA256SUMS.txt)
15. [Local verifier](verify_artifacts.py)

Public evidence contains only synthetic fixtures, public base source and safe offline logs. Actual November 5 HTML/Events, real DB content, runtime secrets, notifications and internal scheduler records were neither collected nor published. All real-state P2 questions remain UNVERIFIED.

The isolated branch retains old base requirements unchanged and must not be deployed. Certifi remains first priority. No existing branch, PR #6, main, task, Production, Model 1.0/1.1, BOX, Freeze, canonical or POINTER is changed by this candidate.
