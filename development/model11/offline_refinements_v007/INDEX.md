# v007 OFFLINE候補 INDEX

固定親 `7aec4fdb6b9f311ee01bf3a2752410e683d83e42`。旧245ファイル無変更。
default DISABLED／実データ投入HOLD／Shadow未起動／閾値・採用未決。

- [全体報告・実装範囲・未確認事項](REPORT.md)
- [schedule状態・取消証拠・可変件数](SCHEDULE_STATES.md)
- [過去時点とsnapshot・締切前odds](POINT_IN_TIME.md)
- [private pilot要約とsd_day・欠損率](PILOT_SUMMARY.md)
- [単調時計診断: 任意設計のみ](MONOTONIC_DIAGNOSTIC_PROPOSED.md)
- [GOとOPEN・推奨順序の境界](GO_AND_OPEN.md)
- [開発内の独立レビュー](INDEPENDENT_REVIEW.md)
- [実測試験・環境・生ログSHA](results/TEST_RESULTS.json)
- [全file bytes/SHA](MANIFEST_V007.json)
- [追加file SHA](SHA256SUMS_V007.txt)
- [差分の追加file一覧](ADDED_FILES.txt)

## 再現

納品commitをcheckoutし`development/model11`で実行する。追加install不要。

```
python -B offline_refinements_v007/verify_artifacts.py
nice -n 10 python -B run_checks.py
python -B -m model11.offline_refinements.cli
nice -n 10 python -B offline_refinements_v007/reproduce_offline.py --output-dir /tmp/model11-v007-new-synthetic
python -B -m model11.offline_refinements.cli pit --enable-offline --input /tmp/model11-v007-new-synthetic/point-in-time.valid.SYNTHETIC.json
python -B -m model11.offline_refinements.cli schedule --enable-offline --target-date 2099-01-07 --schedule /tmp/model11-v007-new-synthetic/schedule.one-cancelled.SYNTHETIC.json --predictions /tmp/model11-v007-new-synthetic/predictions.reused.SYNTHETIC.json
python -B -m model11.offline_refinements.cli pilot --enable-offline --roster /tmp/model11-v007-new-synthetic/pilot-roster.SYNTHETIC.json --observations /tmp/model11-v007-new-synthetic/pilot-observations.SYNTHETIC.json --baseline-id SYNTHETIC_MARKET --baseline-version v001 --roster-complete
```

fixture再現の出力先は未存在の新規一時dirに限る。既存ファイルは上書きしない。
再現器以外の3コマンドは入力JSONを読み、結果をstdoutへ出すだけ。
`--enable-offline`はアプリ起動・実データ投入・本番GOではない。
実pilotを扱うのは後日の承認済みHQ14非公開環境だけで、共有対象はsummaryのみ。
Codex/公開GitHubに実roster・score・時点原本を渡さない。

全ての公開例は合成。申告承認やSHAの形式一致を公式原本・時刻・採用の真正性とみなさない。
manifestは自身と新SHA256SUMSを除外し、SHA256SUMSは自身以外の新規fileとmanifestを対象とする。
両者自身のbytes/SHAは納品時に別記。保存後GitHub readbackは別に確認する。
