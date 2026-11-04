"""Synthetic data only; never actual race records or forecasts."""
from copy import deepcopy
import json
from pathlib import Path

A=[[1,2,3],[1,3,2],[1,2,4],[1,4,2],[1,3,4]]
B=[[2,1,3],[2,3,1],[2,1,4],[2,4,1],[2,3,4]]

def make_fixture():
    d={'schema':'B3_INPUT_V1_PROPOSED','classification':'SYNTHETIC_ONLY_NOT_REAL_RACES','meets':[],'races':[],'locks':[],'results':[],'summaries':[]}
    d['read_coverage']={'schedule':'VERIFIED_COMPLETE','locks':{'A':'VERIFIED_COMPLETE','B':'VERIFIED_COMPLETE'},'results':'VERIFIED_COMPLETE','summaries':{'A':'VERIFIED_COMPLETE','B':'VERIFIED_COMPLETE'}}
    for i,(day,order,payout) in enumerate([('2026-07-11',[1,2,3],1200),('2026-08-11',[2,1,3],800),('2026-09-11',[3,1,2],1600),('2026-10-11',[1,4,2],4000)],1):
        mid=f'SYNTHETIC_MEET_{i}';rid=day.replace('-','')+'_GAMAGORI_1R';result_id=f'SYNTH_RESULT_{i}'
        d['meets'].append({'meet_id':mid,'start_date':day,'end_date':day})
        d['races'].append({'race_id':rid,'meet_id':mid,'date':day,'deadline':day+'T14:00:00+09:00','scheduled':True})
        d['results'].append({'record_id':result_id,'race_id':rid,'status':'FINAL','official_result_verified':True,'order':order,'payout_yen_per_100':payout,'refunded_combinations':[],'refund_evidence_verified':True})
        for source,tickets in [('A',A),('B',B)]:
            lid=f'SYNTH_LOCK_{source}_{i}';hit=order in tickets
            d['locks'].append({'record_id':lid,'race_id':rid,'source':source,'tickets':deepcopy(tickets),'observed_at':day+'T13:01:00+09:00','saved_at':day+'T13:01:01+09:00','existing_LOCK_validity':'VALID','existing_deadline_verdict':'PASS','payload_hash_verified':True,'saved_readback_verified':True})
            d['summaries'].append({'record_id':f'SYNTH_SUMMARY_{source}_{i}','race_id':rid,'source':source,'lock_record_id':lid,'result_record_id':result_id,'verification':'VERIFIED','hit':hit,'stake_yen':500,'payout_yen':payout if hit else 0,'refund_yen':0})
    return d

if __name__=='__main__':Path(__file__).with_name('synthetic_fixture.json').write_text(json.dumps(make_fixture(),indent=2)+'\n')
