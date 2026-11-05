# Shadow Launch-Ready Candidate v005 / OFFLINE

このINDEXは新規追加資料。旧INDEX・旧成果物を上書きしない。
実行・起動承認は含まれず、設定はDISABLED。

- [納品報告・実装範囲・OPEN](REPORT.md)
- [起動前policyと承認束](POLICY_GATES.md)
- [RAW_V001入力変換契約](SOURCE_MAPPING.md)
- [独立保存と復旧境界](STORAGE_CONTRACT.md)
- [条件付き操作手順](OPERATIONS_RUNBOOK.md)
- [GO前チェックリスト・入力欄](LAUNCH_CHECKLIST.md)
- [無効の設定原本](CONFIG_TEMPLATE.json)
- [開発内の独立レビュー](INDEPENDENT_REVIEW.md)
- [実行結果とログSHA](results/TEST_RESULTS.json)
- [全ファイルbytes/SHA](MANIFEST_V005.json)
- [追加ファイルSHA](SHA256SUMS_V005.txt)
- [追加差分の対象一覧](ADDED_FILES.txt)
- [N1の単独成果物](../revision_v004/REPORT.md)

再現は納品commitをcheckoutし、`development/model11`から行う。

```
python -B shadow_launch_v005/verify_artifacts.py
python -B run_checks.py
python -B -m model11.shadow_launch.cli preflight
python -B shadow_launch_v005/run_demo_offline.py --output-dir /tmp/model11-new-synthetic-demo
```

最後のコマンドは**存在しない新規一時ディレクトリ**を指定する。合成データだけを生成し、ローカル専用storeへ書く。
同名の出力が存在すれば上書きせず失敗する。新規temp名に変えることは合成再現時だけに限定し、実Shadowの重複回避に使わない。
default preflightはDISABLEDでsourceもstoreも使わない。実source・秘密情報を渡さない。
Python 3.12／3.14の各環境で同じ手順を実行でき、追加ライブラリは不要。

manifestは旧151ファイルと新規追加ファイルを対象にするが、自己参照を避けるためmanifest自身と新SHA256SUMSを除外する。
SHA256SUMSは新規追加ファイルを対象としmanifestを含め、自身だけを除外する。納品時に両ファイル自身のbytes/SHAも報告する。
ローカル検証器は読取だけであり、GitHubや外部保存の真正性を認証しない。保存後のcommit固定readbackは別途報告する。
