# v004 N1 INDEX

- [README](README.md)
- [報告](REPORT.md)
- [最小修正diff](N1.diff)
- [旧course原本](references/course_v003_original.py.txt)
- [独立開発レビュー](INDEPENDENT_REVIEW.md)
- [N1分類/source再現matrix](results/N1-matrix.json)
- [policy hash不変](results/policy-hashes.json)
- [全試験・出力不変証拠](results/verification.json)
- [Python3.12生ログ](results/tests-python312.raw.log)
- [Python3.14生ログ](results/tests-python314.raw.log)
- [3.12正常demo生ログ](results/demo-python312.raw.log)
- [3.14正常demo生ログ](results/demo-python314.raw.log)
- [全file一覧](MANIFEST_V004.json)
- [SHA256SUMS](SHA256SUMS_V004.txt)

元原本135件は親commitで不変。新branch内では対象courseだけN1修正し、旧同ファイルをbyte一致で別保全。
新manifestは意図的変更1件と保持134件、新規資料を区分。自身とSHA256SUMSは除外し、自己SHAは提出receiptに記載。
