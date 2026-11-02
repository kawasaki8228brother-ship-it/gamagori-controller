"""Isolated fixtures only. Usage: reviewed-python -B isolation.py WORK PROJECT."""
from pathlib import Path
import asyncio, ctypes, datetime as dt, hashlib, http.server, importlib.util, json, os, shlex, socket, sqlite3, ssl, struct, subprocess, sys, threading, time

E=Path(__file__).resolve().parents[1]
if len(sys.argv)!=3:raise SystemExit("WORK and PROJECT arguments required")
WORK=Path(sys.argv[1]).resolve();PROJECT=Path(sys.argv[2]).resolve();WORK.mkdir(parents=True,exist_ok=True)
core=(E/"source/common.py").read_text()
parts=[(E/('source/'+name+'.py')).read_text() for name in ('g2','g3','g4_env','g4_tls','g4_db')]
ns={"__name__":"isolated_library"};exec(core+'\n'+'\n'.join(parts),ns)
Stop=ns['Stop'];AT=dt.datetime(2026,11,2,9,tzinfo=dt.timezone(dt.timedelta(hours=9)))
results=[]
def check(name,fn):
    fn();results.append(name);print('CASE '+name+' PASS',flush=True)
def expect_stop(fn,why):
    try:fn()
    except Stop as exc:assert exc.why==why;return
    raise AssertionError('expected STOP '+why)
def fixture(name,wal=True,unique=True,events=1):
    root=WORK/name;root.mkdir();path=root/'gamagori_shadow.db';c=sqlite3.connect(path)
    if wal:c.execute('PRAGMA journal_mode=WAL')
    c.executescript('CREATE TABLE race_states(race_id TEXT PRIMARY KEY,data_json TEXT NOT NULL,updated_at TEXT NOT NULL);CREATE TABLE idempotency_keys(idempotency_key TEXT PRIMARY KEY,event_uuid TEXT NOT NULL);CREATE TABLE shadow_events(event_uuid TEXT PRIMARY KEY,idempotency_key TEXT '+('UNIQUE' if unique else '')+',race_id TEXT,event_type TEXT,payload_json TEXT,payload_hash TEXT,observed_at TEXT,deadline_version INTEGER,created_at TEXT);')
    for i,state in enumerate(('PENDING','DATA_WAIT','TERMINAL')):
        rid='20261102_GAM_'+str(i+1).zfill(2)+'R';p={'race_id':rid,'status':state,'c_events':[]}
        c.execute('INSERT INTO race_states VALUES(?,?,?)',(rid,json.dumps(p),'2026-11-02 00:00:00'))
    for i in range(events):
        key='k'+str(i);uid='u'+str(i);c.execute('INSERT INTO idempotency_keys VALUES(?,?)',(key,uid));c.execute('INSERT INTO shadow_events VALUES(?,?,?,?,?,?,?,?,?)',(uid,key,'20261102_GAM_01R','CLOSING_OBSERVATION','x'*800,'hash','2026-11-02T00:00:00+00:00',1,'2026-11-02 00:00:00'))
    c.commit()
    if not wal:c.close();c=None
    return root,c
def fingerprints(root):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
def output_frame(rows):return ns['frame']([ns['metadata']('ISOLATION')]+rows)

def g2_known():
    root,w=fixture('g2-known');before=fingerprints(root);rows=ns['g2'](root,PROJECT/'sqlite_readonly_audit.py',AT);after=fingerprints(root)
    assert rows[0]['pending']==1 and rows[0]['nonterminal']==2 and rows[0]['unknown']==0
    assert set(after)==set(before) and before['gamagori_shadow.db']==after['gamagori_shadow.db'] and before['gamagori_shadow.db-wal']==after['gamagori_shadow.db-wal']
    (WORK/'G2.actual.private.txt').write_bytes(output_frame(rows));w.close()
