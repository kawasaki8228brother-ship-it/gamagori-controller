# Model 1.1 検証事前登録案 v002

状態: **PROPOSED / UNVERIFIED / 本番GOなし**。これは審査用の具体案であり、
承認済み研究計画、独立監査PASS、実データ改善、正式昇格を意味しない。
Model 1.0、BOX Ver.1、11/9–14の正式A/B、LOCK・締切・保存処理は維持する。
既存47ファイルおよび既存記述統計の定義は変更しない。

## 1. 一次仮説・推定対象

比較するのは、選択期間終了時に一つに固定したchampionの **P_shrunk** と、
同じ締切前snapshotから得た **P_market**。120通りの三連単joint log-loss
（自然対数、単位nats）を使用する。結果yについて各レースの差を
`d_r = -log(P_market[y]) - (-log(P_shrunk[y]))` とする。正の差がcandidate有利。

開催日j内の適格・完全pairedレースで `d_j = mean_r(d_r)`、一次推定対象は
`Delta_day = mean_j(d_j)`。**各開催日を等重み**にする。
既存metricsの全レース等重みの記述統計とは異なる推定対象であり、
`preparation.planning.equal_day_logloss_estimand()` が双方を別欄で計算する。
日ごとのレース数が1件と3件で差が1と0なら、日等重みは0.5、レース等重みは0.25。

一次帰無仮説の候補は `Delta_day <= 0`。一方向alpha=0.025、power=0.80を
審査候補とする。計画上の検出差0.02 natsは**仮の対立仮説**であり、
達成済み改善幅でも採用閾値でもない。一次推定・検定方法、日間依存の扱い、
confidence intervalの方法は実施前にClaude/HQ14が確定する。
利益を一次仮説へ後付けで置き換えない。

一次対象は6艇120通りを持ち、事前時点適格性・正規化・結果対応を確認できる
同一レースのpaired観測。欠場・取消・オッズ欠損・停止・遅延取得の扱いと、
予定レース分母からの脱落理由を予測・結果を見る前に固定する。
都合の悪い結果による除外は禁止。除外率と曜日/開催日偏りも報告する。

## 2. 学習・選択・封印評価の分離

1. Training: 過去期間のみ。各特徴量の取得/利用可能/改訂、course・F/L・欠場、
   oddsの各時刻が予測時点以前であることを確認。学習結果の利用可能時刻も確認。
2. Selection: trainingより後、holdoutより前。候補方式、特徴量、alpha、
   市場統合w、温度、5点/BOX研究ルール、BET/SKIPをここで確定する。
3. Sealed future holdout: 未使用の将来開催日を全日単位で封印する。
   学習、探索、モデル選択、欠損処理/閾値調整に使わない。
4. 最終計画ではcandidate/model/pipeline/schema/input-adapterのcommitとSHA、
   全パラメータ、日付・race IDの予定台帳、family、除外規則、終了規則をsealする。
   actual/払戻を知る前に予測原本とreadback証拠を残す。

既存walk-forwardは実装回帰・探索用。過去test日の後続fold training利用は
明示済みのexpanding-window研究であり、未使用の最終holdoutと呼び替えない。
今回の一次案は一つに固定したchampionを評価期間中に再学習しない。
再学習が必要なら、手順ごと事前登録した別プロトコルとして再審査する。

**11/9–14の結果に応じて候補・特徴量・パラメータ・閾値・評価条件を変更しない。**
その結果を使った調整を行った場合、その期間を未使用評価と扱わず、新しい計画と
別の未使用将来データが必要。Codexへ当該実結果や私的pilot原本を渡さない。

## 3. 多重比較

推奨案は **SINGLE_FROZEN_CHAMPION**: selectionだけでchampionを一つに決め、
一次確認仮説は一件。holdoutを見てchampionを選び直さない。
他モデル・P_raw/P_model・BOX・subgroupは副次/探索と明記する。

複数のconfirmatory候補を実施したい場合は、候補数m、比較対象、仮説IDを
holdout前に固定した **HOLM_FIXED_FAMILY** とする。Holmのstep-down手順で
family-wise errorを管理する。都合よくfamilyを分割・追加・削除しない。
サンプル数計画では保守的なalpha/mのBonferroni境界を使用する。
この実装はHolm検定そのものや合格を自動実行しない。

## 4. 必要サンプル数の実装・仮数値

`paired_cluster_sample_size(sd_day, effect, power=.8, alpha=.025, comparisons=1)`
はstdlib `statistics.NormalDist.inv_cdf` で次の近似を実計算する。

`必要日数 = ceil(((z(1-alpha/m) + z(power)) * sd_day / effect)^2)`

単位は**paired開催日cluster**。レース数ではない。最小出力は2日。
未知または0のsd_dayはUNVERIFIEDとし、0日や架空の分散を返さない。
無効値・数値限界はSTOP。これは独立な日clusterと既知分散に近い条件での
normal approximationであり、小標本t補正・日間相関・欠測・節依存を保証しない。
同一節の複数日に依存が残る場合、節blockや保守的な追加日数の審査が必要。

