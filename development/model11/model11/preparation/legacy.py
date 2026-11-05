"""Local evaluation-only adapters for supplied frozen A/B predictions.

No production algorithm is reconstructed. Byte agreement is not authenticity.
All returned status/reason strings are fixed codes; received raw data stay local.
"""
from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import itertools
import json
import math
import re

from ..engine import canonical_hash


SOURCES = ("A", "B")
METHODS = ("normal5", "human_box", "mechanical_box")
SCHEMA = "FROZEN_OUTPUT_V1_PROPOSED"
MAX_RAW_BYTES = 2_000_000  # PROPOSED local resource limit, not a study threshold.
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_JST = timezone(timedelta(hours=9))


class _Invalid(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise _Invalid(reason)


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _stamp(value):
    _need(isinstance(value, str) and not value.endswith("-00:00"), "TIMESTAMP_FORMAT")
    # Match the existing candidate precision contract: never truncate precision.
    fraction = re.search(r"\.(\d+)", value)
    _need(not fraction or len(fraction.group(1)) <= 6, "TIMESTAMP_PRECISION")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise _Invalid("TIMESTAMP_FORMAT") from None
    _need(parsed.tzinfo is not None and parsed.utcoffset() is not None, "TIMESTAMP_OFFSET_REQUIRED")
    return parsed


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "RAW_JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _bad_constant(_):
    raise _Invalid("RAW_JSON_NONFINITE")


def _received(frame, prefix):
    _need(isinstance(frame, dict), prefix + "_FRAME_MISSING")
    text = frame.get("raw_bytes_b64")
    size = frame.get("raw_byte_count")
    digest = frame.get("raw_sha256")
    _need(isinstance(text, str), prefix + "_RAW_BYTES_MISSING")
    _need(type(size) is int and 0 < size <= MAX_RAW_BYTES, prefix + "_BYTE_COUNT_INVALID")
    _need(isinstance(digest, str) and _HEX.fullmatch(digest), prefix + "_HASH_INVALID")
    _need(len(text) <= 4 * ((MAX_RAW_BYTES + 2) // 3), prefix + "_RAW_TOO_LARGE")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        raise _Invalid(prefix + "_BASE64_INVALID") from None
    _need(len(raw) == size, prefix + "_BYTE_COUNT_MISMATCH")
    _need(hashlib.sha256(raw).hexdigest() == digest, prefix + "_HASH_MISMATCH")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                            parse_constant=_bad_constant)
    except (ValueError, UnicodeError):
        raise _Invalid(prefix + "_RAW_JSON_INVALID") from None
    _need(isinstance(parsed, dict), prefix + "_RAW_NOT_OBJECT")
    # No received parsed sidecar is trusted independently from the hashed bytes.
    if "parsed_prediction" in frame:
        try:
            sidecar = json.dumps(frame["parsed_prediction"], sort_keys=True, allow_nan=False)
            bound = json.dumps(parsed, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            raise _Invalid(prefix + "_PARSED_CONTENT_MISMATCH") from None
        _need(sidecar == bound, prefix + "_PARSED_CONTENT_MISMATCH")
    return parsed


def _profile(source, profiles):
    _need(isinstance(profiles, dict) and source in profiles, "PROFILE_MISSING")
    frame = profiles[source]
    profile = _received(frame, "PROFILE")
    _need(set(profile) == {"schema", "source", "profile_id", "model_version", "box_version",
                           "classification", "reference_description"}, "PROFILE_FIELDS")
    _need(profile["schema"] == "FROZEN_SOURCE_PROFILE_V1_PROPOSED", "PROFILE_SCHEMA")
    _need(profile["source"] == source, "PROFILE_SOURCE_MISMATCH")
    _need(_identifier(profile["profile_id"]), "PROFILE_ID_INVALID")
    _need(profile["model_version"] == "1.0" and profile["box_version"] == "1", "PROFILE_FROZEN_VERSION")
    _need(profile["classification"] in ("SYNTHETIC_ONLY", "LOCAL_PRIVATE_EXTERNAL"), "PROFILE_CLASSIFICATION")
    _need(profile["reference_description"] in
          ("SYNTHETIC_NOT_FORMAL_LOGIC", "SUPPLIED_FROZEN_OUTPUT_REFERENCE"), "PROFILE_REFERENCE_KIND")
    if profile["classification"] == "SYNTHETIC_ONLY":
        _need(profile["reference_description"] == "SYNTHETIC_NOT_FORMAL_LOGIC", "PROFILE_SYNTHETIC_LABEL")
    _need(isinstance(frame.get("review_evidence_id"), str)
          and _identifier(frame["review_evidence_id"]), "PROFILE_REVIEW_EVIDENCE_MISSING")
    return profile, frame["raw_sha256"]


def _ticket(value):
    _need(isinstance(value, str) and re.fullmatch(r"[1-6]-[1-6]-[1-6]", value), "TICKET_FORMAT")
    triple = tuple(map(int, value.split("-")))
    _need(len(set(triple)) == 3, "TICKET_REPEATED_BOAT")
    return triple


def _method(method, kind):
    _need(isinstance(method, dict), "METHOD_MISSING")
    allowed = {"tickets", "bet_decision"} if kind == "normal5" else {"boats", "tickets", "bet_decision"}
    if kind == "human_box":
        allowed |= {"core", "insertion", "normal5_frequencies"}
    _need(not set(method) - allowed, "METHOD_UNKNOWN_FIELDS")
    tickets = method.get("tickets")
    expected_n = 5 if kind == "normal5" else 6
    _need(isinstance(tickets, list) and len(tickets) == expected_n, "METHOD_TICKET_COUNT")
    triples = [_ticket(ticket) for ticket in tickets]
    _need(len(set(tickets)) == expected_n, "METHOD_DUPLICATE_TICKET")
    if "bet_decision" in method:
        _need(method["bet_decision"] in ("BET", "SKIP"), "METHOD_DECISION")
    if kind != "normal5":
        boats = method.get("boats")
        _need(isinstance(boats, list) and len(boats) == 3
              and all(type(boat) is int and 1 <= boat <= 6 for boat in boats)
              and len(set(boats)) == 3, "BOX_BOATS")
        _need(set(triples) == set(itertools.permutations(boats)), "BOX_PERMUTATIONS")
    if kind == "human_box":
        core, insertion, frequencies = method.get("core"), method.get("insertion"), method.get("normal5_frequencies")
        _need(isinstance(core, list) and len(core) == 2 and all(type(b) is int for b in core)
              and len(set(core)) == 2 and type(insertion) is int
              and insertion not in core and set(core + [insertion]) == set(method["boats"]), "HUMAN_METADATA")
        _need(isinstance(frequencies, dict) and set(frequencies) == set("123456")
              and all(type(n) is int and 0 <= n <= 5 for n in frequencies.values()), "HUMAN_FREQUENCIES")
    return deepcopy(method)


def _frozen(envelope, profiles):
    _need(isinstance(envelope, dict), "ENVELOPE_MISSING")
    source = envelope.get("source")
    _need(source in SOURCES, "SOURCE_NOT_A_OR_B")
    profile, profile_hash = _profile(source, profiles)
    prediction = _received(envelope, "PREDICTION")
    _need(set(prediction) == {"schema", "classification", "source", "profile_id", "reference_sha256",
                              "model_version", "box_version", "race_id", "target_date", "deadline",
                              "generated_at", "methods"}, "PREDICTION_FIELDS")
    _need(prediction["schema"] == SCHEMA, "PREDICTION_SCHEMA")
    _need(prediction["source"] == source, "PREDICTION_SOURCE_MISMATCH")
    _need(prediction["classification"] == profile["classification"], "PREDICTION_CLASSIFICATION")
    for key in ("profile_id", "model_version", "box_version"):
        _need(prediction[key] == profile[key], "PREDICTION_PROFILE_BINDING")
    _need(prediction["reference_sha256"] == profile_hash, "PREDICTION_REFERENCE_BINDING")
    _need(_identifier(prediction["race_id"]), "RACE_ID_INVALID")
    try:
        target = date.fromisoformat(prediction["target_date"])
    except (ValueError, TypeError):
        raise _Invalid("TARGET_DATE_INVALID") from None
    generated, deadline = _stamp(prediction["generated_at"]), _stamp(prediction["deadline"])
    _need(generated < deadline, "PREDICTION_NOT_PREDEADLINE")
    _need(generated.astimezone(_JST).date() == target
          and deadline.astimezone(_JST).date() == target, "PREDICTION_JST_DATE_MISMATCH")
    methods = prediction["methods"]
    _need(isinstance(methods, dict) and methods and not set(methods) - set(METHODS), "PREDICTION_METHODS")
    parsed_methods = {kind: _method(value, kind) for kind, value in methods.items()}
    if "human_box" in methods:
        _need("normal5" in methods, "HUMAN_NORMAL5_FREQUENCY_INPUT_MISSING")
        counted = Counter(boat for ticket in methods["normal5"]["tickets"] for boat in _ticket(ticket))
        _need(methods["human_box"]["normal5_frequencies"] == {str(b): counted[b] for b in range(1, 7)},
              "HUMAN_FREQUENCY_MISMATCH")
    evidence = envelope.get("predeadline_evidence")
    _need(isinstance(evidence, dict), "PREDEADLINE_EVIDENCE_MISSING")
    for field in ("source", "race_id", "target_date", "deadline", "generated_at"):
        _need(evidence.get(field) == prediction[field], "PREDEADLINE_EVIDENCE_BINDING")
    _need(evidence.get("raw_sha256") == envelope["raw_sha256"], "PREDEADLINE_HASH_BINDING")
    _need(evidence.get("kind") == "HASH_RECEIPT" and _identifier(evidence.get("artifact_id")),
          "PREDEADLINE_RECEIPT_METADATA")
    recorded = _stamp(evidence.get("recorded_at"))
    _need(generated <= recorded < deadline, "PREDEADLINE_RECEIPT_TIME")
    if "received_at" in envelope:
        _need(_stamp(envelope["received_at"]) >= recorded, "RECEIVED_BEFORE_RECEIPT")
    return dict(prediction, methods=parsed_methods)


def validate_frozen_predictions(envelopes, profiles):
    """Return metadata-only byte/content checks. No raw/ticket/training export."""
    _need(isinstance(envelopes, list), "ENVELOPES_NOT_LIST")
    rows, accepted, failures = [], [], 0
    for index, envelope in enumerate(envelopes):
        try:
            prediction = _frozen(envelope, profiles)
            key = (prediction["source"], prediction["race_id"], prediction["target_date"])
            accepted.append((index, key))
            rows.append({"index": index, "source": prediction["source"], "status": "LOCAL_MATCHED",
                         "reason": "RAW_HASH_CONTENT_PROFILE_AND_TIME_METADATA_MATCHED",
                         "method_count": len(prediction["methods"]),
                         "raw_byte_count": envelope["raw_byte_count"], "raw_sha256": envelope["raw_sha256"]})
        except (_Invalid, TypeError, KeyError) as exc:
            reason = exc.args[0] if isinstance(exc, _Invalid) else "INPUT_TYPE_OR_FIELD_INVALID"
            status = "OPEN" if reason in ("PROFILE_MISSING", "METHOD_MISSING", "PREDEADLINE_EVIDENCE_MISSING") else "HOLD"
            source = envelope.get("source") if isinstance(envelope, dict) and envelope.get("source") in SOURCES else None
            rows.append({"index": index, "source": source, "status": status, "reason": reason})
            failures += 1
    duplicated = {key for key, count in Counter(key for _, key in accepted).items() if count > 1}
    for index, key in accepted:
        if key in duplicated:
            rows[index].update(status="HOLD", reason="DUPLICATE_SOURCE_RACE_DATE")
            failures += 1
    local_n = sum(row["status"] == "LOCAL_MATCHED" for row in rows)
    return {"status": "HOLD" if any(row["status"] == "HOLD" for row in rows) else
                      "OPEN" if failures or not rows else "LOCAL_MATCHED",
            "received_n": len(envelopes), "local_matched_n": local_n, "rows": rows,
            "external_authenticity": "UNVERIFIED", "frozen_logic_reproduction": "NOT_IMPLEMENTED",
            "purpose": "EVALUATION_ONLY_NOT_TRAINING_INPUT", "production_go": False}


def _research(record):
    _need(isinstance(record, dict), "RESEARCH_RECORD_TYPE")
    _need(_identifier(record.get("race_id")), "RESEARCH_RACE_ID")
    _need(record.get("source") == "MODEL11_RESEARCH", "RESEARCH_SOURCE")
    forecast = deepcopy(record)
    actual = forecast.pop("actual", None)
    forecast["first_course"] = None
    digest = forecast.pop("prediction_sha256", None)
    try:
        _need(isinstance(digest, str) and _HEX.fullmatch(digest)
              and canonical_hash(forecast) == digest, "RESEARCH_FORECAST_HASH_BINDING")
    except (ValueError, TypeError):
        raise _Invalid("RESEARCH_FORECAST_HASH_BINDING") from None
    _need(isinstance(actual, dict) and actual.get("final") is True, "OUTCOME_MISSING_OR_NOT_FINAL")
    for key in ("race_id", "target_date"):
        _need(record.get(key) == actual.get(key), "OUTCOME_RACE_DATE_BINDING")
    if "source" in actual:
        _need(actual["source"] == record["source"], "OUTCOME_SOURCE_BINDING")
    result = actual.get("result")
    _need(isinstance(result, list) and len(result) == 3
          and all(type(b) is int and 1 <= b <= 6 for b in result) and len(set(result)) == 3, "OUTCOME_RESULT")
    generated, deadline = _stamp(record.get("prediction_at")), _stamp(record.get("deadline"))
    _need(generated < deadline, "RESEARCH_NOT_PREDEADLINE")
    available = _stamp(actual.get("available_at"))
    _need(available >= deadline, "OUTCOME_AVAILABLE_BEFORE_DEADLINE")
    # Only an evidence adapter; the engine's data/provenance gates still matter.
    return actual, "-".join(map(str, result))


def _research_method(record, method):
    if method == "normal5":
        value = record.get("selection")
    else:
        name = "human_research" if method == "human_box" else "mechanical_research"
        boxes = record.get("boxes")
        _need(isinstance(boxes, dict), "RESEARCH_METHOD_MISSING")
        value = boxes.get(name)
    _need(isinstance(value, dict), "RESEARCH_METHOD_MISSING")
    projected = {"tickets": value.get("tickets")}
    if method != "normal5":
        projected["boats"] = value.get("boats")
    # Research Human-style candidate is not the external formal Human BOX;
    # compare the six frozen tickets, without inventing a formal selection rule.
    return _method(projected, "mechanical_box" if method == "human_box" else method)


def _settle(tickets, actual, result):
    hit = int(result in tickets)
    refund = actual.get("refund_tickets")
    known_refunds = isinstance(refund, list)
    if known_refunds:
        for ticket in refund:
            _ticket(ticket)
        _need(len(set(refund)) == len(refund), "OUTCOME_DUPLICATE_REFUNDS")
        _need(result not in refund, "OUTCOME_WINNER_REFUNDED")
    payout = actual.get("payout_per_100")
    payout_known = type(payout) in (int, float) and math.isfinite(payout) and payout >= 0
    _need(payout is None or payout_known, "OUTCOME_PAYOUT_INVALID")
    known = known_refunds and (payout_known or not hit)
    stake = 100 * len(tickets)
    returned = (float(payout) if hit else 0.0) + 100 * len(set(tickets).intersection(refund)) if known else None
    return {"hit": hit, "stake": stake, "return": returned, "net": returned - stake if known else None,
            "refund": 100 * len(set(tickets).intersection(refund)) if known else None}


def _ledger(rows):
    money = [row for row in rows if row["net"] is not None]
    stake = sum(row["stake"] for row in money) if money else None
    returned = math.fsum(row["return"] for row in money) if money else None
    return {"n": len(rows), "hit_n": sum(row["hit"] for row in rows),
            "hit_rate": sum(row["hit"] for row in rows) / len(rows) if rows else None,
            "money_n": len(money), "money_unknown_n": len(rows) - len(money),
            "stake_yen": stake, "return_yen": returned,
            "refund_yen": math.fsum(row["refund"] for row in money) if money else None,
            "net_yen": returned - stake if money else None,
            "return_rate": returned / stake if stake else None,
            "roi": (returned - stake) / stake if stake else None,
            "scope": "PAIRED_LOCAL_MATCHED_OBSERVATIONS_ONLY"}


def compare_frozen(research_records, envelopes, profiles):
    """Compare research versus A and versus B in strictly separate ledgers."""
    _need(isinstance(research_records, list), "RESEARCH_RECORDS_NOT_LIST")
    checked = validate_frozen_predictions(envelopes, profiles)
    frozen = {}
    for row in checked["rows"]:
        if row["status"] == "LOCAL_MATCHED":
            prediction = _frozen(envelopes[row["index"]], profiles)
            frozen[(prediction["source"], prediction["race_id"], prediction["target_date"])] = prediction
    scope_keys = [(r.get("race_id"), r.get("target_date")) if isinstance(r, dict)
                  and isinstance(r.get("race_id"), str) and isinstance(r.get("target_date"), str)
                  else (None, None) for r in research_records]
    duplicates = {key for key, n in Counter(scope_keys).items() if n > 1}
    comparisons = {}
    for source in SOURCES:
        method_rows = {method: {"research": [], "frozen": [], "issues": []} for method in METHODS}
        source_rows = []
        for index, record in enumerate(research_records):
            try:
                _need(scope_keys[index] not in duplicates, "RESEARCH_DUPLICATE_RACE_DATE")
                actual, result = _research(record)
                match = frozen.get((source, record["race_id"], record["target_date"]))
                _need(match is not None, "FROZEN_MATCH_MISSING_OR_INVALID")
                _need(_stamp(record["deadline"]) == _stamp(match["deadline"]), "DEADLINE_MISMATCH")
            except (_Invalid, KeyError, TypeError) as exc:
                reason = exc.args[0] if isinstance(exc, _Invalid) else "RESEARCH_TYPE_OR_FIELD_INVALID"
                status = "OPEN" if reason in ("FROZEN_MATCH_MISSING_OR_INVALID", "OUTCOME_MISSING_OR_NOT_FINAL") else "HOLD"
                source_rows.append({"research_index": index, "status": status, "reason": reason})
                for method in METHODS:
                    method_rows[method]["issues"].append({"research_index": index, "status": status, "reason": reason})
                continue
            source_rows.append({"research_index": index, "status": "LOCAL_MATCHED", "reason": "MATCHED_RACE_DATE_DEADLINE"})
            for method in METHODS:
                try:
                    _need(method in match["methods"], "FROZEN_METHOD_MISSING")
                    current = _research_method(record, method)
                    fixed = match["methods"][method]
                    current_settled = _settle(current["tickets"], actual, result)
                    fixed_settled = _settle(fixed["tickets"], actual, result)
                    method_rows[method]["research"].append(current_settled)
                    method_rows[method]["frozen"].append(fixed_settled)
                except (_Invalid, KeyError, TypeError) as exc:
                    reason = exc.args[0] if isinstance(exc, _Invalid) else "METHOD_TYPE_OR_FIELD_INVALID"
                    method_rows[method]["issues"].append({"research_index": index, "status": "OPEN" if reason.endswith("MISSING") else "HOLD", "reason": reason})
        methods = {}
        for name, rows in method_rows.items():
            current, fixed = _ledger(rows["research"]), _ledger(rows["frozen"])
            money_pairs = [(a, b) for a, b in zip(rows["research"], rows["frozen"])
                           if a["net"] is not None and b["net"] is not None]
            missing_money = len(money_pairs) != len(rows["research"])
            statuses = [issue["status"] for issue in rows["issues"]]
            methods[name] = {"status": "HOLD" if "HOLD" in statuses else "OPEN" if statuses or not rows["research"]
                            else "UNVERIFIED_MONEY" if missing_money else "LOCAL_MATCHED_COMPARISON",
                             "expected_race_n": len(research_records), "paired_n": len(rows["research"]),
                             "missing_or_invalid_n": len(research_records) - len(rows["research"]),
                             "research": current, "frozen": fixed,
                             "hit_rate_difference_research_minus_frozen": current["hit_rate"] - fixed["hit_rate"] if rows["research"] else None,
                             "net_difference_yen": math.fsum(a["net"] - b["net"] for a, b in money_pairs) if money_pairs else None,
                             "paired_money_n": len(money_pairs), "issues": rows["issues"],
                             "stake_per_race_yen": 500 if name == "normal5" else 600,
                             "superiority": "UNVERIFIED"}
        extra = sum((race, day) not in set(scope_keys) for s, race, day in frozen if s == source)
        source_errors = [row for row in checked["rows"] if row["source"] in (source, None) and row["status"] != "LOCAL_MATCHED"]
        statuses = [method["status"] for method in methods.values()]
        comparisons["research_vs_" + source] = {
            "status": "HOLD" if any(row["status"] == "HOLD" for row in source_errors) or extra or "HOLD" in statuses else
                      "OPEN" if source_errors or any(s == "OPEN" for s in statuses) else
                      "UNVERIFIED_MONEY" if "UNVERIFIED_MONEY" in statuses else "LOCAL_MATCHED_COMPARISON",
            "source": source, "methods": methods, "race_bindings": source_rows,
            "unmatched_frozen_n": extra, "invalid_or_missing_evidence_n": len(source_errors),
            "external_authenticity": "UNVERIFIED", "source_independence": "SEPARATE_INPUTS_AND_LEDGERS_NOT_INDEPENDENCE_PROOF",
            "superiority": "UNVERIFIED"}
    return {"status": "OFFLINE_FIXED_OUTPUT_COMPARISON_ONLY", "validation": checked,
            "comparisons": comparisons, "pooled_AB_result": "NOT_COMPUTED",
            "training_input_export": "NOT_PROVIDED", "legacy_logic_reproduction": "NOT_IMPLEMENTED",
            "performance_improvement": "UNVERIFIED", "production_go": False}


def _frame(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    return {"raw_bytes_b64": base64.b64encode(raw).decode("ascii"),
            "raw_byte_count": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()}


def make_synthetic_legacy_fixture(research_records=None, *, synthetic_only=False):
    """Invent deterministic dummy frozen outputs, never run/copy a legacy model.

    Existing records are allowed only with explicit flag and 2099 synthetic IDs.
    A and B dummy tickets are chosen independently of research predictions.
    """
    _need(synthetic_only is True, "SYNTHETIC_FLAG_REQUIRED")
    if research_records is None:
        research_records = []
        for number in range(1, 4):
            deadline = f"2099-01-17T13:{number:02}:00+09:00"
            forecast = {"race_id": f"20990117_GAMAGORI_{number}R", "target_date": "2099-01-17",
                        "classification": "LANE2_RESEARCH_ONLY", "source": "MODEL11_RESEARCH",
                        "prediction_at": f"2099-01-17T12:{number:02}:00+09:00", "deadline": deadline,
                        "first_course": None,
                        "selection": {"tickets": ["1-2-3", "1-2-4", "1-3-2", "1-3-4", "2-1-3"]},
                        "boxes": {name: {"boats": [1, 2, 3], "tickets": ["-".join(map(str, t)) for t in itertools.permutations([1, 2, 3])]}
                                  for name in ("human_research", "mechanical_research")}}
            forecast["prediction_sha256"] = canonical_hash(forecast)
            forecast["actual"] = {"race_id": forecast["race_id"], "target_date": forecast["target_date"],
                                  "result": [1, 2, 3], "payout_per_100": 1000,
                                  "refund_tickets": [], "final": True, "available_at": "2099-01-17T14:00:00+09:00"}
            research_records.append(forecast)
    records = deepcopy(research_records)
    for record in records:
        _need(isinstance(record, dict) and str(record.get("target_date", "")).startswith("2099-")
              and re.fullmatch(r"2099\d{4}_GAMAGORI_(?:[1-9]|1[0-2])R", str(record.get("race_id", ""))),
              "SYNTHETIC_2099_SCOPE_REQUIRED")
        _research(record)
    profiles, envelopes = {}, []
    patterns = {"A": (["1-2-3", "2-1-3", "3-1-2", "4-1-2", "5-1-2"], [1, 2, 3], [2, 3, 4]),
                "B": (["6-5-4", "5-6-4", "4-6-5", "3-6-5", "2-6-5"], [4, 5, 6], [1, 5, 6])}
    for source in SOURCES:
        profile = {"schema": "FROZEN_SOURCE_PROFILE_V1_PROPOSED", "source": source,
                   "profile_id": "SYNTHETIC-" + source, "model_version": "1.0", "box_version": "1",
                   "classification": "SYNTHETIC_ONLY", "reference_description": "SYNTHETIC_NOT_FORMAL_LOGIC"}
        profiles[source] = dict(_frame(profile), review_evidence_id="SYNTHETIC-UNAUTHENTICATED-REVIEW")
        normal, human, mechanical = patterns[source]
        frequencies = Counter(boat for ticket in normal for boat in _ticket(ticket))
        for record in records:
            generated = _stamp(record["prediction_at"])
            prediction = {"schema": SCHEMA, "classification": "SYNTHETIC_ONLY", "source": source,
                          "profile_id": profile["profile_id"], "reference_sha256": profiles[source]["raw_sha256"],
                          "model_version": "1.0", "box_version": "1", "race_id": record["race_id"],
                          "target_date": record["target_date"], "deadline": record["deadline"],
                          "generated_at": generated.isoformat(),
                          "methods": {"normal5": {"tickets": list(normal)},
                                      "human_box": {"boats": list(human), "core": human[:2], "insertion": human[2],
                                                    "normal5_frequencies": {str(b): frequencies[b] for b in range(1, 7)},
                                                    "tickets": ["-".join(map(str, t)) for t in itertools.permutations(human)]},
                                      "mechanical_box": {"boats": list(mechanical),
                                                         "tickets": ["-".join(map(str, t)) for t in itertools.permutations(mechanical)]}}}
            frame = _frame(prediction)
            frame.update(source=source, classification="SYNTHETIC_ONLY", received_at=generated.isoformat(),
                         predeadline_evidence={key: prediction[key] for key in
                                               ("source", "race_id", "target_date", "deadline", "generated_at")})
            frame["predeadline_evidence"].update(raw_sha256=frame["raw_sha256"], kind="HASH_RECEIPT",
                                                 artifact_id="SYNTHETIC-SELF-REPORTED-RECEIPT", recorded_at=generated.isoformat())
            envelopes.append(frame)
    return {"classification": "SYNTHETIC_ONLY", "warning": "DUMMY_OUTPUTS_NOT_MODEL10_OR_BOXV1_REPRODUCTION",
            "research_records": records, "profiles": profiles, "envelopes": envelopes}
