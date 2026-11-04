# B3_INPUT_V1_PROPOSED — HQ14 private input

これは新たな本番schemaではない。offline adapterの契約案。実データはHQ14の非公開環境のみで使用する。

- `schema`: `B3_INPUT_V1_PROPOSED`
- `classification`: 呼出側が主張する出典区分。真正性の証明ではない。
- `meets`: 正確に4件。meet_id、start_date/end_date（YYYY-MM-DD）。重複ID/期間重複を拒否。
- `races`: race_id=`YYYYMMDD_GAMAGORI_1R`〜`12R`、meet_id、date、timezone付きdeadline、scheduled=true。
  race ID/date/節範囲/JST deadline日を照合。対象外のrecordは無言で混ぜず入力拒否。
- `read_coverage`: schedule/resultsは`VERIFIED_COMPLETE`等の文字列、locks/summariesはA/B別の文字列。
  未提供/READ_FAILED/INCOMPLETEはUNVERIFIED。完全なpagination・抽出範囲の確認はHQ14の責任。
- `locks`: record_id/race_id/source、tickets（異なる順序3艇を5点）、observed_at/saved_at、
  existing_LOCK_validity、existing_deadline_verdict、payload_hash_verified、saved_readback_verified。
  前2 verdictは既存系統の結果をそのまま供給し、この部品が再判定した値を使わない。
- `results`: record_id/race_id、status、official_result_verified、order、payout_yen_per_100、
  refunded_combinations（返還対象の順序3艇一覧）、refund_evidence_verified。未知金額/listはnull。
  空listは「確認済み返還なし」を意味する。返還組合せの生成・公式情報取得はこのモジュールの対象外。
- `summaries`: record_id/race_id/source、lock_record_id/result_record_id、verification、hit、
  stake_yen/payout_yen/refund_yen。boolを金額0/1として受け入れない。

全record IDはこのinput内で一意。衝突は関連行を保留。source A/B以外は拒否。
日時は秒とoffsetを必須とし、小数秒1〜6桁だけ許す。naive時刻/`-00:00`/勝手な精度切捨ては認めない。
8つのsource opportunityを持つ最小合成例が`synthetic_fixture.json`。

`selection_audit`は任意。verification=VERIFIED/predeadline_verified=true/coverage_complete=trueに加え、
first_candidates、second_candidates_by_first（例key `"1"`）、third_candidates_by_pair（例key `"1-2"`）を供給する。
証拠や必要な分岐集合が欠ける場合、候補段階を推測せずUNSPECIFIEDにする。

本部品は入力flags、保存元、取得時刻、DB同一性を独立立証しない。CLI出力も非公開保全する。
