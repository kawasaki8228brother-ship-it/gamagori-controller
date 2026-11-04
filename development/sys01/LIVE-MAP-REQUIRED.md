# HQ14に必要なlive A/B原本・section対応表

現在は未受領。旧10/11コピーや固定spec hashを全文hashとして使わない。Codexは現タスクでAutomations/本番へ接続しない。

## 必要資料（HQ14の非公開保全）

source A/B別に、現行live本文のexact bytes、取得実時刻、task identityと版のprivate参照、全体bytes/SHA-256。
UTF-8/BOM/LF/CRLF/末尾改行、取得経路、UI文字列復元かnative exportかの証拠区分を明示する。
UI経由の文字列bytesをサービス内部native bytesの数学的証明と呼ばない。取得の限界はOPENとして残す。

section表は各範囲の名前/役割と、0-based start byte inclusive/end byte exclusive、原文slice SHAを含める。
予想決定部分、入力取得、Model1.0/BOX/重み、LOCK/deadline/Freeze、writer、retry/readback、その他を区別し、
どれにも分類できない範囲・相互依存をUNKNOWNとして列挙する。文字offset/UTF-16とbyte offsetを混ぜない。
予定するwriter範囲だけで変更が閉じるか、AとBで対応が異なるかを審査する。

## HQ14向け取得・照合手順案（今回は未実施）

1. 別途承認済みの読取経路で対象live task/versionを固定する。Save/Enable等の変更ボタンを押さない。
2. 同じ経路から独立2回取得し、rawファイルのbytes/SHAを比較。異なれば理由が確認できるまでHOLD。
3. 取得時刻・対象identity・文字変換/改行の扱い・原本保存場所を私的記録へ結び付ける。秘密値や本文をpublicへ出さない。
4. 凍結した各原本をbyte単位でsectionへ切り、全範囲の過不足・重複を検査し、全体hashとslice hashをHQ14が確認。
5. 将来候補を作る場合はwriter以外、特に予想決定部分の旧新slice bytesを直接比較し同一SHAを確認。
   公開報告は件数/hash/同一性の要約だけ。private本文をGitHub diffへ載せない。
6. 原本/hash/mapに不足や曖昧さがあれば既存本文へ着手せずLane2/HOLD。Claude＋アンディ判断へ。

この案は取得の実行GOではない。本文を受領するまで統合改修・section差分のPASSは出さない。
必要ならwriterの原bytes readback契約、先行writeのsettled判定、一意key保証、回数/GO契約もHQ14が同時にprivate確認する。
保存先に原子的一意性が無い場合、検索→createだけで重複防止を保証しない。追加機構の導入は別設計・別GO。
