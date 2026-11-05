# D6：A予測仕様SHAの回帰確認と未提供原本の扱い

対象はA予測仕様の参照であり、専用OBS契約SHAではない。既存v001 QAコード・文書・テスト・fixture、v002訂正資料、requirementsは変更しない。

訂正された64桁値：

```
d462767f4448e28fc735df7363fb6f54a577e014607d5ec3b2fb1a75137c5e7f
```

歴史原文として保持する旧40桁値：

```
d462767f4448e28fc735df7363fb1a75137c5e7f
```

ローカル回帰試験で、桁数・小文字16進形式に加えて次の文字列関係を実測した。

```python
old_40 == corrected_64[:28] + corrected_64[-12:]
```

結果は一致。この一致は文字列上の事実であり、旧値が生成された原因や仕様本文からのdigest一致を証明しない。v001の `related_A_reference` が旧値を保持するのは原本保全のためで、現行参照はv002訂正資料と本資料を併記する。旧値を別アルゴリズムへ読み替えない。

## 受領claimとCodex実測の区別

最新ユーザー／HQ14のD6指示では、「Claudeが10/11のA写しから独立再計算し、訂正後SHAと一致した」という説明を受領した。これは**RECEIVED_CLAIM_ONLY**として記録する。CodexはClaudeの当該写し・計算原本・HQ14原文を再取得しておらず、その独立計算を自身で再現したとは報告しない。

正式 `PROMPT_TEMPLATE_SPEC` が208 UTF-8 bytesであるとの情報も受領しているが、その本文は今回未提供。本文を推測・復元・作成せず、ユーザーに提示や取得を求めない。桁数検査や上記切り詰め関係の成功を、208-byte正式本文の照合PASSへ格上げしない。

専用OBSの全文・版・SHA、payload `event_uuid` 必須性、列側のみの適格性、RUN_START空配列の許容、source_evidenceプロパティ欠損の正式違反性は、引き続きUNVERIFIED。

## 任意の非公開ローカル照合器

新規 `spec_sha_check.py` は、保有者が既に持つローカルファイルを任意指定する場合だけ読む。アプリ・タスク・Airtable・Drive等から取得する機能はない。デフォルトではパスを開かず、原本未入力としてSKIP／UNVERIFIEDを返す。

```python
check_private_spec(private_path=None)
# 戻り値は status / bytes / digest の3項目のみ。
```

指定時は、入力を一切正規化せず、UTF-8として解釈可能か、exact bytesが208か、SHA-256が訂正参照に一致するかを確認する。改行・空白・BOMを削除したり追加したりしない。本文・パス・例外文字列を出力しない。読取不能はbytes=0や一致扱いではなく、bytes/digest=nullのUNVERIFIEDとなる。

コマンド例の引数は非公開端末上の任意指定を示すもので、原本の提出依頼ではない。

```sh
python -B development/health_residuals_20261106_v003/spec_sha_check.py
python -B development/health_residuals_20261106_v003/spec_sha_check.py \
  --private-spec-file "<already-owned-private-file>"
```

未指定の出力：

```json
{"bytes": null, "digest": null, "status": "SKIP_UNVERIFIED_PRIVATE_ORIGINAL_NOT_SUPPLIED"}
```

CLI終了コードは未入力・読取不能等のUNVERIFIEDで3、不一致で1、ローカルbytes一致で0。一致時もstatusは `MATCHED_LOCAL_BYTES_EXTERNAL_AUTHENTICITY_UNVERIFIED` とし、原本の外部真正性や実タスクとの対応を保証しない。異常な引数も私有パスをechoせず固定statusだけを返す。

## 試験記録の範囲

新テストは、64/40桁とprefix/suffix関係、v002の「A予測仕様でありOBS契約ではない」という区分、旧4artifactのbytes/SHA不変、未入力時の無読取、パス非出力、UTF-8 exact bytesの負例を確認する。208-byte負例は明示的な合成文字列であり、正式本文の代用品ではない。

正式本文の任意照合試験は、ローカル保有者が `HEALTH_PRIVATE_SPEC_FILE` を明示指定したときだけ実行する。未入力ならpytestでは次の理由で**1件SKIP**になる。stdlib unittest実行でも同じ理由のskipとなる。

```
UNVERIFIED_PROMPT_TEMPLATE_SPEC_ORIGINAL_NOT_SUPPLIED
```

本作業の対象テスト実測は、Python 3.12.14と3.14.3でそれぞれ **5 passed, 1 skipped**。正式本文照合がPASSしたという意味ではない。全体スイートは親作業の別ログで管理し、この対象試験だけで全体適合を主張しない。

実タスク接続・取得、正式本文の請求、既存QA/仕様/requirementsの上書き、CI変更、本番操作は行わない。
