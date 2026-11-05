# 11/5 Health残件：隔離改善候補 v001

本資料はオフライン開発結果です。本番障害の解消、Claude審査PASS、適用GO、CLOSEを意味しません。

- 基点：`8172aec010894a52f36f48b7091476d26494e4ee`
- 新規隔離ブランチ：`dev/health-residuals-20261105-v001`
- 対象：C raceindexの取得・解析・fallback・日付境界、A運用OBSの読取QA、未確認事項の監査設計。
- 実11/5 HTML・Events・DB・通知・設定は取得していません。公開fixtureは架空のSYNTHETIC_ONLYです。

## P0：C raceindex

### ソースと隔離実行から確認できたこと

旧parserは、合成HTMLの「同一行の複数時刻」「相反する重複レース」「表構造外のレース行」を受理しました。修正候補は3ケースを拒否し、正常12Rの全フィールドは旧版と一致しました。どのケースも実11/5のHTMLを再現したものではありません。

公式・tracking双方の取得失敗を注入した実Controllerの1周期試験では、旧版が前日レースを処理メソッドへ渡す挙動を3ケースで再現しました。候補は前日分を除外し、当日分だけを未確認の回復候補として扱います。実DB、実StateMachine処理、HTTP通信はこの再現に使っていません。保存済み状態は変更していません。

これらは確認できたコード上の弱点であり、11/5異常の根因・実発生を確定する証拠ではありません。

### 修正候補

| 箇所 | 変更 |
| --- | --- |
| `parsers.py` | レース・締切列の意味的anchor、曖昧値・重複・構造不一致の拒否、caller指定の期待レース集合との完全一致 |
| `official.py` | 公式取得失敗／HTML解析失敗／tracking欠損／tracking解析失敗を分離。HTTP 200だけで成功にしない |
| `raceindex_status.py` | 固定コードによる診断、独立日程証拠の正規化入力契約案。生の例外・URLを診断へ出さない |
| `main.py` / `raceindex_scope.py` | cache・保存済み回復・取得snapshotの日付/identity検査、日跨ぎ周期の処理抑止、型付き非開催の処理分岐 |

`NO_RACE_VERIFIED`は、対象日・会場・公式日程原本SHA・独立審査receiptの結合が確認された入力のみで発生します。空HTML、HTTP 200、ParserError、tracking欠損、no-known-raceログからは推定しません。入力ラベルと自己整合SHAだけでは外部の真正性を証明できません。

日程providerは既定で`None`です。実公式日程の取得アダプタも本番設定も追加していません。**この候補を置くだけで11/5がNO_RACE_VERIFIEDになることはありません。** provider契約はPROPOSEDで、実原本と独立receiptの確認はOPENです。

公式取得経路は原則12Rを要求します。短縮日程は独立審査済みの期待集合が必要です。これは誤った部分成功を避ける保守的条件であり、公式HTMLの実互換性・取消表示への対応は未検証です。直接parser呼出しの旧fixture互換性は残しますが、少数行を正式な全日程と認定しません。

trackingは常に非公式扱いです。閉鎖・中止や公式締切・LOCKの根拠へ昇格しません。両経路失敗後の当日保存状態は、公式取得失敗を維持し`official_info=None`で既存state machineへ渡します。前日分は処理対象から除外するだけで、削除・終端化・replayしません。

### 本番原因の確定に不足するもの

- HQ14が非公開で保全・審査する11/5の応答status、取得時刻、最終到達先の分類、HTML原本SHA、日程原本と独立確認。
- 開催日・非開催日・取消/短縮時の公式HTML構造の検証済み要約と、秘密や実原本を含まない再現fixture。
- 同時刻のtracking構造・対象日・stadium 7の有無の非秘匿要約。
- 実サービス・worker・DB identity、DRY_RUN/C_ACTIVEの承認済み安全な読取証拠。

これらの実取得は本依頼では行いません。

## P1：A運用OBS QA

`obs_qa.py`は入力行を変更しない純粋関数です。列とpayloadの`event_uuid`・source・producer_run_id・event_kind・idempotencyを比較します。AのRUN_START/RUN_ENDの確認済み式`SHA256("1|A|producer_run_id|RUN_START")`等を個別検査します。LOCKやBへこの契約を流用しません。

source_evidenceは項目欠損、null、空配列、明示MISSING、取得失敗、正常取得宣言、混在、不正形式を区別します。正常取得「宣言」は原本の真正性確認ではありません。提供された値同士の矛盾と、未確認の必須性を分離します。

**payload内UUID欠損、RUN_STARTの空配列、項目欠損を一律の正式契約違反にしません。** 専用OBS契約原本・版・SHAの独立照合がないため、該当判定はCONTRACT_UNVERIFIEDです。canonical profileも提案入力契約のため、局所的一致と正式A保存仕様の同一性を区別します。

