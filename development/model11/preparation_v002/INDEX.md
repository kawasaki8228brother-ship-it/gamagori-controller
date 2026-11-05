# Model1.1 実データ検証準備 v002 INDEX

基点：`71ddd13dd5869aaf892a504ea0553c60e8b8abe2`
新規隔離branch：`dev/model11-validation-prep-20261105-v002`
Lane2 / 合成ソフトウェアDEV_READY / 実データ検証OPEN / 本番GO=false。

- [提出報告](REPORT.md)
- [再現CLI・5項目・STOP表](README.md)
- [RAW入力契約・正規化](INPUT_CONTRACT.md)
- [凍結A/B比較口](LEGACY_INTERFACE.md)
- [EV・BOX監査](EV_AUDIT.md)
- [未使用評価事前登録案](PREREGISTRATION_PROPOSED.md)
- [第三研究Shadow出力契約](SHADOW_CONTRACT.md)
- [開発内独立レビューと修正](REVIEW_FINDINGS.md)
- [元候補INDEX（不変）](../INDEX.md)
- [新規・保持ファイルのbytes/SHA/Git blob](MANIFEST_V002.json)
- [新規ファイルSHA256SUMS](SHA256SUMS_V002.txt)

実行証拠：

- [Python3.12全263件生ログ](results/tests-python312.raw.log)
- [Python3.14.3全263件生ログ](results/tests-python314.raw.log)
- [3.12デモ生ログ](results/demo-python312.raw.log)
- [3.14.3デモ生ログ](results/demo-python314.raw.log)
- [環境・不変性・試験結果](results/verification.json)
- [元候補のfull-summary SHA一致](results/baseline-preservation.json)
- [raw／derived区分・サイズSHA・runtime比較](results/artifact-provenance.json)
- [RAW入力正規化の別smoke予測](results/adapter-smoke-prediction.json)
- [train-only normalizer](results/adapter-synthetic-normalizer.json)
- [正規化audit](results/adapter-smoke-audit.json)
- [合成A/B凍結入力比較](results/legacy-synthetic-comparison.json)
- [EV監査要約](results/sensitivity-summary.json)
- [EV監査全データ：lossless minified JSON](results/sensitivity.full.min.json)
- [標本設計・primaryの記述値・HOLD](results/sample-size-planning.json)
- [Shadow合成raw原本](results/shadow-synthetic.raw.json)
- [Shadow receipt](results/shadow-synthetic.receipt.json)
- [Shadow自己整合検証](results/shadow-synthetic.verification.json)

full sensitivityの公開版は全JSON値を保持したminified版。元CLIのraw hashとは区別し、provenanceに元bytes/SHAを併記。
json.loads後にsort_keys=True,indent=2,ensure_ascii=True,allow_nan=Falseで再出力しLFを1つ付けると、元rawとバイト一致することを実測。
他のdemoコピーと試験生ログは無改変の実行バイト列。

新MANIFESTは保持47ファイルと新規payloadを列挙し、自身と新SHA256SUMSを除外。
新SHA256SUMSは新MANIFESTを含む新規ファイルを収録し、自身を除外。
この2本の自己bytes/SHAと保存後commit固定URLは最終提出で報告する。
