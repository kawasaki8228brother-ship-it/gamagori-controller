import argparse, hashlib, json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);a=p.parse_args()
r=a.repo.resolve();d=Path(__file__).resolve().parent;manifest=json.loads((d/'MANIFEST.json').read_bytes());bad=[]
for x in manifest['files']:
 f=r/x['path'];b=f.read_bytes() if f.is_file() else b''
 if not f.is_file() or len(b)!=x['bytes'] or hashlib.sha256(b).hexdigest()!=x['sha256']:bad.append(x['path'])
for line in (d/'SHA256SUMS.txt').read_text().splitlines():
 s,n=line.split('  ',1)
 if hashlib.sha256((r/n).read_bytes()).hexdigest()!=s:bad.append(n)
actual={str(f.relative_to(r)) for f in r.rglob('*') if f.is_file() and '.git' not in f.parts and '__pycache__' not in f.parts}
expected={x['path'] for x in manifest['files']}|{str((d/n).relative_to(r)) for n in ['MANIFEST.json','SHA256SUMS.txt']}
if actual!=expected:bad.append('UNLISTED_OR_MISSING_FILES')
print(json.dumps({'status':'PASS' if not bad else 'FAIL','files':len(manifest['files']),'bad':bad,'scope':'byte_integrity_not_authenticity','production_go':False},sort_keys=True))
raise SystemExit(bool(bad))
