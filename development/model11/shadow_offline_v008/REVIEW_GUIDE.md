# P2 V008 preparation: Claude independent review guide

This is a new, offline-only synthetic component on parent
`148c156f472c874075a0b25d4f0b6b7e9fafdcfe`. No existing model, selector, writer,
LOCK, source mapping or historical evidence is replaced. All 320 parent files
remain byte-identical. Status: **IMPLEMENTED + TESTED within the stated synthetic
coverage; complete (Claude review pending)**. All real-data execution, source
approval and Shadow launch remain HOLD, and all GO flags remain false.

Run commands from the isolated repository root. Set
`PYTHONPATH=development/model11`, use `python -B` (an existing interpreter), and
block external networking. The diagnostic commands do not install dependencies,
contact a site, write an external service or start a host. The fault harness
creates and cleans only new local synthetic temporary stores. The complete
regression wrapper and evidence/manifest are supplied by the enclosing package;
review those exact originals rather than a screenshot transcription.

## Ten claims to independently check

Paths in the evidence column below are relative to this guide's directory.

| # | Claim | Reproducible command / source assertion | Required result and preserved evidence |
| ---: | --- | --- | --- |
| 1 | Changes are additions on the declared frozen parent; old evidence is not rewritten | Inspect the enclosing manifest and compare the 320 parent-file byte counts, SHA-256 and Git blobs with the fixed parent; inspect new-file-only Git diff | 320/320 match, no main/PR/formal A/B/requirements/CI changes. The case manifest is the authoritative exact bytes/SHA inventory; self-hash alone is not approval/authentication. |
| 2 | The measured input contract is 264 local patterns, not an invented official mapping | `PYTHONPATH=development/model11 python -B -m shadow_offline_v008.contract_matrix` | 264 patterns expand to 554 targets; 2216 records, 2208 HOLD and eight conditional N/A, zero unexpected acceptance, original input unchanged. `evidence/contract-matrix314.raw.json` preserves every record. Two private review hashes are N/A for this synthetic profile, not fabricated approvals. |
| 3 | Odds require a complete pre-deadline 120-domain; unknown/final values are not substituted | `PYTHONPATH=development/model11 python -B -m unittest discover -s development/model11/tests -p test_shadow_offline_contract.py -v` (OddsAuditTests) | Missing each ticket, bad units, bool/nonfinite/nonpositive odds, unknown/future timestamps, final/unknown role, duplicate JSON and byte-SHA mismatch are HOLD. Age is observed separately; freshness threshold is null, freshness UNVERIFIED, market eligibility false. `CONTRACT_AND_DATA_REVIEW.md`, source `odds_audit.py`, and full logs. |
| 4 | Feature, motor, course and historical timing claims cannot silently admit future data | Same contract discovery command (ContractMatrixTests / PastInformationTests) | All 30 feature observations across three future timestamp positions, post-snapshot revision, missing/final odds, result/payout feature, invalid motor identity/version and late training information are held. Valid zero and F/L warning semantics are preserved; missing is not guessed false. Existing policy permits absent unselected frame under EXHIBITION_ONLY; selected exhibition absent is HOLD. Full matrix and full logs. |
| 5 | Twelve-race output keeps all probability and portfolio invariants | `PYTHONPATH=development/model11 python -B -m shadow_offline_v008.fault_suite` | `12R_PROBABILITY_BOX_RAW_RECEIPT` TESTED: each P_* has 120 distinct tickets/sum one, no repeated boat; normal five stake 500 and separate BOX stakes 600; raw/SHA/receipt/readback agree. `evidence/fault-vectors-314.json`. No performance/superiority claim follows from invented data. |
| 6 | Duplicate, restart, partial-save and lost-acknowledgement cases preserve evidence and fail closed | Same fault-suite command; inspect `CONCURRENT_DUPLICATE_RESTART`, `EVERY_PERSIST_STAGE`, `AMBIGUOUS_PERSIST_STOP`, `LOST_ACK_AFTER_COMPLETE_COMMIT` | One committed forecast; ambiguous response leads to durable STOP and restart HOLD. Lost ACK after completed commit retains input.raw/forecast.raw/receipt.json/completion.json, no automatic replay. `evidence/fault-vectors-314.json`; frozen runner/storage source pin checks fail closed. |
| 7 | Clock/deadline anomalies do not become valid late predictions | `PYTHONPATH=development/model11 python -B -m unittest discover -s development/model11/tests -p test_shadow_offline_faults.py -v`; fault-suite command | Backward/forward clock, deadline crossover and invalid clock observation cases are explicit/HOLD. Wall/monotonic diagnostic remains observation-only: no new freshness, deadline safety-margin or operational clock threshold is adopted. Source `fault_suite.py`, full logs and fault-vector JSON. Actual host/time authenticity is external. |
| 8 | Result revision, refund, cancellation and scratch are distinguished without rewriting predictions | Fault-suite command; inspect append-only/final-selection/refund/scratch vectors and new status-classification test | Corrections append; final selection is explicit. Independent refund example: five stake500/net600, mechanical BOX stake600/net500 for payout1000 plus refund100. Unknown refund is not zero; winner/refund conflict rejected. Cancel/scratch settlement has null P&L and BLOCKED_EXTERNAL/HOLD pending approved contract. Existing forecast bytes and writer rules unchanged. |
| 9 | Scoped A/B independence has static and dynamic evidence, with limits disclosed | `PYTHONPATH=development/model11 python -B -m shadow_offline_v008.independence` | Ten pinned selected-source AST/import/call scans clear; exactly17 declared pointer reads, no A/B prediction pointer. Ignored A/B-shaped envelope poison leaves extracted features and all prediction/selection outputs identical; selected feature or source poison is HOLD. `evidence/independence-314.json`. Parsing the complete JSON is not claimed to be zero parsing of ignored keys; this is not universal noninterference. Evaluation-only frozen-output adapters are explicitly excluded from the prediction boundary. |
| 10 | Software PASS is separate from adoption/approval; counts, failures and limitations are honest | Run the enclosing `run_regressions.py` with each recorded interpreter; inspect environment headers, collection counts, manifest and first-run evidence | Full model suite: 584 PASS on Python3.12 and 584 PASS on Python3.14. New outer methods are17 contract +9 faults =26; 18 embedded baseline replays are not added to method counts. CLI has20 named fault vectors including ACK/refund. Initial QA failure is preserved as `evidence/faults-first-314.log` (REDACTED if necessary, with separately declared original SHA), never relabelled PASS. All GO flags false. |

