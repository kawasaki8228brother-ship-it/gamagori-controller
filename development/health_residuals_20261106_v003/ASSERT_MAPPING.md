# 旧v002→v003 assert対応表（静的・削除/弱化を含む）

基点は`48333a2315628ae17e1fa3ce4f8ef12c70e2662f`。対象は指定5本だけ。旧原本のbytes/SHAを親台帳と照合し、新版は関数・行番号・bytes/SHAで固定した。アプリ/testをimport・実行せずAST抽出した資料で、本番接続もない。候補commitは未確定でJSONのnullは将来のcommitを推測していない。

[ASSERT_MAPPING.json](ASSERT_MAPPING.json)は全assertの式・元source・行番号・関数・if/for/with/try条件、decorator入力、関数対応、全文diffを収録する。Python assert、unittest/Mock検証、raises/log context、assert helper呼出し/本体、失敗sentinelを区別した。`same`は同じ式ASTと局所条件だけで、fixture・順序・coverageの意味的同等性を保証しない。変更式はold removed＋new addedとして残す。assert数、helper展開数、parametrize数の増減は厳格化の証明ではない。

## 静的集計

| ファイル | old→new assertion occurrence | same | 条件変更 | removed | added | test-case proxy old→new |
|---|---:|---:|---:|---:|---:|---:|
| `test_health_controller_scope.py` | 53→53 | 50 | 0 | 3 | 3 | 12→12 |
| `test_health_official_index.py` | 48→45 | 40 | 1 | 7 | 4 | 41→41 |
| `test_health_raceindex_parser.py` | 20→20 | 20 | 0 | 0 | 0 | 37→37 |
| `test_health_v002_controller.py` | 63→64 | 45 | 0 | 18 | 19 | 8→8 |
| `test_health_v002_schedule.py` | 35→18 | 4 | 0 | 31 | 14 | 17→15 |

case proxyはAST内literal decoratorの展開算術で、実行済みテスト数やsubtest数ではない。新規v003ファイルやfull-suite件数はこの集計の対象外。

## 手動対応：変更理由と撤回した期待

### test_health_controller_scope.py

- `test_unverified_no_race_claim_retains_current_cache_and_latches_hold` → `test_legacy_named_failure_retains_current_cache_without_a_latch`。旧`assertTrue(INDEX_HOLD in logs)`→新`assertFalse(...)`、旧`_index_hold_reason == SCHEDULE_AUTHENTICATION_NOT_IMPLEMENTED`→`hasattr(...)=False`、official失敗後trackingの`assert_not_awaited()`→`assert_awaited_once()`。当日cache等価は維持。旧停止方針の撤回であり、同じ安全機能を厳格化したとは扱わない。
- `controller` helperのlatch初期化を日付付き開催材料setへ変更。NoRaceVerifiedはproduction importから、旧名を模したローカルRuntimeError fixtureへ変更。既存state/scope/STOP/当日fallback検査の原式はJSONで個別確認できる。

### test_health_official_index.py

- `test_http_200_empty_partial_or_wrong_structure_is_not_no_race`は3入力を維持。旧reason一律RACE_INDEX_HTML_INVALID→入力別reason（空行だけNO_RACE_ROWS_UNAUTHENTICATED）へ置換。IndexFailure型は維持。例外文字列全体の等価比較ではなく固定分類条件である。
- `test_self_reported_calendar_does_not_skip_http_or_verify_absence`→`test_removed_calendar_provider_is_not_an_admission_api`。旧helper accepted/authenticity/kindを検査するassertを削除し、constructorの未登録provider引数TypeErrorへ置換。12R/HTTP実行検査は維持するが、削除APIの返却内容の検査は存在しない。
- `test_invalid_calendar_never_verifies_absence_or_relaxes_count`は8入力名を維持する一方、旧「8R取得→IndexFailure/kind/HTTP1回」を削除し、一律constructor TypeErrorへ変更。証拠の各不備を処理するテストではなくなった。ケース数維持は内容検証coverage維持の証明にならない。
- `test_self_reported_short_calendar_does_not_relax_expected_twelve`→`test_partial_day_cannot_change_fixed_expected_twelve`。provider入力を廃止し、HTML8Rとtracking8Rの失敗型/分類は保つ。短縮日程を正規化する認定経路を試すものではない。
- `test_calendar_provider_exception_retains_twelve_and_does_not_echo`→`test_removed_provider_argument_never_executes_or_echoes_callback`。旧正常12R取得assertはこの関数から削除。TypeError＋秘密fixture文字列がcaplogへ出ないことを検査する。実行済みcallbackの扱いや全例外本文の等価性を証明しない。
- `fetcher(text,provider=None)`→`fetcher(text)`。`test_tracking_absent_stadium7_is_missing_never_calendar_absence`はassertを維持してfixtureへ`date=DATE`を明示。欠損stadium判定に必要な「対象日が明示された入力」へ具体化したもの。日付無しnegativeは新`test_health_v003_no_race.py`で別検査され、本5本に紛れ込ませていない。

### test_health_raceindex_parser.py

- `test_synthetic_normal_twelve_and_status_semantics`の5assert式は同一だが、旧締切cell内の状態fixtureを、意味的な発売状況列へ移した。**入力変更あり**なのでassert同一を旧全状態推定の互換証明にはしない。
- 最新01:55追記は、意味締切cellと一意な状態cellから時刻除外後のexact8語だけを扱う別の現候補policy。名前/注記からの行全体推定を保証する旧期待は維持しない。新状態・R7誤中止・締切cell等の追加coverageは別v003試験/イベント比較の証拠が必要。
- 残るassert/raises条件は本5本の比較では不変。部分parse等の旧regexには広い比較もあり、それを新たな厳格化やerror文字列完全一致と呼ばない。

