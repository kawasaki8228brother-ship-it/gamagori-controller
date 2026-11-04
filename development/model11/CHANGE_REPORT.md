# 変更範囲

基点：main `8172aec010894a52f36f48b7091476d26494e4ee`。
基点にはdevelopment/model11/が存在しない。今回の差分は同prefixへの新規追加だけ。
旧版アプリの改変diffは0。既存40blobのpath/mode/type/SHAを新treeと照合して不変を確認する。
GitHubのcommit差分が追加内容全行の正確な差分になる。別SYSやP3評価器からコードを統合していない。

新規package：models/probabilities、validation、selection、metrics、engine、walkforward、synthetic、cli。
標準ライブラリだけ。正式requirements、CI、render.yaml、main.py、Model1.0/BOXv1/A/B原本は変更対象外。

再現テストはPython3.12.14と既存のPython3.14.3実行体を読取使用。venvの作成・更新・pip操作は行わない。
これは旧certifi成果やアプリコードの統合ではない。

残余：正式原本・実データ・時点の外部真正性・実性能・Claude審査・本番昇格GOはOPEN。
破棄方法：隔離研究ディレクトリ／出力／新規branchだけが対象。削除は後日の指示に従う。
本番を変更しないため、本番rollback／復元は不要でありその操作は実装しない。
