# P3 independent third-research runtime: design only

This v006 document designs a future dedicated local runtime. It does not select or provision a host, change a cloud service, install a package, start a process/schedule, enable a Shadow, or authorize actual data use. The fixed parent is `f3c3a3eb17073bd0a127bb943f4eda21e407cf2d`. All 196 copied parent files remain immutable; the v005 source, tests and settings are not edited. `RUNTIME_INPUTS.OPEN.json` is an OPEN evidence register, not an active launch configuration; `enabled=false` and `production_go=false` remain explicit.

The actual target host, Python/OpenSSL/SQLite builds, root/volume/filesystem, free space/quota, process owner, clock/synchronization evidence, retention/recovery plan and independent approvals are **null / OPEN**. Historical Render/Production measurements must not be reused as measurements of this separate research runtime. An environment with the same Python patch number can still have a different SQLite/OpenSSL/kernel/filesystem build.

## What the preserved local evidence actually measures

The following values are copied from the unchanged v005 evidence, not new actual-runtime measurements:

| Evidence scope | Python build | OpenSSL | SQLite reported by paired demo | Platform |
| --- | --- | --- | --- | --- |
| v005 synthetic suite/demo 3.12 | `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]` | `OpenSSL 3.5.8 25 Aug 2026` | `3.53.1` | `Linux-6.18.57-x86_64-with-glibc2.41` |
| v005 synthetic suite/demo 3.14 | `3.14.3 (main, Mar 24 2026, 22:50:36) [Clang 22.1.1 ]` | `OpenSSL 3.5.5 27 Jan 2026` | `3.50.4` | `Linux-6.18.57-x86_64-with-glibc2.41` |

Each preserved suite ran 459 tests with zero failures/errors/skips; each paired demo saved 12 invented 2099 forecasts and 12 invented results, with networking blocked in process. SQLite is printed in the **demo** log headers; it is not printed in the corresponding test-suite headers. Do not turn that into a claim that every individual test independently logged its SQLite version. The demo compared equal original input bytes, inner forecasts and inner daily-settlement reports across these local stacks. Outer envelopes, receipts, owner IDs, root/config hashes and exported wrapper bytes are run-specific and are not required to match.

| Preserved evidence, relative to the package root | Bytes measured in this copied workspace | SHA-256 |
| --- | ---: | --- |
| `shadow_launch_v005/results/TEST_RESULTS.json` | 5,417 | `04cdb4a78f8e04ec4e969bcf8b2cc67de438640bf93e8a44fca2f5f198c8ccb2` |
| `shadow_launch_v005/results/tests-python312.raw.log` | 72,110 | `4eb64f62a6a667fdcf2d7d530751c28345c2efa248a0ea58f247b704a8963c34` |
| `shadow_launch_v005/results/tests-python314.raw.log` | 72,109 | `7c61e826d3202401382a0e2731586af254de5c51d2cc60c7d0583c4c4f1883c4` |
| `shadow_launch_v005/results/demo-python312.raw.log` | 392 | `d479acf33ff00bcdd1cf53a21c72853f0800b3f817d459931c596ea52b681cab` |
| `shadow_launch_v005/results/demo-python314.raw.log` | 391 | `5e352adce592c3b6d344485bed6932c5d618cd940c8ac4edfbb9f54d29096557` |

These are software compatibility observations for those local synthetic stacks. They do not verify an actual runtime, wall-clock accuracy, source authenticity, power-loss durability, official parser, live TLS, model performance or actual launch GO. OpenSSL presence is not a successful official-site connection test. No actual endpoint/collector is used or proposed as implemented here: v005 only consumes approved local capture files/spools, and the actual official mapping/collector remains OPEN.

## Dedicated runtime boundary

PROPOSED: a separately approved Linux runtime and new private local root for `MODEL11_THIRD_RESEARCH`, with one explicitly started research worker and explicit local capture inputs. A specific distribution, CPU/RAM/storage SKU, Python build, installation mechanism, service manager, schedule, cloud resource or actual path is **not** chosen. The single-worker assumption is a planning simplification, not a Production setting change. Concurrent storage tests establish exclusion behavior; they do not authorize running multiple actual workers.

