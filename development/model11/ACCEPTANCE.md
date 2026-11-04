# 追加受入条件と検証対応

本表のPASSは合成ソフトウェア検査だけ。実性能・本番適用を意味しない。

| 条件 | 実装 | 検査と残余 |
|---|---|---|
| ①未来情報分離 | validation、engine、model artifact学習cutoff、walk-forward | 各特徴量・状態のacquired/available/revision、締切、ラベル再帰混入、遅延ラベル、未来学習artifactを拒否。時刻の独立真正性はUNVERIFIED |
| ②120通り整合 | model conditional factorization、engine.check_distribution | count/domain/sum1(絶対誤差1e-10)/重複0/負数NaNInf0。異常を修復して成功としない。市場欠損はnullで区別 |
| ③BOX分離 | selection.build_boxes | research Human core2/insertion/five頻度、独立Mechanical、独立EV BOXv1.1、集合差だけYES/NO。正式V1再現はOPEN |
| ④投資額別評価 | metrics | 通常500円、BOX各600円。方式内重複reject、方式間overlap別記、返還、別hit/return/ROI/DD、actionとSKIP counterfactual分離 |
| ⑤比較条件 | walkforward、metrics | whole-day train/selection/test、学習・選択のlabel cutoff、joint/conditionalLL、Brier、校正、市場、daycluster区間。実旧版比較・優位性はOPEN |
| ⑥最初1R | CLI demo、results、FIRST_REPORT.md | 昇順通常5点、3BOX、core/insertion/frequency、構成差、確率、BET/SKIP、予測EVと観測仮収支、時点・欠損・未確認を別記 |

## 独立レビューで検出し修正した統合上の点

- E1：optional market gateでidentity不一致となったoddsを、数値変換が誤って使用しないよう統一。独立変換APIにもidentity検査。
- E2：学習最大利用可能時刻・学習予測時刻をモデルartifactへ保存。単独predictも未来または不明cutoffでSTOP。
- E3：選択済みpipeline温度・市場重みを独立原本として出力。既定値の代用による再現差を防止。
- E4：forecast-only原本と結果付き評価を分離。予測hashの対象を再計算可能にした。
- E5：oddsと手動BOX入力にも独立した利用可能時刻を必須化。取得済みでもLOCK後まで利用不可の入力を排除する。

この開発内レビューはClaudeの独立審査の代わりではない。

## 状態遷移

設計READY → 合成動作DEV_READY → 実データ検証PASS → Claude審査PASS → アンディ正式昇格GOは独立。
現在は前二段のオフライン試験を提出する。残りの段階は未実施／未承認。
