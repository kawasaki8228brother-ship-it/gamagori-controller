# Additional independent runtime and CLI review

Scope: read-only review of the new v006 runtime observer, preparation CLI and
coverage interface. The reviewer did not edit those source files or any parent
artifact. This is a Codex software review, **not Claude review**, authentication
of approval/source evidence, real-host verification or application GO.

Only local invented fixtures and temporary directories were used. No actual
official capture, private race original, credential, network source, production
host/store, task or external writer was accessed.

## Independently executed checks

On Python 3.12.14 / Linux 6.18.57 x86_64:

```text
python -B -m unittest discover -s tests -p test_shadow_preparation_runtime.py -v
Ran 7 tests / OK

python -B -m unittest discover -s tests -p test_shadow_preparation_cli.py -v
Ran 8 tests / OK
```

The runtime checks verified default no directory/clock/process inspection,
strict opt-in, private/unknown scope HOLD, missing-directory noncreation,
file/symlink rejection, unchanged bytes in the caller-created temporary
directory, and no invented process identity when the local observation is
unavailable. The explicit observer reads metadata, free-space statistics,
local `/proc` process identity and local clocks. It does not write files, create
a host/store, open a database, contact a clock authority or register a task.

Runtime reports correctly retain external UTC accuracy UNVERIFIED,
synchronization evidence null, clock offset threshold NOT_ADOPTED, capacity
requirement UNADOPTED, application HOLD and launch_allowed=false. Local clock
ordering and available bytes are observations, not an adopted execution gate or
proof that the clock/capacity is adequate for a real shadow window.

The CLI checks verified default DISABLED with no supplied-file reads,
capture-without-explicit-synthetic-validation HOLD, null/OPEN actual mapping,
F5 proposal non-adoption, safe fixed diagnostics for bad input, and no startup or
write from the explicit temporary-directory runtime command. The private-capture
regression verifies HOLD before loading its mapping or decoding base64 payload.
Private and unknown classification do not become synthetic input by assertion
from the command name. Every emitted report retains application HOLD and
production_go=false.

## Concrete diagnostic finding and correction

The first CLI argument-parser review reproduced an unknown command containing a
private sentinel. `argparse` raised SystemExit outside the error handler, printed
the submitted value on stderr and did not emit a fixed JSON report. The root
owner added a preparation-specific parser error handler. The final eight-test
suite includes unknown command, unknown option/value and missing option-value
regressions, all passing without echoing submitted values. Explicit help remains
the normal help path. No legacy CLI was edited by this reviewer.

## Coverage-interface review finding

Read-only inspection found that the initial coverage implementation expected
`MODEL11_RESEARCH` for SIMULATION inner forecasts, while the immutable V003
predictor used by the v005 runner emits `MODEL11_RESEARCH_V003`. This would
incorrectly HOLD a genuine simulation forecast at its identity check. The finding
was sent to the coverage owner and root. The root owner corrected the exact
source expectation, then generated genuine invented v005-runner forecasts and
receipts for the coverage regression. No parent predictor source was changed.

The reviewer independently reran the pure audit on the root's Python3.12 fixture
files `coverage-final312/SYNTHETIC_ONLY.schedule.json` and
`coverage-final312/SYNTHETIC_ONLY.prediction-evidence.json`, pinning the supplied
ledger storage ID. Observed result:

```text
status = OBSERVATION_COMPLETE_LOCAL
scheduled_rows = 12
supplied_prediction_observations = 12
locally_verified_saved_predictions = 12
counts = {saved_predeadline_local: 12}
issues = []
schedule_approval = SELF_REPORTED_REQUIRED_METADATA_MATCHED
external_schedule_authenticity = UNVERIFIED
external_prediction_authenticity = UNVERIFIED
runtime_final_readback_time = UNVERIFIED_NOT_IN_STORED_RECEIPT
production_go = false
```

The audit ran with file-open, socket and SQLite-connection calls forbidden after
the fixture JSON had been read; no such calls occurred. Input hashes before and
after matched exactly. The schedule file was 2,292 bytes, SHA-256
`f09ad444ed10c74f01bcec56e6c7dd0ef421c7fd76004a80e359f99d7c4c1138`.
The prediction evidence file was 967,013 bytes, SHA-256
`f9039ed32e9e0990d018dcf174ff7e90d5fb24a1838687613fe7d8359caf03cb`.
This resolves the source-name finding for the observed complete stored-forecast
path. Root's additional scenarios/Python3.14 execution and the coverage owner's
focused suite are separate evidence; this reviewer does not claim to have run
those from the independent pure-audit result or runtime/CLI test counts.

The proposed coverage API is a pure audit of caller-supplied schedule and
read-only evidence. Its local hash/time agreement must remain distinct from
actual official schedule approval/authenticity and from source/predictor
semantics. No result here approves a new source, runtime, threshold, launch,
replay, repair or production operation.
