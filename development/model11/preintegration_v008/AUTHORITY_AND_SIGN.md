# P1: F5 authority and sign preintegration components

Scope: new isolated components only; existing v007A, model/selection/Shadow code and the separate F5 document branch are unchanged. These components are not imported by the existing model runner. No branch integration, real-data evaluation, promotion or execution GO is implemented.

## Sole policy authority and additive clarification

The packaged reference is the byte-pinned public `DECISION_LEDGER.json` at commit `1778d2e4080dad8b5f1e80b7cc22ea0f5ce7df67`: 6,541 bytes, SHA-256 `1eda58d7b8aaa221314b02c2be90ae2b5f9640873a33d192aa5b59411e9a222d`. This is an **artifact hash**, not the unavailable original decision-record SHA. Original decision SHA and approval receipt remain null. `project_authority` derives the M0/M2/M1 values from those exact bytes; arbitrary self-asserted documents, supplied original hashes and mutated OPEN values cannot replace the pin.

The eight OPEN values remain null; no new sample-day, effect, missingness, spending, cancellation, dependence or post-pass scope candidates are generated. Historical numerical examples in the original ledger are excluded from the executable-facing projection and are not adopted. The selected six market weights are selection candidates for one frozen champion, not six confirmatory hypotheses. A selected w=1.0 remains pure market and never grants MODEL superiority. Other weights also do not grant superiority without untouched evaluation evidence.

`DECISION_PROVENANCE_OVERRIDE.json` is an additive record. It leaves v007A's `RECOMMENDATION_ONLY_NOT_ADOPTED` body unchanged and records that the policy interpretation is superseded by the decided M0→M2→M1 sequence in the pinned ledger. It does not duplicate or override numerical policy values. It separates Claude's direct-witness statement **「先生のおすすめを採用で！」** (confirmed per the forwarded Claude report; Codex received only) from HQ14's forwarded **20:36** timestamp (Claude UNVERIFIED). No source record or receipt is invented.

## Sign convention

`delta_pilot = champion_joint_logloss - market_joint_logloss`; `d_M0 = -delta_pilot = market_joint_logloss - champion_joint_logloss`. Positive d_M0 and negative delta_pilot favor lower champion loss. The conversion is involutive and preserves sample SD. Inputs are equally weighted paired **day means**, never race reweighting. Fewer than two paired days retain unknown sample SD; zero observed SD does not prove adequate sample size or zero future variance.

The standard-normal lower-tail/upper-tail function is a mathematical identity diagnostic only. It does not implement or validate a confirmatory z-test, daily independence, critical-value choice, optional stopping, pass decision or performance claim. No unresolved F5 threshold is filled by this function.

## Reproduction and claims for root REVIEW_GUIDE

Run from the isolated repository with a prepared Python 3.12 or 3.14 interpreter:

```sh
PYTHONPATH=development/model11 python -B -m unittest discover -s development/model11/tests -p test_preintegration_authority.py -v
```

1. **Pinned sole authority** — `AuthorityTests.test_projection_uses_pinned_decisions_and_keeps_eight_open_values_null` and tampering tests. Expect decided values, exactly eight null OPEN values, and HOLD for altered bytes. Evidence: target test log, pinned reference, authority.py and final artifact inventory.
2. **No history rewrite or fabricated approval** — provenance and frozen-v007A test. Expect original A hash unchanged, two distinct routes, original SHA/receipt null, all GO flags false. Evidence: override JSON and test log.
3. **Sign/SD correctness** — `SignTests` known vectors and inverse conversion. Expect opposite means, equal SD, negative-pilot ↔ positive-M0 favorable direction, unknown/zero dispersion kept distinct. Evidence: signs.py and test log.
4. **Correct one-sided orientation** — tail identity tests. Expect lower pilot tail equals upper M0 tail under the stated reference identity, actual_test_performed=false and test_pass=null. Evidence: test log. This is not evidence that actual holdout inference assumptions hold.

## External gates and shortest resolution steps

| Gate | Owner / required evidence | Minimal resolution steps |
| --- | --- | --- |
| Eight M1 OPEN decisions | HQ14, Claude, Andy; future approved policy decisions after separately approved pilot evidence | 1. Obtain approved private pilot summary. 2. Review uncertainty/dependence. 3. Decide eight items without reusing holdout. 4. Issue a new reviewable ledger and separate integration approval. No values are proposed here. |
| Original source linkage | HQ14/Claude; actual available witness/provenance evidence | 1. Compare the two stated routes. 2. Record supported linkage, or leave unavailable source SHA/receipt null. Do not manufacture a missing original. |
| Integration and execution | Andy with HQ14/Claude review; fixed commits, source mapping, sealed evaluation plan and explicit individual GO | 1. Review these separate components. 2. Approve exact integration scope. 3. Run approved combined regression. 4. Obtain separate data/Shadow/holdout GO. No current operation follows automatically. |

Implementation and synthetic test completion are separate from Claude independent review and every execution gate. Final measured counts/runtime/bytes/SHA belong to the root's retained logs and manifest. This document does not predict those counts or claim actual data validation.