架空20行の測定値はUUID欠損12、source_evidence項目欠損1、空配列3、正常取得宣言16、hash照合20、確認済みidempotency式一致20、一意20です。報告された実OBS20件の再検証ではありません。12行がCONTRACT_UNVERIFIED、8行がOBSERVEDで、OBSERVEDも正式適格の認定ではありません。

関連仕様として受領した`d462767f4448e28fc735df7363fb1a75137c5e7f`は40桁です。「SHA256」としての長さが一致しないことを記録し、勝手に訂正・アルゴリズム推定せず、OBS契約SHAにも流用しません。

将来のタスク修正は[提案書](../../docs/OBS_TASK_CHANGE_PROPOSAL.md)のみです。既存Eventsの補完、再送、編集、削除やAutomations変更はありません。

## P2：未確認事項の監査設計

[読取専用監査計画](P2_READONLY_AUDIT_PLAN.md)と[OPEN台帳](P2_OPEN_REGISTER.json)を作成しました。

| 対象 | 現在の判定 |
| --- | --- |
| C_ACTIVE/DRY_RUNの実設定 | UNVERIFIED。ソースの既定値・guardは実環境の測定ではない |
| 実SQLite直接readback | UNVERIFIED。固定監査原本のSHA一致だけでは実DB照合にならない |
| 通知到達 | UNVERIFIED。送信・transport ack・到達・人間の確認を別証拠とする |
| scheduler内部run IDと監査UUID | UNVERIFIED。producer_run_idから内部IDを推測生成しない |
| 過去B重複LOCK24件 | 件数は受領情報。再照合未実施、B固有canonical/hash契約も要確認 |

本番読取・通知送信を実行するコマンドは本提出で実行していません。DBの通常読取による既存SHM管理が物理変更を生む可能性を残し、「既存ファイル書込みゼロ」とは表現しません。

## 実施試験と限界

| 試験 | 環境と実測結果 |
| --- | --- |
| 基点の既存全テスト | Python 3.14.3、248 PASS |
| 修正候補の全テスト | 同環境、353 PASS＋14 subtests PASS。JUnit records 367とは区別 |
| 内訳 | 既存248＋新規105（parser38、official41、controller12、OBS14）。subtestsは別記 |
| OBS専用stdlib回帰 | Python 3.12.14、14 PASS |
| 前日レース再現 | 旧版3ケースすべて前日dispatchあり、候補3ケースすべてなし |
| parser境界再現 | 正常12R旧新版一致、旧版が受理した曖昧3ケースを候補は拒否 |
| OBS合成20行 | Python 3.12/3.14のfixture/reportがバイト一致。入力不変 |

C全体の試験OpenSSLは3.5.5、OSはLinuxです。HTTPはモックだけで、ネット接続は試験プロセス内で遮断しました。既存のPython環境を読み取り利用し、依存インストール・環境変更はありません。Python 3.12でのC全体互換性、実サービス/TLS/公式HTML/本番SQLiteはUNVERIFIEDです。生ログ・環境・SHAは`evidence/`と`LOG_PROVENANCE.json`を参照してください。

## 変更統制・復元・適用可否

元の40ファイル中、変更は`main.py`・`official.py`・`parsers.py`の3本です。他37本は基点とバイト一致です。3本の旧原本は`references/`に保存しました。新規ファイル全体はMANIFESTに列挙しています。

`state_machine.py`、LOCK有効性、締切判定、予想配点、通常5点、BOX、A/B reader/writer、既存テスト、requirements、render.yaml、CI、SQLite監査原本は不変です。parserのbeforeinfo/odds部分も不変です。scope検査はControllerの処理対象を限定するための候補で、締切ルールは変更しません。

**重要：この隔離ブランチは旧main基点の原requirementsを保持しています。deploy対象にしてはいけません。** certifi作業を優先し、後日採用する場合も、その時点の承認済みcertifi修正後の基点へ限定ソース差分を別途審査し、再試験する必要があります。旧脆弱deployへのrollbackは未承認です。

復元・破棄はこの候補のローカルコピーを破棄するか、独立ブランチで3原本へ戻す範囲に限ります。本番main/DBをreset・復元する手順ではありません。証拠commitは固定参照で保全し、共有ブランチの上書きや履歴改変をしません。

開発候補はDEV_READY（合成試験の範囲）です。実環境検証、Claude独立審査、HQ14整合確認、アンディ個別GO、適用・readback・自然稼働確認は未実施です。G1〜G6を代替しません。

Claude再審査対象は、厳格parserの可用性影響、日程証拠の真正性とprovider契約、日付/回復境界、OBS契約未確認の扱い、限定差分の将来取り込み手順です。根因未確認、時刻/identity不一致、部分HTML受理、tracking格上げ、read失敗、hash/receipt不一致、新規副作用はHOLD/STOPとし、自動修復・再送・task変更・本番停止を実行しません。
