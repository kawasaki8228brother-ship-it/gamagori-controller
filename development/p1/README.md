# P1 独立監査部品・合成fixture 初回試作

状態 **DEV_READY（合成fixtureによる開発検証のみ）**。Claude独立審査は未実施、適用可能性NO、本番適用・CLOSEは未実施。
certifi再実施を最優先とし、この成果の確認・審査はHQ14のcertifi終了確認後とする。
11/9〜14のModel1.0/BOX Ver.1 Freeze、A/B独立性、LOCK有効性、締切、配点を変更しない。

`audit_p1.py`の各関数は独立した観測分類器。ネットワーク、writer、タスク、資格情報、実DB、実送信の実装は無い。
SYS-01/02や他案件をimport・コピー・統合していない。共通の正式判定を置き換えるコードではない。

| 案件 | 開発範囲 | 判定しないもの・OPEN |
|---|---|---|
| SYS-05 | physical Events total/race-linked/unlinked/OBS subset。read失敗と0件を区別 | race一意件数や有効Nではない。実production/test判別契約は未検証 |
| SYS-06 | 同keyの同raw hash/異raw hash/原文取得不能を分類。hash主張と計算値を分離 | duplicateを削除・修復しない、LOCK VALID変更なし |
| SYS-07 | 明示研究profileの列raw hashとpayload内の固定spec hashを別々に照合 | 実B仕様不明。profile未提供/非対応はUNVERIFIED、既存LOCK判定に使用不可 |
| SYS-08 | missing/null/空文字/数値0/false等を別分類 | 空白や数値文字列を自動trim/数値変換しない |
| SYS-11 | START/END存在、重複、scope、stage statusの観測 | 正当なSTART保存失敗後のENDを不可能扱いしない。receipt保存/時刻/hash実検証ではない |
| SYS-12 | 非開催Summaryと公式RESULT/Shadowを独立に分類する研究 | Daily writer・精算・既存分類ルールを変更しない |
| SYS-13 | 合成Daily表示で必須証拠の欠落/値/型の変更を検出 | Daily promptや表示実装は変更せず、実prompt実行はUNVERIFIED |
| SYS-29 | 送信・到達・receiptの供給済み証拠主張を独立表示 | 実通知0回。外部証拠の真正性はここでは検証しない |

## 再現

Python標準ライブラリのみ。実行環境は`results.json`と`tests.log`の実測値を参照。

```sh
python -B -m unittest -v test_p1.py
python -B audit_p1.py SYS-05 CLI_EXAMPLE_SYS05.json
```

`fixtures.json`の全件は合成であり、実Events・実レース・実行ログではない。
合成fixture件数とHQ14が別途扱う実データ56件は無関係。実データを受領・取得していない。
CLIはlocal JSONだけを読み、stdoutへ結果を返す。ファイルは書き換えず、2MiB超過・重複JSONキー・非有限JSON入力はINPUT_ERROR。
module APIはJSON形式に相当するPython値を前提にする。入力仕様外の実装へ無承認で組み込まない。

## 個別の入力・意味

SYS-05：`rows`と`read_status=READ_OK_COMPLETE/READ_FAILED/INCOMPLETE`。
合成profileでは`is_test=true`またはTEST_接頭idを除外し、明示falseだけproduction観測に含める。
flag欠損/0等はproduction_unknown。未完了・読取失敗のtotalはnullであり0ではない。
race_idのmissing/null/空文字はunlinked、空白のみ/非文字列はlink_unknown。OBSはsubsetで二重加算しない。
これは実sourceフィルタの変更ではなく、現在の実フィールド契約はHQ14審査待ち。

SYS-06：各recordの`key`,`payload_raw_b64`,`claimed_hash`。実raw bytesのSHAを計算し、claimとの一致を別に返す。
同claim hashでも異rawはCONFLICT。原文未取得の重複はDUPLICATE_RAW_UNVERIFIED。
出力はkeyのSHAと集計で、原文/値/key名は出さない。同raw duplicateでも自動受理や削除をしない。

SYS-07：`column_hash_kind=RAW_BYTES`,`embedded_hash_kind=FIXED_SPEC_REFERENCE`,
`expected_spec_hash`,`embedded_hash_field`を必須とする合成研究profileだけを試作。
payloadの**原bytesを解析**して指定fieldを取得する。別途供給されたembedded値を無条件に信じない。
列hashと埋込spec hashが異なること自体は異常ではない。両者の参照対象は別。
重複JSON/不正UTF-8/非object/原文欠損/不明profileはUNVERIFIED。実Bのfield名やhash再計算範囲は未確定。
このprofileを既存実装済みと認定せず、`LOCK_validity=NOT_EVALUATED`を保持する。

SYS-11：一つのrun/task scopeを渡す。混在は警告に残す。PAIR_PRESENTは保存真正性のPASSではない。
STARTなしENDは、START保存失敗の独立証拠がある場合の分類と、根拠なし未確認を分離する。
その証拠もcaller claimとして扱い、ここでAirtable保存を確認したとはしない。

SYS-12：公式開催状態、Summary種別、RESULT種別を**供給済み証拠**から分類。
非開催Summaryを公式RESULTへ昇格させず、0件やShadow dry-runを公式の無損失/精算成功と解釈しない。

SYS-13：監査状態/scope/件数/receipt/未確認の5群を型も含め保持する合成表示契約。
欠落、0→false、sourceリスト順の変更、未審査追加fieldを検出する。実Daily文字列や自然runの適合は未検証。

SYS-29：各軸の`status`,`verified`,`evidence_ref`を独立に分類する。
返すCONFIRMED/FAILEDは供給された証拠主張の分類にすぎず、真正性の検証はUNVERIFIED。
receipt成功は送信/到達を証明しない。送信成功も到達を証明しない。総合E2E成功を自動生成しない。

## 復元・破棄・次レビュー

新規隔離ディレクトリのみ。既存本文・writer・保存経路・schema・CI・requirementsは変更していないため本番復元は不要。
棄却時は適用せず、隔離成果を証拠として保持する。main reset/rollback・既存ブランチ上書き・実記録の遡及訂正はしない。
HQ14/Claudeには`OPEN.json`の実profile・scope/epoch・取得完全性・hash参照対象・Daily義務をprivate環境で確認してもらう。
確認済みの実source契約がない案件はOPEN。新しいProduction GO、readback、自然run確認なしにAPPLIED/CLOSEへ昇格しない。
