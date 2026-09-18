# Stage8: bind participant values to their exact evidence snapshot

Base: 2289b38e981d2785577042c46b3d7a19f05913a9, draft PR #2.
Scope: a pure candidate entry and tests. No live connection, model change,
production write, main merge or deploy. Stage7 APIs and tests remain unchanged.

## Resolve the two-channel question

The new entry does not accept expected_boats or an OFFICIAL_PARTICIPANTS
check supplied independently. It accepts a target race, one immutable roster
snapshot and an application-installed semantic validator. Both the participant
set and verification status are derived in the same call from the same bytes.
They are passed to legacy ReadinessContext only inside that call; the caller
cannot override either participant channel through this new entry.

ParticipantEvidence binds target date/venue/race, derived active boats, source
snapshot ID, requested/response URLs, acquired_at, raw-body SHA256, validator
version, locator, status and test-only classification. Its canonical SHA256
allows integrity checks on this association. Changing one field without updating
the binding invalidates it. This is NOT a signature: rewriting the whole record
and recomputing its hash remains possible. A trusted producer/transport/storage
boundary is still required. Existing legacy APIs can still be called directly;
this is not a process sandbox or a database permission change.

## Trust boundary and explicit missing work

No production semantic validator is installed or implemented in this stage.
SemanticValidator is dependency-injected CODE configured by the application,
not a model-supplied PASS boolean. Its implementation must verify body identity,
explicit source semantics for every slot and evidence location. It must never
infer participant status from beforeinfo/odds gaps. The only implemented
validator is a synthetic test double inside tests. It is rejected by default;
allow_test_validator=True is used only by synthetic tests.

The candidate verifies raw-body digest, requested and response URL context,
HTTP/content type, timezone and non-future acquisition. These checks do not
prove body truth, authenticated transport, freshness or the latest roster.
Without the semantic validator it returns UNVERIFIED. With a reviewed validator,
its returned body identity must match the target race. The active set derives
only from all six explicitly accounted-for slots. Missing/UNKNOWN slots do not
shrink the set. Explicit withdrawal may produce a five-boat value; the unchanged
Stage7 reduced-field policy still prevents readiness PASS.

Only the official racelist URL role is currently admitted. Supporting another
independent authoritative endpoint requires an explicit adapter review. No data
was fetched or officially classified through this entry in Stage8.

Other Readiness checks (page identity and exhibition/start freshness) are still
caller assertions inherited from Stage7. Participant freshness/authoritative
state-at-decision also needs a future policy. An old snapshot can have a valid
binding; this does not make it current. No TTL/cutoff/model weights were invented.
Readiness output is not permission to bet, revise or persist after a deadline.

## Verification

The 24 local baseline files were compared with the current GitHub tree via Git
blob SHA1; all matched. The 242 baseline tests passed unchanged. This stage adds
79 tests, for 321 passing locally with zero failures or skips. CI is a separate
check to be recorded by its exact commit/run/XML/artifact after completion.

Coverage includes field tampering, body hash mismatch, spoofed host/redirect,
wrong date/race/body, duplicate query parameters, missing slots, explicit
withdrawal, unknown statuses, malformed metadata, timestamps, test-only bypass,
missing validator, read-only behavior and prevention of the old two-channel
participant override. Positive participant/readiness cases are SYNTHETIC, not
independent official-source verification or evidence of live recovery.

## Next integration step

Implement/review the actual semantic roster validator against independently
labelled source HTML, and source-specific identity/participant-freshness
checks. Wire this entry only after reviewing those checks and the full runtime
chain. Keep partial observation persistence, deadline/live-state checks,
PR #1 integration, A/B isolation and F design as separate outstanding work.
