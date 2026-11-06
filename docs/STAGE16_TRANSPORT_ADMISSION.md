# Stage16: reject test transports without erasing honest replay evidence

Base: 32647655c9329d93641d761e50847a6718fc9274, draft PR #2.
Scope: new read-only transport-record gate, preflight helper and tests. Existing
collector, ledger, readiness, models, tasks and all prior tests are unchanged.
No network trial, retry, production connection, migration, merge or deploy.

## Distinct capture status and admission check

Stage15 COMPLETE describes its capture/storage outcome. An honest MockTransport
replay can remain COMPLETE while the new transport-record gate returns FAIL.
No original flag, receipt, manifest or execution event is edited or relabelled.

inspect_archive_transport accepts only a review-ledger path and work key, not
an externally supplied count or manifest. It uses one read-only transaction,
checks the bound decision/event/manifest, and follows actual receipt references.
Every START and END must have a literal boolean transport_injected declaration.
Any True is FAIL, including an injected START without an END. Missing flags
remain UNVERIFIED; 0/1/strings/null are not coerced into False. START/END conflicts
and mismatches between original records and the stored injected_ends count fail.
Incomplete captures or missing receipts cannot pass merely because the injected
count is zero. FAIL takes precedence while unknown reasons remain visible.

The report preserves event/decision/manifest and per-receipt object, payload
and body hashes, alongside recorded and recomputed counts. The report has its
own canonical binding hash. This does not replace or flatten the original graph.

## Narrow meaning of PASS

PASS means only that the complete capture records DECLARE no injected transport
and meet the existing graph checks. An actor controlling the stored metadata
can lie and recompute all hashes. This is not authenticated network provenance,
a production-store marker, official-source truth, freshness or a security sandbox.
The 12 result inputs' acquisition provenance is explicitly outside this gate.
network_execution_proven, decision_basis_transport_checked, production_authorized
and runtime_integration remain False even for the gate's positive test cases.

require_noninjected_transport is a prospective pre-request helper. It requires
an explicit boolean network permission and refuses every non-None transport,
including falsey objects. It performs no GET and is NOT yet wired into a worker.
Real prevention also needs a reviewed, enforced entry and trusted producer;
adding these functions alone does not close existing runtime bypass paths.

## Verification

The supplied Stage15 work snapshot's 51 files were hashed before development.
All709 baseline tests passed. Fifty-one new tests passed, including actual
MockTransport replay rejection, authored False-declaration cases, partial/error
captures, zero-count forgery, malformed/missing flags, graph corruption, read-only
behavior and preflight validation. The full local run passed760/0fail/0skip.
One earlier full-run tool invocation timed out at45 seconds without reporting a
test failure. Its partial log is retained; the unchanged suite was rerun to
completion using a process whose exit status and XML were collected. No test
was removed, skipped or weakened. CI must be checked by its exact commit/XML.

The prior Stage15 resume archive's existing ledger was opened read-only. A
separate direct-SQL verifier checked65 canonical objects,36 bodies and48 receipts.
The original remains COMPLETE, with injected START24 and END24. The new gate
returns FAIL with48 linked receipt references, and the ledger bytes are unchanged.
No new live acquisition or genuine withdrawal-positive fixture is claimed.
All positive transport-gate examples are authored test declarations, NOT real
non-injected captures. Existing CI five-page recapture is a separate old tool.

## Remaining integration work

Production/trusted worker entry, result-basis provenance, all non-test flags,
interrupted-owner recovery and explicit retry policy, scheduling and storage/
retention remain open. No fixed frequency or retention, live-readiness relaxation,
withdrawal semantics, A/B access change, PR#1 integration or Final Layer F here.
