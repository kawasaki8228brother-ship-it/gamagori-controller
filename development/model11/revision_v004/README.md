# Model1.1 v004 N1限定修正候補

親62721c20676177bac171f97b0488412b07b63594。変更コードはrevision_v003/course.pyだけ。
元v003commitとbranchは無変更。元courseはreferences/course_v003_original.py.txtへ同一バイトで保全。
その他134ファイル、保存済み予測・出力・旧テストはバイト不変。
旧v003SHA一覧は親commitの原本用であり、v004で意図的修正したcourse.pyには適用しない。旧SHA一覧自体は書き換えない。

N1：分類はSYNTHETIC_ONLY+synthetic=true、PRIVATE_REAL+synthetic=falseのみ。
前者は登録済みSYNTHETIC source、後者は登録済みOFFICIAL sourceに限定。prefixだけの未登録sourceは拒否。
frame/exhibitionの全非null観測を、選択・未使用にかかわらず確認する。
未知／欠損分類、非bool／欠損flag、矛盾、未知source、分類source不一致はHOLD。固定コードと固定理由だけを返し、秘密値をechoしない。
正常時のreport/schema/予測出力は変えない。3course policy定義・hash・選定規則も不変。
OFFICIALという名前・hashの形は真正性や正式承認ではない。external_authenticity=UNVERIFIED、実データengine/walk-forward HOLD維持。

## 再現

```sh
cd development/model11
python -B run_checks.py
python -B -m unittest discover -s tests -p test_revision_v004_n1.py -v
```

全346テスト（旧339+N1の7）、Python3.12.14／3.14.3でPASS。
新7method内に全policyと選択／未使用source、fit/distributions/conditionals/explain/engine/walk-forwardの反例を含む。
全入力は2099年の架空fixture。PRIVATE_REAL表示は攻撃メタデータで実データではない。
F1、F3の他部分、F4、通常5点、BOXは変更しない。F2/F5は未採用。
Claude再審査、実source mapping・独立原本証拠・実データ適合・ShadowGOはOPEN。
PR・merge・deploy・本番操作は行わない。