check('G2_PENDING_NONTERMINAL_RO',g2_known)
def g2_unknown():
    root,w=fixture('g2-unknown');w.execute('UPDATE race_states SET data_json=? WHERE race_id=?',(json.dumps({'status':'UNRECOGNIZED'}),'20261102_GAM_01R'));w.commit();rows=ns['g2'](root,PROJECT/'sqlite_readonly_audit.py',AT);assert rows[-1]['r']=='STOP_UNKNOWN' and rows[0]['unknown']==1;w.close()
check('G2_UNKNOWN_STATE_STOP',g2_unknown)
def g2_badjson():
    root,w=fixture('g2-json');w.execute("UPDATE race_states SET data_json='not-json' WHERE race_id='20261102_GAM_01R'");w.commit();assert ns['g2'](root,PROJECT/'sqlite_readonly_audit.py',AT)[0]['unknown']==1;w.close()
check('G2_INVALID_JSON_STOP',g2_badjson)
def g2_hash():
    root,w=fixture('g2-hash');bad=WORK/'untrusted-auditor.py';bad.write_text('raise RuntimeError("MUST_NOT_RUN")');before=fingerprints(root);expect_stop(lambda:ns['g2'](root,bad,AT),'AUDITOR_HASH');assert fingerprints(root)==before;w.close()
check('G2_HASH_MISMATCH_NO_DB_OPEN',g2_hash)
def g2_missing_shm():
    root,w=fixture('g2-shm');w.close();before=set(root.iterdir());expect_stop(lambda:ns['g2'](root,PROJECT/'sqlite_readonly_audit.py',AT),'WAL_SIDECAR_MISSING');assert set(root.iterdir())==before
check('G2_NO_SOURCE_SIDECAR_CREATION',g2_missing_shm)

def watched_backup():
    root,w=fixture('g3-wal',events=50);before=fingerprints(root)
    libc=ctypes.CDLL(None);fd=libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC);assert fd>=0;assert libc.inotify_add_watch(fd,str(root).encode(),0x100|0x200)>=0
    rows=ns['g3'](root,AT);raw=os.read(fd,65536);os.close(fd);assert rows[-1]['r']=='BACKUP_VERIFIED'
    after=fingerprints(root);new=set(after)-set(before);assert len(new)==1;name=next(iter(new));assert name==rows[1]['backup'];assert after[name]==rows[1]['sha256']
    assert before['gamagori_shadow.db']==after['gamagori_shadow.db'] and before['gamagori_shadow.db-wal']==after['gamagori_shadow.db-wal']
    changed_shm=before['gamagori_shadow.db-shm']!=after['gamagori_shadow.db-shm']
    events=[];pos=0
    while pos<len(raw):
        _,mask,_,n=struct.unpack_from('iIII',raw,pos);filename=raw[pos+16:pos+16+n].split(b'\0')[0].decode();pos+=16+n
        assert filename in {name,name+'-journal',name+'-wal',name+'-shm'}
        role='BACKUP'+filename[len(name):];events.append({'role':role,'create':bool(mask&0x100),'delete':bool(mask&0x200)})
    assert not any((root/(name+s)).exists() for s in ('-journal','-wal','-shm'))
    copy=sqlite3.connect((root/name).as_uri()+'?mode=ro&immutable=1',uri=True);assert copy.execute('pragma integrity_check').fetchall()==[('ok',)];assert copy.execute('select count(*) from shadow_events').fetchone()[0]==50;copy.close()
    observation={'source_db_unchanged':True,'source_wal_unchanged':True,'existing_shm_changed':changed_shm,'shm_normal_readmarks_allowed_by_HQ13':True,'extra_final_files':1,'copy_integrity':'ok','sqlite_native_aux_events':events,'sqlite':sqlite3.sqlite_version}
    (WORK/'G3.native-observation.raw.json').write_text(json.dumps(observation,indent=2,sort_keys=True)+'\n');(WORK/'G3.actual.private.txt').write_bytes(output_frame(rows));w.close()
