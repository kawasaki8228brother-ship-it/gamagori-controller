# N1 lineage: why the frozen V003 list currently shows 45/46

Local verification confirms **46 listed entries, 45 direct matches, and one expected N1 supersession**. The sole mismatch is `model11/revision_v003/course.py`: the V003 list intentionally records its historical bytes, while N1 V004 changed that path. This is an explained version transition, not an unexplained corruption finding. No historical SHA list, archive, source, or policy was rewritten by this task.

The original V003 content remains preserved as an exact V004 archive. Reconstructing the historical snapshot from the unchanged 45 current files plus that archive for the course entry verifies all **46 historical expected hashes**. This is different from claiming that the 46 current paths directly match the V003 list.

## The two separate 45/46 counts

- `MANIFEST_V003.json` declares 45 added payload files.
- `SHA256SUMS_V003.txt` contains those 45 payload files **plus `MANIFEST_V003.json` itself**, giving 46 rows; it excludes its own SHA-list file. No missing payload accounts for the extra row.
- At the current N1 tree, 45 of the 46 SHA rows directly match. The one current-path mismatch is the declared N1 course change, resolved against the preserved original archive.

| Check | Measured result |
|---|---|
| Frozen V003 SHA list | 4,928 bytes; SHA-256 `4e0bbddde7ab29596b1185fbdf3edb186e67d07544d636ebd66a29af42ba1b9b` |
| V003 list entries | 46 |
| Direct current-path matches | 45 |
| Expected declared N1 supersession | 1 (`course.py`) |
| Unexplained mismatches | 0 |
| Reconstructed historical matches | 46 (45 unchanged current files + one original archive) |
| V004 SHA-list verification | 16/16 direct matches |

## Exact course lineage and Git blob evidence

| Version/content | Bytes | SHA-256 | Recomputed Git blob SHA-1 |
|---|---:|---|---|
| V003 original / preserved archive | 17,860 | `48b53e1b372c9c8b63027567d920514ac4e23668f0373d9f4f9a559789f0f66b` | `e4853916e7d8b0f335a7c49d6e4855c40f51cff1` |
| N1 V004 / retained V005 current target | 20,110 | `ca28937aa1784fc37fa9a9539e0219d27570390ced01b3a0a2f77268238ed264` | `59d9e564d9370655b5deb84cfb61bd26ac1c2760` |

Git blob IDs are recomputed from the raw bytes using SHA-1 of `blob <byte-count>\0<raw-bytes>`. The original archive matches both the V003 payload metadata and V004 `changed_source_parent`/archive metadata. The new target matches the V004 modified-file metadata and V005 manifest metadata. The preserved N1 unified diff regenerates byte-for-byte from old archive to current target (2,776 bytes; SHA-256 `e4c279b65a08d044bf6931885679435da8750261e74ba57dd47c2ea8f2d9248e`).

These checks use local raw bytes and already published parent manifests as distinct evidence objects. This subtask performs no new remote fetch and does not turn a local hash or manifest into independent authentication or production approval. The prior N1-only development scope explains the declared source transition; no new model fix or policy change is introduced here.

## Commit-fixed raw originals