The runtime must not reuse the Production/A/B DB, disk directory, service account, writer credentials, canonical storage or task namespace. Actual access isolation, filesystem type/mount semantics, ownership/mode and quota/free-space readings require private review. The policy's lexical path checks do not establish these facts. The store's configured identity and generated OWNER storage ID are distinct; the runner pins their context plus approved code/config/artifact hashes. Moving/recreating the store cannot silently retain approval or bypass namespace/race uniqueness.

Keep the v005 owned layout and immutable artifacts: original capture bytes, forecast, receipt, completion marker, result versions, explicit selection frontier and separate daily/operations reports/receipts. The local SQLite ledger belongs only to this independent root. Existing `synchronous=FULL`, per-call connections, `BEGIN IMMEDIATE`, uniqueness and schema version checks are tested software behaviors, not claims of actual storage-device flush guarantees. No automatic SQLite migration, journal-mode change, VACUUM, repair or Production DB operation is authorized. A different SQLite build, OS or filesystem requires fresh compatibility/fault evidence before actual use.

## Capacity model: variables, assumptions and arithmetic

Capacity is a planning calculation, **PROPOSED / NOT APPROVED**, not a claim about an actual disk. Use measured maxima or independently justified upper bounds for variable-sized records; means and a single successful example do not establish bounds. No retention deletion or log rotation is implemented/authorized by choosing a planning horizon.

Let:

- `r` = planned retained forecast attempts per day, including any reserved/staged artifact allowance; `D` = planning horizon in days; `N=r*D`.
- `I,F,R,K` = bytes per retained input payload, forecast envelope, save receipt and completion marker.
- `V,O` = maximum retained result versions per race and bytes per result version.
- `A,S,RA` = daily settlement versions/day, bytes/report and bytes/report receipt.
- `B,U,RU` = operations audit versions/day, bytes/report and bytes/report receipt.
- `M` = fixed private model/normalizer/mapping/course/prediction-config/evaluation/comparison/approval artifact budget; actual model-file bytes are a separately measured component of M.
- `L` = retained private logs/receipts beyond those already counted; `Q` = explicit additional partial/orphan/failure evidence reserve. No cleanup is assumed.
- `P` = retained local spool bytes, including the duplicate original capture and base64/envelope overhead while that spool is retained.
- `J` = peak total SQLite ledger/index/metadata/journal/WAL/SHM allocation reserve, measured on the candidate filesystem or bounded by a reviewed workload. Do not count its same bytes twice.
- `T` = extra transient/concurrency/failure growth beyond the retained-window counts; `h` = additional fractional headroom.

For an initially empty dedicated root:

```text
payload_bytes = N*(I + F + R + K + V*O)
audit_bytes = D*(A*(S+RA) + B*(U+RU))
pre_headroom = payload_bytes + audit_bytes + M + L + Q + P + J + T
required_initial_free_bytes = ceil(pre_headroom*(1+h))
```

For a base64 spool holding `r*Dspool` captures of `I` bytes plus bounded envelope `E`, a proposed conservative estimate is

`P = r*Dspool*(4*ceil(I/3) + E)`.

There is no assumed compression or deduplication. File logical length differs from allocated blocks; directory/inode/quota limits, allocation granularity, SQLite free pages, transaction peaks, result corrections and report revisions must be included in the measured/bounded reserves. A caller supplying a SQLite overhead percentage without evidence must label it an assumption. Current free space and quota must both accommodate the reviewed forecast; a volume-level free-byte figure alone does not prove a private quota is sufficient.

Illustrative **unapproved** numbers: `r=12, D=90, I=65,536, F=131,072, R=2,048, K=2,048, V=3, O=4,096, A=2, S=65,536, RA=2,048, B=1, U=8,192, RU=2,048`; `M=8 MiB, L=16 MiB, Q=16 MiB, J=64 MiB, T=16 MiB`; `Dspool=3, E=4,096, h=0.30`. Here MiB means 1,048,576 bytes. The arithmetic is:

```text
N = 1,080
I+F+R+K+V*O = 212,992 bytes/race
payload_bytes = 230,031,360
A*(S+RA)+B*(U+RU) = 145,408 bytes/day
audit_bytes = 13,086,720
P = 3,293,280
pre_headroom = 372,240,480
required_initial_free_bytes = 483,912,624 (about 461.495 MiB)
```

