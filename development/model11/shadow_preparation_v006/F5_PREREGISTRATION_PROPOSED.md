# F5 最終審査用の選択・評価計画候補 v006

状態: **PROPOSED / 未採用 / 実データ未検証 / GOなし**。
選択日数、候補数、有意水準、効果量、holdout日数を正式採用する資料ではない。
決定者はHQ14・Claude・アンディ。F2買い目/BOXリスク条件も変更・採用しない。
既存のモデル、grid、v003 workflowを含む親成果物を変更しない。
新規pure算術helperと合成単体試験だけを追加する。データ取得・学習・hyperfitはない。

## 1. 現行gridの実測したコード上の事実

`model11/revision_v003/walkforward.py` の `_config` と
`revision_v003/pooling.py` のdefaultを読取り、単体試験でも照合した。

- モデル: hierarchical/contextualの2件。
- alpha: 0.0/0.5の2件。
- temperature: 0.8/1.0/1.2の3件。
- 市場重みw: 0/0.25/0.5/0.75/0.9/1.0の6件。
- nominal gridは **2×2×3×6=72**。
- w=1の12件はexact市場分布で同一class。ここだけをまとめた構造上限は
  **72−12+1=61**。他の同値があれば実際の異なる分布数はさらに少ない。
- 市場自身のclassを除いた比較候補の構造上限は60。

これは72または61個の独立仮説という意味ではない。計算gridの数、異なる予測の数、
探索自由度、確認仮説familyの数を区別する。実際のdefault selectionは4日であり、
適切な必要Nと認定された日数ではない。このv006はそれを変更しない。

## 2. 審査に回す数値候補

以下の日数は**根拠付きの比較候補・計画目安**であり、必要Nの推定結果ではない。
開催日clusterを増やし、探索自由度とのバランスを明示して審査するための案。
alpha=0.5等も固定候補案であって、精度が良いと確認した値ではない。

| 案 | selection目標開催日数 | モデル×alpha×温度×w | nominal / 構造上限 | holdout目標日数の仮置き |
|---|---:|---|---:|---:|
| A: 固定校正・一方式 | 24 | hierarchical ×0.5 ×1.0 ×現行6w | 6 / 6 | 60 |
| B: 固定校正・二方式 | 36 | 2方式 ×0.5 ×1.0 ×現行6w | 12 / 11 | 90 |
| C: 現行full grid | 60 | 現行2×2×3×6 | 72 / 61 | 120 |

Aは最も少ない探索から始める比較案。Bは条件付きモデル構造の比較を残し、
alpha/温度探索を減らす。Cは現行候補を保持するが、selectionを長くしても
過学習しない保証にはならない。全案でw=1市場baselineを残す。
この表から既定案を自動選択する機能はない。各案の目標日数を満たしただけで
selection adequate、formal PASS、PRIVATE起動可と判定しない。

holdoutの60/90/120日も正式必要日数ではない。pilot分散・日間依存・期待効果から
算定した計画がこれを上回るなら、目標値が足りないことを明示する。
実際に確保できる将来開催日数・レース脱落率も未確認。
11/21–24の4日間は最短のSHADOW候補枠のみで、上記の正式評価期間ではない。

`proposed_options()` はこの3案を返すが、全件`adopted=false`、
`formal_selection_minimum=UNVERIFIED_NOT_SET`。実行設定を返却・更新しない。

## 3. primary、market comparator、評価単位

主案はselection終了時にchampionを一つ固定し、**未使用の将来holdout**で
P_shrunkと同時点P_marketのjoint120 log-lossをpaired比較する。
各レース `d_r=log(P_shrunk[actual])-log(P_market[actual])`、正ならcandidate有利。
開催日内平均d_jを求め、開催日を等重みにしたDelta_dayを一次推定対象とする案。
既存workflowのレース等重みselection log-lossと混同しない。

alpha/温度/w、入力変換、course policy、モデル、5点/BOX、BET/SKIPをselectionで
固定し、holdout結果を見て変更しない。市場のみが選ばれればmodel weight=0の
MARKET_ONLYであり、学習モデルの優位性とは扱わない。
市場欠損レースで市場値をモデルへ代用しない。事前定義したpaired coverage、
欠損分母、欠場/取消/返還の扱いを記録する。ゼロ実現確率はlog-loss無限大であり、
結果を見てepsilonを追加しない。

副次案は条件付き1/2/3着loss、Brier、calibration、course/人気帯別、
5点と各BOXの独立した的中率・回収率・ROI・max drawdown・BET/SKIP。
500円と各600円、返還、重複買い目を混算しない。利益を一次評価へ後付けで替えない。
旧Model 1.0/正式BOX Ver.1比較は検証済み固定出力・原本が未提供ならOPEN。

## 4. training / selection / untouched holdoutと多重比較

Training < selection < sealed future holdoutを全開催日単位で分離する。
学習labelの利用可能時刻をselection開始前、selection labelをholdout開始前とする。
特徴量・モーターidentity・course・oddsの取得/利用可能/改訂が締切前であることも
別ゲートで確認する。結果・払戻・A/B予想を特徴量へ入れない。
現行expanding walk-forwardは探索診断であり、以前のtestを後続trainingへ使う。
それを単一の未使用最終holdoutと呼ばない。

