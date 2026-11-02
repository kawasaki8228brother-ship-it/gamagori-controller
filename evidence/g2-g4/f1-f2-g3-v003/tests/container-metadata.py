import sys,ssl,sqlite3,platform,json,hashlib
from importlib.metadata import distributions
assert sys.version_info[:3]==(3,14,3) and sqlite3.sqlite_version=='3.40.1'
c=sqlite3.connect(':memory:')
source=c.execute('select sqlite_source_id()').fetchone()[0]
options=[r[0] for r in c.execute('pragma compile_options')];c.close()
packages=sorted([{'name':d.metadata['Name'],'version':d.version} for d in distributions()],key=lambda x:x['name'].lower())
assert len(packages)==20 and len([p for p in packages if p['name'].lower()!='pip'])==19
print(json.dumps({'environment':{'python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,'os':platform.system(),'machine':platform.machine()},'sqlite_source_id':source,'sqlite_compile_options':options,'packages':packages,'network':'NONE_LOOPBACK_ONLY','image':'python@sha256:f21c0d5a44c56805654c15abccc1b2fd576c8d93aca0a3f74b4aba2dc92510e2','host_runtime_not_used':True,'production_openssl':'3.0.20_REPORTED_DIFFERENT_FROM_TEST_3.0.18','go':False},indent=2,sort_keys=True))
