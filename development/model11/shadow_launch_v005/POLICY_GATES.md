# v005 起動前policy境界

対象は独立した第三研究SHADOWの候補ソフトウェア。既存Model 1.0、正式A/B、
BOX Ver.1、LOCK、タスク、Productionを変更しない。既存ファイルは変更しない。
この資料とテストは開発証拠であり、実データ利用・本番接続・起動GOではない。
実際のHQ14/Claude/アンディ承認束は未提供。**現在のPRIVATE_SHADOWはHOLD**。

## APIとI/O境界

- `validate_settings(settings) -> {valid,status,reasons,enabled}`
- `settings_fingerprints(settings) -> {config_sha256,storage_identity_sha256}`
- `artifact_fingerprints(artifacts,mode='SIMULATION') -> {artifact_name:canonical_sha256}`
- `preflight(settings,artifacts,operator_ack=None,now=None) -> report`

全てpure local計算。ファイル・DB・ネットワーク・source fetchを実行せず、
時計も自分では取得しない。active経路ではcallerがaware datetimeまたは
厳密なaware ISO時刻を`now`へ渡す。timezone不明、時刻欠損、未来fitはHOLD。

`enabled`が未指定、または明示falseならDISABLEDで短絡する。
artifacts、operator_ack、nowを参照しない。storageを初期化せず、sourceも呼ばない。
bool以外の`enabled=1`や文字列`"true"`では有効化しない。
constructor、import、preflightの成功を起動トリガーにしない。

## settingsの正確な9項目

| key | active時の条件 |
|---|---|
| enabled | 明示boolean true |
| mode | SIMULATION または PRIVATE_SHADOW |
| namespace | MODEL11_THIRD_RESEARCH のみ |
| storage_root | `/`単体、相対、`.`/`..`、二重slash、制御文字を除く絶対POSIX文字列 |
| code_commit | 固定40桁lowercase Git commit |
| input_classification | SIMULATIONはSYNTHETIC_ONLY、PRIVATEはHQ14_PRIVATE_OFFLINE |
| storage_identity | callerが固定するsafe ASCII ID |
| pinned_config_sha256 | 明示64桁lowercase SHA |
| pinned_storage_sha256 | 明示64桁lowercase SHA |

DISABLED配布templateでは未知値をnullのまま保持できる。modeやnamespace等も含めた
有効化時の正式チェックはactive preflightで行う。未知項目を既定値で埋めて起動しない。

config SHAはpin2項目を除く残り7項目のcanonical JSONをhashする。
storage SHAはnamespace/storage_root/storage_identityのcanonical JSONをhashする。
`settings_fingerprints`は値を計算するだけで、settings更新・自動承認は行わない。
callerが対象を審査し、明示pinを設定する。configのenabled変更もhashを変更する。

pathの確認は**文字列の形式だけ**。存在・空き容量・symlink・所有権・新規性は
policyでは確認しない。storeが初期化前に実体を確認する。
runner/storeはconfigとstorage identityのpinを永続化・readbackし、既存storeの
異なるpinへの無断切替を拒否する。policyはファイルを書かないため、この永続性を
単独では保証しない。承認対象rootの変更は別contextと別承認を必要とする。

## artifactsとモデル/正規化の時点

active経路のcore artifactは次の5個のraw JSON object。

`model`, `normalizer`, `source_mapping`, `course_policy`, `prediction_config`

`prediction_config={}`のみ空を許容し、固定code commitにある既定設定を明示する。
その他は空/欠損を許容しない。`artifact_sha256s`に各raw objectのcanonical SHAを
すべて記載し、一致させる。SHAは元ファイルbytesではなく、canonical JSONの範囲。
元raw bytes、保存receipt、独立readbackの証拠は別途管理する。

prediction_configはtemperature/market_weight/selection/max_odds_age_secondsのみ。
数値の有限性と基本範囲を確認する。selectionの本体検証は既存kernelに委ねる。
runnerは実際に使用するmodel_configをこのartifactと照合し、model、normalizer、
source_mapping、course_policyも実際の使用対象と照合する。別のwやthresholdで
実行して承認済みconfigと称してはならない。

modelはCOURSE_BOUND_MODEL_V001の自己hash、course policy本体/SHA、training policy
SHAを照合する。学習済みcountと学習特徴/labelの最大利用可能時刻を確認し、
それらをnowより厳密に前とする。normalizerはNORMALIZER_V001/PROPOSED、自己hash、
training最大時刻 < fit cutoff < nowを要求する。
実際のモデル係数・normalizer statistics・source schemaの検証は各componentでも
行う。policyのmetadata合致を、学習の正しさや外部の時刻真正性と呼ばない。

## SIMULATIONだけの追加条件

approval bundleは不要だが、次の`simulation_context`を明示する。

