import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import socket
import ssl
import sys

def blocked(*a,**k):raise AssertionError('NETWORK_DISABLED')
socket.socket.connect=socket.socket.connect_ex=socket.create_connection=socket.getaddrinfo=blocked
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--stage',choices=['before','after'],required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[2];directory=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
source=directory/'references/html_research_rev1.py.txt' if a.stage=='before' else directory/'html_research.py'
expected='7863bea4c520cba48bedb719c7f9c635c98dc9b664a73d5be82cc1f6e4ef45c0' if a.stage=='before' else 'dc84153b86811cad8666ee734615c96690b298f112ca99f7f2cbc11f120bec88'
raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected,'ORPHAN_SOURCE_SNAPSHOT_MISMATCH'
from types import ModuleType
m=ModuleType('orphan_probe_module');exec(compile(raw,'PINNED_RESEARCH_SNAPSHOT','exec'),m.__dict__)
table='<table><tr><th>レース</th><th>投票締切</th></tr>'+''.join(f'<tr><td>{n}R</td><td>13:{n:02d} 投票</td></tr>' for n in range(1,13))+'</table>'
inputs={'normal':table,'outside_tr':table+'<tr><td>1R</td><td>18:59</td></tr>',
        'layout_own_conflict':'<table><tr><td>1R</td><td>18:59</td><td>'+table+'</td></tr></table>'}
rows=[]
for name,html in inputs.items():
 r=m.inspect_research_html(html,'20990107')
 rows.append({'case':name,'status':r['status'],'reason':r.get('reason'),'records':len(r.get('records') or []),'go':r['go']})
if a.stage=='before':assert all(r['status']=='RESEARCH_PARSED' for r in rows)
else:
 assert rows[0]['status']=='RESEARCH_PARSED'
 assert all(r['status']=='HOLD' and r['records']==0 for r in rows[1:])
print(json.dumps({'stage':a.stage,'python':sys.version,'platform':platform.platform(),'openssl':ssl.OPENSSL_VERSION,
    'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'classification':'SYNTHETIC_ONLY','cases':rows,'production_go':False},sort_keys=True))
