# Independent review of the document-only F5 record

Scope: the received-policy ledger, source/receipt reference, OPEN partition
register, companion preregistration/separation/status/checklist text, and static
consistency checks. This reviewer wrote only this review and
`tests/test_document_constraints.py` within the new document directory. No model,
evaluation engine, prediction, private data, source connection, host operation,
Shadow process, existing prompt/configuration, or old model test suite was run.

Outcome: **15 static test methods PASS** on Python 3.12.14 / Linux, including
12 independent document-mutation methods and three parent-byte regression
methods. The final package-root run reported `Ran 15 tests in 0.038s / OK`.
The actual baseline contains 245 unique parent paths; all **245/245** retain
their exact bytes and sizes. No current execution permission follows from these
software checks. Formal Claude review and original-source matching remain
pending.

## Reproduce the scoped checks

From `development/model11/`:

```text
python -B -m unittest discover -s f5_preregistration_v007/tests -p 'test_*.py' -v
```

This discovers only new static/document tests. It does not discover or execute
the old model/evaluation tests. Parent-byte verification reads and hashes files;
it does not import or run their contents.

## Executed constraint checks

| Area | Observed result |
|---|---|
| Actual three JSON records | DOCUMENT_CONSISTENT, empty issue list, production GO false; records remain unmodified |
| M0 drift | HOLD for alpha=.05, power drift, m=6, six confirmatory weight tests, changed endpoint/day weighting/comparator snapshot, two-sidedness, optional stopping, post-hoc changes, or a claimed implemented statistical pass |
| w=1 | HOLD if market-only is relabelled as MODEL superiority |
| Future M1 | HOLD for a different model/alpha/T/grid, B/C confirmatory promotion, holdout-driven selection, or executable application |
| OPEN/nonadoption | HOLD for adopting 24/60 values, filling SESOI, dropping an OPEN item, adopting prior examples, or adopting F2 thresholds |
| Operation authority | HOLD for each ledger operation permission switched true, source-reference Shadow GO, registry enablement/execution/application/production GO, or pilot performance/profit/promotion/holdout permission |
| Source provenance | HOLD for fabricated original or receipt SHA values, a claimed completed HQ14/Claude match, or invented G1-G6 definitions |
| OPEN registry | HOLD for actual/sealed dates, unknown roles, a filled sd_day, claimed verified sd_day, automatic pilot extension, unapproved pilot-development reuse, or a claimed sealed holdout |
| Synthetic partition illustration | Disjoint invented 2099 roles are FIXTURE_CONSISTENT only; pilot/holdout race or day overlap, chronological inversion, unknown roles, training-selection overlap, and unresolved pilot-development reuse are HOLD |
| Pure behavior | Valid document/fixture audits make no file, socket, or database calls under injected failures; input records are unchanged and diagnostics omit a submitted sentinel value |
| Parent preservation | All 245 parent files match; duplicate baseline rows cannot fake the count; an altered expected digest is detected without editing a parent file |

The partition examples contain invented metadata only, with no forecasts,
probabilities, outcomes, losses, actual membership, or operational assignments.
Their role/day counts are not minimum sample requirements or adopted dates.

## Findings resolved before the final run

The first independent mutation run found one accepted contradiction: changing
`additional_pilot_span` to an automatic extension until K>=2 still returned
DOCUMENT_CONSISTENT. The owner bound that field to the explicit separate-review
OPEN state, together with pilot-development reuse, undefined sd_day status, and
the exact OPEN/future-unassigned role statuses. The same twelve independent
methods then passed. The change is document consistency enforcement, not a new
pilot duration or statistical rule.

An initial package-root discovery exposed a working-directory dependency in the
owner's parent-regression test import. The owner changed it to load the static
auditor by explicit file location. The final fifteen-method command above runs
successfully from the package root. No unresolved blocking finding remained in
this examined static scope.

## Manual semantic review

M0 is recorded as the received DECIDED policy: one frozen champion versus the
same complete pre-deadline 120-outcome market snapshot, joint120 log-loss,
identical paired race eligibility, equal day weighting, one-sided alpha=.025,
power target=.8, and m=1. Six selection weights do not become six confirmatory
tests. No optional stopping, holdout-driven replacement, or post-hoc change is
authorized. The text explicitly defines `D=LL_market-LL_champion`, positive for
the champion; its bridge to an older `d=LL_model-LL_market` convention does not
change any existing calculation. A sign reversal leaves sample SD unchanged
where defined. A chosen w=1 is market-only and cannot establish model
superiority.

