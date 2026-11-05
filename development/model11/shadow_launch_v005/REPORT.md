# Model 1.1 Shadow Launch-Ready Candidate v005

判定は **ローカルcapture入力による研究Shadow候補／条件付き提出**。
本番接続・実データ検証・Shadow起動・正式昇格は未承認で、配布設定はDISABLED。
精度改善、市場・Model 1.0に対する優位性、利益はUNVERIFIED。

## 固定基点と変更範囲

- v003監査基点: `62721c20676177bac171f97b0488412b07b63594`
- N1 v004修正: `df807089f5fd27517109f9bd38b6c55f9415600e`
- このv005の親: 上記N1 v004。新規隔離ブランチ: `dev/model11-shadow-launch-20261105-v005`
- v005は新規ファイル追加だけ。N1までの151ファイル、既存選定・BOX・コースpolicyを変更しない。
- main、PR #6、既存正式ブランチ、Production、Model 1.0、BOX Ver.1、A/B、Freeze、POINTERは変更対象外。

N1は分類とflagを厳密に照合し、未選択の非null観測も検査する。
PRIVATE_REALにSYNTHETIC sourceが混じる入力をHOLDとする。OFFICIAL登録名の一致は真正性を証明しない。
N1単独の346テストはPython 3.12／3.14でPASS。原本・diff・独立レビューは`../revision_v004/`に保全。

## 実装済み

| 要求 | 実装と境界 |
|---|---|
| P1 独立ランナー | `ShadowRunner`、明示CLI run/watch。締切前入力、予測・保存完了・最終readback時刻を検査。120通り、通常5点、独立研究BOX、BET/SKIP、ModelVersionを記録 |
| P1 重複・再起動 | namespace×race_idで排他予約。モデル更新でも同race再予測不可。COMPLETION_PENDINGを経て確定し、途中失敗・死んだprocessの未完了予約は保全してHOLD/STOP |
| P2 ローカル入力変換 | 元capture bytesと取得・利用可能・改訂・履歴を保持し、宣言済JSON pointer mappingからRAW_V001へ変換。欠損・未来・source分類不一致はHOLD |
| P3 保存・監査 | 独立所有root、SQLite台帳、原本bytes、SHA/size、receipt、completion、結果の別版、明示最終結果選択、日次精算の別原本とreceipt/readback |
| P4 模擬運転 | 合成12R、重複競合、入力不足、source障害、保存失敗・応答不明、再起動、結果訂正、進入/F/L/欠場、BOX、日次精算、安全停止。詳細はTEST_RESULTS.jsonと生ログ |
| P5 運用準備 | DISABLED template、preflight、起動・観測・停止・独立領域のみの復旧設計・日次監査。操作は将来の個別GOに従う |

正式Human BOXは人間の時点証拠付き別入力だけ。自動候補は`five_appearance_research`。
通常5点500円、各BOX600円、BET/SKIP、返還、重複買い目を分けて評価する。
構成差は艇集合の相違だけであり、優劣を意味しない。F2/F5はPROPOSED／未採用を維持する。

## private経路と承認境界

旧v003の実データHOLDを緩めず、別のv005 private予測経路を用意した。
PRIVATE_REALを合成へ付け替えず、同じ数値kernelを承認artifact・正規化provenance・時点と結合する。
モデル・normalizer・mapping・course・prediction_config・評価計画・正式旧版比較・code/config/storageをpinする。

preflightは入力された承認metadataの**形式照合と操作者の申告**であり、承認者の認証ではない。
HQ14／Claude／アンディの真正な承認確認は外部で必要。テスト中の架空承認を実承認として使わない。
すべての観測は`production_go=false`。この納品時点の実データ起動はHOLD。

## 試験と証拠

- 実行した件数・環境・結果・ログSHA: `results/TEST_RESULTS.json`。
- 生ログは取得したUTF-8 bytesを保持。初期失敗ログの公開用伏せ字版はREDACTEDと明記し、元SHAと別SHAを記録する。
- 12R demoは完全に架空の2099年データ。3.12／3.14の入力原本・内側予測・精算reportの一致を検査する。
- rootの場所、所有ID、receipt等は各実行で異なる。Shadow外側原本の全bytes一致は要求・主張しない。
- demoの`reproduction.code_commit`は固定N1基点を使用したfixtureの参照値。このv005実装全体の再現には納品commitをcheckoutする。自己参照するcommit SHAを成果物へ偽造して埋め込まない。
- socketの接続をブロックした合成試験。ローカル保存crash検査の子processはローカルSQLite専用で、接続clientを実装・使用しない。
- 実環境の時計の正しさ、対象host/FSの停電耐性、公式データ真正性、独立した外部時刻証明は未検証。

## 残る本番固有入力・OPEN

1. 承認済み公式capture形式・source mapping・単位・course選択規則・取得履歴の実証。HTTP収集器は未実装。この候補は**ローカル承認captureの受付まで**。実収集器／feedの供給と審査は別途必要。
2. 学習専用期間でfitした実モデル・normalizerと、その来歴検証。現時点で実データfitや評価を実施していない。
3. 凍結済Model 1.0／BOX Ver.1の正式比較入力、F2/F5を含む事前登録評価計画。未使用期間の結果に合わせて条件を追加・変更しない。
4. 実host・Python/OpenSSL/SQLite・独立保存root・所有/容量/clock・操作者・運用枠・監視/保持/復旧方針。
5. HQ14整合確認、Claude独立審査、アンディ案件別GO。今回のサブagentレビューは正式Claude審査の代替ではない。
6. 外部情報真正性とprocess/hostの信頼。自己hashと別読戻しは同一host内の整合性証拠であり、外部証明ではない。
7. 公式予定レースに対する当日の網羅性。日次精算が保証するのは当該storeの確定予測全件だけ。

予定審査11/15〜19、並走候補11/21〜24は予定だけ。経過日数で起動や承認状態を昇格しない。

## 判定を分離

| 状態 | 今回 |
|---|---|
| コード完成 | 合成・ローカルcapture契約の候補として提出。実測試験結果の範囲のみ |
| 実データ検証PASS | UNVERIFIED／未実施 |
| Claude正式審査PASS | 未受領 |
| Shadow投入承認 | 未承認 |
| 実稼働・本番動作確認 | NOT_STARTED |
| 正式昇格・CLOSE | 未承認 |

復元・破棄は候補コードと専用合成一時領域に限定する。既存本番のrollbackを行わない。
確定予測・部分失敗がある実ShadowのSTOP削除、予約削除、同race replayや自動restoreは実装しない。
独立復旧・再開は原本保全と追加審査／個別GOを必要とする。詳細はOPERATIONS_RUNBOOK.md。
