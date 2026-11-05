"""Sealed cohort leakage checks; no F5 thresholds, model fitting or data I/O."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from .raw_logloss import AuditHold, _need, aware_time, parse_raw, sha256

ROLES = frozenset({"training", "selection", "pilot", "holdout"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")

def selection_projection_sha256(rows):
    """Hash a named derived identity projection, not original roster raw bytes."""
    value = sorted([{k: r[k] for k in ("race_id","target_date","raw_sha256","prediction_at","deadline","record_available_at")} for r in rows], key=lambda r:r["race_id"])
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")).hexdigest()

def audit_cohorts(roster_raw, roster_sha256, seal_raw, seal_sha256, model_raw, model_raw_sha256):
    base = {"status":"HOLD", "reason_codes":[], "production_go":False, "formal_eligibility":"UNVERIFIED",
            "source_authenticity":"UNVERIFIED_SELF_REPORTED", "minimum_selection_days":None,
            "sample_adequacy":"UNVERIFIED_NO_F5_THRESHOLD_ADOPTED", "holdout_start_and_days":None,
            "champion_count_requirement":1, "data_use":"AUDIT_ONLY_NO_FIT_OR_EVALUATION_START"}
    try:
        roster=parse_raw(roster_raw,roster_sha256);seal=parse_raw(seal_raw,seal_sha256)
        _need(type(model_raw) is bytes and bool(model_raw) and isinstance(model_raw_sha256,str) and _SHA.fullmatch(model_raw_sha256) is not None and sha256(model_raw)==model_raw_sha256,"FROZEN_MODEL_RAW_SHA_MISMATCH")
        _need(isinstance(roster,dict) and set(roster)=={"schema","data_classification","synthetic","partitions"} and roster["schema"]=="COHORT_AUDIT_ROSTER_V001_PROPOSED","COHORT_SCHEMA_INVALID")
        _need(roster["data_classification"]=="SYNTHETIC_ONLY" and roster["synthetic"] is True,"PRIVATE_DATA_EXECUTION_NOT_APPROVED")
        groups=roster["partitions"]
        _need(isinstance(groups,dict) and set(groups)==ROLES,"FOUR_EXPLICIT_ROLES_REQUIRED")
        seen_races,seen_hashes,day_roles={}, {}, {}
        normalized={}
        expected={"race_id","target_date","raw_sha256","prediction_at","deadline","record_available_at"}
        for role,rows in groups.items():
            _need(isinstance(rows,list) and bool(rows),"COHORT_INPUTS_INCOMPLETE_NOT_SAMPLE_ADEQUACY_VERDICT")
            normalized[role]=[]
            for row in rows:
                _need(isinstance(row,dict) and set(row)==expected,"COHORT_ROW_FIELDS_INVALID")
                race,day,digest=row["race_id"],row["target_date"],row["raw_sha256"]
                _need(isinstance(race,str) and _ID.fullmatch(race) is not None and isinstance(digest,str) and _SHA.fullmatch(digest) is not None,"COHORT_ID_OR_RAW_SHA_INVALID")
                _need(isinstance(day,str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",day) is not None,"COHORT_DAY_INVALID")
                try: parsed_day=datetime.strptime(day,"%Y-%m-%d").date()
                except ValueError: raise AuditHold("COHORT_DAY_INVALID") from None
                predicted,deadline,available=(aware_time(row[k]) for k in ("prediction_at","deadline","record_available_at"))
                _need(predicted<deadline and deadline.astimezone(timezone(timedelta(hours=9))).date()==parsed_day,"COHORT_TIMING_OR_TARGET_DAY_INVALID")
                _need(available>=predicted,"RECORD_AVAILABLE_BEFORE_PREDICTION")
                _need(race not in seen_races,"DUPLICATE_OR_CROSS_ROLE_RACE")
                _need(digest not in seen_hashes,"DUPLICATE_OR_CROSS_ROLE_RAW_BYTES")
                _need(day not in day_roles or day_roles[day]==role,"CROSS_ROLE_DAY_CLUSTER_CONTAMINATION")
                seen_races[race]=role;seen_hashes[digest]=role;day_roles[day]=role
                normalized[role].append({**row,"_prediction":predicted,"_available":available,"_day":parsed_day})
        _need(max(r["_day"] for r in normalized["training"])<min(r["_day"] for r in normalized["selection"]),"TRAIN_SELECTION_CHRONOLOGY_INVALID")
        _need(max(r["_day"] for r in normalized["selection"])<min(r["_day"] for r in normalized["holdout"]),"SELECTION_HOLDOUT_CHRONOLOGY_INVALID")
        _need(max(r["_day"] for r in normalized["pilot"])<min(r["_day"] for r in normalized["holdout"]),"PILOT_NOT_BEFORE_HOLDOUT")
        _need(max(r["_available"] for r in normalized["training"])<min(r["_prediction"] for r in normalized["selection"]),"FUTURE_TRAINING_INFORMATION_IN_SELECTION")
        expected_seal={"schema","model_raw_sha256","selection_projection_sha256","selected_at","frozen_at","champion_count"}
        _need(isinstance(seal,dict) and set(seal)==expected_seal and seal["schema"]=="SINGLE_CHAMPION_SEAL_V001_PROPOSED","CHAMPION_SEAL_SCHEMA_INVALID")
        _need(type(seal["champion_count"]) is int and seal["champion_count"]==1,"EXACTLY_ONE_FROZEN_CHAMPION_REQUIRED")
        _need(seal["model_raw_sha256"]==model_raw_sha256,"CHAMPION_MODEL_RAW_BINDING_MISMATCH")
        _need(seal["selection_projection_sha256"]==selection_projection_sha256(groups["selection"]),"SELECTION_ROSTER_SEAL_MISMATCH")
        selected,frozen=aware_time(seal["selected_at"]),aware_time(seal["frozen_at"])
        _need(max(r["_available"] for r in normalized["selection"])<=selected<=frozen<min(r["_prediction"] for r in normalized["holdout"]),"SELECTION_FREEZE_HOLDOUT_TIME_INVALID")
        _need(max(r["_available"] for r in normalized["pilot"])<=frozen,"PILOT_NOT_AVAILABLE_BEFORE_CONFIRMATORY_FREEZE")
        return {**base,"status":"COHORT_INVARIANTS_MATCHED_AUDIT_ONLY","role_rows":{r:len(v) for r,v in groups.items()},
                "role_days":{r:len({row["target_date"] for row in v}) for r,v in groups.items()},
                "roster_raw_sha256":roster_sha256,"seal_raw_sha256":seal_sha256,"model_raw_sha256":model_raw_sha256,
                "selection_projection_scope":"DERIVED_SORTED_IDENTITY_SET_NOT_RAW_SOURCE_HASH",
                "pilot_reused_as_holdout":False,"automatic_evaluation_or_promotion":False}
    except AuditHold as exc:return {**base,"reason_codes":[exc.args[0]]}
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):return {**base,"reason_codes":["COHORT_INPUT_INVALID"]}
