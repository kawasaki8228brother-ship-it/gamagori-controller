"""F3: frozen pre-LOCK course semantics for fitting, prior and forecasting.

Hash/timestamp checks establish internal consistency, never external authenticity.
No actual race-entry result is fetched, reconstructed or accepted as a feature.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re

from ..models import make_model, from_dict as base_model_from_dict
from ..validation import validate_race, validate_dataset

_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TIMES = ("acquired_at", "available_at", "revision_at")
_SOURCES = {
    "FRAME_NUMBER": ["OFFICIAL_FRAME_PRELOCK_V001", "SYNTHETIC_FRAME_V001"],
    "EXHIBITION_ENTRY": ["OFFICIAL_EXHIBITION_PRELOCK_V001", "SYNTHETIC_EXHIBITION_V001"],
}


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _make_policy(policy_id, selection, definitions):
    return {"schema_version": "COURSE_POLICY_V001", "policy_id": policy_id,
            "status": "PROPOSED", "selection": selection,
            "allowed_definitions": definitions,
            "fallback_only_if_exhibition_is_null": selection == "EXHIBITION_ELSE_FRAME",
            "allowed_source_ids": deepcopy(_SOURCES)}


_POLICY_TEMPLATES = {
    "FRAME_ONLY_V001": _make_policy("FRAME_ONLY_V001", "FRAME_ONLY", ["FRAME_NUMBER"]),
    "EXHIBITION_ONLY_V001": _make_policy("EXHIBITION_ONLY_V001", "EXHIBITION_ONLY", ["EXHIBITION_ENTRY"]),
    "EXHIBITION_ELSE_FRAME_V001": _make_policy("EXHIBITION_ELSE_FRAME_V001", "EXHIBITION_ELSE_FRAME", ["FRAME_NUMBER", "EXHIBITION_ENTRY"]),
}
COURSE_POLICIES = deepcopy(_POLICY_TEMPLATES)


def _time(value):
    if not isinstance(value, str) or not _TIME.fullmatch(value) or value.endswith("-00:00"):
        return None
    if value[-6:-5] in ("+", "-") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _add(codes, code):
    if code not in codes:
        codes.append(code)


def _policy(policy):
    if not isinstance(policy, dict) or not isinstance(policy.get("policy_id"), str):
        return None
    frozen = _POLICY_TEMPLATES.get(policy["policy_id"])
    if frozen is None:
        return None
    try:
        return deepcopy(frozen) if canonical_hash(policy) == canonical_hash(frozen) else None
    except (ValueError, TypeError, OverflowError, RecursionError):
        return None


def _observation(value, definition, prediction, boats, errors):
    if value is None:
        return None
    required = {"definition", "courses", "source_id", *_TIMES, "evidence_sha256"}
    if not isinstance(value, dict) or set(value) != required:
        _add(errors, "COURSE_OBSERVATION_FIELDS")
        return None
    if value["definition"] != definition:
        _add(errors, "COURSE_DEFINITION_UNKNOWN_OR_MISMATCH")
    if value["source_id"] not in _SOURCES[definition]:
        _add(errors, "COURSE_SOURCE_NOT_PREDECLARED")
    digest = value["evidence_sha256"]
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        _add(errors, "COURSE_EVIDENCE_HASH_INVALID")
    times = {field: _time(value[field]) for field in _TIMES}
    if any(stamp is None for stamp in times.values()):
        _add(errors, "COURSE_OBSERVATION_TIME_INVALID")
    if prediction and any(stamp and stamp > prediction for stamp in times.values()):
        _add(errors, "COURSE_OBSERVATION_FUTURE_OR_LATE_REVISION")
    acquired, available, revised = (times[field] for field in _TIMES)
    if acquired and available and acquired > available:
        _add(errors, "COURSE_AVAILABLE_BEFORE_ACQUIRED")
    if acquired and revised and acquired > revised:
        _add(errors, "COURSE_REVISION_BEFORE_ACQUIRED")
    courses = value["courses"]
    domain = {str(boat) for boat in boats}
    if (not isinstance(courses, dict) or set(courses) != domain
            or any(type(course) is not int or not 1 <= course <= 6 for course in courses.values())
            or len(set(courses.values())) != len(domain)):
        _add(errors, "COURSE_DOMAIN_OR_PERMUTATION_INVALID")
    elif definition == "FRAME_NUMBER" and any(courses[str(boat)] != boat for boat in boats):
        _add(errors, "FRAME_NUMBER_MUST_EQUAL_BOAT_ID")
    return deepcopy(value)


def validate_course(race, policy):
    """Reject unknown/present-invalid observations; fallback is null-only.

    Both present observations are checked even if the frozen policy selects one.
    Every selected numeric course and state timestamp must match its observation.
    """
    errors = []
    frozen = _policy(policy)
    if frozen is None:
        return {"eligible": False, "status": "HOLD", "errors": ["COURSE_POLICY_UNKNOWN_OR_CHANGED"],
                "definition": None, "policy_sha256": None, "selected_observation": None,
                "external_authenticity": "UNVERIFIED", "production_go": False}
    digest = canonical_hash(frozen)
    result = {"eligible": False, "status": "HOLD", "errors": errors, "definition": None,
              "policy_sha256": digest, "policy_id": frozen["policy_id"],
              "selected_observation": None, "observations": None,
              "external_authenticity": "UNVERIFIED", "policy_status": "PROPOSED", "production_go": False}
    if not isinstance(race, dict):
        errors.append("COURSE_RACE_SHAPE")
        return result
    try:
        core = validate_race(race)
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("COURSE_RACE_SCHEMA_INVALID")
        return result
    if not core["eligible"]:
        errors.append("COURSE_RACE_SCHEMA_INVALID")
    if race.get("course_policy_sha256") != digest or race.get("course_policy_id") != frozen["policy_id"]:
        _add(errors, "COURSE_RACE_POLICY_BINDING_MISMATCH")
    predicted = _time(race.get("prediction_at"))
    if predicted is None:
        _add(errors, "COURSE_PREDICTION_TIME_INVALID")
    boats = race.get("boats")
    if (not isinstance(boats, list) or not boats
            or any(not isinstance(boat, dict) or type(boat.get("boat")) is not int
                   or not 1 <= boat["boat"] <= 6 for boat in boats)):
        _add(errors, "COURSE_BOAT_DOMAIN_INVALID")
        return result
    numbers = [boat["boat"] for boat in boats]
    if len(set(numbers)) != len(numbers):
        _add(errors, "COURSE_BOAT_DOMAIN_INVALID")
    inputs = race.get("course_inputs")
    if not isinstance(inputs, dict) or set(inputs) != {"frame", "exhibition"}:
        _add(errors, "COURSE_INPUTS_MISSING_OR_UNREGISTERED")
        return result
    frame = _observation(inputs["frame"], "FRAME_NUMBER", predicted, numbers, errors)
    exhibition = _observation(inputs["exhibition"], "EXHIBITION_ENTRY", predicted, numbers, errors)
    selected = None
    if frozen["selection"] == "FRAME_ONLY":
        selected = frame
    elif frozen["selection"] == "EXHIBITION_ONLY":
        selected = exhibition
    elif inputs["exhibition"] is None:
        selected = frame
    else:
        selected = exhibition
    if selected is None:
        _add(errors, "COURSE_REQUIRED_OBSERVATION_MISSING")
    if selected is not None:
        if isinstance(selected["definition"], str) and selected["definition"] in _SOURCES:
            result["definition"] = selected["definition"]
        if selected["definition"] not in frozen["allowed_definitions"]:
            _add(errors, "COURSE_MIXED_DEFINITION_NOT_PREDECLARED")
        for boat in boats:
            expected = selected["courses"].get(str(boat["boat"])) if isinstance(selected["courses"], dict) else None
            if boat.get("course") != expected:
                _add(errors, "COURSE_NUMERIC_OBSERVATION_MISMATCH")
            state = boat.get("state_times")
            course_times = state.get("course") if isinstance(state, dict) else None
            if (not isinstance(course_times, dict) or set(course_times) != set(_TIMES)
                    or any(course_times.get(field) != selected[field] for field in _TIMES)):
                _add(errors, "COURSE_STATE_TIME_BINDING_MISMATCH")
    if not errors:
        result.update(eligible=True, status="COURSE_CLAIMS_CONSISTENT",
                      selected_observation=selected,
                      observations={"frame": frame, "exhibition": exhibition})
    return result


def apply_course_fixture(race, policy_id="EXHIBITION_ONLY_V001", exhibition_present=True):
    """Detach invented pre-LOCK course fixtures; never turn real data synthetic."""
    if (not isinstance(race, dict) or race.get("synthetic") is not True
            or race.get("data_classification") != "SYNTHETIC_ONLY"
            or not isinstance(race.get("target_date"), str) or not race["target_date"].startswith("2099-")):
        raise ValueError("COURSE_SYNTHETIC_FIXTURE_ONLY")
    if not isinstance(policy_id, str) or policy_id not in _POLICY_TEMPLATES or type(exhibition_present) is not bool:
        raise ValueError("COURSE_FIXTURE_POLICY_OR_PRESENCE_INVALID")
    if not validate_race(race)["eligible"]:
        raise ValueError("COURSE_SYNTHETIC_SOURCE_INVALID")
    detached = deepcopy(race)
    policy = deepcopy(_POLICY_TEMPLATES[policy_id])
    numbers = sorted(boat["boat"] for boat in detached["boats"])
    # Deliberately different from frame numbering, not a reconstructed real entry.
    shifted = numbers[1:] + numbers[:1]
    times = deepcopy(detached["boats"][0]["state_times"]["course"])
    def observation(definition, courses, source):
        return {"definition": definition, "courses": courses, "source_id": source,
                **deepcopy(times), "evidence_sha256": canonical_hash({"synthetic_course_fixture": definition,
                                                                       "race_id": race["race_id"], "courses": courses})}
    frame = observation("FRAME_NUMBER", {str(number): number for number in numbers}, "SYNTHETIC_FRAME_V001")
    exhibition = observation("EXHIBITION_ENTRY", dict(zip(map(str, numbers), shifted)), "SYNTHETIC_EXHIBITION_V001") if exhibition_present else None
    detached["course_inputs"] = {"frame": frame, "exhibition": exhibition}
    detached["course_policy_id"] = policy_id
    detached["course_policy_sha256"] = canonical_hash(policy)
    selected = frame if policy["selection"] == "FRAME_ONLY" or exhibition is None else exhibition
    for boat in detached["boats"]:
        boat["course"] = selected["courses"][str(boat["boat"])]
        boat["state_times"]["course"] = {field: selected[field] for field in _TIMES}
    detached["human_box_input"] = None
    return detached


class CourseBoundModel:
    """Actual old learning kernel, frozen course semantics across fit/predict."""
    def __init__(self, name, model_config=None, course_policy=None):
        supplied = COURSE_POLICIES["EXHIBITION_ONLY_V001"] if course_policy is None else course_policy
        frozen = _policy(supplied)
        if frozen is None:
            raise ValueError("COURSE_POLICY_UNKNOWN_OR_CHANGED")
        self._course_policy = frozen
        self._course_policy_sha256 = canonical_hash(frozen)
        self._base_model = make_model(name, model_config)
        self._training_definitions = []
        self._training_course_sha256 = None
        self._training_policy_sha256 = None

    @property
    def course_policy(self):
        return deepcopy(self._course_policy)

    @property
    def course_policy_sha256(self):
        return self._course_policy_sha256

    @property
    def name(self):
        return self._base_model.name

    @property
    def config(self):
        return deepcopy(self._base_model.config)

    @property
    def training_count(self):
        return self._base_model.training_count

    @property
    def training_max_available_at(self):
        return self._base_model.training_max_available_at

    @property
    def training_max_prediction_at(self):
        return self._base_model.training_max_prediction_at

    def _guard_policy(self):
        if (_policy(self._course_policy) is None
                or canonical_hash(self._course_policy) != self._course_policy_sha256
                or self.training_count and self._training_policy_sha256 != self._course_policy_sha256):
            raise ValueError("COURSE_BOUND_POLICY_CHANGED")

    def _guard(self, race):
        self._guard_policy()
        report = validate_course(race, self._course_policy)
        if not report["eligible"]:
            raise ValueError("COURSE_INPUT_HOLD")
        return report

    def fit(self, races, outcomes):
        self._guard_policy()
        if not isinstance(races, list) or not races:
            raise ValueError("COURSE_TRAINING_DATA_MISSING")
        reports = [self._guard(race) for race in races]
        if not validate_dataset(races, outcomes)["eligible"]:
            raise ValueError("COURSE_TRAINING_SCHEMA_HOLD")
        definitions = sorted({report["definition"] for report in reports})
        if not set(definitions).issubset(self._course_policy["allowed_definitions"]):
            raise ValueError("COURSE_TRAINING_MIX_NOT_PREDECLARED")
        provenance = [{"race_id": race["race_id"], "policy_sha256": report["policy_sha256"],
                       "definition": report["definition"], "observation": report["selected_observation"]}
                      for race, report in zip(races, reports)]
        self._base_model.fit(races, outcomes)
        self._training_definitions = definitions
        self._training_course_sha256 = canonical_hash(sorted(provenance, key=lambda item: item["race_id"]))
        self._training_policy_sha256 = self._course_policy_sha256
        return self

    def distributions(self, race):
        self._guard(race)
        return self._base_model.distributions(race)

    def conditionals(self, race, first=None, second=None, stage="raw"):
        self._guard(race)
        return self._base_model.conditionals(race, first, second, stage)

    def explain(self, race, first=None, second=None, stage="model"):
        self._guard(race)
        return self._base_model.explain(race, first, second, stage)

    def to_dict(self):
        self._guard_policy()
        payload = {"schema_version": "COURSE_BOUND_MODEL_V001", "course_policy": self.course_policy,
                   "course_policy_sha256": self._course_policy_sha256,
                   "training_policy_sha256": self._training_policy_sha256,
                   "training_course_definitions": list(self._training_definitions),
                   "training_course_provenance_sha256": self._training_course_sha256,
                   "base_model": self._base_model.to_dict(),
                   "external_authenticity": "UNVERIFIED", "production_go": False}
        payload["self_sha256"] = canonical_hash(payload)
        return payload

    @classmethod
    def from_dict(cls, payload):
        expected = {"schema_version", "course_policy", "course_policy_sha256", "training_policy_sha256",
                    "training_course_definitions", "training_course_provenance_sha256", "base_model",
                    "external_authenticity", "production_go", "self_sha256"}
        if not isinstance(payload, dict) or set(payload) != expected or payload["schema_version"] != "COURSE_BOUND_MODEL_V001":
            raise ValueError("COURSE_MODEL_SERIALIZATION_INVALID")
        try:
            actual = canonical_hash({key: value for key, value in payload.items() if key != "self_sha256"})
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise ValueError("COURSE_MODEL_SERIALIZATION_INVALID") from None
        if actual != payload["self_sha256"]:
            raise ValueError("COURSE_MODEL_SERIALIZED_HASH_MISMATCH")
        policy = _policy(payload["course_policy"])
        if policy is None or payload["course_policy_sha256"] != canonical_hash(policy):
            raise ValueError("COURSE_MODEL_POLICY_MISMATCH")
        if payload["external_authenticity"] != "UNVERIFIED" or payload["production_go"] is not False:
            raise ValueError("COURSE_MODEL_UNSUPPORTED_AUTHORITY_CLAIM")
        try:
            base = base_model_from_dict(payload["base_model"])
        except (ValueError, TypeError, KeyError, OverflowError):
            raise ValueError("COURSE_BASE_MODEL_INVALID") from None
        definitions, provenance = payload["training_course_definitions"], payload["training_course_provenance_sha256"]
        if (not isinstance(definitions, list) or any(item not in policy["allowed_definitions"] for item in definitions)
                or len(set(definitions)) != len(definitions)):
            raise ValueError("COURSE_SERIALIZED_TRAINING_DEFINITIONS_INVALID")
        if base.training_count:
            if (not definitions or payload["training_policy_sha256"] != payload["course_policy_sha256"]
                    or not isinstance(provenance, str) or not _SHA.fullmatch(provenance)):
                raise ValueError("COURSE_SERIALIZED_TRAINING_BINDING_INVALID")
        elif definitions or provenance is not None or payload["training_policy_sha256"] is not None:
            raise ValueError("COURSE_UNFITTED_BINDING_INVALID")
        model = cls(base.name, base.config, policy)
        model._base_model = base
        model._training_definitions = list(definitions)
        model._training_course_sha256 = provenance
        model._training_policy_sha256 = payload["training_policy_sha256"]
        return model


def from_dict(payload):
    """Module-level convenience matching the old model loader convention."""
    return CourseBoundModel.from_dict(payload)
