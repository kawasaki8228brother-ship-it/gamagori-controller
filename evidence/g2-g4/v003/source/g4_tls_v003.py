TARGETS=[("WWW","https://www.boatrace.jp/",False),("BARE","https://boatrace.jp/",False),("FALLBACK","https://boatraceopenapi.github.io/",False),("NEGATIVE_1","https://dv-g3b-emudhra.we-have-a-problem.com/",True),("NEGATIVE_2","https://dv-g3b-aaa-emudhra.we-have-a-problem.com/",True)]
ISSUER_CODES=frozenset((2,19,20))

class ScopeBlocked(Exception): pass

def exception_nodes(exc,limit=16,max_depth=8):
    queue=[(exc,0)];seen=set();nodes=[];limited=False
    while queue:
        current,depth=queue.pop(0)
        if current is None or id(current) in seen:continue
        if depth>max_depth or len(nodes)>=limit:
            limited=True;continue
        seen.add(id(current));nodes.append(current)
        queue.extend(((current.__cause__,depth+1),(current.__context__,depth+1)))
    return nodes,limited

def safe_verify_message(value):
    if not isinstance(value,str):return None
    value="".join(c if 32<=ord(c)<=126 else "?" for c in value)
    # Only the real verify_message attribute is accepted. Suppress URL/path-like
    # tokens even if an unusual TLS provider puts them in that attribute.
    value=re.sub(r"\S*(?:://|@)\S*","[REDACTED]",value)
    value=re.sub(r"(?<!\w)/\S+","[REDACTED]",value)
    return value[:100]

def classify_exception(exc):
    import httpx,socket
    nodes,limited=exception_nodes(exc)
    certificates=[e for e in nodes if isinstance(e,ssl.SSLCertVerificationError)]
    code=None;message=None;codes=[]
    for certificate in certificates:
        candidate=getattr(certificate,"verify_code",None)
        codes.append(candidate if type(candidate) is int else None)
    if certificates:
        code=codes[0]
        message=safe_verify_message(getattr(certificates[0],"verify_message",None))
    if any(isinstance(e,httpx.ProxyError) for e in nodes):why="PROXY"
    elif any(isinstance(e,httpx.TimeoutException) for e in nodes):why="TIMEOUT"
    elif any(isinstance(e,socket.gaierror) for e in nodes):why="DNS"
    elif any(isinstance(e,ScopeBlocked) for e in nodes):why="SCOPE"
    elif limited:why="CHAIN_LIMIT"
    elif certificates and len(set(codes))!=1:why="VERIFY_AMBIGUOUS"
    elif certificates and code in ISSUER_CODES:
        return "CERT_REJECTED",code,message,"ISSUER_VERIFY"
    elif certificates:why="VERIFY_OTHER"
    else:why="TRANSPORT_OTHER"
    return "OTHER_FAILURE",code,message,why

def tls_summary(rows,baseline=False):
    expected={name:negative for name,_,negative in TARGETS}
    complete=len(rows)==5 and {r["id"] for r in rows}==set(expected)
    if baseline:
        failed=any(expected.get(r["id"]) is False and r["tls"]=="CERT_REJECTED" for r in rows)
        result="FAIL" if failed else "BASELINE_OBS_EXPECTED" if complete and all(r["tls"]=="CONNECTED" for r in rows) else "UNVERIFIED"
    else:
        failed=any((expected.get(r["id"]) is True and r["tls"]=="CONNECTED") or (expected.get(r["id"]) is False and r["tls"]=="CERT_REJECTED") for r in rows)
        passed=complete and all((r["tls"]=="CERT_REJECTED" and r["verify_code"] in ISSUER_CODES) if expected[r["id"]] else r["tls"]=="CONNECTED" for r in rows)
        result="FAIL" if failed else "TLS_OBS_PASS" if passed else "UNVERIFIED"
    return {"r":result,"mode":"BASELINE" if baseline else "POST","go":False}

async def probe_targets(targets,allowed_origins,client_factory=None,baseline=False):
    import httpx
    current={"http":None}
    def in_scope(url):
        return url.scheme=="https" and not url.username and not url.password and (url.host,url.port or 443) in allowed_origins
    async def gate(request):
        if not in_scope(request.url):raise ScopeBlocked()
    async def observe(response):
        if not in_scope(response.request.url):raise ScopeBlocked()
        if current["http"] is None:current["http"]=response.status_code
    # Preserve HQ12's URLs, order, four communication options and single attempt.
    # The response hook remembers the FIRST target response before any redirect.
    kwargs={"timeout":8.0,"verify":True,"trust_env":True,"follow_redirects":True,
            "event_hooks":{"request":[gate],"response":[observe]}}
    rows=[]
    async with (client_factory or httpx.AsyncClient)(**kwargs) as client:
        for name,url,negative in targets:
            current["http"]=None
            row={"id":name,"tls":"OTHER_FAILURE","http":None,"verify_code":None,"verify_message":None}
            try:
                await client.get(url)
                if current["http"] is None:row["why"]="NO_RESPONSE_OBSERVED"
            except Exception as exc:
                if current["http"] is None:
                    row["tls"],row["verify_code"],row["verify_message"],row["why"]=classify_exception(exc)
            if current["http"] is not None:
                row["tls"]="CONNECTED";row["http"]=current["http"]
            rows.append(row)
    return rows+[tls_summary(rows,baseline)]

def checked_app_timeout():
    try:value=float(os.environ.get("HTTP_TIMEOUT_SECONDS","8"))
    except ValueError:raise Stop("APP_TIMEOUT_UNKNOWN")
    if value!=8.0:raise Stop("APP_TIMEOUT_DIFFERS_FROM_HQ12")
    if "SSLKEYLOGFILE" in os.environ:raise Stop("KEYLOG_ENV_PRESENT")

def run_tls_mode(baseline=False):
    import asyncio
    checked_app_timeout()
    env_count=sum(name in os.environ for name in ENV_NAMES)
    if env_count:return [{"r":"STOP","why":"SSL_PROXY_ENV_PRESENT","env_overrides":env_count,"go":False}]
    gate=baseline_gate() if baseline else g4_env()
    expected="BASELINE_ENV_PASS" if baseline else "ENV_OBS_PASS"
    if gate[-1]["r"]!=expected:return gate+[{"r":"STOP","why":"BASELINE_PREFLIGHT" if baseline else "POST_PREFLIGHT","go":False}]
    from urllib.parse import urlsplit
    origins={(urlsplit(url).hostname,443) for _,url,_ in TARGETS}
    global _network
    _network=True
    observed=asyncio.run(probe_targets(TARGETS,origins,baseline=baseline))
    ca=gate[0] if baseline else gate[1]
    return [{"gate":expected,"ca_sha":ca["ca_sha"],"ca_n":ca["ca_n"],
             "eff_n":ca["eff_n"],"eff_eq":ca["eff_eq"],"env_overrides":0}]+observed

def g4_tls_v003():return run_tls_mode(False)
def g4_baseline_v003():return run_tls_mode(True)
