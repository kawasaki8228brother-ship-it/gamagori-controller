# Model 1.1 Shadow残件準備 v006 / オフライン提出

固定親: `f3c3a3eb17073bd0a127bb943f4eda21e407cf2d`。
新規隔離ブランチ: `dev/model11-shadow-prep-20261105-v006`。
既存196ファイルには手を加えず、準備用の新規ファイルだけを追加する。
対象v004/v005へのClaude監査PASS WITH NOTEはHQ14の受領情報。今回v006の正式審査は別途必要。

## 案件ごとの成果と判定

| 案件 | 追加したもの | 判定・未確定事項 |
|---|---|---|
| P1 capture準備 | RAW_V001/N1/captureの264項目、120買い目全件、単位・モーター・展示・時刻・履歴・欠損の入力表、無効なOPEN template、既存converterを1回だけ利用する合成確認器 | 実公式pointer/source/unit/formatはnull/OPEN。正式mappingを捏造しない。private入力・適用はHOLD |
| P2 F5事前登録案 | 現行72候補・構造上限61の照合、gridとselection日数の3案、市場比較、日cluster、holdout、多重比較、必要日数の仮定付き算術、停止・変更・承認欄 | 全案PROPOSED/未採用。F2も未採用。必要N・実分散・検出力はUNVERIFIED |
| P3 独立環境設計 | 独立root、容量計算式と合成実測、Python/SQLite/OpenSSL、時計・PID/再起動・STOP・保持・外部承認原本確認、読取専用のlocal probe | 実host/保存先/clock同期/容量基準/操作者/承認はnull/OPEN。host作成・install・task登録・deployなし |
| P4 12R網羅性 | 独立した予定12R原本のbytes/SHA/申告承認と、保存原本・receipt・completion・台帳の読取exportを照合するpure checkerとCLI | 欠落・重複・未保存・読取失敗・曖昧保存・締切後・日付差を別分類。完全一致もLOCALの観測であり真正性/起動GOではない |
| P5 N1系譜 | 旧一覧46件の全件対応、旧course archive→N1 diff→新courseのbytes/SHA/Git blob/固定URL、旧policy不変の検査 | 現行への直接照合45/46は承認済course置換1件が理由。archiveで歴史的原本46/46を再構成照合。旧SHA一覧は不変 |

通常5点、120確率、研究BOX、BET/SKIP、F1/F3/F4、既存writer/LOCKとv005の正常動作は変更しない。
Model 1.0、BOX Ver.1、正式A/B、main、PR #6、Production、Freeze、POINTERの変更は行わない。

## 実測と推測の分離

試験の実行件数・環境・生ログSHAは`results/TEST_RESULTS.json`に収録する。
合成12Rの既存v005を動かし、保存bytes不変の読取exportと網羅性チェックを再現する。
このfixture用writer実行と、pure checker/CLIの読取専用性を区別する。
checkには予定・原本・台帳の複数入力が必要。COMMITTEDという文字列だけでは成立しない。

予定承認metadataとexportの自己整合を照合しても、正式な公式予定・書込時刻・保存先の真正性は証明できない。
`OBSERVATION_COMPLETE_LOCAL`は外部認証・予測内容の全検証・runtime最終readback時刻の証明ではない。
最終runtime読戻し時刻が保存receiptにないことはUNVERIFIEDと明記し、v005を変更して埋めない。

新しい合成12R storeでは64ファイル、論理806,958 bytes、割当983,040 bytesを観測した。
これはspool・process log・model artifact・backupを除いた1回の合成観測であり、実データの容量上限ではない。
実際のfree容量、quota、保持・障害余裕、同期時計の誤差は未確定。数値例を正式運用値に昇格しない。

## 差分と復元

追加対象は`model11/shadow_preparation/`、`tests/test_shadow_preparation_*.py`、
`shadow_preparation_v006/`だけ。実行コードは既存converter/predictor/storeを置換せず参照する。
全ファイルbytes/SHAは新manifestに記録する。既存196件のbytes一致と、保存前後のGit tree/readbackを確認する。
新manifest自身と新SHA256SUMSの自己参照を除外し、両者のbytes/SHAは納品時に別記する。

破棄はv006の新規追加コード・専用合成一時領域だけを対象とし、旧commitをcheckoutすれば旧動作へ戻れる。
既存ブランチや本番のreset/rollback、実Shadowの予約削除、STOP解除、replayは実施しない。

## OPENとClaude審査対象

1. 公式実構造・取得経路・source mapping・単位・時刻・改訂履歴の独立原本。実データはCodex/公開GitHubへ渡さない。
2. F5の案選択、実pilot分散、最小selection日数、holdout期間、事前固定family/CI/欠測規則。HQ14/Claude/アンディの判断待ち。
3. F2の比較可能な研究案と正式旧版比較。今回のgrid案も既存configへ反映しない。
4. 独立実host、runtimebuild、専用root、clock/同期原本、容量/quota/retention、操作者/復旧承認。
5. 承認済公式予定12R原本と、独立所有storeからの安全な読取export手順・所有ID pinの私的確認。実稼働store抽出器は未実装。
6. N1履歴の「期待された置換」と破損・無断改変の区別、checkerのLOCAL判定境界、private HOLDとCLI無効状態。

完成したのはオフライン準備部品と審査資料。実データ検証PASS、Shadow起動承認、実稼働、正式昇格、CLOSEは未成立。
本番接続・実サイトアクセス・秘密値使用・host作成・定期task登録・PR作成・merge・deploy・Shadow起動は行わない。
certifiのソース、依存、仮想環境、ログ、ブランチ、設定は変更しない。試験用Pythonは既存interpreterの読取利用だけで、installは行わない。