These sizes/horizon/counts/headroom are **not** recommended actual limits and were not approved against real data. In particular `I=64 KiB` is only this example; the v005 adapter accepts payloads up to 4 MiB. Actual captures near that limit invalidate the example and require recomputation. An unchanged 4-MiB allowance cannot be sized from a 19-KiB example. A 90-day planning horizon does not authorize deleting evidence on day 91. If observed growth exceeds a bound, available quota/free space is unknown, or the projected remaining requirement no longer fits, HOLD/STOP only the independent Shadow before further writes; preserve records and ask for reviewed capacity/retention action. Do not alter existing LOCK rules or free space by deleting Production/old evidence.

During continued operation use a new **remaining-growth** forecast plus measured existing owned allocation and transaction peaks; do not subtract estimated old file sizes or assume unapproved deletion. Exact capacity/quota thresholds and response policy must be fixed before an actual start. CPU/RAM/inodes/write latency/fsync peaks also need measurements; none is established by this disk arithmetic.

### Available sample sizes and their limits

The copied synthetic exports were stat/read-hash measured without modifying them. On both preserved stacks, `example-input.raw.json` is 19,662 bytes; `example-forecast.raw.json` is 38,719 bytes; exported `example-receipt.json` is 897 bytes; exported `daily-settlement.json` is 45,921 bytes. Input hashes match across stacks, while run-specific forecast/receipt/daily wrapper hashes need not match. The 897-byte pretty-printed receipt export is **not** claimed to be the compact original store receipt size; the 45,921-byte daily export includes its outer response/receipt rather than only the stored report. None is a real-data maximum.

The root separately measured a fresh v006 owned store containing 12 invented 2099 forecasts/results. Its 64 regular files total **806,958 logical bytes** and **983,040 allocated bytes** (`st_blocks*512`). The source measurement JSON is 1,748 bytes, SHA-256 `8eb92de90441cf3be392a88c851b3f7999743b00002affc0a7ec63d4f0a8a262`; the publication INDEX assigns its evidence location. Group counts/logical/allocated sums were independently recomputed from that JSON here and match. The interpreter for this particular capacity measurement is not inferred from a different runtime log; root's per-run provenance controls.

| Measured store group | Files | Logical sum | Logical min/max per file | Allocated sum |
| --- | ---: | ---: | ---: | ---: |
| Input payloads | 12 | 236,028 | 19,625 / 19,703 | 245,760 |
| Forecast envelopes | 12 | 464,916 | 38,695 / 38,812 | 491,520 |
| Original compact receipts | 12 | 9,975 | 831 / 832 | 49,152 |
| Completion markers | 12 | 1,632 | 136 / 136 | 49,152 |
| Result versions | 12 | 2,842 | 236 / 237 | 49,152 |
| SQLite ledger at observation | 1 | 65,536 | 65,536 / 65,536 | 65,536 |
| OWNER marker | 1 | 131 | 131 / 131 | 4,096 |
| Stored daily report | 1 | 24,329 | 24,329 / 24,329 | 24,576 |
| Daily report receipt | 1 | 1,569 | 1,569 / 1,569 | 4,096 |

This sample excludes the external spool, process logs, model/artifact files and backups. It measures regular-file allocation at one observed point, not directory/inode/quota metadata, maximum concurrent SQLite journal/transaction size, physical durability or a real-data size bound. The final 65,536-byte ledger is not a measured peak SQLite reserve. The compact receipts and stored report clarify why the earlier pretty/export wrapper sizes cannot substitute for raw-store measurements. Actual serialized model-file size is still unprovided; it remains null in the register rather than inferred from an embedded model object or filled with zero.

Additional root local-runtime probes and model/artifact measurements can be added as separate evidence; they remain local software observations. Actual target free bytes, quota and capacity decision stay null/OPEN. No actual target-host probing, package install or store initialization is performed by these two design files.

## Clock evidence: three different facts

