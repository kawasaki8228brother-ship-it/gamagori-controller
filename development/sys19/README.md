# SYS-19 Python/依存関係テスト基盤 — 開発用

Python版別の標準ライブラリ試験、固定requirementsの完全SHA/19件/版照合、診断、既存テスト互換を別結果にする。
既存CIはmain基点の`.github/workflows/c-minimal-review.yml`。Pythonは3.12系指定でpatchは固定されていない。
実GitHub-hosted runnerは未起動。ローカル3.12.14を実CIの実測patchと認定しない。

`runtime_check.py`はUTF-8固定pinのみ受け付け、URL/編集可能install/marker/重複正規化名を拒否する。
実package名とversionのみ比較し、環境変数/認証URL/資格情報を読まない。pipは比較対象外、他の余分なpackageは不一致。
SHA空文字/abc known-vector、missing/extras/version差/Python差/原文SHA差を独立表示する。

requirements.reference.txtは既存PR #6 head 97640c8c307fed8eaa19f2557f5057ccade18da1 の読取参照。
340 bytes、SHA dba91fc609884c39b70c1660151e959779d86613fe0ce13c61626506123a2dc7。
依存先commitを明示した検証用参照で、PRのコードや他案件の実装を統合せず、root requirementsは変更しない。
既存の隔離Python3.14.3環境をread-onlyで再利用し、新規インストールはしない。clean install試験の代用とはしない。

```sh
python -B -m unittest -v test_runtime_check.py
```

`results/`に各実測runtime、unit log、既存pytest結果、OPENを記録する。失敗・未実行をPASSへ変換しない。
既存テストは基点mainのprivate隔離コピーだけで実行し、socket connectを禁止、DB/temp/cacheは新規隔離ディレクトリへ限定。
既存testsをrepoへ再掲載せず、rawログのローカルパスを伏せた派生ログはREDACTEDとして原stdoutのSHAも記録する。
ローカルSQLite/OpenSSLが本番と同じとは認定しない。Renderへの接続・本番適合確認・外部TLS試験は実施しない。

ci-proposal.yml.exampleは新規ディレクトリ内の不活性案で、正式Actions設定を一切変更しない。
案の採択・rootへ移動・実runner実行・pip installには別承認が必要。
復元は不要（既存コード/CI不変、未適用）。審査前に本番へ持ち込まず、この隔離枝を採用しないことで破棄できる。
certifi優先。Claude独立審査はcertifi終了後、全て本番GOとは別判定。

再現用既存テストの実行は、基点mainの全40 blobを照合した新規コピーでだけ行う。
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、guardを含むprivate PYTHONPATHを指定し、
`python -B -m pytest -q -p offline_guard -p pytest_asyncio.plugin --basetemp <新規temp> -o cache_dir=<新規cache>`。
ここで`offline_guard.py`はこのSYS-19資料のguardを指す。実checkoutや本番DBのpathを渡さない。
検査用module/test以外の他案件コードは組み込まず、既存コードはprivateコピーからのみ実行する。
初回計測：3.12.14/3.13.5/3.14.3でstdlib 6 tests各PASS。
3.14.3は19件完全一致・既存248 tests PASS。3.12/3.13のfull suite、clean install、実hosted CIは未実行。
したがって作業群全体の状態はOPEN、部分的な開発検証済み。

`python -B probe_runtime.py`は現在のlocal環境を照合し、一致ならexit0、不一致/入力拒否ならexit2。
不一致診断をCI成功へ読み替えない。実測CLI: 3.12/3.13はexit2、固定環境3.14.3はexit0。
