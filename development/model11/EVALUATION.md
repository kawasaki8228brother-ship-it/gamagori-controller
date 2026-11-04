# Model 1.1 offline evaluation contract

This module computes descriptive research metrics. It cannot certify improvement,
authenticate a historic prediction, place bets, modify a writer, or grant GO.
The included vectors are synthetic. Model 1.0 and BOX Ver.1 remain frozen.

Run from this directory:

```sh
python -B -m unittest discover -s tests -p test_metrics.py -v
```

`model11.metrics.evaluate_records(records, config=None)` accepts the shared root
engine records. `actual` must be final and match `race_id` and `target_date`.
If the outcome includes a `source`, it must match the record's source. A missing
outcome source does not prove independent source provenance. The caller must
validate race input, forecast chronology, observation/revision cutoffs, and
walk-forward isolation before evaluation; this evaluator cannot independently
authenticate those claims. Duplicate `(race_id, source)` pairs are all excluded
with explicit errors, rather than keeping whichever copy happens to be first.
One candidate is evaluated per call.

## Separate ledgers and known money

The four report keys are `five`, `human_research`, `mechanical_research`, and
`box_v11_research`. The first requires five unique valid ordered tickets; each
BOX requires exactly all six permutations of its three distinct boats. A method
with duplicate tickets is unavailable, not a cheaper stake. Each ticket costs
100 research yen, so five costs 500 and each BOX costs 600. Common tickets across
methods are evaluated in separate hypothetical ledgers. There is no combined
portfolio total and no implied decision to buy overlapping methods together.

For each method:

- `hit_n / n` is ordered-triple hit rate, distinct from profitability.
- `gross_payout_yen` uses the official `payout_per_100` once if selected.
- `refund_yen` returns 100 for each selected refunded ticket.
- `return_yen = gross_payout_yen + refund_yen`.
- `return_rate = return_yen / stake_yen`; `roi = net_yen / stake_yen`.
- A winning result also marked refunded is an inconsistent input and excluded.
- Missing refund information makes money unknown. Missing winning payout makes
  money unknown. On a known miss, winning payout is unnecessary: selected payout
  is logically zero, not an imputed missing value.

Monetary totals use explicitly identified known observations only; `money_n`,
`money_unknown_n`, `money_scope`, method coverage, and errors must travel with
the result. A partial-cohort ROI does not describe all input races. An empty
cohort has null totals/rates, not zero performance.

`bet` describes selected BET races. `skip_counterfactual` describes hypothetical
outcomes on SKIP races. `action` includes BET cashflow and zero stake/cashflow for
explicit SKIP; unknown decisions remain UNVERIFIED. An all-SKIP cohort has known
zero action stake/net but undefined ROI. These are simulations, not transaction
receipts. Each BOX needs its own `bet_decision`; the five-ticket decision is not
silently propagated to BOX.

Maximum drawdown starts from cumulative net zero, sorts by timezone-aware
`prediction_at`, and measures the greatest peak-to-trough cumulative loss.
Missing money, missing chronology, or tied timestamps make it UNVERIFIED rather
than inventing intraday ordering. Per-course groups use supplied `first_course`;
unknown course has its own group. Popularity means the actual outcome's ex-post
market probability competition rank (tied probabilities share a rank), grouped
1–3, 4–10, 11–30, 31+. These diagnostics are never predictor features.

## Proper scores and zeros

Each probability stage (`P_raw`, `P_model`, `P_market`, `P_shrunk`) is evaluated
separately. A distribution must contain every ordered permutation of its 3–6
active boats, contain finite probabilities in [0,1], and sum to 1 within 1e-10.
Missing/invalid probabilities are not renormalized or filled. If active boats
are supplied, the entire domain must match them. Outcome outside the domain is
an error.

Joint log loss is `-ln(P(actual))`; multiclass Brier is the sum over the full
domain of `(p_i - indicator_i)^2` (not divided by 120). Zero probability on the
actual outcome produces true infinite log loss. JSON represents this by
`status=INFINITE`, `value=null`, and positive `infinite_count`. It remains an
observed score and is never omitted to improve the mean. Brier remains finite.
An aggregate with any infinite score stays infinite.

