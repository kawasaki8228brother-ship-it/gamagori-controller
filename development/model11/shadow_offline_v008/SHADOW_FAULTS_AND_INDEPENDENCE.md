# P2 Shadow faults and A/B boundary — synthetic V008 component

Status: implemented + synthetic-tested; **complete (Claude review pending)** for this limited component. All reports retain `go=false`. No Shadow process, production connection, real capture, or writer integration is enabled here.

## Scope and frozen baseline

Base commit: `148c156f472c874075a0b25d4f0b6b7e9fafdcfe`. New modules only; existing runner, storage, models, selectors, settlement, settings, source mapping, course policy and A/B remain unchanged. Runtime fixtures are invented 2099 races. Every test store is newly created under `TemporaryDirectory`; no external DB is opened. P1's independently developed raw evaluator is referenced as an evaluation-only exception, never imported or integrated by this component.

The fault harness loads the existing synthetic fixture module only after SHA verification:

| Frozen source | Bytes | SHA-256 |
| --- | ---: | --- |
| tests/test_shadow_launch_runner.py | 25065 | 5b70cc75b4a8cf536ebf4bef9a0b33401e0df1d146b82d8438bb0bd656553bf4 |
| tests/test_shadow_launch_storage.py | 21933 | cfc46ff18ee3af34122fc8c19e8489642b84fca35f381976bdf72ff1917bed60 |

These are **exact baseline test replays**, not 18 newly independent implementations. A newly added ACK-loss probe covers successful on-disk commit followed by lost response. A separate refund probe checks independent arithmetic expectations rather than source-code presence.

## Reproduce