check('G3_WAL_CONSISTENT_BACKUP_AUX_AND_SHM_BOUNDARY',watched_backup)
def g3_rollback():
    root,w=fixture('g3-delete',wal=False);before=fingerprints(root);rows=ns['g3'](root,AT);assert rows[-1]['r']=='BACKUP_VERIFIED';after=fingerprints(root);assert before['gamagori_shadow.db']==after['gamagori_shadow.db'] and len(set(after)-set(before))==1
check('G3_ROLLBACK_JOURNAL_BACKUP',g3_rollback)
def g3_existing():
    root,w=fixture('g3-existing');dest=root/('gamagori_shadow.pre-certifi-97640c8c.20261102.sqlite3');dest.write_bytes(b'KEEP');before=fingerprints(root);expect_stop(lambda:ns['g3'](root,AT),'DEST_EXISTS');assert fingerprints(root)==before;w.close()
check('G3_EXISTING_DEST_NO_CHANGE',g3_existing)
def g3_aux_existing():
    root,w=fixture('g3-existing-aux');dest=root/'gamagori_shadow.pre-certifi-97640c8c.20261102.sqlite3-journal';dest.write_bytes(b'KEEP');before=fingerprints(root);expect_stop(lambda:ns['g3'](root,AT),'DEST_AUX_EXISTS');assert fingerprints(root)==before;w.close()
check('G3_EXISTING_AUX_NO_CHANGE',g3_aux_existing)
def g3_space():
    root,w=fixture('g3-space');before=fingerprints(root);expect_stop(lambda:ns['g3'](root,AT,free_override=0),'SPACE');assert fingerprints(root)==before;w.close()
check('G3_LOW_SPACE_STOP_BEFORE_SOURCE_CONNECT',g3_space)
def g3_partial():
    root,w=fixture('g3-partial');before=set(root.iterdir())
    def broken(*_):raise sqlite3.OperationalError('synthetic copy failure')
    rows=ns['g3'](root,AT,copy_fn=broken);assert rows[-1]['r']=='STOP' and rows[-1]['created'] and rows[-1]['partial_retained'];created=set(root.iterdir())-before;assert len(created)==1
    old=fingerprints(root);expect_stop(lambda:ns['g3'](root,AT),'DEST_EXISTS');assert fingerprints(root)==old;w.close()
check('G3_PARTIAL_RETAINED_RETRY_NO_OVERWRITE',g3_partial)
def g3_integrity():
    root,_=fixture('g3-corrupt',wal=False);p=root/'gamagori_shadow.db';b=bytearray(p.read_bytes());b[100]=0;p.write_bytes(b);before=set(root.iterdir());rows=ns['g3'](root,AT);assert rows[-1]['r']=='STOP' and rows[-1]['phase']=='source' and not rows[-1]['created'];assert set(root.iterdir())==before
check('G3_SOURCE_INTEGRITY_FAILURE_NO_DEST',g3_integrity)
def g3_extra_file():
    root,w=fixture('g3-extra')
    def copy(src,dst,progress):src.backup(dst,progress=progress);(root/'unexpected.aux').write_bytes(b'fixture-only')
    rows=ns['g3'](root,AT,copy_fn=copy);assert rows[-1]['r']=='STOP' and rows[-1]['why'] in ('UNEXPECTED_FILES','UNEXPECTED_FILE_EVENT') and rows[-1]['partial_retained'];w.close()
check('G3_UNEXPECTED_EXTRA_FILE_STOP_NO_CLEANUP',g3_extra_file)
def g3_transient_extra():
    root,w=fixture('g3-transient-extra')
    def copy(src,dst,progress):
        src.backup(dst,progress=progress);p=root/'unexpected.transient';p.write_bytes(b'fixture-only');p.unlink()
    rows=ns['g3'](root,AT,copy_fn=copy);assert rows[-1]['r']=='STOP' and rows[-1]['why']=='UNEXPECTED_FILE_EVENT' and rows[-1]['partial_retained'];w.close()