Actual-prefix conditional probabilities are derived from the joint distribution:

```
p1 = sum(P(a,j,k))
p2_given_1 = sum(P(a,b,k)) / p1
p3_given_12 = P(a,b,c) / sum(P(a,b,k))
```

Their individual log losses sum to the joint loss when all denominators are
positive. A zero numerator contributes infinite loss at its first impossible
stage. Later conditionals with a zero denominator are undefined and explicitly
missing; no arbitrary conditional probability is invented. Coverage is reported
for every stage.

Calibration is top-label equal-width reliability, with forecast confidence and
observed top-label accuracy per bin and ECE. Default ten bins are a PROPOSED
descriptive choice, not a validated model-selection threshold. This does not
claim exhaustive per-ticket or per-course calibration, and small synthetic
cohorts provide no reliability evidence.

Market comparison uses only matched valid candidate/market pairs. Positive
`MARKET_LOSS_MINUS_CANDIDATE_LOSS` means lower candidate loss on those pairs.
Missing market observations reduce paired coverage. A nonfinite log-loss pair
makes the reported paired mean difference UNVERIFIED/null; finite pairs are not
silently used as an apparently complete favorable comparison. No improvement
PASS or superiority label is emitted.

## Day blocks and uncertainty

Intervals are disabled unless the caller supplies an explicit configuration:

```python
{
    "day_bootstrap": {
        "enabled": True,
        "confidence": 0.95,
        "replicates": 2000,
        "min_clusters": 20,
        "seed": 20261105,
        "preregistration_reference": "PROPOSED: replace with reviewed study ID"
    }
}
```

All numbers above are PROPOSED examples, not approved study criteria. The code
requires confidence strictly between zero and one, 100–100000 replicates, at
least two required day clusters, an integer seed, and an explicit reference.
It resamples whole target-date clusters with replacement and recomputes a
race-weighted mean. It reports percentile intervals for each standalone hit
rate and paired candidate-versus-market Brier difference. These are exploratory,
not formal superiority evidence. Fewer clusters than configured remain
UNVERIFIED. Results are conditional on the observed cohort and cannot establish
sample adequacy or independence between dates. Multiple comparisons, seasonal
drift, high-variance payouts, non-inferiority margins, and final sample-size
planning require independent preregistration. Return/ROI intervals and a formal
sequential stopping procedure are OPEN, not falsely supplied by a hit-rate CI.

## Frozen legacy fixed-output adapter

`legacy_adapter(record, profile)` never reimplements old Model 1.0 or BOX Ver.1.
Without verified source material it returns OPEN. A supplied reference profile
must include `verified=True`, `raw_bytes` as actual bytes, the matching full
`sha256`, `source_identity`, and `verification_evidence`. Supplied fixed legacy
output must bind the same race/date/source, that source identity and reference
hash, and a timezone-aware `prediction_at` strictly before the record deadline.
It must contain five or six unique valid tickets; a six-ticket output must also
identify its method and valid BOX boats to enter method comparison.

These checks establish local input agreement only. `external_authenticity`
remains `UNVERIFIED_BY_LOCAL_CODE`, and reproduction remains UNVERIFIED. The
raw reference bytes are never returned in reports. Method-compatible supplied
fixed outputs can be compared through separate metrics and paired hit
differences; no old prediction is generated or overwritten. No verified real
legacy profile is bundled, so actual Model1.0/BOXv1 comparison remains OPEN.

## STOP and review boundaries

Invalid bindings, duplicates, incomplete distributions, inconsistent refunds,
missing forecast proof, ambiguous chronology, or unverified reference identity
must be reviewed using `record_issues` and coverage before interpreting scores.
Zero probability is a scored model failure, not a reason to discard a race.
No real data, external connection, credential, writer, or production setting is
used by this module. Evidence of improvement requires unused future meeting
data, reviewed chronology and receipts, sufficient day clusters, HQ14/Claude
review, and a separate Andy approval. `production_go` always remains false.
