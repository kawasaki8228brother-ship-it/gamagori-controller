# P2 contract, pre-deadline odds and point-in-time review

Status: IMPLEMENTED + TESTED for the stated synthetic scope; Claude review pending.
Application / real-data execution: HOLD. production_go is false throughout.

## Change boundary

Parent: `148c156f472c874075a0b25d4f0b6b7e9fafdcfe` (P1 lineage).
This component adds a mutation harness and diagnostic only. It reuses the frozen
`model11.shadow_preparation.capture_review.required_mapping_inventory`,
`model11.shadow_launch.sources.SourceAdapter`, and
`model11.offline_refinements.point_in_time.audit_point_in_time` from that parent.
It does not integrate a new P1 component, replace RAW_V001, implement an official
source mapping, fit a normalizer, select model/BOX parameters, read A/B outputs,
create an external reader, or modify any writer/LOCK/StateMachine.

Only invented 2099 fixtures are generated. No real captures, credentials,
HTTP request, official-site access, production database, or public raw race data
are used. The imported adapter is invoked on in-memory bytes. Test doubles deny
source file, socket and database access during direct adapter/diagnostic calls.
No freshness-policy number or candidate is adopted here.

## What 264 means (measured, not an invented official schema)

The frozen inventory returns 264 local destination requirement PATTERNS:

| Inventory scope | Patterns | Concrete expansion used |
| --- | ---: | ---: |
| ONE_CAPTURE | 81 | 81 |
| EACH_INCLUDED_BOAT | 58 | 348 (six boats) |
| ONE_FULL_FIELD_TICKET | 120 | 120 |
| EACH_CAPTURE_HISTORY_ENTRY | 5 | 5 (one recorded history entry) |
| Total | 264 | 554 |

Inventory JSON SHA-256 (sorted compact ASCII JSON):
`9e9c4b7fe2e1530753902ef0f0f4bbca92c634feb79a22adceb689946eba8892`.
This is an integrity identifier of the local contract list, not proof of any
actual official field, original or approved mapping.

Each of 554 concrete destinations is subjected to missing / null / wrong-type /
nonfinite mutation on a deepcopy: 2216 attempt records. The unmodified synthetic
profile converts READY. Actual outcome: 2208 HOLD, eight conditional N/A, zero
unexpected outcomes, and original input unchanged. RAW/course bytes and current
history hashes are re-bound after mutation, so a field defect is not hidden by a
trivial stale envelope checksum. Nonfinite adversarial JSON is intentionally
invalid; the frozen strict decoder must refuse it.

The eight N/A records are the four mutations for each of the two PRIVATE review
original hashes. Those originals are not supplied or required for the synthetic
profile. No dummy approval original is generated. They remain externally blocked
for private use. This is not a blanket claim that every missing value is invalid:
under frozen EXHIBITION_ONLY, a separate measured probe with frame observation
null remains READY, while selected exhibition observation null is HOLD. Leaf
mutations cover both present, non-null observations in the matrix. Missingness
requirements for other policies are retained from the frozen contract; this one
profile does not prove all possible observation combinations.

Further regression checks preserve legitimate zero numeric values, distinguish
missing/null/bool from zero, require motor identity/version agreement, and reject
future acquired/available/revision times. F/L=true is preserved as a research
warning (`FL_PRESENT_RESEARCH_INPUT`), not changed into a universal error.
A scratched boat conflicting with the six-active list is HOLD
(`SCRATCH_ACTIVE_MISMATCH`). Neither outcome is production admission.

## 120-odds diagnostic and timing boundary

`audit_odds_snapshot` requires the exact 120 distinct triples of six boats,
positive finite nonboolean numeric gross payout multiples, strict known aware
acquired/available/revision timestamps, temporal order and prediction-before-
deadline. There is no implicit unit conversion, missing value imputation, final
odds substitution, or guessed snapshot role. Caller must explicitly supply
`PRE_DEADLINE`; unknown or final/post-result role is HOLD.

`audit_odds_raw` also requires original bytes, exact byte SHA, strict UTF-8 JSON,
and duplicate-key rejection before dictionary collapse. Empty/oversize bytes,
malformed/nonfinite JSON and wrong SHA are HOLD. The 4 MiB upper bound is reused
from the existing capture engineering limit, not a freshness limit. Dictionary-
only input explicitly cannot prove absence of duplicate keys in the original.
Self-consistent SHA is not independent source authentication.

Age is observed separately for all three timestamps. The maximum age is null,
`freshness_status=UNVERIFIED_NO_APPROVED_MAX_AGE`, market execution eligibility
is false, and application remains HOLD even when all contract claims agree.
The frozen converter has its existing research age behavior; this diagnostic
does not promote that behavior to a formally approved Shadow or F5 policy.
Even very old pre-prediction odds do not receive a FRESH/PASS label.

## Past-data point-in-time checks

The wrapper delegates to the frozen point-in-time checker. Tests include all 30
feature observations at each of the three timestamp positions, post-preservation
revision of a supposed immutable capture, unknown/final odds, result/payout as a
feature, and training labels/features unavailable at fit time. Inconsistency is
HOLD. Normalizer/model fit cutoff must precede prediction. This verifies declared
claims on invented snapshots; it does not authenticate history or recover missing
past pre-deadline snapshots. Market selection/comparison uses only hypothetical
future-captured pre-deadline odds in this suite.

## Executed test evidence

| Runtime | OS | OpenSSL | SQLite | Final result |
| --- | --- | --- | --- | --- |
| Python 3.12.14 | Linux 6.18.57 x86_64, glibc 2.41 | 3.5.8 (25 Aug 2026) | 3.53.1 | 17 PASS, 0 failure/error/skip, 7.600 s |
| Python 3.14.3 | Linux 6.18.57 x86_64, glibc 2.41 | 3.5.5 (27 Jan 2026) | 3.50.4 | 17 PASS, 0 failure/error/skip, 5.525 s |