```
{
  "classification": "SYNTHETIC_ONLY",
  "synthetic": true,
  "target_year": 2099,
  "temporary_store_registered": true,
  "storage_identity_sha256": "<pinned_storage_sha256>"
}
```

各boolは厳密にtrue。整数1を代用しない。登録metadataは一時storeの実体確認では
ないため、runner/storeは新しい所有対象temp storeであることを別途確認する。
実データを2099年/合成flagへ書き換える運用は禁止。
preflight合致は`SIMULATION_PREFLIGHT_ONLY`であり、実際のネットワークへ進まない。

## PRIVATE_SHADOW承認束の構造

追加artifact `evaluation_plan`, `formal_legacy_comparison`もraw JSONとしてhashする。
両者に`review_status=EXTERNALLY_REVIEWED_FOR_SHADOW`と`open_items=[]`を要求する。
これは**外部審査済みというcallerの主張**の形式であり、codeが審査を実施した
という意味ではない。未決のF2/F5を勝手に解決・正式採用してはならない。
必要なthreshold・F5評価計画・旧版比較証拠は外部審査で決定し、実物と照合する。

`approval_bundle`の正確なkeyはoperation/operator_id/valid_from/valid_until/bindings/
reviews/review_truth_attested_by_operator。operationは
`START_THIRD_RESEARCH_SHADOW`だけ。validityはaware時刻で`from <= now < until`。
operator_idはsafe ID、最後のboolはtrueを必要とする。

bindingsは次の10項目を全一致させる。

1. model_sha256
2. normalizer_sha256
3. source_mapping_sha256
4. course_policy_sha256
5. prediction_config_sha256
6. evaluation_plan_sha256
7. formal_legacy_comparison_sha256
8. config_sha256
9. storage_identity_sha256
10. code_commit

reviewsはHQ14/CLAUDE/ANDYの3件を揃える。各件の正確なkey:

`authority`, `reviewer_id`, `evidence_sha256`, `decision`, `operation`,
`bindings_sha256`, `valid_from`, `valid_until`

authorityは所属keyと一致、reviewer/evidenceはそれぞれ異なる値、decisionは
`APPROVED_FOR_THIRD_RESEARCH_SHADOW`、operationは上記の一操作だけ。
bindings_sha256はbindings objectのcanonical SHAに一致させ、全reviewがnowで
有効でなければHOLD。同じIDを別人とみなす等の自動補完はしない。
異なるID/SHAでも人間の独立性や承認原本真正性を証明することはできない。

## operator_ackの正確な構造

単なる文字列、enabled=true、過去の包括GOは代替にならない。

```
{
  "ack": "START_THIRD_RESEARCH_SHADOW",
  "operator_id": "<bundle operator_id>",
  "bindings_sha256": "<canonical SHA of bundle bindings>",
  "attested_at": "<aware ISO time>",
  "evidence_checked_outside_this_program": true
}
```

本人の明示操作で渡す。attested_atは承認期間内、各review有効開始以後、now以前。
ackのcallerが本人か、原本を本当に確認したかはこのcodeでは認証しない。
その外部確認が未完了なら、項目を捏造して先へ進めずHOLD。

## 状態と安全上の限界

- DISABLED: allowed=false、contextを参照しない。
- HOLD: 欠損、不正、未来/期限切れ、pin不一致、review不一致、ack不足等。
- SIMULATION_PREFLIGHT_ONLY: 合成temp contextの形式が整っただけ。
- PRIVATE_ATTESTED_PREFLIGHT_ONLY: 外部確認したというoperator申告が構造上整っただけ。

allowed=trueは「次componentへ同一contextを渡せる構造」であり、独立認証・実GOではない。
常にindependent_approval_authenticity=UNVERIFIED_NOT_AUTHENTICATED_BY_CODE、
actual_execution_go=NOT_ESTABLISHED_BY_PREFLIGHT、production_go=false、auto_start=false。
サービス接続・source fetch・store書込みをpreflightが呼ぶことはない。

現時点で実承認束・正式閾値・実source mapping審査・実旧版比較は未提供なので、
PRIVATEの実行可能性は**HOLD / 未承認**。合成test用の架空reviewによるallowedを
本物の承認や実行試験に読み替えない。署名鍵の新設・資格情報・実原本公開は行わない。

再現:

```
python -B -m unittest discover -s tests -p test_shadow_launch_policy.py -v
```

18件はpure計算、disabled短絡、I/O禁止spy、pin・artifact結合、時点、架空reviewの
構造、operator ack、非認証表示を確認する。利益、予測精度、本番接続、真正なGOは
試験していない。実施できた合成testのPASSと正式審査・実行承認は別判定である。
ISO offsetはhour<=23/minute<=59をparse前に検査する。Pythonが同じ時刻へ
正規化する`+08:60`等も不正入力としてHOLDし、承認・review・ackへ使用しない。
