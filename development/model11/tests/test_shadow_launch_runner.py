"""Independent end-to-end tests using wholly invented 2099 local captures.

No actual official data, service transport, credentials, or approval is used.
The context helper is for offline test/demo construction, not a launch API.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from model11.engine import canonical_hash
from model11.preparation.adapter import fit_normalizer, normalize_race
from model11.revision_v003.course import COURSE_POLICIES, CourseBoundModel
from model11.revision_v003.fixtures import make_dataset_v003
from model11.revision_v003.engine import predict_v003
from model11.shadow_launch.policy import artifact_fingerprints, settings_fingerprints
from model11.shadow_launch.sources import SourceAdapter, make_synthetic_source_fixture
from model11.shadow_launch.storage import ShadowStore


SENTINEL = "SYNTHETIC_PRIVATE_EXCEPTION_TEXT_NEVER_EMIT"


class MutableClock:
    def __init__(self, value):
        self.value = self._parse(value)
        self.calls = 0
        self._lock = threading.Lock()

    @staticmethod
    def _parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value

    def __call__(self):
        with self._lock:
            self.calls += 1
            return self.value

    def set(self, value):
        with self._lock:
            self.value = self._parse(value)

    def advance(self, seconds):
        with self._lock:
            self.value += timedelta(seconds=seconds)


def make_simulation_context(tmp_root):
    """Build local synthetic artifacts: train days1-6, target day7's 12 races.

    Fitted values come only from earlier invented inputs/outcomes. The explicit
    fixture registration and all local hashes are assertions, not independent
    evidence of approval, source authenticity, or real forecasting performance.
    """
    data = make_dataset_v003(days=7, races_per_day=12, seed=20261105)
    source_fixtures = [make_synthetic_source_fixture(race) for race in data["races"]]
    mapping = source_fixtures[0]["mapping"]
    if any(item["mapping"] != mapping for item in source_fixtures):
        raise AssertionError("SYNTHETIC_MAPPING_NOT_FIXED")
    adapter = SourceAdapter(mapping)
    converted = [adapter.convert(item["capture"]) for item in source_fixtures]
    if any(item["status"] != "READY" for item in converted):
        raise AssertionError("SYNTHETIC_SOURCE_NOT_READY")
    train_count = 6 * 12
    targets = data["races"][train_count:]
    target_date = targets[0]["target_date"]
    zone = datetime.fromisoformat(targets[0]["prediction_at"]).tzinfo
    fit_cutoff = datetime.fromisoformat(target_date).replace(tzinfo=zone).isoformat()
    normalizer = fit_normalizer([item["raw"] for item in converted[:train_count]], fit_cutoff,
                                mapping["feature_specs"])
    normalized_train = []
    for item in converted[:train_count]:
        normalized = normalize_race(item["raw"], normalizer, usage="training")["race"]
        normalized.update(deepcopy(item["course"]))
        normalized_train.append(normalized)
    policy = deepcopy(COURSE_POLICIES["EXHIBITION_ONLY_V001"])
    model = CourseBoundModel("hierarchical", {"epochs": 3, "alpha": .5}, policy).fit(
        normalized_train, data["outcomes"][:train_count])
    config = {}
    settings = {"enabled": True, "mode": "SIMULATION", "namespace": "MODEL11_THIRD_RESEARCH",
                "storage_root": str(Path(tmp_root) / "third_research"),
                "code_commit": "df807089f5fd27517109f9bd38b6c55f9415600e",
                "input_classification": "SYNTHETIC_ONLY", "storage_identity": "SYNTHETIC_STORE_001"}
    pins = settings_fingerprints(settings)
    settings.update(pinned_config_sha256=pins["config_sha256"],
                    pinned_storage_sha256=pins["storage_identity_sha256"])
    artifacts = {"model": model.to_dict(), "normalizer": normalizer, "source_mapping": mapping,
                 "course_policy": policy, "prediction_config": config}
    artifacts["artifact_sha256s"] = artifact_fingerprints(artifacts)
    artifacts["simulation_context"] = {"classification": "SYNTHETIC_ONLY", "synthetic": True,
        "target_year": 2099, "temporary_store_registered": True,
        "storage_identity_sha256": pins["storage_identity_sha256"]}
    clock = MutableClock(datetime.fromisoformat(targets[0]["prediction_at"]) + timedelta(seconds=1))
    return {"settings": settings, "model": model, "model_config": config, "normalizer": normalizer,
            "source_adapter": adapter, "artifacts": artifacts, "clock": clock,
            "captures": [item["capture"] for item in source_fixtures[train_count:]],
            "outcomes": deepcopy(data["outcomes"][train_count:]), "races": deepcopy(targets),
            "mapping": deepcopy(mapping), "classification": "SYNTHETIC_ONLY"}


def resign_capture(capture, edit):
    """Modify invented fixture JSON and refresh only its self-reported hashes."""
    result = deepcopy(capture)
    document = json.loads(result["payload_bytes"].decode("ascii"))
    edit(document)
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii")
    digest = hashlib.sha256(payload).hexdigest()
    result["payload_bytes"], result["payload_sha256"] = payload, digest
    result["history"][-1]["payload_sha256"] = digest
    result["history"][-1]["evidence_sha256"] = canonical_hash({"invented_modified_capture": digest})
    return result


class _ForbiddenCall:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            self.calls.append(name)
            raise AssertionError("DISABLED_MUST_NOT_CALL_DEPENDENCY")
        return forbidden

    def __call__(self, *args, **kwargs):
        self.calls.append("clock")
        raise AssertionError("DISABLED_MUST_NOT_READ_CLOCK")


class ShadowRunnerTests(unittest.TestCase):
    def context(self):
        temporary = tempfile.TemporaryDirectory(prefix="shadow-runner-synthetic-")
        self.addCleanup(temporary.cleanup)
        return make_simulation_context(temporary.name)

    def runner(self, context, store=None, source_adapter=None):
        from model11.shadow_launch.runner import ShadowRunner
        store = store or ShadowStore(context["settings"]["storage_root"], clock=context["clock"])
        runner = ShadowRunner(context["settings"], context["model"], model_config=context["model_config"],
            normalizer=context["normalizer"], source_adapter=source_adapter or context["source_adapter"],
            store=store, artifacts=context["artifacts"], clock=context["clock"])
        return runner, store

    def forecast(self, store, race_id):
        readback = store.readback(race_id)
        self.assertEqual(readback["status"], "COMMITTED")
        receipt = readback["receipt"]
        self.assertEqual(receipt["input_sha256"], hashlib.sha256(readback["input_raw"]).hexdigest())
        self.assertEqual(receipt["forecast_sha256"], hashlib.sha256(readback["forecast_raw"]).hexdigest())
        document = json.loads(readback["forecast_raw"].decode("ascii"))
        prediction = document if document.get("schema") == "MODEL11_FORECAST_V003" else document["forecast"]
        self.assertEqual(prediction["schema"], "MODEL11_FORECAST_V003")
        return readback, prediction

    def test_default_disabled_is_zero_io_even_with_exploding_dependencies(self):
        from model11.shadow_launch.runner import ShadowRunner
        for settings in (None, {}, {"enabled": False}):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as root:
                forbidden = _ForbiddenCall()
                before = list(Path(root).iterdir())
                runner = ShadowRunner(settings, forbidden, normalizer=forbidden,
                    source_adapter=forbidden, store=forbidden, artifacts=forbidden, clock=forbidden)
                report = runner.run_race(None)
                self.assertEqual(report["status"], "DISABLED")
                self.assertEqual(runner.ingest_result("20990107_GAMAGORI_1R", {})["status"], "DISABLED")
                self.assertEqual(runner.daily_settlement("2099-01-07", {})["status"], "DISABLED")
                runner.request_stop()
                runner.shutdown()
                self.assertEqual(forbidden.calls, [])
                self.assertEqual(list(Path(root).iterdir()), before)

    def test_twelve_races_have_immutable_separate_forecasts_and_consistent_boxes(self):
        context = self.context()
        runner, store = self.runner(context)
        snapshots = {}
        for race, capture in zip(context["races"], context["captures"]):
            context["clock"].set(datetime.fromisoformat(race["prediction_at"]) + timedelta(seconds=1))
            report = runner.run_race(capture)
            self.assertEqual(report["status"], "COMMITTED")
            readback, prediction = self.forecast(store, race["race_id"])
            self.assertEqual(readback["input_raw"], capture["payload_bytes"])
            self.assertEqual(prediction["race_id"], race["race_id"])
            self.assertNotIn("actual", prediction)
            self.assertFalse(prediction["production_go"])
            for stage in ("P_raw", "P_model", "P_market", "P_shrunk"):
                self.assertEqual(len(prediction["distributions"][stage]), 120)
                self.assertAlmostEqual(sum(prediction["distributions"][stage].values()), 1, places=10)
            five, boxes = prediction["selection"], prediction["boxes"]
            self.assertEqual(len(set(five["tickets"])), 5)
            self.assertEqual(five["tickets"], sorted(five["tickets"]))
            self.assertEqual(five["stake_yen"], 500)
            self.assertIsNone(boxes["human_input_research"])
            self.assertNotIn("human_research", boxes)
            for method in ("five_appearance_research", "mechanical_research", "box_v11_research"):
                self.assertEqual(len(set(boxes[method]["tickets"])), 6)
                self.assertEqual(boxes[method]["stake_yen"], 600)
                self.assertFalse(boxes[method]["formal_box_v1_reproduction"])
            snapshots[race["race_id"]] = readback["forecast_raw"]
        self.assertEqual(len(snapshots), 12)
        for race_id, expected in snapshots.items():
            self.assertEqual(store.readback(race_id)["forecast_raw"], expected)

    def test_concurrent_duplicate_and_restart_cannot_publish_second_forecast(self):
        context = self.context()
        runner, store = self.runner(context)
        self.assertEqual(store.initialize()["status"], "READY")
        capture, race = context["captures"][0], context["races"][0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: runner.run_race(capture), range(2)))
        self.assertEqual(sum(result["status"] == "COMMITTED" for result in results), 1)
        self.assertTrue(all(result["status"] in {"COMMITTED", "DUPLICATE", "HOLD"} for result in results))
        before, _ = self.forecast(store, race["race_id"])
        restart, restarted_store = self.runner(context)
        duplicate = restart.run_race(capture)
        self.assertEqual(duplicate["status"], "DUPLICATE")
        after, _ = self.forecast(restarted_store, race["race_id"])
        self.assertEqual(before["forecast_raw"], after["forecast_raw"])

    def test_runner_reuses_immutable_v003_probability_and_portfolio_math(self):
        context = self.context()
        converted = context["source_adapter"].convert(context["captures"][0])
        normalized = normalize_race(converted["raw"], context["normalizer"])["race"]
        normalized.update(deepcopy(converted["course"]))
        reference = predict_v003(normalized, context["model"], context["model_config"])
        runner, store = self.runner(context)
        self.assertEqual(runner.run_race(context["captures"][0])["status"], "COMMITTED")
        _, observed = self.forecast(store, context["races"][0]["race_id"])
        for field in ("distributions", "P_calibrated", "selection", "boxes", "bet_decision"):
            self.assertEqual(observed[field], reference[field])

    def test_missing_input_near_deadline_holds_without_imputation(self):
        context = self.context()
        race = context["races"][0]
        context["clock"].set(datetime.fromisoformat(race["deadline"]) - timedelta(milliseconds=1))
        capture = resign_capture(context["captures"][0],
            lambda document: document["invented_raw"]["boats"][0]["features"].pop("exhibition"))
        runner, store = self.runner(context)
        report = runner.run_race(capture)
        self.assertEqual(report["status"], "HOLD")
        self.assertNotEqual(store.readback(race["race_id"])["status"], "COMMITTED")

    def test_source_exception_is_safe_hold_without_sensitive_exception_text(self):
        context = self.context()
        class BrokenSource(SourceAdapter):
            def convert(self, capture):
                raise RuntimeError(SENTINEL)
        runner, _ = self.runner(context, source_adapter=BrokenSource(context["mapping"]))
        report = runner.run_race(context["captures"][0])
        self.assertEqual(report["status"], "HOLD")
        self.assertNotIn(SENTINEL, json.dumps(report))

    def test_ambiguous_persist_failure_is_durable_stop_and_preserves_partial_files(self):
        context = self.context()
        def fault(stage):
            if stage == "commit_after_input":
                raise OSError(SENTINEL)
        broken_store = ShadowStore(context["settings"]["storage_root"], clock=context["clock"], fault=fault)
        runner, store = self.runner(context, broken_store)
        report = runner.run_race(context["captures"][0])
        self.assertIn(report["status"], {"HOLD", "STOPPED"})
        self.assertNotIn(SENTINEL, json.dumps(report))
        self.assertTrue(store.is_stopped())
        root = Path(context["settings"]["storage_root"])
        preserved = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("input.raw")}
        self.assertEqual(len(preserved), 1)
        restarted, restarted_store = self.runner(context)
        retry = restarted.run_race(context["captures"][0])
        self.assertIn(retry["status"], {"HOLD", "STOPPED"})
        self.assertTrue(restarted_store.is_stopped())
        self.assertEqual(preserved, {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("input.raw")})

    def test_deadline_crossed_during_persist_is_not_a_valid_forecast(self):
        context = self.context()
        race = context["races"][0]
        def fault(stage):
            if stage == "commit_after_input":
                context["clock"].set(race["deadline"])
        store = ShadowStore(context["settings"]["storage_root"], clock=context["clock"], fault=fault)
        runner, _ = self.runner(context, store)
        report = runner.run_race(context["captures"][0])
        self.assertIn(report["status"], {"HOLD", "STOPPED"})
        self.assertTrue(store.is_stopped())
        self.assertNotEqual(store.readback(race["race_id"])["status"], "COMMITTED")

    def test_future_course_fl_and_scratch_evidence_are_not_used(self):
        for state in ("course", "fl", "scratched"):
            with self.subTest(state=state):
                context = self.context()
                deadline = context["races"][0]["deadline"]
                capture = resign_capture(context["captures"][0],
                    lambda document: document["invented_raw"]["boats"][0][state].update(available_at=deadline))
                runner, store = self.runner(context)
                self.assertEqual(runner.run_race(capture)["status"], "HOLD")
                self.assertNotEqual(store.readback(context["races"][0]["race_id"])["status"], "COMMITTED")

    def test_known_fl_flag_is_preserved_without_inventing_a_new_disqualification_rule(self):
        context = self.context()
        capture = resign_capture(context["captures"][0],
            lambda document: document["invented_raw"]["boats"][0]["fl"].update(value=True))
        runner, store = self.runner(context)
        self.assertEqual(runner.run_race(capture)["status"], "COMMITTED")
        readback, _ = self.forecast(store, context["races"][0]["race_id"])
        self.assertIs(json.loads(readback["input_raw"])["invented_raw"]["boats"][0]["fl"]["value"], True)

    def test_reduced_scratch_domain_holds_instead_of_claiming_full120(self):
        context = self.context()
        def scratch(document):
            raw = document["invented_raw"]
            raw["active_boats"] = [1, 2, 3, 4, 5]
            raw["boats"][5]["scratched"]["value"] = True
            raw["odds_snapshot"]["odds"] = {ticket: value for ticket, value in raw["odds_snapshot"]["odds"].items() if "6" not in ticket}
        capture = resign_capture(context["captures"][0], scratch)
        source_observation = context["source_adapter"].convert(capture)
        self.assertEqual(source_observation["status"], "READY")
        self.assertEqual(len(source_observation["raw"]["active_boats"]), 5)
        runner, store = self.runner(context)
        report = runner.run_race(capture)
        self.assertEqual(report["status"], "HOLD")
        self.assertNotEqual(store.readback(context["races"][0]["race_id"])["status"], "COMMITTED")

    def test_operator_stop_is_durable_and_normal_shutdown_does_not_replay(self):
        context = self.context()
        runner, store = self.runner(context)
        self.assertEqual(runner.run_race(context["captures"][0])["status"], "COMMITTED")
        before = store.readback(context["races"][0]["race_id"])["forecast_raw"]
        report = runner.shutdown()
        self.assertIn(report["status"], {"STOPPED", "SHUTDOWN"})
        self.assertIn(runner.run_race(context["captures"][1])["status"], {"HOLD", "STOPPED"})
        restarted, reopened = self.runner(context)
        duplicate = restarted.run_race(context["captures"][0])
        self.assertIn(duplicate["status"], {"DUPLICATE", "HOLD", "STOPPED"})
        self.assertEqual(reopened.readback(context["races"][0]["race_id"])["forecast_raw"], before)
        stopped = restarted.request_stop()
        self.assertIn(stopped["status"], {"HOLD", "STOPPED"})
        self.assertTrue(reopened.is_stopped())

    def test_shutdown_with_owned_pending_reservation_requires_hold_not_replay(self):
        context = self.context()
        runner, store = self.runner(context)
        self.assertEqual(runner.run_race(context["captures"][0])["status"], "COMMITTED")
        race, capture = context["races"][1], context["captures"][1]
        reservation = store.reserve(race["race_id"], hashlib.sha256(capture["payload_bytes"]).hexdigest(),
                                    canonical_hash(context["model"].to_dict()), race["deadline"])
        self.assertEqual(reservation["status"], "RESERVED")
        runner.shutdown()
        self.assertTrue(store.is_stopped())
        context["clock"].set(datetime.fromisoformat(race["prediction_at"]) + timedelta(seconds=1))
        restarted, reopened = self.runner(context)
        self.assertIn(restarted.run_race(capture)["status"], {"HOLD", "STOPPED"})
        self.assertNotEqual(reopened.readback(race["race_id"])["status"], "COMMITTED")

    def test_result_revisions_are_append_only_and_do_not_change_forecast_bytes(self):
        context = self.context()
        runner, store = self.runner(context)
        race, capture = context["races"][0], context["captures"][0]
        self.assertEqual(runner.run_race(capture)["status"], "COMMITTED")
        original, _ = self.forecast(store, race["race_id"])
        outcome = deepcopy(context["outcomes"][0])
        context["clock"].set(datetime.fromisoformat(outcome["available_at"]) + timedelta(seconds=1))
        first = runner.ingest_result(race["race_id"], outcome)
        self.assertNotIn(first["status"], {"HOLD", "STOPPED", "DISABLED"})
        listing = store.list_results(race["race_id"])
        self.assertEqual(listing["final_count"], 1)
        first_sha = listing["results"][0]["result_sha256"]
        repeat = runner.ingest_result(race["race_id"], outcome)
        self.assertNotIn(repeat["status"], {"HOLD", "STOPPED", "DISABLED"})
        self.assertEqual(store.list_results(race["race_id"])["final_count"], 1)
        context["clock"].advance(1)
        revised = deepcopy(outcome)
        revised.update(result=list(reversed(outcome["result"])),
                       payout_per_100=outcome["payout_per_100"] + 100,
                       available_at=context["clock"]().isoformat())
        second = runner.ingest_result(race["race_id"], revised)
        self.assertNotIn(second["status"], {"HOLD", "STOPPED", "DISABLED"})
        listing = store.list_results(race["race_id"])
        self.assertEqual(listing["final_count"], 2)
        self.assertNotEqual(listing["results"][1]["result_sha256"], first_sha)
        self.assertEqual(store.read_result(race["race_id"], first_sha)["status"], "RESULT_READ")
        self.assertEqual(store.readback(race["race_id"])["forecast_raw"], original["forecast_raw"])
        unresolved = runner.daily_settlement(race["target_date"], {})
        self.assertEqual(unresolved["status"], "HOLD")

    def test_daily_settlement_requires_every_explicit_final_result_version(self):
        context = self.context()
        runner, store = self.runner(context)
        snapshots = {}
        for race, capture in zip(context["races"], context["captures"]):
            context["clock"].set(datetime.fromisoformat(race["prediction_at"]) + timedelta(seconds=1))
            self.assertEqual(runner.run_race(capture)["status"], "COMMITTED")
            snapshots[race["race_id"]] = store.readback(race["race_id"])["forecast_raw"]
        context["clock"].set(datetime.fromisoformat(context["outcomes"][-1]["available_at"]) + timedelta(minutes=1))
        target_date = context["races"][0]["target_date"]
        missing = runner.daily_settlement(target_date, {})
        self.assertEqual(missing["status"], "HOLD")
        selections = {}
        for outcome in context["outcomes"]:
            report = runner.ingest_result(outcome["race_id"], outcome)
            self.assertNotIn(report["status"], {"HOLD", "STOPPED", "DISABLED"})
            versions = store.list_results(outcome["race_id"])["results"]
            self.assertEqual(len(versions), 1)
            selections[outcome["race_id"]] = versions[0]["result_sha256"]
        omitted = dict(selections)
        omitted.pop(context["races"][-1]["race_id"])
        self.assertEqual(runner.daily_settlement(target_date, omitted)["status"], "HOLD")
        complete = runner.daily_settlement(target_date, selections)
        self.assertEqual(complete["status"], "SETTLED")
        evaluation = complete["report"]["evaluation"]
        self.assertEqual(evaluation["matched_final_outcome_n"], 12)
        self.assertEqual(evaluation["invalid_record_n"], 0)
        methods = evaluation["methods"]
        for method in ("five", "five_appearance_research", "mechanical_research", "box_v11_research"):
            stake_per_race = 500 if method == "five" else 600
            expected_hits = 0
            expected_return = 0
            expected_bets = 0
            for race_id, raw in snapshots.items():
                forecast = json.loads(raw)["forecast"]
                portfolio = forecast["selection"] if method == "five" else forecast["boxes"][method]
                outcome = next(value for value in context["outcomes"] if value["race_id"] == race_id)
                won = "-".join(map(str, outcome["result"])) in portfolio["tickets"]
                expected_hits += won
                expected_return += outcome["payout_per_100"] if won else 0
                expected_bets += portfolio["bet_decision"] == "BET"
            observed = methods[method]
            self.assertEqual(observed["n"], 12)
            self.assertEqual(observed["hit_n"], expected_hits)
            self.assertEqual(observed["stake_yen"], 12 * stake_per_race)
            self.assertAlmostEqual(observed["return_yen"], expected_return)
            self.assertAlmostEqual(observed["net_yen"], expected_return - 12 * stake_per_race)
            self.assertEqual(observed["action"]["n"], expected_bets)
            self.assertEqual(observed["action"]["stake_yen"], expected_bets * stake_per_race)
        self.assertEqual(methods["human_input_research"]["n"], 0)
        self.assertIsNone(methods["human_input_research"]["hit_n"])
        self.assertIsNone(methods["human_input_research"]["stake_yen"])
        self.assertIsNone(methods["human_input_research"]["hit_rate"])
        for race_id, raw in snapshots.items():
            self.assertEqual(store.readback(race_id)["forecast_raw"], raw)


if __name__ == "__main__":
    unittest.main()
