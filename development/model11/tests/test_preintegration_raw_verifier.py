"""Independent synthetic raw-score/cohort checks, no production or live readers."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preintegration_v008.raw_logloss import audit_saved_prediction, sha256, TICKETS
from preintegration_v008.cohort_guards import audit_cohorts, selection_projection_sha256

ROOT=Path(__file__).resolve().parents[1]
def raw(value): return (json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False)+"\n").encode("ascii")
def times(value="2099-01-07T12:54:00+09:00"):return {k:value for k in ("acquired_at","available_at","revision_at")}
def distribution(p=None):
    if p is None:return {key:1/120 for key in TICKETS}
    return {key:p if key=="1-2-3" else (1-p)/119 for key in TICKETS}
def prediction():
    info={"feature_times":{str(b):{f:times() for f in ("st","turn","motor","ability","exhibition")} for b in range(1,7)},
          "state_times":{str(b):{f:times() for f in ("course","fl","scratched")} for b in range(1,7)},"odds_times":times()}
    return {"schema":"INDEPENDENT_PROBABILITY_INPUT_V001_PROPOSED","data_classification":"SYNTHETIC_ONLY","synthetic":True,
        "source":"MODEL11_RESEARCH","race_id":"SYNTHETIC_R1","target_date":"2099-01-07",
        "prediction_at":"2099-01-07T12:55:00+09:00","generated_at":"2099-01-07T12:55:01+09:00","deadline":"2099-01-07T13:00:00+09:00",
        "information":info,"distributions":{k:distribution() for k in ("P_raw","P_model","P_market","P_shrunk")},"production_go":False}
def final_result(race="SYNTHETIC_R1"):
    return {"schema":"INDEPENDENT_RESULT_INPUT_V001_PROPOSED","race_id":race,"outcome":[1,2,3],"status":"FINAL",
        "published_at":"2099-01-07T13:10:00+09:00","available_at":"2099-01-07T13:10:01+09:00","revision_at":"2099-01-07T13:10:00+09:00"}
def bound(p,r):
    pb,rb=raw(p),raw(r)
    return {"schema":"SAVED_RAW_LOGLOSS_BINDING_V001_PROPOSED","forecast_sha256":sha256(pb),"result_sha256":sha256(rb),"race_id":p["race_id"],
        "lock_at":"2099-01-07T12:55:02+09:00","prediction_available_at":"2099-01-07T12:55:01+09:00","prediction_revision_at":"2099-01-07T12:55:01+09:00",
        "model_odds_snapshot_sha256":sha256(b"SYNTHETIC_SNAPSHOT"),"market_odds_snapshot_sha256":sha256(b"SYNTHETIC_SNAPSHOT"),
        "odds_acquired_at":p["information"].get("odds_times",times())["acquired_at"],"odds_available_at":p["information"].get("odds_times",times())["available_at"],
        "odds_revision_at":p["information"].get("odds_times",times())["revision_at"],"evaluation_purpose":"HASHED_RAW_EVALUATION_ONLY"}
def score(p=None,r=None,b=None,stage="P_shrunk"):
    p=prediction() if p is None else p;r=final_result(p["race_id"]) if r is None else r
    return audit_saved_prediction(raw(p),sha256(raw(p)),raw(r),sha256(raw(r)),bound(p,r) if b is None else b,stage=stage)
def row(role,day):
    d=f"2099-01-{day:02d}"
    return {"race_id":"SYNTHETIC_"+role,"target_date":d,"raw_sha256":sha256(role.encode()),
        "prediction_at":d+"T12:55:00+09:00","deadline":d+"T13:00:00+09:00","record_available_at":d+"T13:10:00+09:00"}
def cohort():
    return {"schema":"COHORT_AUDIT_ROSTER_V001_PROPOSED","data_classification":"SYNTHETIC_ONLY","synthetic":True,
        "partitions":{role:[row(role,day)] for role,day in (("training",1),("selection",3),("pilot",2),("holdout",5))}}
MODEL=b'{"schema":"SYNTHETIC_FROZEN_MODEL","parameters":[]}'
def seal(c):return {"schema":"SINGLE_CHAMPION_SEAL_V001_PROPOSED","model_raw_sha256":sha256(MODEL),
    "selection_projection_sha256":selection_projection_sha256(c["partitions"]["selection"]),"selected_at":"2099-01-04T12:00:00+09:00",
    "frozen_at":"2099-01-04T12:01:00+09:00","champion_count":1}
def audit(c=None,s=None,model=MODEL):
    c=cohort() if c is None else c;s=seal(c) if s is None else s
    return audit_cohorts(raw(c),sha256(raw(c)),raw(s),sha256(raw(s)),model,sha256(MODEL))

class RawLoglossTests(unittest.TestCase):
    def test_uniform_all_stages_exact_known_logloss_no_normalization(self):
        for stage in ("P_raw","P_model","P_market","P_shrunk"):
            with self.subTest(stage=stage):
                r=score(stage=stage);self.assertEqual(r["status"],"RECOMPUTED_AUDIT_ONLY");self.assertAlmostEqual(r["logloss"],math.log(120))
                self.assertFalse(r["normalization_applied"]);self.assertFalse(r["probability_floor_applied"]);self.assertFalse(r["production_go"])
    def test_stage_selection_is_distinct(self):
        p=prediction();p["distributions"]["P_market"]=distribution(.5);p["distributions"]["P_model"]=distribution(.25)
        self.assertAlmostEqual(score(p,stage="P_market")["logloss"],math.log(2));self.assertAlmostEqual(score(p,stage="P_model")["logloss"],math.log(4))
    def test_explicit_stage_and_expected_raw_hash_not_canonical_reencoding(self):
        p,r=prediction(),final_result();pb,rb=raw(p),raw(r);b=bound(p,r)
        wrong=audit_saved_prediction(pb+b" ",sha256(pb),rb,sha256(rb),b,stage="P_shrunk")
        self.assertEqual(wrong["reason_codes"],["RAW_SHA256_MISMATCH"])
        for stage in (None,"P_calibrated",[],True):self.assertEqual(score(stage=stage)["status"],"HOLD")
    def test_semantically_equal_raw_layout_has_distinct_hash_and_is_not_silently_canonicalized(self):
        p,r=prediction(),final_result();pb=json.dumps(p,indent=1).encode();rb=raw(r);b=bound(p,r);b["forecast_sha256"]=sha256(pb)
        result=audit_saved_prediction(pb,sha256(pb),rb,sha256(rb),b,stage="P_shrunk")
        self.assertEqual(result["status"],"RECOMPUTED_AUDIT_ONLY");self.assertNotEqual(sha256(pb),sha256(raw(p)))
    def test_duplicate_json_keys_and_nonfinite_tokens_rejected_without_echo(self):
        p,r=prediction(),final_result();rb=raw(r);b=bound(p,r)
        for pb in (b'{"secret":"DO_NOT_ECHO","secret":1}',b'{"x":NaN}',b'{"x":Infinity}',b'\xff'):
            b["forecast_sha256"]=sha256(pb);out=audit_saved_prediction(pb,sha256(pb),rb,sha256(rb),b,stage="P_shrunk")
            self.assertEqual(out["status"],"HOLD");self.assertNotIn("DO_NOT_ECHO",str(out));self.assertNotIn("secret",str(out))
    def test_all_probability_domains_values_sums_and_stage_presence(self):
        changes=[lambda v:v.pop("1-2-3"),lambda v:v.update({"1-1-2":v.pop("1-2-3")}),lambda v:v.update({"1-2-3":-1}),
                 lambda v:v.update({"1-2-3":True}),lambda v:v.update({"1-2-3":2}),lambda v:v.update({"1-2-3":.8})]
        for index,change in enumerate(changes):
            with self.subTest(index=index):
                p=prediction();change(p["distributions"]["P_raw"]);self.assertEqual(score(p)["status"],"HOLD")
        p=prediction();p["distributions"].pop("P_market");self.assertEqual(score(p)["status"],"HOLD")
    def test_zero_probability_is_infinite_unverified_not_clipped(self):
        p=prediction();p["distributions"]["P_shrunk"]=distribution(0);out=score(p)
        self.assertEqual(out["status"],"UNVERIFIED_INFINITE_LOGLOSS");self.assertIsNone(out["logloss"]);self.assertEqual(out["nonfinite_logloss"],"POSITIVE_INFINITY")
        p["distributions"]["P_shrunk"]=distribution(1);self.assertEqual(score(p)["logloss"],0.0)
    def test_future_feature_state_and_training_times_rejected(self):
        for group,field in (("feature_times","motor"),("state_times","course")):
            p=prediction();p["information"][group]["1"][field]["revision_at"]="2099-01-07T12:56:00+09:00"
            self.assertEqual(score(p)["reason_codes"],["FUTURE_INFORMATION_IN_SAVED_FORECAST"])
        p=prediction();p["information"]["normalizer"]={"training_max_available_at":"2099-01-08T00:00:00+09:00"}
        self.assertEqual(score(p)["status"],"HOLD")
    def test_all_required_time_evidence_missing_or_invalid_and_deadline(self):
        for group in ("feature_times","state_times","odds_times"):
            p=prediction();p["information"].pop(group)
            self.assertEqual(score(p)["status"],"HOLD")
        for value in ("2099-01-07T12:55:00","2099-01-07T12:55:00-00:00","2099-01-07T25:00:00+09:00"):
            p=prediction();p["prediction_at"]=value;self.assertEqual(score(p)["status"],"HOLD")
        p,r=prediction(),final_result();b=bound(p,r);b["lock_at"]=p["deadline"];self.assertEqual(score(p,r,b)["status"],"HOLD")
    def test_outcomes_in_forecast_and_nonfinal_result_or_future_result(self):
        for key in ("outcome","result","payout"):
            p=prediction();p["information"][key]="DO_NOT_ECHO";o=score(p);self.assertEqual(o["status"],"HOLD");self.assertNotIn("DO_NOT_ECHO",str(o))
        for changes in ({"status":"CANCELLED"},{"outcome":[1,1,2]},{"outcome":[True,2,3]},{"published_at":"2099-01-07T12:59:00+09:00"},{"race_id":"OTHER"}):
            p,r=prediction(),final_result();r.update(changes);self.assertEqual(score(p,r)["status"],"HOLD")
    def test_snapshot_hash_time_binding_and_record_hash_binding(self):
        p,r=prediction(),final_result()
        for field,value in (("market_odds_snapshot_sha256",sha256(b"OTHER")),("odds_available_at","2099-01-07T12:54:01+09:00"),
                            ("forecast_sha256",sha256(b"OTHER")),("prediction_available_at","2099-01-07T12:55:03+09:00")):
            b=bound(p,r);b[field]=value;self.assertEqual(score(p,r,b)["status"],"HOLD")
    def test_private_real_and_unknown_schema_withheld_ab_evaluation_only(self):
        p=prediction();p["data_classification"]="PRIVATE_REAL";p["synthetic"]=False;self.assertEqual(score(p)["status"],"HOLD")
        p=prediction();p["schema"]="UNKNOWN_REAL_SCHEMA";self.assertEqual(score(p)["status"],"HOLD")
        for source in ("A","B"):
            p=prediction();p["source"]=source;out=score(p);self.assertEqual(out["AB_input_role"],"INDEPENDENT_RAW_EVALUATION_ONLY");self.assertFalse(out["production_go"])
    def test_existing_frozen_v005_synthetic_raw_record_is_supported(self):
        pb=(ROOT/"shadow_launch_v005/results/synthetic-demo-python314/example-forecast.raw.json").read_bytes();p=json.loads(pb);r=final_result(p["race_id"]);rb=raw(r)
        projected={**p["forecast"],"generated_at":p["generated_at"]};b=bound(projected,r);b["forecast_sha256"]=sha256(pb)
        out=audit_saved_prediction(pb,sha256(pb),rb,sha256(rb),b,stage="P_shrunk")
        self.assertEqual(out["status"],"RECOMPUTED_AUDIT_ONLY");self.assertAlmostEqual(out["logloss"],-math.log(p["forecast"]["distributions"]["P_shrunk"]["1-2-3"]))
    def test_v005_future_training_and_nested_outcomes_do_not_hide_outside_projection(self):
        original=json.loads((ROOT/"shadow_launch_v005/results/synthetic-demo-python314/example-forecast.raw.json").read_bytes())
        for attack in ("future", "outcome"):
            p=deepcopy(original)
            if attack=="future":p["forecast"]["model_spec"]["base_model"]["training_max_available_at"]="2099-01-08T00:00:00+09:00"
            else:p["forecast"]["config"]["result"]="DO_NOT_ECHO"
            r=final_result(p["race_id"]);pb,rb=raw(p),raw(r);projected={**p["forecast"],"generated_at":p["generated_at"]};b=bound(projected,r);b["forecast_sha256"]=sha256(pb)
            out=audit_saved_prediction(pb,sha256(pb),rb,sha256(rb),b,stage="P_shrunk")
            self.assertEqual(out["status"],"HOLD");self.assertNotIn("DO_NOT_ECHO",str(out))
    def test_function_inputs_are_unchanged_and_authentication_never_promoted(self):
        p,r=prediction(),final_result();b=bound(p,r);before=deepcopy((p,r,b))
        out=score(p,r,b)
        self.assertEqual((p,r,b),before);self.assertEqual(out["formal_eligibility"],"UNVERIFIED")
        self.assertIn("NOT_AUTHENTICATED",out["timing_claim"])
    def test_modules_have_no_model_engine_or_io_import_connections(self):
        import ast
        for name in ("raw_logloss.py","cohort_guards.py"):
            tree=ast.parse((ROOT/"preintegration_v008"/name).read_text())
            imports=[n.module or "" for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            self.assertFalse(any("model11" in name or any(part in name for part in ("engine","selection","storage","runner")) for name in imports))

class CohortGuardTests(unittest.TestCase):
    def test_valid_sealed_roles_are_audit_only_without_f5_values(self):
        out=audit();self.assertEqual(out["status"],"COHORT_INVARIANTS_MATCHED_AUDIT_ONLY");self.assertIsNone(out["minimum_selection_days"]);self.assertFalse(out["production_go"])
    def test_cross_role_race_raw_and_pilot_holdout_day_overlap(self):
        for key in ("race_id","raw_sha256"):
            c=cohort();c["partitions"]["holdout"][0][key]=c["partitions"]["pilot"][0][key];self.assertEqual(audit(c)["status"],"HOLD")
        c=cohort();c["partitions"]["holdout"][0]=dict(row("holdout",2));self.assertEqual(audit(c)["reason_codes"],["CROSS_ROLE_DAY_CLUSTER_CONTAMINATION"])
    def test_same_role_duplicate_raw_or_race_and_day_cluster_multiple_races(self):
        c=cohort();r=deepcopy(c["partitions"]["selection"][0]);c["partitions"]["selection"].append(r);self.assertEqual(audit(c)["status"],"HOLD")
        c=cohort();r=row("selection-second",3);c["partitions"]["selection"].append(r);self.assertEqual(audit(c)["status"],"COHORT_INVARIANTS_MATCHED_AUDIT_ONLY")
    def test_future_training_record_and_selection_holdout_order(self):
        c=cohort();c["partitions"]["training"][0]["record_available_at"]="2099-01-03T13:11:00+09:00";self.assertEqual(audit(c)["status"],"HOLD")
        c=cohort();c["partitions"]["selection"][0]=row("selection",6);self.assertEqual(audit(c)["status"],"HOLD")
    def test_champion_raw_selection_seal_and_time_are_bound(self):
        for field,value in (("champion_count",2),("champion_count",True),("selection_projection_sha256",sha256(b"OTHER")),
                            ("model_raw_sha256",sha256(b"OTHER")),("frozen_at","2099-01-05T12:55:00+09:00"),("selected_at","2099-01-03T12:00:00+09:00")):
            c=cohort();s=seal(c);s[field]=value;self.assertEqual(audit(c,s)["status"],"HOLD")
        self.assertEqual(audit(model=MODEL+b" ")["reason_codes"],["FROZEN_MODEL_RAW_SHA_MISMATCH"])
    def test_roster_and_seal_raw_hashes_not_normalized_and_malformed_records(self):
        c,s=cohort(),seal(cohort());cb,sb=raw(c),raw(s)
        out=audit_cohorts(cb+b" ",sha256(cb),sb,sha256(sb),MODEL,sha256(MODEL));self.assertEqual(out["reason_codes"],["RAW_SHA256_MISMATCH"])
        for mutate in (lambda c:c["partitions"].pop("pilot"),lambda c:c["partitions"].update(training=[]),lambda c:c.update(synthetic=False),
                       lambda c:c["partitions"]["pilot"][0].update(target_date="2099-02-30")):
            c=cohort();mutate(c);self.assertEqual(audit(c)["status"],"HOLD")

if __name__=="__main__":unittest.main()