## Runtime and evidence interpretation

Final full-regression counts above are measured by the enclosing root verifier,
not inferred from this guide's text. The component's direct final tests are:

| Interpreter | OpenSSL | SQLite | Contract tests | Fault outer tests |
| --- | --- | --- | ---: | ---: |
| Python 3.12.14 | 3.5.8 | 3.53.1 | 17 PASS | 9 PASS |
| Python 3.14.3 | 3.5.5 | 3.50.4 | 17 PASS | 9 PASS |

OS: Linux 6.18.57 x86_64 with glibc2.41. These are observed local runtimes, not
proof of compatibility with an unobserved real Shadow host or production SQLite.
The 3.12 environment uses the available read-only system-site runtime; no clean
production-clone claim is made. Full original runs:
`evidence/full312.raw.log` and `evidence/full314.raw.log`.

The initial fault QA incorrectly required an unselected envelope key to cause
rejection. The frozen pointer mapper actually ignores that field; the corrected
QA checks exact selected-pointer reads, identical complete predictions and HOLD
for selected-feature contamination. No writer/model was changed to accommodate
the test. The original failing evidence remains separate from final PASS logs.
Any REDACTED export has a distinct SHA and trust label; it is not the original
log. Consult the enclosing manifest for exact filenames, bytes and full hashes.

## External blockers: who supplies what, and shortest resolution

| Remaining gate | Owner / required input | Minimum safe path |
| --- | --- | --- |
| Real official input mapping and source/time authenticity | HQ14 private custodian; exact privately captured field structure, original evidence and timestamp history; Claude independent review | Private capture under separate approval -> explicit mapping/units/time correspondence -> independent replay/review. No live collector, fabricated mapping or public raw original here. |
| Odds freshness policy / F5 OPEN conditions | HQ14 / Claude / Andy; actual pilot timing, approved rule and remaining evaluation inputs | Retain null/unadopted values -> review actual private summary -> separate recorded adoption and audited boundary tests before private evaluation. No candidate numeric threshold is invented in this package. |
| Private review originals and approval receipts | HQ14 / Claude; actual scoped original bytes/hash/receipt | Obtain originals privately -> independently bind bytes/scope -> explicit GO review. Self-reported hash or OFFICIAL_* spelling is not proof. |
| Past pre-deadline snapshot availability | HQ14 private custodian | Inventory actual snapshots -> independently verify point-in-time availability/revisions; absent snapshots stay blocked. Final odds are never backfilled as pre-deadline odds. |
| Cancel/scratch/refund result contracts | HQ14 / Claude; approved official semantics and original evidence | Supply contract -> independent review -> separately approved implementation/testing. No inferred full refund, zero P&L or TERMINAL policy here. |
| Actual dedicated host/runtime/clock/filesystem/restart evidence | Future separately approved operator, HQ14 / Claude / Andy | Supply isolated host evidence under separate GO -> compatibility and fault review -> independent launch decision. No host/deploy/schedule/Shadow process is created now. |

These are BLOCKED_EXTERNAL, distinct from a failed code test. No current
unresolved code failure is asserted absent evidence: if a vector fails, a frozen
source changes, provenance is unknown, save/readback is ambiguous, a deadline is
crossed or a third file revision is needed, STOP and report. Do not auto-clear
STOP, replay, fill missing input, approve private execution or merge this branch.

Source/tests/component documents are frozen at the handoff revision counts;
this guide is a new file, not a route around that freeze. Any further defect
requires the defined review/STOP process. No actual source mapping, real-data
validation, model superiority, launch approval or production operation is
claimed. Model1.0, BOX Ver.1, formal A/B and all approval gates remain unchanged.
