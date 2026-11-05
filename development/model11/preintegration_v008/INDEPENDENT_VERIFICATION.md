# P1 independent saved-byte score and cohort preparation

Status: IMPLEMENTED + TESTED in synthetic offline scope. No integration GO, private-data GO, statistical acceptance or promotion follows. Existing v001–v007 engine, metrics, walk-forward, writers and frozen outputs are unchanged.

## Implemented boundary

`raw_logloss.py` accepts exact bytes plus caller-provided SHA-256 for a saved prediction and a separate result. Hash checks occur before strict UTF-8 JSON parsing. Duplicate keys, NaN/Infinity, booleans used as probabilities, incomplete/duplicate-boat domains, negative/out-of-range values, wrong stage sets and non-unit sums are rejected. A floating-point sum tolerance of 1e-12 is an engineering consistency check, **not** SESOI, a missing-rate limit or any F5 design value. The four stages remain distinct and the requested stage is explicit. No renormalization or likelihood floor is applied.

The current saved research schema `MODEL11_INDEPENDENT_SHADOW_RECORD_V005` / nested `MODEL11_FORECAST_V003` is supported as an audit projection, including its frozen synthetic example. A narrow `INDEPENDENT_PROBABILITY_INPUT_V001_PROPOSED` envelope is provided for fixtures and future approved adapters. Unknown formal A/B or production schema is HOLD. Five selected tickets alone do not define a 120-way distribution and are never expanded into invented probabilities.

The result uses a separate proposed `INDEPENDENT_RESULT_INPUT_V001_PROPOSED` envelope. It must bind the same race, give a valid 3-of-6 outcome, be FINAL, and have post-deadline publication/availability/revision times. Prediction source and all recorded feature/state/odds/training timestamps must be available no later than prediction time; prediction generation/publication/revision must precede LOCK and LOCK must precede the deadline. Unknown times and timezone-less/unknown-offset times do not become inferred values.

A proposed `SAVED_RAW_LOGLOSS_BINDING_V001_PROPOSED` sidecar binds prediction/result raw hashes, LOCK, publication times and matching model/market odds snapshot hashes/times. These are **self-reported bindings**, not independent proof of real capture, external authenticity or timely publication. No real receipts or original approval SHA are fabricated. The function only reports arithmetic recomputation and internally consistent supplied timing claims. A zero outcome probability is returned as UNVERIFIED positive-infinite log-loss with no finite clipping. Private-real inputs are not admitted by this synthetic-only preparation.

A/B source labels can appear only in the explicitly synthetic full-probability evaluation envelope and are reported as `INDEPENDENT_RAW_EVALUATION_ONLY`. This is the permitted third evaluator exception; there is no feature, prediction, selection, writer, network or saved-event reader connection. The module imports only stdlib. Actual A/B frozen-output mapping and full probability availability remain external prerequisites.

## Cohort and champion checks

`cohort_guards.py` audits exact roster/seal/model bytes. It rejects shared race IDs, raw digests and day clusters across training, selection, pilot and holdout, duplicate identities within a role, chronological misuse and unavailable training/selection/pilot records. The pilot cannot be reused as formal holdout. A single nonempty opaque model-byte artifact is bound by SHA; this is not a model-fit validator.

The seal binds one champion, a derived sorted selection-identity projection, selection time and freeze time before first holdout prediction. That projection hash is explicitly distinguished from original raw roster SHA. Empty roles are structurally incomplete audit inputs, **not** adoption of a minimum selection-day threshold. Sample adequacy, holdout size/start and all eight open F5 design values remain unfilled and outside this module.

These pure functions return no inferential PASS, model-superiority claim, power guarantee, execution authorization or automatic promotion. F5 decision interpretation is owned by the separate pinned-ledger authority component. No code here duplicates its alpha, power, option-selection or adoption decision.

## Executed evidence and revision record

- Python 3.14.3: 22 unittest methods PASS, zero failures/errors/skips.
- Python 3.12.14: the same 22 methods PASS, zero failures/errors/skips.
- Both runs independently check that an empty model artifact with its matching empty hash is rejected.
- Initial 20-method run had one **test fixture helper** KeyError when creating a sidecar after intentionally removing odds-time evidence; the auditor had not yet been reached. The helper was corrected, and all missing-time cases now reach HOLD.
- Second revision also checks V005 full-forecast nested outcomes and future training timestamps outside the minimal score projection.
- Source `raw_logloss.py`, `cohort_guards.py` and the test file have reached revision2 through the shared guard. No third edit is authorized by the current instruction. Any further defect requiring these files to change must STOP and be reported.
- Raw local logs are in `p1/private/raw-verifier-initial314.log`, `raw-verifier-final314-with-runtime.log` and `raw-verifier-final312-with-runtime.log`. Root may publish safe copies with recorded provenance. The initial log contains workspace paths and must not be silently relabelled as a redacted original.

## Top ten review claims

Run the supplied unit file from `development/model11` with the prepared interpreter:

```sh
python -B -m unittest discover -s tests -p test_preintegration_raw_verifier.py -v
```

| Claim for Claude | Test / inspection | Expected | Evidence |
| --- | --- | --- | --- |
| Exact raw hashing precedes parsing | raw-layout/hash tests | whitespace changes need a different expected raw hash | test source + runtime logs |
| Duplicate/nonfinite/boolean values fail closed | duplicate/value tests | HOLD, no submitted secret echoed | test source + logs |
| All120 distinct tickets and four stages stay separate | domain/stage tests | full domain; stage-specific known loss | test source + logs |
| Natural log-loss is recomputed independently | uniform/binary/frozenV005 tests | ln120, ln2/ln4, stored probability loss | test source + logs |
| Zero probability is not hidden by epsilon | zero-probability test | positive-infinite UNVERIFIED, no finite floor | test source + logs |
| Feature/odds/training future information is refused | future/sidecar/V005 tests | HOLD | test source + logs |
| Results stay separate and post-deadline | outcome/finality tests | HOLD for predeadline/result-in-forecast | test source + logs |
| Pilot, holdout and day clusters do not mix | cohort overlap/time tests | HOLD for shared day/race/raw digest | test source + logs |
| One champion is bound before holdout | seal/raw-model tests | HOLD on changed model, late freeze or changed selection set | test source + logs |
| No production or feature connection exists | AST imports + source inspection | stdlib + sibling audit helper only; go=false | both modules + tests |

## External blocks and shortest resolution

| Blocked item | Owner | Needed evidence | Minimum sequence |
| --- | --- | --- | --- |
| Real saved prediction/result adapter | HQ14 + Claude | approved private schema and hash/timing/source mapping, including any formal A/B120 probability availability | 1) map privately; 2) review mapping; 3) rerun this checker privately |
| Real predeadline/odds authenticity | HQ14 + operator | independent saved originals, capture/LOCK/readback receipts and matching snapshot lineage | 1) preserve privately; 2) independently bind hashes/times; 3) review eligibility |
| F5 eight open design values / formal inference | HQ14 + Claude + Andy | actual adopted decisions and original/receipt linkage when available; no values invented here | 1) decide externally before holdout; 2) record authority; 3) individual GO |
| Integration with v007/F5 and any live use | Andy after independent review | approved exact commits, dependency/integration plan, full regression and separate deployment/execution authorization | 1) review candidates; 2) authorize a concrete integration; 3) run approved migration |

The 2099 dates, singleton role examples and probability vectors are synthetic unit inputs, not adopted sample-size/day proposals. Current claim is completion of these offline audit components pending Claude review, not completion of all P1 work or formal adoption.
