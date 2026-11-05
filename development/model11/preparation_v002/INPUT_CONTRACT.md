# RAW_V001: HQ14 private input and train-only normalization

**PROPOSED / Lane2 offline only.** The executable adapter is a preparation tool.
No real race original, private credential, A/B forecast or production connection
has been used. Real feature definitions, source-to-unit mapping, raw snapshot
availability proofs and statistical revision histories are **OPEN**. Passing
synthetic fixtures establishes software behavior, not source authenticity,
real-world forecast skill, Model 1.0 equivalence or production GO.

## Public API

```python
validate_raw_race(raw, feature_specs)  # report; fixed codes, no private values
fit_normalizer(training_records, fit_cutoff, feature_specs)  # frozen dict
normalize_race(raw, normalizer, usage="prediction")  # {race, audit}
synthetic_feature_specs()  # explicit invented PROPOSED configuration
make_raw_fixture(race)  # only synthetic=true, SYNTHETIC_ONLY, year2099
```

Failures in fitting or transformation raise `ValueError` with a fixed code.
Validation reports `eligible`, `status`, `errors`, `warnings`,
`external_authenticity=UNVERIFIED`, `real_mapping=OPEN`, `production_go=false`.
No error interpolates submitted IDs, source URLs, paths or credentials.

## RAW_V001 field contract

Every provenance object below has **acquired_at, available_at, revision_at,
evidence_sha256**. Timestamps must be strict timezone-aware RFC3339 with seconds,
0–6 fractional digits, and Z or an explicit offset. Naive times, `-00:00`, leap
seconds and excess precision are rejected. All times must be <= prediction;
acquisition <= availability and acquisition <= revision. Later revisions of
statistics cannot become historical pre-LOCK features. An asserted early time
still needs independent evidence; a hash-shaped string is not that evidence.

| Field | Required meaning |
|---|---|
| schema_version | Exact `RAW_V001` |
| data_classification | `SYNTHETIC_ONLY` or `HQ14_PRIVATE_OFFLINE` |
| race_id / target_date / venue | Same opaque identity, valid date and GAMAGORI constraints as old schema; source identity proof remains external |
| prediction_at | Strict timestamp, before deadline |
| race_provenance | Provenance of the claimed race identity |
| deadline | `{value: timestamp, unit: "timestamp", ...provenance}` |
| active_boats / active_boats_provenance | Explicit active IDs and independent provenance |
| boats | 3–6 unique boat records; active IDs present; formal scratch betting policy is not inferred |
| odds_snapshot | Null or a complete market snapshot below |

Each boat has exactly **boat, course, fl, scratched, motor_identity, features**.
Course/F/L/scratch are wrappers `{value,unit,...provenance}`, with units
`course_number` or `boolean`. No aggregate timestamp substitutes for a state's
availability. Course is integer 1–6; F/L and scratch are actual booleans. Existing
active/course/scratch checks apply. Unknown states and bool-vs-number conflation
do not become zero or false.

`motor_identity` is `{motor_id, version, effective_at, ...provenance}`. IDs and
version must be nonempty strings. Effective time must be valid, <= acquisition
and <= prediction. The motor feature must explicitly carry matching `motor_id`
and `motor_version`. Its acquisition, availability and revision must each be
at/after this identity's effective time; older statistics cannot be silently
assigned to the newly effective motor version. A reused number without version/effective-time evidence is
not assumed to refer to the same physical/statistical motor. Source chronology
for the real motor replacement and recalculated rates remains HQ14 evidence.

Features have exactly **st, turn, motor, ability, exhibition**. Each is
`{value,unit,...provenance}`; motor additionally has identity references above.
Missing/null/bool/nonfinite values, absent exhibition, unknown extra features or
fields, unknown units, mismatched units, absent provenance and late revisions
block fitting and prediction. No imputation occurs. Source/origin metadata and
unregistered extra fields are rejected, including A/B prediction input.
Outcome/result/payout/refund/legacy/prediction key tokens are recursively blocked
(the timing field `prediction_at` is allowed). This cannot detect a result
deliberately hidden inside an innocuously named score; that needs independent
lineage and source review.

Market: `{unit:"gross_payout_multiple",odds:{"1-2-3":number,...},...provenance}`.
Six active boats require exactly all 120 triples; a reduced field requires its
complete permutation domain. Values must be positive finite gross payout
multiples, never winning-payout hindsight. Missing/incomplete/stale/future or
invalid market data are explicit warnings and unavailable for market shrink/EV;
otherwise valid model-only features can remain eligible. Invalid RAW market
provenance is removed from the normalized model-only snapshot and logged, never
converted into apparently valid odds. No manual A/B/BOX forecast is admitted by
this feature adapter; it outputs `human_box_input=null` explicitly.

## Units and normalization are explicit research choices

`FEATURE_SPECS_V001` freezes `version`, `status=PROPOSED`, `mapping_status`, and
five per-feature entries `{unit,direction,normalization}`. Allowed mapping status
is `SYNTHETIC_INVENTED_ONLY` or `HQ14_PRIVATE_MAPPING_UNVERIFIED`. Units currently
registered are seconds (>0), score_0_100 ([0,100]), rate_fraction ([0,1]) and
rating_points (>=0). Lower/higher direction must be declared; there is no
automatic ST interpretation, milliseconds conversion, feature guessing, or
arbitrary unknown-unit conversion. Real physical scales and semantics need
separate review; this registry does not certify their suitability.

