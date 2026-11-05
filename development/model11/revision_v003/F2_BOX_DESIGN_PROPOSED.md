# F2: future conservative BOX study — design only

**Status: PROPOSED / NOT IMPLEMENTED / NOT ADOPTED.** This document does not
change an existing selector, BOX Ver.1, the existing `box_v11_research`, Model
1.0, a forecast, or a performance result. F1/F3/F4 code corrections are a
separate deliverable; completing those corrections does not approve F2. No
real data, production service, or formal prediction original was consulted.
HQ14 and Claude must review the protocol before real-data testing, and Andy's
separate GO remains necessary for any eventual production action.

## Hypothesis and independent identity

A new future candidate, provisionally named
`BOX11_COVERAGE_RISK_EV_PROPOSED_V001`, would test whether a conservative
coverage gate and an explicit uncertainty penalty improve the usefulness of a
three-boat BOX policy. Improvement is a hypothesis. More selective betting can
raise conditional hit rate or ROI while reducing total net return, so those
statistics alone cannot establish improvement.

This candidate must have its own implementation path, config hash, version,
forecast fields, fixtures, and study entry. It must not replace or silently
alter `box_v11_research`, Mechanical BOX, automatic five-appearance BOX, or
externally supplied formal Human BOX. Manual Human-input research remains a
separate strategy with its own predeadline origin evidence. Neither automated
method is relabelled as the formal Human BOX Ver.1.

## Frozen input and probability provenance

Use the F1 walk-forward-selected **`P_shrunk`** for that race, with the selected
model/alpha/temperature/market-weight, fixed course policy, and exact forecast
SHA recorded. Configuration selection must finish before the test cutoff.
The probability stage name is part of the evidence; `P_model`, `P_calibrated`,
or an old/default blend must not be substituted and called `P_shrunk`.

The initial proposed study scope is six active boats and all 120 ordered
triples. Missing, stale, incomplete, or invalid lock-time odds make `P_shrunk`
or expected return unavailable under the existing gate: emit an unavailable
candidate / known SKIP decision with reasons, not made-up odds or a silently
renamed fallback. A separate market-free study would require another protocol.
This research scope does not change existing scratch/cancellation behavior.

All feature, course, state, odds, and manual-input acquired/available/revision
times must be available by prediction time, and prediction must precede the
deadline. Results, final payouts, and later corrections are evaluation data
only. A future BOX module must consume a frozen prediction object; it must not
receive an outcome or fit on the race being predicted.

## Candidate calculation proposed for later implementation

Enumerate the 20 unordered three-boat sets `S` from six active boats. Each set
contains exactly its six ordered permutations `T(S)`. Use separate research
stakes of 100 yen per ticket, 600 yen per BOX.

For a valid distribution `p` and lock-time gross-return multiples `o_t`:

```
C(S) = sum(p_t for t in T(S))
expected_return_yen(S) = 100 * sum(p_t * o_t for t in T(S))
expected_net_yen(S) = expected_return_yen(S) - 600
```

`C` is predicted coverage, not observed accuracy. `expected_net_yen` is a
conditional model estimate, not a guaranteed or realized return. Payout and
refund settlement remain separate after the result is final.

An uncertainty procedure must be specified and reviewed before use. One
PROPOSED research approach is a fixed-seed block bootstrap of **training**
days or meetings, refitting a fixed already-selected configuration and
predicting the same predeadline input. No test outcome may enter resampling,
parameter choice, or uncertainty estimation. Candidate parameters are frozen;
refitting on a sample does not authorize a new search on test results.

Let `u_C(S)` and `u_U(S)` be explicitly defined uncertainty/stability measures
in coverage units and yen respectively. A possible score is:

```
coverage_score(S) = C(S) - lambda_C * u_C(S)
net_score_yen(S) = expected_net_yen(S) - lambda_U * u_U(S)
eligible(S) = coverage_score(S) >= C_min and net_score_yen(S) >= U_min
```

Choose the eligible set with the greatest `net_score_yen`; break exact ties by
coverage-score then lexicographic boat tuple, with the order frozen in the
protocol. If none qualifies, record SKIP with no fabricated selected BOX.
An alternate coverage-first objective would be another candidate, not an
unreported change to this rule.

These scores are **heuristic risk penalties**, not statistically validated
confidence bounds. Refit dispersion omits model misspecification, market
miscalibration, odds-snapshot uncertainty, and parameter-selection uncertainty.
Those omissions must be reported. Unknown uncertainty is not zero. A procedure
unable to quantify the required uncertainty must leave the candidate
UNVERIFIED/unavailable rather than bypassing the gate.

