# F4: separate automatic five-appearance and human-input research BOX

This V003 addition changes research naming and provenance gates. It does not implement formal Human BOX Ver.1, alter its frozen production rules, introduce a new F2 BOX algorithm, or promote Model 1.1. The existing 88 files and their old labels/results remain unchanged. All new output is an independent research candidate or a migration review, with `production_go=false`.

## New active schema

`build_portfolios(race, dist, five, odds=None, human_input=None, config=None)` returns a `MODEL11_PORTFOLIOS_V003` object for the forecast's `boxes` field:

| Active key | Input/algorithm | Output when unavailable |
| --- | --- | --- |
| `five_appearance_research` | Always automatic: ordinary-five appearance counts, first-position appearances, boat-number tie break; first two core and third insertion | Invalid base input raises; never replaced by a manual slot |
| `human_input_research` | Separate explicit caller input with human-origin assertion and predeadline evidence metadata | `null`, with ABSENT or HOLD gate |
| `mechanical_research` | Unchanged exhaustive maximum six-permutation probability mass | Existing validation rules apply |
| `box_v11_research` | Unchanged original maximum expected-return research kernel; existing explicit probability fallback if admitted odds absent | Existing null EV / SKIP behavior |

There is no active `human_research` key. The automatic display name is **Five-appearance research BOX**, with `origin=AUTOMATED_FIVE_APPEARANCES` and `human_origin=false`. It is not displayed as Human BOX. The explicit manual display name is **Human-input research BOX**; its `HUMAN_MANUAL` origin is an input assertion, not an independent authenticity finding or formal BOX Ver.1 reproduction. All BOX objects retain `formal_box_v1_reproduction=false`.

The ambiguous canonical `race.human_box_input` is never automatically reused by this module. The new engine additionally rejects a non-null legacy field instead of silently adopting its prior meaning. Supplying a manual research input never suppresses or changes the independently computed automatic five-appearance lane. Coincident boat sets remain valid; no artificial difference is forced.

`composition_difference` is a dictionary with `five_appearance_vs_mechanical` and `human_input_vs_mechanical`. Values YES/NO mean only unequal/equal three-boat sets; the manual comparison is null when no admitted manual input exists. The names do not claim quality or superiority. `overlap` records each ordinary-five/available-BOX and BOX/BOX ticket intersection, with the unique union, using the new explicit names.

## Strict separate human-input contract

The argument must contain **exactly** these 12 fields:

