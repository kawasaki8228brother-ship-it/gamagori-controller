# F5 v007：決定・未採用・未確定の分離

本文は**文書のみ**。実行設定、既存モデル、grid、統計計算、245件の親ファイルを
変更しない。機械可読台帳は`DECISION_LEDGER.json`であり、
`executable_configuration=false`、全operation permissionはfalseである。

## 決定の受領と原本証拠

アンディの正式決定時刻として、**2026-11-05 20:36 JST**をHQ14転送の今回指示から
記録した。以下のDECIDEDは、その明示された決定内容の区分を示す。
正式決定原本bytesのSHAとapproval receiptは未提供のため、台帳ではnullを保持する。
HQ14・Claudeの独立した証拠紐付けもPENDING。

決定内容の受領と、原本真正性・独立証拠の確認は別判定である。
本資料のhashを決定原本のhashや、実行GOのreceiptに代用しない。
不明な原本SHA、receipt、日付、個別GOを推測で生成しない。

## M0：DECIDED — 確認比較の枠組み

単一のfrozen championとP_marketを、**同じ締切前の完全120通りodds snapshot**に
基づいて比較する。評価対象は自然対数のJOINT_120_LOGLOSS。
同じpaired適格レースを各日内で平均し、開催日を等重みにする。
レース数が多い日の重みを自動的に増やす評価へ読み替えない。

一方向alpha=0.025、power目標=0.8、confirmatory family sizeは**m=1**。
selectionで用いる6つのwを、holdoutの6個の確認仮説と数えない。
任意停止・結果を見た後の条件変更は禁止。

w=1が選ばれた場合は純市場予測であり、**NO_MODEL_SUPERIORITY**。
raw/model分布が診断用に残っても、モデルが市場を上回ったという証拠にしない。
SESOI、必要日数、依存処理等は後述のOPENであり、alpha/powerだけで
必要N、完全な検定手順、合格判定を自動確定しない。

## M2：DECIDED — 最初の第三研究SHADOW稼働日のpilot

初回の第三研究SHADOW稼働日からpilotとして測定する設計を記録する。
候補窓は**2026-11-21〜24、またはそれ以降**。実際の初稼働日、担当、時刻はnull/未定。
この候補窓はscheduleの設定でも、SHADOW起動・実入力・pilot実行GOでもない。
実施には後日の対象別GOと既存安全ゲートを必要とする。

「最初の稼働日」はpilotへの入口であり、pilotを1日で終える指定ではない。
pilot実施期間・日数は未指定のためnullとする。候補窓の全4日間を自動採用しない。
paired日が1日だけなら日間sample SDは算定できず、K<2はUNVERIFIED。
これは分母K−1の算術上の制約であり、新しいselection閾値ではない。
不足を理由にpilot期間を自動延長したり、追加日数やholdout再利用を採用したりしない。

測定対象は、締切前120通りodds取得率、欠測率と欠測/読取失敗原因、paired日別log-loss差、
推定可能な場合のsd_day、時点証拠とsource mappingの実務確認、予測保存と結果照合の運用。
これらの実測値はまだ存在すると認定していない。

**pilotをholdoutとして扱わない。** pilotから改善・利益・正式昇格を主張しない。
pilotの結果を使った設計調整がある場合、そのデータは未使用の最終評価ではない。
日数や分散の不足を架空の値で補い、将来の必要Nが確定したことにしない。

## M1：FUTURE_DESIGN_DECIDED — 将来の確認候補はAのみ

将来のconfirmatory設計はA案に限定する。
v006の`model11/shadow_preparation/evaluation_design.py`内`proposed_options()`を
読取り、`A_REDUCED_FIXED_CALIBRATION`が**hierarchical**を指定することを確認した。

- モデル方式：hierarchical。
- course alpha：0.5。
- temperature：1.0。
- 市場重み候補：`[0, 0.25, 0.5, 0.75, 0.9, 1.0]`。
- wは市場重み、1−wがモデル重み。
- selectionでwを選び、holdout前に一つのchampionをfreezeする。
- B/C案はexploratoryのみ。confirmatory familyへ無断追加しない。

これは**将来の設計決定**であり、現在のコード・実行grid・private設定を
変更する承認ではない。別途の適用GOなしに既存の実行設定へ反映しない。
M1のA採用を理由に、以前のAのselection24日/holdout60日まで採用したと推定しない。

## 八つのOPEN

以下は台帳で全件`status=OPEN`、`value=null`。

| ID | 未確定事項 |
|---|---|
| SESOI | 最小の意味ある効果量と判断上の扱い |
| MIN_SELECTION_DAYS | selection最小日数・十分性の根拠 |
| HOLDOUT_START_AND_DAYS | 未使用holdoutの開始・必要日数・封印ID |
| ALPHA_SPENDING_NEED | alpha spending計画の要否。任意停止禁止は維持 |
| SCRATCH_REFUND_CANCELLATION_RULES | 欠場・返還・取消・分母の事前規則 |
| ODDS_MISSING_AND_MAX_RATE | odds欠測時の扱い・報告・許容最大率 |
| DAY_MEETING_DEPENDENCE | 日間・節間依存と推論・分散の扱い |
| POST_PASS_ALLOWED_SCOPE | 将来の合格後に認める操作範囲 |

旧文書の24/60日、36/90日、60/120日は**ILLUSTRATIVE_NOT_ADOPTED**。
M0/M1/M2からこれらの値を自動採用したり、OPEN欄へ埋めたりしない。
サンプル数の仮計算、日cluster SD、過去の審査候補も正式閾値へ昇格させない。
OPENの解消・採用値・根拠・承認原本は外部の個別決定待ち。

## PROPOSEDの維持と実行権限

F2は**PROPOSED_NOT_ADOPTED**のまま。BOXやrisk thresholdを新たに採用・変更しない。
Model 1.0、BOX Ver.1、正式A/B、既存Freeze、G1〜G6は維持する。
G1〜G6の定義原文はこの入力で確認できないためUNVERIFIED/nullとし、内容を創作しない。

今回認められるのは決定内容を整理する文書作成のみ。
source接続、実入力、SHADOW開始、pilot、holdout、本番・設定・タスク変更、
PR Ready化・merge・deploy、正式昇格、合格後の自動操作は全て未承認。
統計的合格、Claude審査PASS、実行GO、適用後の正常確認、CLOSEを一括扱いしない。

次工程は原本SHA/receiptと独立証拠紐付け、八つのOPENの個別審査、
実行対象・SHA・期間・操作者・STOP条件を明記した別GOの準備。
この台帳の存在自体を、次工程の実行承認にしない。
