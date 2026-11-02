TARGETS=[("WWW","https://www.boatrace.jp/",False),("BARE","https://boatrace.jp/",False),("FALLBACK","https://boatraceopenapi.github.io/",False),("NEGATIVE_1","https://dv-g3b-emudhra.we-have-a-problem.com/",True),("NEGATIVE_2","https://dv-g3b-aaa-emudhra.we-have-a-problem.com/",True)]
ISSUER_CODES=frozenset((2,19,20))
BAD_ROOTS={"125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f","86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b","bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3"}
HTTPX_INTERNAL_SHA={"redirect":"88dba22b429959500bedfc9a0aa28eef978751a684c8c1958b02db97089c2c81","aread":"b6908ee9b52c8ec693b77caa1f53a759ff6c7a4375fce673b9fe49ebca89ba58","aclose":"f5682caf50a173573be59bb288fd61440a72ccaa5cd2a9b27f1284267fd7821d","stream":"d716d0c5a11fd165a6e18adbd1ea019f688e62feead0cc98f84d5aad989db00d"}

class ScopeBlocked(Exception):pass

def exception_nodes(exc,limit=16,max_depth=8):
    queue=[(exc,0)];seen=set();nodes=[];limited=False
    while queue:
        current,depth=queue.pop(0)
        if current is None or id(current) in seen:continue
        if depth>max_depth or len(nodes)>=limit:limited=True;continue
        seen.add(id(current));nodes.append(current)
        queue.extend(((current.__cause__,depth+1),(current.__context__,depth+1)))
    return nodes,limited

def safe_verify_message(value):
    if not isinstance(value,str):return None
    value="".join(c if 32<=ord(c)<=126 else "?" for c in value)
    value=re.sub(r"\S*(?:://|@)\S*","[REDACTED]",value)
    value=re.sub(r"(?<!\w)/\S+","[REDACTED]",value)
    return value[:100]

def classify_exception(exc):
    import httpx,socket
    nodes,limited=exception_nodes(exc)
    certs=[e for e in nodes if isinstance(e,ssl.SSLCertVerificationError)]
    codes=[getattr(e,"verify_code",None) for e in certs]
    codes=[c if type(c) is int else None for c in codes]
    code=codes[0] if codes else None
    message=safe_verify_message(getattr(certs[0],"verify_message",None)) if certs else None
    row={"state":"OTHER_FAILURE","verify_code":code,"verify_message":message,"issuer_reject":False}
    if any(isinstance(e,httpx.ProxyError) for e in nodes):why="PROXY"
    elif any(isinstance(e,(httpx.TimeoutException,TimeoutError)) for e in nodes):why="TIMEOUT"
    elif any(isinstance(e,socket.gaierror) for e in nodes):why="DNS"
    elif any(isinstance(e,ScopeBlocked) for e in nodes):why="SCOPE"
    elif certs:
        row["state"]="CERT_REJECTED"
        row["issuer_reject"]=not limited and len(set(codes))==1 and code in ISSUER_CODES
        why="ISSUER_VERIFY" if row["issuer_reject"] else "OTHER_CERT_VERIFY"
    else:why="CHAIN_LIMIT" if limited else "TRANSPORT_OTHER"
    row["why"]=why
    return row

def assess(name,state,issuer_reject=False,baseline=False):
    if name in ("WWW","BARE","FALLBACK"):
        return "PASS" if state=="CONNECTED" else "FAIL" if state=="CERT_REJECTED" else "UNVERIFIED"
    if name=="NEGATIVE_1":
        if baseline:return "PASS" if state=="CONNECTED" else "UNVERIFIED"
        return "PASS" if state=="CERT_REJECTED" and issuer_reject else "FAIL" if state=="CONNECTED" else "UNVERIFIED"
    if name=="NEGATIVE_2":
        return "PASS" if state=="CERT_REJECTED" else "FAIL" if state=="CONNECTED" else "UNVERIFIED"
    return "UNVERIFIED"

def httpx_internals_gate():
    import httpx,httpcore,inspect
    from httpcore._async.connection import AsyncHTTPConnection
    if httpx.__version__!="0.28.1" or httpcore.__version__!="1.0.9":raise Stop("HTTP_STACK_VERSION")
    methods={"redirect":httpx.AsyncClient._send_handling_redirects,"aread":httpx.Response.aread,"aclose":httpx.Response.aclose,"stream":httpx.AsyncClient.stream}
    if any(hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()!=HTTPX_INTERNAL_SHA[name] for name,fn in methods.items()):raise Stop("UNREVIEWED_HTTPX_INTERNALS")
    if hashlib.sha256(inspect.getsource(AsyncHTTPConnection._connect).encode("utf-8")).hexdigest()!="2f78c5464ee7554310f9f88fb7db527c0c1f1bb72a9a53adb6c18cf760ddfe9e":raise Stop("UNREVIEWED_HTTPCORE_ALPN")