```json
{
  "race_id": "SYNTHETIC_RACE_ID",
  "target_date": "2099-01-03",
  "core": [1, 2],
  "insertion": 3,
  "origin": "HUMAN_MANUAL",
  "source_id": "SYNTHETIC_ASSERTION_NOT_ACTUAL_HUMAN",
  "observed_at": "2099-01-03T12:54:00+09:00",
  "acquired_at": "2099-01-03T12:54:10+09:00",
  "available_at": "2099-01-03T12:54:20+09:00",
  "revision_at": "2099-01-03T12:54:30+09:00",
  "evidence_recorded_at": "2099-01-03T12:54:40+09:00",
  "evidence_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

This is a schema-only dummy, not an actual person, historical record, or authenticated receipt. Its identity must match the supplied race. `core` contains two distinct active integer boats and `insertion` a third distinct active integer boat. Boolean boat IDs are rejected. The source reference is an opaque identifier, not a URL, credential, person's name, or external lookup instruction. The evidence hash must be 64 lowercase hexadecimal characters. Missing or extra fields are HOLD.

The times mean: human selection observed; snapshot acquired; available to the predictor; last revision included in the receipt; and evidence recorded/sealed. All are strict aware ISO timestamps, with at most six fractional digits, valid timezone offset minutes, and no unknown `-00:00` offset. Require

`observed_at <= acquired_at <= available_at <= evidence_recorded_at <= prediction_at < deadline`

and

`acquired_at <= revision_at <= evidence_recorded_at`.

Equal boundaries are allowed. A receipt cannot be treated as covering a revision made after its recorded time. Revision before acquisition, availability before observed selection, late/future input, malformed time, wrong race identity, unknown origin, or missing evidence hash is HOLD. These are local consistency requirements; the code does not query an external clock, verify a human identity, fetch the receipt bytes, or prove the claimed origin. `external_origin_authenticity` remains **UNVERIFIED**, including when the local gate is `LOCAL_ASSERTION_ACCEPTED`.

`validate_human_input(race, human_input)` returns `eligible`, `status`, fixed `errors`, and input/evidence hashes when locally consistent. No input is ABSENT. Invalid present input is HOLD and yields `human_input_research=null`; the new engine propagates it as a HOLD exception. A locally consistent assertion permits a research comparison only. Actual live use still requires HQ14's private provenance review, Claude independent review, and Andy's separate GO. A self-hash or typed source name cannot satisfy those approvals.

## Separate evaluation and money

`evaluate_records_v003(records, config=None)` accepts the existing `calibration_bins` and `day_bootstrap` research configuration. It reports five independent method groups:

1. `five` — five ordered tickets, 100 yen each, 500 yen.
2. `five_appearance_research` — automatic three-boat BOX, six tickets, 600 yen.
3. `human_input_research` — admitted asserted input only, six tickets, 600 yen.
4. `mechanical_research` — six tickets, 600 yen.
5. `box_v11_research` — original unchanged research kernel, six tickets, 600 yen.

Hits, gross payout, refunds, net, ROI, original BET subset, SKIP counterfactual, drawdown, course/popularity buckets and day-block diagnostics are per method. Overlapping strategies are not pooled. Missing manual input is an unavailable observation: N=0, hit count/rate, stake, return and ROI null when the entire manual cohort is absent; it is not an observed losing ticket, zero-return strategy, or cloned automatic candidate. `absent_input_n` and `invalid_or_unmatched_input_n` distinguish absent assertions from failed observations. Refunds use the old arithmetic: 100 yen for each selected refunded ticket, with no portfolio double-count aggregation.

The evaluator rechecks manual provenance, timestamp order, input hash, core/insertion/boat composition, and ordinary-five appearance counts. Automatic-origin data cannot be evaluated as the human-input lane. An automatic lane with a false origin is unavailable. Duplicate race/source observations do not inflate N. Invalid or absent observations remain explicit.

Only the old arithmetic/statistical kernel is reused. A private detached in-memory alias allows its existing three-BOX math to run; that alias is not serialized or returned, all exposed method/issue names use the new schema, and the additional manual lane is evaluated independently. No old `legacy` output or `legacy_profile` is used. The new report marks frozen Model 1.0/formal BOX Ver.1 comparison OPEN. This is not evidence that either old formal algorithm has been reproduced.

## Non-destructive migration preview

`migrate_v001_prediction(oldforecast, race=None, course_policy=None, human_input=None)` creates a review object, not a live forecast. It requires the sealed old predictor object, with no `actual` and `first_course=None`; callers must preserve the original prediction hash rather than reseal an evaluated record. The function never mutates the supplied object or writes any old file.

Without the exact canonical original race matching `input_sha256`, the preview candidate remains null/HOLD. If available, a detached `V003_MIGRATION_PREVIEW_NOT_NEW_PREDICTION` can be built. It preserves the frozen ordinary five and original distributions/configuration, computes the automatic five-appearance lane solely from that frozen five, and uses the unchanged Mechanical/BOX Ver.1.1 arithmetic. It does not choose new ordinary tickets, optimize outcomes, train a model, or retime a forecast.

An old ambiguous box with the manual method name is **not** simply renamed as automatic and is not accepted as an actual human input. Its original component hash and an UNVERIFIED-origin review flag are retained; the active manual lane stays null unless a separate new 12-field assertion is supplied. Missing course provenance is HOLD. Even supplying consistent course metadata cannot retroactively bind an old model's training and prior to that policy: `OLD_MODEL_NOT_COURSE_POLICY_BOUND` and `requires_new_course_bound_prediction=true` remain. A new course-bound model/forecast must be generated separately. All migration reviews remain `live_eligible=false` and `production_go=false`.

The old object digest covers its canonical JSON representation; it is not claimed to be the original raw file's byte hash. The review explicitly records `NOT_RECEIVED_OBJECT_HASH_ONLY`. The source prediction hash and a distinct `migration_preview_sha256` are kept separate; the preview has no newly forged `prediction_sha256`. Root preservation evidence independently checks all 88 old file bytes and Git readback. Old result files and their historical terminology are retained as historical artifacts, not silently rewritten.

## Checks, limits and STOP

Run `python -B -m unittest discover -s tests -p test_revision_v003_portfolios.py -v` from the package directory. Synthetic tests cover automatic/manual separation, ignored old input, nullable manual metrics, explicit composition names, 500/600-yen stakes, refunds, old kernel agreement, object immutability, source/hash/race errors, every temporal ordering violation, equal boundaries, migration HOLD and origin quarantine, counterfeit lane swaps, duplicate N and rejection of formal legacy-profile configuration. Passing tests is a software observation, not real human-origin or performance PASS.

STOP/HOLD for mismatched source hashes or identity, missing original source bytes where reproduction is requested, missing course binding, unknown manual origin/evidence, late or inconsistent metadata, ambiguous active schemas, unexpected mutation, old-file changes, or any request to apply automatically. Real race data, external authenticity, formal Human/Mechanical BOX Ver.1 reproduction, real-model superiority, F2/F5 adoption, live execution and production approval remain OPEN. No production, task, Model 1.0, BOX Ver.1, Freeze, canonical source, POINTER, PR #6, main, Render, Airtable, Drive, or GitHub action is performed by these modules.
