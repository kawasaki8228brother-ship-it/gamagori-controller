# 入力仕様と判定規約（PROPOSED）

1 record = 1監査対象run。source/taskの混在・予想内容は入力しない。

| field | 意味 |
| --- | --- |
| scheduled_for | 独立に確認された予定枠。実開始の代用不可 |
| started_at | 実行が開始した観測時刻 |
| observed_at | 対象を観測した時刻。現在時刻を自動生成しない |
| completed_at | 実行完了を観測した時刻 |
| saved_at | 保存を観測した/保存原本に記録された時刻。予定・完了とは別 |
| deadline | 既存規則で取得された締切。ここでは有効判定しない |

各値は`YYYY-MM-DDTHH:MM:SS[.ffffff]Z`または`±HH:MM`を含む文字列。
小数精度は最大6桁。追加桁を切捨てない。offsetの分は0–59、時間は0–23、-00:00は未知offsetとしてUNVERIFIED扱い。
timezone無しはNAIVE_TIME、存在しない日付等はMALFORMED。値を修復して使わない。

各項目の状態はMISSING/NULL/EMPTY/INVALID_TYPE/NAIVE_TIME/UNKNOWN_OFFSET/MALFORMED/CLOCK_FAILED/CONFLICT_CLOCK_FAILURE_WITH_VALUE/VALID。
`clock_failures`は取得失敗が判明したfield名の配列。値が同時に与えられたらCONFLICTとして使わない。
0、false、空文字、nullを日時として相互変換しない。保存・観測の未確認は0秒差ではない。

許容幅は任意：`tolerance_policy={"status":"PROPOSED","early_seconds":0,"late_seconds":30}`。
幅は非負の有限数。比較は与えられた数値のDecimal表現で行い、microsecond単位の境界をfloatで丸めない。
outside_proposed_toleranceは参考比較であり合否・採択・LOCK有効性ではない。未提供はnull。

`run_id`は自己申告値として受領するだけ。内部証拠が無ければUNVERIFIED。
`scheduler_evidence`の候補書式は`evidence_class=INTERNAL_SCHEDULER_RECORD`、internal_run_id、scheduled_for、started_at。
一致する場合も入力記録の整合に限り、実schedulerがそのIDを発行したという暗号学的/実運用の証明ではない。
`execution_origin_claim`はSCHEDULED_CONTEXT/MANUAL_AUDIT/UNKNOWNというclaimだけ。claimを証明済みoriginへ変換しない。

OPEN：各fieldの取得経路/時計源/信頼性/精度、予定枠と内部runの結合原本、日跨ぎの対象日規則、許容幅の正式採択。
これらを未確認のまま本番有効性へ適用しない。実原本はHQ14が非公開で保持し、この試作へ公開転記しない。
