# SYS-02 offline prototype — 初回開発報告

状態 **READY（合成データによる開発検証のみ）**。Claude独立審査は未実施、適用可能判定はNO、本番適用は無し。
certifiを最優先し、この成果の確認・独立審査はHQ14がcertifi終了を確認した後とする。
初回報告目標は2026-11-06 18:00 JST、Claude提出目標11/13。11/8読取専用、11/9–14本番Freeze、導入は11/15以降の別審査・別GO。

保存済みJSONの検証結果を3軸で分ける。LOCK有効性・締切・Freeze・予想決定・A/Bの仕様は判定しない。

| 軸 | 規則 |
| --- | --- |
| raw | 完全な入力bytesのSHA-256。再シリアライズしない。対比較ではbytesそのものも比較する |
| canonical | Python `json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)` のUTF-8 SHA-256 |
| semantic | JSON数値をexact Decimalで比較。型・配列順・Unicodeを保ち、辞書キー順は無視 |

`1`と`1.0`はraw/canonicalが異なりsemanticは一致する。trueと1は異なる。
`0.10000000000000001`と`0.1`はPython canonicalが同じになり得るが、semanticは異なる。
この場合は`CANONICAL_DECIMAL_ROUNDING`も出す。canonical一致を意味一致に読み替えない。
canonicalはPython int/float、semanticはDecimalという別の規約であり、両者を同じhashだと呼ばない。

重複キー（Unicode escapeで同じキーになる場合も含む）は別異常。最後のキーを無言で採用しない。
NaN/Infinity/-Infinityは拒否する。有限JSON数値がPython floatでoverflowした場合はcanonicalがUNAVAILABLE、Decimalの意味比較は独立に残す。
不正UTF-8、BOMを含む不正JSON、孤立surrogate、資源上限も個別分類。Unicode正規化はしない。
全結果のANDによる総合PASSは作らない。rawが一致してもJSONが曖昧ならcanonical/semanticはUNVERIFIED。

## 実行

Python標準ライブラリのみ。アプリ本体やrequirementsをimport/installせず、このディレクトリから実行する。

```sh
python -B -m unittest -v test_sys02.py
python -B run_tests.py --run r003
```

記録済みrun IDは上書き禁止。最終記録は`results/r002.json`と`results/r002.log`。
`make_fixtures.py`はすべて合成fixtureを生成し、実データに接続しない。
既知SHA empty/abc/改行/UTF-8の固定値とGNU sha256sumの独立バックエンド照合を含む。
47 fixtureには背景のB数値表現2件・A数字キー順4件を合成で再現したものを含む。元の6件を受領したという意味ではない。
公開分類7 input status、3 canonical status、各軸のMATCH/DIFFERENT/UNVERIFIEDを全てテストする。
これは公開分類の網羅であり、すべてのPython実行経路の形式証明ではない。

## API例

```python
from json_integrity import compare_bytes, inspect_bytes
result = compare_bytes(b'{"n":1}', b'{"n":1.0}')
# raw DIFFERENT, canonical DIFFERENT, semantic MATCH
one = inspect_bytes(b'{"a":1}', expected_raw_sha256=raw_digest,
                    expected_canonical_sha256=canonical_digest)
```

期待hashの種類は呼出側が明示する。出所不明のhash種別を推測しない。
期待hash未提供はnull、計算不能もnullであり、不一致Falseや合格Trueとは分ける。
結果に原文・値・キー名は出さない。完全な入力bytesを受け取るAPIであり、切り詰めたデータを原本と称して渡さない。

## 境界・OPEN

実データ56件はHQ14が非公開環境で検証する。Codexは受領・照会・外部送信しない。要約件数だけを受ける。
raw一致は時刻真正性、DB同一性、取得元の真正性を証明しない。
Python 3.14.3など別実行環境の互換試験、hash種別の運用契約、資源上限の正式採択、独立審査はOPEN。
Decimal方針・負のゼロの数値一致・Unicode非正規化も現段階の試作規約であり、本番規則ではない。
SYS-01等への自動組込みはしない。公開repoの新規`development/sys02/`以外を変更しない。
元mainの既存ファイルは不変で、現段階の復元作業は不要。差戻しは本番へ適用しないことで行い、mainやcertifiをreset/rollbackしない。
