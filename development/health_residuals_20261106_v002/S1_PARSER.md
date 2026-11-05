# S1：意味が明確なraceindex構造の受理と曖昧入力の拒否

本資料は親v001からのオフライン候補差分。実サイトへの取得・本番反映は行わない。
実装は`parsers.py`のraceindex領域だけを変更し、beforeinfo/oddsは変更しない。
Model、LOCK、state、Daily、schedule、環境設定へ変更を加えない。

## 七形式の出典・再現性の範囲

出典はHQ14の最新回答で示された以下の**形式の説明**。
HTML原文bytes、原文SHA、Claudeが使用した各期待出力は未受領である。
`parser_fixtures.py`は説明と一対一に対応する独自の合成HTMLを作る。
説明レベルの対応は確認できるが、Claude原文とのbyte同一性はUNVERIFIED。
公式HTMLをそのまま再現したfixture、当日原本、実取得の証拠とは呼ばない。

| fixture ID | HQ14から受領した説明 | 合成fixtureでの期待 |
|---|---|---|
| S1_F01 | 表外1R〜12Rタブ | nav内の番号をrace rowにせず、table内の12Rだけ読む |
| S1_F02 | 表外見出し12R | h2見出しをrace rowにせず、12Rを読む |
| S1_F03 | ヘッダtd | tdでも意味が一意なrace/締切headerを認識する |
| S1_F04 | 投票締切 | 意味の明確な投票締切列を認識する |
| S1_F05 | 別列に2つ目の時刻 | 更新時刻をdeadlineにせず、確定した締切列だけ採用する |
| S1_F06 | レース名12R | レース名に含む12Rを別raceとして数えない |
| S1_F07 | HH:MM:SS秒保持 | 秒を切り捨てず、datetimeへ正確に保持する |

通常12RのBASELINE_12Rに加え、上記7件と危険11件を提供する。
全て2099年の架空の日付・時刻であり、実日程・実レース原本は含まない。
旧parserが受理したことも、HTMLの公式正当性の証明にはならない。

## 本体の変更

ページ全体のR個数とtr内のR個数を比較するv001の判定を廃止した。
代わりに、race列と締切列が一意に定まるtableのデータだけを読む。
表外タブ/見出し、race名/注記列のRはレコード番号として解釈しない。
race番号は指定されたrace列でのみ1R〜12Rを検査する。

headerはth/tdのどちらでも、レース・レース番号・Rと、
締切/投票締切/発売締切等の明確な列名を認識する。
複数の締切列、複数のsemantic table、列構造不一致、曖昧な番号は拒否する。
初めに見つかったtableや先頭のHH:MMへfallbackしない。

時刻は締切cell内に一つだけ必要。HH:MMは秒0、HH:MM:SSはその秒を保持する。
同じ行の別列に更新時刻等があっても、締切列が確定していれば許容する。
同じ締切cellの複数時刻、不正な秒・桁数・小数秒・欠落時刻は拒否する。
有効な時刻の横の`25:000`や`99:999`等を見落とし、最初の正常時刻だけを
採用しないよう、**不正なtime-shaped spanも数えてから**厳密に検査する。
fullwidth colonの不正な追加時刻も無視しない。

相反する重複に加えて同一内容の重複も引き続き拒否する。
期待集合が与えられた場合は欠落・余分な番号を許容しない。
選択tableの明示的なtable/tr/td/th閉じが欠けた場合は、BeautifulSoupが補修して
全12Rを作れても拒否する。省略終了tag等の別構造を推測で互換認定しない。

## APIと三版比較

本体APIは維持する。

```
parse_race_index(html, date_str, source_url, acquired_at,
                 *, expected_race_numbers=None)
```

expected_race_numbersはcallerが定めた完全集合。既定12Rは保守的候補であり、
当日の公式日程の実測ではない。実短縮編成への緩和には外部証拠が必要。
Noneはlegacy直接呼出し・3行fixtureの互換用で、完全性の認定ではない。

