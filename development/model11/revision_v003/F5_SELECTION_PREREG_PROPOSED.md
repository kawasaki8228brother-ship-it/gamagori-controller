# F5: selection adequacy and expanded-grid preregistration proposal

**PROPOSED / real-data readiness HOLD.** This is a design document, not an
adopted minimum-sample rule, a source-code change, a performance verdict, or a
production GO. F1/F3/F4 fix software behavior; they do not establish statistical
adequacy. Existing 88 artifacts remain unchanged. No real data or service was
used in these calculations. HQ14/Claude must review and approve the final
protocol before private real-data testing.

## Verified software structure versus inference

The old default grid is:

```
2 model families * 2 course-prior alphas * 3 temperatures * 3 market weights
= 36 nominal prediction configurations
```

F1 expands the market weights to `[0, 0.25, 0.5, 0.75, 0.9, 1.0]`:

```
2 * 2 * 3 * 6 = 72 nominal configurations per selection fold
```

These are configurations, not 72 independently trained models or 72 independent
statistical experiments. There are four model/alpha fits, each combined with
three temperatures and six market weights. Their errors and selection scores
are strongly correlated.

On a selection cohort with complete valid market data, all twelve weight-1
configurations (`2*2*3`) produce exactly the same scored distribution:
`P_shrunk = P_market`. Thus there are at most:

```
60 nonunit-weight configurations + 1 MARKET_ONLY equivalence class = 61
structurally distinct scored probability streams
```

The twelve copies must not count as twelve independent market baselines,
twelve wins, or extra evidence for a champion. A chosen weight-1 champion is
labelled MARKET_ONLY, with model contribution zero; against the same market
comparator its probability score difference is exactly zero. Different model
metadata or raw/model distributions do not turn identical selected market
forecasts into separate improvements.

This 61-class statement has an important scope condition. On unavailable-market
races, the existing explicit model-only fallback uses calibrated model
probabilities and `P_shrunk` is unavailable. The twelve weight-1 parameter labels
are then not all the same scored stream if a fallback score is substituted.
For the proposed primary market-comparison selection, use a prespecified
complete-valid-market cohort and report its coverage. Keep unavailable-market
behavior as a separate diagnostic cohort; do not call it MARKET_ONLY or claim
the 61-class reduction there. If the approved primary selection policy instead
includes fallback scores, its equivalence/search-family definition must be
revised before observing outcomes.

Other apparent score ties on a small selection sample are **not** proof of
structural equivalence. Identical scores can arise from different forecasts.
Do not reduce multiplicity after looking at favorable results. Only analytic
identity under the fixed domain/policy, established before outcome inspection,
can define an equivalence class. Keep all nominal rows for audit and map them
to their prespecified equivalence ID; select a deterministic representative.

## Why the current tiny example is not selection evidence

The original software demonstration has four selection days and two synthetic
races per day: eight selection races. A 72-row score table from eight races
is useful for checking execution, endpoint behavior, hash preservation, and
chronology. It does not validate the selected parameters. Comparing 72 nominal
configurations against eight observations can select noise. The descriptive
72/8=9 ratio (or 61/8=7.625 on the complete-market scope) is **not** a formal
sample-size or degrees-of-freedom formula. Races within a day/meeting are not
independent; four selection days are only four day clusters and may be fewer
effectively independent meeting clusters.

Synthetic loss differences, selection stability, ROI, or a repeatedly chosen
weight are not evidence of real predictive improvement. Increasing the grid
alone improves search coverage and can worsen selection optimism. Real-data
selection remains HOLD until the adequacy protocol is adopted.

## Numeric sample proposals for review

A possible **screening floor**, not an adequacy guarantee, is:

- At least **240** valid matched selection races with complete required
  predeadline inputs and market pairing.
- At least **20** distinct selection day clusters across at least **four**
  separate meetings, with meeting/date coverage reported.
- Both the race and cluster floors must be met; unknown/invalid observations
  do not count toward either. Do not fill missing races or count A/B copies as
  independent races.

Rationale: 240 races corresponds to 20 full 12-race venue days, or about 40
days at six eligible races/day, or 120 days at the two-race/day software-demo
rate. It reduces reliance on eight observations and gives a starting point
for day/meeting variation diagnostics. Twenty day clusters and four meetings
are rough diagnostic floors, **not** proof that 61 alternatives can be reliably
selected. Sparse eligible markets, serial correlation, rare outcomes, and drift
can require materially more data. The numerical floor is a proposal for review;
no code or report may label it an approved PASS threshold.

Selection precision must be planned using a private historical/pilot period
that is entirely earlier than model selection and holdout. For illustration,
let `s_day` be the standard deviation of equal-day paired log-loss differences
and `h` a desired screening half-width. A rough independent-day normal
approximation is:

```
required_day_clusters = ceil((z_(1 - 0.05/(2*K)) * s_day / h)^2)
```

Here `K` is a **fixed** screening family, and a Bonferroni normal critical value
is only a conservative planning illustration. It is not a validated
post-selection interval, a power calculation, or a substitute for dependence
review. The following arithmetic uses invented variances, not measured data:

| Fixed family K | Assumed s_day (nats) | Half-width h (nats) | Approximate day clusters |
| --- | --- | --- | --- |
| 1 | 0.10 | 0.05 | 16 |
| 1 | 0.10 | 0.02 | 97 |
| 11 | 0.10 | 0.02 | 202 |
| 61 | 0.10 | 0.02 | 280 |
| 1 | 0.20 | 0.02 | 385 |

