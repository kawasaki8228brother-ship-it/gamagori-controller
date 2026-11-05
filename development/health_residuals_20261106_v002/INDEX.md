# Health残件 v002 / S1・S2 Claude再審査INDEX

親：`845cc1c9c6667699a21933cb4b9d7c324c79ce44`  
新隔離ブランチ：`dev/health-residuals-20261106-v002`  
用途：OFFLINE SYNTHETIC RESEARCH。production GO=false、適用HOLD。

- [総合報告・変更範囲・OPEN・STOP](REPORT.md)
- [S1 parserと7記述の再現候補](S1_PARSER.md) / [合成fixture原本](parser_fixtures.py)
- [S2 認証不能な非開催認定の無効化](S2_AUTHENTICATION.md)
- [Controller安全回帰・内部レビュー](CONTROLLER_REVIEW.md)
- [A予測仕様SHA訂正](OBS_SHA_CORRECTION.md) / [機械可読記録](OBS_SHA_CORRECTION.json)
- [正確なソース差分](C_SOURCE.patch) / [旧期待値の変更差分](TEST_EXPECTATIONS.patch) / [全差分一覧](DIFF_STAT.json)
- [実施試験と3版比較](evidence/RESULTS.json) / [生ログの原本SHAと信頼区分](LOG_PROVENANCE.json)
- [再現手順](REPRODUCE.md)
- [親全ファイルのbytes・SHA・Git blob](PARENT_FILES.json) / [変更前原本](references/)
- [全ファイルbytes・SHA・Git blob](MANIFEST.json) / [SHA256SUMS.txt](SHA256SUMS.txt) / [ローカル検証器](verify_artifacts.py)

7形式はHQ14の監査記述から作った合成再現候補で、ClaudeのHTML原文と同一ではありません。公式HTML互換性・実11/5原因はUNVERIFIED。非開催認定とprovider実行は無効です。旧v001資料のPASSや説明は過去の範囲で保存し、本候補の現在状態はこのINDEX以下を参照してください。

旧基点由来の候補をdeployしないこと。certifi・本番・正式A/B・Model/BOX・main/PR #6・既存ブランチ・task・POINTERの変更権限はありません。
