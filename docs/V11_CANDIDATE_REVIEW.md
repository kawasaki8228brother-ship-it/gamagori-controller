# Ver.1.1 監査・パーサー候補（2026-09-19）

## 状態

**DRAFT / NOT WIRED INTO PRODUCTION / NOT DEPLOYED.**
基準コミットは `057d024dd46797a77e8893ab30e4f4cbd58655bf`。既存PR #1の端末永続化修正とは別の候補であり、main・Render・Model1.0を変更しない。

## 実装したもの

- `v11_candidate.odds.parse_trifecta`: 明示的な買い目セルと、1着ヘッダー6列・2着rowspan・3着セルを持つ行列を解析する。数値の適当な組合せ推定をしない。標準モードは120通り完全性を要求する。重複、部分取得、異常値、表の曖昧性を拒否する。
- `v11_candidate.contracts`: source事前限定クエリ＋返却前payload検証、締切スナップショット、strict時刻順序、monotonic区間計測、定性Delta、取得body hashの記録を提供する。
- `tests/test_v11_candidate.py`: 48ケースをローカル実行し全PASS。Python3.13.5 / bs4 4.14.3 / pytest9.0.2。

## 証拠の限界

HTML fixtureはすべて人工生成であり、公式から保存したレスポンスではない。2026-09-18の事故時raw HTMLは未取得。今回の直接公式ページ取得も失敗している。したがって、行列構造対応候補の単体試験は通ったが、実ページ適合、既存アプリ統合、Cの直前入力一式、稼働中E2E回復はまだ未検証。現行パーサーが明示的区切り文字を要求する点はコード読解で確認済みだが、それだけで事故当時DOMの具体的差分までは確定しない。

source wrapperは呼び出したコードだけを守る。別認証情報や別モデルコンテキストによるアクセス隔離を代替しない。今回A/B稼働タスクへこのPythonコードを挿入したわけではない。

## ローカル実行

```sh
python -m pytest -q tests/test_v11_candidate.py
```

必要パッケージ: beautifulsoup4、pytest。既存依存関係へ自動的に新version pinを強制しない。依存更新は別途全体回帰テストする。

## 本番反映前の必須ゲート

1. BOAT RACE公式の同日・同場・同Rレスポンスを実際に保存する。取得URL、final URL、HTTP status、content-type、取得実時刻、body SHA256、snapshot referenceを対応づける。
2. 実HTMLのヘッダー、rowspan、払戻更新表示、発売前、発売終了、欠場、返還、キャッシュ/エラーページをfixture化し、独立にラベル付けした期待値へ120通り全件照合する。
3. caller側でURL・本文の対象日/場/R・更新時刻を検証する。パーサーのheading一致やHTTP200だけを真正性/鮮度の根拠にしない。
4. parse_beforeinfoの展示/ST/実進入・天候にも実fixtureを追加する。oddsだけ直してC全体回復としない。
5. 既存`parse_odds3t`と`OfficialDataFetcher`へのadapter、SourceEvidence、is_complete判定を実装し、既存テスト＋本候補＋PR #1との統合試験を行う。現時点はadapter未実装で、既存ランタイムは本候補を呼ばない。
6. receipt保存失敗、再試行重複、scheduler証跡、通知到達を別試験する。P95/P99は複数開催の標本蓄積後に推定し、確実な締切保証と呼ばない。
7. 独立レビューと明示的merge承認後にのみデプロイする。実舟券購入は行わない。

## 9/18分析の訂正

B8は差替え前後とも正解1-2-3を持っていなかった。『REVISIONが正解を消した』は不正確。12Rの14秒前はOBS受理で、REVISION永続化の実測ではない。保存済み結果のhash一致はscheduler起動経路の証明ではない。updated_atをdisable実施時刻や主体と断定しない。