M2 is the first third-research Shadow operating-day pilot **entry rule**, not an
instruction to terminate after one day or to run all four candidate calendar
days. The 2026-11-21 through 2026-11-24-or-later window remains a candidate;
actual start, duration, ownership, and individual execution GO are unassigned.
K=1 cannot estimate day-level sample SD with K-1. The record keeps that value
UNVERIFIED/null and does not automatically extend the pilot or replace day
variation with race-level variation. Pilot data never become formal holdout and
support no improvement, profit, or promotion claim.

M1 is future design only: A/hierarchical, course alpha=.5, T=1, six specified
market weights selected only in selection, followed by one frozen champion
before untouched holdout. B/C remain exploratory. Prior 24/60-day examples do
not become adopted durations. All eight decisions remain OPEN/null; source/PIT,
missingness/cancellation, dependence/inference, sample adequacy, and post-pass
scope are not silently resolved. A static synthetic overlap checker is distinct
from an actual-data registry, data-access permission, or an evaluation engine.

The source record distinguishes received decision content from authenticity.
Unknown original bytes/SHA, Andy's receipt, forwarding receipt, independent
matching, and formal Claude originals remain null/PENDING/AWAITING. A generated
document hash is not substituted for any original or approval receipt. F2 is
unadopted; preserved Model1.0, BOX Ver.1, formal A/B, Freeze and G1-G6 are not
redefined. Unknown G1-G6 definitions are not invented.

This review covers the core documents named above. Any later third-party idea
appendix is a separate proposal and is not independently evaluated here; it
cannot alter M0 or supply operational permission through this review. Static
consistency, source authenticity, formal independent review, actual-data
validation, individual operation GO, application, readback and CLOSE remain
separate judgments. No superiority, statistical power guarantee, or execution
approval has been established.

## Supplement: bounded third-party proposal review

This supplement extends the earlier core-only scope to
`THIRD_PARTY_REVIEW_DISPOSITION.md`, `SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json`, and
the owner's `audit_review_proposal` checks. The expanded static suite was
actually executed: **18 methods PASS**, Python 3.12.14, `Ran 18 tests in
0.049s / OK`, using the same package-root command above. No old engine tests,
actual logs, host checks, exports, uploads, or source connections were run.

The two proposal documents preserve the decided primary M0 analysis. Tail
summaries are secondary private diagnostic ideas only; no outlier deletion,
winsorization, loss cap, weighting change, or favorable holdout filter is adopted.
Their levels, bins, disclosure rules, and operating thresholds remain OPEN/null.

Clock text correctly separates wall time, within-origin monotonic elapsed time,
and independent UTC/synchronization evidence. A counter does not authenticate
UTC, replace deadline evidence, compare unrelated reboot origins, or authorize
backdating. No buffer, tolerance, host probe, or monotonic implementation is
adopted. The documents do not convert the suggested ABORT wording into a new
runtime enum or BET/SKIP rule: the existing Shadow's incomplete-market HOLD is
preserved. Read-only source inspection confirmed the referenced
`SOURCE_COMPLETE_MARKET_REQUIRED` branch, parent odds test name, and separate
private candidate market gate; those old runtime tests were not re-executed.

The diagnostic allowlist is a proposed schema, not an implemented exporter or
raw-log masking tool. It excludes arbitrary exceptions, paths, URLs, credentials,
raw race identifiers, predictions, and scores. Code-commit pattern checking is
syntax only. Counts/code versions may still be linkable, manual HQ14 disclosure
review remains required, and complete anonymity is explicitly not guaranteed.
All implementation/export/share/host/start/production permissions are false.

The static proposal auditor checks nonadoption, permission flags, null proposed
parameters, and selected schema/sharing boundaries. Its successful status is
`PROPOSAL_REMAINS_UNADOPTED`. The three added tests reject adoption/export/buffer
mutations and unsafe schema/anonymity claims. They do not test an actual
diagnostic payload validator, privacy guarantee, anonymizer, or export pipeline.
The parent-byte tests again pass for all 245 files. No unresolved blocking
semantic contradiction was found within this limited proposal scope, and no
new statistical or operational authority follows from this supplement.
