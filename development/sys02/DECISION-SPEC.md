# SYS-02 判定仕様・影響範囲

数値方針は`SYS02_DECIMAL_EXACT_V1_PROTOTYPE`。本番採択は未承認。

## 分類順序

1. 設定の型/範囲と期待SHA形式を検査。誤設定は固定メッセージの例外を返す。値は出力しない。
2. 完全なbytesをSHA-256にし、指定されたraw期待値と比較。
3. 解析上限を検査し、strict UTF-8 decode。BOMは削除せずJSON不正にする。
4. Decimal JSON parse。parse_constantの非有限値と、object_pairs_hookで重複キーを拒否。
5. tree深さとUnicode scalarを検査。孤立surrogateは拒否し、有効なsurrogate pairは通常文字として扱う。
6. 有効入力だけを通常Python int/floatで再parseし、指定canonicalにserialize・UTF-8 hash。
7. canonicalのfloat丸め/underflowを別警告にする。overflowはhashを作らずUNAVAILABLE_FLOAT_RANGE。
8. semanticはcanonical計算可否と独立にDecimal treeで比較。

複数の不正が同居するときは最初に検出した分類を報告する。異常の全件抽出器ではない。
raw期待値が一致しても、後続分類を省略しない。重複キーの値・場所を推測修復しない。

## semantic規約

- `1 = 1.0 = 1e0`、`-0 = 0`を数値として認める。canonical表記は統合しない。
- true/falseは数値ではない。null/文字列/配列/辞書を別型にする。
- decimalの丸めやepsilon許容は行わない。数値文字列は数値へ変換しない。
- 配列順・長さは有意、辞書のキー集合/値が一致すれば順序は無視。
- Unicode escapeと同じscalarの文字は一致するが、NFC/NFDの同一視はしない。

## 資源・実行条件

標準上限：解析対象1,048,576 bytes、treeのroot depth=0/子depth+1で最大64、数値token最大256文字。
depth設定は0〜128。数値token長/Decimal実装の指数範囲/JSON parser recursion限界でもRESOURCE_LIMIT。
超過でも既に受け取った完全bytesのraw hashは計算する。prefixをhashして全体のhashとはしない。
閾値はプロトタイプの安全予算で、実データの有効/無効条件・LOCK規則ではない。

## 3軸例

| 入力差 | raw | canonical | semantic |
| --- | --- | --- | --- |
| 同じ原文 | MATCH | MATCH | MATCH |
| キー順/空白のみ | DIFFERENT | MATCH | MATCH |
| 1と1.0 | DIFFERENT | DIFFERENT | MATCH |
| 0.10000000000000001と0.1 | DIFFERENT | MATCH + 丸め警告 | DIFFERENT |
| 値1から2 | DIFFERENT | DIFFERENT | DIFFERENT |
| 同じ重複キー原文 | MATCH | UNVERIFIED | UNVERIFIED |
| 1e400と10e399 | DIFFERENT | UNVERIFIED | MATCH |

## 非変更・未確認

変更はオフライン部品・設計・合成fixture・非秘匿のテスト結果だけ。予想、重み、Model1.0、BOX、A/B、LOCK、deadline、Freeze、保存経路を変更しない。
Python実行環境差によるfloat canonical表現差は事前互換試験が必要。標準canonicalはRFC8785/JCSを意味しない。
実際の保存payloadがraw/canonicalどちらのhashを契約するかはHQ14確認待ち。未知なら推測適用せずHOLD。
実データ56件の検証、時刻/DB/sourceの真正性、Production接続や適用は未実施。
次のレビュー対象：certifi終了後のClaudeによる数値方針・canonical互換・異常分類・hash種別契約。
