# B3 過去4節棚卸し：オフライン試作

**DEV_READY（合成検証のみ）**。本番適用可能・Claude審査済み・本番動作確認済み・CLOSEではない。
certifi最優先。成果の確認・独立審査はcertifi終了をHQ14が確認した後。
実レース原本は受領しない。`synthetic_fixture.json`は4つの架空節・4架空レース×A/Bで、実績ではない。

```sh
python -B -m unittest -v test_b3.py
python -B b3_inventory.py synthetic_fixture.json
python -B run_tests.py
```

最後のコマンドは既存結果を上書きしない。標準ライブラリのみで、ネット・DB・writer・Automations・Render・Airtable・Driveには接続しない。
HQ14は同じ入力仕様のファイルを非公開環境だけでCLIまたは`inventory(data)`へ渡す。実入力/出力を公開repoへ返さない。

## 分母とvalid N

設定した正確に4節の公式予定レース×A/Bを対象に、race_id/sourceでLOCKとSummaryを独立joinする。
公式RESULTだけを同じraceのA/Bへ共通参照する。Bの予想をAの判定に利用せず、その逆もしない。
1件のLOCK、1件のFINAL RESULT、1件のsource別Summary、固有record ID、対応する参照ID、
上流の既存LOCK VALID/deadline PASS/hash/readback/公式結果確認、5点の相異なる有効な順序3艇、Summaryのhit一致を要求。
さらに対象scheduleと各readの完全性をHQ14が明示する。未確認/取得失敗は0件と同一視しない。
重複は最新1件を選ばず除外し、欠損・未確認・競合を理由別に報告する。

timestampはtimezone付きRFC3339、microsecond最大6桁、JSTへ変換する。`-00:00`はoffset不明として拒否。
観測/保存とdeadlineの関係は分析上の整合検査であり、元のexisting_LOCK_validityや既存deadline規則は変更しない。
上流PASSと時刻が矛盾した場合は分析から保留除外するだけで、元LOCKをINVALIDへ書き換えない。
小さな時刻解像度差の扱いはHQ14審査OPEN。新たな猶予や精度補正を加えない。

## 金額とNの分離

hit解析のvalid_Nとmonetary_Nは別。払戻・返還・Summary金額が未確認でも、独立に確定したhit Nを失わない。
金額が不明な行を0円へ置換しない。金額集計は完全に照合できたmonetary_Nだけで、除外数を必ず表示する。
入力の公式払戻は**100円あたり円**。仮投資は5点各100円、合計500円。
返還は公式に検証した順序組合せの一覧と各sourceの5点を照合する。source共通のticket indexを使わない。
gross回収率=(払戻+返還)/投資、net ROI=(払戻+返還-投資)/投資。率はratioであり百分率表示は別変換。
Summaryの金額と不一致ならmonetary_Nを保留し、勝手に修復しない。空の金額cohortは合計/率をnullにする。
節別・JST月別・累計をA/B別に計算し、異なるscopeの金額を混ぜない。

取消・非確定レースはvalid Nへ入れず、的中falseにも置換しない。
現試作の金額scopeは有効FINALレースだけ。取消レースを含む全舟券cash ledger/全返還総額ではない。
取消全返還の運用仕様・既存Summaryとの対応はOPENとして別cohortへ拡張する審査が必要。

## 不的中の分類

5点だけから1/2/3着評価の失敗原因を推測しない。証拠なしはUNSPECIFIED。
締切前に固定し、確認済みの候補集合・条件別2着/3着集合の完全性がある場合だけ、
FIRST/SECOND/THIRD_CANDIDATE_COVERAGE_MISS、またはFIVE_TICKET_SELECTION_MISSという集計ラベルを付ける。
これは候補集合のcoverageラベルで、配点/重み/Modelの因果欠陥の証明ではない。

## OPEN・復元

実4節データ、有効N、live schemaとの適合、read coverageやhash/readback flagsの真正性は未検証。
HQ14へ必要な入力は`INPUT_SPEC.md`と`OPEN.json`。返すのは非秘匿の件数/検証要約のみ。
SYS-01/02等は統合していない。LOCK/Model1.0/BOX/Freeze/既存イベントに変更は無い。
本番未適用なので復元不要。却下時はこの隔離成果を適用せず保持/ローカル破棄し、main/正式枝をresetしない。
