# Five-ticket and BOX research contract

This module is an offline research prototype. All defaults and thresholds are **PROPOSED / NOT ADOPTED**. `BET` means only that a simulated risk gate passed; it authorizes neither a purchase nor production use. Synthetic unit-test success is functional evidence, not evidence of improved hit rate or profit.

## Ordinary five tickets

`select_five(dist, odds=None, config=None)` receives a complete normalized distribution over ordered triples of three to six active boats. Six active boats require all 120 permutations. Values must be finite and nonnegative, sum to one within 1e-10, and contain no repeated boat. Invalid domains are rejected rather than repaired.

The proposed default chooses four probability-ranked main tickets plus one supported value candidate. `main_count=3` changes that to three main plus two value candidates. Outside the main group a value candidate requires `p * gross_odds > 1 + min_value_edge`; default edge is 0.05. Candidates are ordered by expected gross return, then probability, then lexical ticket order. An unfilled value slot falls back to probability rank and is explicitly labelled `PROBABILITY_FALLBACK_NOT_HOLE`. Presentation `tickets` are sorted by first, second, then third boat; `selection_order` preserves algorithmic priority independently. No claim of a supported longshot is made without supporting odds. This functional rule is a new research hypothesis, not a reconstruction of Model 1.0.

Selection and BET/SKIP are separate. Each ordinary ticket assumes 100 yen; five tickets cost 500 yen. Expected gross return is `sum(100 * p * gross_odds)`, net return subtracts stake, and ROI is net/stake. Proposed BET gates require ROI **strictly above** `min_expected_roi` (default zero) and coverage at least `min_coverage` (default zero). A supported value ticket alone does not force BET. These thresholds have not been tuned or adopted.

Missing, partial, or unexpected-domain odds cause null EV and SKIP, including for tickets whose individual odds happen to exist. Invalid numeric odds cause a validation error. Odds are gross payout multiples, not implied probabilities or profit-only multiples. The upstream validator must establish as-of time, freshness, revision provenance, and absence of future information; this pure selector cannot infer those facts from a numeric dictionary.

## Three independent BOX research outputs

`build_boxes(race, dist, five, odds=None, config=None)` returns these separate portfolios:

- `human_research`: a **NOT_FORMAL_BOXV1** human-style research heuristic. It counts appearances of each boat across the ordinary five tickets, then first-position appearances, then boat number for deterministic ties. The first two become the core and the third becomes the insertion boat. Alternatively an explicitly supplied research manual input must have exactly `core`, `insertion`, `observed_at`, `acquired_at`, `available_at`, and `revision_at`. All four aware timestamps must be no later than prediction, acquisition must not follow availability, and prediction must precede deadline. Missing, extra, malformed, or future availability metadata is rejected explicitly. The report includes core, insertion, and ordinary-five appearance counts. This heuristic does not implement the frozen Human BOX Ver.1 rules.
- `mechanical_research`: enumerate every three-boat set and maximize the probability mass of its six permutations; ties use ascending boat tuple. It never reads or copies the Human choice. Equal final sets are allowed and are not made artificially different.
- `box_v11_research`: independently enumerate three-boat sets and maximize expected gross return when a full admitted odds snapshot exists. Tie breaks use probability mass then boat tuple. Without full odds, explicitly fall back to maximum probability mass with unknown EV and SKIP. This may equal Mechanical without implying that it copied Human or a frozen legacy rule.

Every BOX has three distinct boats, six ordered permutations, 100 yen per ticket, and a 600-yen stake. Coverage and expected return are calculated separately for each portfolio. `composition_difference=YES` means only that Human-style and Mechanical boat sets differ; NO means equality. Neither value expresses quality or superiority.

`overlap` reports each ordinary-five/BOX and BOX/BOX ticket intersection and the unique ticket union. Evaluators must report the strategies in separate cohorts, never add their overlapping portfolios and call that one strategy or double-count a hit. Refunds and confirmed payouts are outcome inputs for the evaluator, not information used in selection.

## Frozen BOX Ver.1 adapter boundary

`legacy_box_v1` is always `UNVERIFIED_ORIGINAL_BYTES_SHA_NOT_PROVIDED` and returns null Human and Mechanical predictions. No existing formal rule is reconstructed. A future adapter requires HQ14-verified exact source bytes, full SHA-256, version/section mapping, deadline/provenance evidence, and independently checked frozen outputs. This implementation does not accept an arbitrary claimed hash as proof.

## Validation and remaining gates

The pure functions use only the standard library, make no external calls, and neither read nor write production data. Their outputs are deterministic. The tests cover five unique tickets, three/four main configurations, supported values, missing/partial odds, null EV, independent risk gates, invalid types and timestamps, six BOX permutations, a deliberately divergent synthetic Human/Mechanical example, deterministic equal sets, manual-input deadline rejection, exhaustive objectives, overlap accounting, and an outcome/refund boundary.

OPEN: real-race input adapters and provenance, original frozen Model/BOX implementation, predeadline manual evidence, actual prediction quality, realistic market execution, slippage, refund timing, uncertainty, and unused-future-data evaluation. No research threshold is promoted from PROPOSED. No performance or legacy-reproduction PASS is implied by unit tests. Production remains frozen pending independent Claude review and Andy's separate GO.
