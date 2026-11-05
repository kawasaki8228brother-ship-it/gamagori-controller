# Model1.1 実データ検証準備 v002 提出報告

Lane2・オフラインのみ。旧候補71ddd13の47ファイルはバイト不変。

## 実装と試験

| 項目 | 完了範囲 | 実データ／運用状態 |
|---|---|---|
| private入力契約 | RAW_V001、train-only正規化、単位方向、motor時点、revision、審査metadataゲート | 実mappingと外部証拠OPEN |
| Model1.0/BOXv1比較口 | 凍結bytes/hash/parsed/profile/receipt・A/B別帳簿 | 正式入力未取得OPEN。推測再現なし |
| EV・BOX診断 | 固定27シナリオ、元tickets不変、別IDの保守overlay | PROPOSED、最適化なし |
| 未使用評価案 | primary／日cluster／標本計算／多重性／seal／STOP | 未審査・未登録HOLD |
| Shadow出力仕様 | 4段階120、5点と3BOX、時点証拠、raw＋receipt、再現hash | 生成器だけ。実通信／運用なし |

最終Python3.12.14／3.14.3で各263テストPASS（失敗0、skip0）。旧148件を含む。
Linux、OpenSSLは3.12環境3.5.8、3.14環境3.5.5。テストと全デモはsocket接続を禁止。
追加デモの全研究JSONは両環境でバイト一致（実行時刻を含むruntime/FILESは除外）。
旧40Rのfull-summaryは1,239,489 bytes／SHA256 09a2c12c68583cf02e111276380df007027d0d0750a866052365b1e4e366d587と一致。

## EV監査：観測と仮説を分ける

| 方式 | 予測的中数合計 | 予測仮純収支 | 観測仮純収支 | 別overlay SKIP |
|---|---:|---:|---:|---:|
| box_v11_research | 1.066240 | 28674.40円 | -24000.00円 | 40/40 |
| five | 8.800152 | 13353.02円 | 13092.16円 | 40/40 |
| human_research | 5.112563 | -8142.18円 | -11835.77円 | 40/40 |
| mechanical_research | 7.171527 | -5098.73円 | -4802.58円 | 40/40 |

BOX1.1は0/40。予測的中数合計は1.066240、平均coverageは2.6656%。
モデルが正しく各race条件付き独立という仮定下の0的中確率は0.334409。p値ではなく日依存も未考慮。0/40だけで因果的な過大評価を確定しない。
P_modelのjoint log-lossは市場より約0.4690悪い。下方オッズ、確率誤差、平坦化、高配当EV集中を各scenarioで記録。
別overlayの全SKIPは、市場100%・odds75%というstressと合成価格設計の影響が大きい。収益改善・適切な実運用閾値を立証しない。
元候補・買い目・BET/SKIPは上書きせず、既知40Rを未使用／事前登録済みと呼ばない。

## 未使用評価・日程

primary案：EQUAL_DAY_JOINT_120_LOGLOSS_DELTA_MARKET_MINUS_SHRUNK。正の差が研究候補の低lossを意味する。
既知合成40Rの差は-0.232949。これは事後の記述値で、正式優位性検定ではない。
最終候補とparametersを固定し、学習／選択／将来holdoutを分離。同日は同じpartition。複数候補は事前固定familyのHolm等を審査。
日clusterの標準偏差を非公開pilotで確認し、正規近似の独立日仮定・系列依存・必要標本数を再審査する。

- 仮SD=0.1、効果=0.02、power=0.8、片側alpha=0.025：197日cluster（例示値、採用なし）。
- 仮SD=0.1、効果=0.05、power=0.8、片側alpha=0.025：32日cluster（例示値、採用なし）。
- 仮SD=0.2、効果=0.02、power=0.8、片側alpha=0.025：785日cluster（例示値、採用なし）。
- 仮SD=0.2、効果=0.05、power=0.8、片側alpha=0.025：126日cluster（例示値、採用なし）。
- 仮SD=0.3、効果=0.02、power=0.8、片側alpha=0.025：1766日cluster（例示値、採用なし）。
- 仮SD=0.3、効果=0.05、power=0.8、片側alpha=0.025：283日cluster（例示値、採用なし）。

実分散不明はUNVERIFIED。4日を多数raceで置き換えて標本十分としない。
11/9～14の結果を見て評価条件を後付け変更しない。11/21～24は最速Shadow候補日程だけで、実行GO・scheduleなし。

## Shadow原本

合成原本：41547 bytes、SHA256 526070cecd14ea5fc7238997e9139c4b3db1fe84e6a6e48ed5a7feadc571fa8b。
原本とreceiptは別ファイル。自己整合の検証成功はSELF_CONSISTENT_ONLY、外部真正性はUNVERIFIED。
sampleのcode_commitは凍結engine基点71ddd13の参照例。wrapper追加コードの実commitは今回の提出commitで固定される。実Shadow時は審査済み配布commitをreproductionへ指定する。
入力artifact SHAはcanonical race JSONのhashであり、未知の元ファイルbytesとは区別。raw原本bytesの証拠は別receiptで保全する。
全5点／BOX／4段階120／時点・欠損／BET-SKIPを保持。結果を予測原本へ混ぜない。減艇・欠損stage・締切後生成・hash不一致はHOLD。

## 未実施・OPEN

- 実レースデータ・本番認証情報・正式A/B原本は未取得／未使用。
- 正式Model1.0／BOXv1との実比較、実calibration・利益・精度改善はOPEN。
- 私有実mapping、HQ14／Claude実審査、未使用評価seal、実分散・標本数の確定は未完了。
- 本番writer・通知・実舟券購入・正式A/B接続は未実装。Production操作GOなし。
- 新RAW入力の全fold自動正規化trainerは未実装。契約とtrain限定fit／適用モジュールまで。
- 独立Reviewで発見したmotor発効前統計と結果時刻の欠陥は修正・回帰済み。詳細REVIEW_FINDINGS。

## 再現・破棄

```sh
cd development/model11
python -B run_checks.py
python -B -m model11.preparation.cli demo --output-dir /tmp/model11-prep-v002-unique
```

既存出力への上書きは禁止。部分失敗は保全してSTOP。追加研究ファイルの削除だけで元候補を維持できる。
本番無変更なので本番rollback／restoreは行わない。
