"""Only synthetic inputs; does not create real forecasts or research records."""
from pathlib import Path
from itertools import permutations
import json

HERE=Path(__file__).resolve().parent
domain=['-'.join(map(str,p)) for p in permutations([1,2,3],3)]
def row(index,day):
    race=day.replace('-','')+'_GAMAGORI_'+str(index)+'R'
    old={'race_id':race,'source':'A','target_date':day,'existing_predeadline_verdict':'VERIFIED','tickets':domain[1:6],'probabilities':{k:1/6 for k in domain},'money':{'stake_yen':500,'payout_yen':0,'refund_yen':100}}
    candidate={'race_id':race,'candidate_id':'SYNTHETIC_CANDIDATE','comparator_source':'A','target_date':day,'lane':'THIRD_RESEARCH','existing_predeadline_verdict':'VERIFIED','tickets':domain[:5],'probabilities':{k:1/6 for k in domain},'money':{'stake_yen':500,'payout_yen':1000,'refund_yen':100}}
    return {'synthetic':True,'race_id':race,'race_id_profile':'DATE_PREFIXED_GAMAGORI_V1','day':day,'comparator_source':'A','active_boats':[1,2,3],'result':domain[0],'old':old,'candidate':candidate,'market_odds':{k:6 for k in domain},'market_snapshot_verdict':'VERIFIED'}

fixtures={'classification':'SYNTHETIC_ONLY_NO_REAL_FORECASTS','pairs':[row(1,'2099-01-01'),row(2,'2099-01-02')],
 'cluster_plan':{'replicates':100,'seed':20261105,'confidence':0.95,'min_cluster_days':30,'preregistration_sha256':'a'*64,'exchangeable_days_assumption':True},
 'box':[{'entry_id':'SYNTHETIC_PRE_1','phase':'PRE','period':'SYNTHETIC_MEET','kind':'FLOW','stake_yen':500,'payout_yen':0,'refund_yen':0},
 {'entry_id':'SYNTHETIC_LIVE_1','phase':'LIVE','period':'SYNTHETIC_MEET','kind':'FLOW','stake_yen':500,'payout_yen':1000,'refund_yen':100},
 {'entry_id':'SYNTHETIC_FINAL_1','phase':'FINAL','period':'SYNTHETIC_MEET','kind':'FLOW','confirmed':True,'stake_yen':500,'payout_yen':1000,'refund_yen':100},
 {'entry_id':'SYNTHETIC_FINAL_TOTAL','phase':'FINAL','period':'SYNTHETIC_MEET','kind':'CUMULATIVE_SNAPSHOT','confirmed':True,'scope_complete':True,'stake_yen':500,'payout_yen':1000,'refund_yen':100}],
 'box_coverage':{phase+'|SYNTHETIC_MEET':{'complete':True,'evidence_reference':'SYNTHETIC_COVERAGE_NOT_REAL_ATTESTATION'} for phase in ['PRE','LIVE','FINAL']}}
(HERE/'fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n')
print('SYNTHETIC_FIXTURES_WRITTEN')
