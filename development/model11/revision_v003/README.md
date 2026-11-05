# Model 1.1 Claude監査対応候補 v003

Lane2／完全オフライン。親commit `00d67eea0598ba83671eb400175749df294a6fad`。
v001の47＋v002の41ファイルは原本のまま保持。新規パスだけに追加する。
F1／F3／F4は修正候補を実装、F2／F5は**設計・事前登録待ち**。
ClaudeのPASS WITH NOTEはユーザー提供のv001／v002監査結果であり、v003の再審査PASSではない。

## 起動と再現

作業ディレクトリは`development/model11`。標準ライブラリだけで動作する。

```sh
python -B run_checks.py
python -B -m model11.revision_v003.cli demo --output-dir /tmp/model11-v003-unique
```

元のrun_checks.pyは不変で、新規test_revision_v003も自動検出する。
出力先は未存在ディレクトリ。途中失敗は部分出力を保全しSTOP、上書きや自動再試行をしない。
demoは2099年の架空36日72R、5foldで40Rを後続評価。旧版成績は書き換えない。
展示進入fixtureは旧simulatorが結果抽選より前に生成したcourse値を保持し、inventedな展示source／時点を付ける。
F3の単体反例には明示したshifted-mapも使う。どちらも実レースの展示や確定進入の再現ではない。

単独再現では選択済みmodel／pipelineを両方指定する。

```sh
python -B -m model11.revision_v003.cli predict --race /tmp/model11-v003-unique/synthetic-race-v003.json --model /tmp/model11-v003-unique/selected-model-v003.json --config /tmp/model11-v003-unique/selected-pipeline-v003.json --output /tmp/model11-v003-unique-prediction.json
```

v003のpredictとwalk-forwardはsynthetic=true／SYNTHETIC_ONLY／2099年だけを許容。
実データを読む前のClaude再審査とF5事前登録が未完了のため、実入力はHOLD。
このガードは現実のデータをsyntheticと偽装してよいという許可ではない。実データはCodex／公開GitHubへ持ち込まない。

## F1：市場重み

固定default：`[0, 0.25, 0.5, 0.75, 0.9, 1.0]`。
`w`は市場重み、`1-w`はモデル重み。
`P_shrunk ∝ P_calibrated^(1-w) * P_market^w`。
`P_calibrated`は市場なし`P_model`を明示的に温度校正した別欄。P_raw／P_model／P_marketは上書きしない。
w=1では検査済みP_marketの完全コピー。モデル・α・温度に関係なく一致し、有効marketがなければHOLD。
純市場を選んでも、内部候補モデルが優秀だったという判定にしない。
selectionでは全設定共通のmarket完備コホートだけを比較し、欠損／除外件数を明示する。
synthetic用の小さい別gridは別config SHAで記録。実データ後の候補追加は禁止。

## F3：コース定義

CourseBoundModelはtrain／prior／predict／保存復元を固定policy SHAへ束縛する。
FRAME_ONLY、EXHIBITION_ONLY、事前固定EXHIBITION_ELSE_FRAMEを別IDにする。
枠番は艇番号と一致、展示進入は展示の定義として識別。混在は事前固定規則のnull時fallbackだけ。
未知source／結果確定進入／未来時刻／値・state時刻不一致はHOLD。
source IDの形と自己hashだけで実取得の真正性を証明したとは扱わない。

## F4：表示・schema

新規schemaは`MODEL11_FORECAST_V003`、boxesのactive slotは以下。

| slot | 意味 |
|---|---|
| five_appearance_research | 通常5点の登場回数による自動研究候補。Humanではない |
| human_input_research | 別引数の人由来選択assertion＋締切前証拠。未入力はnull |
| mechanical_research | 独立した確率和による研究候補 |
| box_v11_research | 既存研究EV選択kernel。F2案をまだ統合しない |

人由来assertionも外部真正性はUNVERIFIEDで、正式Human BOX／BOX Ver.1の再現を意味しない。
手動証拠はrace/dateと束縛し、観測→取得→利用可能→証拠保存、改訂→証拠保存の時間順序を確認する。
構成差は`five_appearance_vs_mechanical`と`human_input_vs_mechanical`を分け、集合一致だけを示す。
通常500円、各BOX600円は別会計。人由来入力なしのhit／ROIを0として埋めない。

## 移行と互換性

```sh
python -B -m model11.revision_v003.cli migrate --old-forecast results/demo/example-prediction.json --output /tmp/model11-old-migration-review.json
```

移行は常にHOLDのreview preview。元の予測・原本・hashは変更しない。
旧モデルを後付けでcourse-boundにしたり、旧manualを本物の人由来入力に認定したりしない。
v002のRAW／旧版比較／感度分析／Shadowは元schemaのまま保存される。
v003 recordを旧consumerへそのまま投入しない。v003 evaluatorは内部の算術kernelだけを再利用し、外部名を修正する。
実データRAW source→course_inputs mapping、v003 Shadow reader／旧版比較の正式なconsumer移行は未審査OPEN。

## F2／F5とSTOP

F2の最低coverage・不確実性penalty、F5の最小selection N／cluster／候補budgetは設計資料の例示で、採用していない。
defaultは72名目設定、market完備コホートで構造上最大61系統。w=1の12設定は同じ市場で、12回の独立勝利ではない。
8selection race／4日という合成例を統計的十分とは判定しない。adequacyはUNVERIFIED。
training／selectionラベル利用可能cutoffを守り、test結果は予測を凍結してから評価用に付ける。
未知・未来入力、原本不一致、invalid確率、人入力の時間矛盾、政策不一致、実入力はHOLD／STOP。
本番Model1.0／BOXv1／A/B／LOCK／main／PR6／Render／Production／POINTERに変更なし。
PR・merge・deploy・通知・舟券購入・実運用scheduleは実装しない。production_goは常にfalse。

破棄は追加v003ファイルと隔離出力だけが対象。本番rollbackは不要であり実施しない。
