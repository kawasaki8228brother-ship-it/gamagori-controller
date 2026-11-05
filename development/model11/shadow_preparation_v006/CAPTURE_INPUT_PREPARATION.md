# P1 capture input preparation: known destinations, actual mapping OPEN

**OFFLINE PREPARATION ONLY / application HOLD.** This component adds a local
requirements inventory and a readiness auditor over the immutable v005
`SourceAdapter`. It does not implement a second converter, official parser,
transport, launch procedure, storage writer or production action. All 196 parent
files remain outside this component's write scope.

No actual official capture, actual race original, credential, secret, source URL,
live source, production store or approval original was obtained. Actual official
format, pointer, unit, source identity and independent review are **OPEN**. No
official page semantics, ST conversion, motor rate definition, exhibition field
or odds representation is invented to fill that gap.

## API and safe defaults

```python
required_mapping_inventory()  # new detached list of known local requirements
make_open_mapping_template()  # disabled OPEN preparation record; not runnable
audit_capture_preparation(mapping=None, capture=None, synthetic_validation=False)
```

Default audit returns HOLD without inspecting supplied objects, constructing an
adapter, decoding bytes or calling a converter. `synthetic_validation` must be
the actual boolean true, not 1 or a truthy string. Explicitly private-classified
captures remain HOLD before conversion or byte decoding, even if mapping/source
IDs or review metadata claim an official approval. Real-input authorization and
actual mapping review are not granted here.

The explicit synthetic path constructs the **existing** v005 adapter and calls
its `convert(capture)` exactly once. No field parsing, unit conversion,
timestamp repair or source mapping is duplicated. The old adapter's missing,
unit, source, future-time, evidence and history reason codes are preserved. An
unexpected exception becomes a fixed `CAPTURE_REVIEW_UNVERIFIED`, without
printing exception contents, URL, path or credential values.

Only an actually READY v005 result with explicit SYNTHETIC_ONLY/true,
year2099, six active boats and 120 observed odds earns:

```text
status = SYNTHETIC_CAPTURE_VALIDATION_CANDIDATE
software_check = PASS
converter_status = READY
application_status = HOLD
application_ready = false
official_mapping_status = OPEN
external_authenticity = UNVERIFIED
independent_review_status = UNVERIFIED
production_go = false
```

The software PASS is a synthetic execution result, not actual official mapping
review or application readiness. Unknown/missing/private input and unexecuted
checks stay HOLD/UNVERIFIED. Missing odds do not become zero or a successful
market-free launch. A reduced-field old RAW representation is not sufficient for
this six-active/120-odds preparation check; no existing scratch/LOCK rule changes.
No returned report includes raw captures, race originals, arbitrary source IDs,
private source URLs or original exception text. Successful summaries contain
only hashes, byte count and observed domain counts.

## Exact known local input inventory

`templates/field_mapping.OPEN.json` contains a disabled, non-runnable template.
Every `actual_official_pointer`, `actual_official_unit`,
`actual_official_format`, `actual_official_source` is null. The source mapping
candidate's actual paths, units, format, source identity and review originals
also remain null. It deliberately cannot pass SOURCE_MAPPING_V001 validation.
It is not a newly approved mapping or configuration to apply.

Known local destinations are fixed by the parent RAW_V001 and N1 contracts:

| Group | Required locally; actual official counterpart remains OPEN |
|---|---|
| Identity | RAW version/classification, opaque race_id, target_date, GAMAGORI, prediction_at; race provenance |
| Deadline | Explicit value/unit plus acquisition, availability, revision and evidence hash; strict prediction < deadline |
| Active field | Distinct explicit IDs plus independent field provenance; six active required for launch |
| Boat states | Boat ID, course, F/L, scratch value/unit; separate acquired/available/revision/evidence for each state |
| Motor identity | motor_id, version, effective_at, all three times and evidence; feature references must match identity/version |
| Five feature families | st, turn, motor, ability, exhibition: finite observed value, explicit frozen unit, all three times and evidence for every included boat |
| Motor statistics time | All motor feature timestamps at/after the referenced motor version's effective_at |
| Market | Gross-payout-multiple unit, snapshot times/evidence and all 120 distinct full-field ordered-ticket values |
| N1 course context | Frozen policy ID/hash; strict class/flag; frame and exhibition definition/source/time/evidence and per-boat positions |
| Materialized capture | Exact format/class/flag/source, original bytes/hash, acquired/available/revision |
| Capture history | Each version's payload hash, evidence hash, three timestamps; ordered history, final entry binds current bytes/times |
| Frozen feature specs | Explicit per-feature unit, direction and normalization declaration; no automatic unit assumptions |
| Private review metadata | HQ14/Claude review-original hashes; presence is self-reported metadata, not authentication |

The machine inventory lists every one of the **120 ticket destination keys**,
not a sample. Other `{boat_index}` and `{history_index}` entries are explicitly
local repetition patterns, not actual official JSON pointers. Per-boat entries
apply to all included boat records. The tests compare top-level RAW/course field
sets with the existing adapter's fixed contract and check the complete
permutation domain. None of those known local names demonstrates how an actual
official capture encodes the data.

## Timing, evidence and preservation

The v005 converter remains the only authority for structural source conversion:
strict aware timestamps; no naive/-00:00/invalid offset/excess precision;
acquisition <= availability/revision; field/state/source times <= snapshot;
materialized capture times at/after respective known component maxima; history
and final-version binding; fixed source/classification allowlists; motor
identity/version binding; complete timely market; selected course value and exact
course-state time binding. This preparation code delegates those checks rather
than recreating their implementation or loosening a gate.

The original captured bytes and history must ultimately be privately preserved
and independently checked by HQ14. A locally computed/self-reported SHA does not
establish source truth, pre-LOCK availability, a reviewer decision or identity.
An OFFICIAL-prefixed name is not authentication. Captures are never reclassified
from actual/private to synthetic by this module. The synthetic path's year2099
and flags constrain software fixtures; they do not detect a dishonest external
claim without independent originals.

## HQ14 private inputs still required

To close actual-source preparation later, HQ14/Claude must inspect privately:
the exact source format/version and original capture bytes; field/pointer
correspondence for race/deadline/boat/feature/motor/exhibition/course/full odds;
actual units and whether values are raw or derived; per-field acquisition,
availability and revision semantics/history; motor replacement/version evidence;
capture materialization and historical-version originals; official identity/date
checks; frozen mapping/spec versions and independent review originals.

Do not send actual private originals, credentials or source URLs to public
GitHub or this offline development. Missing inputs stay null/OPEN. This template
cannot substitute for them and does not authorize fetching them. No live
gateway, settings change, execution, promotion or approval flow is added here.

## Executed software verification

Tests use only the immutable parent synthetic dataset and capture fixture helper.
They cover default no inspection, one converter call, no file/socket/database I/O,
known/unknown units, absent mapping, missing fields/exhibition, future
feature/capture time, incomplete/stale market, missing/mismatched/future history,
private classification HOLD without decoding, exception/secret suppression,
complete inventory/120 domain and a null disabled non-runnable template.

```sh
python -B -m unittest discover -s tests -p test_shadow_preparation_capture.py -v
```

Actual executions and environment are reported in the delivery evidence. A test
not executed is UNVERIFIED; software success never upgrades the actual-source
OPEN gates or application HOLD.
