# S1 v003：D1形状方針とD2限定cell状態signal

対象は親v002からの隔離候補。ネットワーク・DB・サービスconstructorは使用しない。
Model、LOCK、state_machine本体、タスク、Productionへ変更を加えない。
beforeinfo/oddsのbyteを維持する。v001/v002の資料・fixture原本は変更しない。

実HTML原本・SHAは未提供。R1〜R20はHQ14が転送したE6説明に基づく合成再現であり、
実公式ページや独立監査原本とのbyte同一性はUNVERIFIED。
P1〜P14は後着のHQ14/Claude転送で完全なgenerator定義と受理/拒否期待を受領した。
これを別moduleで再現したが、当時実行されたHTML原文bytes/SHAとの同一性は未確認。

## B2の最優先変更：01:55追記後の現行候補

旧v002は行全体から「中止」「発売終了」「投票」等を検索して状態を設定した。
そのためrace名「雨天中止順延記念」をcancelと誤認し得た。
これはコードと合成fixtureで再現する性質であり、実当日に同じ原因が起きたとの
観測ではない。v003では**行全体からの状態検索を廃止**した。
一方、確定した締切cellの「13:01 発売終了」からCLOSEDを得る旧互換は維持する。
一度実装した「明示状態cellのみ」のstage1候補はこの互換を失っていたため、
最新のClaude 01:55追記で置き換えた。stage1ログは履歴であり現行候補の証拠ではない。

読むのは**一意に意味特定した締切cellと、任意の一意な明示状態cellだけ**。
各cellから完全で有効なHH:MM/HH:MM:SSを除き、残りの全文が暫定許可語にexact一致
するときだけsignalとする。deadlineの決定は従来どおり締切cell内の一意な時刻からで、
状態cellの時刻をdeadlineへ流用しない。

| 対象 | 暫定allowlist |
|---|---|
| 状態header | 発売状況、状態 |
| 時刻除去後の全文が投票、発売中 | OPEN、closed=false、cancelled=false |
| 時刻除去後の全文が発売終了、締切 | CLOSED、closed=true、cancelled=false |
| 時刻除去後の全文が中止、レース中止、発売中止、取りやめ | CANCELLED、closed=false、cancelled=true |
| 許可cellに未知の残り/両signalが矛盾/状態列複数 | UNKNOWN、closed=false、cancelled=false |

**このheader/語彙は実公式確認前のPROPOSED/POLICY_PENDING**。
rootから認められた隔離候補としての狭い語彙であり、正式な公式mappingではない。
全語彙に`POLICY_PENDING_REAL_HTML`を明示する。英語OPEN/CLOSED/CANCELLEDや
列挙外の類義語、部分一致は採用しない。「中止 発売終了」「発売終了（確認中）」
「中 止」のような残りはUNKNOWN。名前・注記・headerや許可cell外の投票ボタンは
signalにも矛盾判定にも使わない。

空の残りは「無signal」。両cellが空/時刻だけなら情報なしとしてUNKNOWN。
片方だけが許可語で他方は無signalならそのsignalを採用する。
両cellが同じsignalなら採用し、OPENとCANCELLED等で異なればUNKNOWN。
片方に未知の残りがあれば、もう片方の許可語へfallbackしない。
例えば「13:01 投票」＋明示状態「中止」は矛盾してUNKNOWN。

`race_index_status_policy()`はこの候補範囲を新しいdictで返す。
status=PROPOSED_POLICY_PENDING、official_state_confirmation=UNVERIFIED、
vocabulary_policy_status=POLICY_PENDING_REAL_HTML、official_source_authentication=NOT_IMPLEMENTED。
状態列があった事実も、source/date/venueの真正性や当該cellが実公式状態という
証明にはならない。移植前に実HTML・正式語/列・日付venueを独立審査する必要がある。

UNKNOWNのflagsは常にfalseであり、parserからcancelの終端根拠を作らない。
Tracking/非公式sourceのflagsを無効にする制御は別componentの範囲。
本資料はstate_machineのイベントやLOCK判断を変更するものではない。

## D1：R1〜R20の期待と方針待ち