fixture API:

```
from development.health_residuals_20261106_v002.parser_fixtures import (
    cases, DATE, ACQUIRED, SOURCE, EXPECTED_RACE_NUMBERS
)
```

`cases()`はdictのlistを返す。keyはid/description/html/expected_status/
expected_seconds/category/source_identity/date_str/expected_race_numbers。
ACCEPTのexpected_secondsはrace番号文字列からHH:MM:SSへのmap、REJECTではnull。
source_identityは全件`UNVERIFIED_DESCRIPTION_ONLY_NOT_ORIGINAL_HTML`。

rootの比較runnerでは8172旧main、親v001、候補v002を別プロセスで読み、
同じfull12R HTMLと日時を入力する。keyword未対応の旧mainは4引数のまま呼び、
対応版にはexpected集合を渡す。race_id、deadlineの時分秒、closed/cancelled/statusを
正規化し、単なる受理と**正しい時刻での受理**を分ける。
別列の時刻や秒切捨てで受理した版をPASSにしない。
原本sourceと比較の実行ログ・archiveはrootの別成果物を参照する。

危険fixtureは競合重複、末尾欠落、時刻欠落、締切cell内複数時刻、複数締切列、
不正秒、race cell内複数R、閉じtag欠落、締切header不明、複数table、
不正な追加時刻の11件。全件REJECTを要求する。

## v001テスト期待の最小変更と理由

`tests/test_health_raceindex_parser.py`の意味的に過剰な拒否期待だけを変更した。

- 有効な13:00:01を拒否するcaseを、不正秒13:00:60のcaseへ変更。
  秒保持の正しい受理は新テストで検査する。
- 一行2時刻を一律拒否せず、同じ締切cellの2時刻は拒否、別列の時刻は正しい
  締切分へ到達することを検査する。
- 表外Rを一律拒否する期待を、semantic tableの2行だけを読む期待へ変更。
- headerの参考2Rを拒否するcaseを過剰拒否群から外し、新テストで参考Rとrace名Rを
  レコード追加せず受理することを検査する。
- 複数Rの拒否は全行R個数のerror codeから、race/締切cellの意味に基づく
  partial parseへ期待を変更。危険なrace cell/締切cellは今も拒否する。

既存6件のparser試験、3行fixtureの互換、番号不正、欠落、重複、曖昧締切の拒否は維持。
親v001の資料やfixture原本は編集していない。

## 隔離試験・非変更領域

最終の対象3ファイル試験は**84 passed in 0.30s**。

```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /workspace/work/certifi-phase1-policy-b/venv314/bin/python -B -m pytest -c /dev/null -p no:cacheprovider tests/test_parsers.py tests/test_health_raceindex_parser.py tests/test_health_v002_parser.py -q
```

既存の読取専用Python 3.14.3環境を使用。install・requirements変更・ネットワークなし。
子processだけでplugin自動読込を無効化し、bytecode/cacheを作らない。
`-c /dev/null`はasync plugin未使用のparser専用試験で無関係なasyncio_mode設定を
読まないためで、repository設定を変更していない。

`_find_section_table`から末尾（beforeinfo/oddsを含む）のbyte SHAは親と候補で一致:

`77bb91d7b69440a5ada0a6b68d54f3476476d98cbbfbc55fbf8a0dc2d22b2009`

## UNVERIFIED / STOP

HTML原文と取得証拠がないため、公式全形式への適合、HTML本文の当日日付、source真正性、
実際の11/5障害原因はUNVERIFIED。HTTP 200や空行から非開催を認定しない。
no rowsはParserErrorのままであり、verified empty/no-raceへ変換しない。
実日程・日付・取得元・完全性は外部のfetcher/監査ゲートで別途確認する。
未知構造を受理するための推測fallback、calendarゲート緩和、retry増加、
LOCK/Freeze変更は行っていない。合成試験と三版比較は本番GOの代替ではない。
