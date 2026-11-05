# P1 preintegration v008 — Claude REVIEW_GUIDE

Status: offline components implemented and synthetically tested; **Claude independent review pending**. This is not a v008 branch integration, real-data admission, statistical PASS, Shadow start or production GO. The base is `148c156f472c874075a0b25d4f0b6b7e9fafdcfe` on the `7aec4fd` lineage. The F5 ledger branch is referenced by immutable artifact bytes; it has not been merged into the engine.

## Start here

Read [AUTHORITY_AND_SIGN.md](AUTHORITY_AND_SIGN.md), [INDEPENDENT_VERIFICATION.md](INDEPENDENT_VERIFICATION.md), the additive [provenance record](DECISION_PROVENANCE_OVERRIDE.json), and the final root manifest/log provenance. No command below fetches source data or starts a model/Shadow writer.

Use an already prepared offline interpreter and a fresh local checkout. From the repository root:

```sh
cd development/model11
python -B -m unittest discover -s tests -p test_preintegration_authority.py -v
python -B -m unittest discover -s tests -p test_preintegration_raw_verifier.py -v
python -B -m unittest discover -s tests -v
```

Call the first command **A**, the second **B**, and the last **FULL** below. A has 11 methods; B has 22 methods. Root's executed full-model result is **591 PASS in Python 3.12 and 591 PASS in Python 3.14**. Confirm that claim against [full312.raw.log](evidence/full312.raw.log) and [full314.raw.log](evidence/full314.raw.log), including their actual environment headers; counts do not by themselves prove a claim. Root-level controller regression is separate and is not silently included in the591.

The root-supplied `run_regressions.py` records the final command interface and network/cache guards. Its actual `--help` and retained run logs govern its options; this guide does not invent runtime flags. All tests here use synthetic inputs. Do not install into or alter existing certifi/SYS environments to reproduce them.

## Top ten claims to verify

