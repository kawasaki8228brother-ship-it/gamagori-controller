# Model 1.1研究開発・提出INDEX

新規隔離branch：`dev/model11-research-20261105-v001`
基点main：`8172aec010894a52f36f48b7091476d26494e4ee`
基点tree：`9143c19742b672c93f67228669166a8f86c2f37a`

Lane2 / SYNTHETIC_ONLY / DEV_READY（合成動作）/ 実性能UNVERIFIED / 本番GO=false。

- [第1報・1R出力・計算結果](FIRST_REPORT.md)
- [再現手順とアーキテクチャ](README.md)
- [追加6条件の対応表](ACCEPTANCE.md)
- [入力schemaとゲート](INPUT_SCHEMA.md)
- [モデル方式](MODELS.md)
- [BOX分離仕様](BOX_RESEARCH.md)
- [評価算定仕様](EVALUATION.md)
- [仮説・パラメータ・必要実入力・OPEN](RESEARCH_PLAN.md)
- [変更境界](CHANGE_REPORT.md)
- [全payloadファイル名・bytes・SHA-256・Git blob](MANIFEST.json)
- [SHA256SUMS](SHA256SUMS.txt)
- [Python3.12最終生ログ](results/tests-python312.log)
- [Python3.14.3最終生ログ](results/tests-python314.log)
- [実行環境・検証結果](results/verification.json)
- [初回失敗と秘匿化区分](results/initial-attempts.json)
- [予測原本：結果なし・120通り4段階](results/demo/example-prediction.json)
- [1R方式別仮収支](results/demo/example-evaluation.json)
- [合成1R入力](results/demo/synthetic-example-input.json)
- [合成1R結果：別保存](results/demo/synthetic-example-outcome.json)
- [選択モデル](results/demo/selected-model.json)
- [選択pipeline設定](results/demo/selected-pipeline-config.json)
- [40R集計](results/demo/aggregate-evaluation.json)
- [独立候補別集計](results/demo/candidate-evaluations.json)
- [fold境界・情報cutoff・選択scores・予測hash](results/demo/fold-audit.json)
- [raw/derived区分・元summary SHA・両runtime一致](results/demo/provenance.json)

生ログは実行済み結果。初回2失敗は修正前として残し、最終ケース全件は各runtimeでPASS。
集計JSONはCLI full-summaryの厳密なsubobjectを抽出したDERIVEDであり、元raw全体と同一hashとは主張しない。
元full-summary（1,239,489 bytes）SHAはprovenanceに保全。CLI再現出力と照合できる。

MANIFEST.jsonは自身とSHA256SUMS.txtを除く全payloadを収録。
SHA256SUMS.txtはMANIFEST.jsonを含む全他ファイルを収録し、自身のhashは含めない。
この2本自身のbytes/SHAおよびcommit固定URLは保存後の提出receiptに記載する。
