G5 H1-H3修正版草案／Claude独立再監査提出用／文書作成のみ、GO=false
基点70db14bの旧G5は不変。本フォルダを新規追加し、P1-P9の統制を保持する。

G5-GO-PACKAGE-DRAFT.txt: 操作順、非開催日N1-N4、運用identityと残余リスク、DB同一性。
H1-H3-COVERAGE.tsv / R1-R5-COVERAGE.tsv / P1-P9-COVERAGE.tsv: 修正・維持の対応表。
changes/G5-H1-H3.diff: 基点70db14bのG5旧資料との正確な差分（パスのみ改訂フォルダへ対応）。
GO-1-DRAFT.txt / GO-2-DRAFT.txt: 個別操作を列挙した2通の未署名・条件付きGO文案。
IPHONE-OPERATOR.txt / READONLY-PREVIEW.txt: 1回貼付・フレーム・中止と将来の限定読取下見。
RAW-ORIGINALS.txt / RAW-COMMANDS.json / tsv: 固定379原本のURL/bytes/SHA/end token。3資料は旧G5とバイト一致。
DB-IDENTITY.tsv / NONRACE-OBSERVATION.tsv: H3のG2前HOLD、H1の限定観測条件。
PERMISSIONS.tsv / STOP-MATRIX.tsv / CHECKLIST.tsv / POST-ENV-COVERAGE.tsv: 権限/停止/前後確認。
APPROVALS-AND-INPUTS.json / PRIVATE-EVIDENCE-TEMPLATE.txt: 全て未承認・未観測の入力欄。
TASK-WINDOWS.json: W60優先未承認、merge残30分、予定起動と実稼働衝突を分離。
EXPECTED-OBSERVATIONS.json: 期待値契約。実測値ではない。
references/: 監査原本のメタ情報、GitHub読取、静的コード経路、既存の試験根拠。
validation/: 文書・暗号照合結果のみ。Shell/TLS/DB/runtimeの実行試験ではない。

INDEX/MANIFEST/SHA256SUMSは本新規フォルダに限定。自己SHA循環は明示して除外。
6原本はコピー/変更/実行せずcommit379cc1dへ固定参照。PR/main/旧証拠/アプリコードは不変。
実service ID、承認receipt、実ログ/スクショ/バックアップ、秘密値は公開証拠へ保存しない。
プロセス単位identityはUNVERIFIED。E07運用条件と残余リスクはアンディ最終判断対象。
Claude独立再監査 → HQ13整合確認 → アンディ正式GO。現在、Production/Render操作は何も許可されない。
