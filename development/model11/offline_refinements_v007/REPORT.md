# v007 小規模オフライン候補・監査提出

親 `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`。
新規隔離ブランチ `dev/model11-offline-refinements-20261105-v007`。
既存245ファイルはbytes不変。今回追加したのは独立した読取・集計部品と資料のみ。
旧v006へのClaude PASS WITH NOTEはHQ14受領情報であり、このv007の正式審査とは別。

## 今回の4件

1. **schedule基準の網羅性**: 期待数は申告承認済みnormalized manifestのSCHEDULED行から算出する。
   CANCELLED_OFFICIAL / WITHDRAWN_OFFICIALはrace単位の原本bytes/SHA、mapping/version、source/class、
   日付・race identity・発効/取得/利用可能/改訂時刻の証拠を別途要求する。予想がないだけで取消を推測しない。
   既存予想は取消後も保全・未評価のまま、時刻の前後関係を示す。旧12R固定checkerは変更しない。
2. **point-in-time**: 当時のimmutable snapshotを対象とし、特徴量/oddsの取得・利用可能・改訂が
   snapshot保存時刻とas_ofより後なら拒否する。後日更新された統計を古いeffective_atだけで認めない。
   締切前odds欠損をFINALで置換しない。各過去train/selection/validation/evaluation snapshotへ個別に適用する。
   fit cutoffの申告だけで訓練原本の不変性を確認済みにしない。実入力・適用はHOLD。
3. **private pilot集計器**: 同じレースのmodel LL−market LLを日内平均し、paired開催日平均のsample SDを
   K−1で計算する。K<2はsd_day=null、観測SD=0は将来分散0と同一視しない。
   欠損/読取失敗/観測行なしを分け、full rosterの網羅性申告がなければ欠損率の分母は未確認のまま。
   返すのはsummaryだけで、ID・日付・個票・daily means・baseline名の値を含めない。
4. **monotonic診断**: 任意の設計資料のみ。wall clock、boot内のcounter、外部UTC同期を分ける。
   host接続・時計取得の新しい実装・閾値・LOCK判定・自動起動は追加していない。

全てのnormalized schemaと実公式mappingはPROPOSED/OPEN。OFFICIALというenumや自己hashは真正性を証明しない。
後日の取消は、当初の締切時点のLOCK/AC1義務を遡って免除する根拠にしない。
このcheckerは現manifestのcoverageのみで、当初義務はUNVERIFIED、AC1率計算は対象外。
pilotのrosterも自動的にschedule結果から変更しない。

## 検証

実行件数・環境・生ログSHAは`results/TEST_RESULTS.json`。実行した試験だけをPASSとして記録する。
新機能のfixtureは架空2099年。scheduleはv006で保全済みの合成予測証拠を読んで使い、model/storeを再実行しない。
再現器は新しい一時dirへ合成入力・結果JSONを出すだけで、checker・auditor・集計器・CLIは保存操作を行わない。
全旧テストを含めてPython 3.12/3.14で検査し、sourceの旧245ファイル一致を再計算する。

pilot例は日内件数1/2/3、日平均差1/2/4でsd_day=sqrt(7/3)。
planned roster 9件のうちpaired6件、MISSING/READ_FAILED/NO_OBSERVATION各1件を区別する。
この数値は合成の算術検証で、実pilot分散・必要N・性能評価ではない。
scoreはcaller提供で再計算せず、PIT・締切前市場の真正性は別の独立審査が必要。
未知の分母や読取失敗を0として集計せず、重複・日付差・不正LLは全体HOLD。

## 変更・優先順位・採用境界

新規追加対象は`model11/offline_refinements/`、`tests/test_offline_refinements_*.py`、
`offline_refinements_v007/`。予想エンジン、通常5点、BOX、既存writer、LOCK、保存経路を変更しない。
certifi、SYS-01/02のsource/branch/settings/environmentを変更せず、試験は別作業dirで低優先度に実行する。
追加install、実host作成、定期task登録、実site/Production接続、PR作成、merge、deploy、Shadow起動は行わない。

F5のA/B/C案・全閾値、F2はPROPOSEDを維持。M0→M2→M1は推奨順序で、正式採用ではない。
提供資料からM0/M2/M1の詳細定義を推測して実装しない。
実データ投入HOLD、Model 1.0/BOX Ver.1/正式A/B/FREEZE/main/PR #6/Production/POINTERは無変更。

## OPEN / Claude審査対象

- 実公式scheduleと取消/撤回原本、normalized mapping、source・各時刻の独立した証拠。
- 過去時点の保存原本・変更履歴、PIT適用対象の全train/selection/evaluation台帳、締切前oddsの存在。
- HQ14非公開環境だけの実pilot処理、full roster網羅性、固定model/market endpointと版、summaryの独立照合。
- sd_day・欠損率を使うF5の最終条件、候補grid、holdout、日/節依存、必要N・停止規則の個別決定。
- 任意の時計診断の採否と、もし採用する場合の別設計・独立host/clock確認。
- v007の独立Claude審査、HQ14整合確認、アンディの案件別GO。コード候補完成を適用可否やCLOSEに昇格しない。

復元は親commitをcheckoutすることで可能。新規候補コードと合成一時dirだけを破棄できる。
正式branchのreset、既存原本の上書き、実Shadow STOP解除やreplay、脆弱deployへのrollbackは行わない。
