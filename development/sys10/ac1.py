"""SYS-10: offline AC1 initial-LOCK measurement, no production integrations."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

JST = timezone(timedelta(hours=9))
SOURCES = ("A", "B")
BASELINE_START, BASELINE_END = date(2026, 11, 9), date(2026, 11, 14)
INTERVENTION_ACTIONS = {"REPLAY", "TRANSPORT", "SUPPLEMENT", "MANUAL_WRITE", "OTHER"}


def jst_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed_shape = re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(Z|([+-])(\d{2}):(\d{2}))", value)
    if parsed_shape is None or value.endswith("-00:00"):
        return None
    if parsed_shape.group(1) != 'Z' and (int(parsed_shape.group(3)) > 23 or int(parsed_shape.group(4)) > 59):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(JST)


def _verified_ref(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("status") == "VERIFIED" and isinstance(obj.get("evidence_ref"), str) and bool(obj["evidence_ref"].strip())


def _pair(row: dict[str, Any]) -> tuple[Any, Any]:
    if any(not isinstance(x, str) or not x for x in (row.get("race_id"), row.get("source"))):
        raise ValueError("EVIDENCE_SCOPE_STRING_REQUIRED")
    return row.get("race_id"), row.get("source")


def _coverage(proof: Any, race_ids: set[str]) -> bool:
    return (_verified_ref(proof) and proof.get("complete") is True
            and isinstance(proof.get("race_ids"), list) and all(isinstance(x, str) for x in proof["race_ids"])
            and len(proof["race_ids"]) == len(set(proof["race_ids"])) and set(proof["race_ids"]) == race_ids
            and proof.get("sources") == ["A", "B"])


def _formal_gate(data: dict[str, Any], races: list[dict[str, Any]]) -> list[str]:
    """Validate stage evidence only; never discover/adopt deployments or rules."""
    reasons = []
    cohort = data.get("formal_cohort", {})
    if not isinstance(cohort, dict) or not isinstance(cohort.get("adoptions", {}), dict):
        return ["FORMAL_COHORT_SHAPE_INVALID"]
    adopted = []
    adoption_refs = {}
    for task in ("SYS-01", "SYS-02"):
        proof = cohort.get("adoptions", {}).get(task, {})
        observed = jst_time(proof.get("adopted_at")) if isinstance(proof, dict) else None
        if not _verified_ref(proof) or observed is None:
            reasons.append("ADOPTION_EVIDENCE_MISSING_" + task)
        else:
            adopted.append(observed)
            adoption_refs[task] = proof['evidence_ref']
    meet_ids = cohort.get("first_two_meet_ids")
    if not isinstance(meet_ids, list) or len(meet_ids) != 2 or not all(isinstance(x, str) and x for x in meet_ids) or len(set(meet_ids)) != 2:
        reasons.append("FIRST_TWO_MEETS_UNVERIFIED")
    else:
        if {r.get("meet_id") for r in races} != set(meet_ids):
            reasons.append("FORMAL_COHORT_SCOPE_MISMATCH")
    def bound(proof: Any) -> bool:
        return (_verified_ref(proof) and len(adoption_refs) == 2
                and proof.get('cohort_meet_ids') == meet_ids
                and proof.get('adoption_evidence_refs') == adoption_refs)
    if not bound(cohort.get("first_two_after_adoption_attestation")):
        reasons.append("FIRST_TWO_AFTER_ADOPTION_UNVERIFIED")
    if not bound(cohort.get("both_meets_complete")):
        reasons.append("BOTH_MEETS_NOT_CONFIRMED_COMPLETE")
    criterion = cohort.get("threshold_rule", {})
    if not _verified_ref(criterion) or criterion.get("scope") not in ("EACH_SOURCE", "COMBINED"):
        reasons.append("THRESHOLD_SCOPE_RULE_UNVERIFIED")
    if len(adopted) == 2:
        for race in races:
            # Day granularity cannot establish a same-day order; require later day.
            if date.fromisoformat(race["target_date"]) <= max(adopted).date():
                reasons.append("COHORT_NOT_STRICTLY_AFTER_ADOPTION")
                break
    return reasons


def measure(data: dict[str, Any], *, include_details: bool = False) -> dict[str, Any]:
    """Measure supplied evidence. VALID/deadline verdicts are upstream inputs."""
    if not isinstance(data, dict):
        raise ValueError("OBJECT_INPUT_REQUIRED")
    schedule = data.get("official_schedule", {})
    if not isinstance(schedule, dict):
        raise ValueError("OFFICIAL_SCHEDULE_OBJECT_REQUIRED")
    races = schedule.get("races", [])
    if not isinstance(races, list) or not all(isinstance(r, dict) for r in races):
        raise ValueError("RACE_LIST_REQUIRED")
    reasons = []
    if not _verified_ref(schedule) or schedule.get("complete") is not True:
        reasons.append("OFFICIAL_SCHEDULE_NOT_VERIFIED_COMPLETE")
    race_ids = set()
    valid_races = []
    for race in races:
        rid = race.get("race_id")
        try:
            day = date.fromisoformat(race.get("target_date", ""))
        except (ValueError, TypeError):
            reasons.append("SCHEDULE_DATE_UNVERIFIED")
            continue
        if not isinstance(rid, str) or not rid or rid in race_ids or not isinstance(race.get("meet_id"), str) or not race["meet_id"]:
            reasons.append("SCHEDULE_IDENTITY_DUPLICATE_OR_MISSING")
            continue
        race_ids.add(rid)
        valid_races.append(dict(race, target_date=day.isoformat()))
    denominator_known = not reasons
    universe = {(r["race_id"], s) for r in valid_races for s in SOURCES}
    collections = {}
    for name in ("lock_records", "interventions", "pair_attestations"):
        values = data.get(name, [])
        if not isinstance(values, list) or not all(isinstance(x, dict) for x in values):
            raise ValueError("EVIDENCE_LIST_REQUIRED")
        groups = defaultdict(list)
        for item in values:
            groups[_pair(item)].append(item)
        collections[name] = groups
    event_coverage = data.get("lock_record_coverage", {})
    events_complete = _coverage(event_coverage, race_ids)
    interventions_complete = _coverage(data.get("intervention_coverage", {}), race_ids)
    if not events_complete:
        reasons.append("LOCK_RECORD_SCOPE_COMPLETENESS_UNVERIFIED")
    if not interventions_complete:
        reasons.append("INTERVENTION_RECORD_SCOPE_COMPLETENESS_UNVERIFIED")
    details = []
    counts = {"AUTO_CONFIRMED": 0, "INTERVENED": 0, "NO_VALID_INITIAL_SAVE": 0, "UNVERIFIED": 0}
    valid_saved = 0
    conflicts = 0
    outside_scope = sum(len(v) for groups in collections.values() for k, v in groups.items() if k not in universe)
    for race in valid_races:
        for source in SOURCES:
            key = (race["race_id"], source)
            scoped_records = collections["lock_records"][key]
            unknown_role = any(x.get("kind") not in ("INITIAL_LOCK", "REVISION", "OTHER_NON_INITIAL") for x in scoped_records)
            records = [x for x in scoped_records if x.get("kind") == "INITIAL_LOCK"]
            interventions = collections["interventions"][key]
            attestations = collections["pair_attestations"][key]
            state, pair_reasons = "UNVERIFIED", []
            initial_valid = False
            if events_complete and len(records) == 1 and not unknown_role:
                record = records[0]
                evidence = record.get("existing_validity", {})
                initial_valid = _verified_ref(evidence) and evidence.get("verdict") == "VALID" and evidence.get("predeadline") is True and record.get("saved") is True
            if initial_valid:
                valid_saved += 1
            affected, uncertain_intervention = False, False
            for intervention in interventions:
                moment = jst_time(intervention.get("at"))
                complete_row = moment is not None and moment.date().isoformat() == race["target_date"] and intervention.get("action") in INTERVENTION_ACTIONS and isinstance(intervention.get("evidence_ref"), str) and bool(intervention["evidence_ref"].strip())
                effect = intervention.get("initial_lock_effect")
                if not complete_row or effect not in ("AFFECTS_INITIAL", "DOES_NOT_AFFECT_INITIAL"):
                    uncertain_intervention = True
                elif effect == "AFFECTS_INITIAL":
                    affected = True
            if affected:
                state = "INTERVENED"
                pair_reasons.append("INITIAL_LOCK_INTERVENTION_EVIDENCED")
                if any(_verified_ref(a) and a.get("conclusion") == "NO_INTERVENTION" for a in attestations):
                    conflicts += 1
                    pair_reasons.append("NO_INTERVENTION_ATTESTATION_CONFLICT")
            elif unknown_role:
                pair_reasons.append("INITIAL_LOCK_ROLE_UNVERIFIED")
            elif not events_complete:
                pair_reasons.append("LOCK_RECORD_SCOPE_COMPLETENESS_UNVERIFIED")
            elif len(records) > 1:
                pair_reasons.append("MULTIPLE_INITIAL_LOCK_RECORDS")
            elif len(records) == 0:
                state = "NO_VALID_INITIAL_SAVE"
                pair_reasons.append("COMPLETE_SCOPE_NO_INITIAL_LOCK")
            elif initial_valid:
                no_intervention = len(attestations) == 1 and _verified_ref(attestations[0]) and attestations[0].get("coverage_complete") is True and attestations[0].get("conclusion") == "NO_INTERVENTION"
                if uncertain_intervention:
                    pair_reasons.append("INTERVENTION_TIME_OR_EFFECT_UNVERIFIED")
                elif no_intervention and interventions_complete:
                    state = "AUTO_CONFIRMED"
                else:
                    pair_reasons.append("NO_INTERVENTION_NOT_PROVEN_BY_EMPTY_LOG")
            else:
                ev = records[0].get("existing_validity", {})
                if _verified_ref(ev) and (ev.get("verdict") == "INVALID" or ev.get("predeadline") is False or records[0].get("saved") is False):
                    state = "NO_VALID_INITIAL_SAVE"
                    pair_reasons.append("UPSTREAM_INITIAL_SAVE_INVALID_OR_POSTDEADLINE")
                else:
                    pair_reasons.append("EXISTING_VALIDITY_OR_PREDEADLINE_UNVERIFIED")
            counts[state] += 1
            details.append({"race_id": race["race_id"], "source": source, "target_date": race["target_date"], "state": state, "valid_initial_saved": initial_valid, "reasons": pair_reasons})
    n = len(universe) if denominator_known else None
    lower = upper = exact = None
    descriptive = "UNVERIFIED"
    if n:
        lower = Decimal(counts["AUTO_CONFIRMED"]) / Decimal(n)
        upper = Decimal(counts["AUTO_CONFIRMED"] + counts["UNVERIFIED"]) / Decimal(n)
        exact = lower if counts["UNVERIFIED"] == 0 and interventions_complete else None
        if exact is not None:
            descriptive = "AT_OR_ABOVE_95_PERCENT" if exact >= Decimal("0.95") else "BELOW_95_PERCENT"
        else:
            descriptive = "INTERVAL_CROSSES_95_PERCENT" if lower < Decimal("0.95") <= upper else "LOWER_BOUND_AT_OR_ABOVE_95_PERCENT" if lower >= Decimal("0.95") else "UPPER_BOUND_BELOW_95_PERCENT"
    baseline_dates = any(BASELINE_START <= date.fromisoformat(r["target_date"]) <= BASELINE_END for r in valid_races)
    by_source = {}
    for source in SOURCES:
        source_rows = [row for row in details if row['source'] == source]
        source_counts = {state: sum(row['state'] == state for row in source_rows) for state in counts}
        sn = len(valid_races) if denominator_known else None
        sl = source_counts['AUTO_CONFIRMED'] / sn if sn else None
        su = (source_counts['AUTO_CONFIRMED'] + source_counts['UNVERIFIED']) / sn if sn else None
        se = sl if sn and source_counts['UNVERIFIED'] == 0 and interventions_complete else None
        by_source[source] = {'denominator': sn, 'counts': source_counts, 'auto_save_rate': {'lower_bound': sl, 'upper_bound': su, 'exact': se}}
    mode = data.get("phase", "UNVERIFIED")
    gate_reasons = []
    formal = "NOT_APPLICABLE_BASELINE"
    if baseline_dates:
        mode = "BASELINE_20261109_14"
    elif mode == "BASELINE":
        mode = "BASELINE"
    elif mode == "FORMAL_FIRST_TWO_MEETS":
        gate_reasons = _formal_gate(data, valid_races)
        if conflicts:
            gate_reasons.append("INTERVENTION_EVIDENCE_CONFLICT")
        if not denominator_known or not n or counts["UNVERIFIED"] or not events_complete or not interventions_complete:
            gate_reasons.append("MEASUREMENT_COMPLETENESS_UNVERIFIED_OR_EMPTY")
        if gate_reasons:
            formal = "UNVERIFIED"
        else:
            scope = data['formal_cohort']['threshold_rule']['scope']
            satisfies = all(x['counts']['AUTO_CONFIRMED'] * 100 >= 95 * x['denominator'] for x in by_source.values()) if scope == 'EACH_SOURCE' else counts["AUTO_CONFIRMED"] * 100 >= 95 * n
            formal = "PASS" if exact is not None and satisfies else "FAIL"
    else:
        formal = "UNVERIFIED"
        gate_reasons.append("PHASE_NOT_EXPLICIT")
    result = {"module": "SYS-10_OFFLINE_PROTOTYPE", "phase": mode, "official_races_observed": len(valid_races), "denominator": n, "denominator_definition": "OFFICIAL_SCHEDULED_RACES_X_A_B_INITIAL_LOCK_OPPORTUNITIES", "counts": counts, "valid_initial_saved_count": valid_saved,
              "auto_save_rate": {"lower_bound": None if lower is None else float(lower), "upper_bound": None if upper is None else float(upper), "exact": None if exact is None else float(exact)},
              "by_source": by_source,
              "comparison_95_percent": {"threshold": 0.95, "descriptive_only": descriptive, "formal_judgment": formal, "formal_gate_reasons": sorted(set(gate_reasons))},
              "measurement_status": "VERIFIED_INPUT_CONTRACT_ONLY" if denominator_known and n and counts["UNVERIFIED"] == 0 and events_complete and interventions_complete and not conflicts else "UNVERIFIED",
              "reasons": sorted(set(reasons)), "outside_scope_evidence_rows": outside_scope,
              "intervention_evidence_conflicts": conflicts,
              "LOCK_validity_rule": "NOT_IMPLEMENTED_UPSTREAM_EVIDENCE_ONLY", "external_evidence_authenticity": "NOT_PROVEN_BY_THIS_MODULE", "independent_review": "PENDING_AFTER_CERTIFI", "production_GO": False}
    if include_details:
        result["pair_details"] = details
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--details", action="store_true", help="Private local output only; never publish real pair records")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        result = measure(data, include_details=args.details)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        print(json.dumps({"status": "INPUT_UNAVAILABLE_OR_INVALID", "production_GO": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
