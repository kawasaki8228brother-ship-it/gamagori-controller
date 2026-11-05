# Fixed-portfolio EV sensitivity: PROPOSED offline preparation

The old candidate, its probability distributions, configuration, selected tickets, and BET/SKIP decisions remain byte-for-byte unchanged. This addition audits those decisions and creates a separately identified **PROPOSED** risk overlay. It does not buy, send, save to production, or promote anything. Real-data validity, frozen Model 1.0/BOX comparison, prospective performance, and production GO remain **OPEN / UNVERIFIED**.

## Interfaces and information barrier

```python
audit_forecast(forecast, race, scenario_config=None) -> dict
diagnose(forecasts, races, outcomes=None, scenarios=None) -> dict
```

`forecast` is the original sealed predictor output, without `actual` and with `first_course=None`. Its original `prediction_sha256` must still match canonical serialization excluding that digest. The separately supplied canonical race must match `input_sha256` and the forecast's identity/times. Distribution domains, source snapshot eligibility, admitted market probabilities, four portfolio domains/stakes, declared coverage, and declared EV are checked. These are self-consistency checks; valid hashes and supplied timestamps do **not** prove external authenticity or independent predeadline execution.

`audit_forecast` does not accept outcomes. It does not reselect tickets or fit parameters. Embedded outcomes and outcome-derived first-course values are rejected. `diagnose` first computes all audits and risk decisions without passing labels into that block, then joins optional final outcomes for a separate settlement report. Forecast/race/outcome inputs are not mutated. Arrays are joined by unique race ID; duplicate IDs fail closed. `races` and `outcomes` may contain additional training dates, so callers can pass the complete synthetic dataset. Missing/invalid inputs, missing admitted odds, and inconsistent observations remain UNVERIFIED; missing money, missing labels, and missing intervention evidence are never replaced with zero.

The methods `five`, `human_research`, `mechanical_research`, and `box_v11_research` remain separate. Ordinary five costs 500 yen and each three-boat/six-permutation BOX costs 600 yen, with 100 yen per ticket. There is no combined ROI that double-counts overlapping tickets or strategies. Formal Human/Mechanical BOX Ver.1 is not reconstructed.

## Fixed illustrative stress grid

The default Cartesian grid has 27 scenarios:

| Axis | PROPOSED values | Meaning |
| --- | --- | --- |
| Market pooling weight `w` | 0, 0.5, 1 | Arithmetic probability-error stress toward observed reciprocal-odds market probabilities |
| Uniform flattening weight `u` | 0, 0.25, 0.5 | Probability-error stress toward the uniform complete-domain distribution |
| Gross-odds multiplier `h` | 1, 0.9, 0.75 | Uniform downward price drift / haircut; no favorable drift is invented |

For each fixed ticket `t`, the diagnostic distribution is

`q(t) = (1-u) * ((1-w) * P_selected(t) + w * P_market(t)) + u / domain_size`.

This arithmetic mixture is an alternative stress assumption, not a replacement for the old candidate's loglinear market integration. It is not calibrated from these outcomes. If market is missing, scenarios requiring market are UNVERIFIED; zero-weight scenarios can use the supplied model directly. Odds absence keeps expected monetary return null. No absent market probability is filled with zero.

For fixed portfolio `S`, coverage is `sum(q(t) for t in S)`, expected gross return is `sum(100*q(t)*odds(t)*h for t in S)`, and expected net subtracts the unchanged 500/600-yen stake. The report records coverage, EV, ROI, and concentration for every scenario; it does not display an outcome-selected "best" grid point. At fixed probabilities, reducing `h` must monotonically reduce expected return; unit tests verify this. Probability shocks need not be monotone because flattening can increase or decrease a particular tail probability.

Single-ticket concentration is the largest ticket's share of portfolio expected gross return. Selected maximum gross odds and the probability/EV share dependent on odds above the declared high-payoff cap are also recorded. These diagnose how a nominally attractive EV may depend on low hit probability and rare, large payouts. They establish neither the true probabilities nor the cause of observed losses.

Custom `scenario_config` / `scenarios` accepts only `protocol_id`, `market_weights`, `uniform_weights`, `odds_multipliers`, `risk_policy`, and `preregistration_reference`. Grids must include the zero-weight / unharmed-price baseline; odds multipliers must be positive and at most one. Unknown keys and nonfinite values fail closed. Every changed protocol receives a different canonical hash. A supplied reference or hash is not evidence of external registration.

## Separate stricter policy candidate

Candidate IDs have the form `EV_ROBUST_OVERLAY_PROPOSED_V002:<protocol hash prefix>:<method>`. The old method's decision is reported as `original_bet_decision` and is never overwritten. An original SKIP cannot be upgraded to BET.

The illustrative defaults require coverage at least 0.05, maximum single-ticket EV share at most 0.5, maximum selected gross odds at most 1000, and ROI strictly above zero in **every** stress scenario. The coverage and concentration gates also consider the worst stress case. A known failure produces a proposed SKIP; incomplete risk inputs produce UNVERIFIED. An unchanged original BET can pass the new overlay only if all declared gates pass. All thresholds and the overlay remain **PROPOSED / NOT ADOPTED**; no winning tickets or outcomes enter the rule.