| # | Claim for Claude | Reproduction command / focused test | Required observation | Evidence |
| --- | --- | --- | --- | --- |
| 1 | F5 values come from one pinned policy artifact, not arbitrary caller configuration | A; `test_projection_uses_pinned_decisions_and_keeps_eight_open_values_null`, `test_changed_self_asserted_document_never_becomes_an_authority` | Exact ledger6541B/SHA match projects M0/M2/M1. Altered, appended, self-asserted receipt or unknown bytes HOLD. `artifact_sha256` is not Andy's missing original-record SHA. | `authority.py`; `references/F5_DECISION_LEDGER_1778d2e.json`; A/full logs |
| 2 | Decision provenance, history and all eight OPEN values remain honest | A; provenance and projection tests | Claude's witnessed “先生のおすすめを採用で！” is confirmed per the forwarded report; HQ14's20:36 time is Claude UNVERIFIED. Original SHA/receipt stay null, eight values stay null, prior examples are excluded, and v007A's RECOMMENDATION_ONLY body hash is unchanged. | `DECISION_PROVENANCE_OVERRIDE.json`; `AUTHORITY_AND_SIGN.md`; A/full logs |
| 3 | Pilot/M0 sign and SD conversion are consistent | A; `test_roundtrip_and_favorable_direction`, `test_day_mean_sign_changes_sd_does_not_and_input_remains_unchanged`, dispersion tests | `d_M0=-delta_pilot`; roundtrip restores values. Negative pilot favors the model, positive M0 favors the model. Sample SD is unchanged; fewer than two days remain unknown and observed zero is not future-variance certainty. | `signs.py`; A/full logs |
| 4 | One-sided direction and pure-market interpretation cannot grant an unsupported superiority claim | A; tail-identity and market-weight tests | Pilot lower tail equals M0 upper tail under the stated normal identity only. Actual test flag is false and no pass is granted. Selected w=1.0 returns NO_MODEL_SUPERIORITY; m=1 refers to one frozen champion, not six tests. | `authority.py`; `signs.py`; pinned M0/M1; A/full logs |
| 5 | Independent score verification hashes original saved bytes before interpreting them | B; raw-layout/hash, duplicate-JSON and nonfinite tests | Different whitespace/layout needs its own SHA; no canonical re-encoding silently replaces an expected raw digest. Duplicate keys, malformed UTF-8/JSON and nonfinite tokens HOLD without echoing supplied secrets. | `raw_logloss.py`; B/full logs |
| 6 | Exactly120 outcomes and the four probability stages remain distinct | B; domain/value/sum and stage-selection tests | All six-boat permutations occur exactly once; no repeated boat, boolean, negative or nonfinite probability. Raw/model/market/shrunk are explicit stages. Incomplete five-ticket forecasts are not expanded into invented distributions. | `raw_logloss.py`; `test_preintegration_raw_verifier.py`; B/full logs |
| 7 | Natural log-loss is recomputed without a hidden normalization or zero floor | B; uniform, stage-specific, frozenV005 and zero-probability tests | Known uniform loss equals ln120, chosen known probabilities produce their expected natural losses, and existing frozen syntheticV005 is read as an audit projection. Outcome p=0 stays positive-infinite UNVERIFIED; no epsilon creates a finite performance score. | `raw_logloss.py`; B/full logs |
| 8 | Prediction, result and point-in-time evidence stay separate | B; future-feature/state/training, all-time-evidence, result-finality and snapshot-binding tests | Unknown/future/naive times, premature outcomes, mismatched raw hashes or model/market odds snapshots HOLD. Internally matching sidecar claims never become independent proof of real capture, publication or authenticity. | `raw_logloss.py`; `INDEPENDENT_VERIFICATION.md`; B/full logs |
| 9 | Pilot/holdout contamination and post-hoc champion replacement are refused | B; all `CohortGuardTests` | Race IDs, day clusters and raw digests cannot cross roles. Pilot is not formal holdout. One nonempty model-byte artifact and the selection projection/seal must bind before first holdout prediction; late freeze or changed identities/model HOLD. No minimum selection-day or holdout-size value is invented. | `cohort_guards.py`; B/full logs |
| 10 | This remains audit-only preparation with old code preserved | A+B+FULL; `test_modules_have_no_model_engine_or_io_import_connections`; read-only `git diff --name-only 148c156f472c874075a0b25d4f0b6b7e9fafdcfe HEAD` in a real checkout | Audit modules import only stdlib/sibling audit helpers, do not route A/B bytes into features or selection, and all GO flags remain false. Existing320 base files are preserved; additions are new preparation components/tests/evidence. Actual A/B input mapping and real receipts remain external. | full312/full314 logs; root baseline-preservation metadata/manifest; source diff; `AUTHORITY_AND_SIGN.md` |

A read-only Git comparison needs an actual checkout. A downloaded archive has no Git history: use its final manifest and parent-byte inventory instead, and do not report an unexecuted command as PASS. The two proposed score/result envelopes and the sidecar are input contracts for this independent checker, not claims that a formal A/B schema is already mapped. A/B labels are admitted only inside explicitly synthetic full-probability evaluation inputs, as the third-evaluator exception; they are never model features.

## What this guide does not close

- Formal decision original SHA and receipt **do not exist in the supplied evidence**. Keep them null; do not create a substitute record and label it original. The pinned ledger hash is a different artifact identity.
- Eight unresolved F5 values remain empty. No new values, sample-day suggestions or adoption thresholds are proposed. M0→M2→M1 interpretation does not start pilot, holdout or live execution.
- Real saved-output schemas, original timing/source/odds evidence and actual A/B120 probabilities require HQ14/Claude private review. The current code admits only synthetic preparation; no real originals were provided to Codex.
- A matched self-reported sidecar is not timely-publication proof. Zero sample SD, normal-tail identities and synthetic log-loss correctness are not evidence of model superiority, adequate N, profit or real inference validity.
- Integration of the148c156 and1778d2e lines requires a separate concrete approval, followed by combined regression. This branch deliberately does not perform that integration or alter existing engine, market weights, predictions, BOX, A/B, writers or tasks.

External owners, required evidence and shortest resolution sequences are listed in the two component documents. The complete delivery's DEVELOPMENT_STATUS.json separates IMPLEMENTED/TESTED from BLOCKED_EXTERNAL and FAILED_OPEN. Passing this guide's tests means offline evidence is ready for Claude review, not that Claude has already reviewed it.
