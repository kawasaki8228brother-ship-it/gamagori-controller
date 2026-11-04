# Model 1.1 research input contract

Status: **PROPOSED; synthetic fixture execution only.** No production adapter,
verified Model 1.0 profile, formal Human/Mechanical BOX Ver.1 profile, or actual
data completeness/provenance evidence has been supplied. Their reproduction and
real-data suitability remain **UNVERIFIED / OPEN**. This schema does not redefine
official LOCK validity, deadlines, scoring or BOX rules.

## Separate predictor snapshots and outcome labels

The race predictor object is JSON-shaped. Required fields:

| Field | Constraint |
|---|---|
| `race_id` | Nonempty UTF-8 text identifier, at most 256 characters, no controls; opaque, never parsed to guess a date or venue |
| `target_date` | Exact valid `YYYY-MM-DD` |
| `venue` | Exact `GAMAGORI` |
| `prediction_at`, `deadline` | Strict timezone-aware timestamps; prediction strictly before deadline |
| `active_boats` | Distinct integer boat IDs 1–6, length 3–6; bool is not an integer ID |
| `boats` | 3–6 objects, no duplicate boat IDs; every active boat present |
| `odds_snapshot` | Null/missing or separate market object described below |
| `human_box_input` | Optional separate manual research BOX object described below |

Deadline converted to JST must fall on `target_date`. A race ID is opaque: the
adapter/HQ must prove its official identity mapping; matching a made-up string is
not that proof. Optional `race_id`, `target_date`, `venue` repeated on boat,
market or manual records must match the parent race. Unknown JSON-safe metadata
is preserved, not consumed as model features. UTF-8 surrogate errors, nonfinite
numbers, non-JSON values, cycles, nesting over 32 and excessive size are rejected.

Each boat requires `boat`, `course` (integers 1–6), `scratched`, `fl` (actual
booleans), `observed_at`, `motor_updated_at`, `revision_at`, `features`,
`feature_times` and `state_times`. Active courses must be distinct. Active scratched boats are
ineligible. Inactive records can remain only with `scratched=true`; their missing
feature data are not silently used. Reduced fields are research-only warnings;
they are not an implementation decision for formal scratched-race betting.
F/L=true is explicitly flagged, not converted into a fabricated penalty or zero.
Missing/unknown F/L is ineligible. If supplied, `course_updated_at`,
`scratch_updated_at`, `fl_updated_at` must be valid and no later than prediction.

`features` has exactly `st`, `turn`, `motor`, `ability`, `exhibition`: finite
numbers in [-1,1], pre-normalized with higher=better. Raw ST duration is **not**
this score; conversion/standardization and observed-variable lineage need a
separately reviewed adapter trained only on earlier data. Missing, null, bool,
unknown extra feature names, and missing exhibition block prediction; no zero
imputation occurs. Numeric zero remains a valid observed research score.

`feature_times` is mandatory for **each** of the five features:

```json
{"st":{"acquired_at":"2099-11-09T12:58:00+09:00","available_at":"2099-11-09T12:58:00+09:00","revision_at":"2099-11-09T12:58:00+09:00"}}
```

All three times must be present and <= prediction; acquisition <= availability.
This prevents a late-available observation or hindsight revision being accepted
just because an aggregate record timestamp is early. Aggregate boat times also
must be <= prediction; motor update <= observation <= revision. Time assertions
are checked for internal consistency; independent timestamp evidence remains
necessary. A claimed old time alone cannot prove that no later correction leaked.

`state_times` is independently mandatory for **course, fl, scratched** on every
included boat, including an inactive scratched record. Each state entry has the
same `acquired_at`, `available_at`, `revision_at` structure: all present and <=
prediction, acquisition <= availability, with the same strict timezone and
precision checks. Aggregate boat times never substitute for these state-specific
proofs. This covers the course consumed by the prior and F/L/scratch eligibility;
an early numeric feature snapshot cannot make a later course/state update safe.

All accepted timestamps are exact RFC3339-style
`YYYY-MM-DDTHH:MM:SS[.1-to-6-digits](Z|+HH:MM|-HH:MM)`. Naive times, unknown
`-00:00` offsets, leap seconds, >6 fractional digits, invalid dates and malformed
offsets are rejected rather than rounded or defaulted. Comparisons use instants,
not lexical ordering. No missing instant or internal run ID is inferred.

