# P0 offline review index

Parent: `fbd19ff2d1b619e31534c81939c4e03665053636`. New branch: `dev/health-offline-completion-20261106-v004`.

This is an isolated synthetic candidate, not integration or production approval. Begin with [REVIEW_GUIDE.md](REVIEW_GUIDE.md), then [RESULTS.json](RESULTS.json), [CASE_STATUS.json](CASE_STATUS.json), [SOURCE.patch](SOURCE.patch), [EVIDENCE_TRUST.json](EVIDENCE_TRUST.json), [RUNTIME_MATRIX.json](RUNTIME_MATRIX.json).

`MANIFEST.json` lists every repository file except itself and this directory's SHA256SUMS; SHA256SUMS includes the manifest and excludes itself. `PARENT_FILES.json` pins all old files. `EDIT_HISTORY.json` contains all guarded source/test revisions before final evidence generation; final aggregate receipt on the coordination branch covers subsequent one-write metadata files.

Run `python -B development/health_offline_completion_v004/verify_artifacts.py --repo .` and `python -B development/health_offline_completion_v004/run_regressions.py --repo . --scope root`. Use the already authorized dependency environment; do not contact services. No pip installation, credentials, deployment, PR or service operations are part of these commands.

The final cross-case DEVELOPMENT_STATUS and P0 exact-final-commit local trial-merge proof are delivered on a separate evidence-only coordination branch. P1 and P2 are sibling components; no v008 branch integration was performed.
