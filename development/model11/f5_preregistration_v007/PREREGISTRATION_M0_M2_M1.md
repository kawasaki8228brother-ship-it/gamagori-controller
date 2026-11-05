# F5 preregistration: M0 / M2 decided; future M1 design

Document-only. Parent: `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`.
Decision content follows the user's forward dated 2026-11-05T20:36+09:00.
HQ14/Claude originals and receipt SHA remain unverified; see
`SOURCE_RECEIPT_REFERENCE.json`. No engine, configuration, data, host, Shadow,
Production, A/B, Model1.0, BOXV1, LOCK or task is changed or authorized.

## M0: fixed primary comparison

The evaluation subject is **one selected and then frozen champion**, paired
against P_market derived from the **same pre-deadline odds snapshot**. Primary
loss is the joint three-order probability log-loss over all 120 outcomes:

`LL(p,y) = -log(p[y])`.

For a predeclared eligible paired race set R_d on operating day d:
`D_d = mean_R_d(LL_market - LL_champion)`.
The primary aggregate gives each eligible operating day equal weight:
`mean_d(D_d)`. Positive difference favors the champion. This is not a
race-weighted aggregate that lets a larger day dominate. Eligibility/denominator
rules, including missingness, must be fixed before the formal holdout is sealed.
Inference and dependence methods remain under review; no t-test, bootstrap or
sequential method is chosen here.
The separate, non-integrated offline-v007 pilot helper uses
`d=LL_champion-LL_market`: **D=-d**, so signs must be bridged explicitly.
Sign reversal leaves sd_day unchanged where defined; it does not estimate K=1
variance. No old helper or engine is changed.

The decided controls are one-sided alpha=0.025, target power=0.8 and **m=1**.
Here m counts one champion-vs-market comparison, not six weights. Power is a
target, not a small-pilot guarantee. SESOI,
variance, dependence and final sample planning remain unresolved below.

No discretionary interim stopping, outcome-driven extension, repeated peeking,
post-hoc champion substitution, retrospective exclusion or after-the-fact
threshold/weight choice is permitted. Safety/data-quality handling must follow
the presealed protocol; it cannot turn a failed/uncertain comparison into a win.
No unprovided G1–G6 definitions are invented here.

At w=1, the prediction is market-only. The same-snapshot paired distribution is
the market baseline, so it cannot establish MODEL superiority. A market-only
selection must be reported as such; it is not relabeled as a learned-model
victory or replaced after observing holdout outcomes.

## M2: operational pilot, never formal performance evidence

The first operating day of the third-research Shadow is the pilot. A candidate
date is 2026-11-21–24 or later; the actual start is undecided and this is **not
start GO**. Its goals are full120 capture rate, missingness/rationale, paired
daily loss difference, sd_day inputs, timing/source mapping, and prediction,
save/readback and result-handling operations. Pilot observations cannot support
formal superiority, profit, promotion or model replacement.

The first day yields at most one day-cluster statistic. With K=1, sample sd_day
using denominator K-1 is undefined. Record sd_day UNVERIFIED/null; do not invent
zero, use race-level variation as day variation, silently extend the pilot or
adopt a new minimum duration. Any additional pilot span needs separate review.
Pilot races/days must **never** be reused as formal holdout.

## M1: future A-family-only confirmatory design

The v006 A proposal's actual model family is `hierarchical` (verified against
the unchanged `proposed_options()` entry), with course-prior alpha=0.5 and T=1.0. Only
w in `[0,0.25,0.5,0.75,0.9,1.0]` is selected on the designated selection period;
then select one champion and freeze model, normalizer, source definition,
configuration, weight, data IDs/hashes and evaluation plan before holdout.
B/C remain exploratory and are not additional confirmatory tests.

The old illustrative 24 selection days / 60 holdout days are **not adopted**.
Neither a required duration nor formal adequacy is inferred from that example.
All candidate search is confined to development/selection; the final holdout
cannot select a weight, feature, champion, calibration or exclusion rule.
The existing engine/grid remains byte unchanged; this is future design only.

## Exactly eight unresolved decisions

| ID | OPEN item | Current value |
|---|---|---|
| OPEN1 | SESOI（意味のある最小改善量） | null |
| OPEN2 | 最低selection開催日数 | null |
| OPEN3 | holdout開始日・必要日数 | null |
| OPEN4 | α消費計画の要否 | null |
| OPEN5 | 欠場・返還・中止の取扱い | null |
| OPEN6 | オッズ欠損の扱い・最大許容欠損率 | null |
| OPEN7 | 日間・節間依存への統計対応 | null |
| OPEN8 | 合格後に許可する範囲。 | null |

Pilot statistics and these decisions must be reviewed/frozen after the pilot
and **before** the formal holdout seal/first holdout prediction. No automatic
post-pilot completion, pass-triggered permission, sample-size default or alpha
spending plan is supplied. F2 remains unadopted. 基盤優先・G1〜G6承認ゲートを維持;
their original definitions/references are UNKNOWN pending original checks.

## Point-in-time and remaining gates

Every historical training, selection and evaluation race needs its actual
immutable pre-prediction source version and acquisition/availability/revision
history. A later table update cannot be backdated by an old effective date.
Fit cutoffs alone do not verify all old snapshots. Result/payout information
never becomes a feature. Missing pre-deadline odds cannot be replaced with final
odds. Ownership of valid old pre-deadline odds remains UNVERIFIED. Selection and
paired comparison must use only the predeclared complete120 pre-deadline period;
missingness handling is OPEN6, not an implicit post-hoc success filter.

The partition registry is empty/OPEN and no actual dates/IDs/original hashes are
filled. Independent originals, statistical review, data/model readiness, host
readiness and individual operation GO are separate gates. This document grants
none of them; a future statistical success also grants no scope until OPEN8 and
the required explicit authorizations are resolved.
