# Stage9: real racelist extraction, with explicit status/effective-time hold

Base: bc450108f3d23132a826a2e633ff4bc2ada32640 (Stage8).
No runtime integration, main merge, deploy, production data or task changes.

## New evidence
Review CI run 35376071323 captured 2026-09-18 Gamagori racelist 3R and 12R
as raw HTML. Artifact 10559808810 ZIP SHA256:
8bf17190de2072af330e9a98c5fd4d2151f7988a29267ccca84a52bcc391b1d0.
ZIP digest and all five saved HTML body digests were independently checked.
The two new roster bodies are:
- 3R: b5128b35baefcda0656edf12fd3123161bd14f6fa81ad8c65194719dad91e1bf
- 12R: e5bec0d63573914237d1903d075155734d49476a074cf0995e07378aebfe6111

These were acquired after the races (2026-09-19 JST), not at the old decision
time. HTTP Date was observed. It is not the roster effective time. No verified
roster publication/effective timestamp was established from this capture.

## What the candidate extracts
roster_semantics.py reads the body, not the requested URL, to establish the
recognized layout's context: page role/title, venue label/image code, selected
date, all same-race menu links, selected race and the complete race navigation.
The year is derived from body links and checked for internal consistency, not
from an independent signed date. This is not transport authentication.

The table uses semantic headers with expanded row/column spans. Each listed
boat has a registration number whose text and profile link must agree, plus
original/normalized name and a locator. Duplicate/missing context, conflicting
links, wrong venue/day/race, malformed spans and duplicate identities fail
closed. Missing rows never create an inferred reduced active field. Historical
F/L/withdrawal results in past-performance columns do not define current status.

Local replay matched all six listed registrations/names on each captured page:
- 3R registration order: 5169, 5134, 5288, 5337, 5301, 5411.
- 12R registration order: 5234, 5068, 5252, 5246, 5222, 5280.

## Critical distinction / decision not implemented
A normal roster listing has not been reviewed here as an authoritative
ACTIVE-at-decision signal. The parser returns LISTED_STATUS_UNVERIFIED, not
ACTIVE. Its real-HTML SemanticValidator adapter returns UNKNOWN slots to the
unchanged Stage8 entry, which consequently remains UNVERIFIED. This is a real
body/listing extractor, NOT a completed ACTIVE/WITHDRAWN semantic validator.
No withdrawal marker mapping or reduced-field evaluation policy was invented.

The temporal helper reports capture-after-requested-decision as FAIL for that
as-of use, and treats same-day or old captures without source-effective-state
proof as UNVERIFIED. It never manufactures a freshness PASS, TTL, cutoff or
source timestamp from HTTP Date, hash agreement or recent acquired_at.
This helper is a candidate diagnostic, not yet a live gate.

Before a policy maps normal listings to ACTIVE, external design advice is
requested: is ACTIVE to mean listed by the authoritative source as observed,
with separately required live withdrawal/sales-state and freshness evidence?
Which independently verified source semantics cover withdrawals/cancellations?
That mapping and operational freshness acceptance remain unimplemented.

## Tests and scope
All 321 baseline tests retained. Sixty added synthetic layout/context/time
cases passed locally (381 total). Remote CI/XML/artifact must be verified
separately against its exact commit; raw replay is not a full live-E2E test.
All baseline runtime/prediction modules remain unchanged. Only review capture
tooling is modified, plus this new module, tests and document.

Old readiness API remains callable; exports alone are not a security boundary.
Future live integration must centralize the approved entry and enforce its
call graph with tests, while also validating transport/storage provenance.
No A/B/F prediction, official result, stake, or revenue value is changed.
