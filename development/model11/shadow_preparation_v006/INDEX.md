# v006 OFFLINE residual preparation INDEX

親 `f3c3a3eb17073bd0a127bb943f4eda21e407cf2d`。追加資料だけで、既存v005は不変。
実データ投入HOLD／Shadow未起動／全閾値案未採用。

- [報告と範囲・OPEN・Claude審査対象](REPORT.md)
- [P1 field mapping・時刻・欠損](CAPTURE_INPUT_PREPARATION.md)
- [無効の公式mapping入力欄](templates/field_mapping.OPEN.json)
- [P2 F5最終案・未採用](F5_PREREGISTRATION_PROPOSED.md)
- [P3 独立実行環境・容量・時計・復旧](INDEPENDENT_RUNTIME_DESIGN.md)
- [実環境の未確定入力欄](RUNTIME_INPUTS.OPEN.json)
- [P4 公式予定12Rと保存原本の照合契約](SCHEDULE_COVERAGE.md)
- [P5 N1変更履歴と旧原本](N1_LINEAGE.md)
- [系譜の全46件・固定URL・SHA](results/N1_LINEAGE.json)
- [試験結果・runtime・生ログSHA](results/TEST_RESULTS.json)
- [合成12R読取証拠の復号・原本照合](ENCODED_FIXTURES.md)
- [全ファイルbytes/SHA](MANIFEST_V006.json)
- [追加ファイルSHA](SHA256SUMS_V006.txt)
- [追加対象一覧・差分範囲](ADDED_FILES.txt)

## オフライン再現

納品commitをcheckoutし`development/model11`から実行する。追加installは不要。

```
python -B shadow_preparation_v006/verify_artifacts.py
python -B run_checks.py
python -B -m model11.shadow_preparation.cli
python -B -m model11.shadow_preparation.cli f5 --enable-offline
python -B shadow_preparation_v006/reproduce_coverage_fixture.py --output-dir /tmp/model11-v006-new-synthetic
python -B -m model11.shadow_preparation.cli coverage --enable-offline --target-date 2099-01-07 --schedule /tmp/model11-v006-new-synthetic/SYNTHETIC_ONLY.schedule.json --predictions /tmp/model11-v006-new-synthetic/SYNTHETIC_ONLY.prediction-evidence.json
```

fixture再現の出力先は未存在の新規一時dirにする。再現器だけが既存v005合成demo経由で新しい専用storeへ書く。
その後のCLI/checkerはJSON入力を読みstdoutへ出すだけで、store初期化・DB open・source fetch・補完・保存は行わない。
checkerは期待store所有IDを`--expected-storage-id`でpinできる。省略時の原本origin同一性は外部確認が必要。
defaultのCLIはDISABLED。`--enable-offline`も起動GOではない。
captureの試験はさらに`--synthetic-validation`を必要とし、private入力はHOLDを保つ。

fixtureの予定・承認metadataは全て架空2099年であり、実公式原本・実承認を装わない。
完全一致はLOCALのbytes/time観測だけ。未確認値の補完、過去予測の書換え、実source接続や起動を行わない。
stdoutに出した実入力を公開GitHubへ保存しない。公開例・試験は合成だけを使う。
