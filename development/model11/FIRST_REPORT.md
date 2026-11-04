# Model 1.1 Research Candidate 第1報

Lane2・合成データだけの動作確認。正式Model1.0／BOX Ver.1／A/BはFROZEN。

## 実装と観測

- 3着順別headを実際に学習するhierarchicalとcontextual、120通り、course prior、市場変換、校正、対数線形pool。
- 通常5点と独立BOX研究3方式、BET/SKIP、Walk-forward、確率評価・別帳簿・返還・最大DDを実装。
- Python3.12.14（OpenSSL3.5.8）とPython3.14.3（OpenSSL3.5.5）、Linuxで各148テストPASS。
- 追加pip installなし、全テスト中はsocket接続を禁止。全データは2099年の架空fixture。
- 36日72R、5fold、後続評価40R。学習/selection/testは日ごと分離。全体デモJSONは両runtimeでバイト一致。

最終前の統合試験に2失敗：JSON整数keyの読込後型差と、試験追加時のassert配置誤り。修正後に上記全件PASS。初回失敗ログはパスだけREDACTEDとして別保全し、元ログSHAを併記。

## 1Rの実出力（架空・初回評価R）

race_id=20990117_GAMAGORI_1R。結果は別ファイルに保存。

通常5点（昇順）：1-4-2, 1-4-5, 1-5-4, 4-5-1, 5-1-4

Human BOX研究候補：[1, 4, 5]、core=[5, 1]、insertion=4。
通常5点登場回数：{'1': 5, '2': 1, '3': 0, '4': 5, '5': 4, '6': 0}。
これは合成手動core/insertion入力の研究出力。正式Human判断の再現ではない。
Mechanical研究候補：[1, 4, 5]。BOX1.1研究候補：[1, 2, 4]。
構成差=NO（Human研究候補とMechanicalの艇集合のみ比較）。

| 方式 | 予測coverage | 予測EV純損益 | 仮想BET/SKIP | 結果付き仮収支 |
|---|---:|---:|---|---:|
| five | 0.372997 | 1340.16円 | BET | -500.00円 |
| human_research | 0.429096 | 77.95円 | BET | -600.00円 |
| mechanical_research | 0.429096 | 77.95円 | BET | -600.00円 |
| box_v11_research | 0.040697 | 3221.03円 | BET | -600.00円 |

架空の結果=[2, 3, 5]。初回Rは全方式不的中。予測EVと結果付き仮収支は別物。

| 段階 | count | sum（実測表示） | 重複艇 | 無効確率 |
|---|---:|---:|---:|---:|
| P_raw | 120 | 1.0 | 0 | 0 |
| P_model | 120 | 1.0 | 0 | 0 |
| P_market | 120 | 0.9999999999999999 | 0 | 0 |
| P_shrunk | 120 | 1.0 | 0 | 0 |

sumの機械検査許容絶対誤差=1e-10。P_calibratedは別欄。α=0等による値の一致は許すが段階を混同しない。
初回fold選択={'alpha': 0.5, 'candidate': 'hierarchical', 'market_weight': 0.0, 'selection_mean_log_loss': 3.702547683974685, 'temperature': 0.8}。w=0のため当該P_shrunkはP_calibratedと数値一致。

LOCK研究時点=2099-01-17T12:55:00+09:00、締切=2099-01-17T13:00:00+09:00、odds取得=2099-01-17T12:54:30+09:00。
全艇の数値特徴量とcourse/FL/scratchに個別acquired/available/revisionを保持。
この1Rの欠損・警告=[]。
時刻の独立真正性、正式Model1.0/BOXv1、実利益はUNVERIFIED／OPEN。

## 40Rの計算結果（合成ソフトウェア試験のみ）

| 段階 | joint log-loss | Brier |
|---|---:|---:|
| P_market | 3.940114 | 0.970002 |
| P_model | 4.409157 | 0.987007 |
| P_raw | 4.405665 | 0.986688 |
| P_shrunk | 4.173063 | 0.981177 |

| 方式 | 的中 | 投資額 | 仮純収支 | 回収率 | 最大DD |
|---|---:|---:|---:|---:|---:|
| box_v11_research | 0/40 | 24000円 | -24000.00円 | 0.00% | 24000.00円 |
| five | 8/40 | 20000円 | 13092.16円 | 165.46% | 7874.72円 |
| human_research | 6/40 | 24000円 | -11835.77円 | 50.68% | 13518.74円 |
| mechanical_research | 7/40 | 24000円 | -4802.58円 | 79.99% | 7985.54円 |

市場baselineの方がjoint log-lossが小さく、研究BOX1.1は全40R不的中。通常5点の合成プラス収支を優位性の証拠にしない。
各表は方式別の独立仮想投資。SKIPを適用したaction帳簿は別JSON。方式間の重複買い目を合算して利益を作らない。

## アーキテクチャと再現

validation -> models -> four probability stages -> selection/boxes -> frozen forecast -> separate labels -> metrics。
walkforwardは日単位train/selection/testと情報cutoffを監査し、候補別にも同じtestを別評価する。

```sh
cd development/model11
python -B run_checks.py
python -B -m model11.cli demo --output-dir /tmp/model11-demo-unique
```

予測原本の再現にはREADME記載のselected-model.jsonとselected-pipeline-config.json両方を使う。
結果全件・source/fold audit・予測例・bytes/SHAはINDEXとMANIFESTを参照。

## OPENと判定

- 設計／合成動作：DEV_READY、Claude独立審査へ提出可能。正式適用可能という判定ではない。
- 実データ検証、正式Model1.0/BOXv1比較、外部時点証拠、実校正・性能・利益優位性：UNVERIFIED／OPEN。
- 正式昇格GO：なし。PR作成・merge・deploy・本番操作なし。
- 複雑ML、完全Bayesian階層、コース別ST分布・時系列機力は研究OPEN。
- 実入力・非劣性・必要サンプル数・seal条件はRESEARCH_PLANの一覧をHQ14/Claudeが非公開環境で審査。
- 破棄は隔離成果物のみ。本番へ接続・変更する機能は存在しない。
