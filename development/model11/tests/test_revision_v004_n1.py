"""N1 classification-source boundary checks using invented 2099 fixture copies only.

PRIVATE_REAL labels below are adversarial metadata, never actual real race data.
All success claims are local software observations; external authenticity and
production permission remain UNVERIFIED/false. Existing files are not rewritten.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import types
import unittest

from model11.revision_v003.course import (COURSE_POLICIES, CourseBoundModel,
                                         apply_course_fixture, canonical_hash, validate_course)
from model11.revision_v003.engine import predict_v003
from model11.revision_v003.fixtures import make_dataset_v003
from model11.revision_v003.walkforward import walk_forward_v003


# Portable exact parent62721c baseline, excluding the sole N1 edit target.
UNCHANGED_134 = {
  "ACCEPTANCE.md": {
    "bytes": 2545,
    "sha256": "ce2122e6fb40849d51743641cfbc935eeccea226acfd9d416a848f8ae9363c2e"
  },
  "BOX_RESEARCH.md": {
    "bytes": 6123,
    "sha256": "9d2c1a1191760c78414c3407eec1ec9781958e66f1c76bf18f1f1535d9261d55"
  },
  "CHANGE_REPORT.md": {
    "bytes": 1238,
    "sha256": "4d1c8aabd5ec3b7f0948bb2b931224b3357b90ca5c8548374e607b9fcae4515f"
  },
  "EVALUATION.md": {
    "bytes": 8777,
    "sha256": "2e39bf236067b88c7a640cc5e57742cc2d3bef2ca3cda1ae27f188a572fb6e07"
  },
  "FIRST_REPORT.md": {
    "bytes": 5169,
    "sha256": "e2d83bf395a823d72b621cb1edd0800cf049fdbc67fc8ceae60837ee8f18e855"
  },
  "INDEX.md": {
    "bytes": 2408,
    "sha256": "6ebbc88bb13419ddcb504a5aef7de63addad14d9b3854ef52802b33ce76be179"
  },
  "INPUT_SCHEMA.md": {
    "bytes": 9213,
    "sha256": "e1362b3eecc4e738b0aa7b44955cfb946bcba8c0cb601a4c785cbe241594fbe3"
  },
  "MANIFEST.json": {
    "bytes": 13552,
    "sha256": "9b60545e5277418fd3e36612b216f2dbb16e5116d46b8971f16306f4cfe3e82f"
  },
  "MODELS.md": {
    "bytes": 4378,
    "sha256": "6f1f5f4acdd566d8e43dbc23104a31e7235d202de348e6148c7fea45c2ee3e82"
  },
  "README.md": {
    "bytes": 5963,
    "sha256": "d82e89968464ab439ad90a10c096f22b27237eb0bc38753b2dcfa6be771a369e"
  },
  "RESEARCH_PLAN.md": {
    "bytes": 5727,
    "sha256": "e03233e37633a362a1437402c1a56e1e8010f78d6ba87c6798dd975fdf867782"
  },
  "SHA256SUMS.txt": {
    "bytes": 4161,
    "sha256": "f5c7360bef149e7352c7659c93f8ae9c66779e290b70cf7b42e56c189b639daf"
  },
  "model11/__init__.py": {
    "bytes": 117,
    "sha256": "a58893126700f9785fa8c8342813bf65abf1330cecae1695da9c0cf8cbee34de"
  },
  "model11/cli.py": {
    "bytes": 5033,
    "sha256": "30b9bb5e0bd9c15d2600fd0cad9f57a9b2de4a551cbf1a5d5e5070d64dff011d"
  },
  "model11/engine.py": {
    "bytes": 6987,
    "sha256": "6202700406692b7254aff28cb05302afd72b188379ab661832b3101f42072143"
  },
  "model11/metrics.py": {
    "bytes": 25878,
    "sha256": "089aaf12f9e9e2666c6bb44a0c40b49698afc888a5a254f4521f3d2f5f589e71"
  },
  "model11/models.py": {
    "bytes": 16730,
    "sha256": "c4ed50f5123e4b35d8710dea3dcb0ce27dd1eb7433cc7769d97ab33e8bc1566f"
  },
  "model11/preparation/__init__.py": {
    "bytes": 188,
    "sha256": "89bb1d18dd4b2c819f084789a575d1c6c5863f34dd60c4e5a9bfe1da674c7e61"
  },
  "model11/preparation/adapter.py": {
    "bytes": 28485,
    "sha256": "fe1859cd0aa321f5fa0de4d34f96b25e5ad94ed6229d087553c5f1b8196ec557"
  },
  "model11/preparation/cli.py": {
    "bytes": 9852,
    "sha256": "a7ed1eddd8ee1bc33dfbd148a1657e384b2846edbb064744c5ec8ae079642278"
  },
  "model11/preparation/legacy.py": {
    "bytes": 27042,
    "sha256": "02ec7babfb7935adcc4162427498c566ad331f623da74437bb9919073a02e411"
  },
  "model11/preparation/planning.py": {
    "bytes": 13040,
    "sha256": "1e9380622ea4b82eb2216609217e4cd0fc4e454cef37c003199b62f6fe0c16d8"
  },
  "model11/preparation/sensitivity.py": {
    "bytes": 27980,
    "sha256": "00503c4f6fcda5c3c6567d9c6bdca6616d38352731c1aeb1d6342cc7b940d40e"
  },
  "model11/preparation/shadow.py": {
    "bytes": 20324,
    "sha256": "c23b3bfbf18133f1a661c7866e7516853315677862375b4dd99b73575e498a07"
  },
  "model11/probabilities.py": {
    "bytes": 6329,
    "sha256": "979e7b459d0bc5606d6fe665091872fc2d4bb65f92c6298698a2a17625a88084"
  },
  "model11/revision_v003/__init__.py": {
    "bytes": 171,
    "sha256": "0c6a02c0be6315d7fff14c72d66c8a3ea4066d49c3bd350625b09c2bb2ea3ca1"
  },
  "model11/revision_v003/cli.py": {
    "bytes": 7400,
    "sha256": "0b1cbc3752c201f3f8fc019b6bbe80cd665da06daacb6533b0d12978974fe9ef"
  },
  "model11/revision_v003/engine.py": {
    "bytes": 6756,
    "sha256": "33b70ce2ac99c3c61c2fad43b8b3ea798537571846245e0c25d703f0642f5de6"
  },
  "model11/revision_v003/evaluation.py": {
    "bytes": 7842,
    "sha256": "0ba27af735db616d6a1c992b5f1f5aebc1272f15c51640520dcd55d59c40ea24"
  },
  "model11/revision_v003/fixtures.py": {
    "bytes": 1705,
    "sha256": "89eedc81eee04fea193bfb000fd5c1c1e4202be2f88de5ed54bf1f0eed613a67"
  },
  "model11/revision_v003/migration.py": {
    "bytes": 6337,
    "sha256": "c85c390f26cebe2d7c4d581fdc9445d1b05586ad41102108c49c16e8b9b1ec52"
  },
  "model11/revision_v003/pooling.py": {
    "bytes": 2785,
    "sha256": "e1c0962a117978d1caf6685f76a0289dca703a274090a0a67d898dbca68c7704"
  },
  "model11/revision_v003/portfolios.py": {
    "bytes": 8328,
    "sha256": "9183d8fda55a945f768830da5a761f44176fae6656b63397184c282f72b5ff2c"
  },
  "model11/revision_v003/walkforward.py": {
    "bytes": 13998,
    "sha256": "8719f9117968b379c72a37cd34e8e14cebab3284db5e35fcfe6fd831509db96b"
  },
  "model11/selection.py": {
    "bytes": 13969,
    "sha256": "4a9a30ce262741024c9de18f516f6ecd7c07a639147b56ae80a0d5c2e0a9100a"
  },
  "model11/synthetic.py": {
    "bytes": 10200,
    "sha256": "f74505fbd742f841717f7bd862171f0e12ea40c7ab3aaaf24a2712d7e442993c"
  },
  "model11/validation.py": {
    "bytes": 20159,
    "sha256": "ed7e541178593ee1ec716f3fbeb68bbf53c318c2cdb9917f7dd87018568b2d9d"
  },
  "model11/walkforward.py": {
    "bytes": 9626,
    "sha256": "be1cb8725026429aec835ce687045635ccb96be55085a01df52c9eaedebf1b48"
  },
  "preparation_v002/EV_AUDIT.md": {
    "bytes": 11285,
    "sha256": "6ee13bf39fda05b78b6d94da0d9ff28e68a702b58d0b18b9c4fc1a2b9821dda0"
  },
  "preparation_v002/INDEX.md": {
    "bytes": 2642,
    "sha256": "cf01d542fdd72b297c0589ee9ae523fff6b9ecce45a27242ad375fa08861f583"
  },
  "preparation_v002/INPUT_CONTRACT.md": {
    "bytes": 10939,
    "sha256": "091b65b96aef98d02fe6fde04d3fd5bf1169895ef99e3c298b0bb51e10819f92"
  },
  "preparation_v002/LEGACY_INTERFACE.md": {
    "bytes": 10820,
    "sha256": "84cac6297aee50ec7c46b8561c704102a31795ed60fb8bb7f3367fbace333a98"
  },
  "preparation_v002/MANIFEST_V002.json": {
    "bytes": 22803,
    "sha256": "816c8ceaabc9a7f02979de58bf8d011da49a4bf709a04f1f3b0848a1e5f2c38b"
  },
  "preparation_v002/PREREGISTRATION_PROPOSED.md": {
    "bytes": 10062,
    "sha256": "d1e38d0a15c00e6eb3cba7d43a858d1decf6cac5f2b4f5d3b3efd66af262ab8a"
  },
  "preparation_v002/README.md": {
    "bytes": 6251,
    "sha256": "cfbbd31c45175a00f2a775c2a90c677fe0f1cd968cf2761efd78524d30167069"
  },
  "preparation_v002/REPORT.md": {
    "bytes": 5733,
    "sha256": "5dbd611a5091928000a920b464252f2bb0a1ab84c9c9c98e39af45c354faa548"
  },
  "preparation_v002/REVIEW_FINDINGS.md": {
    "bytes": 1669,
    "sha256": "a16edf8deed57c5ad450d52e46a72a399e5c01f02879aceffed563c380a2b3c9"
  },
  "preparation_v002/SHA256SUMS_V002.txt": {
    "bytes": 4281,
    "sha256": "fd586b961fa1ad66011fbb4377765e53dadd0ff2b33bebaa3e572c5a2861d69e"
  },
  "preparation_v002/SHADOW_CONTRACT.md": {
    "bytes": 7094,
    "sha256": "4b85d9282dd593c3e36d227f48dd74f14a83bc7134f108525d0fa9b3fdcceece"
  },
  "preparation_v002/results/adapter-smoke-audit.json": {
    "bytes": 571,
    "sha256": "3ab277f4b7c50172a56f7fe75b4e417389383d2dd8b738ec82cf93e3b450806a"
  },
  "preparation_v002/results/adapter-smoke-prediction.json": {
    "bytes": 43332,
    "sha256": "74bba2b079f306589bc2ad7131f9fe78d05dfeb8c24ee2da78fb9ceda9b06981"
  },
  "preparation_v002/results/adapter-synthetic-normalizer.json": {
    "bytes": 5702,
    "sha256": "04d4ed94e0a4e310ec1b45d969d9c32bc3763b83156d7b8f53d58cb06f3c4479"
  },
  "preparation_v002/results/artifact-provenance.json": {
    "bytes": 4062,
    "sha256": "8a90f83b3a63c4d230b4398db7f04e130a8379146127e828c3b43bbd76754a32"
  },
  "preparation_v002/results/baseline-preservation.json": {
    "bytes": 284,
    "sha256": "87db11bc5b8f42cf4d1251511ddc54309a682f285539a57720eda4be6245990b"
  },
  "preparation_v002/results/demo-python312.raw.log": {
    "bytes": 365,
    "sha256": "01d4be07869be44b7425c4e7dbca1b395d0768fbd8ccf38655fd116c8858afce"
  },
  "preparation_v002/results/demo-python314.raw.log": {
    "bytes": 364,
    "sha256": "ac0dcd75eac987b0aab909ae56781eee301abf687efe1b0ec0ddac1960b48f3a"
  },
  "preparation_v002/results/legacy-synthetic-comparison.json": {
    "bytes": 45645,
    "sha256": "ddf07e6f94d00b8199f8fae66da488932e74175dee0292d8f67f97d9c668b2ce"
  },
  "preparation_v002/results/sample-size-planning.json": {
    "bytes": 10190,
    "sha256": "f80837cbfec1aabd18b896ce052ebca1e9acaf14166fb8b06e561b08240d6a47"
  },
  "preparation_v002/results/sensitivity-summary.json": {
    "bytes": 6527,
    "sha256": "34a7484bebdab52ce8da40b1a8e19a4eff36fab4acf019cd5541ea02c0da4275"
  },
  "preparation_v002/results/sensitivity.full.min.json": {
    "bytes": 1356632,
    "sha256": "8ba0853d34b8f6b5e8b9d4a81eedc1ba1aa6e84ca6fda931a8fd76ed8ae4e7cc"
  },
  "preparation_v002/results/shadow-synthetic.raw.json": {
    "bytes": 41547,
    "sha256": "526070cecd14ea5fc7238997e9139c4b3db1fe84e6a6e48ed5a7feadc571fa8b"
  },
  "preparation_v002/results/shadow-synthetic.receipt.json": {
    "bytes": 338,
    "sha256": "79c7dc9c7621dc31f44a4043f5afc25fe16b3b434b2f71dbf40da5053c8bf17d"
  },
  "preparation_v002/results/shadow-synthetic.verification.json": {
    "bytes": 271,
    "sha256": "69c1ffe7553cbbf34aabda78f3333b774076cffcc1f5b2f33fbd515bd9c4a3a6"
  },
  "preparation_v002/results/tests-python312.raw.log": {
    "bytes": 39178,
    "sha256": "176625bb571f78b287f3c1d34afd644c72365d489e621700fdd2e72152823aa3"
  },
  "preparation_v002/results/tests-python314.raw.log": {
    "bytes": 39177,
    "sha256": "2d25863594c4fd652a80978f8a6a0192a2396333d87aad2738969c02d9dd6e9a"
  },
  "preparation_v002/results/verification.json": {
    "bytes": 2013,
    "sha256": "2fc24a1060a8677baab2706742306469b10bd8928382ab9e482fb59713d52f4e"
  },
  "results/demo/aggregate-evaluation.json": {
    "bytes": 55903,
    "sha256": "fc9afb9ef594be505b2d8fb68af15d160476e5282dc9148c6976a21b2b11698c"
  },
  "results/demo/candidate-evaluations.json": {
    "bytes": 119985,
    "sha256": "4cb6ef01d2f93d7eaa8382edeb568a784a5ce64fe30fd9e070c9a7f96f8110f7"
  },
  "results/demo/example-evaluation.json": {
    "bytes": 38563,
    "sha256": "ad3e19bd0963558eb45922c5e341cacd61b3336d6efd311de3c3d4c5bbe9aaec"
  },
  "results/demo/example-prediction.json": {
    "bytes": 43750,
    "sha256": "7f85ed7ce0110c53445d1de092d468888a777e01c402748bcfcaf0cb85a47dbd"
  },
  "results/demo/fold-audit.json": {
    "bytes": 73116,
    "sha256": "6aae64657c883e6d0ebb397129f815d9142e674fb366588185cb16d186af45e8"
  },
  "results/demo/provenance.json": {
    "bytes": 2677,
    "sha256": "72a01bad921a750723d3cbe50ff0643680b29021e9d6086daec42ae1da013ed1"
  },
  "results/demo/selected-model.json": {
    "bytes": 1402,
    "sha256": "4247a89a8e177284f38965443a2a70e088a932b8d9736252dd42b17e350be8cb"
  },
  "results/demo/selected-pipeline-config.json": {
    "bytes": 68,
    "sha256": "96a555083182fc177215bba18bdc218cd5bfa575f355f804638910764d391b62"
  },
  "results/demo/synthetic-example-input.json": {
    "bytes": 16507,
    "sha256": "6130390145aef386b6697595c847c7de0595208fbf8038696719b3122c8e61b9"
  },
  "results/demo/synthetic-example-outcome.json": {
    "bytes": 292,
    "sha256": "3852b14e646a39324ecf8cbe1ba869913de909314f5153acc1fc7f592107ab52"
  },
  "results/initial-attempts.json": {
    "bytes": 1305,
    "sha256": "992e0e8420c07f50794bae9b5dc93998fcc3e07084ea5b3db6109ec8e8f10a60"
  },
  "results/initial-tests-python312.REDACTED.log": {
    "bytes": 20421,
    "sha256": "eb49d49763f5d949e105a92a955da390b2e88192e6c9f8a942cfe1a0a88979d5"
  },
  "results/initial-tests-python314.REDACTED.log": {
    "bytes": 20461,
    "sha256": "9ecd039459c185c69ff00ffe72ef24c911aff4bd0c0210bcc6e46d76d96265f8"
  },
  "results/tests-python312.log": {
    "bytes": 20394,
    "sha256": "eaf5da834b6577778f5eae76cda3b03c41494220f04dc8b3717b7d107cc65037"
  },
  "results/tests-python314.log": {
    "bytes": 20393,
    "sha256": "24a481ba4ed06835d2cc3f6c80ca6228945e3b422165ac92cfbc9fd341ff7b07"
  },
  "results/verification.json": {
    "bytes": 1925,
    "sha256": "a3f193604aa6a513eadd3a56e8d3ad79346f3a2c9f4c820d53ae052d2d1bc428"
  },
  "revision_v003/AUDIT_RESPONSE.md": {
    "bytes": 2174,
    "sha256": "7f4b15b082bf524f2d03821ba709e3f8a49b2fe857dbd9011fe8ea19b0b3877d"
  },
  "revision_v003/F1_MARKET_WEIGHT.md": {
    "bytes": 7163,
    "sha256": "5892611492c54d932cbec15332b025fae8a0ab007fdd7168649f31afa950f902"
  },
  "revision_v003/F2_BOX_DESIGN_PROPOSED.md": {
    "bytes": 9923,
    "sha256": "fcbb0bfa5bb967ef18a008817fb7fe55f300ff5b20c7423d6a41a25c21617f19"
  },
  "revision_v003/F3_COURSE_CONTRACT.md": {
    "bytes": 8113,
    "sha256": "bd4ca256ec4395aa00f2780be864d239a79c3a25118347b92260280b4ea51838"
  },
  "revision_v003/F4_SCHEMA_MIGRATION.md": {
    "bytes": 10826,
    "sha256": "4f79b05652a5e7a7619c94ca531cba0108d7ec1a5098b13e78efcd9d17d929c5"
  },
  "revision_v003/F5_SELECTION_PREREG_PROPOSED.md": {
    "bytes": 12757,
    "sha256": "e3612741bacd16606e0246c2cafe49988b6d8d3535a652bf2be1c7e9db44e77c"
  },
  "revision_v003/INDEX.md": {
    "bytes": 3063,
    "sha256": "b7f1f4893b4cb1027837b75019d6a3be571889c0631cec9cb94480a94527d15e"
  },
  "revision_v003/MANIFEST_V003.json": {
    "bytes": 35095,
    "sha256": "5f826c0797ffe44ed0d35300d99bcafbc835521ab23b315509b966158b297499"
  },
  "revision_v003/README.md": {
    "bytes": 5971,
    "sha256": "7d74289c5e70e3af9a2181e6f5f4a993a6c241ab1cfe7659d70fbe80e8abf801"
  },
  "revision_v003/REPORT.md": {
    "bytes": 5229,
    "sha256": "1fc76adfa4c7991be1a0a454403d5337ccfc62733f7dfe01db17e4d1facd7506"
  },
  "revision_v003/REVIEW_FINDINGS.md": {
    "bytes": 3533,
    "sha256": "9b7e7f22c35614791ce0a73fefcbcab9c5c1a47e67b69895bc334f5bfdc592ce"
  },
  "revision_v003/SHA256SUMS_V003.txt": {
    "bytes": 4928,
    "sha256": "4e0bbddde7ab29596b1185fbdf3edb186e67d07544d636ebd66a29af42ba1b9b"
  },
  "revision_v003/SOURCE_DIFFS/F1_walkforward.comparison.diff": {
    "bytes": 21113,
    "sha256": "5885162d266f47ed641ab5650bc4baf13f06604e33b715fca931951db14b251a"
  },
  "revision_v003/SOURCE_DIFFS/F4_portfolios.comparison.diff": {
    "bytes": 22633,
    "sha256": "9e3ab68b7882ea7d3242fb794d0fd04c38009e051d661ecde98441ef476a65ec"
  },
  "revision_v003/results/F1-market-only-evidence.json": {
    "bytes": 1210,
    "sha256": "3fdb5baf08392e10c3a8550a3e5da1b27770549ef386ef967dfec993a3d3d156"
  },
  "revision_v003/results/F4-manual-input-SYNTHETIC-ONLY.json": {
    "bytes": 537,
    "sha256": "7ff13595607e8a925f4d0ed9309f5a2d38835d71d01e6d6118a9bf039f08c44d"
  },
  "revision_v003/results/F4-old-artifact-migration.json": {
    "bytes": 876,
    "sha256": "0206494739497607d25e61bb239b5f67f4658d393937edd803fe84c8e7c6c9d7"
  },
  "revision_v003/results/F4-separate-manual-and-automatic.json": {
    "bytes": 50344,
    "sha256": "e51c4edb3266673437815119fc8b388f8a79df69d3ce6e9406afb698992dd670"
  },
  "revision_v003/results/artifact-provenance.json": {
    "bytes": 3787,
    "sha256": "97becf022887dddfac7c34cd47acf720e36d63934f3fe863d55a467bbbe6857a"
  },
  "revision_v003/results/demo-python312.raw.log": {
    "bytes": 334,
    "sha256": "52e9418128c497db04f69249eddc876edce1dcbb36c3be539d1e740100d2d38a"
  },
  "revision_v003/results/demo-python314.raw.log": {
    "bytes": 333,
    "sha256": "7ba4e1eb866c7a914907cee89fc9acc4cb372de144ad4499997c39c17bf9e839"
  },
  "revision_v003/results/evaluation-summary.json": {
    "bytes": 47359,
    "sha256": "ad65b891c44ec8838eefb1b74d3f76d9922d50277629c41088de6c8b1f084888"
  },
  "revision_v003/results/fold-selection-audit.json": {
    "bytes": 23473,
    "sha256": "1068b26fbcaad615e2f3dbbd7c2c8026396f71480aaa54cc6d85104257c77e37"
  },
  "revision_v003/results/prediction-v003.json": {
    "bytes": 47758,
    "sha256": "864b9011465615f828ed34e792b8c66efb73f5c50fdb41172ed1f37d6185fc55"
  },
  "revision_v003/results/preservation.json": {
    "bytes": 184,
    "sha256": "db3ee51f121c08b058fd57fb8009fcdba7ba7fd0d5e9d09cf70812e48694c9a1"
  },
  "revision_v003/results/selected-model-v003.json": {
    "bytes": 2666,
    "sha256": "8b3fc58d8ad6c44f6c6cde8f9aa52aa0c1955b433fef92bf19f5615e288902cd"
  },
  "revision_v003/results/selected-pipeline-v003.json": {
    "bytes": 97,
    "sha256": "3d0e338c63bd4d7eaa0c09aeb2ccfd407bd4770cdf5619c6f8b0da21b6599216"
  },
  "revision_v003/results/synthetic-outcome-separate.json": {
    "bytes": 292,
    "sha256": "3852b14e646a39324ecf8cbe1ba869913de909314f5153acc1fc7f592107ab52"
  },
  "revision_v003/results/synthetic-race-v003.json": {
    "bytes": 17369,
    "sha256": "f5f9655b0002d7939efab19649246e685965263772e8841d176bf4990959944c"
  },
  "revision_v003/results/tests-python312.raw.log": {
    "bytes": 51858,
    "sha256": "5d161110d6a58ac587cd1ee748f8bf7f6c72bcc64e135f9d476c41272ea8e7d1"
  },
  "revision_v003/results/tests-python314.raw.log": {
    "bytes": 51857,
    "sha256": "83c68fa171e1ea0ae803fa463ec283669bef92eb0fadfe783ed11228c40691be"
  },
  "revision_v003/results/verification.json": {
    "bytes": 1856,
    "sha256": "ed5689cd1715ce4279e55d4d2de18ea4bd2d60106e7b94d1ffd0ab4d8a78b168"
  },
  "revision_v003/results/walk-forward-summary.full.min.json": {
    "bytes": 645367,
    "sha256": "503b0b04303522e20d4d20b9d5cc874ec4c11cb5714c68727c81e83fbfe197bc"
  },
  "run_checks.py": {
    "bytes": 1243,
    "sha256": "383e83a41d9aae9008b475bc5f61f6f46ac68553d70fec3c8028ee48a6cebcae"
  },
  "tests/test_cli.py": {
    "bytes": 2339,
    "sha256": "6612bbcc5a0c87a1bbd852947145e0b3816ecc9c565fd55ad3ac2050b414315e"
  },
  "tests/test_engine.py": {
    "bytes": 4935,
    "sha256": "f101b6735dd85a2a4a5ec2ba66caca4ab4fe4bbbb9f7b7c47145ffb3b8b24d6d"
  },
  "tests/test_metrics.py": {
    "bytes": 16052,
    "sha256": "f8661d88df376464f8c1191b09d7fff36b18c5ce192cf16707118cb607c1c79a"
  },
  "tests/test_models.py": {
    "bytes": 16824,
    "sha256": "b48c889102862ac887033396c09523274e624140feeff68565945b9f2342be45"
  },
  "tests/test_preparation_adapter.py": {
    "bytes": 19427,
    "sha256": "f64b8fe4cd7d02360f42eb6c193c5df876c03c4cc84622ef75054802e6eb8b87"
  },
  "tests/test_preparation_integration.py": {
    "bytes": 4528,
    "sha256": "6678921eb9339c7a8bb1e422f05f389206358c980775412697e701954f4d557a"
  },
  "tests/test_preparation_legacy.py": {
    "bytes": 15069,
    "sha256": "644cb581174739a80ae19604f97e1a5945823d7bd07ebe70e0759ef51ab49195"
  },
  "tests/test_preparation_planning.py": {
    "bytes": 9409,
    "sha256": "861d5893ebfeaa6463745c34e3edb956123587d99073b0daff0056adc506a558"
  },
  "tests/test_preparation_sensitivity.py": {
    "bytes": 14218,
    "sha256": "d98a9e6eec0f709192d95785316e1a1bc83f20f69d5ce45185db9952b548226a"
  },
  "tests/test_preparation_shadow.py": {
    "bytes": 13416,
    "sha256": "cfeccd65b32a11764ecc4b6c1c4cffe4d90c468e3fc14e87f890e39b39f6a134"
  },
  "tests/test_revision_v003_course.py": {
    "bytes": 13748,
    "sha256": "7829c0efe85cfb3d0da81dab67776ea4f4d2f2d04ff2d6f997eff44dbe4819a3"
  },
  "tests/test_revision_v003_integration.py": {
    "bytes": 26569,
    "sha256": "3a1c860fc5dbd1da98e47e480d67a58f406ac12d4cfa0ebacd6a437e792672ec"
  },
  "tests/test_revision_v003_portfolios.py": {
    "bytes": 16011,
    "sha256": "85438d8c876799225a324e059b38af36eb5e3bd4f43d06e1662e90f011e2896b"
  },
  "tests/test_revision_v003_walkforward.py": {
    "bytes": 10106,
    "sha256": "7db848cea8302d099305c1c1ac887a91f8a63473a5d2d126132384266c3e2436"
  },
  "tests/test_selection.py": {
    "bytes": 14984,
    "sha256": "39f8337e0eaa49a6e918be60ffc891c3ae4116db5386ab08f35112f7e8dc9967"
  },
  "tests/test_synthetic.py": {
    "bytes": 6921,
    "sha256": "a0a4b388c360648b436130c2e784408b1edd52de88568e45e91920aa82b52424"
  },
  "tests/test_validation.py": {
    "bytes": 23994,
    "sha256": "4ba1a2925cdbece8547adcc6f01a69f7671dcc18fcb6a440e1c28dc862cbc9b2"
  },
  "tests/test_walkforward.py": {
    "bytes": 3508,
    "sha256": "db0cbb4b69c85037846728e9179263fdf37ec3ca1b67fbb8070740484716e762"
  }
}
ARCHIVE_BYTES = 17860
ARCHIVE_SHA256 = "48b53e1b372c9c8b63027567d920514ac4e23668f0373d9f4f9a559789f0f66b"
ROOT = Path(__file__).resolve().parents[1]
POLICY_IDS = tuple(sorted(COURSE_POLICIES))
SOURCE_BY_CLASS = {
    "SYNTHETIC_ONLY": {"frame": "SYNTHETIC_FRAME_V001", "exhibition": "SYNTHETIC_EXHIBITION_V001"},
    "PRIVATE_REAL": {"frame": "OFFICIAL_FRAME_PRELOCK_V001", "exhibition": "OFFICIAL_EXHIBITION_PRELOCK_V001"},
}
SENTINEL = "N1_PRIVATE_VALUE_SENTINEL_9c673"


def parent_course_module():
    # Execute the exact archived trusted parent source in memory. This does not
    # import or modify the patched module and creates no bytecode/cache files.
    path = ROOT / "revision_v004/references/course_v003_original.py.txt"
    raw = path.read_bytes()
    module = types.ModuleType("model11.revision_v003._n1_archived_parent_course")
    module.__package__ = "model11.revision_v003"
    exec(compile(raw, "course_v003_original.py.txt", "exec"), module.__dict__)
    return module


class N1BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_dataset_v003(days=10, races_per_day=1, seed=20261105)
        cls.parent = parent_course_module()
        cls.model = CourseBoundModel("hierarchical", {"epochs": 1, "alpha": .5}).fit(
            cls.data["races"][:6], cls.data["outcomes"][:6])

    def fixture(self, policy_id, exhibition_present=True):
        return apply_course_fixture(self.data["races"][8], policy_id, exhibition_present)

    def classified(self, row, classification):
        row = deepcopy(row)
        row["data_classification"] = classification
        row["synthetic"] = classification == "SYNTHETIC_ONLY"
        for slot, observation in row["course_inputs"].items():
            if observation is not None:
                observation["source_id"] = SOURCE_BY_CLASS[classification][slot]
        return row

    def assert_n1_hold(self, row, policy, expected_code):
        report = validate_course(row, policy)
        self.assertIs(report["eligible"], False)
        self.assertEqual(report["status"], "HOLD")
        self.assertIn(expected_code, report["errors"])
        self.assertEqual(report["external_authenticity"], "UNVERIFIED")
        self.assertFalse(report["production_go"])
        self.assertNotIn(SENTINEL, json.dumps(report, sort_keys=True))
        return report

    def test_original_other134_files_and_archived_target_are_byte_exact(self):
        self.assertEqual(len(UNCHANGED_134), 134)
        for path, expected in UNCHANGED_134.items():
            with self.subTest(path=path):
                raw = (ROOT / path).read_bytes()
                self.assertEqual(len(raw), expected["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])
        raw = (ROOT / "revision_v004/references/course_v003_original.py.txt").read_bytes()
        self.assertEqual(len(raw), ARCHIVE_BYTES)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ARCHIVE_SHA256)

    def test_all_policy_hashes_valid_synthetic_reports_and_model_serialization_unchanged(self):
        self.assertEqual(COURSE_POLICIES, self.parent.COURSE_POLICIES)
        for policy_id in POLICY_IDS:
            policy = COURSE_POLICIES[policy_id]
            with self.subTest(policy=policy_id):
                self.assertEqual(canonical_hash(policy), self.parent.canonical_hash(self.parent.COURSE_POLICIES[policy_id]))
                for exhibition_present in (True, False):
                    if policy_id == "EXHIBITION_ONLY_V001" and not exhibition_present:
                        continue
                    row = self.fixture(policy_id, exhibition_present)
                    before = deepcopy(row)
                    self.assertEqual(validate_course(row, policy), self.parent.validate_course(row, policy))
                    self.assertTrue(validate_course(row, policy)["eligible"])
                    self.assertEqual(row, before)
                train = [apply_course_fixture(race, policy_id) for race in self.data["races"][:6]]
                options = {"epochs": 1, "alpha": .5}
                current = CourseBoundModel("hierarchical", options, policy).fit(train, self.data["outcomes"][:6])
                archived = self.parent.CourseBoundModel("hierarchical", options, policy).fit(train, self.data["outcomes"][:6])
                self.assertEqual(current.to_dict(), archived.to_dict())
                restored = CourseBoundModel.from_dict(current.to_dict())
                self.assertEqual(restored.to_dict(), archived.to_dict())
                row = self.fixture(policy_id)
                self.assertEqual(restored.distributions(row), archived.distributions(row))

    def test_all_three_policies_check_selected_and_unused_nonnull_sources_against_class(self):
        for policy_id in POLICY_IDS:
            policy = COURSE_POLICIES[policy_id]
            for classification in ("SYNTHETIC_ONLY", "PRIVATE_REAL"):
                valid = self.classified(self.fixture(policy_id), classification)
                valid_report = validate_course(valid, policy)
                self.assertTrue(valid_report["eligible"])
                self.assertEqual(valid_report["external_authenticity"], "UNVERIFIED")
                self.assertFalse(valid_report["production_go"])
                wrong_class = "PRIVATE_REAL" if classification == "SYNTHETIC_ONLY" else "SYNTHETIC_ONLY"
                for slot in ("frame", "exhibition"):
                    changed = deepcopy(valid)
                    changed["course_inputs"][slot]["source_id"] = SOURCE_BY_CLASS[wrong_class][slot]
                    with self.subTest(policy=policy_id, classification=classification, slot=slot):
                        self.assert_n1_hold(changed, policy, "COURSE_SOURCE_CLASSIFICATION_MISMATCH")
        mix = COURSE_POLICIES["EXHIBITION_ELSE_FRAME_V001"]
        for classification in ("SYNTHETIC_ONLY", "PRIVATE_REAL"):
            fallback = self.classified(self.fixture("EXHIBITION_ELSE_FRAME_V001", False), classification)
            self.assertTrue(validate_course(fallback, mix)["eligible"])
            fallback["course_inputs"]["frame"]["source_id"] = SOURCE_BY_CLASS[
                "PRIVATE_REAL" if classification == "SYNTHETIC_ONLY" else "SYNTHETIC_ONLY"]["frame"]
            self.assert_n1_hold(fallback, mix, "COURSE_SOURCE_CLASSIFICATION_MISMATCH")

    def test_classification_missing_unknown_and_boolean_flags_are_strict(self):
        for policy_id in POLICY_IDS:
            row, policy = self.fixture(policy_id), COURSE_POLICIES[policy_id]
            missing = deepcopy(row)
            del missing["data_classification"]
            self.assert_n1_hold(missing, policy, "COURSE_DATA_CLASSIFICATION_MISSING_OR_UNKNOWN")
            for value in (None, "", SENTINEL, 1, True, [], {}):
                bad = deepcopy(row)
                bad["data_classification"] = value
                with self.subTest(policy=policy_id, classification_type=type(value).__name__):
                    self.assert_n1_hold(bad, policy, "COURSE_DATA_CLASSIFICATION_MISSING_OR_UNKNOWN")
            missing = deepcopy(row)
            del missing["synthetic"]
            self.assert_n1_hold(missing, policy, "COURSE_SYNTHETIC_FLAG_MISSING_OR_INVALID")
            for value in (None, 0, 1, "true", "", [], {}):
                bad = deepcopy(row)
                bad["synthetic"] = value
                with self.subTest(policy=policy_id, flag_type=type(value).__name__):
                    self.assert_n1_hold(bad, policy, "COURSE_SYNTHETIC_FLAG_MISSING_OR_INVALID")
            for classification in ("SYNTHETIC_ONLY", "PRIVATE_REAL"):
                mismatch = self.classified(row, classification)
                mismatch["synthetic"] = not mismatch["synthetic"]
                self.assert_n1_hold(mismatch, policy, "COURSE_CLASSIFICATION_FLAG_MISMATCH")

    def test_missing_unknown_and_unregistered_official_sources_hold_without_echo(self):
        for policy_id in POLICY_IDS:
            policy = COURSE_POLICIES[policy_id]
            for classification in ("SYNTHETIC_ONLY", "PRIVATE_REAL"):
                row = self.classified(self.fixture(policy_id), classification)
                for slot in ("frame", "exhibition"):
                    missing = deepcopy(row)
                    del missing["course_inputs"][slot]["source_id"]
                    self.assert_n1_hold(missing, policy, "COURSE_SOURCE_MISSING_OR_UNKNOWN")
                    for value in (None, "", SENTINEL, "OFFICIAL_" + SENTINEL, 1, True, [], {}):
                        bad = deepcopy(row)
                        bad["course_inputs"][slot]["source_id"] = value
                        with self.subTest(policy=policy_id, classification=classification, slot=slot, source_type=type(value).__name__):
                            self.assert_n1_hold(bad, policy, "COURSE_SOURCE_MISSING_OR_UNKNOWN")

    def test_private_synthetic_source_cannot_pass_any_model_or_execution_entry_route(self):
        bad = deepcopy(self.data["races"][8])
        bad.update(data_classification="PRIVATE_REAL", synthetic=False)
        self.assert_n1_hold(bad, COURSE_POLICIES["EXHIBITION_ONLY_V001"], "COURSE_SOURCE_CLASSIFICATION_MISMATCH")
        for method in (self.model.distributions, self.model.conditionals, self.model.explain):
            with self.subTest(entry=method.__name__), self.assertRaises(ValueError):
                method(bad)
        bad_train = deepcopy(self.data["races"][:6])
        bad_train[0].update(data_classification="PRIVATE_REAL", synthetic=False)
        with self.assertRaises(ValueError):
            CourseBoundModel("hierarchical", {"epochs": 1}).fit(bad_train, self.data["outcomes"][:6])
        with self.assertRaises(ValueError):
            predict_v003(bad, self.model)
        bad_data = deepcopy(self.data)
        bad_data["races"][8] = bad
        config = {"train_days": 6, "selection_days": 2, "test_days": 2, "epochs": 1,
                  "candidates": ["hierarchical"], "alphas": [0.0], "temperatures": [1.0],
                  "market_weights": [1.0], "evaluation": {}}
        with self.assertRaises(ValueError):
            walk_forward_v003(bad_data, config)

    def test_registered_official_private_claims_consistent_but_execution_still_hold(self):
        official = self.classified(self.data["races"][8], "PRIVATE_REAL")
        report = validate_course(official, COURSE_POLICIES["EXHIBITION_ONLY_V001"])
        self.assertTrue(report["eligible"])
        self.assertEqual(report["status"], "COURSE_CLAIMS_CONSISTENT")
        self.assertEqual(report["external_authenticity"], "UNVERIFIED")
        self.assertFalse(report["production_go"])
        with self.assertRaisesRegex(ValueError, "HOLD_REAL_INPUT_REVIEW_REQUIRED"):
            predict_v003(official, self.model)
        private_looking_data = deepcopy(self.data)
        private_looking_data["classification"] = "PRIVATE_REAL"
        private_looking_data["races"] = [self.classified(row, "PRIVATE_REAL") for row in self.data["races"]]
        with self.assertRaisesRegex(ValueError, "REAL_INPUT_REQUIRES_APPROVED_PREREGISTRATION"):
            walk_forward_v003(private_looking_data)


if __name__ == "__main__":
    unittest.main()
