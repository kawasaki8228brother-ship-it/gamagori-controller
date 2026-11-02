import sys, os, ssl, json, hashlib, datetime as dt, time, sqlite3, stat, io, contextlib, re
from pathlib import Path

AUDITOR_SHA = "354940e9a77d2eaf86feaa1c50089db4a0e410cc5f2fdafd6598d66367566b94"
OFFICIAL_SHA = "8598ef5937c5b944d87b6cfa8c29dea10dc6f09781cb73a0c55521c5f6a29373"
REQUIREMENTS_SHA = "dba91fc609884c39b70c1660151e959779d86613fe0ce13c61626506123a2dc7"
CA_SHA = "2ef52ad56b4803e264045c915e55c236cbfa045b84b81efefc218a19eb44bd2b"
HEAD = "97640c8c307fed8eaa19f2557f5057ccade18da1"
STATES = "PENDING DATA_WAIT CLOSING_WINDOW FREEZE_ZONE SAFE_STOP C_EVENT_DONE REOPENED TERMINAL".split()
ENV_NAMES = "SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY".split()
ENV_NAMES += [x.lower() for x in ENV_NAMES]
_read_sqlite, _write_sqlite = set(), set()
_write_target = None
_network = False

class Stop(Exception):
    def __init__(self, why): self.why = why

def audit_guard(event, args):
    blocked = event.startswith("socket.") and not _network
    blocked = blocked or event in {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.spawn", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate", "os.utime"}
    if event == "sqlite3.connect":
        blocked = str(args[0]) not in _read_sqlite | _write_sqlite
    if event == "open":
        path, mode, flags = args
        write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write:
            blocked = _write_target is None or not isinstance(path, (str, bytes, os.PathLike)) or Path(os.fsdecode(path)).absolute() != _write_target
        if isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).name.startswith(".env"):
            blocked = True
    if blocked: raise PermissionError("G_SIDE_EFFECT_BLOCKED")

def frame(rows):
    body = b"".join((json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode("ascii") for row in rows)
    end = "END CERTIFI_AUDIT_V002 lines="+str(len(rows))+" bytes="+str(len(body))+" sha256="+hashlib.sha256(body).hexdigest()+"\n"
    return b"BEGIN CERTIFI_AUDIT_V002\n"+body+end.encode("ascii")

def metadata(kind):
    return {"g":kind,"py":sys.version.split()[0],"ssl":ssl.OPENSSL_VERSION,"sq":sqlite3.sqlite_version}

def entry(kind, fn):
    sys.dont_write_bytecode = True
    sys.addaudithook(audit_guard)
    rows = [metadata(kind)]
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = fn()
        rows.extend(result)
    except Stop as exc:
        rows.append({"r":"STOP","why":exc.why})
    except Exception as exc:
        rows.append({"r":"STOP","e":type(exc).__name__})
    sys.stdout.buffer.write(frame(rows));sys.stdout.buffer.flush()

def now_jst(): return dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))

def checked_source(root):
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir(): raise Stop("DATA_ROOT")
    source = root / "gamagori_shadow.db"
    try: info = source.lstat()
    except FileNotFoundError: raise Stop("DB_MISSING")
    if not stat.S_ISREG(info.st_mode) or info.st_size < 32: raise Stop("DB_FILE")
    with source.open("rb") as stream: header = stream.read(32)
    if header[:16] != b"SQLite format 3\0": raise Stop("DB_HEADER")
    wal_mode = header[18:20] == b"\x02\x02"
    if not wal_mode and header[18:20] != b"\x01\x01": raise Stop("JOURNAL_UNKNOWN")
    sizes = {"db":info.st_size,"wal":0,"shm":0}
    for name in ("wal","shm"):
        sidecar=Path(str(source)+"-"+name)
        if sidecar.exists():
            s=sidecar.lstat()
            if not stat.S_ISREG(s.st_mode): raise Stop("SIDECAR_FILE")
            sizes[name]=s.st_size
        elif wal_mode: raise Stop("WAL_SIDECAR_MISSING")
    return source, sizes, wal_mode

def ro_connect(path):
    uri=Path(path).resolve().as_uri()+"?mode=ro"
    _read_sqlite.add(uri)
    connection=sqlite3.connect(uri,uri=True,timeout=2.5,isolation_level=None)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA busy_timeout=2500")
    return connection

def deadline_progress(connection, deadline):
    connection.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)

def integrity(connection):
    if connection.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]: raise Stop("INTEGRITY")

PINS = "Pygments==2.21.0 annotated-types==0.8.0 anyio==4.15.1 beautifulsoup4==4.14.3 certifi==2026.10.23 h11==0.16.0 httpcore==1.0.9 httpx==0.28.1 idna==3.20 iniconfig==2.3.0 packaging==26.3 pluggy==1.6.0 pydantic==2.13.4 pydantic_core==2.46.4 pytest-asyncio==1.3.0 pytest==9.0.2 soupsieve==2.9.2 typing-inspection==0.4.4 typing_extensions==4.16.0".split()
BAD_ROOTS={"125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f","86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b","bc4d809b15189d78db3e1d8cf4f9726a795da1643ca5f1358e1ddb0edc0d7eb3"}

