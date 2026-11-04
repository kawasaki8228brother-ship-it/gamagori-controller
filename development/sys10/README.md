# SYS-10 AC1 自動保存率測定 — オフライン試作

状態：DEV_READY（合成データ開発検証のみ）。独立審査未実施、本番適用GOなし。
certifiを最優先し、この成果の確認・Claude審査はHQ14のcertifi終了確認後。

分母は**照合済み公式予定レース × A/Bの初回LOCK機会**。同raceのREVISIONやCは分母へ足さない。
`official_schedule`が完全・検証済みでなければ分母はnullでUNVERIFIED。非開催0機会を100%としない。
原LOCKの有効性・締切・Freezeは実装せず、既存判定の証拠を入力として受け取る。独自の締切猶予を足さない。

## 入力

`input-template.json`は全てSYNTHETIC。`fixtures.json`に25の合成例。
`intervention-template.json`にrace/source/JST時刻/action/内容/証拠参照の記録様式を示す。初回への影響は未判定UNVERIFIEDを初期値とし、欠損から無介入を作らない。

- official_schedule：公式予定race_id、meet_id、target_date、検証status/evidence_ref、complete。
- lock_records：race/source、INITIAL_LOCK区分、saved、既存VALID/INVALID/UNVERIFIED、既存predeadline判定の証拠。
- lock_record_coverage / intervention_coverage：完全性証拠と、分母に一致するrace_ids・sources=[A,B]。
- interventions：race_id、source、timezone付きat（JSTへ変換可能）、action、evidence_ref、initial_lock_effect。
  actionはREPLAY/TRANSPORT/SUPPLEMENT/MANUAL_WRITE/OTHER。初回LOCKへの影響不明はUNVERIFIED。
- pair_attestations：race×source別のNO_INTERVENTIONという独立証拠、coverage_complete、検証status/evidence_ref。

**介入ログが空であることは、介入なしの証明ではない。** 網羅性とpair別独立証拠が無ければ自動保存を確定しない。
`NO_INTERVENTION`は外部で検証した証拠への主張であり、このコードが真正性を立証するものではない。
時刻はRFC3339のZまたは明示offset（秒以下0〜6桁）に限定。未知offsetの-00:00、不正offset、余分な精度を正規化せず未確認にする。
後続・初回非関連の手動操作も明示された影響判定を使い、時刻だけで原因を推測しない。
NO_INTERVENTION証拠と実介入記録が矛盾すればOPENに残し、保存率の自動合格へ進まない。

## 出力と95%比較

AUTO_CONFIRMED / INTERVENED / NO_VALID_INITIAL_SAVE / UNVERIFIEDを別計数する。
一意性が不明な複数INITIAL_LOCKは時刻順に勝手に選ばない。kind不明を非initial扱いせずUNVERIFIEDにする。検索失敗と完全検索0件も区別する。
下限=AUTO_CONFIRMED/分母、上限=(AUTO_CONFIRMED+UNVERIFIED)/分母。網羅性未確認ならexact=null。
95%比較は値・区間の位置を示す表であり、baselineでPASS/FAILを出さない。
合計に加えA/B別の分母・率・未知件数を出す。合計95%で片側90%が隠れる場合も、そのまま両方を表示する。
11/9〜14の日付を含むデータは入力phaseに関係なくBASELINE_ONLY、合否なし。

正式合否はSYS-01/02の適用証拠、適用後の最初の2節という独立証拠、対象2節・両節完了、全測定の網羅性が揃った場合だけ。
最初の2節/両節完了の各証拠はcohort_meet_idsと両SYSのadoption_evidence_refsへ束縛し、別cohortへの証拠流用を拒否する。
95%の適用単位（EACH_SOURCEかCOMBINED）は`formal_cohort.threshold_rule`の審査済み証拠を要求し、未決ならUNVERIFIED。こちらで正式規約を採用しない。
適用時刻・対象2節を推測せず、同日の採用→機会の順序も日付だけでは推定しない。
正式比較のPASSは**入力契約上の測定結果**であり、Claude審査PASS、アンディGO、本番適用、CLOSEへ自動昇格しない。

## ローカル実行

Python標準ライブラリのみ。ネットワーク・DB・writerの実装はない。

```sh
python -B -m unittest -v test_ac1.py
python -B ac1.py input-template.json
python -B record_tests.py
```

CLIはHQ14の非公開環境で実データを入力できる。既定出力は集計のみで、個別race/sourceは出さない。
`--details`の個別出力は非公開保全用。実原本・個別結果を公開repoへ戻さず、要約件数だけを提出する。
`tests.raw.log` / `results.json`は実ローカルテストの記録、`MEASUREMENT-EXAMPLES.tsv`は合成入力だけの95%比較表。

## OPEN・復元

公式予定の範囲/中止時のLOCK機会、既存有効性契約、介入影響判定と完全性証拠の取得能力、適用後2節の確定はHQ14検証待ち。
実データ検証は未実施。コード内のVERIFIEDは外部入力の主張であり、証拠の真正性は独立監査が必要。
本番writer、既存Events、A/B本文、Model1.0/BOX/LOCK/締切/Freeze/正本/POINTERを変更していない。
新規開発prefixのみなので本番の復元は不要。不採用なら適用せず隔離ブランチを証拠として保持する。mainをreset/rollbackしない。
