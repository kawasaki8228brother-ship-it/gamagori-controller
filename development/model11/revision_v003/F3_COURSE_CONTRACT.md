# F3: frozen pre-LOCK course definition and prior binding

**PROPOSED / synthetic software verification only.** No real pre-race entry
original, actual race-entry result, private source, service or production rule
has been obtained or changed. Source timestamps and evidence hashes remain
self-reported; external authenticity is **UNVERIFIED**, production GO=false.
All prior 88 files remain byte immutable.

## Meanings and predeclared policy

`FRAME_NUMBER` means the registered boat/frame number, so course=boat ID.
`EXHIBITION_ENTRY` means an observed pre-LOCK exhibition entry position. It is
not the final actual entry learned after the race. The two meanings are not
silently exchanged because both happen to contain integers 1–6.

`COURSE_POLICIES` exposes three fixed canonical policy objects. The caller must
choose the object before fitting or looking at evaluation results:

| policy_id | Selected observation | Allowed definitions across fit and prediction |
|---|---|---|
| FRAME_ONLY_V001 | frame | FRAME_NUMBER only |
| EXHIBITION_ONLY_V001 (default) | exhibition | EXHIBITION_ENTRY only |
| EXHIBITION_ELSE_FRAME_V001 | valid present exhibition; otherwise frame only if exhibition is explicitly null | Both definitions under this one frozen mixing policy |

Unknown/modified policy objects HOLD. No new mixing rule is learned from results.
The mixing policy is a declared research comparison, not evidence that the two
definitions are statistically interchangeable or formally adopted. A null frame
or exhibition is distinct from an invalid observation. **Both present inputs are
validated, even the one a policy does not select**. Future, unknown, malformed or
untrusted-source-present exhibition never triggers fallback. Missing required
exhibition under the default policy HOLDs even with a valid frame record.

## Per-race observation and source contract

Every race requires:

```text
course_policy_id = one fixed policy ID
course_policy_sha256 = canonical SHA-256 of that exact frozen object
course_inputs = {frame: observation | null, exhibition: observation | null}
```

An observation has **exactly**:

```text
definition: FRAME_NUMBER | EXHIBITION_ENTRY
courses: {"1": integer course, ..., "6": integer course}
source_id: predeclared identifier
acquired_at, available_at, revision_at: strict aware timestamps
evidence_sha256: 64 lowercase hex digits
```

The domain exactly matches all boat records, including retained inactive records.
Courses are distinct integer positions 1–6; bool is not an integer course. For
six boats this is a permutation of 1–6. Reduced-field records use distinct
positions in that domain; this does not adopt a formal scratch-betting policy.
Frame values must equal boat IDs. Exhibition may differ from frame numbering.

Times must be <= prediction, acquisition <= availability, acquisition <=
revision. Naive times, unknown `-00:00`, excessive precision, invalid dates or
offsets HOLD. Selected `boats[].course` must equal the selected observation, and
each `state_times.course` must contain exactly the same three timestamp strings.
Equivalent-looking aggregate times never substitute for observation provenance.

Proposed source IDs are definition-specific:

| Definition | Declared source IDs |
|---|---|
| FRAME_NUMBER | OFFICIAL_FRAME_PRELOCK_V001, SYNTHETIC_FRAME_V001 |
| EXHIBITION_ENTRY | OFFICIAL_EXHIBITION_PRELOCK_V001, SYNTHETIC_EXHIBITION_V001 |

The OFFICIAL identifiers are **contract placeholders**, not a verified live
source adapter or proof that any official site provided an observation. Their
real mapping, originals, availability history and independent evidence require
HQ14/Claude private review before real use. FINAL_ENTRY, ACTUAL_ENTRY,
POST_RESULT_ACTUAL_ENTRY and other unknown definitions/sources HOLD. No source
URL, proxy/credential value or private path is accepted as a source ID.

`validate_course(race,policy)` also applies the old input validator, then returns
`eligible`, fixed-code `errors`, `status`, `definition`, `policy_sha256`, and, only
on a consistent result, `selected_observation` and both `observations`. This
records the selected definition plus all present sources/times/evidence for the
forecast audit. Invalid raw source/definition values are not echoed. An
`eligible=true` result means internally consistent claims, never external proof.

## Learned model and serialized policy binding

```python
CourseBoundModel(name, model_config=None, course_policy=None)
model.fit(races, outcomes)
model.distributions(race)
model.conditionals(race, first=None, second=None, stage="raw")
model.explain(race, first=None, second=None, stage="model")
payload = model.to_dict()
restored = CourseBoundModel.from_dict(payload)  # module from_dict also provided
```

The model wraps the unchanged `ConditionalRankModel` actual learning kernel.
Every training record is validated against one frozen policy. Every public
distribution, conditional and explanation call repeats the same policy guard.
The learning kernel receives exactly the selected pre-LOCK numeric courses; its
training course-frequency prior and prediction-time prior lookup therefore use
the same declared semantics. Tests independently derive prior counts from the
selected exhibition positions and result labels, then compare actual learned
counts. Outcomes remain separate training labels and never become predictor
entry observations.

The wrapper proxies `name`, a detached `config`, `training_count`,
`training_max_available_at`, `training_max_prediction_at`. `course_policy` is a
detached copy. Frozen hash changes or inconsistent live training-policy binding
STOP. The engine must still enforce actual training-before-prediction chronology,
fitted status and normalization usage/cutoff gates; this wrapper does not grant
permission to forecast with a training-only normalization snapshot.

Serialization contains the full frozen policy, policy SHA, training policy SHA,
observed training definitions, hash of selected per-race training course
provenance, the actual old model parameters, and a full internal self-hash.
Roundtrip validates exact schema, hashes, supported canonical policy, learned
parameter shapes and training bindings. Missing provenance, altered policy,
unsupported authority claims, inconsistent training definitions or modified
payloads STOP. The self-hash is consistency evidence, not a signature. A party
able to replace an entire artifact and all hashes can forge internal claims;
independently frozen input/model artifact evidence is still required.

## Synthetic fixture and regression evidence

`apply_course_fixture(race, policy_id="EXHIBITION_ONLY_V001",
exhibition_present=True)` accepts only explicit `synthetic=true`,
`data_classification=SYNTHETIC_ONLY`, year2099 old-schema races. It returns a
detached race, preserves the original dataset/outcomes, creates declared
synthetic observations, deliberately rotates exhibition positions relative to
frame numbers, binds selected numeric courses and exact state times, and sets
legacy `human_box_input=null`. It never invents a real historical exhibition or
post-race actual entry. Missing-exhibition fixtures intentionally HOLD under the
exhibition-only policy and are eligible only under the declared fallback policy.

Tests cover normal frame/exhibition input, numeric mismatch, state-time mismatch,
future acquisition/availability/revision including unused observations, invalid
time precision/offset, forbidden post-result and unknown source definitions,
bad evidence SHA, duplicate/missing/extra/bool courses, null-only fallback,
unknown/modified policy, forbidden unannounced mixing, actual training prior
counts, shared train/predict policy, serialization roundtrip, internal tampering
and unchanged original fixture labels.

```sh
python -B -m unittest discover -s tests -p test_revision_v003_course.py -v
```

Real-data source mapping, independent provenance, meaningful comparison of the
three policy candidates, unseen-future skill and formal adoption remain OPEN.
No production, A/B, Model1.0, BOXV1, LOCK/deadline rule or old artifact is changed.
