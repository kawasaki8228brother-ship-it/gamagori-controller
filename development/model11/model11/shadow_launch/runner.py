"""Explicit independent runner. Constructor/import/default DISABLED do no I/O."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading

from ..engine import canonical_hash
from ..preparation.adapter import normalize_race
from ..validation import validate_outcome, _timestamp as _strict_timestamp
from ..revision_v003.evaluation import evaluate_records_v003
from .candidate import forecast_candidate
from .policy import preflight
from .storage import ShadowStore


def _bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()


def _time(value):
    parsed = _strict_timestamp(value)
    if parsed is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    return parsed


class ShadowRunner:
    def __init__(self, settings=None, model=None, model_config=None, normalizer=None,
                 source_adapter=None, store=None, artifacts=None, clock=None):
        self.settings = deepcopy({"enabled": False} if settings is None else settings)
        self._enabled_at_construction = isinstance(self.settings, dict) and self.settings.get("enabled") is True
        self.model, self.source_adapter = model, source_adapter
        self.normalizer = deepcopy(normalizer) if self._enabled_at_construction else normalizer
        self.model_config = {} if model_config is None else deepcopy(model_config)
        self.artifacts = deepcopy({} if artifacts is None else artifacts) if self._enabled_at_construction else artifacts
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.store = store
        self._init_lock = threading.RLock()
        self._closed = False
        self._storage_id = None

    def _now(self):
        value = self.clock()
        if isinstance(value, str):
            value = _time(value)
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("RUNNER_CLOCK_UNKNOWN")
        return value

    def _prepare(self, operator_ack=None):
        if not self._enabled_at_construction or not isinstance(self.settings, dict) or self.settings.get("enabled") is not True:
            return preflight({"enabled": False}, {}, now=None)
        if self._closed:
            return {"allowed": False, "status": "STOPPED", "reasons": ["RUNNER_SHUT_DOWN"]}
        try:
            gate = preflight(self.settings, self.artifacts, operator_ack=operator_ack, now=self._now())
            if not gate["allowed"]:
                return gate
            if (self.model is None or self.model.to_dict() != self.artifacts["model"]
                    or self.normalizer != self.artifacts["normalizer"]
                    or self.model_config != self.artifacts["prediction_config"]
                    or self.source_adapter is None or self.source_adapter.mapping != self.artifacts["source_mapping"]):
                return {"allowed": False, "status": "HOLD", "reasons": ["ACTUAL_COMPONENTS_DO_NOT_MATCH_FROZEN_ARTIFACTS"]}
            expected_class = "SYNTHETIC_ONLY" if self.settings["mode"] == "SIMULATION" else "PRIVATE_REAL"
            expected_flag = self.settings["mode"] == "SIMULATION"
            if (self.source_adapter.mapping.get("data_classification") != expected_class
                    or self.source_adapter.mapping.get("synthetic") is not expected_flag):
                return {"allowed": False, "status": "HOLD", "reasons": ["SOURCE_MAPPING_EXECUTION_MODE_MISMATCH"]}
            with self._init_lock:
                if self.store is None:
                    self.store = ShadowStore(self.settings["storage_root"], self.settings["namespace"], clock=self.clock)
                if (Path(self.store.root) != Path(self.settings["storage_root"])
                        or self.store.namespace != self.settings["namespace"]):
                    return {"allowed": False, "status": "HOLD", "reasons": ["ACTUAL_STORAGE_CONFIGURATION_MISMATCH"]}
                if self._storage_id is None:
                    ready = self.store.initialize()
                    if ready["status"] != "READY":
                        return {"allowed": False, "status": "HOLD", "reasons": ["STORE_NOT_READY"], "store": ready}
                    self._storage_id = ready["storage_id"]
                binding = {"storage_id": self._storage_id, "config_sha256": gate["config_sha256"],
                           "storage_identity_sha256": gate["storage_identity_sha256"],
                           "artifact_sha256s": gate["artifact_sha256s"]}
                pinned = self.store.bind_context(canonical_hash(binding))
                if pinned["status"] != "CONTEXT_PINNED":
                    return {"allowed": False, "status": "HOLD", "reasons": ["STORE_CONTEXT_PIN_HOLD"], "store": pinned}
                if self.store.is_stopped():
                    return {"allowed": False, "status": "STOPPED", "reasons": ["DURABLE_STOP_SET"]}
            return gate
        except Exception:
            return {"allowed": False, "status": "HOLD", "reasons": ["PREFLIGHT_OR_STORE_UNVERIFIED"]}

    def run_race(self, capture, human_input=None, operator_ack=None):
        gate = self._prepare(operator_ack)
        if not gate["allowed"]:
            return {**gate, "production_go": False}
        reservation = None
        try:
            converted = self.source_adapter.convert(capture)
            if converted["status"] != "READY":
                return {"status": "HOLD", "reasons": converted.get("reasons", ["SOURCE_HOLD"]), "production_go": False}
            race = normalize_race(converted["raw"], self.normalizer)["race"]
            race.update(deepcopy(converted["course"]))
            if len(race["active_boats"]) != 6:
                return {"status": "HOLD", "reasons": ["SIX_ACTIVE_BOATS_REQUIRED_FOR_120_OUTCOMES"], "production_go": False}
            now, deadline = self._now(), _time(race["deadline"])
            if not _time(race["prediction_at"]) <= now < deadline:
                return {"status": "HOLD", "reasons": ["SNAPSHOT_OR_DEADLINE_CLOCK_HOLD"], "production_go": False}
            raw_input = capture["payload_bytes"]
            reservation = self.store.reserve(race["race_id"], hashlib.sha256(raw_input).hexdigest(),
                                              canonical_hash(self.model.to_dict()), race["deadline"])
            if reservation["status"] != "RESERVED":
                return {**reservation, "production_go": False}
            forecast = forecast_candidate(race, self.model, self.model_config, self.settings, self.artifacts,
                                           now, operator_ack=operator_ack, human_input=human_input)
            generated = self._now()
            if not now <= generated < deadline:
                held = self.store.mark_hold(reservation, "FORECAST_FINISHED_AFTER_DEADLINE_OR_CLOCK_REVERSED")
                return {"status": "HOLD", "reasons": ["FORECAST_CLOCK_HOLD"], "store": held, "production_go": False}
            envelope = {"schema": "MODEL11_INDEPENDENT_SHADOW_RECORD_V005",
                        "namespace": self.settings["namespace"], "ModelVersion": "MODEL_1.1_SHADOW_LAUNCH_CANDIDATE_V005",
                        "mode": self.settings["mode"], "race_id": race["race_id"], "target_date": race["target_date"],
                        "generated_at": generated.isoformat(), "deadline": race["deadline"],
                        "source_evidence": converted["source_evidence"], "forecast": forecast,
                        "reproduction": {"code_commit": self.settings["code_commit"],
                                         "artifact_sha256s": gate["artifact_sha256s"],
                                         "config_sha256": gate["config_sha256"],
                                         "storage_identity_sha256": gate["storage_identity_sha256"]},
                        "validity": "REQUIRES_COMMITTED_LEDGER_COMPLETION_AND_READBACK",
                        "external_authenticity": "UNVERIFIED", "production_go": False}
            forecast_raw = _bytes(envelope)
            saved = self.store.commit(reservation, raw_input, forecast_raw,
                                      {"generated_at": generated.isoformat(), "source_payload_sha256": converted["source_evidence"]["payload_sha256"],
                                       "normalized_input_sha256": canonical_hash(race), "forecast_sha256": hashlib.sha256(forecast_raw).hexdigest()})
            if saved["status"] != "COMMITTED":
                return {"status": "HOLD", "reasons": ["SAVE_NOT_ACKNOWLEDGED_VALID"], "store": saved, "production_go": False}
            check = self.store.readback(race["race_id"])
            if check["status"] != "COMMITTED" or check["forecast_raw"] != forecast_raw or check["input_raw"] != raw_input:
                held = self.store.mark_hold(reservation, "RUNNER_READBACK_UNCERTAIN")
                return {"status": "HOLD", "reasons": ["READBACK_UNCERTAIN"], "store": held, "production_go": False}
            if self._now() >= deadline:
                held = self.store.mark_hold(reservation, "DEADLINE_DURING_FINAL_READBACK")
                return {"status": "HOLD", "reasons": ["LATE_FINAL_READBACK"], "store": held, "production_go": False}
            return {"status": "COMMITTED", "race_id": race["race_id"], "forecast": forecast,
                    "receipt": check["receipt"], "receipt_sha256": check["receipt_sha256"],
                    "raw_forecast_sha256": hashlib.sha256(forecast_raw).hexdigest(), "production_go": False}
        except Exception:
            held = self.store.mark_hold(reservation, "RUNNER_PROCESSING_OR_SAVE_UNCERTAIN") if reservation and reservation.get("status") == "RESERVED" else None
            return {"status": "HOLD", "reasons": ["INPUT_OR_EXECUTION_UNVERIFIED"], "store": held, "production_go": False}

    def ingest_result(self, race_id, outcome, operator_ack=None):
        gate = self._prepare(operator_ack)
        if not gate["allowed"]:
            return {**gate, "production_go": False}
        try:
            existing = self.store.readback(race_id)
            if existing["status"] != "COMMITTED":
                return {"status": "HOLD", "reasons": ["RESULT_WITHOUT_VERIFIED_FORECAST"]}
            envelope = json.loads(existing["forecast_raw"])
            if (not isinstance(outcome, dict) or outcome.get("race_id") != race_id
                    or outcome.get("target_date") != envelope["target_date"]
                    or type(outcome.get("final")) is not bool
                    or _time(outcome["available_at"]) > self._now()):
                return {"status": "HOLD", "reasons": ["RESULT_IDENTITY_OR_TIME_HOLD"]}
            if outcome["final"] and not validate_outcome(outcome)["eligible"]:
                return {"status": "HOLD", "reasons": ["FINAL_RESULT_SCHEMA_HOLD"]}
            return self.store.save_result(race_id, _bytes(outcome),
                                         {key: outcome[key] for key in ("race_id", "final", "available_at")})
        except Exception:
            return {"status": "HOLD", "reasons": ["RESULT_INPUT_UNVERIFIED"]}

    def daily_settlement(self, target_date, result_selection, operator_ack=None):
        gate = self._prepare(operator_ack)
        if not gate["allowed"]:
            return {**gate, "production_go": False}
        if not isinstance(result_selection, dict) or not result_selection:
            return {"status": "HOLD", "reasons": ["EXPLICIT_RESULT_SELECTION_REQUIRED"]}
        records = []
        try:
            observed = self.store.list_forecasts()
            if observed["status"] != "FORECASTS_LISTED":
                raise ValueError("FORECAST_SCOPE_UNVERIFIED")
            expected = set()
            for item in observed["forecasts"]:
                stored = self.store.readback(item["race_id"])
                if stored["status"] != "COMMITTED":
                    raise ValueError("UNRESOLVED_FORECAST_IN_STORE")
                if json.loads(stored["forecast_raw"])["target_date"] == target_date:
                    expected.add(item["race_id"])
            if set(result_selection) != expected:
                raise ValueError("INCOMPLETE_OR_EXTRA_RESULT_SELECTION")
            for race_id, digest in sorted(result_selection.items()):
                selected = self.store.select_result(race_id, digest,
                    {"explicit": True, "selection_id": "SETTLEMENT_" + canonical_hash({race_id: digest})[:24]})
                if selected["status"] != "RESULT_SELECTED":
                    raise ValueError("RESULT_SELECTION_HOLD")
                actual = self.store.read_selected_result(race_id)
                prior = self.store.readback(race_id)
                if actual["status"] != "RESULT_READ" or prior["status"] != "COMMITTED":
                    raise ValueError("SETTLEMENT_READBACK_HOLD")
                envelope = json.loads(prior["forecast_raw"])
                outcome = json.loads(actual["raw_result"])
                if envelope["target_date"] != target_date or not validate_outcome(outcome)["eligible"]:
                    raise ValueError("SETTLEMENT_DATE_OR_OUTCOME_HOLD")
                record = deepcopy(envelope["forecast"])
                record["actual"] = outcome
                course = record["course_evidence"]["selected_observation"]["courses"]
                record["first_course"] = course[str(outcome["result"][0])]
                records.append(record)
            report = {"schema": "MODEL11_SHADOW_DAILY_SETTLEMENT_V005", "target_date": target_date,
                      "selected_results": deepcopy(result_selection), "evaluation": evaluate_records_v003(records),
                      "scope": "ALL_COMMITTED_STORE_FORECASTS_FOR_DATE_OFFICIAL_SCHEDULE_COMPLETENESS_UNVERIFIED",
                      "production_go": False}
            saved = self.store.save_audit_report("DAILY_SETTLEMENT", target_date, _bytes(report),
                                                  {"selected_results": deepcopy(result_selection)})
            if saved["status"] not in ("AUDIT_SAVED", "AUDIT_DUPLICATE"):
                return {"status": "HOLD", "reasons": ["SETTLEMENT_SAVE_HOLD"], "store": saved}
            return {"status": "SETTLED", "report": report, "receipt": saved, "production_go": False}
        except Exception:
            return {"status": "HOLD", "reasons": ["SETTLEMENT_UNVERIFIED"], "production_go": False}

    def request_stop(self, reason="OPERATOR_STOP"):
        self._closed = True
        if self.store is None or self._storage_id is None:
            return {"status": "DISABLED", "reasons": ["NO_INITIALIZED_SHADOW_STORE"], "production_go": False}
        return self.store.stop(reason)

    def shutdown(self):
        self._closed = True
        closed = self.store.close() if self.store is not None and self._storage_id is not None else None
        return {"status": "SHUTDOWN", "store_close": closed,
                "reservations_replayed": False, "production_go": False}
