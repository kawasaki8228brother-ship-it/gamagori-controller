# P2 offline review index

Parent: `148c156f472c874075a0b25d4f0b6b7e9fafdcfe`. New branch: `dev/model11-shadow-offline-20261106-v008`.

This is an isolated synthetic candidate, not integration or production approval. Begin with [REVIEW_GUIDE.md](REVIEW_GUIDE.md), then [RESULTS.json](RESULTS.json), [CASE_STATUS.json](CASE_STATUS.json), [SOURCE.patch](SOURCE.patch), [EVIDENCE_TRUST.json](EVIDENCE_TRUST.json), [RUNTIME_MATRIX.json](RUNTIME_MATRIX.json).

`MANIFEST.json` lists every repository file except itself and this directory's SHA256SUMS; SHA256SUMS includes the manifest and excludes itself. `PARENT_FILES.json` pins all old files. `EDIT_HISTORY.json` contains all guarded source/test revisions before final evidence generation; final aggregate receipt on the coordination branch covers subsequent one-write metadata files.

Run `python -B development/model11/shadow_offline_v008/verify_artifacts.py --repo .` and `python -B development/model11/shadow_offline_v008/run_regressions.py --repo . --scope model`. Use the already authorized dependency environment; do not contact services. No pip installation, credentials, deployment, PR or service operations are part of these commands.

The final cross-case DEVELOPMENT_STATUS and P0 exact-final-commit local trial-merge proof are delivered on a separate evidence-only coordination branch. P1 and P2 are sibling components; no v008 branch integration was performed.