At F1 market weight 1, `P_shrunk` is exactly `P_market` on a complete valid-market
race. Refitting the model then produces zero conditional model-refit variation,
but that does **not** prove zero total uncertainty or calibrated true chances.
Market/calibration uncertainty needs separate reviewed treatment. Under simple
normalized inverse-odds market probabilities, `p_t * o_t` is constant across
tickets within a race; high odds alone therefore do not create value. A
market-only candidate must be labelled MARKET_ONLY, not a model improvement.

## Illustrative controls — none adopted

| Field | Illustrative proposal | Rationale and limitation |
| --- | --- | --- |
| `C_min` | 0.10 | Twice the uniform six-ticket coverage `6/120=0.05`; a simple screening example, not a learned optimum or validated threshold. |
| `U_min` | 0 yen | Requires nonnegative penalized estimated net before BET; estimated EV remains unverified. |
| `lambda_C`, `lambda_U` | 1 each | One dispersion-unit penalty for an initial fixed comparison; no claimed confidence level. |
| Bootstrap replicates | 200 | A reproducible software/pilot budget only; precision and dependence need review. |
| Distinct training day clusters | At least 20 | A proposed diagnostic floor; 20 clusters do not prove sample adequacy or independent days. |
| Sensitivity comparator | Same rule with both lambdas 0 | Isolates the proposed penalty; no broad parameter optimization on test data. |

Changing any of these choices after observing evaluation returns creates a new
exploratory protocol/version and consumes fresh future evaluation data. They
must not be copied into default code or treated as approved by this document.
Minimum training size, variance estimator, meeting dependence, handling of
unknown market/calibration uncertainty, and the final candidate budget remain
OPEN. F5 governs the wider selection/holdout protocol.

## Controlled comparisons

Freeze all comparator outputs before results. Use the same valid race inputs,
course policy, selected probability stream, lock-time odds, and stake for
paired method comparisons. Proposed controls are:

1. Existing `box_v11_research`, unchanged and identified by its source commit.
2. Existing independent Mechanical research BOX and automatic five-appearance
   research BOX, each retaining its own name and rule.
3. A market-only BOX baseline with a prespecified objective and tie break.
4. Supplied formal BOX Ver.1 fixed outputs only when HQ14 independently verifies
   their exact bytes/source/predeadline evidence; otherwise comparison is OPEN.

The lambda-zero ablation is a separate explicitly counted comparison. No
candidate is selected by whichever metric happens to look best afterward.
Initial primary scoring, multiplicity family, and whether this is a policy
value study or a pure probability-coverage study require preregistration.
Normal-five and BOX results are never pooled; cross-method overlapping tickets
are identified but do not form an assumed combined purchase portfolio.

Report all of the following, with source/date/meeting scope and missing counts:

- Scheduled opportunities, eligible inputs, emitted BOX count, BET count, SKIP
  count, and unavailable count. Missing data is different from a known SKIP.
- Predicted coverage and its calibration against the selected BOX hit event;
  conditional hit rate must retain its emitted-BOX denominator.
- Standalone 600-yen counterfactual ledger for emitted BOXes, actual policy
  ledger with zero action cashflow only on known SKIP, and net per scheduled
  eligible opportunity. This prevents a high conditional ROI from hiding low
  participation or lost total value.
- Hit rate, payout/refund, net, return rate, ROI, and drawdown separately for
  every method. Unknown payouts/refunds are not replaced by zero.
- Paired differences on common races **and** full-population participation
  differences. Do not silently discard difficult races from one method only.
- Equal-day and meeting-block uncertainty, with preregistered cluster units.
  Resampling and multiple-testing choices are fixed before final evaluation.

## Readiness and STOP

This is design READY for discussion only. Implementation, real-data validation,
Claude review, formal adoption, production GO, and CLOSE remain separate.
STOP/HOLD applies to missing course/probability provenance, invalid odds,
unexplained source or distribution changes, unknown required uncertainty,
outcome leakage, absent predeadline forecast proof, incompatible cohort
matching, or an unapproved parameter/protocol change. An unavailable candidate
does not trigger automatic fallback to an existing formal BOX or a task edit.

HQ14/Claude must approve the candidate identity, uncertainty definition,
thresholds, search budget, comparator/multiplicity family, minimum samples,
chronological split, receipt storage, and unused-future evaluation plan before
any real-data run. No performance gain or application permission is claimed.