From repository root, with an existing isolated interpreter (no installation/network required):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=development/model11 nice -n 10 python -B -m unittest discover -s development/model11/tests -p test_shadow_offline_faults.py -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=development/model11 nice -n 10 python -B -m shadow_offline_v008.fault_suite
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=development/model11 nice -n 10 python -B -m shadow_offline_v008.independence
```

Only synthetic temporary files are written. No HTTP library/collector is called. Importing the new modules does not create storage or start the runner. `fault_suite` explicitly invokes bounded simulations and destroys their new temporary roots afterward.

## Executed results

| Runtime | OS | OpenSSL | SQLite | New outer tests | Embedded baseline vectors |
| --- | --- | --- | --- | ---: | ---: |
| Python 3.12.14 | Linux 6.18.57 x86_64, glibc 2.41 | 3.5.8 | 3.53.1 | 9 PASS, 42.131 s | 18 PASS |
| Python 3.14.3 | Linux 6.18.57 x86_64, glibc 2.41 | 3.5.5 | 3.50.4 | 9 PASS, 41.533 s | 18 PASS |

The 18 embedded vectors are **not** added to unittest collection counts. The CLI additionally reports ACK-loss and refund checks as 20 named vectors. Runtime differences from the eventual host remain `BLOCKED_EXTERNAL`; this is not production compatibility or real-data performance verification.

Raw logs retained privately: `faults-final-312.log`, `faults-final-314.log`, first-run `faults-first-314.log`; CLI evidence `fault-vectors-314.json`, `independence-314.json`. Their bytes/SHA belong in the enclosing case manifest. The first run failed because the new QA expected an **unselected** raw-envelope field to be rejected. The explicit pointer mapper ignores unselected fields: features and full prediction/selection output were unchanged. Revision 2 retains ignored-envelope/readspy equality and tests **selected feature** contamination as HOLD. No frozen model/writer was changed to make the test pass.

## Ten claims for independent review

| # | Claim | Command / assertion | Expected evidence |
| ---: | --- | --- | --- |
| 1 | Baseline raw source is pinned before execution | `fault_suite.load_pinned_fixture` and PINS | exact two SHA values above; mismatch raises fixed error |
| 2 | 12R probability/BOX/raw/receipt integrity | fault CLI `12R_PROBABILITY_BOX_RAW_RECEIPT` | TESTED; every P_* 120 entries/sum 1; five stake 500, separate BOX stakes 600 |
| 3 | Concurrent duplicates and restart do not publish a second forecast | `CONCURRENT_DUPLICATE_RESTART` | TESTED; one COMMITTED, immutable original bytes |
| 4 | Partial persist failures preserve evidence and STOP | `EVERY_PERSIST_STAGE`, `AMBIGUOUS_PERSIST_STOP`, `LOST_ACK_AFTER_COMPLETE_COMMIT` | TESTED; ACK case preserves four artifacts, durable stop and restart HOLD |
| 5 | Deadline delay / backwards clock are fail-closed | `DELAY_CROSSES_DEADLINE`, `CLOCK_FORWARD_DEADLINE`, `CLOCK_BACKWARDS`; clock unit tests | HOLD before valid publish; no safety margin/threshold adopted |
| 6 | Result correction never overwrites forecast | `RESULT_CORRECTION_APPEND_ONLY`, `NEW_FINAL_REQUIRES_RESELECTION`, `DAILY_EXPLICIT_FINAL_SELECTION` | append-only result, explicit final-version selection required |
| 7 | Refund arithmetic stays per portfolio | `SEPARATE_STAKES_EXPLICIT_REFUND` | five net 600, BOX net 500 for payout 1000/refund 100; unknown refund => unknown; winner/refund contradiction rejected |
| 8 | Scratch/cancellation do not invent financial/terminal policy | `SCRATCH_FULL120_HOLD`; status-classification unit test | full-120 impossible input HOLD; distinct event kind, pnl null, no writer integration |
| 9 | Scoped import and data-flow probes expose no A/B prediction input | independence CLI | ten-file AST clear; exactly 17 declared pointers, no A/B pointer; all outputs equal for ignored A/B envelope poison; selected feature/source poison HOLD |
| 10 | Defaults, STOP, source errors and secrets are safe in simulation | `DURABLE_OPERATOR_STOP`, source exception vector, new sentinel test | durable STOP/no replay; fixed result codes, synthetic private exception text absent; go=false |

## Boundary interpretation

Static analysis checks imports and selected call names in **ten listed frozen files**, not all executable Python, host files, plugin behavior, dynamic loading, or universal noninterference. It checks named production connectors; absence is bounded evidence. The dynamic probe wraps the existing JSON-pointer resolver and records its declared 17 reads. The entire submitted JSON is parsed, including ignored A/B-looking fields; parsing them is not use as prediction input. Poison assertions compare extracted raw/course inputs **and full predictor/selection outputs**. Schema-level feature/source poison is rejected.

`preparation/legacy.py` and `revision_v003/evaluation.py` remain evaluation-only supplied-frozen-output adapters. They do not reproduce official Model 1.0/Human BOX and are not training/selection inputs. Their existence is not falsely reported as an A/B prediction reader; the prediction probes operate on the adapter-to-predictor boundary. P1's separately hashed-raw comparison evaluator is outside this branch's import graph by construction.

## Four-state record and external handoff

| Item | IMPLEMENTED | TESTED | Remaining state / owner / shortest resolution |
| --- | --- | --- | --- |
| Fixed synthetic 12R and fault harness | yes | both runtimes | Claude independent review pending; inspect claims and run above three commands |
| ACK-loss, refund arithmetic, scoped A/B probes | yes | both runtimes | Claude independent review pending; run new tests and inspect structured probe output |
| Wall/monotonic observation helper | yes, diagnostic only | synthetic finite/invalid/backward/jump pairs | BLOCKED_EXTERNAL: HQ14 host operator supplies actual clock/runtime evidence, Claude reviews, Andy separately approves use; no threshold/integration here |
| Actual cancellation/scratch financial settlement | no contract adoption | explicit unknown/HOLD tested | BLOCKED_EXTERNAL: HQ14 supplies approved official result/refund/cancel/scratch contract; Claude independently reviews; then separately approved implementation/testing. No zero-profit/full-refund inference |
| Real source mapping/time authenticity | not fabricated | synthetic format only | BLOCKED_EXTERNAL: HQ14 supplies private verified mapping/time evidence; private replay; Claude review + Andy individual GO |
| Actual host/restart/filesystem behavior | no host created | local temp-store simulation only | BLOCKED_EXTERNAL: HQ14 dedicated host evidence → independent compatibility/fault review → separate launch GO |

No unaddressed code failure is represented as PASS. The initial QA expectation defect is fixed with first-failure evidence preserved. Source/test files reached two guarded content revisions and are frozen; a further defect requires STOP/report rather than a third edit or rename.

## STOP / safety / disposal

STOP for frozen source SHA mismatch, failed vector, unknown clock evidence, future/missing source data, uncertain save/readback, duplicate conflict, deadline crossover, unapproved result version, or any attempted real-data/service path. Source exceptions export fixed classifications, never arbitrary exception text. No operator stop is cleared automatically and no replay is scheduled.

Remove only the new offline component and its test to discard this candidate; temporary stores are already cleaned up. Existing production artifacts need no restore because they were not changed. Do not deploy this branch. Formal rule adoption, real-data execution, Shadow activation, and production changes require independent review and Andy's separate GO. Freeze, formal A/B, Model 1.0, BOX Ver.1, LOCK and F2/F5 decisions remain unchanged.
