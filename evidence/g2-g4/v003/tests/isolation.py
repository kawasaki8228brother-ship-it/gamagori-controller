"""Only loopback sockets and injected exceptions. Never execute on Render."""
from pathlib import Path
import asyncio,ast,hashlib,http.server,json,os,platform,re,runpy,socket,ssl,subprocess,sys,threading,time,types
import httpx,certifi

V=Path(__file__).resolve().parents[1];E=V.parent
if len(sys.argv)!=3:raise SystemExit('WORK and disposable PROJECT required')
WORK=Path(sys.argv[1]).resolve();PROJECT=Path(sys.argv[2]).resolve();F=WORK/'tls-fixtures'
ns={'__name__':'isolated_library'}
exec((E/'source/common.py').read_text()+'\n'+(E/'source/g4_env.py').read_text()+'\n'+(V/'source/baseline_gate_v003.py').read_text()+'\n'+(V/'source/g4_tls_v003.py').read_text(),ns)
sys.dont_write_bytecode=True
def local_network_only(event,args):
    if event=='socket.getaddrinfo' and args[0] not in ('localhost','127.0.0.1','::1',b'localhost',b'127.0.0.1'):
        raise PermissionError('EXTERNAL_DNS_FORBIDDEN')
    if event in ('socket.connect','socket.bind'):
        address=args[1]
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1'):
            raise PermissionError('NON_LOOPBACK_FORBIDDEN')