### test_health_v002_controller.py

- normal12、forged午後claim、full-outageの関数では`assertIsNone(_index_hold_reason)`→`assertFalse(hasattr(...))`。同じ「HOLD値が空」の検査でなく、属性自体の廃止確認。
- `test_legacy_no_race_claim_from_either_fetch_preserves_current_states_and_holds`→`test_legacy_named_failure_from_either_fetch_uses_normal_fallback`。旧(取得失敗,true/false固定)＋current1保持＋tracking不呼出しを撤回。official旧名例外後はtracking12R成功、戻り値/件数はorigin別、tracking1回へ変更。repo読取/直接process呼出し無し、状態不変は維持。
- `test_hostile_no_race_exception_is_not_stringified_or_accepted`→`test_hostile_legacy_exception_is_unknown_without_stringification_or_latching`。旧HOLD理由一致を削除し、latch不存在＋UNKNOWN_FAILUREへ置換。str/repr失敗sentinelと秘密文字列非出力は維持。
- `test_hold_latch_survives_next_refresh_and_same_instance_start_without_replay`→`test_unknown_failure_does_not_latch_and_later_poll_dispatches_normally`。旧「2 held polls、fetch/process未呼出し、cache1」を撤回し「次取得成功、12 dispatch、cache12、official await_count2」へ意図的反転。`process_race.assert_not_awaited()`を削除し、mock dispatchを許す。実writer/state変更無しのhelper検査は残る。これは停止安全期待の撤回で、厳格化と称さない。
- `test_held_next_day_prunes_now_stale_cache_without_clearing_latch_or_refetching`→`test_unknown_failure_does_not_prevent_a_fresh_next_day_index`。旧翌日cache空・fetch無し・HOLD維持を、新翌日12R取得/対象日prefix/await1へ置換。履歴の更新やreplayを認める試験ではない。
- full-outage既存当日scope、STOP途中fetch抑止などの残存assertはJSONに全列挙した。空watchdog5/10周期やread failure継続の新coverageは別v003 Controller試験であり、本旧5本のassert増分に混算しない。

### test_health_v002_schedule.py：17→15の明示

- 旧`assert_unverified` helper（accepted/event/full12/kind/reason/authentication/authenticityの7assert）とその呼出しを削除。旧APIを残したまま厳格化したのではない。
- `test_perfectly_self_consistent_claim_still_has_no_authentication`→`test_matching_calendar_claim_cannot_be_injected_as_an_argument`、receipt検査→`test_arbitrary_self_asserted_receipt_cannot_reopen_removed_api`。旧返却決定/不変性/str(result)非漏洩検査から、TypeError＋provider未呼出しへ置換。receiptの`a*64`入力とrawSHA同値への再代入検査も削除。自己整合原本の認定を試す経路は無い。
- `test_evidence_and_target_are_not_inspected_or_stringified`（禁止属性アクセスsentinel含む）と`test_async_provider_is_also_not_invoked`は削除。constructor引数拒否/production API不存在は代替方針だが、これらと同じ入力・実行経路を保持したとは報告しない。
- provider不呼出し2経路→`test_fixed_twelve_remains_without_provider_attribute`。provider属性無し、12R、tracking非公式flagを検査。旧caplogのPRIVATE_PROVIDER_SECRET/NO_RACE_VERIFIED不在assertはこの関数から削除された。
- `test_legacy_decision_function_cannot_reopen_short_count_bypass`（helper monkeypatch、8R失敗/providerとhelper未呼出し）は削除。新`test_schedule_authority_names_and_constructor_hook_are_absent`がAPI/constructor/helper/kind不存在を検査する。追加v003の旧属性注入/partial8検査は別資料の新coverageであり、旧2経路試験を無条件に同等とはしない。
- 旧legacy quarantine→`test_removed_exception_kind_strings_are_ordinary_unknown_failures`（2kind入力）＋新`test_unknown_exception_name_cannot_certify_absence_or_stop_monitor`。SCHEDULE_UNVERIFIED隔離/HOLDの期待を撤回し、UNKNOWN_FAILUREへ変更。malicious属性検査はrenameし固定UNKNOWNを維持。
- 上記組替え後のliteral parametrize proxyは**17→15**。17ケースを全て保持したとは書かない。削除・追加の各assertと条件はJSONに残し、何本増減したかを品質証明にしない。

## 比較の弱化・限界を隠さない

指定5本では、errorへ埋め込まれたURLを除去して比較するような新しい正規化assertは見つからない。ただし既存の広い`pytest.raises(match="partial parse")`等は完全error同一性を検査しない。削除されたcaplog/str(result)/callback検査は上記の通りで、source URLや任意例外本文の一致・非漏洩を本表で包括証明しない。範囲外の比較器にURL等の表現差を無視する処理があれば別の緩和として開示が必要で、本表はそれを等価性証明へ含めない。

同じassertでもinput、loop、mock、parametrize、実行回数が変われば意味が違う。JSONの全文diffと関数source SHAも確認すること。新旧完全な実動作、実HTML互換、本番状態、LOCK有効性、イベント順序、性能、権限はこの静的表からPASSにしない。

付記の再監査は**certifi 11/6 05:00-06:30 JSTの実施終了後**。予定枠の終了だけではcertifi成功/CLOSEと認定しない。実際の結果・未解決事項を確認し、HQ14/Claudeの再審査時期を決める。ここではcertifi・本番・task・merge/deployを操作しない。
