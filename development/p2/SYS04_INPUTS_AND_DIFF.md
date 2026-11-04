# SYS-04 v004 D1〜D3 — UNVERIFIED / OPEN

**USER_HQ14_CONFIRMED_INPUTS_UNAVAILABLE**。
HQ14は正確なD1〜D3定義、旧新原本bytesとSHAの検証済み資料を現時点で提供できないと回答した。
このため本案件は必要入力一覧・検証設計・合成fixtureに固定する。古いコピー/10月版/類似項目から補わない。
D1〜D3の意味、対応section、既存v004の適合性を新しく定義しない。

## 将来必要な入力（非公開、提供可能となった時だけ）

1. 審査対象旧原本とv004候補のexact bytes、各bytes数・SHA-256、版/取得時刻・取得経路と照合receipt。
2. 審査済みD1/D2/D3の無改変原文と出典。各条件が何を許し何を不変にするかの根拠。
3. 予想決定/LOCK/deadline/Freeze/reader/source_evidence等の正確なsection境界（byte start inclusive/end exclusive）と対応表。
4. 許可された変更範囲、保持すべきprefix/suffixまたは複数slice、承認の対象版・source・GO範囲。
5. 実装を変える必要がある場合のClaude審査・アンディ個別GO。判定や予想に影響するならLane2/HOLD。

## 検証設計（未実行）

- privateな旧新原本を個別にraw hashし、取得済みの期待SHAと一致させる。文字列の再serializeを原bytesと混同しない。
- byte境界の完全性、欠落/重複section、範囲外slice不変を検査する。差分対象を推測しない。
- 与えられたD1〜D3原文と正式section対応に対して、条件ごとの期待値を結果前に固定する。
- 旧新全文diffとsection単位同一性を私的に保全し、公開報告には件数/hash/検証範囲/OPENのみを出す。
- 条件の解釈や旧bytesに不足があればUNVERIFIED/HOLD。source_evidenceの実装を勝手に修正しない。

`SYS04_STATUS.json`内のtoy fixtureは`FIXTURE_PREFIX|old|FIXTURE_SUFFIX`とnewの局所byte差だけを示す。
原本の代用でもD1〜D3の再現でもなく、SYS-04の確定検証PASSは出さない。
現在の既存v004実装変更は0。資料提供不能を理由に他のオフライン案件の開発まで止めない。
