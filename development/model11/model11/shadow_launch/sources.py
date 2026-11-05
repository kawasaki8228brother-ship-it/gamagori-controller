"""Pure local, explicit JSON-pointer capture conversion; no HTTP implementation.

LOCAL_CAPTURE_V001 is invented fixture format, not an official-site parser.
READY establishes internally consistent submitted claims, never authentication.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import re

from ..preparation.adapter import (
    make_raw_fixture, synthetic_feature_specs, validate_raw_race,
    _compatible as _raw_schema_probe,
)
from ..validation import FEATURES
from ..revision_v003.course import (
    COURSE_POLICIES, apply_course_fixture, canonical_hash, validate_course,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
_TIMES = ("acquired_at", "available_at", "revision_at")
_RAW_FIELDS = {"schema_version", "data_classification", "race_id", "target_date", "venue", "prediction_at",
               "race_provenance", "deadline", "active_boats", "active_boats_provenance", "boats", "odds_snapshot"}
_COURSE_FIELDS = {"course_inputs", "course_policy_id", "course_policy_sha256", "data_classification", "synthetic"}
_CAPTURE_FIELDS = {"format_id", "data_classification", "synthetic", "source_id", "payload_bytes",
                   "payload_sha256", *_TIMES, "history"}
_PROFILE = {
    "SYNTHETIC_ONLY": {"flag": True, "format": "LOCAL_CAPTURE_V001", "capture_source": "SYNTHETIC_LOCAL_CAPTURE_V001",
                       "frame": "SYNTHETIC_FRAME_V001", "exhibition": "SYNTHETIC_EXHIBITION_V001",
                       "raw_class": "SYNTHETIC_ONLY", "mapping": "SYNTHETIC_INVENTED_ONLY"},
    "PRIVATE_REAL": {"flag": False, "format": "PRIVATE_REVIEWED_JSON_V001", "capture_source": "OFFICIAL_REVIEWED_LOCAL_CAPTURE_V001",
                     "frame": "OFFICIAL_FRAME_PRELOCK_V001", "exhibition": "OFFICIAL_EXHIBITION_PRELOCK_V001",
                     "raw_class": "HQ14_PRIVATE_OFFLINE", "mapping": "HQ14_PRIVATE_MAPPING_UNVERIFIED"},
}


def _digest(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _stamp(value):
    if not isinstance(value, str) or not _TIME.fullmatch(value) or value.endswith("-00:00"):
        return None
    if value[-6:-5] in ("+", "-") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pointer_tokens(pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/") or len(pointer) > 2000:
        raise ValueError("SOURCE_POINTER_INVALID")
    result = []
    for token in pointer[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("SOURCE_POINTER_INVALID")
        result.append(token.replace("~1", "/").replace("~0", "~"))
    return result


def _resolve(document, pointer):
    value = document
    for token in _pointer_tokens(pointer):
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
            index = int(token)
            if index >= len(value):
                raise ValueError("SOURCE_FIELD_MISSING")
            value = value[index]
        else:
            raise ValueError("SOURCE_FIELD_MISSING")
    return deepcopy(value)


def _reject_constant(value):
    raise ValueError("SOURCE_JSON_NONFINITE")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("SOURCE_JSON_DUPLICATE_KEY")
        obj[key] = value
    return obj


def _mapping_errors(mapping):
    required = {"schema_version", "version", "format_id", "data_classification", "synthetic", "source_id",
                "raw_fields", "course_fields", "feature_units", "feature_specs", "course_source_ids"}
    if not isinstance(mapping, dict):
        return ["SOURCE_MAPPING_REQUIRED"]
    classification = mapping.get("data_classification")
    profile = _PROFILE.get(classification) if isinstance(classification, str) else None
    if profile and classification == "PRIVATE_REAL":
        required.add("review_evidence")
    if set(mapping) != required or mapping.get("schema_version") != "SOURCE_MAPPING_V001":
        return ["SOURCE_MAPPING_SCHEMA_INVALID"]
    if profile is None or type(mapping["synthetic"]) is not bool or mapping["synthetic"] is not profile["flag"]:
        return ["SOURCE_MAPPING_CLASSIFICATION_INVALID"]
    if (mapping["format_id"] != profile["format"] or mapping["source_id"] != profile["capture_source"]
            or not isinstance(mapping["version"], str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", mapping["version"])):
        return ["SOURCE_MAPPING_FORMAT_OR_SOURCE_UNREVIEWED"]
    for field, expected in (("raw_fields", _RAW_FIELDS), ("course_fields", _COURSE_FIELDS)):
        paths = mapping[field]
        if not isinstance(paths, dict) or set(paths) != expected:
            return ["SOURCE_MAPPING_FIELDS_INVALID"]
        try:
            for pointer in paths.values():
                _pointer_tokens(pointer)
        except ValueError:
            return ["SOURCE_MAPPING_POINTER_INVALID"]
    sources = mapping["course_source_ids"]
    if sources != {"frame": profile["frame"], "exhibition": profile["exhibition"]}:
        return ["SOURCE_MAPPING_COURSE_SOURCES_UNREVIEWED"]
    specs, units = mapping["feature_specs"], mapping["feature_units"]
    if (not isinstance(specs, dict) or specs.get("mapping_status") != profile["mapping"]
            or not isinstance(specs.get("features"), dict) or set(specs["features"]) != set(FEATURES)
            or not isinstance(units, dict) or set(units) != set(FEATURES)
            or any(not isinstance(specs["features"][name], dict)
                   or units[name] != specs["features"][name].get("unit") for name in FEATURES)):
        return ["SOURCE_MAPPING_FEATURE_UNITS_UNREVIEWED"]
    if classification == "PRIVATE_REAL":
        review = mapping["review_evidence"]
        if (not isinstance(review, dict) or set(review) != {"hq14_review_sha256", "claude_review_sha256"}
                or not all(_digest(value) for value in review.values()) or specs.get("review_evidence") != review):
            return ["SOURCE_MAPPING_PRIVATE_REVIEW_METADATA_REQUIRED"]
    try:
        canonical_hash(mapping)
    except (TypeError, ValueError, RecursionError, OverflowError):
        return ["SOURCE_MAPPING_NOT_JSON"]
    return []


def _times(item, prediction, prefix):
    times = {key: _stamp(item.get(key)) for key in _TIMES}
    if any(value is None for value in times.values()):
        return [prefix + "_TIME_INVALID"]
    if any(value > prediction for value in times.values()):
        return [prefix + "_LATE_OR_FUTURE_REVISION"]
    if times["acquired_at"] > times["available_at"] or times["acquired_at"] > times["revision_at"]:
        return [prefix + "_TIME_ORDER_INVALID"]
    return []


class FixtureTransport:
    """Explicit in-memory fixture transport; never opens files or a socket."""
    def __init__(self, captures):
        self._captures = deepcopy(captures)

    def fetch(self, capture_id):
        if not isinstance(self._captures, dict) or not isinstance(capture_id, str) or capture_id not in self._captures:
            raise ValueError("SOURCE_FIXTURE_NOT_FOUND")
        return deepcopy(self._captures[capture_id])


class SourceAdapter:
    """Frozen declared mapping; construction and conversion perform no I/O."""
    def __init__(self, mapping, transport=None):
        self._mapping = deepcopy(mapping)
        self._transport = transport
        self._mapping_errors = _mapping_errors(self._mapping)
        try:
            self._mapping_sha256 = canonical_hash(self._mapping)
        except (TypeError, ValueError, RecursionError, OverflowError):
            self._mapping_sha256 = None

    @property
    def mapping(self):
        return deepcopy(self._mapping)

    @property
    def mapping_sha256(self):
        return self._mapping_sha256

    def _hold(self, reasons):
        return {"status": "HOLD", "raw": None, "course": None,
                "source_evidence": {"external_authenticity": "UNVERIFIED", "actual_official_mapping": "OPEN"},
                "reasons": list(dict.fromkeys(reasons)), "production_go": False}

    def fetch(self, capture_id):
        """Optional explicit fixture-only path. There is no live transport client."""
        if type(self._transport) is not FixtureTransport:
            return self._hold(["SOURCE_FIXTURE_TRANSPORT_REQUIRED_NO_LIVE_CLIENT"])
        try:
            return self.convert(self._transport.fetch(capture_id))
        except (TypeError, ValueError, KeyError, RecursionError):
            return self._hold(["SOURCE_FIXTURE_TRANSPORT_FAILURE"])

    def convert(self, capture):
        if self._mapping_errors:
            return self._hold(self._mapping_errors)
        if canonical_hash(self._mapping) != self._mapping_sha256:
            return self._hold(["SOURCE_FROZEN_MAPPING_CHANGED"])
        if not isinstance(capture, dict) or set(capture) != _CAPTURE_FIELDS:
            return self._hold(["SOURCE_CAPTURE_SCHEMA_INVALID"])
        mapping = self._mapping
        profile = _PROFILE[mapping["data_classification"]]
        if (capture["data_classification"] != mapping["data_classification"]
                or type(capture["synthetic"]) is not bool or capture["synthetic"] is not mapping["synthetic"]):
            return self._hold(["SOURCE_CAPTURE_CLASSIFICATION_MISMATCH"])
        if capture["format_id"] != mapping["format_id"] or capture["source_id"] != mapping["source_id"]:
            return self._hold(["SOURCE_CAPTURE_FORMAT_OR_SOURCE_MISMATCH"])
        payload = capture["payload_bytes"]
        if not isinstance(payload, bytes) or not 0 < len(payload) <= 4 * 1024 * 1024:
            return self._hold(["SOURCE_CAPTURE_BYTES_REQUIRED_OR_TOO_LARGE"])
        if not _digest(capture["payload_sha256"]) or sha256(payload).hexdigest() != capture["payload_sha256"]:
            return self._hold(["SOURCE_CAPTURE_HASH_MISMATCH"])
        try:
            document = json.loads(payload.decode("utf-8", "strict"),
                                  object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            raw = {field: _resolve(document, pointer) for field, pointer in mapping["raw_fields"].items()}
            course = {field: _resolve(document, pointer) for field, pointer in mapping["course_fields"].items()}
        except (UnicodeError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            return self._hold(["SOURCE_CAPTURE_JSON_OR_FIELDS_INVALID"])
        if (raw.get("data_classification") != profile["raw_class"]
                or course.get("data_classification") != mapping["data_classification"]
                or type(course.get("synthetic")) is not bool or course["synthetic"] is not mapping["synthetic"]):
            return self._hold(["SOURCE_PAYLOAD_CLASSIFICATION_MISMATCH_NO_RELABEL"])
        prediction = _stamp(raw.get("prediction_at"))
        if prediction is None:
            return self._hold(["SOURCE_PREDICTION_TIME_INVALID"])
        reasons = _times(capture, prediction, "SOURCE_CAPTURE")
        history = capture["history"]
        if not isinstance(history, list) or not 1 <= len(history) <= 256:
            reasons.append("SOURCE_CAPTURE_HISTORY_REQUIRED")
        else:
            previous = None
            for entry in history:
                if (not isinstance(entry, dict) or set(entry) != {"payload_sha256", "evidence_sha256", *_TIMES}
                        or not _digest(entry.get("payload_sha256")) or not _digest(entry.get("evidence_sha256"))):
                    reasons.append("SOURCE_CAPTURE_HISTORY_INVALID")
                    continue
                reasons.extend(_times(entry, prediction, "SOURCE_HISTORY"))
                stamp = _stamp(entry["revision_at"])
                if previous and stamp and stamp < previous:
                    reasons.append("SOURCE_CAPTURE_HISTORY_NOT_ORDERED")
                if stamp:
                    previous = stamp
            last = history[-1]
            if (not isinstance(last, dict) or last.get("payload_sha256") != capture["payload_sha256"]
                    or any(last.get(field) != capture[field] for field in _TIMES)):
                reasons.append("SOURCE_CAPTURE_HISTORY_CURRENT_VERSION_MISMATCH")
        if reasons:
            return self._hold(reasons)
        try:
            report = validate_raw_race(raw, mapping["feature_specs"])
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            return self._hold(["SOURCE_RAW_SCHEMA_INVALID"])
        if not report["eligible"]:
            return self._hold(["SOURCE_RAW_GATE_HOLD", *report["errors"]])
        market_warnings = [code for code in report["warnings"]
                           if code.startswith("ODDS_") or code.startswith("RAW_ODDS_")]
        if market_warnings:
            return self._hold(["SOURCE_COMPLETE_MARKET_REQUIRED", *market_warnings])
        # Schema-only zero probe: never returned, fitted, or used as prediction.
        # RAW validation uses this same shape probe. Real normalization is separate.
        values = {boat["boat"]: {name: 0.0 for name in FEATURES} for boat in raw["boats"]}
        try:
            probe = _raw_schema_probe(raw, values)
            probe.update(deepcopy(course))
            policy = COURSE_POLICIES.get(course.get("course_policy_id"))
            gate = validate_course(probe, policy)
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            return self._hold(["SOURCE_COURSE_SCHEMA_INVALID"])
        if not gate["eligible"]:
            return self._hold(["SOURCE_COURSE_GATE_HOLD", *gate["errors"]])
        inputs = course["course_inputs"]
        if any(observation is not None and observation["source_id"] != mapping["course_source_ids"][key]
               for key, observation in inputs.items()):
            return self._hold(["SOURCE_COURSE_MAPPING_SOURCE_MISMATCH"])
        components = [raw["race_provenance"], raw["deadline"], raw["active_boats_provenance"], raw["odds_snapshot"]]
        for boat in raw["boats"]:
            components += [boat[key] for key in ("course", "fl", "scratched", "motor_identity")]
            components += [boat["features"][name] for name in FEATURES]
        components += [observation for observation in inputs.values() if observation is not None]
        materialization_errors = []
        for field in _TIMES:
            latest = max(_stamp(component[field]) for component in components)
            if _stamp(capture[field]) < latest:
                materialization_errors.append("SOURCE_CAPTURE_MATERIALIZATION_PRECEDES_COMPONENT_" + field.upper())
        if materialization_errors:
            return self._hold(materialization_errors)
        return {"status": "READY", "raw": deepcopy(raw), "course": deepcopy(course), "reasons": [],
                "source_evidence": {
                    "mapping_sha256": self._mapping_sha256, "payload_sha256": capture["payload_sha256"],
                    "payload_bytes": len(payload), "source_id": mapping["source_id"],
                    "format_id": mapping["format_id"], "data_classification": mapping["data_classification"],
                    "synthetic": mapping["synthetic"], **{field: capture[field] for field in _TIMES},
                    "history": deepcopy(history), "course_observations": deepcopy(gate["observations"]),
                    "active_boat_count": len(raw["active_boats"]), "odds_ticket_count": len(raw["odds_snapshot"]["odds"]),
                    "raw_warning_codes": report["warnings"], "external_authenticity": "UNVERIFIED",
                    "actual_official_mapping": "OPEN", "mapping_review": "SELF_REPORTED_HASHES_ONLY"},
                "production_go": False}


def make_synthetic_source_fixture(race):
    """Invent a complete captured JSON wrapper; never convert a real input here."""
    if (not isinstance(race, dict) or race.get("synthetic") is not True
            or race.get("data_classification") != "SYNTHETIC_ONLY"
            or not isinstance(race.get("target_date"), str) or not race["target_date"].startswith("2099-")):
        raise ValueError("SOURCE_SYNTHETIC_FIXTURE_ONLY")
    canonical = deepcopy(race)
    if "course_inputs" not in canonical:
        canonical = apply_course_fixture(canonical)
    raw = make_raw_fixture(canonical)
    course = {field: deepcopy(canonical[field]) for field in _COURSE_FIELDS}
    document = {"invented_raw": raw, "invented_course": course}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    digest = sha256(payload).hexdigest()
    specs = synthetic_feature_specs()
    mapping = {"schema_version": "SOURCE_MAPPING_V001", "version": "invented-local-capture-v001",
               "format_id": "LOCAL_CAPTURE_V001", "data_classification": "SYNTHETIC_ONLY", "synthetic": True,
               "source_id": "SYNTHETIC_LOCAL_CAPTURE_V001",
               "raw_fields": {field: "/invented_raw/" + field for field in sorted(_RAW_FIELDS)},
               "course_fields": {field: "/invented_course/" + field for field in sorted(_COURSE_FIELDS)},
               "feature_specs": specs,
               "feature_units": {name: specs["features"][name]["unit"] for name in FEATURES},
               "course_source_ids": {"frame": "SYNTHETIC_FRAME_V001", "exhibition": "SYNTHETIC_EXHIBITION_V001"}}
    times = {field: canonical["prediction_at"] for field in _TIMES}
    capture = {"format_id": mapping["format_id"], "data_classification": "SYNTHETIC_ONLY", "synthetic": True,
               "source_id": mapping["source_id"], "payload_bytes": payload, "payload_sha256": digest,
               **times, "history": [{**times, "payload_sha256": digest,
                                      "evidence_sha256": canonical_hash({"invented_capture_evidence": digest})}]}
    return {"mapping": mapping, "capture": capture}
