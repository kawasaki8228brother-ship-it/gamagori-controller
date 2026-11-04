# SYS-01 保存応答と実保存 — 設計・fixtureのみ

状態 **OPEN**。独立した設計・状態遷移・擬似interface・合成fixtureを作成した。
live A/Bの原文bytes/SHAとsection対応表は未受領。A/B本文、writer adapter、状態機械の実装は未着手。
`validate_design.py`はJSONと宣言経路の静的整合だけを検査する。実保存や状態機械のruntime試験ではない。

certifiが最優先。初回目標2026-11-06 18:00 JST、中間11/11、Claude提出11/13、計画完成目標11/14。
独立審査・確認はHQ14がcertifi終了を確認した後。11/8読取専用、11/9–14本番Freeze。
11/15–19のSYS-01→SYS-02→準備できればSYS-03という適用順も、各GO/1 JST日最大1件/自然run確認を必要とする候補であり実行指示ではない。

## 成果物

- `DESIGN.md`：状態遷移図、応答/保存/retryの分離、安全条件、影響と限界。
- `state-machine.json`：33宣言遷移。writerや状態機械のコードではない。
- `fixtures.json` / `CASE-MATRIX.tsv`：36合成シナリオ。保存確定・未確認・exact retryを独立に表示。
- `INTERFACES.txt`：擬似interfaceのみ。ネット接続/保存実装は無い。
- `LIVE-MAP-REQUIRED.md` / `OPEN-INPUTS.json`：HQ14から必要なprivate原本・byte境界・取得手順。
- `results/design-validation.log/json`：静的検査の実測。全runtimeはUNVERIFIED_NOT_IMPLEMENTED。

```sh
python -B validate_design.py
```

このコマンドはローカルJSONを読むだけ。A/B、Render、Airtable、Automations、実DBへ接続しない。
fixtureのGO・時刻・レース・bytesは全てSYNTHETICであり、実承認/実予測/実保存の証拠ではない。

## OPENとSTOP

live section mapが無ければ既存本文に触れない。旧10/11版・固定spec hash・推測sectionで代用しない。
原予想の再生成をしない。SYS-02のsemantic/canonical一致でSYS-01のexact bytes一致を緩めない。
保存先の原子性/unique key/読戻し原bytes/settled証拠/既存deadline gate/GO契約は未検証。
不足ならHOLD。予想決定部のbyte不変を立証できない統合変更はLane2/HOLD、Claude＋アンディ判断待ち。
作成済み（設計検証）と審査済み・適用可能・本番適用済みは別。現在は後3者すべてNO/PENDING。
本番本文を変更していないため復元操作は不要。今後の復元原本はHQ14の照合済live bytesだけを使う別GOであり、旧本文の推測復元やmain rollbackはしない。