Predictor data **recursively reject** result/outcome/payout/refund/label/actual/
winner key tokens (including camelCase), and `final` label keys. `available_at`
is permitted as observation availability metadata, particularly inside required
`feature_times`. Labels are never stripped to disguise a leak.
No result, payout or post-race field belongs in a predictor snapshot. It is the
caller's responsibility not to encode a result inside an innocuously named score;
this structural checker cannot detect that deception without source evidence.

## Optional market and manual research inputs

An odds snapshot has mandatory `acquired_at`, `available_at`, `revision_at`, and `odds` mapping every ordered
triple in the active field to a finite positive gross payout multiple per unit
stake. At six boats, all 120 triples are required; at five boats, 60. Key format
is `1-2-3`, with distinct boats. All three snapshot times must be present,
timezone-aware and <= prediction; acquisition <= availability and revision >=
acquisition. Missing/future/malformed availability makes the market unavailable,
even when acquisition is early. No aggregate timestamp substitutes for it.
Max age defaults to 120 seconds inclusive, measured from acquisition.
No missing odds, missing combinations or odds normalization is invented here.

`market_status` is AVAILABLE / MISSING / STALE / FUTURE / INVALID;
`market_available` is true only for AVAILABLE. Missing/stale/future/wrong identity/
incomplete or invalid market values produce explicit warnings and unavailable
market data without blocking otherwise valid `P_model` features. Invalid JSON
(e.g. NaN) or leaked labels anywhere still blocks the whole input. The market
consumer must enforce `market_available` and must not shrink to unavailable odds.

Manual research BOX input requires `core` (two distinct active IDs), `insertion`
(third distinct active ID), and mandatory `observed_at`, `acquired_at`,
`available_at`, `revision_at`: all strict aware times <= prediction, with
acquisition <= availability. An early observation never substitutes for later
availability or a missing revision. `human_box_status` is
AVAILABLE / MISSING / INVALID. An unavailable manual input does not block regular
model probabilities; the BOX consumer must not use it or impersonate an actual
manual forecast. This input is not proof of formal Human BOX Ver.1 reproduction.

## Outcomes and dataset joins

Outcomes are separate objects with `race_id`, `target_date`, `result` (three
distinct integer boat IDs), `payout_per_100` (finite nonnegative numeric),
`refund_tickets` (unique legal triple strings), `final` (bool) and `available_at`
(strict timestamp). Nonfinal/missing labels or unknown payout are not eligible
for this complete-outcome schema. Zero payout is distinct from absent payout.
Partial economic-data adapters need a separate reviewed contract; never silently
turn missing money into zero. Optional venue is checked against the race on join.

`validate_dataset` rejects duplicate race IDs, duplicate outcome IDs, malformed
records, orphan outcomes, date/venue mismatch, inactive finishers and final outcome
availability before deadline. Missing outcomes are explicitly `OUTCOME_MISSING`
warnings, not fabricated labels. Empty datasets are flagged. This is not evidence
that a schedule is complete, that every real race was captured, or that a label
was available for training. The walk-forward caller must additionally require
`available_at <= training cutoff` and keep dates/groups disjoint from evaluation.

## Python API and STOP rules

`validate_race(race, max_odds_age_seconds=120)` returns `eligible`, `status`,
`errors`, `warnings`, `market_status`, `market_available`, `human_box_status`,
`legacy_profile_status`. `validate_outcome(outcome)` has the core report fields.
`validate_dataset(races,outcomes)` adds counts and individual reports.
`prediction_view(record)` returns a deep separate copy after recursive JSON/leak
inspection, or raises `ValueError` with a fixed machine code. It does not confer
eligibility: callers must still call `validate_race`. No submitted private value,
URL, credential or path is interpolated into diagnostic codes.

Any input error stops prediction. Market/manual consumers stop using their input
unless their own status is AVAILABLE. Contradictory identity/time, missing data,
unverified real-source mapping and absent legacy profiles remain OPEN; no adapter
or LOCK modification is invented. Passing synthetic fixtures is software gate
evidence only, never real-model improvement or production GO.

Reproduce validation tests without network or a production connection:

```sh
python -B -m unittest discover -s tests -p test_validation.py -v
```
