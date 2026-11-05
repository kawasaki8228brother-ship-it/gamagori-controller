# N1-only independent code and reproduction review

Reviewer: Codex validation sub-agent, independent of the source patch and the
new N1 test author. This is **not Claude review**, external-source authentication,
real-data validation, formal model adoption or production GO.

Reviewed source: `model11/revision_v003/course.py`, 20,110 bytes,
SHA-256 `ca28937aa1784fc37fa9a9539e0219d27570390ced01b3a0a2f77268238ed264`.
Parent reference: `62721c20676177bac171f97b0488412b07b63594`.
All executions used Python 3.12.14 on Linux in the local isolated workspace,
stdlib only. All data originated from invented year2099 synthetic fixtures.
PRIVATE_REAL classifications were attack metadata on those fixtures, not real
race inputs. No network/service/GitHub/Production operation was performed.

## Result and concrete reproductions

No remaining concrete N1 defect was found in this review. The new helper enforces
recognized classification, an exact boolean flag and a source registered for
the observation's definition before applying its classification-family check.
OFFICIAL prefix alone is never sufficient. Each non-null observation is checked,
including the source unused by FRAME_ONLY or EXHIBITION_ONLY.

An independent 69-case validator matrix covered all three unchanged policies:

- Valid synthetic observation/report equality against the archived original.
- Missing/unknown/non-string classification; missing/null/non-bool flags;
  contradictory false synthetic flag.
- Selected and unused sources: registered official source on synthetic data,
  missing source, unregistered OFFICIAL-prefixed source, dict-valued source,
  registered source for the wrong observation definition.
- Correct PRIVATE_REAL/false plus both registered OFFICIAL sources; these report
  consistent claims with authenticity UNVERIFIED and production_go=false.
- PRIVATE_REAL/false with either synthetic source; both selected and unused
  mismatch cases HOLD.

Unknown values containing a private sentinel were not echoed in error/reason
reports. Returned reasons contain fixed text and fixed observation names only.

Propagation reproductions used a contradictory registered OFFICIAL frame source
on a synthetic exhibition-only race, so the attacked observation was unused:
fit, distributions, conditionals, explain and direct predict all rejected it.
Walk-forward rejected the same source mismatch with
`HOLD:COURSE_GATE:COURSE_SOURCE_CLASSIFICATION_MISMATCH`.

Correctly classified private-looking OFFICIAL claims remained blocked at direct
engine execution with `HOLD_REAL_INPUT_REVIEW_REQUIRED` and at walk-forward with
`HOLD:REAL_INPUT_REQUIRES_APPROVED_PREREGISTRATION`. Validator consistency is
therefore not confused with execution authorization. The internal course/model
claim validator is not represented here as an authentication mechanism.

The newly added regression file was independently executed:

```sh
python -B -m unittest discover -s tests -p test_revision_v004_n1.py -v
```

Observed result: **7 test methods passed**, including their subcase matrices.
This document does not claim that the full old suite, other Python versions or
the complete demo were independently rerun by this reviewer; root records those
checks separately.

## Preservation and no algorithm change

The archived original was loaded locally in a separate Python namespace, using
the same unchanged dependencies. The three policy objects and hashes matched
exactly:

| Policy | SHA-256 |
|---|---|
| FRAME_ONLY_V001 | 1d7561a7ee56622f0b3eb8af88b8ca472255d8f8da5620d9693794133d4870b0 |
| EXHIBITION_ONLY_V001 | cdd3bb6b1e660445d428d31757447c4d7b93a8b23b436b22cc1c2a65e2b77aef |
| EXHIBITION_ELSE_FRAME_V001 | 97ed0546cdf6831000a90a42532fbb1f6f95740545935d2d2fa0d03b9e2a8997 |

For valid synthetic data under every policy, fixture output and validation
reports matched the archived original exactly. Actual learned model
serialization, prior counts, distributions, conditionals and explanations also
matched exactly in small deterministic train/future-prediction reproductions.
The helper adds a rejection boundary; it does not change selection, learning,
prior, policy definitions, market pooling, portfolios or statistical algorithms.

The archived target matched the preceding local final target byte-for-byte:
17,860 bytes, SHA-256
`48b53e1b372c9c8b63027567d920514ac4e23668f0373d9f4f9a559789f0f66b`.
All **134 other existing files** were compared against that preceding local final
workspace; no changed bytes were found. This independent local comparison is
distinct from root's later remote commit/readback verification.

## Limits and remaining authority gates

Registered source names, strict flags, timestamp claims and local SHA consistency
do not establish an official source, actual person, historical availability,
independent authenticity or predictive improvement. OFFICIAL source IDs remain
declarations. Real-data execution, preregistration, independent Claude review and
Andy's individual authorization remain outside this work. No PASS here upgrades
those OPEN/UNVERIFIED or execution HOLD conditions.
