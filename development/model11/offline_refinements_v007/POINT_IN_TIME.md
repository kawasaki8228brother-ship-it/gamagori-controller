# Point-in-time audit candidate: no later statistics or final-odds substitution

**PROPOSED / completely offline / invented fixtures only.** The auditor checks
one declared historical snapshot at a fixed pre-deadline `as_of`. It does not
fetch a source, load a latest table, normalize a feature, train/evaluate a model,
change an existing engine or provide a live input gateway. Parent artifacts are
unchanged. Actual private data and actual source mapping remain HOLD/OPEN.

```python
audit_point_in_time(sample) -> report
```

The function performs no file, database, network or clock I/O. Diagnostics use
fixed codes, never submitted source URLs, paths, credentials or exception text.
Examples in `tests/test_offline_refinements_point_in_time.py` are wholly invented
year2099 records. `sample_fixture()` builds a complete example;
`training_context()` builds optional invented chronology metadata.

## One fixed pre-deadline sample

Required top-level fields are exactly:

```text
data_classification=SYNTHETIC_ONLY, synthetic=true
race_id, target_date=valid2099date, as_of, deadline
snapshot, features, odds
training_context (optional)
```

Unknown/private classification, non-bool/contradictory synthetic flag or a
non-2099 target stays HOLD before feature inspection. This software fixture guard
does not authenticate a dishonest external classification claim. All timestamps
use the pinned parent strict aware parser: explicit timezone, seconds, at most
six fractional digits, no naive time, no unknown `-00:00`, no normalized invalid
offset such as `+08:60`, and no rounding/default timezone. Require
`as_of < deadline` and deadline's JST date equal target_date.

`snapshot` has exactly:

```text
mode=IMMUTABLE_SNAPSHOT
snapshot_id, version, preserved_at, source_id
content_sha256, evidence_sha256
```

The original version must be explicitly identified, not `LATEST`, `CURRENT` or a
latest/current-table lookup. Preservation time must be known and <= as_of. Here
`preserved_at` means the claimed original snapshot-version preservation event,
not the date of a later analysis/handoff copy. A later-preserved or unidentified
version HOLDs; no old version is fabricated from a current table.
Each included feature/odds acquisition, availability and revision must also be
<= this version's preserved_at. A revision before as_of but after the claimed
immutable capture is inconsistent with that version and HOLDs. This is snapshot
materialization chronology, not a new betting threshold or LOCK/model rule.

Content/evidence SHA values must be full lowercase hashes, but raw original
snapshot bytes and independent receipts are **not received by this small
auditor**. A shaped hash, asserted immutable mode and old timestamp cannot prove
that a record was historically unchanged or truly available. Their origin and
binding remain SELF_REPORTED_ONLY / external authenticity UNVERIFIED. HQ14 must
independently retain and compare the actual original versions and source history.

## Every feature, including motor and exhibition

`features` contains exactly the 30 distinct `(boat,name)` observations for boats
1–6 and names **st, turn, motor, ability, exhibition**. Each has exactly:

```text
boat, name, value, unit
effective_at, acquired_at, available_at, revision_at
version, snapshot_id, source_id, evidence_sha256
```

Value is a real finite numeric, never bool/null/missing-as-zero. Declared unit
must be explicit, but this auditor neither adopts a physical unit mapping nor
converts it. A valid observed zero remains zero. Missing exhibition, duplicate
observation, unknown feature name, absent source/version/SHA or a different
snapshot_id HOLDs. Result/outcome/payout/refund/actual fields are recursively
rejected; naming a feature `result` is also rejected. Labels never become model
features through this interface.

For **each** feature, acquisition, availability and revision must be valid and
<= as_of; acquisition <= availability and acquisition <= revision. Effective time
must be valid and <= acquisition/as_of. An old effective date never rescues a
later revision or a statistic backfilled after the race. In particular, a motor
rate rewritten tomorrow with an effective date last month cannot be used for
today's historical prediction snapshot. The version/source/evidence must refer
to the preserved old observation, not the current latest statistics table.

This is a temporal/provenance claim audit, not another full motor/source adapter.
Physical motor identity, replacement/version correspondence and actual units
still require the existing source/RAW gates and independently reviewed inputs.
No old statistical values, motor identity or exhibition observation is inferred.

## Only actually pre-deadline odds

`odds` is null (HOLD) or exactly:

```text
kind=PRE_DEADLINE
values={all120distinctorderedticketkeys:positivefinitenumber}
acquired_at, available_at, revision_at
version, snapshot_id, source_id, evidence_sha256
```

All three times must be <= as_of with the same provenance/time-order checks.
The full domain is the 120 permutations of six boats. Unknown prices, absent
tickets, unsupported/latest version or absent provenance HOLD. `FINAL`,
`POST_RACE`, unknown kind and absent pre-deadline odds never fall back to final
odds, payouts, inferred reciprocals or a fabricated number.

Feature eligibility and market eligibility are reported separately. Missing or
final odds can leave current features eligible, but overall status remains HOLD,
`market_baseline_eligible=false`, `expected_value_eligible=false`. The true flags
on a complete synthetic fixture mean only that the submitted temporal inputs are
eligible for an offline calculation; the auditor does not calculate/approve a
market baseline, expected profit, real performance or a bet.

## Optional training chronology does not verify historical inputs

If supplied, `training_context` is exactly:

```text
normalizer_fit_cutoff, model_fit_cutoff
training_rows=[{prediction_at,feature_available_at,label_available_at}, ...]
```

Require strict known timestamps and
`normalizer_fit_cutoff <= model_fit_cutoff < current as_of`. Per row, feature
availability <= that historical prediction < normalizer fit, and historical
prediction < label availability <= model fit. Missing/future label availability,
future model/normalizer fit or features that became available after that old
prediction HOLD. No absent chronology is filled or inferred.

These row timestamps are only explicit chronology claims. **They are not a
substitute for auditing every full historical training, selection, validation
and evaluation snapshot before fitting or evaluation.** Each past race needs
its own preserved-version feature/odds audit at its own pre-deadline as_of.
Fitting-cutoff metadata alone cannot prove that old features were not rewritten
later. The optional context does not recursively load or verify that historical
collection, source originals, label content or independent availability evidence.

Absent context is `UNVERIFIED_NOT_SUPPLIED`; it is not training PASS. A current
synthetic snapshot can pass its feature/market software check while this separate
training context remains unverified. This candidate is not a full walk-forward
pipeline or a replacement for existing chronological fit/evaluation gates.

## Report and limits

Valid complete invented input reports `SYNTHETIC_POINT_IN_TIME_CANDIDATE` and
software_check=PASS. Any failed required gate reports HOLD with separate feature
and market reasons. Every report retains:

```text
application_status=HOLD
real_input_status=HOLD
origin_proof=SELF_REPORTED_ONLY
external_authenticity=UNVERIFIED
actual_source_mapping=OPEN
production_go=false
```

No execution, application, threshold, approval, schedule, A/B, Model1.0, BOXV1,
LOCK/deadline rule or source mapping is adopted. Actual historical originals,
private source/version authenticity, honest revision timestamps and independent
pre-deadline evidence remain OPEN. Software success cannot authenticate those.

Twelve meaningful test methods exercise complete fake input, latest/later
snapshots, all feature-time future/backfill cases, source/version/SHA/effective
binding, explicit label leakage, missing/nonfinite/bool values, final/missing
odds, full120/time gates, strict as_of, fit/label chronology, real-input HOLD and
safe diagnostics. Only actually executed tests are reported PASS:

```sh
python -B -m unittest discover -s tests -p test_offline_refinements_point_in_time.py -v
```
