# raceindex parser残件：隔離候補と確認範囲

対象基点は`8172aec010894a52f36f48b7091476d26494e4ee`。
今回の変更は`parsers.py`のraceindex領域と専用合成試験のみ。
Model、LOCK、state、実タスク、依存関係、Render、本番に変更はない。
実際の2026-11-05 HTML、当日の原本bytes/SHA、取得ログは未提供。
サイトへ接続せず、実ページでの修正効果・正常取得をPASSにしていない。

## 旧コードから確認した問題

旧版はtr全体の最初のHH:MMを採用していたため、別列の更新時刻等をdeadlineと
誤認し得る。race labelと時刻が一つずつあるだけではclosing時刻の根拠にならない。
同じrace番号が重複した場合は後続行を無視していた。
さらに本文自体から末尾行が消えた場合、label集合とparsed集合の一致だけでは
完全な予定race集合との欠落を検出できなかった。
これらはコード上の性質であり、11/5にその原因が起きたという実測ではない。

## 新しい保守的な構造契約

```
parse_race_index(html, date_str, source_url, acquired_at,
                 *, expected_race_numbers=None)
```

レース列と「締切…」列を一意に示すtable headerを要求し、その締切列からだけ
時刻を取得する。現候補が認識するheader文字列は限定的なホワイトリスト。
実HTMLのrowspan/colspan等の構造を推測して補完しない。
merged cell、複数header、複数tableへの分散、変更された列数は不明構造として停止する。

race cellは正規の1R〜12R。一行に複数race label、行全体に複数の時刻、
不正/欠落時刻、締切列以外の時刻を採用しない。
同一race番号の完全一致重複も、時刻の異なる競合重複も全てエラー。
race labelがparsed row外、別table、header内にある場合も保守的に拒否する。
JavaScript/style内の文字列は画面のrace rowとみなさない。

callerがexpected_race_numbersを渡した場合、parsed集合との完全一致を要求する。
set/frozenset/range/list等を受けるが、重複、空、bool、float、範囲外を許容しない。
予定集合を本文の検出labelから自動作成して欠落を隠すことはしない。

**12Rを既定の保守的候補とすることは、当日の実日程を検証したことではない。**
fetcher候補が1〜12を要求する場合、短い集合へ緩和するには独立して審査された
日程原本・当日対象の証拠を必要とする。実際の当日開催や短縮編成は未確認。
Noneは既存APIと3行の旧合成fixture互換のためだけに残す。
Noneで3行を読めても、実ページの完全性や「全3R開催」を認定しない。

## エラーと非開催日の境界

部分/曖昧構造は`ParserError("raceindex: partial parse <FIXED_CODE>")`。
本文やURLの値をerror messageへ埋め込まない。
race rowがないときは旧カテゴリを維持する。

`raceindex: no race rows with race number + deadline found`

空本文やHTTP 200は非開催日の証明ではない。新parserは空listを正常結果として返さず、
「no rows」を成功・全件処理済み・raceなしの確定へ変換しない。
status文字列からのOPEN/CLOSED/CANCELLED/UNKNOWN割当は旧版と同じ優先順を維持する。
このparser変更をLOCK有効性、締切、処理状態変更の承認に使わない。

date_strのYYYYMMDDと暦日としての妥当性は検査するが、**HTML内の当日日付や
正規sourceとの同一性は検証していない**。source_url/acquired_atはcaller metadataの
保持であり、parserがその取得時刻・取得元を認証したという意味ではない。
要求日付・公式URL・日程・HTML原本の外部照合は別のfetcher/監査ゲートが必要。

## 実行した隔離試験

追加pytest関数は12本、parameterized caseは38件。既存parser6件も維持し、合計
**44 passed**。正常12R、旧3R互換、末尾/中間欠落、deadline欠落/不正、複数HH:MM、
同一/競合重複、複数R行、番号不正、tr外label、header/列変更、期待集合不正、
空HTTP本文、暦日不正を合成HTMLで検査した。

実行コマンド:

```
/workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -p no:cacheprovider tests/test_parsers.py tests/test_health_raceindex_parser.py -q
```

実測環境:

- Python 3.14.3（既存隔離venvを使用、installなし）
- Linux 6.18.57 x86_64 / glibc 2.41
- OpenSSL 3.5.5 27 Jan 2026
- 最終結果：44 passed in 0.16s

Pythonのbytecode書込みとpytest cacheを無効化し、requirementsやvenvを変更していない。
このOpenSSL値は隔離環境の値で、本番TLS適合の測定結果ではない。

変更前後のbyte照合:

- raceindex領域より前のprefix SHAは双方
  `9afa2d2cb6aefa00df68158732435f55c4506c7208f3a2fd3768e2b419d98b75`。
- `_find_section_table`から末尾まで（beforeinfo/oddsを含む）のSHAは双方
  `77bb91d7b69440a5ada0a6b68d54f3476476d98cbbfbc55fbf8a0dc2d22b2009`。

## OPEN / STOP

実HTMLが未提供なので新しい狭い契約が実際の公式構造と一致するかはUNVERIFIED。
適法なnavigationやmerged headerをこの候補が拒否する可能性も、実原本なしでは
解決しない。既知formatへ独断でfallbackしてPASSにしない。
実日程・HTML当日日付・source取得証拠・完全expected集合が不明ならSTOP/HOLD。
次の審査では当日原本、取得時刻/source receipt、正しいclosing header/列、
当日race一覧の独立証拠を非公開側で照合する必要がある。
合成parser試験PASSはProduction適用GO・実取得正常・Health回復とは別判定。
