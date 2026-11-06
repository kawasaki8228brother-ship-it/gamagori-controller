# Stage7: observation/readiness candidate (2026-09-19)

Base: `723c9ae42eead56d7ed56e997fb99d10792ccf01` on draft PR #2.
Scope: pure candidates and review tooling only. No live fetcher/state-machine
connection, no model changes, no historical writes, no main merge or deploy.

## Implemented boundary

`observation.py` stages exhibition, start/entry, and weather independently.
Each helper writes to a temporary snapshot. Exceptions discard that entire
section, including a valid-looking prefix; other sections still return.
The original strict `parse_beforeinfo_snapshot` and its tests are unchanged.
Whole-body type/size failures remain fatal for this parser call.

Each section has PARSED/PARTIAL/MISSING/PARSE_FAILED. Only known parse errors
map to the existing SOURCE_PARSE_FAILED. Success does not claim a prediction
revision/no-change; missing is not proof of SOURCE_NOT_PUBLISHED.

`coverage()` derives the existing three capabilities plus `start_data_six`.
F/L alone counts as recognized but not numeric. F.01 keeps raw text, F and .01;
it is not ordinary +.01 ST. A marker-only observation does not automatically
call qualitative_delta(DOWN) or establish a real-race disqualification.

## Named policy, not universal C readiness

`readiness.py` defines C_EXHIBITION_ONLY_NO_MARKET_V1_CANDIDATE.
Required: exhibition_six, entry_six, start_data_six, and successful required
sections. Weather and odds are deliberately unused by THIS policy. This is a
prospective dependency contract, not evidence that all historical A/B decisions
ignored weather. Any future evaluator using these inputs needs its own policy.

Separate explicit evidence checks cover PAGE_IDENTITY, EXHIBITION_FRESHNESS,
START_FRESHNESS and OFFICIAL_PARTICIPANTS. All default to UNVERIFIED. A PASS
assertion requires evidence references, but references alone do not prove the
assertion: acquisition and independent content validation are still unbuilt.
Weather reference race is not used as exhibition/start freshness. No age limit
or reserve threshold was invented. Input eligibility is NOT permission to
append a REVISION, a storage-completion guarantee, or a BET decision.

This candidate supports only an independently established six-boat set.
Reduced fields return REDUCED_FIELD_POLICY_NOT_IMPLEMENTED; missing cells never
shrink the expected set. Proper authoritative withdrawals/refunds remain open.

## Verification

Baseline 19 local source blobs matched the GitHub tree. Baseline 150 tests
passed unchanged; Stage7 adds 92 cases. Local result: 242 pass / 0 fail / 0 skip.
CI result is to be verified against its own commit, XML and artifact; a local
pass is not a CI certificate.

Stored Stage5 post-incident 12R beforeinfo replays without changing any existing
field. Without identity/freshness evidence it returns UNVERIFIED, not eligible.
A deliberately mutated weather value fails only weather and leaves the required
fields identical. Synthetic evidence is clearly labelled in that policy test.
Stored 3R/12R odds remain 120 entries each with unchanged values.

## Remaining integration gates

- Independent body identity, official participant set and per-section freshness.
- Partial-observation persistence with provenance; returned data is not saved data.
- A real exhibition-only evaluator that consumes marker-aware values and does
  not silently read unused weather/odds. No new scoring direction is defined.
- Deadline/live-state and durable-write completion policies, PR #1 integration,
  SQLite migration tests and A/B access isolation.
- Original-incident HTML is unavailable; successful replays are not live recovery.
