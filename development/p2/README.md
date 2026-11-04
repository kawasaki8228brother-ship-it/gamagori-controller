# P2 情報源・独立性・証拠保全のオフライン試作

**OPEN（不足原本・独立証拠の確認待ち）**。作成済みは開発検証だけで、Claude審査PASS・本番GO・本番動作確認・CLOSEはいずれも未成立。
certifiを最優先とし、成果の確認・審査はHQ14によるcertifi終了確認後。11/9〜14のModel1.0・BOX Ver.1 Freezeは不変。

| 案件 | 今回の成果 | 維持する境界 / OPEN |
| --- | --- | --- |
| SYS-04 | 必要入力・差分検証設計・toy byte-slice fixture | `USER_HQ14_CONFIRMED_INPUTS_UNAVAILABLE`。D1〜D3/旧新の照合済bytes・SHAは提供不可とHQ14が回答。UNVERIFIED/OPEN固定、既存実装変更なし |
| SYS-14 | raw SHA / 保存receiptの主張 / readback bytesを独立検査 | local consistencyは取得元・時刻・DB・保存receiptの真正性を証明しない |
| SYS-15 | 正本とPOINTERのID/SHA/版名・明示decision参照の局所整合 | 実正本/POINTER未取得。承認履歴の真正性・最新順は認定しない。更新操作なし |
| SYS-16/17 | 合成C/parser観測の分類 | HTTP200/ParserErrorのみで内容正当・取得成功としない。SYS-17は将来入力変更候補のLane2/HOLD |
| SYS-23 | 宣言graphのA/B相互参照・中立node経由の推移経路を静的検出 | 実reader/filter/A/B本文は未検証・未変更。graph申告の完全性はUNVERIFIED |
| SYS-24 | 自己hashと外部のhash/時刻主張を分離、改ざんfixture | 独立した証拠の真正性は常にUNVERIFIED。新しい鍵・署名・保存先・DBを使わない |

## 実行済みの範囲

最終記録`results/r002.json` / `.log`（r001も履歴として保持）：Python3.12.14、Linux、**57 tests PASS / 46 synthetic cases / 0 failures / 0 errors / 0 skips**。
実レース原本・実Events・実行ログ・資格情報は0件。実サービスへの接続や通知送信は無い。
テストが通ったことは、D1〜D3適合・実A/B独立性・正本の承認・独立証拠の検証PASSを意味しない。

```sh
python -B -m unittest -v test_p2.py
python -B run_tests.py --run r003
python -B evidence_checks.py sys14 synthetic_request.json
```

記録済みrun IDは上書きせず、新しいIDを使う。CLIの入力はローカルJSONだけで、ネット取得/保存writer/署名鍵生成は無い。
CLIは最大1MiB、重複キー・非有限literal・不正UTF-8を拒否する入力ガードを持つ。これは既存SYS-02への統合ではない。
API/CLIの入力仕様は`INPUT_SCHEMA.md`。未知/欠損はUNVERIFIED、hash不一致はMISMATCHとして分け、真偽や0で補完しない。

## 重要な限界

- SYS-14は保存ACKと実保存を別にするが、readbackの取得元が本物かは検証しない。
- SYS-15は今回提案したmanifest schemaに対する整合検査。固定spec hashを全文hashとみなさず、historyの最後を自動採用しない。
- SYS-16は非開催の既知ParserErrorと日付・場・別の公式日程主張が両立するという限定観測。HTTP404とSSL失敗は別。
- SYS-23は宣言graphだけを検査し、実コード/readerの完全な静的解析や本番のデータ流証明ではない。中立Healthから予想系統へ相手データを中継する経路も違反候補として出す。
- SYS-24は`verified: true`という入力だけでは昇格しない。原本・自己hash・外部claimすべてを書き換えられても、外部の独立性は未確認のまま。
- Python3.14.3等での互換試験、実manifest schema・独立証拠方式の採択は未実施。

## 差分・復元・審査

新規`development/p2/`だけの追加。既存SYS-01/SYS-02や別案件コードをコピー・統合せず、依存commitは無し。
main・PR #6・C Shadow・parser・reader/filter・正本・POINTER・Model/BOX/LOCK/deadline/Freezeを変更しない。
適用していないので本番復元は不要。不採択なら隔離成果を適用せず保持し、mainや既存ブランチのreset/force-push/削除をしない。
私的入力を試す場合はHQ14の非公開環境だけを使い、その入力/出力を公開repoへ追加しない。
次のレビューは不足原本一覧、manifest schema、声明graphの取得方法、独立証拠の信頼境界。アンディの個別GOなしに実装を本番へ組み込まない。
