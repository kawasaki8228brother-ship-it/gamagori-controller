# E7：ローカルruntime・依存関係の実測区分

これはオフライン開発環境の記録であり、現在のRender実体や本番適合の証明ではない。実タスク・Renderへの接続、ネット導入、既存環境のinstall/変更、requirements/CI設定の変更は行わない。調査・対象試験はnice=10で実行した。

## 宣言・過去情報・現在実測

- 現在の `render.yaml` には `PYTHON_VERSION` がない。宣言だけから本番Pythonのpatch版を特定できない。
- `.github/workflows/c-minimal-review.yml` の宣言はPython `3.12`。patch版を固定しておらず、今回GitHub runnerの実体は確認していない。
- 過去に観測されたRender Python 3.14.3は過去情報であり、現在の本番版の証明として使わない。
- 以下の3.12.14／3.14.3、OpenSSL、依存版は、今回アクセス可能な**ローカル環境**の実測である。

| 環境 | Python | OpenSSL | 今回の位置付け |
| --- | --- | --- | --- |
| system既存 | 3.12.14 | 3.5.8（25 Aug 2026） | pytest・bs4等が不足する当初の観測。既存環境は変更しない。 |
| 新private offline venv | 3.12.14 | 3.5.8（25 Aug 2026） | 新規のpure依存コピー＋system-site読取参照。既存cp312 coreをそのまま使用。 |
| 既存314 venv（読取専用） | 3.14.3 | 3.5.5（27 Jan 2026） | ローカル版比較とpure依存コピー元。変更・installしない。 |

## 5直接requirementsと19件の観測は別

既存 `requirements.txt` は5行・90 bytes。SHA-256は
`125749db489c1885b54524b46ce4ed032896e2cf12d72021a69590e72220febd`。
内容は変更していない。

| 直接指定 | 期待版 | 新312 | 既存314 |
| --- | --- | --- | --- |
| pydantic | 2.13.4 | 一致 | 一致 |
| httpx | 0.28.1 | 一致 | 一致 |
| beautifulsoup4 | 4.14.3 | 一致 | 一致 |
| pytest | 9.0.2 | 一致 | 一致 |
| pytest-asyncio | 1.3.0 | 一致 | 一致 |

選択した19件のメタデータ実測は次のとおり。これはrequirementsに19件を新たに固定したという意味でも、全環境に19件しか存在しないという意味でもない。

| パッケージ | system 312・変更前 | 新private 312 | 読取専用314参照 |
| --- | --- | --- | --- |
| Pygments | 2.21.0 | 2.21.0 | 2.21.0 |
| annotated-types | 0.8.0 | 0.8.0 | 0.8.0 |
| anyio | 4.14.2 | 4.15.1 | 4.15.1 |
| beautifulsoup4 | 未導入 | 4.14.3 | 4.14.3 |
| certifi | 2026.7.22 | 2026.10.23 | 2026.10.23 |
| h11 | 0.16.0 | 0.16.0 | 0.16.0 |
| httpcore | 1.0.9 | 1.0.9 | 1.0.9 |
| httpx | 0.28.1 | 0.28.1 | 0.28.1 |
| idna | 3.18 | 3.20 | 3.20 |
| iniconfig | 未導入 | 2.3.0 | 2.3.0 |
| packaging | 26.3 | 26.3 | 26.3 |
| pluggy | 未導入 | 1.6.0 | 1.6.0 |
| pydantic | 2.13.4 | 2.13.4 | 2.13.4 |
| pydantic_core | 2.46.4 | 2.46.4 | 2.46.4 |
| pytest-asyncio | 未導入 | 1.3.0 | 1.3.0 |
| pytest | 未導入 | 9.0.2 | 9.0.2 |
| soupsieve | 未導入 | 2.9.2 | 2.9.2 |
| typing-inspection | 0.4.3 | 0.4.4 | 0.4.4 |
| typing_extensions | 4.16.0 | 4.16.0 | 4.16.0 |

新312は、5直接指定全一致に加えて、上記19件の版も314参照と一致した。19件について現在のdefault markerで適用される依存制約をローカルメタデータで検査し、違反なしを確認した。extrasを含む全installed世界のpip check、完全隔離、外部配布元真正性、現在CI／Renderとの一致を検証したという意味ではない。

## 新312環境の作り方と限界

新規private配下だけに、system-site-packages参照を有効にしたvenvを作成した。pip導入・ネットinstallは行わない。欠ける／版が異なるpureな10 distribution（beautifulsoup4、soupsieve、pytest、pytest-asyncio、pluggy、iniconfig、anyio、certifi、idna、typing-inspection）の258ファイルを既存314から新環境へ排他的コピーし、copy先readbackとcopy元bytesの前後一致を確認した。

cp314のnative extensionはコピーしていない。既存system側の一致するpydantic_core 2.46.4を読取参照し、cp312用extensionで実importできることを確認した。native extensionコピー件数は0。

この方式は**完全隔離ではない**。system側の追加パッケージが可視であり、未指定のimportやpluginの影響余地が残る。対応としてpytest autoloadを無効にし、必要なasyncio pluginのみ明示し、bytecode/cache書込を抑制する。それでも公式wheelからの新規クリーンinstallや、19件だけの厳密環境と同等とは主張しない。

非公開調査receiptのローカルfingerprint：

| 調査記録 | bytes | SHA-256 |
| --- | --- | --- |
| runtime312-metadata.json | 1,740 | e8a2504b58eff0e66a639d08e32ed33c037a0a59528a262ee2e354e4b8aa10f5 |
| runtime312-copy-receipt.json | 2,489 | 01a2bfbef951189aba496c7acc737f200154ea028fb860f1ab7b4aa9e70f3e8e |

実体パス・環境変数一覧・秘密値は本資料に収録しない。既存のcertifi作業venvは読取専用のままで、変更していない。

## 対象試験と再現条件

D6対象の `tests/test_health_v003_spec_reference.py` は、新312と既存314の各環境で **5 passed, 1 skipped** を実測した。skipは未提供208-byte正式原本であり、正式本文一致PASSとして数えない。全体pytestの実測は親作業の別ログで管理し、本資料の対象試験だけから全体成功を主張しない。

次は、操作者がローカルinterpreter変数を設定して使うcommand templateである。private pathを公開するものではない。

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
nice -n 10 "$HEALTH_RUNTIME_312_PY" -B -m pytest \
  -p pytest_asyncio.plugin -p no:cacheprovider -q -rs

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
nice -n 10 "$HEALTH_RUNTIME_314_PY" -B -m pytest \
  -p pytest_asyncio.plugin -p no:cacheprovider -q -rs
```

Python patch、OpenSSL、system-site参照、全依存世界、現在CI／Renderの実体は別々の確認対象である。現在の本番patchが未確認のまま最終本番適合PASSにしない。source-provenance、正式208-byte本文照合、本番操作GOも本記録ではUNVERIFIED／未承認のまま維持する。
