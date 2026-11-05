# 監査指示と修正範囲

入力：HQ14が本会話で提供したClaude監査F1～F5指示。
Claude原本bytesは今回取得していない。v003の実装・合成観測を別の証拠として提出する。

| finding | v003対応 | 判定範囲 |
|---|---|---|
| F1必須 | 6市場重み、純市場endpoint、market共通コホート、重複設定識別 | 合成ソフトウェア試験。実性能UNVERIFIED |
| F3必須 | 締切前枠番／展示のsource・3時点・定義・policy、学習と予測の束縛 | 外部source真正性・real mapping OPEN |
| F4必須 | 自動five_appearanceと別human_input、nullable手動、schema移行review | 正式Human／BOXv1再現は未実装 |
| F2待ち | 別BOX候補・最低coverage・不確実性penaltyの設計資料だけ | 閾値・候補採用なし。HQ14／Claude事前審査待ち |
| F5待ち | selection N／日cluster／候補budget・多重性・HOLDの設計資料だけ | 小標本をPASSにしない。実入力はHOLD |

開発内独立レビュー（Claude再審査とは別）で次を補強した。

1. v002のTRAINING_ONLY／未来normalizer拒否を、v003 forecast境界でも維持。既存v002関数を読取再利用。
2. 手動BOXの証拠保存より後の改訂、取得前改訂、選択前の利用可能時刻を拒否。時刻の自己申告だけで人由来真正性を認定しない。
3. walk-forwardだけでなく単独predict API／CLIも未承認実データを拒否する。
4. F3合成defaultでは元simulatorの結果前course値を保持し、ラベルを改変せず定義metadataを追加する。
5. datetime parserが補正する不正offsetを明示拒否。選択観測だけでなく未使用観測も`+09:99`等ならHOLD。

旧47＋41ファイルは不変。旧予測・成績をv003の結果として再表示しない。
正確なGit差分は親v002→v003の新規追加のみ。v001→v003の累積比較には保持済みv002の41追加も含むため、今回の変更とは区別する。
SOURCE_DIFFS内のunified diffは旧実装と新実装を比較するレビュー資料で、旧ファイルを書き換える適用patchではない。
