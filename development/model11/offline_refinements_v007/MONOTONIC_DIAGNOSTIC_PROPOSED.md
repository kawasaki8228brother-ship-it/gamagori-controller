# Optional monotonic diagnostic: DESIGN ONLY

Parent: `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`. This small v007 note adds no implementation, host probe, connection, clock setting, service, schedule or startup action. All parent files and existing deadline/LOCK rules remain unchanged. Actual host verification and execution GO are OPEN.

Three different facts must remain separate:

| Observation | Possible evidence | Does not establish |
| --- | --- | --- |
| Aware wall timestamp | Claimed UTC/offset at an event; existing source/generation/save/readback comparisons | Correct UTC, synchronization or source authenticity |
| Monotonic counter within one clock origin | Elapsed intervals and process pauses without treating civil-clock steps as elapsed time | UTC, a source's availability time, or comparability across reboot |
| External synchronization evidence | Independently reviewed source/status, measured offset, uncertainty and freshness | Truth merely because a field or local self-hash exists |

PROPOSED optional records could bracket a monotonic reading with wall-before/wall-after timestamps and record phase, selected counter type, boot-context evidence and process/start-tick evidence. Pair readings at input admission, generation, save and readback without rewriting the original forecast. Bracketing exposes sampling delay; it does not make the two clocks atomic. Record raw observations separately from any derived elapsed/difference values. The exact schema/API and privacy rules require review; nothing is adopted here.

A backwards wall step with increasing monotonic readings would be an inconsistency diagnostic, not permission to retime a forecast. A long pause can increase both elapsed measures without proving clock error. Filesystem delays, descheduling, suspend and wake behavior must not be conflated: the chosen counter's target-OS suspend semantics require explicit review. A negative/unavailable counter delta is unknown, not zero elapsed time. No tolerance, maximum pause, offset, freshness or divergence threshold is selected by this note.

Reboot changes the clock origin; PID reuse or a new process requires its own context. Do not subtract counter values across incompatible origins, infer continuity from a numerically increasing value, or backfill a missing timestamp. The existing Linux PID/start-ticks/boot-ID liveness checks are distinct from UTC accuracy. Counter samples cannot authenticate the human operator or approval origin.

The existing v005 path records wall-clock ordering; a paired monotonic forecast chain is not implemented by this document. Even a future diagnostic must not replace wall-deadline evidence, widen a cutoff, add a grace period, change LOCK validity, or treat a source snapshot time as actual completion. Unknown clock validity remains an independent review/HOLD issue under the existing approved rules; this note creates no new automatic gate.

Future offline fixture ideas: backwards wall step, equal readings, a long pause, reboot/new-origin mismatch, PID reuse, unavailable sample and suspend ambiguity. These are proposed cases, **not tests executed or PASS claims**. Actual target clock/sync evidence, diagnostic implementation and adoption need separate HQ14/Claude review and Andy's individual authorization. No Production, Render, task, source endpoint or time service is accessed.
