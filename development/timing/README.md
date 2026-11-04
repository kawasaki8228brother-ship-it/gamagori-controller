# SYS-27 / SYS-09 時刻・scheduler照合のオフライン試作

状態：DEV_READY（合成入力による開発検証のみ）。Claude審査PASS、適用GO、本番動作確認、CLOSEはいずれも未成立。
certifiを最優先し、この成果の確認・独立審査はHQ14がcertifi終了を確認した後とする。
11/9–14のModel1.0/BOX Ver.1 Freezeや既存LOCK有効性、締切規則は変更しない。

## 実装と実行

`timing_audit.py` は標準ライブラリだけのローカル検査器。予定時刻・開始・観測・完了・保存・締切の6項目を独立に扱う。
日付付きtimezone-aware ISO8601をUTC/JSTへ変換し、整数microsecondsの差を計算する。
予定時刻を開始時刻として代用せず、欠損値を隣の時刻・現在時刻・scheduler記録から補完しない。

```sh
python -B -m unittest -v test_timing.py
python -B timing_audit.py private-input.json
python -B timing_audit.py - < private-input.json
```

CLIはローカルJSON objectまたはobject配列だけを読む。上限1MiB、不正UTF-8/JSON/重複キー/非有限JSONを拒否する。
結果はstdoutだけ。サービス接続、書込み、通知、scheduler起動、タスク設定変更は無い。
本番データをこのrepoへ追加しない。HQ14は非公開環境で実データを入力し、非秘匿の要約だけを戻す。

## 判定の分離

- 開始差は `started_at - scheduled_for`。EARLY/LATE/AT_SCHEDULEを表示するが、実行の合否やLOCK判定ではない。
- 保存とdeadlineの前後関係はBEFORE/AT/AFTERを観測値として示すだけ。新しい締切許容・有効判定を作らない。
- completed_atがstarted_atより前なら、時系列矛盾候補として記録する。別時計・別run・原本誤記等の根因は断定しない。
- saved_atがobserved_at/completed_atより前でも、一律異常としない。以前の保存を後から観測する場合があるため、符号付き差だけを残す。
- 許容幅は明示された`PROPOSED`方針でのみ参考比較する。未提供/不正はnull、既定閾値は作らず、採択済みともしない。

`scheduler_evidence`のrun IDと予定/開始時刻が一致しても、分類はCONSISTENT_PROVIDED_RECORD。
入力者の自己申告を内部run証拠に昇格せず、原本/取得元の真正性はNOT_PROVEN_OFFLINE、origin_provenは常にfalse。
実内部IDが未確認ならUNVERIFIEDのまま。origin claimがSCHEDULED_CONTEXTでも予定実行を立証したとはしない。

## テスト・OPEN

29合成fixtureと9件の契約テスト、合計38 testsを実行。全time status、早発/遅延/JST日跨ぎ、時計失敗、ID未確認/矛盾、microsecond境界、CLI拒否を含む。
環境・実測結果は`results.json`、生ログは`unittest.log`。合成時刻は実行ログの再現や原本の証拠ではない。
Python 3.14.3/正式CI/実schedulerの互換・収録契約は未検証。SYS-19や他案件のコードは取り込んでいない。
時刻真正性・同一worker/runの証明・schedulerの内部証拠取得能力・許容幅の採択はOPEN。
別案件の変更、A/Bのreaderや予想決定部分、Model/BOX/LOCK/Freezeには触れない。

## 復元と次の審査

新規ディレクトリだけの試作で本番適用は無い。元mainの既存bytesは変更しておらず、本番の復元操作は不要。
不採用時はこの隔離成果を適用しない。main/certifiをreset/rollbackしたり既存ブランチを削除しない。
HQ14/Claudeには入力原本の取得方式・各時刻の意味・run identity証拠・閾値の業務根拠を審査してもらう。
