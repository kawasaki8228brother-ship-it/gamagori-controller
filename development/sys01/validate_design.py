"""Static graph/fixture consistency audit, NOT a state engine or writer."""
from pathlib import Path
import base64
import hashlib
import json
import platform
import sys

HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'state-machine.json').read_text())
fixtures=json.loads((HERE/'fixtures.json').read_text())['cases']
edges={e['id']:e for e in m['transitions']}
assert len(edges)==len(m['transitions'])
assert not m['runtime_implemented'] and not m['production_GO']
covered=set();sources=set();rows=[]
for c in fixtures:
 assert c['synthetic']
 state='START'
 for eid in c['path']:
  edge=edges[eid];assert edge['from']==state,(c['id'],eid)
  state=edge['to'];covered.add(eid)
 assert state==c['expected']['final_state']
 assert state in m['terminal_or_reportable_states']
 assert c['expected']['runtime_test']=='UNVERIFIED_NOT_IMPLEMENTED'
 assert c['expected']['LOCK_validity']=='NOT_EVALUATED'
 assert c['expected']['current_execution_permission']=='NONE_DESIGN_ONLY'
 f=c['frozen'];sources.add(f['source']);g=c['guards']
 invalid=set(c['intentional_invalid_fields'])
 if 'frozen_raw_missing' in invalid:
  assert f['raw_b64'] is None and state=='STOP_FROZEN'
 else:
  raw=base64.b64decode(f['raw_b64'],validate=True)
  actual=hashlib.sha256(raw).hexdigest()
  if 'frozen_hash_mismatch' in invalid:
   assert actual!=f['raw_sha256'] and state=='STOP_FROZEN'
  else:assert actual==f['raw_sha256']
 assert len(c['write_intents'])==c['path'].count('e08')+c['path'].count('e31')
 assert c['prior_attempts']+len(c['write_intents'])<=g['max_total_attempts']
 for intent in c['write_intents']:
  assert intent['raw_b64']==f['raw_b64'] and intent['key']==f['idempotency_key']
  assert intent['source']==f['source'] and intent['race']==f['race']
  assert intent['existing_deadline_check_at_intent']=='PASS'
  assert intent['atomic_sink_dedup_proven_at_intent'] is True
  assert intent['GO_receipt']=='SYNTHETIC_NOT_A_REAL_AUTHORIZATION'
 if 'e30' in c['path']:
  for k in ['read_scope_authorized','retry_specific_GO','original_bytes_available','original_bytes_and_hash_match','same_key_race_source','prior_write_settled','search_complete_authoritative','atomic_sink_dedup_proven','safety_block_resolved']:
   assert g[k] is True,(c['id'],k)
  assert g['existing_deadline_check']=='PASS'
  pos=c['path'].index('e30')
  used=c['prior_attempts']+sum(eid in ['e08','e31'] for eid in c['path'][:pos])
  assert used<g['max_total_attempts']
 if c['expected']['exact_retry']=='DESIGN_ELIGIBLE_NO_EXECUTION':assert state=='RETRY_DESIGN_ELIGIBLE'
 else:assert c['expected']['exact_retry']=='DENY'
 if 'e12' in c['path']:assert 'e30' not in c['path'] and 'e31' not in c['path']
 if not g['search_complete_authoritative']:assert 'e30' not in c['path'] and 'e31' not in c['path']
 if not g['read_scope_authorized']:assert c['path']==['e32']
 if c['expected']['save_confirmed_unique_exact'] is True:
  assert c['observations']['raw_readback']=='EXACT_ORIGINAL_BYTES_SHA'
  records=c['observations']['records'];assert len(records)==1
  r=records[0]
  assert r['raw_b64']==f['raw_b64'] and r['raw_sha256']==f['raw_sha256']
  assert r['source']==f['source'] and r['race']==f['race'] and r['key']==f['idempotency_key']
  assert c['expected']['persistence_unverified'] is False
 if 'e25' in c['path']:
  assert c['observations']['raw_readback']=='NOT_READ_SCOPE_REJECTED'
  assert c['observations']['other_source_payload_read'] is False
  assert c['observations']['records'][0]['raw_b64'] is None
 if 'e24' in c['path']:
  assert c['observations']['raw_readback']=='DIFFERENT_FROM_ORIGINAL_BYTES'
  assert c['observations']['records'][0]['raw_b64']!=f['raw_b64']
 if 'e01' in c['path'] or 'e32' in c['path']:
  assert c['observations']['raw_readback']=='NOT_REQUESTED'
  assert c['observations']['records'] is None and c['observations']['candidate_count'] is None
 rows.append({'id':c['id'],'structural_validation':'PASS','runtime_validation':'UNVERIFIED_NOT_IMPLEMENTED','final_state_declared':state})
assert covered==set(edges),(set(edges)-covered)
assert sources=={'A','B'}
report={'status':'PASS_STATIC_DESIGN_CONSISTENCY_ONLY','case_count':len(fixtures),'declared_transitions':len(edges),'covered_transition_ids':sorted(covered),'runtime_implemented':False,'writer_requests_executed':0,'A_B_live_originals':'NOT_RECEIVED','section_map':'OPEN','independent_review':'PENDING_AFTER_CERTIFI','production_GO':False,'cases':rows}
env={'python':sys.version.split()[0],'os':platform.platform(),'scope':'OFFLINE_STATIC_DESIGN_ONLY'}
print('ENV '+json.dumps(env,sort_keys=True))
print(json.dumps(report,indent=2))
