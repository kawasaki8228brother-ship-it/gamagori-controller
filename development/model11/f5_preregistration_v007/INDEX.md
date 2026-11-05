# F5事前登録 文書v007 / 独立審査用候補

基点: `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`（v006）。
新規ブランチ: `evidence/model11-f5-preregistration-20261105-v007`。
F5文書namespaceは`F5_PREREGISTRATION_V007`。先行するoffline refinements v007
`148c156f472c874075a0b25d4f0b6b7e9fafdcfe`とは別成果物で、統合・上書きしない。

アンディの2026-11-05 20:36 JST決定をHQ14転送の**受領情報**として記録した。
方針の正式決定と、原本照合、統計評価、Shadow起動・実データ・本番GOを分離する。
原本SHA/承認receiptは未取得のnull。今回生成したfile SHAを承認原本SHAと呼ばない。

| 区分 | 決定の範囲 |
|---|---|
| M0 DECIDED | 単一凍結champion vs同一締切前snapshot P_market、joint120 log-loss、開催日paired等重み、片側α=.025/power=.8/m=1 |
| M2 DECIDED | 最初の第3研究Shadow稼働日をpilotとする方針。候補11/21〜24以降、実開始と起動GOは未確定 |
| M1 FUTURE_DESIGN_DECIDED | 将来の確証はA限定。hierarchical/alpha=.5/T=1/市場重み6候補をselectionで選び単一championを凍結 |
| OPEN | 指定8項目は全てnull。24/60日等を採用せず、事前登録の最終sealは未実施 |

市場重み6候補をm=6として検定しない。w=1純市場選択はMODEL優位としない。
pilotは正式holdoutに再利用せず、pilotで利益・性能改善・昇格を主張しない。
F2は未採用、G1〜G6と11/9〜14のFreezeは維持する。未提供のgate定義を補わない。

## 提出資料

- [決定台帳](DECISION_LEDGER.json)
- [DECIDED / PROPOSED / OPEN対応表](DECIDED_PROPOSED_OPEN.md)
- [M0・M2・M1事前登録文書](PREREGISTRATION_M0_M2_M1.md)
- [pilot/holdout重複禁止・seal設計](PILOT_HOLDOUT_SEPARATION.md)
- [未割当・無効のpartition参照欄](DATA_PARTITIONS.OPEN.json)
- [原本SHA・承認receipt・独立照合欄](SOURCE_RECEIPT_REFERENCE.json)
- [Claude再審査依頼資料](CLAUDE_REVIEW_REQUEST.md)
- [開発内の独立レビュー](INDEPENDENT_REVIEW.md)
- [Chrome第三者意見の反映・既存対策・追加提案](THIRD_PARTY_REVIEW_DISPOSITION.md)
- [許可項目方式のエラー要約設計: PROPOSED](SAFE_DIAGNOSTIC_EXPORT.PROPOSED.json)
- [実行済み静的試験・環境・生ログSHA](results/TEST_RESULTS.json)
- [基点245 fileのbytes/SHA一覧](PARENT_BYTE_BASELINE.json)
- [全file一覧とbytes/SHA](MANIFEST_F5_V007.json)
- [追加file SHA](SHA256SUMS_F5_V007.txt)
- [追加差分一覧](ADDED_FILES.txt)

## 静的再現

納品commitをcheckoutし`development/model11`から実行する。install不要。

```
nice -n 10 python -B f5_preregistration_v007/run_static_checks.py
python -B f5_preregistration_v007/static_audit.py
python -B f5_preregistration_v007/verify_artifacts.py
```

文書の整合性、架空2099年のpartition重複/時系列、基点245 fileのbyte保全だけを調べる。
予想/evaluation engine、実データ、p値・検出力計算、モデル選定、host/Shadowは実行しない。
`DOCUMENT_CONSISTENT`は文書間整合であり、原本真正性・統計PASS・起動GOではない。
Chrome追加提案も設計だけで、時計・fallback・外れ値処理・ログexport実装は変更しない。

原本receipt独立照合、8 OPENの決定、実データ/時点証拠・host/gate確認、Claude/HQ14審査と
案件別GOは後続工程。certifi/SYS-01/02を優先し、既存branch、main、PR #6、Productionを変更しない。
元に戻す場合は親commitを参照する。新規文書候補の破棄だけで、旧原本や本番のreset/rollbackは不要。

新manifestは自身と新SHA256SUMSを除外し、SHA256SUMSは自身以外の新fileとmanifestを対象とする。
manifest自身とSHA256SUMS自身のbytes/SHAは納品時に別記し、保存後はcommit固定readbackで照合する。