These are isolated synthetic checks, not observations of Render or a production
Python/OpenSSL/SQLite combination. The 3.12 environment references the available
read-only system-site runtime; it is not represented as a fresh production clone.
The local modules use the standard library plus the frozen package. Initial
14-case runs and final expanded 17-case runs were both retained; no failing run
has been relabelled PASS. The second revision deliberately added F/L/scratch,
training chronology and original-byte-bound cases after initial checks.

Preserved private raw evidence (to be inventoried by the parent):

- `contract-tests312-initial.raw.log`: original 14-test run.
- `contract-tests314.raw.log`: original 14-test run.
- `contract-tests312-final.raw.log`: final 17-test run; unchanged unittest output.
- `contract-runtime312.raw.json`: separately measured environment, not inserted
  into or represented as part of that original unittest log.
- `contract-tests314-final.raw.log`: final 17-test run with environment header.
- `contract-matrix314.raw.json`: all 2216 case records, environment and conditional
  null-observation probes. It contains only synthetic local target paths/reason
  codes, never raw capture values, URLs, secret paths or exception text.

## Reproduction and reviewer claims

Run from the isolated repository root; `PYTHONPATH=development/model11`.
Use `python -B` and an environment with external networking denied. No package
installation, test cache, application startup or database is required.

| Claim to check | Command / test | Expected evidence |
| --- | --- | --- |
| Exact frozen inventory, no replacement schema | `python -B -m shadow_offline_v008.contract_matrix` | 264 patterns, 554 targets, inventory SHA above |
| Every applicable target rejects four mutation modes | same module command | attempts 2216, HOLD 2208, N/A 8, failures empty, unchanged true |
| Conditional requirements are not blanket failures | final raw matrix conditional probe | frame null READY, exhibition null HOLD under EXHIBITION_ONLY |
| No guessed F/L or scratch behavior | discovery test `test_fl_is_a_research_warning_and_active_scratch_is_a_distinct_hold` | warning retained; scratch conflict HOLD; go false |
| No file/network/DB source calls | discovery test `test_adapter_and_diagnostic_perform_no_source_network_database_or_file_io` | denied-call doubles remain uncalled |
| Exact odds domain, no final fallback | `OddsAuditTests` in discovery | each missing ticket, invalid unit/value/time and final role held |
| SHA consistency is not authenticity | raw/dictionary odds tests | strict duplicate rejection; authenticity UNVERIFIED |
| No invented freshness threshold | all valid odds report tests | age observed, threshold null, eligibility false |
| Historical and training chronology enforced | `PastInformationTests` in discovery | future/revised/late-fit inputs held |
| No existing-source rewrite | parent Git-blob comparison | all 320 parent files byte-identical |

Portable complete command (also covers all claims with valid discovery imports):

```sh
PYTHONPATH=development/model11 python -B -m unittest discover -s development/model11/tests -p test_shadow_offline_contract.py -v
PYTHONPATH=development/model11 python -B -m shadow_offline_v008.contract_matrix
```

The complete discovery command executes the named tests without assuming a test-
package import layout. Source revision counts at handoff: contract_matrix creation
1, odds_audit 2, tests 2, this document 2. A documentation-only correction aligned
the review table with the actual OddsAuditTests class and discovery commands.
The latter two code files are frozen under the two-edit safety gate.

## External blockers and STOP conditions

| Blocker | Who / needed evidence | Minimum resolution path |
| --- | --- | --- |
| Actual official field mapping, units, source identity | HQ14 supplies privately observed structure; Claude independently reviews | 1. Capture privately under separate GO. 2. Bind source fields/units/times and immutable original hashes. 3. Independent contract review. No public raw data. |
| Private approval originals and receipts | HQ14 / Claude; originals with independently checked SHA | 1. Obtain actual records privately. 2. Independently match their scope and bytes. Never substitute self-reported review hashes. |
| Approved odds freshness policy | HQ14 / Claude / Andy | 1. Review pilot timing/missingness. 2. Approve policy before evaluation. 3. Add separately audited boundary fixtures. No candidate value is proposed here. |
| Past pre-deadline snapshot possession | HQ14 private custodian | 1. Inventory actual point-in-time originals. 2. Verify original availability/revision chronology. If absent, keep historical market comparison blocked and use future capture only. |
| Production-specific runtime / source authentication | approved independent Shadow operator / reviewers | 1. Supply private environment and time evidence under separate GO. 2. Review observations. 3. Run approved preflight; synthetic PASS alone cannot admit private data. |
| F5 evaluation inputs and independent approval | HQ14 / Claude / Andy | Retain existing OPEN values, holdout separation and go=false until separately approved. |

Software portions above are IMPLEMENTED and TESTED within stated fixture coverage.
These external items are BLOCKED_EXTERNAL. There is no known FAILED_OPEN item in
this final 17-test component, but comprehensive JSON fuzzing, actual official
compatibility, private source authenticity and real-data performance are not
claimed. A newly discovered uncaught validator exception is EXCEPTION_UNVERIFIED
and a failed software check, never a rejection PASS. Unexpected mutation
acceptance, raw mismatch, unknown time, final odds, or source ambiguity is HOLD.
If a third content revision becomes necessary, stop and report before editing.

No production application, Shadow start, automatic approval, threshold adoption,
model superiority or profit claim follows from this report. Independent Claude
review and the user's separate deployment/real-data GO remain outstanding.
