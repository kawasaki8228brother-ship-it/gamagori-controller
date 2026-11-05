"""Independent black-box V003 software checks; no real-performance claims."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import unittest

from model11.engine import canonical_hash
from model11.models import make_model
from model11.synthetic import make_dataset
from model11.revision_v003.course import COURSE_POLICIES, CourseBoundModel, apply_course_fixture
from model11.revision_v003.engine import predict_v003
from model11.revision_v003.fixtures import make_dataset_v003
from model11.revision_v003.walkforward import walk_forward_v003


# Exact immutable 88-file baseline, parent00d67eea0598ba83671eb400175749df294a6fad.
# Embedded for portable verification; no private workspace file is needed.
BASELINE = {
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


class RevisionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_dataset_v003(days=10, races_per_day=1, seed=20261105)
        cls.train, cls.labels = cls.data["races"][:6], cls.data["outcomes"][:6]
        cls.race = cls.data["races"][8]
        cls.model = CourseBoundModel("hierarchical", {"epochs": 2, "alpha": .5},
                                     COURSE_POLICIES["EXHIBITION_ONLY_V001"]).fit(cls.train, cls.labels)

    def test_existing_eighty_eight_files_are_byte_immutable(self):
        self.assertEqual(len(BASELINE), 88)
        root = Path(__file__).resolve().parents[1]
        for relative, expected in BASELINE.items():
            with self.subTest(relative=relative):
                raw = (root / relative).read_bytes()
                self.assertEqual(len(raw), expected["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected["sha256"])

    def test_synthetic_fixture_has_fixed_exhibition_course_evidence(self):
        self.assertEqual(self.data["classification"], "SYNTHETIC_ONLY")
        self.assertEqual(len(self.data["races"]), 10)
        self.assertTrue(all(race["target_date"].startswith("2099-") for race in self.data["races"]))
        for race in self.data["races"]:
            self.assertIsNone(race["human_box_input"])
            self.assertIsNotNone(race["course_inputs"]["exhibition"])
            for boat in race["boats"]:
                self.assertEqual(boat["course"], race["course_inputs"]["exhibition"]["courses"][str(boat["boat"])] )

    def test_default_fixture_course_metadata_preserves_original_model_probabilities(self):
        original = make_dataset(days=10, races_per_day=1, seed=20261105)
        for old_race, revised_race in zip(original["races"], self.data["races"]):
            self.assertEqual([boat["course"] for boat in old_race["boats"]],
                             [boat["course"] for boat in revised_race["boats"]])
            self.assertEqual(old_race["odds_snapshot"], revised_race["odds_snapshot"])
            self.assertEqual([boat["features"] for boat in old_race["boats"]],
                             [boat["features"] for boat in revised_race["boats"]])
        self.assertEqual(original["outcomes"], self.data["outcomes"])
        base = make_model("hierarchical", {"epochs": 2, "alpha": .5}).fit(
            original["races"][:6], original["outcomes"][:6])
        old_dist = base.distributions(original["races"][8])
        revised_dist = self.model.distributions(self.race)
        self.assertEqual(old_dist["P_raw"], revised_dist["P_raw"])
        self.assertEqual(old_dist["P_model"], revised_dist["P_model"])

    def test_private_or_non_synthetic_inputs_are_hold_not_real_data_approval(self):
        for mutate in (lambda race: race.update(synthetic=False),
                       lambda race: race.update(data_classification="PRIVATE_INPUT_UNVERIFIED"),
                       lambda race: race.update(target_date="2026-11-09")):
            invented_input = deepcopy(self.race)
            mutate(invented_input)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(ValueError, "HOLD_REAL_INPUT_REVIEW_REQUIRED"):
                predict_v003(invented_input, self.model)

    def test_four_stages_120_finite_five_sorted_and_four_semantic_box_slots(self):
        prediction = predict_v003(self.race, self.model)
        self.assertEqual(prediction["schema"], "MODEL11_FORECAST_V003")
        self.assertEqual(prediction["version"], "0.3.0-research")
        for stage in ("P_raw", "P_model", "P_market", "P_shrunk"):
            dist = prediction["distributions"][stage]
            self.assertEqual(len(dist), 120)
            self.assertTrue(all(math.isfinite(p) and 0 <= p <= 1 for p in dist.values()))
            self.assertAlmostEqual(math.fsum(dist.values()), 1, places=11)
            self.assertTrue(all(len(set(ticket.split("-"))) == 3 for ticket in dist))
        five = prediction["selection"]["tickets"]
        self.assertEqual(five, sorted(five))
        self.assertEqual(len(set(five)), 5)
        boxes = prediction["boxes"]
        for name in ("five_appearance_research", "human_input_research", "mechanical_research", "box_v11_research"):
            self.assertIn(name, boxes)
        self.assertIsNone(boxes["human_input_research"])
        self.assertNotIn("human_research", boxes)
        for name in ("five_appearance_research", "mechanical_research", "box_v11_research"):
            self.assertEqual(len(set(boxes[name]["tickets"])), 6)
            self.assertFalse(boxes[name]["formal_box_v1_reproduction"])
        self.assertFalse(prediction["production_go"])
        self.assertNotIn("actual", prediction)
        self.assertNotIn("result", prediction)

    def test_weight_one_is_bit_exact_market_regardless_alpha_temperature_or_model(self):
        original = deepcopy(self.race)
        by_variant = []
        calibrated_variants = []
        for name, alpha, temperature in (("hierarchical", 0.0, .7), ("contextual", 1.0, 1.3)):
            model = CourseBoundModel(name, {"epochs": 2, "alpha": alpha},
                                     COURSE_POLICIES["EXHIBITION_ONLY_V001"]).fit(self.train, self.labels)
            pred = predict_v003(self.race, model, {"temperature": temperature, "market_weight": 1.0})
            self.assertEqual(pred["distributions"]["P_shrunk"], pred["distributions"]["P_market"])
            by_variant.append(pred["distributions"]["P_shrunk"])
            calibrated_variants.append(pred["P_calibrated"])
        self.assertEqual(by_variant[0], by_variant[1])
        self.assertNotEqual(calibrated_variants[0], calibrated_variants[1])
        self.assertEqual(self.race, original)

    def test_weight_one_without_usable_odds_is_hold(self):
        for mutate in (lambda r: r.update(odds_snapshot=None),
                       lambda r: r["odds_snapshot"].update(available_at=r["deadline"])):
            race = deepcopy(self.race)
            mutate(race)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                predict_v003(race, self.model, {"market_weight": 1.0})

    def test_bound_course_policy_mismatch_is_hold(self):
        frame_race = apply_course_fixture(self.race, policy_id="FRAME_ONLY_V001")
        with self.assertRaises(ValueError):
            predict_v003(frame_race, self.model)

    def test_future_and_result_course_evidence_are_hold(self):
        for mutate in (lambda r: r["course_inputs"]["exhibition"].update(available_at=r["deadline"]),
                       lambda r: r["course_inputs"]["exhibition"].update(definition="ACTUAL_ENTRY_RESULT"),
                       lambda r: r["course_inputs"]["exhibition"].update(source_id="RESULT_FINAL_ENTRY")):
            race = deepcopy(self.race)
            mutate(race)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                predict_v003(race, self.model)

    def test_course_bound_model_serialized_roundtrip_preserves_predictions(self):
        artifact = self.model.to_dict()
        copy = CourseBoundModel.from_dict(json.loads(json.dumps(artifact, allow_nan=False)))
        expected = predict_v003(self.race, self.model, {"market_weight": .9})
        actual = predict_v003(self.race, copy, {"market_weight": .9})
        self.assertEqual(actual, expected)
        self.assertEqual(copy.to_dict(), artifact)
        bad = deepcopy(artifact)
        bad["unexpected_tamper"] = True
        with self.assertRaises(ValueError):
            CourseBoundModel.from_dict(bad)

    def test_explicit_manual_human_input_is_separate_from_automatic_slot(self):
        t = (datetime.fromisoformat(self.race["prediction_at"]) - timedelta(seconds=30)).isoformat()
        manual = {"core": [1, 2], "insertion": 3, "origin": "HUMAN_MANUAL",
                  "race_id": self.race["race_id"], "target_date": self.race["target_date"],
                  "source_id": "SYNTHETIC_MANUAL_TEST_ONLY", "evidence_sha256": "a" * 64,
                  "observed_at": t, "acquired_at": t, "available_at": t,
                  "revision_at": t, "evidence_recorded_at": t}
        with_manual = predict_v003(self.race, self.model, human_input=manual)
        automatic = predict_v003(self.race, self.model)
        self.assertIsNotNone(with_manual["boxes"]["human_input_research"])
        self.assertEqual(with_manual["boxes"]["human_input_research"]["boats"], [1, 2, 3])
        self.assertEqual(with_manual["boxes"]["five_appearance_research"], automatic["boxes"]["five_appearance_research"])
        self.assertIsNone(automatic["boxes"]["human_input_research"])
        self.assertNotIn("human_research", with_manual["boxes"])
        self.assertEqual(set(with_manual["boxes"]["composition_difference"]),
                         {"five_appearance_vs_mechanical", "human_input_vs_mechanical"})
        self.assertFalse(with_manual["boxes"]["human_input_research"]["formal_box_v1_reproduction"])
        for bad_origin in ("AUTOMATIC", "UNKNOWN", ""):
            invalid = deepcopy(manual)
            invalid["origin"] = bad_origin
            with self.subTest(origin=bad_origin), self.assertRaises(ValueError):
                predict_v003(self.race, self.model, human_input=invalid)
        for mutate in (lambda value: value.update(race_id="20990101_GAMAGORI_12R"),
                       lambda value: value.update(available_at=self.race["deadline"])):
            invalid = deepcopy(manual)
            mutate(invalid)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                predict_v003(self.race, self.model, human_input=invalid)

    def test_legacy_canonical_human_slot_is_not_automatically_reused(self):
        race = deepcopy(self.race)
        t = (datetime.fromisoformat(race["prediction_at"]) - timedelta(seconds=30)).isoformat()
        race["human_box_input"] = {"core": [1, 2], "insertion": 3, "observed_at": t,
                                   "acquired_at": t, "available_at": t, "revision_at": t}
        with self.assertRaisesRegex(ValueError, "LEGACY_HUMAN_INPUT"):
            predict_v003(race, self.model)

    def test_outcome_fields_do_not_enter_v003_prediction(self):
        race = deepcopy(self.race)
        race["nested"] = {"result": [1, 2, 3]}
        with self.assertRaises(ValueError):
            predict_v003(race, self.model)

    def test_training_only_or_future_normalization_stays_out_of_prediction(self):
        training = deepcopy(self.race)
        training["normalization_usage"] = "TRAINING_ONLY_NOT_FORECAST"
        with self.assertRaisesRegex(ValueError, "NORMALIZATION"):
            predict_v003(training, self.model)
        valid = deepcopy(self.race)
        valid["normalization_usage"] = "PREDICTION_AS_OF_GATE_PASSED"
        valid["normalization_provenance"] = {
            "normalizer_sha256": "a" * 64, "feature_specs_sha256": "b" * 64,
            "training_input_sha256": "c" * 64, "usage": "prediction",
            "fit_cutoff": self.train[-1]["prediction_at"],
            "training_max_available_at": self.labels[-1]["available_at"],
        }
        predicted = predict_v003(valid, self.model)
        self.assertEqual(predicted["information"]["normalization_provenance"]["fit_cutoff"], self.train[-1]["prediction_at"])
        self.assertEqual(predicted["information"]["normalization_provenance"]["timestamp_authenticity"], "UNVERIFIED_SELF_REPORTED_INPUT")
        for key in ("fit_cutoff", "training_max_available_at"):
            race = deepcopy(valid)
            race["normalization_provenance"][key] = race["prediction_at"]
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "NORMALIZATION"):
                predict_v003(race, self.model)

    def test_walkforward_test_labels_do_not_influence_selected_forecast(self):
        config = {"train_days": 6, "selection_days": 2, "test_days": 2, "epochs": 1,
                  "candidates": ["hierarchical"], "alphas": [0.0], "temperatures": [1.0],
                  "market_weights": [0.0, 1.0], "evaluation": {}}
        original = walk_forward_v003(self.data, config)
        altered_data = deepcopy(self.data)
        for outcome in altered_data["outcomes"][8:]:
            outcome["result"] = list(reversed(outcome["result"]))
        altered = walk_forward_v003(altered_data, config)
        self.assertEqual(len(original["records"]), 2)
        self.assertEqual(len(altered["records"]), 2)
        for before, after in zip(original["records"], altered["records"]):
            self.assertEqual(before["prediction_sha256"], after["prediction_sha256"])
            self.assertEqual(before["selection"], after["selection"])
            self.assertEqual(before["distributions"], after["distributions"])
            self.assertEqual(before["boxes"], after["boxes"])
        self.assertEqual(original["folds"][0]["selected"], altered["folds"][0]["selected"])
        self.assertFalse(original["production_go"])


if __name__ == "__main__":
    unittest.main()