`HQ14_PRIVATE_OFFLINE` input with `SYNTHETIC_INVENTED_ONLY` specs is rejected;
changing an invented fixture's classification cannot authorize its invented
mapping on private data. A private-mapping spec additionally requires
`review_evidence={hq14_review_sha256,claude_review_sha256}`, both full lowercase
64-digit hexadecimal hashes. Missing/invalid metadata yields HOLD / fit STOP.
This conditional field does not change the synthetic spec shape. The hashes
are **SELF_REPORTED_HASHES_ONLY**: their presence is not proof that either review
exists, concerns the exact mapping, passed, or was approved by an authorized
person. HQ14 must independently inspect those private originals and their scope.
External authenticity remains UNVERIFIED, real mapping OPEN, production_go=false
even when dummy hash-shaped strings satisfy this metadata gate. Tests use only
invented fixtures and dummy hashes, never actual private records/reviews.

Only explicit `TRAIN_MINMAX_CLIP_V001` is implemented:

`score = clip(2*(x-training_min)/(training_max-training_min)-1, -1, 1)`

Invert the sign only for `LOWER_IS_BETTER`. Training means/statistics are never
fit using test rows. Clipping is an explicit PROPOSED choice, recorded per boat
and feature; it is not evidence of robustness or a fitted-on-holdout adjustment.
Constant/absent training statistics STOP; the adapter does not invent a variance
or normalized zero. Raw numerical unit bounds still apply before clipping.

The simulator helper invents ST as `0.25-0.2*x` seconds, turn as `50+50*x`, motor
fraction as `(x+1)/2`, ability as `50+10*x`, and exhibition as `7.0-0.6*x` seconds
from the old synthetic score x. **These are plumbing fixtures, not empirical
Gamagori transformations, weights, units or formally adopted mappings.** It
rejects non-synthetic input and dates outside 2099. Normalized outputs will
generally differ from the original simulator scores; no old fitted weights are
reused for a new normalization as if they were equivalent.

## Frozen fitting and temporal gates

`fit_normalizer` accepts only raw training records, cutoff and specs: no outcomes
or A/B forecasts. It rejects no-data, duplicates, invalid records, any training
prediction at/after cutoff and late statistical observations/revisions. It
records frozen feature specs/SHA, training IDs, per-record hashes, combined
training-input SHA, cutoff, maximum training prediction/availability, and the
per-feature extrema/count/unit/direction. Its own SHA binds those internal
claims; it does not authenticate their origin. Caller must freeze the actual
input files privately and independently verify training membership/source times.

Default `normalize_race(...,usage="prediction")` requires target prediction
strictly after fit cutoff and maximum training availability. The transform is
read-only and never refits statistics on a holdout outlier. Explicit
`usage="training"` is permitted only for matching IDs **and matching complete
raw hashes** in that normalizer. It returns `TRAINING_ONLY_NOT_FORECAST`; this
mode supports model fitting and must never be submitted as a historical shadow
forecast. Unknown usage, altered training records or normalizer mismatch STOP.

The returned old-schema race preserves per-feature/state times, explicit model
features and eligible odds. It adds:

```text
normalization_usage = TRAINING_ONLY_NOT_FORECAST | PREDICTION_AS_OF_GATE_PASSED
normalization_provenance = {
  normalizer_sha256, feature_specs_sha256, fit_cutoff,
  training_max_available_at, training_input_sha256,
  usage: training | prediction
}
```

This metadata survives the engine's input hash and lets Shadow link the actual
frozen normalization artifact. Keep the returned audit alongside the forecast.
Original 47 files/old candidate/Model1.0/BOXV1 remain unchanged. A new model must
be trained on the transformed training scores before using transformed holdout
scores; calling old weights with new scales is not a validation.

## HQ14 private handoff and OPEN / STOP

Provide privately, without sending real originals to Codex/public GitHub:
raw identity/deadline evidence; uncorrected pre-LOCK source snapshots; all
per-field acquisition/availability/revision times; true raw units/directions;
motor identity/version/effective history; exhibition availability; complete
timestamped 120-odds snapshots; feature-definition versions; training/selection/
untouched-future period IDs; frozen file hashes and independent readback records.
Do not provide A/B predictions as features, credentials, source URLs containing
secrets or retrospectively revised statistics with backdated availability.

Unknown provenance/mapping/completeness and independent authenticity stay OPEN.
Missing features, time contradictions, motor mismatch, unit mismatch, forbidden
input, absent statistics, future fitting, changed training record and unexpected
schema are HOLD/STOP. Synthetic success does not close those real-data gates.
Real-data walk-forward fitting of normalization at every fold is a future HQ14
private validation task; this preparation adapter is not a real-data skill test.

Reproduce locally with no service connection:

```sh
python -B -m unittest discover -s tests -p test_preparation_adapter.py -v
```
