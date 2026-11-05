# Health残件 v003 / B1–B3・D1–D7

隔離開発候補です。実データ検証、本番移植、deploy、CLOSEは未承認です。

基点：`48333a2315628ae17e1fa3ce4f8ef12c70e2662f`  
新ブランチ：`dev/health-residuals-20261106-v003`

## B2：誤中止の修正

行全体から「中止」「発売終了」「投票」を探す処理を廃止しました。2026-11-06 01:55 JSTの追記に従い、意味で特定した締切列セルと、一意な明示状態列セルだけを読取対象にします。各セルから時刻を除いた残りが暫定許可語と完全一致した場合だけOPEN/CLOSED/CANCELLEDを扱い、名前・見出し・注記から状態を推測しません。無情報、複数状態列、複合語、矛盾、未確認語はUNKNOWNで、cancelled/closed flagsはfalseです。

R7の「雨天中止順延記念」は中止扱いにしません。R19の意味的締切セル「15:11 発売終了」は、時刻除外後の完全一致によってCLOSEDです。暫定語は「発売終了／締切」「中止／レース中止／発売中止／取りやめ」「投票／発売中」の8語です。暫定列名・語彙は[政策資料](S1_STATUS_POLICY.md)に明示し、公式HTMLで確認済みとは扱いません。公式の対象日・会場・原本対応と状態mappingの審査前に、この候補を本番へ持ち込んではいけません。

StateMachine・LOCK・締切ルールは変更しません。a:締切セル終了、b:状態列、c:無状態、d:R7名前中止、e:実状態セル中止の5ケースを比較します。a/b/eは旧版とのイベント種類・時刻一致が必須、dは誤中止解消による意図差です。cは結果を一覧化し、UNKNOWNでは時刻だけでTERMINALにならずSAFE_STOP/C_EVENT_DONE等が残る点をC5と結び付けます。Cの実装が出すイベントだけを証拠にし、リポジトリに存在しない正式A/B LOCKイベントを作成・推測しません。

追記前のstate列限定案では、締切セル終了をUNKNOWNにした場合に終端差が生じることをコードから確認しました。追記後は締切セルの限定読取を認めた最終案で再検証します。締切超過による自動TERMINALという回避ルールは追加していません。

## B3：未使用の停止経路を除去

provider引数・属性・旧非開催認定API・例外・特別分類とprocess内HOLD latchを、実行ソースから除去しました。新しい日単位HOLD、永続HOLD、翌日解除、restart復旧を追加していません。旧非開催名を自称する例外は一般の取得失敗として扱い、cache消去や監視停止を発生させません。

watchdogはレース対象が空でも5周期ごとに呼び、読取失敗はUNVERIFIEDの警告として残します。10周期等の合成ループで同日・翌日・新instance・不正例外・空周期を検証します。明示STOPは引き続き新規dispatchを抑止し、既存処理の強制取消・LOCK復旧・replayは行いません。外部の再起動・復旧を安全と認定したものではありません。

旧v002のHOLD試験は、削除した機能を保存する期待を撤回したことが分かる差分と原本を残します。旧資料の歴史的説明は書き換えず、現候補の動作はこのINDEX以下で区別します。

## B1 / D1 / D7：HTML政策と4版比較

R1–R20はClaudeの説明から作った合成fixtureです。P1–P14は後着のgenerator定義から再構築します。Claudeの原文bytesとの同一性や本物の公式HTMLであることはUNVERIFIEDです。Claudeから転送された旧結果は受領情報であり、Codexの独立実行結果と分離します。

R1/R3/R4/R5/R6/R13/R20はPOLICY_PENDING_REAL_HTMLとして理由付きで拒否します。HTML5で合法な終了タグ省略を、通信切断や不正HTMLと断定しません。P11/P13の時刻なし中止/締切済み表示も実原本未確認のため政策拒否です。

12行あること・閉じtableがあることだけでは、通信完全性、公式性、日程正当性は分かりません。HTTP数値、長さの比較可能性、ストリーム完了、文書終端、解析結果は別証拠とします。未確定構造を便宜的に受理する回避処理は追加しません。

旧8172aec・v001・v002・v003を独立プロセスで同じfixtureに適用し、受理/拒否/政策保留、締切秒、状態flagを比較します。旧版の受理は正当性の証明ではありません。実HTML取得・private Drive保存は未実施で、E0の取得候補も実行していません。

## D4：非開催候補の診断だけを表示

正確な「レース行なし」解析エラーとtrackingのstadium 7欠損が揃い、当日の開催材料がなく、保存状態の読取も成功した場合だけ、NON_RACE_CANDIDATE_UNAUTHENTICATEDを表示します。開催判定はUNVERIFIEDのままです。

当日の公式解析成功歴、trackingの蒲郡レース、当日cache、当日保存状態（終端を含む）があればSOURCE_FAILURE_DAY_EVIDENCE_CONFLICTです。DB読取失敗はREAD_FAILEDとして分け、0件や非開催の疑いに変換しません。一般のHTTP/TLS/解析障害は非開催候補の条件に含めません。

診断は観測専用です。12Rの削除・終了・精算除外、公式LOCKの変更には使いません。既存のStateMachineが行う期限・source-error処理そのものは変更していません。日付境界は既存の当日scopeを維持し、過去状態を改変しません。

## D5：監査品質のオフライン部品

[監査品質設計](AUDIT_QUALITY_DESIGN.md)を参照してください。

