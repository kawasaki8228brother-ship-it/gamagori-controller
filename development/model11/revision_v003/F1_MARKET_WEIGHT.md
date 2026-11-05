# F1 市場統合候補の拡張・v003オフライン検証

状態は **PROPOSED / 合成データ診断専用 / 実データ適用HOLD**。
親commit `00d67eea0598ba83671eb400175749df294a6fad` の既存88ファイル、
旧モデル・旧workflow・旧成果物は変更しない。新しいpoolingとwalk-forwardを
`model11/revision_v003/` に追加する。

## 市場重みと正確なendpoint

`pool_market(model_dist, market_dist, weight)` のwは**市場重み**、
1-wは**モデル重み**。

`P_shrunk(t) proportional to P_calibrated(t)^(1-w) * P_market(t)^w`

配布版のdefault候補は順序も含めて次の6件に固定する。

`[0, 0.25, 0.5, 0.75, 0.9, 1.0]`

- w=0: 校正済みモデル分布の独立した**exact copy**。
- w=1: 市場分布の独立した**exact copy**。モデルや温度に依存しない。
- 0<w<1: log空間で計算し、積の分布を正規化する。

endpointにも両入力の完全なactive-ticket domain、確率範囲、有限性、質量1を
要求する。無効入力を未使用だからと許容しない。endpointではsoftmax、
追加正規化、epsilonを使わず、値をそのまま返す。出力dictは入力と共有しない。
中間wで入力確率0があればその積のsupportは0。共通の正supportがない場合HOLD。
負値・NaN・inf・重複艇・domain欠落・不正な総和を修復して続行しない。

P_raw、コースprior適用後で市場を含まないP_model、別欄P_calibrated、
P_market、P_shrunkを区別する。w=1でもraw/modelは診断用に残るが、
予測確率へのモデル寄与は0である。市場欠損時のw=1をモデル分布で代用しない。
rootのv003 predictorはその場合HOLD。w<1で市場欠損の場合もmarket/shrunkはnull、
model-onlyの診断とSKIPだけであり、市場統合成功とは扱わない。

## 選択方法と同値class

`walk_forward_v003(dataset, config=None)` は学習・選択・将来testを開催日単位で
分離する。defaultはtrain12日、selection4日、test4日のexpanding workflow。
既存実装と同じ条件付き学習を、F3の `CourseBoundModel` で固定policyに結合する。
default policyは `EXHIBITION_ONLY_V001`。trainと予測でpolicy SHAを一致させる。

alpha、温度、w、モデル方式の候補は各foldのtestに先立つselectionでのみ選ぶ。
scoreは**selectionレース等重みの平均joint log-loss**。同点は設定されたgridの
先頭を選ぶ決定的な規則。testの結果でtie-break・候補追加・再選択しない。
F5の別案である日等重みの一次評価や最小selection Nを、このF1修正で採用しない。

w=1を純粋な市場候補として公平に比較するため、selectionでは全gridに共通する
有効marketのあるレースだけを使用する。欠損分母・除外件数・paired IDを記録する。
marketがないレースでw=1をモデルへ読み替えない。完全pairedレースが0ならSTOP。
testにおける予測前のmarket欠損も独立したゲートで処理する。

defaultの2モデル×2 alpha×3温度×6wは**72 grid member**。
ただしw=1の12件は同じ市場分布であり、一つの確率同値class。
従ってこの点だけをまとめた構造上の上限は61。さらにw=0等に別の同値が
生じる可能性があるため、61個の独立仮説や61個の実際に異なる予測とは主張しない。
各selection分布のSHAから観測上の異なるvector数も別欄で記録する。

w=1が選ばれた場合は `prediction_type=MARKET_ONLY`、`model_weight=0`、
`underlying_candidate_role=DIAGNOSTIC_ONLY_NOT_A_LEARNED_MODEL_VICTORY` を明示する。
保存された候補名はraw/model診断と再現のための基礎モデルであり、モデルが
市場を上回った、最良の学習方式が判明した、という意味ではない。
各モデル別評価も記述比較に留まり、多重比較の合格証拠にはしない。

## 少標本・未採用のF5

selectionの開催日数、全レース数、共通market paired数、欠損数、grid数を出力する。
算術的に選択を実行できても適切な標本数や探索量であるとは認定しない。

- `selection_adequacy.status=UNVERIFIED_NOT_PREREGISTERED`
- `reason=F5_DESIGN_PENDING_NOT_ADOPTED`
- 解釈は `SYNTHETIC_DIAGNOSTIC_UNDERPOWERED_NO_FORMAL_PASS`

selection4日等は既存診断workflowの設定であり、審査済み必要Nではない。
F5文書の候補値・family・最小日数・逐次停止規則をコードで正式採用しない。
実際の実データ入力は全て `HOLD:REAL_INPUT_REQUIRES_APPROVED_PREREGISTRATION`。
SYNTHETIC_ONLY、各レース/結果の合成flag、2099年のfixtureに限定する。
自己申告flagやSHAは外部真正性の証明にはならない。

小さいfixtureや単体試験用の明示custom gridは合成診断でのみ使用できる。
設定はdeep copyし、独自の `frozen_config_sha256` を記録する。
配布defaultと異なるgridを承認済み研究計画と呼ばない。
実データの計画では、grid変更を**データを見る前**にHQ14/Claudeが審査・固定する。
test結果を見て市場寄りwやモデル候補を追加し、同じtestで改善を主張しない。

## 時点境界・再現・STOP

学習labelはselection開始前、selection labelはtest開始前に利用可能であることを
厳密に確認する。境界時刻と同時のlabelも進行させない。
予測のhashを確定してから、結果を評価専用フィールドにdeep copyする。
入力race/outcome/configを変更しない。先のtestを後続fold trainingに利用するため、
これは単一の未使用最終holdoutではない。別途sealした将来評価はOPEN。

STOP/HOLD条件: 実データ入力、分類・合成証拠不足、course policy/時刻の不整合、
重複ID、結果未対応、label遅延、必要期間不足、selection market全欠損、
不正確率、無限selection log-loss、未知設定、予測時点のw=1 market欠損。
対象別理由を記録し、未知値を0やPASSへ補完しない。

通常5点500円、five-appearance研究BOX600円、手入力研究BOX600円、
Mechanical研究BOX600円、BOX v1.1研究600円はv003 evaluatorで分離する。
formal Human BOXや旧BOX Ver.1の再現を主張せず、旧原本を上書きしない。
120通り正規化、5点数、各BOX6通り、締切・未来情報・保存境界は回帰検査対象。

再現用の合成テスト:

```
python -B -m unittest discover -s tests -p test_revision_v003_walkforward.py -v
```

独立endpoint、wの向き、両入力検査、純市場の選択、同値class、時系列分割、
test label/未来特徴変更に対する過去予測不変、selection欠損coverage、
小標本UNVERIFIED、実データHOLD、120/5/BOXを検査する。
ソフトウェア試験PASSは性能改善・利益・実データ優位性・独立審査PASSではない。
`superiority=UNVERIFIED`、`production_go=false`、`real_data_execution_go=false` を維持する。
