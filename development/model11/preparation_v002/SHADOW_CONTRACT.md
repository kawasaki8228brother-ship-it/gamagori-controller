# Third research shadow output preparation

Status: **PROPOSED / OFFLINE SOFTWARE ONLY**. Real performance, independent
timestamp authenticity, formal BOX Ver.1 reproduction, and production use are
**UNVERIFIED**. No approved schedule or execution integration exists.
2026-11-21 through 2026-11-24 is only an earliest proposed review window, not
permission to run. Current Model1.0, BOX Ver.1, and formal A/B remain frozen.

## API

`build_shadow_output(prediction, race, generated_at, reproduction) -> dict`

The prediction must be the unmodified engine `0.1.0-research` forecast, with no
evaluation `actual` field and `first_course=None`. If using an offline evaluation
record, the caller must explicitly remove its evaluation-only `actual` and reset
`first_course=None`; the original stored `prediction_sha256` must then verify.
The function never reconstructs or edits a legacy forecast. It never mutates its
arguments. Times are aware ISO timestamps; `prediction_at <= generated_at <
deadline` is required. An internally consistent timestamp is not proof of when
the output was actually published.

Required `reproduction` keys:

| Field | Meaning and verification |
|---|---|
| `code_commit` | Full lowercase 40-hex commit reference. Content and authenticity UNVERIFIED; no GitHub call. |
| `input_artifact_sha256` | SHA-256 of canonical JSON of the supplied validated race, verified against forecast `input_sha256`. |
| `model_sha256` | Actual canonical hash of forecast `model_spec`, checked against forecast and reproduction reference. |
| `config_sha256` | Actual canonical hash of forecast `config`, checked against reproduction reference. |

The input artifact convention is sorted keys, separators `,` and `:`, ASCII JSON
escapes, finite values, no trailing LF, matching `model11.engine.canonical_hash`.
It identifies a derived canonical race artifact. It makes **no claim** about the
unknown raw bytes of any original source file, acquired document, or external
receipt. Original file bytes and independent readback evidence remain separate
inputs for future nonpublic review.

Example reproduction construction, given an existing validated forecast:

```python
reproduction = {
    "code_commit": "71ddd13dd5869aaf892a504ea0553c60e8b8abe2",
    "input_artifact_sha256": prediction["input_sha256"],
    "model_sha256": prediction["model_sha256"],
    "config_sha256": canonical_hash(prediction["config"]),
}
record = build_shadow_output(prediction, race, generated_at, reproduction)
payload, receipt = serialize_shadow(record)
verification = verify_shadow(payload, receipt)
```

`serialize_shadow(record) -> (payload: bytes, receipt: dict)` serializes the whole
record in canonical ASCII JSON without a trailing LF. The external receipt
contains exact payload byte count and full SHA-256; the receipt is not inside its
own hash body. The function writes no file.

`verify_shadow(payload, receipt) -> dict` checks raw bytes and internal consistency.
Its strongest success status is `SELF_CONSISTENT_ONLY`, with `authenticity=
UNVERIFIED`, `predeadline_publication=UNVERIFIED_NO_INDEPENDENT_RECEIPT`, and both
operational GO flags false. Tampering with a payload alone is detectable; an
attacker can regenerate both self-hashed payload and receipt. This is neither a
signature nor independently sealed evidence.

## Output coverage and gates

The wrapper version `0.2.0-preparation-PROPOSED` and source
`MODEL11_THIRD_RESEARCH` are separate from engine version `0.1.0-research` and its
`MODEL11_RESEARCH` forecast. The engine's values remain unchanged.

The record contains race ID/date, prediction/generated/deadline times, six active
boats, all four complete 120-outcome distributions (`P_raw`, `P_model`, `P_market`,
`P_shrunk`), separate calibrated probabilities, ordinary five tickets, separate
Human Research / Mechanical Research / BOX v1.1 research tickets, their expected
economics and BET/SKIP observations, and Human/Mechanical composition YES/NO.
Composition means three-boat set equality only and does not imply superiority.
Human Research is not proof of formal Human BOX Ver.1 reproduction.

Feature and categorical-state acquired/available/revision evidence, market times,
manual research input times, warnings, and explicit missing-input codes are
recorded. Missing optional manual input is labelled as an automatic research
heuristic; it is not silently represented as a verified manual original.
When an adapter supplies `normalization_provenance`, its normalizer/spec/training
input hashes, fit cutoff, maximum training availability, and prediction usage are
retained as self-reported evidence. Both training cutoff and maximum training
availability must strictly precede prediction. `TRAINING_ONLY_NOT_FORECAST`
records are rejected; no training-transform record becomes a shadow forecast.
Absence of adapter metadata is allowed for the original pre-normalized schema;
it is not evidence of a raw physical-feature adapter or verified source mapping.

STOP/HOLD conditions include:

- Forecast, model, config, input, or reproduction hash mismatch; evaluation/result
  fields; altered research boundary; missing or unknown code reference.
- Unknown/naive/late generated time, invalid input availability, identity mismatch,
  missing or mismatched time evidence, training-only normalization or future
  normalization fit cutoff/training availability.
- Fewer than six active boats, including a scratched boat. The old engine may
  validly predict a reduced domain; this full-120 output protocol holds instead
  of mislabelling 60 outcomes as 120.
- Missing/stale/unavailable odds or any missing probability stage. The old model
  can still generate market-free probabilities and SKIP; this four-stage shadow
  preparation command does not fabricate a market stage.
- Wrong probability mass/domain, duplicate selection tickets, incorrect BOX
  permutations/stakes, inconsistent composition or BET/SKIP values.
- Paths, source URLs, credentials, result/outcome payloads, unsupported fields,
  raw byte truncation, receipt mismatch, or noncanonical serialized bytes.

The package contains no A/B writer, notification sender, scheduler, network
client, real-money bet interface, or automatic production promotion. It does not
consume actual outcomes. Examples/tests are synthetic and use dates in 2099.
Independent Claude review, HQ14 integration review, nonpublic input provenance,
and Andy's separate explicit GO remain required before any real execution.

## Reproduce scoped checks

From the package directory:

```text
python -B -m unittest discover -s tests -p test_preparation_shadow.py -v
```

The tests cover raw receipt round-trip, immutable inputs, full four-stage output,
separate research selections, strict time gates, evaluation contamination,
reproduction hashes, missing market/manual input, scratched/reduced domains,
time-evidence mismatch, truncation/newlines, recomputed self-hash limitations,
GO/proof injection, sensitive fields, and noncanonical bytes. Passing these
software checks is not evidence of actual forecast quality or deployment GO.
