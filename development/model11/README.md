# 蒲郡 Model 1.1 Research Candidate — Lane2

動作する完全オフライン研究ソフトウェア。**研究開発READYと本番適用GOは別**。
実レースの精度・利益改善はUNVERIFIED。Model 1.0、BOX Ver.1、正式A/BはFROZENのまま。

## 実装範囲と境界

- 学習する3つの着順別softmax head。`hierarchical`（着順別線形）と`contextual`（先着艇との特徴量相互作用）の独立比較。
- `P(first) * P(second|first) * P(third|first,second)`で6艇120通り。course priorは学習期間だけの頻度にBayesian型擬似カウントを加える。
- `P_raw`（能力）、`P_model`（市場なしcourse prior）、`P_market`（時点適格な完全オッズの逆数正規化）、`P_shrunk`（校正後モデルと市場の対数線形pool）を別欄で保持。
- `P_calibrated`は`P_model`の温度校正を明示した追加欄。P_raw/P_modelを校正結果で上書きしない。
- 通常5点、Human BOX研究候補、Mechanical BOX研究候補、BOX Ver.1.1研究候補を別々に生成・評価。通常500円、各BOX600円。全て仮想計算。
- 日単位のexpanding walk-forward。各foldで学習→過去selection→後続testを分離。α・市場重みw・温度・候補選択はselectionだけ。
- 条件付き／joint log-loss、Brier、top-label reliability、calibration error、方式別hit/回収率/ROI/最大DD、BET/SKIP、コース／人気帯、日クラスタ区間、固定旧版出力アダプタ。

`contextual`は統計的学習モデルであり高度なML全般の実装完了を意味しない。
生のST秒数・モーター率等を適当に混ぜない。入力の5特徴量は事前に定義・凍結した変換による[-1,1]、高いほど良い値。
現時点で実データ用の蒲郡固有変換・配点・重みを正式採用していない。

## 実行（ネット接続・追加パッケージ不要）

リポジトリのこのディレクトリを作業ディレクトリにする。Python標準ライブラリのみ。

```sh
cd development/model11
python -B run_checks.py
python -B -m model11.cli demo --output-dir /tmp/model11-demo-unique
```

出力先は未存在の新規ディレクトリ。既存ファイルの上書きは禁止する設計。
同じseed/config/runtimeでは予測・選択・評価が再現する。`runtime.json`の実行時刻と実行時間は再実行で変わる。
`FILES.json`は各生成ファイルのbytes/SHAを記録し、自分自身のhashは含めない。

デモ：36日×2R=72の**2099年の架空レース**。最初12日学習・4日selection・4日test、以後testを4日ずつ送る5foldで40Rを評価。
各後続foldでは過去testが歴史として学習／selectionへ入る。これは事前順序の逐次評価であり、単一の永続未使用holdoutではない。
正式な優劣判断には、事前登録後の別の未使用将来開催が必要。

凍結研究artifactを使った1R再現（実際に選ばれたpipeline configはsummaryのfold.selectedを参照）：

```sh
python -B -m model11.cli predict --race /tmp/model11-demo-unique/synthetic-example-input.json --model /tmp/model11-demo-unique/selected-model.json --config /tmp/model11-demo-unique/selected-pipeline-config.json --output /tmp/model11-prediction-unique.json
```

pipeline設定の形：`{"temperature":1.0,"market_weight":0.25,"selection":{}}`。
再現には実際の`selected-pipeline-config.json`を使い、既定値で代用しない。
`example-prediction.json`には結果を付けない。評価は`example-evaluation.json`、架空結果は別ファイルに分離。
予測hashは`prediction_sha256`欄を除いたforecast-only objectをcanonical_hashして検証できる。
凍結モデルの学習情報cutoffが予測時刻より前でなければSTOPする。未検証旧版モデルの再現は禁止。

HQ14の承認済み非公開環境向け入力口（Codexは実データ未使用）：

```sh
python -B -m model11.cli backtest --input /private/approved-input.json --config /private/preregistered-config.json --output-dir /private/new-research-output
```

private入力・生成結果を公開GitHubへ置かない。CLIはバックテスト全入力を自動複製しない。

## データ・安全条件

詳細は[INPUT_SCHEMA.md](INPUT_SCHEMA.md)、[MODELS.md](MODELS.md)、[BOX_RESEARCH.md](BOX_RESEARCH.md)、[EVALUATION.md](EVALUATION.md)。

各特徴量のacquired/available/revision時刻、ボート状態、odds、LOCK前スナップショットを検査。
利用可能時刻が遅い特徴量、ラベル混入、欠損展示、重複・時刻不正は予測失敗。
市場が欠損／古い／identity不一致ならP_market/P_shrunk/EVはnull、BETはSKIP。P_modelだけは独立に計算できる。
入力の自己申告時刻や自己整合hashだけでは、独立した締切前証拠の真正性は証明できない。

Human BOX研究候補の自動選定は正式Human BOXの人間判断を再現したものではない。
手動core/insertion入力にも時点検査が必要。Mechanicalは全3艇集合の6順列確率和最大、研究BOX1.1は期待払戻最大を独立に探索。
集合が偶然一致してもYESを作るために変更しない。構成差は集合比較だけ。

## 状態

| 項目 | 状態 |
|---|---|
| 設計・合成ソフトウェア動作 | 実行ログで判定 |
| 実データ品質・実回収率・旧版超え | UNVERIFIED / OPEN |
| 正式Model1.0/BOX Ver.1再現比較 | 検証済み原本または凍結出力待ちOPEN |
| Claude独立審査 | 未実施 |
| 正式昇格・本番適用 | GOなし・禁止 |

新規コードは`development/model11/`だけ。他SYS成果を統合せず、main基点の既存40ファイルを不変で保持。
破棄は研究用出力と隔離ブランチだけを後日明示承認で削除。本番復元操作は不要であり本実装に存在しない。