| ID | HQ14からの説明 | v003候補 |
|---|---|---|
| R1 | 閉じtd/tr省略 | POLICY_PENDING_REAL_HTMLで拒否 |
| R2 | thead/tbody | 受理 |
| R3 | レイアウト表内出走表 | POLICY_PENDING_REAL_HTMLで拒否 |
| R4 | PC/スマホ表2つ | POLICY_PENDING_REAL_HTMLで拒否 |
| R5 | レースNo. header | POLICY_PENDING_REAL_HTMLで拒否 |
| R6 | race/締切以外header colspan | POLICY_PENDING_REAL_HTMLで拒否 |
| R7 | 名前「雨天中止順延記念」 | 受理、名前からcancelにしない。当fixtureは時刻だけなのでUNKNOWN |
| R8 | レース/締切列の逆順 | 受理 |
| R9 | 非表示重複1R 00:00 | 重複で拒否、可視性を推測して片方を捨てない |
| R10 | 全角時刻 | 拒否 |
| R11 | 25:10 | 拒否 |
| R12 | 時刻なし注記行 | 注記をレコードにせず受理 |
| R13 | 時刻あり注記行 | POLICY_PENDING_REAL_HTMLで拒否 |
| R14 | 1 Rの空白 | 受理 |
| R15 | 13R | 範囲外で拒否 |
| R16 | CRLF | 受理 |
| R17 | 締切cell br | 受理、時刻を除いた投票がexactならOPEN |
| R18 | コメントアウトtable | コメントをデータにせず受理 |
| R19 | 締切cell「発売終了」 | 受理、時刻を除いたexact語からCLOSED、cancel=false |
| R20 | 途中repeated header | POLICY_PENDING_REAL_HTMLで拒否 |

R1/R3/R4/R5/R6/R13/R20は、実HTMLと正式方針がないため受理範囲を広げないという
**policy拒否**。合法なHTML5省略記法やlayoutを「truncated/壊れたHTML」と断定しない。
error codeもPOLICY_PENDING_REAL_HTMLを含む理由に変更した。
この7件の方針待ちを、実HTMLテスト不合格や公式が不正という判定へ読み替えない。

12行が読めた、tableが閉じている、期待集合と一致したという局所検査だけで、
ページ全体・開催日・venue・取得元・当日編成の完全性を認定しない。
HTTP 200やno rowsから非開催を認定することもない。no rowsはエラーのまま。

## fixture API・比較

```
from development.health_residuals_20261106_v003.parser_fixtures import (
    cases, DATE, ACQUIRED, SOURCE, EXPECTED_RACE_NUMBERS
)
```

`cases()`は29件（通常12R、R1〜R20、明示状態/危険状態8件）。
v002比較runner互換のid/description/html/expected_status/expected_secondsを保持し、
expected_flags、expected_reason、policy_status、state_vocabulary_statusを追加する。
expected_flagsはrace番号文字列からsales_status/is_closed/is_cancelledへのmap。
拒否caseではtime/flagsはnull、reasonに期待する固定error部分文字列を置く。
全件source_identity=SYNTHETIC_DESCRIPTION_REPRODUCTION_ORIGINAL_BYTES_UNVERIFIED。

状態8件はCANCELLED/CLOSED/OPEN/UNKNOWNの明示cell、複合矛盾、複数状態列、
未確認英語語彙、名前/注記の紛らわしい単語を扱う。
旧main・v001・v002との比較では時刻だけでなくflagsも比較する。
特にR7の誤cancelと、R19のCLOSED旧互換を正常に見える時刻結果へ埋めない。
state_machineイベント列・正確な新旧比較ログはroot/別担当の成果物で確認する。

`e5_fixtures.py`は同じcases()/constants APIで5比較を提供する。
E5_aは締切cell時刻+発売終了→CLOSED、E5_bは明示状態cell発売終了→CLOSED、
E5_cは情報なし→UNKNOWN、E5_dはR7の名前中止→UNKNOWN/notcancel、
E5_eは明示状態cell中止→CANCELLED。これは記述からの独自合成再現で、
実HTMLとの同一性はUNVERIFIED。締切cell由来の旧互換を失わず、名前由来の
誤cancelを除くことを比較する。StateMachine本体は変更しない。

## 後着P1〜P14 generatorの受領と再現

`p_fixtures.py`は転送されたHDR/rows/page/nav定義をそのまま記述した独立module。
DATE=20990107、SOURCE=S、ACQUIRED=A。時刻は架空の13:01〜13:12で、P14は秒00。
P8は定義どおり文字列の先頭`int(len(full)*0.6)`文字に切断する（bytes割合ではない）。
比較APIは同じ`cases()`とconstants、source_identityは
GENERATOR_RECEIVED_ORIGINAL_BYTES_UNVERIFIED。
Rの29件とPの14件を混ぜず、ID・入力定数・期待を各moduleから取得する。