| Object | Fixed raw URL |
|---|---|
| V003 original course | [62721c2 original](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/62721c20676177bac171f97b0488412b07b63594/development/model11/model11/revision_v003/course.py) |
| V003 frozen SHA list | [62721c2 SHA list](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/62721c20676177bac171f97b0488412b07b63594/development/model11/revision_v003/SHA256SUMS_V003.txt) |
| V003 manifest | [62721c2 manifest](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/62721c20676177bac171f97b0488412b07b63594/development/model11/revision_v003/MANIFEST_V003.json) |
| N1 V004 updated course | [df80708 updated course](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/df807089f5fd27517109f9bd38b6c55f9415600e/development/model11/model11/revision_v003/course.py) |
| N1 preserved original archive | [df80708 original archive](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/df807089f5fd27517109f9bd38b6c55f9415600e/development/model11/revision_v004/references/course_v003_original.py.txt) |
| N1 exact diff | [df80708 N1.diff](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/df807089f5fd27517109f9bd38b6c55f9415600e/development/model11/revision_v004/N1.diff) |
| N1 manifest | [df80708 manifest](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/df807089f5fd27517109f9bd38b6c55f9415600e/development/model11/revision_v004/MANIFEST_V004.json) |
| N1 SHA list | [df80708 SHA list](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/df807089f5fd27517109f9bd38b6c55f9415600e/development/model11/revision_v004/SHA256SUMS_V004.txt) |
| V005 retained current course | [f3c3a3e current course](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/f3c3a3eb17073bd0a127bb943f4eda21e407cf2d/development/model11/model11/revision_v003/course.py) |
| V005 retained original archive | [f3c3a3e archive](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/f3c3a3eb17073bd0a127bb943f4eda21e407cf2d/development/model11/revision_v004/references/course_v003_original.py.txt) |
| V005 manifest | [f3c3a3e manifest](https://raw.githubusercontent.com/kawasaki8228brother-ship-it/gamagori-controller/f3c3a3eb17073bd0a127bb943f4eda21e407cf2d/development/model11/shadow_launch_v005/MANIFEST_V005.json) |

All links contain full commit IDs. URL availability is not independently re-fetched in this subtask; byte/Git-blob bindings are verified locally against the existing manifests.

## Course policies remain unchanged

Archived and current policy objects are equal, and all three policy hashes match the published V004 before/after record:

| Policy | Archive = current SHA-256 |
|---|---|
| `EXHIBITION_ELSE_FRAME_V001` | `97ed0546cdf6831000a90a42532fbb1f6f95740545935d2d2fa0d03b9e2a8997` |
| `EXHIBITION_ONLY_V001` | `cdd3bb6b1e660445d428d31757447c4d7b93a8b23b436b22cc1c2a65e2b77aef` |
| `FRAME_ONLY_V001` | `1d7561a7ee56622f0b3eb8af88b8ca472255d8f8da5620d9693794133d4870b0` |

## Complete 46-row V003 SHA inventory

The machine-readable [N1_LINEAGE.json](results/N1_LINEAGE.json) additionally records every raw current byte count, SHA-256, Git blob ID, expected historical SHA, resolution, and V003/V005 fixed raw URL. `DIRECT` below means current raw bytes match the frozen SHA; `N1` refers only to the archive-reconciled supersession described above.

| # | Historical list path | Expected V003 SHA-256 | Current resolution |
|---:|---|---|---|
| 1 | `model11/revision_v003/__init__.py` | `0c6a02c0be6315d7fff14c72d66c8a3ea4066d49c3bd350625b09c2bb2ea3ca1` | DIRECT |
| 2 | `model11/revision_v003/cli.py` | `0b1cbc3752c201f3f8fc019b6bbe80cd665da06daacb6533b0d12978974fe9ef` | DIRECT |
| 3 | `model11/revision_v003/course.py` | `48b53e1b372c9c8b63027567d920514ac4e23668f0373d9f4f9a559789f0f66b` | N1: current ca28937aa1784fc37fa9a9539e0219d27570390ced01b3a0a2f77268238ed264 |
| 4 | `model11/revision_v003/engine.py` | `33b70ce2ac99c3c61c2fad43b8b3ea798537571846245e0c25d703f0642f5de6` | DIRECT |
| 5 | `model11/revision_v003/evaluation.py` | `0ba27af735db616d6a1c992b5f1f5aebc1272f15c51640520dcd55d59c40ea24` | DIRECT |
| 6 | `model11/revision_v003/fixtures.py` | `89eedc81eee04fea193bfb000fd5c1c1e4202be2f88de5ed54bf1f0eed613a67` | DIRECT |
| 7 | `model11/revision_v003/migration.py` | `c85c390f26cebe2d7c4d581fdc9445d1b05586ad41102108c49c16e8b9b1ec52` | DIRECT |
| 8 | `model11/revision_v003/pooling.py` | `e1c0962a117978d1caf6685f76a0289dca703a274090a0a67d898dbca68c7704` | DIRECT |
| 9 | `model11/revision_v003/portfolios.py` | `9183d8fda55a945f768830da5a761f44176fae6656b63397184c282f72b5ff2c` | DIRECT |
| 10 | `model11/revision_v003/walkforward.py` | `8719f9117968b379c72a37cd34e8e14cebab3284db5e35fcfe6fd831509db96b` | DIRECT |
| 11 | `revision_v003/AUDIT_RESPONSE.md` | `7f4b15b082bf524f2d03821ba709e3f8a49b2fe857dbd9011fe8ea19b0b3877d` | DIRECT |
| 12 | `revision_v003/F1_MARKET_WEIGHT.md` | `5892611492c54d932cbec15332b025fae8a0ab007fdd7168649f31afa950f902` | DIRECT |
| 13 | `revision_v003/F2_BOX_DESIGN_PROPOSED.md` | `fcbb0bfa5bb967ef18a008817fb7fe55f300ff5b20c7423d6a41a25c21617f19` | DIRECT |
| 14 | `revision_v003/F3_COURSE_CONTRACT.md` | `bd4ca256ec4395aa00f2780be864d239a79c3a25118347b92260280b4ea51838` | DIRECT |
| 15 | `revision_v003/F4_SCHEMA_MIGRATION.md` | `4f79b05652a5e7a7619c94ca531cba0108d7ec1a5098b13e78efcd9d17d929c5` | DIRECT |
| 16 | `revision_v003/F5_SELECTION_PREREG_PROPOSED.md` | `e3612741bacd16606e0246c2cafe49988b6d8d3535a652bf2be1c7e9db44e77c` | DIRECT |
| 17 | `revision_v003/INDEX.md` | `b7f1f4893b4cb1027837b75019d6a3be571889c0631cec9cb94480a94527d15e` | DIRECT |
| 18 | `revision_v003/MANIFEST_V003.json` | `5f826c0797ffe44ed0d35300d99bcafbc835521ab23b315509b966158b297499` | DIRECT |
| 19 | `revision_v003/README.md` | `7d74289c5e70e3af9a2181e6f5f4a993a6c241ab1cfe7659d70fbe80e8abf801` | DIRECT |
| 20 | `revision_v003/REPORT.md` | `1fc76adfa4c7991be1a0a454403d5337ccfc62733f7dfe01db17e4d1facd7506` | DIRECT |
| 21 | `revision_v003/REVIEW_FINDINGS.md` | `9b7e7f22c35614791ce0a73fefcbcab9c5c1a47e67b69895bc334f5bfdc592ce` | DIRECT |
| 22 | `revision_v003/SOURCE_DIFFS/F1_walkforward.comparison.diff` | `5885162d266f47ed641ab5650bc4baf13f06604e33b715fca931951db14b251a` | DIRECT |
| 23 | `revision_v003/SOURCE_DIFFS/F4_portfolios.comparison.diff` | `9e3ab68b7882ea7d3242fb794d0fd04c38009e051d661ecde98441ef476a65ec` | DIRECT |
| 24 | `revision_v003/results/F1-market-only-evidence.json` | `3fdb5baf08392e10c3a8550a3e5da1b27770549ef386ef967dfec993a3d3d156` | DIRECT |
| 25 | `revision_v003/results/F4-manual-input-SYNTHETIC-ONLY.json` | `7ff13595607e8a925f4d0ed9309f5a2d38835d71d01e6d6118a9bf039f08c44d` | DIRECT |
| 26 | `revision_v003/results/F4-old-artifact-migration.json` | `0206494739497607d25e61bb239b5f67f4658d393937edd803fe84c8e7c6c9d7` | DIRECT |
| 27 | `revision_v003/results/F4-separate-manual-and-automatic.json` | `e51c4edb3266673437815119fc8b388f8a79df69d3ce6e9406afb698992dd670` | DIRECT |
| 28 | `revision_v003/results/artifact-provenance.json` | `97becf022887dddfac7c34cd47acf720e36d63934f3fe863d55a467bbbe6857a` | DIRECT |
| 29 | `revision_v003/results/demo-python312.raw.log` | `52e9418128c497db04f69249eddc876edce1dcbb36c3be539d1e740100d2d38a` | DIRECT |
| 30 | `revision_v003/results/demo-python314.raw.log` | `7ba4e1eb866c7a914907cee89fc9acc4cb372de144ad4499997c39c17bf9e839` | DIRECT |
| 31 | `revision_v003/results/evaluation-summary.json` | `ad65b891c44ec8838eefb1b74d3f76d9922d50277629c41088de6c8b1f084888` | DIRECT |
| 32 | `revision_v003/results/fold-selection-audit.json` | `1068b26fbcaad615e2f3dbbd7c2c8026396f71480aaa54cc6d85104257c77e37` | DIRECT |
| 33 | `revision_v003/results/prediction-v003.json` | `864b9011465615f828ed34e792b8c66efb73f5c50fdb41172ed1f37d6185fc55` | DIRECT |
| 34 | `revision_v003/results/preservation.json` | `db3ee51f121c08b058fd57fb8009fcdba7ba7fd0d5e9d09cf70812e48694c9a1` | DIRECT |
| 35 | `revision_v003/results/selected-model-v003.json` | `8b3fc58d8ad6c44f6c6cde8f9aa52aa0c1955b433fef92bf19f5615e288902cd` | DIRECT |
| 36 | `revision_v003/results/selected-pipeline-v003.json` | `3d0e338c63bd4d7eaa0c09aeb2ccfd407bd4770cdf5619c6f8b0da21b6599216` | DIRECT |
| 37 | `revision_v003/results/synthetic-outcome-separate.json` | `3852b14e646a39324ecf8cbe1ba869913de909314f5153acc1fc7f592107ab52` | DIRECT |
| 38 | `revision_v003/results/synthetic-race-v003.json` | `f5f9655b0002d7939efab19649246e685965263772e8841d176bf4990959944c` | DIRECT |
| 39 | `revision_v003/results/tests-python312.raw.log` | `5d161110d6a58ac587cd1ee748f8bf7f6c72bcc64e135f9d476c41272ea8e7d1` | DIRECT |
| 40 | `revision_v003/results/tests-python314.raw.log` | `83c68fa171e1ea0ae803fa463ec283669bef92eb0fadfe783ed11228c40691be` | DIRECT |
| 41 | `revision_v003/results/verification.json` | `ed5689cd1715ce4279e55d4d2de18ea4bd2d60106e7b94d1ffd0ab4d8a78b168` | DIRECT |
| 42 | `revision_v003/results/walk-forward-summary.full.min.json` | `503b0b04303522e20d4d20b9d5cc874ec4c11cb5714c68727c81e83fbfe197bc` | DIRECT |
| 43 | `tests/test_revision_v003_course.py` | `7829c0efe85cfb3d0da81dab67776ea4f4d2f2d04ff2d6f997eff44dbe4819a3` | DIRECT |
| 44 | `tests/test_revision_v003_integration.py` | `3a1c860fc5dbd1da98e47e480d67a58f406ac12d4cfa0ebacd6a437e792672ec` | DIRECT |
| 45 | `tests/test_revision_v003_portfolios.py` | `85438d8c876799225a324e059b38af36eb5e3bd4f43d06e1662e90f011e2896b` | DIRECT |
| 46 | `tests/test_revision_v003_walkforward.py` | `7db848cea8302d099305c1c1ac887a91f8a63473a5d2d126132384266c3e2436` | DIRECT |

## Reproduce and interpretation limits

```text
python -B -m unittest discover -s tests -p test_shadow_preparation_lineage.py -v
```

Executed locally: **8 test methods PASS**, Python 3.12.14, Linux 6.18.57 x86_64/glibc 2.41. Checks cover all 46 rows, the 45-plus-manifest count, both raw Git blob identities, exact N1 diff, all three policy objects/hashes, preserved historical lists, V004 16/16, and the new evidence row bindings.

No remote service, actual race data, model calculation change, old SHA-list repair, archive overwrite, live execution, or production action is part of this work. A direct `sha256sum -c` against V003 paths after N1 will correctly report the one historical course mismatch. Use the lineage-aware check above to distinguish that expected supersession from an unexplained alteration. Do not replace the old SHA with the new SHA inside the historical list.
