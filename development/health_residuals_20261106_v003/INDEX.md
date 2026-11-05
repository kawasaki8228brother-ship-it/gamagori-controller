# Health v003 / Claude独立再審査INDEX

親：`48333a2315628ae17e1fa3ce4f8ef12c70e2662f`  
隔離branch：`dev/health-residuals-20261106-v003`  
状態：オフライン候補、本番移植HOLD、GO=false。

1. [総合報告・D1–D7・OPEN・STOP](REPORT.md)
2. [parser/state政策とR/P fixture定義](S1_STATUS_POLICY.md) / [R fixture](parser_fixtures.py) / [P fixture](p_fixtures.py)
3. [B3旧経路の除去](NO_RACE_REMOVAL.md)
4. [Controller・watchdog・イベント列の試験範囲](CONTROLLER_AND_EVENT_REVIEW.md)
5. [C4/C5/C7/C8監査品質設計](AUDIT_QUALITY_DESIGN.md)
6. [208B仕様SHAの回帰準備とSKIP区分](SPEC_SHA_REGRESSION.md) / [Runtime matrix](RUNTIME_MATRIX.md)
7. [移植候補のファイル・hunk・除外一覧](PORT_SCOPE.json)
8. [ソース正確差分](C_SOURCE.patch) / [旧テスト期待の変更](TEST_EXPECTATIONS.patch) / [差分一覧](DIFF_STAT.json)
9. [実測結果](evidence/RESULTS.json) / [fixture bytes・SHA](evidence/FIXTURE_INVENTORY.json) / [ログ原本SHA・信頼区分](LOG_PROVENANCE.json)
10. [再現手順](REPRODUCE.md) / [原本・全ファイル検証器](verify_artifacts.py)
11. [親全ファイル台帳](PARENT_FILES.json) / [変更前原本と旧8172資料](references/)
12. [全files bytes/SHA256/Git blob](MANIFEST.json) / [SHA256SUMS.txt](SHA256SUMS.txt)
13. [旧新版assert対応・撤回／弱化の説明](ASSERT_MAPPING.md) / [5本全体のAST台帳](ASSERT_MAPPING.json)

旧資料は歴史原文として保存し、現在の動作・試験結果はこのv003資料で確認してください。R/Pは合成再構築で公式HTMLではありません。208B正式原文は未検証、状態語とHTML政策は暫定、C4transport統合はOPEN。本番実行やcertifi後基点への移植を承認しません。

追記2は初回v003 `971c63a95385690b365e16cadf22a8b1b50d097b`の後に追加commitで保全します。再監査は11/6 05:00〜06:30 JSTのcertifi作業より後です。予定時間だけで成功やGOを推定しません。