| ID | 受領generatorの形式 | 期待 |
|---|---|---|
| P1 | 共通page、通常12R | ACCEPT 12R |
| P2 | 表前nav 1R〜12R | ACCEPT 12R |
| P3 | 表前h2「本日の最終 12R」 | ACCEPT 12R |
| P4 | tdのレース/締切予定時刻header | ACCEPT 12R |
| P5 | 投票締切header | ACCEPT 12R |
| P6 | R/締切予定header | ACCEPT 12R |
| P7 | 発走列に別の13:15 | ACCEPT 12R、確定締切列だけ採用 |
| P8 | 共通pageを先頭60%文字で切断 | REJECT |
| P9 | 表後に気温table | ACCEPT 12R |
| P10 | レース名「ドリーム12R」 | ACCEPT 12R |
| P11 | 12R締切cellが時刻なし「中止」 | POLICY_PENDING_REAL_HTMLでREJECT |
| P12 | 全角race label/Ｒ | REJECT |
| P13 | 1R締切cellが時刻なし「締切」 | POLICY_PENDING_REAL_HTMLでREJECT |
| P14 | HH:MM:SSの秒00 | ACCEPT 12R |

P11/P13は実公式の無時刻表示と、その時刻/取消/締切の意味が未確認。
exactの「中止」「締切」cellに専用のpolicy拒否reasonを追加するだけで、
deadlineを生成したり、状態列以外からCANCELLED/CLOSEDを補完したりしない。
受理するP caseでは、P1〜P7/P9の締切cellは時刻を除くと投票なのでOPEN、
P10/P14は時刻だけなのでUNKNOWN。headerの「投票」はsignalに数えない。
受理/拒否の受領期待と、最新B2方針に基づく状態期待を分けて記録する。

転送された過去のClaude観測、受領generatorの期待、rootが今実施する新旧比較は
別証拠として扱う。このmoduleや合成試験結果を過去実行bytes・公式HTML・
Claude独立監査そのものと呼ばない。実際の原文HTML/SHAは依然未確認。

## 旧テスト期待の撤回理由

私有範囲`tests/test_health_raceindex_parser.py`のstatus試験は、deadline cellに
中止/発売終了を書くだけのfixtureから、明示「発売状況」列のfixtureへ移した。
状態推定の誤りを温存せず、狭い候補mapping自体はOPEN/CLOSED/CANCELLEDで検査する。
旧main由来`tests/test_parsers.py`はroot担当が締切cellのexact許可語による
CLOSED/CANCELLEDの期待を戻し、OPENも検査する。情報なしはUNKNOWNのまま。
stage1の締切cell signal一律禁止は撤回したが、全行/名前検索は復活させない。
既存v002時刻試験は書換えず、秒保持・曖昧時刻・誤った追加時刻の拒否を継続する。

実施コマンド（既存read-only Python 3.14.3、低優先nice10）:

```
nice -n 10 env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -c /dev/null -p no:cacheprovider tests/test_health_raceindex_parser.py tests/test_health_v002_parser.py tests/test_health_v003_parser.py -q
```

担当scopeは**159 passed in 0.47s**。合成試験のみ、network/DB/controller constructorなし。
全体回帰の件数・新旧比較・原本archiveはrootの最終記録を参照する。
依存追加、install、venv変更、pytest cache/bytecode書込み、commit/pushは行わない。

beforeinfo/oddsを含む`_find_section_table`以降のbyte SHAは維持する:

`77bb91d7b69440a5ada0a6b68d54f3476476d98cbbfbc55fbf8a0dc2d22b2009`

## 移植前STOP

正式状態語/列、公式取得日のdate/venue/sourceの真正性、pending7形式の実HTMLと
原本期待出力が不明な間は本番・portable適用を認定しない。
P1〜P14はgenerator受領・合成再現済みだが、原文bytes真正性まで検証済みとしない。
自己申告「公式」やfixture hashだけで
実公式認証が成立する実装も追加しない。
合成試験PASS、独立審査、個別GO、適用、自然実行確認、CLOSEは別判定である。
