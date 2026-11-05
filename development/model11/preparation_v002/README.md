# Model 1.1追加開発：実データ検証準備 v002

Lane2／オフライン専用。基点 `71ddd13dd5869aaf892a504ea0553c60e8b8abe2`。
元の47ファイルと既存候補はバイト不変。新規コード・試験・資料だけを追加する。
**実装の動作確認、実データ検証、Claude審査、正式GOは別判定。**

## 追加した5項目

| 依頼 | 実装・文書 | 限界 |
|---|---|---|
| private実入力契約 | `preparation.adapter`、INPUT_CONTRACT.md | RAW_V001、全時点、単位・方向・motor identity、train限定normalizer。実mapping・証拠真正性はOPEN |
| 正式旧版との比較口 | `preparation.legacy`、LEGACY_INTERFACE.md | 凍結済み原本bytesを照合するだけ。正式ロジック再現なし。A/Bは別入力・別帳簿 |
| EV／BOX診断 | `preparation.sensitivity`、EV_AUDIT.md | 元の買い目・設定を固定した感度分析。別IDのPROPOSED overlay。最適化・本番変更なし |
| 未使用評価の案 | `preparation.planning`、PREREGISTRATION_PROPOSED.md | primary、日cluster、標本設計、候補多重性、seal・審査欄。事前登録は未完了 |
| 第三研究Shadow原本 | `preparation.shadow`、SHADOW_CONTRACT.md | JSON原本＋独立receipt生成・照合だけ。writer、通信、通知、舟券購入なし |

## 再現（標準ライブラリのみ）

このREADMEの一段上、`development/model11`を作業ディレクトリにする。

```sh
python -B run_checks.py
python -B -m model11.preparation.cli demo --output-dir /tmp/model11-prep-v002-unique
```

demoは2099年の架空36日72Rから、基点と同じwalk-forward評価40Rを再生成する。
基点full-summary SHA `09a2c12c68583cf02e111276380df007027d0d0750a866052365b1e4e366d587`と照合し、不一致ならSTOP。
RAW adapterの動作例は、train限定正規化で**別のsmokeモデル重み**を学習する。元モデルの重みに新normalizerを後付けしない。
旧版比較fixtureは独立して発明したA/Bダミー出力。正式Model1.0／BOXv1の成績として解釈しない。
全出力は未存在ディレクトリへ保存。失敗した部分出力は保全し、上書きや自動再試行をしない。

## HQ14非公開環境向けのローカル入力口

以下は将来の実行例であり、実データ投入の承認ではない。HQ14／Claudeによる契約・split・mapping・証拠審査が先。
Codexへ実データ・原本・秘密値を送らない。公開GitHubへprivate入力や生成結果を置かない。

```sh
python -B -m model11.preparation.cli fit-normalizer --training /private/train-only.json --specs /private/reviewed-feature-specs.json --fit-cutoff APPROVED_AWARE_TIMESTAMP --output /private/new-normalizer.json
python -B -m model11.preparation.cli normalize --raw /private/predeadline-snapshot.json --normalizer /private/frozen-normalizer.json --output /private/new-normalized.json
python -B -m model11.preparation.cli compare --research /private/research-evaluated.json --envelopes /private/frozen-AB-envelopes.json --profiles /private/separate-source-profiles.json --output /private/new-comparison.json
python -B -m model11.preparation.cli diagnose --forecasts /private/forecast-only.json --races /private/snapshots.json --outcomes /private/separate-final-outcomes.json --output /private/new-diagnostics.json
python -B -m model11.preparation.cli shadow --prediction /private/frozen-forecast.json --race /private/snapshot.json --generated-at APPROVED_AWARE_TIMESTAMP --reproduction /private/reproduction.json --output-dir /private/new-shadow-artifact
```

旧版比較だけが評価用のA/B予想を読む。RAW feature adapterはA/B予想入力を拒否し、学習口を出さない。
将来のstacking研究は別案件・別承認が必要。本追加機能にその実装はない。
`fit-normalizer`が使うのは明示したtrainだけ。selection／holdoutをtrainファイルへ混ぜた自己申告の偽装はコードだけでは検出できないため、splitとraw hashの独立審査が必要。
normalizerのtraining使用は凍結ID＋原本hashに限定し、歴史的予測として出力しない。prediction使用はfit cutoffより後だけ。
全RAW foldを自動fitする新しい学習エンジンは今回未実装。各foldのtrain限定fit・適用は契約に従い別途記録する。

## 診断の解釈

既知40Rの0/40やROIを使って閾値を探索・選択しない。固定27シナリオは事後の構造診断であり、この40Rへの事前登録ではない。
市場への混合、確率平坦化、下方オッズ変動で元の買い目のEVを再計算する。因果的な原因はUNVERIFIED。
厳格overlayは市場100%・odds75%のstressを含み、合成価格設計では全SKIPになり得る。これを利益改善の証拠にしない。
未来の比較条件は実データ前に審査・sealする。11/9～14の結果で評価条件を後付け変更しない。
11/21～24は最速の研究Shadow候補日程。実行・schedule・正式運用・購入のGOは存在しない。

## STOP／HOLD

| 条件 | 処置 |
|---|---|
| 基点bytes・hash不一致、旧候補の結果不一致 | STOP。既存候補を修正して合わせない |
| 後日revision、未知単位、motor不一致、未来normalizer、ラベル／A/B特徴量混入 | adapter STOP／HOLD |
| 旧版原本・receipt・source・時刻・内容不整合 | 比較HOLD。欠損はOPEN、件数を明示 |
| オッズ不足や無効確率、risk入力不明 | EV／risk UNVERIFIED。0・BETへ補完しない |
| primaryの市場pair不足、標本不足、未使用評価未seal | 統計判定HOLD／UNVERIFIED |
| Shadowの途中切れ、raw bytes／hash不一致、締切後生成、減艇 | HOLD。送信や自動修復なし |
| 実データ・本番操作が必要 | 現作業範囲で実行せずHQ14／Claude審査と個別GOへ |

自己hash・review hashの形が一致しても、独立真正性・正式承認を証明しない。`production_go`は常にfalse。

破棄は追加した研究ファイルとローカル出力だけを後日の指示で行う。元候補は親commitにそのまま存在し、本番復旧操作は不要。
