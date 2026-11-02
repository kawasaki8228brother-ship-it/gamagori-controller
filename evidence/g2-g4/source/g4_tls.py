TARGETS=[("WWW","https://www.boatrace.jp/",False),("BARE","https://boatrace.jp/",False),("FALLBACK","https://boatraceopenapi.github.io/",False),("NEGATIVE_1","https://dv-g3b-emudhra.we-have-a-problem.com/",True),("NEGATIVE_2","https://dv-g3b-aaa-emudhra.we-have-a-problem.com/",True)]

class ScopeBlocked(Exception): pass

def cert_error(exc):
    # HQ12 original certificate-error recognition; classification adds the
    # requested ProxyError/HTTP-403 exclusion before using this helper.
    for _ in range(10):
        if exc is None:break
        if isinstance(exc,ssl.SSLCertVerificationError):return True
        s=str(exc).upper()
        if "CERTIFICATE_VERIFY_FAILED" in s or "CERTIFICATE VERIFY FAILED" in s:return True
        exc=exc.__cause__ or exc.__context__
    return False

def chain_has(exc,kind):
    for _ in range(10):
        if exc is None:return False
        if isinstance(exc,kind):return True
        exc=exc.__cause__ or exc.__context__
    return False

async def probe_targets(targets,allowed_origins,client_factory=None):
    import httpx,socket
    async def gate(request):
        u=request.url
        if u.scheme!="https" or u.username or u.password or (u.host,u.port or 443) not in allowed_origins:raise ScopeBlocked()
    kwargs={"timeout":8.0,"verify":True,"trust_env":True,"follow_redirects":True}
    # Only a pre-send allowlist hook is added; HQ12 four communication options
    # and the two negative URLs remain unchanged. No proxy/CA bypass or retry.
    kwargs["event_hooks"]={"request":[gate]}
    rows=[]
    async with (client_factory or httpx.AsyncClient)(**kwargs) as client:
        for name,url,negative in targets:
            try:
                response=await client.get(url)
                if response.status_code>=400:
                    row={"id":name,"c":"OTHER_FAILURE","why":"HTTP_"+str(response.status_code)}
                else:row={"id":name,"c":"CONNECTED","http":response.status_code}
            except httpx.TransportError as exc:
                if chain_has(exc,httpx.ProxyError):row={"id":name,"c":"OTHER_FAILURE","why":"ProxyError"}
                elif chain_has(exc,httpx.TimeoutException):row={"id":name,"c":"OTHER_FAILURE","why":"Timeout"}
                elif chain_has(exc,socket.gaierror):row={"id":name,"c":"OTHER_FAILURE","why":"DNS"}
                elif cert_error(exc):row={"id":name,"c":"CERT_REJECTED"}
                else:row={"id":name,"c":"OTHER_FAILURE","why":type(exc).__name__}
            except Exception as exc:
                row={"id":name,"c":"OTHER_FAILURE","why":type(exc).__name__}
            row["expect"]="REJECT" if negative else "CONNECT"
            rows.append(row)
    known_fail=any(r["c"]!="OTHER_FAILURE" and ((r["c"]=="CERT_REJECTED")!=(r["expect"]=="REJECT")) for r in rows)
    unknown=any(r["c"]=="OTHER_FAILURE" for r in rows)
    rows.append({"r":"FAIL" if known_fail else "UNVERIFIED" if unknown else "TLS_OBS_PASS","go":False})
    return rows

def g4_tls():
    import asyncio
    # Reject environmental overrides before any external request. Keep HQ12's
    # timeout=8.0 exactly; a differing app timeout requires new scoped review.
    if g4_env()[-1]["r"]!="ENV_OBS_PASS":raise Stop("ENV_PREFLIGHT")
    try:timeout=float(os.environ.get("HTTP_TIMEOUT_SECONDS","8"))
    except ValueError:raise Stop("APP_TIMEOUT_UNKNOWN")
    if timeout!=8.0:raise Stop("APP_TIMEOUT_DIFFERS_FROM_HQ12")
    global _network
    _network=True
    from urllib.parse import urlsplit
    origins={(urlsplit(url).hostname,443) for _,url,_ in TARGETS}
    return asyncio.run(probe_targets(TARGETS,origins))

if __name__=="__main__":entry("G4_TLS",g4_tls)
