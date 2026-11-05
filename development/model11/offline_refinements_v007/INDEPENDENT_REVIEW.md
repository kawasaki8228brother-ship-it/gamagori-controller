# Independent offline refinements review — v007

Scope: read-only review of the four new modules below, local execution of their scoped tests, and additional invented-vector assertions. No source code was changed by this reviewer. No real race data, actual source, service, production store, or approval bundle was used.

Observed outcome: **41 scoped test methods PASS** on Python 3.12.14 / Linux 6.18.57 x86_64 / glibc 2.41. The final scoped run reported `Ran 41 tests in 0.815s / OK`. This is an offline software observation, not Claude review, performance superiority, adopted thresholds, or permission to apply.

| Reviewed new file | Bytes | SHA-256 |
|---|---:|---|
| `model11/offline_refinements/cli.py` | 2875 | `a4b0db948985858d309655ee870c65e887857fc209a1d74b3217365e15b261db` |
| `model11/offline_refinements/point_in_time.py` | 10833 | `a108d81f06e1f007add34d23939e5a8587c02afaae2a244567f9b121fa2c8e84` |
| `model11/offline_refinements/pilot.py` | 11487 | `6e12548e49de30daa019a3350ba43d7ceca98091cb012ffcc12bdfe70a7036cd` |
| `model11/offline_refinements/schedule.py` | 14966 | `926cbf757e6646576a0e78a20a947b0e1e20beda641a9a325025f1e4fffe7a0e` |

## Executed checks

```text
python -B -m unittest discover -s tests -p 'test_offline_refinements_*.py' -v
```

| Area | Executed observations |
|---|---|
| CLI — 6 methods | Default/status remain DISABLED; supplying paths without the offline flag performs no input reads. Unknown commands/options and read failures return fixed diagnostics without submitted arguments, paths, or exceptions. The offline flag never makes application status GO. |
| Point in time — 12 methods | Thirty declared feature observations and 120 pre-deadline odds are checked. Future acquisition/availability/revision, latest-table substitution, later archive preservation, missing versions, label fields, missing features, invalid values, and invalid time domains are held. Missing/final/post-race odds cannot supply a market baseline or expected value. |
| Pilot — 10 methods | Within-day mean differences receive equal day weight. Sample SD uses K−1. MISSING, READ_FAILED, and NO_OBSERVATION remain distinct. Unconfirmed/missing planned rosters leave planned-denominator rates null. Duplicate/conflicting identities, mismatched baseline/model versions, nonfinite losses, and contradictory missing reasons are held. Raw identities, dates, baseline IDs, and individual losses are absent from shared summaries. |
| Schedule — 13 methods | Dynamic expected counts follow bound manifest rows. Missing predictions do not imply cancellation. Exclusions require byte/hash-bound race-event status evidence; an empty day requires bound day-closure evidence or every race exclusion proof. Boat withdrawal is not silently accepted as race withdrawal. Existing predictions remain unmodified/unassessed for excluded races. |

The reviewer also executed independent assertions beyond the unittest methods:

- Parent byte preservation: all **245/245** files from parent `7aec4fdb6b9f311ee01bf3a2752410e683d83e42` match their recorded byte counts and SHA-256 values; zero mismatches. This was a local byte comparison, not a new remote readback.
- Pilot known vector: day means 1, 2, and 4, with unequal race counts 1, 2, and 3, yield `sd_day = 1.5275252316519468 = sqrt(7/3)`. A nine-race declared roster with one MISSING, one READ_FAILED, and one NO_OBSERVATION yields each rate 1/9 and total unpaired 3/9. Submitted synthetic private-marker IDs do not appear in the summary.
- PIT: a later statistical revision is held despite an older effective date. Missing, FINAL, and POST_RACE odds each leave feature eligibility separate while market-baseline and EV eligibility are false. A training label unavailable at fit is held.
- PIT preservation ordering: revision 12:58:59 cannot belong to the claimed immutable version preserved at 12:58:30, even when both precede as-of 12:59; the new source-time-after-preservation gate holds it.
- Schedule: an after-deadline cancellation records AFTER_DEADLINE and UNASSESSED_OFFICIAL_EXCLUSION, with first-LOCK/AC1 assessment explicitly NOT_PERFORMED_CURRENT_MANIFEST_ONLY. Input bytes/objects are unchanged. Removing a prediction yields missing-observation HOLD with zero inferred cancellations; removing cancellation proof yields HOLD.

## Observed finding and closure

An empty pilot input initially reported `baseline_binding=MATCHED_SELF_REPORTED_FIXED_ID_AND_VERSION` despite zero observations. The overall result was already UNVERIFIED, but that binding label overstated what had been compared. The owner changed only the empty-observation label to `UNVERIFIED_NO_OBSERVATIONS`; the reviewer independently re-executed that exact case and the final 41-test scope. Statistics were not altered.

The PIT owner also strengthened immutable snapshot chronology: component acquisition, availability, and revision must be at or before both as-of and snapshot preservation. The reviewer executed the internal-preservation inconsistency case after that change and observed HOLD.

No unresolved blocking finding remained in the examined offline scope after these checks. This does not substitute for the separate complete regression matrix, external audit, or actual data-source verification.

## Interpretation boundaries retained

- Schedule completeness is relative to supplied, declared-reviewed, locally bound manifest evidence. Official source and cancellation authenticity remain UNVERIFIED. A current cancellation exclusion is not proof that an earlier first-LOCK obligation never existed; it does not retroactively waive LOCK validity or AC1. The original obligation is UNVERIFIED when its historical snapshot is absent.
- A PIT software PASS is limited to the supplied synthetic feature/market metadata. Optional missing training context remains UNVERIFIED_NOT_SUPPLIED. Local source IDs, hashes, versions, and timestamp assertions do not authenticate historical snapshots, actual source mappings, or all historical training inputs. Real input and application remain HOLD.
- Pilot baseline/model bindings match caller-declared identifiers and versions; they do not independently prove a pre-deadline market baseline. The equal-day SD is a descriptive sample statistic, not proof of day independence, adequate sample size, power, or future variance. A zero observed SD is not zero future uncertainty.
- No F2/F5 threshold was adopted, no M0/M2/M1 definition was inferred, and no model, LOCK, prediction, writer, schedule, task, or production behavior was changed by this review. The result contains no recommendation to relax a gate or execute a live operation.
