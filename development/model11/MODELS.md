# Conditional-rank candidates (PROPOSED / research only)

Both candidates learn separate first, conditional-second and conditional-third
softmax heads using deterministic full-batch conditional cross-entropy gradients
and L2 regularization. `hierarchical` has five coefficients per head;
`contextual` adds 25 interactions with the first boat and 25 with the second.
Inactive context terms are zero. These are statistical conditional models, not a
single overall rank followed by ticket enumeration. Batch gradients average over
supplied races. Fitting resets state, sorts by race ID and does not shuffle.

Inputs must supply **pre-normalized, higher-is-better** ST, turning, motor,
ability and exhibition features in [-1,1]. This package does not claim to know
the correct real-race normalization, missing-data policy or feature weights.
Absent/invalid features are rejected, not filled. Normalized ST is not raw ST
duration; a separately reviewed input adapter is required.

`P_raw` is the fitted conditional product without course prior. `P_model` adds
`alpha * log(stage/course winner count + prior_strength)` to each conditional
logit, using training outcomes only. This is equivalent to a log-linear course
prior after its conditional normalizing constant cancels. Alpha defaults to 0;
course effects are not established. No market inputs affect either distribution.
The market baseline is normalized reciprocal **complete** odds at the permitted
cutoff. Stale, future, invalid or incomplete odds yield a null distribution.
`loglinear_pool` uses weight w for the market; temperature calibration acts on
the resulting distribution. Alpha, w and temperature must be selected only from
past training/model-selection windows, never future evaluation outcomes.

All defaults and hyperparameters are PROPOSED. Fit validates one-to-one race /
final-outcome IDs, dates and active result triples. The walk-forward caller must
also enforce outcome availability and train/selection/test time separation.
Prediction does not accept outcome fields. `.explain` exposes feature and prior
logit contributions. `.to_dict` records JSON-safe parameters, input feature
names, training count and a digest of training IDs; `from_dict` validates a
same-version parameter snapshot. It is not an independent attestation of data.

Artifacts also record maximum training-feature prediction time and maximum
training-label availability time. Unknown/missing timestamp provenance remains
null; it is not inferred from date or race identity. The prediction engine must
reject unknown cutoffs and any cutoff not strictly before the new prediction.
These metadata only support consistency checks on self-reported input times;
they do not independently authenticate when real information became available.

Per-feature acquisition/availability/revision metadata are permitted predictor
metadata, not numerical features. Their cutoff validation is mandatory in the
input-validation/engine layer before invoking fit/predict. Model-level checks
cover shape/finite values and known outcome-field rejection; direct calls to
models do not independently attest chronological eligibility. Odds revisions
may precede acquisition; both must be no later than prediction time.
An odds snapshot must explicitly supply aware `acquired_at`, `available_at`
and `revision_at`. All three must be no later than prediction, and availability
must not precede acquisition. Missing availability is INVALID, never inferred.

Numerical policy: stable max-subtracted softmax; exponent differences smaller
than -700 are floored at -700 to keep tiny positive floating-point mass. The
joint is normalized again in log space. This changes exact factorization only
at extreme numerical tails; normal-range conditionals equal the joint product
within floating-point precision. No numerical underflow is interpreted as a
truly impossible event. Serialized absolute weights above 1e6 are rejected.

Reproduce synthetic model tests from this directory:

```
python -B -m unittest discover -s tests -p test_models.py -v
```

The tests verify learning, conditional interactions, active-domain mass,
factorization, numerical stability, serialization, odds isolation and missing
market handling. They establish software behavior on synthetic fixtures only.
Real-race gain, calibration, profit and superiority to Model 1.0 remain
**UNVERIFIED**.
