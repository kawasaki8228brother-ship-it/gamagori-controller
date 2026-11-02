"""Disposable local servers and injected unit exceptions only; never Render."""
from pathlib import Path
import asyncio,ast,hashlib,http.server,json,os,platform,re,runpy,socket,socketserver,ssl,subprocess,sys,threading,time,types
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
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','::1'):raise PermissionError('NON_LOOPBACK_FORBIDDEN')
sys.addaudithook(local_network_only)
environment={'python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'kernel':platform.release(),'machine':platform.machine(),'httpx':httpx.__version__,'certifi':certifi.__version__,'network':'LOOPBACK_ONLY_NO_EXTERNAL_TARGETS'}
print('ENV '+json.dumps(environment,sort_keys=True),flush=True)
cases=[];observed=[];servers=[]
def check(name,fn):
    try:fn()
    except BaseException as exc:
        print('CASE '+name+' FAIL '+type(exc).__name__,flush=True);raise SystemExit(1)
    cases.append(name);print('CASE '+name+' PASS',flush=True)
def record(name,data):
    observed.append({'case':name,**data});print('OBS '+json.dumps({'case':name,**data},sort_keys=True),flush=True)
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.server.gets+=1
        status={'/forbidden':403,'/missing':404,'/server-error':503,'/redirect-block':302,'/redirect-local':302,'/redirect-bad-cert':302}.get(self.path,200)
        if self.path=='/header-timeout':time.sleep(8.25)
        try:
            self.send_response(status)
            if self.path=='/redirect-block':self.send_header('Location','https://outside.invalid/never-send')
            elif self.path=='/redirect-local':self.send_header('Location','/huge')
            elif self.path=='/redirect-bad-cert':self.send_header('Location',BAD_CERT_URL)
            self.send_header('Content-Length','1000000000' if self.path in ('/huge','/redirect-local','/redirect-block') else '0')
            self.end_headers()
            # Intentionally send NO BODY, even with huge Content-Length.
        except (OSError,ssl.SSLError):pass
class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_CONNECT(self):
        self.server.gets+=1;self.send_response(403);self.send_header('Content-Length','0');self.end_headers()
class Server(http.server.ThreadingHTTPServer):daemon_threads=True
class CaptureHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(1)
        try:data=self.request.recv(4096)
        except (OSError,ssl.SSLError):data=b''
        self.server.application_lengths.append(len(data))
class StallHandler(socketserver.BaseRequestHandler):
    def handle(self):time.sleep(8.3)
class TCPServer(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
def server(cert=None,proxy=False,capture=False,stall=False):
    s=TCPServer(('127.0.0.1',0),CaptureHandler if capture else StallHandler) if capture or stall else Server(('127.0.0.1',0),ProxyHandler if proxy else Handler)
    s.gets=0;s.sni=[];s.application_lengths=[]
    if cert:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(F/(cert+'.pem'),F/'leaf.key');context.set_alpn_protocols(['http/1.1'])
        context.set_servername_callback(lambda sock,name,initial:s.sni.append(name))
        s.socket=context.wrap_socket(s.socket,server_side=True)
    t=threading.Thread(target=s.serve_forever,kwargs={'poll_interval':0.02},daemon=True);t.start();servers.append((s,t));return s
def context(cafile='trusted',partial=True):
    c=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);c.load_verify_locations(cafile=F/(cafile+'.pem'));c.verify_flags|=ssl.VERIFY_X509_STRICT
    if partial:c.verify_flags|=ssl.VERIFY_X509_PARTIAL_CHAIN
    else:c.verify_flags&=~ssl.VERIFY_X509_PARTIAL_CHAIN
    return c
def fingerprints(c):return {hashlib.sha256(b).hexdigest() for b in c.get_ca_certs(binary_form=True)}
def factory(c=None,proxy_port=None,transport=None,seen=None):
    def make(**kwargs):
        assert {k:kwargs[k] for k in ('timeout','verify','trust_env','follow_redirects')}=={'timeout':8.0,'verify':True,'trust_env':True,'follow_redirects':True}
        assert set(kwargs['event_hooks'])=={'request','response'}
        tr=transport or httpx.AsyncHTTPTransport(verify=c or context(),trust_env=False,proxy=('http://127.0.0.1:'+str(proxy_port)) if proxy_port else None)
        client=httpx.AsyncClient(transport=tr,**kwargs)
        if seen is not None:seen.append(client)
        return client
    return make
def url(s,path='/'):return 'https://localhost:'+str(s.server_address[1])+path
def origins(*sv):return {('localhost',s.server_address[1]) for s in sv}
def one(name,s,path='/',c=None,connector=None,allow=None,baseline=False):
    c=c or context()
    rows=asyncio.run(ns['probe_stages']([(name,url(s,path),name.startswith('NEGATIVE'))],allow or origins(s),fingerprints(c),factory(c),connector,baseline))
    record(name,rows[0]);return rows
def synthetic(code=None,message='synthetic verification message'):
    e=ssl.SSLCertVerificationError(1,'DO_NOT_PRINT_EXCEPTION_STRING')
    if code is not None:e.verify_code=code
    e.verify_message=message;return e
def wrap(error,kind=httpx.ConnectError):
    e=kind('DO_NOT_PRINT_EXCEPTION_STRING');e.__cause__=error;return e
def get_only(name,s,path='/',c=None,proxy_port=None,transport=None,allowed=None):
    async def run():
        current,hooks=ns['headers_only_hooks'](allowed or origins(s))
        async with factory(c,proxy_port,transport)(timeout=8.0,verify=True,trust_env=True,follow_redirects=True,event_hooks=hooks) as client:
            return await ns['get_observation'](client,url(s,path),current)
    result=asyncio.run(run());record(name,result);return result
try:
    valid=server('valid');unknown=server('unknown-issuer');chain=server('untrusted-chain');expired=server('expired');wrong=server('wrong-host');leaf=server('self-signed');inter=server('intermediate-chain');proxy=server(proxy=True);capture=server('valid',capture=True);stall=server(stall=True)
    BAD_CERT_URL=url(unknown)
    def tls_no_http_sni_same_context():
        c=context();seen=[]
        async def connector(host,port,**kwargs):
            assert host=='localhost' and kwargs['server_hostname']=='localhost' and kwargs['ssl_handshake_timeout']==8.0 and kwargs['ssl'] is c
            result=await asyncio.open_connection(host,port,**kwargs)
            assert result[1].get_extra_info('ssl_object').selected_alpn_protocol()=='http/1.1'
            return result
        async def run():
            client=httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(verify=c,trust_env=False),trust_env=True)
            async with client:
                selected=ns['httpx_context'](client,fingerprints(c));assert selected is c
                return await ns['handshake']('localhost',capture.server_address[1],selected,connector)
        r=asyncio.run(run());time.sleep(.05);record('HANDSHAKE_ONLY',r)
        assert r['state']=='CONNECTED' and capture.application_lengths==[0] and capture.sni==['localhost'] and capture.gets==0
    check('HANDSHAKE_ONLY_ZERO_APPLICATION_BYTES_SNI_SAME_HTTPX_CONTEXT_ALPN',tls_no_http_sni_same_context)
    def issuer_cases():
        for s,c,code in ((unknown,context(),20),(chain,context(),19),(inter,context('intermediate',False),2)):
            r=one('NEGATIVE_1',s,c=c)[0]
            assert r['tls']['state']==r['get']['state']=='CERT_REJECTED' and r['tls']['verify_code']==r['get']['verify_code']==code
            assert r['tls']['v']==r['get']['v']=='PASS'
    check('ACTUAL_ISSUER_CODES_2_19_20_BOTH_STAGES_NEGATIVE1_PASS',issuer_cases)
    def other_certificate_cases():
        for s,code in ((expired,10),(wrong,62),(leaf,18)):
            r=one('NEGATIVE_1',s)[0]
            assert r['tls']['state']==r['get']['state']=='CERT_REJECTED' and r['tls']['verify_code']==r['get']['verify_code']==code
            assert r['tls']['v']==r['get']['v']=='UNVERIFIED'
    check('ACTUAL_CODES_10_62_18_DISTINCT_CERT_ERRORS_NEGATIVE1_UNVERIFIED',other_certificate_cases)
    def positive_any_cert_failure():
        for code in (2,19,20,10,62,18,None):assert ns['assess']('WWW','CERT_REJECTED',code in (2,19,20))=='FAIL'
        r=one('WWW',expired)[0];assert r['tls']['v']==r['get']['v']=='FAIL'
    check('POSITIVE_ANY_ACTUAL_CERT_VERIFICATION_ERROR_FAIL',positive_any_cert_failure)
    def negative2_any_code_control():
        for code in (2,19,20,10,62,18,None):
            e=ns['classify_exception'](wrap(synthetic(code)));assert e['state']=='CERT_REJECTED' and ns['assess']('NEGATIVE_2',e['state'],e['issuer_reject'])=='PASS'
        r=one('NEGATIVE_2',expired,baseline=True)[0];assert r['tls']['v']==r['get']['v']=='PASS'
        r=one('NEGATIVE_2',leaf)[0];assert r['tls']['v']==r['get']['v']=='PASS'
    check('NEGATIVE2_ANY_VERIFICATION_CODE_OR_MISSING_CODE_CONTROL_ONLY',negative2_any_code_control)
    def anchors():
        c=context();c.set_alpn_protocols(['http/1.1'])
        r=asyncio.run(ns['handshake']('localhost',valid.server_address[1],c));record('VERIFIED_ANCHOR',r)
        anchor=next(iter(fingerprints(c)));assert r['anchor_sha256']==anchor and r['bad_root'] is False
        old=ns['BAD_ROOTS'];ns['BAD_ROOTS']={anchor}
        try:
            again=asyncio.run(ns['handshake']('localhost',valid.server_address[1],c));assert again['state']=='CONNECTED' and again['bad_root'] is True
        finally:ns['BAD_ROOTS']=old
        assert ns['verified_anchor'](object(),c)==(None,None)
    check('VERIFIED_CHAIN_ANCHOR_SHA_BAD_ROOT_DIAGNOSTIC_ONLY_NULL_FALLBACK',anchors)
    def statuses():
        for path,status in (('/',200),('/forbidden',403),('/missing',404),('/server-error',503)):
            rows=one('WWW',valid,path);r=rows[0]
            assert r['tls']['state']=='CONNECTED' and r['tls']['v']=='PASS' and r['get']['state']=='HTTP_RESPONSE' and r['get']['http']==status and r['get']['v']=='PASS'
        r=one('NEGATIVE_1',valid,'/forbidden')[0];assert r['tls']['v']==r['get']['v']=='FAIL'
    check('HTTP_200_403_404_503_RECORDED_WITHOUT_CHANGING_TLS_VERDICT',statuses)
    def real_no_body_redirects():
        started=time.monotonic();r=get_only('HUGE_NO_BODY',valid,'/huge');assert r['state']=='HTTP_RESPONSE' and r['http']==200 and time.monotonic()-started<2
        started=time.monotonic();r=get_only('REDIRECT_NO_BODY',valid,'/redirect-local');assert r['http']==302 and r['last_http']==200 and r['end']=='COMPLETE' and time.monotonic()-started<2
    check('ACTUAL_STREAM_HEADERS_ONLY_HUGE_BODY_AND_REDIRECT_NO_DRAIN',real_no_body_redirects)
    def redirect_blocks():
        r=get_only('REDIRECT_SCOPE',valid,'/redirect-block');assert r['state']=='HTTP_RESPONSE' and r['http']==302 and r['end']=='SCOPE'
        r=get_only('SCOPE_BEFORE_RESPONSE',valid,allowed={('localhost',1)});assert r['state']=='OTHER_FAILURE' and r['http'] is None and r['why']=='SCOPE'
        r=get_only('REDIRECT_CERT_ERROR',valid,'/redirect-bad-cert',allowed=origins(valid,unknown));assert r['state']=='HTTP_RESPONSE' and r['http']==302 and r['end']=='ISSUER_VERIFY' and r['verify_code']==20 and r['error']=='CERT_REJECTED'
        r=one('WWW',valid,'/redirect-block')[0];assert r['tls']['v']=='PASS' and r['get']['v']=='UNVERIFIED'
        r=one('WWW',valid,'/redirect-bad-cert',allow=origins(valid,unknown))[0];assert r['tls']['v']=='PASS' and r['get']['v']=='FAIL' and r['get']['verify_code']==20
    check('ALLOWLIST_REDIRECT_BLOCK_AND_LATER_CERT_ERROR_SEPARATE_FROM_TLS',redirect_blocks)
    def body_spy():
        counters={'iterated':0,'closed':0,'requests':0}
        class BodyBomb(httpx.AsyncByteStream):
            async def __aiter__(self):
                counters['iterated']+=1;raise AssertionError('BODY_READ_FORBIDDEN');yield b''
            async def aclose(self):counters['closed']+=1
        def handle(request):
            counters['requests']+=1
            return httpx.Response(302 if counters['requests']==1 else 403,headers={'Location':'/next'} if counters['requests']==1 else {},stream=BodyBomb())
        r=get_only('INJECTED_BODY_BOMB',valid,transport=httpx.MockTransport(handle));assert r['http']==302 and r['last_http']==403 and counters=={'iterated':0,'closed':2,'requests':2}
        record('BODY_ITERATION_COUNTERS',counters)
    check('INJECTED_STREAM_BODY_ITERATOR_NEVER_CALLED_EVEN_REDIRECTS',body_spy)
    def proxy_error():
        r=get_only('LOCAL_PROXY_403',valid,proxy_port=proxy.server_address[1]);assert r['state']=='OTHER_FAILURE' and r['http'] is None and r['why']=='PROXY'
        assert ns['classify_exception'](wrap(synthetic(20),httpx.ProxyError))['state']=='OTHER_FAILURE'
    check('ACTUAL_LOCAL_PROXY_CONNECT_403_OTHER_FAILURE_NO_TARGET_HTTP',proxy_error)
    def dns():
        async def fail_dns(*args,**kwargs):raise socket.gaierror(socket.EAI_NONAME,'synthetic DNS')
        r=one('WWW',valid,connector=fail_dns)[0];assert r['tls']['state']=='OTHER_FAILURE' and r['tls']['why']=='DNS' and r['get']['state']=='HTTP_RESPONSE'
        class DNS(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):raise wrap(socket.gaierror(socket.EAI_NONAME,'synthetic DNS'))
        r=get_only('INJECTED_GET_DNS',valid,transport=DNS());assert r['state']=='OTHER_FAILURE' and r['why']=='DNS'
    check('INJECTED_DNS_BOTH_STAGES_NO_EXTERNAL_RESOLVER',dns)
    def tls_timeout():
        c=context();r=asyncio.run(ns['handshake']('localhost',stall.server_address[1],c));record('TLS_HANDSHAKE_TIMEOUT_8',r)
        assert r['state']=='OTHER_FAILURE' and r['why']=='TIMEOUT'
    check('ACTUAL_HANDSHAKE_TIMEOUT_8_SECONDS_OTHER_FAILURE',tls_timeout)
    def http_timeout():
        r=one('WWW',valid,'/header-timeout')[0];assert r['tls']['state']=='CONNECTED' and r['tls']['v']=='PASS' and r['get']['state']=='OTHER_FAILURE' and r['get']['why']=='TIMEOUT' and r['get']['v']=='UNVERIFIED'
    check('ACTUAL_HTTP_HEADERS_TIMEOUT_8_SECONDS_TLS_RESULT_RETAINED',http_timeout)
    def typed_attributes_only():
        class NoString(httpx.ConnectError):
            def __str__(self):raise AssertionError('str forbidden')
        assert ns['classify_exception'](NoString('CERTIFICATE_VERIFY_FAILED'))['state']=='OTHER_FAILURE'
        assert ns['classify_exception'](ssl.SSLError(1,'CERTIFICATE_VERIFY_FAILED'))['state']=='OTHER_FAILURE'
        for code in (2,19,20,10,62,18,None):
            r=ns['classify_exception'](wrap(synthetic(code,'bad\n\t\u2603 '+('x'*150))))
            assert r['state']=='CERT_REJECTED' and len(r['verify_message'])<=100 and all(32<=ord(c)<=126 for c in r['verify_message'])
        m=ns['safe_verify_message']('verify https://secret.invalid/token user:pass@proxy /private/path\n');assert '://' not in m and '@' not in m and '/private' not in m
        for code in (True,'20'):
            r=ns['classify_exception'](synthetic(code));assert r['verify_code'] is None and not r['issuer_reject']
    check('ACTUAL_EXCEPTION_TYPES_ONLY_ASCII_100_NO_STR_URLS_OR_PROXY_VALUES',typed_attributes_only)
    def chains():
        root=wrap(synthetic(20));root.__context__=root;assert ns['classify_exception'](root)['issuer_reject']
        mixed=synthetic(20);mixed.__context__=synthetic(10);assert not ns['classify_exception'](mixed)['issuer_reject']
        for _ in range(12):root=wrap(root)
        assert not ns['classify_exception'](root)['issuer_reject']
        assert ns['classify_exception'](wrap(synthetic(20),httpx.ReadTimeout))['state']=='OTHER_FAILURE'
    check('CAUSE_CONTEXT_CYCLES_LIMIT_AMBIGUOUS_CODES_TIMEOUT_PRECEDENCE',chains)
    def role_aggregates():
        def rows(baseline=False):
            result=[]
            for name,_,negative in ns['TARGETS']:
                state='CERT_REJECTED' if name=='NEGATIVE_2' or name=='NEGATIVE_1' and not baseline else 'CONNECTED'
                result.append({'id':name,'tls':{'state':state,'v':'PASS'},'get':{'state':'HTTP_RESPONSE' if state=='CONNECTED' else state,'v':'PASS'}})
            return result
        r=rows();s=ns['summarize'](r);assert s['r']=='TLS_OBS_PASS' and s['effect_evidence']==1 and s['go'] is False
        for stage in ('tls','get'):
            bad=rows();bad[3][stage]['v']='FAIL';assert ns['summarize'](bad)['r']=='FAIL' and ns['summarize'](bad)['effect_evidence']==0
            bad=rows();bad[0][stage]['v']='UNVERIFIED';assert ns['summarize'](bad)['r']=='UNVERIFIED'
        assert ns['summarize'](rows(True),True)['r']=='BASELINE_OBS_EXPECTED' and ns['summarize'](rows(True),True)['effect_evidence']==0
        assert ns['assess']('NEGATIVE_1','CERT_REJECTED',False)=='UNVERIFIED'
        assert ns['assess']('NEGATIVE_2','CERT_REJECTED',False)=='PASS'
        bad=rows();bad[0]['get']['close_unknown']=True;assert ns['summarize'](bad)['r']=='UNVERIFIED'
    check('ROLE_SPECIFIC_POST_BASELINE_AGGREGATES_NEGATIVE2_NEVER_EFFECT_EVIDENCE',role_aggregates)
    def complete_real_profiles():
        c=context();allowed=origins(valid,unknown,expired)
        ports=[valid,valid,valid,unknown,expired];paths=['/','/forbidden','/missing','/','/']
        targets=[(name,url(s,path),negative) for (name,_,negative),s,path in zip(ns['TARGETS'],ports,paths)]
        rows=asyncio.run(ns['probe_stages'](targets,allowed,fingerprints(c),factory(c)))
        assert rows[-1]['r']=='TLS_OBS_PASS' and rows[-1]['effect_evidence']==1;record('LOCAL_POST_PROFILE',rows[-1])
        ports=[valid,valid,valid,valid,expired]
        targets=[(name,url(s),negative) for (name,_,negative),s in zip(ns['TARGETS'],ports)]
        rows=asyncio.run(ns['probe_stages'](targets,allowed,fingerprints(c),factory(c),baseline=True))
        assert rows[-1]['r']=='BASELINE_OBS_EXPECTED' and rows[-1]['effect_evidence']==0;record('LOCAL_BASELINE_ROLE_PROFILE_ONLY',rows[-1])
        compact=ns['compact_observations'](rows);assert all('issuer_reject' not in r['tls'] and 'issuer_reject' not in r['get'] for r in compact[:-1])
        (WORK/'profile-output.private.frame.txt').write_bytes(ns['frame']([{'scope':'SYNTHETIC_LOCAL_BASELINE_PROFILE_NOT_OLD_BUNDLE'}]+compact))
    check('REAL_LOCAL_FIVE_TARGET_POST_AND_CORRECTED_BASELINE_PROFILES',complete_real_profiles)
    def internal_guards():
        ns['httpx_internals_gate']()
        old=dict(ns['HTTPX_INTERNAL_SHA']);ns['HTTPX_INTERNAL_SHA']['redirect']='0'*64
        try:
            try:ns['httpx_internals_gate']();raise AssertionError('changed internals accepted')
            except ns['Stop'] as e:assert e.why=='UNREVIEWED_HTTPX_INTERNALS'
        finally:ns['HTTPX_INTERNAL_SHA']=old
        async def run():
            c=context()
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(verify=c,trust_env=False)) as client:
                assert ns['httpx_context'](client,fingerprints(c)) is c
                try:ns['httpx_context'](client,set());raise AssertionError('CA mismatch accepted')
                except ns['Stop']:pass
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(verify=c,trust_env=False,proxy='http://127.0.0.1:1')) as client:
                try:ns['httpx_context'](client,fingerprints(c));raise AssertionError('proxy pool accepted')
                except ns['Stop']:pass
        asyncio.run(run())
    check('PINNED_HTTPX_HTTPCORE_CONTEXT_CA_ALPN_AND_PRIVATE_API_STOP_GUARDS',internal_guards)
    def baseline_and_post_gates():
        obs={'certifi_module':'2026.07.22','certifi_metadata':'2026.7.22','ca_sha':ns['BASELINE_CA_SHA'],'ca_n':121,'eff_n':121,'eff_eq':True,'verify_required':True,'hostname':True,'env_overrides':0,'runtime':True,'app_source':True}
        assert ns['baseline_observations_pass'](obs)
        for key,val in [('certifi_module','2026.10.23'),('ca_sha','0'*64),('ca_n',118),('eff_n',118),('eff_eq',False),('env_overrides',1),('hostname',False),('verify_required',False)]:
            bad=dict(obs);bad[key]=val;assert not ns['baseline_observations_pass'](bad)
        make=lambda:__import__('httpx._config',fromlist=['create_ssl_context']).create_ssl_context(trust_env=False)
        assert ns['g4_env'](PROJECT,environ={},context_factory=make)[-1]['r']=='ENV_OBS_PASS'
        assert ns['baseline_gate'](PROJECT,environ={},context_factory=make)[-1]['r']=='STOP_BASELINE_ENV'
    check('ACTUAL_POST_GATE_AND_BASELINE_PREDICATE_ONLY_OLD_BUNDLE_UNAVAILABLE',baseline_and_post_gates)
    def env_stops():
        saved=ns['os']
        try:
            for name in ns['ENV_NAMES']:
                ns['os']=types.SimpleNamespace(environ={name:''})
                for baseline in (False,True):
                    r=ns['safe_tls_mode'](baseline);assert r==[{'r':'STOP','why':'SSL_PROXY_ENV_PRESENT','go':False}]
            for environ in ({'SSLKEYLOGFILE':''},{'HTTP_TIMEOUT_SECONDS':'7'},{'HTTP_TIMEOUT_SECONDS':'NaN'}):
                ns['os']=types.SimpleNamespace(environ=environ);assert ns['safe_tls_mode']()[0]['r']=='STOP'
        finally:ns['os']=saved
    check('ALL_14_ENV_NAMES_KEYLOG_TIMEOUT_GATES_STOP_NO_COMMUNICATION',env_stops)
    def fixed_scope_and_commands():
        assert [u for _,u,_ in ns['TARGETS']]==['https://www.boatrace.jp/','https://boatrace.jp/','https://boatraceopenapi.github.io/','https://dv-g3b-emudhra.we-have-a-problem.com/','https://dv-g3b-aaa-emudhra.we-have-a-problem.com/']
        runpy.run_path(str(V/'tests/verify-commands.py'))['verify']()
        verify=runpy.run_path(str(E/'tests/verify-output.py'))['verify']
        for name in ('G4_TLS_v003','G4_baseline_v003'):
            b=(V/('commands/'+name+'.candidate.txt')).read_bytes();command=b.decode('ascii');assert '\n' not in command and not b.endswith(b'\n')
            for cut in (1,10,100,len(b)//2,len(b)-50,len(b)-1):assert subprocess.run(['bash','-n','-c',command[:cut]],capture_output=True).returncode!=0
            env=dict(os.environ);env['PATH']=str(Path(sys.executable).parent)+os.pathsep+env.get('PATH','');env['HTTP_PROXY']=''
            result=subprocess.run(['bash','-c',command],cwd=PROJECT,env=env,capture_output=True);assert verify(result.stdout) and b'SSL_PROXY_ENV_PRESENT' in result.stdout and b'"go":false' in result.stdout and not result.stderr
            (WORK/(name+'.gate-stop.frame.txt')).write_bytes(result.stdout)
    check('EXACT_HQ12_URLS_PARAMETERS_ASCII_FRAMES_TRUNCATION_AND_REGENERATION',fixed_scope_and_commands)
    summary={'cases':len(cases),'classification_and_stream_tests':'PASS','python':sys.version.split()[0],'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'production_openssl_reported_by_HQ13':'OpenSSL 3.0.20','openssl_3_0_20_compatibility':'UNVERIFIED_NOT_AVAILABLE','actual_old_bundle_gate':'UNVERIFIED_NOT_AVAILABLE','external_targets':'NOT_RUN','render':'NOT_RUN','go':False}
    print('SUMMARY '+json.dumps(summary,sort_keys=True),flush=True);print('EXIT_CODE 0',flush=True)
    (WORK/'summary.raw.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    (WORK/'observations.raw.json').write_text(json.dumps(observed,indent=2,sort_keys=True)+'\n')
finally:
    for s,t in servers:s.shutdown();s.server_close();t.join(timeout=2)
