# private pilot分散・欠測率の集計器 v007

状態は**オフライン開発 / 実データ未使用 / F5未採用**。Codexは実データ・実結果を
取得せず、下記の既知vectorと欠測を合成した10件の試験だけを実行した。
実運用はHQ14の非公開環境で別途承認された資料を入力することを想定する。
既存モデル、F2、F5文書・閾値、selection N、予測・保存処理は変更しない。

## pure APIと二つのJSON入力

```
summarize_pilot(
    roster, observations, *, baseline_id, baseline_version,
    endpoint='JOINT_120_LOGLOSS', roster_complete=False,
    model_id=None, model_version=None
)
```

I/O・通信・自動ファイル作成なし。入力を変更せず、集計summaryだけを返す。
ファイルの読取はHQ14用の外側CLIの責務。入力原本や詳細を公開先へ書き出さない。

`roster`は予定対象全件の`[{race_id,target_date},...]`、または未提供のnull。
各target_dateは正確なYYYY-MM-DD。予定台帳の完全性を外側で確認した場合だけ
`roster_complete=True`を明示する。台帳があるというだけで完全と推定しない。
予定台帳と観測のID・日付対応を検査し、余分な観測や相反する日付はHOLD。

`observations`は次の必須fieldを持つlist。

| field | 条件 |
|---|---|
| race_id / target_date | 予定台帳と対応。入力内で一意 |
| baseline_id / baseline_version | callerが明示した固定値と全行一致 |
| model_ll / market_ll | 自然対数joint120 log-lossの有限非負数、または未知null |
| state | PAIRED / MISSING / READ_FAILED |

任意fieldはmissing_reason、probability_endpoint、model_id、model_versionのみ。
endpointを付ける場合もJOINT_120_LOGLOSSに一致させる。異なる予測対象を混ぜない。
model ID/versionを付ける場合は両方を全行で揃え、混在・版混在を拒否する。
未提供ならモデル結合はUNVERIFIED。caller指定model_id/versionがある場合は全行照合。

PAIREDは両scoreが既知でmissing_reasonなし。ここでeligibleとするのは
**callerがpaired適格と申告した行**だけであり、codeが実際の時点適格性を認証しない。
適格/対象外の基準と予定分母は、実結果を見る前に外部の評価計画で固定する。
この集計器には、都合の良い行だけを採用するselectorや自動除外機能はない。

## 欠測分類

- MISSING: MODEL_MISSING / MARKET_MISSING / BOTH_MISSING。
- READ_FAILED: MODEL_READ_FAILED / MARKET_READ_FAILED / BOTH_READ_FAILED /
  SOURCE_READ_FAILED。
- NO_OBSERVATION: 提供された予定台帳にはあるが観測行自体がない。

MODEL_*はmodel scoreがnullかつmarket既知、MARKET_*は逆、BOTH_*は双方null。
SOURCE_READ_FAILEDでは少なくとも一方がnull。行stateとreasonの矛盾はHOLD。
両scoreが揃うのにmissingとする操作や、欠測をlog-loss 0へ補完する操作は禁止。
log-lossそのものの0は確率1に対応する有効な実数であり、欠測ではない。

完全な予定台帳の明示があるときだけ、以下を予定件数で割る。

`MISSING`, `READ_FAILED`, `NO_OBSERVATION`, `TOTAL_UNPAIRED`

例: 予定4件、paired1件、MISSING1件、READ_FAILED1件、行なし1件なら、
各欠測率は0.25/0.25/0.25、total unpairedは0.75。
台帳未提供・完全性未確認ならplanned denominatorと**全欠測率はnull**。
受領行がすべてpairedでも「欠測0%」とはしない。空の予定台帳でも率は未定義null。
supplied roster内の行なし件数と、認証されていない全体分母を区別する。

## 日等重みのsample SD

同一日の対応したPAIRED行だけで
`d_j = mean_r(model_ll - market_ll)` を計算する。
次にK個の日平均のsample SDを、分母**K−1**で求める。
日ごとのレース数が異なっても、日平均は一日一票で扱う。
レース全件を直接standard deviationへ渡す方法とは異なる。

合成known-vector:

- 1日目1レースの差1、2日目3レースの差が各3なら、日平均は[1,3]、sd_day=√2。
- 3日の日平均が[1,3,5]ならsample SD=2。母分散の分母Kは使わない。
- K<2ならsd_day=null/UNVERIFIED。
- 複数日の観測差が同じなら実測sample SD=0を返すが、将来分散0と推定しない。

sample SDだけを返し、日別差、日付、レースID、元score、baselineラベル、
個別行、改善幅や性能判定をsummaryへ含めない。
model−marketの符号は既存F5のmarket−modelと反対でもSD値には影響しない。
この集計器は優劣判定を返さない。

## score由来と時点適格性の境界

**この集計器はscoreをcallerから受領するだけ**。確率や結果からlog-lossを
再計算せず、実際に締切前に取得したmarketか、PIT履歴があるかも検証しない。
baseline ID/versionの一致は、同じラベルの入力だという整合確認に過ぎない。
実際の締切前odds、計算式、対応結果、取得・利用可能・改訂時刻の真正性は未検証。

固定report欄:

- losses_origin=CALLER_SUPPLIED_NOT_RECOMPUTED
- pit_and_predeadline_baseline_audit=UNVERIFIED_EXTERNAL_EVIDENCE_REQUIRED_BEFORE_F5_USE
- source_data_authenticity=UNVERIFIED_SELF_REPORTED_INPUT
- day_independence=UNVERIFIED

latest/final oddsへのfallbackは実装しない。外部の独立したPIT・締切前baseline監査、
原本bytes/SHA・保存receipt/readback、score再計算照合を通す前に、このsdをF5採用値へ
昇格させない。独立日cluster仮定、日間/節間依存、pilot対象選定も外部審査が必要。

## HOLD・共有・採用の区分

重複、相反日付、予定台帳との不一致、baseline/endpoint/model版不一致、
NaN/inf/負LL/bool、矛盾した欠測reason、未知field、計算overflowでは**全体HOLD**。
一部の悪い行だけを捨てて小さいsdや高いcoverageを出さない。HOLD時はsdとcountsを
不明にし、固定reason codeだけを返す。提出値・パス・秘密ラベルをerrorへ埋め込まない。

正常に集計できてもSUMMARY_COMPUTED_UNVERIFIEDであり、統計的PASSではない。
sample size adequacy、分散の安定性、day独立性、source真正性は未確認のまま。
power_guarantee=false、f5_adopted=false、f2_changed=false、production_go=false。

HQ14は非公開側に入力原本を保全し、共有する場合はsummaryと独立審査の非秘匿
receiptだけを選ぶ。Codexへ実レースのscoreや詳細日別表を渡す必要はない。
sd_dayは外部pilot審査後にv006の**illustrative planner**へ入力できるが、
計画算式の結果が正式必要N・採用閾値になるわけではない。0 SDや不足Kから
架空の必要日数・ゼロリスクを生成しない。最終決定はHQ14/Claude/アンディ。

再現: `python -B -m unittest discover -s tests -p test_offline_refinements_pilot.py -v`

10件は合成算術・欠測区分・privacy・HOLD・不変性だけを確認する。
実pilotの取り込み・実データ検証・本番実行は行っていない。
