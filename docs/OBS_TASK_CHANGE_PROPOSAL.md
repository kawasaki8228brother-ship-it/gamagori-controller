# Future A operational OBS task proposal — no task edit

**PROPOSED / HOLD for actual task modification.** This document is a reviewable
change outline, not an edited Automation prompt, full replacement task text,
deployment, schema update, or execution GO. No actual Airtable/Events or
Automation was queried or changed. Prediction decision bytes, Model 1.0,
LOCK/deadline rules, retries, origin, schedule/enabled settings, save paths and
START/END behavior remain untouched.

## What can be retained without inventing a contract

HQ14's answer identifies A RUN_START and RUN_END as operational OBS and
confirms preservation of producer_run_id, separate idempotency formulas,
start/end time, stages, actual errors, and pre/post canonical-JSON SHA checks.
The future task proposal retains these requirements; it does not replace
producer identity, combine START with END, suppress actual errors, or copy a
column UUID into the payload automatically.

The related A main v3 / Model 1.0 FROZEN / execution_patch 2026-09-18.1 reference
has received label `SHA256` and verbatim value:

```
d462767f4448e28fc735df7363fb1a75137c5e7f
```

This is 40 hex characters. Algorithm and completeness remain UNVERIFIED. It
is not the independently matched OBS contract, and cannot serve as authority
to rewrite a missing full task body. Do not infer or relabel its algorithm.

## Proposed review delta

Subject to a later independent review of the actual baseline, consider adding
**read-only QA reporting** alongside the existing operational receipts:

1. Report separately whether normalized column and payload values were
   provided and whether `event_uuid`, source, producer ID, event kind, and idempotency
   values agree. Keep missing/null/empty values distinct. Do not derive a new
   producer ID or silently select a conflicting copy.
2. Verify the confirmed A START and END formula separately using the existing
   producer_run_id. Preserve both records. Keep repeated-key observations and
   conflicting raw payloads visible for independent review; do not delete,
   overwrite, retry, or choose one row automatically.
3. Preserve exact actual start/end, stage, and error information in its existing
   protected payload/receipt path. Public or user-visible QA should expose
   fixed diagnostics/counts rather than actual source URLs, credentials,
   producer IDs, or error values.
4. Keep source_evidence property absent, null, empty array, explicit missing,
   failed fetch, claimed normal, mixed, and unrecognized representation
   separate. Literal MISSING may be reported in the explicit-missing bucket
   without rewriting the original payload; unknown aliases are not guessed.
   Claimed normal is not authenticated source evidence. Do not
   replace missing with an empty list or turn RUN_START's empty list into a
   uniform failure policy.
5. Retain the **actual independently confirmed A canonicalization** and its
   before/after verification. The offline tool's sorted/compact/ASCII profile
   is a candidate comparison only; it must not silently replace the existing
   producer canonicalizer or its metadata.
6. Use observational labels (OBSERVED / CONTRACT_UNVERIFIED / INCONSISTENCY)
   in the additional QA. Do not let those labels change eligible LOCKs,
   forecast scoring, source filters, Model/BOX, receipts, execution origin,
   retry behavior, or scheduler settings.

This is an outline for future review, not a claim that any absent field is
already required or that the outline is compatible with an unseen full prompt.
No replacement full prompt is fabricated from the related reference alone.

## Four independent decisions that remain OPEN

| Question | Current decision | Safe proposal handling |
| --- | --- | --- |
| Payload UUID mandatory? | UNVERIFIED | Report absence, preserve current data; no formal FAIL or automatic UUID insertion. |
| Column UUID alone eligible? | UNVERIFIED | Observe column/payload presence; no eligibility promotion. |
| RUN_START empty source_evidence allowed? | UNVERIFIED | Preserve and label its exact state; no uniform empty-array FAIL. |
| Missing source_evidence property a formal violation? | UNVERIFIED | Report MISSING_FIELD distinctly; no backfilled field or retrospective invalidation. |

Each question needs independently matched contract evidence or an explicit
new policy approved as a **future change**, not retroactively presented as
existing behavior. RUN_START can precede external fetching; the absence of
fetch evidence is not fabricated into either a successful fetch or a breach.

## Required nonsecret inputs before an actual change candidate

HQ14/Claude must privately verify the current full A task/OBS contract version,
exact raw bytes and correct hash algorithm/value, actual column/payload field
mapping, canonicalization definition/implementation, START/END and source
evidence semantics, and receipt/readback requirements. Resolve the forty-hex
reference discrepancy without guessing. Also identify which fragment is
purely visible reporting and which fragment controls behavior.

Codex does not need actual Events, real run IDs, credentials, URLs, protected
payload contents or production access for this offline proposal. Nonsecret
contract definitions and independently verified digest/version metadata are
the appropriate review inputs. Actual-record checks, if required, belong in
HQ14's approved private environment; the twenty-row synthetic example is not
a substitute.

## Future acceptance and STOP gates

Before any actual prompt edit, reviewers should have a concrete original and
candidate full body, exact diff, protected-section byte/hash comparison,
rollback original, and explicit intended authority. At minimum, demonstrate
that the candidate leaves these unchanged: Model 1.0 / prediction decision
text, LOCK/deadline validity, audit calculations, existing save/receipt paths,
START/END production behavior, retries, origin, schedule, and enabled state.
Compare actual canonicalization through independently supplied vectors;
do not use the offline candidate profile as proof of current A behavior.

STOP/HOLD if the baseline cannot be independently matched, the hash label is
unresolved, any of the four required policy questions is silently decided,
protected bytes change, a new mandatory property is invented, a source claim
is promoted to verified authenticity, B or LOCK is processed under A's OBS
rule, or a proposed report changes writing/retry/execution behavior. A test
PASS on synthetic data is development evidence only.

No automatic patch, prompt upload, Events repair, production rollback, or
Automation action is part of this work. Claude independent review → HQ14
consistency review → Andy's individual GO remains a future sequence. Until
then this task-change proposal and actual-contract compatibility remain HOLD.