| 仮のsd_day | 仮の検出差 | power | 一方向alpha | m | 近似必要日数 |
|---:|---:|---:|---:|---:|---:|
| 1.0 | 1.0 | 0.80 | 0.025 | 1 | 8 |
| 0.10 | 0.02 | 0.80 | 0.025 | 1 | 197 |

上表はknown-vectorと算式の説明だけ。実分散・正式効果量・必要Nの採用値ではない。
実際のsd_dayはHQ14の非公開pilotで、事前に選んだ過去日から算定し、
cluster数・算定法・時点適格性・相関診断・非秘匿receipt/SHAを第三者審査する。
Codexは実結果を取得しない。現時点で実分散、正式必要日数、必要レース数は
**UNVERIFIED / OPEN**。未知Nを「4〜5節で足りる」等に置き換えない。

**11/21–24の4日間は最速のSHADOW候補枠だけ**。日程・担当・実行承認は未確定。
4日間を正式な検出力、Model 1.0超え、利益改善の証拠としない。
Model 1.1の対外性能主張・本番適用・正式昇格は別審査と個別GOが必要。

## 5. 副次評価と金銭リスク

- first / second-conditional / third-conditional log-loss、joint Brier、calibration。
- 市場とのpaired差、コース/人気帯別、日別・節別の不確実性。
- 通常5点500円、Human-style研究BOX600円、Mechanical研究BOX600円、
  BOX v1.1研究600円を**別集計**。的中率、返還、払戻、仮収支、回収率、ROI、
  max drawdown、BET/SKIP、方式間重複を混ぜない。
- P_raw、P_model、P_market、P_shrunkは別段階。市場欠損時にmarket/shrunkを捏造せず、
  primary pairing欠損としてcoverageを報告する。
- 旧Model 1.0・正式Human BOX/Mechanical BOX Ver.1との比較は、検証済み原本または
  締切前固定出力がない限り **OPEN**。研究heuristicを正式Humanの再現と呼ばない。

一着率・回収率等で都合のよい指標だけ採用しない。ROIの分散・裾・返還/取消依存と
サンプル数は未知。log-loss改善から金銭利益や許容drawdownを推定しない。
副次指標の非劣性margin、ROI損失上限、drawdown許容値は**未採用 / 要審査**。
合格は一次仮説だけで自動成立せず、事前に確定した安全条件と独立審査を必要とする。

## 6. 停止・欠損・変更管理

ゼロの実現確率はlog-loss無限大。隠れたepsilonや再正規化による修復は禁止。
`equal_day_logloss_estimand` は無限/不明pairを数え、finite JSONのUNVERIFIEDとする。
有限観測subsetの記述値を、完全な一次推定値へ昇格しない。

未来情報、締切超過、source対応不明、予測保存欠落、hash不一致、重複、
120通り不正、仕様変更、予定分母不明、pilot/holdout混入、未承認条件変更ではHOLD/STOP。
結果を見ながらの早期合格・早期打切り・サンプル追加は禁止。
品質上の停止は利益/的中に関係なく記録し、欠けたデータを遡及予測で補わない。
中断後の再開・期間延長・閾値変更は独立再審査、新版seal、必要なら別holdout。

## 7. 実施前の未確定入力・証拠seal

`protocol_readiness(inputs)` は以下の**形式と整合**をローカル確認するだけ。
完全でも `READY_FOR_REVIEW`、自己申告証拠はUNVERIFIED、全GOはfalse。

- protocol ID、審査主体、一次metric/comparator、alpha/power/検出差。
- training cutoff < selection cutoff < holdout開始 < 終了（全てaware時刻）。
- candidate、parameters、schema、split plan、sealed holdout IDs、hypothesis familyのSHA。
- seal receipt、承認原本、pilot variance receipt、日間依存審査のSHA。
- 実pilot由来sd_day、実際に確保できる**開催日数**、欠測見込み。
- 非公開の元資料とSHAの真正性確認、予測の締切前保存・readback、第三研究系統の独立性。

次の承認欄は現時点で全て未記入。

| 項目 | 状態 / 確定者・日時・原本SHA |
|---|---|
| 候補/入力変換/全パラメータの固定 | PROPOSED / 未確定 |
| primary endpoint・family・検定/CI・非劣性/金銭安全条件 | PROPOSED / 未確定 |
| pilot分散・必要日数・日間依存の審査 | UNVERIFIED / 未確定 |
| training / selection / sealed future ID台帳 | OPEN / 未確定 |
| private実データ取扱・第三研究系統の予測証拠保存 | 未承認 |
| Claude独立審査 / HQ14整合確認 | 未実施 |
| アンディ個別GO（対象・SHA・期間・操作範囲） | 未承認 |
| Production・正式昇格 | 禁止 / 別案件 |

ローカル再現:

```
python -B -m unittest discover -s tests -p test_preparation_planning.py -v
```

合成fixtureのテストPASSは算式とソフトウェア挙動だけを示す。
実データ改善、独立証拠の真正性、統計的優位性、本番GOは検証していない。
