# Model1.1 v003 Claude監査対応・提出報告

Lane2／オフライン修正候補。v001／v002原本88ファイルは不変。

| Finding | 実装・証拠 | 未完了 |
|---|---|---|
| F1 必須 | 6市場重み、w=1完全市場コピー、共通market cohort、未来test非干渉 | 実データ性能・grid事前登録 |
| F3 必須 | frame／exhibitionの出典・3時点・定義、固定policy、fit/prior/predictの束縛 | real source mapping・外部真正性 |
| F4 必須 | five_appearance自動とhuman_input別入力、時点証拠、nullable評価、HOLD移行 | 正式Human BOX／BOXv1の再現なし |
| F2 待ち | 独立BOX候補・最低coverage・不確実性penaltyの設計だけ | 閾値審査・事前登録・実装未採用 |
| F5 待ち | selection N・cluster・grid budget・多重性・HOLDの設計だけ | 閾値審査・事前登録未採用 |

## 実行済み試験

Python3.12.14／3.14.3で各339件PASS（旧263＋新76、failure/error/skip各0）。
Linux、OpenSSLは3.12環境3.5.8、3.14環境3.5.5。socket接続を禁止した試験・デモだけを実行。
全デモ研究JSONは両runtimeでバイト一致（実行時刻を含むruntime/FILES除外）。
既存88原本のbytes/SHA一致、旧baseモデルとcourse-boundモデルのP_raw／P_model完全一致を検証。
held-out結果や後続featureを変更しても当該foldの選択・予測が不変。未来label availabilityはHOLD。

## F1 実測

固定default weights=[0, 0.25, 0.5, 0.75, 0.9, 1.0]。wは市場、1-wはモデル。
P_raw／P_model／P_marketは別欄。P_calibratedも分離。P_shrunkは対数線形統合。
w=1でexact市場copy=True、異なるモデル・温度で同一市場予測=True。
marketが無効・欠損のw=1はHOLD。モデル単独へ代替しない。
72名目設定、market完備選択コホートでは構造上最大61確率系統。w=1の12設定は1系統。

- fold1: w=0, model_weight=1, MODEL_ONLY; selection=8R/4日; adequacy=UNVERIFIED_NOT_PREREGISTERED。
- fold2: w=0.5, model_weight=0.5, MODEL_MARKET_POOL; selection=8R/4日; adequacy=UNVERIFIED_NOT_PREREGISTERED。
- fold3: w=0.9, model_weight=0.09999999999999998, MODEL_MARKET_POOL; selection=8R/4日; adequacy=UNVERIFIED_NOT_PREREGISTERED。
- fold4: w=1.0, model_weight=0.0, MARKET_ONLY; selection=8R/4日; adequacy=UNVERIFIED_NOT_PREREGISTERED。
- fold5: w=0.5, model_weight=0.5, MODEL_MARKET_POOL; selection=8R/4日; adequacy=UNVERIFIED_NOT_PREREGISTERED。

## 新schemaの1R例（架空2099）

race=20990117_GAMAGORI_1R、course policy=EXHIBITION_ONLY_V001、definition=EXHIBITION_ENTRY。
通常5点：1-4-2, 1-4-5, 1-5-4, 4-5-1, 5-1-4。
自動five_appearance=[1, 4, 5]、human_input=None。
構成差={'five_appearance_vs_mechanical': 'NO', 'human_input_vs_mechanical': None}。
人入力なしの方式をHumanと呼ばず、hit/ROIは未観測null。別ファイルの手動例は合成人assertionで、実在人物・正式規則の証拠ではない。
4段階とも120通り、合計1（絶対誤差1e-10）、重複艇・負値・NaN・Inf0。

## 既知合成40Rの記述値

| 段階 | joint log-loss |
|---|---:|
| P_market | 3.940114 |
| P_model | 4.409157 |
| P_raw | 4.405665 |
| P_shrunk | 4.141528 |

| 方式 | N | 的中 | 仮純収支 |
|---|---:|---:|---:|
| box_v11_research | 40 | 1 | -21548.42 |
| five | 40 | 9 | -5450.6 |
| five_appearance_research | 40 | 7 | -11164.32 |
| human_input_research | 0 | None | None |
| mechanical_research | 40 | 9 | -2466.709999999999 |

P_shrunkは市場baselineのlossを下回っていない。既知40Rは未使用の最終評価ではなく、改善・利益優位性を認定しない。
旧Human系統は意味が変わるため成績を一括比較しない。通常500円、各BOX600円を別会計に保持。

## 移行・差分

保存済みv001予測の移行review status=HOLD。旧manual originとcourse provenanceを後付けで認定しない。
移行reviewは新しい予測ではない。元raw・出力・成績は変更しない。
SOURCE_DIFFSは旧実装と新実装の正確な比較で、旧ファイルへ適用するpatchではない。
親v002とのGit差分は新規v003パス追加のみ。v001との累積比較には保持済みv002追加41ファイルも含む。

## OPEN・Claude再審査

- F1／F3／F4：合成修正候補として提出。Claude再監査は未実施。
- F3の実source／course mapping・証拠真正性、実人入力の独立証拠は未確認。
- F2／F5：例示閾値・候補・最小Nを正式採用しない。実データ前にHQ14／Claude審査・事前登録が必要。
- v003 real入力はpredict／walk-forwardともHOLD。F5未決のまま実データ検証PASSを出さない。
- v003 consumerへのRAW／Shadow／正式旧版比較の移行、正式Model1.0／BOXv1比較はOPEN。
- 本番Model1.0／BOXv1／A/B／LOCK／main／PR6／Render／Airtable／Automations／Production／POINTER無変更。
- PR作成・merge・deploy・通知・実舟券購入・本番GOなし。11/6certifi作業には接続しない。

```sh
cd development/model11
python -B run_checks.py
python -B -m model11.revision_v003.cli demo --output-dir /tmp/model11-v003-unique
```