def httpx_context(client,expected_fingerprints):
    import httpx,httpcore
    transport=getattr(client,"_transport",None);pool=getattr(transport,"_pool",None)
    context=getattr(pool,"_ssl_context",None)
    if type(transport) is not httpx.AsyncHTTPTransport or type(pool) is not httpcore.AsyncConnectionPool:raise Stop("HTTPX_CONTEXT_UNKNOWN")
    if not isinstance(context,ssl.SSLContext) or context.verify_mode!=ssl.CERT_REQUIRED or not context.check_hostname:raise Stop("HTTPX_VERIFY_DISABLED")
    if any(v is not None for v in getattr(client,"_mounts",{}).values()):raise Stop("HTTPX_MOUNT_UNKNOWN")
    if getattr(pool,"_http2",None) is not False or getattr(pool,"_http1",None) is not True:raise Stop("HTTPX_PROTOCOL_UNKNOWN")
    effective={hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
    if effective!=expected_fingerprints:raise Stop("HTTPX_EFFECTIVE_CA_DIFFERS")
    # Match the HTTP/1.1 ALPN preparation in pinned httpcore._connect before the
    # handshake-only phase. This is the SAME context later used by that client.
    context.set_alpn_protocols(["http/1.1"])
    return context

def verified_anchor(ssl_object,context):
    try:
        chain=ssl_object.get_verified_chain()
        if not chain or not isinstance(chain[-1],bytes):return None,None
        fingerprint=hashlib.sha256(chain[-1]).hexdigest()
        trusted={hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
        if fingerprint not in trusted:return None,None
        return fingerprint,fingerprint in BAD_ROOTS
    except Exception:return None,None

async def handshake(host,port,context,connector=None):
    import asyncio
    writer=None
    row={"state":"OTHER_FAILURE","verify_code":None,"verify_message":None,"issuer_reject":False,"anchor_sha256":None,"bad_root":None}
    try:
        reader,writer=await asyncio.wait_for((connector or asyncio.open_connection)(host,port,ssl=context,server_hostname=host,ssl_handshake_timeout=8.0),timeout=8.0)
        ssl_object=writer.get_extra_info("ssl_object")
        if ssl_object is None or ssl_object.context is not context:raise Stop("HANDSHAKE_CONTEXT_UNKNOWN")
        row["state"]="CONNECTED"
        row["anchor_sha256"],row["bad_root"]=verified_anchor(ssl_object,context)
        # No reader.read(), writer.write(), HTTP request or application data.
    except Stop:raise
    except Exception as exc:row.update(classify_exception(exc))
    finally:
        if writer is not None:
            try:
                writer.close();await asyncio.wait_for(writer.wait_closed(),timeout=1.0)
            except Exception:row["cleanup_unknown"]=True
    return row

def summarize(rows,baseline=False):
    expected={name for name,_,_ in TARGETS}
    complete=len(rows)==5 and {r["id"] for r in rows}==expected
    def verdict(stage):
        values=[r[stage]["v"] for r in rows]
        if baseline:return "BASELINE_OBS_EXPECTED" if complete and all(v=="PASS" for v in values) else "UNVERIFIED"
        return "FAIL" if "FAIL" in values else "PASS" if complete and all(v=="PASS" for v in values) else "UNVERIFIED"
    tls=verdict("tls");get=verdict("get")
    uncertain=any(r["tls"].get("cleanup_unknown") or r["get"].get("close_unknown") for r in rows)
    if baseline:result="BASELINE_OBS_EXPECTED" if tls==get=="BASELINE_OBS_EXPECTED" and not uncertain else "UNVERIFIED"
    else:result="FAIL" if "FAIL" in (tls,get) else "TLS_OBS_PASS" if tls==get=="PASS" and not uncertain else "UNVERIFIED"
    evidence=0 if baseline else sum(r["id"]=="NEGATIVE_1" and r["tls"]["v"]==r["get"]["v"]=="PASS" for r in rows)
    return {"r":result,"tls":tls,"get":get,"effect_evidence":evidence,"mode":"BASELINE" if baseline else "POST","go":False}

def headers_only_hooks(allowed_origins):
    current={"http":None,"last_http":None,"responses":0,"close_unknown":False}
    def in_scope(url):return url.scheme=="https" and not url.username and not url.password and (url.host,url.port or 443) in allowed_origins
    async def request_gate(request):
        if not in_scope(request.url):raise ScopeBlocked()
    async def headers_only(response):
        if not in_scope(response.request.url):raise ScopeBlocked()
        if current["http"] is None:current["http"]=response.status_code
        current["last_http"]=response.status_code;current["responses"]+=1
        # HTTPX 0.28.1 normally drains redirect bodies even with stream=True.
        # Close without iterating, then supply an empty local cache so its pinned
        # redirect aread() takes the no-I/O fast path. Never modify dependencies.
        try:await response.aclose()
        except Exception:
            current["close_unknown"]=True;raise
        response._content=b""
    return current,{"request":[request_gate],"response":[headers_only]}

async def get_observation(client,url,current):
    current.update(http=None,last_http=None,responses=0,close_unknown=False)
    get={"state":"OTHER_FAILURE","http":None,"last_http":None,"verify_code":None,"verify_message":None,"issuer_reject":False,"end":"COMPLETE"}
    try:
        async with client.stream("GET",url) as response:
            status=response.status_code
            if not response.is_closed or response.content!=b"":raise Stop("BODY_GUARD_UNKNOWN")
            if current["http"] is None:raise Stop("RESPONSE_HOOK_MISSING")
    except Stop:raise
    except Exception as exc:
        error=classify_exception(exc);get.update(error);get["end"]=error["why"];get["error"]=error["state"]
    if current["http"] is not None:
        # Preserve a later-hop verification exception's actual attributes while
        # retaining the independently observed first HTTP status.
        get.update(state="HTTP_RESPONSE",http=current["http"],last_http=current["last_http"])
    if current["close_unknown"]:get["close_unknown"]=True
    return get

def assess_get(name,get,baseline=False):
    # Any response already proves acceptance of a negative target. A later-hop
    # error cannot mask that post-change failure (or the NEGATIVE_2 control).
    if get["http"] is not None and (name=="NEGATIVE_2" or name=="NEGATIVE_1" and not baseline):return "FAIL"
    state=get.get("error") or ("CONNECTED" if get["state"]=="HTTP_RESPONSE" else get["state"])
    return assess(name,state,get["issuer_reject"],baseline)

async def probe_stages(targets,allowed_origins,expected_fingerprints,client_factory=None,connector=None,baseline=False):
    import httpx
    current,hooks=headers_only_hooks(allowed_origins)
    kwargs={"timeout":8.0,"verify":True,"trust_env":True,"follow_redirects":True,
            "event_hooks":hooks}
    rows=[]
    async with (client_factory or httpx.AsyncClient)(**kwargs) as client:
        context=httpx_context(client,expected_fingerprints)
        for name,url,_ in targets:
            parsed=httpx.URL(url)
            if parsed.scheme!="https" or parsed.username or parsed.password or (parsed.host,parsed.port or 443) not in allowed_origins:raise Stop("TARGET_SCOPE")
            tls=await handshake(parsed.host,parsed.port or 443,context,connector)
            tls["v"]=assess(name,tls["state"],tls["issuer_reject"],baseline)
            rows.append({"id":name,"tls":tls})
        # Independent HQ12 GET phase. Handshake outcomes do not skip/retry GETs.
        for row,(_,url,_) in zip(rows,targets):
            get=await get_observation(client,url,current)
            get["v"]=assess_get(row["id"],get,baseline)
            row["get"]=get
    return rows+[summarize(rows,baseline)]

def compact_observations(rows):
    result=[]
    for row in rows:
        if "id" not in row:result.append(row);continue
        clean={"id":row["id"]}
        for phase in ("tls","get"):
            part=dict(row[phase]);part.pop("issuer_reject",None)
            if part.get("state")=="CERT_REJECTED":part.pop("why",None)
            if part.get("end")=="COMPLETE":part.pop("end",None)
            if phase=="get" and part.get("last_http")==part.get("http"):part.pop("last_http",None)
            clean[phase]=part
        result.append(clean)
    return result

def checked_preflight(baseline=False):
    try:value=float(os.environ.get("HTTP_TIMEOUT_SECONDS","8"))
    except ValueError:raise Stop("APP_TIMEOUT_UNKNOWN")
    if value!=8.0:raise Stop("APP_TIMEOUT_DIFFERS_FROM_HQ12")
    if "SSLKEYLOGFILE" in os.environ:raise Stop("KEYLOG_ENV_PRESENT")
    env_count=sum(name in os.environ for name in ENV_NAMES)
    if env_count:raise Stop("SSL_PROXY_ENV_PRESENT")
    gate=baseline_gate() if baseline else g4_env()
    if gate[-1]["r"]!=("BASELINE_ENV_PASS" if baseline else "ENV_OBS_PASS"):raise Stop("BASELINE_PREFLIGHT" if baseline else "POST_PREFLIGHT")
    httpx_internals_gate()
    return gate

def run_tls_mode(baseline=False):
    import asyncio,certifi,httpx
    gate=checked_preflight(baseline)
    data=Path(certifi.where()).read_bytes()
    pems=re.findall(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",data,re.S)
    expected={hashlib.sha256(ssl.PEM_cert_to_DER_cert(p.decode())).hexdigest() for p in pems}
    origins={(httpx.URL(url).host,443) for _,url,_ in TARGETS}
    global _network
    _network=True
    observed=asyncio.run(probe_stages(TARGETS,origins,expected,baseline=baseline))
    ca=gate[0] if baseline else gate[1]
    return [{"gate":"BASELINE" if baseline else "POST","ca_sha":ca["ca_sha"],"ca_n":ca["ca_n"],"eff_n":ca["eff_n"],"eff_eq":ca["eff_eq"]}]+compact_observations(observed)

def safe_tls_mode(baseline=False):
    try:return run_tls_mode(baseline)
    except Stop as exc:return [{"r":"STOP","why":exc.why,"go":False}]
    except Exception:return [{"r":"STOP","why":"INTERNAL_UNKNOWN","go":False}]

def g4_tls_v003():return safe_tls_mode(False)
def g4_baseline_v003():return safe_tls_mode(True)
