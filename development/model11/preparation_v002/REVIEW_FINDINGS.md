# 開発内の独立レビュー（Claude審査とは別）

実行環境：Python3.12.14／Linux。全て合成入力で再現。実データなし。

## R1 motor identityと統計時点

修正前：motor ID／versionが一致していても、特徴量の取得・利用可能・改訂時刻をidentity発効前にするとeligible=trueになった。
修正後：3時刻のいずれかがeffective_atより前なら`RAW_MOTOR_STAT_PREDATES_IDENTITY_EFFECTIVE`でHOLD。
等しい境界は許容。欠損・後日revisionは他の時点ゲートで拒否する。

## R2 旧版比較の結果時点

修正前：評価用actual.available_atが締切前でも比較対象へ入った。
修正後：欠損・naive・締切前の結果利用可能時刻はHOLD。締切と等しい時刻は境界として許容。
当該レースの除外・paired件数不足を明示し、読取失敗や不明を不的中／収支0として埋めない。

## 追加の境界確認

- 未来にfitしたnormalizerを過去予測へ適用しない。training専用出力はShadow不可。
- RAWにA/Bや旧版予想を特徴量として入れない。A/B比較は別source・別帳簿。
- 元の予測hash、別保存の原本bytes、解析済みJSON、profile、receiptを結び付ける。
- outcomeを変えても事前risk overlayは変わらない。元のtickets／BET-SKIPは不変。
- 自己整合hashから独立真正性やGOへ昇格しない。
- SYNTHETIC用mappingをprivate入力に流用しない。private用のreview metadataは別途必要で、真正性は未証明。

修正後の最終試験件数・実測環境・生ログはresultsとREPORTを参照。