**The grid and these risk thresholds are illustrative examples, not optimized against the observed 0/40, hit rate, log-loss, or ROI. The 40-race synthetic aggregate was already known before this preparation task. Therefore neither this grid nor this overlay is prospectively registered for those already seen 40 races.** The software fixes a supplied configuration before its optional label-evaluation block; this code structure is not historical proof that a person chose it before seeing an aggregate. A future confirmatory evaluation requires independent locking and approval before new, unused observations arrive.

The full-market scenario is deliberately severe. In this generator, synthetic odds were created from market probabilities using an invented payout factor approximately 0.78. At `w=1, u=0, h=0.75`, expected return/stake is consequently approximately `0.78*0.75 = 0.585`, or ROI -0.415, for every fixed portfolio. Requiring positive ROI in every scenario therefore makes **all-SKIP likely by construction**. That demonstrates the policy's conservatism, not improved prediction or profitable strategy selection. Comparing the zero spending/loss of all-SKIP against a losing candidate is not a fair profit-improvement claim; it also forgoes the positive synthetic ordinary-five result. No production recommendation or superiority claim follows.

## Observed synthetic discrepancy and limits

The root's regenerated 36-day, two-race/day fixture produces the same 40 evaluated forecasts as the frozen old package. The initial preparation smoke report observed these descriptive quantities:

| BOX Ver.1.1 research quantity | Synthetic observation |
| --- | ---: |
| All fixed portfolios evaluated | 40 |
| Observed hits | 0 |
| Predicted sum of hit probabilities | 1.0662399168399765 |
| Predicted expected net over all fixed portfolios | 28,674.395306245264 yen |
| Realized net over all 40 fixed portfolios | -24,000 yen |
| Original BET subset | 39 portfolios, -23,400 yen |
| New illustrative overlay | 40 SKIP, 0 BET |

The expected hit count implies average predicted coverage about 2.67%, despite the large nominal expected return. This is consistent with high payout dependence and substantial variance as a possible explanation; it is not proof of a causal explanation. The report's product of `1-coverage` is approximately 0.3344 for zero hits **only if** the supplied model probabilities are correct and outcomes are conditionally independent. It is labelled hypothetical, not a p-value: common-day dependence, model misspecification, payout selection, and repeated research are unaccounted for. Zero hits alone does not identify an implementation bug or validate the model.

Across the same 40 matched synthetic outcomes, observed mean joint log-loss `P_model - P_market` was about +0.4690429898; the market baseline had lower observed loss. This generator intentionally creates its market from a noisy latent synthetic distribution, so that result cannot establish a real-market advantage or show that Model 1.1 beats a frozen predecessor. Paired comparisons use the same known labels, expose missing/infinite losses, and perform no significance test, optimization, or automatic model choice.

Expected EV and realized settlement remain separate fields. Settlement uses independently supplied final payout and refund records, not snapshot odds as a substitute for the final payout. Refunds return 100 yen per actually selected refunded ticket; a refunded winner, unknown refunds/payout, domain mismatch, early label availability, or nonfinal outcome is UNVERIFIED. Predicted EV does not model unknown future cancellations or refunds. All-method and original-BET-subset settlement are separately reported, with known and unknown observation counts.

## Reproduction and remaining gates

From the package directory, run `python -B -m unittest discover -s tests -p test_preparation_sensitivity.py -v`. The tests exercise input immutability, original-ticket/config preservation, baseline EV equality, the fixed grid, monotone odds haircuts, independent policy identity, null EV for missing odds, invalid/missing data, refund arithmetic, and the fact that arbitrary outcome changes cannot change pre-outcome audits or risk decisions. Passing these tests is a software observation, not a performance PASS.

The local CLI is `python -B -m model11.preparation.cli diagnose --forecasts <forecasts.json> --races <races.json> --outcomes <outcomes.json> --output <new-audit.json>`. Omitting `--outcomes` leaves settlement and log-loss unknown while still permitting pre-outcome diagnostics. The complete synthetic integration run is `python -B -m model11.preparation.cli demo --output-dir <new-directory>`; its baseline-preservation receipt checks the frozen candidate before writing separate new preparation evidence. No network, actual bets, production writer, credentials, real input source, or external storage is used by this component.

STOP/HOLD: any frozen-source change, malformed/seal-mismatched forecast, input hash mismatch, identity/availability error, incomplete or stale market, invalid portfolio, unexplained EV discrepancy, duplicated identity, unknown settlement, or external-authenticity uncertainty must remain explicitly unresolved. No automatic threshold tuning, ticket reselection, old forecast rewriting, actual-data validation PASS, old-model superiority claim, deployment GO, or state promotion is authorized. HQ14 must separately approve private real-data use and independent future protocol registration; Claude reviews methodology and Andy retains the individual application GO.