- C4：HTTP status、取得成否、解析成否、wire/decoded bytes、Content-Lengthの単位、encoding、stream/document終端を区別。実transportへの収集統合は未実装でOPENです。
- C5：入力された保存状態から前日未完了数を集計。DBへ接続せず、レース処理や状態を変更しません。
- C7：固定した既存OBS QAを再利用し、Aの確認済みidempotency式の一致・不一致・重複・競合を検査。Bへ式を流用せず未確認を保持します。
- C8：journal_mode値の読取と時間外監査の設計。journal変更、checkpoint、VACUUM、実Render/SQLite接続は行いません。mode=roでも正常なSHM管理は物理変更を生む可能性があります。

## D6 / E7：SHAとPython

新64桁参照はAの固定予測仕様SHAでありOBS専用契約SHAではありません。旧40桁との切り詰め関係と形式は公開fixtureで検査します。正式208 UTF-8 bytesは未提供なので、その原本の再計算はSKIP=UNVERIFIEDです。別の208B文字列を正式原文の代用にしません。

Claudeが10/11のA写しから独立再計算して一致したとの転送情報は、Codex実測やHQ14の再取得とは別の出典として記録します。OBSのevent_uuid/source_evidence必須性はUNVERIFIEDを維持します。

render.yamlにはPython版の宣言がありません。現在の本番patch版はここから確定できず、過去の3.14.3観測を現在値へ格上げしません。Python 3.14.3の既存環境を読み取り利用し、3.12.14は新しいprivate診断venvで検証します。3.12側は既存system-siteのnative依存を読み取り参照するため、完全密閉の独立インストールではありません。既存certifi環境・SYS-01/02環境・requirementsは変更していません。

実測件数・skip・runtime・比較結果は`evidence/RESULTS.json`と生ログが正本です。ローカル合成試験PASSを公式互換性、実本番適合、208B原文検証のPASSと扱いません。

02:20 JST追記後の最終全回帰は、両runtimeでそれぞれ**554 passed・1 skipped（UNVERIFIED）・27 subtests passed**でした。555 primary collectionとJUnit582 recordsを区別します。親v002は両runtimeで418 passed・18 subtests passedです。実測OpenSSL/SQLiteは、3.12.14側が3.5.8/3.53.1、3.14.3側が3.5.5/3.50.4であり、現在本番との一致は未確認です。

4版比較は各67fixtureを実行し、v003は全て現在の合成期待と一致しました。これは旧版の全結果をそのまま保存するという意味ではなく、政策拒否と誤中止修正を含む明示された期待です。実行イベント比較ではa/b/eが一致、cは両版で終端0、dはR7の誤CANCELLED除去による意図差となりました。cの翌日未完了数は供給された合成12件としてC5で可視化し、実DB全体の網羅性は認定しません。

内部レビューで判明した「前日tracking JSONで蒲郡欠損を先に判定すると、当日の非開催候補へ誤分類する」問題も修正しました。payload/programs宣言日付を会場欠損より先に検査し、前日データは通常のTRACKING_PAYLOAD_DATE_MISMATCH障害として扱います。対応回帰を追加し、他のStateMachine規則は変更していません。

追記2に従い、payload/programsの少なくとも一方に明示dateを必須化しました。両方にある場合は両方が対象日と一致しなければなりません。日付欄なしはTRACKING_PARSE_FAILED／TRACKING_PAYLOAD_DATE_UNVERIFIEDで、当日会場欠損やNON_RACE候補の根拠にはしません。stadium内のdateだけでこの前提を代用せず、未確認の情報形式は拒否します。古いJSONを現在URLから返すcache模擬も回帰に含め、未観測のHTTP Age等へ数値閾値を追加していません。

変更した既存テスト5本の[assert対応表](ASSERT_MAPPING.md)と[全AST抽出台帳](ASSERT_MAPPING.json)を追加しました。廃止APIの検査撤回、検査対象をconstructor拒否へ置換した箇所、privacy assertの一部撤回、HOLDから監視継続への反転等を隠さず示します。全てを同等維持・一律厳格化とは主張しません。当日会場欠損fixtureへのdate追加は入力契約の明確化で、TRACKING_MISSING assert自体は維持しています。

最初のv003 commit `971c63a95385690b365e16cadf22a8b1b50d097b`は固定履歴として保全し、追記2は同じ新規隔離ブランチの追加commitへ保存します。旧v001/v002や他ブランチは変更しません。Claude再監査は11/6 05:00〜06:30 JSTのcertifi作業より後に行う前提です。予定枠終了だけでcertifiの成功・CLOSEや本番GOを認定せず、作業が延長された場合もそれより先に審査を進めません。

## 移植範囲・STOP・復元

[PORT_SCOPE](PORT_SCOPE.json)で候補ソースの差分単位、既存scope helper依存、除外する旧provider/例外/停止latch、オフライン専用品を分けています。旧main由来の候補を直接deployしないこと。certifi後の正式基点への取り込みは未承認です。

公式HTML/state mapping未確認、現在runtime不明、source/time/DB identity不一致、未確認のVERIFIED化、名前由来の中止、誤った非開催候補、監視停止、イベント順序差、LOCK/依存設定差、hash/readback不一致は移植STOPです。C4未統合・208B未取得等のOPENも隠さずClaude/HQ14へ審査を委ねます。

元ソース・テストを`references/`に保全し、既存v001/v002の固定commitとブランチは変更しません。破棄は新候補のローカルコピーを削除する範囲で、本番rollbackやmain resetを意味しません。正式A/B・Model 1.0・BOX Ver.1・Production・POINTERはFROZENです。PR/merge/deploy/本番接続/自動昇格は未実施・未承認です。
