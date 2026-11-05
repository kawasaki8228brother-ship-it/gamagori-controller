# 合成保存証拠の原本受渡し

`results/SYNTHETIC_ONLY.prediction-evidence-python312.json.gz.b64.txt`と314版は、
新規一時storeで生成した架空2099年12Rの読取export JSONをgzip＋base64で保全したもの。
実レース原本・本番DB・秘密値・実backupではない。source、mode、classificationを合成として確認済み。
元JSONのbytes/SHAと符号化ファイルのbytes/SHAは`results/TEST_RESULTS.json`に別記する。
符号化→復号で元JSON bytesと一致することを提出前に検査する。

明示した新規一時ファイルだけへ復元する例（既存ファイルは上書きしない）:

```
python - <<'PY'
import base64, gzip, hashlib
from pathlib import Path
source = Path('shadow_preparation_v006/results/SYNTHETIC_ONLY.prediction-evidence-python312.json.gz.b64.txt')
raw = gzip.decompress(base64.b64decode(source.read_bytes()))
with Path('/tmp/model11-v006-decoded-NEW.json').open('xb') as output:
    output.write(raw)
print(len(raw), hashlib.sha256(raw).hexdigest())
PY
```

そのSHAをTEST_RESULTSの`decoded_original`と照合し、対応する312版の予定fixtureと組み合わせる。
checker自体はJSONを読むだけで、復元・store作成・予測・補完は行わない。
符号化ファイルと元JSONを同じSHAと報告しない。

12R再生成器ではstore所有IDと一時保存rootのhashが毎回変わるため、別実行のexport全bytesは一致しなくてよい。
固定された提出原本の復号一致と、別実行で同じ検証結果を再現することを区別する。
すべての予定承認metadataはfixtureの架空申告であり、実公式承認や外部真正性の証拠ではない。