check('G3_TRANSIENT_UNEXPECTED_FILE_EVENT_STOP',g3_transient_extra)
def g3_copy_bad():
    root,w=fixture('g3-copy-bad');rows=ns['g3'](root,AT,copy_fn=lambda *_:None);assert rows[-1]['r']=='STOP' and rows[-1]['phase']=='copy_integrity' and rows[-1]['partial_retained'];w.close()
check('G3_INVALID_COPY_STOP_PARTIAL_RETAINED',g3_copy_bad)
def ro_enforcement():
    root,_=fixture('source-ro',wal=False);before=fingerprints(root);c=ns['ro_connect'](root/'gamagori_shadow.db')
    try:
        try:c.execute("DELETE FROM race_states");raise AssertionError('source write allowed')
        except sqlite3.OperationalError:pass
    finally:c.close()
    assert fingerprints(root)==before
check('SOURCE_MODE_RO_DENIES_DATA_MUTATION',ro_enforcement)
def g3_concurrent():
    root,w=fixture('g3-concurrent',events=1200);start=threading.Event();done=threading.Event();writer_count=[]
    def writer():
        c=sqlite3.connect(root/'gamagori_shadow.db',timeout=2.5);start.wait();count=0
        while not done.is_set() and count<100:
            count+=1;k='later'+str(count);c.execute('insert into idempotency_keys values(?,?)',(k,k));c.execute('insert into shadow_events values(?,?,?,?,?,?,?,?,?)',(k,k,'rid','event','x','h','now',1,'now'));c.commit();time.sleep(0.001)
        writer_count.append(count);c.close()
    thread=threading.Thread(target=writer);thread.start()
    def copy(src,dst,progress):
        def paced(*args):start.set();time.sleep(0.0002);progress(*args)
        src.backup(dst,pages=1,progress=paced,sleep=0.05)
    try:rows=ns['g3'](root,AT,copy_fn=copy)
    finally:done.set();start.set();thread.join(timeout=5)
    assert rows[-1]['r']=='BACKUP_VERIFIED' and writer_count[0]>0 and rows[-1]['rows']['shadow_events']==1200
    assert w.execute('select count(*) from shadow_events').fetchone()[0]>1200;w.close()
check('G3_SNAPSHOT_WITH_CONCURRENT_FIXTURE_WRITER',g3_concurrent)

def g4_env_cases():
    import certifi
    factory=lambda:ssl.create_default_context(cafile=certifi.where())
    good=ns['g4_env'](PROJECT,environ={},context_factory=factory);assert good[-1]['r']=='ENV_OBS_PASS'
    bad=ns['g4_env'](PROJECT,environ={'https_proxy':'SYNTHETIC_NOT_PRINTED'},context_factory=factory);assert bad[-1]['r']=='STOP_ENV' and bad[0]['env_overrides']==1
    def extra():
        c=factory();c.load_verify_locations(cafile=str(WORK/'tls-fixtures/ca.pem'));return c
    assert ns['g4_env'](PROJECT,environ={},context_factory=extra)[-1]['r']=='STOP_ENV'
    assert len(ns['PINS'])==19 and len(ns['TARGETS'])==5
check('G4_FIXED19_CA118_EFFECTIVE_CA_NO_OVERRIDES',g4_env_cases)

class Handler(http.server.BaseHTTPRequestHandler):
    status=200
    def do_GET(self):self.send_response(self.status);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'ok')
    def log_message(self,*_):pass
class TLS:
    def __init__(self,cert,status=200):
        handler=type('FixtureHandler',(Handler,),{'status':status});self.s=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(WORK/('tls-fixtures/'+cert+'.pem'),WORK/'tls-fixtures/leaf.key');self.s.socket=ctx.wrap_socket(self.s.socket,server_side=True);self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start();self.url='https://127.0.0.1:'+str(self.s.server_port)
    def close(self):self.s.shutdown();self.s.server_close();self.t.join()