The table shows why a convenient 20-day floor cannot imply precise selection
among a large family. Unknown/zero pilot variance remains UNVERIFIED, never a
zero-sample requirement. Day correlation can make these approximations
optimistic; meeting-level blocks or effective-sample adjustments need review.
Final unused-holdout power/non-inferiority planning is separate, using the
preregistered effect, margin, variance, sidedness, power, and multiplicity.

## Candidate budget alternatives — choose before real outcomes

No alternative is adopted here:

1. **Full 72-row grid:** retain all required endpoint/weight coverage for
   synthetic diagnostics. Real selection from its up-to-61 complete-market
   equivalence classes is HOLD pending sample/stability review.
2. **Restricted real-study grid:** for example two model families, one fixed
   alpha, one fixed temperature, and all six weights gives 12 nominal rows,
   or 11 complete-market equivalence classes. Choosing which alpha/temperature
   to freeze must use theory or a disjoint earlier pilot, not favorable final
   selection/holdout results. This is a separate registered protocol and does
   not remove F1's expanded software capability.
3. **Single frozen champion:** use development/inner selection to freeze one
   complete algorithm and compare it with the market on a genuinely unused
   future holdout. No retuning or champion replacement after opening it.

Budget accounting must include every inspected model, alpha, temperature,
market weight, selection objective, feature/course-policy variant, seed search,
BOX threshold, uncertainty method, and repeated informal trial. F2 future BOX
choices are not hidden inside the 72-row probability grid. They form an
explicit additional family, with their own budget and unused evaluation plan.
Failed or abandoned trials remain in the audit history; deleting them does not
reset the search budget. A nominal budget cannot be expanded after seeing a
disappointing score while keeping the same confirmatory protocol ID.

## Nested chronology and evidence to freeze

Before real data are opened for selection, register exact IDs/time cutoffs,
not a random race split:

1. Earlier development/pilot data: feature engineering, variance/dependence
   study, and a fixed candidate budget. Their outcomes never enter final
   inference as untouched data.
2. Training prefix: fit only observations/outcomes available before selection
   prediction time. All training-feature provenance and course policy hashes
   are validated. No result or payout is a predictor feature.
3. Inner chronological selection blocks: evaluate fixed candidate configs on
   later days; calibration/market weights are selected here only. Use
   prespecified equal-day proper-score objective and tie break. Market coverage
   and nonfinite losses remain explicit. A zero actual probability is infinite
   loss, not a dropped race or an epsilon repair.
4. Outer chronological validation blocks: freeze the inner-selected algorithm
   before each future block. Record every inner choice and each outer forecast
   hash before results. A prior outer block may become later training history
   only under a predeclared prequential protocol; it ceases to be untouched.
5. Sealed future final evaluation: once the champion and its entire protocol
   are fixed, use separate unused meetings. No selection on this period. If
   results trigger redesign, the opened period is development evidence and a
   new future final evaluation is required.

Candidate grid, equivalence map, scoring cohort, missing-data rules, primary
estimand, tie policy, fitting budget, all random seeds, course policy, cutoff
timestamps, training/selection/holdout ID hashes, and forecast schema must be
sealed with independent receipt/readback evidence. A local self-hash checks
consistency only and cannot prove sealing time or external authenticity.

The proposed primary score is the **equal-day paired joint-120 log-loss
difference, market minus selected `P_shrunk`**, positive when the candidate has
lower loss. Keep joint Brier, conditional first/second/third losses,
calibration, five-ticket/BOX hit rates, ROI, drawdown, and BET/SKIP participation
as prespecified secondary/descriptive metrics. Do not switch the champion's
selection objective to ROI after seeing results. Complete-market cohort and
unavailable-market reporting are fixed before evaluation; no favorable
post-hoc cohort filtering is allowed.

## Multiplicity, minimum clusters, and stopping

For final inference, one option is a **single frozen champion** versus one
market baseline, with one primary hypothesis. Model-family comparisons,
formal Model1.0/BOXv1 comparisons, F2 policies, and secondary metrics remain
descriptive unless placed in a fixed family with an approved adjustment such
as Holm. Exact MARKET_ONLY duplicates collapse to one predefined hypothesis;
they do not increase apparent independent support. Distinct source A/B
comparisons remain separate paired ledgers, never an artificial doubled N.

For the proposal, keep at least 20 day clusters/four meetings as a diagnostic
minimum, and use the larger independently reviewed precision/power/dependence
requirement for the actual final plan. Bootstrap replicate count does not
increase the number of real clusters. Holdout effective N, expected race yield,
missingness, and meeting correlation must be reviewed before starting it.

Stop/HOLD on leakage, missing/ambiguous provenance, incompatible course policy,
unavailable pilot variance, inadequate clusters, changed eligibility rules,
unexpected configuration expansion, nonfinite primary comparisons, or lost
forecast/receipt evidence. No favorable optional stopping: fix evaluation end
dates/events and analysis looks in advance, or preregister a separately reviewed
sequential method. Insufficient data or an inconclusive result means postpone,
not lower the margin/sample threshold or optimize against the opened holdout.

## Approval fields still OPEN

HQ14/Claude must fill and independently review: protocol/version and approval
receipt; complete primary/cohort definition; adopted selection race/day/meeting
minimums; actual earlier pilot variance and dependence evidence; candidate
budget/equivalence map; exact split IDs/cutoffs; effect/non-inferiority margin;
sample-size and power rationale; fixed multiplicity family; stopping and missing
data rules; future predeadline evidence storage; and review dates. Until then
`selection_adequacy=UNVERIFIED_NOT_PREREGISTERED`, real-study readiness is HOLD,
performance improvement is UNVERIFIED, and production GO is false.
