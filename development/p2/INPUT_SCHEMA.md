# 入力仕様（PROPOSED、実データschemaの採択ではない）

全modeの入力はJSON object。バイナリ原本はstrict base64で渡す。hashはSHA-256 hex64桁、種類はraw固定。
APIは純粋な局所比較だけを行う。CLIはローカルファイルを読むだけで、HTTP URLを取得しない。
欠損/不正hashはUNVERIFIED、rawの欠損と空bytesは区別する。出力の一致から原本の真正性を推定しない。

## sys14 / SYS-14

```
raw_b64: exact原本bytesのbase64 | null
expected_raw_sha256: 照合元に固定済みのraw hash | null
save_receipt: {acknowledged: true|false|null, raw_sha256: string|null} | null
readback_b64: 別に読み戻したbytesのbase64 | null
```

原本expected hash、receipt中のhash主張、readback bytesを独立比較。ACKだけでは保存済みとしない。
全て一致しても`LOCALLY_CONSISTENT`だけで、receipt/取得経路/保存の時刻・DB同一性は未証明。
APIはhash計算対象の完全bytesを受け取る。切り詰めたデータを原本と称して渡さない。

## sys15 / SYS-15

```
canonical: {id, sha256, version}
canonical_raw_b64: 元bytes | null
pointer: {canonical_id, canonical_sha256, canonical_version, decision_id}
decisions: [{id, canonical_id, sha256, version, ...}]
```

ID/SHA/版名と明示decision参照を比較する。履歴ID欠損・重複は警告、同じIDの履歴を無言で最後優先しない。
decisionのapproval等は文字列主張にすぎず、アンディGOの検証結果にしない。最新決定や承認優先順位は推測しない。
原bytes未提供ならhash文字列同士が合っていても元内容はUNVERIFIED。

## sys16_17 / SYS-16・17

```
http_status: integer 100..599 | null
network_error: NONE|SSL|DNS|TIMEOUT|PROXY|CONNECTION|UNKNOWN
expected_date, observed_date: YYYY-MM-DD | null
expected_venue, observed_venue: string | null
parser_error: NONE|NO_RACE_ROWS|OTHER|UNKNOWN
official_calendar: NO_RACE_VERIFIED|RACE_VERIFIED|UNKNOWN
input_format: EXPECTED|CHANGED|UNKNOWN
tracking_fallback: PRESENT|MISSING|UNKNOWN
scratch_count: nonnegative integer | null
```

これらはすべて観測値/別途確認された入力の主張。独立取得を行うコードではない。
日付/場/format/別日程の主張が揃った非開催パターンでも成功保証をしない。HTTP200だけでHTML内容適正や正式取得成功としない。
scratch/format変化を自動吸収せずSYS-17のLane2/HOLDを維持する。deadline/LOCK有効性は常にNOT_EVALUATED。

## sys23 / SYS-23

```
nodes: [{id: nonempty unique string, owner: A|B|NEUTRAL|PUBLIC|UNKNOWN}]
edges: [{from: existing node ID, to: existing node ID}]
```

edgeは宣言された情報依存方向。A→BまたはB→Aの到達可能性を中立/共通node経由も含め検査する。
最大256 node / 2048 edgeは試作資源上限であり本番仕様ではない。未知ownerがあれば無違反結果でもUNVERIFIED。
ownerは名前から推定せず申告で与える。graphに漏れが無い証拠、source filterや実readerとの対応はHQ14から別途必要。
出力のpathはmetadata ID。私的IDを含む実graphや出力をpublicへ置かない。

## sys24 / SYS-24

```
raw_b64: 元bytes | null
self_sha256: 自己整合hash | null
external_record: {raw_sha256, observed_at: timezone付きISO8601|null, ...} | null
```

外部recordと時刻も入力された主張であり、署名や発行者を本試作では認証しない。
`verified`フラグは信頼しない。自己hashが一致しても外部参照との不一致は記録する。
全主張が一致しても`independent_attestation=UNVERIFIED_NO_EXTERNAL_VERIFIER_OR_TRUST_ANCHOR`。
新しい鍵・署名方式・証拠保存先はこの研究に含めない。