推奨する**審査候補**はSINGLE_FROZEN_CHAMPION対市場の一仮説family(m=1)。
selectionで多数を試しても、holdoutを本当に一度だけ使う一候補選択として扱う。
holdout後の再選択や、負けた候補を消して都合の良い候補だけ報告することは禁止。

複数の確認候補を評価する場合は、全仮説ID・familyとHolm等の処理を事前固定する。
単にgridが61classだからm=61を自動採用しない。全非市場classの改善を主張するなら
現行構造上の比較上限は60だが、実際の対象仮説と重複を審査して決める。
61を使う計算例は市場baselineも含めた保守的な仮budgetの例であり、正式familyではない。

`multiplicity_plan()` は算術だけを計算する。一方向family alpha=0.025という
**PROPOSED**値を仮定した例:

| 仮m | Bonferroni各比較alpha / Holm最初 | Holm最後 |
|---:|---:|---:|
| 1 | 0.025 | 0.025 |
| 10 | 0.0025 | 0.025 |
| 60 | 0.0004166666666666667 | 0.025 |
| 61 | 0.0004098360655737705 | 0.025 |

各比較へ0.025を無補正で使うm=61のunion boundはmin(1,61×0.025)=1。
これは実際の誤陽性確率が1だという主張ではない。Bonferroni配分のunion boundは0.025。
union bound/Holmは独立性を必要としないが、**個別検定のp値が有効**である必要がある。
このhelperはp値算出・検定・Holmの合否判定を行わない。

## 5. 必要日数の不確実性とprivate pilot

実pilot分散は未取得。Codexは実データや実結果を取得しない。
HQ14の非公開環境で、事前に定めた過去pilot日からpaired d_jのsd_dayを算定し、
期間、日数、欠損、同一節内依存、算定法、元資料SHA/receiptを独立審査する。
極少数日のsdが0でも将来の分散0とは扱わない。

`illustrative_sample_days()` は実計算するが、状態は
`ASSUMPTIONS_NOT_VALIDATED`、`power_guarantee=false`。

`n=ceil(((z(1-alpha/m)+z(power))*sd_day/effect)^2 * design_effect)`

単位は**paired開催日cluster**。レース数ではない。normal approximationと独立日
clusterの仮定に依存する。design_effectはcallerが仮置きする分散倍率(>=1)であり、
日間相関をデータから推定した補正でも、妥当性が証明された係数でもない。
同一節/連続日の依存があれば、節block・有効cluster数・検定/CI法を再審査する。

仮のeffect=0.02 nats、power=0.8、alpha=0.025、m=1、design_effect=1の算術例:

| 仮sd_day | 近似日数 |
|---:|---:|
| 0.05 | 50 |
| 0.10 | 197 |
| 0.20 | 785 |

sd=0.10、m=10では333日、m=60では438日、m=61では439日。
sd=0.10、m=1、仮design_effect=2では未丸め値を2倍して393日。
先に197へ切り上げて倍にする計算ではない。
どれも採用値ではなく、4日間や数節を十分な検出力と称せない理由を示す例。
効果量0.02は仮の対立仮説で、達成済み改善・採用marginではない。

sd_day不明/0ならUNVERIFIEDとし、日数を返さない。不正入力・数値限界はSTOP。
計画日数が算式を上回っても`adequacy=UNVERIFIED`を維持する。
有効性/非劣性margin、ROI損失上限、drawdown安全限界は外部の決定待ち。
このv006がそれらを決めたり、既存F2を置き換えたりしない。

## 6. seal、停止、変更、承認欄

実施前に次を固定する: code commit、candidate/model/normalizer/source mapping/course
policy/prediction config、training/selection日時、holdout予定ID/開催日台帳、
family、primary/secondary、適格/除外/欠測規則、サンプル数と最大期間、停止・再開規則。
全原本bytes/SHA、保存receipt、独立readback、承認原本を区別する。
第三研究予測は締切前に原本を保存し、結果更新は別版として予測を変更しない。

利益/的中を見ながらの早期PASS、任意の標本追加、grid変更、後付け除外は禁止。
時点違反、原本/receipt不足、hash不一致、曖昧な保存、仕様変化、学習/holdout混入、
分母不明、統計仮定不明ならHOLD。結果を遡って予測し直して欠損を埋めない。
11/9–14の正式A/BとFreezeを維持し、その結果に応じて計画条件を変えない。
延長や変更が必要なら新版を独立再審査し、別の未使用将来期間を確保する。

| 未確定項目 | 状態 |
|---|---|
| A/B/Cまたは別案・selection必要N | PROPOSED / 未採用 |
| private pilot分散・日間/節間依存 | UNVERIFIED |
| 効果量・alpha/power・family・検定/CI | PROPOSED / 未採用 |
| 実際の必要開催日数・未使用holdout期間 | OPEN |
| 非劣性・ROI・drawdown等の安全条件 | OPEN / F2変更なし |
| 原本/receipt/readback・旧版比較・第三研究独立性 | 要実物審査 |
| HQ14 / Claude / アンディ決定の原本SHA・日時 | 未提供 |
| PRIVATE起動・本番・正式昇格 | 未承認 |

再現: `python -B -m unittest discover -s tests -p test_shadow_preparation_evaluation.py -v`
8件のPASSは算術・非採用状態・不正入力処理・既存grid不変の確認だけ。
実データ有効性、審査PASS、必要N確定、本番GOではない。