1. **Aware wall clock / UTC interpretation.** Existing v005 compares source prediction, generation, persist, ledger, completion and final readback wall observations against the original deadline, and checks ordering. Actual clock source, timezone, drift/steps and independent accuracy are not proven by an aware ISO string. Source acquired/available/revision claims require separate authenticity evidence.
2. **Monotonic elapsed time.** PROPOSED diagnostics should pair wall observations with monotonic-counter readings to detect within-process pauses/backward wall steps and latency. v005 does **not** record a monotonic clock chain, so this is a design gap, not an implemented guarantee. Monotonic values cannot establish civil UTC or be compared across reboot/restart without an appropriate origin; boot/process context must be recorded. No new monotonic gate is silently added to frozen v005 code.
3. **Synchronization/offset evidence.** An approved private operator must separately inspect synchronization source/status, observation time, estimated offset, uncertainty/error bounds and freshness. A kernel timestamp, successful local fake-clock test or nondecreasing wall sequence is not independent sync evidence. Actual source, offset limits, freshness limits, measurements and reviewer evidence remain null/OPEN; this document does not enable/change a time service or contact a time endpoint.

Clock-policy review must relate the uncertainty to real deadline evidence before a future start. An unknown or contradicted actual clock is HOLD; do not backdate, widen a deadline, infer a timestamp, relabel real data synthetic or treat a source snapshot time as actual completion time. Existing production LOCK/deadline semantics remain frozen. Suggested extra diagnostics or operational margins are separate review candidates, not new LOCK eligibility rules. Actual comparison cutoffs remain `prediction_at <= generation < deadline` and all required save/completion/readback observations before deadline; wall-clock/storage atomicity is not mathematically guaranteed by the code.

## Linux process identity, crash and restart

The immutable v005 storage implementation reads `/proc/<pid>/stat` field 22 (start ticks) and `/proc/sys/kernel/random/boot_id`, storing their identity alongside the owner PID/session. A PID number alone is not a process identity. Start ticks plus boot identity distinguish PID reuse/reboot and help determine whether a pending owner is still the same local process. These are local Linux liveness claims, not a human/operator authentication mechanism, nor proof of UTC synchronization. Do not expose actual host identifiers in public evidence.

On restart the store inspects RESERVED/STAGING/COMPLETION_PENDING and incomplete committed artifacts, preserves abandoned/uncertain state, marks HOLD_UNCERTAIN and writes durable STOP. Missing/unreadable process identity, unsupported OS/process namespace behavior, a fork reusing an inherited initialized instance, unexpected files/symlinks, wrong ownership, context mismatch or incomplete result/audit files must not be converted into a successful replay. A forked child constructs its own instance under the same unique namespace/race boundary. Parent local Linux fault tests do not certify another target container's `/proc`, shared storage, network filesystem, reboot behavior or physical power failure.

Normal close preserves pending uncertainty and closes the session; a closed instance is not a fresh launch. `STOP.json` is the first immutable incident record; STOP blocks forecast/result/audit writes. Reading retained evidence for investigation is separate from resume. There is no automatic STOP clear, reservation repair, old-race replay, schema migration, rollback or restore. Recovery of this Shadow alone needs a separately reviewed plan/backup integrity/readback and individual renewed GO, preserving original files and duplicate/uncertain history. Never repair or restore Production/A/B or change namespace/root to evade a reserved race.

## Private logs, receipts, approval origin and recovery review

Retain original input/forecast/result/report bytes, raw logs where authorized, hashes, size/allocated-byte observations, receipt/completion/ledger identity, source times and final-selection provenance separately. Report a failed read as unknown, not count zero; local committed-day scope is not official scheduled-race completeness. Public evidence may contain invented fixtures and fixed nonsecret summaries only. A redacted log has its own bytes/SHA/trust label, retaining the private original SHA as a separate reference. Never publish actual captures, private host paths/IDs, approvals, credential material or backup bytes.

The HQ14/Claude/Andy review artifacts and operator ACK must be independently checked in the approved private process, including authority, operation, exact identities, binding digest, validity/expiry, external origin and actual operator identity. v005 preflight checks supplied structure and self-reported attestations; it is not an authentication service. A valid fingerprint, a typed `EXTERNALLY_REVIEWED` flag, presence of this document, a populated JSON register or the dates 11/15-19 and 11/21-24 does not supply actual GO. Those dates remain review/start-window candidates only.

Before actual use, review actual host isolation, runtime/build match, `/proc` compatibility, clock/sync proof, workload/latency/capacity bounds, approved local source/mapping producer, private retention/incident monitoring, independent approval-origin verification and Shadow-only stop/recovery. Root's future local opt-in runtime validator/probe is another software measurement, not an automatic enablement mechanism. Any failed/unknown requirement is HOLD. Actual host, schedule, cloud settings, start, backup/restore, Production change and formal promotion remain unapproved.
