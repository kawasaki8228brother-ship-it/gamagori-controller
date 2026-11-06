# Stage10: preserve withdrawal text before deciding official status

Base: f5af34f5c07383f6ae9b38648a8440ef5c1000d2, draft PR #2.
Scope: an optional pure scanner, tests and this document. No legacy source,
readiness, expected participant set, model, persistence, task, main or deploy
change. The legacy blank('欠場') behavior intentionally remains unchanged.

## What was implemented first

`scan_withdrawal_text(body: bytes)` scans ONLY the current exhibition-time and
start-ST fields in the previously supported six-row beforeinfo layout. It
returns WITHDRAWAL_TEXT_OBSERVED with boat, section, field, original visible
text, normalized exact token, DOM locator and exact input-body SHA256. Hashes
bind observations to bytes; they do not prove source authenticity or currency.

The scanner distinguishes 欠場 from blank/dashes/F/L. It does not match a
substring or infer a synonym: 欠場なし, 前走欠場, 欠場予定, 出走取消 and 中止 do
not become withdrawal signals. Previous-performance columns, weather, notes
and unrelated tables are excluded. UTF-8 is explicit; decoding is not guessed.

Every section is validated completely before any signals from it are returned.
Malformed or ambiguous sections discard valid-looking prefixes. Other sections
survive. Rowspans do not duplicate signals, missing rows do not shift course
assignments, and a missing boat identity is not guessed. Coexisting withdrawal
text and numeric exhibition/start information is recorded, not resolved in
favor of either source field. SCANNED describes traversal, not an active set.
No signal means no supported signal observed, not proof of no withdrawal.

## Deliberate gap to OFFICIALLY_WITHDRAWN

The reviewed captures contain no real withdrawal example in these target
fields. Positive examples are authored fixtures or explicitly mutated copies
of the one stored beforeinfo page. This stage proves text preservation and
isolation only; it does not validate an actual official withdrawal layout,
body identity, participant effective time or acquisition provenance.
`official_status_verified` and `page_identity_verified` remain false and
`source_effective_at` is null. No official-withdrawal set is emitted.

The legacy observation and readiness interfaces remain unchanged. The scanner
is NOT connected to the acquisition path. Receiving an object is not saving it.
Unknown withdrawal layouts still require real-source evidence and review.

## Three-state proposal: accepted direction, unimplemented acceptance policy

LISTED_AS_OF_CAPTURE, corroboration by a separate prereace page and an explicit
withdrawal observation should carry different claims. This stage does not
rename the existing LISTED_STATUS_UNVERIFIED or add a corroboration readiness
gate. Before later implementation, maintain these distinctions:

- Two pages from one official publisher are different endpoints, not statistically
  independent evidence. Shared lag/cache errors and later changes remain possible.
- Matching six-boat fields is consistency at observed captures, not proof that
  every withdrawal must immediately produce a hole or marker. That guarantee
  was not established in the current evidence.
- `reserve_seconds` checks time remaining for work, not section freshness or
  closeness to the deadline by itself; it does not implement a closing-window
  membership test. These require separately bound clocks and conditions.
- B8's 21 seconds was a REVISION persistence margin; B12's 14 seconds was an OBS
  receipt margin. Neither is a calibrated participant-confidence value. Keep
  time margins as time measurements, not probability or confidence estimates.
- An accepted official withdrawal requires identity, field semantics, provenance
  and decision-time context. A token match alone cannot provide those checks.

## Verification

381 baseline tests pass unchanged. 78 scanner cases were added: local total
459 pass / 0 fail / 0 errors / 0 skip. Thirty baseline source blobs match the
Stage9 snapshot; none was edited. GitHub CI is to be checked separately by its
exact tested commit, XML and artifact before it is claimed successful.

The saved Stage9 CI ZIP and all five HTML body hashes were recomputed and
matched metadata. The one unmodified beforeinfo page produces no withdrawal
signal and grants no official status. Twelve deliberate mutations (two target
fields times six boats) preserve the expected marker/boat association, and
leave all official-status flags false. They are not real withdrawal evidence.

## Next unimplemented work

Real withdrawal snapshots and field/source semantics; body identity/freshness
binding; named corroboration state policy and its acceptance criteria; actual
observation persistence; enforced single entry; runtime integration/PR #1 and
full-day tests. Do not change old records or loosen gates to make replay pass.