def g4_env(project=None,environ=None,context_factory=None,distributions=None):
    import re,certifi,httpx
    from importlib.metadata import distributions as all_distributions
    from httpx._config import create_ssl_context
    project=Path.cwd() if project is None else Path(project)
    environ=os.environ if environ is None else environ
    normalize=lambda s:re.sub(r"[-_.]+","-",s).lower()
    expected={normalize(p.split("==")[0]):p.split("==")[1] for p in PINS}
    found={};duplicates=0
    for dist in (all_distributions() if distributions is None else distributions):
        name=normalize(dist.metadata["Name"])
        if name in found:duplicates+=1
        found[name]=dist.version
    pip=found.pop("pip",None)
    dep_bad=sum(found.get(k)!=v for k,v in expected.items())+len(set(found)-set(expected))+duplicates
    env_present=[name for name in ENV_NAMES if name in environ]
    req_ok=hashlib.sha256((project/"requirements.txt").read_bytes()).hexdigest()==REQUIREMENTS_SHA
    official_ok=hashlib.sha256((project/"official.py").read_bytes()).hexdigest()==OFFICIAL_SHA
    data=Path(certifi.where()).read_bytes()
    pems=re.findall(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",data,re.S)
    bundle_fps={hashlib.sha256(ssl.PEM_cert_to_DER_cert(p.decode())).hexdigest() for p in pems}
    context=(context_factory or create_ssl_context)()
    effective={hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
    ca_ok=certifi.__version__=="2026.10.23" and hashlib.sha256(data).hexdigest()==CA_SHA and len(pems)==118 and len(bundle_fps)==118
    effective_ok=context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname and effective==bundle_fps and not(BAD_ROOTS&effective)
    runtime_ok=sys.version_info[:3]==(3,14,3) and httpx.__version__=="0.28.1"
    passed=not dep_bad and len(found)==19 and pip is not None and not env_present and req_ok and official_ok and ca_ok and effective_ok and runtime_ok
    return [{"deps":len(found),"bad":dep_bad,"pip":pip is not None,"env_overrides":len(env_present),"req":req_ok,"app_source":official_ok},{"ca_n":len(pems),"ca_sha":hashlib.sha256(data).hexdigest(),"eff_n":len(effective),"eff_eq":effective_ok},{"r":"ENV_OBS_PASS" if passed else "STOP_ENV","runtime":runtime_ok,"go":False}]

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

def combined_verdict(row,baseline=False):
    tls,get=row["tls"],row["get"]
    if row["id"] in ("WWW","BARE","FALLBACK"):
        if tls["state"]=="CERT_REJECTED" or get["state"]=="CERT_REJECTED" or get.get("error")=="CERT_REJECTED":return "FAIL"
        return "PASS" if tls["state"]=="CONNECTED" else "UNVERIFIED"
    # Existing conservative negative rules: BOTH independent stages must match.
    values=(tls["v"],get["v"])
    return "FAIL" if "FAIL" in values else "PASS" if values==("PASS","PASS") else "UNVERIFIED"

def summarize(rows,baseline=False):
    labels=[name for name,_,_ in TARGETS];expected=set(labels)
    complete=len(rows)==5 and {r["id"] for r in rows}==expected
    def verdict(stage):
        values=[r[stage]["v"] for r in rows]
        if baseline:return "BASELINE_OBS_EXPECTED" if complete and all(v=="PASS" for v in values) else "UNVERIFIED"
        return "FAIL" if "FAIL" in values else "PASS" if complete and all(v=="PASS" for v in values) else "UNVERIFIED"
    tls=verdict("tls");get=verdict("get")
    uncertain=any(r["tls"].get("cleanup_unknown") or r["get"].get("close_unknown") for r in rows)
    by_id={row["id"]:row for row in rows}
    combined={name:combined_verdict(by_id[name],baseline) if name in by_id else "UNVERIFIED" for name in labels}
    guards={name:bool(by_id[name]["tls"].get("cleanup_unknown") or by_id[name]["get"].get("close_unknown")) if name in by_id else False for name in labels}
    if baseline:
        positive_fail=any(combined[name]=="FAIL" for name in ("WWW","BARE","FALLBACK"))
        differs=[name for name in labels if combined[name]!="PASS" or guards[name]]
        if not complete and not differs:differs=["TARGET_SET"]
        result="FAIL" if positive_fail else "BASELINE_OBS_EXPECTED" if complete and not differs else "BASELINE_DIFFERS:"+",".join(differs)
    else:result="FAIL" if "FAIL" in combined.values() else "TLS_OBS_PASS" if complete and all(v=="PASS" for v in combined.values()) and not uncertain else "UNVERIFIED"
    evidence=0 if baseline else sum(r["id"]=="NEGATIVE_1" and r["tls"]["v"]==r["get"]["v"]=="PASS" for r in rows)
    return {"r":result,"tls":tls,"get":get,"combined":combined,"guard_stop":uncertain,"effect_evidence":evidence,"mode":"BASELINE" if baseline else "POST","go":False}

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

if __name__=="__main__": entry('G4_TLS_V003',g4_tls_v003)