def tls_cases():
    import httpx
    servers=[TLS('valid'),TLS('expired'),TLS('wrong-host'),TLS('self-signed'),TLS('valid',403)]
    trusted=ssl.create_default_context(cafile=str(WORK/'tls-fixtures/ca.pem'))
    def factory(**kw):kw.update(verify=trusted,trust_env=False);return httpx.AsyncClient(**kw)
    targets=[('valid',servers[0].url,False),('expired',servers[1].url,True),('host',servers[2].url,True),('self',servers[3].url,True),('403',servers[4].url,True)]
    origins={('127.0.0.1',s.s.server_port) for s in servers}
    try:rows=asyncio.run(ns['probe_targets'](targets,origins,factory))
    finally:
        for s in servers:s.close()
    assert [r['c'] for r in rows[:-1]]==['CONNECTED','CERT_REJECTED','CERT_REJECTED','CERT_REJECTED','OTHER_FAILURE'] and rows[-1]['r']=='UNVERIFIED'
check('G4_REAL_LOOPBACK_TLS_AND_HTTP403_THREE_CLASSES',tls_cases)
def tls_failures():
    import httpx
    seen=[]
    def handle(req):
        seen.append(req.url.host)
        if req.url.path=='/proxy':
            exc=httpx.ProxyError('CERTIFICATE_VERIFY_FAILED synthetic');exc.__cause__=ssl.SSLCertVerificationError(1,'synthetic');raise exc
        if req.url.path=='/dns':
            exc=httpx.ConnectError('synthetic');exc.__cause__=socket.gaierror(-2,'synthetic');raise exc
        if req.url.path=='/timeout':raise httpx.ReadTimeout('synthetic')
        if req.url.path=='/redirect':return httpx.Response(302,headers={'Location':'https://outside.invalid/'})
        return httpx.Response(200)
    def factory(**kw):kw.update(transport=httpx.MockTransport(handle));return httpx.AsyncClient(**kw)
    targets=[(x,'https://allowed.invalid/'+x,True) for x in ('proxy','dns','timeout','redirect')]
    rows=asyncio.run(ns['probe_targets'](targets,{('allowed.invalid',443)},factory))
    assert all(r['c']=='OTHER_FAILURE' for r in rows[:-1]) and 'outside.invalid' not in seen
    assert {r['why'] for r in rows[:-1]}=={'ProxyError','DNS','Timeout','ScopeBlocked'}
check('G4_DNS_TIMEOUT_PROXY_REDIRECT_NOT_PASS',tls_failures)
def hq12_settings():
    import ast
    original=ast.parse((E/'references/HQ12_original.py').read_text());call=next(n for n in ast.walk(original) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='AsyncClient')
    settings={k.arg:ast.literal_eval(k.value) for k in call.keywords}
    assert settings=={'timeout':8.0,'verify':True,'trust_env':True,'follow_redirects':True}
    assert ns['TARGETS'][-2:]==[('NEGATIVE_1','https://dv-g3b-emudhra.we-have-a-problem.com/',True),('NEGATIVE_2','https://dv-g3b-aaa-emudhra.we-have-a-problem.com/',True)]
check('G4_HQ12_URLS_FOUR_OPTIONS_PRESERVED',hq12_settings)
def db_checks():
    root,w=fixture('g4-db');assert ns['g4_db'](root)[-1]['r']=='DB_OBS_PASS';w.execute("insert into idempotency_keys values('orphan','orphan')");w.commit();assert ns['g4_db'](root)[-1]['r']=='STOP_DB';w.close()
    root,w=fixture('g4-duplicate',unique=False);w.execute("insert into shadow_events values('other','k0','r','e','p','h','t',1,'t')");w.commit();assert ns['g4_db'](root)[1]['dup']==1;w.close()
check('G4_SQLITE_INTEGRITY_DUPLICATE_AND_ORPHAN',db_checks)

