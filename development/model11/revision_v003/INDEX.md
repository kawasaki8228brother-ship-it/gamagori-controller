# Model1.1 v003 監査対応候補 INDEX

parent：`00d67eea0598ba83671eb400175749df294a6fad`
new branch：`dev/model11-audit-fixes-20261105-v003`
Lane2 / F1-F3-F4合成修正候補 / F2-F5設計待ち / 実データHOLD / 本番GO=false。

- [提出報告・試験・OPEN](REPORT.md)
- [再現・schema・STOP・互換性](README.md)
- [監査指示への対応表](AUDIT_RESPONSE.md)
- [F1市場重み](F1_MARKET_WEIGHT.md)
- [F3コース契約](F3_COURSE_CONTRACT.md)
- [F4 schema・移行](F4_SCHEMA_MIGRATION.md)
- [F2 BOX設計案のみ](F2_BOX_DESIGN_PROPOSED.md)
- [F5 selection事前登録案のみ](F5_SELECTION_PREREG_PROPOSED.md)
- [開発内独立レビュー](REVIEW_FINDINGS.md)
- [旧v001 INDEX：不変](../INDEX.md)
- [旧v002 INDEX：不変](../preparation_v002/INDEX.md)
- [全ファイルbytes/SHA/Git blob](MANIFEST_V003.json)
- [新規SHA256SUMS](SHA256SUMS_V003.txt)
- [F1旧新source比較](SOURCE_DIFFS/F1_walkforward.comparison.diff)
- [F4旧新source比較](SOURCE_DIFFS/F4_portfolios.comparison.diff)

source比較は旧ファイルを変更する適用patchではない。実際の親commit差分は新規v003追加だけ。

実行証拠：

- [Python3.12.14全339件生ログ](results/tests-python312.raw.log)
- [Python3.14.3全339件生ログ](results/tests-python314.raw.log)
- [3.12デモ生ログ](results/demo-python312.raw.log)
- [3.14.3デモ生ログ](results/demo-python314.raw.log)
- [試験結果・環境・旧88不変](results/verification.json)
- [raw/derived区分・元SHA・runtime比較](results/artifact-provenance.json)
- [全walk-forward JSON：lossless minified](results/walk-forward-summary.full.min.json)
- [fold・grid・選択N監査](results/fold-selection-audit.json)
- [評価集計](results/evaluation-summary.json)
- [v003予測原本](results/prediction-v003.json)
- [course-bound選択モデル](results/selected-model-v003.json)
- [選択pipeline](results/selected-pipeline-v003.json)
- [合成race：F3 evidence付き](results/synthetic-race-v003.json)
- [結果：別保存](results/synthetic-outcome-separate.json)
- [F1純市場endpoint証拠](results/F1-market-only-evidence.json)
- [F4合成manual input：実人の証拠ではない](results/F4-manual-input-SYNTHETIC-ONLY.json)
- [F4手動・自動の別出力](results/F4-separate-manual-and-automatic.json)
- [保存済み旧予測のHOLD移行review](results/F4-old-artifact-migration.json)
- [旧88不変確認](results/preservation.json)

full walk-forwardの公開版は全JSON値を保持したminified版。元rawのbytes/SHAをprovenanceに併記。
json.loads後sort_keys=True,indent=2,ensure_ascii=True,allow_nan=Falseで再出力しLFを1つ付けると元rawバイト列と一致することを実測。
他のraw copiesと試験生ログは無改変。

MANIFESTは保持88ファイルと追加payloadを列挙し、自身と新SHA256SUMSを除く。
新SHA256SUMSは新MANIFESTを含む追加ファイルを列挙し、自身を除く。
この2本自身のbytes/SHA・commit固定URLとreadbackは最終提出で報告。