sys.addaudithook(local_network_only)
print('ENV '+json.dumps({'python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'kernel':platform.release(),'machine':platform.machine(),'httpx':httpx.__version__,'certifi':certifi.__version__,'network':'LOOPBACK_ONLY_NO_EXTERNAL_TARGETS'},sort_keys=True),flush=True)
cases=[];observed=[];servers=[]
def check(name,fn):
    try:fn()
    except BaseException as exc:
        print('CASE '+name+' FAIL '+type(exc).__name__,flush=True);raise SystemExit(1)
    cases.append(name);print('CASE '+name+' PASS',flush=True)
def record(name,row):
    observed.append({'case':name,**row});print('OBS '+json.dumps({'case':name,**row},sort_keys=True),flush=True)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        status={'/forbidden':403,'/missing':404,'/server-error':503,'/redirect-block':302,'/redirect-local':302,'/redirect-bad-cert':302}.get(self.path,200)
        if self.path=='/timeout':time.sleep(8.25)
        try:
            self.send_response(status)
            if self.path=='/redirect-block':self.send_header('Location','https://outside.invalid/never-send')
            elif self.path=='/redirect-local':self.send_header('Location','/forbidden')
            elif self.path=='/redirect-bad-cert':self.send_header('Location',BAD_CERT_URL)
            self.send_header('Content-Length','0');self.end_headers()
        except (OSError,ssl.SSLError):pass
class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_CONNECT(self):
        self.send_response(403);self.send_header('Content-Length','0');self.end_headers()
class Server(http.server.ThreadingHTTPServer):daemon_threads=True
def server(cert=None,proxy=False):
    s=Server(('127.0.0.1',0),ProxyHandler if proxy else Handler)
    if cert:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(F/(cert+'.pem'),F/'leaf.key');s.socket=context.wrap_socket(s.socket,server_side=True)
    thread=threading.Thread(target=s.serve_forever,kwargs={'poll_interval':0.02},daemon=True);thread.start();servers.append((s,thread))
    return s.server_address[1]
def client_context(cafile='trusted',partial=True):
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.load_verify_locations(cafile=F/(cafile+'.pem'))
    context.verify_flags|=ssl.VERIFY_X509_STRICT
    if partial:context.verify_flags|=ssl.VERIFY_X509_PARTIAL_CHAIN
    else:context.verify_flags&=~ssl.VERIFY_X509_PARTIAL_CHAIN
    return context
def factory(context=None,proxy_port=None,transport=None,seen=None):
    def make(**kwargs):
        assert {k:kwargs[k] for k in ('timeout','verify','trust_env','follow_redirects')}=={'timeout':8.0,'verify':True,'trust_env':True,'follow_redirects':True}
        assert set(kwargs['event_hooks'])=={'request','response'}
        if seen is not None:seen.append(True)
        t=transport or httpx.AsyncHTTPTransport(verify=context or client_context(),trust_env=False,proxy=('http://127.0.0.1:'+str(proxy_port)) if proxy_port else None)
        return httpx.AsyncClient(transport=t,**kwargs)
    return make
def probe(label,port,path='/',context=None,negative=False,proxy_port=None,allowed=None):
    url='https://127.0.0.1:'+str(port)+path
    rows=asyncio.run(ns['probe_targets']([(label,url,negative)],allowed or {('127.0.0.1',port)},factory(context,proxy_port)))
    record(label,rows[0]);return rows[0]
def synthetic(code=None,message='synthetic verify message'):
    error=ssl.SSLCertVerificationError(1,'DO_NOT_PRINT_THIS_EXCEPTION_STRING')
    if code is not None:error.verify_code=code
    error.verify_message=message
    return error
def wrap(error,kind=httpx.ConnectError):
    result=kind('DO_NOT_PRINT_THIS_EXCEPTION_STRING');result.__cause__=error;return result

try:
    valid=server('valid');unknown=server('unknown-issuer');chain=server('untrusted-chain');expired=server('expired');wrong=server('wrong-host');leaf=server('self-signed');inter=server('intermediate-chain');proxy=server(proxy=True)
    BAD_CERT_URL='https://127.0.0.1:'+str(unknown)+'/'
    def issuer20():
        r=probe('ISSUER_20',unknown,negative=True);assert r['tls']=='CERT_REJECTED' and r['verify_code']==20 and r['http'] is None
    check('ACTUAL_UNKNOWN_ISSUER_CODE20',issuer20)
    def issuer19():
        r=probe('ISSUER_19',chain,negative=True);assert r['tls']=='CERT_REJECTED' and r['verify_code']==19
    check('ACTUAL_UNTRUSTED_ROOT_CHAIN_CODE19',issuer19)
    def issuer2():
        r=probe('ISSUER_2',inter,context=client_context('intermediate',partial=False),negative=True);assert r['tls']=='CERT_REJECTED' and r['verify_code']==2
    check('ACTUAL_MISSING_ISSUER_CODE2_FIXTURE_FLAGS',issuer2)
    def expiry():
        r=probe('EXPIRED',expired,negative=True);assert r['tls']=='OTHER_FAILURE' and r['verify_code']==10
    check('ACTUAL_EXPIRED_CODE10_OTHER',expiry)
    def hostname():
        r=probe('HOSTNAME',wrong,negative=True);assert r['tls']=='OTHER_FAILURE' and r['verify_code'] in (62,64)
    check('ACTUAL_HOSTNAME_MISMATCH_OTHER',hostname)
    def selfsigned():
        r=probe('SELF_SIGNED_LEAF',leaf,negative=True);assert r['tls']=='OTHER_FAILURE' and r['verify_code']==18
    check('ACTUAL_SELF_SIGNED_LEAF_CODE18_OTHER',selfsigned)
    def responses():
        for path,status in (('/',200),('/forbidden',403),('/missing',404),('/server-error',503)):
            r=probe('HTTP_'+str(status),valid,path);assert r['tls']=='CONNECTED' and r['http']==status and r['verify_code'] is None
    check('TARGET_HTTP_200_403_404_503_CONNECTED',responses)
    def redirect_scope():
        r=probe('REDIRECT_SCOPE',valid,'/redirect-block');assert r['tls']=='CONNECTED' and r['http']==302
    check('FIRST_RESPONSE_RETAINED_AFTER_REDIRECT_BLOCK',redirect_scope)
    def redirect_local():
        r=probe('REDIRECT_FIRST_HOP',valid,'/redirect-local');assert r['tls']=='CONNECTED' and r['http']==302
    check('FIRST_RESPONSE_RETAINED_AFTER_LOCAL_REDIRECT',redirect_local)
    def redirect_bad_cert():
        r=probe('REDIRECT_LATER_CERT_ERROR',valid,'/redirect-bad-cert',allowed={('127.0.0.1',valid),('127.0.0.1',unknown)});assert r['tls']=='CONNECTED' and r['http']==302 and r['verify_code'] is None
    check('FIRST_RESPONSE_RETAINED_AFTER_LATER_CERT_ERROR',redirect_bad_cert)
    def scope_before():
        r=probe('SCOPE_BEFORE_RESPONSE',valid,allowed={('127.0.0.1',1)});assert r['tls']=='OTHER_FAILURE' and r['http'] is None and r['why']=='SCOPE'
    check('SCOPE_BEFORE_RESPONSE_OTHER_NO_NETWORK',scope_before)
    def proxy403():
        r=probe('PROXY_403',valid,proxy_port=proxy);assert r['tls']=='OTHER_FAILURE' and r['http'] is None and r['why']=='PROXY'
    check('ACTUAL_LOCAL_PROXY_CONNECT_403_OTHER',proxy403)
    def timeout():
        r=probe('TIMEOUT_8_SECONDS',valid,'/timeout');assert r['tls']=='OTHER_FAILURE' and r['http'] is None and r['why']=='TIMEOUT'
    check('ACTUAL_LOCAL_READ_TIMEOUT_8_SECONDS_OTHER',timeout)
    def dns():
        class DNSTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):raise wrap(socket.gaierror(socket.EAI_NONAME,'synthetic DNS'))
        rows=asyncio.run(ns['probe_targets']([('INJECTED_DNS','https://127.0.0.1:1/',False)],{('127.0.0.1',1)},factory(transport=DNSTransport())))
        record('INJECTED_DNS',rows[0]);assert rows[0]['tls']=='OTHER_FAILURE' and rows[0]['http'] is None and rows[0]['why']=='DNS'
    check('INJECTED_DNS_OTHER_NO_RESOLVER',dns)
    def typed_only():
        class NoString(httpx.ConnectError):
            def __str__(self):raise AssertionError('str must never be called')
        error=NoString('CERTIFICATE_VERIFY_FAILED CERTIFICATE VERIFY FAILED')
        assert ns['classify_exception'](error)[0]=='OTHER_FAILURE'
        generic=ssl.SSLError(1,'CERTIFICATE_VERIFY_FAILED')
        assert ns['classify_exception'](generic)[0]=='OTHER_FAILURE'
        assert ns['classify_exception'](synthetic())[0]=='OTHER_FAILURE'
        for code in (18,10,62,64,21,True,'20'):
            assert ns['classify_exception'](synthetic(code))[0]=='OTHER_FAILURE'
    check('INSTANCE_ONLY_TEXT_AND_MISSING_OR_OTHER_CODES',typed_only)
    def verify_messages():
        for code in (2,19,20):
            r=ns['classify_exception'](wrap(synthetic(code,'bad\n\t\u2603 '+('x'*150))))
            assert r[0]=='CERT_REJECTED' and type(r[1]) is int and len(r[2])<=100 and all(32<=ord(c)<=126 for c in r[2])
        m=ns['safe_verify_message']('verify https://secret.invalid/token user:pass@proxy /private/path\n')
        assert '://' not in m and '@' not in m and '/private' not in m
        assert ns['safe_verify_message'](None) is None
    check('VERIFY_ATTRIBUTES_ASCII_100_URL_PATH_SUPPRESSION',verify_messages)
    def graph():
        error=synthetic(20);root=wrap(error);root.__context__=root;assert ns['classify_exception'](root)[0]=='CERT_REJECTED'
        for _ in range(12):root=wrap(root)
        assert ns['classify_exception'](root)[0]=='OTHER_FAILURE'
        mixed=synthetic(20);mixed.__context__=synthetic(10);assert ns['classify_exception'](mixed)[0]=='OTHER_FAILURE'
        for kind in (httpx.ProxyError,httpx.ReadTimeout):
            assert ns['classify_exception'](wrap(synthetic(20),kind))[0]=='OTHER_FAILURE'
        assert ns['classify_exception'](wrap(wrap(synthetic(20)),httpx.ConnectError))[0]=='CERT_REJECTED'
    check('CAUSE_CONTEXT_CYCLES_LIMIT_AMBIGUITY_PROXY_TIMEOUT',graph)
    def aggregate_real():
        ports=[valid,valid,valid,unknown,chain];paths=['/','/forbidden','/redirect-block','/','/']
        targets=[(name,'https://127.0.0.1:'+str(port)+path,negative) for (name,_,negative),port,path in zip(ns['TARGETS'],ports,paths)]
        rows=asyncio.run(ns['probe_targets'](targets,{('127.0.0.1',p) for p in ports},factory()))
        assert rows[-1]=={'r':'TLS_OBS_PASS','mode':'POST','go':False};record('LOCAL_POST_AGGREGATE',rows[-1])
        targets=[(name,'https://127.0.0.1:'+str(valid)+'/',negative) for name,_,negative in ns['TARGETS']]
        baseline=asyncio.run(ns['probe_targets'](targets,{('127.0.0.1',valid)},factory(),baseline=True));assert baseline[-1]=={'r':'BASELINE_OBS_EXPECTED','mode':'BASELINE','go':False};record('LOCAL_BASELINE_CLASSIFIER_ONLY',baseline[-1])
    check('REAL_LOCAL_FIVE_TARGET_POST_AND_BASELINE_AGGREGATES',aggregate_real)
    def aggregates():
        rows=[{'id':n,'tls':'CERT_REJECTED' if neg else 'CONNECTED','http':None if neg else 403,'verify_code':20 if neg else None,'verify_message':None} for n,_,neg in ns['TARGETS']]
        assert ns['tls_summary'](rows)['r']=='TLS_OBS_PASS'
        for index in (3,4):
            bad=[dict(r) for r in rows];bad[index].update(tls='CONNECTED',http=403,verify_code=None);assert ns['tls_summary'](bad)['r']=='FAIL'
        bad=[dict(r) for r in rows];bad[0].update(tls='CERT_REJECTED',verify_code=19,http=None);assert ns['tls_summary'](bad)['r']=='FAIL'
        for code in (None,18,10,62):
            bad=[dict(r) for r in rows];bad[3].update(tls='OTHER_FAILURE',verify_code=code);assert ns['tls_summary'](bad)['r']=='UNVERIFIED'
        assert ns['tls_summary'](rows[:-1])['r']=='UNVERIFIED'
    check('POST_FAIL_UNVERIFIED_AND_GO_ALWAYS_FALSE',aggregates)
    def baseline_aggregate():
        rows=[{'id':n,'tls':'CONNECTED','http':403,'verify_code':None,'verify_message':None} for n,_,_ in ns['TARGETS']]
        assert ns['tls_summary'](rows,True)=={'r':'BASELINE_OBS_EXPECTED','mode':'BASELINE','go':False}
        rows[0].update(tls='CERT_REJECTED',http=None,verify_code=20)
        assert ns['tls_summary'](rows,True)=={'r':'FAIL','mode':'BASELINE','go':False}
        rows[0].update(tls='CONNECTED',http=200,verify_code=None);rows[3].update(tls='CERT_REJECTED',http=None,verify_code=20)
        assert ns['tls_summary'](rows,True)=={'r':'UNVERIFIED','mode':'BASELINE','go':False}
    check('BASELINE_EXPECTED_IS_NOT_POST_PASS_POSITIVE_REJECTION_FAIL',baseline_aggregate)
    def baseline_predicate():
        obs={'certifi_module':'2026.07.22','certifi_metadata':'2026.7.22','ca_sha':ns['BASELINE_CA_SHA'],'ca_n':121,'eff_n':121,'eff_eq':True,'verify_required':True,'hostname':True,'env_overrides':0,'runtime':True,'app_source':True}
        assert ns['baseline_observations_pass'](obs)
        for key,value in (('certifi_module','2026.10.23'),('certifi_metadata','2026.7.22rc1'),('ca_sha','0'*64),('ca_n',118),('eff_n',118),('eff_eq',False),('verify_required',False),('hostname',False),('env_overrides',1),('runtime',False),('app_source',False)):
            bad=dict(obs);bad[key]=value;assert not ns['baseline_observations_pass'](bad)
    check('BASELINE_PREDICATE_SIMULATED_OLD_OBSERVATIONS_ONLY',baseline_predicate)
    def gate_no_network():
        original=ns['os'];saved_post=ns['g4_env'];saved_baseline=ns['baseline_gate']
        try:
            for name in ns['ENV_NAMES']:
                ns['os']=types.SimpleNamespace(environ={name:''})
                for baseline in (False,True):
                    result=ns['run_tls_mode'](baseline);assert result[-1]['r']=='STOP' and result[-1]['why']=='SSL_PROXY_ENV_PRESENT'
            ns['os']=types.SimpleNamespace(environ={})
            ns['g4_env']=lambda:[{'r':'STOP_ENV'}]
            ns['baseline_gate']=lambda:[{'r':'STOP_BASELINE_ENV'}]
            assert ns['run_tls_mode'](False)[-1]['why']=='POST_PREFLIGHT'
            assert ns['run_tls_mode'](True)[-1]['why']=='BASELINE_PREFLIGHT'
            for value in ('not-a-number','7','NaN'):
                ns['os']=types.SimpleNamespace(environ={'HTTP_TIMEOUT_SECONDS':value})
                try:ns['checked_app_timeout']();raise AssertionError('timeout accepted')
                except ns['Stop']:pass
            ns['os']=types.SimpleNamespace(environ={'SSLKEYLOGFILE':''})
            try:ns['checked_app_timeout']();raise AssertionError('keylog accepted')
            except ns['Stop']:pass
        finally:ns['os']=original;ns['g4_env']=saved_post;ns['baseline_gate']=saved_baseline
    check('ALL_14_ENV_NAMES_AND_MISMATCH_STOP_BEFORE_CLIENT',gate_no_network)
    def actual_gates():
        context=lambda:__import__('httpx._config',fromlist=['create_ssl_context']).create_ssl_context(trust_env=False)
        post=ns['g4_env'](PROJECT,environ={},context_factory=context);assert post[-1]['r']=='ENV_OBS_PASS'
        baseline=ns['baseline_gate'](PROJECT,environ={},context_factory=context);assert baseline[-1]['r']=='STOP_BASELINE_ENV'
        record('ACTUAL_NEW_BUNDLE_BASELINE_STOP',baseline[0])
    check('ACTUAL_POST_BUNDLE_PASS_OLD_BASELINE_REJECTS_NEW_BUNDLE',actual_gates)
    def successful_gate_output_simulated_client():
        saved={k:ns[k] for k in ('os','g4_env','baseline_gate','probe_targets','_network')}
        actual_context=lambda:__import__('httpx._config',fromlist=['create_ssl_context']).create_ssl_context(trust_env=False)
        try:
            ns['os']=types.SimpleNamespace(environ={})
            async def no_network(targets,origins,baseline=False):
                assert len(targets)==5 and origins=={(httpx.URL(u).host,443) for _,u,_ in ns['TARGETS']}
                return [{'r':'UNVERIFIED','go':False}]
            ns['probe_targets']=no_network
            ns['g4_env']=lambda:saved['g4_env'](PROJECT,environ={},context_factory=actual_context)
            ca={'ca_sha':ns['BASELINE_CA_SHA'],'ca_n':121,'eff_n':121,'eff_eq':True}
            ns['baseline_gate']=lambda:[ca,{'r':'BASELINE_ENV_PASS','go':False}]
            for baseline in (False,True):
                rows=ns['run_tls_mode'](baseline);assert rows[0]['ca_n']==(121 if baseline else 118) and rows[0]['eff_eq'] and rows[0]['eff_n']==rows[0]['ca_n']
                assert rows[0]['ca_sha']==(ns['BASELINE_CA_SHA'] if baseline else ns['CA_SHA']) and rows[0]['env_overrides']==0 and rows[-1]['go'] is False
        finally:ns.update(saved)
    check('GATE_OUTPUT_CA_HASH_EFFECTIVE_SET_SIMULATED_CLIENT_NO_NETWORK',successful_gate_output_simulated_client)
    def urls_conditions():
        assert [u for _,u,_ in ns['TARGETS']]==['https://www.boatrace.jp/','https://boatrace.jp/','https://boatraceopenapi.github.io/','https://dv-g3b-emudhra.we-have-a-problem.com/','https://dv-g3b-aaa-emudhra.we-have-a-problem.com/']
        assert len(ns['ENV_NAMES'])==14
    check('HQ12_URLS_FOUR_OPTIONS_AND_SINGLE_ATTEMPT_PRESERVED',urls_conditions)
    def commands():
        module=runpy.run_path(str(V/'tests/verify-commands.py'));module['verify']()
        verifier=runpy.run_path(str(E/'tests/verify-output.py'))['verify']
        for filename in ('G4_TLS_v003','G4_baseline_v003'):
            b=(V/('commands/'+filename+'.candidate.txt')).read_bytes();command=b.decode('ascii');assert '\n' not in command and not b.endswith(b'\n')
            for cut in (1,2,10,100,len(b)//2,len(b)-50,len(b)-2,len(b)-1):
                parsed=subprocess.run(['bash','-n','-c',command[:cut]],capture_output=True);assert parsed.returncode!=0
            tokens=__import__('shlex').split(command);envelope=ast.literal_eval(tokens[4][5:-1]);encoded=re.search(r'base64.b64decode\("([A-Za-z0-9+/=]+)"',envelope).group(1)
            changed=('A' if encoded[0]!='A' else 'B')+encoded[1:]
            bad=command.replace(encoded,changed,1)
            result=subprocess.run(['bash','-c',bad],capture_output=True);assert result.returncode!=0 and b'BEGIN' not in result.stdout
            task_env=dict(os.environ);task_env['PATH']=str(Path(sys.executable).parent)+os.pathsep+task_env.get('PATH','');task_env['HTTP_PROXY']=''
            result=subprocess.run(['bash','-c',command],cwd=PROJECT,env=task_env,capture_output=True)
            assert verifier(result.stdout) and b'SSL_PROXY_ENV_PRESENT' in result.stdout and result.stderr==b''
            (WORK/(filename+'.gate-stop.frame.txt')).write_bytes(result.stdout)
    check('ASCII_FRAMES_TRUNCATION_HASH_GUARDS_AND_FULL_GATE_STOP',commands)
    summary={'cases':len(cases),'classification_tests':'PASS','python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'production_openssl_reported_by_HQ13':'OpenSSL 3.0.20','openssl_3_0_compatibility':'UNVERIFIED_NOT_AVAILABLE','baseline_old_bundle_actual':'UNVERIFIED_NOT_AVAILABLE','external_five_targets':'NOT_RUN','render':'NOT_RUN','go':False}
    print('SUMMARY '+json.dumps(summary,sort_keys=True),flush=True);print('EXIT_CODE 0',flush=True)
    (WORK/'summary.raw.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    (WORK/'observations.raw.json').write_text(json.dumps(observed,indent=2,sort_keys=True)+'\n')
finally:
    for s,t in servers:s.shutdown();s.server_close();t.join(timeout=2)