def frames_and_guards():
    commands=list((E/'commands').glob('*.candidate.txt'))
    assert len(commands)==5
    for path in commands:
        command=path.read_text();assert command.isascii() and '\n' not in command and command.startswith('{ ') and command.endswith('; }')
        args=shlex.split(command[2:-3]);assert args[:3]==['python','-B','-c'] and len(args)==5
        assert subprocess.run(['bash','-n','-c',command],capture_output=True).returncode==0
        for cut in (1,len(command)//2,len(command)-3,len(command)-1):
            r=subprocess.run(['bash','-c',command[:cut]],capture_output=True);assert r.returncode==2 and not r.stdout
        r=subprocess.run([sys.executable,'-B','-c',args[3]],capture_output=True);assert r.returncode!=0 and b'BEGIN' not in r.stdout
    for name in ('G2.actual.private.txt','G3.actual.private.txt'):
        raw=(WORK/name).read_bytes();lines=raw.splitlines(keepends=True);import re
        match=re.fullmatch(br'END CERTIFI_AUDIT_V002 lines=([0-9]+) bytes=([0-9]+) sha256=([a-f0-9]{64})\n',lines[-1]);body=b''.join(lines[1:-1]);assert match and len(lines)-2==int(match[1]) and len(body)==int(match[2]) and hashlib.sha256(body).hexdigest().encode()==match[3]
check('ALL_FIVE_ASCII_FRAMES_AND_TRUNCATION_GUARDS',frames_and_guards)
def command_guards():
    code=core+'\n'+'''sys.addaudithook(audit_guard)
import socket,subprocess
for f in (lambda:open("/__G_WRITE_FORBIDDEN__","w"),lambda:open(".env","r"),lambda:socket.socket(),lambda:subprocess.run([sys.executable,"-c","pass"]),lambda:sqlite3.connect(":memory:")):
    try:f();raise AssertionError("unexpected side effect")
    except PermissionError as exc:assert str(exc)=="G_SIDE_EFFECT_BLOCKED"
print("GUARDS_OK")
'''
    r=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True);assert r.returncode==0 and r.stdout=='GUARDS_OK\n' and not r.stderr
check('COMMAND_WRITE_DOTENV_NETWORK_SUBPROCESS_DB_GUARDS',command_guards)
def guarded_functions():
    for fn in ('g2','g3','g4_db'):
        root,w=fixture('guarded-'+fn)
        code='__name__="isolated_library"\n'+core+'\n'+'\n'.join(parts)+'\n'
        code+='entry("GUARDED_FIXTURE",lambda: '+fn+'(Path(sys.argv[1])'+(',Path(sys.argv[2]),dt.datetime(2026,11,2,9,tzinfo=dt.timezone(dt.timedelta(hours=9))))' if fn=='g2' else ',dt.datetime(2026,11,2,9,tzinfo=dt.timezone(dt.timedelta(hours=9))))' if fn=='g3' else ')')+')\n'
        r=subprocess.run([sys.executable,'-B','-c',code,str(root),str(PROJECT/'sqlite_readonly_audit.py')],capture_output=True,text=True,timeout=20)
        assert r.returncode==0 and not r.stderr
        rows=[json.loads(line) for line in r.stdout.splitlines()[1:-1]]
        assert rows[-1]['r'] in ('SNAPSHOT_ONLY','BACKUP_VERIFIED','DB_OBS_PASS'),rows[-1]
        w.close()
check('G2_G3_G4_DB_COMPLETE_WITH_ACTIVE_AUDIT_GUARDS',guarded_functions)
meta={'python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,'os':os.uname().sysname,'cases':len(results),'render_execution':'NOT_RUN','external_NEGATIVE_1_2':'UNVERIFIED_NOT_RUN','claude_independent_review':'PENDING'}
meta['command_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((E/'commands').glob('*.candidate.txt'))}
(WORK/'test-summary.raw.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print('SUMMARY '+json.dumps(meta,sort_keys=True),flush=True)
