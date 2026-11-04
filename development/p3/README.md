# P3研究・算術・適用状態のオフライン部品

状態：**DEV_READY（合成データによる試作検証のみ）**。FAST-02/03はOPENの入力一覧・設計のみ。
Claude審査、実データ検証、適用可能性、本番適用、CLOSEは未成立。certifiを最優先し、成果確認・審査はHQ14のcertifi終了確認後に行う。

## SYS-25 評価器

`evaluator.evaluate_pairs`は同一raceの既存予想とTHIRD_RESEARCH候補を、比較元AまたはBを固定して比較する。予測の生成、学習、探索、重み・配点の決定はしない。A/Bを混ぜた学習や置換は無い。

比較元sourceとcandidate_idを呼出側が明示し、各予想側source/target_date、候補ID、両race IDを照合する。
対応するrace_id profileはDATE_PREFIXED_GAMAGORI_V1（YYYYMMDD_GAMAGORI_1..12R）のみで、日付prefixとdayの一致が必須。
欠損/不一致/未知profileは除外理由を出し、推測で結合しない。他形式はHQ14の正確な入力仕様待ちでOPEN。
この構造照合自体は、sourceや時刻の現実の真正性を立証しない。

- 相異なる有効5点の三連単順序と供給済み結果を照合。既存predeadline verdictを入力として消費するだけでLOCK有効性を再定義しない。
- 重複race pairは最初の1件を採用せず全件除外。source不一致、late/unknown、結果不足等の理由と母数・除外数を別表示する。
- 払戻/返還は明示された円額。総return=(払戻+返還)/投資、net ROI=(払戻+返還-投資)/投資。金額未確認は0にせず、双方が全額既知のpaired行だけのNを表示。
- 全有効組合せの確率がある場合だけlog-loss/Brierを計算。通常6艇120通り、欠場時k*(k-1)*(k-2)の全domainを要求。5点だけから全確率を作らない。
- この試作は厳密に正の有限確率とsum≈1（数値検査許容1e-9）を要求する。0/NaN/Infinity/不正分布はproper-score UNVERIFIEDとして理由を返す。clipや勝手な再正規化はしない。この契約の正式採択はOPEN。
- Brierはmulticlassの全class平方誤差の**和**。calibrationは入力済みbinによるtop-label ECEで、bin未指定はUNVERIFIED。metric内同値tieはキー辞書順の決定的集計とし、予想5点選択ルールではない。
- 市場baselineは全domainの正のoddsと供給済みsnapshot verdictが必要。正規化逆oddsはproxyで真の勝率ではない。old/candidate/marketの3者が揃う同じ行でloss差を別表示する。
- 開催日を丸ごと再標本化する、race-weighted day-block percentile bootstrapを試作。seed/回数/confidence/min_days/事前登録hash参照/交換可能な日の仮定が必須。小cluster・未指定はUNVERIFIED。

CIが算出できてもEXPLORATORYであり改善PASSにはしない。日間依存、季節性、選択・除外バイアス、元のeligibilityや時刻の真正性は本コードで立証できない。入力の母集団/欠測管理もHQ14の検証が必要。
合成fixtureの95%やmin_days=30はテスト入力であり、正式な採択閾値ではない。

`PREREGISTRATION.json`はtraining / search-validation / untouched evaluationの時系列・hash・対象raceを別々に固定する空欄書式。
第三系統の締切前予想の保存/独立receipt仕様はHQ14とClaudeで固定する。createdTimeや自己hashだけを締切前証明としない。
このモジュールはそのデータを生成・保存しない。11/9〜14の正式A/B、Model1.0/BOXを変更せず、Model1.1正式導入のGOではない。

## SYS-26 算術器

`box_arithmetic.check_box`はphase PRE/LIVE/FINAL×periodごとに分離する。FLOWのみを足し、CUMULATIVE_SNAPSHOTを二重に加算しない。
返還は受取側へ加え、投資額を勝手に減額しない。FINALはconfirmedがある行だけを扱い、不明/重複ID/未知金額/期間網羅性不足はUNVERIFIED。
全期間を表す外部coverage参照が無ければ、既知subtotalは出してもcomplete totalや累計一致を確定しない。coverage参照の真正性は別審査。
claim累計との不一致はFalseとして記録するだけで、既存累計を書き換えない。PRE/LIVE/FINALを横断する総計は作らない。

## SYS-30 手動証拠台帳

`lifecycle`はDRAFT→DEV_READY→CLAUDE_REVIEWED→GO_APPROVED→APPLIED→READBACK_VERIFIED→NATURAL_RUN_VERIFIED→CLOSEを**明示1操作1段階**だけ記録するローカル試作品。状態から本番操作を呼ぶコードは無い。

| 状態 | 必須の別証拠 |
| --- | --- |
| DEV_READY | developerのTEST_REPORT |
| CLAUDE_REVIEWED | 独立ClaudeのREVIEW_PASS |
| GO_APPROVED | Andyの案件別/当該commitのAPPLY GO |
| APPLIED | operatorのAPPLICATION_RECEIPT |
| READBACK_VERIFIED | verifierのREADBACK_REPORT |
| NATURAL_RUN_VERIFIED | verifierのNATURAL_RUN_REPORT |
| CLOSE | 独立close reviewとAndy CLOSE_DECISIONの両方 |

全証拠にcase/commit/固有evidence ID/hash/issuer/観測時刻/source参照/別のverification参照が必要。
false・単なるverified=true・欠損・同じ自己参照・未登録issuer・自己審査・future時刻・段階飛越・履歴改変・証拠ID再利用を拒否する。
各eventのfrom/to、previous_event_id、時間順も検査する。同時刻を許すのは記録解像度の限界で、因果や実時刻を保証するものではない。
時刻入力profileはRFC3339型のT/秒/明示offset、fractionは最大6桁。unknown offset -00:00、naive、過剰桁を拒否し、丸めて既知UTCにしない。
証拠のobserved_atと台帳記入recorded_atは別物。適用証拠がGOのobserved_atより前なら拒否し、後からの記入時刻で過去の未承認操作を正当化しない。

**重要な信頼境界**：issuer registry、EXTERNALLY_VERIFIEDという入力文字列、外部verification参照の真正性をこのコードは検証できない。
形式の整った偽registry/偽外部証拠まで防げるとは主張しない。全ledgerにUNVERIFIED_BY_LOCAL_CODEを残す。
外部の独立審査とAndyの真のGOを代替せず、公開fixtureを実承認や本番適用証拠と認定しない。

## 実行と復元

Python標準ライブラリのみ。このディレクトリで `python -B -m unittest -v test_p3.py`。
記録用は `python -B run_tests.py --run r005`。既存run IDは上書き禁止。最終r004、旧r001/r002/r003はPRIOR-RUNS.jsonに元bytes/base64/SHAで保持。
合成fixtureは`make_fixtures.py`で生成可能。CLIサービス接続、モデル呼出し、通知、鍵生成、Drive/Airtable/本番DBへの書込は無い。

全ファイルは新規prefixのみ。旧原本はABSENT、既存アプリを変更していないため復元操作は不要。差戻しは未適用のまま保留し、mainや他案件のcommitをreset/revertしない。
SYS-01/02等の別案件コードはコピー/統合していない。次の審査入力：privateな収録能力/分布/時刻・母数、事前登録、coverage、独立issuerと証拠の検証契約、FAST残差表。
