# Independent V003 cross-module software review

Scope: new offline F1/F3/F4 candidate paths. This review uses synthetic races
dated 2099, local immutable files, and stdlib tests only. It does not attest to
real prediction quality, actual source authenticity, formal BOX reproduction,
preregistered selection adequacy, Claude approval, or operational GO.

The integration suite embeds the exact paths, byte sizes, and SHA-256 values of
all 88 files at parent `00d67eea0598ba83671eb400175749df294a6fad`. Verification is
portable and does not require a private manifest. These older files remain
unchanged; new tests and implementations occupy new V003 paths.

Observed and resolved during development: the V003 predictor initially called
the original normalized race schema without explicitly carrying forward the
preparation adapter's forecast-usage boundary. The original schema intentionally
does not enforce new adapter metadata. The new V003 engine now calls the
unchanged V002 normalization evidence gate. The integration regression requires
HOLD for training-only normalized records, cutoff at/after prediction, and
training information at/after prediction, while retaining valid self-reported
normalization evidence. This is a software boundary check, not proof that the
reported training timestamps or hashes originate from a trusted external source.

The direct predictor/CLI boundary was also reviewed separately from walk-forward:
the final new engine rejects anything other than explicitly synthetic,
SYNTHETIC_ONLY, 2099-dated fixture input. This closes a path that could otherwise
bypass the walk-forward real-input HOLD while F5 and independent review remain
pending. The regression changes only synthetic metadata to exercise this gate;
no real data is received, used, or attested as passing.

Cross-module checks cover:

- All 88 original files remain byte-identical.
- The default exhibition fixture preserves the original simulator's pre-outcome
  course values, features, odds, and outcomes. Identically configured original
  base-model and course-bound fits yield bit-identical P_raw and P_model values;
  adding course provenance does not silently change this synthetic experiment.
- Four finite full 120-outcome probability stages, sorted unique ordinary five,
  and separate automatic five-appearance/manual Human/Mechanical/v1.1 BOX slots.
- Market weight 1 equals `P_market` exactly under different fitted candidates,
  alpha values, and temperatures; calibrated model probabilities actually differ.
  Missing or future-unavailable market evidence causes HOLD at weight 1.
- A fitted course policy is bound through prediction and model serialization.
  Different policies, future course evidence, final-result course definitions,
  and forbidden post-result sources cause HOLD.
- Manual Human input requires its own origin and pre-deadline evidence. Automatic
  five appearances are not labelled as Human; legacy canonical manual fields are
  not automatically reused. Cross-race and future manual receipts cause HOLD.
- In one chronological fold, changing only held-out test outcomes does not change
  selected parameters, forecast hashes, probability stages, selections, or boxes.

Reproduce from the package directory:

```text
python -B -m unittest discover -s tests -p test_revision_v003_integration.py -v
```

All synthetic demonstrations remain software observations. F2/F5 proposals and
real data evaluation remain OPEN/UNVERIFIED. No external service or production
operation is part of this suite.
